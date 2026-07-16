"""
verification_runner.py
CLVS (Cognitive Layer Verification Suite) — Canonical Profile Replay Runner

Replay Fidelity 原则：每一次 Tick 的信号更新都通过真实的
inference_pipeline.BayesianAggregator + promotion_policy.PromotionPolicy
调用链完成，不走任何捷径或 mock。

已确认事项（2026-07-15 与 Yongwu 核实）：
  - `_validate_theory_boundary()` 在仓库中不存在，本 runner 不依赖它、
    也不假装它存在。仓库中已有的回归资产命名习惯是按 ADR 编号
    （例如 `validation/regression/ADR008_reflection.json`），本次验证
    对应 ADR-012，产出资产应命名为
    `validation/regression/ADR012_promotion_policy.json`，与既有习惯对齐。

已知记录、非违规的观察项（不触发 FAIL，仅记录）：
  - Student D 在 fragile<->emerging 之间会有短暂振荡，这是设计上刻意
    不加滞回保护的结果（ADR-012 讨论：stable 是"郑重宣布"需要锁存，
    fragile<->emerging 是"战术级试探"，允许高灵敏度浮动）。
  - 当前 PromotionPolicy 实现中，窗口未填满前（前 N-1 轮）一律强制判定
    为 fragile，不会提前显示 emerging，即使这几轮 dominant_world 已经
    高度一致（例如 Student A 前 4 轮）。2026-07-15 与 Yongwu 确认：暂不
    急于修改，留待 Dashboard UX 需求明确后再评估，本版本如实记录该现象，
    不视为 bug。
"""

import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inference_pipeline import BayesianAggregator
from pcsa_interfaces import Evidence
from promotion_policy import PromotionPolicy


# ------------------------------------------------------------------
# Canonical Fixtures (verbatim from validation/student_archetypes/)
# ------------------------------------------------------------------
CANONICAL_PROFILES = {
    "SYN_A_REPRESENTATION": {
        "profile_name": "Representation Dominant Student",
        "signal_sequence": [
            {"order": 1, "signal": "BOUNDS_TRAP", "concept": "5.4"},
            {"order": 2, "signal": "BOUNDS_TRAP", "concept": "5.4"},
            {"order": 3, "signal": "PRE_SUBSTITUTION", "concept": "4.3"},
            {"order": 4, "signal": "BOUNDS_TRAP", "concept": "8.1"},
            {"order": 5, "signal": "BOUNDS_TRAP", "concept": "5.4"},
        ],
        "expected": {
            "final_dominant_world": "RWM",
            "rwm_weight_gte": 0.80,
            "fwm_weight_lte": 0.15,
            "awm_weight_lte": 0.15,
            "stage_expected": "stable",
        },
    },
    "SYN_B_FLOW": {
        "profile_name": "Flow Thinker",
        "signal_sequence": [
            {"order": 1, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 2, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 3, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 4, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 5, "signal": "EWM_B1C", "concept": "B1"},
        ],
        "expected": {
            "final_dominant_world": "FWM",
            "fwm_weight_gte": 0.75,
            "rwm_weight_lte": 0.15,
            "awm_weight_lte": 0.15,
            "stage_expected": "stable",
        },
    },
    "SYN_C_MIXED": {
        "profile_name": "Mechanism Interweaving Student",
        "signal_sequence": [
            {"order": 1, "signal": "WASHER_TRAP", "concept": "6.2"},
            {"order": 2, "signal": "BOUNDS_TRAP", "concept": "5.4"},
            {"order": 3, "signal": "CHAIN_FRACTURE", "concept": "8.1"},
            {"order": 4, "signal": "BOUNDS_TRAP", "concept": "5.4"},
            {"order": 5, "signal": "WASHER_TRAP", "concept": "6.2"},
            {"order": 6, "signal": "CHAIN_FRACTURE", "concept": "3.5"},
            {"order": 7, "signal": "BOUNDS_TRAP", "concept": "8.1"},
        ],
        "expected": {
            "world_weights_expected": {"RWM": 0.60, "FWM": 0.26, "AWM": 0.14},
            "world_weights_tolerance": 0.05,
            "confidence_expected": 0.133,
            "confidence_tolerance": 0.03,
            "stage_expected_in": {"fragile", "emerging"},  # 绝不能是 stable
        },
    },
    "SYN_D_UNCERTAIN": {
        "profile_name": "Uncertainty Student (Chaos)",
        "signal_sequence": [
            {"order": 1, "signal": "BOUNDS_TRAP", "concept": "5.4"},
            {"order": 2, "signal": "IVT_MVT_CONFUSION", "concept": "4.2"},
            {"order": 3, "signal": "ABSOLUTE_VALUE", "concept": "7.2"},
            {"order": 4, "signal": "WASHER_TRAP", "concept": "6.2"},
            {"order": 5, "signal": "PRE_SUBSTITUTION", "concept": "4.3"},
            {"order": 6, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 7, "signal": "CHAIN_FRACTURE", "concept": "3.5"},
            {"order": 8, "signal": "IVT_MVT_CONFUSION", "concept": "4.2"},
            {"order": 9, "signal": "BOUNDS_TRAP", "concept": "5.4"},
            {"order": 10, "signal": "WASHER_TRAP", "concept": "6.2"},
        ],
        "expected": {
            "max_world_weight_lte": 0.55,
            "confidence_lt": 0.2,
            "stage_expected_in": {"fragile", "emerging"},  # 绝不能是 stable
        },
    },
    "SYN_E_RECOVERY": {
        "profile_name": "Recovery Student (Representation Overcome, Flow Emerges)",
        "requires_dual_scale": True,  # ADR-013：必须用 aggregate_dual_scale 的 recent 视图
        "recent_n": 5,
        "signal_sequence": [
            {"order": 1, "signal": "BOUNDS_TRAP", "concept": "5.4"},
            {"order": 2, "signal": "BOUNDS_TRAP", "concept": "5.4"},
            {"order": 3, "signal": "BOUNDS_TRAP", "concept": "5.4"},
            {"order": 4, "signal": "BOUNDS_TRAP", "concept": "5.4"},
            {"order": 5, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 6, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 7, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 8, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 9, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 10, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 11, "signal": "EWM_B1C", "concept": "B1"},
            {"order": 12, "signal": "EWM_B1C", "concept": "B1"},
        ],
        "expected": {
            "transitional_dip_between_ticks": (5, 11),  # 5-11轮之间必须出现过非stable的过渡态
            "final_locked_world": "FWM",
            "recent_world_weights_expected": {"RWM": 0.142857, "FWM": 0.821429, "AWM": 0.035714},
            "recent_world_weights_tolerance": 0.01,
            "recent_confidence_expected": 0.4096,
            "recent_confidence_tolerance": 0.01,
            "recovery_tick_lte": 11,  # 真正稳定在FWM不应晚于第11轮（回归哨兵，防止未来变慢却没人发现）
            "stage_expected": "stable",
        },
    },
}


def build_evidence(signal_sequence, base_time):
    out = []
    for i, item in enumerate(signal_sequence):
        out.append(Evidence(
            signal=item["signal"],
            concept=item.get("concept", ""),
            timestamp=base_time + timedelta(minutes=i),
        ))
    return out


def replay_profile(student_id, profile):
    """
    Replay Fidelity: 每一轮都通过真实的 BayesianAggregator 和
    PromotionPolicy.update() 完整走一遍，不做任何捷径。

    ADR-013 支持：若 fixture 标记 requires_dual_scale=True，改用
    aggregate_dual_scale()，Promotion Policy 消费 recent（近期视图）而非
    cumulative（长线累积视图）；ticks 里同时记录两者，供审计表和回归基线
    使用，但断言判定只针对 recent（因为那才是 Promotion 实际消费的字段）。
    """
    base_time = datetime.now(timezone.utc)
    evidence = build_evidence(profile["signal_sequence"], base_time)

    aggregator = BayesianAggregator()
    policy = PromotionPolicy()

    use_dual_scale = profile.get("requires_dual_scale", False)
    recent_n = profile.get("recent_n", 5)

    ticks = []
    for i in range(1, len(evidence) + 1):
        if use_dual_scale:
            cumulative_wv, recent_wv = aggregator.aggregate_dual_scale(evidence[:i], recent_n=recent_n)
            promotion_input_wv = recent_wv
        else:
            cumulative_wv = aggregator.aggregate(evidence[:i])
            recent_wv = None
            promotion_input_wv = cumulative_wv

        stage = policy.update(promotion_input_wv.world_weights)
        dominant_world = max(promotion_input_wv.world_weights.items(), key=lambda kv: kv[1])
        ticks.append({
            "tick": i,
            "signal": profile["signal_sequence"][i - 1]["signal"],
            "world_weights": promotion_input_wv.world_weights,  # Promotion 实际消费的视图
            "cumulative_world_weights": cumulative_wv.world_weights if use_dual_scale else None,
            "dominant_world": dominant_world[0],
            "dominant_weight": dominant_world[1],
            "confidence": promotion_input_wv.confidence,
            "entropy": promotion_input_wv.entropy,
            "effective_sample_size": promotion_input_wv.effective_sample_size,
            "stage": stage,
            "locked_world": policy._locked_world,
            "state_revision": None,  # 见文件末尾说明：本 runner 不追踪 dan_state 的
                                      # revision 计数，那是 dan_memory_service.py 的
                                      # 职责，超出本次 Promotion Policy 验证范围
        })
    return ticks


def check_expectations(student_id, profile, ticks):
    """
    对照 fixture 的 expected 字段做断言检查，返回 (passed: bool, findings: list[str])
    """
    findings = []
    passed = True
    final = ticks[-1]
    expected = profile["expected"]

    if "rwm_weight_gte" in expected:
        actual = final["world_weights"].get("RWM", 0.0)
        ok = actual >= expected["rwm_weight_gte"]
        passed &= ok
        findings.append(f"RWM final weight {actual:.4f} >= {expected['rwm_weight_gte']}: {'PASS' if ok else 'FAIL'}")

    if "fwm_weight_gte" in expected:
        actual = final["world_weights"].get("FWM", 0.0)
        ok = actual >= expected["fwm_weight_gte"]
        passed &= ok
        findings.append(f"FWM final weight {actual:.4f} >= {expected['fwm_weight_gte']}: {'PASS' if ok else 'FAIL'}")

    if "world_weights_expected" in expected:
        tol = expected.get("world_weights_tolerance", 0.05)
        for world, exp_val in expected["world_weights_expected"].items():
            actual = final["world_weights"].get(world, 0.0)
            ok = abs(actual - exp_val) <= tol
            passed &= ok
            findings.append(f"{world} final weight {actual:.4f} within {tol} of {exp_val}: {'PASS' if ok else 'FAIL'}")

    if "confidence_expected" in expected:
        tol = expected.get("confidence_tolerance", 0.03)
        actual = final["confidence"]
        ok = abs(actual - expected["confidence_expected"]) <= tol
        passed &= ok
        findings.append(f"confidence {actual:.4f} within {tol} of {expected['confidence_expected']}: {'PASS' if ok else 'FAIL'}")

    if "confidence_lt" in expected:
        actual = final["confidence"]
        ok = actual < expected["confidence_lt"]
        passed &= ok
        findings.append(f"confidence {actual:.4f} < {expected['confidence_lt']}: {'PASS' if ok else 'FAIL'}")

    if "max_world_weight_lte" in expected:
        actual = max(final["world_weights"].values())
        ok = actual <= expected["max_world_weight_lte"]
        passed &= ok
        findings.append(f"max world weight {actual:.4f} <= {expected['max_world_weight_lte']}: {'PASS' if ok else 'FAIL'}")

    if "stage_expected" in expected:
        ok = final["stage"] == expected["stage_expected"]
        passed &= ok
        findings.append(f"final stage '{final['stage']}' == '{expected['stage_expected']}': {'PASS' if ok else 'FAIL'}")

    if "stage_expected_in" in expected:
        ok = final["stage"] in expected["stage_expected_in"]
        passed &= ok
        findings.append(f"final stage '{final['stage']}' in {expected['stage_expected_in']}: {'PASS' if ok else 'FAIL'}")
        # 硬约束：C/D 绝不能是 stable，单独再断言一次，即使 stage_expected_in 恰好包含它
        never_stable_ok = final["stage"] != "stable"
        passed &= never_stable_ok
        findings.append(f"never reaches 'stable': {'PASS' if never_stable_ok else 'FAIL (CRITICAL)'}")

    if "final_locked_world" in expected:
        actual = final.get("locked_world")
        ok = actual == expected["final_locked_world"]
        passed &= ok
        findings.append(f"final locked_world '{actual}' == '{expected['final_locked_world']}': {'PASS' if ok else 'FAIL'}")

    if "recent_world_weights_expected" in expected:
        tol = expected.get("recent_world_weights_tolerance", 0.01)
        for world, exp_val in expected["recent_world_weights_expected"].items():
            actual = final["world_weights"].get(world, 0.0)
            ok = abs(actual - exp_val) <= tol
            passed &= ok
            findings.append(f"recent {world} final weight {actual:.6f} within {tol} of {exp_val}: {'PASS' if ok else 'FAIL'}")

    if "recent_confidence_expected" in expected:
        tol = expected.get("recent_confidence_tolerance", 0.01)
        actual = final["confidence"]
        ok = abs(actual - expected["recent_confidence_expected"]) <= tol
        passed &= ok
        findings.append(f"recent confidence {actual:.4f} within {tol} of {expected['recent_confidence_expected']}: {'PASS' if ok else 'FAIL'}")

    if "transitional_dip_between_ticks" in expected:
        start, end = expected["transitional_dip_between_ticks"]
        window = [t for t in ticks if start <= t["tick"] <= end]
        has_dip = any(t["stage"] in ("fragile", "emerging") for t in window)
        passed &= has_dip
        findings.append(
            f"transitional dip (fragile/emerging) present between tick {start}-{end}: "
            f"{'PASS' if has_dip else 'FAIL (CRITICAL — 说明旧锁定被静默替换，未经过正确的解锁-重新晋升流程)'}"
        )

    if "recovery_tick_lte" in expected:
        # 找到"最终锁定的 world"第一次稳定下来的 tick，且此后一直保持
        target_world = expected.get("final_locked_world")
        recovery_tick = None
        if target_world:
            for t in ticks:
                if t["stage"] == "stable" and t["locked_world"] == target_world:
                    # 确认此后所有 tick 都保持在这个 world 上的 stable（不是昙花一现）
                    remaining = [t2 for t2 in ticks if t2["tick"] >= t["tick"]]
                    if all(t2["stage"] == "stable" and t2["locked_world"] == target_world for t2 in remaining):
                        recovery_tick = t["tick"]
                        break
        ok = recovery_tick is not None and recovery_tick <= expected["recovery_tick_lte"]
        passed &= ok
        findings.append(
            f"genuine recovery tick = {recovery_tick} <= {expected['recovery_tick_lte']}: "
            f"{'PASS' if ok else 'FAIL (回归哨兵：复苏变慢了，需要检查窗口逻辑是否被意外改动)'}"
        )

    return passed, findings


def render_audit_table(student_id, profile, ticks, passed):
    status = "PASS" if passed else "FAIL"
    width = 72
    print("=" * width)
    print(f"CLVS Verification Run: {student_id} ({status})")
    print("=" * width)
    print(f"{'Tick':<5}{'Emitted Signal':<20}{'Dominant World':<18}{'Conf':<8}{'Stage':<10}")
    print("-" * width)
    prev_stage = None
    for t in ticks:
        marker = ""
        if prev_stage is not None and t["stage"] != prev_stage:
            marker = "  <-- transition"
        if t["tick"] == len(ticks):
            marker = f"  <-- {status}"
        print(
            f"{t['tick']:<5}{t['signal']:<20}"
            f"{t['dominant_world']} ({t['dominant_weight']:.3f}){'':<3}"
            f"{t['confidence']:.3f}   {t['stage']:<10}{marker}"
        )
        prev_stage = t["stage"]
    print("=" * width)
    print()


def export_baseline_json(all_results, path):
    """
    导出本次运行的完整轨迹与断言结果为 JSON，命名习惯对齐仓库既有的
    validation/regression/ADR008_reflection.json，本文件对应产出
    validation/regression/ADR012_promotion_policy.json。

    2026-07-16 更新：加入 SYN_E_RECOVERY（ADR-013 双时间尺度机制验证），
    文件名保持不变（仍以 ADR012 命名），因为 A-E 五组 Canonical Profile
    由同一个 verification_runner 一次性跑出、一起 diff，拆成两个文件反而
    增加对比成本；adr_reference 字段改为同时标注 ADR-012 与 ADR-013。
    """
    import json

    payload = {
        "adr_reference": "ADR-012: Diagnosis-Promotion 分层解耦 (Profiles A-D) "
                          "+ ADR-013: Diagnostic State 时间尺度分层 (Profile E)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "confidence_formula": {
            "definition": "confidence = evidence_factor * concentration_factor",
            "evidence_factor": "1 - 1/(1+effective_sample_size)",
            "concentration_factor": "1 - entropy/H_MAX, H_MAX = ln(3)",
            "entropy": "-sum(p*ln(p)) over world_weights, p>0",
            "source": "BAYESIAN_AGGREGATOR_SPEC_v0.2.md / inference_pipeline.py::BayesianAggregator._aggregate()",
            "note": "DeepSeek 评阅（2026-07-15）指出此前记录未定义 confidence 公式，"
                     "已补充定义并逐一手工反推验证四组 Profile 数值自洽（entropy/"
                     "effective_sample_size 见各 profile 的 ticks 明细）。",
        },
        "promotion_policy_config": {
            "window_size": 5,
            "min_consistent": 4,
            "margin": 0.15,
            "theta": 0.55,
            "demote_below": 3,
        },
        "known_observations": [
            {
                "student_id": "SYN_D_UNCERTAIN",
                "observation": "fragile<->emerging 短暂振荡（第5-8轮附近），未违反'绝不进入stable'的硬约束，设计上刻意不加滞回保护。",
                "is_violation": False,
            },
            {
                "student_id": "SYN_A_REPRESENTATION",
                "observation": "窗口未填满前（前4轮）强制显示fragile，不提前显示emerging，即使dominant_world已高度一致。2026-07-15确认暂不修改，留待Dashboard UX需求明确后再评估。",
                "is_violation": False,
            },
            {
                "student_id": "SYN_E_RECOVERY",
                "observation": "第5-8轮短暂'假稳定'锁定在旧世界(RWM)，第9-10轮才解锁进入emerging，第11轮才真正锁定新世界(FWM)——不是纸面推演设想的第6-8轮。根因是Diagnosis层recent窗口与Promotion层持续性窗口首尾相接产生的双重延迟，已记录进ADR-013，不视为bug，但作为回归哨兵（recovery_tick_lte=11）持续追踪，防止未来改动导致复苏进一步变慢却无人察觉。",
                "is_violation": False,
            },
        ],
        "profiles": [],
    }

    for student_id, ticks, passed, findings in all_results:
        profile_entry = {
            "student_id": student_id,
            "passed": passed,
            "findings": findings,
            "ticks": [
                {
                    "tick": t["tick"],
                    "signal": t["signal"],
                    "world_weights": {k: round(v, 6) for k, v in t["world_weights"].items()},
                    "cumulative_world_weights": (
                        {k: round(v, 6) for k, v in t["cumulative_world_weights"].items()}
                        if t.get("cumulative_world_weights") else None
                    ),
                    "dominant_world": t["dominant_world"],
                    "confidence": round(t["confidence"], 6),
                    "entropy": t["entropy"],
                    "effective_sample_size": t["effective_sample_size"],
                    "stage": t["stage"],
                    "locked_world": t.get("locked_world"),
                }
                for t in ticks
            ],
        }
        payload["profiles"].append(profile_entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return path


def main():
    overall_pass = True
    summary_rows = []
    all_results = []

    for student_id, profile in CANONICAL_PROFILES.items():
        ticks = replay_profile(student_id, profile)
        passed, findings = check_expectations(student_id, profile, ticks)
        render_audit_table(student_id, profile, ticks, passed)

        print(f"  断言明细 ({student_id}):")
        for f in findings:
            print(f"    - {f}")
        print()

        overall_pass &= passed
        all_results.append((student_id, ticks, passed, findings))

        # 找"最终持续保持到底"的 stable 起点，而非任意第一次出现的 stable——
        # 后者会把 Student E 第5轮的假稳定(RWM)误报成复苏点，而真正的复苏在第11轮(FWM)
        final_stage = ticks[-1]["stage"]
        stable_tick = None
        if final_stage == "stable":
            final_locked_world = ticks[-1].get("locked_world")
            for t in ticks:
                if t["stage"] == "stable" and t.get("locked_world") == final_locked_world:
                    remaining = [t2 for t2 in ticks if t2["tick"] >= t["tick"]]
                    if all(t2["stage"] == "stable" and t2.get("locked_world") == final_locked_world for t2 in remaining):
                        stable_tick = t["tick"]
                        break
        summary_rows.append({
            "student_id": student_id,
            "passed": passed,
            "final_stage": ticks[-1]["stage"],
            "stable_at_tick": stable_tick,
        })

    print("=" * 72)
    print("CLVS Summary")
    print("=" * 72)
    for row in summary_rows:
        stable_note = f"stable@tick{row['stable_at_tick']}" if row["stable_at_tick"] else "never stable"
        print(f"  {row['student_id']:<24} {'PASS' if row['passed'] else 'FAIL':<6} "
              f"final={row['final_stage']:<10} ({stable_note})")
    print("=" * 72)
    print(f"OVERALL: {'ALL PASS' if overall_pass else 'FAIL — see above'}")

    return overall_pass, all_results


if __name__ == "__main__":
    result, all_results = main()

    baseline_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "regression",
        "ADR012_promotion_policy.json",
    )
    os.makedirs(os.path.dirname(baseline_path), exist_ok=True)
    export_baseline_json(all_results, baseline_path)
    print(f"\n回归基线已导出: {baseline_path}")

    sys.exit(0 if result else 1)
