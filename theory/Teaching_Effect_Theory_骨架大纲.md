# Teaching Effect Theory（骨架大纲，待展开）

**文档性质声明**：本文档是 Diagnosis Scope 理论文档 v0.2 第 7 节的展开文档。v0.2 已确立核心原则（Trajectory Change，非 Outcome），本文档负责把这条原则展开成可讨论、最终可实现的完整体系。当前版本只搭结构、列出每一节需要回答的问题，不填具体结论——留给下一轮讨论逐节填充。

---

## 0. 开篇原则（已在 v0.2 确立，本文档承接）

> The goal of teaching is not to maximize immediate correctness, but to maximize durable changes in reasoning behavior.
> （教学的目标不是最大化学生眼前答对，而是最大化学生推理行为的持久改变）

> Teaching Effect 不是 Outcome，而是 Trajectory Change（认知轨迹改变）——教学是否改变了学生下一步思考的方式，而不是是否立即改变了最终答案。

---

## 1. 三层效果模型（结构已提出，需要逐层定义可观察标准）

```
Behavior Change（行为改变）
    ↓
Reasoning Change（推理改变）
    ↓
Transfer（迁移）
```

**待讨论**：

- 每一层各自的、可以从对话文本里检测出来的具体触发标准是什么？
- 三层之间是否是严格递进关系（必须先有 Behavior 才能有 Reasoning），还是可以跳层出现？
- 三层各自对应的教学"含金量"权重是否不同（比如 Transfer 远比 Behavior Change 更有价值）？如果是，权重如何量化？

### 1.1 第一层：Behavior Change

候选例子（待确认、待补充）：开始画图、开始写条件、开始检查步骤。

**待讨论**：这一层的判定是否可以完全基于关键词/行为模式匹配（比如检测到学生主动提及"我先画个图"），还是需要更复杂的语义判断？

### 1.2 第二层：Reasoning Change

候选例子（待确认、待补充）：开始主动解释"为什么"、开始比较两种方法、开始主动验证。

**待讨论**：这一层和第一层的边界在哪？"开始检查步骤"算 Behavior 还是 Reasoning？

### 1.3 第三层：Transfer

候选例子（待确认、待补充）：下一道新题（可能是不同概念）自动采用同一种策略。

**待讨论**：Transfer 的检测天然需要跨概念、跨时间窗口，这和 Diagnosis Scope v0.2 里 Concept Context 的挂起/关闭生命周期如何对接？是否需要 Global Scope 参与才能检测到 Transfer？

---

## 2. Observable Learning Event（OLE）：可观察事件体系

### 2.1 核心思路（已在讨论中提出）

Teaching Effect 本身不能被直接观察，能被观察的是**事件**（Event）。例如：

- 学生第一次主动画图
- 第一次主动检查单位
- 第一次主动解释为什么

**待讨论**：

- OLE 的完整分类体系是什么？需要列出一份初始的 OLE 标签清单（类比现有的 EWM 信号清单：`BOUNDS_TRAP`、`PRE_SUBSTITUTION` 等），供团队讨论增删。
- OLE 检测是否可以复用现有 `detect_ewm()` 的技术路径（Claude 输出标签、后端正则解析），比如新增 `[OLE:SPONTANEOUS_VERIFICATION]`、`[OLE:FIRST_EXPLANATION]` 这类标签？
- OLE 和 EWM 是否共享同一套系统提示词基础设施（`SCL_SYSTEM_PROMPT`），还是需要独立维护一套？
- "第一次"如何界定——是该学生在该 Concept 内第一次，还是该学生在整个 Global 历史里第一次？这两种定义对应的教学意义不同。

### 2.2 OLE 与 Learning Outcome（v0.2 第 7.4 节 V1 代理指标）的关系

**待讨论**：v0.2 已经给出一个低成本的 V1 代理指标（同概念 3 轮内 EWM 不再复现）。OLE 体系建成后，是否用 OLE 完全替代这个代理指标，还是两者并存（OLE 作为更准确的主指标，代理指标作为兜底/交叉验证）？

---

## 3. Policy Effect：从个体事件到策略级别的聚合

**已在讨论中提出的候选方向**：Global Scope 未来积累的可能不是正确率，而是 OLE 出现的模式。例如：

> FlowReasoning → Policy V2 → 平均在第 3 轮开始出现"主动总结"这一 OLE

**待讨论**：

- 这类"策略 → 平均第几轮触发某类 OLE"的统计，应该存在哪里？是 Global Scope 的一部分，还是需要一个独立的、专门服务于教学策略研究的分析层？
- 这类统计的最小样本量是多少才有意义？在样本不足时如何呈现（避免过早给出误导性结论）？
- 是否需要为不同的 `TEACHING_POLICY_INJECTIONS` 版本（`TEACHING_POLICY_VERSION`）分别统计 Policy Effect，从而支持未来的教学策略 A/B 对比？

---

## 4. 与 Learning World Model（LWM）的接口

**已在讨论中提出的方向**：如果 Teaching Effect 的定义成立，LWM 的目标函数不再是"提高正确率"，而是"学习哪些教学干预最容易引发思维方式的改变"。

**待讨论（远期，不要求本轮回答）**：

- LWM 的训练数据具体从哪些字段构造？（Concept Summary + OLE 事件流 + Policy Effect 统计？）
- 这是否意味着未来需要收集大量真实学生的完整对话轨迹作为训练语料，当前的数据留存策略（v0.2 第 6 节归档规则）是否已经满足这个需求？
- LWM 是本文档的范畴，还是应该另立第三份文档？（初步判断：应另立，本节仅作为"为什么 Teaching Effect 定义方式很重要"的远期动机说明，不在本文档展开 LWM 本身的设计）

---

## 5. 与现有代码的关系（现状盘点，待补充）

| 项目 | 现状 | 待建 |
|---|---|---|
| EWM 信号检测 | 已实现（`detect_ewm()`, `ONTOLOGY` 字典） | 可复用同一技术路径 |
| OLE 信号检测 | 不存在 | 待设计标签体系 + 复用/新建解析逻辑 |
| `teaching_intervention_log` 表 | 已实现（ADR-018），记录干预注入事件 | 待补充 outcome 相关字段 |
| Policy Effect 统计 | 不存在 | 待设计（依赖 OLE 体系先建成） |

---

## 6. 优先级建议（供下一轮讨论参考，非定论）

1. 先确定 OLE 的初始标签清单（哪怕只有 3-5 个最容易检测的事件类型），因为这是整个体系里唯一能立刻复用现有基础设施（`detect_ewm` 模式）落地的部分。
2. 再讨论三层模型（Behavior / Reasoning / Transfer）里每一层的具体判定标准，特别是第一层与第二层的边界。
3. Policy Effect 聚合和 LWM 接口属于远期方向，本轮不需要深入，只需要在数据存留策略上不要把路堵死（比如第 6 节现状盘点里提到的字段扩展要留有余地）。

---

**本文档当前状态**：骨架大纲，所有"待讨论"标注的问题均为开放项，等待下一轮讨论逐项填充为正式结论后，参照 Diagnosis Scope v0.2 的文档结构（区分"已确定"与"待确定"）整理成正式版本。
