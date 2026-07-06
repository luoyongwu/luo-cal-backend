# Evidence Aggregator — 贝叶斯设计规范 v0.2
## 已确认设计，待实现

**状态变更：** v0.1 是"供审阅，暂不实现"的草案；本版所有待定项已通过三方审阅（Claude 草案 → DeepSeek 评审 → Gemini 数学复核 → 交叉确认）收敛，可以直接作为下次实现的规格书。

---

## 1. 设计原则（v0.1 不变，三方一致确认保留）

两段显式矩阵，不是黑箱：

```
Evidence (signal, confidence)
      │
      ▼
矩阵 1：Signal → Mechanism 归因      ← 对应 Ontology §3 证据映射
      ▼
mechanism_attribution（后验均值向量，真实中间变量）
      │
      ▼
矩阵 2：Mechanism → World 映射（可条件于 signal）← 对应 Ontology §4 推理映射
      ▼
world_weights
```

**这一层设计以后价值最高的一句话（三方讨论中最值得记住的一条）：** Mechanism 不是为了 Explainability 事后编出来的解释，是计算过程本身真实存在的中间变量。多数"可解释 AI"系统是先出答案、再编理由；这里理由本身就是计算过程。这条原则今后要写进论文。

认知惯性阻尼（N≥5、时间衰减）完全不在这一层——那是 `CognitiveInertiaDamper` 的职责（ADR-003）。

---

## 2. 矩阵 1：Signal → Mechanism（P(mechanism | signal)）—— 已定稿

| Signal | RepresentationShift | SemanticIntegrity | FlowReasoning | StructuralReasoning | 来源 |
|---|---|---|---|---|---|
| BOUNDS_TRAP | **1.0** | — | — | — | Ontology §3，硬映射 |
| PRE_SUBSTITUTION | **1.0** | — | — | — | Ontology §3，硬映射 |
| CHAIN_FRACTURE | — | **0.7** | **0.3** | — | Ontology §4 给出的 v2.0 示例数值，逐位复现（见 §6 验证） |
| IVT_MVT_CONFUSION | — | — | — | **1.0** | Ontology §3，硬映射 |
| WASHER_TRAP | — | — | — | **1.0** | Ontology §3，硬映射 |
| EWM_B1C | — | — | **1.0** | — | Ontology §3，硬映射 |
| ABSOLUTE_VALUE | **0.5** | **0.5** | — | — | **最大无知原则（Maximum Ignorance Principle）**：Ontology 只做定性区分，未给定量依据，均分是唯一诚实的选择 |

---

## 3. 矩阵 2：Mechanism → World，条件于 Signal —— 已定稿

不再是纯粹的两维矩阵 `P(world|mechanism)`，升级为 `P(world|mechanism, signal)` 的条件贝叶斯网络——但结构仍然是"默认基线 + 显式覆盖表"，仍然可打印、可审计，没有破坏两段式架构：

```yaml
# 默认基线（当没有 signal_override 时使用）
mechanism_to_world_default:
  RepresentationShift: {RWM: 1.0}
  SemanticIntegrity:   {RWM: 1.0}
  FlowReasoning:        {FWM: 1.0}
  StructuralReasoning:  {FWM: 0.5, AWM: 0.5}   # 最大无知，见下方说明

# 仅当 mechanism = StructuralReasoning 时的信号级覆盖
signal_overrides:
  IVT_MVT_CONFUSION: {FWM: 0.5, AWM: 0.5}     # 最大无知，一致执行
  WASHER_TRAP:       {FWM: 0.5, AWM: 0.5}     # 最大无知，一致执行
```

**关键决策（本版与 v0.1 的最大差异）：** 最初提议过 `IVT_MVT_CONFUSION → {FWM:0.7, AWM:0.3}`、`WASHER_TRAP → {FWM:0.2, AWM:0.8}` 这类基于错误语义直觉的分配，但审阅中发现这和 `ABSOLUTE_VALUE` 用"最大无知原则"的理由不一致——两处都是"Ontology 没给定量依据、凭直觉给数字"，却一个被认定为"不诚实"、另一个被认定为"更准确"，这个双重标准经不起审稿人追问（"旋转体积分的空间直觉占 80% 的证据在哪里？"）。

**最终决定：一致执行最大无知原则，所有未实证的分割点全部 0.5/0.5。** `signal_overrides` 这张表在架构上保留（为将来 telemetry 数据反推真实比例留好接口），但 v0.2 版本里所有条目的数值都等于默认基线——即当前版本这张表实质上是"占位声明",不影响任何计算结果，但明确了"以后从哪里改"。

---

## 4. 聚合公式 —— 已定稿

### 4.1 软计数：引入 Detector 置信度加权

```
soft_counts[m] = Σ_i  confidence_i × P(mechanism=m | signal_i)
```

`confidence_i` 是每条证据自带的检测置信度（例如 Claude/DeepSeek 判定某个 EWM 信号时的把握程度）。这一项目前**没有数据源可用**——现有 SCL 检测是二元的（打标签或不打），`cognitive_signals` 表也没有存置信度分数的字段。

**实现方式：** 接口层面接收 `confidence: float = 1.0`，现在写好接口，但底层暂时"空转"——所有证据的 `confidence_i` 目前恒为 1.0，直到未来 SCL 提示词升级为同时输出把握度分数、`cognitive_signals` 加一列存它为止。这样以后升级检测端时，聚合器这一层不需要改代码，只需要真实数据流入这个已经存在的接口。

### 4.2 Dirichlet 后验（先验可配置）

```
α[m] = α₀ + soft_counts[m]
mechanism_attribution[m] = α[m] / Σ_m' α[m']
```

`α₀` 不写死在代码里，进 `config.yaml`：

```yaml
aggregator:
  alpha_prior: 0.5      # 先验伪计数，越小系统对早期证据反应越快
  window_mode: "recent_n"    # 或 "time_window"
  window_size_n: 50          # window_mode=recent_n 时：只取最近 N 条
  # window_days: 90          # window_mode=time_window 时：只取最近 T 天
```

配置化的直接价值：以后可以用 Colab 跑 α₀ = 0.1 到 2.0 的敏感度分析，画出"系统对早期信号的谨慎度曲线"，是一篇 Architecture Paper 里很自然的图。

### 4.3 World Weights 传播（矩阵2）

```
world_weights[w] = Σ_m  mechanism_attribution[m] × P(world=w | mechanism=m, signal)
```

### 4.4 置信度公式 —— 本版修复了一处真实数学漏洞

**v0.1 的纯熵公式有 bug，不能用：** `confidence = 1 − H/H_max` 只看后验分布的"方向是否一致"，不看"到底攒了多少证据"。结果是：**只有一条证据、且这条证据 100% 指向单一世界时，熵为 0，算出来置信度 = 1.0**——用一次喷嚏就 100% 确诊某种罕见病，这是错的，而且是比 v0.1 更早那版"只看数量不看方向"更隐蔽的错误。

**修复：两个独立因子相乘，缺一不可：**

```
evidence_factor      = 1 − 1 / (1 + effective_sample_size)   # 证据攒得够不够多
concentration_factor = 1 − H(world_weights) / H_max            # 证据方向一不一致
                        其中 H = −Σ_w p_w·ln(p_w)，H_max = ln(3)

confidence = evidence_factor × concentration_factor
```

两个极端验证：
- **一条干净证据**（N=1，100% 指向单一世界）：`concentration_factor` 接近 1，但 `evidence_factor` 因样本太小而很低（比如 0.3）→ 相乘后置信度被正确压低。Dashboard 可以诚实地说"方向清晰，但样本太少，暂不确定"。
- **十条矛盾证据**（在三个世界反复横跳）：`evidence_factor` 接近 1，但 `concentration_factor` 因后验接近均匀分布而趋近 0 → 相乘后置信度同样被正确压低。

这个复合公式是本轮审阅里唯一真正的数学修正，其余都是工程增强。

---

## 5. WeightVector 最终字段（已在 `pcsa_interfaces.py` 落地，向后兼容）

```python
world_weights: Dict[str, float]
mechanism_attribution: Dict[str, float]
confidence: float
aggregator_version: str = "unversioned"
evidence_used: int = 0                 # 窗口内实际参与聚合的证据条数
effective_sample_size: float = 0.0     # Σ confidence_i，等效证据量（区别于原始条数）
entropy: float = 0.0                   # world_weights 的香农熵原始值（非归一化），供 Dashboard 直接引用
```

`evidence_used` 和 `effective_sample_size` 分开保留的原因：一旦 detector 置信度真正启用，两者会出现差异（比如 10 条证据但平均置信度 0.7，`evidence_used=10` 而 `effective_sample_size=7`），Dashboard 可以同时展示"证据量"和"证据质量"两个维度，而不是糅成一个数字。

这三个新字段已经加进 `pcsa_interfaces.py` 的 `WeightVector` 定义和理论边界校验，且已验证向后兼容——不传这几个字段的旧实现（如 `DummyAggregator`）使用默认值，依然能通过校验。

---

## 6. 验证：矩阵1×矩阵2 精确复现 Ontology 给定的唯一数值示例

Ontology §4 原文：`CHAIN_FRACTURE → SemanticIntegrity → {RWM: 0.7, FWM: 0.3}`

假设学生只有一条 `CHAIN_FRACTURE` 证据（confidence=1.0，忽略先验简化演示）：

- 矩阵1查表：`CHAIN_FRACTURE → {SemanticIntegrity: 0.7, FlowReasoning: 0.3}`
- `mechanism_attribution ≈ {SemanticIntegrity: 0.7, FlowReasoning: 0.3}`
- 矩阵2传播：`SemanticIntegrity→RWM(1.0)`、`FlowReasoning→FWM(1.0)`
- `world_weights = 0.7×{RWM:1} + 0.3×{FWM:1} = {RWM: 0.7, FWM: 0.3}` ✅ 与原文精确吻合

这个验证在 v0.2 里依然成立——本轮的所有修改都没有触碰矩阵1/矩阵2的核心机制，只是修了置信度公式、加了信号置信度加权接口、把先验和窗口做成配置项。

---

## 7. 性能防线：时间/数量窗口（新增，v0.1 未覆盖）

**问题：** 如果 Aggregator 每次都扫描学生的全部历史证据，几年后单个学生可能积累上万条信号，性能会持续下降；而且十年前的一次错误，不应该继续影响今天的诊断。

**决定：** Aggregator 不做全表扫描，只读取"最近 N 条"或"最近 T 天"（二选一，配置驱动，见 §4.2 的 `config.yaml`）。真正的长期记忆衰减（旧证据权重指数衰减）依然完全是 `CognitiveInertiaDamper` 的职责——这里只是限制"参与本次计算的原始数据量"，不做任何加权衰减，分工边界不变。

实现建议：SQL 查询层面直接 `ORDER BY timestamp DESC LIMIT :window_size_n`（或加时间条件），不在 Python 里 fetch 全表再截断。

---

## 8. 待实现清单（下次编码时的具体任务）

1. 在 `inference_pipeline.py` 里新增 `BayesianAggregator(EvidenceAggregator)`，实现矩阵1、矩阵2、Dirichlet 聚合、复合置信度公式
2. 新增 `config.yaml`（或等效配置读取方式），至少包含 `alpha_prior`、`window_mode`、`window_size_n`/`window_days`
3. `fetch_evidence_history()` 改造以支持窗口参数（当前是全量拉取，需要加 `LIMIT`/时间过滤）
4. `Evidence` 数据类需要加一个 `confidence: float = 1.0` 字段（当前没有，见 §4.1）
5. `DummyAggregator` 可以保留作为对照基线（A/B 测试或回归测试用），不必删除

`pcsa_interfaces.py` 的字段扩展已经提前完成（见 §5），不在下次待办里。

---

## 9. 决策记录索引

本次三方审阅中两处需要拍板的分歧已收敛，完整推理过程记录于 `planning/DESIGN_NOTES.md` ADR-005：
- 置信度公式为什么必须是两个因子相乘，不能只用熵
- 为什么 `StructuralReasoning` 的信号级分割最终也回到 0.5/0.5，而不是采纳最初的直觉数字

---

## 10. 三方复核后的补充事项（第四轮审阅）

规格定稿后又收到一轮评审，指出三处"不是 bug，是 v1.1 可以考虑"的点。处理方式各不相同，记在这里避免以后忘记：

1. **`confidence` 不应被理解为 Probability。** `confidence=0.8` 不是"World 有 80% 概率是真的"，而是"系统对当前诊断稳定性的把握程度"，更准确的说法是 Diagnostic Confidence / Diagnostic Reliability。**决定：不改代码字段名**（接口刚冻结，改名成本此刻大于收益），但已在 `pcsa_interfaces.py` 的 `WeightVector` docstring 里把语义钉死，并且约定：论文和正式文档一律写"Diagnostic Confidence"，不裸写"Confidence"。

2. **Evidence factor 的饱和函数应该可配置。** 目前固定用 `1 − 1/(1+n)`（有理函数形式），未来不同学科可能需要不同的饱和速度（比如物理可能需要比微积分更多证据才能同等确信）。**决定：预留配置接口，不现在实现。** 未来 `config.yaml` 增加：
   ```yaml
   aggregator:
     evidence_growth:
       function: "rational"   # 或 "exponential": 1 - exp(-n/k)
       k: 1.0                  # exponential 模式下的尺度参数
   ```

3. **Aggregator 应该输出 `reasoning_trace`。** 这条被认为是三条里最有价值的一条——直接为 Phase 3 的 Evidence Trace 提供原始材料，不需要 Dashboard 自己反推计算过程。**决定：现在就加，不等 v1.1。** 已经加进 `pcsa_interfaces.py` 的 `WeightVector`（`reasoning_trace: Optional[List[dict]] = None`），采用和 `evidence_used`/`effective_sample_size`/`entropy` 完全相同的模式——可选字段、默认值、向后兼容，成本几乎为零。真正实现 `BayesianAggregator` 时，应该在计算过程中顺手把每一步的 Signal→Mechanism→World 具体数值记进这个字段，不要等实现完了再回头补。

**这一轮审阅最重要的一句判断，值得留在这里：** 项目已经从"Idea → 代码"的个人开发模式，变成了"Theory Freeze → Specification → Interface → Implementation → Experiment → Paper"的科研团队开发方式。这是过去一个月最大的变化，比任何一次具体的公式修正都重要——今天关于置信度公式、最大无知原则的每一次拍板，本质上都是这条链路本身在正常运转的证据，而不是链路运转的目的。
