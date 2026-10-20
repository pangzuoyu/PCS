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
  tag_number / project_id 列；**有 record_hash**（P9A-4 D0 新增，ADR-0048 §⑥
  的并发令牌 —— cost_est 是唯一「可编辑 ∧ 无任何并发令牌」的结果表），
  service 层调 ``finalize_calc_record`` 收口；
  以 ``equipment_id`` 为 FK 入口（FK → equipment_list，unique）

依据：Task 35（3 calc 模块）+ Task 30（CostEstResult ORM 11 业务列）
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import (
    check_project_access_or_404,
    check_record_access_or_404,
)
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
from app.schemas.edit_conflict import BASELINE_FIELDS
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
from app.services.edit_guard import check_conflict, record_edit_audit

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


# ============================================================================
# 项目守卫（P9A-5 Task B · TODO-061）
#
# ⚠️ 本模块原先 **0 处**项目鉴权，而 `CostEstResult` 连 `project_id` 列都没有
#    （`app/models/calc.py:1193 class CostEstResult(Base)` 不继承 mixin）
#    ⇒ 守卫挂不上。⇒ 最宽的一条是读面：`GET /results` 不传参时整表返回。
# ⚠️ 顺序：**先鉴权，再写**（bug-2039 的教训 —— 鉴权排在保存之后时，响应是
#    404 但**行已经改了**）。PATCH 的顺序固定为
#    预取 → 鉴权 → check_conflict → 保存。
# ============================================================================


async def _guard_by_equipment(
    db: AsyncSession, *, user_id: uuid.UUID, equipment_id: uuid.UUID, roles: list[str]
) -> None:
    """按 `equipment_id` 守卫：设备的 project 即结果的 project（P9A-5 Task B）。

    ⚠️ 4 个**创建**端点（3 calc + direct）都只有 `equipment_id`
    ⇒ 「这条记录属于哪个项目」只能从 equipment 反查。
    ⚠️ equipment_id 不存在时这里**放行**（不是 404）：存在性由 service 的
    `COST_EST_EQUIPMENT_NOT_FOUND`（422）报，那是本模块既有的语义，
    不在这里改。
    """
    from sqlalchemy import select as _sa_select

    from app.models.equipment import EquipmentList

    project_id = (
        await db.execute(
            _sa_select(EquipmentList.project_id).where(
                EquipmentList.equipment_id == equipment_id
            )
        )
    ).scalar_one_or_none()
    if project_id is None:
        return
    await check_project_access_or_404(
        db, user_id=user_id, project_id=project_id, actor_roles=roles
    )


async def _prefetch_for_guard(db: AsyncSession, result_id: uuid.UUID):
    """按 `cost_est_id` 取记录供守卫用（不存在 ⇒ None）。"""
    from sqlalchemy import select as _sa_select

    from app.models.calc import CostEstResult

    return (
        await db.execute(
            _sa_select(CostEstResult).where(CostEstResult.cost_est_id == result_id)
        )
    ).scalar_one_or_none()

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
    await _guard_by_equipment(
        db, user_id=user.user_id,
        equipment_id=req.equipment_id, roles=user.roles,
    )
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
    await _guard_by_equipment(
        db, user_id=user.user_id,
        equipment_id=req.equipment_id, roles=user.roles,
    )
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
    await _guard_by_equipment(
        db, user_id=user.user_id,
        equipment_id=req.equipment_id, roles=user.roles,
    )
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
    await _guard_by_equipment(
        db, user_id=user.user_id,
        equipment_id=req.equipment_id, roles=user.roles,
    )
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
    project_id: Annotated[uuid.UUID, Query()],
    equipment_id: Annotated[uuid.UUID | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> CostEstListResponse:
    """按 project_id 列出 CostEstResult（GET list，分页）。

    ⚠️ **`project_id` 必填**（P9A-5 Task B）：原先不传 `equipment_id` 就是
    **整表返回** ⇒ 跨项目读泄漏。现在与其余 5 个结果模块一致 ——
    `project_id: Annotated[UUID, Query(...)]` 必填 + 守卫 + 按项目过滤。

    可选再按 equipment_id 收窄（CostEstResult 1:1 跟随 equipment）。
    无 OBSOLETE 态门禁（区别于 TaggedRecordMixin 表）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id, actor_roles=user.roles,
    )
    records = await list_cost_est_results_service(
        db,
        project_id=project_id,
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
    # ⚠️ **先鉴权，再冲突/再写**（P9A-5 Task B · bug-2039 的教训）：
    # 冲突检查会把**持锁人身份**放进 409 响应 ⇒ 排在鉴权之前，无权者就能
    # 问出「谁在改这条记录」；且 update/delete service 取记录不带 project_id
    # ⇒ 保存那一步零隔离。顺序固定：**预取 → 鉴权 → 冲突检查 → 保存**。
    pre_record = await _prefetch_for_guard(db, result_id)
    if pre_record is not None:
        await check_record_access_or_404(
            db, user_id=user.user_id, record=pre_record,
            actor_roles=user.roles,
        )
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
    # ⚠️ **先鉴权，再冲突/再写**（P9A-5 Task B · bug-2039 的教训）：
    # 冲突检查会把**持锁人身份**放进 409 响应 ⇒ 排在鉴权之前，无权者就能
    # 问出「谁在改这条记录」；且 update/delete service 取记录不带 project_id
    # ⇒ 保存那一步零隔离。顺序固定：**预取 → 鉴权 → 冲突检查 → 保存**。
    pre_record = await _prefetch_for_guard(db, result_id)
    if pre_record is not None:
        await check_record_access_or_404(
            db, user_id=user.user_id, record=pre_record,
            actor_roles=user.roles,
        )
    # P9A-4 D2：并发基线检查（ADR-0048 §⑥）—— 冲突 ⇒ 409，**不保存、不写审计**
    conflict = await check_conflict(
        db,
        record_type="CostEstResult",
        record_id=result_id,
        expected_hash=req.expected_hash,
        expected_updated_at=req.expected_updated_at,
    )
    if conflict.conflict is not None:
        raise CorePcsError(
            code="RECORD_EDIT_CONFLICT",
            message="该记录无法安全保存，请刷新后重新编辑",
            status=409,
            detail={"conflict": conflict.conflict.model_dump(mode="json")},
        )
    patch = req.model_dump(exclude_unset=True, exclude=BASELINE_FIELDS)
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

    # 编辑审计（ADR-0048 §⑦）：changed_fields = **字段名列表**（不含值）
    await record_edit_audit(
        db,
        record_type="CostEstResult",
        record_id=result_id,
        user_id=user.user_id,
        changed_fields=sorted(patch.keys()),
        overwrote_stale_baseline=conflict.overwrote_stale_baseline,
    )
    await db.commit()
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
    # ⚠️ **先鉴权，再删**（P9A-5 Task B）—— cost_est 是**物理**删除
    # ⇒ 删掉就找不回来，没有「软删可恢复」这层兜底。
    pre_record = await _prefetch_for_guard(db, result_id)
    if pre_record is not None:
        await check_record_access_or_404(
            db, user_id=user.user_id, record=pre_record,
            actor_roles=user.roles,
        )
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