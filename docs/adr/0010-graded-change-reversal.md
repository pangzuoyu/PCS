---
status: accepted
date: 2026-08-28
---

# 变更撤销以"是否已对外生效"为界分级处理，新增 REVERSAL_PENDING 状态

进行中的变更（CHANGE_PENDING）需要能反悔：上游数据改回、客户撤回意见。原建议以"是否校核通过"为撤销边界——被否决。正确边界是**是否已对外生效**（变更单/新版交付物已发布）：校核通过本身不产生对外效力，不应阻塞撤销。

决定三条路径：**A** CHANGE_PENDING 中放弃——设计人自行操作、免批准，恢复变更前快照回 CHECKED，审计 CHANGE_ABANDONED。**B** CHANGED 撤销——新增 REVERSAL_PENDING 状态，设计人发起、撤销批准链批准（3 级矩阵取 Reviewer、4 级取 Approver，项目模板可配），批准即恢复快照回 CHECKED，批准记录本身即凭证；驳回回 CHANGED 继续等凭证。**C** 已生效变更的撤销——只能创建新变更单（change_type=CHANGE_REVERSAL）反向修改，走完整签署。STALE 不需要撤销：上游恢复后重算哈希不变自动回 CHECKED。进入 STALE / CHANGE_PENDING 时系统自动保存变更前快照，支撑哈希判定与回滚。

## Consequences

- RecordSignStatus 最终 8 值：DRAFT / CHECKED / CHECK_REJECTED / STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE。
- 记录表新增 reversal_* 字段组；审计新增 CHANGE_REVERSAL_REQUESTED / APPROVED / REJECTED。
- 撤销批准角色在项目模板中配置（P2）；撤销审批 UI 进 P9；快照恢复服务进 P1。
