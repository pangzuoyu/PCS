---
status: accepted
date: 2026-08-28
---

# 变更单是交付物的子类型（deliverable_type=CHANGE_NOTICE），不是平行实体

ADR-0002 一边说变更单"复用版本序列和签署矩阵机制"，一边又设计了独立 change_notices 表（自带 sign_status / matrix_id / version_purpose / cn_no）。照此实现 P1 需要两套签署状态机、两套编号、两套版本历史，"复用"落空。

决定：变更单 = deliverables 表中的一行（deliverable_type=CHANGE_NOTICE），签署状态机、编号模板、Rev（deliverable_versions）、快照绑定全部复用交付物机制；变更单特有字段（change_type、reason、triggered_by）放 1:1 扩展表 change_notice_details。deliverable_record_bindings 增加 old_record_hash_before_change 字段承载新旧哈希对比（替代原 change_notice_record_bindings）。删除独立 change_notices 表。变更单默认 3 级矩阵（校核/审核/审定，通常无 CUSTOMER；响应客户意见的项目可配置增加），版本目的 ISSUED_FOR_CHANGE。变更单 APPROVED 后系统自动将绑定记录 CHANGED → CHECKED 并写入 change_resolved_by；被驳回则回 DRAFT，绑定记录保持 CHANGED。

## Consequences

- 一套交付物状态机、一套编号、一套版本历史覆盖普通交付物与变更单。
- deliverable_type / version_purpose 枚举扩展；签署矩阵模板库增加 CHANGE_NOTICE_3_LEVEL。
- P0 删除 change_notices 表、新增 change_notice_details；P1/P2/P8/P9 按"交付物机制覆盖变更单"修订。

## 修订记录

### 2026-10-26 · 「绑定记录保持 CHANGED」**经裁决确认**，与 ADR-0002 的冲突已消解

本 ADR 说「被驳回则回 DRAFT，**绑定记录保持 CHANGED**」；ADR-0002 说「变更单
驳回则记录回 CHANGE_PENDING 重改」—— 字面互斥（2026-10-26 评审发现）。

**裁决**：**本 ADR 管辖「变更单被驳回」** ⇒ 记录**保持 CHANGED**。
理由与「重改」的落地路径（撤销 → 重来）见 **ADR-0002 §修订记录
2026-10-26**（两处互相引用，不重复论证）。

一句话：**驳回的是「单据」，不是「校核结论」** —— 变更已经校核完（记录在
CHANGED），被驳回的是那张变更单 ⇒ 单据回 DRAFT 重签，记录不动。
若要改**数据**，走撤销恢复快照后重做。
