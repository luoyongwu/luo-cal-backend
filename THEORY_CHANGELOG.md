

## 2026-07-31：ADR-016 Route A 收尾——两处 requires_dual_scale 相关回归修复

**背景**：Route A（学生级全局 `dan_global_state` 表，取代按 world 拆三行
分别判断 Promotion 状态的旧设计，见 ADR-016 §12/v8）真实 Supabase 环境
验证时，`student_A_representation.json` 与 `student_B_flow.json` 两个
Canonical Profile 的 `stage_expected` 断言持续 FAIL（`expected: stable`,
`actual: fragile`），尽管权重数值本身（RWM/FWM weight、
`state_revision_count`）均已达标。

**修复一：fixture 缺少 `requires_dual_scale: true`**
两个 fixture 的 `expected_output` 写了 `stage_expected: "stable"`，
但顶层缺少 `requires_dual_scale: true`（对照已通过验证的
`SYN_E_RECOVERY.json` 有此字段）。`validation/verification_runner.py::
replay_fixture()` 默认该字段为 `False`，导致两个 fixture 被静默路由进
ADR-012 之前的旧逻辑 `decide_stage()`，而非新的 `PromotionPolicy`
（N=5, K=4, Margin=0.15, θ=0.55）路径。`decide_stage()` 要求
`effective_confidence = confidence * world_share >= 0.7` 才能晋升，而
`BayesianAggregator` 的 `confidence` 公式中 `evidence_factor` 在样本数
n=5 时数学上限约 0.833，即使证据 100% 纯净一致，`effective_confidence`
在 5 条证据规模下也很难突破 0.7——这不是数据噪声导致的偶发失败，是
路径选择错误导致断言在结构上不可能通过。已为两个 fixture 补上
`requires_dual_scale: true`。

**修复二（更深层，第一次修复未能解决问题后才发现）：
`check_stage_expected()` 未随 Route A 同步更新**
修复一 push 后重新验证，A/B 的算法路径、权重数值确认已改用
`PromotionPolicy`，但 `stage_expected` 断言结果表面上毫无变化，仍报
`actual: fragile`。排查发现根目录 `verification_runner.py::
check_stage_expected()` 固定读取
`run_result["final_state"][dominant_world]["stage"]`，即按 world 拆
三行的旧 `dan_state.stage` 列。但 Route A 之后，`run_pipeline()` 新路径
（`use_promotion_policy=True`）不再写这一列（`write_state()` 调用中
`stage`/`promotion_state` 参数始终是 `_UNSET` 哨兵），该列永久停留在
`ensure_student_initialized()` 打底时的初始值 `"fragile"`。真正的
stage 结果只存在于 `dan_global_state.stage`
（`run_result["final_global_state"]["stage"]`），由
`update_global_promotion_state()` 写入。

此 bug 自 Route A 落地起就已存在，此前未暴露的原因是：唯一走
`requires_dual_scale=true` 路径且使用 `stage_expected` 字段做断言的
fixture 只有刚补上该字段的 A/B；`SYN_E_RECOVERY.json` 虽然也走新路径，
但用的是 Route A 时新写的 `recovery_tick`/`final_locked_world`
两个检查函数，这两个函数从一开始就正确读取 `final_global_state`，
未受影响。

`check_stage_expected()` 现按 fixture 是否 `requires_dual_scale` 分支：
`true` 时读 `final_global_state.stage`；`false`（旧 `decide_stage()`
路径，兼容尚未迁移的历史 fixture）时保持原有读法不变。

**验证结果**：两次修复叠加后，重新运行根目录 `verification_runner.py`
（真实 Supabase，覆盖全部 A-E Canonical Profile），总计从 19/22 提升到
21/22。A/B 的 `stage_expected` 均转为 PASS，C/D/E 结果与修复前完全一致，
未引入回归。剩余唯一 FAIL 是 `student_D_uncertain.json` 的
`dominant_world: "none_or_weak"`（历史遗留的过时期望值字符串，验证器
只会输出具体世界名，该断言结构上无法 PASS，真正想验证的意图已由
`max_world_weight_lte=0.55` 覆盖并通过），已记录、留待单独处理，不属于
本次修复范围。

**记录进"已知模式"清单**：本次两处 bug 都属于同一类模式——
"架构迁移后，某个下游消费方（本例是验证器的断言检查函数）没有同步
更新读取字段，不报错，只是静默测不到该测的东西"。与此前
`fetch_evidence_history()` 缺失、`concept_id` 未同步到
`st.session_state` 属于同一类历史事故模式，值得在未来做类似的表结构
迁移（例如把某个状态从一张表挪到另一张表）时，专门检查一遍所有下游
读取点是否都已同步。

## 2026-08-02：socratic_chat() 无跨轮对话记忆——规则6在架构层面无法生效

**发现过程**：一份原本用于验证 SCL_SYSTEM_PROMPT 规则6（"任务完成推进
（含信息重复检测）"）合规性的探针脚本，脚本化模拟了三组多轮对话（学生
给出正确完整答案后观察模型是否推进），逐字读取完整对话记录时意外发现：
模型每一轮的回复单独看都合理、像模像样，但通读完整对话会发现模型似乎
"忘了"自己上一轮问过的内容。

**根因**：排查 `main.py::socratic_chat()` 发现，该函数每次调用 Claude
API 时是：

```python
message = claude.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=500,
    system=prompt,
    messages=[{"role": "user", "content": f"概念{data.concept_id}\n学生输入：{data.user_input}"}]
)
```

**每次只发一条孤立消息，完全不携带对话历史**。生产环境里，Claude 每一
轮收到的都是一次性的、失忆的单条消息——上一轮问了什么、学生上一轮说了
什么，这一轮的 API 调用里根本不存在。这意味着规则6里"自我核查：这个
问题的答案是否已经明确出现在学生刚才的回复文本中"这条指令，从架构层面
看，模型永远无法真正判断"这个问题我是不是已经问过第二次、第三次了"——
prompt 承诺了一种基于跨轮次记忆的行为，但底层架构根本没有提供这种记忆。
写得再精确的 prompt，也没法让模型记住它自己上一轮说过什么。

**为什么此前未被发现**：这属于"不报错、悄悄退化、只有换个角度看才会
暴露"的历史模式（与 `fetch_evidence_history()` 缺失、`BOUNDS_TRAP`
反斜杠属于同一类）。更结构性的原因是：CLVS/十位学生模测/Canonical
Profile A-F/SIM系列/D3系列，全部直接手工构造 `Evidence` 对象喂给算法，
从未真正调用过 `socratic_chat()` 本身——`verification_runner.py` 模块
文档里明确记录这是"刻意的范围限定，不是疏漏"，但副作用是这个函数内部
"要不要传对话历史"这件事，从来不在任何一次模测的覆盖范围内。人工手动
测试时，即使是多轮对话，单条回复通常看起来合理、不像"明显故障"，只有
通读完整多轮对话、专门去对比"这个问题是不是问过了"才会注意到，这正是
本次探针脚本因为设计成脚本化多轮对话、又逐字通读了完整记录才意外撞见
的场景。

**修复**：

1. 新增 `chat_messages` 表（Supabase migration 已手动执行），持久化每个
   `(student_id, session_id)` 下的完整对话轮次。
2. `main.py` 新增 `fetch_chat_history()`/`save_chat_message()`，
   `socratic_chat()` 现在会先读取该 session 下最近的对话历史（上限20条，
   约10轮问答），拼进 `messages` 数组一起发给 Claude；响应返回后把本轮
   对话（学生输入 + `clean_response`，不含内部 `[EWM:...]` 标记）持久化
   供下一轮读取。
3. 失败容错模式与 `write_signal()` 一致——读写失败只打印，不打断学生的
   对话体验。

**已知限制（本次未处理，留待后续）**：
- `session_id` 默认值是 `"default"`，若前端不为不同 concept 分配不同
  `session_id`，历史会跨概念无限累积混杂，需要前端配合或后续补充概念
  切换时的 session 重置逻辑。
- 历史读取上限固定20条，未做基于 token 数的动态截断或摘要，长对话场景
  可能需要后续优化。
- 本次修复后规则6是否真的稳定生效，仍需要一次真实的多轮对话实测确认
  （此前的探针脚本因为未正确传入 `turns` 字段，本身也有设计缺陷，需要
  重新设计探针或直接用真实 `/api/v1/chat` 接口验证）。

**记录进"已知模式"清单**：本次是第三次遇到"某个环节因为验证范围的
刻意限定，导致一个真实存在的问题长期不在任何自动化测试的覆盖范围内"
——`fetch_evidence_history()` 缺失、`BOUNDS_TRAP` 反斜杠属于"实现细节
静默退化"，本次属于"验证体系的架构性盲区"，性质上更接近后者：不是代码
写错了没测出来，是这类代码从设计上就没有被任何现有测试路径覆盖过。未来
如果计划新增覆盖真实 `/api/v1/chat` 端点（而非绕过它直接构造 Evidence
对象）的验证机制，应作为独立的验证层级，不与现有 CLVS 混淆职责范围。

## 2026-08-02：CONCEPT_CONSTRAINTS 从前端迁移到后端——单一真值源修复

**发现过程**：在排查 Streamlit 前端仓库归属时（确认 Streamlit Cloud 部署
日志显示实际绑定的是 `luoyongwu/Ap-cal` 仓库 `main` 分支的 `app.py`，
而非其他几个相似命名的历史仓库），审查该前端代码时发现：

```python
class RailwayAdapter:
    def chat(self, system, messages, max_tokens=500):
        ...
        payload = {"concept_id": concept_id, "user_input": last_user,
                   "session_id": "streamlit", "language": lang}
        # system 参数从函数签名接收，但从未出现在 payload 里
```

`get_ai_response()` 精心构造的 `system_msg`——包含全部 19 条
`CONCEPT_CONSTRAINTS`（逐 AP Calculus 概念定制的 Socratic 教学
HARD RULE，含 4.3 概念极其重要的 PRE-OVERRIDE 硬性规则）——被传给
`adapter.chat(system_msg, msgs)`，但当用户在侧边栏选择"🚀 Railway
Backend"（唯一需要授权码、真正调用 Claude、真正写入 `dan_state` 的
生产/测试链路）时，`RailwayAdapter.chat()` 完全丢弃了这个参数。后端
`main.py::socratic_chat()` 当时也没有任何地方能接收或使用这类信息，
即使前端把它发过去也无处安放。

**影响范围**：只要学生走的是 Railway Backend 这条真实生产链路（唯一
会产生 `cognitive_signals`/`dan_state`/`dan_global_state` 诊断数据的
链路），这套精心设计的逐概念教学策略**从未真正生效过**——包括 4.3
概念那条要求"必须先确认是否求导前代入数值"的关键 HARD RULE。这意味着
此前所有走 Railway Backend 产生的对话数据，是在"通用苏格拉底规则"下
产出的，不是在"逐概念精确约束"下产出的，诊断数据的教学精度低于设计
预期。走 Anthropic/DeepSeek/Ollama 这几个不参与测试、不需要授权码的
路径不受影响（那几个 adapter 会正常使用 `system` 参数）。

**决策（2026-08-02，Yongwu 拍板）**：采纳"方案1"——把 `CONCEPT_CONSTRAINTS`
彻底搬进后端，作为 SCL 策略引擎的硬性组成部分，不采用"前端透传 system
给后端"的方案2。理由：
- 前端透传等于让前端拥有"篡改导师控制策略"的特权，与"前端只做 UI/
  身份认证，后端掌控控制论"的既有分层原则（`main.py` 已有的
  `SCL_SYSTEM_PROMPT`/EWM检测/`aggregate_dual_scale()`/
  `PromotionPolicy` 全部位于后端域）不一致。
- 若透传，未来任何新客户端（移动端/自动化评估脚本等）接入后端都得
  各自重新实现一份 `CONCEPT_CONSTRAINTS`，教学策略会在多处重复维护、
  彼此不同步，是新的技术债来源。

**修复（单一真值源迁移）**：

1. `luo-cal-backend` 仓库新增 `concept_constraints.py`，19 条策略
   逐字迁移自前端，未做任何改写。
2. `main.py::socratic_chat()` 按 `data.concept_id` 查表，动态拼进
   `SCL_SYSTEM_PROMPT_ZH/EN` 之后再发给 Claude：
   ```python
   concept_constraint = CONCEPT_CONSTRAINTS.get(data.concept_id, "Guide step by step.")
   final_system_prompt = f"{prompt}\n\n【当前概念专项教学约束】\n{concept_constraint}"
   ```
3. `luoyongwu/Ap-cal` 仓库删除 `CONCEPT_CONSTRAINTS` 字典本身与
   `system_msg` 里的 `TEACHING CONSTRAINT` 拼接行；`STATUS`/`LEAKAGE`
   标签体系、`SINGLE-PROBLEM RULE`、`OPENING_PROMPTS` 等与
   `CONCEPT_CONSTRAINTS` 无关的逻辑原样保留，仍对 Anthropic/DeepSeek/
   Ollama 等测试用途路径有效。

**验证**：本地沙盒验证 `main.py` 能正确 `import concept_constraints`，
4.3 的 PRE-OVERRIDE 规则文本完整；前端 `app.py` 本地 AST 解析确认
`CONCEPT_CONSTRAINTS` 字典与其唯一调用点均已彻底移除，`OPENING_PROMPTS`
等无关功能保留完整。两个仓库分别 commit + push，并各自做了独立验证
（重新 clone 全新副本核实内容落地）。

**记录进"已知模式"清单**：与 `fetch_evidence_history()` 缺失、
`socratic_chat()` 无跨轮记忆同属"某个环节静默丢弃数据但不报错"的
历史模式，本次的特殊之处在于跨越了两个独立仓库（前端/后端），提醒
未来审查数据管道完整性时，不能只看单一仓库内部的调用链，还需要
确认"跨仓库、跨部署边界"传递的数据是否真的被下游消费，而不是止步于
"函数签名接收了参数"就认为没问题。

## 2026-08-03：locked_mechanism 滞回保持修复——诊断信号的保守输出原则

**发现过程**：2026-08-02 第四轮十位学生模拟（专门验证 ADR-018 新增的
`dan_global_state_history` 历史表）意外暴露：多个学生（D4_01/D4_02/
D4_05）在证据流出现真实迁移、mechanism-level track 正常 demote 时，
`locked_mechanism` 会在同一轮里立即被置回 `None`——即使 `world_stage`
依然是 `stable`，诊断整体并未真正"失去确定性"。

**根因**：`update_global_promotion_state()` 组装 `locked_mechanism`
的逻辑此前是"`mechanism_stage == "stable"` 时才赋值，否则为 `None`"。
`PromotionPolicy._decide_mechanism_stage()` 的滞回逻辑（demote_below=3）
会在证据窗口真实变化时让 `mechanism_stage` 从 `stable` 正常降级到
`emerging`——这是设计意图内的行为——但降级发生的同一轮，输出组装逻辑
就把 `locked_mechanism` 整个清空了，没有给"刚降级、旧结论还没完全失效"
这个中间状态留任何余地。

**架构原则（Yongwu + DeepSeek 讨论达成，2026-08-03）**：诊断引擎内部
计算必须绝对诚实——`world_weights`/`mechanism_attribution` 该是多少
就是多少，`PromotionPolicy` 自己的锁存状态不应该被下游输出逻辑篡改；
但向下游（Teaching Policy 等控制/决策系统）输出的信号应该适度保守、
稳定，不应该因为单轮证据的短暂波动就立刻收回已经建立的诊断结论——
类比自动驾驶不因单帧画面闪烁就猛打方向盘。这条原则具有一般性，未来
任何"诊断信号→下游消费"的边界都适用，不只是这一次修复。

**修复**：在 `update_global_promotion_state()` 的输出组装层（不是
`PromotionPolicy` 内部）新增"滞回保持 + 强制释放"逻辑——`mechanism_stage`
不再是 `stable` 时，检查上一轮锁定的 mechanism 是否已经从当前
`mechanism_window_snapshot` 里完全消失（计数为 0）：未消失则沿用
上一轮 `locked_mechanism`（连带恢复对应的 `locked_worlds`）；完全消失
才真正释放为 `None`。不引入任何新持久化状态，只复用已有的
`policy.mechanism_window_snapshot`（Step 1 就已暴露的只读属性）和
`dan_global_state.locked_mechanism`（上一轮写入的值，通过
`get_global_state()` 读回）。

**验证**：用 D4 模测中真实触发过此问题的确切序列（D4_01/D4_02/D4_05）
做回归验证，确认修复后三者的 `locked_mechanism` 在证据真实迁移的
过渡轮次里正确滞回保持，直到旧 mechanism 真正从窗口消失才释放。同时
确认"结构性永久平局"场景（D4_03/D4_07，如 `ABSOLUTE_VALUE` 的
`RepresentationShift`/`SemanticIntegrity` 精确 50/50 归因，`mechanism`
层从未真正锁定过）完全不受本次修复影响——这是 ADR-017 Mechanism
Parity 问题的另一个独立变体，`old_locked_mechanism` 从一开始就是
`None`，滞回保持分支从未被触发，行为与修复前逐字节一致，留待下一个
session 单独讨论是否需要引入 `locked_mechanisms`（复数）概念。

**新发现的语义提醒（需要在未来下游消费逻辑里明确遵守）**：回归验证
中 D4_09 出现了此前从未见过的组合——`stage=emerging`（既未 world 层
锁定也未 mechanism 层重新锁定）却依然携带 `locked_mechanism=
StructuralReasoning`/`locked_worlds=['FWM','AWM']`（滞回保持中）。这
意味着**滞回保持机制生效之后，`stage=='stable'` 不再是
`locked_mechanism is not None` 的充分条件**——过去可以默认"看到具体
mechanism 名字就等于 stage 是 stable"，现在不再成立。任何未来读取
`dan_global_state` 做展示或决策的下游逻辑（Dashboard、Teaching Policy
之外的其他消费方），判断"诊断是否可用"应该直接检查
`locked_mechanism is not None`，不应该依赖 `stage` 字段做代理判断。
`TEACHING_POLICY_INJECTIONS` 的查表逻辑本身已经是直接按
`locked_mechanism` 查的，不受影响；这条提醒是给未来新增的消费方准备
的，防止同一个"表面矛盾组合"在不知情的情况下被误判为 bug。

**记录进"已知模式"清单**：这是第一次在"诊断结果"和"下游消费"之间
显式引入"保守化"这一层，此前所有历史事故（`fetch_evidence_history()`
缺失、`BOUNDS_TRAP` 反斜杠、`socratic_chat()` 无跨轮记忆、
`CONCEPT_CONSTRAINTS` 前后端断层）都是"某处静默丢失了本该传递的信息"，
这次不同——本次是刻意决定"在数据诚实性和下游稳定性之间，边界层应该
偏向稳定性"，是一次真正的架构取舍，不是简单的 bug 修复，值得和历史
事故区分对待。

