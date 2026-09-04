---
status: accepted
date: 2026-09-01
---

# 设备联动最终一致性窗口 ≤ 5 分钟（CIA 异步传播）

ADR-0005 已规定"来源记录 STALE / CHANGE_PENDING / CHANGED 时设备记录联动进入相同状态"。P1 实施审阅（2026-09-01）发现设备联动归属模糊：若由状态机 Sprint 2 同步执行，则 CIA 扫描（Sprint 3 异步）失去意义；若由 CIA 异步执行，则状态机已 CHECKED 时设备记录仍可能 STALE 存在中间窗口。

决定：**设备联动走 CIA 异步链路，窗口期容忍 ≤ 5 分钟**。具体：

- 来源记录状态变化（如 CHECKED → STALE）触发 CIA 扫描任务（cron 1 分钟扫 `data_lineage.timestamp >= now()-7d` 增量 + 5 分钟兜底扫全量），由 `cia_engine.py` 完成设备记录状态联动。
- 期间存在最终一致性窗口：来源已 STALE / CHANGE_PENDING / CHANGED 但设备记录仍为 CHECKED，**最长 5 分钟**（cron 兜底周期）。
- 设备一览表（EQUIP_LIST）发布时（P1.2 交付物）必须等待 CIA 扫描完成或显式声明接受窗口期。
- **CIA 扫描失败 3 次后**：`equipment_list.actual_data_status` 置为 `NEED_RECALC`（P0 DICT 已定义枚举值，零 Schema 变更）+ `audit_logs.action=CIA_NOTIFIED` + `remarks="SCAN_FAILED"` + 告警。扫描恢复后设备记录按正常状态机路径自然回到 STALE / CHECKED，**不引入新持久状态列**。

此为可接受的最终一致性（vs 强一致）：强一致需在状态机 transition 内同步触发设备联动，导致 transition 跨表事务膨胀、CIA 失去意义。

## Consequences

- 设备联动延迟由 ADR-0005 的"自动同步"修订为"≤ 5 分钟最终一致"。
- `change_impact.py` 提供 `/change-impact/{record_type}/{record_id}/confirm-recalc` 高层动作，内部调用 `StateMachineService.transition`，状态机不暴露 CONFIRM_RECALC 复合动作。
- **零 Schema 变更**：`equipment_list.actual_data_status` 复用 P0 已有 `NEED_RECALC` 枚举值表达"需要重新计算/同步"。
- 前端需展示"设备同步中"标记（Sprint 3 UI；P1.2 通知面板）。
- `audit_logs` 增加 `CIA_NOTIFIED` action 记录每次扫描完成（Issue 6 锁定）。
- 设备一览表发布的 SPEC-P1 V1.3 §3.2.5 需声明窗口期。
- 与 ADR-0005 § 联动状态同步（"自动同步"修订为"≤5分钟最终一致"）；与 ADR-0010 / ADR-0024 无冲突。