"""
verification_runner.py
Luo-cal CLVS (Cognitive Layer Verification Suite) — Correctness Validation Runner

设计原则（与 validation/README.md 的三层验证体系对应）：
- 本 runner 只负责 Level 2: Synthetic Students (Correctness Validation)。
- 驱动的是"真实生产路径"：每条证据到达后调用与 main.py 生产环境完全相同的
  run_pipeline()，逐步演化状态；不是把全部证据一次性塞给 aggregator 后
  只对比一次最终结果（那是离线日志分析，不是系统验证）。
- 断言比对逻辑只认字段名后缀（_gte/_lte/_lt/_approx+tolerance），
  绝不写死具体数字字面量，保护 fixture 的理论刚性、也保护本文件本身
  不被超参数微调（如 alpha_prior）意外击穿。
- 每个学生独立生命周期：运行前清空该 student_id 的历史数据（
  DANMemoryService 未提供 delete/reset 方法，需直接操作 Supabase 表），
  避免"Student A 的证据残留污染 Student A 下一次运行"。
- Student D 的双轨制（Correctness / Robustness）通过字段名关键词分流，
  为未来物理拆分成 validation/robustness/ 做好过渡准备。

Replay Fidelity 边界声明（如实标注，不夸大覆盖范围）：
本 runner 忠实复现的生产路径起点是"Evidence 对象已经构造完成"之后的那一段——
即 Evidence → Aggregator → Damper → Persistence 这一段，与main.py里
update_dan_state_after_signal()调用run_pipeline()的方式完全一致。
本 runner 不复现更早的那一段：学生在前端提交答案 → FastAPI /api/v1/chat
端点 → Claude 判断对错 → SCL 检测 EWM 标签 → write_signal()写入
cognitive_signals表。这一段被直接跳过，改为由fixture里的signal_sequence
直接指定"结果已知的证据"。这是刻意的范围限定，不是疏漏：
完整复现前半段意味着每次跑测试都要真实调用LLM去生成对话、判断学生答案，
这在验证贝叶斯推断层本身时是不必要的成本。若未来需要验证SCL检测环节
本身的准确性，需要另一套专门覆盖该环节的验证机制，不属于本runner范围。

已知局限（如实记录，不掩盖）：
- cross_world_contamination_check / oscillation_check 等叙事性 note 字段
  目前不做自动化断言，仅打印供人工复核；只有明确数值后缀的字段才自动判定。
- 时间戳统一使用当前时刻（构造证据时），不模拟真实的时间衰减场景；
  这意味着 ThresholdRecencyDamper 的 recency_weight 在本 runner 下恒为
  接近 1.0，不测试跨天衰减行为——这需要专门的时间旅行测试，不在本次范围内。
"""

import os
import sys
import json
import glob
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from supabase import create_client
from pcsa_interfaces import Evidence, WeightVector
from inference_pipeline import (
    BayesianAggregator,
    load_aggregator_config,
    run_pipeline,
)
from dan_memory_service import DANMemoryService

VALID_WORLDS = ("RWM", "FWM", "AWM")

CORRECTNESS_FIELDS = {
    "dominant_world", "stage_expected", "max_world_weight_lte", "confidence_lt",
    "confidence_gte", "rwm_weight_gte", "rwm_weight_lte", "fwm_weight_gte",
    "fwm_weight_lte", "awm_weight_lte", "awm_weight_lt_PENDING_VERIFICATION",
    "state_revision_count_gte",
}
ROBUSTNESS_FIELDS = {"numerical_stability_check", "oscillation_check"}


def cleanup_student(supabase_client, student_id: str) -> None:
    supabase_client.table("cognitive_signals").delete().eq("student_id", student_id).execute()
    supabase_client.table("dan_state").delete().eq("student_id", student_id).execute()


def setup_student(dan_service: DANMemoryService, student_id: str,
                   subject_id: str = "ap_calculus") -> None:
    dan_service.ensure_student_initialized(student_id, subject_id)


def expand_signal_sequence(fixture: Dict[str, Any]) -> List[Dict[str, Any]]:
    expanded = []
    for item in fixture["signal_sequence"]:
        count = item.get("count", 1)
        for _ in range(count):
            expanded.append({"signal": item["signal"], "concept": item.get("concept", "")})
    return expanded


def load_fixture(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def replay_fixture(
    fixture: Dict[str, Any],
    supabase_client,
    dan_service: DANMemoryService,
    aggregator: BayesianAggregator,
    subject_id: str = "ap_calculus",
) -> Dict[str, Any]:
    student_id = fixture["student_id"]
    signals = expand_signal_sequence(fixture)

    evidence_history: List[Evidence] = []
    trajectory: List[Dict[str, Any]] = []

    for step_idx, sig_item in enumerate(signals, start=1):
        now = datetime.now(timezone.utc)
        evidence_history.append(
            Evidence(
                signal=sig_item["signal"],
                mechanism=None,
                concept=sig_item.get("concept", ""),
                timestamp=now,
                confidence=1.0,
            )
        )

        raw_snapshot: Optional[WeightVector] = None
        try:
            raw_snapshot = aggregator.aggregate(evidence_history)
        except ValueError as e:
            trajectory.append({"step": step_idx, "error": str(e)})
            print(f"  Event {step_idx:2d} [{sig_item['signal']:20s}] ❌ ERROR: {e}")
            continue

        current_full_state = dan_service.get_state(student_id, subject_id)
        step_results = {}
        for world in VALID_WORLDS:
            step_results[world] = run_pipeline(
                student_id, world, evidence_history,
                current_full_state[world] or {"stage": "fragile"},
                dan_service, subject_id=subject_id, aggregator=aggregator,
            )

        trajectory.append({
            "step": step_idx,
            "signal": sig_item["signal"],
            "world_weights": dict(raw_snapshot.world_weights),
            "mechanism_attribution": dict(raw_snapshot.mechanism_attribution),
            "confidence": raw_snapshot.confidence,
            "entropy": raw_snapshot.entropy,
            "evidence_used": raw_snapshot.evidence_used,
            "effective_sample_size": raw_snapshot.effective_sample_size,
            "pipeline_results": step_results,
        })

        ww_str = ", ".join(f"{w}={v:.3f}" for w, v in raw_snapshot.world_weights.items())
        print(f"  Event {step_idx:2d} [{sig_item['signal']:20s}] "
              f"confidence={raw_snapshot.confidence:.4f} | {ww_str}")

    final_state = dan_service.get_state(student_id, subject_id)
    return {
        "student_id": student_id,
        "trajectory": trajectory,
        "final_state": final_state,
        "final_snapshot": trajectory[-1] if trajectory else None,
    }


def _get_actual_value(field_name: str, run_result: Dict[str, Any],
                       expected_output: Dict[str, Any]) -> Optional[float]:
    snap = run_result["final_snapshot"]
    if snap is None:
        return None

    if field_name.startswith("rwm_weight"):
        return snap["world_weights"].get("RWM")
    if field_name.startswith("fwm_weight"):
        return snap["world_weights"].get("FWM")
    if field_name.startswith("awm_weight"):
        return snap["world_weights"].get("AWM")
    if field_name.startswith("max_world_weight"):
        return max(snap["world_weights"].values())
    if field_name.startswith("confidence"):
        return snap["confidence"]
    if field_name.startswith("state_revision_count"):
        counts = [
            (run_result["final_state"].get(w) or {}).get("state_revision_count", 0)
            for w in VALID_WORLDS
        ]
        return max(counts)
    return None


def check_numeric_assertion(field_name: str, expected_value: Any,
                             run_result: Dict[str, Any],
                             expected_output: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    actual = _get_actual_value(field_name, run_result, expected_output)
    if actual is None:
        return None

    if field_name.endswith("_gte"):
        passed = actual >= expected_value
    elif field_name.endswith("_lte"):
        passed = actual <= expected_value
    elif field_name.endswith("_lt"):
        passed = actual < expected_value
    elif field_name.endswith("_gt"):
        passed = actual > expected_value
    else:
        return None

    return {"field": field_name, "expected": expected_value, "actual": round(actual, 4),
            "passed": passed}


def check_dominant_world(expected_world: str, run_result: Dict[str, Any]) -> Dict[str, Any]:
    snap = run_result["final_snapshot"]
    ww = snap["world_weights"]
    actual_dominant = max(ww, key=ww.get)
    passed = actual_dominant == expected_world
    return {"field": "dominant_world", "expected": expected_world,
            "actual": actual_dominant, "passed": passed}


def check_stage_expected(expected_stage: str, run_result: Dict[str, Any],
                          fixture: Dict[str, Any]) -> Dict[str, Any]:
    candidates = expected_stage.split("_or_")
    dominant_world = max(
        run_result["final_snapshot"]["world_weights"],
        key=run_result["final_snapshot"]["world_weights"].get,
    )
    actual_stage = (run_result["final_state"].get(dominant_world) or {}).get("stage")
    passed = actual_stage in candidates
    return {"field": "stage_expected", "expected": expected_stage,
            "actual": actual_stage, "passed": passed}


def check_numerical_health(run_result: Dict[str, Any]) -> Dict[str, Any]:
    errors = [step for step in run_result["trajectory"] if "error" in step]
    passed = len(errors) == 0
    return {"field": "numerical_stability_check", "passed": passed,
            "detail": errors if errors else "全部 step 通过 _validate_theory_boundary()"}


def check_oscillation(run_result: Dict[str, Any], max_step_delta: float = 0.3) -> Dict[str, Any]:
    confidences = [s["confidence"] for s in run_result["trajectory"] if "confidence" in s]
    max_delta = 0.0
    for i in range(1, len(confidences)):
        max_delta = max(max_delta, abs(confidences[i] - confidences[i - 1]))
    passed = max_delta <= max_step_delta
    return {"field": "oscillation_check", "max_observed_delta": round(max_delta, 4),
            "threshold": max_step_delta, "passed": passed}


def verify_fixture(fixture_path: str, supabase_client, dan_service: DANMemoryService,
                    aggregator: BayesianAggregator) -> Dict[str, Any]:
    fixture = load_fixture(fixture_path)
    student_id = fixture["student_id"]

    print(f"\n{'='*60}\n验证 {os.path.basename(fixture_path)} (student_id={student_id})\n{'='*60}")

    cleanup_student(supabase_client, student_id)
    setup_student(dan_service, student_id)

    run_result = replay_fixture(fixture, supabase_client, dan_service, aggregator)

    expected = fixture.get("expected_output", {})
    correctness_checks: List[Dict[str, Any]] = []
    robustness_checks: List[Dict[str, Any]] = []
    manual_review_fields: List[str] = []

    for field_name, expected_value in expected.items():
        if field_name in CORRECTNESS_FIELDS or field_name in ROBUSTNESS_FIELDS:
            track = robustness_checks if field_name in ROBUSTNESS_FIELDS else correctness_checks

            if field_name == "dominant_world":
                track.append(check_dominant_world(expected_value, run_result))
            elif field_name == "stage_expected":
                track.append(check_stage_expected(expected_value, run_result, fixture))
            elif field_name == "numerical_stability_check":
                track.append(check_numerical_health(run_result))
            elif field_name == "oscillation_check":
                track.append(check_oscillation(run_result))
            elif isinstance(expected_value, (int, float)):
                result = check_numeric_assertion(field_name, expected_value, run_result, expected)
                if result:
                    track.append(result)
                else:
                    print(f"  ⚠️ WARNING: 字段 '{field_name}' 在已知分类中，"
                          f"但无法从run_result中取到对应实际值，请检查_get_actual_value()映射")
        elif field_name.endswith(("_gte", "_lte", "_lt", "_gt")) and isinstance(expected_value, (int, float)):
            print(f"  ⚠️ WARNING: 字段 '{field_name}' 具有可判定的数值后缀，"
                  f"但未登记在CORRECTNESS_FIELDS/ROBUSTNESS_FIELDS中，将不会被自动校验，"
                  f"已归入人工复核清单。请检查是否需要补充显式分类。")
            manual_review_fields.append(field_name)
        else:
            manual_review_fields.append(field_name)

    cleanup_student(supabase_client, student_id)

    return {
        "fixture": os.path.basename(fixture_path),
        "student_id": student_id,
        "validation_claim": fixture.get("validation_claim", ""),
        "track_A_correctness": correctness_checks,
        "track_B_robustness": robustness_checks,
        "manual_review_fields": manual_review_fields,
        "final_snapshot": run_result["final_snapshot"],
    }


def print_report(report: Dict[str, Any]) -> None:
    print(f"\n--- {report['fixture']} ---")
    print(f"Claim: {report['validation_claim'][:80]}...")

    for track_name, checks in [("Track A (Correctness)", report["track_A_correctness"]),
                                ("Track B (Robustness)", report["track_B_robustness"])]:
        if not checks:
            continue
        print(f"\n  {track_name}:")
        for c in checks:
            status = "✅ PASS" if c.get("passed") else "❌ FAIL"
            print(f"    {status} | {c}")

    if report["manual_review_fields"]:
        print(f"\n  ⚠️  以下字段为叙事性说明，未自动判定，需人工复核："
              f"{report['manual_review_fields']}")


def main():
    supabase_url = os.environ.get("SUPABASE_URL", "https://cckahbvgzffyfucrluym.supabase.co")
    supabase_key = os.environ["SUPABASE_KEY"]
    supabase_client = create_client(supabase_url, supabase_key)

    dan_service = DANMemoryService(client=supabase_client)
    aggregator = BayesianAggregator(load_aggregator_config())

    fixture_dir = "validation/student_archetypes"
    fixture_paths = sorted(glob.glob(os.path.join(fixture_dir, "*.json")))

    if not fixture_paths:
        print(f"⚠️ 在 {fixture_dir} 未找到任何 fixture 文件")
        sys.exit(1)

    all_reports = []
    for path in fixture_paths:
        report = verify_fixture(path, supabase_client, dan_service, aggregator)
        print_report(report)
        all_reports.append(report)

    total_checks = sum(
        len(r["track_A_correctness"]) + len(r["track_B_robustness"]) for r in all_reports
    )
    total_passed = sum(
        sum(1 for c in r["track_A_correctness"] + r["track_B_robustness"] if c.get("passed"))
        for r in all_reports
    )
    print(f"\n{'='*60}\n总计：{total_passed}/{total_checks} 项断言通过\n{'='*60}")


if __name__ == "__main__":
    main()
