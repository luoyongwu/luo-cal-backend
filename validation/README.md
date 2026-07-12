# Luo-cal CLVS 验证体系（Cognitive Layer Verification Suite）

本目录不是普通意义上的单元测试集合，而是一个**理论验证集（Theory Validation Suite）**。
它验证的不只是代码有没有 bug，而是 Luo-cal 整个 PCSA（Persistent Cognitive State
Architecture）理论链条——Ontology → Bayesian Inference → Persistent Memory →
Cognitive State——是否在实现层面真正成立。

## 三层验证体系

目录结构按验证性质分为三类，分别回答三个完全不同的科学问题：

### 1. Correctness Validation（正确性验证）
**回答的问题：理论是否成立？**

位置：`validation/student_archetypes/`

用一组"合成学生原型（Student Archetype）"——而非零散的单元测试用例——去验证
Luo-cal 认知推断理论的核心命题是否在系统中真正实现。每个原型对应一条独立的
理论主张（validation_claim）：

- **Student A（Representation Dominant）**：单一认知机制在无噪声、重复证据下，
  能否收敛到对应认知世界的稳定高置信度后验分布。
- **Student B（Flow Thinker）**：不同认知世界是否具有各自独立的收敛路径。
- **Student C（Mechanism Interweaving）**：跨世界证据是否会污染无关世界；
  同一世界内的不同机制是否可被分别追踪，而非相互吞并或覆盖。

每个 fixture 只绑定理论关系（世界排名、置信度区间、数值健康性），不绑定
具体数字答案——这样未来调整超参数（如 Dirichlet 先验 α₀）不会导致测试集
大面积误报，同时保护了理论不变量本身的刚性。

### 2. Regression Validation（回归验证）
**回答的问题：后续修改有没有破坏理论？**

位置：`validation/regression/`

不同于 Correctness Validation 的探索性质，这一类用例验证的是**已经明确定义、
不容妥协的架构边界**是否被未来的代码改动意外破坏。

- **ADR008_reflection.json**：验证 ADR-008 定义的边界——Meta Feedback
  （REFLECTION 信号）永远不参与认知推断。用"3条真实信号 vs 100条 REFLECTION"
  的悬殊比例放大问题，并用位级快照比对（`math.isclose(..., abs_tol=1e-9)`）
  逐世界断言 REFLECTION 信号不产生任何非零梯度贡献；同时对 `evidence_used`、
  `effective_sample_size` 等元数据字段做同等严格的快照对比，防止"数值正确
  但元数据被污染"这类隐蔽缺陷。

这类用例应被纳入 CI 例行回归：任何改动 `BayesianAggregator` 或相关管道的
代码，第一件事就应该跑一遍这里的用例。

### 3. Robustness Validation（鲁棒性验证）
**回答的问题：参数变化、压力增大时系统是否仍然可靠？**

位置：`validation/robustness/`（规划中，尚未建立）

验证系统在极端条件、参数扫描、大规模压力下的行为边界，包括但不限于：

- **高熵/低信噪比压力测试**：信号在多个世界间高频交替时，聚合器是否保持
  数值稳定（不下溢、不 NaN、不震荡），这部分内容目前暂时合并在
  `student_archetypes/student_D_uncertain.json` 中，**待后续拆分**——
  该 fixture 目前混合了两类不同性质的断言：数值稳定性检查（Robustness）
  与"保守判断而非虚假收敛"（Correctness，属于贝叶斯推断诚实性的理论主张）。
  未来应将数值稳定性部分独立迁移至此目录，与更大规模的压力测试
  （如1000/10000条随机信号）合并。
- **Detector 置信度敏感性**（Student G，规划中）：验证信号置信度字段
  （`confidence_i`，当前默认1.0，接口已预留）接入后系统的行为。
- **Dirichlet 先验敏感性**（Student H，规划中）：固定信号序列，扫描
  `alpha_prior`（如0.1 vs 2.0），验证早期收敛速度的变化是否符合理论预期，
  可直接用于论文中的 sensitivity curve。

## 尚未覆盖的已知缺口

- **AWM 端缺失纯净原型**：当前 `ONTOLOGY` 映射下没有任何信号直接映射到
  AWM，因此不存在类似 Student A/B 那样的"纯净 AWM 收敛"用例。这是当前
  Signal→Mechanism→World 映射覆盖范围的如实反映，非测试设计遗漏。
- **State Evolution（状态演化）未覆盖**：现有 A-D 均为静态证据流，未验证
  学生认知状态随时间演化（如从 RepresentationShift 主导逐渐过渡到
  FlowReasoning 主导）时，系统是否表现出平滑迁移而非瞬间跳变。这项验证
  依赖于对 `inference_pipeline.py` 中阻尼/惯性机制实际实现的核实，
  在核实完成前不设计具体 fixture，避免基于未经验证的假设构建测试用例。

## 术语约定

- `world_weight`：单个认知世界（RWM/FWM/AWM）在后验分布中的分量。
- `confidence`：贝叶斯聚合器复合置信度公式（evidence_factor ×
  concentration_factor）产出的标量，代表系统对当前整体状态估计的把握程度。
  与 `world_weight` 是两个不同层面的量，命名严格区分，避免混淆
  （参见 `BAYESIAN_AGGREGATOR_SPEC_v0.2.md`）。
- `validation_claim`：每个 fixture 对应的理论主张，采用可直接引用于论文的
  英中双语表述，替代早期版本中偏工程化的 `Requirement N` 编号命名。
