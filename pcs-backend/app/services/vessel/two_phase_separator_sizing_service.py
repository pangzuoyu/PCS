"""P6-4 C-08 两相分离器尺寸计算（SPEC §3.4.2 V1.2 重写）。

按 WS-CA-PR-010 Rev A 5 段计算：
  1. 油/水/气体积流量（bbl/d, MMscfd）
  2. 混合相密度（体积加权平均）
  3. Souders-Brown Vmax = K × √((ρL − ρV) / ρV)
  4. 气相 CSA 校核（最小 CSA 85% 利用率 vs 实际 π·D²/4）
  5. 喷嘴动量校核 + 仪表控制高度 + 停留时间

V1.2 关键修正（与 V1.0/V1.1 区别）：
  - 服务名：two_phase_separator_sizing_service（非 vessel_weight_estimate_service）
  - 计算内容：5 段 sizing（**不是**重量估算）
  - V1.2 新增字段：oil_sg / water_sg / gas_sg（WS-CA-PR-010 Rev A §3 原始 SG 输入；
    与 density 等效但与 xls 对账更直观）
  - 消费 T3 (C-12) calc_partial_volume 接口（dataclass 输入非 positional）
  - V1.0 污染禁止：不复用 heat/weight_estimate_service.py；不抽 WeightSegment；
    不加 vessel_results.weight_kg 列（见 D7 ADR-0040 / SPEC §3.4.2 V1.2）

调用链（与 T3 衔接）：
  two_phase_separator_sizing_service
    → calc_partial_volume（V1.2 接口冻结的 C-12 公共服务，T3 交付）
    → T3 result.total_volume_m3 × n_vessels 算多容器 total
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError
from app.services.vessel.vessel_service import (
    HeadType,
    PartialVolumeInput,
    calc_partial_volume,
)

# 物理常量（ISO 80000-3 + WS-CA-PR-010 Rev A §3 单位约定）
_WATER_DENSITY_KG_M3: Final[float] = 999.0  # 水密度基准（SG 反推用）
_AIR_DENSITY_KG_M3: Final[float] = 1.225    # 空气密度基准（15°C, 1 atm，SG 反推用）
_BARREL_TO_M3: Final[float] = 0.1589873     # 1 bbl (oil) = 0.1589873 m³
_MMSCF_TO_M3: Final[float] = 28316.85       # 1 MMscf = 28316.85 m³（60°F, 14.7 psia）
# CSA 安全系数（0.85 = 保留 15% 余量，WS-CA-PR-010 Rev A §4.3 工程惯例）
_CSA_UTILIZATION_FACTOR: Final[float] = 0.85
# kg/d → kg/s 换算
_SECONDS_PER_DAY: Final[float] = 86400.0

# 容器方位字面量（与 calc_vessel_sizing 区分：sizing 输入用大写）
VesselShape = Literal["VERTICAL", "HORIZONTAL", "SPHERICAL"]


class TwoPhaseSeparatorSizingError(PcsError):
    """两相分离器 sizing 输入物理量不合法（422）。

    含 SG/density 反推一致性校验失败（V1.2 oil_sg = oil_density/999.0 等）。
    """

    code = "TWO_PHASE_SEPARATOR_SIZING_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class TwoPhaseSeparatorSizingInput:
    """两相分离器尺寸计算输入（frozen dataclass）。

    物理量 SI 单位（按 SPEC §3.4.2 V1.3 单位约定）：
      - 长度 m；面积 m²；体积 m³；速度 m/s；时间 s
      - 压力 kPa（gauge）/ MPa
      - 温度 °C
      - 密度 kg/m³；流量 kg/d；分子量 kg/kmol
      - 动量限值 kg·m/s²（即 N·s）

    V1.2 新增 SG 字段（WS-CA-PR-010 Rev A §3 原始 SG 输入；与密度等效，
    但与 xls 对账更直观）：
      - oil_sg = oil_density_kg_m3 / 999.0
      - water_sg = water_density_kg_m3 / 999.0（通常 1.0~1.05）
      - gas_sg = gas_density_kg_m3 / 1.225（与 gas_mw_kg_kmol / 28.97 一致）
    """

    vessel_shape: VesselShape
    diameter_m: float
    length_m: float  # 立式=高度；卧式=切线长；球罐=0
    head_type: HeadType  # 复用 T3 calc_partial_volume 字面量
    operating_pressure_kpa: float
    operating_temperature_c: float
    oil_mass_rate_kg_d: float
    water_mass_rate_kg_d: float
    gas_mass_rate_kg_d: float
    oil_density_kg_m3: float
    water_density_kg_m3: float
    gas_density_kg_m3: float
    oil_sg: float
    water_sg: float
    gas_sg: float
    gas_mw_kg_kmol: float
    k_factor: float  # Souders-Brown K（按 WS-CA-PR-010 Rev A §4 表查表）
    nozzle_inlet_momentum_limit_kg_m_s2: float  # 入口喷嘴动量限值
    nozzle_outlet_momentum_limit_kg_m_s2: float  # 出口喷嘴动量限值
    instrument_response_time_s: float  # 仪表响应时间 t_c
    design_pressure_mpa: float = 1.0
    n_vessels: int = 1
    imperial_units: bool = False


@dataclass(frozen=True)
class TwoPhaseSeparatorSizingResult:
    """两相分离器尺寸计算输出（frozen dataclass）。

    字段按 WS-CA-PR-010 Rev A §3~§5 + SPEC §3.4.2：
      - oil_vol_rate_bbl_d: 油体积流量（bbl/d）
      - water_vol_rate_bbl_d: 水体积流量（bbl/d）
      - gas_vol_rate_mmscfd: 气体积流量（MMscfd）
      - mixed_density_kg_m3: 混合相密度（体积加权平均）
      - vmax_m_s: Vmax = K × √((ρL - ρV) / ρV)
      - csa_min_m2: 最小所需气相 CSA（85% 利用率）
      - csa_actual_m2: 实际气相 CSA = π·D²/4
      - nozzle_inlet_min_id_m: 入口喷嘴最小内径
      - nozzle_outlet_min_id_m: 出口喷嘴最小内径
      - control_height_m: 仪表控制高度 H_c = t_c × Q_total_volumetric / (3600 × CSA)
      - control_volume_m3: 控制体积（T3 calc_partial_volume 调用；total × n_vessels）
      - residence_time_s: 实际停留时间 V_total / Q_total_volumetric_m3_s
      - imperial_conversion: 双单位转换（仅 imperial_units=True 时填充）
      - formula_ref: 公式溯源（dict，含 T3 几何 + WS-CA-PR-010 sizing 两部分）
    """

    oil_vol_rate_bbl_d: float
    water_vol_rate_bbl_d: float
    gas_vol_rate_mmscfd: float
    mixed_density_kg_m3: float
    vmax_m_s: float
    csa_min_m2: float
    csa_actual_m2: float
    nozzle_inlet_min_id_m: float
    nozzle_outlet_min_id_m: float
    control_height_m: float
    control_volume_m3: float
    residence_time_s: float
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------


def _validate_input(inp: TwoPhaseSeparatorSizingInput) -> None:
    """输入物理量边界校验 + SG/density 反推一致性校验（V1.2）。

    Raises:
        TwoPhaseSeparatorSizingError: 任何物理量越界或 SG/density 不一致
            （相对误差 > 1% 时拒绝）。
    """
    if inp.diameter_m <= 0:
        raise TwoPhaseSeparatorSizingError(
            f"diameter_m={inp.diameter_m} 必须 > 0"
        )
    if inp.length_m < 0:
        raise TwoPhaseSeparatorSizingError(
            f"length_m={inp.length_m} 必须 ≥ 0（球罐 length=0）"
        )
    if inp.operating_pressure_kpa < 0:
        raise TwoPhaseSeparatorSizingError(
            f"operating_pressure_kpa={inp.operating_pressure_kpa} 不能为负"
        )
    if inp.operating_temperature_c <= -273.15:
        raise TwoPhaseSeparatorSizingError(
            f"operating_temperature_c={inp.operating_temperature_c} 低于绝对零度"
        )
    for fld in ("oil_mass_rate_kg_d", "water_mass_rate_kg_d", "gas_mass_rate_kg_d"):
        v = getattr(inp, fld)
        if v < 0:
            raise TwoPhaseSeparatorSizingError(f"{fld}={v} 不能为负")
    if inp.oil_density_kg_m3 <= 0 or inp.water_density_kg_m3 <= 0 or inp.gas_density_kg_m3 <= 0:
        raise TwoPhaseSeparatorSizingError(
            "密度必须 > 0（oil/water/gas）"
        )
    if inp.oil_density_kg_m3 < inp.gas_density_kg_m3:
        raise TwoPhaseSeparatorSizingError(
            f"ρ_oil={inp.oil_density_kg_m3} < ρ_gas={inp.gas_density_kg_m3} "
            "物理不合理（液相密度应 > 气相）"
        )
    if inp.gas_mw_kg_kmol <= 0:
        raise TwoPhaseSeparatorSizingError(
            f"gas_mw_kg_kmol={inp.gas_mw_kg_kmol} 必须 > 0"
        )
    if not (0.01 <= inp.k_factor <= 1.0):
        raise TwoPhaseSeparatorSizingError(
            f"k_factor={inp.k_factor} 越界（SI 物理范围 0.01~1.0 m/s）"
        )
    if inp.nozzle_inlet_momentum_limit_kg_m_s2 <= 0:
        raise TwoPhaseSeparatorSizingError(
            "入口喷嘴动量限值必须 > 0"
        )
    if inp.nozzle_outlet_momentum_limit_kg_m_s2 <= 0:
        raise TwoPhaseSeparatorSizingError(
            "出口喷嘴动量限值必须 > 0"
        )
    if inp.instrument_response_time_s <= 0:
        raise TwoPhaseSeparatorSizingError(
            "仪表响应时间 t_c 必须 > 0"
        )
    if inp.n_vessels < 1:
        raise TwoPhaseSeparatorSizingError(
            f"n_vessels={inp.n_vessels} 必须 ≥ 1"
        )
    # SG/density 反推一致性校验（V1.2；相对误差 > 1% 拒绝）
    if abs(inp.oil_sg - inp.oil_density_kg_m3 / _WATER_DENSITY_KG_M3) / max(
        inp.oil_sg, 1e-9
    ) > 0.01:
        raise TwoPhaseSeparatorSizingError(
            f"oil_sg={inp.oil_sg} 与 oil_density_kg_m3={inp.oil_density_kg_m3} "
            f"反推（={inp.oil_density_kg_m3 / _WATER_DENSITY_KG_M3:.4f}）不一致"
        )
    if abs(inp.water_sg - inp.water_density_kg_m3 / _WATER_DENSITY_KG_M3) / max(
        inp.water_sg, 1e-9
    ) > 0.01:
        raise TwoPhaseSeparatorSizingError(
            f"water_sg={inp.water_sg} 与 water_density_kg_m3={inp.water_density_kg_m3} "
            f"反推（={inp.water_density_kg_m3 / _WATER_DENSITY_KG_M3:.4f}）不一致"
        )
    if abs(inp.gas_sg - inp.gas_density_kg_m3 / _AIR_DENSITY_KG_M3) / max(
        inp.gas_sg, 1e-9
    ) > 0.01:
        raise TwoPhaseSeparatorSizingError(
            f"gas_sg={inp.gas_sg} 与 gas_density_kg_m3={inp.gas_density_kg_m3} "
            f"反推（={inp.gas_density_kg_m3 / _AIR_DENSITY_KG_M3:.4f}）不一致"
        )


# ---------------------------------------------------------------------------
# 5 段计算
# ---------------------------------------------------------------------------


def _stage1_volumetric_flows(
    inp: TwoPhaseSeparatorSizingInput,
) -> tuple[float, float, float, float, float, float]:
    """阶段 1：油/水/气 体积流量（m³/d + bbl/d + MMscfd）。

    Returns:
        (oil_vol_rate_bbl_d, water_vol_rate_bbl_d, gas_vol_rate_mmscfd,
         oil_vol_rate_m3_d, water_vol_rate_m3_d, gas_vol_rate_m3_d)
    """
    oil_vol_m3_d = inp.oil_mass_rate_kg_d / inp.oil_density_kg_m3
    water_vol_m3_d = inp.water_mass_rate_kg_d / inp.water_density_kg_m3
    gas_vol_m3_d = inp.gas_mass_rate_kg_d / inp.gas_density_kg_m3
    oil_vol_bbl_d = oil_vol_m3_d / _BARREL_TO_M3
    water_vol_bbl_d = water_vol_m3_d / _BARREL_TO_M3
    gas_vol_mmscfd = gas_vol_m3_d / _MMSCF_TO_M3
    return (
        oil_vol_bbl_d,
        water_vol_bbl_d,
        gas_vol_mmscfd,
        oil_vol_m3_d,
        water_vol_m3_d,
        gas_vol_m3_d,
    )


def _stage2_mixed_density(
    oil_vol_m3_d: float, water_vol_m3_d: float, gas_vol_m3_d: float,
    oil_density: float, water_density: float, gas_density: float,
) -> float:
    """阶段 2：混合相密度（体积加权平均；kg/m³）。"""
    total_vol = oil_vol_m3_d + water_vol_m3_d + gas_vol_m3_d
    if total_vol <= 0:
        # 零流量边界（用于停留时间边界测试）返回 ρ_V（vapor 主导假设）
        return gas_density
    return (
        oil_vol_m3_d * oil_density
        + water_vol_m3_d * water_density
        + gas_vol_m3_d * gas_density
    ) / total_vol


def _stage3_vmax_souders_brown(
    rho_L_kg_m3: float,
    rho_V_kg_m3: float,
    k_factor: float,
) -> float:
    """阶段 3：Souders-Brown Vmax = K × √((ρL − ρV) / ρV)。

    Args:
        rho_L_kg_m3: 液相密度（油水混合）
        rho_V_kg_m3: 气相密度
        k_factor: Souders-Brown K（m/s）
    """
    if rho_L_kg_m3 <= rho_V_kg_m3:
        raise TwoPhaseSeparatorSizingError(
            f"ρ_L={rho_L_kg_m3} 必须 > ρ_V={rho_V_kg_m3}"
        )
    return k_factor * math.sqrt((rho_L_kg_m3 - rho_V_kg_m3) / rho_V_kg_m3)


def _stage4_csa_check(
    gas_vol_m3_d: float, vmax_m_s: float, diameter_m: float,
) -> tuple[float, float]:
    """阶段 4：气相 CSA 校核（最小 vs 实际）。"""
    q_gas_m3_s = gas_vol_m3_d / _SECONDS_PER_DAY
    csa_min = q_gas_m3_s / (vmax_m_s * _CSA_UTILIZATION_FACTOR)
    csa_actual = math.pi * diameter_m**2 / 4.0
    return csa_min, csa_actual


def _stage5_nozzle_control_residence(
    inp: TwoPhaseSeparatorSizingInput,
    oil_vol_m3_d: float, water_vol_m3_d: float, gas_vol_m3_d: float,
    rho_mix_kg_m3: float, csa_actual_m2: float,
) -> tuple[float, float, float, float, float, float]:
    """阶段 5：喷嘴动量 + 仪表控制高度 + 停留时间。

    Returns:
        (nozzle_inlet_min_id_m, nozzle_outlet_min_id_m, control_height_m,
         control_volume_m3, residence_time_s, total_vol_m3_per_vessel)
    """
    # 5a. 喷嘴动量校核（入口/出口对称计算）
    m_total_kg_s = (
        inp.oil_mass_rate_kg_d + inp.water_mass_rate_kg_d + inp.gas_mass_rate_kg_d
    ) / _SECONDS_PER_DAY
    if m_total_kg_s <= 0:
        raise TwoPhaseSeparatorSizingError(
            "总质量流量为 0（无法计算喷嘴尺寸）"
        )
    # ID_min = √(4m² / (π × N × ρ_mix))
    nozzle_inlet_id = math.sqrt(
        4.0 * m_total_kg_s**2 / (math.pi * inp.nozzle_inlet_momentum_limit_kg_m_s2 * rho_mix_kg_m3)
    )
    nozzle_outlet_id = math.sqrt(
        4.0 * m_total_kg_s**2 / (math.pi * inp.nozzle_outlet_momentum_limit_kg_m_s2 * rho_mix_kg_m3)
    )

    # 5b. 仪表控制高度 H_c = t_c × Q_total_volumetric_m3_h / (3600 × CSA)
    q_total_m3_s = (oil_vol_m3_d + water_vol_m3_d + gas_vol_m3_d) / _SECONDS_PER_DAY
    q_total_m3_h = q_total_m3_s * 3600.0
    h_c = inp.instrument_response_time_s * q_total_m3_h / (3600.0 * csa_actual_m2)

    # 5c. 控制体积：调 T3 calc_partial_volume（D7 接口冻结）
    pv_inp = PartialVolumeInput(
        D_m=inp.diameter_m,
        L_m=inp.length_m,
        head_type=inp.head_type,
        H_m=h_c,
        n_vessels=inp.n_vessels,
    )
    pv_result = calc_partial_volume(pv_inp)
    # T2 reviewer 修正：total_volume_m3 × n_vessels（不要 partial × n_vessels）
    control_volume_m3 = pv_result.total_volume_m3 * inp.n_vessels
    total_vol_m3_per_vessel = pv_result.total_volume_m3

    # 5d. 实际停留时间 V_total_per_vessel / Q_total_m3_s
    #    多容器情形：每容器处理 1/n_vessels 的总流量（按 D7 物理一致）
    q_per_vessel_m3_s = q_total_m3_s / inp.n_vessels
    residence_time_s = total_vol_m3_per_vessel / q_per_vessel_m3_s

    return (
        nozzle_inlet_id,
        nozzle_outlet_id,
        h_c,
        control_volume_m3,
        residence_time_s,
        total_vol_m3_per_vessel,
    )


def _imperial_conversion(
    vmax_m_s: float,
    csa_min_m2: float,
    csa_actual_m2: float,
    nozzle_inlet_id_m: float,
    nozzle_outlet_id_m: float,
    control_height_m: float,
    residence_time_s: float,
    rho_mix_kg_m3: float,
) -> dict[str, float]:
    """双单位转换（imperial_units=True 时填充；ft/s / ft² / in / s）。"""
    return {
        "vmax_ft_s": vmax_m_s / 0.3048,
        "csa_min_ft2": csa_min_m2 / 0.09290304,
        "csa_actual_ft2": csa_actual_m2 / 0.09290304,
        "nozzle_inlet_min_id_in": nozzle_inlet_id_m / 0.0254,
        "nozzle_outlet_min_id_in": nozzle_outlet_id_m / 0.0254,
        "control_height_ft": control_height_m / 0.3048,
        "residence_time_min": residence_time_s / 60.0,
        "rho_mix_lb_ft3": rho_mix_kg_m3 * 0.062428,  # kg/m³ → lb/ft³
    }


def calc_two_phase_separator_sizing(
    inp: TwoPhaseSeparatorSizingInput,
) -> TwoPhaseSeparatorSizingResult:
    """两相分离器尺寸计算（5 段：Souders-Brown + CSA + 喷嘴 + 仪表 + 停留时间）。

    公式来源：WS-CA-PR-010 Rev A §3~§5 + SPEC §3.4.2 V1.2。

    Args:
        inp: TwoPhaseSeparatorSizingInput（frozen dataclass）

    Returns:
        TwoPhaseSeparatorSizingResult：13 数值字段 + formula_ref（dict，
        含 T3 几何 + WS-CA-PR-010 sizing 两部分合并）。

    Raises:
        TwoPhaseSeparatorSizingError: 输入物理量越界或 SG/density 反推不一致。
    """
    _validate_input(inp)

    # 阶段 1：体积流量
    (
        oil_vol_bbl_d,
        water_vol_bbl_d,
        gas_vol_mmscfd,
        oil_vol_m3_d,
        water_vol_m3_d,
        gas_vol_m3_d,
    ) = _stage1_volumetric_flows(inp)

    # 阶段 2：混合相密度
    rho_mix = _stage2_mixed_density(
        oil_vol_m3_d, water_vol_m3_d, gas_vol_m3_d,
        inp.oil_density_kg_m3, inp.water_density_kg_m3, inp.gas_density_kg_m3,
    )

    # 液相密度（油 + 水体积加权；用于 Souders-Brown）
    liquid_vol_m3_d = oil_vol_m3_d + water_vol_m3_d
    if liquid_vol_m3_d > 0:
        rho_L = (
            oil_vol_m3_d * inp.oil_density_kg_m3
            + water_vol_m3_d * inp.water_density_kg_m3
        ) / liquid_vol_m3_d
    else:
        # 零液相边界：用 gas_density 替代（不应发生；物理不合理）
        rho_L = inp.gas_density_kg_m3 * 1.5

    # 阶段 3：Souders-Brown Vmax
    vmax = _stage3_vmax_souders_brown(rho_L, inp.gas_density_kg_m3, inp.k_factor)

    # 阶段 4：CSA 校核
    csa_min, csa_actual = _stage4_csa_check(gas_vol_m3_d, vmax, inp.diameter_m)

    # 阶段 5：喷嘴 + 仪表 + 停留时间
    (
        nozzle_inlet_id,
        nozzle_outlet_id,
        h_c,
        control_volume_m3,
        residence_time_s,
        _total_vol_m3_per_vessel,
    ) = _stage5_nozzle_control_residence(
        inp, oil_vol_m3_d, water_vol_m3_d, gas_vol_m3_d, rho_mix, csa_actual,
    )

    # 公式溯源：合并 T3 几何 + WS-CA-PR-010 sizing（不覆盖 T3）
    pv_inp = PartialVolumeInput(
        D_m=inp.diameter_m,
        L_m=inp.length_m,
        head_type=inp.head_type,
        H_m=h_c,
        n_vessels=inp.n_vessels,
    )
    t3_formula_ref = calc_partial_volume(pv_inp).formula_ref
    sizing_formula_ref = {
        "stage1_volumetric": (
            f"oil_vol_bbl = m_oil / (ρ_oil × {_BARREL_TO_M3}); "
            f"gas_vol_mmscfd = m_gas / (ρ_gas × {_MMSCF_TO_M3})"
        ),
        "stage2_mixed_density": "ρ_mix = (Σ Q_i × ρ_i) / (Σ Q_i)",
        "stage3_souders_brown": (
            "Vmax = K × √((ρL − ρV) / ρV) [WS-CA-PR-010 §4.2]"
        ),
        "stage4_csa": (
            f"A_min = Q_gas / (Vmax × {_CSA_UTILIZATION_FACTOR}); "
            "A_actual = π·D²/4 [WS-CA-PR-010 §4.3]"
        ),
        "stage5_nozzle": (
            "ID = √(4m² / (π × N × ρ_mix)) [WS-CA-PR-010 §5.1]"
        ),
        "stage5_control": (
            "H_c = t_c × Q_total_volumetric_m3_h / (3600 × CSA) "
            "[WS-CA-PR-010 §5.3 / SPEC §3.4.2]"
        ),
        "stage5_residence": (
            "t_r = V_total_per_vessel / Q_per_vessel_m3_s "
            "(n_vessels 并联：Q_per_vessel = Q_total / n_vessels)"
        ),
        "ws_ca_pr_010_sizing": "Rev A §3~§5",
    }
    formula_ref = {**t3_formula_ref, **sizing_formula_ref}

    # 双单位转换（仅 imperial_units=True）
    imperial = None
    if inp.imperial_units:
        imperial = _imperial_conversion(
            vmax, csa_min, csa_actual,
            nozzle_inlet_id, nozzle_outlet_id,
            h_c, residence_time_s, rho_mix,
        )

    return TwoPhaseSeparatorSizingResult(
        oil_vol_rate_bbl_d=oil_vol_bbl_d,
        water_vol_rate_bbl_d=water_vol_bbl_d,
        gas_vol_rate_mmscfd=gas_vol_mmscfd,
        mixed_density_kg_m3=rho_mix,
        vmax_m_s=vmax,
        csa_min_m2=csa_min,
        csa_actual_m2=csa_actual,
        nozzle_inlet_min_id_m=nozzle_inlet_id,
        nozzle_outlet_min_id_m=nozzle_outlet_id,
        control_height_m=h_c,
        control_volume_m3=control_volume_m3,
        residence_time_s=residence_time_s,
        imperial_conversion=imperial,
        formula_ref=formula_ref,
    )


__all__ = [
    "TwoPhaseSeparatorSizingInput",
    "TwoPhaseSeparatorSizingResult",
    "TwoPhaseSeparatorSizingError",
    "calc_two_phase_separator_sizing",
    "VesselShape",
]