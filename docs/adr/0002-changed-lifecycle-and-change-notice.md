---
status: accepted
date: 2026-08-28
---

# 已发布记录的修改走 CHANGED 生命周期 + 变更单机制，不回退 DRAFT、不写时复制

被交付物快照绑定的 CHECKED 记录需要修改时（场景：管道一览表 Rev 0 已发布，第 5 条管径算错），存在三条路：原地回退 DRAFT、写时复制新记录、交付物驱动解锁。三条都有缺陷——回退 DRAFT 丢失"修改已发布数据"与"新建"的语义区分；写时复制使位号唯一性、设备表同步、血缘追溯都要处理双记录并存；交付物驱动解锁让数据正确性问题被发布流程卡住。

决定：记录层增加 CHANGE_PENDING（获准修改、正在改+重校核）与 CHANGED（校核完成、等待关闭）两态。变更通过两种凭证关闭：新版交付物发布（大变更，升 Rev）或**变更单（Change Notice）**发布（小变更，独立签署矩阵，版本目的 ISSUED_FOR_CHANGE，与工程 DCN/ECN 实践一致）。变更单驳回则记录回 CHANGE_PENDING 重改。被绑定的旧 Rev 永久标记 AFFECTED（快照与当前数据不一致是既成事实）。

## Consequences

- RecordSignStatus 扩展为 6 值；业务记录表新增 change_pending_since / change_resolved_by / change_resolved_at / old_record_hash_before_change 四字段。
- 新增 change_notices、change_notice_record_bindings 两张表；变更单复用 SUP-004 版本目的与 SUP-005 签署矩阵机制（新增 CHANGE_NOTICE 文档类型、ISSUED_FOR_CHANGE 目的）。
- 每次对已发布数据的修改都有可追溯的关闭凭证（谁、为什么、凭什么关闭），防止无声修改。
- SUP-005 §3.2"上游变更回退规则"需与 CHANGED 机制对齐（见后续 ADR）。
