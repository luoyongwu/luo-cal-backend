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
      from pre-ADR-016 behavior. This is what Level 1/2 (Smoke/Shadow) run
      against in comparison mode, and what Rollback Criteria falls back to.

    - NEW path (flag on, after Level 3 Full Validation passes): rehydrates
      a PromotionPolicy from current_state["promotion_state"], runs
      aggregate_dual_scale(), feeds `recent.world_weights` into
      policy.update(), and persists policy.export_state() back alongside
      temporal_views. See ADR-016 §3 Stage 2 for the full rationale.
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

    # --- NEW path: PromotionPolicy stateful rehydration (ADR-016) ---
    if aggregator is None or not hasattr(aggregator, "aggregate_dual_scale"):
        raise TypeError(
            "run_pipeline() with USE_PROMOTION_POLICY enabled requires an "
            "aggregator implementing aggregate_dual_scale() (e.g. "
            "BayesianAggregator). DummyAggregator does not implement this "
            "method; pass an explicit BayesianAggregator instance."
        )

    policy = PromotionPolicy.rehydrate(
        config=None,  # default PromotionPolicyConfig; see ADR-016 §3 note on
                      # per-student/per-concept config customization being
                      # out of scope for this initial integration
        state_dict=current_state.get("promotion_state"),
    )

    cumulative, recent = aggregator.aggregate_dual_scale(
        evidence_history, recent_n=policy.config.window_size
    )
    new_stage = policy.update(world_weights=recent.world_weights)

    dan_service.write_state(
        student_id=student_id,
        cognitive_world=cognitive_world,
        stage=new_stage,
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
        promotion_state=policy.export_state(),
    )

    return {
        "raw_confidence": round(cumulative.confidence, 4),
        "damped_confidence": round(recent.confidence, 4),
        "old_stage": current_state.get("stage", "fragile"),
        "new_stage": new_stage,
    }
