"""
inference_pipeline.py
Luo-cal v3.0 PCSA — Phase 2 管道联调 + 贝叶斯聚合器实现

本文件历史：先用 DummyAggregator 把管道（Evidence → Aggregator → Damper →
Stage 决策 → dan_state 写入）压力测试通电，再实现真正的贝叶斯数学。
接口在 pcsa_interfaces.py 冻结，DummyAggregator 换成 BayesianAggregator 时，
Damper、decide_stage、run_pipeline 的编排逻辑本身不需要改动。

本版新增：BayesianAggregator（严格对照 BAYESIAN_AGGREGATOR_SPEC_v0.2.md 实现，
两段显式矩阵 + Dirichlet 后验 + 复合置信度公式），以及配置加载函数。
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
    """
    读取 config.yaml 中的 aggregator 配置段（Spec §4.2）。
    找不到文件、缺少 PyYAML、或文件里没有 aggregator 段时，
    退回内置默认值并打印警告，不让配置缺失导致整个管道崩溃。
    """
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
    """
    占位实现，仅用于管道压力测试，不是 Phase 2 的最终交付物。
    按错误频次做最朴素的计数统计，不做任何贝叶斯推断。
    保留作为 A/B 测试 / 回归测试的对照基线（Spec §8 第5条）。
    """

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
    """
    Phase 2 正式贝叶斯聚合器，严格对照
    planning/BAYESIAN_AGGREGATOR_SPEC_v0.2.md 实现。
    """

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


class ThresholdRecencyDamper(CognitiveInertiaDamper):
    """
    Phase 2 初版阻尼器实现：升级门槛（默认 N≥5）+ 时间衰减。
    """

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
    应用 State Transition Policy 的定性规则
    """
    world_share = damped_vector.world_weights.get(cognitive_world, 0.0)
    effective_confidence = damped_vector.confidence * world_share

    idx = STAGE_ORDER.index(current_stage)
    if effective_confidence >= 0.7 and idx < len(STAGE_ORDER) - 1:
        return STAGE_ORDER[idx + 1]
    elif effective_confidence < 0.35 and idx > 0:
        return STAGE_ORDER[idx - 1]
    return current_stage


def fetch_evidence_history(supabase_client, student_id: str) -> List[Evidence]:
    """
    从 cognitive_signals（Event Log）拉取某学生的完整证据历史
    """
    resp = (
        supabase_client.table("cognitive_signals")
        .select("signal, root_cause, concept, timestamp, error_level")
        .eq("student_id", student_id)
        .order("timestamp", desc=False)
        .execute()
    )
    evidence_list = []
    for row in resp.data:
        try:
            ts = datetime.fromisoformat(row["timestamp"])
        except (ValueError, TypeError, KeyError):
            ts = datetime.now(timezone.utc)
        evidence_list.append(
            Evidence(
                signal=row.get("signal", "Unknown"),
                mechanism=row.get("root_cause"),
                concept=row.get("concept", ""),
                timestamp=ts,
                error_level=row.get("error_level"),
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
) -> Dict[str, Any]:
    """
    完整管道编排：Evidence → Aggregator → Damper → Stage 决策 → 写回 dan_state
    """
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
