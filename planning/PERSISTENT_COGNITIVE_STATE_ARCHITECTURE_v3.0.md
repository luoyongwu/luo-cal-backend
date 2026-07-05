# Luo-cal v3.0 — Persistent Cognitive State Architecture (PCSA)
## Implementation Architecture Plan

**制定日期：** 2026-07-03
**修订：** Rev 4（2026-07-05）— Phase 2 开工前的四项架构决策：接口先冻结、State Transition Policy 四大不变量认识论升级、Cognitive Inertia Damper 独立组件化、N≥5 降级为工程超参数。决策记录详见 `planning/DESIGN_NOTES.md`
**范围：** 白皮书路线图 v3.0
**命名说明：** "PCSA"直接沿用 Volume I 图6 Level 4 的名称——"Persistent Cognitive State"。DAN Memory 是这一层的持久化实现手段，不是被建模的对象；State 才是。本次更名不是新造术语，是把文档拉回宪法自身的词汇表
**性质：** Implementation Architecture Plan。治理体系保持 **Constitution → Specification → Implementation** 三层，不新增"Execution Layer"——本文档是 Implementation 层的架构蓝图，未来 Coding Standard / CI/CD / Testing 等文档都归在同一层下，不再叠加新层级
**前提：** 一切实现必须引用 Volume I/II/III 的既有条款，不得反向修改理论
**明确排除：**
- 视频项目不纳入本计划，待共识后另行排期
- SCL Provider Compliance Verification（新 Provider 接入时的 MADNESS 探针集、Leakage Score 对比基线）不纳入本计划，将在独立的 *Provider Qualification Plan* 中定义，不占用 v3.0 开发资源

**状态：** 已冻结（Frozen）——Phase 1 架构决策已确认，可直接进入实施

---

## ✅ 架构决策记录：evidence_history 不单独建表（已确认，2026-07-03）

审阅生产环境 `cognitive_signals` 表实际 DDL 后发现：该表已经带有 `cognitive_model_weights`（JSONB，三世界权重，默认全 0.0）和 `persistent_cognitive_state`（JSONB，三世界阶段，默认全 `"unobserved"`）两个字段——每一条 EWM 信号落盘时，理论上已经在同一行里为持久化状态预留了位置，只是从未被写入过。

**最终决策：方案 A（事件溯源范式）。**

- `cognitive_signals` 作为唯一的、不可篡改的证据序列（Event Log）。不新建 `evidence_history`，不做双写
- 每次状态演化时，Evidence Aggregation Engine 直接对 `cognitive_signals` 做 SQL 窗口函数聚合，取代维护一张派生的中间表
- Phase 1 只新建一张 `dan_state` 表——全局当前状态快照（Snapshot），对应事件溯源架构中 Event Log 之上的 Materialized View

**否决方案 B 的理由：**
- **数据主权唯一性。** 错误信号一旦落盘即是既成事实（Event Sourcing 的核心原则），不应在多张表里产生多份投影。方案 B 要求 `main.py` 每次捕获错误时同步双写两张表，双写失败即产生分布式不一致——方案 A 从架构上直接消除了这类故障模式，不需要额外的一致性补偿逻辑
- **工程阻抗最低。** 现有 `cognitive_signals` 字段类型（`id SERIAL`、`VARCHAR(50)` 等）与生产环境严丝合缝，Phase 1 只需一张新表即可通电，比方案 B 少一半的建表和迁移工作量

**架构含义：** `cognitive_signals`（Event Log，只追加不修改）→ Evidence Aggregation Engine（读时聚合）→ `dan_state`（Materialized View，当前状态）。这与"架构总览：四层解耦"的设计精神一致——证据本身不可变，可变的只有基于证据算出的状态。

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
Evidence Aggregation Engine（证据聚合引擎）   ← Phase 2 核心之一
      │   只算"纯净"概率，不掺教学策略
      │   当前实现：Bayesian
      │   未来可替换：Hidden Markov / Kalman / Transformer Memory / LLM Evaluator
      │   替换聚合算法 = 不改 State 结构、不改 Dashboard、不改理论
      ▼
Cognitive Inertia Damper（认知惯性阻尼器）    ← Phase 2 核心之二，独立组件
      │   只管教学策略：够不够格升级？该不该衰减？
      │   接收"纯净"概率，输出"过滤后"概率
      │   N≥5、衰减速率等超参数只存在于这一层
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

**职责边界（新增，重要）：** `EvidenceAggregator` 只负责算出"纯净"的概率/权重——不掺杂任何教学策略判断（要不要真的升级、要不要因为太久没练习而衰减）。这些策略性判断属于下面新引入的 `CognitiveInertiaDamper`，两者严格分层：数学计算与教学业务规则彻底剥离，换掉其中一个不影响另一个。

**理论边界（写死，不可配置）：** Aggregation Engine 不得直接修改理论映射（Evidence → Mechanism → World），只能计算已有理论框架下的状态更新。这条约束现在看似多余，但至关重要——未来如果换成 LLM Evaluator 这类端到端模型，它有能力直接从 Evidence 跳到 World、绕过 Mechanism 层输出一个"看起来合理"的结果。一旦发生，Volume I 的命题1（多对多推断映射）就形同虚设，整套 Constitution 的可审计性随之失效。任何聚合算法的实现都必须显式输出中间的 Mechanism 归因，不能只给最终 World 权重。

---

## Phase 1 — Persistence Foundation

**产出：** 系统具备读写跨会话状态的能力（尚不含状态演化逻辑）

- **生产 Schema 对齐（已完成，2026-07-03）**
  实际 `cognitive_signals` DDL 已取得：`id SERIAL`、`student_id VARCHAR(50)`、`session_id VARCHAR(100)`、`concept_id VARCHAR(20)`、`error_signal VARCHAR(50)`、`cognitive_mechanism VARCHAR(50)`、`error_level VARCHAR(20)`、`confidence FLOAT`、`cognitive_model_weights JSONB`、`persistent_cognitive_state JSONB`、`trigger_context JSONB`、`intercept_result JSONB`、`created_at TIMESTAMPTZ`。字段与 Ontology v3.0 术语（`cognitive_mechanism` 等）已对齐，**不需要额外做 v2.0→v3.0 的 signal schema migration**
- **Schema 设计（已确认：事件溯源范式，方案 A）**（约 0.5-1 天）
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

### Step 0 — 接口冻结（Interface Freeze，先于任何算法实现）

在写任何具体的数学公式之前，先把"插槽"的形状定死。这不是拖延，是防止未来 v4.0 跨学科扩展或算法迭代时，前端和数据库承受重构摩擦力。本阶段冻结两个接口：

- `EvidenceAggregator`（已在"架构总览"一节定义）——纯概率计算，不含教学策略
- `CognitiveInertiaDamper`（本节新定义，见下）——教学策略过滤，不含概率数学

两个接口一旦冻结，Phase 2 剩余的所有工作都是"往插槽里装东西"，不再触碰插槽形状本身。这是为什么本阶段要先出一份接口文档，再动手写贝叶斯公式。

### State Transition Policy（约 1 天，Research + 少量 Coding）

不是"Stage 迁移规则"，是一份独立的策略文档：Fragile→Emerging→Stable 何时升级、何时降级、多久失效。产出一份可被论文直接引用的 Policy 文档，代码只是该 Policy 的实现。

**契约化定义：**
- **Inputs：** Evidence History（来自 `cognitive_signals`）、Weight Vector（Aggregation Engine 输出）、Recency（距今时间）
- **Outputs：** Stage、Confidence

**四大不变量（Invariants，认识论级别，不可因工程便利妥协）：**

1. **可逆性（Reversibility）。** Stage 必须可逆——学生这次考得好可以升星，状态转差也必须能够降星。这保护的是学生的"自我修正主权"，系统不能演变成一次考试定终身的黑箱评级机器。
2. **可追溯性（Traceability）。** 任何状态更新都必须能一键回溯到触发它的具体证据——系统说某学生是 Fragile，必须能真实拉出那几条触发 `BOUNDS_TRAP` 的原始记录（"真实流水小票"），拒绝黑箱断言。
3. **不可绕过核心推断链路（No-Bypass）。** 计算必须严格沿 L1(现象)→L2(机制)→L3(世界模型)→L4(持久状态) 走，禁止任何实现"抄近路"直接用错题数量映射最终状态。这条不变量是理论边界约束（命题1的多对多映射）在 Policy 层面的重申——"架构总览"一节已经对 Aggregation Engine 提出过同样要求，这里再次对整条 Policy 提出，双重保险。
4. **推断性，非事实性（Posterior, not Reality）。** Dashboard 展示的星级是系统基于现有证据做出的"当前最合理推测"，不是给学生下的死结论。呼应红线，也是 Phase 4 审计清单里的自动检查项。

  **降级展示规则：** 当 Stage 因 recency decay 或负面证据降级时，Dashboard 必须显示降级原因和重新激活条件（例如"你已 3 周未练习，此评估可能已过期。完成一次相关练习后可更新"）。降级不能悄无声息地发生——这是不变量1（可逆性）在 UI 层面的兑现。

### Evidence Aggregation Engine（约 4-6 天，Research 为主）

当前实现：Bayesian（Ontology §4 v2.0 设计），满足上方 `EvidenceAggregator` 接口契约。

只做一件事：算出"纯净"的概率/权重，不掺杂"是否应该真的升级"这类教学判断——那是下面 `CognitiveInertiaDamper` 的职责。这次拆分之前，N≥5 收敛阈值曾经写在这一层的描述里，混淆了"数学计算"和"教学策略"，现已剥离，见下方 Damper 一节。

证据序列来源：直接对 `cognitive_signals` 做 SQL 窗口函数聚合（事件溯源范式，见 Phase 1 架构决策）。必须遵守理论边界约束：输出中间 Mechanism 归因，不得跳过直接给 World 权重。这是整个计划理论敏感度最高的一段，实现完成后单独发你核对措辞是否偏离 Volume I。

**交付物：** 除代码外，产出一份简短的算法说明文档（未来论文可直接引用的 Method 段），明确记录先验设定、似然函数形式——不是代码注释，是可发表的方法陈述。

### Cognitive Inertia Damper（新增独立组件，约 1-2 天）

**职责：** 接收 Aggregation Engine 算出的"纯净"概率，结合证据历史和当前状态，决定这个概率能不能真的转化成 Stage 变化。数学计算和教学业务策略在这里彻底剥离——贝叶斯引擎只管"客观算出概率有多高"，阻尼器只管"这个概率够不够格触发状态改变"。

```python
class CognitiveInertiaDamper:
    def dampen(self, raw_weight_vector: WeightVector,
               evidence_history: List[Evidence],
               current_state: dict) -> WeightVector:
        """
        输入：Aggregation Engine 输出的纯净权重、证据历史、当前持久状态
        输出：应用教学策略过滤后的权重向量——可能等于输入，
              也可能被按住不放行（例如概率虽高但连续正面信号不足 N 次）
        """
        raise NotImplementedError
```

**当前策略（Phase 2 初版）：**
- 升级门槛从严：需要连续多场会话（默认 N≥5）的密集正面信号积累才能升级，单次表现不足以触发
- 时间衰减（Recency Decay）：旧错误信号的权重随时间推移或正确回答累积做指数/对数衰减，不能让很久以前的一次失误永远压着当前状态

**N≥5 的治理定位（重要，本次会议明确降级）：** 这个连续信号数阈值正式定义为**可验证、可调的工程超参数（Hyperparameter）**，不是 Volume I 的理论承诺，不写入 Constitution 层。它只存在于本文档和未来的算法说明文档里；未来实验证明 N=7 更合适时，修改它只需要工程验证（A/B 测试、模拟数据），像调收音机音量一样，不需要走 Constitution 修订流程。这是三层治理体系（Constitution → Specification → Implementation）的直接体现：理论层承诺"存在阻尼机制"，具体阈值是 Implementation 层的实现细节。

### Evidence History Tracking

证据序列即 `cognitive_signals`（Event Log，见 Phase 1 架构决策，不单独建表），确保每次 State Update 都能回溯到具体信号——为 Phase 3 的 Evidence Trace 打基础。

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

