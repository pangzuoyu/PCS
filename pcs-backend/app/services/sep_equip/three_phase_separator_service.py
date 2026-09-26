"""三相分离器（油水气）尺寸计算（SPEC §3.4.3 V1.5）。

5 段计算：
  1. 三相体积流量（油/水/气各自 m³/d）
  2. 堰板高度 H_w（控制油水界面）
  3. 油水界面位置（SPEC §3.4.3 Eq.1）
  4. 停留时间 t_r（液相 ≥ 5 min，气相 ≥ 10 s）
  5. 体积校核

调用 C-12 公共服务（D7 接口冻结）：
  - calc_partial_volume（D7 接口冻结）算 H_total 体积
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.services.exceptions import PcsError
from app.services.vessel.vessel_service import (
    HeadType,
    PartialVolumeInput,
    VesselShape,
    calc_partial_volume,
)

_RESIDENCE_TIME_LIQUID_MIN: Final[float] = 5.0
_RESIDENCE_TIME_GAS_S: Final[float] = 10.0

# Imperial 单位换算
_M3_TO_FT3: Final[float] = 35.3147


class ThreePhaseSeparatorError(PcsError):
    """三相分离器输入校验失败（422）。"""

    code = "THREE_PHASE_SEPARATOR_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class ThreePhaseSeparatorInput:
    """三相分离器输入（frozen dataclass）。

    物理量 SI 单位：
      - 长度 m，质量流量 kg/d，密度 kg/m³。
    """

    vessel_shape: VesselShape
    diameter_m: float
    length_m: float
    head_type: HeadType
    oil_mass_rate_kg_d: float
    water_mass_rate_kg_d: float
    gas_mass_rate_kg_d: float
    oil_density_kg_m3: float
    water_density_kg_m3: float
    gas_density_kg_m3: float
    weir_height_m: float
    oil_water_interface_target_m: float
    imperial_units: bool = False


@dataclass(frozen=True)
class ThreePhaseSeparatorResult:
    """三相分离器结果（frozen dataclass）。"""

    oil_vol_rate_m3_d: float
    water_vol_rate_m3_d: float
    gas_vol_rate_m3_d: float
    oil_water_interface_m: float
    weir_height_required_m: float
    liquid_residence_time_min: float
    gas_residence_time_s: float
    is_residence_time_ok: bool
    total_volume_m3: float
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _validate_input(inp: ThreePhaseSeparatorInput) -> None:
    """F2 + F5：几何/流量/密度 + weir_height 边界校验。"""
    if inp.diameter_m <= 0:
        raise ThreePhaseSeparatorError(
            f"diameter_m={inp.diameter_m} 必须 > 0"
        )
    if inp.length_m < 0:
        raise ThreePhaseSeparatorError(
            f"length_m={inp.length_m} 必须 ≥ 0"
        )
    for fld in (
        "oil_mass_rate_kg_d",
        "water_mass_rate_kg_d",
        "gas_mass_rate_kg_d",
    ):
        if getattr(inp, fld) < 0:
            raise ThreePhaseSeparatorError(f"{fld} 不能为负")
    if (
        inp.oil_density_kg_m3 <= 0
        or inp.water_density_kg_m3 <= 0
        or inp.gas_density_kg_m3 <= 0
    ):
        raise ThreePhaseSeparatorError("油/水/气密度必须 > 0")
    # F2 boundary：weir_height 严格 0 < H_w < D
    if not (0.0 < inp.weir_height_m < inp.diameter_m):
        raise ThreePhaseSeparatorError(
            f"weir_height={inp.weir_height_m} 越界 (0, D={inp.diameter_m})"
        )
    if inp.oil_water_interface_target_m < 0:
        raise ThreePhaseSeparatorError(
            "oil_water_interface_target_m 不能为负"
        )


def calc_three_phase_separator(
    inp: ThreePhaseSeparatorInput,
) -> ThreePhaseSeparatorResult:
    """三相分离器（油水气）尺寸计算（SPEC §3.4.3 V1.5）。

    计算项：
      - 三相体积流量（油/水/气 m³/d）
      - 油水界面位置 H_ow = H·(ρ_w - ρ_oil)/(ρ_w - ρ_g)（SPEC §3.4.3 Eq.1 反推 H_total）
      - 堰板高度（按 weir_height_m 校核）
      - 停留时间：液 5 min / 气 10 s（GPSA §4.4）
      - 体积校核：调用 C-12 calc_partial_volume（D7 冻结）

    Args:
        inp: ThreePhaseSeparatorInput（frozen）

    Returns:
        ThreePhaseSeparatorResult（frozen）

    Raises:
        ThreePhaseSeparatorError: 输入校验失败（F2 weir_height 越界、F5 极值）
    """
    _validate_input(inp)

    # 1. 三相体积流量（油/水/气 m³/d）
    q_oil = inp.oil_mass_rate_kg_d / inp.oil_density_kg_m3
    q_water = inp.water_mass_rate_kg_d / inp.water_density_kg_m3
    q_gas = inp.gas_mass_rate_kg_d / inp.gas_density_kg_m3
    q_liquid = q_oil + q_water

    # 2. 油水界面（SPEC §3.4.3 Eq.1 反推 H_total）
    # H_total = H_ow · (ρ_w - ρ_g) / (ρ_w - ρ_oil)
    h_total = inp.oil_water_interface_target_m * (
        inp.water_density_kg_m3 - inp.gas_density_kg_m3
    ) / (inp.water_density_kg_m3 - inp.oil_density_kg_m3)

    # 3. 容器几何最大可用高度 h_max
    # Z-2 v5：移除 Final[...]（mypy warning），普通 dict 即可
    head_depth_map = {
        "HEMISPHERICAL": lambda D: D / 2.0,
        "2:1_ELLIPTICAL": lambda D: D / 4.0,
        "TORISPHERICAL": lambda D: 0.169 * D,
        "FLAT": lambda D: 0.0,
    }
    head_depth = head_depth_map[inp.head_type](inp.diameter_m)
    if inp.vessel_shape == "HORIZONTAL":
        h_max = inp.diameter_m
    else:
        h_max = inp.diameter_m + 2.0 * head_depth
    if h_total > h_max:
        raise ThreePhaseSeparatorError(
            f"H_total={h_total:.3f}m > h_max={h_max:.3f}m（油水界面目标越界）"
        )

    h_ow = inp.oil_water_interface_target_m
    h_w_required = inp.weir_height_m

    # 4. 调用 C-12 calc_partial_volume（D7 冻结）算液体体积
    pv_inp = PartialVolumeInput(
        D_m=inp.diameter_m,
        L_m=inp.length_m,
        head_type=inp.head_type,
        H_m=h_total,
        n_vessels=1,
        vessel_shape=inp.vessel_shape,
    )
    pv_result = calc_partial_volume(pv_inp)
    v_total = pv_result.total_volume_m3
    v_liquid_part = pv_result.partial_volume_m3

    # 5. 停留时间（液/气）
    t_r_liquid_min = (
        v_liquid_part / q_liquid * 1440.0 if q_liquid > 0 else float("inf")
    )
    t_r_gas_s = (
        v_total / q_gas * 86400.0 if q_gas > 0 else float("inf")
    )
    is_ok = (
        t_r_liquid_min >= _RESIDENCE_TIME_LIQUID_MIN
        and t_r_gas_s >= _RESIDENCE_TIME_GAS_S
    )

    # Imperial 双单位（仅当请求）
    imperial = None
    if inp.imperial_units:
        imperial = {
            "oil_vol_rate_ft3_d": q_oil * _M3_TO_FT3,
            "water_vol_rate_ft3_d": q_water * _M3_TO_FT3,
            "gas_vol_rate_ft3_d": q_gas * _M3_TO_FT3,
        }

    return ThreePhaseSeparatorResult(
        oil_vol_rate_m3_d=q_oil,
        water_vol_rate_m3_d=q_water,
        gas_vol_rate_m3_d=q_gas,
        oil_water_interface_m=h_ow,
        weir_height_required_m=h_w_required,
        liquid_residence_time_min=t_r_liquid_min,
        gas_residence_time_s=t_r_gas_s,
        is_residence_time_ok=is_ok,
        total_volume_m3=v_total,
        imperial_conversion=imperial,
        formula_ref={
            "oil_water_interface": (
                "H_ow = H·(ρ_w - ρ_oil)/(ρ_w - ρ_g) [SPEC §3.4.3 Eq.1]"
            ),
            "residence_time": "GPSA §4.4 液 5 min / 气 10 s",
            "vessel_partial_volume": "调用 C-12 calc_partial_volume (D7 冻结)",
            "volumetric_flow": "Q = m_dot / ρ",
        },
    )


__all__ = [
    "ThreePhaseSeparatorInput",
    "ThreePhaseSeparatorResult",
    "ThreePhaseSeparatorError",
    "calc_three_phase_separator",
]