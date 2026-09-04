---
status: accepted
date: 2026-08-28
---

# 物流（streams）采用简化门禁：初次引入须校对，后续修改知情管理不重校对

streams 是 SIM 导入的输入事实而非设计成果，原 schema 无 sign_status——任何人改一个数字即全项目相关记录大面积 STALE，改动本身无确认概念。纯走 9 态记录门禁又会导致"上游变更源头自己也要凭证"的循环嵌套。

决定：streams 用独立的简化状态集（DRAFT / IN_APPROVAL / CHECKED / OBSOLETE）。**初次引入**（导入/创建）走校对审核（默认 1 级校对人，可配 2 级加审核），校对项含来源一致性、组成归一化（100±0.5%）、单位、完整性、数值合理性；DRAFT/IN_APPROVAL/OBSOLETE 状态不可被计算记录引用（403）。**后续修改**已 CHECKED 的物流：状态保持 CHECKED，不重新校对——限权（DESIGNER + 项目负责人）+ 强制修改原因 + 影响预览（展示下游波及清单后确认），确认后触发 CIA、下游记录 STALE。物流弃用直接 OBSOLETE 免凭证（未被交付物绑定）。验明正身一次，之后的变化由知情管理覆盖。

## Consequences

- streams 表新增 sign_status / approval_step / approval_depth / checked_by / checked_at；StreamSignStatus 与 RecordSignStatus 是两个独立枚举。
- 项目模板新增 stream_approval_config（P2）；SIM 模块导入后校对流程（P3）；物流校对 UI（P9）。
- 修改管控三件套（限权/原因/预览）同样适用于其他无门禁基础数据（如 BEDD 字段）的修改场景，可复用。
