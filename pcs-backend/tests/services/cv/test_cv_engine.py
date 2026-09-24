"""P6-1 Task 8: cv_engine IEC 60534-2-1 Cv 计算核心测试。

补齐 P6-0 Task 3 Path A 简化公式缺失：
- 液体阻塞流检测（FL/FF/Pv/Pc 参数）
- 气体 Y 修正 x_choked clamp（Task 3 仅在 Y≤0 时抛错，本任务完整 x ≥ x_choked clamp）
- 液体 cavitation / flashing 检测
- 噪音 SIL 简化法

公式源：SPEC §3.2.1.1~1.4（line 146-158 节录 + brief 详细化）。
"""
from __future__ import annotations

import math

import pytest

from app.services.cv import cv_engine

# ============================================================================
# 液体 Cv 计算（SPEC §3.2.1.1 + IEC 60534-2-1）
# ============================================================================


def test_compute_Cv_liquid_normal_case():
    """液体非阻塞工况：Cv = Q · √(SG/ΔP)。

    工况：水 Q=100 m³/h, SG=1, ΔP=1 bar, FL=0.9, FF=0.96, Pv=2000 Pa, Pc=22 MPa。
    手算：Cv = 100 · √(1/1) = 100。
    """
    Cv, choked, cavitation, flashing = cv_engine._compute_Cv_liquid(
        Q_m3h=100.0, SG=1.0, dP_bar=1.0,
        FL=0.9, FF=0.96, Pv=2000.0, Pc=22.0e6,
    )
    assert Cv == pytest.approx(100.0, rel=1e-6), (
        f"液体 Cv 应为 100.0，实际 {Cv}"
    )
    assert choked is False, "标准工况不应判定阻塞流"
    assert cavitation is False, "标准工况不应有空化"
    assert flashing is False, "标准工况不应有闪蒸"


def test_compute_Cv_liquid_choked_case():
    """液体阻塞流：dP ≥ FL²·(Pc-Pv)/FF²。

    工况：Pc_term = 0.9²·(22e6 - 2e3)/0.96² ≈ 19.25e6 Pa ≈ 192.5 bar。
    取 dP=200 bar > Pc_term → 阻塞流。
    """
    Cv, choked, cavitation, flashing = cv_engine._compute_Cv_liquid(
        Q_m3h=100.0, SG=1.0, dP_bar=200.0,
        FL=0.9, FF=0.96, Pv=2000.0, Pc=22.0e6,
    )
    assert choked is True, "dP ≥ Pc_term 应判定阻塞流"
    # 阻塞工况 Cv 基于 Pc_term 而非 dP
    Pc_term_bar = (0.9**2 * (22.0e6 - 2000.0) / 0.96**2) / 1.0e5
    expected_Cv_choked = 100.0 * math.sqrt(1.0 / Pc_term_bar)
    assert Cv == pytest.approx(expected_Cv_choked, rel=1e-6), (
        f"阻塞 Cv 应为 {expected_Cv_choked}（基于 Pc_term），实际 {Cv}"
    )


def test_compute_Cv_liquid_cavitation_case():
    """液体 cavitation：dP/P1 ≥ FL²/FF² 但未达阻塞。

    cavitation 判据（IEC 60534-2-1 §5.2.1）：当 FL²/FF² ≤ dP/P1 < Pc_term/P1
    且未闪蒸时为 cavitation。
    工况：取 P1 = 3 bar (绝对)，FL=0.9, FF=0.96, Pc=22e6 Pa, Pv=2000 Pa。
    计算：
        FL²/FF² = 0.81/0.9216 ≈ 0.879
        Pc_term_bar = (0.81 · 21.998e6 / 0.9216) / 1e5 ≈ 193.4 bar
        dP/P1 处于 0.879 ~ 64.5 之间 → cavitation（且 Pv/P1=2000/3e5≈0.0067 < 0.5，不闪蒸）
    取 dP=1.5 bar，P1=3 bar：dP/P1 = 0.5 < 0.879 → 应为正常。
    改取 dP=3 bar，P1=3 bar：dP/P1 = 1.0 > 0.879 → cavitation。
    """
    Cv, choked, cavitation, flashing = cv_engine._compute_Cv_liquid(
        Q_m3h=100.0, SG=1.0, dP_bar=3.0,
        FL=0.9, FF=0.96, Pv=2000.0, Pc=22.0e6, P1_pa=3.0e5,
    )
    assert choked is False, "dP/P1=1.0 < Pc_term/P1=64.5，未达阻塞"
    assert cavitation is True, "dP/P1=1.0 > FL²/FF²=0.879，应判定 cavitation"
    assert flashing is False, "Pv/P1=0.0067 < 0.5，不闪蒸"


# ============================================================================
# 气体 Cv 计算（SPEC §3.2.1.2/3 + IEC 60534-2-1 §6.3）
# ============================================================================


def test_compute_Cv_gas_with_Y_correction():
    """气体非阻塞：Y 修正 + 与 Task 3 Path A control_valve_cv_gas 一致。

    工况：空气 Q=100 Nm³/h, P1=10 bar, T1=300 K, M=29, Z=1,
    ΔP=1 bar, γ=1.4, xT=0.7。
    手算：
        x = 1/10 = 0.1
        F_γ = 1.4/1.4 = 1.0
        Y = 1 - 0.1/(3·1.0·0.7) = 1 - 0.04762 = 0.95238
        Cv = 100 / (0.0865·1·10·0.95238·√(0.1/(29·300·1)))
    """
    Cv, choked = cv_engine._compute_Cv_gas(
        Q_Nm3h=100.0, P1_pa=10.0e5, T1_k=300.0,
        M=29.0, Z=1.0, dP_pa=1.0e5, gamma=1.4, xT=0.7,
    )
    assert choked is False, "x=0.1 < x_choked=0.7，未达阻塞"
    # 手算预期值
    x = 0.1
    F_gamma = 1.4 / 1.4
    Y = 1.0 - x / (3.0 * F_gamma * 0.7)
    expected_Cv = 100.0 / (
        0.0865 * 1.0 * 10.0 * Y * math.sqrt(x / (29.0 * 300.0 * 1.0))
    )
    assert Cv == pytest.approx(expected_Cv, rel=1e-9), (
        f"气体 Cv 应为 {expected_Cv}，实际 {Cv}"
    )


def test_compute_Cv_gas_choked_case():
    """气体阻塞流：x ≥ F_gamma · xT 时 Y clamp 至 2/3。

    工况：取 ΔP=8 bar，P1=10 bar → x=0.8 > x_choked = F_gamma·xT = 1.0·0.7 = 0.7。
    此时 Y 应被 clamp 到 Y_choked = 1 - x_choked/(3·F_gamma·xT) = 2/3。
    Cv 用 Y_choked=2/3 计算：
        Cv = 100 / (0.0865·1·10·(2/3)·√(0.8/(29·300·1)))
    """
    Cv, choked = cv_engine._compute_Cv_gas(
        Q_Nm3h=100.0, P1_pa=10.0e5, T1_k=300.0,
        M=29.0, Z=1.0, dP_pa=8.0e5, gamma=1.4, xT=0.7,
    )
    assert choked is True, "x=0.8 ≥ x_choked=0.7，应判定阻塞流"
    # 阻塞 Y = 2/3
    Y_choked = 2.0 / 3.0
    expected_Cv_choked = 100.0 / (
        0.0865 * 1.0 * 10.0 * Y_choked * math.sqrt(0.8 / (29.0 * 300.0 * 1.0))
    )
    assert Cv == pytest.approx(expected_Cv_choked, rel=1e-6), (
        f"阻塞 Cv 应为 {expected_Cv_choked}（Y=2/3），实际 {Cv}"
    )


# ============================================================================
# 噪音 SIL 简化法（SPEC §3.2.1.4 + IEC 60534-8-3）
# ============================================================================


def test_compute_noise_sil_basic():
    """噪音 SIL 简化法：dB 与 Kc·ΔP·Q 对数相关（结果 > 0 即可）。

    工况：ΔP=1e5 Pa, Q=100 m³/h, Kc=1.0 → SIL 应 > 0 dB。
    """
    sil = cv_engine._compute_noise_sil(dP_pa=1.0e5, Q_m3h=100.0, Kc=1.0)
    assert isinstance(sil, float)
    assert sil > 0.0, f"SIL dB 应为正值，实际 {sil}"


# ============================================================================
# CvEngine.calculate() 主入口
# ============================================================================


def test_CvEngine_calculate_liquid():
    """CvEngine.calculate：液体路径调用 _compute_Cv_liquid 并组装 21 键 payload。

    最小字段（仅做引擎入口烟测；Task 10 接入 Pydantic CvCalculateRequest 完整 21 字段）。
    """
    engine = cv_engine.CvEngine()
    payload = engine.calculate(
        fluid_phase="LIQUID",
        Q_m3h=100.0, SG=1.0, dP_bar=1.0,
        FL=0.9, FF=0.96, Pv=2000.0, Pc=22.0e6, P1_pa=3.0e5,
    )
    assert "Cv_calculated" in payload
    assert payload["choked"] is False
    assert payload["cavitation"] is False
    assert payload["flashing"] is False
    assert payload["fluid_phase"] == "LIQUID"


def test_CvEngine_calculate_gas():
    """CvEngine.calculate：气体路径调用 _compute_Cv_gas 并组装 21 键 payload。"""
    engine = cv_engine.CvEngine()
    payload = engine.calculate(
        fluid_phase="GAS",
        Q_Nm3h=100.0, P1_pa=10.0e5, T1_k=300.0,
        M=29.0, Z=1.0, dP_pa=1.0e5, gamma=1.4, xT=0.7,
    )
    assert "Cv_calculated" in payload
    assert payload["choked"] is False
    assert payload["fluid_phase"] == "GAS"


def test_calculate_default_standard_profile_code_iec_60534():
    """CvEngine.calculate：C-07 裁决默认 standard_profile_code = IEC_60534。

    不传 standard_profile_code 时，payload['standard_profile_code'] 应为
    IEC_60534（GB/T 4213 等同采用 IEC 60534-2-1:2011；C-07 评审委员会 2026-09-24）。

    显式传值时也应透传（kwargs 参数化）。
    """
    engine = cv_engine.CvEngine()

    # 1. 不传 → 默认 IEC_60534
    payload_default = engine.calculate(
        fluid_phase="LIQUID",
        Q_m3h=100.0, SG=1.0, dP_bar=1.0,
        FL=0.9, FF=0.96, Pv=2000.0, Pc=22.0e6, P1_pa=3.0e5,
    )
    assert payload_default["standard_profile_code"] == "IEC_60534", (
        "默认 standard_profile_code 应为 IEC_60534，"
        f"实际 {payload_default['standard_profile_code']!r}"
    )

    # 2. 显式传 GB-12241 → 透传（仅溯源，不参与公式）
    payload_custom = engine.calculate(
        fluid_phase="LIQUID",
        Q_m3h=100.0, SG=1.0, dP_bar=1.0,
        FL=0.9, FF=0.96, Pv=2000.0, Pc=22.0e6, P1_pa=3.0e5,
        standard_profile_code="GB-12241",
    )
    assert payload_custom["standard_profile_code"] == "GB-12241", (
        f"显式传值应透传，实际 {payload_custom['standard_profile_code']!r}"
    )

    # 3. Cv_calculated 在两种 standard_profile_code 下必须完全一致（仅溯源不参与公式）
    assert payload_default["Cv_calculated"] == pytest.approx(
        payload_custom["Cv_calculated"], rel=1e-12
    ), (
        "standard_profile_code 仅溯源不参与公式，Cv_calculated 应相同："
        f"{payload_default['Cv_calculated']} vs {payload_custom['Cv_calculated']}"
    )