# Root Cause Ontology v2 — 三层认知诊断架构

**作者：罗永武 | 硅基智库**
**日期：2026-06-25**
**状态：设计稿，待实现**

---

## 一、核心论点

当前大多数教育AI系统停留在第一层：记录学生犯了什么错误。
Luo-cal 的目标是向上抽象到三层：

    Error（错误现象）      ← 目前 EWM v1 已实现
        ↓
    Root Cause（根因能力） ← Ontology v1 已实现
        ↓
    World Model（认知世界观） ← v2 待实现

---

## 二、三层架构对照表

| 层级 | 名称 | 例子 | 类比 |
|------|------|------|------|
| L1 | Error | BOUNDS_TRAP | 症状：咳嗽 |
| L2 | Root Cause | RepresentationShift | 诊断：肺炎 |
| L3 | World Model | RWM（表征世界模型）| 体质：免疫系统薄弱 |

---

## 三、完整信号映射

### RWM — Representation World Model（表征世界模型）
> 学生心理里的数学对象，没有随着变量变换而同步更新。

| EWM信号 | Root Cause | World Model |
|---------|-----------|-------------|
| BOUNDS_TRAP | RepresentationShift | RWM |
| PRE_SUBSTITUTION | RepresentationShift | RWM |
| ABSOLUTE_VALUE | ExecutionIntegrity | RWM |
| CHAIN_FRACTURE | ExecutionIntegrity | RWM |

**大白话解释：**
不是不会积分，不是不会求导。
而是：当数学对象发生变化时，学生的心理模型没有同步更新。

---

### FWM — Flow World Model（流程世界模型）
> 学生知道每一步，但无法自主推进到下一步。

| EWM信号 | Root Cause | World Model |
|---------|-----------|-------------|
| EWM_B1C | FlowReasoning | FWM |
| IVT_MVT_CONFUSION | StructuralReasoning | FWM |

**大白话解释：**
脑子里的推理流程断了。
不是不会，而是无法自主连接上下文。

---

### AWM — Approximation World Model（近似世界模型）
> 学生缺乏对数学对象量级感和行为感的直觉。

| EWM信号 | Root Cause | World Model |
|---------|-----------|-------------|
| WASHER_TRAP | StructuralReasoning | AWM |
| （待扩展） | | |

---

## 四、Dashboard v0.2 设计原则

**首页：直接显示 World Model 星级**

    🟡 Representation World Model   ★★☆☆☆
    🟢 Flow World Model             ★★★★☆
    🟢 Approximation World Model    ★★★★★

**点击展开后显示证据层：**

    证据（Evidence）：
      • BOUNDS_TRAP ×3
      • PRE_SUBSTITUTION ×2
      • ABSOLUTE_VALUE ×1

    根因（Root Cause）：
      RepresentationShift — 变量追踪薄弱

    建议（Recommendation）：
      先练 Representation Bridge 题型

**设计原则：**
- 错误是证据（Evidence），不是结论
- World Model 才是最终诊断（Diagnosis）
- 学生看到的是能力画像，不是错误清单

---

## 五、与现有竞品的差异

| 产品 | 追踪层级 |
|------|----------|
| Khan Academy | L0（完成度）|
| Duolingo | L1（答对/答错）|
| Carnegie Learning MATHia | L1.5（概念掌握度）|
| **Luo-cal v2** | **L1+L2+L3（Error→Root Cause→World Model）** |

目前没有已知商业产品实现 L3 层的认知世界观可视化。

---

## 六、论文升级方向

原贡献：SCL + EWM检测（指令层→结构层）
升级贡献：SCL + EWM → Root Cause → World Model 三层认知诊断体系

建议新标题：
**从错误到世界模型：基于认知层工程的微积分学习诊断系统**

Figure 1 候选：Dashboard 首页 World Model 星级图

---

## 七、实现路线图

- [x] L1 EWM信号检测（v1已完成）
- [x] L2 Root Cause Ontology v1映射（v1已完成）
- [ ] L3 World Model聚合算法
- [ ] Dashboard v0.2 World Model首页
- [ ] 学生纵向追踪（World Model随时间变化）
- [ ] FWM预测（根据已有信号预判下一瓶颈）
