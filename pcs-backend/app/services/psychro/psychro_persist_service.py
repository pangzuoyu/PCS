"""PSYCHRO PsychroResult ORM 落库 service（P6-2 Task 26）。

按 SPEC §3.2.3 P6-FLR-004：标准 CRUD + sign_status 流（镜像 Task 25
``cool_tower_persist_service``）。
引用 .wolf/cerebrum.md Do-Not-Repeat 规则：POST API 创建（service 层补必填）→
DB UPDATE 状态字段；避免 ORM kwarg 拼装遗漏必填字段（tag_number NOT NULL /
project_id FK / workspace_id）。

PsychroResult 字段一览（Task 18 ORM）：
- 业务（15 字段 = 11 平铺 Float + 2 JSONB 容器 + 2 溯源）：
  - 溯源：standard_profile_code（默认 ASHRAE_FUND_2021）、calc_type、
    coolprop_version（自动从 get_coolprop_version() 写入）
  - 计算结果（6 calc_type 各自 result）：
    humidity_ratio_kg_kg / dew_point_c / wet_bulb_c / enthalpy_kj_kg /
    specific_volume_m3_kg / sensible_heat_kw / latent_heat_kw
  - P6-4 Task 4（C-17 显式水含量 4 列；SATURATION_W_CALC calc_type）：
    saturation_w_kg_kg / saturation_w_mg_sm3 / saturation_w_lb_per_mmscf /
    saturation_T_c
  - JSONB 容器：input_json / output_json
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

from app.models.calc import PsychroResult
from app.models.enums import RecordSignStatus9
from app.services.calc_lineage import finalize_calc_record
from app.services.psychro.coolprop_version import get_coolprop_version

# P6-2 Task 26 — psychro_persist formula version（与 Task 18 ORM 一致锚点）
_FORMULA_VERSION = "PSYv1.0-p6-2-task26"


class PsychroPersistInputError(Exception):
    """psychro_persist 输入不合法（422）。"""

    def __init__(
        self,
        message: str,
        code: str = "PSYCHRO_PERSIST_INPUT_ERROR",
    ):
        super().__init__(message)
        self.message = message
        self.code = code


# PsychroResult 业务字段名白名单（避免 PATCH 越权改 PK / mixin 字段）
# 排除：id / psychro_id / record_hash / created_at / updated_at /
# created_by / audit 字段（sign_status / approval_* / lock_* / change_* /
# obsoleted_* / reversal_* / stale_* / hash_changed / changed_fields）
_PSYCHRO_BUSINESS_FIELDS: frozenset[str] = frozenset(
    {
        "standard_profile_code",  # 溯源
        "calc_type",  # 溯源
        "coolprop_version",  # 溯源（payload 缺时自动填）
        "humidity_ratio_kg_kg",  # 业务
        "dew_point_c",  # 业务
        "wet_bulb_c",  # 业务
        "enthalpy_kj_kg",  # 业务
        "specific_volume_m3_kg",  # 业务
        "sensible_heat_kw",  # 业务（cooling_coil 专用）
        "latent_heat_kw",  # 业务（cooling_coil 专用）
        # P6-4 Task 4 (C-17) — SATURATION_W_CALC calc_type 4 业务列
        "saturation_w_kg_kg",  # 业务（饱和 W kg/kg dry air）
        "saturation_w_mg_sm3",  # 业务（饱和 W mg/Sm³ dry air）
        "saturation_w_lb_per_mmscf",  # 业务（饱和 W lb/MMscf dry air）
        "saturation_T_c",  # 业务（饱和温度 °C）
        "input_json",  # JSONB
        "output_json",  # JSONB
    }
)


# update 可写字段白名单（业务字段子集，不含 3 溯源字段 — PATCH 越权防护）
_PSYCHRO_UPDATE_FIELDS: frozenset[str] = frozenset(
    {
        "humidity_ratio_kg_kg",
        "dew_point_c",
        "wet_bulb_c",
        "enthalpy_kj_kg",
        "specific_volume_m3_kg",
        "sensible_heat_kw",
        "latent_heat_kw",
        # P6-4 Task 4 (C-17) — SATURATION_W_CALC 4 业务列
        "saturation_w_kg_kg",
        "saturation_w_mg_sm3",
        "saturation_w_lb_per_mmscf",
        "saturation_T_c",
        "input_json",
        "output_json",
    }
)


async def save_psychro_result(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    standard_profile_code: str,
    payload: dict,
    calc_type: str = "HUMIDITY_RATIO",
    sign_status: RecordSignStatus9 = RecordSignStatus9.DRAFT,
    created_by: uuid.UUID | None = None,
) -> PsychroResult:
    """创建 PsychroResult 行（POST 入口）。

    Args:
        session: async SQLAlchemy session。
        project_id: 项目 ID（RecordMixin FK → projects.project_id）。
        workspace_id: 工作区 ID（业务隔离）。
        tag_number: 位号（TaggedRecordMixin NOT NULL）。
        standard_profile_code: 项目标准（C-07 String(16) 锁定；
            默认 "ASHRAE_FUND_2021"）。
        calc_type: 计算类型（HUMIDITY_RATIO / DEW_POINT / WET_BULB /
            ENTHALPY / SPECIFIC_VOLUME / COOLING_COIL；String(32) NOT NULL）。
        payload: 业务字段 dict（12 字段；键名按 ORM 列名）。
        sign_status: 签审状态（默认 DRAFT）。
        created_by: 创建人 UUID（可空）。

    Returns:
        PsychroResult（含 psychro_id / record_hash）。

    Raises:
        PsychroPersistInputError: 输入字段不合法（422）。

    关键约束：
        - **coolprop_version 自动填**：payload 未含 coolprop_version 时，
          service 层从 ``get_coolprop_version()`` 兜底写入（SPEC §3.2.5
          coolprop_version 溯源要求）。
        - **finalize_calc_record**：自动落 record_hash reflection +
          DataLineage 血缘（ADR-0028 §决策 4）；PsychroResult 是 CONFIG
          类计算，无源流，``source_stream_ids=[]``。
    """
    if not tag_number or not tag_number.strip():
        raise PsychroPersistInputError("tag_number 不能为空")
    if not standard_profile_code or not standard_profile_code.strip():
        raise PsychroPersistInputError("standard_profile_code 不能为空")
    if not calc_type or not calc_type.strip():
        raise PsychroPersistInputError("calc_type 不能为空")
    if not payload:
        raise PsychroPersistInputError("payload 不能为空")

    # 过滤 payload 仅保留业务字段（避免越权写 PK / mixin 字段）
    safe_payload = {
        k: v for k, v in payload.items() if k in _PSYCHRO_BUSINESS_FIELDS
    }
    if not safe_payload:
        raise PsychroPersistInputError(
            f"payload 至少包含一个业务字段（{_PSYCHRO_BUSINESS_FIELDS}）"
        )

    # coolprop_version 溯源自动填（payload 缺时由 service 层兜底）
    if not safe_payload.get("coolprop_version"):
        safe_payload["coolprop_version"] = get_coolprop_version()

    record = PsychroResult(
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
    await session.flush()  # 拿到 psychro_id

    # ADR-0028 §决策 4 record_hash reflection + DataLineage 血缘收口
    # （PsychroResult 是 CONFIG 类计算，无源流；source_stream_ids=[]）
    await finalize_calc_record(
        session,
        record,
        source_stream_ids=[],
        formula_version=_FORMULA_VERSION,
    )

    await session.commit()
    await session.refresh(record)
    return record


async def list_psychro_results(
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
) -> Sequence[PsychroResult]:
    """按 project_id 列出 PsychroResult（GET list）。

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
        PsychroResult 列表（按 created_at DESC）。
    """
    stmt = select(PsychroResult).where(
        PsychroResult.project_id == project_id,
    )
    if sign_status_filter:
        stmt = stmt.where(
            PsychroResult.sign_status.in_(sign_status_filter)
        )
    if standard_profile_code:
        stmt = stmt.where(
            PsychroResult.standard_profile_code == standard_profile_code
        )
    stmt = (
        stmt.order_by(PsychroResult.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_psychro_result(
    session: AsyncSession,
    *,
    record_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> PsychroResult | None:
    """按 record_id 取 PsychroResult（GET detail）。

    Args:
        session: async SQLAlchemy session。
        record_id: PsychroResult.psychro_id（PK UUID）。
        project_id: 项目 ID（可选；ACL 强制 project 隔离）。

    Returns:
        PsychroResult 或 None（不存在 / 项目隔离不匹配时）。
    """
    stmt = select(PsychroResult).where(PsychroResult.psychro_id == record_id)
    if project_id is not None:
        stmt = stmt.where(PsychroResult.project_id == project_id)
    result = await session.execute(stmt)
    return result.scalars().first()


async def update_psychro_result(
    session: AsyncSession,
    *,
    record_id: uuid.UUID,
    payload: dict,
    project_id: uuid.UUID | None = None,
) -> PsychroResult | None:
    """更新 PsychroResult 业务字段（PATCH）。

    仅 DRAFT / CHANGE_PENDING 状态可改（CHECKED / IN_APPROVAL /
    REVERSAL_PENDING 等锁定态拒绝更新，避免评审中数据漂移）。

    注：不重新触发 record_hash 计算；sign_status 流由专用的
    change_pending_flow / state_machine 服务接管。

    Args:
        session: async SQLAlchemy session。
        record_id: PsychroResult.psychro_id。
        payload: 待更新字段 dict（仅业务字段；溯源 / PK / mixin 必填不可写）。
        project_id: 项目 ID（可选；ACL 隔离）。

    Returns:
        PsychroResult（更新后）或 None（不存在 / 隔离不匹配）。

    Raises:
        PsychroPersistInputError: 当前 sign_status 不允许 PATCH
            （CHECKED 等锁定态）。
    """
    record = await get_psychro_result(
        session, record_id=record_id, project_id=project_id
    )
    if record is None:
        return None
    if record.sign_status not in (
        RecordSignStatus9.DRAFT,
        RecordSignStatus9.CHANGE_PENDING,
    ):
        raise PsychroPersistInputError(
            f"sign_status={record.sign_status.value} 不允许 PATCH"
            "（仅 DRAFT/CHANGE_PENDING 可改）",
            code="PSYCHRO_PERSIST_SIGN_STATUS_LOCKED",
        )

    # 白名单过滤 + 直接 setattr
    for k, v in payload.items():
        if k in _PSYCHRO_UPDATE_FIELDS:
            setattr(record, k, v)
    record.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(record)
    return record


async def soft_delete_psychro_result(
    session: AsyncSession,
    *,
    record_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> bool:
    """软删除 PsychroResult（DELETE → sign_status=OBSOLETE）。

    软删而非物理删除（SPEC §3.2.3 P6-FLR-004 审计要求）：
    sign_status=OBSOLETE + stale_resolution_path='PSYCHRO_RESULT_SOFT_DELETE'
    标记被 list 过滤（DRAFT/CHECKED 默认 filter 排除 OBSOLETE）。

    Args:
        session: async SQLAlchemy session。
        record_id: PsychroResult.psychro_id。
        project_id: 项目 ID（可选；ACL 隔离）。

    Returns:
        True 软删成功；False 不存在 / 隔离不匹配。
    """
    record = await get_psychro_result(
        session, record_id=record_id, project_id=project_id
    )
    if record is None:
        return False
    record.sign_status = RecordSignStatus9.OBSOLETE
    record.stale_resolution_path = "PSYCHRO_RESULT_SOFT_DELETE"
    record.updated_at = datetime.now(UTC)
    await session.commit()
    return True


__all__ = [
    "PsychroPersistInputError",
    "save_psychro_result",
    "list_psychro_results",
    "get_psychro_result",
    "update_psychro_result",
    "soft_delete_psychro_result",
]
