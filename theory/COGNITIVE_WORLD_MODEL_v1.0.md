# Cognitive World Model v1.0
## 认知世界模型 — 学生认知空间地图

**作者：罗永武 | 硅基智库**
**日期：2026-07-02**
**状态：Constitution v1.0 第二部，正式冻结**
**修改门槛：跨学科扩展或大量真实数据支持**
**地位：本文档与 Root Cause Ontology v3.0 是姊妹文档，共同构成 Luo-cal 理论宪章。
Ontology 是病理学（How failure is inferred），本文档是解剖学（What is organized）。
两者不可互相替代。**

---

## 一、定位声明

> **Root Cause explains failure. Cognitive World Model explains organization.**
> （认知机制解释失效；认知世界模型解释组织方式。）

层级关系：

```
Student Cognition
      │
      ▼
Cognitive World          ← 本文档定义
      │
      ▼
World Failure
      │
      ▼
Root Cause Evidence      ← Ontology 定义
      │
      ▼
EWM Signal
```

一个 World **不是**错误，也不是错误的集合。它是学生用来组织和处理某一类
数学对象或推理过程的**稳定认知结构**。Root Cause（认知机制）是这个结构运作
失败时留下的证据（Evidence），而 World Model 是这个结构本身。

**World ≠ Error；Root Cause ≠ World；Evidence ≠ World。**

---

## 二、CWM 通用结构（Core / Instance 划分）

CWM 分为两层：**通用核心（CWM Core）**与**学科实例（Domain Instance）**。
这个划分是 CWM 可以跨学科扩展（Linear Algebra、Physics、Statistics）而不需要
重新发明理论的原因——以后新增学科只是新增 Instance 列，不改 Core。

| CWM Core（通用） | AP微积分实例 | 未来实例（预留） |
|------------------|-------------|-----------------|
| Representation World | 变量关系、坐标系、参数空间 | 线性代数：基变换；物理：参考系 |
| Flow World | 求解路径、定理选择、推理链 | 线性代数：消元步骤；物理：受力分析链 |
| Approximation World | 极限直觉、误差容忍、渐近行为 | 统计：置信区间直觉；物理：量级估算 |

---

## 三、三个 World 的正式定义（AP微积分实例）

统一采用四段式：**Definition / Healthy State / Failure Signature / Typical
AP Calculus Domains**。

### 3.1 RWM — Representation World Model（表征世界模型）

| | |
|---|---|
| **Definition** | 学生用于表征数学对象及其变换关系（换元、坐标转换、参数化）的心理结构 |
| **Healthy State** | 当数学对象发生变换时，心理表征能够同步跟随变化 |
| **Failure Signature** | 换元后变量已变，但心理表征仍停留在原变量系统中（对应 RepresentationShift 机制） |
| **Typical AP Calculus Domains** | u-substitution、参数方程、积分限变换、多变量坐标转换 |

### 3.2 FWM — Flow World Model（流程世界模型）

| | |
|---|---|
| **Definition** | 学生用于组织多步骤推理路径的心理结构 |
| **Healthy State** | 能够自主地从一步推进到下一步，无需外部提示重启推理链 |
| **Failure Signature** | 知道每一步该做什么，但无法自主连接步骤之间的逻辑（对应 FlowReasoning 机制） |
| **Typical AP Calculus Domains** | 分部积分（IBP）多轮迭代、微分方程求解步骤、IVT/MVT 应用推理链 |

### 3.3 AWM — Approximation World Model（近似世界模型）

| | |
|---|---|
| **Definition** | 学生对数学对象"量级感"和"行为趋势"的直觉结构 |
| **Healthy State** | 精确计算之前，对结果的合理范围和渐近行为有正确预期 |
| **Failure Signature** | 计算正确但对结果合理性没有直觉判断力（对应 StructuralReasoning 机制的子类） |
| **Typical AP Calculus Domains** | 极限直觉、旋转体体积估算、级数收敛行为、误差估计 |

---

## 四、World 之间的关系

### 4.1 独立性

三个 World 理论上独立，但实践中一次错误可能同时暴露多个 World 的脆弱性
（见 Ontology 第四节权重向量机制）。

### 4.2 Hypothesized Dependencies（假设性依赖，非正式理论）

初步观察：RWM 的稳定性可能是 FWM 稳定性的前提条件——学生若不能正确表征
变换后的对象，即使流程正确也会在错误的对象上执行。

> Current observations suggest a possible dependency between RWM stability
> and FWM stability. **This relationship remains unvalidated and therefore
> is not part of the canonical ontology.**
>
> 目前观察提示 RWM 稳定性与 FWM 稳定性之间可能存在依赖关系。**该关系尚未
> 经过验证，因此不属于正式本体论的一部分。**

---

## 五、扩展协议（新增 World 的判定标准）

在提出第四个 World 之前，必须满足以下三个条件：

1. **不可归约性：** 该认知现象无法通过现有三个 World 的组合或权重解释
2. **跨情境稳定性：** 该现象在多个不同 EWM 信号中重复出现，具有跨题目一致性
3. **理论必要性：** 缺少该 World，会导致 Ontology 中某类机制无法归属到任何
   World（悬空机制）

满足以上三条后，需在本文档中新增章节并更新版本号至 v1.1，同时更新
Ontology 中对应的 Inference Mapping 表。

**当前状态：** StructuralReasoning 机制被分配到 FWM/AWM 之间（按信号区分，
见 Ontology 第四节），这是一个已知的过渡状态，不代表需要第四个 World——
它更可能反映 StructuralReasoning 本身需要在 Phase 2 进一步细分，而非
CWM 结构不足。

---

## 六、与 Dashboard 的接口

CWM 是 Dashboard 星级显示的直接理论依据：

```
🟡 Representation World Model   ★★☆☆☆
🟢 Flow World Model             ★★★★☆
🟢 Approximation World Model    ★★★★★
```

**星级来源：** 星级不是对 World Model 本身的直接测量（World Model 不可直接
观测），而是基于该 World 关联的所有 Root Cause 信号的**证据强度与新近度**
计算得出的间接推断（见 Ontology 第四节 v2.0 权重机制）。

> **Dashboard visualizes inferred cognitive state rather than directly
> observed mental representations.**
>
> Dashboard 展示的是**后验推断（Posterior）**，不是**认知现实本身
> （Reality）**。

**Evidence 展开：** 点击星级后展开的证据列表，来自 Ontology 第三节
Evidence Mapping，即触发该 World 相关 Root Cause 的具体 EWM 信号历史。

---

## 七、Appendix A：完整案例走查

**问题：**

```
∫₀¹ 2x(x²+1)³ dx
```

**学生行为：** 设 u = x²+1，但积分限仍写 x=0 到 x=1，未换算为 u=1 到 u=2。

**完整推断链：**

```
Observed Error
    BOUNDS_TRAP
        │
        ▼
Root Cause Evidence（Ontology 第三节）
    RepresentationShift
        │
        ▼
Inference Mapping（Ontology 第四节）
    { RWM: 高权重 }
        │
        ▼
World Update（本文档第六节）
    Representation World Model 证据 +1
    该 World 的星级评分随之调整
        │
        ▼
Dashboard 展示
    🟡 Representation World Model   ★★☆☆☆
    展开证据：BOUNDS_TRAP ×3（含本次）
```

**关键说明：** 这条链路的每一步都是**推断**，不是观察。系统直接观察到的只有
"学生写了 BOUNDS_TRAP 模式的答案"；其余全部是基于本文档与 Ontology 的
理论推断。

---

## 八、Non-goals（非目标）

> This document does not attempt to model the complete cognitive architecture
> of mathematical thinking. It defines only the World Models necessary to
> organize evidence collected through the EWM detection pipeline in the
> current Validation Domain (AP Calculus). **This document does not claim
> that every mathematical activity can be uniquely decomposed into the
> three World Models** — activities such as Optimization, Geometric
> Reasoning, or Formal Proof may require World structures not yet defined
> here, and are explicitly out of scope for v1.0.
>
> 本文档并不试图为数学思维建立完整的认知架构模型。它仅定义了在当前验证域
> （AP微积分）中，组织 EWM 检测管线所收集证据所必需的世界模型。**本文档
> 不主张所有数学活动都能被唯一分解为这三个世界模型**——诸如最优化、几何
> 推理、形式化证明等活动，可能需要本文档尚未定义的 World 结构，v1.0 版本
> 明确将其排除在范围之外。

---

## 九、Normative Statement（规范性陈述）

> This document specifies the structural taxonomy of Cognitive World Models
> recognized by the Luo-cal architecture. The three-World structure (RWM,
> FWM, AWM) may be extended to additional Worlds only through the protocol
> defined in Section 5. Domain instances (right column in Section 2) may be
> added freely; the CWM Core (left column) requires the same theoretical
> and empirical justification as changes to Root Cause Ontology.
> **The Core Worlds are conceptual commitments rather than implementation
> artifacts** — changes to code, Dashboard, or prompts do not, by
> themselves, justify changes to the World structure.
>
> 本文档明确了 Luo-cal 架构所认定的认知世界模型的结构性分类法。三世界结构
> （RWM、FWM、AWM）只能通过第五节定义的协议进行扩展。学科实例（第二节右列）
> 可自由增加；CWM 核心（左列）的修改需要与 Root Cause Ontology 变更同等
> 严格的理论与实证依据。**核心世界是概念性承诺，而非实现细节的产物**——
> 代码、Dashboard 或 Prompt 的改动本身不构成修改 World 结构的理由。

---

## 十、引用规则

1. 本文档与 Root Cause Ontology v3.0 共同构成 Luo-cal 理论宪章的第一、二部
2. 三个 World 的定义为唯一合法来源，Dashboard 标签、论文表述、代码变量名
   必须与此一致
3. 新增 World 前必须完成第五节判定协议
4. 修改历史记录于 THEORY_CHANGELOG.md
5. **开放问题（Open Question）**：Flow World 是 Process 而非 Object，与
   RWM/AWM 的 Object-oriented 定位不完全平行。此问题不影响 v1.0 冻结，
   记录于 THEORY_CHANGELOG.md，待 Phase 2 跨学科验证后重新评估命名。

---

*Luo-cal Cognitive Layer Engineering | 硅基智库 Silicon-Based Think Tank | Constitution v1.0*
