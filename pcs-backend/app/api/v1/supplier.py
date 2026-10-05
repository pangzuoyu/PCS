"""供应商实际数据录入 API (P7 Sprint 4 S4-1 / ADR-0025).

端点（4）：
- GET /api/v1/equipment/{equipment_id}/actual-data → 读回录入值
- PUT /api/v1/equipment/{equipment_id}/actual-data → 录入一整台设备的参数集
- GET /api/v1/equipment/{equipment_id}/deviation-report → 偏差报告（SPEC §3.2.4）
- GET /api/v1/equipment/{equipment_id}/deviation-report/export → 导出 excel/pdf

录入入口是**手工 UI 页面**（S4-1 裁决）：要求供应商填统一 Excel 不现实，
故无 Excel 批量导入端点 —— 设备方逐项在页面上录入。

PUT 语义是**整体替换**而非合并：页面上「重录」是覆盖，不是追加；合并会让
上轮残留值混入 S4-2 的偏差计算，而录入者以为已经改过。

ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（VIEWER 只读，走 GET）。
"""

from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.equipment import EquipmentList
from app.schemas.supplier import (
    ActualDataEntryRequest,
    ActualDataResponse,
    CheckRequest,
    ConfirmRequest,
    DeviationReportOut,
    DeviationRowOut,
)
from app.services.supplier.actual_data_service import record_actual_data
# 别名: 端点函数与 service 函数同名 (confirm_actual_data), 直接 import 会把
# service 覆盖掉 —— 端点体内调到的就成了自己。
from app.services.supplier.confirmation_service import (
    confirm_actual_data as confirm_actual_data_svc,
)
from app.services.supplier.confirmation_service import (
    pass_check as pass_check_svc,
)
from app.services.supplier.confirmation_service import (
    reject_check as reject_check_svc,
)
from app.services.supplier.deviation_report import (
    build_report,
    export_excel,
    export_pdf,
)

router = APIRouter(prefix="/equipment", tags=["supplier"])

_WRITE_ROLES = ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
_READ_ROLES = ("VIEWER", "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")


async def _load_equipment(
    db: AsyncSession, equipment_id: uuid.UUID, actor: _Actor
) -> EquipmentList:
    """取设备并校验访问权；查无或无权统一 404（不泄漏存在性）。"""
    record = (
        await db.execute(
            select(EquipmentList).where(EquipmentList.equipment_id == equipment_id)
        )
    ).scalar_one_or_none()
    if record is None:
        # 与 guard 同语义：设备不存在 = 对该 caller 不可见
        raise HTTPException(status_code=404, detail="Equipment not found")
    await check_project_access_or_404(
        db,
        user_id=actor.user_id,
        project_id=record.project_id,
        actor_roles=actor.roles,
    )
    return record


def _to_response(record: EquipmentList) -> ActualDataResponse:
    return ActualDataResponse(
        equipment_id=str(record.equipment_id),
        tag_number=record.tag_number,
        actual_data_status=record.actual_data_status,
        actual_data_json=record.actual_data_json,
    )


@router.get("/{equipment_id}/actual-data", response_model=ActualDataResponse)
async def get_actual_data(
    equipment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> ActualDataResponse:
    """读回设备实测值。未录入时 actual_data_json 为 null。"""
    require_roles(actor, *_READ_ROLES)
    record = await _load_equipment(db, equipment_id, actor)
    return _to_response(record)


@router.put("/{equipment_id}/actual-data", response_model=ActualDataResponse)
async def put_actual_data(
    equipment_id: uuid.UUID,
    body: ActualDataEntryRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> ActualDataResponse:
    """录入一整台设备的参数集（整体替换），状态转 PENDING_CONFIRM。

    PcsError ACTUAL_DATA_VALIDATION 422 由全局 handler 转 422 —— UI 逐项
    提示，不静默丢值。
    """
    require_roles(actor, *_WRITE_ROLES)
    record = await _load_equipment(db, equipment_id, actor)
    updated = await record_actual_data(
        db, record, [e.model_dump() for e in body.entries]
    )
    return _to_response(updated)


# ---------------------------------------------------------------------------
# 偏差报告 (SPEC V1.4 §3.2.4)
# ---------------------------------------------------------------------------


def _report_to_response(report) -> DeviationReportOut:
    return DeviationReportOut(
        equipment_id=report.equipment_id,
        tag_number=report.tag_number,
        actual_data_status=report.actual_data_status,
        rows=[DeviationRowOut.model_validate(r) for r in report.rows],
        can_confirm=report.can_confirm,
        blocking_reason=report.blocking_reason,
    )


@router.get("/{equipment_id}/deviation-report", response_model=DeviationReportOut)
async def get_deviation_report(
    equipment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> DeviationReportOut:
    """设计值 vs 实际值偏差报告（SPEC §3.2.4(3)）。

    `can_confirm` 是 SPEC §3.2.4(4) 的确认门禁 —— 存在不合格或不可判项时
    为 false，前端据此禁用「已确认」。

    ⚠️ 已知缺口：`design_parameters_json` 目前无写入方，故生产路径上全部行
    都会落「缺设计值（不可判）」。引擎已按 SPEC 逐条实现，设计值来源待定。
    """
    require_roles(actor, *_READ_ROLES)
    record = await _load_equipment(db, equipment_id, actor)
    return _report_to_response(build_report(record))


_EXPORT_TYPES = {
    "excel": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx",
    ),
    "pdf": ("application/pdf", "pdf"),
}


# ---------------------------------------------------------------------------
# 核算与更新流程 (SPEC V1.4 §3.2.4(4))
# ---------------------------------------------------------------------------

# 设计人（录入/确认）与校核人是**两个角色** —— 同一人既提交又校核等于没有校核。
_CONFIRM_ROLES = ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
_CHECK_ROLES = ("REVIEWER", "APPROVER", "SYSTEM_ADMIN")


@router.post("/{equipment_id}/actual-data/confirm", response_model=ActualDataResponse)
async def confirm_actual_data(
    equipment_id: uuid.UUID,
    body: ConfirmRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> ActualDataResponse:
    """设计人勾选「确认实际数据满足工艺要求」并提交校核（SPEC §3.2.4(4)）.

    存在不合格或不可判项 → 422 `DEVIATION_BLOCKS_CONFIRMATION`。
    """
    require_roles(actor, *_CONFIRM_ROLES)
    record = await _load_equipment(db, equipment_id, actor)
    await confirm_actual_data_svc(db, record, actor, reason=body.reason)
    return _to_response(record)


@router.post("/{equipment_id}/actual-data/check", response_model=ActualDataResponse)
async def check_actual_data(
    equipment_id: uuid.UUID,
    body: CheckRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> ActualDataResponse:
    """校核人校核（SPEC §3.2.4(4)）.

    - `pass` → 标记 CONFIRMED，并发 `actual_data_replaces_design` 事件
      （`before` 必带 —— P8 反向恢复的唯一来源）
    - `reject` → 退回 PENDING_CONFIRM，重新录入通道解锁（§3.2.4(5)）
    """
    require_roles(actor, *_CHECK_ROLES)
    record = await _load_equipment(db, equipment_id, actor)
    if body.decision == "pass":
        await pass_check_svc(db, record, actor, reason=body.reason)
    else:
        await reject_check_svc(db, record, actor, reason=body.reason)
    return _to_response(record)


@router.get("/{equipment_id}/deviation-report/export")
async def export_deviation_report(
    equipment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
    format: Annotated[str, Query(pattern="^(excel|pdf)$")],
) -> Response:
    """导出偏差报告（SPEC §3.2.4(3)「可导出PDF/Excel」）。

    文件名走 RFC 5987 `filename*` 编码 —— 设备位号可能含中文，直接塞进
    `filename` 会被部分浏览器丢弃。
    """
    require_roles(actor, *_READ_ROLES)
    record = await _load_equipment(db, equipment_id, actor)
    report = build_report(record)

    if format == "excel":
        content = export_excel(report)
        media_type, ext = _EXPORT_TYPES["excel"]
    else:
        content = export_pdf(report)
        media_type, ext = _EXPORT_TYPES["pdf"]

    safe_tag = quote(record.tag_number, safe="")
    filename = f"deviation-report-{safe_tag}.{ext}"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="deviation-report.{ext}"; '
                f"filename*=UTF-8''{filename}"
            )
        },
    )
