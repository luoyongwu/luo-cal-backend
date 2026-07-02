# Root Cause Ontology v3.0
## 认知机制本体论 — Constitution v1.0（理论宪章）

**作者：罗永武 | 硅基智库**
**日期：2026-07-02**
**状态：Constitution v1.0 — 理论宪章，正式冻结**
**修改门槛：新EWM信号验证 + MADNESS测试通过，且必须先更新本文档再改代码**
**地位：本文档是整个系统唯一合法的术语来源（类比：医学ICD / 心理学DSM）。**
**Dashboard、论文、代码、数据库均引用此处，不得重新发明定义。**

---

## Normative Statement（规范性陈述）

> This Constitution specifies the conceptual commitments of the Luo-cal
> cognitive architecture. Future revisions may extend or refine individual
> mechanisms, but changes to the core propositions require both theoretical
> justification and empirical validation.
>
> 本章程明确了 Luo-cal 认知架构的各项概念性承诺。未来的修订可能会扩展或
> 细化具体机制，但对核心命题的任何变更，均须同时具备理论依据与实证验证。

**价值：**
- 明确区分宪章层（Constitution）与实现层（Implementation）
- 强调核心命题不能因工程实现而随意修改
- 为未来 v1.1、v2.0 的演化建立正式治理规则，而非简单版本更新

---

## 〇、版本演进

- v1：EWM信号 → Root Cause 初始映射
- v2：三层架构（Error → Root Cause → World Model）确立
- **v3.0（本版 / Constitution v1.0）：Root Cause 更名 Cognitive Mechanism；**
  **Proposition 1 确立；Evidence/Inference 分离；权重向量预留；**
  **Figure 6 四层双向闭环；Non-goals 确立；理论主线冻结**

---

## 一、Proposition 1（核心命题）

> **Proposition 1.** Observable Errors, Cognitive Mechanisms, and Cognitive
> World Models constitute three distinct abstraction layers rather than a
> hierarchical taxonomy. **The mapping between layers is therefore
> inferential rather than definitional.**
>
> （命题1：可观测错误、认知机制与认知世界模型构成三个彼此独立的抽象层级，
> 而非一棵层级分类树。**因此，层与层之间的映射属于推断关系（Inference），
> 而非定义关系（Definition）。**）

**关键澄清：** RepresentationShift 不等于 Representation World。
机制只是世界模型的 Evidence（证据），不是其定义。
这一区分是后续 DAN 贝叶斯更新的理论依据。

**证明责任：** 三层之间存在多对多映射。

**多对多证据（同一 Error，不同 Mechanism）：**

学生在分离变量积分中漏写 `ln|y|` 的绝对值，可能来自两种完全不同的机制：

- 情形A：学生不知道对数真数必须为正 → **SemanticIntegrity**
- 情形B：学生已换元 u=y，后来忘记 u 代表原来的 y → **RepresentationShift**

Error 完全相同，机制完全不同。诊断必须区分。

**多对多证据（同一 Mechanism，不同 Error）：**

RepresentationShift 可导致：BOUNDS_TRAP、PRE_SUBSTITUTION、
（未来多变量场景下的）Jacobian Missing。

**推论：** 若映射为一对一，三层退化为分类树，本体论不成立。
多对多映射的存在，是 Luo-cal 区别于一切基于知识点分类的 ITS 的理论基础。
论文相应章节：*Why Cognitive Mechanisms are not Error Categories*。

---

## 二、核心定义

### 2.1 Cognitive Mechanism（认知机制）

> **定义：** 一种可被任务情境激活或抑制的内部处理过程，其运行结果可被观察为
> 错误模式，但机制本身不等于"能力水平"。
>
> Cognitive Mechanism = a context-sensitive internal process that can be
> activated or suppressed by task conditions; its outcome is observable as
> error patterns, but the mechanism itself is not an "ability level."

**为什么不叫"能力"：** 能力隐含稳定的、可测量的、有高低之分的个人属性。
机制是情境敏感的过程——学生会做这道题却没做对，不是缺乏能力，而是该情境下
机制未被激活。由此，干预策略是"激活机制"，而非"补能力差"。
这为 Adaptive Cognitive Intervention (SCL) 提供了理论基础。

### 2.2 Canonical Mechanisms（正式机制目录）

| 机制 | 定义 | 状态 |
|------|------|------|
| **RepresentationShift** | 数学对象发生变换（换元、坐标转换、参数化）后，心理表征未同步更新 | 冻结 |
| **SemanticIntegrity** (Working Name) | 符号操作过程中，数学对象背后的语义约束丢失 | 机制冻结，命名待跨学科验证 |
| **FlowReasoning** | 推理流程中断：知道每一步，但无法自主推进到下一步 | 冻结 |
| **StructuralReasoning** | 题目情境与数学模型之间的结构映射失败 | 冻结 |

**SemanticIntegrity 命名说明：** 候选名包括 Symbolic Integrity、
Representation Integrity。Final terminology will be determined after
cross-domain validation in Calculus, Linear Algebra and Physics.
**机制先冻结，名字后冻结。**

### 2.3 SemanticIntegrity 论证表

| Error | 表面现象 | Semantic Integrity 解读 |
|-------|---------|------------------------|
| ABSOLUTE_VALUE | 漏写绝对值符号 | 未保持"对数真数域为正"的语义约束 |
| CHAIN_FRACTURE | 链式法则中途断裂 | 未维持"导数在复合映射下坐标系一致"的语义约束 |
| CONSTANT_DROP — Reserved (Not Yet Validated) | 不定积分漏写 +C | 未维持"不定积分是函数族而非单个函数"的语义理解 |

**共同本质：** 学生并非不知道规则，而是在符号操作过程中丢失了数学对象背后的
语义约束。SemanticIntegrity 捕捉的是"符号与意义之间的保持关系"。

---

## 三、Evidence Mapping（EWM信号 → Cognitive Mechanism）

本节是**证据聚合（Evidence Aggregation）**，非固定分类。

| EWM信号 | 主要机制（缺省） | 备注 |
|---------|---------|------|
| BOUNDS_TRAP | RepresentationShift | |
| PRE_SUBSTITUTION | RepresentationShift | |
| ABSOLUTE_VALUE | SemanticIntegrity | 情形B下为 RepresentationShift（见 Proposition 1） |
| CHAIN_FRACTURE | SemanticIntegrity | 部分学生为 FlowReasoning（见第四节权重） |
| IVT_MVT_CONFUSION | StructuralReasoning | |
| WASHER_TRAP | StructuralReasoning | |
| EWM_B1C | FlowReasoning | 单轮隧道视野（IBP中途停止） |

**注意：** 本表为缺省映射。Proposition 1 决定了这不是唯一映射；
情境证据可推翻缺省值。

---

## 四、Inference Mapping（Cognitive Mechanism → CWM）

本节是**推断（Inference）**，非定义。

### v1.0（当前）：硬分类

| 机制 | Cognitive World Model |
|------|----------------------|
| RepresentationShift | RWM |
| SemanticIntegrity | RWM |
| FlowReasoning | FWM |
| StructuralReasoning | FWM / AWM（按信号区分） |

### v2.0（Phase 2 后）：权重向量

```
CHAIN_FRACTURE → SemanticIntegrity → { RWM: 0.7, FWM: 0.3 }
```

**权重来源规则（防止静态分配陷阱）：**

- 权重不由固定规则给定，而由**证据累积**动态调整
- 同一学生 DAN 信号积累至 N≥5 条时，按机制共现模式收敛权重
- **收敛路径本身即诊断信息**：快速收敛 → 认知模式稳定；
  持续波动 → 认知结构尚未固化
- v2.0 的 DAN 不仅是记忆，而是持续更新的贝叶斯先验

**论文表述：** "我们最初采用硬分类以建立理论基线，
后续通过证据累积机制过渡到概率权重。"

---

## 五、Figure 6：四层双向闭环（论文核心理论图）

> **Figure 6. Hierarchical Abstraction from Observable Errors to Persistent
> Cognitive State in the Luo-cal Cognitive Layer Engine**
>
> **Figure 6 describes a closed-loop cognitive architecture rather than a
> data pipeline.**（本图描述的是闭环认知架构，而非数据流程图。）

```
        Evidence Flow ──────►

Level 1: Observable Error            → EWM 检测（具体、可观察、单次会话内）
         BOUNDS_TRAP, ABSOLUTE_VALUE, CHAIN_FRACTURE ...
              │
              ▼
Level 2: Cognitive Mechanism         → Root Cause Ontology（机制性解释）
         RepresentationShift, SemanticIntegrity, FlowReasoning ...
              │
              ▼
Level 3: Cognitive World Model       → CWM（稳定认知结构）
         Representation World, Flow World, Approximation World
              │
              ▼
Level 4: Persistent Cognitive State  → DAN Memory（跨会话累积）
         Representation: Fragile → Emerging → Stable
         Flow:           Fragile → Emerging → Stable
         Approximation:  Fragile → Emerging → Stable
              │
              ▼
         Adaptive Cognitive Intervention (SCL)
              │
              ▼
         Future Observable Error ──► 回到 Level 1（闭环）

        ◄────── Knowledge Update
```

**双向箭头说明：** Evidence Flow（顺时针）承载观察证据向上抽象；
Knowledge Update（逆时针）承载认知状态向下驱动干预。

**闭环的意义：** 无反馈箭头，此图描述的是 Memory；
有反馈箭头，此图描述的是 Learning。这是两个层级的差别。

**与传统 ITS 的对比：**

- 传统 ITS：错误 → 知识点 → 推荐练习（终止于 "Unit 7.2 正确率 62%"）
- Luo-cal：错误 → 机制 → 认知结构 → 长期状态 → 策略适应 → 新错误（闭环）

---

## 六、理论主线（正式冻结）

```
Observable Error (EWM)
   ↓  Why did it happen?
Cognitive Mechanism
   ↓  What cognitive system is affected?
Cognitive World Model
   ↓  How does it accumulate?
Persistent Cognitive State (DAN)
   ↓  How does the system respond?
Adaptive Cognitive Intervention (SCL)
   ↓
Future Observable Error（回到起点，闭环）
```

**定位声明：** 微积分是本框架的第一个 **Validation Domain（验证域）**，
而非研究对象本身。核心贡献是一种可验证、可扩展、模型无关（model-agnostic）
的 **Cognitive Layer Engineering** 框架。

---

## 七、Non-goals（非目标）

> This ontology does not attempt to classify all mathematical errors.
> Instead, it provides a cognitive abstraction layer for organizing
> diagnostically useful evidence. Its purpose is not exhaustive taxonomy,
> but actionable inference.
>
> （本体论并不追求覆盖所有数学错误。它追求的是：把具有诊断价值的信息，
> 组织成可以驱动教学决策的认知推断。目的不是穷尽分类，而是可行动的推断。）

---

## 八、关于 Identity 层（明确否决，预留展望）

**否决理由：** 教育伦理。固定标签（如 "Low Representation Thinker"）
会产生 Label Effect（标签自我实现效应）。

**未来若引入，命名规则：**
- 禁用 Identity / 永久性描述
- 采用 **Current Cognitive Profile**，永远强调 Current
- 更新频率不低于每 5 次会话一次重评估
- Dashboard 必须显示："此描述基于最近 X 次学习的观察，可能随学习进程变化"

**论文展望句（唯一允许的提法）：**

> Longitudinal observations may eventually support the emergence of stable
> learner cognitive profiles built on top of the World Model layer. However,
> such profiles must be treated as **dynamic, probabilistic and revisable**,
> not as fixed learner identities.

---

## 九、引用规则

1. 本文档是唯一合法术语来源（类比：医学 ICD / 心理学 DSM）
2. 任何重大理论修改：**先改本文档，再改代码与论文**
3. 数据库字段、Dashboard 标签、论文术语必须与本文档一致
4. 命名冲突时，以本文档为准
5. 修改历史记录于 THEORY_CHANGELOG.md，重大决策记录于 ADR

---

*Luo-cal Cognitive Layer Engineering | 硅基智库 Silicon-Based Think Tank | Constitution v1.0*
