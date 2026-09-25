"""FILTRATION 计算结果持久化服务（SPEC §3.2.7）。

依据：Task 33 3 calc 模块（ruth_constant_pressure / ruth_constant_rate /
ergun）+ Task 30 FiltrationResult ORM 11 字段（含 PK filter_id + 4 既有
业务字段 + 6 派生字段）。

服务函数（8 个）：
- 3 save：save_ruth_constant_pressure_result / save_ruth_constant_rate_result /
  save_ergun_result
- 5 CRUD（统一 _service 后缀别名；与 P5-3/Task 25 cool_tower 一致）：
    list_filtration_results_service / get_filtration_result_service /
    update_filtration_result_service / soft_delete_filtration_result_service /
    create_filtration_result_direct（不走 calc，直接落库入口）

公式版本：FILv1.0-p6-3-task34（与 Task 18 flare/cool_tower/psychro ORM
一致锚点；Task 33 calc 模块同版本号）。

Do-Not-Repeat：
- TaggedRecordMixin：tag_number NOT NULL（unique per project）+ project_id +
  workspace_id；service 层负责补齐必填，不允许 endpoint 直构
  FiltrationResult。
- ADR-0022：outlet stream（FILTRATION 不创建 outlet stream，无中间物流）。
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import FiltrationResult
from app.models.enums import RecordSignStatus9
from app.services.calc_lineage import finalize_calc_record

# P6-3 Task 34 — filtration_persist formula version
_FORMULA_VERSION = "FILv1.0-p6-3-task34"


class FiltrationPersistInputError(Exception):
    """FILTRATION 持久化输入不合法（422）。

    触发场景：
    - tag_number 为空
    - area <= 0 / pressure_drop <= 0 / cycle_time < 0 越界
    - PATCH 字段不在 _FILTRATION_UPDATE_FIELDS 白名单
    - DRAFT / CHANGE_PENDING 之外状态拒绝 PATCH
    - record_id 不存在
    """

    def __init__(
        self,
        message: str,
        code: str = "FILTRATION_PERSIST_INPUT_ERROR",
    ):
        super().__init__(message)
        self.message = message
        self.code = code


# FiltrationResult 业务字段白名单（PATCH 可写）
# 排除 PK（filter_id）/ mixin 必填（project_id / workspace_id /
# tag_number / sign_status / created_by / record_hash / stale_resolution_path
# / created_at / updated_at）；与 ORM 11 业务字段一致。
_FILTRATION_UPDATE_FIELDS: frozenset[str] = frozenset(
    {
        "filter_type",
        "media_type",
        "area",
        "cycle_time",
        "pressure_drop",
        "cake_resistance_alpha",
        "specific_resistance_r0",
        "permeability_k",
        "porosity_eps",
        "filter_velocity",
    }
)


# ============================================================================
# 1. 3 save 函数（按 calc 模块 1:1 对应；service 层补必填）
# ============================================================================


async def save_ruth_constant_pressure_result(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    media_type: str,
    area: float,
    cycle_time: float,
    pressure_drop: float,
    cake_resistance_alpha: float | None = None,
    specific_resistance_r0: float | None = None,
    filter_velocity: float | None = None,
    created_by: uuid.UUID | None = None,
) -> FiltrationResult:
    """落库 Ruth 恒压过滤结果（§3.2.7 第一项）。

    Args:
        session: async SQLAlchemy session。
        project_id: 项目 ID（RecordMixin FK）。
        workspace_id: 工作区 ID（业务隔离）。
        tag_number: 位号（TaggedRecordMixin NOT NULL，per-project 唯一）。
        media_type: 介质代码（SAND/ANTHRACITE/CARBON/RUTH_FILTER_CLOTH/
            ERGUN_PACKING；对应 G-05 filtration_media_library.code）。
        area: 过滤面积 A（m²，>0）。
        cycle_time: 过滤周期（h，≥0）。
        pressure_drop: 压降（Pa，>0）。
        cake_resistance_alpha: 滤饼比阻 α（m/kg，可空）。
        specific_resistance_r0: 介质单位阻力 R₀（1/m，可空）。
        filter_velocity: 过滤速率（m/s，可空）。
        created_by: 创建人 UUID。

    Returns:
        FiltrationResult（含 filter_id / record_hash）。

    Raises:
        FiltrationPersistInputError: 输入字段缺失或越界（422）。
    """
    if not tag_number or not isinstance(tag_number, str):
        raise FiltrationPersistInputError("tag_number 必须为非空字符串")
    if area <= 0 or cycle_time < 0 or pressure_drop <= 0:
        raise FiltrationPersistInputError(
            "area > 0 且 cycle_time ≥ 0 且 pressure_drop > 0"
        )

    record = FiltrationResult(
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag_number,
        filter_type="RUTH_CONST_PRESSURE",
        media_type=media_type,
        area=area,
        cycle_time=cycle_time,
        pressure_drop=pressure_drop,
        cake_resistance_alpha=cake_resistance_alpha,
        specific_resistance_r0=specific_resistance_r0,
        filter_velocity=filter_velocity,
        sign_status=RecordSignStatus9.DRAFT,
        created_by=created_by,
    )
    session.add(record)
    await session.flush()  # 拿到 filter_id

    # ADR-0028 §决策 4 record_hash reflection + DataLineage 血缘收口
    # （FILTRATION 是 CONFIG 类计算，无源流；source_stream_ids=[]）
    await finalize_calc_record(
        session,
        record,
        source_stream_ids=[],
        formula_version=_FORMULA_VERSION,
    )
    await session.commit()
    await session.refresh(record)
    return record


async def save_ruth_constant_rate_result(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    media_type: str,
    area: float,
    cycle_time: float,
    pressure_drop: float,
    cake_resistance_alpha: float | None = None,
    specific_resistance_r0: float | None = None,
    filter_velocity: float | None = None,
    created_by: uuid.UUID | None = None,
) -> FiltrationResult:
    """落库 Ruth 恒速过滤结果（§3.2.7 第二项）。

    与 save_ruth_constant_pressure_result 镜像；区别仅在于 filter_type
    写为 "RUTH_CONST_RATE"（恒速泵入/吸滤场景）。
    """
    if not tag_number or not isinstance(tag_number, str):
        raise FiltrationPersistInputError("tag_number 必须为非空字符串")
    if area <= 0 or cycle_time < 0 or pressure_drop <= 0:
        raise FiltrationPersistInputError(
            "area > 0 且 cycle_time ≥ 0 且 pressure_drop > 0"
        )

    record = FiltrationResult(
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag_number,
        filter_type="RUTH_CONST_RATE",
        media_type=media_type,
        area=area,
        cycle_time=cycle_time,
        pressure_drop=pressure_drop,
        cake_resistance_alpha=cake_resistance_alpha,
        specific_resistance_r0=specific_resistance_r0,
        filter_velocity=filter_velocity,
        sign_status=RecordSignStatus9.DRAFT,
        created_by=created_by,
    )
    session.add(record)
    await session.flush()

    await finalize_calc_record(
        session,
        record,
        source_stream_ids=[],
        formula_version=_FORMULA_VERSION,
    )
    await session.commit()
    await session.refresh(record)
    return record


async def save_ergun_result(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    media_type: str,
    area: float,
    cycle_time: float,
    pressure_drop: float,
    permeability_k: float | None = None,
    porosity_eps: float | None = None,
    filter_velocity: float | None = None,
    created_by: uuid.UUID | None = None,
) -> FiltrationResult:
    """落库 Ergun 介质阻力结果（§3.2.7 第三项 — 深层过滤）。

    额外填 permeability_k（m²）/ porosity_eps（无量纲，0~1）。media_type
    通常为 ERGUN_PACKING 或 SAND/ANTHRACITE/CARBON（来自
    filtration_media_library G-05）。
    """
    if not tag_number or not isinstance(tag_number, str):
        raise FiltrationPersistInputError("tag_number 必须为非空字符串")
    if area <= 0 or cycle_time < 0 or pressure_drop <= 0:
        raise FiltrationPersistInputError(
            "area > 0 且 cycle_time ≥ 0 且 pressure_drop > 0"
        )
    if porosity_eps is not None and not (0 < porosity_eps < 1):
        raise FiltrationPersistInputError(
            "porosity_eps 必须在 (0, 1) 严格开区间"
        )

    record = FiltrationResult(
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag_number,
        filter_type="ERGUN_DEEP_BED",
        media_type=media_type,
        area=area,
        cycle_time=cycle_time,
        pressure_drop=pressure_drop,
        permeability_k=permeability_k,
        porosity_eps=porosity_eps,
        filter_velocity=filter_velocity,
        sign_status=RecordSignStatus9.DRAFT,
        created_by=created_by,
    )
    session.add(record)
    await session.flush()

    await finalize_calc_record(
        session,
        record,
        source_stream_ids=[],
        formula_version=_FORMULA_VERSION,
    )
    await session.commit()
    await session.refresh(record)
    return record


# ============================================================================
# 2. 5 CRUD 函数（统一 _service 后缀别名）
# ============================================================================


async def list_filtration_results_service(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    include_obsolete: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[FiltrationResult]:
    """按 project_id 列出 FiltrationResult（GET list）。

    默认 ``include_obsolete=False`` → 过滤 sign_status == OBSOLETE。
    按 created_at DESC 排序 + skip/limit 分页。

    Args:
        session: async SQLAlchemy session。
        project_id: 项目 ID（必填；隔离键）。
        include_obsolete: 是否包含 OBSOLETE（默认 False）。
        skip: 分页偏移（默认 0）。
        limit: 分页上限（默认 50；brief 推荐 ≤200）。

    Returns:
        FiltrationResult 列表。
    """
    stmt = select(FiltrationResult).where(
        FiltrationResult.project_id == project_id,
    )
    if not include_obsolete:
        stmt = stmt.where(
            FiltrationResult.sign_status != RecordSignStatus9.OBSOLETE
        )
    stmt = (
        stmt.order_by(FiltrationResult.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_filtration_result_service(
    session: AsyncSession,
    *,
    result_id: uuid.UUID,
) -> FiltrationResult:
    """按 filter_id 取 FiltrationResult（GET detail）。

    Returns:
        FiltrationResult。

    Raises:
        FiltrationPersistInputError: record 不存在（FILTRATION_NOT_FOUND）。
    """
    record = await session.get(FiltrationResult, result_id)
    if record is None:
        raise FiltrationPersistInputError(
            f"FILTRATION result {result_id} 不存在",
            code="FILTRATION_NOT_FOUND",
        )
    return record


async def update_filtration_result_service(
    session: AsyncSession,
    *,
    result_id: uuid.UUID,
    patch: dict,
) -> FiltrationResult:
    """PATCH 锁定业务字段。

    仅 DRAFT / CHANGE_PENDING 可改；CHECKED / IN_APPROVAL 等锁定态拒绝。
    字段白名单：_FILTRATION_UPDATE_FIELDS。

    Returns:
        FiltrationResult（更新后）。

    Raises:
        FiltrationPersistInputError: 记录不存在 / 字段越界 / 锁定态。
    """
    record = await get_filtration_result_service(
        session, result_id=result_id
    )
    if record.sign_status not in (
        RecordSignStatus9.DRAFT,
        RecordSignStatus9.CHANGE_PENDING,
    ):
        raise FiltrationPersistInputError(
            f"sign_status={record.sign_status.value} 不允许 PATCH "
            "（仅 DRAFT/CHANGE_PENDING 可改）",
            code="FILTRATION_LOCKED",
        )
    invalid = set(patch.keys()) - _FILTRATION_UPDATE_FIELDS
    if invalid:
        raise FiltrationPersistInputError(
            f"非法字段: {sorted(invalid)}；只允许 "
            f"{sorted(_FILTRATION_UPDATE_FIELDS)}",
            code="FILTRATION_INVALID_FIELDS",
        )
    for k, v in patch.items():
        setattr(record, k, v)
    record.stale_resolution_path = "service_layer_update"
    record.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(record)
    return record


async def soft_delete_filtration_result_service(
    session: AsyncSession,
    *,
    result_id: uuid.UUID,
) -> FiltrationResult:
    """软删除 FiltrationResult（DELETE → sign_status=OBSOLETE）。

    位号终身锁定：tag_number 加 ``__OBSOLETE_<unix_ts>`` 后缀，保留原
    tag_number 历史溯源；stale_resolution_path='service_layer_soft_delete'。
    后续 list 默认不命中（OBSOLETE 被过滤）。

    Returns:
        FiltrationResult（已 OBSOLETE）。

    Raises:
        FiltrationPersistInputError: 记录不存在。
    """
    record = await get_filtration_result_service(
        session, result_id=result_id
    )
    record.sign_status = RecordSignStatus9.OBSOLETE
    record.tag_number = (
        f"{record.tag_number}__OBSOLETE_{int(datetime.now(UTC).timestamp())}"
    )
    record.stale_resolution_path = "service_layer_soft_delete"
    record.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(record)
    return record


async def create_filtration_result_direct(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    created_by: uuid.UUID | None = None,
    **payload,
) -> FiltrationResult:
    """直接 service 入口（不走 calc）创建 FiltrationResult。

    用于"前端填业务字段直接保存"的场景（非 calc-driven）。所有业务字段
    通过 kwargs 传入；越权字段（PK / mixin / audit）拒绝。

    Returns:
        FiltrationResult。

    Raises:
        FiltrationPersistInputError: tag_number 空 / 字段越界。
    """
    if not tag_number or not isinstance(tag_number, str):
        raise FiltrationPersistInputError("tag_number 必须为非空字符串")
    invalid = set(payload.keys()) - _FILTRATION_UPDATE_FIELDS
    if invalid:
        raise FiltrationPersistInputError(
            f"非法字段: {sorted(invalid)}；只允许 "
            f"{sorted(_FILTRATION_UPDATE_FIELDS)}",
            code="FILTRATION_INVALID_FIELDS",
        )

    record = FiltrationResult(
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag_number,
        sign_status=RecordSignStatus9.DRAFT,
        created_by=created_by,
        **payload,
    )
    session.add(record)
    await session.flush()

    await finalize_calc_record(
        session,
        record,
        source_stream_ids=[],
        formula_version=_FORMULA_VERSION,
    )
    await session.commit()
    await session.refresh(record)
    return record


__all__ = [
    "FiltrationPersistInputError",
    # 3 save
    "save_ruth_constant_pressure_result",
    "save_ruth_constant_rate_result",
    "save_ergun_result",
    # 5 CRUD
    "list_filtration_results_service",
    "get_filtration_result_service",
    "update_filtration_result_service",
    "soft_delete_filtration_result_service",
    "create_filtration_result_direct",
]