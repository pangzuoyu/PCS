"""P6-2 PSYCHRO API：Task 26 6 calc endpoints + psychro_persist CRUD endpoints。

端点（SPEC §3.2.5 P6-PSY-001 + §3.2.3 P6-FLR-004）：
- POST /api/v1/psychro/humidity-ratio
    body: HumidityRatioRequest
    response: HumidityRatioResponse（§3.2.5 P6-PSY-001 子项 1）
- POST /api/v1/psychro/dew-point
    body: DewPointRequest
    response: DewPointResponse（§3.2.5 子项 2）
- POST /api/v1/psychro/wet-bulb
    body: WetBulbRequest
    response: WetBulbResponse（§3.2.5 子项 3）
- POST /api/v1/psychro/enthalpy
    body: EnthalpyRequest
    response: EnthalpyResponse（§3.2.5 子项 4）
- POST /api/v1/psychro/specific-volume
    body: SpecificVolumeRequest
    response: SpecificVolumeResponse（§3.2.5 子项 5）
- POST /api/v1/psychro/cooling-coil
    body: CoolingCoilRequest
    response: CoolingCoilResponse（§3.2.5 子项 6）
- POST /api/v1/psychro/saturation-water-content/calculate
    body: SaturationWaterContentRequest
    response: SaturationWaterContentResponse（§3.2.5 子项 7 — P6-4 Task 4 C-17）
- POST   /api/v1/psychro/results        创建 PsychroResult（201）
- GET    /api/v1/psychro/results        列出（分页，DRAFT/CHECKED filter）
- GET    /api/v1/psychro/results/{id}   详情
- PATCH  /api/v1/psychro/results/{id}   更新（仅 DRAFT/CHANGE_PENDING 可改）
- DELETE /api/v1/psychro/results/{id}   软删除（→ OBSOLETE）

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（11 endpoints 统一）
- 业务异常 → 走 core.errors.PcsError envelope
- **6 个 calc endpoint 直调 chedl_wrapper 6 函数**
  （ADR-0030 V1.2 G-02 锁定包装层；禁止 endpoint 内重新包装 CoolProp）
- 计算端点（humidity-ratio / dew-point / wet-bulb / enthalpy / specific-volume
  / cooling-coil）不写 DB；落库统一由 psychro_persist endpoints 处理
  （SPEC §3.2.3 P6-FLR-004 镜像 Task 25）
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.models.enums import RecordSignStatus9
from app.schemas.psychro import (
    CoolingCoilRequest,
    CoolingCoilResponse,
    DewPointRequest,
    DewPointResponse,
    EnthalpyRequest,
    EnthalpyResponse,
    GlycolDehydrationRequest,
    GlycolDehydrationResponse,
    HumidityRatioRequest,
    HumidityRatioResponse,
    PsychroResultCreateRequest,
    PsychroResultListResponse,
    PsychroResultResponse,
    PsychroResultUpdateRequest,
    SaturationWaterContentRequest,
    SaturationWaterContentResponse,
    SpecificVolumeRequest,
    SpecificVolumeResponse,
    WetBulbRequest,
    WetBulbResponse,
)
from app.services.chedl_wrapper import (  # P6-2 Task 26 — 6 calc 包装函数
    humid_air_coil_delta_h,
    humid_air_dew_point,
    humid_air_enthalpy,
    humid_air_humidity_ratio,
    humid_air_specific_volume,
    humid_air_wet_bulb,
)
from app.services.exceptions import PcsError
from app.services.psychro import (  # P6-4 Task 4 (C-17) — 饱和水含量 service
    GlycolDehydrationInput,
    SaturationWaterContentInput,
    calc_glycol_dehydration,
    calc_saturation_water_content,
)
from app.services.psychro.psychro_persist_service import (  # P6-2 Task 26
    PsychroPersistInputError,
    save_psychro_result,
)
from app.services.psychro.psychro_persist_service import (
    get_psychro_result as get_psychro_result_service,
)
from app.services.psychro.psychro_persist_service import (
    list_psychro_results as list_psychro_results_service,
)
from app.services.psychro.psychro_persist_service import (
    soft_delete_psychro_result as soft_delete_psychro_result_service,
)
from app.services.psychro.psychro_persist_service import (
    update_psychro_result as update_psychro_result_service,
)

router = APIRouter(prefix="/psychro", tags=["psychro"])

# 公式溯源标记（5 单点 calc 公共前缀 + 1 cooling-coil 独立）
_FORMULA_REF_BASIC = "ASHRAE_RP-1845_CoolProp"
_FORMULA_REF_COIL = "ASHRAE_HF2021_§1.2"

# Celsius → Kelvin 偏移（chedl_wrapper 6 函数输入约定 K）
_C_TO_K = 273.15


def _to_http(err: PcsError) -> CorePcsError:
    """service 层 PcsError → FastAPI HTTPException envelope。

    注：P6-OPEN-010 fix — CorePcsError 使用 ``status`` kwarg（非
    ``status_code``，避免与 HTTPException 混淆）。
    """
    return CorePcsError(
        code=err.code, message=str(err), status=err.status
    )


# ============================================================================
# 6 calc endpoints（直调 chedl_wrapper 6 函数；不写 DB）
# ============================================================================


@router.post("/humidity-ratio", response_model=HumidityRatioResponse)
async def calc_humidity_ratio(
    req: HumidityRatioRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HumidityRatioResponse:
    """湿度比 W（§3.2.5 P6-PSY-001 子项 1；kg 水 / kg 干空气）。

    直调 ``chedl_wrapper.humid_air_humidity_ratio(T_K, RH, P_pa)``
    （ADR-0030 V1.2 G-02 包装层）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        w_kg_kg = humid_air_humidity_ratio(
            req.t_c + _C_TO_K, req.rh, req.p_pa
        )
    except PcsError as e:
        raise _to_http(e) from e
    except ValueError as e:
        # chedl_wrapper 校验失败（如 RH 越界）
        raise _to_http(
            CorePcsError(
                code="PSYCHRO_HUMIDITY_RATIO_INPUT_ERROR",
                message=str(e),
                status=422,
            )
        ) from e

    del db  # 计算端点不写 DB
    return HumidityRatioResponse(
        humidity_ratio_kg_kg=w_kg_kg,
        formula_ref=_FORMULA_REF_BASIC,
    )


@router.post("/dew-point", response_model=DewPointResponse)
async def calc_dew_point(
    req: DewPointRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DewPointResponse:
    """露点温度 D（§3.2.5 子项 2；°C）。

    chedl_wrapper 返回 K，本响应减 273.15 转 °C。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        d_k = humid_air_dew_point(req.t_c + _C_TO_K, req.rh, req.p_pa)
    except PcsError as e:
        raise _to_http(e) from e
    except ValueError as e:
        raise _to_http(
            CorePcsError(
                code="PSYCHRO_DEW_POINT_INPUT_ERROR",
                message=str(e),
                status=422,
            )
        ) from e

    del db
    return DewPointResponse(
        dew_point_c=d_k - _C_TO_K,
        formula_ref=_FORMULA_REF_BASIC,
    )


@router.post("/wet-bulb", response_model=WetBulbResponse)
async def calc_wet_bulb(
    req: WetBulbRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WetBulbResponse:
    """湿球温度 B（§3.2.5 子项 3；°C）。

    chedl_wrapper 返回 K，本响应减 273.15 转 °C。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        b_k = humid_air_wet_bulb(req.t_c + _C_TO_K, req.rh, req.p_pa)
    except PcsError as e:
        raise _to_http(e) from e
    except ValueError as e:
        raise _to_http(
            CorePcsError(
                code="PSYCHRO_WET_BULB_INPUT_ERROR",
                message=str(e),
                status=422,
            )
        ) from e

    del db
    return WetBulbResponse(
        wet_bulb_c=b_k - _C_TO_K,
        formula_ref=_FORMULA_REF_BASIC,
    )


@router.post("/enthalpy", response_model=EnthalpyResponse)
async def calc_enthalpy(
    req: EnthalpyRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnthalpyResponse:
    """比焓 H（§3.2.5 子项 4；kJ/kg dry air）。

    chedl_wrapper 返回 J/kg，本响应 ÷1000 转 kJ/kg。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        h_j_kg = humid_air_enthalpy(req.t_c + _C_TO_K, req.rh, req.p_pa)
    except PcsError as e:
        raise _to_http(e) from e
    except ValueError as e:
        raise _to_http(
            CorePcsError(
                code="PSYCHRO_ENTHALPY_INPUT_ERROR",
                message=str(e),
                status=422,
            )
        ) from e

    del db
    return EnthalpyResponse(
        enthalpy_kj_kg=h_j_kg / 1000.0,
        formula_ref=_FORMULA_REF_BASIC,
    )


@router.post("/specific-volume", response_model=SpecificVolumeResponse)
async def calc_specific_volume(
    req: SpecificVolumeRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SpecificVolumeResponse:
    """比容 V（§3.2.5 子项 5；m³/kg dry air）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        v_m3_kg = humid_air_specific_volume(
            req.t_c + _C_TO_K, req.rh, req.p_pa
        )
    except PcsError as e:
        raise _to_http(e) from e
    except ValueError as e:
        raise _to_http(
            CorePcsError(
                code="PSYCHRO_SPECIFIC_VOLUME_INPUT_ERROR",
                message=str(e),
                status=422,
            )
        ) from e

    del db
    return SpecificVolumeResponse(
        specific_volume_m3_kg=v_m3_kg,
        formula_ref=_FORMULA_REF_BASIC,
    )


@router.post("/cooling-coil", response_model=CoolingCoilResponse)
async def calc_cooling_coil(
    req: CoolingCoilRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CoolingCoilResponse:
    """冷却盘管显热 + 潜热（§3.2.5 子项 6；kW）。

    计算链（直调 chedl_wrapper 两个函数，包装层未做单位换算）：

    1. ``humid_air_coil_delta_h(T1_K, rh1, T2_K, rh2, P_pa)`` →
       ``(Q_sensible_J_kg, Q_latent_J_kg)``（J/kg dry air）
    2. 取平均状态 (T_avg, RH_avg) →
       ``humid_air_specific_volume(T_avg_K, RH_avg, P_pa)`` → ``v_m3_kg``
       （用于推算 m_dot_kg_s = q_air_m3_s / v_m3_kg）
    3. 显热 kW = m_dot_kg_s × Q_sensible / 1000
       潜热 kW = m_dot_kg_s × Q_latent / 1000

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    t1_k = req.t1_c + _C_TO_K
    t2_k = req.t2_c + _C_TO_K
    rh_avg = 0.5 * (req.rh1 + req.rh2)
    t_avg_c = 0.5 * (req.t1_c + req.t2_c)
    try:
        q_sensible_j_kg, q_latent_j_kg = humid_air_coil_delta_h(
            t1_k, req.rh1, t2_k, req.rh2, req.p_pa
        )
        v_avg_m3_kg = humid_air_specific_volume(
            t_avg_c + _C_TO_K, rh_avg, req.p_pa
        )
    except PcsError as e:
        raise _to_http(e) from e
    except ValueError as e:
        raise _to_http(
            CorePcsError(
                code="PSYCHRO_COOLING_COIL_INPUT_ERROR",
                message=str(e),
                status=422,
            )
        ) from e

    if v_avg_m3_kg <= 0:
        raise _to_http(
            CorePcsError(
                code="PSYCHRO_COOLING_COIL_INVALID_SPECIFIC_VOLUME",
                message=(
                    f"average specific_volume 非正（v={v_avg_m3_kg}），"
                    "无法推算 m_dot"
                ),
                status=422,
            )
        )
    m_dot_kg_s = req.q_air_m3_s / v_avg_m3_kg
    sensible_kw = m_dot_kg_s * q_sensible_j_kg / 1000.0
    latent_kw = m_dot_kg_s * q_latent_j_kg / 1000.0

    del db
    return CoolingCoilResponse(
        sensible_heat_kw=sensible_kw,
        latent_heat_kw=latent_kw,
        formula_ref=_FORMULA_REF_COIL,
    )


@router.post(
    "/saturation-water-content/calculate",
    response_model=SaturationWaterContentResponse,
)
async def calc_saturation_water_content_endpoint(
    req: SaturationWaterContentRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SaturationWaterContentResponse:
    """饱和水含量 W_sat（§3.2.5 P6-PSY-001 §3.9.2 — P6-4 Task 4 C-17 显式水含量）。

    直调 ``calc_saturation_water_content`` service（service 内 RH=1.0 直调
    ``chedl_wrapper.humid_air_humidity_ratio``，不重复包装 CoolProp）：
    - 3 独立单位输出（kg/kg / mg/Sm³ / lb/MMscf）
    - ISO 18453 简式酸性气校正（CO2+H2S > 40 mol%）
    - 温压越界（T ∉ [-50, 100]°C 或 P > ~100 atm）→ WARNING + NaN
      （SPEC §3.2.5 "WARNING，不抛错"约定）
    - D14 lru_cache(maxsize=4096)（service 层；同 (T, P, composition) 缓存命中）

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        result = calc_saturation_water_content(
            SaturationWaterContentInput(
                temperature_c=req.temperature_c,
                pressure_kpa=req.pressure_kpa,
                acidic_gas_composition=req.acidic_gas_composition or {},
                units=req.units,
            )
        )
    except PcsError as e:
        raise _to_http(e) from e

    del db  # 计算端点不写 DB
    return SaturationWaterContentResponse(
        saturation_w_kg_kg=result.saturation_w_kg_kg,
        saturation_w_mg_sm3=result.saturation_w_mg_sm3,
        saturation_w_lb_per_mmscf=result.saturation_w_lb_per_mmscf,
        saturation_T_c=result.saturation_T_c,
        temperature_out_of_range=result.temperature_out_of_range,
        warning_message=result.warning_message,
        acidic_gas_correction_applied=result.acidic_gas_correction_applied,
        acidic_gas_correction_factor=result.acidic_gas_correction_factor,
        formula_ref=result.formula_ref,
    )


# ============================================================================
# 8. P6-6A-6 (Ruling 5 closure, v4) POST /psychro/glycol-dehydration/calculate
# ============================================================================


@router.post(
    "/glycol-dehydration/calculate",
    response_model=GlycolDehydrationResponse,
)
async def calc_glycol_dehydration_endpoint(
    req: GlycolDehydrationRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GlycolDehydrationResponse:
    """FULL 甘醇脱水系统（§3.9.1 — P6-6A-6 Ruling 5 closure, v4）。

    11 OUT_OF_SCOPE 字段 + 现有 7 字段 + dewpoint_unavailable_reason +
    acid_gas_corrected；TEG only（DEG v5.1 Ruling 5 FULL system 不支持，
    service 层抛 GlycolDehydrationError → 422）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        result = calc_glycol_dehydration(
            GlycolDehydrationInput(
                gas_flow_mmscfd=req.gas_flow_mmscfd,
                inlet_water_content_lb_per_mmscf=req.inlet_water_content_lb_per_mmscf,
                outlet_water_content_lb_per_mmscf=req.outlet_water_content_lb_per_mmscf,
                glycol_type=req.glycol_type,
                contactor_tray_count=req.contactor_tray_count,
                glycol_circulation_rate_gpm=req.glycol_circulation_rate_gpm,
                relative_volatility=req.relative_volatility,
                imperial_units=req.imperial_units,
                temperature_f=req.temperature_f,
                pressure_psia=req.pressure_psia,
                lean_glycol_concentration=req.lean_glycol_concentration,
                vapour_space_ft=req.vapour_space_ft,
                sump_height_ft=req.sump_height_ft,
                hetp_ft=req.hetp_ft,
                approach_to_equilibrium_f=req.approach_to_equilibrium_f,
                flooding_c_sb=req.flooding_c_sb,  # v3
                co2_mol_pct=req.co2_mol_pct,  # v4
                h2s_mol_pct=req.h2s_mol_pct,  # v4
            )
        )
    except PcsError as e:
        raise _to_http(e) from e

    del db  # 计算端点不写 DB
    return GlycolDehydrationResponse(
        dehydration_efficiency=result.dehydration_efficiency,
        n_tray_minimum=result.n_tray_minimum,
        is_tray_count_ok=result.is_tray_count_ok,
        teg_loss_gpd=result.teg_loss_gpd,
        contactor_diameter_in=result.contactor_diameter_in,
        imperial_conversion=result.imperial_conversion,
        formula_ref=result.formula_ref,
        water_dewpoint_f=result.water_dewpoint_f,
        adjusted_dewpoint_f=result.adjusted_dewpoint_f,
        lean_glycol_concentration=result.lean_glycol_concentration
        if result.lean_glycol_concentration is not None
        else req.lean_glycol_concentration,
        stripping_gas_scf_per_gal_teg=result.stripping_gas_scf_per_gal_teg,
        column_diameter_full_in=result.column_diameter_full_in
        if result.column_diameter_full_in is not None
        else 0.0,
        column_height_ft=result.column_height_ft
        if result.column_height_ft is not None
        else 0.0,
        number_of_transfer_units=result.number_of_transfer_units
        if result.number_of_transfer_units is not None
        else 0.0,
        mass_h2o_removed_lb_s=result.mass_h2o_removed_lb_s
        if result.mass_h2o_removed_lb_s is not None
        else 0.0,
        reboiler_duty_btu_hr=result.reboiler_duty_btu_hr
        if result.reboiler_duty_btu_hr is not None
        else 0.0,
        column_csa_ft2=result.column_csa_ft2
        if result.column_csa_ft2 is not None
        else 0.0,
        dewpoint_unavailable_reason=result.dewpoint_unavailable_reason,  # v3
        acid_gas_corrected=result.acid_gas_corrected,  # v4
        glycol_type=req.glycol_type,
    )


# ============================================================================
# psychro_persist CRUD
# ============================================================================


@router.post("/results", response_model=PsychroResultResponse, status_code=201)
async def create_psychro_result(
    req: PsychroResultCreateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PsychroResultResponse:
    """创建 PsychroResult 行（POST → 201）。

    ``save_psychro_result`` service 层自动 final record_hash
    （ADR-0028 §决策 4），并自动从 ``get_coolprop_version()`` 兜底写入
    ``coolprop_version`` 字段（payload 缺时；SPEC §3.2.5 溯源要求）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # 字符串 sign_status → enum（非法字面 → 422 PcsError envelope）
    try:
        sign_status_enum = RecordSignStatus9(req.sign_status)
    except ValueError as e:
        raise _to_http(
            CorePcsError(
                code="PSYCHRO_RESULT_SIGN_STATUS_INVALID",
                message=f"sign_status={req.sign_status!r} 非法：{e}",
                status=422,
            )
        ) from e
    # 业务 payload：排除溯源 / mixin 必填（已拆为 save_psychro_result
    # 显式 kwarg）
    payload = req.model_dump(
        exclude={
            "project_id",
            "workspace_id",
            "tag_number",
            "standard_profile_code",
            "calc_type",
            "sign_status",
        },
    )
    actor_id = getattr(user, "id", None) or getattr(user, "user_id", None)
    try:
        record = await save_psychro_result(
            db,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            tag_number=req.tag_number,
            standard_profile_code=req.standard_profile_code,
            calc_type=req.calc_type,
            sign_status=sign_status_enum,
            payload=payload,
            created_by=actor_id,
        )
    except PsychroPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return PsychroResultResponse.model_validate(record, from_attributes=True)


@router.get("/results", response_model=PsychroResultListResponse)
async def list_psychro_results(
    project_id: Annotated[uuid.UUID, Query(...)],
    standard_profile_code: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> PsychroResultListResponse:
    """按 project_id 列出 PsychroResult（GET list，分页）。

    默认 sign_status filter = (DRAFT, CHECKED) — 排除 OBSOLETE 等门禁态。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    records = await list_psychro_results_service(
        db,
        project_id=project_id,
        standard_profile_code=standard_profile_code,
        limit=limit,
        offset=offset,
    )
    items = [
        PsychroResultResponse.model_validate(r, from_attributes=True)
        for r in records
    ]
    return PsychroResultListResponse(
        items=items, total=len(items), limit=limit, offset=offset
    )


@router.get("/results/{record_id}", response_model=PsychroResultResponse)
async def get_psychro_result(
    record_id: uuid.UUID,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> PsychroResultResponse:
    """按 id 取 PsychroResult（GET detail）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    record = await get_psychro_result_service(db, record_id=record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="PsychroResult not found"
        )
    return PsychroResultResponse.model_validate(record, from_attributes=True)


@router.patch("/results/{record_id}", response_model=PsychroResultResponse)
async def update_psychro_result(
    record_id: uuid.UUID,
    req: PsychroResultUpdateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PsychroResultResponse:
    """更新 PsychroResult 业务字段（PATCH；仅 DRAFT/CHANGE_PENDING 可改）。

    CHECKED / IN_APPROVAL / REVERSAL_PENDING 等锁定态拒绝更新（避免
    评审中数据漂移）。project_id 由 ACL 在 Phase 后续 PATCH 透传；本
    批次为 None（service 层不强制隔离）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    payload = req.model_dump(exclude_unset=True)
    try:
        record = await update_psychro_result_service(
            db,
            record_id=record_id,
            project_id=None,
            payload=payload,
        )
    except PsychroPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e
    if record is None:
        raise HTTPException(
            status_code=404, detail="PsychroResult not found"
        )
    return PsychroResultResponse.model_validate(record, from_attributes=True)


@router.delete("/results/{record_id}", status_code=204)
async def delete_psychro_result(
    record_id: uuid.UUID,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> None:
    """软删除 PsychroResult（DELETE → sign_status=OBSOLETE）。

    软删而非物理删除（SPEC §3.2.3 P6-FLR-004 审计要求）；记录不再被
    list 默认过滤（DRAFT/CHECKED filter）展示。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    ok = await soft_delete_psychro_result_service(
        db, record_id=record_id, project_id=None
    )
    if not ok:
        raise HTTPException(
            status_code=404, detail="PsychroResult not found"
        )


__all__ = ["router"]
