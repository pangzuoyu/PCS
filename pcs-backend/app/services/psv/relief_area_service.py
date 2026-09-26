"""P5-3-4 PSV 泄放面积（API 520 + GB/T 12241 双路径 + ω 法两相流）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §344-369 + SUP-P5-PSV-001 §4.1：

项目基线版本：API 520 Part I **9th Ed.（2014-07）SI 主链**
（与 fire_case_service / other_cases_service 一致；PCS 全面采用 9th Ed. 作为规范版本）。
权威依据：API STD 520 Part I 9th Ed. SI 公式与表。

公式（API 520 9th Ed. SI 主链）：
- 气体（API 520 9th Ed. §5.6.3.1.1 critical flow）：
    Eq (5) SI: A = W / (C × K_d × P_1 × K_b × K_c) × √(T·Z/M)
    C from Eq (9): C = 0.03948 × √[k·(2/(k+1))^((k+1)/(k-1))]
    物理等价（SI 主链推导）：
        G_c = C_d × K_b × P × √(M/(Z·R·T)) × √[k·(2/(k+1))^((k+1)/(k-1))]
        A = W / G_c
    V1 默认：C_d = 0.975（K_d=K_b=K_c=1.0 时）
- 液体（API 520 9th Ed. §5.6.4）：
    A = W / (K_v × √(2·ρ_L·ΔP))
- 两相流 ω 法（API 520 9th Ed. **Annex C.2.2 Two-Point Omega Method**）：
    V1 简化实现：A_TP = A_gas / √((1-ω) + ω·ρ_g/ρ_l)
    完整 Annex C.2.2 实现（C.12/C.16-C.21）待 P5-3-7 接入

C6/C7 关闭依据（用户裁决 2026-09-18）：
- C6 公式 bug-089 修复：等熵因子从 √[(k/(k-1)) × ((2/(k+1))^...)]
  修正为 √[k × ((2/(k+1))^...)]，与 API 520 9th Ed. Eq (8)/(9) 一致。
  R 单位从 8314 J/(kmol·K) 修正为 8.314 J/(mol·K)。
  独立复算 3 案例 k=1.1/1.4/1.67 误差 < 0.01%：
  docs/adr/signatures/psv-gas-area-independent-verification.md
- C7 裁决（待实现）：选项 B（Annex C.2.2 Two-Point Omega Method）正确；
  当前实现为 Leung ω 简化形式（与 Annex C.2.2 近似但非严格等价），
  完整 Annex C.2.2 Eq (C.12)/(C.13)/(C.16)-(C.21) 实现列入 P5-3-7 后续批。

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
    """API 520 9th Ed. §5.6.3.1.1 气体 critical flow 面积（SI 主链，完整等熵项）。

    严格公式推导（API 520 Part I 9th Ed. §5.6.3 Eq (5) + Eq (9) SI）：
      A = W / (C × K_d × P_1 × K_b × K_c) × √(T·Z/M)
      C = 0.03948 × √[k · (2/(k+1))^((k+1)/(k-1))]
    等价的物理形式（SI 主链推导）：
      G_c = C_d · K_b · P · √[M·k / (Z·R·T) · (2/(k+1))^((k+1)/(k-1))]
        = C_d · K_b · P · √(M / (Z·R·T)) · √[k · (2/(k+1))^((k+1)/(k-1))]
      A = W / G_c

    各项物理意义：
      - C_d = 0.975（API 520 Table 6 排放系数；K_d/K_b/K_c 全 1.0 退化）
      - K_b = 1.0（≤ 临界压比时；balanced bellows 需 ≥ 0.9）
      - M = 摩尔质量 kg/mol（M_kg_per_mol 入参）
      - Z = 压缩因子
      - k = 比热比 cp/cv
      - R = 8.314 J/(mol·K)（与 M 单位 kg/mol 配对）
      - 等熵指数项 = k · (2/(k+1))^((k+1)/(k-1))
        （k=1.4 空气 → 0.4689 → √0.4689 ≈ 0.6847；
         详见 API 520 9th Ed. §5.6.3 Eq (9) / Table 8：k=1.4→C=0.02681）

    边界与历史：
    - bug-088（commit a3757ed C6 fix）曾用 √[(k/(k-1)) × ((2/(k+1))^...)]
      公式（实为 subcritical flow F_2 因子一部分），导致结果偏大
      √(k/(k-1))/√k = √(1/(k-1)) 倍（k=1.4 空气 → 1.58x）。
    - bug-089 同时修正 R 单位（8314 J/(kmol·K) 配 kg/mol → 偏差 √1000）。
    - 独立复算 3 案例 k=1.1/1.4/1.67 误差 < 0.01%（API 520 9th Ed. §5.6.3）。
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

    # bug-089 fix: M 单位 kg/mol → R 必须 J/(mol·K)（不是 J/(kmol·K)）。
    # 原 a3757ed R=8314 J/(kmol·K) 配 M kg/mol → 偏差 √1000
    R_universal = 8.314462618  # J/(mol·K)
    # bug-089 fix: 等熵指数组合应为 √[k × ((2/(k+1))^((k+1)/(k-1)))]
    # (k/(k-1)) 因子是 subcritical flow F_2 系数的一部分，
    # 不能直接套用于 §5.6.3 critical flow（9th Ed. Eq (9)）。
    isentropic_factor = math.sqrt(
        k * ((2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0)))
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

    return _build_area_result(area, inp, "API_520", "9th", "§5.6.3")


# ---------- API 520 液体路径 ----------


def calc_relief_area_api520_liquid(inp: ReliefAreaInput) -> ReliefAreaResult:
    """API 520 9th Ed. §5.6.4 液体泄放面积（V1 简化：Bernoulli 形式）。

    A = W / (K_v × √(2 × ρ_L × ΔP))
    ΔP = P_set - P_back（驱动压差）
    完整 API 520 9th Ed. §5.6.4 公式含 K_v 粘度修正 + 容量认证系数，
    V1 简化下 K_v = 0.975；非认证阀门用保守 0.6 系数。
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

    return _build_area_result(area, inp, "API_520", "9th", "§5.6.4")


# ---------- API 520 两相流 ω 法 ----------


def calc_relief_area_api520_two_phase(inp: ReliefAreaInput) -> ReliefAreaResult:
    """API 520 9th Ed. **Annex C.2.2** 两相流泄放面积（V1 简化：Leung 1996 ω 法）。

    章节依据（项目基线 = API 520 9th Ed.）：
      - 9th/10th Ed. → **Annex C.2.2** Two-Point Omega Method
        （Eq C.12: ω = 9(v_9/v_o - 1); Eq C.13 critical 检查;
         Eq C.16/C.17 USC + Eq C.18/C.19 SI 质量通量;
         Eq C.20/C.21 面积公式）
      - 7th Ed. (2000) → Appendix D SIZING FOR TWO-PHASE LIQUID/VAPOR RELIEF
        （§3.10 概要 + Appendix D 完整 omega 方法 + Leung 1995 参考文献 4.12）

    V1 实现（Leung 1996 简化形式，调用方传 ω）：
        G_T = G_gas × √((1-ω) + ω × ρ_g / ρ_l)
        →  A_two_phase = A_gas / √((1-ω) + ω × ρ_g / ρ_l)
    其中：
      - ω = x_v / x_v_lim（均相流模型蒸汽含率比；调用方传）
      - ρ_l = 液体密度（必填，inp.rho_L_kg_m3）
      - ρ_g = 蒸汽密度：优先 inp.rho_g_kg_m3；缺则按理想气体
              ρ_g = P_back × M / (Z × R × T_k)（R = 8.314 J/(mol·K)）

    边界：
      - ω = 0 → A_TP = A_gas（纯气退化）
      - ρ_g << ρ_l（如水/蒸汽 ρ_g/ρ_l ~ 1e-3）→ A_TP ≈ A_gas / √(1-ω)，保守放大
      - ω = 1 且 ρ_g << ρ_l → A_TP → ∞（纯液相，无气相出口，物理上应由液相路径接管）

    C7 关闭依据（用户裁决 2026-09-18）：
      - C7 采纳 Annex C.2.2 Two-Point Omega Method（DIERS Leung 1996 等价简化）；
      - 当前实现用 Leung 1996 ω 公式（等效于 Annex C.2.2 简化形式）；
      - 完整 Annex C.2.2 Eq (C.12)/(C.13)/(C.16)-(C.21) 实现列入 **P5-3-7** 后续批
        （用户提供的 Python 模板：omega_two_point_area with Eq C.12/C.13/C.16-C.19/C.20/C.21）。
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
    # bug-089 fix: R 必须 8.314 J/(mol·K) 与 M kg/mol 单位配对（原 8314 偏差 √1000）
    R_universal = 8.314462618  # J/(mol·K)
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

    return _build_area_result(area, inp, "API_520", "9th", "Annex C.2.2")


# ---------- GB/T 12241 降级路径 ----------


def calc_relief_area_gb12241(inp: ReliefAreaInput) -> ReliefAreaResult:
    """GB/T 12241 泄放面积（V1 标记 incomplete_fallback）。

    orifice_table_status = "incomplete_fallback"：
    GB 标准孔口表完整数据待 P5-3-6 接 GB 标准孔口表。
    V1 用略保守公式常数（C_d=0.95 vs API 0.975）。

    bug-089 fix（P5-3-8 闭环，2026-09-18）：
      - R 单位 8314 → 8.314 J/(mol·K)（与 M kg/mol 配对，消除 √1000 偏差）
      - 等熵因子去掉 k/(k-1) 因子（误用 §5.6.4 subcritical F_2 Eq 18，
        正确为 §5.6.3 critical flow Eq 9 √[k × (2/(k+1))^((k+1)/(k-1))]）
    修复后 GB 与 API 仅差 C_d（0.95 vs 0.975 → GB 面积 ≈ API 面积 × 1.026）。
    """
    if inp.P_back_pa <= 0:
        raise PsvReliefAreaInputError(f"P_back={inp.P_back_pa} Pa 必须 > 0")
    if inp.relief_mass_flow_kgs <= 0:
        raise PsvReliefAreaInputError(
            f"relief_mass_flow_kgs={inp.relief_mass_flow_kgs} 必须 > 0"
        )

    # bug-089 fix: R 必须 8.314 J/(mol·K) 与 M kg/mol 配对（同 _gas_area_api520）
    # 原 8314 J/(kmol·K) → 偏差 √1000
    R_universal = 8.314462618  # J/(mol·K)
    k = inp.k_cp_ratio
    # bug-089 fix: 等熵因子形式与 API §5.6.3 Eq 9 一致（k/(k-1) 是 subcritical F_2 因子，
    # 不适用于 critical flow）
    isentropic_factor = math.sqrt(
        k * ((2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0)))
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