"""P5-3-4 PSV 泄放面积（API 520 + GB/T 12241 双路径 + ω 法两相流）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §344-369 + SUP-P5-PSV-001 §4.1：

公式（API 520 7th Ed. SI 主链）：
- 气体（API 520 §5.6.3）：
    A = W / (C_d × P_back × K_b)
    简化模型 V1：Cd = 0.975，K_b = 1.0（开口面积）
- 液体（API 520 §5.6.4）：
    A = W / (ρ_L × sqrt(2 × ΔP / ρ_L))
    = W / sqrt(2 × ρ_L × ΔP)
- 两相流 ω 法（API 520 §5.6.5）：
    ω = x_v / x_v_lim  （基于均相流模型）
    G_two_phase = G_total × (1 / (1 + ω × cp_v / cp_l ...))
    V1 简化：两相流直接 ω 系数修正单相 A

GB/T 12241 降级路径（SUP-P5-PSV-001 §4.1）：
- orifice_table_status = "incomplete_fallback"（V1 标记降级；待 P5-3-6 接 GB 标准孔口表）
- A = 同 API 公式但用 GB 公式常数（保守安全）

API/GB 计算逻辑完全隔离：独立函数 + 公用入口分发（按 standard 路由）。
formula_ref 结构化（F-09）：standard + version + clause。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError

# ---------- 类型别名 ----------


Phase = Literal["GAS", "LIQUID", "TWO_PHASE"]

TwoPhaseMethod = Literal["two_point", "single_point", "direct_integration"]

StandardCode = Literal["API", "GB"]


@dataclass(frozen=True)
class ReliefAreaFormulaRef:
    """泄放面积公式溯源（F-09）。"""

    standard: str
    version: str
    clause: str


# ---------- 输入输出 ----------


@dataclass(frozen=True)
class ReliefAreaInput:
    """泄放面积计算输入。

    物理量 SI 单位：
      - relief_mass_flow_kgs: 所需泄放质量流量 kg/s（来自 P5-3-3 aggregate）
      - phase: 相态（GAS / LIQUID / TWO_PHASE）
      - P_back_pa: 背压 Pa（PSV 出口侧）
      - P_set_pa: 整定压力 Pa
      - rho_L_kg_m3: 液体密度（LIQUID / TWO_PHASE 用）
      - T_k: 流体温度 K（GAS 用）
      - M_kg_per_mol: 摩尔质量 kg/mol（GAS 用）
      - Z: 压缩因子（GAS 用，默认 1.0）
      - k_cp_ratio: 比热容比 cp/cv（GAS 用，默认 1.4 空气）
      - two_phase_method: 两相流计算方法（TWO_PHASE 用）
      - omega: 两相流均相流模型参数（TWO_PHASE 用）
      - rho_g_kg_m3: 蒸汽密度（two_phase Leung 法用；缺则按理想气体从 P_back/T_k 估算）
    """

    relief_mass_flow_kgs: float
    phase: Phase
    P_back_pa: float
    P_set_pa: float
    rho_L_kg_m3: float = 0.0
    T_k: float = 300.0
    M_kg_per_mol: float = 0.029  # 空气
    Z: float = 1.0
    k_cp_ratio: float = 1.4
    two_phase_method: TwoPhaseMethod = "two_point"
    omega: float = 0.0
    rho_g_kg_m3: float = 0.0  # 0 = 由 P_back/T_k + 理想气体推导


@dataclass(frozen=True)
class ReliefAreaResult:
    """泄放面积计算结果。

    字段：
      - area_required_m2: 所需泄放面积 m²
      - orifice_diameter_m: 估算等效孔径 m（A=π·d²/4 反算）
      - phase: 相态（输入透传）
      - orifice_table_status: "exact" / "incomplete_fallback"
      - formula_ref: 公式溯源
    """

    area_required_m2: float
    orifice_diameter_m: float
    phase: Phase
    orifice_table_status: Literal["exact", "incomplete_fallback"]
    formula_ref: ReliefAreaFormulaRef


# ---------- 物理常量 ----------


_R_UNIVERSAL: Final[float] = 8.314  # J/(mol·K)

# API 520 SI 主链公式常数（V1 简化）
_API520_GAS_C_D_DEFAULT: Final[float] = 0.975  # 排放系数（API 520 Table 6）
_API520_GAS_K_B_DEFAULT: Final[float] = 1.0  # 背压修正（≤临界压比时）
_API520_LIQUID_K_V_DEFAULT: Final[float] = 0.975  # 液体排放系数
_GB12241_GAS_C_D_DEFAULT: Final[float] = 0.95  # GB 略保守
_GB12241_GAS_K_B_DEFAULT: Final[float] = 1.0


# ---------- 异常 ----------


class PsvReliefAreaInputError(PcsError):
    """PSV 泄放面积输入不合法（422）。"""

    code = "PSV_INPUT_ERROR"
    status = 422


# ---------- API 520 气体路径 ----------


def _gas_area_api520(
    W: float,
    P_back: float,
    T_k: float,
    M: float,
    Z: float,
    k: float,
) -> float:
    """API 520 §5.6.3 气体面积（SI 主链，完整等熵项）。

    严格公式（API 520 Part I 9th Ed. §5.6.2.3 critical flow）：
      G_c = C_d · K_b · P_back · √(M / (Z·R·T)) · √(k·(2/(k+1))^((k+1)/(k-1)) / (k-1))
      A = W / G_c

    各项物理意义：
      - C_d = 0.975（API 520 Table 6 排放系数）
      - K_b = 1.0（≤ 临界压比时；balanced bellows 需 ≥ 0.9）
      - M = 摩尔质量 kg/kmol
      - Z = 压缩因子
      - k = 比热比 cp/cv
      - 等熵指数项 = (k/(k-1)) × ((2/(k+1))^((k+1)/(k-1)))
        （k=1.4 空气 → 1.172 → √1.172 ≈ 1.0826）

    比 V1 简化（Cd·Kb·P_back 反推）更准确：原 V1 忽略 M/Z/T/k 等熵项，
    实际气体（蒸汽/烃类）结果偏差 10-30%。SUP-P5-PSV-001 §4.1 C6 fix。
    """
    if P_back <= 0:
        raise PsvReliefAreaInputError(f"P_back={P_back} Pa 必须 > 0")
    if T_k <= 0:
        raise PsvReliefAreaInputError(f"T_k={T_k} 必须 > 0")
    if M <= 0:
        raise PsvReliefAreaInputError(f"M_kg_per_mol={M} 必须 > 0")
    if Z <= 0:
        raise PsvReliefAreaInputError(f"Z={Z} 必须 > 0")
    if k <= 1.0:
        raise PsvReliefAreaInputError(f"k_cp_ratio={k} 必须 > 1.0（理想气体比热比下限）")

    R_universal = 8314.462618  # J/(kmol·K)
    # 等熵指数组合：√[(k/(k-1)) × ((2/(k+1))^((k+1)/(k-1)))]
    # k>1 保证分母 > 0；k 越大（cp/cv 接近 1）越接近极限
    isentropic_factor = math.sqrt(
        (k / (k - 1.0)) * ((2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0)))
    )
    # 临界质量通量 kg/(s·m²)
    G_c = (
        _API520_GAS_C_D_DEFAULT
        * _API520_GAS_K_B_DEFAULT
        * P_back
        * math.sqrt(M / (Z * R_universal * T_k))
        * isentropic_factor
    )
    return W / G_c


def calc_relief_area_api520_gas(inp: ReliefAreaInput) -> ReliefAreaResult:
    """API 520 §5.6.3 气体泄放面积。"""
    if inp.phase != "GAS":
        raise PsvReliefAreaInputError(
            f"calc_relief_area_api520_gas 仅接受 phase=GAS，传入 {inp.phase}"
        )

    area = _gas_area_api520(
        W=inp.relief_mass_flow_kgs,
        P_back=inp.P_back_pa,
        T_k=inp.T_k,
        M=inp.M_kg_per_mol,
        Z=inp.Z,
        k=inp.k_cp_ratio,
    )

    return _build_area_result(area, inp, "API_520", "7th", "§5.6.3")


# ---------- API 520 液体路径 ----------


def calc_relief_area_api520_liquid(inp: ReliefAreaInput) -> ReliefAreaResult:
    """API 520 §5.6.4 液体泄放面积。

    A = W / (K_v × √(2 × ρ_L × ΔP))
    ΔP = P_set - P_back（驱动压差）
    """
    if inp.phase != "LIQUID":
        raise PsvReliefAreaInputError(
            f"calc_relief_area_api520_liquid 仅接受 phase=LIQUID，传入 {inp.phase}"
        )
    if inp.P_set_pa <= inp.P_back_pa:
        raise PsvReliefAreaInputError(
            f"P_set={inp.P_set_pa} 必须 > P_back={inp.P_back_pa}"
        )
    if inp.rho_L_kg_m3 <= 0:
        raise PsvReliefAreaInputError(f"rho_L_kg_m3={inp.rho_L_kg_m3} 必须 > 0")

    delta_P = inp.P_set_pa - inp.P_back_pa
    area = inp.relief_mass_flow_kgs / (
        _API520_LIQUID_K_V_DEFAULT * math.sqrt(2.0 * inp.rho_L_kg_m3 * delta_P)
    )

    return _build_area_result(area, inp, "API_520", "7th", "§5.6.4")


# ---------- API 520 两相流 ω 法 ----------


def calc_relief_area_api520_two_phase(inp: ReliefAreaInput) -> ReliefAreaResult:
    """API 520 §4.3.5.2 两相流泄放面积（DIERS Leung 1996 ω 法）。

    Leung, J.C., "Two-Phase Flashing Flow", Chem. Eng. Prog., 1996 / DIERS Final Report §4.3:
        G_T = G_gas × √((1-ω) + ω × ρ_g / ρ_l)
        →  A_two_phase = A_gas / √((1-ω) + ω × ρ_g / ρ_l)
    其中：
      - ω = x_v / x_v_lim（均相流模型蒸汽含率比；调用方传）
      - ρ_l = 液体密度（必填，inp.rho_L_kg_m3）
      - ρ_g = 蒸汽密度：优先 inp.rho_g_kg_m3；缺则按理想气体 ρ_g = P_back × M / (Z × R × T_k)

    边界：
      - ω = 0 → A_TP = A_gas（纯气退化）
      - ρ_g << ρ_l（如水/蒸汽 ρ_g/ρ_l ~ 1e-3）→ A_TP ≈ A_gas / √(1-ω)，保守放大
      - ω = 1 且 ρ_g << ρ_l → A_TP → ∞（纯液相，无气相出口，物理上应由液相路径接管）
    """
    if inp.phase != "TWO_PHASE":
        raise PsvReliefAreaInputError(
            f"calc_relief_area_api520_two_phase 仅接受 phase=TWO_PHASE，传入 {inp.phase}"
        )
    if not (0.0 <= inp.omega <= 1.0):
        raise PsvReliefAreaInputError(f"omega={inp.omega} 必须在 [0, 1]")
    if inp.rho_L_kg_m3 <= 0:
        raise PsvReliefAreaInputError(
            f"TWO_PHASE 必填 rho_L_kg_m3（实测={inp.rho_L_kg_m3}）"
        )
    if inp.two_phase_method not in ("two_point", "single_point", "direct_integration"):
        raise PsvReliefAreaInputError(
            f"two_phase_method={inp.two_phase_method} 不在支持范围"
        )

    # 先按气体公式计算基线面积（用 omega=0 等价于纯气体）
    base_inp = ReliefAreaInput(
        relief_mass_flow_kgs=inp.relief_mass_flow_kgs,
        phase="GAS",
        P_back_pa=inp.P_back_pa,
        P_set_pa=inp.P_set_pa,
        rho_L_kg_m3=inp.rho_L_kg_m3,
        T_k=inp.T_k,
        M_kg_per_mol=inp.M_kg_per_mol,
        Z=inp.Z,
        k_cp_ratio=inp.k_cp_ratio,
    )
    base_area = _gas_area_api520(
        W=base_inp.relief_mass_flow_kgs,
        P_back=base_inp.P_back_pa,
        T_k=base_inp.T_k,
        M=base_inp.M_kg_per_mol,
        Z=base_inp.Z,
        k=base_inp.k_cp_ratio,
    )

    # 蒸汽密度：优先用入参；缺则理想气体推导
    R_universal = 8314.462618  # J/(kmol·K)
    if inp.rho_g_kg_m3 > 0:
        rho_g = inp.rho_g_kg_m3
    else:
        rho_g = inp.P_back_pa * inp.M_kg_per_mol / (inp.Z * R_universal * inp.T_k)

    # DIERS Leung 1996：G_T/G_gas = √((1-ω) + ω × ρ_g/ρ_l)
    #                  A_TP / A_gas = 1 / √((1-ω) + ω × ρ_g/ρ_l)
    omega = inp.omega
    density_ratio = rho_g / inp.rho_L_kg_m3
    denominator_sq = (1.0 - omega) + omega * density_ratio
    if denominator_sq <= 0:
        # 数学退化（不应发生：ω ∈ [0,1] 且 ρ_g/ρ_l > 0）
        raise PsvReliefAreaInputError(
            f"Leung 分母平方 ≤ 0（ω={omega}, ρ_g/ρ_l={density_ratio:.3e}）"
        )
    area = base_area / math.sqrt(denominator_sq)

    return _build_area_result(area, inp, "API_520", "7th", "§4.3.5.2")


# ---------- GB/T 12241 降级路径 ----------


def calc_relief_area_gb12241(inp: ReliefAreaInput) -> ReliefAreaResult:
    """GB/T 12241 泄放面积（V1 标记 incomplete_fallback）。

    orifice_table_status = "incomplete_fallback"：
    GB 标准孔口表完整数据待 P5-3-6 接 GB 标准孔口表。
    V1 用略保守公式常数（C_d=0.95 vs API 0.975）。
    """
    if inp.P_back_pa <= 0:
        raise PsvReliefAreaInputError(f"P_back={inp.P_back_pa} Pa 必须 > 0")
    if inp.relief_mass_flow_kgs <= 0:
        raise PsvReliefAreaInputError(
            f"relief_mass_flow_kgs={inp.relief_mass_flow_kgs} 必须 > 0"
        )

    # GB 略保守：C_d=0.95（同 API 气体公式结构；含 M/Z/k 等熵项与 API 一致）
    # GB 与 API 唯一差异：C_d（GB 0.95 vs API 0.975）
    R_universal = 8314.462618
    k = inp.k_cp_ratio
    isentropic_factor = math.sqrt(
        (k / (k - 1.0)) * ((2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0)))
    )
    G_c = (
        _GB12241_GAS_C_D_DEFAULT
        * _GB12241_GAS_K_B_DEFAULT
        * inp.P_back_pa
        * math.sqrt(inp.M_kg_per_mol / (inp.Z * R_universal * inp.T_k))
        * isentropic_factor
    )
    area = inp.relief_mass_flow_kgs / G_c

    result = _build_area_result(area, inp, "GB_T_12241", "2021", "§4.3.1")
    # 标记降级（不可变 dataclass：构造新对象）
    return ReliefAreaResult(
        area_required_m2=result.area_required_m2,
        orifice_diameter_m=result.orifice_diameter_m,
        phase=result.phase,
        orifice_table_status="incomplete_fallback",
        formula_ref=result.formula_ref,
    )


# ---------- 公用入口分发 ----------


def calc_relief_area(
    inp: ReliefAreaInput,
    *,
    standard: StandardCode = "API",
) -> ReliefAreaResult:
    """泄放面积入口分发（按 standard 路由）。

    API：按 phase 分发到 gas/liquid/two_phase
    GB：统一降级路径（V1 阶段不区分 phase）
    """
    if inp.relief_mass_flow_kgs <= 0:
        raise PsvReliefAreaInputError(
            f"relief_mass_flow_kgs={inp.relief_mass_flow_kgs} 必须 > 0"
        )

    if standard == "API":
        if inp.phase == "GAS":
            return calc_relief_area_api520_gas(inp)
        if inp.phase == "LIQUID":
            return calc_relief_area_api520_liquid(inp)
        if inp.phase == "TWO_PHASE":
            return calc_relief_area_api520_two_phase(inp)
        raise PsvReliefAreaInputError(f"phase={inp.phase} 不支持")
    if standard == "GB":
        return calc_relief_area_gb12241(inp)
    raise PsvReliefAreaInputError(f"standard={standard} 不支持")


# ---------- 辅助 ----------


def _build_area_result(
    area: float,
    inp: ReliefAreaInput,
    standard: str,
    version: str,
    clause: str,
) -> ReliefAreaResult:
    """构造 ReliefAreaResult（含 orifice_diameter 反算）。"""
    if area <= 0:
        raise PsvReliefAreaInputError(f"计算面积 {area} m² 非正")
    orifice_d = math.sqrt(4.0 * area / math.pi)
    return ReliefAreaResult(
        area_required_m2=area,
        orifice_diameter_m=orifice_d,
        phase=inp.phase,
        orifice_table_status="exact",
        formula_ref=ReliefAreaFormulaRef(
            standard=standard, version=version, clause=clause,
        ),
    )


__all__ = [
    "Phase",
    "TwoPhaseMethod",
    "StandardCode",
    "ReliefAreaFormulaRef",
    "ReliefAreaInput",
    "ReliefAreaResult",
    "calc_relief_area",
    "calc_relief_area_api520_gas",
    "calc_relief_area_api520_liquid",
    "calc_relief_area_api520_two_phase",
    "calc_relief_area_gb12241",
    "PsvReliefAreaInputError",
]