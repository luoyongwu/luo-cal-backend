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

## ADR-011: Composite Confidence 与 Stage Promotion 阈值的设计一致性问题（Design Consistency Issue）

**日期**: 2026-07-14
**发现场景**: CLVS Phase 2.5 验证

**问题描述**:
CLVS验证中，student_A_representation（单一RepresentationShift机制、5条纯净递增证据）
和 student_B_flow（单一FlowReasoning机制、5条纯净证据）两个fixture均设计为
"应收敛至stable"，但实际运行均停留在fragile。

**这不是实现Bug**：Python代码没有语法错误、没有逻辑崩溃，已通过实测数据核实
（见下方实测数据），排除了_aggregate()/decide_stage()本身写错的可能。

**真正确认的事实（100%成立）**：
现有设计（evidence_factor × concentration_factor × world_share 的复合置信度，
与 decide_stage() 的 0.7 升级门槛）与 Canonical Validation Fixture
（student_A/B 的预期"应快速收敛"）之间存在不一致。

**尚未能下的结论**：
这一不一致究竟应归因于以下哪一项，目前证据还不足以拍板：
- 可能A：Composite Confidence 对 early learning（少量证据）过于保守（目前倾向，但非定论）
- 可能B：stage 门槛（0.70）本身定得偏高，理论上应更低（如0.55）
- 可能C：Canonical Student 的证据条数（5条）本身就短于设计目标所要求的最小证据量
  （若设计初衷本就要求 stable 至少需要8~10条证据，则A/B停留在fragile反而是符合设计的）

**技术细节补充**：
decide_stage() 真正用于比较的 effective_confidence 是三项相乘，不是两项：
confidence = evidence_factor × concentration_factor
effective_confidence = confidence × world_share
world_share（该学生证据集中所在world的权重占比）是第三层，
在评审"重新校准confidence公式"这一方向时需一并纳入考虑，
否则只调整前两项，天花板问题可能只被部分解决。

**实测数据**：
- student_A_representation: confidence约0.4613（5条证据），world_share(RWM)约0.857，
  effective_confidence约0.395 到 decide_stage结果: fragile
- student_B_flow: world_weights={RWM:0.1429, FWM:0.8214, AWM:0.0357}，
  confidence=0.4096 到 effective_confidence约0.337 到 decide_stage结果: fragile

**为什么这是个重要问题**：
如果连最理想的学习路径都无法进入stable，真实学生几乎不可能进入stable。
系统后续所有依赖stable的功能（长期记忆、掌握判定、Dashboard提示等）都会受影响。
这不是局部参数问题，而是会影响整个Cognitive Layer行为的设计一致性问题。

**待评审的设计方向（Possible Design Directions，非"解决方案"，保持开放）**：

方向一：重新校准 Stage Threshold
- 支持：改动最简单，只需改config.yaml一个数字
- 反对：治标不治本且有风险——全局降低门槛，可能让Student C这类"混合交织型"
  或未来的脏数据也更容易"混"进stable，降低诊断纯净度

方向二：重新设计 Composite Confidence（不是删除concentration_factor）
- 说明：concentration_factor（基于香农熵的专注度因子）是应对"多条互相矛盾信号"
  这种混沌场景的数学补丁，若直接去掉，系统会退化成"只看数量、不看冲突"的模型，
  是理论上的倒退，不建议采纳
- 更优的子方向：不删除，而是重新校准，例如用平方根concentration_factor或
  logistic/其他饱和函数替代直接相乘，让early learning阶段不被惩罚这么重
  （这是ML里常见的calibration手法）——若采用此方向，需一并考虑上述的world_share第三层

方向三：重新定义 Stage Promotion（滑动窗口式判定）
- 核心逻辑：不要求单次瞬间冲到0.70，而是"连续N次都超过某个较低阈值"即可晋升
  （控制论里的滑动窗口平滑滤波思路）
- 优势：更贴近教育学直觉（人类学会一样东西通常是"连续表现稳定"而非"啪的一下顿悟"）；
  不需要改动Aggregator的数学核心，只需在CognitiveInertiaDamper里加一条
  "时间轴连续判定"规则，保持数学层纯净、教学策略层承担变通

**验证方式**:
直接调用仓库内真实 BayesianAggregator 与 decide_stage 函数代入两组fixture证据，
数值与理论推导完全吻合，非手工估算。

**状态**:
问题已定位、复现、记录并冻结，尚未修改生产代码。
需进一步设计评审后，决定调整 Composite Confidence、Stage Threshold，
还是重新定义 Stage Promotion，或三者组合。

**方法论意义**:
这是CLVS（Cognitive Layer Verification Suite）发挥作用的第一个真实案例——
它没有发现代码错误，而是发现了算法设计与理论预期之间的不一致，
并在进入真实学生测试之前将其暴露出来。这标志着validation第一次真正推动了
architecture evolution，是Luo-cal Validation Framework成熟的重要标志。

---

## ADR-012: Diagnosis-Promotion 分层解耦

**日期**: 2026-07-15 | **状态**: Accepted
**发现场景**: ADR-011 后续讨论，围绕 effective_confidence 三层乘法的根因分析

**背景**:
ADR-011 已确认 student_A/B 停留在 fragile 不是实现 bug，而是设计一致性问题。进一步的纸面推演揭示了更深层的语义错位：

当前 effective_confidence 是一个三层乘积——evidence_factor（证据够不够）× concentration_factor（信号集中不集中）× world_share（哪个 world 赢了）。这三个因子各自回答不同的问题，但被压缩成一个标量，同时驱动两个性质完全不同的系统行为：描述认知状态（diagnosis）和决定教学进程（promotion）。

举例（示意性数值，非实测结果，实测数据见 ADR-011）：一个学生在若干条纯净同类型证据后，某个 world 的权重已明显占优，但 effective_confidence 仍被 concentration_factor 和 evidence_factor 压低，decide_stage() 判定其为 fragile。Dashboard 告诉老师"学生还不稳定"——这与实际观察到的行为模式产生语义断裂。理论上该标量会随证据积累逐渐收敛并突破 0.70 阈值，但收敛所需的证据量本身就是问题所在。

这不是公式的数学错误。公式在数学上是正确的、可收敛的。问题在于：confidence 刻画的是"系统对自己推断有多确定"（epistemic certainty），而 stage 想回答的是"现在是否该开始针对性教学"（pedagogical readiness）——这是两个不同的问题，被同一个标量绑在了一起。

**核心决定**:
诊断层（Diagnosis）负责回答"学生当前的认知状态是什么"；决策层（Promotion）负责回答"系统现在应该如何行动"。两者可以共享信息，但不应共享判定规则。

1. Diagnosis 与 Promotion 属于两个不同的系统职责。Bayesian Diagnosis 追求统计严谨性，回答"认知状态的最优估计是什么"；Promotion 追求教学及时性与鲁棒性，回答"基于当前估计，是否应该推进教学"。
2. Stage（fragile / emerging / stable）不是 Diagnostic State 的直接映射，而是基于认知状态产生的教学决策。Stage 由独立的 Promotion Policy 产生，而非从 Bayesian confidence 直接映射。Promotion Policy 可以使用持续性判定（Persistence）、时间窗口（Sliding Window）、滞回机制（Hysteresis）或任何其他时序决策方法，其实现不影响 Bayesian Diagnosis。
3. Bayesian Diagnosis 保持统计正确性，不因教学策略的需要而修改其数学行为。Dirichlet 先验的底噪、entropy 对小样本的敏感性——这些都是贝叶斯框架的合法特性，在诊断层保留，不因"学生需要更快升级"而被校准掉。
4. Promotion Policy 可以独立演化，只消费 Diagnostic State，不反向影响诊断层。Promotion 可以基于 Diagnostic State 中的一部分信息（如 dominant world 的一致性、局部 world weight 的稳定性等），无需依赖完整的 effective_confidence 复合标量。未来 Promotion 层的算法升级（例如引入强化学习策略）不应要求修改 Bayesian Diagnosis；反之亦然。

**与 ADR-010 四层架构的衔接**:
本 ADR 不改变 ADR-010 的四层划分，仅在 Layer 3（Cognitive Layer: Mechanism→World→DAN）内部新增一道边界：DAN 只输出 Diagnostic State（各 world 的 confidence、evidence_count、weight_vec 等），不再直接输出 Stage。Stage 由 Promotion Policy 在消费 DAN 输出后产生，其产物仍归属 Layer 3 内部的输出，不上升为 Layer 4（Interaction）的职责，也不改变 Layer 3 对 Layer 4 的服务边界。

**为什么不采用 ADR-011 中"方向一：重新校准 Stage Threshold"或"方向二：重新设计 Composite Confidence"**:
Confidence is an epistemic quantity, whereas promotion is an instructional decision. Recalibrating confidence thresholds cannot eliminate the semantic mismatch between these two objectives.

Confidence 本质上描述的是认知不确定性，而 Promotion 描述的是教学行动，两者属于不同语义层次。单纯调整阈值（如 0.70 → 0.45）或重新设计 concentration_factor 公式，都试图在"保留同一个复合标量驱动 Promotion"这一前提下修补问题。但复合标量天然会将"证据够不够""模式稳不稳""world 是否唯一"这三个不同性质的信息压缩成一个数字——任何调参都只是移动折衷点，没有消除信息丢失。分层解耦从根本上避免了这个问题，实质上是 ADR-011"方向三：重新定义 Stage Promotion"的架构化、原则化版本。

换一个更抽象的说法，可作为全文的一句话总结：Bayesian inference estimates latent cognitive state, whereas instructional progression requires temporal decision policies. Inference and promotion optimize different objectives.

**Consequences**:

Positive：
- Diagnosis 层保持统计一致性，不受教学策略影响，论文可独立论证其数学正确性
- Promotion 层保持教学及时性，不会因贝叶斯底噪而延迟对明显稳定模式的识别
- 两层可独立演化：未来更换 Promotion 算法或升级 Bayesian Diagnosis，互不波及

Negative：
- Promotion 层需要新增独立的状态机逻辑，增加系统复杂度
- 需要维护 Promotion 层的额外参数（窗口长度、持续性阈值等）
- 需要在验证体系中新增 Promotion 专项测试用例（如验证混沌学生不被误放行）

**验证状态**:
Preliminary paper analysis indicates that separating promotion from composite confidence substantially reduces the delay in recognizing stable learning patterns, while preserving Bayesian diagnosis unchanged.

初步纸面分析表明，将 Promotion 与复合 confidence 分离，能在保持贝叶斯诊断不变的前提下，显著缩短识别稳定学习模式的延迟。具体参数和边界规则的验证待 student_C/D 数据补充后完成。代码尚未修改。

**未来原则**:
未来对 Bayesian Diagnosis 的改进不应要求修改 Promotion Policy；未来对 Promotion Policy 的改进也不应要求修改 Bayesian Diagnosis。这一互不侵入原则是本 ADR 冻结的核心约束。

本 ADR 冻结的是架构原则。滑动窗口大小、K/N 容错比例、dominant_world 有效确立的边界规则、局部权重阈值等具体参数与算法选择，属于后续 Promotion Policy Design 文档的范围，不在本 ADR 内冻结。

**方法论意义**:
本次决策标志着从 ADR-011 记录的"参数调优"层面（0.7 还是 0.55、5 条还是 20 条证据）上升到"指标语义与系统架构"层面的讨论——这是 CLVS 推动 architecture evolution 的第二个真实案例。
