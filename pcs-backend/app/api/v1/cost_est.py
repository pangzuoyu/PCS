"""P6-3 COST_EST API（SPEC §3.2.8 + Task 36）。

端点（8 个）：
- POST /api/v1/cost-est/six-tenths-rule/calculate    POST §3.2.8 六十法则+CEPCI（201）
- POST /api/v1/cost-est/cepci-adjustment/calculate    POST §3.2.8 CEPCI 调整（201）
- POST /api/v1/cost-est/cost-correlation/calculate    POST §3.2.8 成本关联式（201）
- POST   /api/v1/cost-est/results         创建 CostEstResult（201，不走 calc）
- GET    /api/v1/cost-est/results         列表（按 equipment_id 过滤）
- GET    /api/v1/cost-est/results/{id}    详情
- PATCH  /api/v1/cost-est/results/{id}    更新
- DELETE /api/v1/cost-est/results/{id}    物理删除（CostEstResult 无 OBSOLETE 态）

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（8 endpoints 全部用
  ``require_roles``，与 Task 32 OPEN_CHANNEL / Task 34 FILTRATION 一致）
- 业务异常 → 走 core.errors.PcsError envelope
- 3 calc 端点：endpoint 调 calc_* → save_*_result service 层构造 record，
  禁止 endpoint 直构 CostEstResult（红线 #1）
- CostEstResult 不继承 TaggedRecordMixin / RecordMixin → 无 sign_status /
  record_hash / tag_number / project_id 列；service 层不调用
  ``finalize_calc_record``（会因 record_hash 列缺失抛 AttributeError）；
  以 ``equipment_id`` 为 FK 入口（FK → equipment_list，unique）

依据：Task 35（3 calc 模块）+ Task 30（CostEstResult ORM 11 业务列）
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.schemas.cost_est import (
    CepciAdjustmentCalcRequest,
    CepciAdjustmentCalcResponse,
    CostCorrelationCalcRequest,
    CostCorrelationCalcResponse,
    CostEstCreateRequest,
    CostEstDeleteResponse,
    CostEstListResponse,
    CostEstResultResponse,
    CostEstUpdateRequest,
    SixTenthsRuleCalcRequest,
    SixTenthsRuleCalcResponse,
)
from app.services.cost_est import (  # 8 persist（Task 36）
    # 3 calc（Task 35）
    CepciAdjustmentInput,
    CepciAdjustmentInputError,
    CostCorrelationInput,
    CostCorrelationInputError,
    CostEstPersistInputError,
    SixTenthsRuleInput,
    SixTenthsRuleInputError,
    calc_cepci_adjustment,
    calc_six_tenths_rule,
    create_cost_est_result_direct,
    get_cost_est_result_service,
    list_cost_est_results_service,
    lookup_cost_correlation,
    save_cepci_adjustment_result,
    save_cost_correlation_result,
    save_six_tenths_rule_result,
    soft_delete_cost_est_result_service,
    update_cost_est_result_service,
)

router = APIRouter(prefix="/cost-est", tags=["cost-est"])


def _to_http(err: Exception) -> CorePcsError:
    """service 层 PcsError / PersistInputError → FastAPI HTTPException envelope。

    注：P6-OPEN-010 fix — CorePcsError 使用 ``status`` kwarg（非
    ``status_code``，避免与 HTTPException 混淆）。
    """
    if isinstance(err, CorePcsError):
        return err
    code = getattr(err, "code", "COST_EST_PERSIST_INPUT_ERROR")
    status = 422
    return CorePcsError(code=code, message=str(err), status=status)


# ============================================================================
# 3 calc endpoints（POST /cost-est/{six-tenths-rule,cepci-adjustment,cost-correlation}/calculate）
# ============================================================================


@router.post(
    "/six-tenths-rule/calculate",
    response_model=SixTenthsRuleCalcResponse,
    status_code=201,
)
async def calculate_six_tenths_rule(
    req: SixTenthsRuleCalcRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SixTenthsRuleCalcResponse:
    """六十法则 + CEPCI 联合计算（§3.2.8 第一项 + 第二项）。

    流程：
    1. endpoint 调 ``calc_six_tenths_rule``（输入 reference_cost + ratio +
       scaling_exponent → target_cost）
    2. 调 ``calc_cepci_adjustment``（CEPCI 时间/通胀调整 → final estimated_cost）
    3. ``save_six_tenths_rule_result`` service 层构造 CostEstResult 行；
       禁止 endpoint 直构 ORM（红线 #1）

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        # 1. 六十法则（reference_cost × ratio^n；reference_scale/target_scale
        #    取 1.0 → ratio=1，仅用 scaling_exponent 表达）
        six_inp = SixTenthsRuleInput(
            reference_cost=req.reference_cost,
            reference_scale=1.0,
            target_scale=1.0,
        )
        six_r = calc_six_tenths_rule(six_inp, scaling_exponent=req.scaling_exponent)
        # 2. CEPCI 调整（六法则 C₂ 作为 CEPCI 调整的 reference_cost）
        cepci_inp = CepciAdjustmentInput(
            reference_cost=six_r.target_cost,
            reference_cepci=req.reference_cepci,
            target_cepci=req.target_cepci,
        )
        cepci_r = calc_cepci_adjustment(cepci_inp)
    except (SixTenthsRuleInputError, CepciAdjustmentInputError) as e:
        raise _to_http(e) from e

    # 3. 落库（service 层校验 equipment_id 存在 + 1:1 唯一约束）
    try:
        record = await save_six_tenths_rule_result(
            db,
            equipment_id=req.equipment_id,
            reference_cost=req.reference_cost,
            reference_cepci=req.reference_cepci,
            target_cepci=req.target_cepci,
            scaling_exponent=req.scaling_exponent,
            estimated_cost=cepci_r.target_cost,
            currency=req.currency,
            cost_index_year=req.cost_index_year,
            base_cost=req.base_cost,
            base_year=req.base_year,
        )
    except CostEstPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return SixTenthsRuleCalcResponse(
        estimated_cost=record.estimated_cost,
        currency=record.currency,
        cost_index_year=record.cost_index_year,
        base_cost=record.base_cost,
        base_year=record.base_year,
        cepci_index_base=record.cepci_index_base,
        cepci_index_target=record.cepci_index_target,
        scaling_exponent=record.scaling_exponent,
        result_id=record.cost_est_id,
        equipment_id=record.equipment_id,
        created_at=record.created_at,
    )


@router.post(
    "/cepci-adjustment/calculate",
    response_model=CepciAdjustmentCalcResponse,
    status_code=201,
)
async def calculate_cepci_adjustment(
    req: CepciAdjustmentCalcRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CepciAdjustmentCalcResponse:
    """CEPCI 时间/通胀调整（§3.2.8 第二项 — 不含 60 法则）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        cepci_inp = CepciAdjustmentInput(
            reference_cost=req.reference_cost,
            reference_cepci=req.reference_cepci,
            target_cepci=req.target_cepci,
        )
        cepci_r = calc_cepci_adjustment(cepci_inp)
    except CepciAdjustmentInputError as e:
        raise _to_http(e) from e

    try:
        record = await save_cepci_adjustment_result(
            db,
            equipment_id=req.equipment_id,
            reference_cost=req.reference_cost,
            reference_cepci=req.reference_cepci,
            target_cepci=req.target_cepci,
            estimated_cost=cepci_r.target_cost,
            currency=req.currency,
            cost_index_year=req.cost_index_year,
            base_cost=req.base_cost,
            base_year=req.base_year,
        )
    except CostEstPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return CepciAdjustmentCalcResponse(
        estimated_cost=record.estimated_cost,
        currency=record.currency,
        cost_index_year=record.cost_index_year,
        base_cost=record.base_cost,
        base_year=record.base_year,
        cepci_index_base=record.cepci_index_base,
        cepci_index_target=record.cepci_index_target,
        scaling_exponent=record.scaling_exponent,
        result_id=record.cost_est_id,
        equipment_id=record.equipment_id,
        created_at=record.created_at,
    )


@router.post(
    "/cost-correlation/calculate",
    response_model=CostCorrelationCalcResponse,
    status_code=201,
)
async def calculate_cost_correlation(
    req: CostCorrelationCalcRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CostCorrelationCalcResponse:
    """成本关联式查 CONFIG 表 + 计算（§3.2.8 第三项）。

    流程：endpoint 调 ``lookup_cost_correlation`` → 返回 ``estimated_cost +
    correlation_id`` → ``save_cost_correlation_result`` 落库。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        corr_inp = CostCorrelationInput(
            equipment_type=req.equipment_type,
            scale_parameter=req.scale_parameter,
        )
        corr_r = lookup_cost_correlation(corr_inp)
    except CostCorrelationInputError as e:
        raise _to_http(e) from e

    try:
        record = await save_cost_correlation_result(
            db,
            equipment_id=req.equipment_id,
            equipment_type=req.equipment_type,
            scale_parameter=req.scale_parameter,
            correlation_source=corr_r.correlation_id,
            estimated_cost=corr_r.estimated_cost,
            currency=req.currency,
            cost_index_year=req.cost_index_year,
            base_cost=req.base_cost,
            base_year=req.base_year,
        )
    except CostEstPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return CostCorrelationCalcResponse(
        estimated_cost=record.estimated_cost,
        currency=record.currency,
        cost_index_year=record.cost_index_year,
        base_cost=record.base_cost,
        base_year=record.base_year,
        correlation_source=record.correlation_source,
        result_id=record.cost_est_id,
        equipment_id=record.equipment_id,
        created_at=record.created_at,
    )


# ============================================================================
# 5 CRUD endpoints（/cost-est/results）
# ============================================================================


@router.post(
    "/results", response_model=CostEstResultResponse, status_code=201
)
async def create_cost_est_result(
    req: CostEstCreateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CostEstResultResponse:
    """直接创建 CostEstResult 行（POST → 201，不走 calc）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    payload = req.model_dump(exclude={"equipment_id"})
    try:
        record = await create_cost_est_result_direct(
            db,
            equipment_id=req.equipment_id,
            **payload,
        )
    except CostEstPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return CostEstResultResponse.model_validate(record, from_attributes=True)


@router.get("/results", response_model=CostEstListResponse)
async def list_cost_est_results(
    equipment_id: Annotated[uuid.UUID | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> CostEstListResponse:
    """按 equipment_id 列出 CostEstResult（GET list，分页）。

    CostEstResult 1:1 跟随 equipment；不传 equipment_id = 全量列表。
    无 OBSOLETE 态门禁（区别于 TaggedRecordMixin 表）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    records = await list_cost_est_results_service(
        db,
        equipment_id=equipment_id,
        skip=skip,
        limit=limit,
    )
    items = [
        CostEstResultResponse.model_validate(r, from_attributes=True)
        for r in records
    ]
    return CostEstListResponse(
        items=items, total=len(items), skip=skip, limit=limit
    )


@router.get(
    "/results/{result_id}", response_model=CostEstResultResponse
)
async def get_cost_est_result(
    result_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CostEstResultResponse:
    """按 cost_est_id 取 CostEstResult（GET detail）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        record = await get_cost_est_result_service(db, result_id=result_id)
    except CostEstPersistInputError as e:
        if e.code == "COST_EST_NOT_FOUND":
            raise HTTPException(
                status_code=404, detail="CostEstResult not found"
            ) from e
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return CostEstResultResponse.model_validate(record, from_attributes=True)


@router.patch(
    "/results/{result_id}", response_model=CostEstResultResponse
)
async def update_cost_est_result(
    result_id: uuid.UUID,
    req: CostEstUpdateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CostEstResultResponse:
    """更新 CostEstResult 业务字段（PATCH）。

    CostEstResult 无 sign_status 列 → 不做"锁定态"门禁（区别于
    filtration / open_channel）；所有状态可 PATCH。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    patch = req.model_dump(exclude_unset=True)
    try:
        record = await update_cost_est_result_service(
            db, result_id=result_id, patch=patch
        )
    except CostEstPersistInputError as e:
        if e.code == "COST_EST_NOT_FOUND":
            raise HTTPException(
                status_code=404, detail="CostEstResult not found"
            ) from e
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return CostEstResultResponse.model_validate(record, from_attributes=True)


@router.delete(
    "/results/{result_id}", response_model=CostEstDeleteResponse
)
async def soft_delete_cost_est_result(
    result_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CostEstDeleteResponse:
    """物理删除 CostEstResult（DELETE 行；无 OBSOLETE 态）。

    CostEstResult 1:1 跟随 equipment；删除后 equipment 可重建 cost_est。
    返回删除前 cost_est_id + equipment_id + deleted_at 时间戳。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        record = await soft_delete_cost_est_result_service(
            db, result_id=result_id
        )
    except CostEstPersistInputError as e:
        if e.code == "COST_EST_NOT_FOUND":
            raise HTTPException(
                status_code=404, detail="CostEstResult not found"
            ) from e
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return CostEstDeleteResponse(
        result_id=record.cost_est_id,
        equipment_id=record.equipment_id,
        deleted_at=getattr(record, "_deleted_at", None) or record.created_at,
    )


__all__ = ["router"]