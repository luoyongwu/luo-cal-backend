"""
verification_runner.py
（文件名不变——2026-07-16 THEORY_CHANGELOG.md 已明确记录本文件为"根目录生产级
验证器"，结论是"不受影响，保留，不需要删除或修改"。2026-07-29 曾一度错误地
计划把本文件改名为 clvs_sandbox_runner.py，该改名决定已撤销：那条 07-16 记录
里真正被考虑改名的是另一个文件 validation/verification_runner.py（沙盒版，
写死 CANONICAL_PROFILES 字典、不接数据库），不是本文件。见文件末尾"命名澄清"。）

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

=== ADR-016 阶段三更新（2026-07-29） ===
新增对 SYN_E_RECOVERY 这类 requires_dual_scale=true fixture 的验证支持——
对应 2026-07-16 THEORY_CHANGELOG.md 记录里明确列出的后续待办第2、3项：

1. `replay_fixture()` 现在会读取 fixture 的 `requires_dual_scale` 字段，
   若为 true，调用 `run_pipeline()` 时显式传 `use_promotion_policy=True`
   （此前遗漏这一步，会导致要求双时间尺度机制的 fixture 静默走旧的
   `decide_stage()` 路径，测不到它本该测的东西——这正是 07-16 记录里
   预见到的"若现在直接运行根目录的生产级 runner，Student A/B 大概率仍会
   停留在 fragile"这个问题的延伸：SYN_E_RECOVERY 面临的是同一类风险）。
2. 每轮 replay 后新增记录 `promotion_state_snapshot`（此前 trajectory
   只记录 `pipeline_results` 里的 old_stage/new_stage，完全没有留存
   `promotion_state`，导致 `recovery_tick` 这类需要逐轮追踪 `locked_world`
   变化轨迹的验证项根本无法计算）。
3. 新增 `check_final_locked_world()` / `check_recovery_tick()` 两个检查
   函数，并把 `final_locked_world` / `recovery_tick` 注册进
   `CORRECTNESS_FIELDS`——对应 07-16 记录里"决定 SYN_E_RECOVERY.json 的
   字段是否要改写为生产级 runner 认识的后缀格式，还是给生产级 runner
   补充一个能识别 dual-scale 特殊断言的分支"这一待办，采用的是后一种方案
   （补充专门的断言分支，而非强改 fixture 字段名去凑后缀格式）。

**关于 promotion_state_snapshot 取哪个 world 的说明（已过时，见下方 Route A 更新）**：
本节保留作历史记录——阶段三上线时，`run_pipeline()` 对 RWM/FWM/AWM 三个
`cognitive_world` 分别调用，但三次调用喂给 `PromotionPolicy.update()` 的
`world_weights` 都来自同一次 `aggregate_dual_scale()` 结果，因此三个
world 各自的 `PromotionPolicy` 实例会解出完全相同的判断，本 runner 当时
固定取 "FWM" 通道的 promotion_state 作为代表快照。这个"三通道天然一致"
的假设后来被 ADR-016 v8 认定为需要修正的架构缺口（`dan_state.FWM.stage
="stable"` 但真正锁定的 `locked_world` 其实是 RWM 这类语义歧义），已在
下方 Route A 更新里被移除，不再依赖这个假设。

=== Route A 更新（2026-07-31，ADR-016 v8/§12）===
`stage`/`locked_world`/`promotion_state` 从"三个 world 通道各自持有"
改为"学生级别的全局字段"，存放在独立的 `dan_global_state` 表（见
`dan_memory_service.py::get_global_state()`/`write_global_state()`）。
相应改动：

1. `replay_fixture()` 现在会在 per-world 诊断循环**之外**，额外调用一次
   `inference_pipeline.update_global_promotion_state()`（每轮 replay 调用
   一次，不是每个 world 各调用一次），并把它的返回结果记录为
   `trajectory` 每一步的 `global_promotion_result` 字段（取代此前的
   `promotion_state_snapshot`，语义从"某个 world 通道恰好读到的快照"
   变成"全局判断本身的直接返回值"）。
2. `check_final_locked_world()` / `check_recovery_tick()` 相应改为读取
   `run_result["final_global_state"]` / `step["global_promotion_result"]`，
   不再从任何单一 world 通道读取。

**已知但本次未处理的相邻缺口**：fixture 里 `final_recent_world_weights`/
`final_recent_confidence` 这类字段搭配了 `_tolerance` 后缀（如
`final_recent_world_weights_tolerance`），暗示需要一种"_approx + tolerance"
的比对机制（模块文档字符串开头也提到了这个设计意图），但
`check_numeric_assertion()` 目前只认 `_gte/_lte/_lt/_gt` 四种后缀，
不认 `_approx`/`_tolerance` 配对。这意味着 SYN_E_RECOVERY 里这两个字段
目前会落入 `manual_review_fields`（人工复核），不会被自动断言。这是一个
真实存在、与本次改动相邻但范围不同的缺口，本次不顺手扩大范围去实现，
留作独立的后续任务。
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
    update_global_promotion_state,
)
from dan_memory_service import DANMemoryService

VALID_WORLDS = ("RWM", "FWM", "AWM")

CORRECTNESS_FIELDS = {
    "dominant_world", "stage_expected", "max_world_weight_lte", "confidence_lt",
    "confidence_gte", "rwm_weight_gte", "rwm_weight_lte", "fwm_weight_gte",
    "fwm_weight_lte", "awm_weight_lte", "awm_weight_lt_PENDING_VERIFICATION",
    "state_revision_count_gte",
    # ADR-016 阶段三新增（2026-07-29）：SYN_E_RECOVERY 验证需要的两个字段
    "final_locked_world", "recovery_tick",
    # ADR-017 §8 Step 3 新增（2026-07-31）：mechanism-level 判定结果验证
    # 用的三个字段。与 final_locked_world 并存但不冲突——final_locked_world
    # 是 ADR-016 时代的字段名（SYN_E_RECOVERY.json 沿用），locked_world 是
    # ADR-017 新 fixture（如 student_F_structural.json）使用的字段名，二者
    # 底层读取的都是 final_global_state["locked_world"]，只是历史沿革下
    # 出现了两个字段名并存的情况，不强行统一以避免破坏已有 fixture。
    "locked_world", "locked_worlds", "locked_mechanism",
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

    # ADR-016 阶段三：requires_dual_scale=true 的 fixture 必须显式走新路径，
    # 否则会静默退回旧的 decide_stage()，测不到 PromotionPolicy 的行为。
    use_promotion_policy = bool(fixture.get("requires_dual_scale", False))

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
                use_promotion_policy=use_promotion_policy,
            )

        # === Route A 更新（2026-07-31，ADR-016 v8/§12）===
        # 此前这里在 per-world 循环结束后固定读 "FWM" 通道的 promotion_state
        # 作为"代表快照"，隐含假设三个通道的判断天然一致——这正是 v8 发现的
        # 语义幻觉的根源。Route A 之后，全局 Promotion 判断只应该被计算
        # 一次，本函数现在显式调用 update_global_promotion_state()（在
        # per-world 循环之外，恰好一次），并记录它的返回结果作为本轮的
        # 全局快照，不再从任何单一 world 通道"顺带"读取。
        global_result = None
        if use_promotion_policy:
            global_result = update_global_promotion_state(
                student_id, evidence_history, dan_service,
                subject_id=subject_id, aggregator=aggregator,
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
            "global_promotion_result": global_result,
        })

        ww_str = ", ".join(f"{w}={v:.3f}" for w, v in raw_snapshot.world_weights.items())
        print(f"  Event {step_idx:2d} [{sig_item['signal']:20s}] "
              f"confidence={raw_snapshot.confidence:.4f} | {ww_str}")

    final_state = dan_service.get_state(student_id, subject_id)
    final_global_state = dan_service.get_global_state(student_id, subject_id) if use_promotion_policy else None
    return {
        "student_id": student_id,
        "trajectory": trajectory,
        "final_state": final_state,
        "final_global_state": final_global_state,
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
    """
    Route A 回归修复（2026-07-31，二次修复）：此前本函数固定读
    run_result["final_state"][dominant_world]["stage"]，即按-world拆三行
    的旧 dan_state.stage 列。但 Route A 之后，只要 fixture 走
    requires_dual_scale=true 路径，run_pipeline() 就不再写这一列（新路径
    下 stage/promotion_state 在 write_state() 调用里始终是 _UNSET 哨兵，
    见 inference_pipeline.py::run_pipeline() 文档字符串），该列永远停留在
    ensure_student_initialized() 打底时的 "fragile"。真正的 stage 判断
    结果只存在于 dan_global_state.stage（run_result["final_global_state"]），
    由 update_global_promotion_state() 写入。

    此前只修复了 A/B fixture 缺失 requires_dual_scale 字段本身（使其正确
    路由进 PromotionPolicy 路径），但遗漏了本函数需要同步改读新字段来源
    这一层——导致 fixture 层面的修复看似"毫无效果"：算法确实换了、权重
    数值也确实变了，但断言检查的仍是一个已被架构性弃用、结构上不会再变化
    的旧字段。这是本次改动记录里如实追加的第二次修复。

    分支逻辑：
      - fixture 标记 requires_dual_scale=true（走新 PromotionPolicy 路径）
        -> 读 final_global_state.stage
      - 否则（走旧 decide_stage() 路径，例如尚未接入 Route A 的历史 fixture）
        -> 保持原有读法，不破坏旧路径的验证能力
    """
    candidates = expected_stage.split("_or_")
    use_promotion_policy = bool(fixture.get("requires_dual_scale", False))

    if use_promotion_policy:
        final_global_state = run_result.get("final_global_state")
        actual_stage = final_global_state.get("stage") if final_global_state else None
    else:
        dominant_world = max(
            run_result["final_snapshot"]["world_weights"],
            key=run_result["final_snapshot"]["world_weights"].get,
        )
        actual_stage = (run_result["final_state"].get(dominant_world) or {}).get("stage")

    passed = actual_stage in candidates
    return {"field": "stage_expected", "expected": expected_stage,
            "actual": actual_stage, "passed": passed}


def check_final_locked_world(expected_world: str, run_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route A 更新（2026-07-31，ADR-016 v8/§12）：检查最终全局
    locked_world 是否等于期望值。此前从某个 world 通道的
    promotion_state 里读（隐含"三通道一致"的假设，这正是 v8 发现的
    语义幻觉根源），现在改为直接读 dan_service.get_global_state() 的
    返回结果（run_result["final_global_state"]，由 replay_fixture()
    在 Route A 之后统一提供）。

    若该 fixture 没有走 use_promotion_policy=True 路径，
    final_global_state 会是 None，此时判定为不通过并如实报告
    actual=None，而不是抛异常掩盖"这个 fixture 根本没启用双时间尺度
    路径"这个更重要的信息。
    """
    final_global_state = run_result.get("final_global_state")
    actual = final_global_state.get("locked_world") if final_global_state else None
    passed = actual == expected_world
    return {"field": "final_locked_world", "expected": expected_world,
            "actual": actual, "passed": passed}


def check_locked_world(expected_world: Optional[str], run_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    ADR-017（§8 Step 3）：检查最终全局 locked_world（单一 world 锁定场景，
    如 "RWM"）。与 check_final_locked_world() 读取的是同一个底层字段
    （final_global_state["locked_world"]），只是注册在不同的 fixture 字段
    名（"locked_world" vs "final_locked_world"）下，供新旧两代 fixture
    各自使用自己习惯的命名，互不干扰。

    expected_world 允许为 None——这对应"这次锁定的是复合 world（如
    StructuralReasoning 场景），locked_world 应为 None，真正的锁定信息在
    locked_worlds 里"这种断言场景（见 student_F_structural.json）。
    """
    final_global_state = run_result.get("final_global_state")
    actual = final_global_state.get("locked_world") if final_global_state else None
    passed = actual == expected_world
    return {"field": "locked_world", "expected": expected_world,
            "actual": actual, "passed": passed}


def check_locked_worlds(expected_worlds: Optional[List[str]], run_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    ADR-017（§8 Step 3）：检查最终全局 locked_worlds（复数，代数封闭的
    world 集合）。比较时忽略顺序——"世界集合"在语义上是无序集合，
    ["FWM","AWM"] 与 ["AWM","FWM"] 应视为相同结果，不应因为
    update_global_promotion_state() 内部字典遍历顺序的实现细节而误判。
    """
    final_global_state = run_result.get("final_global_state")
    actual = final_global_state.get("locked_worlds") if final_global_state else None
    if actual is None and expected_worlds is None:
        passed = True
    elif actual is None or expected_worlds is None:
        passed = False
    else:
        passed = set(actual) == set(expected_worlds)
    return {"field": "locked_worlds", "expected": expected_worlds,
            "actual": actual, "passed": passed}


def check_locked_mechanism(expected_mechanism: Optional[str], run_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    ADR-017（§8 Step 3）：检查最终全局 locked_mechanism（纯溯源字段）。
    """
    final_global_state = run_result.get("final_global_state")
    actual = final_global_state.get("locked_mechanism") if final_global_state else None
    passed = actual == expected_mechanism
    return {"field": "locked_mechanism", "expected": expected_mechanism,
            "actual": actual, "passed": passed}


def check_recovery_tick(expected_tick: int, run_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route A 更新（2026-07-31，ADR-016 v8/§12）：逐轮扫描 trajectory 里的
    global_promotion_result（此前叫 promotion_state_snapshot，取自某个
    world 通道；现在取自每轮 update_global_promotion_state() 的直接返回
    结果，全局唯一，不再有"取哪个 world 通道代表全局"这个问题），找到
    "锁定进入 stable 状态、且该锁定的 locked_world 从此轮起持续保持不变
    直到最后一轮"的最早一轮，作为 recovery_tick 的实际值。

    这个定义刻意排除了早期可能出现的、后来又被解除的锁定（例如
    SYN_E_RECOVERY 里 tick5-8 先锁定 RWM，但 tick9-10 该锁定被正确解除，
    tick5 不应该被误判为"recovery"发生的时刻）——只有持续到 replay 结束
    都没有再变化的锁定，才算真正的"复苏点"。如果 fixture 的
    never_permanently_stuck_check 要求的中间过渡态没有出现，这里也会
    因为"过早的锁定被误认为最终锁定"而给出错误的 actual_tick，间接起到
    交叉验证的作用。
    """
    trajectory = run_result["trajectory"]
    actual_tick = None

    for idx, step in enumerate(trajectory):
        result = step.get("global_promotion_result")
        if not result or result.get("new_stage") != "stable":
            continue

        candidate_world = result.get("locked_world")
        remaining = trajectory[idx:]
        holds_to_end = all(
            (s.get("global_promotion_result") or {}).get("new_stage") == "stable"
            and (s.get("global_promotion_result") or {}).get("locked_world") == candidate_world
            for s in remaining
        )
        if holds_to_end:
            actual_tick = step["step"]
            break

    passed = actual_tick == expected_tick
    return {"field": "recovery_tick", "expected": expected_tick,
            "actual": actual_tick, "passed": passed}


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
            elif field_name == "final_locked_world":
                track.append(check_final_locked_world(expected_value, run_result))
            elif field_name == "recovery_tick":
                track.append(check_recovery_tick(expected_value, run_result))
            elif field_name == "locked_world":
                track.append(check_locked_world(expected_value, run_result))
            elif field_name == "locked_worlds":
                track.append(check_locked_worlds(expected_value, run_result))
            elif field_name == "locked_mechanism":
                track.append(check_locked_mechanism(expected_value, run_result))
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


# ---------------------------------------------------------------------------
# 命名澄清（2026-07-29，见文件顶部说明）
#
# 本文件名保持 verification_runner.py 不变。2026-07-29 曾一度计划把本文件
# 改名为 clvs_sandbox_runner.py，该计划已撤销——依据是 2026-07-16
# theory/THEORY_CHANGELOG.md 里"发现：两套 verification_runner.py 并存"
# 这条记录，明确写着"根目录 verification_runner.py：不受影响，保留，
# 不需要删除或修改"。真正被那条记录考虑过要改名的，是另一个文件
# validation/verification_runner.py（沙盒版，写死 CANONICAL_PROFILES
# 字典、不接数据库），跟本文件是两个完全不同职责的验证器，不要混淆。
#
# 本次（2026-07-29）实际做的是 07-16 记录里列出的后续待办第2、3项：
# 把 PromotionPolicy/aggregate_dual_scale 的验证能力补进本文件（见文件
# 顶部"ADR-016 阶段三更新"），不涉及改名。
# ---------------------------------------------------------------------------

