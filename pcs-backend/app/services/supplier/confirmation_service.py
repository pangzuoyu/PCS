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
from app.services.events import derive_event_id, emit_event
from app.services.supplier.deviation_report import build_report, can_confirm

# 事件类型
CHECK_SUBMITTED = "actual_data_check_submitted"
REPLACES_DESIGN = "actual_data_replaces_design"


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
        raise PcsError(
            code="ACTUAL_DATA_ALREADY_CONFIRMED",
            message="实际数据已确认 —— 修改需校核人先退回（SPEC §3.2.4(5)）",
            status=422,
        )

    report = build_report(equipment)
    if not can_confirm(report):
        raise PcsError(
            code="DEVIATION_BLOCKS_CONFIRMATION",
            message=f"存在不合格或不可判项，禁止确认：{report.blocking_reason}",
            status=422,
        )

    # ⚠️ `CHECK_SUBMITTED` 的 event_id 派生口径**待定**（Sprint 5 候选，未登记 P8）——
    # 与 `replaces_design` 不同，它这里仍是现生成的 uuid4()：
    #   - 若本端点日后有状态前置守卫（#5 修复后 `pass_check` 的 PENDING_CONFIRM 守卫
    #     是同类形态）→ 重发被守卫挡住，uuid4 安全，不必改。
    #   - 若无守卫且双击「提交校核」会重发 → 应同 #3 改 uuid5 确定性派生。
    # 改前先确认「同一台设备重复提交校核」是否是真业务操作。参考 #3 裁决：
    # `replaces_design` 已改 uuid5，正是因为它无前置守卫。
    # ⚠️ 勿照搬 `cia_mark_stale`：那个事件的语义是「每次扫描都该重新评估」，
    # 幂等去重会直接让它不再工作，改 uuid5 是 bug 不是 feature（已闭，不改）。
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

    前置（审查 #5）：状态必须是 PENDING_CONFIRM，且门禁在此**重跑一次**。
    修复前本函数第一条语句就是置 CONFIRMED，端点侧唯一闸是
    `require_roles(_CHECK_ROLES)` —— 持项目访问权的 REVIEWER 可把从未录入的
    设备直推 CONFIRMED，而 CONFIRMED 正是 `record_actual_data` 认定的锁
    （ACTUAL_DATA_LOCKED），本该填数据的设计人被永久冻结。`can_confirm`
    此前只在 `confirm_actual_data` 里跑，「录入 → 校核」之间的任何改动
    不再被复判，四眼控制落空。
    """
    if equipment.actual_data_status != ActualDataStatus.PENDING_CONFIRM.value:
        # inline raise（非 `_error` 工厂）—— 工厂返回式 PcsError 会被
        # meta_service 的 AST 扫描器漏掉，新码进不了错误码注册表（审查 #4）。
        raise PcsError(
            code="ACTUAL_DATA_STATE_CONFLICT",
            message=(
                f"当前状态 {equipment.actual_data_status} 不可校核通过 —— "
                "只有 PENDING_CONFIRM 可过（NOT_ENTERED 尚未录入、"
                "CONFIRMED 已确认、NEEDS_RECALC 待重算）"
            ),
            status=409,
            detail={
                "retryable": False,
                "current_state": equipment.actual_data_status,
                "required_state": ActualDataStatus.PENDING_CONFIRM.value,
            },
        )
    if not can_confirm(build_report(equipment)):
        raise PcsError(
            code="DEVIATION_BLOCKS_CONFIRMATION",
            message="偏差报告存在不合格/不可判项, 不可校核通过（请退回重录）",
            status=422,
        )
    equipment.actual_data_status = ActualDataStatus.CONFIRMED.value
    await session.flush()

    # ⚠️ 改为确定性 event_id（uuid5）**必须**与 `events.py::_claim` 的 savepoint
    # 改造同提交 —— 见该函数 docstring 的「原子性约束」段。单修此处会打开数据丢失路径：
    # 碰撞从「不可能」变为「可能」，而 `_claim` 的 rollback 分支尚未修时会连同上面
    # flush 的 CONFIRMED 一起丢弃。推导 uuid5 时 payload_hash 的计算范围**只含业务字段**
    # （equipment_id + before + after），不得含 timestamp / request_id / iat，
    # 否则每次重投 hash 不同，幂等彻底失效。
    await emit_event(
        session,
        REPLACES_DESIGN,
        event_id=derive_event_id(
            REPLACES_DESIGN,
            equipment.design_parameters_json,
            equipment.actual_data_json,
            scope=str(equipment.equipment_id),
        ),
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
    """校核人退回 → 回到 PENDING_CONFIRM，重新录入通道解锁（§3.2.4(5)）.

    前置（审查 #5）：状态必须是 CONFIRMED。修复前本函数无条件把状态置回
    PENDING_CONFIRM —— 即「没确认过的设备也能被退回」，凭空打开一条
    绕过录入的写入路径。
    """
    if equipment.actual_data_status != ActualDataStatus.CONFIRMED.value:
        raise PcsError(
            code="ACTUAL_DATA_STATE_CONFLICT",
            message=(
                f"当前状态 {equipment.actual_data_status} 不可退回 —— "
                "只有 CONFIRMED 可退回重录（NOT_ENTERED / PENDING_CONFIRM / "
                "NEEDS_RECALC 均无已确认数据可退）"
            ),
            status=409,
            detail={
                "retryable": False,
                "current_state": equipment.actual_data_status,
                "required_state": ActualDataStatus.CONFIRMED.value,
            },
        )
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
