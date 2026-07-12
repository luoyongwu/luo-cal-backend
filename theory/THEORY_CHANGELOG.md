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
