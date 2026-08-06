# Diagnosis Scope 理论文档 v0.3

**文档性质声明**：本文档是理论讨论稿（Theory Paper），在 v0.2 基础上整合新一轮已收敛的补强结论。文档结构与 v0.2 保持一致，改动处以【v0.3 更新】标注，未改动部分不再赘述理由（详见 v0.2 原文）。本版本末尾新增"下一轮议题"，收录三个本轮暴露、尚未讨论的开放问题，明确不在本版本强行定案。

---

## 0. 三条原则

### 公理一：Diagnosis Scope 的核心定义

> Diagnosis Scope 定义的不是数据保存多久，而是每一种诊断对象（Diagnosis Object）的观察对象、生命周期、更新规则和消费权限。

### 公理二：一号原则

> Every diagnosis must have pedagogical consequence.（每一项诊断都必须具有教育意义）

任何状态如果不能改变下一步的教学决策，就不应该成为独立的 Diagnosis Object——它最多算 Analytics，不属于 Diagnosis 层。

### 核心原则（非公理，可被实证检验）：Teaching Effect

> Teaching Effect 不是 Outcome（是否答对），而是 Trajectory Change（认知轨迹改变）——教学是否改变了学生下一步思考的方式，而不是是否立即改变了最终答案。

> **【v0.3 补充说明】** 公理二要求诊断必须驱动教学决策，本条要求教学效果的衡量不看即时正确率。两者不矛盾，但工程落地上存在张力：V1 代理指标（第 7.4 节，同概念 3 轮内 EWM 不再复现）本质上仍是"缺陷信号是否消失"，不是"思维模式是否改变"的直接度量。这个张力已被诚实标注（第 7.4 节），未来 OLE 体系建成后，需要一个显式的"何时从代理指标切换为 OLE 判定"的标准——本版本不定义该标准，留待 Teaching Effect Theory 文档展开。

---

## 1. 零号问题：Concept Scope 为什么存在？

（与 v0.2 一致，不重复展开）Concept Scope 服务即时教学，Global Scope 服务长期认知画像，两者目的不同，因此生命周期和更新规则必须独立。

---

## 2. 对"Concept Scope 需要 stable"这一隐藏假设的否决

（与 v0.2 一致）Concept Scope 不追求 `stable`，`stable` 是 Global Scope 专属概念。路线 A 已定案，路线 B 已否决。

---

## 3. Concept Scope 状态机

```
collecting → candidate → teachable → closed
```

### 3.1 四个状态的定义（与 v0.2 一致）

- **collecting**：零信号阶段，Teaching Policy 走纯兜底策略。
- **candidate**：探测阶段，K=1，W_top1 ≥ 0.35，Teaching Policy 追加轻微偏置。
- **teachable**：确认阶段，定义见第 4 节。
- **closed**：概念完成或长期不活跃，生命周期终止，终态归并入 Global Scope。

### 3.2 状态迁移规则

- `collecting → candidate`：K=1，W_top1 ≥ 0.35。
- `candidate → collecting`：下一轮不是同一 mechanism，无阻尼立即回退。
- `candidate → teachable`：下一轮同一 mechanism 继续 top-1 且 W_top1 ≥ 0.40（K=2）。
- `teachable → collecting`：连续 2 轮不再是原 mechanism 才退出（滞回保护）。
- **【v0.3 新增】** `teachable(Composite) → collecting`：沿用通用退出规则——连续 2 轮 top-2 组合改变即退出，不额外加保守设计。理由：复合态的两个 mechanism 中任一开始波动，top-2 组合本身就已经改变，这已经是一个足够敏感的退出信号。

### 3.3 【v0.3 新增】教育学语言映射（不新增状态）

上一轮讨论提出为状态机补一层教育学叙事语言（Observation → Hypothesis → Confirmation → Action），建议不增加第五个独立状态，而是把这套语言映射到已有四态和状态迁移事件上：

| 教育学语言 | 对应 Diagnosis Scope 概念 |
|---|---|
| Observation（观察） | `collecting` 状态 |
| Hypothesis（假设） | `candidate` 状态 |
| Confirmation（确认） | `candidate → teachable` 这次状态迁移事件本身（K=2 那条证据） |
| Action（行动） | `teachable` 状态下 Teaching Policy 的实际输出 |

"确认"不是一个需要独立建模的状态，它就是候选假设被下一轮证据验证的那个事件。这样处理既满足了语义清晰度的诉求，也不增加状态机的验证复杂度。

### 3.4 V2 待验证方向（本版本不实现）

`teachable → candidate` 降级路径仍为开放方向，理由与 v0.2 一致：会引入环路，且缺乏真实数据支撑其必要性。

---

## 4. teachable 的定义

### 4.1 概念定义（教育学，永久不变）

> teachable 是一种教学决策状态（Instructional Readiness），不是诊断确定性状态（Diagnostic Certainty）。当前已有证据足以支持系统改变教学策略，且预计这种改变的收益高于继续使用默认策略时，该 Concept Context 进入 teachable。

### 4.2 【v0.3 新增】形式化：Teaching Gain

上一轮讨论提出，为让 4.1 节的"预期收益"不只是一句定性描述，引入一个可被不同方法估计的形式化变量：

> **Teaching Gain** = Expected Learning(采用针对性干预) − Expected Learning(维持默认教学)

当 Teaching Gain > 0 时，进入 teachable。这不是对 4.1 节定义的替换，是给同一个概念起了正式名字、并明确它是一个可以被不同方法估计的量——V1 用"连续 top-1 计数"估计它，V2 可以用 Posterior、Entropy、LLM 判断、甚至强化学习方法估计同一个量，理论定义本身不需要因为估计方法迭代而改变。

### 4.3 操作性定义 V1（工程实现，Teaching Gain 的 V1 估计方式）

（与 v0.2 一致）进入条件：K=2 连续同一 mechanism top-1，W_top1 ≥ 0.40；复合态例外：W_top1+W_top2 ≥ 0.70 且连续 2 轮 top-2 组合不变。退出条件：连续 2 轮不再是原 mechanism。

---

## 5. Global Scope

### 5.1 更新机制：事件驱动的 Profile Consolidation

（与 v0.2 一致）公式：`W_global(t) = λ · W_global(t-1) + (1-λ) · W_concept_final`，λ=0.85 占位硬编码。`W_concept_final` 为 Concept Context 关闭时完整的 4 维机制后验分布向量。

> **【v0.3 补充说明】** Profile Consolidation 不是统计学意义上的聚合运算，而是 **Incremental Belief Update**（增量信念更新）。这句澄清的目的是防止未来的实现者或读者把 Global Scope 误当成一个"数据库汇总表"来设计——Global Scope 本质上是一个持续演化的信念状态（Belief State），不是对历史记录做批量统计。这个区分会影响未来的 Schema 设计直觉：Global Scope 的字段应该被设计成"当前信念的快照"，而不是"历史事件的堆叠"。

### 5.2 Concept Summary 的完整结构

**【v0.3 更新】** 在 v0.2 已有字段基础上新增两项：

| 字段 | 说明 |
|---|---|
| Concept ID | 该概念的标识 |
| Start Time / End Time | 生命周期起止时间 |
| Mechanism Distribution | 即 W_concept_final，4 维后验分布向量 |
| Teaching Strategy Used | 该概念生命周期内实际注入过的 Teaching Policy 版本/内容 |
| Outcome | Learning Outcome（独立字段，见第 7 节） |
| Revision Count | 该概念内 stage/mechanism 判断发生变化的次数 |
| **Diagnosis Confidence**（新增） | 该概念关闭时诊断结论的置信程度，与 Teaching Confidence（教学策略本身是否被正确执行）是两个独立维度，不要混淆 |
| **Evidence Coverage**（新增） | 该概念内实际产生的证据/题目数量（例如"只做了 2 题"还是"做了 20 题"），供未来 Dashboard 呈现诊断结论的可信程度 |
| Notes | 预留自由字段 |

### 5.3 Subject Profile（与 v0.2 一致）

架构图体现 `Student → Subject Profile → Concept Context` 三层，当前只预留 `subject_id` 字段，不新增实现。

---

## 6. 生命周期：Suspend / Resume / Closed

```
Created → Active ⇄ Suspended → Closed
```

**明确写死的规则**：只有 `Closed` 状态才能进入 Global；`Suspend` 不进入 Global，`Resume` 不重新创建 Context。

### 6.1 【v0.3 新增】关闭权限：谁有权 Close？

上一轮讨论明确指出，此前版本只定义了生命周期形态，没有回答"谁有权关闭"。本版本明确：只有以下两类事件可以触发 Closure，除此之外任何模块不得直接 Close：

1. **Pedagogical Completion**（教学完成）：学生真正掌握该概念（判定标准见第 13 节下一轮议题第一项，本版本暂不定义）。
2. **Administrative Expiration**（管理性失效）：TTL 超时。当前只有 `ttl_timeout` 一种具体实现，未来课程/学期抽象层建立后，会增加 `course_boundary`（课程边界，如学期结束）这一具体实现，两者都属于 Administrative Expiration 这个大类。

建议数据库层面用 `closure_reason ENUM('mastery', 'ttl_timeout', 'course_boundary')` 记录具体触发原因，其中 `mastery` 对应 Pedagogical Completion，另外两个对应 Administrative Expiration 的两种当前/未来实现。

### 6.2 TTL

- **挂起 TTL**：占位 1-2 天（建议具体值 48 小时），区分"同一学习周期内的短暂切换"与"真正离开"。
- **关闭 TTL**：占位 7 天（168 小时），超时后触发 Administrative Expiration。
- **【v0.3 新增】恢复即重置计时器**：如果学生在挂起 TTL 超时前重新进入同一概念，Context 从 `Suspended` 恢复为 `Active`，挂起 TTL 的计时器同时重置为 0——每次 `Active` 状态结束（学生离开概念）时重新开始计时，不是从学生首次离开时算起的固定截止时间。
- **【v0.3 新增】V1 关闭行为明确为"软关闭"**：TTL 触发的 Administrative Expiration 关闭是软关闭——数据归档、终态归入 Global，但如果学生后续真的回来了，允许从归档数据中恢复 Context（而不是当作全新 Context 重新创建、丢弃此前的窗口状态）。硬关闭（彻底阻止恢复）在 V1 阶段不实现，避免"学生放假一周回来、系统装作不认识"这种糟糕体验。
- **设计意图记录**：一旦 Luo-cal 引入课程/学期层面的抽象，TTL 判定逻辑应优先切换为 `course_boundary` 驱动，数字型 TTL 退化为兜底机制。

### 6.3 归档策略（与 v0.2 一致）

Concept 关闭后，原始 Context 数据永久归档（soft archive），不做物理删除。

---

## 7. Teaching Effect：闭环的最后一块拼图

### 7.1-7.3（与 v0.2 一致）

否决"下一题做对""locked_mechanism 改变""学生自评"这三个候选定义。核心原则见第 0 节。

### 7.4 V1 落地路径

（与 v0.2 一致）同概念内 3 轮 EWM 消退验证，`undetermined` 为合法判定值，数据结构挂载于 Concept Summary 的 Outcome 字段。

---

## 8. 与其他文档的关系

- **Teaching Effect Theory**（独立文档，本轮已更新至 v0.2，见配套文档）：三层效果模型改名为 Execution / Strategy / Transfer，新增 Retention 第四层（占位不实现），OLE 改名为 Observable Pedagogical Event（但 V1 范围不扩大到教师侧事件），Policy Effect 改为按 (locked_mechanism, policy_version) 二维分组统计。详见配套文档正文。

---

## 9. Teaching Focus：Diagnosis Label 与教学层解耦

（与 v0.2 一致）V1 恒等映射 + 代码结构预留间接层。升级触发条件：教学策略同质化信号 / 学生响应无差异信号（Chi-Square 独立性检验 p > 0.10 且样本量 N ≥ 30 时人工评估升级，不做自动化触发）。

> **【v0.3 补充说明】** 触发条件回答的是"什么信号出现时说明该考虑升级"，但缺少"谁来发起"这件事的流程保障——这两个信号不会自动被发现，需要有团队成员在数据积累到一定量后主动做一次 Teaching Policy 效果回顾。这是流程约定，不是技术标准：升级不会自动发生，需要人主动触发分析。

---

## 10. Session Scope（与 v0.2 一致）

已隐含存在于现有代码（`chat_messages` + `fetch_chat_history()`），不需要新建表，正式定义详见 v0.2 第 10 节。

---

## 11. Teaching Policy 的消费规则（与 v0.2 一致）

当前读 Global 是零阶近似过渡态，最终目标是消费 Concept Scope 的输出。

---

## 12. Schema 层的代价（与 v0.2 一致）

架构级迁移，受影响范围见 v0.2 第 12 节，不重复列出。

---

## 13. 待确定事项（v0.3 收尾时仍然开放，不阻塞 V1）

| 编号 | 问题 | 现状 |
|---|---|---|
| B2-详细 | Teaching Effect 完整体系 | 原则已定，配套文档已更新至 v0.2，OLE 初始标签清单已给出 |
| B4-触发 | Teaching Focus 映射升级的启动流程 | 触发条件+流程约定已定（第 9 节），不阻塞 V1 |
| TTL-课程绑定 | TTL 由教学计划驱动的具体机制 | 方向已记录，V1 明确为软关闭（第 6.2 节），等待课程/学期抽象层建立 |

---

## 14. 下一轮议题（本版本刻意不定案，留给下一轮专门讨论）

本轮讨论暴露了三个分量较重、尚未有任何一方给出回应的新问题。不建议在 v0.3 强行拍板，列出以供下一轮专题讨论：

### 14.1 什么叫 Concept Finished？（不是 TTL）

第 6.1 节的 Pedagogical Completion 需要一个判定标准，目前完全没有定义。一个值得注意的线索：现有 Streamlit 前端已经有一套 `mastery_scores` 机制——学生连续 3 次答对（`[STATUS: CORRECT]`）会解锁"知识点总结"（`mastery_ready`）。这是系统里现成的一套"概念完成"判定逻辑，但目前只服务于前端 UI 展示，从未与本文档讨论的 Concept Context 关闭语义正式对接。

**待讨论**：是否直接复用这套现成标准（连续 3 次正确），还是"教学意义上真正完成"需要一套更严格、独立设计的标准（比如需要结合 teachable 状态、Learning Outcome 一起判断）？

### 14.2 Teaching Effect 的评估边界：归因给 Policy 还是归因给学生？

学生可能是自己回家看书学会的，不是这次教学干预的功劳——如果不定义清楚这个归因边界，未来的统计会混乱（无法回答"到底是这次干预有效，还是学生自己开窍了"）。

**待讨论**：V1 阶段是否只承认"相关性、不承认因果性"这个更弱的声明（即当前 Learning Outcome/Policy Effect 的统计只是观察到的相关模式，不是严格的因果归因）？真正的因果归因是否需要留给未来的 A/B 测试能力建立之后才能做？

### 14.3 Diagnosis 与 Intervention 的因果链路是否需要拆分？

本文档目前默认的链路是 `Diagnosis → Teaching → Effect`。本轮讨论提出了一个更细的候选链路：

```
Diagnosis → Intervention Selection → Intervention → Observable Events → Teaching Effect → Diagnosis Revision
```

核心主张是：真正驱动闭环的不是 Diagnosis 本身，而是 Intervention（教学干预）——Diagnosis 回答"学生现在处于什么认知状态"，Intervention 回答"系统实际做了什么"，Teaching Effect 评估"这个干预是否改变了学生的认知轨迹"，三者职责完全分离。

**待讨论**：这是一次结构性改动，可能牵动本文档已经定型的状态机和消费规则设计，不建议在 v0.3 直接采纳或否决。建议单独开一轮讨论，先把"Intervention Selection"这个新节点的职责边界（它和现有 Teaching Policy 拼接逻辑是什么关系？是否是同一件事换了个名字，还是真的需要独立建模？）讨论清楚，再决定是否要在未来版本里正式引入。

---

**本版本状态**：v0.2 中的待确定事项（B2-详细、B4-触发、TTL-课程绑定）已在正文中给出具体落地方案，不再作为开放问题。本版本新暴露的三个问题（14.1-14.3）明确挂账，留给下一轮讨论，不影响本文档已确定部分支撑 ADR 撰写的成熟度。
