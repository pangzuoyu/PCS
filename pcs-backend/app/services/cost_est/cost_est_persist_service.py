"""COST_EST 计算结果持久化服务（SPEC §3.2.8，P6-3 Task 36）。

依据：Task 35 3 calc 模块（six_tenths_rule / cepci_adjustment /
cost_correlation_lookup）+ Task 30 CostEstResult ORM（11 业务列：
PK cost_est_id + FK equipment_id + 4 v3.1 业务列 estimated_cost/currency/
cost_index_year + 6 Task 30 派生列 base_cost/base_year/cepci_index_base/
cepci_index_target/correlation_source/scaling_exponent + created_at）。

与 filtration/open_channel 持久化的关键差异（CostEstResult 不继承任何
mixin；1:1 跟随 equipment_list）：

- **无 project_id / workspace_id / tag_number / sign_status / record_hash
  / stale_resolution_path / created_by / updated_at 列** —— CostEstResult
  仅承载 cost_est_id + equipment_id（FK unique） + 10 业务列 +
  created_at。service 层不调用 ``finalize_calc_record``（会因 record_hash
  列缺失而抛 AttributeError），不写 RecordSignStatus9。
- **equipment_id 是天然隔离键**：CostEstResult.equipment_id UNIQUE → 每
  个 equipment 至多 1 条 cost_est；service 层在落库前校验 equipment_id
  存在。
- **软删除** = DELETE 行（1:1 跟随设备生命周期；不像 TaggedRecordMixin
  表有 OBSOLETE 态门禁）。

服务函数（8 个）：
- 3 save：``save_six_tenths_rule_result`` / ``save_cepci_adjustment_result``
  / ``save_cost_correlation_result``
- 5 CRUD（统一 ``_service`` 后缀别名；与 filtration / open_channel 一致）：
    ``list_cost_est_results_service`` / ``get_cost_est_result_service`` /
    ``update_cost_est_result_service`` / ``soft_delete_cost_est_result_service``
    / ``create_cost_est_result_direct``

公式版本：``CEv1.0-p6-3-task36``（与 Task 18 flare/cool_tower/psychro ORM
一致锚点；Task 35 calc 模块同版本号）。
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import CostEstResult

# P6-3 Task 36 — cost_est_persist formula version
_FORMULA_VERSION = "CEv1.0-p6-3-task36"


class CostEstPersistInputError(Exception):
    """COST_EST 持久化输入不合法（422）。

    触发场景：
    - equipment_id 不存在 / FK 失败
    - estimated_cost < 0 / currency 长度越界
    - 数值列（cepci_index_* / base_cost / scaling_exponent）越界
    - PATCH 字段不在 _COST_EST_UPDATE_FIELDS 白名单
    - record_id 不存在
    - 违反 equipment_id 唯一约束（已存在 cost_est）
    """

    def __init__(
        self,
        message: str,
        code: str = "COST_EST_PERSIST_INPUT_ERROR",
    ):
        super().__init__(message)
        self.message = message
        self.code = code


# CostEstResult 业务字段白名单（PATCH 可写）
# 排除 PK（cost_est_id）/ FK（equipment_id）/ 生命周期（created_at）；与
# ORM 10 业务列一致。
_COST_EST_UPDATE_FIELDS: frozenset[str] = frozenset(
    {
        "estimated_cost",
        "currency",
        "cost_index_year",
        "base_cost",
        "base_year",
        "cepci_index_base",
        "cepci_index_target",
        "correlation_source",
        "scaling_exponent",
    }
)

_COST_EST_CREATE_FIELDS: frozenset[str] = _COST_EST_UPDATE_FIELDS


async def _ensure_equipment_exists(
    session: AsyncSession, equipment_id: uuid.UUID
) -> None:
    """校验 equipment_id 存在于 equipment_list（FK 必填）。

    实现：``SELECT equipment_id FROM equipment_list WHERE equipment_id = ?``
    — 仅查 PK 列，不触发 ORM ``SELECT *``（equipment_list 走
    TaggedRecordMixin → RecordMixin，含 P4-0-1 审计 3 列；
    ``session.get`` 会展开 SELECT *，在 pcs_test 库会触发
    "column stale_resolution_path does not exist"；因此存在性校验只查 PK）。

    Raises:
        CostEstPersistInputError: equipment_id 不存在（COST_EST_EQUIPMENT_NOT_FOUND）。
    """
    from app.models.equipment import EquipmentList

    stmt = select(EquipmentList.equipment_id).where(
        EquipmentList.equipment_id == equipment_id
    )
    exists = (await session.execute(stmt)).scalar_one_or_none()
    if exists is None:
        raise CostEstPersistInputError(
            f"equipment_id {equipment_id} 不存在（FK 必填）",
            code="COST_EST_EQUIPMENT_NOT_FOUND",
        )


def _ensure_created_at(record: CostEstResult) -> None:
    """显式填充 ``created_at`` —— CostEstResult ORM ``created_at`` 列在
    v3.1 迁移里未声明 ``server_default=now()``（其他 15 张表都有），导致
    INSERT 不带 created_at 时落 NULL；API 层 Pydantic schema 要求
    ``datetime`` 非空 → 422。service 层显式 set 兜底，确保 in-memory /
    DB / refresh 后的值一致。

    是过渡期 fix：未来若 ORM 修齐 ``server_default=func.now()``，本函数
    可移除（no-op）。
    """
    if record.created_at is None:
        record.created_at = datetime.now(UTC)


async def _ensure_no_existing_cost_est(
    session: AsyncSession, equipment_id: uuid.UUID
) -> None:
    """校验 equipment_id 下尚无 cost_est 记录（FK unique）。

    Raises:
        CostEstPersistInputError: 已存在 cost_est（COST_EST_DUPLICATE）。
    """
    stmt = select(CostEstResult.cost_est_id).where(
        CostEstResult.equipment_id == equipment_id
    )
    existing = (await session.execute(stmt)).scalars().first()
    if existing is not None:
        raise CostEstPersistInputError(
            f"equipment_id {equipment_id} 已存在 cost_est 记录（1:1 唯一）",
            code="COST_EST_DUPLICATE",
        )


def _validate_common_inputs(
    *,
    estimated_cost: float,
    currency: str,
    cost_index_year: int,
) -> None:
    """通用字段校验（estimated_cost / currency / cost_index_year）。"""
    if estimated_cost < 0:
        raise CostEstPersistInputError("estimated_cost 必须 ≥ 0")
    if not currency or not isinstance(currency, str):
        raise CostEstPersistInputError("currency 必须为非空字符串")
    if len(currency) > 10:
        raise CostEstPersistInputError("currency 长度必须 ≤ 10")
    if cost_index_year < 1900 or cost_index_year > 2200:
        raise CostEstPersistInputError("cost_index_year 必须在 [1900, 2200]")


def _validate_cepci_pair(
    *,
    cepci_index_base: float | None,
    cepci_index_target: float | None,
) -> None:
    """CEPCI 双件套校验（>0）。"""
    if cepci_index_base is not None and cepci_index_base <= 0:
        raise CostEstPersistInputError("cepci_index_base 必须 > 0")
    if cepci_index_target is not None and cepci_index_target <= 0:
        raise CostEstPersistInputError("cepci_index_target 必须 > 0")


def _validate_scaling_exponent(value: float | None) -> None:
    if value is not None and (value <= 0 or value > 1.5):
        raise CostEstPersistInputError("scaling_exponent 必须在 (0, 1.5]")


def _validate_base_cost(value: float | None) -> None:
    if value is not None and value < 0:
        raise CostEstPersistInputError("base_cost 必须 ≥ 0")


# ============================================================================
# 1. 3 save 函数（按 calc 模块 1:1 对应；service 层补必填）
# ============================================================================


async def save_six_tenths_rule_result(
    session: AsyncSession,
    *,
    equipment_id: uuid.UUID,
    reference_cost: float,
    reference_cepci: float,
    target_cepci: float,
    scaling_exponent: float,
    estimated_cost: float,
    currency: str = "USD",
    cost_index_year: int = 2019,
    base_cost: float | None = None,
    base_year: int | None = None,
) -> CostEstResult:
    """落库六十法则 + CEPCI 联合估算结果（§3.2.8 第一项 + 第二项）。

    Args:
        session: async SQLAlchemy session。
        equipment_id: 设备 UUID（FK → equipment_list，unique）。
        reference_cost: 基准投资 C₁。
        reference_cepci: 基准 CEPCI 指数 CEPCI₁。
        target_cepci: 目标 CEPCI 指数 CEPCI₂。
        scaling_exponent: 六十法则 scaling 指数 n。
        estimated_cost: 估算投资 C₂（已含 CEPCI 调整）。
        currency: 货币代码（默认 USD；最长 10 字符）。
        cost_index_year: 目标年（默认 2019）。
        base_cost: 基准年成本 C₁（用于六十法则 scaling；可空）。
        base_year: 基准年（用于 base_cost 时点；可空）。

    Returns:
        CostEstResult（含 cost_est_id）。

    Raises:
        CostEstPersistInputError: 输入字段缺失或越界 / equipment_id 不存在 /
            已存在 cost_est 记录（422）。
    """
    _validate_common_inputs(
        estimated_cost=estimated_cost,
        currency=currency,
        cost_index_year=cost_index_year,
    )
    _validate_cepci_pair(
        cepci_index_base=reference_cepci,
        cepci_index_target=target_cepci,
    )
    _validate_scaling_exponent(scaling_exponent)
    _validate_base_cost(base_cost)

    await _ensure_equipment_exists(session, equipment_id)
    await _ensure_no_existing_cost_est(session, equipment_id)

    record = CostEstResult(
        equipment_id=equipment_id,
        estimated_cost=estimated_cost,
        currency=currency,
        cost_index_year=cost_index_year,
        base_cost=base_cost,
        base_year=base_year,
        cepci_index_base=reference_cepci,
        cepci_index_target=target_cepci,
        scaling_exponent=scaling_exponent,
        correlation_source=None,
    )
    _ensure_created_at(record)
    session.add(record)
    await session.flush()
    await session.commit()
    await session.refresh(record)
    return record


async def save_cepci_adjustment_result(
    session: AsyncSession,
    *,
    equipment_id: uuid.UUID,
    reference_cost: float,
    reference_cepci: float,
    target_cepci: float,
    estimated_cost: float,
    currency: str = "USD",
    cost_index_year: int = 2019,
    base_cost: float | None = None,
    base_year: int | None = None,
) -> CostEstResult:
    """落库 CEPCI 单独调整结果（§3.2.8 第二项 — 不含 60 法则）。

    与 save_six_tenths_rule_result 镜像；区别仅 scaling_exponent=None
    （纯通胀调整，无 scaling）。
    """
    _validate_common_inputs(
        estimated_cost=estimated_cost,
        currency=currency,
        cost_index_year=cost_index_year,
    )
    _validate_cepci_pair(
        cepci_index_base=reference_cepci,
        cepci_index_target=target_cepci,
    )
    _validate_base_cost(base_cost)

    await _ensure_equipment_exists(session, equipment_id)
    await _ensure_no_existing_cost_est(session, equipment_id)

    record = CostEstResult(
        equipment_id=equipment_id,
        estimated_cost=estimated_cost,
        currency=currency,
        cost_index_year=cost_index_year,
        base_cost=base_cost,
        base_year=base_year,
        cepci_index_base=reference_cepci,
        cepci_index_target=target_cepci,
        scaling_exponent=None,
        correlation_source=None,
    )
    _ensure_created_at(record)
    session.add(record)
    await session.flush()
    await session.commit()
    await session.refresh(record)
    return record


async def save_cost_correlation_result(
    session: AsyncSession,
    *,
    equipment_id: uuid.UUID,
    equipment_type: str,
    scale_parameter: float,
    correlation_source: str,
    estimated_cost: float,
    currency: str = "USD",
    cost_index_year: int = 2019,
    base_cost: float | None = None,
    base_year: int | None = None,
) -> CostEstResult:
    """落库成本关联式查 CONFIG 表计算结果（§3.2.8 第三项）。

    与 save_six_tenths_rule_result 镜像；区别在于：
    - 不需要 reference_cost / reference_cepci / target_cepci（关联式
      内置基准年+CEPCI 隐含在 cost_correlations.base_year / base_currency）
    - 额外填 scale_parameter（直径/容积/面积/流量/功率/长度×直径）+ correlation_source
    - scaling_exponent 由 lookup_cost_correlation 内部使用，本表不持久化
      （若需落库，从 CostCorrelationResult.scaling_exponent_n 取得）
    """
    _validate_common_inputs(
        estimated_cost=estimated_cost,
        currency=currency,
        cost_index_year=cost_index_year,
    )
    _validate_base_cost(base_cost)
    if not equipment_type or not isinstance(equipment_type, str):
        raise CostEstPersistInputError("equipment_type 必须为非空字符串")
    if scale_parameter <= 0:
        raise CostEstPersistInputError("scale_parameter 必须 > 0")
    if not correlation_source or not isinstance(correlation_source, str):
        raise CostEstPersistInputError("correlation_source 必须为非空字符串")
    if len(correlation_source) > 64:
        raise CostEstPersistInputError("correlation_source 长度必须 ≤ 64")

    await _ensure_equipment_exists(session, equipment_id)
    await _ensure_no_existing_cost_est(session, equipment_id)

    record = CostEstResult(
        equipment_id=equipment_id,
        estimated_cost=estimated_cost,
        currency=currency,
        cost_index_year=cost_index_year,
        base_cost=base_cost,
        base_year=base_year,
        cepci_index_base=None,
        cepci_index_target=None,
        scaling_exponent=None,
        correlation_source=correlation_source,
    )
    _ensure_created_at(record)
    session.add(record)
    await session.flush()
    await session.commit()
    await session.refresh(record)
    return record


# ============================================================================
# 2. 5 CRUD 函数（统一 _service 后缀别名）
# ============================================================================


async def list_cost_est_results_service(
    session: AsyncSession,
    *,
    equipment_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[CostEstResult]:
    """列出 COST_EST 结果（默认按 equipment_id 过滤；不传则全量）。

    与 filtration/open_channel 不同：CostEstResult 不含 project_id 列（隔离
    键经 equipment_id → equipment_list.project_id 间接传递）。本批次
    按 equipment_id 过滤，便于前端按设备查其投资估算。

    Args:
        session: async SQLAlchemy session。
        equipment_id: 设备 UUID（可选；不传 = 全量）。
        skip: 分页偏移（默认 0）。
        limit: 分页上限（默认 50）。

    Returns:
        CostEstResult 列表（按 created_at DESC）。
    """
    stmt = select(CostEstResult)
    if equipment_id is not None:
        stmt = stmt.where(CostEstResult.equipment_id == equipment_id)
    stmt = (
        stmt.order_by(CostEstResult.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_cost_est_result_service(
    session: AsyncSession,
    *,
    result_id: uuid.UUID,
) -> CostEstResult:
    """按 cost_est_id 取 COST_EST 结果（GET detail）。

    Returns:
        CostEstResult。

    Raises:
        CostEstPersistInputError: record 不存在（COST_EST_NOT_FOUND）。
    """
    record = await session.get(CostEstResult, result_id)
    if record is None:
        raise CostEstPersistInputError(
            f"COST_EST result {result_id} 不存在",
            code="COST_EST_NOT_FOUND",
        )
    return record


async def update_cost_est_result_service(
    session: AsyncSession,
    *,
    result_id: uuid.UUID,
    patch: dict,
) -> CostEstResult:
    """PATCH 业务字段。

    CostEstResult 无 sign_status 列 → 不做"锁定态"门禁（区别于 filtration
    / open_channel）；所有状态可 PATCH（生产环境由 CIA 引擎后续批次管理
    stale 状态）。

    字段白名单：_COST_EST_UPDATE_FIELDS。

    Returns:
        CostEstResult（更新后）。

    Raises:
        CostEstPersistInputError: 记录不存在 / 字段越界。
    """
    record = await get_cost_est_result_service(session, result_id=result_id)
    invalid = set(patch.keys()) - _COST_EST_UPDATE_FIELDS
    if invalid:
        raise CostEstPersistInputError(
            f"非法字段: {sorted(invalid)}；只允许 "
            f"{sorted(_COST_EST_UPDATE_FIELDS)}",
            code="COST_EST_INVALID_FIELDS",
        )
    # 复用字段级校验
    for k, v in patch.items():
        setattr(record, k, v)
    if "estimated_cost" in patch or "currency" in patch or "cost_index_year" in patch:
        _validate_common_inputs(
            estimated_cost=record.estimated_cost or 0.0,
            currency=record.currency,
            cost_index_year=record.cost_index_year or 0,
        )
    if "cepci_index_base" in patch or "cepci_index_target" in patch:
        _validate_cepci_pair(
            cepci_index_base=record.cepci_index_base,
            cepci_index_target=record.cepci_index_target,
        )
    if "scaling_exponent" in patch:
        _validate_scaling_exponent(record.scaling_exponent)
    if "base_cost" in patch:
        _validate_base_cost(record.base_cost)
    await session.commit()
    await session.refresh(record)
    return record


async def soft_delete_cost_est_result_service(
    session: AsyncSession,
    *,
    result_id: uuid.UUID,
) -> CostEstResult:
    """物理删除 COST_EST 结果（DELETE 行；CostEstResult 无 OBSOLETE 态）。

    CostEstResult 1:1 跟随 equipment；删除后 equipment 可重新创建 cost_est
    （FK unique 释放）。区别于 TaggedRecordMixin 表的"加 __OBSOLETE_<ts>
    后缀"软删除模式。

    Returns:
        删除前快照（用于 DELETE response）。

    Raises:
        CostEstPersistInputError: 记录不存在。
    """
    record = await get_cost_est_result_service(session, result_id=result_id)
    snapshot = CostEstResult(
        cost_est_id=record.cost_est_id,
        equipment_id=record.equipment_id,
        estimated_cost=record.estimated_cost,
        currency=record.currency,
        cost_index_year=record.cost_index_year,
        base_cost=record.base_cost,
        base_year=record.base_year,
        cepci_index_base=record.cepci_index_base,
        cepci_index_target=record.cepci_index_target,
        scaling_exponent=record.scaling_exponent,
        correlation_source=record.correlation_source,
        created_at=record.created_at,
    )
    snapshot._deleted_at = datetime.now(UTC)  # type: ignore[attr-defined]
    await session.delete(record)
    await session.commit()
    return snapshot


async def create_cost_est_result_direct(
    session: AsyncSession,
    *,
    equipment_id: uuid.UUID,
    **payload,
) -> CostEstResult:
    """直接 service 入口（不走 calc）创建 COST_EST 结果。

    用于"前端填业务字段直接保存"的场景（非 calc-driven）。所有业务字段
    通过 kwargs 传入；越权字段（PK / FK / 生命周期）拒绝。

    Returns:
        CostEstResult。

    Raises:
        CostEstPersistInputError: 字段越界 / equipment_id 不存在 / 重复。
    """
    invalid = set(payload.keys()) - _COST_EST_CREATE_FIELDS
    if invalid:
        raise CostEstPersistInputError(
            f"非法字段: {sorted(invalid)}；只允许 "
            f"{sorted(_COST_EST_CREATE_FIELDS)}",
            code="COST_EST_INVALID_FIELDS",
        )
    # 业务字段校验（仅当字段存在时）
    if "estimated_cost" in payload or "currency" in payload or "cost_index_year" in payload:
        _validate_common_inputs(
            estimated_cost=payload.get("estimated_cost", 0.0),
            currency=payload.get("currency", "USD"),
            cost_index_year=payload.get("cost_index_year", 2019),
        )
    if "cepci_index_base" in payload or "cepci_index_target" in payload:
        _validate_cepci_pair(
            cepci_index_base=payload.get("cepci_index_base"),
            cepci_index_target=payload.get("cepci_index_target"),
        )
    if "scaling_exponent" in payload:
        _validate_scaling_exponent(payload["scaling_exponent"])
    if "base_cost" in payload:
        _validate_base_cost(payload["base_cost"])

    await _ensure_equipment_exists(session, equipment_id)
    await _ensure_no_existing_cost_est(session, equipment_id)

    record = CostEstResult(
        equipment_id=equipment_id,
        **payload,
    )
    _ensure_created_at(record)
    session.add(record)
    await session.flush()
    await session.commit()
    await session.refresh(record)
    return record


__all__ = [
    "CostEstPersistInputError",
    # 3 save
    "save_six_tenths_rule_result",
    "save_cepci_adjustment_result",
    "save_cost_correlation_result",
    # 5 CRUD
    "list_cost_est_results_service",
    "get_cost_est_result_service",
    "update_cost_est_result_service",
    "soft_delete_cost_est_result_service",
    "create_cost_est_result_direct",
]