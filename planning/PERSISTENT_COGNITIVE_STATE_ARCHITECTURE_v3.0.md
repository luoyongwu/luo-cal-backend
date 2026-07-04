# Luo-cal v3.0 — Persistent Cognitive State Architecture (PCSA)
## Implementation Architecture Plan

**制定日期：** 2026-07-03
**修订：** Rev 3 — 正式更名（原"DAN Memory 持久化"）；采纳架构复审第三轮意见
**范围：** 白皮书路线图 v3.0
**命名说明：** "PCSA"直接沿用 Volume I 图6 Level 4 的名称——"Persistent Cognitive State"。DAN Memory 是这一层的持久化实现手段，不是被建模的对象；State 才是。本次更名不是新造术语，是把文档拉回宪法自身的词汇表
**性质：** Implementation Architecture Plan。治理体系保持 **Constitution → Specification → Implementation** 三层，不新增"Execution Layer"——本文档是 Implementation 层的架构蓝图，未来 Coding Standard / CI/CD / Testing 等文档都归在同一层下，不再叠加新层级
**前提：** 一切实现必须引用 Volume I/II/III 的既有条款，不得反向修改理论
**明确排除：**
- 视频项目不纳入本计划，待共识后另行排期
- SCL Provider Compliance Verification（新 Provider 接入时的 MADNESS 探针集、Leakage Score 对比基线）不纳入本计划，将在独立的 *Provider Qualification Plan* 中定义，不占用 v3.0 开发资源

**状态：** 待明天解决一个开放架构问题（见下方"⚠️ 明天第一决策点"）后，即可冻结为正式实施蓝图

---

## ⚠️ 明天第一决策点：evidence_history 是否还需要单独建表

审阅生产环境 `cognitive_signals` 表实际 DDL 后发现：该表已经带有 `cognitive_model_weights`（JSONB，三世界权重，默认全 0.0）和 `persistent_cognitive_state`（JSONB，三世界阶段，默认全 `"unobserved"`）两个字段。也就是说，**每一条 EWM 信号被记录时，理论上已经在同一行里为持久化状态预留了位置**——只是这两个字段从未被写入过，一直是默认值。

这改变了 Phase 1 的候选方案。两条路：

- **方案 A（推荐，默认采纳）：** 不新建 `evidence_history` 表。`cognitive_signals` 本身就是逐信号历史，`Evidence Aggregation Engine` 直接查询 `cognitive_signals`（按 `student_id` + `subject_id` 过滤、按 `created_at` 排序）作为证据序列输入，聚合结果写回一张新的 `dan_state` 表（当前状态，一学生一学科一世界一行）。Phase 1 只新建一张表，不是两张。
- **方案 B：** 仍按原计划新建 `evidence_history`，作为 `cognitive_signals` 的派生/整理视图，代价是数据双写、需要保证一致性。

本文档后续 Schema 部分先按**方案 A** 撰写；明天你确认后如果选 B，我再改回来。

---

## 里程碑定义（Milestone Definition）

**v3.0 的完成标准不是"拥有持久化数据库"，而是"系统首次具备跨会话认知状态（Persistent Cognitive State）的能力"。**

自此，Luo-cal 从单会话 AI Tutor 演进为具有纵向学习记忆的认知系统。后续的证据聚合算法迭代、纵向学习分析、跨学科扩展（v4.0），都建立在这一能力之上。v3.0 不是数据库升级，是架构里程碑。

---

## 红线（Constitution 硬约束）

来自 Volume I 第八节，身份层否决：学习者画像必须保持当前状态的、概率性的、可修正的，且展示时附带证据基础。任何让状态"粘滞不可逆"或让学生被贴上固定标签的实现，违宪，必须推倒重来。本计划 Phase 4 将此约束转为自动化检查项，不再依赖人工审计。

**工程落地：** `dan_state` 增加 `state_revision_count` 字段，记录该状态被修正的次数。这个字段本身不阻止违宪，但让 Phase 4 的自动化审计能直接检测"是否存在从未被修正过的状态"——如果某学生某 World 长期停留同一 Stage 且 `revision_count = 0`，即是潜在的"粘滞不可逆"信号，触发审计告警。

---

## 架构总览：四层解耦

在写任何代码之前，先把数据流的四层分开，这是本计划最重要的一处调整：

```
Evidence（EWM 信号，已有）
      │
      ▼
Evidence Aggregation（证据聚合引擎）   ← Phase 2 核心
      │   当前实现：Bayesian
      │   未来可替换：Hidden Markov / Kalman / Transformer Memory / LLM Evaluator
      │   替换聚合算法 = 不改 State 结构、不改 Dashboard、不改理论
      ▼
State Update（持久状态更新）
      │
      ▼
Dashboard（Visualization + Evidence Trace）
```

Volume I 的理论主线（Evidence → Mechanism → World → State）保持不变；Evidence Aggregation Engine 是这条理论主线在 Phase 2 的**唯一实现层**，把算法选择和状态结构、展示逻辑彻底解耦。这是为什么现在这样设计，而不是直接写贝叶斯更新函数的原因。

**接口契约（不绑定任何具体算法，写入本计划作为未来替换算法的验收标准）：**

```python
class EvidenceAggregator:
    def aggregate(self, evidence_history: List[Evidence]) -> WeightVector:
        """
        输入：学生的完整证据历史（按时间排序）
        输出：三个 World 的权重向量，每个权重在 [0,1] 之间
        约束：输出必须附带 confidence 值，用于 Dashboard 展示和宪法审计
        """
        raise NotImplementedError
```

当前实现（Phase 2）满足此接口即可；未来替换为隐马尔可夫、Kalman、Transformer Memory 或 LLM Evaluator，只需实现同一接口，State/Dashboard/理论层都不用动。

**理论边界（写死，不可配置）：** Aggregation Engine 不得直接修改理论映射（Evidence → Mechanism → World），只能计算已有理论框架下的状态更新。这条约束现在看似多余，但至关重要——未来如果换成 LLM Evaluator 这类端到端模型，它有能力直接从 Evidence 跳到 World、绕过 Mechanism 层输出一个"看起来合理"的结果。一旦发生，Volume I 的命题1（多对多推断映射）就形同虚设，整套 Constitution 的可审计性随之失效。任何聚合算法的实现都必须显式输出中间的 Mechanism 归因，不能只给最终 World 权重。

---

## Phase 1 — Persistence Foundation

**产出：** 系统具备读写跨会话状态的能力（尚不含状态演化逻辑）

- **生产 Schema 对齐（已完成，2026-07-03）**
  实际 `cognitive_signals` DDL 已取得：`id SERIAL`、`student_id VARCHAR(50)`、`session_id VARCHAR(100)`、`concept_id VARCHAR(20)`、`error_signal VARCHAR(50)`、`cognitive_mechanism VARCHAR(50)`、`error_level VARCHAR(20)`、`confidence FLOAT`、`cognitive_model_weights JSONB`、`persistent_cognitive_state JSONB`、`trigger_context JSONB`、`intercept_result JSONB`、`created_at TIMESTAMPTZ`。字段与 Ontology v3.0 术语（`cognitive_mechanism` 等）已对齐，**不需要额外做 v2.0→v3.0 的 signal schema migration**
- **Schema 设计（按方案 A，见上方决策点）**（约 0.5-1 天，取决于明天是否改选方案 B）
  只新建 `dan_state` 表——学生当前持久状态，按 `(student_id, subject_id, cognitive_world)` 一行：
  ```sql
  CREATE TABLE IF NOT EXISTS dan_state (
      student_id VARCHAR(50) NOT NULL,
      subject_id VARCHAR(20) NOT NULL DEFAULT 'ap_calculus',   -- 原 domain，v4.0 跨学科分域
      cognitive_world VARCHAR(10) NOT NULL,                     -- 原 world；RWM / FWM / AWM
      stage VARCHAR(10) NOT NULL DEFAULT 'fragile',             -- fragile / emerging / stable
      evidence_count INT NOT NULL DEFAULT 0,
      weight_vector JSONB DEFAULT '{}'::jsonb,                  -- Evidence Aggregation Engine 输出，不绑定具体算法字段
      aggregator_version VARCHAR(30),                           -- 见 Phase 4.5
      state_revision_count INT NOT NULL DEFAULT 0,              -- 见"红线"一节
      last_updated TIMESTAMPTZ,
      created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (student_id, subject_id, cognitive_world)
  );
  ```
  证据历史直接查询既有 `cognitive_signals`（按 `student_id` + `session_id` 前缀或新增 `subject_id` 字段过滤），不重复建表
- **Migration**（约 0.5 天）
  幂等 SQL；为现有学生按 `cognitive_signals` 历史回填 `dan_state` 基线（默认 Fragile，evidence_count 按已有信号数回填）；`getpass` 盲输连接串，脚本完整可直接 Colab 运行
- **Persistence Service**（约 1.5 天）
  FastAPI `DANMemoryService`：会话开始读取 `dan_state`，会话中复用既有 EWM 检测链路写入 `cognitive_signals`（不变），会话结束/每轮触发 Evidence Aggregation Engine 重新计算并写回 `dan_state`。此阶段只做读写，不做演化判断——演化逻辑属于 Phase 2

## Phase 2 — Evidence-to-State Inference

**产出：** 状态能够根据证据正确演化，且演化逻辑与算法实现解耦

> 命名说明：这一阶段真正发生的是 Evidence → Inference → State，不是"状态自己演化"。旧标题"State Evolution"容易被读成数据库更新；真正重要的是中间的推断过程，标题必须体现这一点。

- **State Transition Policy**（约 1 天，Research + 少量 Coding）
  不是"Stage 迁移规则"，是一份独立的策略文档：Fragile→Emerging→Stable 何时升级、何时降级、多久失效。产出一份可被论文直接引用的 Policy 文档，代码只是该 Policy 的实现

  **契约化定义（让它读起来像一个真正的软件 Policy，而不是一段散文）：**
  - **Inputs：** Evidence History（来自 `cognitive_signals`）、Weight Vector（Aggregation Engine 输出）、Recency（距今时间）
  - **Outputs：** Stage、Confidence
  - **Invariants：** Stage 必须可逆；Evidence 必须可追溯；Identity 不得固定（呼应红线）

  **认知惯性阻尼（Cognitive Inertia）：** 微积分学习中的认知状态本身就有波动——上午连对三题冲到 Stable，下午状态差跌回 Fragile，这种剧烈震荡会让学生和家长质疑系统权威性。因此：
  - 升级门槛从严：需要连续多场会话（N≥5）的密集正面信号积累才能升级，单次表现不足以触发
  - 引入时间衰减（Recency Decay）：旧错误信号的权重随时间推移或正确回答累积做指数/对数衰减，不能让很久以前的一次失误永远压着当前状态

  **降级展示规则：** 当 Stage 因 recency decay 或负面证据降级时，Dashboard 必须显示降级原因和重新激活条件（例如"你已 3 周未练习，此评估可能已过期。完成一次相关练习后可更新"）。降级不能悄无声息地发生——这是"可修正"承诺在 UI 层面的兑现

- **Evidence Aggregation Engine**（约 5-7 天，Research 为主）
  当前实现：Bayesian（Ontology §4 v2.0 设计，N≥5 触发收敛，收敛路径本身即诊断信息），满足上方 `EvidenceAggregator` 接口契约
  证据序列来源：直接查询 `cognitive_signals`（按方案 A，见 Phase 1）
  必须遵守理论边界约束（见上方"架构总览"）：输出中间 Mechanism 归因，不得跳过直接给 World 权重
  这是整个计划理论敏感度最高的一段，实现完成后单独发你核对措辞是否偏离 Volume I
  **交付物：** 除代码外，产出一份简短的算法说明文档（未来论文可直接引用的 Method 段），明确记录先验设定、似然函数形式、N≥5 收敛阈值的依据——不是代码注释，是可发表的方法陈述
- **Evidence History Tracking**
  证据序列复用 `cognitive_signals`（不再单独建表，见 Phase 1 决策点），确保每次 State Update 都能回溯到具体信号——为 Phase 3 的 Evidence Trace 打基础

## Phase 3 — Visualization & Evidence Trace

**产出：** 学生和你都能看懂"为什么"，不只是"是什么"

拆成两个独立任务，第二个更重要：

- **Visualization**（约 0.5 天）
  Streamlit 前端：从单会话星级升级为跨会话轨迹图（stage 随时间变化）
- **Evidence Trace**（约 1 天，原 "Evidence Explanation"——改名理由见下）
  点开星级必须展开完整推断链，不是简单的"证据数量"：
  ```
  ⭐⭐☆☆☆
      │ Why?
      ▼
  BOUNDS_TRAP ×3 → RepresentationShift → RWM → Stage: Emerging

  其他可能：SemanticIntegrity（可能性较低，基于你之前 4 次绝对值遗漏的上下文）
  此诊断基于概率推断，非确定性判断。
  ```
  这是 Volume II "仪表盘展示后验，非认知现实"这条认识论声明在 v3.0 的具体落地——没有这一步，纵向数据只是数字，理论没有体现

  "其他可能"这一行呼应 Volume I 命题1（多对多映射，诊断本质不确定）：同一 EWM 信号可能来自不同机制。它有三个作用：向学生传达"诊断是推断，不是标签"；为 Reflection Rate 的开放文本框提供自然锚点（"你觉得这个判断准吗？"）；直接呼应宪法红线——展示概率性

  **命名说明：** "Explainability"在 AI 领域已经泛化到几乎可以指任何解释性功能。改用 **Evidence Trace**，与 `Evidence History`（数据层）、`Evidence Chain`（理论层，Volume II §5.4）三个术语在论文和代码中保持统一，读者一眼看出三者说的是同一条链路的三个切面

## Phase 4 — Verification

**产出：** 系统在对抗条件下仍然可信，且可信度可自动验证

- **Persistence Validation**（约 1.5 天，原 "MADNESS" 已不适用）
  持久化引入的攻击面和单会话 Prompt 攻击不同，新增四类测试：
  - Memory Injection — 学生伪造历史
  - Replay Attack — 重复旧消息
  - History Corruption — 数据库异常
  - State Rollback — 状态逆转
  这属于 Persistence Test，不再是传统 MADNESS 范畴，论文中应分开陈述
- **End-to-End Test**（约 1 天）
  模拟学生跨 3+ 会话、带特定 EWM 信号序列，验证 stage 演变、聚合引擎输出、Dashboard 展示全链路
- **Constitution Audit Checklist**（自动化，不再人工检查）
  部署前自动跑一遍：
  - [ ] 不存在永久标签
  - [ ] 不存在不可逆 Stage（结合 Phase 1 的 `state_revision_count`：长期 0 revision 触发告警）
  - [ ] 展示 Probability
  - [ ] 显示 Evidence
  - [ ] 保留 Revision 能力
  - [ ] 所有 Dashboard 推断均显示 "Posterior, not Reality"（Volume II 最独特的认识论声明——不能只写在论文里，Dashboard 渲染层必须自动检查这行文案是否存在，缺失即视为审计失败）

  **实现方式：** Audit Checklist 作为独立脚本实现，不嵌入任何 Phase 的代码路径，本身进入版本控制。这不是普通单元测试（检查代码有没有报错），而是**合规性熔断器（Compliance Circuit Breaker）**——普通测试检查"对不对"，这个脚本检查"违不违宪"。在 Railway 部署脚本中加一行硬断言：如果代码中出现类似 `is_low_learner = true` 这样的永久性身份赋值，部署流程 100% 报错并就地熔断，禁止上线。每次 Release 前手动或 CI 自动运行，检查失败 → 禁止部署
- **Deployment**（约 0.5 天）
  Railway 生产后端；生产 Supabase migration 验证

## Phase 4.5 — Telemetry

**产出：** 系统运行数据本身成为未来论文的数据来源

上线前容易被忽略、但决定 v3.5/v4.0 有没有真实数据可用的一层：

- Average Evidence（人均证据量）
- Average Stage（平均阶段分布）
- Average Update Delay（状态更新延迟）
- Average Confidence（聚合引擎置信度）
- Rollback Count（Phase 4 对抗测试触发次数，生产环境持续监控）
- Stage Oscillation（阶段震荡频率）——**诊断性指标，不作为自动告警触发器**：高震荡不一定是系统错误，可能是 Policy 阈值需要调整，也可能是该学生认知状态确实在快速变化
- **Evidence Diversity**（证据多样性）——该学生的证据是否集中在单一 World，还是覆盖 RWM/FWM/AWM 三者。为未来论文预留一个研究问题：证据多样性是否影响学习效果
- **Time-to-Stable**（平均达到 Stable 所需会话数）——论文级别的指标，天然适合画成一张漂亮的分布图

这一层现在搭好，v3.5 扩展消融和纵向学习分析可以直接复用，不用回头补数据管道。

**算法版本追踪：** `dan_state.aggregator_version`（Phase 1 已加入该字段，如 `"bayesian_v1"`）记录每次 State Update 使用的聚合算法版本。Phase 2 未来切换聚合算法时，这个字段让你能区分"状态变化是因为学生真的变了，还是因为算法变了"——没有它，算法迭代和学生进步在数据里无法区分。

---

## Future Extension

> Future algorithms may replace the Evidence Aggregation Engine without modifying:
> - Constitution
> - Specification
> - State Schema
> - Dashboard Interface

这正是"架构总览：四层解耦"要在 Phase 2 编码之前先定义接口契约的原因——这一节存在的全部意义，就是让上面这四行始终成立。

---

## 弹性说明

- Phase 2 的 State Transition Policy 阈值、Evidence Aggregation Engine 的具体公式，属于工程决策而非理论决策；Phase 2 开始前先给出候选阈值方案和模拟数据，供讨论后拍板
- 按 Phase 而非按天排期：任何一个 Phase 延期，不需要重写整份文档，只需调整该 Phase 内部的模块估时
- ~~Phase 1 的 schema 是否现在就为 v4.0 跨学科扩展预留字段~~ **已决定：现在加。** `subject_id` 字段已写入 Phase 1 的 `dan_state` schema，默认值 `'ap_calculus'`，为 v4.0 线性代数/物理等学科预留分域存储。现在加成本极低，Phase 3 后补则要返工
- 视频项目、SCL Provider Compliance Verification 单独排期，不占用本计划

