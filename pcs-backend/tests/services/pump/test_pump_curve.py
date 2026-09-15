"""P4-4-3 PUMP 曲线插值 单元测试（纯函数，不落库）。

覆盖：
1. 单点区间内插值（5 点曲线，Q=中间值 → 精确插值）
2. Q < 最小点 → raise
3. Q > 最大点 → raise
4. 曲线点 < 2 → raise
5. 设计点判定：Q == rated_flow_m3_s → is_rated_point=True
6. distance_from_rated_pct：手算
7. 三曲线同时插值：H / η / NPSHr 三值都对
8. 端点 Q：Q == 最小/最大点 → 区间端点插值

Golden 溯源：
- 测试 7 用例取自 fixtures/golden_pump_curve.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.pump.curve_service import (
    PumpCurve,
    PumpCurveInputError,
    PumpCurvePoint,
    interpolate_curve,
)

# ---------- 5 点曲线（任务规约一致） ----------
_CENTRIFUGAL_POINTS: tuple[PumpCurvePoint, ...] = (
    PumpCurvePoint(0.01, 35.0, 0.65, 2.0),
    PumpCurvePoint(0.02, 33.0, 0.75, 2.5),
    PumpCurvePoint(0.03, 30.0, 0.80, 3.2),
    PumpCurvePoint(0.04, 26.0, 0.78, 4.0),
    PumpCurvePoint(0.05, 21.0, 0.70, 5.0),
)


def _make_curve(
    points: tuple[PumpCurvePoint, ...] = _CENTRIFUGAL_POINTS,
    rated_flow: float = 0.03,
    rated_head: float = 30.0,
    rated_eff: float = 0.80,
) -> PumpCurve:
    return PumpCurve(
        pump_tag="P-1001",
        pump_type="CENTRIFUGAL",
        api610_type="OH2",
        speed_rpm=2950.0,
        points=points,
        rated_flow_m3_s=rated_flow,
        rated_head_m=rated_head,
        rated_efficiency=rated_eff,
    )


def _load_golden() -> dict:
    p = Path(__file__).parent / "fixtures" / "golden_pump_curve.json"
    return json.loads(p.read_text(encoding="utf-8"))


# ---------- 1. 区间内插值 ----------
def test_interp_mid_segment_linear_h():
    """Q=0.025 在 [0.02, 0.03]，H = 33 + (0.025-0.02)/(0.03-0.02)*(30-33) = 31.5。"""
    r = interpolate_curve(_make_curve(), 0.025)
    assert abs(r.head_m - 31.5) < 1e-9
    assert r.flow_m3_s == 0.025


def test_interp_second_segment_linear_h():
    """Q=0.035 在 [0.03, 0.04]，H = 30 + 0.5*(26-30) = 28.0。"""
    r = interpolate_curve(_make_curve(), 0.035)
    assert abs(r.head_m - 28.0) < 1e-9


# ---------- 2/3. Q 越界 ----------
def test_q_below_min_raises():
    with pytest.raises(PumpCurveInputError, match="越界"):
        interpolate_curve(_make_curve(), 0.005)


def test_q_above_max_raises():
    with pytest.raises(PumpCurveInputError, match="越界"):
        interpolate_curve(_make_curve(), 0.10)


# ---------- 4. 曲线点 < 2 ----------
def test_curve_with_zero_points_raises():
    curve = _make_curve(points=())
    with pytest.raises(PumpCurveInputError, match="至少 2"):
        interpolate_curve(curve, 0.03)


def test_curve_with_one_point_raises():
    curve = _make_curve(points=(_CENTRIFUGAL_POINTS[0],))
    with pytest.raises(PumpCurveInputError, match="至少 2"):
        interpolate_curve(curve, 0.01)


# ---------- 5. 设计点判定 ----------
def test_rated_flow_marked_is_rated_point():
    r = interpolate_curve(_make_curve(), 0.03)
    assert r.is_rated_point is True
    assert r.distance_from_rated_pct == 0.0
    # 三值与 rated 一致
    assert abs(r.head_m - 30.0) < 1e-9
    assert abs(r.efficiency - 0.80) < 1e-9
    assert abs(r.npshr_m - 3.2) < 1e-9


def test_off_rated_flow_not_marked_is_rated():
    r = interpolate_curve(_make_curve(), 0.025)
    assert r.is_rated_point is False


# ---------- 6. distance_from_rated_pct 手算 ----------
def test_distance_from_rated_pct_matches_formula():
    # |0.04 - 0.03| / 0.03 × 100 ≈ 33.333...
    r = interpolate_curve(_make_curve(), 0.04)
    assert abs(r.distance_from_rated_pct - (0.01 / 0.03 * 100.0)) < 1e-6


# ---------- 7. 三曲线同时插值 ----------
def test_three_curves_interp_simultaneously():
    """Q=0.035：H=28, η=0.79, NPSHr=3.6。"""
    r = interpolate_curve(_make_curve(), 0.035)
    # H: 30 + 0.5*(26-30) = 28
    assert abs(r.head_m - 28.0) < 1e-9
    # η: 0.80 + 0.5*(0.78-0.80) = 0.79
    assert abs(r.efficiency - 0.79) < 1e-9
    # NPSHr: 3.2 + 0.5*(4.0-3.2) = 3.6
    assert abs(r.npshr_m - 3.6) < 1e-9
    assert r.is_rated_point is False
    assert r.distance_from_rated_pct > 0


# ---------- 8. 端点 Q（边界） ----------
def test_q_at_min_endpoints_interps_correctly():
    r = interpolate_curve(_make_curve(), 0.01)
    assert abs(r.head_m - 35.0) < 1e-9
    assert abs(r.efficiency - 0.65) < 1e-9
    assert abs(r.npshr_m - 2.0) < 1e-9


def test_q_at_max_endpoints_interps_correctly():
    r = interpolate_curve(_make_curve(), 0.05)
    assert abs(r.head_m - 21.0) < 1e-9
    assert abs(r.efficiency - 0.70) < 1e-9
    assert abs(r.npshr_m - 5.0) < 1e-9


# ---------- Golden fixture 校验 ----------
def test_golden_fixture_queries_match_within_tolerance():
    golden = _load_golden()["centrifugal_5_points"]
    pts = tuple(
        PumpCurvePoint(
            flow_m3_s=p["flow_m3_s"],
            head_m=p["head_m"],
            efficiency=p["efficiency"],
            npshr_m=p["npshr_m"],
        )
        for p in golden["points"]
    )
    curve = _make_curve(
        points=pts,
        rated_flow=golden["rated_flow_m3_s"],
        rated_head=golden["rated_head_m"],
        rated_eff=golden["rated_efficiency"],
    )
    for q in golden["test_queries"]:
        r = interpolate_curve(curve, q["flow_m3_s"])
        assert abs(r.head_m - q["expected_head_m"]) < q["tolerance"], (
            f"Q={q['flow_m3_s']}: expected {q['expected_head_m']}, got {r.head_m}"
        )


# ---------- 额外校验：rated / speed 非法 ----------
def test_invalid_rated_flow_raises():
    with pytest.raises(PumpCurveInputError, match="rated_flow_m3_s"):
        interpolate_curve(_make_curve(rated_flow=0.0), 0.03)


def test_invalid_rated_efficiency_raises():
    with pytest.raises(PumpCurveInputError, match="rated_efficiency"):
        interpolate_curve(_make_curve(rated_eff=0.0), 0.03)


def test_invalid_speed_rpm_raises():
    curve = PumpCurve(
        pump_tag="P-1001",
        pump_type="CENTRIFUGAL",
        api610_type="OH2",
        speed_rpm=0.0,
        points=_CENTRIFUGAL_POINTS,
        rated_flow_m3_s=0.03,
        rated_head_m=30.0,
        rated_efficiency=0.80,
    )
    with pytest.raises(PumpCurveInputError, match="speed_rpm"):
        interpolate_curve(curve, 0.03)