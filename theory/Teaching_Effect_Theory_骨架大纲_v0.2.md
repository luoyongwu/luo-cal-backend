# Teaching Effect Theory（骨架大纲 v0.2）

**文档性质声明**：本文档是 Diagnosis Scope 理论文档第 7 节核心原则的展开文档。v0.1 只搭了结构、列了待讨论问题；本版本吸收了一轮讨论后确认下来的结构性调整（层级改名、新增 Retention 层、OLE 命名与初始标签清单、Policy Effect 统计口径），仍然保留大量"待讨论"标注——这不是一份闭环文档，是持续演化的研究提纲。

---

## 0. 开篇原则（已在 Diagnosis Scope 文档中确立，本文档承接）

> The goal of teaching is not to maximize immediate correctness, but to maximize durable changes in reasoning behavior.

> Teaching Effect 不是 Outcome，而是 Trajectory Change（认知轨迹改变）。

---

## 1. 四层效果模型（v0.2 更新：改名 + 新增第四层）

```
Execution（做法层）
    ↓
Strategy（策略层）
    ↓
Transfer（迁移层）
    ↓
Retention（保持层，占位不实现）
```

> **【v0.2 更名说明】** 原骨架用 Behavior / Reasoning 描述前两层，本版本改为 Execution / Strategy——"做法变了"和"思考方式变了"是两个更清晰、维度更统一的描述。已经讨论过的具体判定边界（见 1.1、1.2）原样保留，只是层级名称变化，不需要重新定义边界本身。

### 1.1 第一层：Execution（原 Behavior）

**判定边界（已确认）**：纯动作/格式层。例如：主动列出已知条件、主动画图、主动写出换元映射表。检测方式：关键词与正向正则表达式匹配即可，不需要 LLM 语义提取。

### 1.2 第二层：Strategy（原 Reasoning）

**判定边界（已确认）**：逻辑因果层。例如：主动解释"为什么这里要用分部积分而不是换元"、主动验证边界条件。检测方式：需要 LLM 提取语义标签，不能只靠关键词匹配。

### 1.3 第三层：Transfer

**判定边界（已确认）**：跨概念/跨题型迁移层。在新的 Concept Context 中首次遇到同类结构时，主动采用正确策略。检测方式：需要 Global Scope 跨 Context 关联判断，不是单个 Concept Context 内能独立完成的检测。

### 1.4 第四层：Retention（v0.2 新增，占位不实现）

**为什么新增**：教育学意义上，Transfer 通常不是终点，Retention（比如两个月后是否还能自动使用）才是。这对未来 Learning World Model 的目标函数至关重要——一次教学干预如果只带来短期的 Transfer、没有 Retention，其教育价值需要打折扣。

**当前状态**：V1 完全不实现这一层的检测。理论上先把位置留出来，理由是当前系统的数据留存周期和 Global Scope 更新频率都撑不住"两个月后回顾"这种检测需求，需要等 Global Scope 积累了足够长期的数据资产后再考虑。

### 1.5 层级权重（已确认，非严格递进）

四层之间不是严格递进关系（不要求先出现 Execution 才能出现 Strategy），但权重不同：

```
Execution = 1
Strategy = 3
Transfer = 10
Retention = 待定（远期）
```

**V1 落地范围**：只在 Concept Scope 内检测 Execution 和 Strategy 两层，Transfer 和 Retention 均不在 V1 实现。

---

## 2. Observable Pedagogical Event（v0.2 更名，范围保持不变）

### 2.1 命名调整（已确认）

原称 Observable Learning Event（OLE），本版本改名为 **Observable Pedagogical Event**（仍缩写 OLE），理由：并非所有可观察事件都代表"学生学到了"——有些事件反映的是"老师采取了什么行动"（比如给了提示），把命名从"Learning"收窄为"Pedagogical"更准确，也为未来纳入教师侧事件留了口子。

> **【范围说明，与命名调整分开处理】** 虽然命名扩大了概念范围，但 V1 的标签清单**不扩大到教师侧事件**——教师/系统侧的行为（比如"这一轮注入了什么教学策略"）已经由现有 `teaching_intervention_log` 表记录，不需要再用一套并行的 `[OLE:xxx]` 标签重复记录同一件事。V1 的 OLE 标签清单继续只覆盖学生侧的可观察行为。

### 2.2 检测路径（已确认）：完全复用 detect_ewm() 的技术路径

在后端 API 解析 LLM 回复时，让 SCL 同步输出 `[OLE:XXX]` 标签，复用现有的正则解析基础设施（`detect_ewm()` 的模式），不需要新建独立的检测基础设施。

### 2.3 V1 初始 OLE 标签清单（已确认，4 个）

| 标签 | 名称 | 触发条件 |
|---|---|---|
| `[OLE:SPONTANEOUS_VERIFICATION]` | 主动验证 | 学生在给出答案前，主动检验了边界、定义域或单位 |
| `[OLE:EXPLICIT_REASONING]` | 显式因果解释 | 学生使用了"因为……所以应用某定理"的完整推导，而非仅给出算式 |
| `[OLE:REPRESENTATION_ALIGNMENT]` | 表征主动对齐 | 学生主动画图、画表格，或显式写出变量映射关系（如 u=g(x)） |
| `[OLE:SELF_CORRECTION]` | 对话内自纠 | 在没有 SCL 直接指出错误的情况下，学生根据 SCL 的对比性提问，自己在下一轮主动修正了上一轮的推导 |

**统计粒度（已确认）**：OLE 标签按 Concept Context 粒度统计，即判断该事件在该概念内是否为首次出现。

### 2.4 OLE 与 V1 代理指标（Diagnosis Scope 第 7.4 节）的关系

**待讨论**：Diagnosis Scope v0.3 已给出一个低成本的 V1 代理指标（同概念 3 轮内 EWM 不再复现）。本文档的 OLE 体系建成后，是否用 OLE 完全替代这个代理指标，还是两者并存（OLE 作为更准确的主指标，代理指标作为兜底/交叉验证）？这个切换标准本版本不定义。

---

## 3. Policy Effect：从个体事件到策略级别的聚合（v0.2 更新：改为二维分组）

### 3.1 统计口径调整（已确认）

原骨架只统计 `Policy → OLE`，本版本改为 `Diagnosis → Policy → OLE` 三元组、按 `(locked_mechanism, policy_version)` 二维分组统计：

```
Policy Effect(mechanism, policy_version) = Count(该 mechanism 下、该 policy_version 触发后出现 OLE 的次数) / Total Interventions(该 mechanism, 该 policy_version)
```

**为什么需要二维分组，不能只按 policy 分组**：如果只统计 `Policy → OLE`，无法回答"到底是这个教学策略本身有效，还是这个 mechanism 对应的问题本来就容易被解决"——不同 mechanism 的"天然难度"不同，混在一起统计会掩盖真实的策略效果差异。`teaching_intervention_log` 表已经同时记录了 `locked_mechanism` 和 `policy_version`，二维分组不需要新增字段，只是统计口径的调整。

### 3.2 存储位置（已确认）

独立存放在 Analytics 层，不混入控制论核心（DWM/Diagnosis Working Memory）。建议在 `teaching_intervention_log` 表基础上，新增一张异步聚合的分析表 `policy_effect_stats`，仅用于事后评估不同 `TEACHING_POLICY_VERSION` 的优劣，不参与在线的实时阻尼计算。

---

## 4. 与 Learning World Model（LWM）的接口（远期，不要求本版本回答）

（与 v0.1 一致，保留原状）如果 Teaching Effect 的定义成立，LWM 的目标函数不再是"提高正确率"，而是"学习哪些教学干预最容易引发思维方式的改变"。

**待讨论（远期）**：LWM 训练数据具体从哪些字段构造（Concept Summary + OLE 事件流 + Policy Effect 统计？）；当前数据留存策略是否已经满足这个需求；LWM 是否应该另立第三份文档（初步判断：应另立，本节仅作远期动机说明）。

---

## 5. 最小可验证单元（v0.2 新增）

本文档覆盖的议题（四层效果模型、OLE 标签体系、Policy Effect 聚合、LWM 接口）是一个完整的远期研究议程，不是能一次性闭环的文档。为避免"每节都是开放问题、没有一节能落地"，明确 V1 阶段的最小可验证单元：

> **V1 最小可验证单元 = OLE 初始 4 标签清单（第 2.3 节） + 复用 `detect_ewm()` 技术路径（第 2.2 节）**

理由：这是唯一能立刻用真实对话数据跑起来验证的部分，不需要等三层效果模型的边界完全厘清、不需要等 Policy Effect 的统计口径完全确定。跑起来之后，真实数据会反过来告诉我们哪些 OLE 标签频繁出现、哪些几乎不出现——这比继续在理论层面推演更快、更准。

四层效果模型（第 1 节）、Policy Effect 二维统计（第 3 节）、LWM 接口（第 4 节）可以作为远期规划保留在本文档里，但不阻塞 V1 落地，V1 只做最小可验证单元。

---

## 6. 与现有代码的关系

| 项目 | 现状 | 待建 |
|---|---|---|
| EWM 信号检测 | 已实现（`detect_ewm()`, `ONTOLOGY` 字典） | 可复用同一技术路径 |
| OLE 信号检测 | 不存在 | V1：4 个标签 + 复用现有解析逻辑（第 5 节最小可验证单元） |
| `teaching_intervention_log` 表 | 已实现（ADR-018），已含 `locked_mechanism` 和 `policy_version` 字段 | 待补充 Outcome 相关字段（见 Diagnosis Scope v0.3 第 5.2 节 Concept Summary） |
| `policy_effect_stats` 分析表 | 不存在 | 待设计（依赖 OLE 体系先落地） |

---

## 7. 待讨论问题清单（更新）

1. OLE 与 V1 代理指标的切换标准（第 2.4 节）——何时可以不再依赖"EWM 消失"这个代理指标，改用 OLE 判定教学效果。
2. Retention 层的具体检测机制（第 1.4 节）——远期问题，本版本只占位。
3. Teaching Effect 的归因边界——学生的改变是否真的能归因给某次具体的教学干预？这个问题已在 Diagnosis Scope v0.3 第 14.2 节列为下一轮议题，本文档不重复展开，仅提示两份文档在这一点上是同一个开放问题的两面。

---

**本文档当前状态**：v0.2，四层模型命名、OLE 命名与初始标签清单、Policy Effect 统计口径已确认并整合入正文。最小可验证单元已明确（第 5 节），可据此开始 V1 实现（复用 `detect_ewm()` 技术路径，新增 4 个 OLE 标签）。远期方向（四层模型完整边界、Retention 检测、LWM 接口）继续保留在文档中，不阻塞 V1。
