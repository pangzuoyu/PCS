"""COOL_TOWER CoolingTowerResult ORM 落库 service。

按 SPEC §3.2.3 P6-FLR-004：标准 CRUD + sign_status 流（镜像
Task 23 ``flare_persist_service``）。
引用 .wolf/cerebrum.md Do-Not-Repeat 规则：POST API 创建（service 层补必填）→
DB UPDATE 状态字段；避免 ORM kwarg 拼装遗漏 NOT NULL 字段（如 tag_number
NOT NULL / project_id FK 等）。

CoolingTowerResult 字段一览（Task 18 ORM）：
- 业务（10 字段 = 5 平铺 Float + 3 JSONB 容器 + 2 溯源）：
  - 溯源：standard_profile_code（默认 CTI_ATC_105）、calc_type
  - 计算结果：duty_kw / water_flow_m3h / makeup_water_m3h / fan_power_kw /
    merkel_integral
  - JSONB 容器：data_sheet_json / input_json / output_json
- mixin 字段：tag_number (NOT NULL via TaggedRecordMixin), project_id,
  workspace_id, sign_status, record_hash, audit 三件套
  (stale_resolution_path / hash_changed / changed_fields)
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import CoolingTowerResult
from app.models.enums import RecordSignStatus9
from app.services.calc_lineage import finalize_calc_record

# P6-2 Task 25 — cool_tower_persist formula version（与 Task 18 ORM 一致锚点）
_FORMULA_VERSION = "CTPv1.0-p6-2-task25"


class CoolTowerPersistInputError(Exception):
    """cool_tower_persist 输入不合法（422）。"""

    def __init__(
        self,
        message: str,
        code: str = "COOL_TOWER_PERSIST_INPUT_ERROR",
    ):
        super().__init__(message)
        self.message = message
        self.code = code


# CoolingTowerResult 业务字段名白名单（避免 PATCH 越权改 PK / mixin 字段）
# 排除：id / cooling_tower_id / record_hash / created_at / updated_at /
# created_by / audit 字段（sign_status / approval_* / lock_* / change_* /
# obsoleted_* / reversal_* / stale_* / hash_changed / changed_fields）
_COOLTOWER_BUSINESS_FIELDS: frozenset[str] = frozenset(
    {
        "standard_profile_code",  # 溯源
        "calc_type",  # 溯源
        "tower_type",  # 业务
        "duty_kw",  # 业务
        "water_flow_m3h",  # 业务
        "makeup_water_m3h",  # 业务
        "fan_power_kw",  # 业务
        "merkel_integral",  # 业务
        "data_sheet_json",  # JSONB 容器
        "input_json",
        "output_json",
    }
)


# update 可写字段白名单（业务字段子集，不含 2 溯源字段 — PATCH 越权防护）
_COOLTOWER_UPDATE_FIELDS: frozenset[str] = frozenset(
    {
        "tower_type",
        "duty_kw",
        "water_flow_m3h",
        "makeup_water_m3h",
        "fan_power_kw",
        "merkel_integral",
        "data_sheet_json",
        "input_json",
        "output_json",
    }
)


async def save_cool_tower_result(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    standard_profile_code: str,
    payload: dict,
    calc_type: str = "MERKEL",
    sign_status: RecordSignStatus9 = RecordSignStatus9.DRAFT,
    created_by: uuid.UUID | None = None,
) -> CoolingTowerResult:
    """创建 CoolingTowerResult 行（POST 入口）。

    Args:
        session: async SQLAlchemy session。
        project_id: 项目 ID（RecordMixin FK → projects.project_id）。
        workspace_id: 工作区 ID（业务隔离）。
        tag_number: 位号（TaggedRecordMixin NOT NULL）。
        standard_profile_code: 项目标准（C-07 String(16) 锁定；
            默认 "CTI_ATC_105"）。
        calc_type: 计算类型（MERKEL / WATER_BALANCE / FAN_POWER /
            HEAT_AGGREGATE；String(32) NOT NULL）。
        payload: 业务字段 dict（10 字段；键名按 ORM 列名，例：
            duty_kw / fan_power_kw / merkel_integral / data_sheet_json 等）。
        sign_status: 签审状态（默认 DRAFT）。
        created_by: 创建人 UUID（可空）。

    Returns:
        CoolingTowerResult（含 cooling_tower_id / record_hash）。

    Raises:
        CoolTowerPersistInputError: 输入字段不合法（422）。
    """
    if not tag_number or not tag_number.strip():
        raise CoolTowerPersistInputError("tag_number 不能为空")
    if not standard_profile_code or not standard_profile_code.strip():
        raise CoolTowerPersistInputError("standard_profile_code 不能为空")
    if not calc_type or not calc_type.strip():
        raise CoolTowerPersistInputError("calc_type 不能为空")
    if not payload:
        raise CoolTowerPersistInputError("payload 不能为空")

    # 过滤 payload 仅保留业务字段（避免越权写 PK / mixin 字段）
    safe_payload = {
        k: v for k, v in payload.items() if k in _COOLTOWER_BUSINESS_FIELDS
    }
    if not safe_payload:
        raise CoolTowerPersistInputError(
            f"payload 至少包含一个业务字段（{_COOLTOWER_BUSINESS_FIELDS}）"
        )

    record = CoolingTowerResult(
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag_number,
        standard_profile_code=standard_profile_code,
        calc_type=calc_type,
        sign_status=sign_status,
        created_by=created_by,
        **safe_payload,
    )
    session.add(record)
    await session.flush()  # 拿到 cooling_tower_id

    # ADR-0028 §决策 4 record_hash reflection + DataLineage 血缘收口
    # （CoolingTowerResult 是 CONFIG 类计算，无源流；source_stream_ids=[]）
    await finalize_calc_record(
        session,
        record,
        source_stream_ids=[],
        formula_version=_FORMULA_VERSION,
    )

    await session.commit()
    await session.refresh(record)
    return record


async def list_cool_tower_results(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    standard_profile_code: str | None = None,
    sign_status_filter: tuple[RecordSignStatus9, ...] = (
        RecordSignStatus9.DRAFT,
        RecordSignStatus9.CHECKED,
    ),
    limit: int = 100,
    offset: int = 0,
) -> Sequence[CoolingTowerResult]:
    """按 project_id 列出 CoolingTowerResult（GET list）。

    默认 sign_status filter = (DRAFT, CHECKED) — 排除 OBSOLETE/IN_APPROVAL/
    STALE/CHANGE_PENDING/CHANGED/REVERSAL_PENDING/CHECK_REJECTED 等门禁态，
    避免列表展示垃圾数据。Caller 可按需传空 tuple 取消过滤。

    Args:
        session: async SQLAlchemy session。
        project_id: 项目 ID（必填；隔离键）。
        standard_profile_code: 项目标准（可选；二次过滤）。
        sign_status_filter: sign_status 白名单 tuple。
        limit: 分页上限（默认 100）。
        offset: 分页偏移（默认 0）。

    Returns:
        CoolingTowerResult 列表（按 created_at DESC）。
    """
    stmt = select(CoolingTowerResult).where(
        CoolingTowerResult.project_id == project_id,
    )
    if sign_status_filter:
        stmt = stmt.where(
            CoolingTowerResult.sign_status.in_(sign_status_filter)
        )
    if standard_profile_code:
        stmt = stmt.where(
            CoolingTowerResult.standard_profile_code == standard_profile_code
        )
    stmt = (
        stmt.order_by(CoolingTowerResult.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_cool_tower_result(
    session: AsyncSession,
    *,
    record_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> CoolingTowerResult | None:
    """按 record_id 取 CoolingTowerResult（GET detail）。

    Args:
        session: async SQLAlchemy session。
        record_id: CoolingTowerResult.cooling_tower_id（PK UUID）。
        project_id: 项目 ID（可选；ACL 强制 project 隔离）。

    Returns:
        CoolingTowerResult 或 None（不存在 / 项目隔离不匹配时）。
    """
    stmt = select(CoolingTowerResult).where(
        CoolingTowerResult.cooling_tower_id == record_id
    )
    if project_id is not None:
        stmt = stmt.where(CoolingTowerResult.project_id == project_id)
    result = await session.execute(stmt)
    return result.scalars().first()


async def update_cool_tower_result(
    session: AsyncSession,
    *,
    record_id: uuid.UUID,
    payload: dict,
    project_id: uuid.UUID | None = None,
) -> CoolingTowerResult | None:
    """更新 CoolingTowerResult 业务字段（PATCH）。

    仅 DRAFT / CHANGE_PENDING 状态可改（CHECKED / IN_APPROVAL /
    REVERSAL_PENDING 等锁定态拒绝更新，避免评审中数据漂移）。

    注：不重新触发 record_hash 计算；sign_status 流由专用的
    change_pending_flow / state_machine 服务接管。

    Args:
        session: async SQLAlchemy session。
        record_id: CoolingTowerResult.cooling_tower_id。
        payload: 待更新字段 dict（仅业务字段；溯源 / PK / mixin 必填不可写）。
        project_id: 项目 ID（可选；ACL 隔离）。

    Returns:
        CoolingTowerResult（更新后）或 None（不存在 / 隔离不匹配）。

    Raises:
        CoolTowerPersistInputError: 当前 sign_status 不允许 PATCH
            （CHECKED 等锁定态）。
    """
    record = await get_cool_tower_result(
        session, record_id=record_id, project_id=project_id
    )
    if record is None:
        return None
    if record.sign_status not in (
        RecordSignStatus9.DRAFT,
        RecordSignStatus9.CHANGE_PENDING,
    ):
        raise CoolTowerPersistInputError(
            f"sign_status={record.sign_status.value} 不允许 PATCH"
            "（仅 DRAFT/CHANGE_PENDING 可改）",
            code="COOL_TOWER_PERSIST_SIGN_STATUS_LOCKED",
        )

    # 白名单过滤 + 直接 setattr
    for k, v in payload.items():
        if k in _COOLTOWER_UPDATE_FIELDS:
            setattr(record, k, v)
    record.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(record)
    return record


async def soft_delete_cool_tower_result(
    session: AsyncSession,
    *,
    record_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> bool:
    """软删除 CoolingTowerResult（DELETE → sign_status=OBSOLETE）。

    软删而非物理删除（SPEC §3.2.3 P6-FLR-004 审计要求）：
    sign_status=OBSOLETE + stale_resolution_path='COOL_TOWER_RESULT_SOFT_DELETE'
    标记被 list 过滤（DRAFT/CHECKED 默认 filter 排除 OBSOLETE）。

    Args:
        session: async SQLAlchemy session。
        record_id: CoolingTowerResult.cooling_tower_id。
        project_id: 项目 ID（可选；ACL 隔离）。

    Returns:
        True 软删成功；False 不存在 / 隔离不匹配。
    """
    record = await get_cool_tower_result(
        session, record_id=record_id, project_id=project_id
    )
    if record is None:
        return False
    record.sign_status = RecordSignStatus9.OBSOLETE
    record.stale_resolution_path = "COOL_TOWER_RESULT_SOFT_DELETE"
    record.updated_at = datetime.now(UTC)
    await session.commit()
    return True


__all__ = [
    "CoolTowerPersistInputError",
    "save_cool_tower_result",
    "list_cool_tower_results",
    "get_cool_tower_result",
    "update_cool_tower_result",
    "soft_delete_cool_tower_result",
]