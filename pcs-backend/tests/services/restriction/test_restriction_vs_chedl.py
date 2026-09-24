"""C-04: RESTRICTION 交叉验证测试（pcs.restriction_engine vs chedl_wrapper）。

按 C-04 偏差数据归档裁决（评审委员会 2026-09-24）：
- ISO 5167 系列（ORIFICE/VENTURI/NOZZLE）确定性高，偏差阈值 ≤3%
- pcs.restriction_engine 直接调用 chedl_wrapper.flow_meter_*（Task 12 设计）
  故基础公式 100% 一致；本测试作为回归测试，确保 wrapping 不引入偏差。
- 3 例 RED→GREEN：ORIFICE / VENTURI / NOZZLE。

设计要点：
- pcs.restriction_engine._compute_orifice → chedl_wrapper.flow_meter_orifice
- 三种装置（ORIFICE/VENTURI/NOZZLE）共用 _compute_X 签名
- 工况：液体 SG=1.0, D=0.1m, d=0.05m, Re_D=100000, P1=500 kPa, dP=50 kPa
"""
from __future__ import annotations

from app.services import chedl_wrapper
from app.services.restriction import restriction_engine

# C-04 阈值：ISO 5167 系列确定性高，公式相同，理论上 ~0% 偏差
_C04_RESTRICTION_TOLERANCE = 0.03  # ChEDL 实施差异容差 3%


def _relative_deviation(pcs_value: float, chedl_value: float) -> float:
    """相对偏差 = |pcs - chedl| / chedl（C-04 判定基准）。"""
    if chedl_value == 0:
        return float("inf") if pcs_value != 0 else 0.0
    return abs(pcs_value - chedl_value) / chedl_value


# 公共工况：液体（D=0.1m, d=0.05m → β=0.5；Re_D=10^5；P1=500 kPa；dP=50 kPa）
_COMMON_KWARGS: dict[str, float] = {
    "D": 0.1,
    "d": 0.05,
    "Re_D": 100_000.0,
    "P1": 500_000.0,
    "dP": 50_000.0,
    "rho1": 1000.0,
}


# ============================================================================
# 1. ORIFICE：ISO 5167-2 Reader-Harris/Gallagher
# ============================================================================


def test_restriction_vs_chedl_orifice():
    """孔板（ORIFICE）：pcs.restriction_engine._compute_orifice vs chedl.flow_meter_orifice。

    pcs 与 chedl 公式源相同（C/ε 均由 chedl_wrapper 提供），理论上偏差 = 0%。
    工况：D=0.1m, d=0.05m（β=0.5）, Re_D=10^5, P1=500 kPa, dP=50 kPa。

    期望：
    - C = 0.5961 + 0.0261·β² - 0.216·β⁸ + 0.000521·(10⁶·β/Re_D)^0.7
        = 0.5961 + 0.0261·0.25 - 0.216·0.00390625 + 0.000521·(5e6/1e5)^0.7
        ≈ 0.5961 + 0.006525 - 0.000844 + 0.000521·50^0.7
        ≈ 0.6027
    - ε = 1 - (0.351 + 0.256·β⁴ + 0.93·β⁸)·ΔP/P1
        = 1 - (0.351 + 0.256·0.0625 + 0.93·0.00390625)·0.1
        ≈ 1 - (0.367 + 0.0036)·0.1 ≈ 0.963
    """
    C_pcs, epsilon_pcs, _ = restriction_engine._compute_orifice(**_COMMON_KWARGS)
    C_chedl, epsilon_chedl = chedl_wrapper.flow_meter_orifice(
        D_m=_COMMON_KWARGS["D"],
        d_m=_COMMON_KWARGS["d"],
        Re_D=_COMMON_KWARGS["Re_D"],
        P1_pa=_COMMON_KWARGS["P1"],
        dP_pa=_COMMON_KWARGS["dP"],
        rho1=_COMMON_KWARGS["rho1"],
    )

    # C 偏差
    C_deviation = _relative_deviation(C_pcs, C_chedl)
    assert C_deviation <= _C04_RESTRICTION_TOLERANCE, (
        f"ORIFICE C 偏差应 ≤3%，实际 {C_deviation:.4%} "
        f"（pcs={C_pcs:.6f}, chedl={C_chedl:.6f}）"
    )
    # ε 偏差
    eps_deviation = _relative_deviation(epsilon_pcs, epsilon_chedl)
    assert eps_deviation <= _C04_RESTRICTION_TOLERANCE, (
        f"ORIFICE ε 偏差应 ≤3%，实际 {eps_deviation:.4%} "
        f"（pcs={epsilon_pcs:.6f}, chedl={epsilon_chedl:.6f}）"
    )


# ============================================================================
# 2. VENTURI：ISO 5167-4 铸造标准
# ============================================================================


def test_restriction_vs_chedl_venturi():
    """文丘里（VENTURI）：pcs.restriction_engine._compute_venturi vs chedl.flow_meter_venturi。

    文丘里 C 取铸造标准 0.99（chEDL Path A），β=0.5 时
    ε = 1 - (0.65·β⁶ + 0.002)·ΔP/P1 = 1 - (0.65·0.015625 + 0.002)·0.1 ≈ 0.9989。
    """
    C_pcs, epsilon_pcs, _ = restriction_engine._compute_venturi(**_COMMON_KWARGS)
    C_chedl, epsilon_chedl = chedl_wrapper.flow_meter_venturi(
        D_m=_COMMON_KWARGS["D"],
        d_m=_COMMON_KWARGS["d"],
        Re_D=_COMMON_KWARGS["Re_D"],
        P1_pa=_COMMON_KWARGS["P1"],
        dP_pa=_COMMON_KWARGS["dP"],
        rho1=_COMMON_KWARGS["rho1"],
    )

    C_deviation = _relative_deviation(C_pcs, C_chedl)
    assert C_deviation <= _C04_RESTRICTION_TOLERANCE, (
        f"VENTURI C 偏差应 ≤3%，实际 {C_deviation:.4%} "
        f"（pcs={C_pcs:.6f}, chedl={C_chedl:.6f}）"
    )
    eps_deviation = _relative_deviation(epsilon_pcs, epsilon_chedl)
    assert eps_deviation <= _C04_RESTRICTION_TOLERANCE, (
        f"VENTURI ε 偏差应 ≤3%，实际 {eps_deviation:.4%} "
        f"（pcs={epsilon_pcs:.6f}, chedl={epsilon_chedl:.6f}）"
    )


# ============================================================================
# 3. NOZZLE：ISO 5167-3 ISA 1932 完整公式
# ============================================================================


def test_restriction_vs_chedl_nozzle():
    """喷嘴（NOZZLE）：pcs.restriction_engine._compute_nozzle vs chedl.flow_meter_nozzle。

    喷嘴 ISA 1932 完整公式：β=0.5, Re_D=10^5 时
    C = 0.9900 - 0.2262·0.5^4.1 - (0.00175·0.25 - 0.0033·0.5^4.15)·(10^6/10^5)^1.15
      ≈ 0.9900 - 0.2262·0.0411 - (0.000438 - 0.000074)·10^1.15
      ≈ 0.9900 - 0.00929 - 0.000364·14.13
      ≈ 0.9900 - 0.00929 - 0.00514
      ≈ 0.9756
    ε = 1 - (0.7·β⁴ - 0.3·β⁸)·ΔP/P1 = 1 - (0.7·0.0625 - 0.3·0.00390625)·0.1
      ≈ 1 - (0.0438 - 0.00117)·0.1
      ≈ 0.9957
    """
    C_pcs, epsilon_pcs, _ = restriction_engine._compute_nozzle(**_COMMON_KWARGS)
    C_chedl, epsilon_chedl = chedl_wrapper.flow_meter_nozzle(
        D_m=_COMMON_KWARGS["D"],
        d_m=_COMMON_KWARGS["d"],
        Re_D=_COMMON_KWARGS["Re_D"],
        P1_pa=_COMMON_KWARGS["P1"],
        dP_pa=_COMMON_KWARGS["dP"],
        rho1=_COMMON_KWARGS["rho1"],
    )

    C_deviation = _relative_deviation(C_pcs, C_chedl)
    assert C_deviation <= _C04_RESTRICTION_TOLERANCE, (
        f"NOZZLE C 偏差应 ≤3%，实际 {C_deviation:.4%} "
        f"（pcs={C_pcs:.6f}, chedl={C_chedl:.6f}）"
    )
    eps_deviation = _relative_deviation(epsilon_pcs, epsilon_chedl)
    assert eps_deviation <= _C04_RESTRICTION_TOLERANCE, (
        f"NOZZLE ε 偏差应 ≤3%，实际 {eps_deviation:.4%} "
        f"（pcs={epsilon_pcs:.6f}, chedl={epsilon_chedl:.6f}）"
    )