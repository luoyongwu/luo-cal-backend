"""
inference_pipeline.py
Luo-cal v3.0 PCSA — Phase 2 管道联调

本文件的目的不是交付最终的贝叶斯实现，而是"先通电，再优化核心部件"：
用一个极简的占位聚合器（DummyAggregator）撑起完整管道
（Evidence → Aggregator → Damper → Stage 决策 → dan_state 写入），
在真正的贝叶斯数学写完之前，先把数据库层面的问题（revision_count 递增、
复合主键冲突、多世界并发写入）压力测试出来。

接口已在 pcsa_interfaces.py 冻结，DummyAggregator 换成真实贝叶斯实现时，
本文件的 Damper、decide_stage、run_pipeline 都不需要改动。

⚠️ DummyAggregator 不是 Phase 2 的最终交付物。它按错误频次做最朴素的计数
统计，不做任何真正的概率推断，仅用于验证管道本身是否可靠。
"""

from datetime import datetime, timezone
from typing import List, Dict, Any

from pcsa_interfaces import (
    Evidence,
    WeightVector,
    EvidenceAggregator,
    CognitiveInertiaDamper,
)

STAGE_ORDER = ["fragile", "emerging", "stable"]


class DummyAggregator(EvidenceAggregator):
    """
    占位实现，仅用于管道压力测试，不是 Phase 2 的最终交付物。
    按错误频次做最朴素的计数统计，不做任何贝叶斯推断。
    真正的贝叶斯实现完成后应替换这个类——接口已冻结，替换时
    不需要动 Damper、State、Dashboard 任何一层。
    """

    # v1.0 硬分类简化映射（Ontology §4），真实实现应支持按信号做更精细的区分
    # 注：main.py 当前实际使用 "ExecutionIntegrity"（历史命名，与 Volume I
    # 冻结的 "SemanticIntegrity" 不一致，见 THEORY_CHANGELOG 待办事项）
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
            confidence = min(1.0, total / 10)  # 朴素启发式：10 条证据封顶置信度

        mech_total = sum(mechanism_counts.values())
        if mech_total > 0:
            mechanism_attribution = {m: c / mech_total for m, c in mechanism_counts.items()}
        else:
            mechanism_attribution = {"Unknown": 1.0}  # 保证理论边界校验不会因空字典失败

        return WeightVector(
            world_weights=world_weights,
            mechanism_attribution=mechanism_attribution,
            confidence=confidence,
            aggregator_version="dummy_v0_placeholder",
        )


class ThresholdRecencyDamper(CognitiveInertiaDamper):
    """
    Phase 2 初版阻尼器实现：升级门槛（默认 N≥5）+ 时间衰减。
    这两个数字是工程超参数（ADR-004），不是理论承诺，可以随时调整
    而不需要改接口、不需要走 Constitution 修订流程。
    """

    UPGRADE_MIN_STREAK = 5       # 工程超参数：至少多少条"有效"证据才允许升级
    DECAY_HALF_LIFE_DAYS = 14.0  # 工程超参数：多少天后旧证据权重衰减到一半

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
            # 证据不够密集，按比例打压 confidence，防止单次表现就跳级
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
        )

    def _recency_weight(self, evidence_time: datetime, now: datetime) -> float:
        if evidence_time.tzinfo is None:
            evidence_time = evidence_time.replace(tzinfo=timezone.utc)
        days_elapsed = (now - evidence_time).total_seconds() / 86400
        return 0.5 ** (days_elapsed / self.DECAY_HALF_LIFE_DAYS)


def decide_stage(damped_vector: WeightVector, current_stage: str, cognitive_world: str) -> str:
    """
    应用 State Transition Policy 的定性规则（见 planning/STATE_TRANSITION_POLICY_v1.0.md）：
    - 每次最多移动一级（不允许 fragile 直接跳 stable）
    - 升级需要较高置信度；降级门槛低于升级门槛（不变量1，可逆性 + 教育伦理，
      见 Policy 文档 §4.2：错误地把进步学生耽误在过时评价里，比误降级危害更大）
    阈值本身是工程参数，可调。

    关键点（Phase 2 压力测试发现并修复的 bug）：不能直接用 damped_vector.confidence
    这个全局置信度去判断某一个具体 World 的 Stage——如果证据 100% 与 RWM 相关、
    与 FWM/AWM 无关（world_weights = {"RWM":1.0, "FWM":0.0, "AWM":0.0}），
    那么 FWM/AWM 不应该跟着 RWM 一起被拉升。必须用"整体置信度 × 该 World 的权重占比"
    作为该 World 实际生效的置信度，这是"不可绕过核心推断链路"（不变量3）的直接体现——
    A 世界的证据不能顺带给 B 世界镀金。
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
    从 cognitive_signals（Event Log）拉取某学生的完整证据历史，
    转换为 Evidence 对象列表。字段名对齐 Phase 1 排查确认的真实 schema。
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
) -> Dict[str, Any]:
    """
    完整管道编排：Evidence → Aggregator → Damper → Stage 决策 → 写回 dan_state。
    dan_service 需要提供 write_state()（见 dan_memory_service.py）。
    """
    aggregator = DummyAggregator()
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
