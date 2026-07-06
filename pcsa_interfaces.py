"""
pcsa_interfaces.py
Luo-cal v3.0 PCSA — Phase 2 Step 0: Interface Freeze

本文件冻结 Phase 2 的两个核心接口，在任何具体算法（贝叶斯、HMM、Transformer
Memory、LLM Evaluator）实现之前先定死"插槽"形状。参见：
planning/PERSISTENT_COGNITIVE_STATE_ARCHITECTURE_v3.0.md §架构总览、§Phase 2 Step 0

设计原则（ADR-001, ADR-003，见 planning/DESIGN_NOTES.md）：
- EvidenceAggregator 只算"纯净"概率，不掺教学策略
- CognitiveInertiaDamper 只管教学策略过滤，不做概率数学
- 两者严格分层，换掉其中一个不影响另一个

理论边界（ADR 未单独编号，见 PCSA 文档"架构总览"）：
Aggregation Engine 不得跳过 Mechanism 层直接从 Evidence 给出 World 权重。
本文件通过模板方法模式强制校验这条约束——子类无法绕过，运行时会直接报错，
不依赖实现者自觉遵守。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

VALID_WORLDS = ("RWM", "FWM", "AWM")


@dataclass
class Evidence:
    """
    单条证据，对应 cognitive_signals 的一行（Event Log 中的一个事件）。
    字段名对齐生产环境真实 schema（见 Phase 1 排查结果）。
    """
    signal: str                    # 如 "BOUNDS_TRAP"（对应 cognitive_signals.signal）
    mechanism: Optional[str]       # 如 "RepresentationShift"（对应 cognitive_signals.root_cause）
    concept: str                   # 如 "5.4"（对应 cognitive_signals.concept）
    timestamp: datetime            # 对应 cognitive_signals.timestamp
    error_level: Optional[str] = None   # procedural / conceptual


@dataclass
class WeightVector:
    """
    Evidence Aggregation Engine 的输出契约。
    world_weights 与 mechanism_attribution 都是必填——理论边界要求
    聚合算法必须显式给出中间 Mechanism 归因，不能只给最终 World 权重。

    v0.2 扩字段（Bayesian Aggregator 候选公式定稿后新增，向后兼容——
    DummyAggregator 等既有实现不传这些字段时，默认值仍能通过校验）：
    - evidence_used: 本次计算实际参与聚合的证据条数（时间/数量窗口内）
    - effective_sample_size: Σ confidence_i，等效证据量（不是原始条数，
      是按 detector 置信度加权后的"软"证据量）
    - entropy: world_weights 的香农熵，供 Dashboard 解释"证据方向是否一致"
    - reasoning_trace: 可选的推断链路记录（Signal→Mechanism→World 每一步的
      具体数值），为 Phase 3 的 Evidence Trace 直接提供原始材料，不需要
      Dashboard 自己重新反推一遍计算过程。同样是计算过程的自然副产物。

    这些字段没有一个是"为了 Explainability 临时生成的"——它们全部是
    计算过程的自然副产物，符合"Mechanism Attribution 是真实中间变量，
    不是事后编的解释"这条设计原则（见 BAYESIAN_AGGREGATOR_SPEC_v0.2.md）。

    ⚠️ 命名澄清（重要，不影响字段名，只影响使用方式）：`confidence` 不是
    "World 有多大概率是真的"这种统计学 Probability，而是"系统对当前诊断
    稳定性的把握程度"（Diagnostic Confidence / Diagnostic Reliability）。
    论文和文档里正式表述一律使用"Diagnostic Confidence"这个说法，不要
    裸写"Confidence"，避免有统计学背景的读者误解成后验概率本身。
    代码层面字段名暂不改动（接口刚冻结，牵连文件已经不止一个，改名成本
    此刻大于收益），只在这里把语义钉死。
    """
    world_weights: Dict[str, float]        # {"RWM": 0.7, "FWM": 0.2, "AWM": 0.1}
    mechanism_attribution: Dict[str, float]  # {"RepresentationShift": 0.6, "SemanticIntegrity": 0.1, ...}
    confidence: float                      # [0, 1]，Diagnostic Confidence，非 Probability——见上方澄清
    aggregator_version: str = "unversioned"  # 见 PCSA Phase 4.5，用于区分"学生变了"还是"算法变了"
    evidence_used: int = 0                 # 本次窗口内实际参与聚合的证据条数
    effective_sample_size: float = 0.0     # Σ confidence_i，等效证据量
    entropy: float = 0.0                   # world_weights 的香农熵
    reasoning_trace: Optional[List[dict]] = None  # Phase 3 Evidence Trace 的原始材料，可选


class EvidenceAggregator(ABC):
    """
    证据聚合引擎的抽象基类。

    职责边界：只负责算出"纯净"的概率/权重，不掺杂任何教学策略判断
    （要不要真的升级、要不要因为太久没练习而衰减）。那些是
    CognitiveInertiaDamper 的职责，不属于这里。

    子类实现 _aggregate()，不要覆盖 aggregate() 本身——aggregate() 是
    模板方法，负责在子类算完之后强制校验理论边界约束。这个校验不是
    建议性的：违反会在运行时直接抛出异常，不依赖实现者自觉遵守。
    """

    def aggregate(self, evidence_history: List[Evidence]) -> WeightVector:
        """
        输入：学生的完整证据历史（按时间排序）
        输出：三个 World 的权重向量，附带中间 Mechanism 归因和 confidence

        这是最终方法（不要在子类中覆盖）。真正的算法逻辑写在 _aggregate() 里。
        """
        result = self._aggregate(evidence_history)
        self._validate_theory_boundary(result)
        return result

    @abstractmethod
    def _aggregate(self, evidence_history: List[Evidence]) -> WeightVector:
        """子类在这里实现具体算法（贝叶斯 / HMM / Transformer Memory / ...）。"""
        raise NotImplementedError

    @staticmethod
    def _validate_theory_boundary(result: WeightVector) -> None:
        """
        强制校验理论边界约束（PCSA 文档"架构总览"一节）：
        1. 必须显式输出 Mechanism 归因，不能只给最终 World 权重
        2. confidence 必须在 [0, 1] 区间
        3. world_weights 必须覆盖三个 World，且大致归一化
        任何一条不满足，直接抛出异常——不允许静默通过。
        """
        if not result.mechanism_attribution:
            raise ValueError(
                "理论边界违规：聚合算法必须输出中间 Mechanism 归因，"
                "不能只给最终 World 权重（见 PCSA 文档'架构总览'一节；"
                "呼应 Volume I 命题1 的多对多推断映射，跳过 Mechanism 层"
                "会让 Constitution 的可审计性形同虚设）。"
            )
        if not (0.0 <= result.confidence <= 1.0):
            raise ValueError(f"confidence 必须在 [0,1] 区间，得到 {result.confidence}")
        missing_worlds = set(VALID_WORLDS) - set(result.world_weights.keys())
        if missing_worlds:
            raise ValueError(f"world_weights 缺少必需的 World：{missing_worlds}")
        total = sum(result.world_weights.values())
        if not (0.98 <= total <= 1.02):  # 留一点浮点误差空间
            raise ValueError(f"world_weights 之和应约等于 1.0（归一化），得到 {total}")
        if result.evidence_used < 0:
            raise ValueError(f"evidence_used 不能为负，得到 {result.evidence_used}")
        if result.effective_sample_size < 0:
            raise ValueError(f"effective_sample_size 不能为负，得到 {result.effective_sample_size}")
        if result.entropy < 0:
            raise ValueError(f"entropy 不能为负，得到 {result.entropy}")


class CognitiveInertiaDamper(ABC):
    """
    认知惯性阻尼器的抽象基类。

    职责边界：接收 EvidenceAggregator 算出的"纯净"权重，结合证据历史和
    当前持久状态，决定这份权重能不能真的转化成 Stage 变化。这里只管
    教学策略（够不够格升级、该不该衰减），不做概率数学——那是
    EvidenceAggregator 的职责。

    N≥5 之类的具体阈值不属于接口本身，是子类实现中的工程超参数
    （ADR-004，已从 Volume I 理论承诺中降级，调整只需工程验证）。
    """

    @abstractmethod
    def dampen(
        self,
        raw_weight_vector: WeightVector,
        evidence_history: List[Evidence],
        current_state: dict,
    ) -> WeightVector:
        """
        输入：
            raw_weight_vector — EvidenceAggregator 输出的纯净权重
            evidence_history  — 完整证据历史，用于判断"连续信号数"等策略条件
            current_state     — 当前持久状态（dan_state 当前行），用于判断
                                 是否满足升级/降级条件
        输出：
            应用教学策略过滤后的权重向量——可能等于输入（策略放行），
            也可能被按住不放行（例如概率虽高但连续正面信号不足 N 次）
        """
        raise NotImplementedError
