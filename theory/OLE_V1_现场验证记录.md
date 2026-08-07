# OLE V1 现场验证记录（2026-08-07）

**文档性质**：Teaching Effect Theory v0.2 第 5 节"最小可验证单元"部署后的首次真实现场验证记录。补充材料，不是理论文档正文，供后续 Teaching Effect Theory 修订时参考。

---

## 一、验证目的

`main.py` 接入 `detect_ole()`/`strip_ole_tags()` 并推送部署后，现场验证两件事：

1. OLE 标签是否能被正确检测、正确写入 `teaching_intervention_log.ole_events`；
2. OLE 标签是否会像此前 EWM 标签那次一样泄漏给学生看到。

---

## 二、验证方式

概念 5.4（换元积分法），授权码 2。针对 4 个 V1 初始标签逐一设计场景，故意在回答中做出对应的行为，观察系统是否正确打标、且不泄漏。

## 三、结果汇总

| 时间 | 设计意图 | 实际检测结果 | 界面是否泄漏 |
|---|---|---|---|
| 19:11-19:12 | `REPRESENTATION_ALIGNMENT`（显式写出 u=1+x² 映射） | `[]`（未触发） | 无泄漏 |
| 19:13-19:14 | `SPONTANEOUS_VERIFICATION`（主动检查边界） | ✅ `["SPONTANEOUS_VERIFICATION"]` | 无泄漏 |
| 19:25 | `EXPLICIT_REASONING`（完整因果推导选 u） | ✅ `["EXPLICIT_REASONING"]` | 无泄漏 |
| 19:26 | `SPONTANEOUS_VERIFICATION`（第二次，边界换算） | ✅ `["SPONTANEOUS_VERIFICATION"]` | 无泄漏 |
| 19:27 | `SELF_CORRECTION`（对比性问题引导下自我纠正） | `["EXPLICIT_REASONING"]`（未按预期触发） | 无泄漏 |
| 19:28 | 收尾回答（延续同一因果推导） | `["EXPLICIT_REASONING"]` | 无泄漏 |

**总计**：6 次有意设计的交互，`EXPLICIT_REASONING` 命中 3 次，`SPONTANEOUS_VERIFICATION` 命中 2 次，`REPRESENTATION_ALIGNMENT` 与 `SELF_CORRECTION` 本次均未命中。全程未观察到任何 `[OLE:...]` 标签泄漏给学生。

---

## 四、核心结论

### 4.1 已确认：检测与清洗机制工作正常

`detect_ole()` 能正确识别标签并写入数据库，`strip_ole_tags()` 能正确清洗、不泄漏给学生——这是本次验证最核心的目标，已经达成。

### 4.2 新发现：`SELF_CORRECTION` 与 `EXPLICIT_REASONING` 存在语义重叠，模型倾向于识别更表层的特征

19:27 那次交互是专门设计用来触发 `SELF_CORRECTION` 的场景：系统此前用一个反例（√(1+x³) vs 1+x³）引导，没有直接指出学生"选最复杂部分当 u"这个判断标准是错的；学生在下一轮里用"等等，我之前说的……不对……而是……"这种自我否定转折的方式给出了修正后的正确标准。这轮同时具备两种特征：

- **完整因果推导**（符合 `EXPLICIT_REASONING` 的定义）
- **对先前错误说法的主动修正**（符合 `SELF_CORRECTION` 的定义）

模型这次选择了 `EXPLICIT_REASONING`，说明当前 SCL prompt 里对这两个标签的描述，让模型更容易识别"表层是否有完整因果推导句式"，而不容易识别"这段推导在对话语境里是否扮演了自我纠正的角色"。

结合 19:11-19:12 那次 `REPRESENTATION_ALIGNMENT` 也未被触发（学生已经显式写出 u=1+x² 的映射，但模型未打标），两次"漏检"合在一起看，指向同一个模式：**模型对"动作的表层模式"比较敏感，对"动作在对话语境里的功能角色"区分度不够**。

### 4.3 建议的改进方向（未实施，留待下一轮迭代）

在 `SCL_SYSTEM_PROMPT` 的 OLE 检测指令里，为 `SELF_CORRECTION` 补充更明确的判别线索，例如："如果学生的回复中包含'我之前说的不对/我漏掉了/等等，应该是……'这类对自己先前说法的否定或修正表述，优先判定为 SELF_CORRECTION，即使该修正本身也包含完整的因果推导。"

这条改进建议不属于本次验证范围内的紧急修复——`EXPLICIT_REASONING` 和 `SELF_CORRECTION` 都是"学生表现良好"的信号，误标不会对学生造成任何负面体验，只是会让未来基于 OLE 数据做统计分析（比如 Policy Effect）时，这两个标签的边界不够干净。建议在积累更多真实学生数据、观察这个重叠问题的普遍程度后，再决定是否值得专门修一次 prompt。

### 4.4 待补充：`REPRESENTATION_ALIGNMENT` 样本量不足

本次仅设计过一次场景（19:11-19:12），且未命中，样本量不足以下任何结论（无法判断是这个标签的判定条件在 prompt 里描述得不够清晰，还是这次具体的回答确实不够"主动"、够不上触发门槛）。留待后续真实使用中自然积累更多样本。

---

## 五、下一步

- 不再继续人工设计场景加测——继续加测的边际价值有限，且人工设计的样本天然是"我知道自己想触发什么"，不是无偏样本。
- 等待真实学生使用积累自然数据后，重新评估 4.2 节提到的标签重叠问题是否普遍，以及 `REPRESENTATION_ALIGNMENT` 的实际触发率。
- 4.3 节的 prompt 改进建议记录在案，不紧急，可在下一轮 SCL prompt 迭代时一并处理。
