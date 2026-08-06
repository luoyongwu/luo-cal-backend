# Diagnosis Scope 理论文档 v0.2

**文档性质声明**：本文档是理论讨论稿（Theory Paper），不是 ADR，不直接驱动代码改动。经过多轮讨论收敛，本版本相较 v0.1 有实质性修订（特别是状态机从三态改为四态），并新增 Teaching Effect 原则。文档目标是为后续 ADR、Schema 设计、Teaching Policy 改造提供统一的理论锚点。

---

## 0. 两条公理

### 公理一：Diagnosis Scope 的核心定义

> Diagnosis Scope 定义的不是数据保存多久，而是每一种诊断对象（Diagnosis Object）的观察对象、生命周期、更新规则和消费权限。

"要不要 reset()"不是一个应该被直接回答的问题，而是下面这条推论的副产品：

> 当某个 Scope 的生命周期结束时，它停止接收新的证据；是否保留历史，由生命周期定义决定，而不是由一次函数调用决定。

### 公理二：一号原则

> Every diagnosis must have pedagogical consequence.（每一项诊断都必须具有教育意义）

任何状态如果不能改变下一步的教学决策，就不应该成为独立的 Diagnosis Object——它最多算 Analytics（可记录、可事后分析），不属于 Diagnosis 层。这条原则是未来所有"要不要新增一个 state/字段/label"提议的第一道过滤器。

---

## 1. 零号问题：Concept Scope 为什么存在？

Diagnosis 服务两种完全不同的目的，此前的讨论长期把它们混在一起：

| 目的 | 回答的问题 | 服务对象 | 对应 Scope |
|---|---|---|---|
| 即时教学 | 学生现在这一刻、这道题，为什么卡住？ | Teaching Policy，局部、当下 | Concept Scope |
| 长期认知画像 | 这个学生为什么总是在不同章节犯同一种错误？ | Dashboard / Analytics，长期、跨概念 | Global Scope |

**结论**：Concept Scope 和 Global Scope 是两个目的不同、因此必须有各自独立生命周期和更新规则的诊断对象，不是同一套机制的两种参数配置。

---

## 2. 对"Concept Scope 需要 stable"这一隐藏假设的否决

当前 PromotionPolicy 的 `stage == "stable"` 标准是为 Global 级别的确定性诊断设计的认证标准（certification standard）——宁可慢，也要排除噪声。这套标准被原样套用到 Concept Scope 上，而没有人问过：**Concept Scope 真的需要认证级别的确定性吗？**

课堂类比：学生连续两道题都忘了 Chain Rule，老师不会说"再等三题，等我窗口满了"。教学决策需要的是 **enough to teach**（够教了），不是 **enough to certify**（够认证了）。这是两个完全不同的标准。

**结论**：Concept Scope 不追求 `stable`，`stable` 是 Global Scope 专属概念。这一步同时消解了"window_size=5 永远凑不满、Concept Scope 永远卡在 fragile"这个此前反复出现的矛盾——不是被解决了，是它的前提本身不再成立。

**路线裁决**：路线 A（否决 stable 假设，本文档采纳）已定案；路线 B（缩小窗口逼近 stable）已否决，仅作为"为什么没选"的存档保留。

---

## 3. Concept Scope 状态机（本版本相较 v0.1 已修订）

```
collecting → candidate → teachable → closed
```

> **修订说明**：v0.1 曾给出三态状态机（不含 candidate），本版本经讨论后正式修订为四态。理由见 3.1。

### 3.1 四个状态的定义

- **collecting**：零信号阶段，证据不足以支撑任何判断。Teaching Policy 走纯兜底策略（`TEACHING_POLICY_INJECTIONS[None]`）。
- **candidate**：探测阶段。同一 mechanism 首次（K=1）成为该概念下证据的 top-1，且权重 W_top1 ≥ 0.35。Teaching Policy 在兜底策略基础上追加"轻微偏置"——不新建独立问题库，在现有对比性问题文案后拼接一句动态偏置指引（例如围绕检测到的 mechanism 方向适度倾斜提问，但不直接告诉学生系统已经注意到这个模式）。
- **teachable**：确认阶段。定义见第 4 节。
- **closed**：概念完成（学生连续正确完成巩固题）或长期不活跃（见第 6 节），生命周期终止，最终状态归并入 Global Scope（归并内容见第 5 节）。

### 3.2 状态迁移规则

- `collecting → candidate`：K=1，某 mechanism 首次 top-1 且 W_top1 ≥ 0.35。
- `candidate → collecting`：下一轮证据不是同一 mechanism，立即无阻尼回退（candidate 是轻量探针，不需要滞回保护，撤销要快）。
- `candidate → teachable`：下一轮同一 mechanism 继续 top-1 且 W_top1 ≥ 0.40（K=2，见第 4 节）。
- `teachable → collecting`：连续 2 轮不再是原 mechanism 才退出（滞回保护，与 ADR-012 PromotionPolicy 哲学一致，避免单次噪声导致策略抖动）。

> **V2 待验证方向（本版本不实现）**：`teachable → candidate` 的降级路径（"曾经确信、现在没那么确信了"与"曾经确信、现在完全没信号"应有区别）目前只是候选想法，会让状态机出现环路、复杂度显著上升，且没有真实数据支撑其必要性。本版本 `teachable` 退出直接回 `collecting`，此项留待未来数据验证后再考虑。

---

## 4. teachable 的两层定义

### 4.1 概念定义（教育学，永久不变）

> teachable 是一种教学决策状态（Instructional Readiness），不是诊断确定性状态（Diagnostic Certainty）。当前已有证据足以支持系统改变教学策略，且预计这种改变的收益高于继续使用默认策略时，该 Concept Context 进入 teachable。

这句话不随实现方式变化而改变，未来任何操作性定义的迭代都不能违背它。

### 4.2 操作性定义 V1（工程实现，可迭代）

**进入条件**（需同时满足）：
- 同一 mechanism 连续 K=2 轮成为该 Concept 内证据的 top-1；
- 该轮 top-1 权重占比 W_top1 ≥ 0.40（排除高熵打平场景下的伪 top-1，例如两个 mechanism 权重都在 0.35 附近微幅抖动导致的偶然 top-1）；
- 复合态例外：若 W_top1 + W_top2 ≥ 0.70 且连续 2 轮 top-2 组合不变，触发 `teachable(Composite)`。

**退出条件**：连续 2 轮不再是原 mechanism 才退出（见 3.2）。

**V2 可能的替代实现**（不影响概念定义）：Posterior 阈值、Entropy 下降幅度、LLM 直接判断等，均可在未来替换当前的"连续 top-1 计数"规则，只要满足 4.1 的概念定义即可。

---

## 5. Global Scope

### 5.1 更新机制：事件驱动的 Profile Consolidation

Global Scope 不重新跑一次全量 Evidence 的 PromotionPolicy，也不保存原始 Evidence 或 Conversation。Global Scope 只在 Concept Context Closure（关闭）时，吸收该概念输出的 **Concept Summary**。

聚合公式（原称"Moment Merge"，本版本正式更名为 **Profile Consolidation**，更准确反映其本质是状态更新而非统计学矩估计）：

```
W_global(t) = λ · W_global(t-1) + (1-λ) · W_concept_final
```

- λ = 0.85，作为占位默认值直接硬编码上线，不等待实证数据校准（该参数需要真实纵向数据才能优化，理论阶段精确调参属于过早优化）。
- `W_concept_final` 定义为 Concept Context 关闭时**完整的 4 维机制后验分布向量**（不是 one-hot）：

  ```
  W_concept_final = [P(RepresentationShift), P(SemanticIntegrity), P(FlowReasoning), P(StructuralReasoning)]，ΣP = 1.0
  ```

  理由：one-hot 会抹杀该概念内部真实的熵分布信息（丢失 top-2 共生信息）；即使概念从未进入 teachable（一直停留在 collecting/candidate），完整分布仍然可以把"该概念上学生的思维倾向"归入 Global，避免未锁定概念在 Global 里完全隐形。

### 5.2 Concept Summary 的完整结构

Concept Context 关闭时输出的 Concept Summary，固定包含以下字段：

| 字段 | 说明 |
|---|---|
| Concept ID | 该概念的标识 |
| Start Time / End Time | 生命周期起止时间 |
| Mechanism Distribution | 即 W_concept_final，4 维后验分布向量 |
| Teaching Strategy Used | 该概念生命周期内实际注入过的 Teaching Policy 版本/内容 |
| Outcome | 见第 7 节 Learning Outcome（独立字段，不混入 Mechanism Distribution 向量） |
| Revision Count | 该概念内 stage/mechanism 判断发生变化的次数 |
| Notes | 预留自由字段 |

Global Merge 消费的是这份 Concept Summary，不是原始 Evidence。

### 5.3 Subject Profile（概念层面预留，不新增实现）

理论架构应体现三层：

```
Student → Subject Profile → Concept Context
```

而不是 `Student → Concept Context` 直接跳过学科层。这一层目前**只在架构图和概念上体现**，不新增数据表、不新增处理逻辑——当前 Global Scope 数据表预留 `subject_id` 字段（固定为 `'ap_calculus'`）即可满足这一层的存在，为未来接入其他学科（物理、线性代数）保留数据基础和图示位置，不做任何提前实现。

---

## 6. 生命周期：Suspend / Resume / Closed

Concept Context 不应该 reset/destroy，应该挂起（Suspend）与恢复（Resume）：

```
Created → Active ⇄ Suspended → Closed
```

**明确写死的规则**：只有 `Closed` 状态才能进入 Global；`Suspend` 不进入 Global，`Resume` 不重新创建 Context（从挂起状态原样恢复，窗口和状态不衰减）。

**TTL 说明**：

- 理论上，TTL 应该由教学计划驱动（课程结束、学期结束、连续长期未访问等），而不是一个写死的天数，避免理论被具体实现数字绑架。
- 但当前 Luo-cal 的数据模型里还没有"课程/学期"这层抽象，理论上的教学计划驱动逻辑暂时不可执行。因此本版本**保留数字型占位值作为当前系统下的临时替代**：挂起 TTL（1-2 天，区分"同一学习周期内的短暂切换"与"真正离开"）、关闭 TTL（7 天，超时后正式关闭）。
- **设计意图记录**：一旦 Luo-cal 引入课程/学期层面的抽象，TTL 判定逻辑应优先切换为教学计划驱动，数字型 TTL 退化为兜底机制，不再是主要判定依据。

**归档策略**：Concept 关闭后，原始 Context 数据（窗口历史、逐轮 stage 轨迹）永久归档（soft archive），不做物理删除，为未来 Predictive Tutoring / Learning World Model 保留数据资产。关闭时终态归入 Global 是必做项，不是可选项。

---

## 7. Teaching Effect：闭环的最后一块拼图

### 7.1 为什么需要这一节

Diagnosis 回答"学生现在发生了什么"，Teaching Policy 回答"系统决定做什么"。但如果没有 Teaching Effect，闭环缺一块——**系统永远不知道自己的教学决策是否真的有用**，未来的 Learning World Model 也就没有训练目标。

### 7.2 三个必须否决的候选定义

在正式定义 Teaching Effect 之前，先否决三个"看起来合理但不够格"的标准：

1. **下一题做对了**——Correct ≠ Learned。可能是运气、记模板、或系统提示太多，这最多算 Performance，不是 Teaching Effect。
2. **locked_mechanism 改变了**——这只是 Diagnosis Change，不是 Learning，甚至可能只是系统当天诊断不稳定。
3. **学生自评"我懂了"**——Self-report 在教育研究中早已被证明不可靠。

### 7.3 核心原则

> Teaching Effect 不是 Outcome（是否答对），而是 Trajectory Change（认知轨迹改变）——教学是否改变了学生下一步思考的方式，而不是是否立即改变了最终答案。

即使题目最终仍然做错，但如果学生从"直接乱算"变成"先判断条件、再计算"，从教育学角度看，这次教学是有效的。这条原则和公理一、公理二同级，写入本文档作为第三条核心原则。

### 7.4 与已有工程方案的关系（V1 落地路径）

7.3 的原则不会立刻被完整实现（三层 Behavior/Reasoning/Transfer 的完整体系、Observable Learning Event 的分类标准，见第 8 节另立文档）。V1 阶段需要一个能跑起来的近似指标，作为过渡：

**V1 代理指标（proxy metric，明确标注为近似，不是 Teaching Effect 本身）**：
- 同概念内即时验证：`teachable` 触发针对性教学策略后，接下来 3 轮内同一 EWM 信号是否不再出现；
- 数据结构（附加于 Concept Summary 的 Outcome 字段）：
  ```json
  {
    "intervention_mechanism": "FlowReasoning",
    "outcome": "effective / ineffective / undetermined",
    "evidence_count_after_intervention": 3,
    "same_ewm_recurred": false
  }
  ```
- `undetermined` 是合法判定值，用于概念过早结束、没有足够后续证据判断的情况——不强行二元化。

**该代理指标的局限（必须在文档里明示，避免被误当作 Teaching Effect 的完整定义）**：EWM 信号消失可能是学生真的懂了，也可能只是后续题目没有机会触发同一检测条件——这是"没机会犯错"和"不会再犯错"的混淆，与 7.2 否决的"下一题做对"是同一类问题的变体，只是信号源更精细。V1 采用它是因为成本低、可以立刻跑起来，不是因为它等价于 Teaching Effect。

**跨概念延迟验证（V2，本版本不实现）**：下次同一 mechanism 在任意概念下再次成为主导时，记录中间跨越的概念数/时间差。延迟不可控、归因链条长（可能有学校老师授课、学生自己复习等其他变量介入），V1 阶段不值得为此买单。

---

## 8. 与其他文档的关系

- **Teaching Effect Theory**（另立文档，见配套大纲）：7.3 的原则需要完整展开——三层效果（Behavior Change / Reasoning Change / Transfer）、Observable Learning Event（OLE）的具体标签体系、OLE 检测的工程实现方式。本文档只确立原则，不展开细节，避免稀释 Diagnosis Scope 本身的主题。

---

## 9. Teaching Focus：Diagnosis Label 与教学层解耦

Concept Scope 对外不直接输出内部 mechanism 名，输出 **Teaching Focus**。V1 采用恒等映射（`RepresentationShift → RepresentationShift`），但代码结构上落地间接层：

```python
# teaching_policy.py
def get_teaching_focus(mechanism: str) -> str:
    # V1: 恒等映射（过渡态）
    # 未来可无缝扩展为: return FOCUS_MAPPING.get(mechanism, mechanism)
    return mechanism
```

复用 `concept_constraints.py::get_concept_constraint()` 已验证过的"数据与逻辑解耦"设计模式。

**升级为多对一映射的触发条件**（真实数据驱动，不做预判）：
1. **教学策略同质化信号**：两个不同 mechanism 对应的 Teaching Policy 指令在实践中高度重叠；
2. **学生响应无差异信号**：mechanism A 和 mechanism B 分别触发不同教学策略，但学生的 Learning Outcome（见第 7 节）没有显著差异。

这两个信号都必须靠真实数据发现，V1 阶段不设计任何预判性分组。

---

## 10. Session Scope（正式定义，无需新建表）

Session Scope 已隐含存在于现有代码（`chat_messages` + `fetch_chat_history()`，`CHAT_HISTORY_LIMIT=20`）：

- **观察对象**：当前连续对话窗口内的所有消息；
- **生命周期**：按 `session_id` 划分，创建于首次消息写入，销毁策略暂不定义；
- **更新规则**：每轮追加一对消息（student + assistant）；
- **消费方**：`socratic_chat()` 拼接进 Claude 的 messages 数组；
- **与 Concept/Global 的关系**：Session Scope 是对话基础设施，不参与认知诊断、不参与长期画像。EWM 信号提取后才进入 Evidence 流，Evidence 流才是 Concept/Global Scope 的输入。

不需要新建表，本节只是正式定义的文档化。

---

## 11. Teaching Policy 的消费规则（过渡态说明）

**如实说明现状**：当前 `main.py` 里 `socratic_chat()` 的 Teaching Policy 拼接逻辑读取的是 `dan_service.get_global_state()`（Global Scope），因为 Concept Scope 尚未实现。这不是 bug，是必然的过渡态。

**最终目标**：Teaching Policy 应消费 Concept Scope 的输出（`teachable`/`candidate` 状态下的 Teaching Focus 判断），不是直接读 Global。这个迁移需要等 Concept Context 实现出来之后才有意义，现在不需要、也不应该动代码。

---

## 12. Schema 层的代价（架构迁移，非加字段）

这是一次内存架构迁移，受影响范围至少包括：

- `BayesianAggregator`：需要能按 concept_id 过滤证据；
- `PromotionPolicy`：需要拆分为 ConceptPromotionPolicy（新四态状态机）与现有 Global 逻辑；
- `fetch_evidence_history()`：需要新增按 concept_id 过滤的能力；
- `DANMemoryService`：需要新增 Concept Context 表的读写逻辑；
- `dan_global_state`：更新逻辑从"每次 pipeline 更新"改为"Concept Context 关闭时归并"；
- Dashboard：如果未来需要展示"当前概念诊断"vs"长期认知画像"，需要同时读取两个来源。

这是架构级变化，不应在任何文档或讨论中被描述为"加一个 concept_id 字段"。本文档不给出具体 schema DDL，留待正式 ADR 阶段设计。

---

## 13. 待确定事项（v0.2 收尾时仍然开放）

| 编号 | 问题 | 现状 |
|---|---|---|
| B2-详细 | Teaching Effect 完整体系（三层效果、OLE 标签集合） | 原则已定（7.3），完整体系另立 Teaching Effect Theory 文档 |
| B4-触发 | Teaching Focus 映射升级的具体统计门槛（如相关系数阈值） | 方向已定（9），不阻塞 V1，V1 只需落地间接层 |
| TTL-课程绑定 | TTL 由教学计划驱动的具体机制 | 方向已记录（6），需等待课程/学期抽象层建立后才可执行 |

以上三项均不阻塞 V1 核心链路（Concept Scope 四态状态机 + Global Profile Consolidation + Session Scope 正式定义）的实现。

---

## 14. 与现有代码的映射

| 层级 | 现状 | 待建 |
|---|---|---|
| Session Scope | 已隐含实现 | 补充正式定义（本文档第 10 节已完成） |
| Concept Scope | 不存在，Teaching Policy 目前直接读 Global（零阶近似） | 全新构建：四态状态机、`teachable`/`candidate` 判定、挂起/恢复机制、新增数据表 |
| Global Scope | 已实现（`dan_global_state`），但更新方式是逐条 Evidence 触发 PromotionPolicy | 更新逻辑改造：从"逐证据更新"改为 Profile Consolidation |
| Teaching Effect | 不存在 | V1 代理指标（同概念 3 轮验证）+ 完整体系另立文档 |

---

**本版本状态**：v0.1 中的开放问题 B1（candidate）、B3（归并内容）已正式裁决并写入正文。B2（Learning Outcome）给出 V1 落地方案、完整体系留待另立文档。B4（Teaching Focus 升级）给出触发条件、不阻塞 V1。TTL 与 Subject Profile 的理论原则已记录，当前实现保留占位值。本文档已具备支撑 ADR 撰写的成熟度，建议下一步按 Concept Scope 四态状态机为核心拆分出对应的 ADR。
