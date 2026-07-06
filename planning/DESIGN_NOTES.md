# Luo-cal — Design Notes（架构决策日记 / ADR）

**性质：** 本文档不记代码 Bug，不记功能上线——那些记在 `THEORY_CHANGELOG.md` 和 `constraints_changelog.md` 里。这里只记**"当时为什么做出这个选择"**。

---

## ADR-001：先冻结接口，再写具体算法

**日期：** 2026-07-05 | **状态：** Accepted

**背景：** Phase 2 要建的 Evidence Aggregation Engine，相当于给整个认知诊断系统装一颗"芯片"。传统开发直觉是立刻去写具体数学公式，但这样做的代价是：一旦未来要换算法（隐马尔可夫、Transformer Memory、甚至端到端大模型），整条从数据库到前端的管道都可能被迫跟着重构。

**决策：** 不管里面装的是贝叶斯、HMM 还是未来的大模型，先把"插槽"的形状定死——`EvidenceAggregator` 和 `CognitiveInertiaDamper` 两个接口在 Phase 2 编码开始前先冻结。

**后果：** Phase 2 的实际编码工作量不会因此减少，但换算法、跨学科扩展（v4.0）时前端和数据库不需要承受重构摩擦力。

---

## ADR-006：WeightVector 三字段文档-代码不同步

**日期：** 2026-07-06 | **状态：** Accepted

**背景：** `BAYESIAN_AGGREGATOR_SPEC_v0.2.md` §5 声称 `evidence_used`、`effective_sample_size`、`entropy` 三个字段"已经加进 `pcsa_interfaces.py`"。但 Phase 2 实现阶段核对源码时发现，这三个字段实际并不存在——规格书记录的是一个"打算做"的状态，被误写成了"已完成"。

**决策：** 按 Spec §5 给定的精确定义（字段名、类型、默认值）原样补齐，不重新讨论数值或语义。

**后果：** `WeightVector` 现在与 Spec §5 一致。此事本身被记录，因为和 Phase 1 的 `cognitive_signals` schema drift 属于同一类问题——"文档说完成、代码没同步"。

---

## ADR-008：Cognitive Evidence 与 Meta Feedback 的边界划分

**日期：** 2026-07-06 | **状态：** Accepted

**背景：** 核查 `cognitive_signals` 真实生产数据时发现，`REFLECTION_VERY_LIKE` / `REFLECTION_PARTIAL` / `REFLECTION_NOT_LIKE` 三个信号合计占全部证据的约 34%，是学生对 Dashboard 诊断结果的自评反馈，不是 Root Cause Ontology 定义的认知错误信号。若强行塞进 Signal→Mechanism 矩阵，会产生语义空洞和循环推断问题。

**决策：** 确立 Cognitive Evidence（供聚合器推断用）与 Meta Feedback（供未来反思率评估用）是两类不同性质的数据，严格保持因果方向单向：学生行为 → 系统诊断 → 学生反馈。`REFLECTION_*` 保留在表中但排除在聚合器输入之外。

**过渡方案：** 当前用显式信号名单区分。长期建议给 `cognitive_signals` 加 `event_type` 列（`evidence` / `feedback`），本次不做 schema 变更。

**后果：** 聚合器能正确区分三类信号（Cognitive Evidence 参与推断 / Meta Feedback 静默跳过 / 真正未知信号告警）。

---

*后续每次做出影响架构走向的决策，追加新的 ADR 到本文档末尾*
