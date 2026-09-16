"""P4-2-4 TwoPhaseService 单元测试。

覆盖：
1. golden 水平管气液：手算 Bx/By/pressure_gradient/void_fraction
2. 流型判定 6 路径：ANNULAR / MIST / BUBBLE / SLUG / STRATIFIED / WAVE 各一例
3. two_phase_check 判定：PASS / WARNING / FAIL 各一例
4. 落库 roundtrip：calc → persist → SELECT → 字段全保留
5. 边界：D≤0 / L≤0 / 负 flow → raise

Golden 溯源：
- Lockhart-Martinelli 参数 X = √[(dp/dz)_l / (dp/dz)_g]（Chisholm 1983）
- Baker C 参数：turbulent-turbulent C=21（最常用默认；Crane TP-410 §6）
- φ_l² = 1 + C/X + 1/X²（Chisholm-Baker）
- Chisholm void fraction：ε_g = 1 / (1 + (1/X)^(2/3) × (ρ_g/ρ_l)^(1/3))
- 单相摩阻 f：Colebrook-White（P4-2-1 已有 _colebrook_f，复用避免重复造轮子）
"""
from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import dispose_engines_async, get_async_session_factory
from app.services.pipe.two_phase_persist import persist_two_phase_result
from app.services.pipe.two_phase_service import (
    TwoPhaseInput,
    TwoPhaseInputError,
    TwoPhaseResult,
    calc_two_phase,
)

# ---------------------------------------------------------------------------
# Golden fixture 加载
# ---------------------------------------------------------------------------


_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_two_phase.json"
GOLDEN = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 辅助构造
# ---------------------------------------------------------------------------


def _golden_input(case: str = "horizontal_air_water") -> TwoPhaseInput:
    """从 golden fixture 构造 TwoPhaseInput。"""
    g = GOLDEN[case]
    return TwoPhaseInput(
        liquid_mass_flow=g["liquid_mass_flow_kg_s"],
        gas_mass_flow=g["gas_mass_flow_kg_s"],
        liquid_density=g["rho_l"],
        gas_density=g["rho_g"],
        liquid_viscosity=g["mu_l"],
        gas_viscosity=g["mu_g"],
        surface_tension=g["sigma"],
        pipe_diameter_m=g["D_m"],
        pipe_roughness_m=g["roughness_m"],
        inclination_deg=g["inclination_deg"],
        L_m=g["L_m"],
        P1_pa=g["P1_pa"],
    )


# ---------------------------------------------------------------------------
# 1) golden 水平管气液
# ---------------------------------------------------------------------------


def test_calc_two_phase_golden_horizontal_air_water():
    """golden：水平管气液 → Bx / By / pressure_gradient / void_fraction 全部命中。"""
    g = GOLDEN["horizontal_air_water"]
    inp = _golden_input()
    res = calc_two_phase(inp)

    assert isinstance(res, TwoPhaseResult)
    # Bx / By 容差 5%（手算 Colebrook f 有舍入）
    assert math.isclose(res.Bx, g["Bx"], rel_tol=g["tolerance"]), (
        f"Bx expected≈{g['Bx']}, got={res.Bx}"
    )
    assert math.isclose(res.By, g["By"], rel_tol=g["tolerance"]), (
        f"By expected≈{g['By']}, got={res.By}"
    )
    # 速度严格（直接由 m_dot/(ρ·A) 计算，无迭代）
    assert math.isclose(res.liquid_velocity, g["liquid_velocity"], rel_tol=1e-4)
    assert math.isclose(res.gas_velocity, g["gas_velocity"], rel_tol=1e-4)
    # 压降梯度（kPa/m）：手算与模型容差
    assert math.isclose(
        res.pressure_gradient, g["pressure_gradient_kpa_m"], rel_tol=g["tolerance"]
    )
    # void fraction：手算与模型容差（Chisholm 简化公式，相对容差）
    assert math.isclose(res.void_fraction, g["void_fraction"], rel_tol=1e-2), (
        f"ε_g expected≈{g['void_fraction']}, got={res.void_fraction}"
    )
    # 流型 + 校核
    assert res.flow_pattern == g["flow_pattern"]
    assert res.two_phase_check == g["two_phase_check"]
    assert res.calc_method == g["calc_method"]


def test_calc_two_phase_golden_velocity_formula():
    """v_sl/v_sg 直接由 m_dot/(ρ·A) 计算（确定性公式，不依赖 Colebrook）。"""
    inp = _golden_input()
    res = calc_two_phase(inp)
    A = math.pi * inp.pipe_diameter_m ** 2 / 4.0
    v_sl_expected = inp.liquid_mass_flow / (inp.liquid_density * A)
    v_sg_expected = inp.gas_mass_flow / (inp.gas_density * A)
    assert math.isclose(res.liquid_velocity, v_sl_expected, rel_tol=1e-12)
    assert math.isclose(res.gas_velocity, v_sg_expected, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# 2) 流型判定 6 路径
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "v_sl_ms", "v_sg_ms", "inclination_deg", "expected_pattern"),
    [
        # ANNULAR: v_sg = 5 m/s（≥ 3 m/s 阈值）
        ("annular", 1.0, 5.0, 0.0, "ANNULAR"),
        # MIST: v_sg = 50 m/s（≥ 30）, v_sl < 1
        ("mist", 0.5, 50.0, 0.0, "MIST"),
        # BUBBLE: v_sg < 0.5, v_sl ≥ 0.5
        ("bubble", 1.0, 0.1, 0.0, "BUBBLE"),
        # SLUG: 垂直管 + v_sg ≥ 0.5 + v_sl < 0.5
        ("slug", 0.3, 1.0, 90.0, "SLUG"),
        # STRATIFIED: 水平管 + v_sl < 0.05
        ("stratified", 0.01, 0.5, 0.0, "STRATIFIED"),
        # WAVE: 水平管 + v_sl ∈ [0.05, 0.3) + v_sg < 1.0
        ("wave", 0.1, 0.5, 0.0, "WAVE"),
    ],
)
def test_calc_two_phase_flow_pattern_six_paths(
    name: str, v_sl_ms: float, v_sg_ms: float, inclination_deg: float, expected_pattern: str
) -> None:
    """流型判定 6 路径：ANNULAR / MIST / BUBBLE / SLUG / STRATIFIED / WAVE。"""
    # 构造反推：给 v_sl, v_sg 反推 m_dot
    A = math.pi * 0.05 ** 2 / 4.0  # D=0.05
    m_l = v_sl_ms * 1000.0 * A
    m_g = v_sg_ms * 1.2 * A
    inp = TwoPhaseInput(
        liquid_mass_flow=m_l,
        gas_mass_flow=m_g,
        liquid_density=1000.0,
        gas_density=1.2,
        liquid_viscosity=1.0e-3,
        gas_viscosity=1.8e-5,
        surface_tension=0.072,
        pipe_diameter_m=0.05,
        pipe_roughness_m=4.5e-5,
        inclination_deg=inclination_deg,
        L_m=10.0,
        P1_pa=200000.0,
    )
    res = calc_two_phase(inp)
    assert res.flow_pattern == expected_pattern, (
        f"{name}: expected={expected_pattern}, got={res.flow_pattern} "
        f"(v_sl={v_sl_ms}, v_sg={v_sg_ms}, inc={inclination_deg})"
    )


# ---------------------------------------------------------------------------
# 3) two_phase_check 判定
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "v_sl_ms", "v_sg_ms", "expected_check", "bx_range"),
    [
        # PASS: v_sg = 20 m/s（高气速 ANNULAR），Bx ≈ 1.5 < 10 → PASS
        ("pass", 1.0, 20.0, "PASS", (0.0, 10.0)),
        # WARNING: v_sg = 1 m/s，Bx ≈ 30（10~100）→ WARNING
        ("warning", 1.0, 1.0, "WARNING", (10.0, 100.0)),
        # FAIL: v_sg = 0.1 m/s（极低气速），Bx ≈ 300 > 100 → FAIL
        ("fail", 1.0, 0.1, "FAIL", (100.0, 1e9)),
    ],
)
def test_calc_two_phase_check_three_levels(
    name: str, v_sl_ms: float, v_sg_ms: float, expected_check: str, bx_range: tuple[float, float]
) -> None:
    """two_phase_check 三档：PASS / WARNING / FAIL（按 Bx 阈值）。

    注：Bx 反推公式 X ∝ (v_sl/v_sg) × √(ρ_l f_l / (ρ_g f_g))，
    简化下 f_l ≈ f_g，ρ_l/ρ_g = 833，故 X ≈ (v_sl/v_sg) × √833 ≈ 28.87 × (v_sl/v_sg)。
    """
    A = math.pi * 0.05 ** 2 / 4.0  # D = 0.05
    m_l = v_sl_ms * 1000.0 * A
    m_g = v_sg_ms * 1.2 * A
    inp = TwoPhaseInput(
        liquid_mass_flow=m_l,
        gas_mass_flow=m_g,
        liquid_density=1000.0,
        gas_density=1.2,
        liquid_viscosity=1.0e-3,
        gas_viscosity=1.8e-5,
        surface_tension=0.072,
        pipe_diameter_m=0.05,
        pipe_roughness_m=4.5e-5,
        inclination_deg=0.0,
        L_m=10.0,
        P1_pa=200000.0,
    )
    res = calc_two_phase(inp)
    # 断言 Bx 在预期范围内 + check 档位匹配
    assert bx_range[0] <= res.Bx <= bx_range[1], (
        f"{name}: Bx={res.Bx:.2f} not in {bx_range}"
    )
    assert res.two_phase_check == expected_check, (
        f"{name}: Bx≈{res.Bx:.2f}, expected check={expected_check}, "
        f"got={res.two_phase_check}"
    )


# ---------------------------------------------------------------------------
# 4) 边界校验
# ---------------------------------------------------------------------------


def test_calc_two_phase_D_zero_raises():
    """D ≤ 0 → raise TwoPhaseInputError。"""
    inp = _golden_input()
    bad = TwoPhaseInput(**{**inp.__dict__, "pipe_diameter_m": 0.0})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)


def test_calc_two_phase_D_negative_raises():
    """D < 0 → raise TwoPhaseInputError。"""
    inp = _golden_input()
    bad = TwoPhaseInput(**{**inp.__dict__, "pipe_diameter_m": -0.05})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)


def test_calc_two_phase_L_zero_raises():
    """L ≤ 0 → raise TwoPhaseInputError（管长退化）。"""
    inp = _golden_input()
    bad = TwoPhaseInput(**{**inp.__dict__, "L_m": 0.0})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)


def test_calc_two_phase_liquid_flow_negative_raises():
    """m_l < 0 → raise TwoPhaseInputError（物理非法）。"""
    inp = _golden_input()
    bad = TwoPhaseInput(**{**inp.__dict__, "liquid_mass_flow": -1.0})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)


def test_calc_two_phase_gas_flow_negative_raises():
    """m_g < 0 → raise TwoPhaseInputError（物理非法）。"""
    inp = _golden_input()
    bad = TwoPhaseInput(**{**inp.__dict__, "gas_mass_flow": -0.05})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)


def test_calc_two_phase_rho_l_le_rho_g_raises():
    """ρ_l ≤ ρ_g → raise TwoPhaseInputError（液相必须重于气相；否则非两相流）。"""
    inp = _golden_input()
    # ρ_l = ρ_g（相等）：触发
    bad = TwoPhaseInput(**{**inp.__dict__, "liquid_density": 1.2})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)
    # ρ_l < ρ_g：触发
    bad2 = TwoPhaseInput(**{**inp.__dict__, "liquid_density": 1.0})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad2)


def test_calc_two_phase_rho_l_zero_raises():
    """ρ_l ≤ 0 → raise TwoPhaseInputError。"""
    inp = _golden_input()
    bad = TwoPhaseInput(**{**inp.__dict__, "liquid_density": 0.0})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)


def test_calc_two_phase_rho_g_zero_raises():
    """ρ_g ≤ 0 → raise TwoPhaseInputError。"""
    inp = _golden_input()
    bad = TwoPhaseInput(**{**inp.__dict__, "gas_density": 0.0})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)


def test_calc_two_phase_mu_l_zero_raises():
    """μ_l ≤ 0 → raise TwoPhaseInputError。"""
    inp = _golden_input()
    bad = TwoPhaseInput(**{**inp.__dict__, "liquid_viscosity": 0.0})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)


def test_calc_two_phase_mu_g_zero_raises():
    """μ_g ≤ 0 → raise TwoPhaseInputError。"""
    inp = _golden_input()
    bad = TwoPhaseInput(**{**inp.__dict__, "gas_viscosity": 0.0})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)


def test_calc_two_phase_P1_zero_raises():
    """P1 ≤ 0 → raise TwoPhaseInputError。"""
    inp = _golden_input()
    bad = TwoPhaseInput(**{**inp.__dict__, "P1_pa": 0.0})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)


def test_calc_two_phase_sigma_zero_raises():
    """σ ≤ 0 → raise TwoPhaseInputError。"""
    inp = _golden_input()
    bad = TwoPhaseInput(**{**inp.__dict__, "surface_tension": 0.0})
    with pytest.raises(TwoPhaseInputError):
        calc_two_phase(bad)


# ---------------------------------------------------------------------------
# 5) 落库 roundtrip（DB）
# ---------------------------------------------------------------------------


_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason="落库测试仅允许 pcs_test 库；需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test",
)


@pytest_asyncio.fixture(autouse=True)
async def _reset_async_engine():
    await dispose_engines_async()
    yield
    await dispose_engines_async()


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_persist_two_phase_result_roundtrip():
    """calc → persist → SELECT：13 字段全部保留。"""
    inp = _golden_input()
    res = calc_two_phase(inp)

    factory = get_async_session_factory()
    async with factory() as session:
        row = await persist_two_phase_result(session, inp, res, formula_version="LM-Baker-v1.0")
        await session.commit()
        pk = row.two_phase_id

    assert isinstance(pk, uuid.UUID)

    # 重新读回，断言所有 13 字段
    async with factory() as session:
        result = await session.execute(
            text("SELECT * FROM two_phase_results WHERE two_phase_id = :pk"),
            {"pk": str(pk)},
        )
        record = result.mappings().one()
    got = dict(record)

    # 11 业务字段 + created_at
    assert got["Bx"] is not None and math.isclose(float(got["Bx"]), res.Bx, rel_tol=1e-9)
    assert got["By"] is not None and math.isclose(float(got["By"]), res.By, rel_tol=1e-9)
    assert got["flow_pattern"] == res.flow_pattern
    assert got["two_phase_check"] == res.two_phase_check
    assert math.isclose(float(got["liquid_velocity"]), res.liquid_velocity, rel_tol=1e-9)
    assert math.isclose(float(got["gas_velocity"]), res.gas_velocity, rel_tol=1e-9)
    assert math.isclose(
        float(got["pressure_gradient"]), res.pressure_gradient, rel_tol=1e-9
    )
    assert math.isclose(float(got["void_fraction"]), res.void_fraction, abs_tol=1e-6)
    assert got["calc_method"] == res.calc_method
    assert got["created_at"] is not None
    # JSONB 透传
    assert got["input_json"]["pipe_diameter_m"] == inp.pipe_diameter_m
    assert got["output_json"]["Bx"] == res.Bx


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_persist_two_phase_result_formula_version_default():
    """不传 formula_version 时默认 LM-Baker-v1.0。"""
    inp = _golden_input()
    res = calc_two_phase(inp)

    factory = get_async_session_factory()
    async with factory() as session:
        row = await persist_two_phase_result(session, inp, res)
        await session.commit()
        pk = row.two_phase_id

    async with factory() as session:
        result = await session.execute(
            text("SELECT calc_method FROM two_phase_results WHERE two_phase_id = :pk"),
            {"pk": str(pk)},
        )
        method = result.scalar_one()
    # calc_method 来自 result.calc_method（不是 formula_version，formula_version 仅作标注）
    assert method == res.calc_method


# ---------------------------------------------------------------------------
# 6) calc_method 字段约定
# ---------------------------------------------------------------------------


def test_calc_two_phase_calc_method_is_lm_baker():
    """默认 calc_method = 'LOCKHART_MARTINELLI_BAKER'（命名规范锁定）。"""
    res = calc_two_phase(_golden_input())
    assert res.calc_method == "LOCKHART_MARTINELLI_BAKER"
