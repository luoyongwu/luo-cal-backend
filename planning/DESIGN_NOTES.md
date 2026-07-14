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


## 已知问题-1：Streamlit session_state 意外重置（2026-07-11晚，观察3次，未定位根因）

触发点不完全一致：一次在提交答案后、一次在切换 Concept 时。Streamlit 日志显示为完整的依赖重装/容器重建过程，非脚本内异常重跑；同期 Railway 后端日志全为 200 OK，排除后端崩溃导致。暂判断为 Streamlit Cloud 资源限制触发的容器回收（怀疑与单次会话内 `st.session_state.messages` 累积过大有关），不影响已写入数据库的信号数据，仅影响前端会话体验。样本量不足，暂不排查，留待样本积累到4-5次或进入大规模模拟测试阶段后再处理。

## 已知问题-2：`RailwayAdapter.chat()` 未使用传入的 `system` 参数（app.py）

`get_ai_response()` 构造了含 STATUS/LEAKAGE 标签指令的 `system_msg` 并传给 `adapter.chat(system_msg, msgs)`，但 `RailwayAdapter.chat()` 的实现完全忽略 `system` 参数，只发送 `concept_id`/`user_input`/`session_id`/`language` 给后端。真正生效的是 main.py 独立维护的 `SCL_SYSTEM_PROMPT_ZH/EN`，其中不含 STATUS/LEAKAGE 标签机制。前端展示的 "Leakage Score" 在 Railway Backend 路径下，很可能是切换 backend 时未清空的 `leakage_log` 历史残留，不代表当前对话的真实评分。低优先级，暂不修复。


---

## ADR-011: decide_stage() 的乘法置信度结构导致 stage 升级门槛实质过严

**日期**: 2026-07-14
**发现场景**: CLVS Phase 2.5 验证

**问题描述**:
CLVS验证中，student_A_representation（单一RepresentationShift机制、5条纯净递增证据）
和 student_B_flow（单一FlowReasoning机制、5条纯净证据）两个fixture均设计为
"应收敛至stable"，但实际运行均停留在fragile。

**根因**:
`decide_stage()` 中 `effective_confidence = damped_vector.confidence * world_share`，
即使某个world已占绝对主导（如B_flow的FWM权重0.8214），`confidence`本身
（由 `evidence_factor × concentration_factor` 复合计算）在仅5条证据时通常在0.4附近，
乘以world_share后进一步被压低（A: ≈0.395，B: ≈0.337），
始终达不到 `decide_stage` 的0.7升级门槛。

**验证方式**:
直接调用仓库内真实 `BayesianAggregator` 与 `decide_stage` 函数代入两组fixture证据，
数值与理论推导完全吻合，非手工估算。

实测数据：
- student_A_representation: confidence≈0.4613（最高5条），world_share(RWM)≈0.857，
  effective_confidence≈0.395 → decide_stage结果: fragile
- student_B_flow: world_weights={RWM:0.1429, FWM:0.8214, AWM:0.0357}，
  confidence=0.4096 → effective_confidence≈0.337 → decide_stage结果: fragile

**影响范围**:
任何证据量较少（≤10条量级）的场景，即便证据高度一致、理论上应快速收敛，
也难以触发stage升级——这可能影响所有新学生/新概念的早期教学反馈及时性。

**待讨论修复方向**:
1. 降低0.7阈值（需评估对其他fixture的连带影响）
2. 移除 `× world_share` 的乘法惩罚，直接用 `confidence` 本身判断
   （dominant_world已单独校验，此处可能是重复约束）
3. 引入"连续N次超过较低门槛"的替代升级路径

**状态**: 待决策，暂不修改代码
