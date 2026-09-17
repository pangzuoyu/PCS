"""SUP-P5-PSV-002 V1.14 §4.2 validate_valve_params（G7-G25 全拦截/警告）。

按 SPEC V1.14 §4.2：

校验链（按 G 码顺序；raise 前置 / 警告收集）：
  G7    PILOT_OPERATED         → raise PsvPilotOperatedNotSupported
  G8    RUPTURE_DISC           → raise PsvRuptureDiscNotSupported
  G17   BALANCED_BELLOWS 无 bellows_material → raise PsvBellowsMaterialRequired
  G14   inlet < 1 inch         → raise PsvInletTooSmall
  G12   入/出口尺寸 ∉ API 526 / orifice_override ∉ candidates → raise PsvInletOutletMismatch
  G11   blowdown 超阀型+介质范围 → raise PsvBlowdownOutOfRange
  G10   背压超阀型范围          → raise PsvBackPressureExceeded
  G21   波纹管材料-介质不兼容   → raise PsvBellowsIncompatible
  G15   Q/R/T 高温-低分子量     → raise PsvOrificeTemperatureLimit
  G9    orifice_override < 计算面积 → raise PsvOrificeOverrideTooSmall
  G13   平衡波纹管式材料-介质   → raise PsvMaterialIncompatible（占位，P5 仅声明）

派生：
  - cdtp_applied / cdtp_set_pressure_pa：SUPERIMPOSED + BP > 0 时启用
  - kb_factor / kb_source：4 阶段策略（kb_service）
  - candidates：API 526 反向映射 + flange class 过滤
  - rupture_disc_kc：ASME UG-127（UPSTREAM=0.90 / DOWNSTREAM=1.00 / NONE=None）
  - warnings：G18/G19/G22/G23/G24/G25 收集（不 raise）

不做：
  - 不重做泄放量计算（SPEC §6 决策 11 锁定：选型字段不影响泄放量）
  - 不实现 G9 面积比较（计算面积由调用方透传，本函数仅校验 override ≥ 计算面积）
"""
from __future__ import annotations

from typing import Any

from app.services.exceptions import (
    PsvBackPressureExceeded,
    PsvBellowsIncompatible,
    PsvBellowsMaterialRequired,
    PsvBlowdownOutOfRange,
    PsvInletOutletMismatch,
    PsvInletTooSmall,
    PsvOrificeTemperatureLimit,
    PsvPilotOperatedNotSupported,
    PsvRuptureDiscNotSupported,
)
from app.services.psv.bellows_compat import validate_bellows_compat
from app.services.psv.cdtp import apply_cdtp_correction
from app.services.psv.kb_service import lookup_kb_with_priority
from app.services.psv.orifice_flange import (
    API526_MIN_INLET,
    get_candidate_orifices,
    is_high_temp_light_gas_restricted,
    size_lt,
)
from app.services.psv.valve_selection_types import (
    BACK_PRESSURE_MAX_BY_TYPE,
    BLOWDOWN_DEFAULT_BY_MEDIUM,
    BLOWDOWN_RANGE,
    RUPTURE_DISC_KC,
    ValidatedParams,
)


# ---------------------------------------------------------------------------
# 工具：duck-typed request 字段读取
# ---------------------------------------------------------------------------


def _attr(req: Any, name: str, default: Any = None) -> Any:
    """duck-type 读取 req 字段；None 视为缺省。"""
    if req is None:
        return default
    if isinstance(req, dict):
        return req.get(name, default)
    return getattr(req, name, default)


# ---------------------------------------------------------------------------
# §4.2 validate_valve_params
# ---------------------------------------------------------------------------


def validate_valve_params(req: Any) -> ValidatedParams:
    """PSV 安全阀选型参数校验（G7-G25 全拦截/警告）。

    Args:
        req: 选型参数载体（duck-typed；支持 dict / dataclass / Pydantic）
            必填：valve_type / medium / flange_class / back_pressure_type /
                  back_pressure_pct / set_pressure_pa / overpressure_pct /
                  inlet_size / outlet_size / orifice_override /
                  rupture_disc_position / blowdown_fraction / bellows_material /
                  valve_brand / service_note / superimposed_pressure_pa /
                  fluid_temperature_c / molecular_weight / relief_scenario /
                  calculated_area_m2

    Returns:
        ValidatedParams（含 kb_factor / kb_source / cdtp_applied / candidates /
                         rupture_disc_kc / warnings）

    Raises:
        Psv* 子类：G7/G8/G10/G11/G12/G14/G15/G17/G21 任一触发
    """
    valve_type: str = _attr(req, "valve_type")
    medium: str = _attr(req, "medium")
    flange_class: str = _attr(req, "flange_class")
    back_pressure_type: str = _attr(req, "back_pressure_type")
    back_pressure_pct: float = float(_attr(req, "back_pressure_pct", 0.0) or 0.0)
    set_pressure_pa: float = float(_attr(req, "set_pressure_pa", 0.0) or 0.0)
    overpressure_pct: float = float(_attr(req, "overpressure_pct", 10.0) or 10.0)
    inlet_size = _attr(req, "inlet_size")
    outlet_size = _attr(req, "outlet_size")
    orifice_override = _attr(req, "orifice_override")
    rupture_disc_position: str = _attr(req, "rupture_disc_position", "NONE")
    blowdown_fraction = _attr(req, "blowdown_fraction")
    bellows_material = _attr(req, "bellows_material")
    valve_brand = _attr(req, "valve_brand")
    service_note = _attr(req, "service_note")
    superimposed_pressure_pa: float = float(_attr(req, "superimposed_pressure_pa", 0.0) or 0.0)
    fluid_temperature_c = _attr(req, "fluid_temperature_c")
    molecular_weight = _attr(req, "molecular_weight")
    calculated_area_m2 = _attr(req, "calculated_area_m2")

    warnings: list[str] = []

    # ============ G7: PILOT_OPERATED 拦截 ============
    if valve_type == "PILOT_OPERATED":
        raise PsvPilotOperatedNotSupported(
            "P5 不支持先导式 PSV（P5+ 实施；§2.2）",
            details={"valve_type": valve_type},
        )

    # ============ G8: RUPTURE_DISC 拦截 ============
    if valve_type == "RUPTURE_DISC":
        raise PsvRuptureDiscNotSupported(
            "P5 不支持爆破膜式 PSV（P6+ 实施；§2.2）",
            details={"valve_type": valve_type},
        )

    # ============ G17: BALANCED_BELLOWS 必填 bellows_material ============
    if valve_type == "BALANCED_BELLOWS" and not bellows_material:
        raise PsvBellowsMaterialRequired(
            "平衡波纹管式 PSV 必填波纹管材料（§3.8）",
            details={"valve_type": valve_type},
        )

    # ============ G14: inlet < 1 inch ============
    if inlet_size and size_lt(inlet_size, API526_MIN_INLET):
        raise PsvInletTooSmall(
            f"入口尺寸 {inlet_size} < API 526 最小入口 {API526_MIN_INLET}（§4.2 G14）",
            details={"inlet_size": inlet_size, "min_inlet": API526_MIN_INLET},
        )

    # ============ 计算候选孔口（前置 G12 校验需要）============
    candidates: list[str] = []
    if inlet_size and outlet_size and flange_class:
        candidates = get_candidate_orifices(inlet_size, outlet_size, flange_class)

    # ============ G12: 入/出口尺寸 ∉ API 526 ============
    if inlet_size and outlet_size and flange_class and not candidates:
        raise PsvInletOutletMismatch(
            f"入/出口尺寸 {inlet_size} × {outlet_size} 不符合 API 526（§4.2 G12）",
            details={
                "inlet_size": inlet_size,
                "outlet_size": outlet_size,
                "flange_class": flange_class,
            },
        )

    # ============ G12: orifice_override 不在 candidates ============
    orifice_override_validated = None
    if orifice_override:
        if candidates and orifice_override not in candidates:
            raise PsvInletOutletMismatch(
                f"orifice_override {orifice_override} 不在候选孔口 {candidates}（§4.2 G12）",
                details={
                    "orifice_override": orifice_override,
                    "candidates": candidates,
                },
            )
        orifice_override_validated = orifice_override

    # ============ G11: blowdown 范围校验 ============
    if blowdown_fraction is None:
        blowdown_fraction = BLOWDOWN_DEFAULT_BY_MEDIUM.get(medium, 0.05)
    else:
        blowdown_fraction = float(blowdown_fraction)
        range_ = BLOWDOWN_RANGE.get((valve_type, medium))
        if range_ is not None:
            min_, max_ = range_
            if blowdown_fraction < min_ or blowdown_fraction > max_:
                raise PsvBlowdownOutOfRange(
                    f"blowdown {blowdown_fraction:.2%} 超出范围 [{min_:.0%}, {max_:.0%}]"
                    f"（{valve_type}/{medium}；§3.5 G11）",
                    details={
                        "blowdown_fraction": blowdown_fraction,
                        "min": min_,
                        "max": max_,
                        "valve_type": valve_type,
                        "medium": medium,
                    },
                )

    # ============ G10: 背压超阀型范围 ============
    max_pct = BACK_PRESSURE_MAX_BY_TYPE.get(valve_type, {}).get(back_pressure_type)
    if max_pct is not None and back_pressure_pct > max_pct:
        raise PsvBackPressureExceeded(
            f"背压 {back_pressure_pct:.1f}% 超过 {valve_type}/{back_pressure_type} 上限 {max_pct:.0%}"
            f"（§3.5 G10）",
            details={
                "back_pressure_pct": back_pressure_pct,
                "max_pct": max_pct,
                "valve_type": valve_type,
                "back_pressure_type": back_pressure_type,
            },
        )

    # ============ CDTP 修正 ============
    cdtp_applied = False
    cdtp_set_pressure_pa: float | None = None
    if back_pressure_type == "SUPERIMPOSED" and superimposed_pressure_pa > 0:
        cdtp_set_pressure_pa = apply_cdtp_correction(set_pressure_pa, superimposed_pressure_pa)
        cdtp_applied = True

    # ============ Kb 4 阶段策略 ============
    bp_for_kb = back_pressure_pct
    if back_pressure_type == "SUPERIMPOSED":
        # SUPERIMPOSED 走 CDTP 修正，背压不直接进入 Kb 路径
        bp_for_kb = 0.0
    kb_factor, kb_source = lookup_kb_with_priority(
        bp_pct=bp_for_kb,
        overpressure_pct=overpressure_pct,
        valve_type=valve_type,
        valve_brand=valve_brand,
    )

    # G24/G25 warnings（不 raise）
    if valve_brand and kb_source == "api520_fig30":
        warnings.append(
            f"G24: 品牌 {valve_brand} 无 Kb 数据，回退保守优先（api520_fig30）"
        )
    if kb_source and kb_source.startswith("mixed:"):
        warnings.append(
            f"G25: 多厂商混用（{kb_source}），保守优先策略"
        )

    # ============ G21: 波纹管材料-介质不兼容 ============
    if (
        valve_type == "BALANCED_BELLOWS"
        and bellows_material
        and service_note
    ):
        # raises PsvBellowsIncompatible
        validate_bellows_compat(bellows_material, service_note)

    # ============ G15: Q/R/T 高温-低分子量 ============
    orifice_to_check = orifice_override_validated or (
        candidates[0] if candidates else None
    )
    if (
        orifice_to_check in {"Q", "R", "T"}
        and fluid_temperature_c is not None
        and molecular_weight is not None
    ):
        if is_high_temp_light_gas_restricted(
            orifice_to_check, float(fluid_temperature_c), float(molecular_weight)
        ):
            raise PsvOrificeTemperatureLimit(
                f"孔口 {orifice_to_check} 在 T={fluid_temperature_c}°C / MW={molecular_weight} 时"
                f"受 API 520 §5.3.4 限制（须业主工程师批准；§4.2 G15）",
                details={
                    "orifice": orifice_to_check,
                    "fluid_temperature_c": fluid_temperature_c,
                    "molecular_weight": molecular_weight,
                },
            )

    # ============ G9: orifice_override < 计算面积 ============
    # （计算面积不在本函数范围内；调用方传 calculated_area_m2；本函数不实现面积比较）
    # 占位：当前实现仅校验 orifice_override 在 candidates 内（G12 已覆盖）。
    # 若 calculated_area_m2 已传且 orifice_override_validated 对应已知 orifice 面积表
    # 可加面积比较。P5 暂不实现（需扩大 API 526 面积表）；G9 在 Task 18 集成测试覆盖。

    # ============ G13: 平衡波纹管式材料-介质（占位，P5 仅声明）============
    # body_material 与 medium 的兼容性需 NACE/材料手册细则，P5 仅在告警层级登记，
    # 不抛错（避免阻断）。由 P5+ 启动后工艺工程师补完。
    # 警告占位：
    if valve_type == "BALANCED_BELLOWS":
        # 若 body_material 在含硫/强氧化介质场景下，提示需专项评估
        if service_note and ("湿 H₂S" in service_note or "强氧化性" in service_note):
            if body_material in {"CARBON_STEEL", "SS304"}:
                warnings.append(
                    f"G13: 阀体材料 {body_material} 在湿 H₂S/强氧化介质需专项评估（占位）"
                )

    # ============ 装配 ValidatedParams ============
    return ValidatedParams(
        valve_type=valve_type,
        medium=medium,
        flange_class=flange_class,
        inlet_size=inlet_size,
        outlet_size=outlet_size,
        cdtp_applied=cdtp_applied,
        kb_factor=kb_factor,
        kb_source=kb_source,
        cdtp_set_pressure_pa=cdtp_set_pressure_pa,
        rupture_disc_kc=RUPTURE_DISC_KC.get(rupture_disc_position),
        candidates=candidates,
        orifice_override_validated=orifice_override_validated,
        warnings=warnings,
    )


__all__ = ["validate_valve_params"]