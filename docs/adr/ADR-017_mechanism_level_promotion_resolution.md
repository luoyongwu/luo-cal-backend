# ADR-017: Mechanism-Level Promotion Resolution

**Status:** Accepted（§6 复合 world schema 已决定，可进入实现阶段）
**Date:** 2026-07-31
**Depends on:** ADR-012 (Diagnosis-Promotion Decoupling), ADR-013 (Diagnostic State
Dual-Timescale Layering), ADR-016 (Production Pipeline Integration / Route A)

---

## 1. Context

ADR-012 established `PromotionPolicy` as an independent controller consuming
only `world_weights`（RWM/FWM/AWM 三元分布）来判断 Stage
（fragile/emerging/stable）。`_resolve_dominant_world()` 的判定条件是：

- top-1 world 权重与 top-2 的差距 ≥ `margin`（0.15）
- top-1 world 权重本身 ≥ `theta`（0.55）

两者皆满足才算该轮"resolved"到某个具体 world；否则记为 `UNRESOLVED`，
不计入任何 world 的持续性窗口计数。

`world_weights` 由 `BayesianAggregator._aggregate()` 通过两步计算得出：
先算 `mechanism_attribution`（RepresentationShift / SemanticIntegrity /
FlowReasoning / StructuralReasoning 四元分布），再用
`MECHANISM_TO_WORLD_DEFAULT` 把 mechanism 分布投影到 world 分布：

```python
MECHANISM_TO_WORLD_DEFAULT = {
    "RepresentationShift": {"RWM": 1.0},
    "SemanticIntegrity":   {"RWM": 1.0},
    "FlowReasoning":       {"FWM": 1.0},
    "StructuralReasoning": {"FWM": 0.5, "AWM": 0.5},
}
```

前三个 mechanism 都是 100% 单一映射到某个 world——这一步投影不损失
任何信息。唯独 `StructuralReasoning` 是 50/50 split 到 FWM 和 AWM。

## 2. Problem Statement

2026-07-31 十位合成学生模拟（`SIM_03_IVT_MVT_PURE` / `SIM_04_WASHER_PURE`，
分别连续 5 轮纯净 `IVT_MVT_CONFUSION` / `WASHER_TRAP`，二者均 100%
归因于 `StructuralReasoning`）暴露：即使证据 100% 纯净、连续 5 轮完全
一致，FWM/AWM 权重也只能收敛到约 0.464 / 0.393（差距 0.071），
**结构性地小于 Margin=0.15**。`_resolve_dominant_world()` 因此每轮都
判 `UNRESOLVED`，`PromotionPolicy` 的持续性窗口永远填不出一致计数，
`stage` 永久卡在 `fragile`——无论证据流跑多少轮、多么纯净都不会改变。

这不是数据噪声或证据不足导致的合理"诊断不确定"，而是
`MECHANISM_TO_WORLD_DEFAULT` 的 50/50 split 在 world 层制造了一个
**数学上永远无法跨越 Margin 门槛的结构性死锁**。

该问题违反两条设计原则：

**2.1 混淆了"诊断确定性"与"认知健康度"**

ADR-012/013 中 `stage=stable` 的语义是"系统已经以高置信度、持续稳定地
抓住了该学生当前的主导心智模型/错误机制"——这个语义不预设该机制是否
"健康"，只断言诊断本身是否确定。当前实现把"mechanism 层其实已经百分百
确定"这一事实，错误地传导成了"world 层无法确定"，导致系统即使在
mechanism 层已经握有教科书级别的确定性证据时，也无法在诊断报告里给出
"stable"结论。

**2.2 打破了 Ontology 机制间的"地位等价性"（Mechanism Parity）**

犯 `RepresentationShift`（100% 独占 RWM）的学生 5 轮纯净证据即可被诊断
为 `stable/RWM`；犯 `StructuralReasoning`（FWM/AWM 均分）的学生哪怕
表现同样纯净，却被永久判定为 `fragile`。四个 mechanism 在 Root Cause
Ontology 里本应是并列、地位对等的诊断对象，但当前实现使其中一个因为
纯粹的映射结构（而非该错误本身固有的模糊性）而永久处于"无法诊断"状态。
这会在未来 Dashboard 统计与 SCL 教学决策上产生系统性偏见：结构性错误
的学生在统计图表里会永远呈现"无规律瞎猜"的假象。

## 3. Root Cause（精确定位）

病灶不在于"StructuralReasoning 本质上具有更高不确定性"这个直觉判断
本身，而在于：**Promotion 层目前只在 mechanism→world 投影之后（一个
对 StructuralReasoning 而言有损的坐标系）里做持续性判定，用同一把
world-level margin 尺子去衡量信息密度不对等的四个 mechanism。**
RepresentationShift/SemanticIntegrity/FlowReasoning 的 mechanism→world
投影无损，所以 mechanism 层的确定性能完整传导到 world 层；
StructuralReasoning 的投影有损，确定性在这一步被打散，永远无法在
world 层重新聚合出足够的 margin。

诊断确定性理应优先在信息无损的层级（mechanism 层）判定，再决定如何在
world 层呈现，而不是把判定门槛设在信息已经损失之后的层级。

## 4. Considered Options

**Option A：调低 world-level margin 或 theta**
拒绝：会削弱 RepresentationShift/SemanticIntegrity/FlowReasoning 三个
无损映射机制的判定严格度，用一个全局参数去修补一个只发生在特定
mechanism 上的结构性问题，治标不治本，且会引入新的误判风险（更容易
在证据混乱时误报 stable）。

**Option B：修改 MECHANISM_TO_WORLD_DEFAULT，取消 StructuralReasoning
的 50/50 split，强制归到单一 world**
拒绝：这是对 Root Cause Ontology 理论本身的篡改——StructuralReasoning
同时关联长流程推理（FWM）和边界/环境认知（AWM）是这个 mechanism
在理论设计阶段就已确立的双重属性，不是实现细节，不应为了修一个
Promotion 层的工程问题而扭曲上游理论。

**Option C：Promotion 层新增 mechanism 级别的并行判定通道
（本 ADR 采纳）**
`PromotionPolicy.update()` 除接收 `world_weights`，同时接收
`mechanism_attribution`（`aggregate_dual_scale()` 的 `recent`
WeightVector 中已经计算但此前未下传的字段）。新增
`_resolve_dominant_mechanism()`，用同样的 Margin/Theta 逻辑作用于
mechanism 的四元分布。晋升判定改为：**world 层解出 OR mechanism 层
解出，二者满足其一即可判定 stable**。

## 5. Decision

采纳 Option C。理由：

- 不改动上游 Ontology 理论（StructuralReasoning 的双重归因保持不变）
- 不削弱其余三个无损映射 mechanism 的判定严格度（world-level 判定路径
  完全保留，作为 fast path）
- 直接解决 Mechanism Parity 问题：四个 mechanism 现在都有平等的机会
  在证据纯净时被判定为"确定"，无论其 mechanism→world 投影是否有损

## 6. Decision on `locked_world` Schema（最终决定，2026-07-31 线下讨论定稿）

三个初始方案（存 mechanism 名 / 新增 `locked_mechanism` 独立字段 /
复合 world）、线下讨论提出的"方案 4：双层锁定"（扩展 `locked_world`
枚举值为 `"STRUCTURAL"`）均已评估并否决（否决理由见下方"被否决方案"）。

**最终采纳：`locked_world`（单值，取值域完全不变）+ `locked_worlds`
（复数，代数封闭）+ `locked_mechanism`（纯溯源信息，不参与判定逻辑）
三字段并存。**

```json
{
  "stage": "stable",

  // 单一 world 锁定场景（RepresentationShift/SemanticIntegrity/FlowReasoning）：
  "locked_world": "RWM",
  "locked_worlds": ["RWM"],
  "locked_mechanism": "RepresentationShift",

  // 复合 world 锁定场景（StructuralReasoning）：
  // "locked_world": null,
  // "locked_worlds": ["FWM", "AWM"],
  // "locked_mechanism": "StructuralReasoning"
}
```

**关键设计点（相对于当天较早版本的修正）**：单一 world 锁定时，
`locked_world` 与 `locked_worlds` **同时写入、值语义完全一致**
（`locked_world="RWM"` 时 `locked_worlds=["RWM"]`），而不是只写
`locked_world`、留 `locked_worlds` 为空。这样"旧下游零感知"不再只是
"理论上不受影响"，而是字面意义上——任何只读 `locked_world` 的既有
消费方（验证器、未来 API）读到的值和迁移前完全一样，不需要额外判断
"这次是不是复合锁定"。只有复合锁定场景（目前仅 `StructuralReasoning`）
才会出现 `locked_world=None` 且 `locked_worlds` 长度大于 1 的情况，
这也是唯一需要新下游逻辑介入的场景。

**`locked_mechanism` 重新纳入，但降级为纯溯源字段**：早期草稿评估
"新增独立字段"方案时，否决理由是"下游若只读 `locked_world` 会漏掉
这类学生"（Consumption Loss）。这个顾虑在当前设计里已经被
`locked_worlds` 的自解释性化解——下游不需要认识 `StructuralReasoning`
这个 Ontology 内部术语，只需读 `locked_worlds` 就能拿到判定结果。
在此前提下，`locked_mechanism` 不再是"判定结果的唯一载体"，而是单纯
记录"这次锁定的根源 mechanism 是什么"，用于 debug、审计、以及未来
Dashboard 展示人类可读文案（复用 `main.py::ROOT_CAUSE_LABELS`）——
它加不加都不影响任何判定逻辑的正确性，纯粹是溯源信息的富化，没有
下游必须处理它的强制性。

判定规则：

- Mechanism 层解出、映射到单一 world（`RepresentationShift`/
  `SemanticIntegrity`/`FlowReasoning`）：`locked_world` 与
  `locked_worlds`（长度 1 的列表）同时写入相同的 world；
  `locked_mechanism` 写入该 mechanism 名
- Mechanism 层解出、映射到多个 world（当前仅 `StructuralReasoning`
  → `{FWM, AWM}`）：`locked_world` 置 `None`；`locked_worlds` 写入
  这些 world 的列表；`locked_mechanism` 写入该 mechanism 名
- World 层解出但 mechanism 层未解出（理论上不应发生，因为 world
  层解出是 mechanism 层信息的下游投影，但保留此分支作为防御性设计）：
  `locked_world`/`locked_worlds` 按 world 层结果写入，`locked_mechanism`
  置 `None`，不臆造溯源信息
- 下游读取优先级：只关心是否复合锁定 → 看 `locked_worlds` 长度是否
  大于 1；只需要兼容旧逻辑 → 继续读 `locked_world`，行为不变；需要
  溯源/人类可读展示 → 读 `locked_mechanism`

**被否决方案汇总**：
- 方案 1（`locked_world` 直接存 mechanism 名）：破坏 `locked_world`
  的强类型语义屏障
- 方案"双层锁定"（`locked_world` 扩展枚举值为 `"STRUCTURAL"`）：与
  方案 1 犯同一类错误（塞入非 world 的 sentinel），且需要 DB
  CHECK/ENUM migration，Postgres ENUM 加值容易删值几乎不可能，是
  永久性历史包袱；未来每新增一个复合映射关系都需要新造一个 sentinel +
  一次新迁移，`locked_worlds` 数组的代数封闭性完全免疫这个问题
- 仅新增独立 `locked_mechanism`（不带 `locked_worlds`）：造成
  Consumption Loss，已通过引入 `locked_worlds` 化解，`locked_mechanism`
  降级为溯源字段后重新纳入设计

**§4 Option C 描述修正**：原描述"world 层解出 OR mechanism 层解出，
二者满足其一即可判定 stable"需要补充区分——在单一 world 映射的
mechanism 上，mechanism 层解出与 world 层解出等价，行为不变；在
`StructuralReasoning` 这类多重映射 mechanism 上，mechanism 层解出应
触发 `locked_world=None` + `locked_worlds=["FWM","AWM"]` +
`locked_mechanism="StructuralReasoning"` 三字段联动写入，而非试图在
单一字段里塞入非 world 信息。

**新增 Canonical Profile**：需要新增一个 `StructuralReasoning` 纯净
场景的合成学生（类似本次十位模拟中 `SIM_03`/`SIM_04` 的证据模式），
纳入 `validation/student_archetypes/`，作为本次修复的回归哨兵，
`expected_output` 中应包含 `locked_world: null`、
`locked_worlds: ["FWM", "AWM"]`、`locked_mechanism: "StructuralReasoning"`
三项断言。

## 7. Consequences

**正面：**
- 修复 Mechanism Parity 违规，四个 mechanism 在诊断确定性判定上重新
  平等
- `stage=stable` 的语义回归其本意（诊断确定性），不再与
  mechanism→world 投影是否有损耦合
- 为未来 Ontology 新增更多具有非单一 world 映射的 mechanism（若有）
  预留了正确的架构处理路径，而不必每次都单独打补丁

**代价 / 风险：**
- `PromotionPolicy` 需要维护两套并行窗口状态（world 级 + mechanism
  级），`export_state()`/`rehydrate()` 的持久化 schema 需要扩展，
  产生新的向后兼容问题（历史 `promotion_state` JSONB 数据不含
  mechanism 级窗口，rehydrate 时需要能优雅处理缺失字段）
- 需要新增 Canonical Profile（例如纯净 `IVT_MVT_CONFUSION`/
  `WASHER_TRAP` 学生）作为本次修复的回归哨兵，纳入
  `validation/student_archetypes/`，防止未来再次退化

## 8. Rollout Plan

参照 ADR-016 Route A 的 feature-flag 分阶段模式：

1. `PromotionPolicy` 新增 mechanism 级窗口机制，但先不接入判定逻辑
   （纯新增，不改变现有行为）
2. 补充针对 `SIM_03`/`SIM_04` 场景的 Canonical Profile 到
   `validation/student_archetypes/`，作为本次要修复问题的回归基线
3. 实现三字段（`locked_world`/`locked_worlds`/`locked_mechanism`）的
   写入与读取逻辑：
   - `PromotionPolicy._decide_stage()` 按 §6 判定规则联动写入三字段
     （单一 world 锁定时 `locked_world`/`locked_worlds` 值语义一致；
     复合锁定时 `locked_world=None`）
   - `export_state()`/`rehydrate()` 扩展序列化全部三字段；历史
     `promotion_state` JSONB 数据缺失新字段时，`rehydrate()` 置为
     `None`，不影响现有行为
   - `update_global_promotion_state()` 的返回值契约新增
     `locked_worlds`/`locked_mechanism`
   - `check_final_locked_world()` 扩展：fixture 期望单一 world 时
     继续走 `locked_world` 断言（值不变，验证零改动）；期望复合 world
     （如新增的 `StructuralReasoning` 专用 fixture）时新增
     `locked_worlds`/`locked_mechanism` 断言
4. Shadow Run：新逻辑与旧逻辑并行跑，对比历史合成学生（A-E 五组 +
   本次十位模拟 + 新增回归 fixture），确认无 world-level 判定路径的
   回归
5. 正式切换，存档进 `THEORY_CHANGELOG.md`
