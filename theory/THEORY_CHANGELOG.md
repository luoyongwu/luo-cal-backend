# Theory Changelog
## Luo-cal 理论变更日志

本文件记录所有理论宪章文档（Ontology、CWM、SCL Spec、White Paper）的
重大决策、开放问题与版本变更历史。

---

## 2026-07-02 — Constitution v1.0 冻结

### 已完成
- Root Cause Ontology v3.0 正式冻结（Constitution v1.0 第一部）
- Cognitive World Model v1.0 正式冻结（Constitution v1.0 第二部）

### Open Questions（开放问题，不影响当前冻结）

**OQ-001：Flow World 命名的本体论类型问题**

- 提出者：DeepSeek 交叉审阅
- 问题：Representation World 与 Approximation World 均为
  Object-oriented（对象性）定位，而 Flow World 本质是
  Process-oriented（过程性）——描述的是推理流程而非认知对象。
  三者理论层级并不完全平行。
- 候选替代名：Reasoning World / Inference World / Procedure World /
  Planning World
- 当前决定：**不在 v1.0 阶段修改**，因为 Flow World 已与 Ontology、
  Dashboard、论文形成一致引用，过早改名会造成理论体系内部不一致
- 复审时机：Phase 2 完成跨学科验证（Linear Algebra / Physics）后
  重新评估

**OQ-002：RWM → FWM 依赖关系**

- 见 COGNITIVE_WORLD_MODEL_v1.0.md 第4.2节
- 初步观察：RWM 稳定性可能是 FWM 稳定性的前提条件
- 当前决定：标注为 Hypothesized Dependency，不写入正式理论
- 复审时机：Phase 2 真实学生数据积累后

---

*Luo-cal Cognitive Layer Engineering | 硅基智库*

## 2026-07-02 — SCL Specification v1.0 冻结 + 命名变更

### 已完成
- SCL Specification v1.0 正式冻结（Constitution v1.0 第三部 / Volume III）
- 三卷体系正式命名：Volume I (Ontology) / Volume II (CWM) / Volume III (SCL Spec)

### 命名变更（Naming Change）

**NC-001：SCL 全称变更**

- 提出者：DeepSeek 交叉审阅
- 变更前：Socratic Constraint Layer
- 变更后：**System Constraint Layer**（缩写 SCL 不变）
- 理由：SCL 约束的内容（Leakage、Hard Rule、Provider、Adapter、MADNESS）
  均不特定依赖苏格拉底式对话，与 Ontology 中 Adaptive Cognitive
  Intervention 的术语升级保持一致
- 影响范围：仅文档表述，不影响现有代码变量名（如需同步修改代码注释，
  留待下次工程迭代处理，不影响功能）

### Open Questions（新增）

**OQ-003：Leakage Score 加权口径的历史数据重算**

- 问题：A1-A4 消融实验数据基于旧版计数口径（Count-based）采集，
  v1.0 引入加权口径（Weighted）后尚未重新计算
- 当前决定：暂不重算，两种口径并存于文档中，明确标注数据来源口径
- 复审时机：Phase 2 补充分析

## 2026-07-02（续）— SCL Specification v1.0 修订

### DeepSeek 双重交叉审阅后的必须性修改（8处，全部完成）

1. 架构图加入 DAN Memory 节点：CWM → DAN Memory → Dashboard
2. 新增 Provider 验证要求：从至少一轮改为全部11个MADNESS探针
3. P0/P1 判断标准明确化：能否穷举安全例外
4. Hint Leakage 边界说明：学生已隐含信息时不算主动泄漏
5. Reflection 实现状态标注：跨会话计数器留待Phase 2
6. Adapter契约要求：system参数不得截断改写
7. Hard Rule清单冻结范围声明
8. 第0章补充Constitution/Specification/Implementation三层修改门槛

### 三卷术语交叉验证结果

DeepSeek 对 Ontology / CWM / SCL 三卷进行术语一致性检查，未发现冲突。

### Constitution v1.0 三部曲正式完整落定

- Volume I: ROOT_CAUSE_ONTOLOGY_v3.0.md
- Volume II: COGNITIVE_WORLD_MODEL_v1.0.md
- Volume III: SCL_SPECIFICATION_v1.0.md

## 2026-07-03 — White Paper v1.0 冻结（Constitution v1.0 第四部 / Volume IV）

### 已完成

- `WHITE_PAPER_v1.0.md`（英文）与 `WHITE_PAPER_v1.0_CN.md`（中文）正式冻结
- 定位确立：White Paper 为**对外综合文档**（Volume IV）——三卷定义，白皮书论证。四份文档共同构成 Constitution v1.0
- 品牌层级正式确立：**Cognitive Layer Engineering (CLE)** 为范式主体；Luo-cal 为 CLE 的 reference implementation；AP 微积分为第一个验证域

### 文档主题句（Thesis，正式确立）

> Teaching constraints should not be prompts. They should be architecture.

配套核心洞见（引自受约束模型自我分析，已在 Ontology 命题1 / SCL 规范中呼应）：
> what must be suppressed is not error, but premature correctness.

### CLE 正式定义（可引用）

> A cognitive layer is an explicit, auditable, model-independent layer that governs how an AI system may affect the learner's cognitive state.

### DeepSeek 交叉审阅（两轮）

**第一轮（作者意见 + DeepSeek 结构诊断）：** 文档职责重新设计——从"三卷串联摘要（作者视角）"重构为"架构宣言（读者视角）"，采用 Problem → Why → Architecture → Components → Validation → Future 路径。7 项升级全部采纳：Thesis 首页化、CLE 可引用定义、Student-in-loop 闭环大图（图2）、认知栈（The Cognitive Stack）命名、Positioning 对比章、CLE-first 品牌层级、结尾回归架构。

**第二轮（DeepSeek 逐章评估）：** 结构判定为可冻结。4 处小修全部采纳：
1. 三个失败现象概念标签化（Benevolent Leakage / Reassuring Error Confirmation / Tutoring Hallucination）
2. 图2 增补 EWM 观察范围澄清（EWM 信号是认知状态的唯一直接观察窗口，但非系统唯一接收的信息）
3. 身份层措辞与 Volume I 对齐（"否决固定身份标签"而非"否决身份层"，补入"定期重新评估"）
4. Positioning 对比表下方增补"CLE 是补充，不是竞争"说明
5.（可选）OQ-003 加权口径重算标注预期解决时间（Phase 2 扩展消融）

### 数据口径声明（承接 OQ-003）

消融实验 A1–A4 数据（6.1 / 4.8 / 0 / 0，每12探针）采用原始计数口径。加权口径重算排期于 Phase 2 扩展消融分析。两种口径并存，每处数字标注来源。

### 引用规则

- 四份文档（Ontology / CWM / SCL Spec / White Paper）为后续代码、论文、仪表板、Provider 接入的唯一规范来源
- White Paper 不定义理论，仅论证；措辞与三卷冲突时以三卷为准
- 后续对外发表（arXiv / The Gradient）以本白皮书为叙事基线

## 2026-07-04 — cognitive_signals 表结构修复：补齐 root_cause / error_level / cognitive_dimension 字段

### 发现过程

在 v3.0 PCSA（Persistent Cognitive State Architecture）Phase 1 开发过程中，为搭建 `dan_state` 表并接入 `DANMemoryService`，需要核对 `main.py` 现有代码与 `cognitive_signals` 真实表结构是否一致。核对时发现：

- 之前另行提供的"生产环境 DDL"描述（字段名 `concept_id`、`error_signal`、`cognitive_mechanism`、`session_id`、`confidence` 等）与 `main.py` 实际执行的 `INSERT` 语句字段名（`concept`、`signal`、`root_cause`、`error_level`、`cognitive_dimension` 等）完全对不上
- 通过 `information_schema.columns` 查询真实表结构，确认表中实际只有 10 个字段：`id, student_id, concept, signal, timestamp, dan_profile, trigger_context, intercept_result, fwm_predicted_next_error, fwm_prediction_accuracy`
- `main.py` 的 `write_signal()` 函数试图写入的 `root_cause`、`error_level`、`cognitive_dimension` 三个字段，在真实表中**不存在**

### 根因

`write_signal()` 函数用 `try/except` 包裹插入操作，异常仅 `print` 到 stdout，不抛出、不持久化记录：

```python
def write_signal(student_id, concept, signal, trigger_context, intercept_result):
    try:
        ...
        supabase.table("cognitive_signals").insert({...}).execute()
    except Exception as e:
        print(f"Signal write error: {e}")
```

只要这三个字段在插入语句中，PostgREST 会拒绝整条插入，但错误被静默吞掉，学生端的教学对话（错误检测、拦截、苏格拉底引导）不受影响，唯独这条错误信号从未被记录进数据库。

### 触发场景评估

用探针插入（`student_id = 'TEST_PROBE'`）复现确认：插入语句在字段补齐前必然失败（`column "root_cause" of relation "cognitive_signals" does not exist`）。

同时确认这**不是一次数据丢失事故**：现有的 18 条历史 EWM 信号记录（截至 2026-06-24）均不含这三个字段，推断为字段加入代码之前写入的旧数据；此后系统没有真实学生使用，`write_signal()` 未被实际调用过，因此没有静默失败的真实发生记录——这是一个在正式上线前被提前发现、从未被触发的休眠 bug。

### 修复（方案 B：改数据库以保留机制归因信息）

评估过两种修复路径：
- 方案 A（改代码）：删除三个字段的写入，改动最小，但会丢失机制归因信息——这正是 Root Cause Ontology 的核心产出，且是 Phase 2 Evidence Aggregation Engine 未来需要读取的证据来源
- 方案 B（改数据库，采纳）：`ALTER TABLE` 补齐缺失字段，代码不变，保留机制归因数据完整性，与正在建设的 PCSA 架构方向一致

```sql
ALTER TABLE cognitive_signals
ADD COLUMN IF NOT EXISTS root_cause VARCHAR(50),
ADD COLUMN IF NOT EXISTS error_level VARCHAR(20),
ADD COLUMN IF NOT EXISTS cognitive_dimension JSONB;
```

修复后用同一探针插入语句重新验证，写入成功；测试数据已清理。

### 影响范围

- `cognitive_signals` 表新增三列，不影响现有数据
- `dan_state` 表及其 Phase 1 回填（30 行）不受影响——Migration 脚本仅使用 `student_id` 字段
- `main.py` 代码无需改动
- 遗留问题：`main.py` 中 `ONTOLOGY` 字典使用 `ExecutionIntegrity` 命名，与 Volume I 冻结的 `SemanticIntegrity` 不一致，属独立的命名层面遗留问题，记录于此，暂不在本次范围内处理

### 后续建议

- `write_signal()` 的静默 `except` 应升级为至少写入结构化日志（而非仅 `print`），避免同类问题未来再次无声发生
- 建议在 Phase 4 的 Constitution Audit / CI 流程中加入一项：部署前自动比对 `main.py` 的插入字段与数据库真实 schema，提前拦截此类漂移


## SCL "绕圈子"现象的普遍性确认（2026-07-11晚）

**触发场景**：001号学生 flow 测试（目标信号 EWM_B1C，概念 B1）过程中观察到，学生连续给出正确答案后，SCL 不确认推进，反而追加不必要的回溯性/验证性追问。为确认这不是 B1 或 003 号学生的个例，追加测试 001 号在 7.2（可分离变量微分方程，唯一答案型任务）与 7.1（斜率场，开放式定性任务）两个不含"loop"关键词的概念。

**结果**：四案例（003/5.4、001/B1、001/7.2、001/7.1）全部复现同一模式——学生给出正确、完整答案后，SCL 不确认+推进，而是继续追问已解决的细节、要求重新推导/验证，或回溯到已完成步骤。绕圈子首次出现的轮次：003/5.4 较早；001/B1 第3-4轮（连续正确后）；001/7.2 第2轮；001/7.1 第2轮（最快）。

**结论**：绕圈子与任务是否有唯一答案、是否触发 EWM 错误信号均无关，是 SCL 在"子步骤/任务完成判定"环节的通用性缺陷，比最初判断（认为局限于 B1 类多步骤概念）覆盖范围更广。

**发现方式**：001号 flow 测试及后续三个对照案例，人工审查 SCL 对话记录发现。

---

## 【修复尝试】SCL prompt Rule 6：任务完成推进（2026-07-11晚，main.py）

**原因**：上条"绕圈子"问题的轻量级修复，作为"简单处理先扛住、优雅方案留待因材施教阶段"策略的落地。

**修改前后对比**：`SCL_SYSTEM_PROMPT_ZH/EN`（main.py）核心规则新增 Rule 6——学生给出正确完整答案后必须确认+推进（出新题/进阶应用题/明确收尾），禁止无限回溯验证，同一答案最多允许一次巩固性追问。

**验证结果**：**部分有效，不稳定**。以 001/7.1 为例：Rule 6 部署后重测同一节点，第一个关键节点（"零斜率线"确认）表现为干净推进；但紧接着第二个节点（"斜率变化趋势"确认）又复现绕圈子，SCL 重复追问学生刚回答过的信息。

**初步判断**：Rule 6 对"正确/完整"的判据本身不够明确，在开放式定性任务（如7.1）中"回答是否完整"比有唯一答案的任务更模糊，导致模型对是否该推进的判断不稳定。提示 Requirement 5（SCL Adaptive Use of DAN）的 Canonical Profile 设计应按任务类型（唯一答案型 vs 开放定性型）分别设计判据，而非单一通用规则。

**触发场景记录**：001号，7.1，重测时间紧接 Rule 6 部署后（同一 commit 生效期间）。

**发现方式**：Rule 6 部署后针对已知复现节点做回归重测。


## 【修复尝试-续】SCL prompt Rule 6 v2：新增信息重复检测（2026-07-12晚，main.py）

**原因**：针对 v1 在 001/7.1 实测中暴露的具体失败模式——学生在回答中已明确说明"x-y变成负数"，SCL 仍重复追问"x-y是正数还是负数"。v1 依赖"正确/完整"这一抽象判据，在开放式任务中容易被模型绕过；v2 换成更机械、更难规避的检查。

**修改内容**：`SCL_SYSTEM_PROMPT_ZH/EN`（main.py）Rule 6 升级为"任务完成推进（含信息重复检测）"——新增强制自查：提出下一个问题前，必须核实该问题答案是否已明确出现在学生上一轮回复文本中；如果是，禁止提问，必须换成要求新信息/新计算/新判断角度的问题。

**验证结果**：**积极，v2部署后立即用001/7.1回归重测**。连续两个关键节点表现均为干净推进：
1. "零斜率线"确认节点——确认后直接推进（与v1表现一致，非新增证据）
2. "斜率符号(x-y>0)"确认节点——**这是v1曾经复现绕圈子的确切节点**。v2版本下，SCL确认后不仅未重复追问，而是直接跳出当前分析框架，出示一道全新的综合应用题（结合两条直线的不等式组区域问题），表现出真正的进阶推进，是四次尝试（v1两轮+v2两轮）中最好的一次。

**当前判断**：v2在已知失败节点上的针对性修复看起来有效，但样本量仍有限（同一学生同一概念的一次回归测试）。历史观察显示部分绕圈子案例要到第3-4轮才复现，因此暂不宣布"已解决"，标记为"初步验证通过，待更多样本（不同概念/不同学生）确认稳定性"。后续验证可纳入13-16号计划或CLVS Requirement 5的Canonical Profile回归集。

**触发场景记录**：001号，7.1，Rule 6 v2部署后立即回归重测，同一对话session连续两个节点。

**发现方式**：针对v1已知失败节点做定向回归验证。


## 【修复尝试-续2】SCL prompt Rule 6 v2：003号学生/5.4回归验证（2026-07-13，main.py未改动，纯验证记录）

**目的**：此前 Rule 6 v2 仅在 001号/7.1（开放式定性任务，无EWM信号触发路径）验证过。为巩固证据强度，需要在"错误信号触发路径 + 唯一答案型任务"这一组合下补测——这恰好是本次绕圈子排查最早发现问题的原始场景（003/5.4），也是历史上 v1 曾经复现失败的路径类型（对照001/B1）。

**测试设计**：003号学生在5.4（换元定积分）故意在换元后保留原x积分限（触发`BOUNDS_TRAP`），观察SCL引导纠正后的推进表现。

**结果**：**通过**。`[EWM:BOUNDS_TRAP]`正确触发，SCL反问"这两个数字原本是哪个变量的范围"；学生给出正确纠正（改用u的范围1到2，算出正确结果）后，SCL立即确认"完全正确！...你的计算结果...是对的"，且未做任何重复追问或回溯验证，直接推进到一道全新的进阶换元积分题（`∫sinx cosx dx`）。

**累计证据汇总**：

| 案例 | 触发路径 | 任务类型 | Rule 6版本 | 结果 |
|---|---|---|---|---|
| 001/B1 | 错误信号 | 唯一答案 | v1 | 绕圈子(3-4轮后) |
| 001/7.1(节点1) | 无 | 开放定性 | v1 | 通过 |
| 001/7.1(节点2) | 无 | 开放定性 | v1 | 绕圈子 |
| 001/7.1(两节点) | 无 | 开放定性 | v2 | 通过+进阶 |
| 003/5.4 | 错误信号 | 唯一答案 | v2 | 通过+进阶 |

v2已在两个学生、两种任务类型（唯一答案/开放定性）、两种触发路径（错误信号/正常流程）下验证通过，且"错误纠正后确认推进"这条此前v1最容易失败的路径（对照001/B1）在v2下同样表现良好。

**当前判断**：证据强度已足以支撑"Rule 6 v2基本稳定"的阶段性结论。暂停本轮回归测试，转入`verification_runner.py`开发。后续若在CLVS Level 3场景验证（完整学习路径/连续答题）中发现新的失败节点，再针对性追加案例，不再专门为Rule 6单独安排测试时段。

## CLVS 首次全量闭环验证：ADR-012 Promotion Policy 与真实贝叶斯聚合器联调（2026-07-15，promotion_policy.py 新增，inference_pipeline.py 未改动）

**背景**：ADR-011 记录的 Composite Confidence 设计一致性问题（student_A/B 两个理想学习路径在旧算法下永远停留在 fragile）此前已冻结为架构决策 ADR-012（Diagnosis-Promotion 分层解耦），并落地为独立的 `promotion_policy.py` 模块（参数：N=5, K=4, Margin=0.15, θ=0.55，另加 Yongwu + DeepSeek 交叉审阅时补充的降级保护 demote_below=3）。本条记录该模块首次接入真实 `inference_pipeline.py` 的 `BayesianAggregator` 后，用 `validation/student_archetypes/` 四份 Canonical Profile（SYN_A/B/C/D）做端到端 Replay Fidelity 验证的结果。

**触发场景**：`promotion_policy.py` 完成本地纸面自检（含 Student C 混合交织场景发现并修复两处问题：①argmax 伪主导需要 Margin 过滤，②Stable 锁存需绑定具体 world 身份而非任意 world 的票数，否则可能静默误判）后，接入真实聚合器做首次正式回归验证。

**结果**：**通过**。四组 Canonical Profile 全部符合预期：

- SYN_A_REPRESENTATION：第5轮进入 `stable`（RWM=0.8571），此前在旧算法下永远停留在 fragile 的问题解决
- SYN_B_FLOW：第5轮进入 `stable`（FWM=0.8214），同上
- SYN_C_MIXED：全程未误入 `stable`，第6轮起进入 `emerging`（RWM=0.60, FWM=0.2611, AWM=0.1389, confidence=0.1333，与 fixture 文档记录的推演值在容差内完全吻合）
- SYN_D_UNCERTAIN：全程未误入 `stable`，最终 `fragile`（RWM=0.475, FWM=0.3375, AWM=0.1875, confidence=0.0534，与 fixture 文档记录的推演值完全一致）

四组 fixture 文档中标注"已用 inference_pipeline.py 真实推演"的数字，本次用独立运行的方式核实，全部在容差范围内吻合，验证了 CLVS 校准方法论本身的可信度。

**关于 confidence 数字的定义（回应 DeepSeek 2026-07-15 评阅）**：DeepSeek 交叉评阅时指出，上述 confidence 数字（如 SYN_C 的 0.1333、SYN_D 的 0.0534）未在记录中给出公式，读者无法独立复算；DeepSeek 尝试用 Pmax−Psecond 反推但不匹配，这个尝试本身也说明缺定义确实会造成歧义。经核实，真实公式定义于 `BAYESIAN_AGGREGATOR_SPEC_v0.2.md`，代码实现在 `inference_pipeline.py::BayesianAggregator._aggregate()`：

```
confidence = evidence_factor × concentration_factor
evidence_factor = 1 − 1/(1+effective_sample_size)
concentration_factor = 1 − entropy/H_MAX，H_MAX = ln(3)
entropy = −Σ p·ln(p)，对 world_weights 中每个 p>0 求和
```

用此公式对四组 Profile 的最终 tick 逐一手工反推验证，全部精确匹配（entropy、effective_sample_size 数值已随 `ADR012_promotion_policy.json` 的 ticks 明细一并导出，供后续复算）：

| Profile | entropy | effective_sample_size | 计算得 confidence | 记录值 | 匹配 |
|---|---|---|---|---|---|
| SYN_A (round5) | 0.4904 | 5.0 | 0.4613 | 0.4613 | ✅ |
| SYN_B (round5) | 0.5586 | 5.0 | 0.4096 | 0.4096 | ✅ |
| SYN_C (round7) | 0.9313 | 7.0 | 0.1333 | 0.1333 | ✅ |
| SYN_D (round10) | 1.0341 | 10.0 | 0.0534 | 0.0534 | ✅ |

**观察到但不构成失败的现象（记录，不视为 bug）**：

1. SYN_D_UNCERTAIN 在第5-8轮附近于 `fragile` 与 `emerging` 之间短暂振荡后回落至 `fragile`。这是设计上刻意的取舍——ADR-012 讨论时决定只给 `stable` 加滞回锁存（因为晋升 stable 是"郑重宣布"、教学意义上代价较高的动作），`fragile`↔`emerging` 之间保持高灵敏度浮动（"战术级试探"，仅影响呈现层的引导强度）。是否需要为这条边界也加保护，取决于 Dashboard 是否会把 `emerging` 状态展示给老师；本次暂不处理，留待 Dashboard UX 需求明确后再评估。
2. SYN_A_REPRESENTATION 前4轮（窗口未填满）一律强制显示 `fragile`，即使这几轮 dominant_world 已经高度一致，不会提前显示 `emerging`，导致第5轮从 `fragile` 直接跳到 `stable`，中间没有过渡态。2026-07-15 与 Yongwu 确认：暂不修改，留待 Dashboard UX 阶段一并评估。

**已确认非本次范围**：DeepSeek 交叉评阅时提及的 `_validate_theory_boundary()` 熔断机制，经核实仓库中不存在此函数，`verification_runner.py` 未依赖它。仓库中已有的回归资产命名习惯（如 `validation/regression/ADR008_reflection.json`）已沿用至本次产出 `validation/regression/ADR012_promotion_policy.json`。

**当前判断**：ADR-012 从架构原则到具体实现的完整链条（原则 → 参数设计 → 真实代码 → fixture 数值交叉核对）已闭环，作为 CLVS 首份正式回归基线固化。后续任何改动 Aggregator 或 Promotion Policy 的工作，应重跑 `validation/verification_runner.py` 并与本基线 diff，观察行为是否漂移。

**发现方式**：`promotion_policy.py` 本地模拟自检 → Yongwu + DeepSeek 两轮交叉审阅（新增 Margin/θ 调整、Stable 滞回锁存）→ 接入真实 `BayesianAggregator` 端到端验证。

## 发现：两套 verification_runner.py 并存，PromotionPolicy 尚未接入生产管道（2026-07-16）

**背景**：
排查根目录下 `verification_runner.py`（"2 days ago"）与 `validation/verification_runner.py`（本次 ADR-012/013 工作新增）为何同名时发现，两者不是新旧版本关系，而是两套完全独立、职责不同的验证器。

**发现过程**：
核对根目录 `verification_runner.py` 源码后确认三点：

1. **两套 runner 的定位完全不同**。根目录版本是真正的生产级验证器——真实连接 Supabase（`create_client`）、真实调用 `DANMemoryService`、真实走 `main.py` 生产环境同一条 `run_pipeline()` 调用链，并用 `glob` 自动扫描 `validation/student_archetypes/*.json` 下全部 fixture 逐一验证。`validation/verification_runner.py`（本次新增）是独立的沙盒版本——不接数据库，直接调用 `BayesianAggregator`/`PromotionPolicy`，Student A-E 的证据序列写死在 Python 字典 `CANONICAL_PROFILES` 里，并不读取磁盘上的 fixture JSON 文件。

2. **新增的 `SYN_E_RECOVERY.json` 会被生产级 runner 自动扫到，但读不懂**。生产级 runner 靠字段名后缀（`_gte`/`_lte`/`_lt`/`_gt`）自动判定断言；`SYN_E_RECOVERY.json` 使用的字段名（`requires_dual_scale`、`recent_world_weights_expected`、`transitional_dip_between_ticks`、`recovery_tick_lte`、`final_locked_world`）不在其识别范围内，会被全部归入"人工复核清单"，不产生任何有效自动断言——不会报错崩溃，但也不会真正验证到任何东西。

3. **`run_pipeline()` 目前调用的仍是旧的 `decide_stage()`，不是 `PromotionPolicy`**。生产级 runner 依赖的 `inference_pipeline.run_pipeline()` 内部编排仍是 `aggregate() → dampen() → decide_stage()`——就是 ADR-011 记录的、effective_confidence 三层乘法有设计一致性问题的那个旧函数。也就是说，**ADR-012（PromotionPolicy）与 ADR-013（aggregate_dual_scale）这两项工作，截至目前从未真正接入生产管道**。本次 A-E 五组"全部 PASS"，验证的是 `PromotionPolicy` 这套设计本身在独立沙盒环境下成立，尚未验证接入 `run_pipeline()` 生产路径后是否依然成立。若现在直接运行根目录的生产级 runner，Student A/B 大概率仍会停留在 `fragile`（因为它走的还是旧公式）。

**关于 `_validate_theory_boundary()` 的悬案澄清**：此前（ADR-012 阶段）确认仓库中不存在名为 `_validate_theory_boundary()` 的函数。这次核对发现该字符串确实出现在根目录 `verification_runner.py` 里，但只是 `check_numerical_health()` 函数中一句 `print` 的描述性文字（`"全部 step 通过 _validate_theory_boundary()"`），代码实际逻辑只是普通的 `except ValueError`，并非真实存在的熔断函数。此前"不存在此函数"的结论依然成立，但找到了 DeepSeek 当初提及这个名字的可能来源。

**影响范围**：
- 根目录 `verification_runner.py`：不受影响，保留，不需要删除或修改
- `validation/verification_runner.py`：沙盒验证器定位不变，继续作为 CLVS 快速迭代/纸面验证工具使用，但需要明确其验证范围边界（见下）
- `validation/student_archetypes/SYN_E_RECOVERY.json`：目前只被沙盒 runner 消费，生产级 runner 扫到后不会产生有效断言，需要后续补充字段兼容或专门的断言分支

**当前判断（范围边界声明）**：
本次 A-E 五组验证（含 ADR-012/013 全部工作）验证的是"PromotionPolicy 与 aggregate_dual_scale 这套设计本身是否成立"，尚未验证"接入生产管道后是否成立"。这不是疏漏，是 Montreal 出发前的合理范围控制——触碰 `run_pipeline()`/`decide_stage()` 属于生产代码改动，按既定原则不适合在出发前一天匆忙推进。

**后续待办（留待返程后处理，非本次范围）**：
1. 将 `PromotionPolicy` 正式接入 `inference_pipeline.run_pipeline()`，替换其中的 `decide_stage()` 调用
2. 决定 `SYN_E_RECOVERY.json` 的字段是否要改写为生产级 runner 认识的后缀格式（`_gte`/`_lte`等），还是给生产级 runner 补充一个能识别 dual-scale 特殊断言的分支
3. 生产级 runner 接入 `PromotionPolicy` 后，需要重新跑一遍 A-E 五组，确认沙盒环境里验证过的行为在真实 Supabase + `DANMemoryService` 路径下依然成立
4. 考虑是否需要给两套 runner 改个更容易区分的命名（例如 `validation/verification_runner.py` 改名为 `validation/promotion_policy_sandbox_runner.py`），避免未来同名引发混淆

**发现方式**：核对 GitHub 仓库文件列表时发现根目录存在同名文件，人工比对源码后确认。
