# Luo-cal v3.0 — DAN Memory 持久化
## Architecture Execution Plan

**制定日期：** 2026-07-03
**范围：** 白皮书路线图 v3.0（Persistent DAN Memory）
**性质：** 本文档不是一次性任务清单，是 v3.x 系列持续演进的工程蓝图，与三卷宪法形成第四层——Execution Layer
**前提：** 一切实现必须引用 Volume I/II/III 的既有条款，不得反向修改理论
**明确排除：** 视频项目不纳入本计划，待共识后另行排期

---

## 里程碑定义（Milestone Definition）

**v3.0 的完成标准不是"拥有持久化数据库"，而是"系统首次具备跨会话认知状态（Persistent Cognitive State）的能力"。**

自此，Luo-cal 从单会话 AI Tutor 演进为具有纵向学习记忆的认知系统。后续的证据聚合算法迭代、纵向学习分析、跨学科扩展（v4.0），都建立在这一能力之上。v3.0 不是数据库升级，是架构里程碑。

---

## 红线（Constitution 硬约束）

来自 Volume I 第八节，身份层否决：学习者画像必须保持当前状态的、概率性的、可修正的，且展示时附带证据基础。任何让状态"粘滞不可逆"或让学生被贴上固定标签的实现，违宪，必须推倒重来。本计划 Phase 4 将此约束转为自动化检查项，不再依赖人工审计。

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
Dashboard（Visualization + Explainability）
```

Volume I 的理论主线（Evidence → Mechanism → World → State）保持不变；Evidence Aggregation Engine 是这条理论主线在 Phase 2 的**唯一实现层**，把算法选择和状态结构、展示逻辑彻底解耦。这是为什么现在这样设计，而不是直接写贝叶斯更新函数的原因。

---

## Phase 1 — Persistence Foundation

**产出：** 系统具备读写跨会话状态的能力（尚不含状态演化逻辑）

- **Schema 设计**（约 1 天）
  `dan_state` 表：`student_id`、`world`（RWM/FWM/AWM）、`stage`、`evidence_count`、`last_updated`、`weight_vector`（JSON，为 Phase 2 聚合引擎预留，不绑定具体算法字段）
  `evidence_history` 表：关联既有 `cognitive_signals`，保证 Volume II §5.4 式完整推断链可审计
- **Migration**（约 0.5 天）
  幂等 SQL；现有学生会话内快照回填为持久基线（默认 Fragile，evidence_count=0）；`getpass` 盲输连接串，脚本完整可直接 Colab 运行
- **Persistence Service**（约 1.5 天）
  FastAPI `DANMemoryService`：会话开始读取持久状态，会话中复用既有 EWM 检测链路，会话结束/每轮写回。此阶段只做读写，不做演化判断——演化逻辑属于 Phase 2

## Phase 2 — State Evolution

**产出：** 状态能够根据证据正确演化，且演化逻辑与算法实现解耦

- **State Transition Policy**（约 1 天，Research + 少量 Coding）
  不是"Stage 迁移规则"，是一份独立的策略文档：Fragile→Emerging→Stable 何时升级、何时降级、多久失效（recency decay）。产出一份可被论文直接引用的 Policy 文档，代码只是该 Policy 的实现
  关键约束：任何 stage 必须可逆——呼应红线
- **Evidence Aggregation Engine**（约 5-7 天，Research 为主）
  当前实现：Bayesian（Ontology §4 v2.0 设计，N≥5 触发收敛，收敛路径本身即诊断信息）
  接口设计成可插拔：`aggregate(evidence_history) -> weight_vector`，未来替换算法只需实现同一接口
  这是整个计划理论敏感度最高的一段，实现完成后单独发你核对措辞是否偏离 Volume I
- **Evidence History Tracking**
  与 Phase 1 的 `evidence_history` 表打通，确保每次 State Update 都能回溯到具体证据——为 Phase 3 的 Explainability 打基础

## Phase 3 — Visualization & Explainability

**产出：** 学生和你都能看懂"为什么"，不只是"是什么"

拆成两个独立任务，第二个更重要：

- **Visualization**（约 0.5 天）
  Streamlit 前端：从单会话星级升级为跨会话轨迹图（stage 随时间变化）
- **Evidence Explanation**（约 1 天）
  点开星级必须展开完整推断链，不是简单的"证据数量"：
  ```
  ⭐⭐☆☆☆
      │ Why?
      ▼
  BOUNDS_TRAP ×3 → RepresentationShift → RWM → Stage: Emerging
  ```
  这是 Volume II "仪表盘展示后验，非认知现实"这条认识论声明在 v3.0 的具体落地——没有这一步，纵向数据只是数字，理论没有体现

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
  - [ ] 不存在不可逆 Stage
  - [ ] 展示 Probability
  - [ ] 显示 Evidence
  - [ ] 保留 Revision 能力
  每次 Release 前跑，长期沉淀为 CI 的一部分
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
- Stage Oscillation（阶段震荡频率——高震荡可能提示 Policy 阈值需要调整）

这一层现在搭好，v3.5 扩展消融和纵向学习分析可以直接复用，不用回头补数据管道。

---

## 弹性说明

- Phase 2 的 State Transition Policy 阈值、Evidence Aggregation Engine 的具体公式，属于工程决策而非理论决策，我会给候选方案，需要你拍板
- 按 Phase 而非按天排期：任何一个 Phase 延期，不需要重写整份文档，只需调整该 Phase 内部的模块估时
- Phase 1 的 schema 是否现在就为 v4.0 跨学科扩展预留字段，最好现在决定，避免 Phase 2/3 返工
- 视频项目单独排期，不占用本计划

