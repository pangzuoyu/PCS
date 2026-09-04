---
status: accepted
date: 2026-08-28
---

# 上游变更命中锁定记录走 STALE 标记 + 哈希判定，替换 P1 的作废重建规则

P1 §3.2.6 原规则（APPROVED → 原记录 OBSOLETE + 自动新建记录从 DRAFT 开始）与两层模型冲突：记录层已无 APPROVED，且作废重建会造成位号唯一性、设备表同步、血缘引用断链（ADR-0002 已否决双记录并存）。同时 STALE 机制补上了 ADR-0002 的缺口——CHANGE_PENDING 原只有设计人主动发起一个入口，上游变更由系统检测、无人发起。

决定：上游变更命中**已锁定的 CHECKED 记录** → STALE（数据存疑，只读）→ 设计人确认重算 → 哈希不变则 STALE 清除恢复 CHECKED（交付物 AFFECTED 若因此消除则一并清除）；哈希变化则进 CHANGE_PENDING → CHANGED → 凭证关闭。命中**未绑定的 CHECKED 记录** → 直接回 DRAFT 重算，不走 STALE。"变更"以结果哈希变化为准，不以上游是否变动为准。

## Consequences

- RecordSignStatus 最终为 7 值：DRAFT / CHECKED / CHECK_REJECTED / STALE / CHANGE_PENDING / CHANGED / OBSOLETE。
- 哈希 = SHA-256，仅覆盖计算结果字段，数值先规范化舍入（6 位有效数字）再比对，防浮点精度假变化。
- 业务记录表新增 stale_since / stale_reason / stale_resolved_at 字段；审计日志新增 UPSTREAM_CHANGE_DETECTED、STALE_RESOLVED_NO_CHANGE、STALE_RESOLVED_CHANGED 等 action。
- STALE 与 CHANGED 都不可被新交付物绑定；STALE 不一定需要凭证（结果不变即无变更）。
- P1 §3.2.6 状态回退规则整段替换；"受影响记录自动锁定只读"由 STALE 状态本身承载。
