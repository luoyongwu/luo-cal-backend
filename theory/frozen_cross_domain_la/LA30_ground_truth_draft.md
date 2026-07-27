<!--
冻结说明（FREEZE-01）
作用：LA-30 标准答案（Ground Truth）草案，Claude 基于 OMP v0.2 决策树对30个案例做的试拟 Primary/Secondary 机制标签，供未来独立分类者盲测结束后核对使用。
未决问题：
  1. 全部标签均为 Claude 试拟判断，需要项目负责人逐条复核，尤其是文件末尾标注"置信度中"的几条（RAW-02、12、19）。
  2. SemanticIntegrity 占比明显偏高（15/30），需要判断是真实反映线性代数学科特性，还是分类时的自我偏差（"不确定案例被无意识倒进更包容的类别"）——这是本文件自己主动标注的风险点，正式测试前必须解决，否则会污染后续统计。
  3. 标签分布统计里提到"StructuralReasoning 有一条与08重复计入需要核对"，这个计数矛盾本身也需要项目负责人重新点数确认。
状态：草稿，未经复审，禁止作为正式 Ground Truth 使用；分类者在完成 LA30_blind_pack_v2.md 全部分类之前不得查看本文件。
-->

# LA-30 · 标准答案文件（Ground Truth）v2

**严正声明**：本文件里的机制标签（Primary/Secondary）是 Claude 基于 OMP 决策树逻辑做的**试拟判断**，不是经过真人教学专家验证过的真值。在真正用于第一阶段 AI 盲测或第二阶段真人评分之前，这些标签必须经过项目负责人（或其他数学教学专家）逐条复核修正，才能升级为可信的 Ground Truth。目前的状态更准确的说法是"Claude 提议的参考答案草案"，不是"标准答案"。

**使用规则**：分类者（AI 或真人）在完成 `LA30_blind_pack_v2.md` 的全部分类之前，不得查看本文件。

---

**RAW-01**
- 导师观察：学生混淆了"客观实体本身"与"特定视角下的数字化表达"。他误以为实体的不变性等同于表达数字的不变性，参照基准发生转移时，没有把这种变化同步传播到数值表达上。
- Primary：RepresentationShift
- Secondary：无
- Claude 置信度：高

**RAW-02**
- 导师观察：学生把非对称的复合操作，套用了满足交换律的初等直觉，不理解先后顺序在这类复合中的本质差异。
- Primary：SemanticIntegrity（对"复合操作"这个概念本身的理解有误）
- Secondary：RepresentationShift（低置信度——也可以理解为把"顺序"当成纯粹的表达排布问题而非本质属性）
- Claude 置信度：中（这是审阅者们讨论时提到的"多机制共存"典型案例，建议真人评分者重点关注这条的分歧率）

**RAW-03**
- 导师观察：学生意识到核心变量需要切换表达方式，但在后续长流程中未能保持全局一致性，下游计算混用了新旧两种表达方式的数据。
- Primary：RepresentationShift
- Secondary：无
- Claude 置信度：高

**RAW-04**
- 导师观察：整体方法论框架正确，但在微观执行层发生局部遗漏，导致操作完整性断裂。
- Primary：FlowReasoning
- Secondary：无
- Claude 置信度：高

**RAW-05**
- 导师观察：学生局部计算正确，但未能把局部结果升级为对整体结构关系的约束，忽略了守恒关系，产生了不必要的计算冗余。
- Primary：StructuralReasoning
- Secondary：无
- Claude 置信度：高

**RAW-06**
- 导师观察：学生混淆了"表达方式（影子）"与"被表达的对象本身（本体）"，认为表达方式的改写等同于客观性质的湮灭。
- Primary：RepresentationShift
- Secondary：无
- Claude 置信度：高

**RAW-07**
- 导师观察：学生将"冗余导致的无效叠加"和"真实的有效扩张"混淆，对"独立贡献"这个概念的语义理解有偏差。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：中高

**RAW-08**
- 导师观察：学生因局部数据为零，盲目裁剪了系统的整体维度边界，导致结构约束在后续推导中坍塌。
- Primary：StructuralReasoning
- Secondary：无
- Claude 置信度：高

**RAW-09**
- 导师观察：学生未能区分"操作层面的复合"与"结果层面的算术运算"，把复合操作错误理解成了可以对自变量分别处理再相乘的初等结构。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：高（这条和 RAW-02 是同一病灶的不同呈现，可用于交叉核对分类者是否稳定）

**RAW-10**
- 导师观察：学生缺乏对长流程中"前向依赖与破坏性更新"的追踪能力，操作序列发生震荡和自我抵消。
- Primary：FlowReasoning
- Secondary：无
- Claude 置信度：高

**RAW-11**
- 导师观察：学生无法理解"有限的独立基准信号通过组合可以覆盖无限连续范围"这一语义，认知停留在"有限无法映射无限"的离散化直觉中。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：中高

**RAW-12**
- 导师观察：学生混淆了结构的拓扑突变点（指标是否精确为零）与数值的绝对大小，未能识别非零即存在强约束这一点。
- Primary：SemanticIntegrity（对"临界判定"这个概念的语义理解有误）
- Secondary：StructuralReasoning（低置信度）
- Claude 置信度：中

**RAW-13**
- 导师观察：学生不理解降维操作会导致高维信息永久湮灭，固守"所有操作都双向对称、完美可逆"的初等幻觉。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：中高

**RAW-14**
- 导师观察：学生未能理解"排他性条件"的逻辑结构，把一个永远成立的平凡事实当成了证明独立性的有效证据。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：高

**RAW-15**
- 导师观察：学生未能正确维持两个独立区域之间的约束关系，不理解对一个区域的扰动会影响另一个区域的状态。
- Primary：StructuralReasoning
- Secondary：无
- Claude 置信度：高

**RAW-16**
- 导师观察：学生在执行多方向并行操作时，未能用正确的复合方式承载并发状态，导致操作丢失。
- Primary：FlowReasoning
- Secondary：无
- Claude 置信度：中高

**RAW-17**
- 导师观察：学生不理解负号在这类映射中代表方向翻转，被"体积必须为正"的初等常识绑架，产生了不必要的认知卡顿。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：高

**RAW-18**
- 导师观察：学生把"约束少于变量必然无唯一解"的定性规则过度泛化，未能识别特殊结构下依然可能存在唯一解的情形。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：中高

**RAW-19**
- 导师观察：学生认知局限在实数范围内，拒绝在推导需要时把表达形式一致扩展到更大的数域，导致推导中断。
- Primary：RepresentationShift（未能扩展表达形式的适用范围）
- Secondary：SemanticIntegrity（低置信度——也可理解为对"解的存在性"这个概念本身理解不完整）
- Claude 置信度：中（这条我犹豫较大，建议真人评分者重点核对）

**RAW-20**
- 导师观察：学生只追踪了标量层面的不变特征，忽略了方向层面的关键结构，导致认知结构片面化。
- Primary：StructuralReasoning
- Secondary：无
- Claude 置信度：中高

**RAW-21**
- 导师观察：方法论骨架正确（知道要做剔除），但在微观代数动作上把方向做反了。
- Primary：FlowReasoning
- Secondary：无
- Claude 置信度：高

**RAW-22**
- 导师观察：学生在没有建立真实空间映射直觉的情况下，把视觉上的表格翻转等同于空间的真实变换，构建了虚假的几何意义。
- Primary：RepresentationShift
- Secondary：无
- Claude 置信度：高

**RAW-23**
- 导师观察：学生不理解决定长期收敛性的是"绝对大小"而非"代数符号"，被初等的正负号直觉误导。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：高

**RAW-24**
- 导师观察：学生未能理解"没有信息量的结果意味着自由度、解是一个连续范围"，而是把代数形式上的零等同于变量本身不存在。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：高

**RAW-25**
- 导师观察：学生未能理解"被消去的方向在输出中必须精确归零"这一结构逻辑，误用常数占位，导致输出脱离目标范围。
- Primary：StructuralReasoning
- Secondary：无
- Claude 置信度：高

**RAW-26**
- 导师观察：学生没有建立"冗余数据导致结构坍塌"的直觉，仍停留在"数值对称=结果完美"的初等代数本能中。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：中高

**RAW-27**
- 导师观察：学生没有建立"沿不变方向的整条范围都是不变量方向"这一认知，把代数上的尺度放大错误表达成了物理世界里的非线性变轨。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：中高

**RAW-28**
- 导师观察：学生未能从"输出范围极端狭窄"这一事实逆向推导出系统内部结构退化这一现实，因果关系发生倒置。
- Primary：StructuralReasoning
- Secondary：无
- Claude 置信度：中高

**RAW-29**
- 导师观察：学生无法在更高维度的场景里维持"全员两两相互约束"的整体结构，只执行了局部的、单向的链接。
- Primary：StructuralReasoning
- Secondary：无
- Claude 置信度：高

**RAW-30**
- 导师观察：学生被表面的视觉特征（主轴为零）误导，不理解真正决定可逆性的语义是"各方向是否保持独立"，而非个别位置的数值。
- Primary：SemanticIntegrity
- Secondary：无
- Claude 置信度：中高

---

## 标签分布统计（供设计阶段参考，不是正式结果）

- RepresentationShift（Primary）：6条（01,03,06,19,22 + 02 secondary 不计入）
- SemanticIntegrity（Primary）：15条
- FlowReasoning（Primary）：5条
- StructuralReasoning（Primary）：7条（有一条与08重复计入需要核对，建议项目负责人复核时重新点数）

**一个需要提醒的观察**：SemanticIntegrity 占比明显偏高（约一半案例）。这本身可能是真实的（线性代数确实是一门"概念语义"要求很高的学科），但也可能是我在做分类判断时，无意识地把"不确定该怎么归类"的案例都倾向性地放进了这个看起来更包容的类别——这正是上一轮反馈里特别警告过的"兜底类别吸走案例"风险。建议项目负责人复核时，对 SemanticIntegrity 这一类的案例格外多看一眼，确认是不是真的都站得住，而不是我自己也无意识地掉进了这个坑。
