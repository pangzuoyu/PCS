"""P6-2 Task 21 FLARE_SYS kod_sizing 测试。

按 SPEC §3.2.3 P6-FLR-002 + API 521 §5.15.3（Souders-Brown）+ §5.15.5
（Water Seal）：

- 8 单元测试（不依赖 DB；纯计算函数）：
  1. test_kod_basic_air_steam：vapor W=10 kg/s + ρ_V=1.177 + ρ_L=1000 + K=0.3
     → u_perm ≈ 8.760 m/s / A ≈ 0.970 m² / D ≈ 1.110 m（手算校核）
  2. test_kod_k_sb_inverse：同输入 K=0.1 vs 0.4 → D 反比
  3. test_kod_u_actual_equals_u_perm：实际速度 == 允许速度（数学恒等自检）
  4. test_kod_input_validation：vapor_mass_flow=0 / ρ_L < ρ_V / K > 2.0 / K <= 0 → 422
  5. test_water_seal_basic：header=200000 Pa + pot=0 + ρ_w=1000 + g=9.81 + sf=1.5
     → ΔP=200000 / h_seal ≈ 20.387 m / h_design ≈ 30.580 m（手算校核）
  6. test_water_seal_safety_factor_15：safety_factor=1.5 vs 2.0 → h_design 比 4:3
  7. test_water_seal_surge：surge_pressure=50000 Pa → h_seal 增大
  8. test_water_seal_input_validation：header ≤ pot / ρ_water ≤ 0 / safety_factor < 1 /
     surge_pressure < 0 → 422

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

from app.services.flare import (  # noqa: E402
    KodInput,
    KodResult,
    KodSizingInputError,
    KodSizingResult,
    WaterSealInput,
    WaterSealInputError,
    WaterSealResult,
    calc_kod,
    calc_kod_sizing,
    calc_water_seal,
)

# ============================================================================
# 1. 基础空气工况（手算校核）
# ============================================================================


def test_kod_basic_air_steam() -> None:
    """vapor W=10 kg/s + ρ_V=1.177 + ρ_L=1000 + K=0.3 → D ≈ 1.113 m。

    手算校核（API 521 §5.15.3 Souders-Brown）：
        u_perm = 0.3 × sqrt((1000 − 1.177) / 1.177) = 0.3 × sqrt(848.701) ≈ 8.739 m/s
        A = 10 / (1.177 × 8.739) ≈ 0.972 m²
        D = sqrt(4 × 0.972 / π) ≈ 1.113 m
        u_actual = 10 / (1.177 × 0.972) ≈ 8.739 m/s == u_perm（数学恒等）
        limit_ratio = 1.000

    注：brief 给出 u_perm ≈ 8.760 是 brief 手算的算术误差；按
    (1000 − 1.177) / 1.177 = 848.701 → sqrt = 29.131 → ×0.3 = 8.739。
    实施严格按 API 521 §5.15.3 公式 sqrt((ρ_L − ρ_V)/ρ_V) × K 实施。
    """
    inp = KodInput(
        vapor_mass_flow_kgs=10.0,
        vapor_density_kg_m3=1.177,
        liquid_density_kg_m3=1000.0,
        k_sb_m_s=0.3,
    )
    r = calc_kod(inp)
    assert isinstance(r, KodResult)
    # u_perm 手算 ≈ 8.739 m/s
    assert r.u_perm_m_s == pytest.approx(8.739, abs=5e-3)
    # A 手算 ≈ 0.972 m²
    assert r.area_m2 == pytest.approx(0.972, abs=1e-3)
    # D 手算 ≈ 1.113 m
    assert r.diameter_m == pytest.approx(1.113, abs=5e-3)
    # u_actual == u_perm（数学恒等）
    assert r.u_actual_m_s == pytest.approx(r.u_perm_m_s, rel=1e-9)
    # limit_ratio == 1.0（数学恒等；合规自检）
    assert r.limit_ratio == pytest.approx(1.0, rel=1e-9)
    # formula_ref 溯源
    assert r.formula_ref == "API_521_§5.15.3"


# ============================================================================
# 2. K_sb 反比关系（K 越小 → u_perm 越小 → A 越大 → D 越大）
# ============================================================================


def test_kod_k_sb_inverse() -> None:
    """同输入 K=0.1 vs 0.4 → D 反比（K 越小 → u_perm 越小 → 面积/直径越大）。"""
    base_kwargs = {
        "vapor_mass_flow_kgs": 10.0,
        "vapor_density_kg_m3": 1.177,
        "liquid_density_kg_m3": 1000.0,
    }
    r_low_k = calc_kod(KodInput(**base_kwargs, k_sb_m_s=0.1))
    r_high_k = calc_kod(KodInput(**base_kwargs, k_sb_m_s=0.4))

    # K 越小 → u_perm 越小
    assert r_low_k.u_perm_m_s < r_high_k.u_perm_m_s
    # K 越小 → 面积越大（与 u_perm 反比）
    assert r_low_k.area_m2 > r_high_k.area_m2
    # K 越小 → 直径越大
    assert r_low_k.diameter_m > r_high_k.diameter_m
    # 各自的 u_actual == u_perm（数学恒等）
    assert r_low_k.u_actual_m_s == pytest.approx(r_low_k.u_perm_m_s, rel=1e-9)
    assert r_high_k.u_actual_m_s == pytest.approx(r_high_k.u_perm_m_s, rel=1e-9)


# ============================================================================
# 3. u_actual == u_perm 数学恒等（合规自检）
# ============================================================================


def test_kod_u_actual_equals_u_perm() -> None:
    """实际蒸气速度 == 允许蒸气速度（数学恒等；合规自检 limit_ratio == 1.0）。

    由公式 u_perm = K × sqrt((ρ_L − ρ_V)/ρ_V) 与 A = W/(ρ_V × u_perm)，
    代入 u_actual = W/(ρ_V × A) 必然等于 u_perm；极限比 limit_ratio == 1.0
    是合规自检（实现未引入额外因子）。
    """
    inp = KodInput(
        vapor_mass_flow_kgs=5.0,  # 不同 W
        vapor_density_kg_m3=2.5,
        liquid_density_kg_m3=850.0,
        k_sb_m_s=0.25,
    )
    r = calc_kod(inp)
    assert r.u_actual_m_s == r.u_perm_m_s
    assert r.limit_ratio == pytest.approx(1.0, rel=1e-12)


# ============================================================================
# 4. KOD 输入校验（422）
# ============================================================================


@pytest.mark.parametrize(
    ("kwargs", "expected_substr"),
    [
        # vapor_mass_flow_kgs 必须 > 0
        ({"vapor_mass_flow_kgs": 0}, "vapor_mass_flow_kgs"),
        ({"vapor_mass_flow_kgs": -1.0}, "vapor_mass_flow_kgs"),
        # vapor_density_kg_m3 必须 > 0
        ({"vapor_density_kg_m3": 0}, "vapor_density_kg_m3"),
        ({"vapor_density_kg_m3": -0.5}, "vapor_density_kg_m3"),
        # liquid_density_kg_m3 必须 > vapor_density（无气液分离）
        ({"liquid_density_kg_m3": 1.0, "vapor_density_kg_m3": 2.0}, "liquid_density_kg_m3"),
        ({"liquid_density_kg_m3": 1.177, "vapor_density_kg_m3": 1.177}, "liquid_density_kg_m3"),
        # k_sb_m_s 必须 > 0
        ({"k_sb_m_s": 0}, "k_sb_m_s"),
        ({"k_sb_m_s": -0.1}, "k_sb_m_s"),
        # k_sb_m_s 上界 2.0
        ({"k_sb_m_s": 2.5}, "k_sb_m_s"),
    ],
)
def test_kod_input_validation(kwargs: dict, expected_substr: str) -> None:
    """KOD 输入字段越界或非正 → 422 KodSizingInputError。"""
    base_kwargs = {
        "vapor_mass_flow_kgs": 10.0,
        "vapor_density_kg_m3": 1.177,
        "liquid_density_kg_m3": 1000.0,
        "k_sb_m_s": 0.3,
    }
    base_kwargs.update(kwargs)
    with pytest.raises(KodSizingInputError) as exc_info:
        calc_kod(KodInput(**base_kwargs))
    assert exc_info.value.status == 422
    assert exc_info.value.code == "FLARE_KOD_INPUT_ERROR"
    assert expected_substr in str(exc_info.value)


# ============================================================================
# 5. Water Seal 基础工况（手算校核）
# ============================================================================


def test_water_seal_basic() -> None:
    """header=200000 Pa + pot=0 + ρ_w=1000 + g=9.81 + sf=1.5 + surge=0
    → ΔP=200000 / h_seal ≈ 20.387 m / h_design ≈ 30.580 m（手算校核）。

    手算校核（API 521 §5.15.5）：
        ΔP = (200000 + 0) − 0 = 200000 Pa
        h_seal = 200000 / (1000 × 9.81) ≈ 20.387 m
        h_design = 20.387 × 1.5 ≈ 30.580 m

    注：h_seal=20m 是异常大的工程数字（实际火炬系统 header 高压在 1–5 kPa
    gauge 量级，seal pot 在 atmospheric 下，h_seal 通常 0.5–2 m）。这里用
    200 kPa 仅为展示数学一致性。实际工程值由 Task 19/20 提供。
    """
    inp = WaterSealInput(
        header_pressure_pa=200000.0,
        seal_pot_pressure_pa=0.0,
        water_density_kg_m3=1000.0,
        gravity_m_s2=9.81,
        safety_factor=1.5,
        surge_pressure_pa=0.0,
    )
    r = calc_water_seal(inp)
    assert isinstance(r, WaterSealResult)
    assert r.delta_pressure_pa == pytest.approx(200000.0, abs=1e-6)
    assert r.h_seal_m == pytest.approx(20.387, abs=5e-3)
    assert r.h_design_m == pytest.approx(30.580, abs=5e-3)
    assert r.formula_ref == "API_521_§5.15.5"


# ============================================================================
# 6. safety_factor 比例关系（sf=1.5 vs 2.0 → h_design 比 4:3）
# ============================================================================


def test_water_seal_safety_factor_15() -> None:
    """safety_factor=1.5 vs 2.0 → h_design 比 4:3（h_seal 不变，仅 h_design 变化）。"""
    base_kwargs = {
        "header_pressure_pa": 200000.0,
        "seal_pot_pressure_pa": 0.0,
        "water_density_kg_m3": 1000.0,
        "gravity_m_s2": 9.81,
        "surge_pressure_pa": 0.0,
    }
    r_sf_15 = calc_water_seal(WaterSealInput(**base_kwargs, safety_factor=1.5))
    r_sf_20 = calc_water_seal(WaterSealInput(**base_kwargs, safety_factor=2.0))

    # h_seal 一致（仅与 ΔP、ρ_w、g 有关）
    assert r_sf_15.h_seal_m == pytest.approx(r_sf_20.h_seal_m, rel=1e-12)
    # h_design 比 sf 比 → 1.5 : 2.0 = 3 : 4
    assert r_sf_15.h_design_m == pytest.approx(r_sf_20.h_design_m * 1.5 / 2.0, rel=1e-12)
    # h_design_sf2 = h_design_sf1 × (2.0/1.5) = h_design_sf1 × 4/3
    assert r_sf_20.h_design_m == pytest.approx(r_sf_15.h_design_m * 4.0 / 3.0, rel=1e-12)


# ============================================================================
# 7. surge_pressure 影响（surge > 0 → h_seal 增大）
# ============================================================================


def test_water_seal_surge() -> None:
    """surge_pressure=50000 Pa → ΔP 增大 → h_seal 增大。

    手算校核：
        ΔP_no_surge = (200000 + 0) − 0 = 200000 Pa
        ΔP_with_surge = (200000 + 50000) − 0 = 250000 Pa
        h_seal_no_surge ≈ 20.387 m
        h_seal_with_surge = 250000 / (1000 × 9.81) ≈ 25.484 m
    """
    base_kwargs = {
        "header_pressure_pa": 200000.0,
        "seal_pot_pressure_pa": 0.0,
        "water_density_kg_m3": 1000.0,
        "gravity_m_s2": 9.81,
        "safety_factor": 1.5,
    }
    r_no_surge = calc_water_seal(WaterSealInput(**base_kwargs, surge_pressure_pa=0.0))
    r_with_surge = calc_water_seal(
        WaterSealInput(**base_kwargs, surge_pressure_pa=50000.0)
    )

    # ΔP 差 50000 Pa
    assert r_with_surge.delta_pressure_pa - r_no_surge.delta_pressure_pa == pytest.approx(
        50000.0, abs=1e-6
    )
    # h_seal 增大
    assert r_with_surge.h_seal_m > r_no_surge.h_seal_m
    delta_h = 50000 / (1000 * 9.81)
    assert r_with_surge.h_seal_m == pytest.approx(
        r_no_surge.h_seal_m + delta_h, rel=1e-9
    )
    # h_design 也增大（与 h_seal 同比例）
    assert r_with_surge.h_design_m > r_no_surge.h_design_m


# ============================================================================
# 8. Water Seal 输入校验（422）
# ============================================================================


@pytest.mark.parametrize(
    ("kwargs", "expected_substr"),
    [
        # header_pressure_pa 必须 > seal_pot_pressure_pa
        ({"header_pressure_pa": 100000.0, "seal_pot_pressure_pa": 200000.0}, "header_pressure_pa"),
        ({"header_pressure_pa": 100000.0, "seal_pot_pressure_pa": 100000.0}, "header_pressure_pa"),
        # water_density_kg_m3 必须 > 0
        ({"water_density_kg_m3": 0}, "water_density_kg_m3"),
        ({"water_density_kg_m3": -1000.0}, "water_density_kg_m3"),
        # gravity_m_s2 必须 > 0
        ({"gravity_m_s2": 0}, "gravity_m_s2"),
        ({"gravity_m_s2": -9.81}, "gravity_m_s2"),
        # safety_factor 必须 ≥ 1.0
        ({"safety_factor": 0.5}, "safety_factor"),
        ({"safety_factor": 1.0 - 1e-9}, "safety_factor"),
        # surge_pressure_pa 必须 ≥ 0
        ({"surge_pressure_pa": -1.0}, "surge_pressure_pa"),
    ],
)
def test_water_seal_input_validation(kwargs: dict, expected_substr: str) -> None:
    """Water Seal 输入字段越界或非正 → 422 WaterSealInputError。"""
    base_kwargs = {
        "header_pressure_pa": 200000.0,
        "seal_pot_pressure_pa": 0.0,
        "water_density_kg_m3": 1000.0,
        "gravity_m_s2": 9.81,
        "safety_factor": 1.5,
        "surge_pressure_pa": 0.0,
    }
    base_kwargs.update(kwargs)
    with pytest.raises(WaterSealInputError) as exc_info:
        calc_water_seal(WaterSealInput(**base_kwargs))
    assert exc_info.value.status == 422
    assert exc_info.value.code == "FLARE_WATER_SEAL_INPUT_ERROR"
    assert expected_substr in str(exc_info.value)


# ============================================================================
# 9. 综合计算 calc_kod_sizing（覆盖 schema + service 综合）
# ============================================================================


def test_kod_sizing_combined() -> None:
    """综合调用 calc_kod_sizing：返回 KodSizingResult 且含 kod + water_seal 子结果。"""
    kod_inp = KodInput(
        vapor_mass_flow_kgs=10.0,
        vapor_density_kg_m3=1.177,
        liquid_density_kg_m3=1000.0,
        k_sb_m_s=0.3,
    )
    water_inp = WaterSealInput(
        header_pressure_pa=200000.0,
        seal_pot_pressure_pa=0.0,
        safety_factor=1.5,
    )
    combined = calc_kod_sizing(kod_inp, water_inp)
    assert isinstance(combined, KodSizingResult)
    assert isinstance(combined.kod, KodResult)
    assert isinstance(combined.water_seal, WaterSealResult)
    assert combined.formula_ref == "API_521_§5.15.3+§5.15.5"
    # 子结果与单独调用一致
    assert combined.kod == calc_kod(kod_inp)
    assert combined.water_seal == calc_water_seal(water_inp)
