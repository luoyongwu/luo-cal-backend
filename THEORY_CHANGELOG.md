

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

