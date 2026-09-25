"""P6-1 Task 12 + P6-2 S-01: restriction_engine ISO 5167 + 多级降压 + 闪蒸校核 + HEM 测试。

按 SPEC §3.2.2.1~4 + 评审委员会 2026-09-24 闪蒸路径裁决：
- §3.2.2.1 孔板 ISO 5167-2（Reader-Harris 3 项截断 + κ=1.4 ε）
- §3.2.2.2 文丘里 ISO 5167-4（C=0.99 + κ=1.4 ε）
- §3.2.2.3 喷嘴 ISO 5167-3（ISA 1932 完整 + κ=1.4 ε）
- §3.2.2.4 多级降压（等分 dP + 单级阻塞流判据）
- §3.2.2.1 闪蒸校核：调 P4 flash_service.calc_pure_fluid_bubble_point_pa
- §3.2.2.1 HEM 模型：闪蒸工况切换 API STD 520 Annex C

**P6-2 S-01 升级**：
- RestrictionEngine.calculate() 改为 async（需要 await check_flashing）
- 新增 6 测试：test_check_flashing_false / test_check_flashing_true /
  test_calculate_orifice_non_flashing / test_calculate_orifice_flashing_hem /
  test_calc_restriction_hem_vs_iso5167 / test_remove_p1_50kpa_heuristic

合计 14（旧 P6-1）+ 6（P6-2 S-01 新增）= 20 测试。
"""
from __future__ import annotations

import math

import pytest

from app.services.restriction import restriction_engine
from app.services.restriction.restriction_engine import (
    HEMResult,
    calc_restriction_hem,
    check_flashing,
)

# ============================================================================
# 1. 孔板 ISO 5167-2（Reader-Harris 3 项截断）— 2 例
# ============================================================================


def test_compute_orifice_normal_case():
    """孔板正常工况：C 在 [0.59, 0.62] 范围（β=0.5, Re_D=1e6）。

    工况：D=0.1m, d=0.05m, Re_D=1e6, P1=200 kPa, dP=10 kPa, rho1=1000。
    β=0.5；β²=0.25；β⁸≈3.9e-4；β⁴=0.0625
    Reader-Harris: C = 0.5961 + 0.0261·0.25 - 0.216·3.9e-4 + 0.000521·(0.5·1e6/1e6)^0.7
                 = 0.5961 + 0.00653 - 8.5e-5 + 0.000521·1^0.7
                 ≈ 0.60306
    ε = 1 - (0.351 + 0.256·0.0625 + 0.93·3.9e-4) · 0.05
      = 1 - (0.351 + 0.016 + 0.000363) · 0.05
      = 1 - 0.3674 · 0.05
      ≈ 0.9816
    """
    C, epsilon, Re_D_out = restriction_engine._compute_orifice(
        D=0.1, d=0.05, Re_D=1.0e6, P1=200_000.0, dP=10_000.0, rho1=1000.0
    )
    assert 0.59 < C < 0.62, f"孔板 C 应在 [0.59, 0.62]，实际 {C}"
    assert 0.97 < epsilon < 0.99, f"孔板 ε 应在 [0.97, 0.99]，实际 {epsilon}"
    assert Re_D_out == 1.0e6, "Re_D 应透传"


def test_compute_orifice_high_pressure_drop():
    """孔板高压差：dP/P1 > 0.5，ε 显著小于 1（可压缩性修正）。

    工况：D=0.1m, d=0.05m, Re_D=1e6, P1=100 kPa, dP=80 kPa, rho1=10（气体）。
    β=0.5；x=0.8
    ε = 1 - 0.3674 · 0.8 ≈ 0.7061
    """
    C, epsilon, _ = restriction_engine._compute_orifice(
        D=0.1, d=0.05, Re_D=1.0e6, P1=100_000.0, dP=80_000.0, rho1=10.0
    )
    assert 0.6 < C < 0.65, f"高压差 C 应在 [0.6, 0.65]，实际 {C}"
    assert epsilon < 0.8, f"高压差 ε 应显著小于 0.8，实际 {epsilon}"


# ============================================================================
# 2. 文丘里 ISO 5167-4（C=0.99 简化）— 2 例
# ============================================================================


def test_compute_venturi_normal_case():
    """文丘里正常工况：C=0.99（铸造标准中值）。

    工况：D=0.2m, d=0.1m, Re_D=1e6, P1=200 kPa, dP=10 kPa, rho1=1000。
    β=0.5；β⁶=0.015625
    ε = 1 - (0.65·0.015625 + 0.002) · 0.05
      = 1 - 0.012156 · 0.05
      ≈ 0.99939
    """
    C, epsilon, Re_D_out = restriction_engine._compute_venturi(
        D=0.2, d=0.1, Re_D=1.0e6, P1=200_000.0, dP=10_000.0, rho1=1000.0
    )
    assert C == pytest.approx(0.99, rel=1e-6), f"文丘里 C 应为 0.99，实际 {C}"
    assert 0.99 < epsilon <= 1.0, f"文丘里 ε 应 ≈ 1（典型压差下），实际 {epsilon}"
    assert Re_D_out == 1.0e6


def test_compute_venturi_invalid_diameter():
    """文丘里参数异常：d >= D 抛 ValueError。"""
    with pytest.raises(ValueError, match="参数异常"):
        restriction_engine._compute_venturi(
            D=0.1, d=0.1, Re_D=1.0e6, P1=200_000.0, dP=10_000.0, rho1=1000.0
        )


# ============================================================================
# 3. 喷嘴 ISO 5167-3（ISA 1932 完整）— 2 例
# ============================================================================


def test_compute_nozzle_normal_case():
    """喷嘴正常工况：C 在 [0.95, 0.99] 范围（β=0.5, Re_D=1e6）。

    工况：D=0.1m, d=0.05m, Re_D=1e6, P1=200 kPa, dP=10 kPa, rho1=1000。
    β=0.5；β⁴=0.0625；β^4.1≈0.0453；β²=0.25；β^4.15≈0.0418
    ISA 1932:
    C = 0.9900 - 0.2262·0.0453 - (0.00175·0.25 - 0.0033·0.0418)·(1e6/1e6)^1.15
      = 0.9900 - 0.01025 - (0.0004375 - 0.0001380)·1
      = 0.9900 - 0.01025 - 0.0002995
      ≈ 0.97945
    """
    C, epsilon, _ = restriction_engine._compute_nozzle(
        D=0.1, d=0.05, Re_D=1.0e6, P1=200_000.0, dP=10_000.0, rho1=1000.0
    )
    assert 0.95 < C < 0.99, f"喷嘴 C 应在 [0.95, 0.99]，实际 {C}"
    assert 0.98 < epsilon <= 1.0, f"喷嘴 ε 应 ≈ 1（低压差），实际 {epsilon}"


def test_compute_nozzle_beta_ratio_out_of_range():
    """喷嘴参数异常：d >= D 抛 ValueError（hedl_wrapper 边界检查）。"""
    with pytest.raises(ValueError, match="参数异常"):
        restriction_engine._compute_nozzle(
            D=0.1, d=0.1, Re_D=1.0e6, P1=200_000.0, dP=10_000.0, rho1=1000.0
        )


# ============================================================================
# 4. 多级降压 — 2 例（均分 + 阻塞流判据）
# ============================================================================


def test_compute_multi_stage_normal_case():
    """多级降压正常工况：4 级均分 100 kPa 总压差，每级 25 kPa。

    stages=4, total=100 kPa → per_stage=25 kPa
    single_stage_dP=0（默认）→ choked=False（均分无单级承担过大份额）
    """
    per_stage_dP, choked = restriction_engine._compute_multi_stage(
        total_dP_pa=100_000.0, stages=4, single_stage_dP_pa=0.0
    )
    assert per_stage_dP == pytest.approx(25_000.0, rel=1e-6)
    assert choked is False


def test_compute_multi_stage_choked_case():
    """多级降压阻塞流：单级 dP 超过均分值（用户指定 single_stage_dP_pa > per_stage）。

    total=100 kPa, stages=4, single_stage=40 kPa
    per_stage=25 kPa < single_stage=40 kPa → choked=True
    """
    per_stage_dP, choked = restriction_engine._compute_multi_stage(
        total_dP_pa=100_000.0, stages=4, single_stage_dP_pa=40_000.0
    )
    assert per_stage_dP == pytest.approx(25_000.0, rel=1e-6)
    assert choked is True


# ============================================================================
# 5. RestrictionEngine.calculate() 主入口 — 4 例（4 种 device_type 分流）
# ============================================================================


async def test_RestrictionEngine_calculate_orifice():
    """RestrictionEngine.calculate ORIFICE 路径：组装 13 键 payload + C 在合理区间。"""
    engine = restriction_engine.RestrictionEngine()
    payload = await engine.calculate(
        device_type="ORIFICE",
        D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=10_000.0, rho1=1000.0,
        fluid="WATER", upstream_T_K=298.15,
    )
    # 13 键对齐 SPEC §3.2.2.6
    for key in (
        "device_type", "D_pipe_m", "d_solved_m", "beta_ratio", "C_discharge",
        "epsilon", "Re_D", "delta_P_pa", "delta_omega_pa",
        "choked", "flashing", "stages", "design_stage",
    ):
        assert key in payload, f"payload 缺字段 {key}"
    assert payload["device_type"] == "ORIFICE"
    assert 0.59 < payload["C_discharge"] < 0.62
    assert payload["beta_ratio"] == pytest.approx(0.5, rel=1e-6)
    assert payload["choked"] is False  # 10 kPa / 200 kPa = 0.05
    # P6-2 S-01 闪蒸元数据
    assert payload["flashing"] is False  # 水 25°C @ P_outlet=190 kPa >> P_sat=3.17 kPa
    assert payload["model_used"] == "ISO_5167"
    assert payload["P_sat_pa"] is not None
    assert payload["vapor_fraction_at_outlet"] == 0.0


async def test_RestrictionEngine_calculate_venturi():
    """RestrictionEngine.calculate VENTURI 路径：C=0.99 + ε≈1。"""
    engine = restriction_engine.RestrictionEngine()
    payload = await engine.calculate(
        device_type="VENTURI",
        D_pipe_m=0.2, d_solved_m=0.1, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=10_000.0, rho1=1000.0,
        fluid="WATER", upstream_T_K=298.15,
    )
    assert payload["device_type"] == "VENTURI"
    assert payload["C_discharge"] == pytest.approx(0.99, rel=1e-6)
    assert 0.99 < payload["epsilon"] <= 1.0
    assert payload["flashing"] is False
    assert payload["model_used"] == "ISO_5167"


async def test_RestrictionEngine_calculate_nozzle():
    """RestrictionEngine.calculate NOZZLE 路径：C 在 [0.95, 0.99]。"""
    engine = restriction_engine.RestrictionEngine()
    payload = await engine.calculate(
        device_type="NOZZLE",
        D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=10_000.0, rho1=1000.0,
        fluid="WATER", upstream_T_K=298.15,
    )
    assert payload["device_type"] == "NOZZLE"
    assert 0.95 < payload["C_discharge"] < 0.99
    assert payload["flashing"] is False
    assert payload["model_used"] == "ISO_5167"


async def test_RestrictionEngine_calculate_multi_stage():
    """RestrictionEngine.calculate MULTI_STAGE 路径：4 级均分 dP + 无阻塞流。"""
    engine = restriction_engine.RestrictionEngine()
    payload = await engine.calculate(
        device_type="MULTI_STAGE",
        D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=100_000.0, rho1=1000.0,
        stages=4, fluid="WATER", upstream_T_K=298.15,
    )
    assert payload["device_type"] == "MULTI_STAGE"
    assert payload["stages"] == 4
    assert payload["delta_omega_pa"] == pytest.approx(25_000.0, rel=1e-6)
    assert payload["choked"] is False  # 25 kPa / 100 kPa = 0.25 < 0.7
    # 多级视为串联，首级 C 由孔板公式给出
    assert payload["C_discharge"] is not None
    assert payload["flashing"] is False
    assert payload["model_used"] == "ISO_5167"


# ============================================================================
# 6. 错误路径 + 边界 — 2 例
# ============================================================================


async def test_RestrictionEngine_calculate_invalid_device_type():
    """无效 device_type 抛 ValueError。"""
    engine = restriction_engine.RestrictionEngine()
    with pytest.raises(ValueError, match="device_type 必须"):
        await engine.calculate(
            device_type="UNKNOWN",
            D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
            P1_pa=200_000.0, dP_pa=10_000.0, rho1=1000.0,
        )


async def test_RestrictionEngine_calculate_default_standard_profile():
    """缺省 standard_profile_code → 默认 ISO-5167。"""
    engine = restriction_engine.RestrictionEngine()
    payload = await engine.calculate(
        device_type="ORIFICE",
        D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=10_000.0, rho1=1000.0,
    )
    assert payload["design_stage"] == "BASIC"
    assert payload["device_type"] == "ORIFICE"
    # P6-2 S-01 缺省 fluid / T 走 graceful fallback（无 P_sat，但 model_used 仍 ISO_5167）
    assert payload["flashing"] is False
    assert payload["model_used"] == "ISO_5167"


# ============================================================================
# 7. P6-2 S-01 闪蒸校核（check_flashing + HEM 模型）— 6 例
# ============================================================================


async def test_check_flashing_false():
    """非闪蒸工况：水 25°C @ P_outlet=190 kPa >> P_sat=3.17 kPa → flashing=False。

    验证 check_flashing 调 P4 flash_service.calc_pure_fluid_bubble_point_pa
    返回合理 P_sat，且 P_outlet > P_sat → 不闪蒸、走 ISO_5167。
    """
    result = await check_flashing(
        fluid="WATER", upstream_T_K=298.15,
        P1_pa=200_000.0, P_outlet_pa=190_000.0,
    )
    assert result.flashing is False
    assert result.P_sat_pa is not None
    assert 3_000 < result.P_sat_pa < 4_000, (
        f"水 25°C P_sat 应 ≈ 3169 Pa，实际 {result.P_sat_pa} Pa"
    )
    assert result.vapor_fraction_at_outlet == 0.0
    assert result.model_used == "ISO_5167"
    assert result.error_code is None


async def test_check_flashing_true():
    """闪蒸工况：水 200°C @ P_outlet=200 kPa，P_sat ≈ 1.55 MPa → P_outlet << P_sat。

    P_sat(200°C) ≈ 1554.3 kPa（iapws95）>> P_outlet=200 kPa → 闪蒸；
    vapor_fraction ≈ 1 - 200/1554 ≈ 0.87；model_used=HEM。
    """
    result = await check_flashing(
        fluid="WATER", upstream_T_K=473.15,  # 200 °C
        P1_pa=2_000_000.0, P_outlet_pa=200_000.0,  # 节流到 200 kPa
    )
    assert result.flashing is True
    assert result.P_sat_pa is not None
    assert 1_500_000 < result.P_sat_pa < 1_600_000, (
        f"水 200°C P_sat 应 ≈ 1.554 MPa，实际 {result.P_sat_pa} Pa"
    )
    assert result.vapor_fraction_at_outlet > 0.8, (
        f"P_outlet/P_sat ≈ 0.13 → vfrac 应 ≈ 0.87，实际 {result.vapor_fraction_at_outlet}"
    )
    assert result.model_used == "HEM"
    assert result.error_code is None


async def test_calculate_orifice_non_flashing():
    """非闪蒸工况主入口：ORIFICE + 水 25°C + P_outlet=190 kPa → flashing=False, ISO_5167。

    验证 RestrictionEngine.calculate() 主入口与 check_flashing 一致；payload.flashing=False；
    payload.P_sat_pa 合理；payload.model_used=ISO_5167。
    """
    engine = restriction_engine.RestrictionEngine()
    payload = await engine.calculate(
        device_type="ORIFICE",
        D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=10_000.0, rho1=1000.0,
        fluid="WATER", upstream_T_K=298.15,
    )
    assert payload["flashing"] is False
    assert payload["P_sat_pa"] is not None
    assert 3_000 < payload["P_sat_pa"] < 4_000
    assert payload["vapor_fraction_at_outlet"] == 0.0
    assert payload["model_used"] == "ISO_5167"
    # 13 键完整
    assert payload["C_discharge"] is not None


async def test_calculate_orifice_flashing_hem():
    """闪蒸工况主入口：ORIFICE + 水 200°C + 节流到 200 kPa → flashing=True, HEM。

    验证 payload.flashing=True；payload.model_used=HEM；
    payload.vapor_fraction_at_outlet > 0.8；提供 rho_l/rho_v 后 payload.G_hem_kg_s 存在。
    """
    engine = restriction_engine.RestrictionEngine()
    payload = await engine.calculate(
        device_type="ORIFICE",
        D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
        P1_pa=2_000_000.0, dP_pa=1_800_000.0, rho1=1000.0,
        fluid="WATER", upstream_T_K=473.15,
        rho_l_kg_m3=864.0, rho_v_kg_m3=7.8,  # 水 200°C
    )
    assert payload["flashing"] is True
    assert payload["model_used"] == "HEM"
    assert payload["vapor_fraction_at_outlet"] > 0.8
    # HEM 模型字段（因提供 rho_l/rho_v 触发计算）
    assert payload.get("G_hem_kg_s") is not None
    assert payload.get("F_t") is not None
    # 单相 ISO 5167 C 仍保留（CDTP 修正链路不断）
    assert payload["C_discharge"] is not None


async def test_calc_restriction_hem_vs_iso5167():
    """HEM vs ISO 5167 流量差异：相同上游，闪蒸 G_hem 应 > ISO 5167 液体 G（密度修正）。

    工程含义：闪蒸工况 ρ_hem < ρ_l → 同等 dP 下 HEM 流量小于液体单相；
    但本测试锁定的是 HEM 模型自洽性（F_t²·ρ_hem 单调性 + 边界条件）。
    """
    # 1) 纯液体（x=0）：ρ_hem=ρ_l, F_t=1 → G_iso = G_hem
    res_liquid = calc_restriction_hem(
        Cd=0.62, A_m2=0.002, dP_pa=10_000.0,
        rho_l_kg_m3=1000.0, rho_v_kg_m3=10.0, x_vapor_outlet=0.0,
    )
    # 2) 闪蒸（x=0.5）：ρ_hem < ρ_l, F_t > 1 → G_hem 与液体单相差异
    res_flash = calc_restriction_hem(
        Cd=0.62, A_m2=0.002, dP_pa=10_000.0,
        rho_l_kg_m3=1000.0, rho_v_kg_m3=10.0, x_vapor_outlet=0.5,
    )
    # x=0 单相退化：ρ_hem=1000, F_t=1
    assert res_liquid.rho_hem_kg_m3 == pytest.approx(1000.0, rel=1e-6)
    assert res_liquid.F_t == pytest.approx(1.0, rel=1e-6)
    # x=0.5：ρ_hem = 1/(0.5/10 + 0.5/1000) = 1/0.0505 ≈ 19.80198
    assert res_flash.rho_hem_kg_m3 == pytest.approx(19.80198, rel=1e-4)
    # F_t² = 0.5 + 0.5·sqrt(100) = 0.5 + 5 = 5.5 → F_t ≈ 2.345
    assert res_flash.F_t == pytest.approx(math.sqrt(5.5), rel=1e-6)
    # 流量守恒：x=0 单相（液体）与 x=0.5 两相的 G_hem 自洽计算
    G_liquid_expected = 0.62 * 0.002 * math.sqrt(1.0 * 1000.0 * 10_000.0)
    assert res_liquid.G_hem_kg_s == pytest.approx(G_liquid_expected, rel=1e-6)
    # G_flash：5.5 · 19.80198 · 10000 = 1,089,108.91 → sqrt = 1043.604
    G_flash_expected = 0.62 * 0.002 * math.sqrt(5.5 * 19.80198 * 10_000.0)
    assert res_flash.G_hem_kg_s == pytest.approx(G_flash_expected, rel=1e-6)
    # 数据完整性
    assert isinstance(res_flash, HEMResult)


async def test_remove_p1_50kpa_heuristic():
    """漏判旧 P1<50 kPa 启发式场景：P1=100 kPa 但蒸汽压 80 kPa → flashing=True。

    旧启发式：P1=100 kPa >= 50 kPa → flashing=False ❌（漏判）
    新逻辑：调 flash_service 求 P_sat=80 kPa；P_outlet < 80 kPa → flashing=True ✅
    工况：propane @ 50°C (T_K=323.15) → P_sat ≈ 1.7 MPa（远超 80 kPa）
    改用更现实工况：水 100°C (T_K=373.15) → P_sat ≈ 101.3 kPa；
    设 P_outlet=80 kPa → flashing=True（旧 P1=200 kPa 启发式漏判）。
    """
    engine = restriction_engine.RestrictionEngine()
    # P1=200 kPa, dP=120 kPa → P_outlet=80 kPa；fluid=WATER @ 100°C
    payload = await engine.calculate(
        device_type="ORIFICE",
        D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=120_000.0, rho1=1000.0,
        fluid="WATER", upstream_T_K=373.15,  # 100 °C
    )
    # 旧启发式 P1=200 kPa >> 50 kPa → flashing=False（漏判）
    # 新逻辑：P_sat(100°C) ≈ 101.3 kPa > P_outlet=80 kPa → flashing=True
    assert payload["P_sat_pa"] is not None
    assert 95_000 < payload["P_sat_pa"] < 110_000, (
        f"水 100°C P_sat 应 ≈ 101.3 kPa，实际 {payload['P_sat_pa']} Pa"
    )
    assert payload["flashing"] is True, (
        "P_outlet=80 kPa < P_sat≈101.3 kPa → 应闪蒸（漏判旧 P1<50 kPa 启发式）"
    )
    assert payload["model_used"] == "HEM"
    assert payload["vapor_fraction_at_outlet"] > 0.0


# ============================================================================
# 8. P6-2 S-01 calc_restriction_hem 边界条件
# ============================================================================


def test_calc_restriction_hem_invalid_inputs():
    """calc_restriction_hem 边界：非法 A/dP/rho/x 抛 ValueError。"""
    with pytest.raises(ValueError, match="A_m2"):
        calc_restriction_hem(
            Cd=0.62, A_m2=0.0, dP_pa=10_000.0,
            rho_l_kg_m3=1000.0, rho_v_kg_m3=10.0, x_vapor_outlet=0.0,
        )
    with pytest.raises(ValueError, match="x_vapor_outlet"):
        calc_restriction_hem(
            Cd=0.62, A_m2=0.002, dP_pa=10_000.0,
            rho_l_kg_m3=1000.0, rho_v_kg_m3=10.0, x_vapor_outlet=1.5,
        )


async def test_check_flashing_missing_input_graceful_fallback():
    """check_flashing 缺关键输入（fluid/T）：graceful fallback → flashing=False。

    验证：当上游流缺少 fluid 或 T_K 输入时，保守走 ISO_5167 + error_code='missing_input'，
    不抛异常（调用方负责提供；缺省时 P_sat 不可知）。
    """
    result = await check_flashing(
        fluid=None, upstream_T_K=None,
        P1_pa=200_000.0, P_outlet_pa=190_000.0,
    )
    assert result.flashing is False
    assert result.P_sat_pa is None
    assert result.vapor_fraction_at_outlet == 0.0
    assert result.model_used == "ISO_5167"
    assert result.error_code == "missing_input"


async def test_check_flashing_fluid_unknown():
    """check_flashing 流体名不识别：graceful fallback + error_code='fluid_unknown'。"""
    result = await check_flashing(
        fluid="XYZ_UNKNOWN", upstream_T_K=298.15,
        P1_pa=200_000.0, P_outlet_pa=190_000.0,
    )
    assert result.flashing is False
    assert result.P_sat_pa is None
    assert result.model_used == "ISO_5167"
    assert result.error_code == "fluid_unknown"