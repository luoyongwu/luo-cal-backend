# Evidence Aggregator — 贝叶斯设计规范 v0.2

（完整内容见 GitHub planning/ 目录）

## 关键修改（§5）

这三个新字段的定义已在本节确定；实际补进 `pcsa_interfaces.py` 的 `WeightVector` 
是在 Phase 2 实现阶段完成的（见 `DESIGN_NOTES.md` ADR-006——规格定稿与代码同步之间 
曾有过一次记录疏漏）。不传这几个字段的旧实现（如 `DummyAggregator`）使用默认值，
依然能通过校验。
