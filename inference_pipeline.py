"""
inference_pipeline.py
Luo-cal v3.0 PCSA — Phase 2 管道联调 + 贝叶斯聚合器实现

=== ADR-016 更新（2026-07-28）：run_pipeline() 状态化接入 ===
run_pipeline() 现在支持通过一个显式的 feature flag 在"旧逻辑"
（ThresholdRecencyDamper + decide_stage()，行为完全不变）与"新逻辑"
（PromotionPolicy.rehydrate() + aggregate_dual_scale()）之间切换，
两条路径完整保留、互不干扰，具体见 run_pipeline() 与 USE_PROMOTION_POLICY
的说明。这是 ADR-016 阶段四 Rollback Criteria 依赖的 feature flag 机制：
默认关闭（旧逻辑），Level 3 Full Validation 通过后再显式开启。

=== 生产事故复盘（2026-07-28）：fetch_evidence_history() 缺失 ===
本次修改前，main.py 的 `from inference_pipeline import run_pipeline,
fetch_evidence_history` 引用了一个在 inference_pipeline.py 里根本不存在
的函数。这个 ImportError 被 update_dan_state_after_signal() 的
try/except 静默吞掉，导致自生产上线以来 dan_state 从未被真实学生数据
更新过一次（用"学生2"账号实测触发 BOUNDS_TRAP 确认，Railway 运行时
日志：`cannot import name 'fetch_evidence_history' from 'inference_pipeline'`）。
本次已补齐该函数的真实实现（见文件末尾），从 cognitive_signals 表读取
证据历史并转换为 Evidence 对象列表。这也意味着 dan_state 表目前完全
干净，没有历史脏数据需要清理，阶段二的这次改动是它第一次真正运行。

=== ADR-017 更新（2026-07-31，§8 Step 3）：mechanism-level track 接入 ===
update_global_promotion_state() 现在把 mechanism_attribution 一并传给
PromotionPolicy.update()，并把 mechanism-level 判定结果接入整体的
stage/locked_world/locked_worlds/locked_mechanism 输出。详见该函数的
文档字符串与 ADR-017 §5/§6/§8。
"""

import math
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pcsa_interfaces import (
    CognitiveInertiaDamper,
    Evidence,
    EvidenceAggregator,
    WeightVector,
)
from promotion_policy import PromotionPolicy, PromotionPolicyConfig

STAGE_ORDER = ["fragile", "emerging", "stable"]

DEFAULT_AGGREGATOR_CONFIG: Dict[str, Any] = {
    "alpha_prior": 0.5,
    "window_mode": "recent_n",
    "window_size_n": 50,
    "window_days": 90,
}

# ADR-016 feature flag: controls whether run_pipeline() uses the new
# PromotionPolicy-based decision path or the old decide_stage() path.
# Default is OFF (old logic) -- production stays on the proven path until
# Level 3 Full Validation (ADR-016 §4) has passed. This is an explicit,
# environment-variable-driven flag (not a code comment) per the Rollback
# Criteria requirement in ADR-016.
def _promotion_policy_enabled(explicit: Optional[bool] = None) -> bool:
    """
    Resolve whether the new PromotionPolicy path should be used.

    explicit: if the caller passes True/False directly to run_pipeline(),
        that value wins (useful for Smoke/Shadow Run test harnesses that
        need to force one path regardless of the environment).
    Otherwise falls back to the USE_PROMOTION_POLICY environment variable
    (default "false" -- old logic).
    """
    if explicit is not None:
        return explicit
    import os
    return os.environ.get("USE_PROMOTION_POLICY", "false").strip().lower() == "true"


def load_aggregator_config(path: str = "config.yaml") -> Dict[str, Any]:
    try:
        import yaml
    except ImportError:
        warnings.warn("未安装 PyYAML，aggregator 配置使用内置默认值。请 pip install pyyaml。")
        return dict(DEFAULT_AGGREGATOR_CONFIG)

    try:
        with open(path, "r", encoding="utf-8") as f:
            full_config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        warnings.warn(f"未找到配置文件 {path}，aggregator 配置使用内置默认值。")
        return dict(DEFAULT_AGGREGATOR_CONFIG)

    agg_config = full_config.get("aggregator", {})
    merged = dict(DEFAULT_AGGREGATOR_CONFIG)
    merged.update(agg_config)
    return merged


class DummyAggregator(EvidenceAggregator):
    MECHANISM_TO_WORLD = {
        "RepresentationShift": "RWM",
        "SemanticIntegrity": "RWM",
        "ExecutionIntegrity": "RWM",
        "FlowReasoning": "FWM",
        "StructuralReasoning": "FWM",
    }

    def _aggregate(self, evidence_history: List[Evidence]) -> WeightVector:
        world_counts = {"RWM": 0, "FWM": 0, "AWM": 0}
        mechanism_counts: Dict[str, int] = {}

        for ev in evidence_history:
            mech = ev.mechanism or "Unknown"
            mechanism_counts[mech] = mechanism_counts.get(mech, 0) + 1
            world = self.MECHANISM_TO_WORLD.get(mech)
            if world:
                world_counts[world] += 1

        total = sum(world_counts.values())
        if total == 0:
            world_weights = {"RWM": 1 / 3, "FWM": 1 / 3, "AWM": 1 / 3}
            confidence = 0.0
        else:
            world_weights = {w: c / total for w, c in world_counts.items()}
            confidence = min(1.0, total / 10)

        mech_total = sum(mechanism_counts.values())
        if mech_total > 0:
            mechanism_attribution = {m: c / mech_total for m, c in mechanism_counts.items()}
        else:
            mechanism_attribution = {"Unknown": 1.0}

        return WeightVector(
            world_weights=world_weights,
            mechanism_attribution=mechanism_attribution,
            confidence=confidence,
            aggregator_version="dummy_v0_placeholder",
            evidence_used=total,
            effective_sample_size=float(total),
        )


class BayesianAggregator(EvidenceAggregator):
    SIGNAL_TO_MECHANISM: Dict[str, Dict[str, float]] = {
        "BOUNDS_TRAP": {"RepresentationShift": 1.0},
        "PRE_SUBSTITUTION": {"RepresentationShift": 1.0},
        "CHAIN_FRACTURE": {"SemanticIntegrity": 0.7, "FlowReasoning": 0.3},
        "IVT_MVT_CONFUSION": {"StructuralReasoning": 1.0},
        "WASHER_TRAP": {"StructuralReasoning": 1.0},
        "EWM_B1C": {"FlowReasoning": 1.0},
        "ABSOLUTE_VALUE": {"RepresentationShift": 0.5, "SemanticIntegrity": 0.5},
    }

    MECHANISMS = (
        "RepresentationShift",
        "SemanticIntegrity",
        "FlowReasoning",
        "StructuralReasoning",
    )

    MECHANISM_TO_WORLD_DEFAULT: Dict[str, Dict[str, float]] = {
        "RepresentationShift": {"RWM": 1.0},
        "SemanticIntegrity": {"RWM": 1.0},
        "FlowReasoning": {"FWM": 1.0},
        "StructuralReasoning": {"FWM": 0.5, "AWM": 0.5},
    }

    META_FEEDBACK_SIGNALS = frozenset({
        "REFLECTION_VERY_LIKE",
        "REFLECTION_PARTIAL",
        "REFLECTION_NOT_LIKE",
    })

    H_MAX = math.log(3)

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or DEFAULT_AGGREGATOR_CONFIG
        self.alpha_prior: float = config.get("alpha_prior", 0.5)
        self.window_mode: str = config.get("window_mode", "recent_n")
        self.window_size_n: int = config.get("window_size_n", 50)
        self.window_days: float = config.get("window_days", 90)

        if self.window_mode not in ("recent_n", "time_window"):
            raise ValueError(f"window_mode 必须是 'recent_n' 或 'time_window'，得到 {self.window_mode!r}")
        if self.alpha_prior <= 0:
            raise ValueError(f"alpha_prior 必须为正数，得到 {self.alpha_prior}")

    def _apply_window(self, evidence_history: List[Evidence]) -> List[Evidence]:
        if self.window_mode == "recent_n":
            if len(evidence_history) > self.window_size_n:
                return evidence_history[-self.window_size_n:]
            return evidence_history

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self.window_days)
        windowed = []
        for ev in evidence_history:
            ts = ev.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                windowed.append(ev)
        return windowed

    def _aggregate(self, evidence_history: List[Evidence]) -> WeightVector:
        windowed = self._apply_window(evidence_history)

        soft_counts: Dict[str, float] = {m: 0.0 for m in self.MECHANISMS}
        effective_sample_size = 0.0
        evidence_used = 0

        for ev in windowed:
            if ev.signal in self.META_FEEDBACK_SIGNALS:
                continue

            mech_probs = self.SIGNAL_TO_MECHANISM.get(ev.signal)
            if mech_probs is None:
                warnings.warn(
                    f"未知 signal '{ev.signal}'：Signal→Mechanism 矩阵（Spec §2）"
                    f"未定义此信号，该条证据被跳过，不参与本次聚合。"
                )
                continue

            confidence_i = ev.confidence if ev.confidence is not None else 1.0
            for mech, p in mech_probs.items():
                soft_counts[mech] += confidence_i * p

            effective_sample_size += confidence_i
            evidence_used += 1

        alpha = {m: self.alpha_prior + soft_counts[m] for m in self.MECHANISMS}
        alpha_sum = sum(alpha.values())
        mechanism_attribution = {m: alpha[m] / alpha_sum for m in self.MECHANISMS}

        world_weights = {"RWM": 0.0, "FWM": 0.0, "AWM": 0.0}
        for mech, p_mech in mechanism_attribution.items():
            world_dist = self.MECHANISM_TO_WORLD_DEFAULT.get(mech, {})
            for world, p_world in world_dist.items():
                world_weights[world] += p_mech * p_world

        total_w = sum(world_weights.values())
        if total_w > 0:
            world_weights = {w: v / total_w for w, v in world_weights.items()}

        entropy = -sum(p * math.log(p) for p in world_weights.values() if p > 0)
        concentration_factor = 1 - entropy / self.H_MAX
        evidence_factor = 1 - 1 / (1 + effective_sample_size)
        confidence = evidence_factor * concentration_factor
        confidence = max(0.0, min(1.0, confidence))

        return WeightVector(
            world_weights=world_weights,
            mechanism_attribution=mechanism_attribution,
            confidence=confidence,
            aggregator_version="bayesian_v0.2",
            evidence_used=evidence_used,
            effective_sample_size=round(effective_sample_size, 6),
            entropy=round(entropy, 6),
        )


    def aggregate_dual_scale(
        self,
        evidence_history: List[Evidence],
        recent_n: int = 5,
    ) -> "tuple[WeightVector, WeightVector]":
        """
        Diagnostic State 的双时间尺度输出（新增，非 ADR-012 原始范围，见拟议中的
        ADR-013：Diagnostic State 的时间尺度分层）。

        返回 (cumulative, recent) 两个 WeightVector：
          - cumulative：沿用本实例配置的 window_mode/window_size_n（默认 N=50），
            代表长线认知画像，供 Dashboard / dan_state 长期趋势使用，行为与
            aggregate() 完全一致，不受本方法影响。
          - recent：仅取 evidence_history 最近 recent_n 条，用同一套
            _aggregate() 数学逻辑重新计算一次，代表近期认知快照，供
            Promotion Policy 做"近期持续性"判断使用。

        关键设计原则：不新建独立的"影子聚合器"类或实例配置，只是对同一个
        BayesianAggregator 的 _aggregate() 方法用不同的证据切片调用两次。
        这样贝叶斯数学逻辑永远只有一份实现，不会出现两份聚合器代码长期不同步
        的风险（对照 ADR-006 WeightVector 字段文档-代码不同步的教训）。

        参数约定（ADR-013）：recent_n 应从调用方 PromotionPolicy 的
        PromotionPolicyConfig.window_size 读取，不应在调用点硬编码固定值，
        避免 Promotion 的窗口大小调整后 Diagnosis 的近期快照窗口没有同步跟随，
        导致两层窗口隐式失配。本方法签名里 recent_n 默认值 5 仅为探索阶段的
        便利值，正式接入生产管道时调用方需显式传入
        PromotionPolicyConfig.window_size，而非依赖此默认值。

        ADR-016：run_pipeline() 新逻辑路径调用本方法时，会显式传入
        `policy.config.window_size`，不使用此处的默认值 5。
        """
        cumulative = self.aggregate(evidence_history)

        recent_slice = evidence_history[-recent_n:] if len(evidence_history) > recent_n else evidence_history
        recent = self._aggregate(recent_slice)

        return cumulative, recent


class ThresholdRecencyDamper(CognitiveInertiaDamper):
    UPGRADE_MIN_STREAK = 5
    DECAY_HALF_LIFE_DAYS = 14.0

    def dampen(
        self,
        raw_weight_vector: WeightVector,
        evidence_history: List[Evidence],
        current_state: dict,
    ) -> WeightVector:
        now = datetime.now(timezone.utc)
        effective_count = sum(
            1 for ev in evidence_history
            if self._recency_weight(ev.timestamp, now) > 0.1
        )

        if effective_count < self.UPGRADE_MIN_STREAK:
            damped_confidence = raw_weight_vector.confidence * (
                effective_count / self.UPGRADE_MIN_STREAK
            )
        else:
            damped_confidence = raw_weight_vector.confidence

        return WeightVector(
            world_weights=raw_weight_vector.world_weights,
            mechanism_attribution=raw_weight_vector.mechanism_attribution,
            confidence=damped_confidence,
            aggregator_version=raw_weight_vector.aggregator_version,
            evidence_used=raw_weight_vector.evidence_used,
            effective_sample_size=raw_weight_vector.effective_sample_size,
            entropy=raw_weight_vector.entropy,
        )

    def _recency_weight(self, evidence_time: datetime, now: datetime) -> float:
        if evidence_time.tzinfo is None:
            evidence_time = evidence_time.replace(tzinfo=timezone.utc)
        days_elapsed = (now - evidence_time).total_seconds() / 86400
        return 0.5 ** (days_elapsed / self.DECAY_HALF_LIFE_DAYS)


def decide_stage(damped_vector: WeightVector, current_stage: str, cognitive_world: str) -> str:
    """
    OLD decision logic (pre-ADR-012). Kept fully intact and unmodified --
    this is the Rollback Criteria fallback path (ADR-016 §4). Do NOT delete
    or refactor this function; run_pipeline() must be able to fall back to
    it verbatim if USE_PROMOTION_POLICY is off or a rollback is triggered.
    """
    world_share = damped_vector.world_weights.get(cognitive_world, 0.0)
    effective_confidence = damped_vector.confidence * world_share

    idx = STAGE_ORDER.index(current_stage)
    if effective_confidence >= 0.7 and idx < len(STAGE_ORDER) - 1:
        return STAGE_ORDER[idx + 1]
    elif effective_confidence < 0.35 and idx > 0:
        return STAGE_ORDER[idx - 1]
    return current_stage


# ---------------------------------------------------------------------------
# fetch_evidence_history() — 真实实现（2026-07-28 补齐）
#
# 背景：main.py 的 `from inference_pipeline import run_pipeline,
# fetch_evidence_history` 此前因为这个函数完全不存在而持续抛
# ImportError，被 update_dan_state_after_signal() 的 try/except 静默吞掉
# ——也就是说，自生产上线以来，dan_state 从未被真实学生数据更新过一次
# （2026-07-28 用"学生2"账号触发 BOUNDS_TRAP 实测确认，Railway 运行时日志
# 报错：cannot import name 'fetch_evidence_history' from 'inference_pipeline'）。
# 这是一个好消息：意味着 dan_state 表目前完全干净，没有任何"半成品"历史
# 数据需要清理，阶段二这次改动是第一次真正让它运行起来。
#
# 字段映射依据：main.py 的 write_signal() 写入 cognitive_signals 时用的字段
# 是 student_id / concept / signal / timestamp / root_cause / error_level /
# cognitive_dimension / trigger_context / intercept_result / dan_profile。
# Evidence 只需要其中五个：signal, mechanism(<-root_cause), concept,
# timestamp, error_level。
#
# save_reflection() 写入的 REFLECTION_* 行没有 root_cause/error_level 字段
# （对应列会是 NULL）——这里不特殊处理、原样转换成 mechanism=None 的
# Evidence 对象即可，因为 BayesianAggregator._aggregate() 已经在内部用
# META_FEEDBACK_SIGNALS 集合把这类信号过滤掉了，fetch_evidence_history()
# 不需要重复做这件事（保持"只负责取数据、不做业务判断"的单一职责）。
# ---------------------------------------------------------------------------
def fetch_evidence_history(
    supabase_client,
    student_id: str,
    limit: int = 200,
) -> List[Evidence]:
    """
    从 cognitive_signals 表读取某学生的完整证据历史，转换成
    Evidence 对象列表，按 timestamp 升序排列。

    升序排列是必需的，不是随意选择：BayesianAggregator._apply_window()
    的 recent_n 模式用 evidence_history[-N:] 切片"最近 N 条"，这个切片
    逻辑隐含假设列表末尾就是时间上最新的证据；如果这里按降序取数据却不
    倒转顺序，aggregate_dual_scale() 算出的 "recent" 快照会实际上是
    "最早的 N 条"，而不是"最近的 N 条"——一个不会报错、但会悄悄产生
    错误认知诊断结果的严重 bug，值得在这里明确注释以防未来有人不小心
    改成降序查询。

    limit: 单次查询上限。默认 200 留了较大余量：
    BayesianAggregator 默认 window_size_n=50（cumulative 视图用），
    recent_n 通常是 PromotionPolicy 的 window_size=5（rolling 视图用），
    200 条足够覆盖两者的窗口需求，同时避免学生做了几百道题后单次查询
    过大。若某学生证据量长期超过此值，属于"历史很长的老学生"场景，
    不在本次 ADR-016 阶段二范围内优化（见 ADR-016 阶段四 Shadow Run
    风险清单中"真实时间戳 vs 合成时间戳"一项，长历史学生的性能问题
    应放在那一步专门验证）。

    本函数只读 cognitive_signals，不修改、不删除任何记录。
    """
    resp = (
        supabase_client.table("cognitive_signals")
        .select("signal, root_cause, concept, timestamp, error_level")
        .eq("student_id", student_id)
        .order("timestamp", desc=False)
        .limit(limit)
        .execute()
    )

    evidence_list: List[Evidence] = []
    for row in resp.data:
        ts_raw = row.get("timestamp")
        if isinstance(ts_raw, str):
            timestamp = datetime.fromisoformat(ts_raw)
        elif isinstance(ts_raw, datetime):
            timestamp = ts_raw
        else:
            # 时间戳缺失或类型异常的行不应该悄悄参与聚合计算
            # （错误的 timestamp 会破坏 ThresholdRecencyDamper 的
            # recency_weight 计算），跳过并保留可追溯性由调用方决定
            # 是否记录日志。
            continue

        mechanism = row.get("root_cause")
        if mechanism == "Unknown":
            # write_signal() 对未登记在 ONTOLOGY 里的 signal 会写 "Unknown"
            # 字符串而不是 NULL；转换成 Evidence.mechanism=None，
            # 语义上和"这条证据没有已知机制归因"保持一致，
            # 避免 BayesianAggregator.SIGNAL_TO_MECHANISM.get(ev.signal)
            # 之外，mechanism 字段本身携带一个容易被误用的字符串字面量。
            mechanism = None

        evidence_list.append(
            Evidence(
                signal=row.get("signal") or "Unknown",
                mechanism=mechanism,
                concept=row.get("concept") or "",
                timestamp=timestamp,
                error_level=row.get("error_level"),
                confidence=1.0,
            )
        )
    return evidence_list


def run_pipeline(
    student_id: str,
    cognitive_world: str,
    evidence_history: List[Evidence],
    current_state: dict,
    dan_service,
    subject_id: str = "ap_calculus",
    aggregator: Optional[EvidenceAggregator] = None,
    use_promotion_policy: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    ADR-016: this function now supports two mutually-exclusive execution
    paths, selected by the USE_PROMOTION_POLICY feature flag (or the
    use_promotion_policy override param, mainly for test harnesses):

    - OLD path (flag off, default): DummyAggregator/BayesianAggregator.aggregate()
      -> ThresholdRecencyDamper.dampen() -> decide_stage(). Fully unchanged
      from pre-ADR-016 behavior, INCLUDING continuing to write dan_state.stage
      per world (this is legitimate under the old design: decide_stage()'s
      effective_confidence depends on each world's own world_share, so the
      three worlds CAN genuinely diverge in stage under the old logic -- this
      is not the v8 semantic-illusion bug, which only applies to the new
      PromotionPolicy path below). This is what Level 1/2 (Smoke/Shadow) run
      against in comparison mode, and what Rollback Criteria falls back to.

    - NEW path (flag on): Route A update (2026-07-31, ADR-016 §12/v8).
      This function NO LONGER computes or writes stage/locked_world/
      promotion_state -- that responsibility moved to
      update_global_promotion_state() below, which the caller must invoke
      ONCE PER STUDENT (not once per world) after/alongside the per-world
      loop that still calls this function 3 times for diagnostic storage.
      This function's new-path branch now only writes the per-world
      DIAGNOSTIC distribution (weight_vector/temporal_views) to dan_state;
      it does not touch dan_state.stage or dan_state.promotion_state at all
      (both are left _UNSET in the write_state() call, per the sentinel
      contract -- see DANMemoryService.write_state() docstring).

      Why this split: aggregate_dual_scale() already produces a GLOBAL
      competing vector (RWM+FWM+AWM weights sum to 1) -- it is not three
      independent per-world computations, so recomputing/rewriting the same
      PromotionPolicy decision three times (once per world, as the pre-Route-A
      code did) was redundant work AND the root cause of the v8 semantic
      illusion (dan_state.FWM.stage="stable" while the actually-locked world
      was RWM). Splitting the concerns means: this function still runs once
      per world (for diagnostic storage, matching the existing caller loop
      structure -- no caller-side restructuring needed beyond adding one extra
      call), while the actual Promotion decision runs exactly once per student.
    """
    flag_on = _promotion_policy_enabled(use_promotion_policy)

    if not flag_on:
        # --- OLD path: unchanged, byte-for-byte the pre-ADR-016 behavior ---
        aggregator = aggregator or DummyAggregator()
        damper = ThresholdRecencyDamper()

        raw = aggregator.aggregate(evidence_history)
        damped = damper.dampen(raw, evidence_history, current_state)
        new_stage = decide_stage(damped, current_state.get("stage", "fragile"), cognitive_world)

        dan_service.write_state(
            student_id=student_id,
            cognitive_world=cognitive_world,
            stage=new_stage,
            evidence_count=len(evidence_history),
            weight_vector=damped.world_weights,
            aggregator_version=damped.aggregator_version,
            subject_id=subject_id,
            # NOTE: temporal_views / promotion_state intentionally NOT passed
            # here (they default to the _UNSET sentinel in write_state()),
            # so the old path never touches these two columns.
        )

        return {
            "raw_confidence": round(raw.confidence, 4),
            "damped_confidence": round(damped.confidence, 4),
            "old_stage": current_state.get("stage", "fragile"),
            "new_stage": new_stage,
        }

    # --- NEW path (Route A, 2026-07-31): diagnostic storage only ---
    # PromotionPolicy / global stage decision has moved OUT of this function.
    # See update_global_promotion_state() below -- the caller must call it
    # exactly once per student, separately from this per-world loop.
    if aggregator is None or not hasattr(aggregator, "aggregate_dual_scale"):
        raise TypeError(
            "run_pipeline() with USE_PROMOTION_POLICY enabled requires an "
            "aggregator implementing aggregate_dual_scale() (e.g. "
            "BayesianAggregator). DummyAggregator does not implement this "
            "method; pass an explicit BayesianAggregator instance."
        )

    # window_size no longer comes from a per-call PromotionPolicy instance
    # (that instance now only exists inside update_global_promotion_state());
    # use the dataclass default directly so the rolling window used for
    # diagnostic display stays consistent with whatever the global promotion
    # decision actually uses.
    cumulative, recent = aggregator.aggregate_dual_scale(
        evidence_history, recent_n=PromotionPolicyConfig().window_size
    )

    dan_service.write_state(
        student_id=student_id,
        cognitive_world=cognitive_world,
        evidence_count=len(evidence_history),
        weight_vector=recent.world_weights,
        aggregator_version=recent.aggregator_version,
        subject_id=subject_id,
        temporal_views={
            "rolling": {
                "world_weights": recent.world_weights,
                "entropy": recent.entropy,
                "effective_sample_size": recent.effective_sample_size,
            }
        },
        # NOTE: stage / promotion_state intentionally NOT passed (Route A) --
        # both default to the _UNSET sentinel in write_state(), so this
        # per-world call never touches dan_state.stage or
        # dan_state.promotion_state anymore. The global decision is written
        # once, separately, by update_global_promotion_state() to
        # dan_global_state.
    )

    return {
        "raw_confidence": round(cumulative.confidence, 4),
        "damped_confidence": round(recent.confidence, 4),
    }


def update_global_promotion_state(
    student_id: str,
    evidence_history: List[Evidence],
    dan_service,
    subject_id: str = "ap_calculus",
    aggregator: Optional[EvidenceAggregator] = None,
) -> Dict[str, Any]:
    """
    Route A（2026-07-31，ADR-016 v8 发现的修复）：学生级别的全局 Promotion
    决策，取代此前"对 RWM/FWM/AWM 三个 world 通道各调用一次
    PromotionPolicy.update()"的做法。

    调用方式：调用方（main.py::update_dan_state_after_signal() /
    verification_runner.py::replay_fixture()）应该在原有"for world in
    VALID_WORLDS: run_pipeline(...)"这个per-world循环**之外**，额外调用
    这个函数**恰好一次**（每个学生每次新证据到达调用一次，不是每个 world
    各调用一次）。这个函数只在 USE_PROMOTION_POLICY 开启时才有意义——调用方
    应该用同样的 flag 判断来决定是否调用它（如果 flag 关闭，不应该调用本
    函数，旧逻辑路径的 per-world stage 完全由 run_pipeline() 自己处理）。

    为什么要拆成独立函数而不是让 run_pipeline() 自己判断"这是第几次调用"：
    显式的独立函数、显式的调用点，比"函数内部悄悄判断这是不是三次调用里
    的第一次"更不容易出错、更容易看懂调用链——这正是 v8 发现的教训：隐性
    的、依赖调用顺序的假设，是这类语义歧义 bug 最容易滋生的地方。

    返回值里的 old_stage / new_stage / locked_world 是学生级别的全局值，
    不是某个具体 world 的值——这是 Route A 要解决的核心问题：全局判断
    只应该有一份，不应该在多个地方被重复计算和存储。

    === ADR-017 更新（2026-07-31，§8 Step 3）：mechanism-level track 接入 ===

    此前（Step 1/2）PromotionPolicy 新增的 mechanism-level 并行窗口只是
    纯新增、不影响本函数的输出。本次改动正式"接线"：

    1. policy.update() 现在同时传入 world_weights 与
       recent.mechanism_attribution（Step 1 新增的可选参数），驱动
       mechanism-level track 与 world-level track 并行判定。

    2. 整体 new_stage（写入 dan_global_state.stage 的值）现在取
       world-level stage 与 mechanism-level stage 两者中"阶段更高"的
       一个（fragile < emerging < stable）。这是 ADR-017 §5 Option C
       "world 层解出 OR mechanism 层解出，二者满足其一即可判定 stable"
       的直接实现。

    3. locked_world/locked_worlds/locked_mechanism 三字段的组装规则
       （详见 ADR-017 §6）：
       - 若 world 层本身已解出（world_stage=="stable" 且
         policy.export_state() 里有 locked_world），优先使用 world 层
         解出的具体值——这是原有生产路径，保持最大行为兼容。对
         RepresentationShift/SemanticIntegrity/FlowReasoning 这三个无损
         映射 mechanism 而言，world 层通常会和 mechanism 层同时解出、
         结果一致，不受这条优先级顺序影响。
       - 只有当 world 层未解出、而 mechanism 层解出时，才会真正走到
         "mechanism 层兜底"这条分支：反查
         BayesianAggregator.MECHANISM_TO_WORLD_DEFAULT，若该 mechanism
         映射到单一 world，则 locked_world/locked_worlds 都写入该 world
         （值语义一致，如 SIM_01 那样的 RepresentationShift 场景，即使
         走到这条分支也不会产生任何行为差异）；若映射到多个 world
         （目前仅 StructuralReasoning），则 locked_world 置 None，
         locked_worlds 写入这些 world 的列表——这正是 ADR-017 要修复
         的 SIM_03/SIM_04/student_F_structural 场景。
       - locked_mechanism 只在 mechanism 层确实解出时才写入具体值，
         否则为 None（不臆造溯源信息，见 ADR-017 §6 判定规则第三条）。
    """
    if aggregator is None or not hasattr(aggregator, "aggregate_dual_scale"):
        raise TypeError(
            "update_global_promotion_state() requires an aggregator "
            "implementing aggregate_dual_scale() (e.g. BayesianAggregator)."
        )

    current_global_state = dan_service.get_global_state(student_id, subject_id)
    old_stage = current_global_state["stage"] if current_global_state else "fragile"
    promotion_state_dict = current_global_state["promotion_state"] if current_global_state else None
    # 2026-08-03 修复：locked_mechanism 滞回保持（见下方 §"locked_mechanism
    # 滞回保持"注释），需要读取上一轮写入的 locked_mechanism 作为参照。
    old_locked_mechanism = current_global_state.get("locked_mechanism") if current_global_state else None

    policy = PromotionPolicy.rehydrate(config=None, state_dict=promotion_state_dict)

    cumulative, recent = aggregator.aggregate_dual_scale(
        evidence_history, recent_n=policy.config.window_size
    )

    # ADR-017 §8 Step 3: 同时喂 world_weights 与 mechanism_attribution，
    # 驱动两条并行 track。world_stage 是原有返回值（world-level），
    # mechanism_stage 是 Step 1 新增的只读属性，反映 mechanism-level
    # track 的判定结果。
    world_stage = policy.update(
        world_weights=recent.world_weights,
        mechanism_attribution=recent.mechanism_attribution,
    )
    mechanism_stage = policy.mechanism_stage

    STAGE_RANK = {"fragile": 0, "emerging": 1, "stable": 2}
    # ADR-017 §5 Option C: world 层解出 OR mechanism 层解出，满足其一
    # 即可判定为更高阶段。整体 new_stage 取两条 track 中阶段更高的一个
    # （非严格意义上的"OR"运算，而是把 fragile<emerging<stable 视为
    # 全序关系取 max，这样自然延伸覆盖了 emerging 这个中间状态，不只是
    # stable 这一个端点）。
    if STAGE_RANK[mechanism_stage] > STAGE_RANK[world_stage]:
        new_stage = mechanism_stage
    else:
        new_stage = world_stage

    exported = policy.export_state()

    # --- ADR-017 §6: 组装 locked_world / locked_worlds / locked_mechanism ---
    locked_world: Optional[str] = None
    locked_worlds: Optional[List[str]] = None
    locked_mechanism: Optional[str] = None

    if mechanism_stage == "stable" and policy.locked_mechanism:
        mech_name = policy.locked_mechanism
        mapping = getattr(aggregator, "MECHANISM_TO_WORLD_DEFAULT", {})
        mapped_worlds = list(mapping.get(mech_name, {}).keys())
        if len(mapped_worlds) == 1:
            locked_world = mapped_worlds[0]
            locked_worlds = mapped_worlds
        elif len(mapped_worlds) > 1:
            locked_world = None
            locked_worlds = mapped_worlds
        locked_mechanism = mech_name

    # === 2026-08-03 修复：locked_mechanism 滞回保持 ===
    # 背景（2026-08-02 第四轮十位学生模拟发现）：mechanism-level track
    # 的 hysteresis（demote_below=3）会导致 mechanism_stage 在证据流
    # 出现真实迁移时正常地从 stable 降级到 emerging/fragile——这本身
    # 是设计意图内的行为（PromotionPolicy._decide_mechanism_stage()
    # 的滞回逻辑），但上面这段"组装"逻辑此前只在 mechanism_stage 严格
    # 等于 stable 时才赋值 locked_mechanism，一旦降级就立刻整个置回
    # None——即使 world_stage 依然是 stable、诊断整体并未真正"失去
    # 确定性"。这会让刚上线的 ADR-018 Teaching Policy 静默退化到
    # 兜底策略，且退化本身不会被任何人注意到。
    #
    # 讨论达成的架构原则（Yongwu + DeepSeek，2026-08-03）：诊断引擎
    # 内部计算必须绝对诚实（world_weights/mechanism_attribution 该是
    # 多少就是多少，PromotionPolicy 自己的锁存状态也不应该被这里的
    # 输出层修改）；但向下游（Teaching Policy 等控制/决策系统）输出
    # 的信号应该"适度保守与稳定"，不应该因为单轮证据的短暂波动就
    # 立刻收回已经建立的诊断结论——类比自动驾驶不因单帧画面闪烁就
    # 猛打方向盘。
    #
    # 修复方式：不修改 PromotionPolicy 内部状态（它自己的滞回锁存
    # 保持不变，继续诚实地反映"mechanism 层当前是否解出"），而是在
    # 这一层输出上新增一道更保守的"强制释放"判定——只有当上一轮锁定
    # 的 mechanism 在当前 mechanism-level 窗口里完全消失（计数为0）
    # 时，才真正把 locked_mechanism 释放为 None；否则沿用上一轮的
    # locked_mechanism 值，直到它真的从窗口里完全消失。
    #
    # 这个门槛比 PromotionPolicy 自己的 demote_below=3 更严格（3 不是
    # 0），是刻意的：demote_below 管的是"mechanism 层内部要不要保持
    # stable 判定"，这里管的是"要不要放弃已经建立的下游输出"，后者
    # 理应比前者更保守——2026-08-03 讨论认定这是合理的初始保守值，
    # 具体阈值可以在 Session 3 真实对话观察后调整。
    #
    # 明确排除的范围（另一个独立问题，本次不修）：某些学生的
    # mechanism-level track 因为信号的 mechanism 归因是精确对半分
    # （如 ABSOLUTE_VALUE 的 RepresentationShift/SemanticIntegrity
    # 各50%），结构性地永远无法在 mechanism 层解出——这种情况下
    # old_locked_mechanism 从一开始就是 None（从未真正锁定过），本次
    # 修复的滞回保持逻辑不会、也不应该对这类学生产生任何影响。这是
    # ADR-017 Mechanism Parity 问题的另一个变体，需要独立的架构决定
    # （例如是否引入 locked_mechanisms 复数概念），留待下一个 session
    # 单独讨论，不在本次修复范围内。
    if locked_mechanism is None and old_locked_mechanism:
        window_snapshot = policy.mechanism_window_snapshot
        old_mechanism_count_in_window = window_snapshot.count(old_locked_mechanism)
        if old_mechanism_count_in_window > 0:
            # 旧 mechanism 尚未从窗口里完全消失，滞回保持上一轮的结论
            locked_mechanism = old_locked_mechanism
            mapping = getattr(aggregator, "MECHANISM_TO_WORLD_DEFAULT", {})
            mapped_worlds = list(mapping.get(old_locked_mechanism, {}).keys())
            if mapped_worlds:
                locked_worlds = mapped_worlds
        # else: 旧 mechanism 已完全消失（强制释放条件满足），
        # locked_mechanism 保持 None（上面已经是默认值，无需再赋值）

    # world 层若也解出，其具体值优先作为 locked_world 的最终依据
    # （保持原有生产路径行为最大兼容）。
    world_level_locked = exported.get("locked_world")
    if world_stage == "stable" and world_level_locked:
        locked_world = world_level_locked
        if not locked_worlds:
            locked_worlds = [world_level_locked]

    dan_service.write_global_state(
        student_id=student_id,
        stage=new_stage,
        locked_world=locked_world,
        promotion_state=exported,
        subject_id=subject_id,
        locked_worlds=locked_worlds,
        locked_mechanism=locked_mechanism,
    )

    return {
        "old_stage": old_stage,
        "new_stage": new_stage,
        "locked_world": locked_world,
        "locked_worlds": locked_worlds,
        "locked_mechanism": locked_mechanism,
        "raw_confidence": round(cumulative.confidence, 4),
        "damped_confidence": round(recent.confidence, 4),
    }
