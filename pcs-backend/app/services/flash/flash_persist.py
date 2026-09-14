"""P4-1-3 FLASH 计算落库 + 状态点联动 + 出口物流（service 层）。

统一入口流程（3 端点共用）：
1. ``check_calc_inputs(db, [stream_id])`` — 三步守卫（404/403/422）
2. 读 stream → 提取 T/P/组成/CASs + system_type
3. 调 ``flash_service.<calc>`` 拿结果
4. 构造 ``FlashResult`` ORM + 落库（input_json + output_json + calc_type + method）
5. ``finalize_calc_record(db, record, source_stream_ids=[stream_id], formula_version=...)``
6. 状态点联动（ADR-0020）：calc 出 vfrac 时写回 stream.stream_properties_json
   - 键不存在 → 写入（estimated=true）
   - 键存在且值不同 → 写 conflict_resolutions_json，**不静默覆盖** user 值
   - 键存在且值相同 → no-op
7. 出口物流（ADR-0022）：PT/PH/PS/BUBBLE/DEW 产生新物流 → outlet DRAFT
8. commit + 返回响应数据

calc_type 与 FlashResult.calc_type 一一映射（8 种）：
PT_FLASH / PH_FLASH / PS_FLASH / SATURATION / BUBBLE_P / BUBBLE_T / DEW_P / DEW_T

method 字段：当前为占位 stub 实现，记为 "RAOULT_WAGNER"（P4-1-2 物性包），
native 物性包替换后由 build_thermo 返回 class 名覆盖。

不做：
- 不写 record_hash 之外的审计列（只经 calc_lineage.finalize_calc_record）
- 不写 stream.sign_status（StreamService.transition 统一入口）
- 不并发锁（batch 入口由 SELECT FOR UPDATE 在 StateMachineService 兜底；本
  模块只 flush → finalize，不与状态机交互）
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import FlashResult
from app.models.project import Stream
from app.services.calc_entry import check_calc_inputs
from app.services.calc_lineage import finalize_calc_record
from app.services.flash.flash_service import (
    BUBBLE_P,
    BUBBLE_T,
    DEW_P,
    DEW_T,
    PH_FLASH,
    PS_FLASH,
    PT_FLASH,
    SATURATION,
)
from app.services.flash.thermo_factory import build_thermo
from app.services.outlet_stream import create_outlet_stream

# P4-1-2 物性包：Wagner + Raoult + Rachford-Rice 解析
_FORMULA_VERSION = "Fv1.0-flash-stub"
_METHOD_DEFAULT = "RAOULT_WAGNER"

# calc_type → 是否产生 outlet 流（SATURATION 纯组分，无源流组成更新）
_OUTLET_CALC_TYPES: frozenset[str] = frozenset(
    {"PT_FLASH", "PH_FLASH", "PS_FLASH", "BUBBLE_P", "BUBBLE_T", "DEW_P", "DEW_T"}
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _system_type_from_data_mode(data_mode: str | None) -> str:
    """data_mode → THERMO_METHOD_MAP key。

    映射规则：
    - "CHEMICAL" → LIGHT_HYDROCARBON（默认；占位）
    - "PETROLEUM" → GAS_PROCESSING
    - "SOLID" / None → LIGHT_HYDROCARBON（兜底）

    P4-1-4+ 改由 stream.system_type 字段驱动；本批次使用 data_mode 近似。
    """
    if data_mode == "PETROLEUM":
        return "GAS_PROCESSING"
    return "LIGHT_HYDROCARBON"


def _extract_composition(stream: Stream) -> tuple[list[float], list[str]]:
    """从 stream.composition_json 提取 zs + cass（按 CAS 字典序保证稳定）。

    Returns:
        (zs, cass) — 长度相同的并列 list

    Raises:
        ValueError: composition_json 缺失或格式不对
    """
    comp = stream.composition_json or {}
    if not comp:
        raise ValueError(
            f"stream {stream.stream_id} 缺少 composition_json；无法进行 flash 计算"
        )
    cass = sorted(comp.keys())
    zs = [float(comp[c]) for c in cass]
    return zs, cass


def _generate_tag_number(project_id: uuid.UUID) -> str:
    """生成项目内唯一 FlashResult tag_number（ADR-0003 + TaggedRecordMixin）。

    格式：``FLASH-{short_uuid}``（短码 8 位 hex；项目内由 DB unique 约束兜底）。
    P4-TASK0 批次替换为 NumberingService 编号（届时本函数删除）。
    """
    return f"FLASH-{uuid.uuid4().hex[:8].upper()}"


def _normalize_temp_press(stream: Stream, T_K: float, P_Pa: float) -> tuple[float, float]:
    """归一化 T/P：API 入参 SI (K/Pa)；stream.temp/press 兜底。

    当前 API 直接传 T_K/P_Pa；保留扩展位。
    """
    return float(T_K), float(P_Pa)


def _link_state_point(
    stream: Stream,
    calc_vfrac: float,
) -> None:
    """状态点联动（ADR-0020）：写回 stream.stream_properties_json。

    行为契约：
    - 键不存在 → 写入 {vapor_fraction, _source, _estimated}
    - 键存在且值==calc_value → no-op（幂等）
    - 键存在且值!=calc_value → **不静默覆盖** user 值；写 conflict_resolutions_json

    冲突格式：``conflict_resolutions_json[field_name] =
        {user_value, calc_value, source, ts}``
    """
    spj = dict(stream.stream_properties_json or {})
    existing = spj.get("vapor_fraction")
    if existing is None:
        spj["vapor_fraction"] = float(calc_vfrac)
        spj["_source"] = "FLASH_CALCULATED"
        spj["_estimated"] = True
        stream.stream_properties_json = spj
        return

    if abs(float(existing) - float(calc_vfrac)) < 1e-12:
        # 幂等：值一致不动作
        return

    # 冲突：保留 user 值；写 conflict_resolutions_json
    crj = dict(stream.conflict_resolutions_json or {})
    crj["vapor_fraction"] = {
        "user_value": existing,
        "calc_value": float(calc_vfrac),
        "source": "FLASH_CALCULATED",
        "ts": "P4-1-3",
        "resolver": "user-wins",
    }
    stream.conflict_resolutions_json = crj
    # spj 中 user 值保留不变（不静默覆盖）


def _writeback_properties(
    stream: Stream,
    calc_result: dict[str, float],
    calc_type: str,
) -> None:
    """P4-1-4：calc → stream.stream_properties_json 反向写入（H/S/vfrac）。

    行为契约（沿 P4-1-3 user-wins）：
    - calc_result 含 ``vapor_fraction`` 时：仅 0 < v < 1（单相不污染）→ 写入
    - calc_result 含 ``enthalpy`` 时：calc 提供 → 写入
    - calc_result 含 ``entropy`` 时：calc 提供 → 写入
    - stream_properties_json[key] 已存在 → calc 值入
      conflict_resolutions_json[key] = {user_value, calc_value, source, resolver=user-wins}；
      effective 值不变（user-wins 生效）
    - stream_properties_json[key] 缺失 → 写入 stream_properties_json[key]，
      附 _source=FLASH_CALCULATED + estimated=true

    Args:
        stream: 目标 Stream ORM 对象（in-place 修改；commit 由调用方负责）
        calc_result: 计算输出 dict，可含 vapor_fraction / enthalpy / entropy
        calc_type: 计算类型（PT_FLASH / PH_FLASH / PS_FLASH / ...），仅用于标注
    """
    # 候选写入键：按 calc_type 过滤 + 单相不污染
    candidates: list[tuple[str, float]] = []
    if "vapor_fraction" in calc_result:
        vf = float(calc_result["vapor_fraction"])
        if 0.0 < vf < 1.0:  # 单相 (v=0/1) 不污染
            candidates.append(("vapor_fraction", vf))
    if "enthalpy" in calc_result:
        candidates.append(("enthalpy", float(calc_result["enthalpy"])))
    if "entropy" in calc_result:
        candidates.append(("entropy", float(calc_result["entropy"])))

    if not candidates:
        return

    spj = dict(stream.stream_properties_json or {})
    crj = dict(stream.conflict_resolutions_json or {})

    for key, calc_value in candidates:
        existing = spj.get(key)
        if existing is None:
            # 未设值 → 写入 + 标记
            spj[key] = float(calc_value)
            spj["_source"] = "FLASH_CALCULATED"
            spj["_estimated"] = True
            continue

        try:
            existing_f = float(existing)
        except (TypeError, ValueError):
            existing_f = None

        if existing_f is not None and abs(existing_f - float(calc_value)) < 1e-12:
            # 幂等：值一致不动作
            continue

        # 冲突：保留 user 值；写 conflict_resolutions_json
        crj[key] = {
            "user_value": existing,
            "calc_value": float(calc_value),
            "source": "FLASH_CALCULATED",
            "ts": "P4-1-4",
            "resolver": "user-wins",
        }

    stream.stream_properties_json = spj
    stream.conflict_resolutions_json = crj


# ---------------------------------------------------------------------------
# Core entry points（3 端点对应）
# ---------------------------------------------------------------------------


async def persist_pt_flash(
    db: AsyncSession,
    *,
    stream_id: uuid.UUID,
    T_K: float,
    P_Pa: float,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """PT_FLASH 落库 + 状态点联动 + outlet 流。"""
    await check_calc_inputs(db, [stream_id])
    stream = await db.get(Stream, stream_id)
    if stream is None:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"Stream {stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )
    zs, cass = _extract_composition(stream)
    T_K, P_Pa = _normalize_temp_press(stream, T_K, P_Pa)
    system_type = _system_type_from_data_mode(stream.data_mode)
    thermo = build_thermo(system_type, zs, cass)

    result = PT_FLASH(zs, T_K, P_Pa, thermo)

    # P4-1-4：PT_FLASH 隐式产出 H/S（占位 thermo 模型）；写入 record + 反向回写
    h_calc = thermo.H_PT(
        zs, T_K, P_Pa, result.vapor_fraction, result.y_vapor, result.x_liquid
    )
    s_calc = thermo.S_PT(
        zs, T_K, P_Pa, result.vapor_fraction, result.y_vapor, result.x_liquid
    )

    # 构造 record
    record = FlashResult(
        tag_number=_generate_tag_number(stream.project_id),
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
        stream_id=stream.stream_id,
        calc_type="PT_FLASH",
        method=_METHOD_DEFAULT,
        input_json={
            "T_K": T_K,
            "P_Pa": P_Pa,
            "zs": zs,
            "cass": cass,
            "system_type": system_type,
        },
        output_json={
            "vapor_fraction": result.vapor_fraction,
            "y_vapor": result.y_vapor,
            "x_liquid": result.x_liquid,
            "enthalpy": h_calc,
            "entropy": s_calc,
        },
    )
    db.add(record)
    await db.flush()  # 让 flash_id 落库（finalize 内 LineageTracker 也需要 PK）

    await finalize_calc_record(
        db,
        record,
        source_stream_ids=[stream.stream_id],
        formula_version=_FORMULA_VERSION,
    )

    # 状态点联动：仅当 2-phase 时写 vfrac（v=0/1 单相不写，避免污染）
    if 0.0 < result.vapor_fraction < 1.0:
        _link_state_point(stream, result.vapor_fraction)
    # P4-1-4 反向写入：vfrac（2-phase 时）+ enthalpy + entropy（H/S 来自 thermo）
    _writeback_properties(
        stream,
        {"vapor_fraction": result.vapor_fraction, "enthalpy": h_calc, "entropy": s_calc},
        "PT_FLASH",
    )

    # 出口物流（PT_FLASH 总是产生 outlet 流 — 包含两相/单相结果）
    outlet = await create_outlet_stream(
        db,
        source_stream_id=stream.stream_id,
        calc_type="PT_FLASH",
        source_type="FLASH_CALCULATED",
        properties={
            "vapor_fraction": result.vapor_fraction,
            "y_vapor": result.y_vapor,
            "x_liquid": result.x_liquid,
            "T_K": T_K,
            "P_Pa": P_Pa,
            "_calc_type": "PT_FLASH",
        },
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
    )

    # 回填 outlet vapor_fraction（create_outlet_stream 初始化为 None）
    outlet.vapor_fraction = result.vapor_fraction
    outlet.y_vapor = result.y_vapor
    outlet.x_liquid = result.x_liquid
    await db.flush()

    await db.commit()
    return {
        "calc_id": record.flash_id,
        "calc_type": record.calc_type,
        "record_hash": record.record_hash,
        "stream_id": stream.stream_id,
        "result": {
            "vapor_fraction": result.vapor_fraction,
            "y_vapor": result.y_vapor,
            "x_liquid": result.x_liquid,
        },
        "outlet_stream_id": outlet.stream_id,
        "outlet_stream_name": outlet.stream_name,
    }


async def persist_ph_flash(
    db: AsyncSession,
    *,
    stream_id: uuid.UUID,
    T_K: float,
    H_target: float,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """PH_FLASH 落库 + 状态点联动 + outlet 流。"""
    await check_calc_inputs(db, [stream_id])
    stream = await db.get(Stream, stream_id)
    if stream is None:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"Stream {stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )
    zs, cass = _extract_composition(stream)
    system_type = _system_type_from_data_mode(stream.data_mode)
    thermo = build_thermo(system_type, zs, cass)

    P, vfrac, y, x = PH_FLASH(zs, T_K, H_target, thermo)

    # P4-1-4：PH_FLASH 显式提供 H（H_target），写入 record + 反向回写
    record = FlashResult(
        tag_number=_generate_tag_number(stream.project_id),
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
        stream_id=stream.stream_id,
        calc_type="PH_FLASH",
        method=_METHOD_DEFAULT,
        input_json={
            "T_K": T_K,
            "H_target": H_target,
            "zs": zs,
            "cass": cass,
            "system_type": system_type,
        },
        output_json={
            "P_Pa": P,
            "vapor_fraction": vfrac,
            "y_vapor": y,
            "x_liquid": x,
            "enthalpy": H_target,
        },
    )
    db.add(record)
    await db.flush()
    await finalize_calc_record(
        db,
        record,
        source_stream_ids=[stream.stream_id],
        formula_version=_FORMULA_VERSION,
    )
    if 0.0 < vfrac < 1.0:
        _link_state_point(stream, vfrac)
    # P4-1-4 反向写入：vfrac（2-phase 时）+ enthalpy（H_target）
    _writeback_properties(
        stream,
        {"vapor_fraction": vfrac, "enthalpy": H_target},
        "PH_FLASH",
    )
    outlet = await create_outlet_stream(
        db,
        source_stream_id=stream.stream_id,
        calc_type="PH_FLASH",
        source_type="FLASH_CALCULATED",
        properties={
            "P_Pa": P,
            "vapor_fraction": vfrac,
            "y_vapor": y,
            "x_liquid": x,
            "T_K": T_K,
            "H_target": H_target,
            "_calc_type": "PH_FLASH",
        },
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
    )
    outlet.vapor_fraction = vfrac
    await db.flush()
    await db.commit()
    return {
        "calc_id": record.flash_id,
        "calc_type": record.calc_type,
        "record_hash": record.record_hash,
        "stream_id": stream.stream_id,
        "result": {"P_Pa": P, "vapor_fraction": vfrac, "y_vapor": y, "x_liquid": x},
        "outlet_stream_id": outlet.stream_id,
        "outlet_stream_name": outlet.stream_name,
    }


async def persist_ps_flash(
    db: AsyncSession,
    *,
    stream_id: uuid.UUID,
    T_K: float,
    S_target: float,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """PS_FLASH 落库 + 状态点联动 + outlet 流。"""
    await check_calc_inputs(db, [stream_id])
    stream = await db.get(Stream, stream_id)
    if stream is None:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"Stream {stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )
    zs, cass = _extract_composition(stream)
    system_type = _system_type_from_data_mode(stream.data_mode)
    thermo = build_thermo(system_type, zs, cass)

    vfrac, y, x, P = PS_FLASH(zs, T_K, S_target, thermo)

    # P4-1-4：PS_FLASH 显式提供 S（S_target），写入 record + 反向回写
    record = FlashResult(
        tag_number=_generate_tag_number(stream.project_id),
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
        stream_id=stream.stream_id,
        calc_type="PS_FLASH",
        method=_METHOD_DEFAULT,
        input_json={
            "T_K": T_K,
            "S_target": S_target,
            "zs": zs,
            "cass": cass,
            "system_type": system_type,
        },
        output_json={
            "P_Pa": P,
            "vapor_fraction": vfrac,
            "y_vapor": y,
            "x_liquid": x,
            "entropy": S_target,
        },
    )
    db.add(record)
    await db.flush()
    await finalize_calc_record(
        db,
        record,
        source_stream_ids=[stream.stream_id],
        formula_version=_FORMULA_VERSION,
    )
    if 0.0 < vfrac < 1.0:
        _link_state_point(stream, vfrac)
    # P4-1-4 反向写入：vfrac（2-phase 时）+ entropy（S_target）
    _writeback_properties(
        stream,
        {"vapor_fraction": vfrac, "entropy": S_target},
        "PS_FLASH",
    )
    outlet = await create_outlet_stream(
        db,
        source_stream_id=stream.stream_id,
        calc_type="PS_FLASH",
        source_type="FLASH_CALCULATED",
        properties={
            "P_Pa": P,
            "vapor_fraction": vfrac,
            "y_vapor": y,
            "x_liquid": x,
            "T_K": T_K,
            "S_target": S_target,
            "_calc_type": "PS_FLASH",
        },
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
    )
    outlet.vapor_fraction = vfrac
    await db.flush()
    await db.commit()
    return {
        "calc_id": record.flash_id,
        "calc_type": record.calc_type,
        "record_hash": record.record_hash,
        "stream_id": stream.stream_id,
        "result": {"P_Pa": P, "vapor_fraction": vfrac, "y_vapor": y, "x_liquid": x},
        "outlet_stream_id": outlet.stream_id,
        "outlet_stream_name": outlet.stream_name,
    }


async def persist_saturation(
    db: AsyncSession,
    *,
    stream_id: uuid.UUID,
    fluid: str,
    P: float | None = None,
    T: float | None = None,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """SATURATION 落库（纯组分计算，无 outlet 流）。"""
    # SATURATION 是纯组分计算，不做 check_calc_inputs 三步守卫（无组分输入）
    # 但仍校验 stream 存在（API 层校验 → 实际由 stream_id 走数据库）
    stream = await db.get(Stream, stream_id)
    if stream is None:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"Stream {stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )

    other, h_fg = SATURATION(fluid, P=P, T=T)

    record = FlashResult(
        tag_number=_generate_tag_number(stream.project_id),
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
        stream_id=stream.stream_id,
        calc_type="SATURATION",
        method=_METHOD_DEFAULT,
        input_json={"fluid": fluid, "P_Pa": P, "T_K": T},
        output_json={
            "other_var": other,
            "h_fg_J_per_kg": h_fg,
            # 简化：明确键名供 API 响应直接读取
            **(
                {"T_sat_K": other, "h_fg_J_per_kg": h_fg}
                if P is not None
                else {"P_sat_Pa": other, "h_fg_J_per_kg": h_fg}
            ),
        },
    )
    db.add(record)
    await db.flush()
    await finalize_calc_record(
        db,
        record,
        source_stream_ids=[stream.stream_id],
        formula_version=_FORMULA_VERSION,
    )
    await db.commit()
    return {
        "calc_id": record.flash_id,
        "calc_type": record.calc_type,
        "record_hash": record.record_hash,
        "stream_id": stream.stream_id,
        "result": dict(record.output_json),
        "outlet_stream_id": None,
        "outlet_stream_name": None,
    }


async def persist_bubble(
    db: AsyncSession,
    *,
    stream_id: uuid.UUID,
    mode: str,  # "T" 给 T 求 P_bubble；"P" 给 P 求 T_bubble
    value: float,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """BUBBLE 落库 + outlet 流（mode=T → BUBBLE_P；mode=P → BUBBLE_T）。"""
    await check_calc_inputs(db, [stream_id])
    stream = await db.get(Stream, stream_id)
    if stream is None:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"Stream {stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )
    zs, cass = _extract_composition(stream)
    system_type = _system_type_from_data_mode(stream.data_mode)
    thermo = build_thermo(system_type, zs, cass)

    if mode == "T":
        # 给 T 求 P_bubble
        result = BUBBLE_P(zs, float(value), thermo)
        calc_type = "BUBBLE_P"
        result_label = "bubble_P_Pa"
        input_label = {"T_K": float(value)}
    elif mode == "P":
        # 给 P 求 T_bubble
        result = BUBBLE_T(zs, float(value), thermo)
        calc_type = "BUBBLE_T"
        result_label = "bubble_T_K"
        input_label = {"P_Pa": float(value)}
    else:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"BUBBLE mode 必须是 T 或 P，当前={mode!r}",
            code="FLASH_INPUT_ERROR",
            status=422,
        )

    record = FlashResult(
        tag_number=_generate_tag_number(stream.project_id),
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
        stream_id=stream.stream_id,
        calc_type=calc_type,
        method=_METHOD_DEFAULT,
        input_json={**input_label, "zs": zs, "cass": cass, "system_type": system_type},
        output_json={result_label: result},
    )
    db.add(record)
    await db.flush()
    await finalize_calc_record(
        db,
        record,
        source_stream_ids=[stream.stream_id],
        formula_version=_FORMULA_VERSION,
    )

    # 出口物流：outlet stream T/P 按 mode 不同设置
    if mode == "T":
        outlet_props = {
            "T_K": float(value),
            "P_Pa": result,
            "phase": "BUBBLE",
            "_calc_type": calc_type,
        }
    else:
        outlet_props = {
            "P_Pa": float(value),
            "T_K": result,
            "phase": "BUBBLE",
            "_calc_type": calc_type,
        }
    outlet = await create_outlet_stream(
        db,
        source_stream_id=stream.stream_id,
        calc_type=calc_type,
        source_type="FLASH_CALCULATED",
        properties=outlet_props,
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
    )
    await db.commit()
    return {
        "calc_id": record.flash_id,
        "calc_type": calc_type,
        "record_hash": record.record_hash,
        "stream_id": stream.stream_id,
        "result": {result_label: result},
        # 兼容 API 响应：bubble_T_K / bubble_P_Pa 在顶层
        result_label: result,
        "outlet_stream_id": outlet.stream_id,
        "outlet_stream_name": outlet.stream_name,
    }


async def persist_dew(
    db: AsyncSession,
    *,
    stream_id: uuid.UUID,
    mode: str,  # "T" 给 T 求 P_dew；"P" 给 P 求 T_dew
    value: float,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """DEW 落库 + outlet 流（mode=T → DEW_P；mode=P → DEW_T）。"""
    await check_calc_inputs(db, [stream_id])
    stream = await db.get(Stream, stream_id)
    if stream is None:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"Stream {stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )
    zs, cass = _extract_composition(stream)
    system_type = _system_type_from_data_mode(stream.data_mode)
    thermo = build_thermo(system_type, zs, cass)

    if mode == "T":
        result = DEW_P(zs, float(value), thermo)
        calc_type = "DEW_P"
        result_label = "dew_P_Pa"
        input_label = {"T_K": float(value)}
    elif mode == "P":
        result = DEW_T(zs, float(value), thermo)
        calc_type = "DEW_T"
        result_label = "dew_T_K"
        input_label = {"P_Pa": float(value)}
    else:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"DEW mode 必须是 T 或 P，当前={mode!r}",
            code="FLASH_INPUT_ERROR",
            status=422,
        )

    record = FlashResult(
        tag_number=_generate_tag_number(stream.project_id),
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
        stream_id=stream.stream_id,
        calc_type=calc_type,
        method=_METHOD_DEFAULT,
        input_json={**input_label, "zs": zs, "cass": cass, "system_type": system_type},
        output_json={result_label: result},
    )
    db.add(record)
    await db.flush()
    await finalize_calc_record(
        db,
        record,
        source_stream_ids=[stream.stream_id],
        formula_version=_FORMULA_VERSION,
    )

    if mode == "T":
        outlet_props = {
            "T_K": float(value),
            "P_Pa": result,
            "phase": "DEW",
            "_calc_type": calc_type,
        }
    else:
        outlet_props = {
            "P_Pa": float(value),
            "T_K": result,
            "phase": "DEW",
            "_calc_type": calc_type,
        }
    outlet = await create_outlet_stream(
        db,
        source_stream_id=stream.stream_id,
        calc_type=calc_type,
        source_type="FLASH_CALCULATED",
        properties=outlet_props,
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
    )
    await db.commit()
    return {
        "calc_id": record.flash_id,
        "calc_type": calc_type,
        "record_hash": record.record_hash,
        "stream_id": stream.stream_id,
        "result": {result_label: result},
        result_label: result,
        "outlet_stream_id": outlet.stream_id,
        "outlet_stream_name": outlet.stream_name,
    }


# ---------------------------------------------------------------------------
# API 统一调度入口
# ---------------------------------------------------------------------------


async def persist_calculate(
    db: AsyncSession,
    *,
    calc_type: str,
    stream_id: uuid.UUID,
    T_K: float | None = None,
    P_Pa: float | None = None,
    H_target: float | None = None,
    S_target: float | None = None,
    fluid: str | None = None,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """POST /api/v1/flash/calculate 统一调度：按 calc_type 派发到对应 persist_* 函数。"""
    if calc_type == "PT_FLASH":
        if T_K is None or P_Pa is None:
            from app.services.exceptions import PcsError

            raise PcsError(
                "PT_FLASH 必须给 T_K + P_Pa",
                code="FLASH_INPUT_ERROR",
                status=422,
            )
        return await persist_pt_flash(
            db, stream_id=stream_id, T_K=T_K, P_Pa=P_Pa, actor=actor
        )
    if calc_type == "PH_FLASH":
        if T_K is None or H_target is None:
            from app.services.exceptions import PcsError

            raise PcsError(
                "PH_FLASH 必须给 T_K + H_target",
                code="FLASH_INPUT_ERROR",
                status=422,
            )
        return await persist_ph_flash(
            db, stream_id=stream_id, T_K=T_K, H_target=H_target, actor=actor
        )
    if calc_type == "PS_FLASH":
        if T_K is None or S_target is None:
            from app.services.exceptions import PcsError

            raise PcsError(
                "PS_FLASH 必须给 T_K + S_target",
                code="FLASH_INPUT_ERROR",
                status=422,
            )
        return await persist_ps_flash(
            db, stream_id=stream_id, T_K=T_K, S_target=S_target, actor=actor
        )
    if calc_type == "SATURATION":
        if not fluid:
            from app.services.exceptions import PcsError

            raise PcsError(
                "SATURATION 必须给 fluid",
                code="FLASH_INPUT_ERROR",
                status=422,
            )
        return await persist_saturation(
            db, stream_id=stream_id, fluid=fluid, P=P_Pa, T=T_K, actor=actor
        )
    from app.services.exceptions import PcsError

    raise PcsError(
        f"未支持的 calc_type={calc_type!r}；"
        f"支持：PT_FLASH/PH_FLASH/PS_FLASH/SATURATION",
        code="FLASH_INPUT_ERROR",
        status=422,
    )


__all__ = [
    "persist_calculate",
    "persist_pt_flash",
    "persist_ph_flash",
    "persist_ps_flash",
    "persist_saturation",
    "persist_bubble",
    "persist_dew",
]
