# State Transition Policy v1.0
## Luo-cal PCSA — Phase 2 规范文档

**作者：** 罗永武 | 硅基智库
**日期：** 2026-07-06
**状态：** Phase 2 Policy 文档，Implementation 层（非 Constitution）
**定位：** 本文档定义 `dan_state.stage` 在 Fragile / Emerging / Stable 之间迁移的规则契约与不变量。规则的具体数值参数（连续信号数阈值、衰减速率等）不在本文档中给出——那些是 `CognitiveInertiaDamper` 的工程实现细节（见 `DESIGN_NOTES.md` ADR-004，已从理论承诺降级为可调超参数）。本文档只规定"迁移必须满足什么样的形状"，不规定"具体数字是多少"。

---

## 1. 定位声明

三卷宪法回答"为什么会犯错"（Ontology）、"认知结构是什么"（CWM）、"系统如何执行约束"（SCL）。PCSA 回答"跨会话状态如何持久化"。本文档在 PCSA 之下，回答一个更窄的问题：**状态究竟在什么条件下从一个 Stage 迁移到另一个 Stage。**

这不是一份代码规格书，是一份可以被论文 Method 部分直接引用的策略陈述——描述的是政策边界（policy boundary），不是实现细节（implementation detail）。

## 2. 形式化契约

**State Machine：**

```
        upgrade
 Fragile ────────► Emerging ────────► Stable
    ▲                  │   ▲               │
    │     degrade       │   │    degrade     │
    └───────────────────┘   └────────────────┘
              （任何方向都可逆，见不变量1）
```

**Inputs：**
- Evidence History — 来自 `cognitive_signals` 的完整证据序列（Event Log）
- Weight Vector — `EvidenceAggregator` 输出的纯净概率（见 `pcsa_interfaces.py`）
- Recency — 距最近一次相关证据的时间

**Outputs：**
- Stage ∈ {fragile, emerging, stable}
- Confidence ∈ [0, 1]

**契约边界：** 本 Policy 本身不做计算。计算由 `EvidenceAggregator`（概率）和 `CognitiveInertiaDamper`（策略过滤）完成；本文档是这两者之上的规则契约——规定输出必须满足的不变量，不规定如何算出输出。

## 3. 四大不变量

1. **可逆性（Reversibility）。** Stage 必须可逆——学生这次表现好可以升级，状态转差也必须能够降级。这保护的是学生的"自我修正主权"，系统不能演变成一次考试定终身的黑箱评级机器。
2. **可追溯性（Traceability）。** 任何状态迁移都必须能一键回溯到触发它的具体证据——系统判定某学生处于 Fragile，必须能真实拉出触发该判定的原始信号记录，拒绝黑箱断言。
3. **不可绕过核心推断链路（No-Bypass）。** 状态迁移的计算必须严格沿 Evidence → Mechanism → World → State 的推断链走，禁止任何实现"抄近路"直接用错题数量映射最终 Stage。这条不变量是 Volume I 命题1（多对多推断映射）在本 Policy 层面的重申，也是对 `EvidenceAggregator` 理论边界约束的呼应。
4. **推断性，非事实性（Posterior, not Reality）。** Dashboard 展示的 Stage 是系统基于现有证据做出的"当前最合理推测"，不是给学生下的死结论。任何面向学生/家长的展示都必须保持这一认识论立场。

## 4. 迁移规则（定性，不含具体数值）

### 4.1 升级（Fragile → Emerging → Stable）

升级要求**持续的、多会话的正面证据积累**——单次表现不构成升级依据。这不是可选的宽松策略，而是不变量1（可逆性）的对称面：如果一次好表现就能升级，系统也会在一次差表现后立即降级，制造统计噪声主导的剧烈震荡（对应 PCSA Phase 4.5 的 Stage Oscillation 指标）。

"持续"具体量化为多少次会话、多高的置信度阈值，是 `CognitiveInertiaDamper` 的工程超参数，不在本 Policy 的管辖范围——这条边界本身就是治理体系分层的体现：本文档承诺"存在从严的升级门槛"，具体数字属于 Implementation 细节。

### 4.2 降级（Stable → Emerging → Fragile）

降级触发条件有两类：
- **负面证据积累**——学生在该 World 相关概念上重新出现错误信号
- **时间衰减（Recency Decay）**——状态在无相关证据的情况下，随时间推移置信度自然衰减

降级门槛应当**低于或等于**升级门槛。这是不变量1与教育伦理的直接推论：错误地把一个已经进步的学生耽误在过时的高星级评价里，比错误地让一个已掌握的学生"被降级一次"危害更小、更容易纠正。系统应当在"判定掌握"上更谨慎，不能让评价惯性压过学生的真实变化。

### 4.3 降级展示规则

当 Stage 因任何原因（负面证据或时间衰减）降级时，Dashboard 必须同时展示：
- 降级原因（新证据触发，还是纯粹时间衰减）
- 重新激活条件（完成什么样的练习可以重新评估）

降级不得静默发生。这是不变量1（可逆性）在用户界面层面的直接兑现——可逆不仅意味着数据库里的值可以改回来，也必须是学生和家长能看懂、能采取行动恢复的过程。

### 4.4 失效（Expiry）

"多久失效"不是一种独立的第三类状态转移，而是降级的一种特殊情形：极端的 Recency Decay（长期无证据）应导致状态向 Fragile 方向衰减，而不是让系统假装"沉默等于掌握"。沉默的学生不产生新证据，不代表他们的认知状态被冻结在最后一次观测的时刻。

## 5. 与理论层的关系

本 Policy 的四大不变量直接继承自 Volume I 的核心承诺（命题1的多对多映射、第八节的身份层否决）和 Volume II 的认识论声明（仪表盘展示后验非现实）。本 Policy 不创造新的理论主张，只是把已有的宪法承诺翻译成一份可执行、可审计的规则契约。

**修订依赖关系：** 若未来 Constitution 修订（Volume I/II 变更），本 Policy 必须相应修订以保持一致；反之，Policy 内部规则的细化调整（如降级触发条件的具体设计）不需要触碰 Constitution，只需工程验证。这一条本身也是三层治理体系（Constitution → Specification → Implementation）在本文档位置上的具体体现。

---

*本文档是 Luo-cal PCSA v3.0 Phase 2 的组成部分。具体数值超参数的实现见代码库中 `CognitiveInertiaDamper` 的具体子类。架构决策记录见 `planning/DESIGN_NOTES.md`。*
