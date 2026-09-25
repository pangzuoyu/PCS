"""COOL_TOWER 循环水量 + 补充水量（蒸发/风吹/排污/总补充水）。

按 SPEC §3.2.4.3 + §3.2.4.4 P6-CT-001：

§3.2.4.3 循环水量：
    q_w_m3_s = heat_load_kw / (ρ_w × Cp_w × ΔT)
    q_w_m3_h = q_w_m3_s × 3600
    默认：ρ_w = 1000 kg/m³，Cp_w = 4.187 kJ/kg·K

§3.2.4.4 补充水量：
    E = q_w_m3_s × ΔT × Cp_w / h_vap          # 蒸发损失
    D = drift_fraction × q_w_m3_s              # 风吹损失
    B = E / (cycle_ratio − 1) − D               # 排污损失（cycle_ratio ≤ 1 时物理不合理）
    M = E + D + B                               # 总补充水
    默认：h_vap = 2400 kJ/kg，cycle_ratio = 4，drift_fraction = 0.001

§3.2.4.7 验收标准：蒸发损失 ≤ 5%（vs 1% ΔT 经验法）。

不依赖 DB（纯计算函数）；输入 heat_load_kw 来自 Task 25 heat_load_aggregator。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.exceptions import PcsError

# 工程默认值（与 SPEC §3.2.4.3 + §3.2.4.4 一致）
_RHO_W_DEFAULT = 1000.0  # kg/m³（水密度，0~80°C 范围近似常数）
_CP_W_DEFAULT = 4.187  # kJ/kg·K（水比热，0~80°C 范围近似常数）
_H_VAP_DEFAULT = 2400.0  # kJ/kg（蒸发潜热，典型工况近似）
_CYCLE_RATIO_DEFAULT = 4.0  # 浓缩倍数 C_cycle（典型 3~5）
_DRIFT_FRACTION_DEFAULT = 0.001  # 风吹损失系数（典型 0.001~0.002）
_DRIFT_FRACTION_MAX = 0.1  # 工程上限校验


# ───────────────────────────── 循环水量 ─────────────────────────────


@dataclass(frozen=True)
class WaterFlowInput:
    """循环水量输入（§3.2.4.3）。

    字段：
    - heat_load_kw: 热负荷 kW（来自 Task 25 heat_load_aggregator 汇总）
    - delta_t_k: 进/出水温差 K
    - rho_w: 水密度 kg/m³（默认 1000）
    - cp_w: 水比热 kJ/kg·K（默认 4.187）
    """

    heat_load_kw: float  # 热负荷 kW
    delta_t_k: float  # 温差 K
    rho_w: float = _RHO_W_DEFAULT  # kg/m³
    cp_w: float = _CP_W_DEFAULT  # kJ/kg·K


@dataclass(frozen=True)
class WaterFlowResult:
    """循环水量输出。

    字段：
    - q_w_m3_s: 循环水量 m³/s
    - q_w_m3_h: 循环水量 m³/h（工程常用单位）
    - formula_ref: 公式溯源标记 "API_CTI_ATC-105_§3.2.4.3"
    """

    q_w_m3_s: float  # m³/s
    q_w_m3_h: float  # m³/h
    formula_ref: str = "API_CTI_ATC-105_§3.2.4.3"


# ───────────────────────────── 补充水量 ─────────────────────────────


@dataclass(frozen=True)
class WaterBalanceInput:
    """补充水量输入（§3.2.4.4）。

    字段：
    - q_w_m3_s: 循环水量 m³/s（来自 calc_water_flow 输出）
    - delta_t_k: 温差 K
    - cp_w: 水比热 kJ/kg·K（默认 4.187）
    - h_vap: 蒸发潜热 kJ/kg（默认 2400）
    - cycle_ratio: 浓缩倍数 C_cycle（默认 4，典型 3~5；必须 > 1）
    - drift_fraction: 风吹损失系数（默认 0.001，范围 [0, 0.1]）
    """

    q_w_m3_s: float  # m³/s
    delta_t_k: float  # K
    cp_w: float = _CP_W_DEFAULT  # kJ/kg·K
    h_vap: float = _H_VAP_DEFAULT  # kJ/kg
    cycle_ratio: float = _CYCLE_RATIO_DEFAULT  # 浓缩倍数（必须 > 1）
    drift_fraction: float = _DRIFT_FRACTION_DEFAULT  # 风吹损失系数


@dataclass(frozen=True)
class WaterBalanceResult:
    """补充水量输出。

    字段：
    - evaporation_m3_s: 蒸发损失 E（m³/s）
    - drift_m3_s: 风吹损失 D（m³/s）
    - blowdown_m3_s: 排污损失 B（m³/s；工程下限 clamp 0）
    - makeup_m3_s: 总补充水 M（m³/s）
    - formula_ref: 公式溯源标记 "API_CTI_ATC-105_§3.2.4.4"
    """

    evaporation_m3_s: float  # m³/s
    drift_m3_s: float  # m³/s
    blowdown_m3_s: float  # m³/s
    makeup_m3_s: float  # m³/s
    formula_ref: str = "API_CTI_ATC-105_§3.2.4.4"


# ───────────────────────────── 异常类型 ─────────────────────────────


class WaterFlowInputError(PcsError):
    """循环水量输入不合法（422）。

    触发场景：heat_load_kw <= 0 / delta_t_k <= 0 / rho_w <= 0 / cp_w <= 0。
    """

    code = "WATER_FLOW_INPUT_ERROR"
    status = 422


class WaterBalanceInputError(PcsError):
    """补充水量输入不合法（422）。

    触发场景：q_w_m3_s <= 0 / delta_t_k < 0 / cp_w <= 0 / h_vap <= 0 /
    cycle_ratio <= 1 / drift_fraction ∉ [0, 0.1]。
    """

    code = "WATER_BALANCE_INPUT_ERROR"
    status = 422


# ───────────────────────────── 计算函数 ─────────────────────────────


def calc_water_flow(inp: WaterFlowInput) -> WaterFlowResult:
    """循环水量 Q_w = H / (ρ × Cp × ΔT)（§3.2.4.3）。

    实现步骤：
    1. 输入校验：heat > 0 / ΔT > 0 / ρ > 0 / Cp > 0
    2. q_w_m3_s = heat_load_kw / (ρ × Cp × ΔT)
    3. q_w_m3_h = q_w_m3_s × 3600

    Args:
        inp: WaterFlowInput（已冻结 dataclass）。

    Returns:
        WaterFlowResult（含 q_w_m3_s / q_w_m3_h / formula_ref）。

    Raises:
        WaterFlowInputError: 输入字段越界或非正（422）。
    """
    # 输入校验
    if inp.heat_load_kw <= 0:
        raise WaterFlowInputError(
            f"heat_load_kw ({inp.heat_load_kw}) 必须 > 0"
        )
    if inp.delta_t_k <= 0:
        raise WaterFlowInputError(
            f"delta_t_k ({inp.delta_t_k}) 必须 > 0"
        )
    if inp.rho_w <= 0:
        raise WaterFlowInputError(
            f"rho_w ({inp.rho_w}) 必须 > 0"
        )
    if inp.cp_w <= 0:
        raise WaterFlowInputError(
            f"cp_w ({inp.cp_w}) 必须 > 0"
        )

    # 循环水量
    q_w_m3_s = inp.heat_load_kw / (inp.rho_w * inp.cp_w * inp.delta_t_k)
    q_w_m3_h = q_w_m3_s * 3600.0
    return WaterFlowResult(q_w_m3_s=q_w_m3_s, q_w_m3_h=q_w_m3_h)


def calc_water_balance(inp: WaterBalanceInput) -> WaterBalanceResult:
    """补充水量 M = E + D + B（§3.2.4.4）。

    实现步骤：
    1. 输入校验：q_w > 0 / ΔT ≥ 0 / Cp > 0 / h_vap > 0 / cycle_ratio > 1 /
       drift_fraction ∈ [0, 0.1]
    2. E = q_w × ΔT × Cp / h_vap（蒸发损失）
    3. D = drift_fraction × q_w（风吹损失）
    4. B = E / (cycle_ratio − 1) − D（排污损失；负数 → clamp 0）
    5. M = E + D + B（总补充水）

    工程说明：
    - blowdown 变负 → cycle_ratio 过低或 drift 过大；保留 0 不截断
    - 蒸发损失 vs 经验法 1% ΔT：E / q_w ≈ ΔT × Cp / h_vap ≈ 1.74% ΔT
      （与 SPEC §3.2.4.7 验收 ≤5% 一致）

    Args:
        inp: WaterBalanceInput（已冻结 dataclass）。

    Returns:
        WaterBalanceResult（含 evaporation / drift / blowdown / makeup /
        formula_ref）。

    Raises:
        WaterBalanceInputError: 输入字段越界或非正（422）。
    """
    # 输入校验
    if inp.q_w_m3_s <= 0:
        raise WaterBalanceInputError(
            f"q_w_m3_s ({inp.q_w_m3_s}) 必须 > 0"
        )
    if inp.delta_t_k < 0:
        raise WaterBalanceInputError(
            f"delta_t_k ({inp.delta_t_k}) 必须 ≥ 0"
        )
    if inp.cp_w <= 0:
        raise WaterBalanceInputError(
            f"cp_w ({inp.cp_w}) 必须 > 0"
        )
    if inp.h_vap <= 0:
        raise WaterBalanceInputError(
            f"h_vap ({inp.h_vap}) 必须 > 0"
        )
    if inp.cycle_ratio <= 1:
        raise WaterBalanceInputError(
            f"cycle_ratio ({inp.cycle_ratio}) 必须 > 1"
        )
    if not 0 <= inp.drift_fraction <= _DRIFT_FRACTION_MAX:
        raise WaterBalanceInputError(
            f"drift_fraction ({inp.drift_fraction}) "
            f"必须在 [0, {_DRIFT_FRACTION_MAX}] 区间"
        )

    # 补充水量
    evaporation = inp.q_w_m3_s * inp.delta_t_k * inp.cp_w / inp.h_vap
    drift = inp.drift_fraction * inp.q_w_m3_s
    blowdown = evaporation / (inp.cycle_ratio - 1.0) - drift
    if blowdown < 0:
        # 工程提示：blowdown 变负 → cycle_ratio 过低或 drift 过大；保留 0 不截断
        blowdown = 0.0
    makeup = evaporation + drift + blowdown

    return WaterBalanceResult(
        evaporation_m3_s=evaporation,
        drift_m3_s=drift,
        blowdown_m3_s=blowdown,
        makeup_m3_s=makeup,
    )


__all__ = [
    "WaterFlowInput",
    "WaterFlowResult",
    "WaterFlowInputError",
    "calc_water_flow",
    "WaterBalanceInput",
    "WaterBalanceResult",
    "WaterBalanceInputError",
    "calc_water_balance",
]
