"""P4-2-4：两相压降服务（Lockhart-Martinelli-Baker + 流型判定 + 校核）。

公式：
- 单相摩阻 f：Colebrook-White（Crane TP-410 / Perry's 8th ed. §6），
  层流（Re<2300）→ f = 64/Re。复用 sizing_service._colebrook_f，
  避免重复造轮子。
- Lockhart-Martinelli 参数 X = √[(dp/dz)_l / (dp/dz)_g]
- Baker 二相乘数：φ_l² = 1 + C/X + 1/X²，C = 21（turbulent-turbulent 默认）
- 二相压降梯度：(dp/dz)_tp = (dp/dz)_l × φ_l²  (Pa/m)
- 空泡率（Chisholm 简化）：ε_g = 1 / (1 + (1/X)^(2/3) × (ρ_g/ρ_l)^(1/3))

流型判定（简化 Mandhane / Baker）：
- MIST：v_sg ≥ 30 m/s 且 v_sl < 1 m/s（雾状；极高气速）
- ANNULAR：v_sg ≥ 3 m/s（环状；高气速液膜）
- BUBBLE：v_sg < 0.5 m/s 且 v_sl ≥ 0.5 m/s（气泡；低气速高液速）
- 垂直管（|incl-90°| < 1°）：默认 SLUG
- 水平管 STRATIFIED：v_sl < 0.05 m/s
- 水平管 WAVE：v_sl ∈ [0.05, 0.3) 且 v_sg < 1.0 m/s
- 兜底：ANNULAR

二相校核（基于 Lockhart-Martinelli X）：
- X ≥ 100 → FAIL（极端倍率，模型外推风险高）
- X ≥ 10 → WARNING（中倍率；建议复核）
- 否则 PASS

流型 override：
- MIST → FAIL（雾状流模型外推风险高）

设计参考：
- Chisholm, D. (1983). Two-Phase Flow in Pipelines and Heat Exchangers.
- Crane TP-410 (2009). Flow of Fluids Through Valves, Fittings, and Pipe.
- Perry's Chemical Engineers' Handbook, 8th ed., §6.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError
from app.services.pipe.sizing_service import _colebrook_f

# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class TwoPhaseInputError(PcsError):
    """TwoPhase 输入错误（业务非法 / 公式除零）。

    触发场景：
    - D_m ≤ 0（管径退化）
    - L_m ≤ 0（管长退化）
    - ρ_l ≤ 0 / ρ_g ≤ 0（密度退化）
    - μ_l ≤ 0 / μ_g ≤ 0（粘度退化）
    - σ ≤ 0（表面张力退化）
    - P1_pa ≤ 0（上游压力退化）
    - m_l < 0 / m_g < 0（负流量物理非法；= 0 视为零流量返回零 dp）
    - ρ_l ≤ ρ_g（液相必须重于气相；否则非两相流）
    """

    code = "TWO_PHASE_INPUT_ERROR"
    status = 422


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------


FlowPattern = Literal["ANNULAR", "MIST", "BUBBLE", "SLUG", "STRATIFIED", "WAVE"]
TwoPhaseCheck = Literal["PASS", "WARNING", "FAIL"]


@dataclass(frozen=True)
class TwoPhaseInput:
    """两相压降输入（SI 单位）。

    Attributes:
        liquid_mass_flow: 液相质量流量 (kg/s)
        gas_mass_flow: 气相质量流量 (kg/s)
        liquid_density: 液相密度 (kg/m³)
        gas_density: 气相密度 (kg/m³)
        liquid_viscosity: 液相动力粘度 (Pa·s)
        gas_viscosity: 气相动力粘度 (Pa·s)
        surface_tension: 表面张力 (N/m)
        pipe_diameter_m: 管内径 (m)
        pipe_roughness_m: 管壁绝对粗糙度 (m)
        inclination_deg: 倾角 (°；0=水平，90=垂直向上)
        L_m: 管长 (m)
        P1_pa: 上游压力 (Pa；用于未来压降比校核，本批预留)
    """

    liquid_mass_flow: float
    gas_mass_flow: float
    liquid_density: float
    gas_density: float
    liquid_viscosity: float
    gas_viscosity: float
    surface_tension: float
    pipe_diameter_m: float
    pipe_roughness_m: float
    inclination_deg: float
    L_m: float
    P1_pa: float


@dataclass(frozen=True)
class TwoPhaseResult:
    """两相压降计算结果。

    Attributes:
        Bx: Lockhart-Martinelli 参数 X = √[(dp/dz)_l / (dp/dz)_g]
        By: 液相二相乘数 φ_l² = (dp/dz)_tp / (dp/dz)_l
        flow_pattern: 流型（ANNULAR / MIST / BUBBLE / SLUG / STRATIFIED / WAVE）
        two_phase_check: 校核档位（PASS / WARNING / FAIL）
        liquid_velocity: 液相表观速度 (m/s)
        gas_velocity: 气相表观速度 (m/s)
        pressure_gradient: 总压降梯度 (kPa/m)
        void_fraction: 截面空泡率 ε_g（无量纲）
        calc_method: 计算方法标识（LOCKHART_MARTINELLI_BAKER）
    """

    Bx: float
    By: float
    flow_pattern: FlowPattern
    two_phase_check: TwoPhaseCheck
    liquid_velocity: float
    gas_velocity: float
    pressure_gradient: float
    void_fraction: float
    calc_method: str


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------


# Baker C 参数（turbulent-turbulent；Chisholm 1983 §4）
_BAKER_C: Final[float] = 21.0

# 流型判定阈值
_MIST_VSG_MIN: Final[float] = 30.0      # m/s
_MIST_VSL_MAX: Final[float] = 1.0       # m/s
_ANNULAR_VSG_MIN: Final[float] = 3.0    # m/s
_BUBBLE_VSG_MAX: Final[float] = 0.5     # m/s
_BUBBLE_VSL_MIN: Final[float] = 0.5     # m/s
_STRATIFIED_VSL_MAX: Final[float] = 0.05  # m/s
_WAVE_VSL_MAX: Final[float] = 0.3       # m/s
_WAVE_VSG_MAX: Final[float] = 1.0       # m/s
_VERTICAL_INCL_TOL: Final[float] = 1.0  # ±1° 视为垂直
_HORIZONTAL_INCL_TOL: Final[float] = 1.0  # ±1° 视为水平

# 校核档位阈值（Bx）
_BX_FAIL_MIN: Final[float] = 100.0
_BX_WARNING_MIN: Final[float] = 10.0


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _friction_factor(rho: float, v: float, D_m: float, mu: float, eps_m: float) -> float:
    """Darcy 摩阻系数 f：Colebrook（Re≥2300）或层流 64/Re。

    复用 sizing_service._colebrook_f（Crane TP-410 brentq 解）。
    """
    if v <= 0.0 or rho <= 0.0 or mu <= 0.0:
        return 0.0
    Re = rho * v * D_m / mu
    if Re < 2300.0:
        return 64.0 / Re
    return _colebrook_f(D_m=D_m, v_ms=v, rho=rho, mu=mu, eps_m=eps_m)


def _classify_flow_pattern(
    v_sl: float, v_sg: float, inclination_deg: float
) -> FlowPattern:
    """流型判定（简化 Mandhane / Baker map）。"""
    abs_incl = abs(inclination_deg)
    vertical = abs(abs_incl - 90.0) <= _VERTICAL_INCL_TOL
    horizontal = abs_incl <= _HORIZONTAL_INCL_TOL

    # MIST：极高气速 + 低液速
    if v_sg >= _MIST_VSG_MIN and v_sl < _MIST_VSL_MAX:
        return "MIST"
    # ANNULAR：高气速
    if v_sg >= _ANNULAR_VSG_MIN:
        return "ANNULAR"
    # BUBBLE：低气速 + 高液速（与方向无关）
    if v_sg < _BUBBLE_VSG_MAX and v_sl >= _BUBBLE_VSL_MIN:
        return "BUBBLE"
    # 垂直管剩余：默认 SLUG
    if vertical:
        return "SLUG"
    # 水平管细分
    if horizontal:
        if v_sl < _STRATIFIED_VSL_MAX:
            return "STRATIFIED"
        if v_sl < _WAVE_VSL_MAX and v_sg < _WAVE_VSG_MAX:
            return "WAVE"
        return "ANNULAR"
    # 倾斜管：退化为 ANNULAR（兜底；后续可扩展 Mandhane 倾斜线）
    return "ANNULAR"


def _classify_two_phase_check(Bx: float, flow_pattern: FlowPattern) -> TwoPhaseCheck:
    """两相校核档位（基于 Lockhart-Martinelli X + 流型）。

    阈值（Chisholm 1983 工程经验）：
    - FAIL：MIST（雾状流模型外推风险高）OR Bx ≥ 100（极端倍率）
    - WARNING：Bx ≥ 10（中倍率；建议复核二相乘数）
    - PASS：Bx < 10（模型可靠区间）

    注：ANNULAR 不直接触发 WARNING（属正常操作工况）；仅 Bx 极端或 MIST 才 FAIL。
    """
    if flow_pattern == "MIST":
        return "FAIL"
    if Bx >= _BX_FAIL_MIN:
        return "FAIL"
    if Bx >= _BX_WARNING_MIN:
        return "WARNING"
    return "PASS"


def _void_fraction_chisholm(Bx: float, rho_l: float, rho_g: float) -> float:
    """Chisholm 简化空泡率：ε_g = 1 / (1 + (1/X)^(2/3) × (ρ_g/ρ_l)^(1/3))。

    X 趋近 0 → ε_g → 0（液体主导）
    X 趋近 ∞ → ε_g → 1（气体主导）
    """
    if Bx <= 0.0:
        return 0.0
    rho_ratio = rho_g / rho_l if rho_l > 0 else 1.0
    return 1.0 / (1.0 + (1.0 / Bx) ** (2.0 / 3.0) * rho_ratio ** (1.0 / 3.0))


# ---------------------------------------------------------------------------
# 入口：calc_two_phase
# ---------------------------------------------------------------------------


def calc_two_phase(inp: TwoPhaseInput) -> TwoPhaseResult:
    """两相压降计算（Lockhart-Martinelli-Baker + 流型 + 校核）。

    公式：
    - v_sl = m_l_dot / (ρ_l × A)
    - v_sg = m_g_dot / (ρ_g × A)
    - Re_l, Re_g；Colebrook f_l, f_g
    - (dp/dz)_l = f_l × ρ_l × v_sl² / (2D)；(dp/dz)_g = f_g × ρ_g × v_sg² / (2D)
    - X² = (dp/dz)_l / (dp/dz)_g
    - φ_l² = 1 + C/X + 1/X²，C = 21
    - (dp/dz)_tp = (dp/dz)_l × φ_l²  →  pressure_gradient (kPa/m)
    - ε_g = 1 / (1 + (1/X)^(2/3) × (ρ_g/ρ_l)^(1/3))（Chisholm 简化）

    流型：见 _classify_flow_pattern（简化 Mandhane）。
    校核：见 _classify_two_phase_check（Bx + 流型）。

    Args:
        inp: 两相输入（SI 单位）

    Returns:
        TwoPhaseResult

    Raises:
        TwoPhaseInputError: 任一输入越界（D/L/ρ/μ/σ/P1 ≤ 0；m_l/m_g < 0；ρ_l ≤ ρ_g）
    """
    # --- 输入校验 ---
    if inp.pipe_diameter_m <= 0:
        raise TwoPhaseInputError(
            f"D_m={inp.pipe_diameter_m} 必须 > 0（管径退化 / 无效）",
            details={"D_m": inp.pipe_diameter_m},
        )
    if inp.L_m <= 0:
        raise TwoPhaseInputError(
            f"L_m={inp.L_m} 必须 > 0（管长退化 / 无效）",
            details={"L_m": inp.L_m},
        )
    if inp.liquid_density <= 0:
        raise TwoPhaseInputError(
            f"ρ_l={inp.liquid_density} 必须 > 0",
            details={"liquid_density": inp.liquid_density},
        )
    if inp.gas_density <= 0:
        raise TwoPhaseInputError(
            f"ρ_g={inp.gas_density} 必须 > 0",
            details={"gas_density": inp.gas_density},
        )
    if inp.liquid_viscosity <= 0:
        raise TwoPhaseInputError(
            f"μ_l={inp.liquid_viscosity} 必须 > 0",
            details={"liquid_viscosity": inp.liquid_viscosity},
        )
    if inp.gas_viscosity <= 0:
        raise TwoPhaseInputError(
            f"μ_g={inp.gas_viscosity} 必须 > 0",
            details={"gas_viscosity": inp.gas_viscosity},
        )
    if inp.surface_tension <= 0:
        raise TwoPhaseInputError(
            f"σ={inp.surface_tension} 必须 > 0",
            details={"surface_tension": inp.surface_tension},
        )
    if inp.P1_pa <= 0:
        raise TwoPhaseInputError(
            f"P1_pa={inp.P1_pa} 必须 > 0",
            details={"P1_pa": inp.P1_pa},
        )
    if inp.liquid_mass_flow < 0:
        raise TwoPhaseInputError(
            f"m_l={inp.liquid_mass_flow} 不能为负（物理非法）",
            details={"liquid_mass_flow": inp.liquid_mass_flow},
        )
    if inp.gas_mass_flow < 0:
        raise TwoPhaseInputError(
            f"m_g={inp.gas_mass_flow} 不能为负（物理非法）",
            details={"gas_mass_flow": inp.gas_mass_flow},
        )
    if inp.liquid_density <= inp.gas_density:
        raise TwoPhaseInputError(
            f"ρ_l={inp.liquid_density} 必须 > ρ_g={inp.gas_density}（液相必须重于气相；"
            f"否则非两相流）",
            details={
                "liquid_density": inp.liquid_density,
                "gas_density": inp.gas_density,
            },
        )

    # --- 表观速度 ---
    A = math.pi * inp.pipe_diameter_m ** 2 / 4.0
    v_sl = inp.liquid_mass_flow / (inp.liquid_density * A)
    v_sg = inp.gas_mass_flow / (inp.gas_density * A)

    # --- 单相摩阻梯度（Darcy-Weisbach per unit length）---
    f_l = _friction_factor(
        inp.liquid_density, v_sl, inp.pipe_diameter_m,
        inp.liquid_viscosity, inp.pipe_roughness_m,
    )
    f_g = _friction_factor(
        inp.gas_density, v_sg, inp.pipe_diameter_m,
        inp.gas_viscosity, inp.pipe_roughness_m,
    )
    dpdz_l = f_l * inp.liquid_density * v_sl ** 2 / (2.0 * inp.pipe_diameter_m)
    dpdz_g = f_g * inp.gas_density * v_sg ** 2 / (2.0 * inp.pipe_diameter_m)

    # --- Lockhart-Martinelli X + Baker φ_l² ---
    # X² = (dp/dz)_l / (dp/dz)_g；任一为 0 → X = 0
    if dpdz_g <= 0.0:
        Bx = 0.0
        By = 1.0 + _BAKER_C * 1.0e12  # 极大值（避免除零；Bx=0 时无物理意义）
    else:
        X_squared = dpdz_l / dpdz_g
        Bx = math.sqrt(X_squared) if X_squared > 0.0 else 0.0
        if Bx > 0.0:
            By = 1.0 + _BAKER_C / Bx + 1.0 / (Bx * Bx)
        else:
            By = 1.0 + _BAKER_C * 1.0e12

    # --- 二相压降梯度（kPa/m）---
    dpdz_tp = dpdz_l * By  # Pa/m
    pressure_gradient_kpa_m = dpdz_tp / 1000.0

    # --- 空泡率 ---
    void_fraction = _void_fraction_chisholm(Bx, inp.liquid_density, inp.gas_density)

    # --- 流型 + 校核 ---
    flow_pattern = _classify_flow_pattern(v_sl, v_sg, inp.inclination_deg)
    two_phase_check = _classify_two_phase_check(Bx, flow_pattern)

    return TwoPhaseResult(
        Bx=Bx,
        By=By,
        flow_pattern=flow_pattern,
        two_phase_check=two_phase_check,
        liquid_velocity=v_sl,
        gas_velocity=v_sg,
        pressure_gradient=pressure_gradient_kpa_m,
        void_fraction=void_fraction,
        calc_method="LOCKHART_MARTINELLI_BAKER",
    )


__all__ = [
    "FlowPattern",
    "TwoPhaseCheck",
    "TwoPhaseInput",
    "TwoPhaseInputError",
    "TwoPhaseResult",
    "calc_two_phase",
]
