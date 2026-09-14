"""P4-2-1 PipeSizingService 单元测试。

覆盖：
1. velocity 法 golden：D≈79.788 mm（容差 0.5），DN="DN80"
2. dp 法 golden：迭代收敛到 DN100
3. fluid_phase 映射：LIQUID / GAS / STEAM / TWO_PHASE 各自推荐 v；未知 phase → ValueError
4. D 边界：V 接近 0 → ValueError；v=0 → ValueError
5. DN 圆整策略：D=50.5 → DN50（不越档）；D=63.3 → DN65（越档）

Golden 溯源：HG/T 20570.6-95 表 5.1（管道推荐流速；种子
pcs-backend/app/seeds/category3_defaults.json → recommended_velocity.rows）。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services.pipe.sizing_service import (
    DNResult,
    PipeSizingConvergenceError,
    PipeSizingInputError,
    size_by_dp,
    size_by_velocity,
)

# ---------------------------------------------------------------------------
# Golden fixture 加载
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_pipe_sizing.json"
GOLDEN = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1) velocity 法 golden
# ---------------------------------------------------------------------------


def test_size_by_velocity_water_golden():
    """velocity 法 golden：V=0.01 m³/s, v=2.0 m/s, LIQUID → D≈79.788 mm / DN80。"""
    golden = GOLDEN["velocity_method_water"]
    res = size_by_velocity(
        V=golden["V_m3s"],
        fluid_phase=golden["fluid_phase"],
    )
    assert isinstance(res, DNResult)
    assert math.isclose(res.D_calc_mm, golden["D_calc_mm"], abs_tol=golden["tolerance"])
    assert res.DN == golden["DN_round"]
    assert res.method == "velocity"


def test_size_by_velocity_uses_phase_recommended_speed():
    """LIQUID 默认 v=2.0 m/s；与显式传 v_target_ms 一致。"""
    res_default = size_by_velocity(V=0.01, fluid_phase="LIQUID")
    res_explicit = size_by_velocity(V=0.01, fluid_phase="LIQUID", v_target_ms=2.0)
    assert math.isclose(res_default.D_calc_mm, res_explicit.D_calc_mm, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# 2) dp 法 golden
# ---------------------------------------------------------------------------


def test_size_by_dp_water_golden():
    """dp 法 golden：V=0.01 m³/s, dp_per_100m=30 kPa → DN100（默认水物性）。"""
    golden = GOLDEN["dp_method_water"]
    res = size_by_dp(
        V=golden["V_m3s"],
        fluid_phase=golden["fluid_phase"],
        dp_per_100m_kpa=golden["dp_per_100m_kpa"],
    )
    assert isinstance(res, DNResult)
    assert res.DN == golden["DN_round"]
    assert res.method == "dp"
    # dp_per_100m 计算值 ≤ 目标（满足）
    assert res.dp_per_100m_kpa is not None
    assert res.dp_per_100m_kpa <= golden["dp_per_100m_kpa"] + 1e-6
    # cap max_dn_mm=80 → 全 DN 都不满足 ≤ 30，抛 ConvergenceError
    with pytest.raises(PipeSizingConvergenceError):
        size_by_dp(
            V=golden["V_m3s"],
            fluid_phase=golden["fluid_phase"],
            dp_per_100m_kpa=golden["dp_per_100m_kpa"],
            max_dn_mm=80.0,
        )


# ---------------------------------------------------------------------------
# 3) fluid_phase 映射
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fluid_phase, expected_v",
    [
        ("LIQUID", GOLDEN["fluid_phase_velocity_targets"]["LIQUID"]),
        ("GAS", GOLDEN["fluid_phase_velocity_targets"]["GAS"]),
        ("STEAM", GOLDEN["fluid_phase_velocity_targets"]["STEAM"]),
        ("TWO_PHASE", GOLDEN["fluid_phase_velocity_targets"]["TWO_PHASE"]),
    ],
)
def test_size_by_velocity_fluid_phase_recommended_speed(fluid_phase, expected_v):
    """LIQUID / GAS / STEAM / TWO_PHASE 各自推荐 v（HG/T 20570.6-95 表 5.1）。"""
    res = size_by_velocity(V=0.05, fluid_phase=fluid_phase)
    # D = 1000 * sqrt(V / (0.785 * v))
    expected_D = 1000.0 * math.sqrt(0.05 / (0.785 * expected_v))
    assert math.isclose(res.D_calc_mm, expected_D, abs_tol=1e-6)
    assert res.v_target_ms == expected_v


def test_size_by_velocity_unknown_fluid_phase_raises():
    """未知 fluid_phase → raise PipeSizingInputError（业务错误）。"""
    with pytest.raises(PipeSizingInputError):
        size_by_velocity(V=0.01, fluid_phase="UNKNOWN_PHASE")


# ---------------------------------------------------------------------------
# 4) D 边界
# ---------------------------------------------------------------------------


def test_size_by_velocity_zero_V_raises():
    """V=0 → 无有效 D，raise PipeSizingInputError。"""
    with pytest.raises(PipeSizingInputError):
        size_by_velocity(V=0.0, fluid_phase="LIQUID")


def test_size_by_velocity_negative_V_raises():
    """V<0 → 物理非法，raise PipeSizingInputError。"""
    with pytest.raises(PipeSizingInputError):
        size_by_velocity(V=-0.01, fluid_phase="LIQUID")


def test_size_by_velocity_zero_v_target_raises():
    """v_target_ms=0 → 除零，raise PipeSizingInputError。"""
    with pytest.raises(PipeSizingInputError):
        size_by_velocity(V=0.01, fluid_phase="LIQUID", v_target_ms=0.0)


# ---------------------------------------------------------------------------
# 5) DN 圆整策略
# ---------------------------------------------------------------------------


def test_dn_round_no_step_at_50_5mm():
    """D=50.5 → DN50（不越档）。"""
    golden = GOLDEN["dn_rounding_boundary"]["no_step"]
    res = size_by_velocity(
        V=golden["D_calc_mm"] ** 2 * 0.785 * 2.0 / 1e6,
        fluid_phase="LIQUID",
    )
    assert res.DN == golden["DN_round"]


def test_dn_round_step_at_63_3mm():
    """D=63.3 > 50 → 升档 DN65（HG/T 20570.6 越档+安全裕度）。"""
    golden = GOLDEN["dn_rounding_boundary"]["step_one"]
    res = size_by_velocity(
        V=golden["D_calc_mm"] ** 2 * 0.785 * 2.0 / 1e6,
        fluid_phase="LIQUID",
    )
    assert res.DN == golden["DN_round"]


def test_dn_round_below_smallest_dn_raises():
    """D < DN15（15 mm） → 无合适 DN，raise PipeSizingConvergenceError。"""
    # V 极小 → D 极小
    V = 1e-8  # D ≈ 3.6 mm < DN15
    with pytest.raises(PipeSizingConvergenceError):
        size_by_velocity(V=V, fluid_phase="LIQUID")