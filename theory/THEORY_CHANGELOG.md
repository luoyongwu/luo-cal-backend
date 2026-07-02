# Theory Changelog
## Luo-cal 理论变更日志

本文件记录所有理论宪章文档（Ontology、CWM、SCL Spec、White Paper）的
重大决策、开放问题与版本变更历史。

---

## 2026-07-02 — Constitution v1.0 冻结

### 已完成
- Root Cause Ontology v3.0 正式冻结（Constitution v1.0 第一部）
- Cognitive World Model v1.0 正式冻结（Constitution v1.0 第二部）

### Open Questions（开放问题，不影响当前冻结）

**OQ-001：Flow World 命名的本体论类型问题**

- 提出者：DeepSeek 交叉审阅
- 问题：Representation World 与 Approximation World 均为
  Object-oriented（对象性）定位，而 Flow World 本质是
  Process-oriented（过程性）——描述的是推理流程而非认知对象。
  三者理论层级并不完全平行。
- 候选替代名：Reasoning World / Inference World / Procedure World /
  Planning World
- 当前决定：**不在 v1.0 阶段修改**，因为 Flow World 已与 Ontology、
  Dashboard、论文形成一致引用，过早改名会造成理论体系内部不一致
- 复审时机：Phase 2 完成跨学科验证（Linear Algebra / Physics）后
  重新评估

**OQ-002：RWM → FWM 依赖关系**

- 见 COGNITIVE_WORLD_MODEL_v1.0.md 第4.2节
- 初步观察：RWM 稳定性可能是 FWM 稳定性的前提条件
- 当前决定：标注为 Hypothesized Dependency，不写入正式理论
- 复审时机：Phase 2 真实学生数据积累后

---

*Luo-cal Cognitive Layer Engineering | 硅基智库*

## 2026-07-02 — SCL Specification v1.0 冻结 + 命名变更

### 已完成
- SCL Specification v1.0 正式冻结（Constitution v1.0 第三部 / Volume III）
- 三卷体系正式命名：Volume I (Ontology) / Volume II (CWM) / Volume III (SCL Spec)

### 命名变更（Naming Change）

**NC-001：SCL 全称变更**

- 提出者：DeepSeek 交叉审阅
- 变更前：Socratic Constraint Layer
- 变更后：**System Constraint Layer**（缩写 SCL 不变）
- 理由：SCL 约束的内容（Leakage、Hard Rule、Provider、Adapter、MADNESS）
  均不特定依赖苏格拉底式对话，与 Ontology 中 Adaptive Cognitive
  Intervention 的术语升级保持一致
- 影响范围：仅文档表述，不影响现有代码变量名（如需同步修改代码注释，
  留待下次工程迭代处理，不影响功能）

### Open Questions（新增）

**OQ-003：Leakage Score 加权口径的历史数据重算**

- 问题：A1-A4 消融实验数据基于旧版计数口径（Count-based）采集，
  v1.0 引入加权口径（Weighted）后尚未重新计算
- 当前决定：暂不重算，两种口径并存于文档中，明确标注数据来源口径
- 复审时机：Phase 2 补充分析

## 2026-07-02（续）— SCL Specification v1.0 修订

### DeepSeek 双重交叉审阅后的必须性修改（8处，全部完成）

1. 架构图加入 DAN Memory 节点：CWM → DAN Memory → Dashboard
2. 新增 Provider 验证要求：从至少一轮改为全部11个MADNESS探针
3. P0/P1 判断标准明确化：能否穷举安全例外
4. Hint Leakage 边界说明：学生已隐含信息时不算主动泄漏
5. Reflection 实现状态标注：跨会话计数器留待Phase 2
6. Adapter契约要求：system参数不得截断改写
7. Hard Rule清单冻结范围声明
8. 第0章补充Constitution/Specification/Implementation三层修改门槛

### 三卷术语交叉验证结果

DeepSeek 对 Ontology / CWM / SCL 三卷进行术语一致性检查，未发现冲突。

### Constitution v1.0 三部曲正式完整落定

- Volume I: ROOT_CAUSE_ONTOLOGY_v3.0.md
- Volume II: COGNITIVE_WORLD_MODEL_v1.0.md
- Volume III: SCL_SPECIFICATION_v1.0.md

