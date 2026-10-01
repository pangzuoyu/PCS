"""S1-4 EQUIP_LIST 同步服务（sync_from_source）。

SourceModule 触发器：来源记录（如 PUMP 结果）签审为 ``CHECKED`` 时调用，
自动创建 / 更新 ``EquipmentList`` 记录（含 V1.4 ``source_service`` 字段）。

Per D2 裁决 2A: advisory lock per ``(project_id, tag_number)`` 防止两路并发
CHECKED 触发 race condition（INSERT vs UPDATE 竞争）。

用法：
    await sync_from_source(
        source_module="PUMP",
        source_service="pump_service",
        source_record_id=pump.pump_id,
        db=session,
    )
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipment import EquipmentList, EquipmentTypeCode
from app.services.advisory_lock import acquire_equip_list_lock
from app.services.equip_list.source_resolver import get_source_record
from app.services.equip_list.type_code_map import derive_type_code


async def _resolve_type_code_fk(
    project_id: UUID, type_code: str, db: AsyncSession
) -> UUID | None:
    """Resolve composite FK target for ``equipment_type_codes``.

    Final-review I1 fix（升级自 Important 为 Critical）：EquipmentList 复合 FK
    ``(equipment_type_project_id, type_code) → equipment_type_codes(project_id, type_code)``
    要求精确匹配。T1.5 seed 仅 seed 31 个公司级（project_id NULL）codes，
    无项目级 override 时 sync_from_source 直接写 source.project_id 会触发 FK
    违反。

    Resolution priority：
    1. 项目级 ``(source.project_id, type_code)`` — if exists（项目覆写场景）
    2. 公司级 ``(NULL, type_code)`` — T1.5 seed 默认（fallback）

    Returns:
        写入 ``equipment_type_project_id`` 的 project_id 值；
        项目级命中返回 source.project_id，公司级 fallback 返回 None。
    """
    proj_level_stmt = (
        select(EquipmentTypeCode.type_code)
        .where(
            EquipmentTypeCode.project_id == project_id,
            EquipmentTypeCode.type_code == type_code,
        )
        .limit(1)
    )
    if (await db.execute(proj_level_stmt)).first() is not None:
        return project_id
    return None  # 公司级 fallback


async def sync_from_source(
    *,
    source_module: str,
    source_service: str,
    source_record_id: UUID,
    db: AsyncSession,
) -> EquipmentList:
    """PUMP/HEAT/PSV/CV/... CHECKED → EquipmentList 同步（创建 or 更新）。

    步骤：
    1. 加载 source 记录（dispatch source_module）
    2. 校验 source.sign_status == "CHECKED"（否则 raise）
    3. advisory lock per (project_id, tag_number)（D2 裁决 2A）
    4. 查询现有 EquipmentList 同 (project_id, tag_number)：
       - 不存在 → INSERT（equipment_status="N" New）
       - 存在 → UPDATE sign_status + equipment_status="E" Existing
    5. 继承 approval_step / approval_depth（V1.1）
    6. 复合 FK target 解析：项目级 → 公司级 fallback（I1 fix）

    Returns:
        The EquipmentList instance (newly created or updated).

    Raises:
        LookupError: source_record_id 在指定 module 下找不到记录。
        ValueError: source.sign_status 不是 CHECKED；或 source 无 tag_number。
        UnsupportedSourceModuleError: source_module 不在 dispatcher 表内。
    """
    source = await get_source_record(source_module, source_record_id, db)
    if source is None:
        raise LookupError(
            f"source record not found: module={source_module} id={source_record_id}"
        )
    # Accept both enum (RecordSignStatus9.CHECKED) and plain str
    # (SQLite native_enum downgrade; fixture convenience).
    _ss = source.sign_status
    ss_value = _ss.value if hasattr(_ss, "value") else _ss
    if ss_value != "CHECKED":
        raise ValueError(
            f"source record not CHECKED: module={source_module} "
            f"sign_status={ss_value}"
        )

    project_id = source.project_id
    tag_number = source.tag_number
    if tag_number is None:
        raise ValueError(
            f"source has no tag_number: module={source_module} id={source_record_id}"
        )

    await acquire_equip_list_lock(
        db, project_id=project_id, tag_number=tag_number
    )

    existing = (
        await db.execute(
            select(EquipmentList).where(
                EquipmentList.project_id == project_id,
                EquipmentList.tag_number == tag_number,
            )
        )
    ).scalar_one_or_none()

    type_code = derive_type_code(source_module)

    if existing is not None:
        existing.sign_status = source.sign_status
        existing.equipment_status = "E"  # Existing
        existing.approval_step = source.approval_step
        existing.approval_depth = source.approval_depth
        existing.source_module = source_module
        existing.source_service = source_service
        existing.source_record_id = source_record_id
        # I1 fix: 复合 FK target 重解析（项目级 override 可能新增）
        existing.equipment_type_project_id = await _resolve_type_code_fk(
            project_id, type_code, db
        )
        existing.type_code = type_code
        await db.commit()
        await db.refresh(existing)
        return existing

    # I1 fix: 复合 FK target 公司级 fallback
    equipment_type_project_id = await _resolve_type_code_fk(
        project_id, type_code, db
    )
    new_record = EquipmentList(
        equipment_type_project_id=equipment_type_project_id,
        type_code=type_code,
        # mixin 注入字段（TaggedRecordMixin: project_id/workspace_id/tag_number/
        # sign_status/approval_step/approval_depth）
        project_id=project_id,
        workspace_id=source.workspace_id,
        tag_number=tag_number,
        sign_status=source.sign_status,
        approval_step=source.approval_step,
        approval_depth=source.approval_depth,
        # V1.4 来源组
        source_module=source_module,
        source_service=source_service,
        source_record_id=source_record_id,
        # 设备自身
        equipment_name=tag_number,  # 默认用 tag；可后续 update
        equipment_status="N",  # New
    )
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)
    return new_record
