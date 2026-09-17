"""P5-3-2 PSV 其他工况（阀门关闭 + 反应失控 + 热膨胀）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §293-318 + SUP-P5-PSV-001 §4.1：

公式（API 521 7th Ed. SI 主链）：
- 阀门关闭（API 521 §5.15.2.3）— 液体段塞：
    Q_v = V_pipe × ρ_L / t_isolation
    基于上游管道段体积 + 隔离时间
- 反应失控（API 521 §5.15.2.4）— 化学反应放热：
    Q_r = (ΔH_rxn × r_reaction × V_reactor) / M
    r_reaction = k(T) × C^n（Ahrrenius 简化）
- 热膨胀（API 521 §5.15.2.5）— 等温容器液体热膨胀：
    W_mass = V_L × ρ_L × β × ΔT / t_heat
    β = 体膨胀系数 1/K

P5-3-2 范围：API 路径（V1）；GB 路径留 P5-3-6 profile 注入时扩展。
后续 P5-3-3 多工况叠加会同时调用本服务。

formula_ref 结构化（F-09）：
  standard=API_521, version=7th, clause=§5.15.2.X
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.services.exceptions import PcsError

# ---------- 类型别名 ----------


@dataclass(frozen=True)
class OtherCaseFormulaRef:
    """其他工况公式溯源（F-09：standard 含年份 + version 冗余 + clause）。"""

    standard: str
    version: str
    clause: str


# ---------- 阀门关闭工况（API 521 §5.15.2.3）----------


@dataclass(frozen=True)
class ClosedValveInput:
    """阀门关闭工况输入。

    物理量 SI 单位：
      - V_pipe_m3: 上游管道液体体积
      - rho_L_kg_m3: 液体密度
      - t_isolation_s: 隔离时间（阀门关闭到 PSV 起跳的时间）
    """

    V_pipe_m3: float
    rho_L_kg_m3: float
    t_isolation_s: float


@dataclass(frozen=True)
class ClosedValveResult:
    """阀门关闭工况计算结果。"""

    relief_mass_flow_kgs: float
    relief_volume_flow_m3s: float
    formula_ref: OtherCaseFormulaRef


# ---------- 反应失控工况（API 521 §5.15.2.4）----------


@dataclass(frozen=True)
class ReactionRunawayInput:
    """反应失控工况输入。

    物理量 SI 单位：
      - Q_rxn_w: 反应放热功率 W（基于放热焓 + 反应速率）
      - fraction_to_valve: 反应热进入 PSV 的分率 [0, 1]
    """

    Q_rxn_w: float
    fraction_to_valve: float


@dataclass(frozen=True)
class ReactionRunawayResult:
    """反应失控工况计算结果。"""

    heat_input_w: float
    relief_mass_flow_kgs: float
    h_fg_j_per_kg: float
    formula_ref: OtherCaseFormulaRef


# ---------- 热膨胀工况（API 521 §5.15.2.5）----------


@dataclass(frozen=True)
class ThermalExpansionInput:
    """热膨胀工况输入。

    物理量 SI 单位：
      - V_L_m3: 容器中液体体积
      - rho_L_kg_m3: 液体密度
      - beta_per_K: 体膨胀系数 1/K
      - delta_T_k: 温升 K
      - t_heat_s: 受热时间（达到温升所需）
    """

    V_L_m3: float
    rho_L_kg_m3: float
    beta_per_k: float
    delta_T_k: float
    t_heat_s: float


@dataclass(frozen=True)
class ThermalExpansionResult:
    """热膨胀工况计算结果。"""

    expansion_volume_m3: float
    relief_mass_flow_kgs: float
    relief_volume_flow_m3s: float
    formula_ref: OtherCaseFormulaRef


# ---------- 物理常量 ----------


_RHO_AIR_DEFAULT_KG_M3: Final[float] = 1.2  # 空气标况（体积流量换算用）


# ---------- 异常 ----------


class PsvOtherCaseInputError(PcsError):
    """PSV 其他工况输入不合法（422）。"""

    code = "PSV_INPUT_ERROR"
    status = 422


# ---------- 阀门关闭工况实现 ----------


def calc_closed_valve_case(inp: ClosedValveInput) -> ClosedValveResult:
    """API 521 §5.15.2.3 阀门关闭工况（液体段塞）。

    W_mass = V_pipe × ρ_L / t_isolation
    Q_v    = W_mass / ρ_L = V_pipe / t_isolation
    """
    _validate_closed_valve(inp)

    relief_mass_flow_kgs = inp.V_pipe_m3 * inp.rho_L_kg_m3 / inp.t_isolation_s
    relief_volume_flow_m3s = relief_mass_flow_kgs / inp.rho_L_kg_m3

    return ClosedValveResult(
        relief_mass_flow_kgs=relief_mass_flow_kgs,
        relief_volume_flow_m3s=relief_volume_flow_m3s,
        formula_ref=OtherCaseFormulaRef(
            standard="API_521",
            version="7th",
            clause="§5.15.2.3",
        ),
    )


# ---------- 反应失控工况实现 ----------


def calc_reaction_runaway_case(
    inp: ReactionRunawayInput,
    *,
    h_fg_j_per_kg: float = 350_000.0,
) -> ReactionRunawayResult:
    """API 521 §5.15.2.4 反应失控工况。

    Q_reactor = Q_rxn × fraction_to_valve  （进入 PSV 的有效热输入）
    W_mass = Q_reactor / h_fg
    """
    _validate_reaction_runaway(inp)
    if h_fg_j_per_kg <= 0:
        raise PsvOtherCaseInputError(
            f"h_fg_j_per_kg={h_fg_j_per_kg} 必须 > 0"
        )

    heat_input_w = inp.Q_rxn_w * inp.fraction_to_valve
    relief_mass_flow_kgs = heat_input_w / h_fg_j_per_kg

    return ReactionRunawayResult(
        heat_input_w=heat_input_w,
        relief_mass_flow_kgs=relief_mass_flow_kgs,
        h_fg_j_per_kg=h_fg_j_per_kg,
        formula_ref=OtherCaseFormulaRef(
            standard="API_521",
            version="7th",
            clause="§5.15.2.4",
        ),
    )


# ---------- 热膨胀工况实现 ----------


def calc_thermal_expansion_case(inp: ThermalExpansionInput) -> ThermalExpansionResult:
    """API 521 §5.15.2.5 热膨胀工况。

    ΔV = V_L × β × ΔT    （液体体积膨胀量）
    W_mass = ρ_L × ΔV / t_heat
    Q_v   = ΔV / t_heat
    """
    _validate_thermal_expansion(inp)

    expansion_volume_m3 = inp.V_L_m3 * inp.beta_per_k * inp.delta_T_k
    relief_mass_flow_kgs = inp.rho_L_kg_m3 * expansion_volume_m3 / inp.t_heat_s
    relief_volume_flow_m3s = expansion_volume_m3 / inp.t_heat_s

    return ThermalExpansionResult(
        expansion_volume_m3=expansion_volume_m3,
        relief_mass_flow_kgs=relief_mass_flow_kgs,
        relief_volume_flow_m3s=relief_volume_flow_m3s,
        formula_ref=OtherCaseFormulaRef(
            standard="API_521",
            version="7th",
            clause="§5.15.2.5",
        ),
    )


# ---------- 校验 ----------


def _validate_closed_valve(inp: ClosedValveInput) -> None:
    if inp.V_pipe_m3 <= 0:
        raise PsvOtherCaseInputError(f"V_pipe_m3={inp.V_pipe_m3} 必须 > 0")
    if inp.rho_L_kg_m3 <= 0:
        raise PsvOtherCaseInputError(f"rho_L_kg_m3={inp.rho_L_kg_m3} 必须 > 0")
    if inp.t_isolation_s <= 0:
        raise PsvOtherCaseInputError(f"t_isolation_s={inp.t_isolation_s} 必须 > 0")


def _validate_reaction_runaway(inp: ReactionRunawayInput) -> None:
    if inp.Q_rxn_w <= 0:
        raise PsvOtherCaseInputError(f"Q_rxn_w={inp.Q_rxn_w} 必须 > 0")
    if not (0.0 <= inp.fraction_to_valve <= 1.0):
        raise PsvOtherCaseInputError(
            f"fraction_to_valve={inp.fraction_to_valve} 必须在 [0, 1]"
        )


def _validate_thermal_expansion(inp: ThermalExpansionInput) -> None:
    if inp.V_L_m3 <= 0:
        raise PsvOtherCaseInputError(f"V_L_m3={inp.V_L_m3} 必须 > 0")
    if inp.rho_L_kg_m3 <= 0:
        raise PsvOtherCaseInputError(f"rho_L_kg_m3={inp.rho_L_kg_m3} 必须 > 0")
    if inp.beta_per_k <= 0:
        raise PsvOtherCaseInputError(f"beta_per_k={inp.beta_per_k} 必须 > 0")
    if inp.delta_T_k < 0:
        raise PsvOtherCaseInputError(f"delta_T_k={inp.delta_T_k} 必须 >= 0")
    if inp.t_heat_s <= 0:
        raise PsvOtherCaseInputError(f"t_heat_s={inp.t_heat_s} 必须 > 0")


__all__ = [
    "OtherCaseFormulaRef",
    "ClosedValveInput",
    "ClosedValveResult",
    "ReactionRunawayInput",
    "ReactionRunawayResult",
    "ThermalExpansionInput",
    "ThermalExpansionResult",
    "calc_closed_valve_case",
    "calc_reaction_runaway_case",
    "calc_thermal_expansion_case",
    "PsvOtherCaseInputError",
]