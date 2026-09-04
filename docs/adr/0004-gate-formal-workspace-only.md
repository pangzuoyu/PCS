---
status: accepted
date: 2026-08-28
---

# 校核门禁与交付物仅存在于正式工作区，个人/临时区记录永远 DRAFT

工作区与两层模型交叉处需定门禁归属：个人工作区的试算数据能否提交校核、能否攒交付物。P1 只规定了"导入正式项目时创建新记录从 DRAFT 开始"，未禁止个人区内走签署。

决定：CHECKED/STALE/CHANGE_PENDING/CHANGED 与交付物、变更单全部只存在于 FORMAL 工作区。PERSONAL/TEMPORARY 记录永远 DRAFT（试算），提交校核/创建交付物/创建变更单 API 对非 FORMAL 工作区返回 403。校核人不为试算数据背签。个人区可只读快照引用正式区 CHECKED 数据，正式区不可引用试算数据；导入正式区 = 复制新 record_id、重算 record_hash、从 DRAFT 走完整门禁，血缘记录导入来源，原试算记录保留并标记"已导入"防重复。

## Consequences

- 状态机在个人/临时区退化为单态 DRAFT，无跨工作区信任传递。
- 业务记录表新增 imported_from_workspace_id / imported_at 字段。
- 个人区对正式区数据的引用是快照，不参与 CIA 变更影响分析（试算结果不随上游联动）。
- P1 新增 P1-WS-006~009；P9 新增工作区相关 UI 需求。
