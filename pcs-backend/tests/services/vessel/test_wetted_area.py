"""P6-4 T3 C-12 calc_wetted_area 测试（V1.2 接口冻结）。

按 SPEC §3.4.4 C-12 + WS-CA-PR-013 Rev A：
- 5 例 golden fixture（含 2:1 椭圆复现 WS-CA-PR-013 立式算例）
- 强公式 <0.1% 容差；rel_tol=1e-3
- D7 接口冻结（ADR-0040）
"""
from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from app.services.vessel.vessel_service import (
    WettedAreaInput,
    WettedAreaResult,
    _head_full_area,
    calc_wetted_area,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "golden_vessel_wetted_area.json"
)


def _load_golden_cases() -> list[dict]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["cases"]


def _case_to_input(c: dict) -> WettedAreaInput:
    return WettedAreaInput(
        D_m=c["D_m"],
        L_m=c["L_m"],
        head_type=c["head_type"],
        H_m=c["H_m"],
        n_vessels=c["n_vessels"],
    )


# ============================================================================
# 1. Golden fixture 5 例
# ============================================================================


@pytest.mark.parametrize(
    "case", _load_golden_cases(), ids=lambda c: c["id"]
)
def test_golden_wetted_area(case):
    """5 例 golden fixture：wetted / total / head / cylinder 字段 <0.1% 容差。"""
    inp = _case_to_input(case)
    result = calc_wetted_area(inp)

    exp = case["expected"]
    tol = exp["tol_pct"] / 100.0

    assert math.isclose(
        result.wetted_area_m2, exp["wetted_area_m2"], rel_tol=tol
    ), (
        f"{case['id']} wetted_area={result.wetted_area_m2:.4f} "
        f"期望 {exp['wetted_area_m2']:.4f}"
    )
    assert math.isclose(
        result.total_wetted_area_m2, exp["total_wetted_area_m2"], rel_tol=tol
    ), (
        f"{case['id']} total_wetted_area={result.total_wetted_area_m2:.4f} "
        f"期望 {exp['total_wetted_area_m2']:.4f}"
    )
    assert math.isclose(
        result.head_area_m2, exp["head_area_m2"], rel_tol=tol
    ), (
        f"{case['id']} head_area={result.head_area_m2:.4f} "
        f"期望 {exp['head_area_m2']:.4f}"
    )
    assert math.isclose(
        result.cylinder_area_m2, exp["cylinder_area_m2"], rel_tol=tol
    ), (
        f"{case['id']} cylinder_area={result.cylinder_area_m2:.4f} "
        f"期望 {exp['cylinder_area_m2']:.4f}"
    )
    # 字段分解恒等式：wetted = head + cylinder
    assert math.isclose(
        result.wetted_area_m2,
        result.head_area_m2 + result.cylinder_area_m2,
        rel_tol=1e-9,
    )


# ============================================================================
# 2. 2:1 椭圆封头面积公式（半 oblate 椭球闭式）单测
# ============================================================================


def test_2to1_elliptical_full_head_area():
    """2:1 椭圆封头完整面积 = π·D²·[1/4 + ln(2+√3)/(8√3)] ≈ 0.3451·π·D²。

    D=1.8: A = π·3.24·0.3451 ≈ 3.5121（与 WS-CA-PR-013 对账）。
    """
    expected = math.pi * 1.8**2 * (
        0.25 + math.log(2.0 + math.sqrt(3.0)) / (8.0 * math.sqrt(3.0))
    )
    actual = _head_full_area(1.8, "2:1_ELLIPTICAL")
    assert math.isclose(actual, expected, rel_tol=1e-12)
    assert math.isclose(actual, 3.5121, rel_tol=1e-3)


def test_wetted_area_H_zero():
    """H=0 应返回 wetted=0（无液相接触）。"""
    inp = WettedAreaInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=0.0
    )
    result = calc_wetted_area(inp)
    assert result.wetted_area_m2 == 0.0
    assert result.head_area_m2 == 0.0
    assert result.cylinder_area_m2 == 0.0
    # total 不变
    assert math.isclose(result.total_wetted_area_m2, 32.4711, rel_tol=1e-3)


def test_wetted_area_H_full_top_head_partial():
    """H > L（液位进入顶部封头）：top head 部分填，A_head_top > 0。"""
    # D=2, L=3, b=0.5; H=3.6 → L_liq_bottom=3.1, z_top=0.1
    inp = WettedAreaInput(
        D_m=2.0, L_m=3.0, head_type="2:1_ELLIPTICAL", H_m=3.6
    )
    result = calc_wetted_area(inp)
    assert result.head_area_m2 > 0
    # 顶部封头部分填（z_top=0.1 > 0），所以 head_area > 0
    assert result.cylinder_area_m2 > 0


# ============================================================================
# 3. 数据类契约（frozen dataclass）
# ============================================================================


def test_wetted_area_input_result_frozen_dataclasses():
    """WettedAreaInput / WettedAreaResult 字段冻结校验。"""
    in_fields = {f.name for f in fields(WettedAreaInput)}
    expected_in = {"D_m", "L_m", "head_type", "H_m", "n_vessels"}
    assert in_fields == expected_in

    out_fields = {f.name for f in fields(WettedAreaResult)}
    expected_out = {
        "wetted_area_m2",
        "total_wetted_area_m2",
        "head_area_m2",
        "cylinder_area_m2",
        "formula_ref",
    }
    assert out_fields == expected_out

    inp = WettedAreaInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=1.0
    )
    with pytest.raises(FrozenInstanceError):
        inp.D_m = 2.0  # type: ignore[misc]

    result = calc_wetted_area(inp)
    with pytest.raises(FrozenInstanceError):
        result.wetted_area_m2 = 999.0  # type: ignore[misc]


def test_wetted_area_torisph_partial_fill():
    """碟形封头部分填充（H < b）：A_head < A_full。"""
    inp_full = WettedAreaInput(
        D_m=2.0, L_m=4.5, head_type="TORISPHERICAL", H_m=0.34
    )
    inp_half = WettedAreaInput(
        D_m=2.0, L_m=4.5, head_type="TORISPHERICAL", H_m=0.17
    )
    r_full = calc_wetted_area(inp_full)
    r_half = calc_wetted_area(inp_half)
    # 碟形封头深度 0.169·D = 0.338; H=0.34 > b → 封头满
    assert r_full.head_area_m2 > r_half.head_area_m2
    # 满封头面积 = 1.20·D² = 4.8（per head），底部只算了单头
    assert r_full.head_area_m2 > 0