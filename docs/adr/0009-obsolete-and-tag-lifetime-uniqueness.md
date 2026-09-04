---
status: accepted
date: 2026-08-28
---

# OBSOLETE = 人工弃用（分级凭证）；位号终身唯一，弃用不复用

ADR-0003 之后 OBSOLETE 的两个旧触发条件（上游变更、版本替换）均已失效，需重新定义。同时存在场景：管线整个取消（CHECKED 且被 Rev 0 绑定）、改线后同位号重算。

决定：OBSOLETE 只由设计人主动弃用触发。**未绑定记录**：填写弃用原因后直接 OBSOLETE，免凭证。**被绑定记录**：必须创建变更单（change_type=RECORD_CANCELLATION），变更单 APPROVED 后记录转 OBSOLETE，所有绑定旧 Rev 标 AFFECTED，下次升 Rev 时从快照移除。弃用权限仅设计人与项目负责人。

**位号终身唯一**（修订，推翻初稿"位号释放可复用"）：管道号/设备位号一经分配终身占用，唯一约束覆盖含 OBSOLETE 的全部记录，弃用不释放、永不复用；替代必须分配新号（P-101A 取消则新泵用 P-102A）。管线未取消仅参数变化 → 走 CHANGED 流程，禁止弃用+同位号重建。理由：避免项目文件、现场标记、采购记录中的同号异义混淆，符合多数工程实践。

## Consequences

- 记录表新增 obsoleted_reason / obsoleted_by / obsoleted_at / obsoleted_via_deliverable_id；不设 superseded_by_record_id（同位号替代被禁止）。
- 数据库唯一约束：(project_id, tag_number/line_no) 含 OBSOLETE 记录。
- 设备联动：来源记录弃用 → 设备记录 sign_status 跟随 OBSOLETE，EquipmentStatus 置 D；表级 EquipmentStatus 与 sign_status 并存，前者优先表述生命周期。
- 变更单 change_type 新增 RECORD_CANCELLATION；弃用确认 UI 须警示号码永久锁定。
