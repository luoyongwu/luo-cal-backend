

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

