"""
inference_pipeline.py
Luo-cal v3.0 PCSA — Phase 2 管道联调 + 贝叶斯聚合器实现
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

STAGE_ORDER = ["fragile", "emerging", "stable"]

DEFAULT_AGGREGATOR_CONFIG: Dict[str, Any] = {
    "alpha_prior": 0.5,
    "window_mode": "recent_n",
    "window_size_n": 50,
    "window_days": 90,
}


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
    world_share = damped_vector.world_weights.get(cognitive_world, 0.0)
    effective_confidence = damped_vector.confidence * world_share

    idx = STAGE_ORDER.index(current_stage)
    if effective_confidence >= 0.7 and idx < len(STAGE_ORDER) - 1:
        return STAGE_ORDER[idx + 1]
    elif effective_confidence < 0.35 and idx > 0:
        return STAGE_ORDER[idx - 1]
    return current_stage


def run_pipeline(
    student_id: str,
    cognitive_world: str,
    evidence_history: List[Evidence],
    current_state: dict,
    dan_service,
    subject_id: str = "ap_calculus",
    aggregator: Optional[EvidenceAggregator] = None,
) -> Dict[str, Any]:
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
    )

    return {
        "raw_confidence": round(raw.confidence, 4),
        "damped_confidence": round(damped.confidence, 4),
        "old_stage": current_state.get("stage", "fragile"),
        "new_stage": new_stage,
    }
