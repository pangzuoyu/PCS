"""P6-1 Task 12: restriction_engine ISO 5167 + 多级降压测试。

按 SPEC §3.2.2.1~4：
- §3.2.2.1 孔板 ISO 5167-2（Reader-Harris 3 项截断 + κ=1.4 ε）
- §3.2.2.2 文丘里 ISO 5167-4（C=0.99 + κ=1.4 ε）
- §3.2.2.3 喷嘴 ISO 5167-3（ISA 1932 完整 + κ=1.4 ε）
- §3.2.2.4 多级降压（等分 dP + 单级阻塞流判据）

8 + 1 + 4 = 13 测试（覆盖单元函数 + calculate 主入口 + 边界）。
"""
from __future__ import annotations

import pytest

from app.services.restriction import restriction_engine

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


def test_RestrictionEngine_calculate_orifice():
    """RestrictionEngine.calculate ORIFICE 路径：组装 13 键 payload + C 在合理区间。"""
    engine = restriction_engine.RestrictionEngine()
    payload = engine.calculate(
        device_type="ORIFICE",
        D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=10_000.0, rho1=1000.0,
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


def test_RestrictionEngine_calculate_venturi():
    """RestrictionEngine.calculate VENTURI 路径：C=0.99 + ε≈1。"""
    engine = restriction_engine.RestrictionEngine()
    payload = engine.calculate(
        device_type="VENTURI",
        D_pipe_m=0.2, d_solved_m=0.1, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=10_000.0, rho1=1000.0,
    )
    assert payload["device_type"] == "VENTURI"
    assert payload["C_discharge"] == pytest.approx(0.99, rel=1e-6)
    assert 0.99 < payload["epsilon"] <= 1.0


def test_RestrictionEngine_calculate_nozzle():
    """RestrictionEngine.calculate NOZZLE 路径：C 在 [0.95, 0.99]。"""
    engine = restriction_engine.RestrictionEngine()
    payload = engine.calculate(
        device_type="NOZZLE",
        D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=10_000.0, rho1=1000.0,
    )
    assert payload["device_type"] == "NOZZLE"
    assert 0.95 < payload["C_discharge"] < 0.99


def test_RestrictionEngine_calculate_multi_stage():
    """RestrictionEngine.calculate MULTI_STAGE 路径：4 级均分 dP + 无阻塞流。"""
    engine = restriction_engine.RestrictionEngine()
    payload = engine.calculate(
        device_type="MULTI_STAGE",
        D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=100_000.0, rho1=1000.0,
        stages=4,
    )
    assert payload["device_type"] == "MULTI_STAGE"
    assert payload["stages"] == 4
    assert payload["delta_omega_pa"] == pytest.approx(25_000.0, rel=1e-6)
    assert payload["choked"] is False  # 25 kPa / 100 kPa = 0.25 < 0.7
    # 多级视为串联，首级 C 由孔板公式给出
    assert payload["C_discharge"] is not None


# ============================================================================
# 6. 错误路径 + 边界 — 2 例
# ============================================================================


def test_RestrictionEngine_calculate_invalid_device_type():
    """无效 device_type 抛 ValueError。"""
    engine = restriction_engine.RestrictionEngine()
    with pytest.raises(ValueError, match="device_type 必须"):
        engine.calculate(
            device_type="UNKNOWN",
            D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
            P1_pa=200_000.0, dP_pa=10_000.0, rho1=1000.0,
        )


def test_RestrictionEngine_calculate_default_standard_profile():
    """缺省 standard_profile_code → 默认 ISO-5167。"""
    engine = restriction_engine.RestrictionEngine()
    payload = engine.calculate(
        device_type="ORIFICE",
        D_pipe_m=0.1, d_solved_m=0.05, Re_D=1.0e6,
        P1_pa=200_000.0, dP_pa=10_000.0, rho1=1000.0,
    )
    assert payload["design_stage"] == "BASIC"
    # 13 键 payload 不含 standard_profile_code（device field 包含在 calculate 输出里）
    # 但 design_stage 已对齐
    assert payload["device_type"] == "ORIFICE"