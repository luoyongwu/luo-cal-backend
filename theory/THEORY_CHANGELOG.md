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
