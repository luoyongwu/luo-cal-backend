"""
pcsa_interfaces.py
Luo-cal v3.0 PCSA — Phase 2 Step 0: Interface Freeze

本文件冻结 Phase 2 的两个核心接口，在任何具体算法（贝叶斯、HMM、Transformer
Memory、LLM Evaluator）实现之前先定死"插槽"形状。

设计原则（ADR-001, ADR-003，见 planning/DESIGN_NOTES.md）：
- EvidenceAggregator 只算"纯净"概率，不掺教学策略
- CognitiveInertiaDamper 只管教学策略过滤，不做概率数学
- 两者严格分层，换掉其中一个不影响另一个

本版变更：
  - Evidence 新增 confidence: float = 1.0（检测置信度，当前恒为 1.0）
  - WeightVector 新增 evidence_used / effective_sample_size / entropy
    三个字段（用于 Dashboard 展示和审计）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

VALID_WORLDS = ("RWM", "FWM", "AWM")


@dataclass
class Evidence:
    """单条证据，对应 cognitive_signals 的一行"""
    signal: str
    mechanism: Optional[str]
    concept: str
    timestamp: datetime
    error_level: Optional[str] = None
    confidence: float = 1.0


@dataclass
class WeightVector:
    """Evidence Aggregation Engine 的输出契约"""
    world_weights: Dict[str, float]
    mechanism_attribution: Dict[str, float]
    confidence: float
    aggregator_version: str = "unversioned"
    evidence_used: int = 0
    effective_sample_size: float = 0.0
    entropy: float = 0.0


class EvidenceAggregator(ABC):
    """证据聚合引擎抽象基类"""

    def aggregate(self, evidence_history: List[Evidence]) -> WeightVector:
        result = self._aggregate(evidence_history)
        self._validate_theory_boundary(result)
        return result

    @abstractmethod
    def _aggregate(self, evidence_history: List[Evidence]) -> WeightVector:
        raise NotImplementedError

    @staticmethod
    def _validate_theory_boundary(result: WeightVector) -> None:
        if not result.mechanism_attribution:
            raise ValueError(
                "理论边界违规：聚合算法必须输出中间 Mechanism 归因"
            )
        if not (0.0 <= result.confidence <= 1.0):
            raise ValueError(f"confidence 必须在 [0,1] 区间")
        missing_worlds = set(VALID_WORLDS) - set(result.world_weights.keys())
        if missing_worlds:
            raise ValueError(f"world_weights 缺少必需的 World：{missing_worlds}")
        total = sum(result.world_weights.values())
        if not (0.98 <= total <= 1.02):
            raise ValueError(f"world_weights 之和应约等于 1.0，得到 {total}")


class CognitiveInertiaDamper(ABC):
    """认知惯性阻尼器抽象基类"""

    @abstractmethod
    def dampen(
        self,
        raw_weight_vector: WeightVector,
        evidence_history: List[Evidence],
        current_state: dict,
    ) -> WeightVector:
        raise NotImplementedError
