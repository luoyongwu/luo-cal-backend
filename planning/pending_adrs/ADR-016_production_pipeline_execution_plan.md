<!--
草稿说明：本文件是 ADR-016 的定稿版本，按约定的工作惯例暂作为独立文件存入仓库
planning/pending_adrs/ 目录，不直接合并进 planning/DESIGN_NOTES.md 正文。

工作惯例（首次在此明确记录，适用于此后所有同类情况）：
对于涉及较大风险的 ADR（尤其是触及生产数据、不可逆操作的），先以独立文件形式存档，
不急于并入主文档；待执行过程中风险基本消失（例如阶段四 Full Validation 通过、
Rollback Criteria 从未被触发）后，再正式合并进 DESIGN_NOTES.md，且合并时必须
附上一段"过程描述"——记录实际执行中计划与现实的出入、遇到的问题、如何修正——
而不是只保留合并后的最终结论。这是为了如实反映"计划-尝试-修正"的动态过程，
避免文档只呈现事后诸葛亮式的整洁叙事。
-->

# ADR-016: 生产管道接入执行计划（ADR-012/013 落地）

**状态**：已确认，独立存档中（暂不并入 `planning/DESIGN_NOTES.md`，待阶段四 Full Validation 通过、Rollback Criteria 从未触发后再正式合并，合并时需附过程描述）
**日期**：2026-07-28（初稿），2026-07-29 更新（v4/v5/v6，见第十一节 ADR Evolution）
**关联 ADR**：ADR-012（Persistence-based Promotion Policy）、ADR-013（Diagnostic State 时序分离）、ADR-014 + Amendment（持久化与工具决策框架）

---

## 一、背景

ADR-012/013 的设计（`PromotionPolicy` + `aggregate_dual_scale()`）已在沙盒环境（CLVS，五组合成画像 SYN_A～SYN_E_RECOVERY）中完成验证，但生产管道 `run_pipeline()` 目前仍调用旧的 `decide_stage()`，两者存在集成缺口。本 ADR 记录把设计从"沙盒验证"推进到"生产真实运行"的完整执行计划，包括阶段拆分、每阶段的执行要点、风险来源与规避措施。

---

## 二、五阶段总览

| 阶段 | 任务 | 风险等级 |
|---|---|---|
| 一 | `dan_state` 表执行 `temporal_views` 列迁移 | 最低 |
| 二 | `PromotionPolicy` + `aggregate_dual_scale()` 正式接入 `run_pipeline()`，替换 `decide_stage()` | 核心攻坚点 |
| 三 | `SYN_E_RECOVERY.json` 补齐字段验证支持（`recovery_tick`/`final_locked_world`），不涉及文件改名 | 中等 |
| 四 | 生产级 runner（真实 Supabase + `DANMemoryService`）重跑 A-E 五组，三级渐进式验证 | 本计划中不确定性最大的阶段 |
| 五 | `theory/THEORY_CHANGELOG.md` 补记录 | 收尾 |

**总工作量估计**：7～10 个工作 session（约2周，视阶段四排查情况可能延长）。

---

## 三、各阶段执行要点与常见走偏之处

### 阶段一：schema 迁移

不只是"加一列"，关键是确认**旧代码完全不依赖隐式全字段遍历**。

**执行前置检查**：
- 全文搜索现有代码里对 `dan_state` 表的访问方式，确认没有 `SELECT *` 或按字段名遍历的隐式依赖，避免新增列意外触发未预期的行为。

**执行状态**：`temporal_views JSONB DEFAULT NULL` 已确认存在（2026-07-28 健康检查：`is_nullable=YES`，全表 NULL，无重复主键，`aggregator_version` 唯一，baseline 干净）。

**追加迁移（阶段二前置发现，2026-07-28）**：见下方"PromotionPolicy 有状态重建契约"，需在阶段二开工前追加执行：

```sql
ALTER TABLE dan_state ADD COLUMN promotion_state JSONB DEFAULT NULL;
```

此列与 `temporal_views` 平级、独立、语义不重叠，风险等级与阶段一原迁移相同（最低）。执行后应重新跑一次健康检查 SQL（在原有四项基础上加一条 `promotion_state IS NOT NULL` 的计数，确认新列全表为 NULL）。

### 阶段二：PromotionPolicy 接入

不只是"替换一个函数调用"，是**同时拆分了两件事**：旧 `decide_stage()` 同时负责"推断认知状态"和"决定 Promotion 策略"；新设计把 `aggregate_dual_scale()`（计算）和 `PromotionPolicy`（决策）拆开了。

**执行前置检查**：
- 显式验证两者之间的数据传递契约：`aggregate_dual_scale()` 返回 `(cumulative, recent)` 两个 `WeightVector`；`PromotionPolicy.update()` 期望的入参是裸 `Dict[str, float]`（`world_weights`），不是 `WeightVector` 对象，且必须传 **`recent.world_weights`**，不是 `cumulative`（`aggregate_dual_scale()` 文档字符串明确 `recent` 才是供 Promotion 做"近期持续性"判断用的）。
- **验收项**：在调用 `policy.update()` 前加断言，确认传入的确实是 `dict` 而非 `WeightVector` 对象，防止手滑传错整个对象或传错 cumulative/recent。

**[最高优先级架构前置约束] PromotionPolicy 有状态重建契约**（2026-07-28 发现，阶段二真正的核心攻坚点，非上述类型断言可覆盖）：

`PromotionPolicy` 是**有状态的控制器**（`_window` 滑动窗口 deque + `_locked_stable`/`_locked_world` 施密特触发器式滞回锁存），必须跨多次 `update()` 调用累积。若 `run_pipeline()` 每次都无状态地 `PromotionPolicy()` 重新实例化空对象，N=5/K=4 窗口机制与滞回锁存将完全失效，ADR-012/013 建立的"时序持续性"判断会退化为一维瞬态映射——这是比接口类型不匹配严重得多的问题，禁止在阶段二直接空对象初始化。

**方案确认：`promotion_state` 独立列，不与 `temporal_views` 合并存储。**

- `temporal_views`：认知诊断结果的快照（`rolling` 视图：`world_weights`/`entropy`/`effective_sample_size`），**可重算**（有 `evidence_history` 即可重新跑 `aggregate_dual_scale()` 得到同样结果），沿用 ADR-013/014 原定义，不改动。
- `promotion_state`（新列）：`PromotionPolicy` 决策过程的累积状态，**不可重算**（`_window` 里是历史决策的中间结果，不是原始 evidence，丢失即不可恢复），独立列存储。

**为什么不把两者合并进同一个 `temporal_views` JSONB（曾讨论过的备选方案，已否决）**：ADR-014 已冻结 `temporal_views` 为"诊断状态的时间视图"这一语义；合并存储等于事后改写一份已定稿 ADR 的接口契约，而不是正交新增。且会让"`temporal_views` 是否为 NULL"这条健康检查语义变得含糊（诊断视图为空 ≠ 控制器状态为空）。独立列保持两条检查各自干净，也更贴合 ADR-012 的诊断/决策分层原则。

**`promotion_state` 存储结构**：

```json
{
  "window": ["FWM", "FWM", "RWM", "FWM", "FWM"],
  "locked_stable": true,
  "locked_world": "FWM"
}
```

**⚠️ 待补：Versioned State（2026-07-29 采纳，尚未实施）**：当前已上线的 `export_state()`/`rehydrate()` 输出的 `promotion_state` **还没有版本字段**。建议尽快（不必等到阶段三/四完成）补一个 `"version": 1` 键：

```json
{
  "version": 1,
  "window": ["FWM", "FWM", "RWM", "FWM", "FWM"],
  "locked_stable": true,
  "locked_world": "FWM"
}
```

理由：`PromotionPolicy` 未来大概率会演进（比如新增 `confidence`/`lock_reason`/`last_transition` 这类字段），现在加一个版本号成本几乎为零；等真的改了结构再补，`rehydrate()` 就要处理"这条历史记录到底是哪个版本、字段该怎么解释"的猜测性代码。`rehydrate()` 读取时应对 `version` 缺失（即已上线的旧记录）按 `version=1` 处理，保持向后兼容。

**`PromotionPolicy` 需新增的序列化接口**（`promotion_policy.py`）：

```python
def export_state(self) -> dict:
    """导出控制器内部状态快照，用于持久化落库"""
    return {
        "window": list(self._window),
        "locked_stable": self._locked_stable,
        "locked_world": self._locked_world,
    }

@classmethod
def rehydrate(cls, config: Optional[PromotionPolicyConfig], state_dict: Optional[dict]) -> "PromotionPolicy":
    """从持久化快照恢复控制器状态；state_dict 为 None/空 dict 时等价于全新实例"""
    instance = cls(config)
    if state_dict:
        instance._window = deque(state_dict.get("window", []), maxlen=instance.config.window_size)
        instance._locked_stable = state_dict.get("locked_stable", False)
        instance._locked_world = state_dict.get("locked_world", None)
    return instance
```

**为什么不用"每次从 `evidence_history` 现场重算窗口"这个不改 schema 的备选方案（已否决）**：
- 性能随历史长度线性恶化——学生做到第 100 题时，每次新信号到达都要重新在内存里跑 100 次 `policy.update()`。
- 若未来 `PromotionPolicy` 算法细节或 `margin`/`theta` 参数调整，历史重算会让过去已落库的 stage 轨迹在内存中被悄悄篡改，且无法区分"刚满足锁存条件"与"已锁存很久"这两种在原始设计里可能对应不同行为的状态。
- 本质是把"持久化"问题转移成"每次重算"，回避而非解决问题。

**`DANMemoryService` 需要的配套改动**（2026-07-28 发现的额外缺口，两份材料均未提及，必须一并修复，否则前述改动全部落空）：
- `get_state()` 的 `.select(...)` 字段列表目前**不包含** `temporal_views` 也不包含 `promotion_state`，必须加入。
- `write_state()` 的 `.update({...})` 目前**不写入**这两个字段，必须加入对应参数与写入逻辑。

**`run_pipeline()` 修正后的执行链路**：

```python
def run_pipeline(student_id, cognitive_world, evidence_history, current_state,
                  dan_service, subject_id, aggregator):
    policy = PromotionPolicy.rehydrate(
        config=None,  # 默认 PromotionPolicyConfig，除非未来需要按学生/概念定制
        state_dict=current_state.get("promotion_state"),
    )
    cumulative, recent = aggregator.aggregate_dual_scale(
        evidence_history, recent_n=policy.config.window_size
    )
    new_stage = policy.update(world_weights=recent.world_weights)

    dan_service.write_state(
        student_id=student_id,
        cognitive_world=cognitive_world,
        stage=new_stage,
        evidence_count=len(evidence_history),
        weight_vector=recent.world_weights,
        aggregator_version=recent.aggregator_version,
        temporal_views={"rolling": {
            "world_weights": recent.world_weights,
            "entropy": recent.entropy,
            "effective_sample_size": recent.effective_sample_size,
        }},
        promotion_state=policy.export_state(),
        subject_id=subject_id,
    )
    ...
```

**验收项（汇总）**：
1. `promotion_state` 列已迁移且确认可空（见阶段一追加迁移）
2. `PromotionPolicy.export_state()` / `rehydrate()` 已实现并有单元测试覆盖（至少覆盖：全新学生 `state_dict=None`、已有锁存状态的学生两种路径）
3. `DANMemoryService.get_state()` / `write_state()` 已包含 `temporal_views` 与 `promotion_state` 的读写
4. `run_pipeline()` 每次调用都先 `rehydrate()` 再 `update()`，调用后写回 `export_state()`，全程不出现无状态空对象初始化

**⚠️ 待补：轻量级可观测性（2026-07-29 采纳，尚未实施）**：`fetch_evidence_history()` 缺失这个 bug 之所以潜伏很久没被发现，根本原因是系统没有可观测性——出问题只能靠事后翻 Railway 日志，而不是主动发现。不建议现在就建一套完整的统计仪表盘（成本过高、缺乏真实使用压力驱动），但建议给 `run_pipeline()` 加一条**结构化日志**（每次调用打印一行，不建单独的统计系统）：

```
student_id, latency, evidence_count, old_stage, new_stage, feature_flag(on/off)
```

这样数据从现在开始自然积累，等真的需要做统计分析或画图时，数据已经在日志里，不需要再回头补埋点。

### 阶段三：SYN_E_RECOVERY 验证支持补齐

**本节两处历史修正（2026-07-29）**：

1. 本节最初假设 `recovery_tick`/`locked_world` 是 `dan_state` 表里需要核实/新建的数据库列，据此写了一段"先查 `information_schema` 确认字段名"的前置检查——**这个假设是错的**。看过 `validation/student_archetypes/SYN_E_RECOVERY.json` fixture 原文后确认：这两个字段是 fixture `expected_output` 里的**验证目标值**，需要 runner 在逐轮 replay 时自己算出来再和期望值比较，从来就不是数据库表结构的一部分。下面的 SQL 前置检查段落已废弃，不要执行。
2. 本节最初还计划把 `verification_runner.py` 改名为 `clvs_sandbox_runner.py`——**这个计划也已撤销**。依据是 2026-07-16 `theory/THEORY_CHANGELOG.md` 里"发现：两套 verification_runner.py 并存"这条真实存在的历史记录，明确写着"根目录 `verification_runner.py`：不受影响，保留，不需要删除或修改"。真正被那条记录考虑过要改名的，是另一个文件 `validation/verification_runner.py`（沙盒版，写死 `CANONICAL_PROFILES` 字典、不接数据库），跟本 ADR 一直在改的这份文件是两个完全不同职责的验证器，本次改名计划是在不知道这段历史的情况下做出的错误决定，已撤销。

**实际需要做的事**（对应 07-16 记录里明确列出的后续待办第2、3项）：

1. `verification_runner.py`（文件名不变）的 `replay_fixture()` 需要读取 fixture 的 `requires_dual_scale` 字段，为 `true` 时显式给 `run_pipeline()` 传 `use_promotion_policy=True`——此前遗漏这一步，`SYN_E_RECOVERY` 这类要求双时间尺度机制的 fixture 会静默走旧的 `decide_stage()` 路径，测不到它本该测的东西。
2. 每轮 replay 后需要记录 `promotion_state_snapshot`（此前 trajectory 完全没有留存这个信息，导致 `recovery_tick` 这类需要逐轮追踪 `locked_world` 变化轨迹的验证项根本无法计算）。
3. 新增 `check_final_locked_world()` / `check_recovery_tick()` 两个检查函数，注册进 `CORRECTNESS_FIELDS`——对应 07-16 记录里"给生产级 runner 补充一个能识别 dual-scale 特殊断言的分支"这个方案（而不是强改 fixture 字段名去凑 `_gte`/`_lte` 后缀格式）。

**已废弃的前置检查（仅作记录，不要执行）**：

```sql
-- 已废弃：recovery_tick/locked_world 不是 dan_state 的列，这条查询问的是错误的问题
SELECT
  column_name,
  data_type,
  is_nullable,
  (SELECT COUNT(*) FROM dan_state WHERE dan_state.column_name IS NULL) AS null_count
FROM information_schema.columns
WHERE table_name = 'dan_state'
  AND column_name IN ('recovery_tick', 'locked_world', 'world_weights', 'aggregator_version');
```

**验收项**：
1. `replay_fixture()` 对 `requires_dual_scale=true` 的 fixture 正确传 `use_promotion_policy=True`
2. `promotion_state_snapshot` 正确记录在每轮 trajectory 里
3. `check_recovery_tick()` 的判定逻辑经过合成数据测试（模拟 fixture 描述的"先误锁 RWM、再正确解锁、最终锁定 FWM"轨迹），确认不会把中途被打破的早期锁定误判为最终复苏点
4. `verification_runner.py`（根目录）文件名不变；已知但本次未处理的相邻缺口——`final_recent_world_weights`/`final_recent_confidence` 这类需要"_approx + tolerance"比对机制的字段，目前仍会落入人工复核，留作独立后续任务

**验证结果（2026-07-29，已完成，阶段三验收通过）**：在真实 Supabase 上跑通全部 A-E 五组，`SYN_E_RECOVERY` 的两项新断言精确通过——`recovery_tick`（expected=11, actual=11）、`final_locked_world`（expected=FWM, actual=FWM）。详见 `theory/THEORY_CHANGELOG.md` 2026-07-29 条目"ADR-016 阶段三验收：SYN_E_RECOVERY 验证支持接入真实 Supabase 后完整通过"。A/B/D 三组 `stage_expected` 断言 FAIL 属预期内（旧 `decide_stage()` 路径的已知局限，待阶段四开启 `USE_PROMOTION_POLICY` 后解决，非本次回归）。

---

## 三点五、Stage 3.5：自然观测期（Natural Observation，2026-07-29 新增）

阶段三完成后、启动 Level 2 Shadow Run 之前，插入一个轻量的观测窗口，不做任何代码改动，只观察真实运行数据自然积累。**不需要刻意等待固定天数**——阶段三做完即可转入正常开发节奏，数据会随真实使用自然积累；这个窗口的作用是"到 Shadow Run 前记得回头看一眼"，而不是强制暂停开发。

观察项：
1. `promotion_state` 是否持续正常累积，而不是频繁被重置
2. `window` 长度是否始终符合 `config.window_size`，没有异常增长（对照第六节 Invariant Checklist 里已列出的这条不变性）
3. `temporal_views` 是否按预期持续更新，没有长期停滞
4. 是否出现异常的 Promotion 抖动（频繁 `stable ↔ fragile` 切换）
5. 是否有新的异常日志或性能问题

**已知限制**：目前真实学生数量少，观测数据量有限，这一步能做的验证深度本身受限于这个前提，不强求在数据不足的情况下人为拉长观测时间。

---

## 四、阶段四：三级渐进式验证流程

阶段四是整个计划中风险最集中的环节。采用三级递进式验证，核心原则：**每一级只多冒一种新风险**，前一级验证通过才能进入下一级，出问题时排查范围被逐级压缩。

### 回滚方案（Feature Flag，阶段二实施时一并写入）

`run_pipeline()` 保留旧 `decide_stage()` 的代码路径，通过一个**显式的 feature flag**（环境变量或函数参数，不是代码注释）控制新旧逻辑切换：

- Level 1（Smoke）、Level 2（Shadow）期间，flag 指向旧逻辑——生产管道继续用旧逻辑正常运行，新逻辑的测试完全不影响线上
- Level 3（Full Validation）写入生产数据前，把"flag 切换"和"写入"放在同一个操作窗口内——写入后立刻发现问题，可以立刻把 flag 切回旧逻辑

**flag 的作用边界需要明确**：它不是用来"万一出事就救火"的——数据库一旦已经写入新格式数据，单纯切回旧逻辑救不回已写入的数据，它的作用是把"出问题到发现问题"的影响时间窗口控制在分钟级，而不是让新逻辑跑了几天才发现异常。

**需要在切换前确认的一点**：如果 Level 3 已经写入了 `temporal_views` 列，切回旧逻辑后，旧 `decide_stage()` 不会读这一列，所以残留数据本身不影响旧逻辑运行——但如果届时已有 Dashboard 或其他消费者开始读 `temporal_views`，切回旧逻辑后它们会读到"有数据但不再更新"的状态，需要在切换前确认没有下游消费者受影响。

### Rollback Criteria（回滚触发条件）

以下任一情况发生，立即执行回滚，不再继续排查：

1. Shadow Run 出现无法解释的差异（差异分类表里落入"需要排查"且核实后仍无法解释）
2. 生产数据健康检查脚本运行失败或检出异常项
3. Supabase 层面出现数据异常（如写入报错、连接超时、字段类型冲突）
4. Pipeline 响应延迟相较旧逻辑增加超过 50%（初始阈值，可根据实测基线调整）

**回滚动作**（按顺序执行）：
1. Feature flag 切回旧版 `decide_stage()`
2. 禁用 `PromotionPolicy` 的写入路径（不删除代码，只停用调用）
3. 保留 `temporal_views` 列及其已写入数据，不做删除或回滚清空（供事后排查用）
4. 记录 Incident Report：触发的具体条件、发生时间、涉及的 `student_id` 范围、初步判断的原因、后续修复计划

### Level 1 · Smoke Test（阶段二完成后立即做）

- 只跑 SYN_A（结构最简单的画像）
- 用生产级 runner + 真实 Supabase，但写入独立的测试表/测试 schema，**不碰生产 `dan_state` 表**
- 目的：验证"新代码在生产依赖下能跑通"，不测正确性
- 通过标准：不报错、不超时、输出结构符合预期

### Level 2 · Shadow Run（Smoke 通过后）

- 用生产级 runner + 真实 Supabase，**只读生产数据、不写入**
- 跑全部 A-E 五组
- 新旧逻辑（`aggregate_dual_scale()` vs 旧 `decide_stage()`）输出并排比较
- **判断标准**：新旧结果不应完全一致（否则说明新设计无实际效果），但差异的方向和幅度必须可解释

**差异分类标准**（逐条按此表归类，不凭感觉判断）：

| 差异类型 | 判定 | 处理方式 |
|---|---|---|
| rolling 窗口为空导致 `temporal_views.rolling` 为 NULL，旧逻辑有值 | 预期内 | 记录，不阻塞 |
| 同一学生 cumulative 画像新旧基本一致，rolling 画像在合理范围内波动（如 fragile ↔ emerging） | 预期内 | 记录，不阻塞 |
| 同一学生 cumulative 画像新旧出现方向性矛盾（如旧逻辑判 stable、新逻辑 cumulative 判 fragile） | 需要排查 | **阻塞** Shadow Run 通过 |
| 某学生状态在新逻辑下"从不稳定直接跳 stable"，旧逻辑有过渡态 | 可能是预期行为（ADR-014 讨论过），但需确认 | 逐条核实 |

- 通过标准：全部差异归类为"预期内"或已核实清楚的"逐条核实"项；只要出现未解释的"需要排查"案例，停下来修 bug，不带着疑问进入 Level 3

**额外检查项（2026-07-29 新增，与 `fetch_evidence_history()` 修复质量间接相关）**：修复该函数后新写入的记录，`evidence_count` 是否在合理增长——如果增长速度和真实学生的实际答题频率明显不符（过快或过慢），说明这次修复本身可能还有遗漏（例如查询范围不对、遗漏了某类信号），这是对修复质量的一次间接验证，不要跳过。

### Level 3 · Full Validation（Shadow Run 通过后）

- 正式写入生产 `dan_state` 表，跑全部 A-E 五组
- **并发写入测试**（并入本级，而非独立环节）：用 `asyncio.gather()` 模拟 **3-5 个不同 `student_id`** 同时触发 `run_pipeline()`，写入同一 Supabase 实例的同一张表，跑完后逐条核对是否存在写入冲突（如同一记录被两个事务部分覆盖、`temporal_views` 缺失字段）。**注意**：不测试同一个 `student_id` 的并发更新——这是更极端、生产环境里基本不会出现的场景（一个真实学生不会同时在两台设备上答两道不同题），且这类问题该由数据库行锁或应用层幂等设计解决，不该靠 Promotion 逻辑本身兜底。不同 `student_id` 并发写入才是生产环境的真实并发模式
- **错误路径检查**：在烟雾测试阶段故意触发一次中间步骤异常，验证系统是否优雅降级、留下可排查日志，而非静默把 `dan_state` 写成半成品——只需确认这一个核心安全属性，不需要覆盖所有错误类型
- 写入后立即跑一次生产数据健康检查脚本（见下）
- 通过标准：全部断言通过 + 健康检查无异常

### 附：生产数据健康检查脚本（阶段一 migration 执行后、阶段二接入前先跑一次建立 baseline；阶段四 Full Validation 后再跑一次做对比）

检查项：
1. `temporal_views` 是否为 NULL（migration 刚执行完时全部应为 NULL）
2. `promotion_state` 是否为 NULL（追加迁移刚执行完时全部应为 NULL，2026-07-28 新增）
3. 现有 `world_weights` 列是否有 NULL 值或异常类型
4. 同一 `student_id` 是否存在多条记录（不应该有）
5. `aggregator_version` 字段是否存在、是否一致

该脚本本身不修复数据，只用于记录"当前生产数据的 baseline 状态"，供阶段四出问题时溯源对比。

---

## 五、阶段五：变更记录规范

`theory/THEORY_CHANGELOG.md` 里的这条记录，至少包含：
- 切换日期
- 切换前后的函数名和所在文件
- 涉及的主要 ADR 编号（012/013/014，及本 ADR-016）
- 一句简要说明"为什么切换"（避免一年后的读者需要翻三份 ADR 才能理解这条记录）
- 一个指向阶段四验证结果的指针（例如"验证通过，详见某次测试记录"）
- **已知行为差异声明**：列出 Shadow Run 中确认为"预期内"的新旧逻辑行为差异，例如：
  - "旧逻辑在证据不足时可能直接返回 stable，新逻辑在同等条件下返回 fragile——不是 bug，是 ADR-012 设计的预期行为"
  - "rolling 窗口为空时，`temporal_views.rolling` 为 NULL，`PromotionPolicy` 回退使用 cumulative 画像——与 ADR-014 Amendment 的 fallback 约定一致"

  这份声明的作用：一年后如果有人发现某学生状态和"以前"不一样，翻 changelog 能立刻判断"这是设计预期的变化"还是"可能是后来引入的 bug"。没有这份声明，所有新旧行为差异在事后都会被当成 bug 排查一遍。

---

## 六、不变性检查表（Invariant Checklist）

`PromotionPolicy`、`aggregate_dual_scale()`、`temporal_views` 一旦上线，本质上构成了一个状态机，而不是普通的无状态代码。以下不变性必须在每次改动这三者之后手动核对，健康检查脚本也应把可自动化的项目纳入断言：

| 不变性 | 说明 |
|---|---|
| `student_id` 永远唯一 | 同一学生不应在 `dan_state` 表里出现多条记录（阶段四健康检查已覆盖此项） |
| `aggregator_version` 不能下降 | 版本号只能前进或持平，不能出现新写入的记录版本号低于历史记录 |
| `temporal_views` 不能为空（migration 后） | 迁移完成后所有记录该列应至少为 NULL 占位，不应缺失整个字段 |
| `promotion_level` 不能倒退超过一级 | 认知诊断的晋级/降级应是渐进的，一次性跨级倒退大概率是 bug 而非真实学生表现 |
| 时间戳必须单调递增 | 同一学生的 evidence 事件时间戳序列不应出现乱序或回退 |
| `promotion_state.window` 长度不超过 `config.window_size` | deque 的 `maxlen` 保证了这一点在内存中成立，但反序列化路径（`rehydrate()`）若绕过 deque 直接赋值列表，需额外校验，防止窗口无限增长 |

**用法**：任何改动 `PromotionPolicy`/`aggregate_dual_scale()`/`temporal_views` 相关代码前，先对照这张表检查改动是否可能破坏某条不变性；阶段四的健康检查脚本中可自动化的项（`student_id` 唯一性、`temporal_views` 非空）已纳入检查项，其余两条（版本不降、晋级不倒退超一级）建议在 Shadow Run 的差异比较逻辑里一并加入断言。

---

## 七、风险清单汇总（供执行时对照检查）

| 风险来源 | 对应规避措施 | 所属阶段/环节 |
|---|---|---|
| 并发/时序写入冲突 | `asyncio.gather()` 并发写入测试 | Level 3 · Full Validation |
| 真实时间戳 vs 合成时间戳的边界行为差异 | Shadow Run 新旧结果并排比较 | Level 2 · Shadow Run |
| 历史脏数据 | 生产数据健康检查脚本（迁移后立即跑一次建 baseline） | 阶段一后 / Level 3 后 |
| SYN_E_RECOVERY 验证支持缺失（recovery_tick/final_locked_world 是 fixture 期望值，不是数据库列；此前误判为字段映射问题） | 补齐 `replay_fixture()` 的 use_promotion_policy 传参 + promotion_state_snapshot 记录 + 两个新检查函数 | 阶段三 |
| 错误处理路径从未被触发 | Level 3 故意触发中间步骤异常 | Level 3 · Full Validation |
| 数据传递契约不匹配（阶段二） | `PromotionPolicy` 初始化 schema 断言 | 阶段二 |
| 隐式全字段遍历依赖（阶段一） | 全文搜索 `dan_state` 访问方式 | 阶段一 |
| PromotionPolicy 隐性有状态、每次无状态重新实例化导致窗口/锁存失效（2026-07-28 发现） | 新增独立 `promotion_state` 列 + `export_state()`/`rehydrate()` 序列化接口 | 阶段一追加迁移 / 阶段二 |

---

## 八、执行关卡

鉴于 Luo-cal 目前是单人开发，不设正式的"负责人分配表"，但阶段四三个 Level 之间设置显式确认关卡：

- **Level 1 → Level 2**：Smoke Test 通过标准（不报错、不超时、输出结构符合预期）达成后，执行者可自行判断进入 Shadow Run，无需额外确认
- **Level 2 → Level 3**：Shadow Run 的差异分类表必须全部落在"预期内"或"已核实的逐条核实项"，**这一步建议项目负责人显式过目差异分类结果再拍板进入 Full Validation**——因为 Level 3 一旦写入生产数据，回滚成本显著上升
- **触发暂停条件**：如果任一阶段的排查时间明显超出预期估计（参考第二节工作量估计的对应阶段），暂停并重新评估，而不是带着"再试一次可能就通过"的心态继续投入时间

## 九、确认状态

1. ADR 编号：**ADR-016**（确认，不与已预留的 ADR-015《State Interface Contract》冲突）
2. 总工作量估计：**7～10 个 session**（确认，原估计 5-8，因新增前置检查环节而上调）
3. 存档策略：**独立存档**（本 ADR 涉及生产数据写入与不可逆操作，按工作惯例暂不并入 `planning/DESIGN_NOTES.md`；待阶段四 Full Validation 通过、Rollback Criteria 从未被触发，视为风险基本消失后，再正式合并，合并时补充过程描述）

---

## 十、暂缓事项（2026-07-29 讨论，明确记录"已知会做，但等触发条件出现再做"，防止过早抽象）

以下几项来自一次外部反馈讨论，方向认可，但判断当前没有真实使用压力驱动，强行现在实施属于"看起来严谨但未经验证必要性"的过度设计，明确记录，等触发条件出现再启动：

- **Feature Flag → Strategy 模式**：目前只有 legacy/new 两条路径，`if/else` 足够清晰；等真的出现第三条路径（如 `experiment`）时再重构成策略模式，不需要现在为两个选项引入额外抽象层。
- **`PromotionPolicy.explain()`**：目前没有任何消费者（Dashboard/Tutor 都未实现），等真的有具体场景需要向人解释"为什么判定 stable"时再加，现在加是没有真实使用反馈的猜测式设计。
- **ADR-017 Replay Framework**：`verification_runner.py` 已经是一个 replay runner 的雏形（只是目前只喂合成数据）。不新开 ADR 凭空设计框架；等真的出现 `REAL_Student_102` 这类真实学生案例、且现有 runner 明显不够用时，再把它演化升级为正式框架。
- **Cognitive Metrics / Learning Analytics**（平均恢复时间、Promotion Delay、False Stable 比例等）：需要真实学生规模支撑，目前学生数量不足，等数据积累到有统计意义再启动。

判断原则（供未来同类讨论参考）：**让"普遍性的原则"从真实遇到的具体问题里长出来，而不是提前搭好框架等着往里填。** FREEZE-01 的存档惯例、本 ADR 的 Rollback Criteria、Stage 3.5 观测期，都是先遇到真实问题、再提炼出的通用做法，这样的"普遍性"经得起检验；反过来先建好框架等真实压力出现，容易做的是"看起来完备"而非"确实必要"，且对单人开发的时间预算不划算。

---

## 十一、ADR Evolution（记录本 ADR 自身的演进过程，2026-07-29 起正式采用此章节格式）

**v1（2026-07-27）**：初稿，五阶段拆分 + 风险清单。为什么这样设计：把 ADR-012/013 从沙盒验证推进到生产运行，需要一份可执行的落地计划，而不只是"设计已经定了"这句话。

**v2（2026-07-28）**：发现 `PromotionPolicy` 隐性有状态问题（每次无状态重新实例化会导致窗口/锁存机制完全失效）。为什么改：这是比接口类型不匹配严重得多的架构缺口，若不在阶段二解决，后续所有验证都建立在一个错误的地基上。新增 `promotion_state` 独立列方案、`export_state()`/`rehydrate()` 契约。

**v3（2026-07-28，同日）**：阶段二编码过程中，发现 `fetch_evidence_history()` 从未被实现，导致 `dan_state` 自生产上线以来从未被真实数据更新过，问题被 `except Exception` 静默吞掉。为什么改：这是真实生产 bug，不是设计缺口，用"学生2"账号实测确认后当场修复并验证。Lessons Learned：设计阶段的严谨追问（"这条路径到底有没有真的跑起来过"）本身就是最好的观测触发器，不需要额外的监控系统才能发现问题。

**v4（2026-07-29）**：采纳外部反馈中的四项低成本改进（Versioned State、Stage 3.5 自然观测期、阶段三字段处理分支明确化、轻量级可观测性），同时明确记录五项暂缓事项，避免过早抽象。Lessons Learned：不是所有"方向正确"的建议都该立刻实施，成本和触发条件的判断同样重要。

**v5（2026-07-29，同日）**：撤销 v4 里关于阶段三的两处错误决定。为什么改：①阶段三最初假设 `recovery_tick`/`locked_world` 是 `dan_state` 的数据库列，据此设计了一段字段核实 SQL，但看过 `SYN_E_RECOVERY.json` fixture 原文后确认这两个字段是 fixture 期望值，从来不是数据库列，前置检查从一开始就问错了问题；②阶段三计划把 `verification_runner.py` 改名为 `clvs_sandbox_runner.py`，但这个决定是在不知道 `theory/THEORY_CHANGELOG.md` 2026-07-16 已有明确记录（"根目录 verification_runner.py：不受影响，保留，不需要删除或修改"）的情况下做出的，与既有历史决定冲突，已撤销。Lessons Learned：这次纠错的触发点，是执行全仓库引用检查脚本时意外搜出了历史 changelog 里的相关记录——**验证执行环节（全仓库搜索）本身发现了设计环节的错误假设**，这是"观察触发修正"的另一个真实案例，说明验证步骤的价值不只是确认代码对不对，也能反向暴露决策本身站不站得住脚。

**v6（2026-07-29，同日）**：阶段三代码推送后，实际在真实 Supabase 上跑通 `verification_runner.py`，`SYN_E_RECOVERY` 的两项新断言（`recovery_tick`/`final_locked_world`）精确通过，阶段三验收完成。为什么记录：这是 `check_recovery_tick()` 判定算法首次在真实生产依赖（真实 `run_pipeline()` 调用链、真实 Supabase 读写）下验证，此前只做过合成数据单元测试；结果与理论推导值完全一致，确认阶段三改动正确。详见 `theory/THEORY_CHANGELOG.md` 同日条目。
