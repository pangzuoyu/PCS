"""OPEN_CHANNEL 计算结果持久化服务（SPEC §3.2.6 P6-OPEN-001）。

依据：Task 31 4 calc 模块（manning/section/critical/jump）+ Task 30
OpenChannelResult ORM 14 字段。

服务函数（11 个）：
- 4 save（按 calc 模块 1:1 对应）：
    save_manning_result / save_section_result / save_critical_result /
    save_jump_result
- 5 CRUD（统一 _service 后缀别名；与 P5-3/Task 25 cool_tower 一致）：
    list_open_channel_results_service / get_open_channel_result_service /
    update_open_channel_result_service / soft_delete_open_channel_result_service /
    create_open_channel_result_direct（不走 calc，直接落库入口）

公式版本：OCv1.0-p6-3-task32（与 Task 18 flare/cool_tower/psychro ORM 一致锚点）

Do-Not-Repeat：
- TaggedRecordMixin：tag_number NOT NULL（unique per project）+ project_id +
  workspace_id；service 层负责补齐必填，不允许 endpoint 直构 OpenChannelResult。
- ADR-0022：outlet stream（OPEN_CHANNEL 不创建 outlet stream，无中间物流）。
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import OpenChannelResult
from app.models.enums import RecordSignStatus9
from app.services.calc_lineage import finalize_calc_record

# P6-3 Task 32 — open_channel_persist formula version
_FORMULA_VERSION = "OCv1.0-p6-3-task32"


class OpenChannelPersistInputError(Exception):
    """OPEN_CHANNEL 持久化输入不合法（422）。

    触发场景：
    - tag_number 为空
    - channel_type 不在 RECT/TRAP/CIRC 集合
    - flow_rate / depth / velocity / slope 越界（<0）
    - PATCH 字段不在 _OPENCHANNEL_UPDATE_FIELDS 白名单
    - CHECKED 锁定态拒绝 PATCH
    - record_id 不存在
    """

    def __init__(
        self,
        message: str,
        code: str = "OPEN_CHANNEL_PERSIST_INPUT_ERROR",
    ):
        super().__init__(message)
        self.message = message
        self.code = code


# OpenChannelResult 业务字段白名单（PATCH 可写）
# 排除 PK / mixin 必填 / 审计字段；与 ORM 14 字段一致（task_number 通过
# TaggedRecordMixin NOT NULL 强制；soft_delete 时改 tag_number 后缀）
_OPENCHANNEL_UPDATE_FIELDS: frozenset[str] = frozenset(
    {
        "channel_type",
        "cross_section_json",
        "flow_rate",
        "depth",
        "velocity",
        "slope",
        "critical_depth",
        "froude_number",
        "manning_n",
        "hydraulic_radius",
        "jump_type",
        "conjugate_depth",
        "energy_loss",
    }
)


# ============================================================================
# 1. 4 save 函数（按 calc 模块 1:1 对应；service 层补必填）
# ============================================================================


async def save_manning_result(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    channel_type: str,
    cross_section_json: dict,
    flow_rate: float,
    depth: float,
    velocity: float,
    slope: float,
    hydraulic_radius: float | None = None,
    manning_n: float | None = None,
    created_by: uuid.UUID | None = None,
) -> OpenChannelResult:
    """落库 Manning 公式流量计算结果（§3.2.6 第一项）。

    Args:
        session: async SQLAlchemy session。
        project_id: 项目 ID（RecordMixin FK）。
        workspace_id: 工作区 ID（业务隔离）。
        tag_number: 位号（TaggedRecordMixin NOT NULL，per-project 唯一）。
        channel_type: 'RECT' / 'TRAP' / 'CIRC'。
        cross_section_json: 断面几何 {bottom_width, side_slope, diameter}。
        flow_rate: 流量 Q（m³/s，≥0）。
        depth: 水深 h（m，≥0；来自 calc ManningResult.area）。
        velocity: 流速 v（m/s，≥0；来自 calc ManningResult.velocity）。
        slope: 坡度 S（m/m，≥0）。
        hydraulic_radius: 水力半径 R（m，可空；来自 calc ManningResult.hydraulic_radius）。
        manning_n: 糙率 n（可空；来自请求）。
        created_by: 创建人 UUID。

    Returns:
        OpenChannelResult（含 open_channel_id / record_hash）。

    Raises:
        OpenChannelPersistInputError: 输入字段缺失或越界（422）。
    """
    if not tag_number or not isinstance(tag_number, str):
        raise OpenChannelPersistInputError("tag_number 必须为非空字符串")
    if channel_type not in ("RECT", "TRAP", "CIRC"):
        raise OpenChannelPersistInputError(
            f"channel_type={channel_type!r} 非法；只允许 RECT/TRAP/CIRC"
        )
    if flow_rate < 0 or depth < 0 or velocity < 0 or slope < 0:
        raise OpenChannelPersistInputError(
            "flow_rate / depth / velocity / slope 必须 ≥ 0"
        )

    record = OpenChannelResult(
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag_number,
        channel_type=channel_type,
        cross_section_json=cross_section_json,
        flow_rate=flow_rate,
        depth=depth,
        velocity=velocity,
        slope=slope,
        hydraulic_radius=hydraulic_radius,
        manning_n=manning_n,
        sign_status=RecordSignStatus9.DRAFT,
        created_by=created_by,
    )
    session.add(record)
    await session.flush()  # 拿到 open_channel_id

    # ADR-0028 §决策 4 record_hash reflection + DataLineage 血缘收口
    # （OPEN_CHANNEL 是 CONFIG 类计算，无源流；source_stream_ids=[]）
    await finalize_calc_record(
        session,
        record,
        source_stream_ids=[],
        formula_version=_FORMULA_VERSION,
    )
    await session.commit()
    await session.refresh(record)
    return record


async def save_section_result(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    channel_type: str,
    cross_section_json: dict,
    flow_rate: float,
    depth: float,
    velocity: float,
    slope: float,
    manning_n: float | None = None,
    hydraulic_radius: float | None = None,
    created_by: uuid.UUID | None = None,
) -> OpenChannelResult:
    """落库最优断面设计结果（§3.2.6 第二项）。

    与 save_manning_result 镜像；区别仅在于调用方传入的 depth/velocity/
    hydraulic_radius 来自 SectionResult（按设计流量反算的最优断面）。
    """
    if not tag_number or not isinstance(tag_number, str):
        raise OpenChannelPersistInputError("tag_number 必须为非空字符串")
    if channel_type not in ("RECT", "TRAP", "CIRC"):
        raise OpenChannelPersistInputError(
            f"channel_type={channel_type!r} 非法；只允许 RECT/TRAP/CIRC"
        )
    if flow_rate < 0 or depth < 0 or velocity < 0 or slope < 0:
        raise OpenChannelPersistInputError(
            "flow_rate / depth / velocity / slope 必须 ≥ 0"
        )

    record = OpenChannelResult(
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag_number,
        channel_type=channel_type,
        cross_section_json=cross_section_json,
        flow_rate=flow_rate,
        depth=depth,
        velocity=velocity,
        slope=slope,
        hydraulic_radius=hydraulic_radius,
        manning_n=manning_n,
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


async def save_critical_result(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    channel_type: str,
    cross_section_json: dict,
    flow_rate: float,
    depth: float,
    velocity: float,
    slope: float,
    critical_depth: float,
    froude_number: float,
    manning_n: float | None = None,
    hydraulic_radius: float | None = None,
    created_by: uuid.UUID | None = None,
) -> OpenChannelResult:
    """落库临界水深 + Froude 数结果（§3.2.6 第三项）。

    除 7 字段平铺外，额外写 critical_depth / froude_number 两个派生字段。
    """
    if not tag_number or not isinstance(tag_number, str):
        raise OpenChannelPersistInputError("tag_number 必须为非空字符串")
    if channel_type not in ("RECT", "TRAP", "CIRC"):
        raise OpenChannelPersistInputError(
            f"channel_type={channel_type!r} 非法；只允许 RECT/TRAP/CIRC"
        )
    if flow_rate < 0 or depth < 0 or velocity < 0 or slope < 0:
        raise OpenChannelPersistInputError(
            "flow_rate / depth / velocity / slope 必须 ≥ 0"
        )
    if critical_depth < 0 or froude_number < 0:
        raise OpenChannelPersistInputError(
            "critical_depth / froude_number 必须 ≥ 0"
        )

    record = OpenChannelResult(
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag_number,
        channel_type=channel_type,
        cross_section_json=cross_section_json,
        flow_rate=flow_rate,
        depth=depth,
        velocity=velocity,
        slope=slope,
        critical_depth=critical_depth,
        froude_number=froude_number,
        hydraulic_radius=hydraulic_radius,
        manning_n=manning_n,
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


async def save_jump_result(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    channel_type: str,
    cross_section_json: dict,
    flow_rate: float,
    depth: float,
    velocity: float,
    slope: float,
    jump_type: str,
    conjugate_depth: float,
    energy_loss: float,
    manning_n: float | None = None,
    hydraulic_radius: float | None = None,
    created_by: uuid.UUID | None = None,
) -> OpenChannelResult:
    """落库水跃 Bélanger 方程计算结果（§3.2.6 第四项）。

    除 7 字段平铺外，额外写 jump_type / conjugate_depth / energy_loss 三件套。
    """
    if not tag_number or not isinstance(tag_number, str):
        raise OpenChannelPersistInputError("tag_number 必须为非空字符串")
    if channel_type not in ("RECT", "TRAP", "CIRC"):
        raise OpenChannelPersistInputError(
            f"channel_type={channel_type!r} 非法；只允许 RECT/TRAP/CIRC"
        )
    if flow_rate < 0 or depth < 0 or velocity < 0 or slope < 0:
        raise OpenChannelPersistInputError(
            "flow_rate / depth / velocity / slope 必须 ≥ 0"
        )
    if jump_type not in ("WAVY", "WEAK", "OSCILLATING", "STEADY", "STRONG"):
        raise OpenChannelPersistInputError(
            f"jump_type={jump_type!r} 非法；只允许 "
            "WAVY/WEAK/OSCILLATING/STEADY/STRONG"
        )
    if conjugate_depth < 0 or energy_loss < 0:
        raise OpenChannelPersistInputError(
            "conjugate_depth / energy_loss 必须 ≥ 0"
        )

    record = OpenChannelResult(
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag_number,
        channel_type=channel_type,
        cross_section_json=cross_section_json,
        flow_rate=flow_rate,
        depth=depth,
        velocity=velocity,
        slope=slope,
        jump_type=jump_type,
        conjugate_depth=conjugate_depth,
        energy_loss=energy_loss,
        hydraulic_radius=hydraulic_radius,
        manning_n=manning_n,
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


async def list_open_channel_results_service(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    include_obsolete: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[OpenChannelResult]:
    """按 project_id 列出 OpenChannelResult（GET list）。

    默认 ``include_obsolete=False`` → 过滤 sign_status == OBSOLETE。
    按 created_at DESC 排序 + skip/limit 分页。

    Args:
        session: async SQLAlchemy session。
        project_id: 项目 ID（必填；隔离键）。
        include_obsolete: 是否包含 OBSOLETE（默认 False）。
        skip: 分页偏移（默认 0）。
        limit: 分页上限（默认 50；brief 推荐 ≤200）。

    Returns:
        OpenChannelResult 列表。
    """
    stmt = select(OpenChannelResult).where(
        OpenChannelResult.project_id == project_id,
    )
    if not include_obsolete:
        stmt = stmt.where(
            OpenChannelResult.sign_status != RecordSignStatus9.OBSOLETE
        )
    stmt = (
        stmt.order_by(OpenChannelResult.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_open_channel_result_service(
    session: AsyncSession,
    *,
    result_id: uuid.UUID,
) -> OpenChannelResult:
    """按 open_channel_id 取 OpenChannelResult（GET detail）。

    Returns:
        OpenChannelResult。

    Raises:
        OpenChannelPersistInputError: record 不存在（OPEN_CHANNEL_NOT_FOUND）。
    """
    record = await session.get(OpenChannelResult, result_id)
    if record is None:
        raise OpenChannelPersistInputError(
            f"OPEN_CHANNEL result {result_id} 不存在",
            code="OPEN_CHANNEL_NOT_FOUND",
        )
    return record


async def update_open_channel_result_service(
    session: AsyncSession,
    *,
    result_id: uuid.UUID,
    patch: dict,
) -> OpenChannelResult:
    """PATCH 锁定业务字段。

    仅 DRAFT / CHANGE_PENDING 可改；CHECKED / IN_APPROVAL 等锁定态拒绝。
    字段白名单：_OPENCHANNEL_UPDATE_FIELDS。

    Returns:
        OpenChannelResult（更新后）。

    Raises:
        OpenChannelPersistInputError: 记录不存在 / 字段越界 / 锁定态。
    """
    record = await get_open_channel_result_service(
        session, result_id=result_id
    )
    if record.sign_status not in (
        RecordSignStatus9.DRAFT,
        RecordSignStatus9.CHANGE_PENDING,
    ):
        raise OpenChannelPersistInputError(
            f"sign_status={record.sign_status.value} 不允许 PATCH "
            "（仅 DRAFT/CHANGE_PENDING 可改）",
            code="OPEN_CHANNEL_LOCKED",
        )
    invalid = set(patch.keys()) - _OPENCHANNEL_UPDATE_FIELDS
    if invalid:
        raise OpenChannelPersistInputError(
            f"非法字段: {sorted(invalid)}；只允许 "
            f"{sorted(_OPENCHANNEL_UPDATE_FIELDS)}",
            code="OPEN_CHANNEL_INVALID_FIELDS",
        )
    for k, v in patch.items():
        setattr(record, k, v)
    record.stale_resolution_path = "service_layer_update"
    record.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(record)
    return record


async def soft_delete_open_channel_result_service(
    session: AsyncSession,
    *,
    result_id: uuid.UUID,
) -> OpenChannelResult:
    """软删除 OpenChannelResult（DELETE → sign_status=OBSOLETE）。

    位号终身锁定：tag_number 加 ``__OBSOLETE_<unix_ts>`` 后缀，保留原
    tag_number 历史溯源；stale_resolution_path='service_layer_soft_delete'。
    后续 list 默认不命中（OBSOLETE 被过滤）。

    Returns:
        OpenChannelResult（已 OBSOLETE）。

    Raises:
        OpenChannelPersistInputError: 记录不存在。
    """
    record = await get_open_channel_result_service(
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


async def create_open_channel_result_direct(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
    created_by: uuid.UUID | None = None,
    **payload,
) -> OpenChannelResult:
    """直接 service 入口（不走 calc）创建 OpenChannelResult。

    用于"前端填业务字段直接保存"的场景（非 calc-driven）。所有业务字段
    通过 kwargs 传入；越权字段（PK / mixin / audit）拒绝。

    Returns:
        OpenChannelResult。

    Raises:
        OpenChannelPersistInputError: tag_number 空 / 字段越界。
    """
    if not tag_number or not isinstance(tag_number, str):
        raise OpenChannelPersistInputError("tag_number 必须为非空字符串")
    invalid = set(payload.keys()) - _OPENCHANNEL_UPDATE_FIELDS
    if invalid:
        raise OpenChannelPersistInputError(
            f"非法字段: {sorted(invalid)}；只允许 "
            f"{sorted(_OPENCHANNEL_UPDATE_FIELDS)}",
            code="OPEN_CHANNEL_INVALID_FIELDS",
        )

    record = OpenChannelResult(
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
    "OpenChannelPersistInputError",
    # 4 save
    "save_manning_result",
    "save_section_result",
    "save_critical_result",
    "save_jump_result",
    # 5 CRUD
    "list_open_channel_results_service",
    "get_open_channel_result_service",
    "update_open_channel_result_service",
    "soft_delete_open_channel_result_service",
    "create_open_channel_result_direct",
]