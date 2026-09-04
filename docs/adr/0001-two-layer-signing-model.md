---
status: accepted
date: 2026-08-28
---

# 签署与版本采用两层模型：计算记录无 Rev，交付物承载全部发布语义

原规格存在矛盾：P0 Schema 给每条业务记录（piping_results、equipment_list 等）都配了 `version` + `sign_status`，而 SUP-004/005 的签署页与版本目的（Issued for Construction 等）是按交付物（文档）发布的工程实践。按记录逐条版本化会让"管道一览表 Rev 1"无定义。

决定采用两层模型：**计算记录（Record）** 只有数据正确性门禁（DRAFT → CHECKED，退回 CHECK_REJECTED，作废 OBSOLETE），无 Rev、无版本目的；**交付物（Deliverable）** 独占 Rev（A/B/C → 0/1/2 → AS-BUILT，X 作废）、版本目的与完整签署矩阵，发布时通过快照绑定（record_id + record_hash）锁定所引用的记录。

## Considered Options

- 纯记录级版本化——"文档 Rev"无定义，签署页无法生成，否决。
- 纯交付物级——单条数据何时"校核通过"无处追踪，设备表同步失去依据，否决。
- 模块数据集级——粒度过粗，单条修改需整体重签，否决。

## Consequences

- 业务记录表移除 `version` / `version_purpose` / `version_description` / `customer_approval_date`，新增 `record_hash`、`locked_by_deliverable`。
- 新增 `deliverables` / `deliverable_versions` / `deliverable_record_bindings` 三张表。
- SUP-004 版本序列与 SUP-005 签署矩阵的作用对象从"所有工程数据记录"改为"仅交付物"；记录层签署简化为两级门禁。
- P1 状态机拆分：记录层门禁状态机 + 交付物层签署矩阵状态机。
- 上游变更回退规则仅对记录层"回 DRAFT"；已发布交付物受影响时走新 Rev，不改历史 Rev。
