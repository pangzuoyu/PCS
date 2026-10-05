"""供应商核算与更新流程 (P7 Sprint 4 Task S4-3 / SPEC V1.4 §3.2.4(4)(5)(6)).

流程（SPEC §3.2.4(4) 原文）：
    设计人录入实际数据 → 系统自动比对生成偏差报告
    → 设计人确认：全部合格/仅警告 → 勾选"确认实际数据满足工艺要求" → 提交校核
    → 校核人校核 → 通过后标记"已确认"
    → 系统更新（UTIL 引用实际值 / 触发变更影响分析）

三条 SPEC 约束在这里落地：
1. **不合格 / 不可判项禁止确认**（§3.2.4(4) + 风险 #4）—— 门禁用 S4-2 的
   `can_confirm`，它已把「不可判」也算作阻断（fail-closed）。
2. **实际数据不参与设备记录门禁哈希**（§3.2.4(5)）—— 本模块**不碰**
   `sign_status` / `record_hash`。实际数据的确认门禁是 `actual_data_status`，
   与记录签审 9 态互不替代（见 `app/models/enums.py` EquipmentStatus 文档）。
3. **已确认的实际数据修改需校核人退回**（§3.2.4(5)）—— 门禁在
   `actual_data_service.record_actual_data`，本模块提供 `reject_check` 解锁。

**D4 裁决 4A**：本模块**只 `emit_event`，不直调 state_machine**（有静态守卫测试
锁定）。`actual_data_replaces_design` 事件的 `before` **必带** —— 值一旦被覆盖
就永久丢失，漏了它 P8 的反向恢复无从下手。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.enums import ActualDataStatus
from app.services.events import emit_event
from app.services.supplier.deviation_report import build_report, can_confirm

# 事件类型
CHECK_SUBMITTED = "actual_data_check_submitted"
REPLACES_DESIGN = "actual_data_replaces_design"


def _error(code: str, message: str, status: int = 422) -> PcsError:
    return PcsError(code=code, message=message, status=status)


async def confirm_actual_data(
    session: AsyncSession,
    equipment,
    actor: Any,
    *,
    reason: str = "",
) -> Any:
    """设计人勾选「确认实际数据满足工艺要求」并提交校核（§3.2.4(4)）.

    前置：偏差报告全部合格或仅警告。存在不合格/不可判 → 422。

    `actual_data_status` 此时**仍为 PENDING_CONFIRM** —— 校核通过才转 CONFIRMED。
    PENDING_CONFIRM 同时覆盖「待确认」与「校核中」两段，是 ADR-0025 现有 4 值
    枚举的容量限制（增第 5 值要动迁移与状态列默认值，超出本 Task 范围）。
    """
    if equipment.actual_data_status == ActualDataStatus.CONFIRMED.value:
        raise _error(
            "ACTUAL_DATA_ALREADY_CONFIRMED",
            "实际数据已确认 —— 修改需校核人先退回（SPEC §3.2.4(5)）",
        )

    report = build_report(equipment)
    if not can_confirm(report):
        raise _error(
            "DEVIATION_BLOCKS_CONFIRMATION",
            f"存在不合格或不可判项，禁止确认：{report.blocking_reason}",
        )

    await emit_event(
        session,
        CHECK_SUBMITTED,
        event_id=uuid.uuid4(),
        equipment_id=equipment.equipment_id,
        actor_user_id=actor.user_id,
        actor_role=actor.role,
        reason=reason,
        blocking_reason="",
    )
    await session.commit()
    return equipment


async def pass_check(
    session: AsyncSession,
    equipment,
    actor: Any,
    *,
    reason: str = "",
) -> Any:
    """校核人校核通过 → 标记「已确认」并发出 `actual_data_replaces_design`.

    `before` 存设计值、`after` 存实际值 —— **P8 反向恢复的唯一来源**。
    事件带 `before` 是硬要求，漏了就永久丢数据。
    """
    equipment.actual_data_status = ActualDataStatus.CONFIRMED.value
    await session.flush()

    await emit_event(
        session,
        REPLACES_DESIGN,
        event_id=uuid.uuid4(),
        before=equipment.design_parameters_json,   # deepcopy 后落 event_idempotency
        after=equipment.actual_data_json,
        equipment_id=equipment.equipment_id,
        actor_user_id=actor.user_id,
        actor_role=actor.role,
        reason=reason,
    )
    await session.commit()
    return equipment


async def reject_check(
    session: AsyncSession,
    equipment,
    actor: Any,
    *,
    reason: str = "",
) -> Any:
    """校核人退回 → 回到 PENDING_CONFIRM，重新录入通道解锁（§3.2.4(5)）."""
    equipment.actual_data_status = ActualDataStatus.PENDING_CONFIRM.value
    await session.commit()
    return equipment


__all__ = [
    "CHECK_SUBMITTED",
    "REPLACES_DESIGN",
    "confirm_actual_data",
    "pass_check",
    "reject_check",
]
