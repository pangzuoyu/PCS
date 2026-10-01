"""S1-4b EQUIP_LIST persist service（bulk_sync + update + list helper）。

Per R8 ruling 补 API 层；sync_service (S1-4) 是主入口，本文件是批量 + 列表查询 helper：
- bulk_sync_from_sources: 批量调用 sync_from_source，partial failure 不中断
- list_equipment_records: 按过滤条件分页查询
- update_equipment_status: 手动 status 调整（N→E/D/M/F）

设计要点：
- bulk_sync 用 try/except per entry；一个失败不影响其他（per API layer brief）
- list helper 返回 (rows, total_count)；total_count 用 SQL COUNT(*) 单独查询
- 不重复 EquipmentList 复合 FK 解析（委托 sync_from_source）
"""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipment import EquipmentList
from app.services.equip_list.sync_service import sync_from_source


async def bulk_sync_from_sources(
    entries: Sequence[dict],
    db: AsyncSession,
) -> tuple[list[EquipmentList], list[dict]]:
    """批量 sync_from_source；partial failure 容错。

    Args:
        entries: list of {source_module, source_service, source_record_id}
        db: AsyncSession

    Returns:
        (succeeded, failed)
        succeeded: list of synced EquipmentList records
        failed: list of {entry, error_code, error_message}
    """
    succeeded: list[EquipmentList] = []
    failed: list[dict] = []
    for entry in entries:
        try:
            result = await sync_from_source(
                source_module=entry["source_module"],
                source_service=entry["source_service"],
                source_record_id=entry["source_record_id"],
                db=db,
            )
            succeeded.append(result)
        except Exception as e:  # noqa: BLE001
            failed.append(
                {
                    "entry": entry,
                    "error_code": type(e).__name__,
                    "error_message": str(e),
                }
            )
    return succeeded, failed


async def list_equipment_records(
    db: AsyncSession,
    *,
    project_id: UUID | None = None,
    workspace_id: UUID | None = None,
    source_module: str | None = None,
    sign_status: str | None = None,
    equipment_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[Sequence[EquipmentList], int]:
    """按过滤条件分页查询 EquipmentList。

    Args:
        db: AsyncSession
        project_id / workspace_id: 可选项目/workspace 过滤
        source_module: 可选源模块过滤
        sign_status / equipment_status: 可选状态过滤
        limit / offset: 分页

    Returns:
        (rows, total_count)
    """
    stmt = select(EquipmentList)
    count_stmt = select(func.count()).select_from(EquipmentList)

    if project_id is not None:
        stmt = stmt.where(EquipmentList.project_id == project_id)
        count_stmt = count_stmt.where(EquipmentList.project_id == project_id)
    if workspace_id is not None:
        stmt = stmt.where(EquipmentList.workspace_id == workspace_id)
        count_stmt = count_stmt.where(EquipmentList.workspace_id == workspace_id)
    if source_module is not None:
        stmt = stmt.where(EquipmentList.source_module == source_module)
        count_stmt = count_stmt.where(EquipmentList.source_module == source_module)
    if sign_status is not None:
        stmt = stmt.where(EquipmentList.sign_status == sign_status)
        count_stmt = count_stmt.where(EquipmentList.sign_status == sign_status)
    if equipment_status is not None:
        stmt = stmt.where(EquipmentList.equipment_status == equipment_status)
        count_stmt = count_stmt.where(
            EquipmentList.equipment_status == equipment_status
        )

    stmt = stmt.order_by(EquipmentList.equipment_id).limit(limit).offset(offset)

    rows = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
    return rows, int(total)


async def update_equipment_status(
    db: AsyncSession,
    *,
    equipment_id: UUID,
    equipment_status: str,
) -> EquipmentList:
    """手动更新 equipment_status（N=New/E=Existing/D=Deleted/M=Modified/F=Frozen）。

    Raises:
        LookupError: equipment_id 不存在
        ValueError: equipment_status 不在合法 5 态内
    """
    valid = {"N", "E", "D", "M", "F"}
    if equipment_status not in valid:
        raise ValueError(
            f"equipment_status {equipment_status!r} 不在合法 5 态内: {sorted(valid)}"
        )
    record = (
        await db.execute(
            select(EquipmentList).where(EquipmentList.equipment_id == equipment_id)
        )
    ).scalar_one_or_none()
    if record is None:
        raise LookupError(f"EquipmentList not found: equipment_id={equipment_id}")
    record.equipment_status = equipment_status
    await db.commit()
    await db.refresh(record)
    return record
