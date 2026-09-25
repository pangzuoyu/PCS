"""P6-2 Task 23 FLARE_SYS flare_tip 测试（API 521 §5.15.6）。

按 SPEC §3.2.3 P6-FLR + API 521 7th Ed. §5.15.6（火焰尖端速度）：

- 6 单元测试（不依赖 DB；纯计算函数）：
  1. test_flare_tip_basic_air：D=0.25, MW=28.97, k=1.4, T=300, P=101325,
     M=0.2 → ρ≈1.177 / a≈347.19 / A≈0.0491 / u≈69.44 / G≈81.74
     （手算校核）
  2. test_flare_tip_target_mach_05_vs_02：同输入 M=0.5 vs 0.2 → u 比 5:2
  3. test_flare_tip_actual_mach_恒等：u/a == target_mach（rel=1e-9）
  4. test_flare_tip_input_validation：D≤0 / MW≤0 / T≤0 / P≤0 / k≤1.0 /
     M 越界 → 422
  5. test_flare_tip_formula_ref：所有结果 formula_ref == "API_521_§5.15.6"
  6. test_flare_tip_density_sound_speed_consistency：
     ρ × R × T / MW ≈ P（验证理想气体假设）

测试模式参照 ``tests/services/flare/test_header_sizing.py``（纯计算函数，
无 DB / Mock session）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.exceptions import PcsError  # noqa: E402
from app.services.flare import (  # noqa: E402
    FlareTipInput,
    FlareTipInputError,
    FlareTipResult,
    calc_flare_tip,
)

# 通用气体常数（与 service 一致；用于手算校核）
_R_UNIVERSAL = 8314.462618  # J/(kmol·K)


# ============================================================================
# 1. 基础空气工况（手算校核）
# ============================================================================


def test_flare_tip_basic_air() -> None:
    """空气（N2 简化 MW=28.97/k=1.4）+ D=0.25 m + T=300 K + P=101325 Pa
    + M_target=0.2 → 手算校核 ρ/a/A/u/G 全字段。

    手算：
        ρ = P * MW / (R * T) = 101325 * 28.97 / (8314.462618 * 300)
          ≈ 1.1768 kg/m³
        a = sqrt(k * R * T / MW) = sqrt(1.4 * 8314.462618 * 300 / 28.97)
          ≈ 347.19 m/s
        A = π * D² / 4 = π * 0.25² / 4 ≈ 0.04909 m²
        u = M_target * a = 0.2 * 347.19 ≈ 69.44 m/s
        G = ρ * u ≈ 1.1768 * 69.44 ≈ 81.71 kg/(s·m²)
    """
    inp = FlareTipInput(
        header_diameter_m=0.25,
        mw_kg_kmol=28.97,
        tip_temperature_k=300.0,
        tip_pressure_pa=101325.0,
        specific_heat_ratio=1.4,
        target_mach=0.2,
    )
    r = calc_flare_tip(inp)
    assert isinstance(r, FlareTipResult)
    # 密度
    assert r.gas_density_kg_m3 == pytest.approx(1.177, abs=1e-3)
    # 声速
    assert r.sound_speed_m_s == pytest.approx(347.2, abs=1e-1)
    # 面积
    assert r.tip_area_m2 == pytest.approx(0.0491, abs=1e-4)
    # 速度
    assert r.tip_velocity_m_s == pytest.approx(69.44, abs=1e-2)
    # 质量流速
    assert r.mass_flux_kgs_m2 == pytest.approx(81.71, abs=1e-2)
    # 尖端直径 == header 直径（单点 tip 假设）
    assert r.tip_diameter_m == pytest.approx(0.25, abs=1e-12)


# ============================================================================
# 2. target_mach 比较（Mach 越大 → 速度越大）
# ============================================================================


def test_flare_tip_target_mach_05_vs_02() -> None:
    """同 input M=0.5 vs 0.2 → u 比 = 5:2（线性正比）。"""
    base_kw = dict(
        header_diameter_m=0.25,
        mw_kg_kmol=28.97,
        tip_temperature_k=300.0,
        tip_pressure_pa=101325.0,
        specific_heat_ratio=1.4,
    )
    r_02 = calc_flare_tip(FlareTipInput(target_mach=0.2, **base_kw))
    r_05 = calc_flare_tip(FlareTipInput(target_mach=0.5, **base_kw))
    # u_05 / u_02 == 5/2 = 2.5
    assert r_05.tip_velocity_m_s / r_02.tip_velocity_m_s == pytest.approx(2.5, abs=1e-9)


# ============================================================================
# 3. actual_mach 恒等于 target_mach（构造恒等）
# ============================================================================


def test_flare_tip_actual_mach_恒等() -> None:
    """u/a == target_mach（相对误差 ≤ 1e-9；纯数学恒等）。"""
    for m_target in (0.1, 0.2, 0.3, 0.5, 0.7, 0.95):
        r = calc_flare_tip(
            FlareTipInput(
                header_diameter_m=0.25,
                mw_kg_kmol=28.97,
                tip_temperature_k=300.0,
                tip_pressure_pa=101325.0,
                specific_heat_ratio=1.4,
                target_mach=m_target,
            )
        )
        assert r.actual_mach == pytest.approx(m_target, rel=1e-9)


# ============================================================================
# 4. 输入校验失败 → 422
# ============================================================================


def test_flare_tip_input_validation() -> None:
    """D ≤ 0 / MW ≤ 0 / T ≤ 0 / P ≤ 0 / k ≤ 1.0 / M 越界 → 422。"""
    # 各字段单独构造（无 base 字典 — 避免 kwarg 重复）
    # D <= 0
    with pytest.raises(FlareTipInputError):
        calc_flare_tip(
            FlareTipInput(
                header_diameter_m=0.0,
                mw_kg_kmol=28.97,
                tip_temperature_k=300.0,
                tip_pressure_pa=101325.0,
                specific_heat_ratio=1.4,
                target_mach=0.2,
            )
        )
    with pytest.raises(FlareTipInputError):
        calc_flare_tip(
            FlareTipInput(
                header_diameter_m=-1.0,
                mw_kg_kmol=28.97,
                tip_temperature_k=300.0,
                tip_pressure_pa=101325.0,
                specific_heat_ratio=1.4,
                target_mach=0.2,
            )
        )
    # MW <= 0
    with pytest.raises(FlareTipInputError):
        calc_flare_tip(
            FlareTipInput(
                header_diameter_m=0.25,
                mw_kg_kmol=0.0,
                tip_temperature_k=300.0,
                tip_pressure_pa=101325.0,
                specific_heat_ratio=1.4,
                target_mach=0.2,
            )
        )
    # T <= 0
    with pytest.raises(FlareTipInputError):
        calc_flare_tip(
            FlareTipInput(
                header_diameter_m=0.25,
                mw_kg_kmol=28.97,
                tip_temperature_k=-300.0,
                tip_pressure_pa=101325.0,
                specific_heat_ratio=1.4,
                target_mach=0.2,
            )
        )
    # P <= 0
    with pytest.raises(FlareTipInputError):
        calc_flare_tip(
            FlareTipInput(
                header_diameter_m=0.25,
                mw_kg_kmol=28.97,
                tip_temperature_k=300.0,
                tip_pressure_pa=-101325.0,
                specific_heat_ratio=1.4,
                target_mach=0.2,
            )
        )
    # k <= 1.0
    with pytest.raises(FlareTipInputError):
        calc_flare_tip(
            FlareTipInput(
                header_diameter_m=0.25,
                mw_kg_kmol=28.97,
                tip_temperature_k=300.0,
                tip_pressure_pa=101325.0,
                specific_heat_ratio=1.0,
                target_mach=0.2,
            )
        )
    with pytest.raises(FlareTipInputError):
        calc_flare_tip(
            FlareTipInput(
                header_diameter_m=0.25,
                mw_kg_kmol=28.97,
                tip_temperature_k=300.0,
                tip_pressure_pa=101325.0,
                specific_heat_ratio=0.5,
                target_mach=0.2,
            )
        )
    # M 越界（< 0.05 或 > 1.0）
    with pytest.raises(FlareTipInputError):
        calc_flare_tip(
            FlareTipInput(
                header_diameter_m=0.25,
                mw_kg_kmol=28.97,
                tip_temperature_k=300.0,
                tip_pressure_pa=101325.0,
                specific_heat_ratio=1.4,
                target_mach=0.04,
            )
        )
    with pytest.raises(FlareTipInputError):
        calc_flare_tip(
            FlareTipInput(
                header_diameter_m=0.25,
                mw_kg_kmol=28.97,
                tip_temperature_k=300.0,
                tip_pressure_pa=101325.0,
                specific_heat_ratio=1.4,
                target_mach=1.5,
            )
        )
    # 异常必须是 PcsError 子类（PcsError envelope 协议）
    assert issubclass(FlareTipInputError, PcsError)
    assert FlareTipInputError.code == "FLARE_TIP_INPUT_ERROR"
    assert FlareTipInputError.status == 422


# ============================================================================
# 5. formula_ref 恒等于 "API_521_§5.15.6"
# ============================================================================


def test_flare_tip_formula_ref() -> None:
    """所有结果的 formula_ref 恒等于 API_521_§5.15.6。"""
    r = calc_flare_tip(
        FlareTipInput(
            header_diameter_m=0.3,
            mw_kg_kmol=20.0,
            tip_temperature_k=400.0,
            tip_pressure_pa=200000.0,
            specific_heat_ratio=1.3,
            target_mach=0.5,
        )
    )
    assert r.formula_ref == "API_521_§5.15.6"
    # 另一组输入再验一次
    r2 = calc_flare_tip(
        FlareTipInput(
            header_diameter_m=0.5,
            mw_kg_kmol=44.01,
            tip_temperature_k=350.0,
            tip_pressure_pa=150000.0,
            specific_heat_ratio=1.28,
            target_mach=0.3,
        )
    )
    assert r2.formula_ref == "API_521_§5.15.6"


# ============================================================================
# 6. 密度 × R × T / MW ≈ P（验证理想气体一致性）
# ============================================================================


def test_flare_tip_density_sound_speed_consistency() -> None:
    """ρ × R × T / MW ≈ P（rel=1e-9；理想气体状态方程自洽）。

    用于交叉验证 api 521 §5.15.4 的等温理想气体密度公式与 §5.15.6 复用。
    """
    inp = FlareTipInput(
        header_diameter_m=0.25,
        mw_kg_kmol=28.97,
        tip_temperature_k=300.0,
        tip_pressure_pa=101325.0,
        specific_heat_ratio=1.4,
        target_mach=0.2,
    )
    r = calc_flare_tip(inp)
    p_recovered = r.gas_density_kg_m3 * _R_UNIVERSAL * inp.tip_temperature_k / inp.mw_kg_kmol
    assert p_recovered == pytest.approx(inp.tip_pressure_pa, rel=1e-9)
    # 声速平方应当 k*R*T/MW
    a2 = r.sound_speed_m_s ** 2
    assert a2 == pytest.approx(
        inp.specific_heat_ratio * _R_UNIVERSAL * inp.tip_temperature_k / inp.mw_kg_kmol,
        rel=1e-9,
    )
