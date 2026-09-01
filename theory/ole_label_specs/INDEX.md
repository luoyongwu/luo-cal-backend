# OLE Label Specs — Index

跟踪七个 OLE 标签的"三张地图"规范文档冻结状态。每个标签独立文档，命名为 `{LABEL}_v{N}.md`。

| 标签 | 当前冻结版本 | 冻结日期 | 三层归属 | 状态 |
|---|---|---|---|---|
| RA (REPRESENTATION_ALIGNMENT) | v3 | 2026-09-01 | 认知行为事件层 | 冻结，待数据攻击 |
| SV (SPONTANEOUS_VERIFICATION) | — | — | 认知行为事件层（预判） | 未开始 |
| JR (JUDGMENT_RATIONALE) | — | — | 认知行为事件层（预判） | 未开始 |
| ER (EXPLICIT_REASONING) | — | — | 横向伴随维度 / moderator（预判） | 未开始 |
| SC (SELF_CORRECTION) | — | — | 认知行为事件层，动态事件（预判） | 未开始 |
| TC (TASK_COMPLETION) | — | — | 任务状态层（预判） | 未开始 |
| CC (CONCEPT_COMPLETION) | — | — | 教学过程决策层（预判） | 未开始 |

## 三层假设（待验证）
- 层 1：认知行为事件（Student Cognitive Event）— SV / JR / RA / SC，Phase 2 核心变量
- 横向维度：ER — moderator，不构成独立层，描述"是否说明了理由"，可与任意层 1 标签共现
- 层 2：任务状态（Task State）— TC，回答"这次任务完不完整"，与过程变量不在同一本体层级
- 层 3：教学过程决策 / 状态转移（Teaching Process Decision）— CC，更接近教学决策而非纯学生认知事件

验证方法：待六个标签三张地图全部完成后，统一设计跨标签数据攻击测试；若各标签地图三（决策地图）的结构差异与上表预判一致，则三层假设获得支持。

## 通用写作纪律（RA v2→v3 修订中确立，适用于后续所有标签）
- OLE 层负责观察，Cognitive State 层负责解释，Teaching Decision 层负责行动 — 三层不能混
- 地图二、地图三首稿即应避免因果化措辞（如"转换有效""策略意识不足"），只描述共现关系，不下结论
- 失败链 / 组合模式一律使用纯描述性语言，不使用评价性词汇（"成熟""更强"等），认知解释留给 Cognitive State 层
- 边界锚点案例保留在地图一，但明确标注为"对照证据"而非"定义本身"
