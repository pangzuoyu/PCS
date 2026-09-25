"""C-04: CV/RESTRICTION 交叉验证测试（pcs.cv_engine vs chedl_wrapper）。

按 C-04 偏差数据归档裁决（评审委员会 2026-09-24）：
- 偏差阈值分级：
  * 标准算例（IEC 60534-2-1 / ISO 5167 标准算例）≤1%
  * ChEDL 实施差异容差 ≤3%（P6 简化公式 vs fluids 完整 API）
- 4 例 RED→GREEN：液体/气体 × 非阻塞/阻塞。

设计要点：
- pcs.cv_engine 与 chedl_wrapper.control_valve_* 公式源相同（SPEC §3.2.1）
- pcs 实现补充阻塞流 clamp / cavitation / flashing（CVEngine 路径独有）
- 对照计算：当 pcs 进入阻塞/闪蒸路径时，用 chedl 的等效工况
  （如 chedl 不应用 clamp 时用 dP=Pc_term/x_choked 代入）作对照
- 4 例全部断言 |pcs.Cv - chedl.Cv| / chedl.Cv ≤ 3%
"""
from __future__ import annotations

from app.services import chedl_wrapper
from app.services.cv import cv_engine

# C-04 阈值常量
_C04_CHEDL_TOLERANCE = 0.03  # ChEDL 实施差异容差 3%
_C04_STANDARD_TOLERANCE = 0.01  # 标准算例 1%


def _relative_deviation(pcs_value: float, chedl_value: float) -> float:
    """相对偏差 = |pcs - chedl| / chedl（C-04 判定基准）。"""
    if chedl_value == 0:
        return float("inf") if pcs_value != 0 else 0.0
    return abs(pcs_value - chedl_value) / chedl_value


# ============================================================================
# 1. 液体非阻塞：CV 偏差 ≤3%（应实际 0%，公式完全一致）
# ============================================================================


def test_cv_vs_chedl_liquid_non_choked():
    """液体非阻塞：Q=100 m³/h, SG=1, dP=1 bar。

    工况：水工况，dP=1 bar << FL²·(Pc-Pv)/FF² ≈ 192 bar → 非阻塞。

    公式对照：
    - pcs.cv_engine._compute_Cv_liquid: Cv = Q·√(SG/dP) = 100·√(1/1) = 100
    - chedl.control_valve_C_liquid(Q=100, SG=1, dP=1): Cv = 100·√(1/1) = 100

    期望偏差 = 0%（公式完全一致）。
    """
    Q_m3h, SG, dP_bar = 100.0, 1.0, 1.0
    FL, FF, Pv, Pc, P1_pa = 0.9, 0.96, 2000.0, 22.0e6, 3.0e5

    # pcs 计算（带阻塞流校核；本工况不阻塞）
    pcs_Cv, choked, cavitation, flashing = cv_engine._compute_Cv_liquid(
        Q_m3h=Q_m3h, SG=SG, dP_bar=dP_bar,
        FL=FL, FF=FF, Pv=Pv, Pc=Pc, P1_pa=P1_pa,
    )
    assert choked is False, "工况非阻塞"
    assert cavitation is False, "P1 充足不空化"
    assert flashing is False, "P1 >> Pv 不闪蒸"

    # chedl 计算（仅基础公式）
    chedl_Cv = chedl_wrapper.control_valve_C_liquid(
        Q_m3h=Q_m3h, SG=SG, dP_bar=dP_bar,
    )

    # 偏差校验：标准算例 ≤1%，ChEDL ≤3%（取严标准 ≤1%）
    deviation = _relative_deviation(pcs_Cv, chedl_Cv)
    assert deviation <= _C04_STANDARD_TOLERANCE, (
        f"液体非阻塞偏差应 ≤1%（标准算例），实际 {deviation:.4%} "
        f"（pcs={pcs_Cv:.4f}, chedl={chedl_Cv:.4f}）"
    )


# ============================================================================
# 2. 液体阻塞：阻塞工况 Pc_term 重算 vs chedl 等效工况
# ============================================================================


def test_cv_vs_chedl_liquid_choked():
    """液体阻塞：dP ≥ FL²·(Pc-Pv)/FF² 时 pcs 用 Pc_term 重算 Cv。

    工况：Q=100 m³/h, SG=1, dP=200 bar（远大于 Pc_term ≈ 192 bar）。
    pcs 进入阻塞流路径，用 Pc_term 重算 Cv；chedl 不做 clamp，
    对照计算时把 chedl 也按 Pc_term 代入（公式相同）。

    对照原则：C-04 是偏差数据归档，不是双引擎一致性回归；
    pcs 阻塞流 clamp 是 SPEC §3.2.1 + IEC 60534-2-1 §5.2.1 规范行为，
    故对照值取 chedl 按 Pc_term 代入的结果。
    """
    Q_m3h, SG, dP_bar = 100.0, 1.0, 200.0
    FL, FF, Pv, Pc, P1_pa = 0.9, 0.96, 2000.0, 22.0e6, 3.0e5

    # pcs 计算（阻塞路径：Pc_term 重算）
    pcs_Cv, choked, cavitation, flashing = cv_engine._compute_Cv_liquid(
        Q_m3h=Q_m3h, SG=SG, dP_bar=dP_bar,
        FL=FL, FF=FF, Pv=Pv, Pc=Pc, P1_pa=P1_pa,
    )
    assert choked is True, "dP=200 bar > Pc_term 应触发阻塞流"

    # chedl 等效工况：用 Pc_term 代入（公式源相同）
    Pc_term_pa = (FL**2) * (Pc - Pv) / (FF**2)
    Pc_term_bar = Pc_term_pa / 1.0e5
    chedl_Cv_equiv = chedl_wrapper.control_valve_C_liquid(
        Q_m3h=Q_m3h, SG=SG, dP_bar=Pc_term_bar,
    )

    # 偏差校验：阻塞路径公式相同，应 ≤1%
    deviation = _relative_deviation(pcs_Cv, chedl_Cv_equiv)
    assert deviation <= _C04_STANDARD_TOLERANCE, (
        f"液体阻塞 Pc_term 重算偏差应 ≤1%（公式相同），实际 {deviation:.4%} "
        f"（pcs={pcs_Cv:.4f}, chedl_Pc_term={chedl_Cv_equiv:.4f}）"
    )


# ============================================================================
# 3. 气体非阻塞：Y 修正公式一致，偏差 ≤1%
# ============================================================================


def test_cv_vs_chedl_gas_non_choked():
    """气体非阻塞：x < F_γ·xT 时 Y = 1 - x/(3·F_γ·xT)。

    工况：空气 Q=100 Nm³/h, P1=10 bar, T1=300 K, M=29, Z=1,
    dP=1 bar, γ=1.4, xT=0.7 → x=0.1 < x_choked=0.7 → 非阻塞。

    公式对照：pcs._compute_Cv_gas 与 chedl.control_valve_cv_gas 公式源一致。
    """
    Q_Nm3h, P1_pa, T1_k, M, Z = 100.0, 10.0e5, 300.0, 29.0, 1.0
    dP_pa, gamma, xT = 1.0e5, 1.4, 0.7

    # pcs 计算
    pcs_Cv, choked = cv_engine._compute_Cv_gas(
        Q_Nm3h=Q_Nm3h, P1_pa=P1_pa, T1_k=T1_k,
        M=M, Z=Z, dP_pa=dP_pa, gamma=gamma, xT=xT,
    )
    assert choked is False, "x=0.1 < x_choked=0.7 非阻塞"

    # chedl 计算（公式相同：Fp=1）
    chedl_Cv = chedl_wrapper.control_valve_cv_gas(
        Q_Nm3h=Q_Nm3h, P1_pa=P1_pa, T1_k=T1_k,
        M=M, Z=Z, dP_pa=dP_pa, gamma=gamma, xT=xT,
    )

    deviation = _relative_deviation(pcs_Cv, chedl_Cv)
    assert deviation <= _C04_STANDARD_TOLERANCE, (
        f"气体非阻塞偏差应 ≤1%（公式相同），实际 {deviation:.4%} "
        f"（pcs={pcs_Cv:.4f}, chedl={chedl_Cv:.4f}）"
    )


# ============================================================================
# 4. 气体阻塞：x = x_choked 边界，pcs clamp Y=2/3 与 chedl 等同
# ============================================================================


def test_cv_vs_chedl_gas_choked():
    """气体阻塞：x ≥ x_choked 时 pcs 将 Y clamp 到 2/3。

    工况：空气 Q=100 Nm³/h, P1=10 bar, T1=300 K, M=29, Z=1,
    dP=7 bar → x=x_choked=0.7（边界阻塞）。

    pcs 阻塞流路径：x ≥ x_choked → Y = 2/3 = 1 - x_choked/(3·F_γ·xT)。
    chedl 在 x=x_choked 处：Y = 1 - 0.7/(3·1·0.7) = 2/3（数学一致）。

    公式与 sqrt 项完全相同，偏差 = 0%。
    """
    Q_Nm3h, P1_pa, T1_k, M, Z = 100.0, 10.0e5, 300.0, 29.0, 1.0
    dP_pa, gamma, xT = 7.0e5, 1.4, 0.7  # x=0.7 = x_choked（边界）

    # pcs 计算（边界阻塞路径：Y clamp=2/3）
    pcs_Cv, choked = cv_engine._compute_Cv_gas(
        Q_Nm3h=Q_Nm3h, P1_pa=P1_pa, T1_k=T1_k,
        M=M, Z=Z, dP_pa=dP_pa, gamma=gamma, xT=xT,
    )
    assert choked is True, "x=0.7 ≥ x_choked=0.7 应判定阻塞流（边界）"

    # chedl 计算（边界处 Y=2/3；与 pcs 公式相同）
    chedl_Cv = chedl_wrapper.control_valve_cv_gas(
        Q_Nm3h=Q_Nm3h, P1_pa=P1_pa, T1_k=T1_k,
        M=M, Z=Z, dP_pa=dP_pa, gamma=gamma, xT=xT,
    )

    # Y=2/3 + sqrt(x) 项都相同，偏差应 = 0%
    deviation = _relative_deviation(pcs_Cv, chedl_Cv)
    assert deviation <= _C04_CHEDL_TOLERANCE, (
        f"气体阻塞边界工况偏差应 ≤3%（公式相同），实际 {deviation:.4%} "
        f"（pcs={pcs_Cv:.4f}, chedl={chedl_Cv:.4f}）"
    )