"""P6-4 T3 C-12 calc_partial_volume 测试（V1.2 接口冻结）。

按 SPEC §3.4.4 C-12 + WS-CA-PR-013 Rev A：
- 6 例 golden fixture（含 2:1 椭圆复现 WS-CA-PR-013 立式算例）
- 强公式 <0.1% 容差；rel_tol=1e-3
- D7 接口冻结（ADR-0040）：函数签名 + 行为冻结至 2027-03-25
"""
from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from app.services.vessel.vessel_service import (
    PartialVolumeInput,
    PartialVolumeResult,
    VesselInputError,
    calc_partial_volume,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "golden_vessel_partial_volume.json"
)


def _load_golden_cases() -> list[dict]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["cases"]


def _case_to_input(c: dict) -> PartialVolumeInput:
    return PartialVolumeInput(
        D_m=c["D_m"],
        L_m=c["L_m"],
        head_type=c["head_type"],
        H_m=c["H_m"],
        n_vessels=c["n_vessels"],
    )


# ============================================================================
# 1. Golden fixture 6 例（强公式 <0.1% 容差）
# ============================================================================


@pytest.mark.parametrize(
    "case", _load_golden_cases(), ids=lambda c: c["id"]
)
def test_golden_partial_volume(case):
    """6 例 golden fixture：partial / total / head / cylinder 字段全字段 <0.1% 容差。"""
    inp = _case_to_input(case)
    result = calc_partial_volume(inp)

    exp = case["expected"]
    tol = exp["tol_pct"] / 100.0  # 0.001

    assert math.isclose(
        result.partial_volume_m3, exp["partial_volume_m3"], rel_tol=tol
    ), (
        f"{case['id']} partial_volume={result.partial_volume_m3:.4f} "
        f"期望 {exp['partial_volume_m3']:.4f}"
    )
    assert math.isclose(
        result.total_volume_m3, exp["total_volume_m3"], rel_tol=tol
    ), (
        f"{case['id']} total_volume={result.total_volume_m3:.4f} "
        f"期望 {exp['total_volume_m3']:.4f}"
    )
    assert math.isclose(
        result.head_volume_m3, exp["head_volume_m3"], rel_tol=tol
    ), (
        f"{case['id']} head_volume={result.head_volume_m3:.4f} "
        f"期望 {exp['head_volume_m3']:.4f}"
    )
    assert math.isclose(
        result.cylinder_volume_m3, exp["cylinder_volume_m3"], rel_tol=tol
    ), (
        f"{case['id']} cylinder_volume={result.cylinder_volume_m3:.4f} "
        f"期望 {exp['cylinder_volume_m3']:.4f}"
    )
    # 字段分解恒等式：partial = head + cylinder
    assert math.isclose(
        result.partial_volume_m3,
        result.head_volume_m3 + result.cylinder_volume_m3,
        rel_tol=1e-9,
    ), f"{case['id']} partial ≠ head + cylinder"


# ============================================================================
# 2. H=0/H=D 边界 + H < D/4 部分填充
# ============================================================================


def test_partial_volume_H_zero():
    """H=0 应返回 partial=0（无液相）。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=0.0
    )
    result = calc_partial_volume(inp)
    assert result.partial_volume_m3 == 0.0
    assert result.head_volume_m3 == 0.0
    assert result.cylinder_volume_m3 == 0.0
    # total 不变（容器几何不变）
    assert math.isclose(result.total_volume_m3, 12.9779, rel_tol=1e-3)


def test_partial_volume_H_full():
    """H=L+2b 满罐应 partial=total（顶部封头也填满）。"""
    # D=1.8, L=4.5, 2:1 ellipse b=D/4=0.45; H=L+2b=4.5+0.9=5.4
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=5.4
    )
    result = calc_partial_volume(inp)
    assert math.isclose(
        result.partial_volume_m3, result.total_volume_m3, rel_tol=1e-9
    )


def test_partial_volume_2to1_partial_head_fill():
    """2:1 椭圆封头部分填充（H = b/2）：V_partial_head = π·Z·(3D² - 16Z²)/12。"""
    # D=2, b=D/4=0.5; Z=0.25 (half of b)
    # V = π·0.25·(3·4 - 16·0.0625)/12 = π·0.25·(12 - 1)/12 = π·2.75/12
    # ≈ π·0.22917 ≈ 0.7199
    inp = PartialVolumeInput(
        D_m=2.0, L_m=3.0, head_type="2:1_ELLIPTICAL", H_m=0.25
    )
    result = calc_partial_volume(inp)
    expected = math.pi * 0.25 * (3.0 * 4.0 - 16.0 * 0.0625) / 12.0
    assert math.isclose(
        result.head_volume_m3, expected, rel_tol=1e-9
    ), f"Z=0.25 2:1 椭圆 V_head={result.head_volume_m3:.6f} 期望 {expected:.6f}"


# ============================================================================
# 3. n_vessels 缩放（partial 单容器，调用方按 total × n 计算）
# ============================================================================


def test_partial_volume_n_vessels_scales_total():
    """n_vessels 缩放：partial 单容器值不变（spec 设计：n_vessels 留给 API 层做 total × n）。"""
    inp_single = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=0.9, n_vessels=1
    )
    inp_quad = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=0.9, n_vessels=4
    )
    r_single = calc_partial_volume(inp_single)
    r_quad = calc_partial_volume(inp_quad)
    # 单容器 partial/total 相同（V1.2 接口冻结约定：partial 按单容器）
    assert math.isclose(
        r_single.partial_volume_m3, r_quad.partial_volume_m3, rel_tol=1e-9
    )
    assert math.isclose(
        r_single.total_volume_m3, r_quad.total_volume_m3, rel_tol=1e-9
    )


def test_partial_volume_invalid_D_raises():
    """D_m ≤ 0 应抛 VesselInputError。"""
    with pytest.raises(VesselInputError):
        calc_partial_volume(
            PartialVolumeInput(
                D_m=0.0, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=1.0
            )
        )


def test_partial_volume_invalid_n_vessels_raises():
    """n_vessels < 1 应抛 VesselInputError。"""
    with pytest.raises(VesselInputError):
        calc_partial_volume(
            PartialVolumeInput(
                D_m=1.8,
                L_m=4.5,
                head_type="2:1_ELLIPTICAL",
                H_m=1.0,
                n_vessels=0,
            )
        )


# ============================================================================
# 4. 数据类契约（frozen dataclass，D7 接口冻结）
# ============================================================================


def test_partial_volume_input_result_frozen_dataclasses():
    """PartialVolumeInput / PartialVolumeResult 必须是 frozen dataclass。

    ADR-0040 V1.2 §F2.1: 8 字段（5 必填 + H1_m/H2_m/H3_m Optional[float] = None
    预留 + n_vessels=1）。
    H1/H2/H3 是预留字段，当前实现忽略；forward-compat 多段语义待 ADR-0041 扩展。
    """
    pv_in_fields = {f.name for f in fields(PartialVolumeInput)}
    # ADR-0041 v7 F2.1（2026-09-25 冻结契约修订）：+1 Optional vessel_shape
    expected_in = {
        "D_m", "L_m", "head_type", "H_m", "n_vessels",
        "H1_m", "H2_m", "H3_m",
        "vessel_shape",
    }
    assert pv_in_fields == expected_in, (
        f"PartialVolumeInput 字段不匹配。缺失: {expected_in - pv_in_fields}，"
        f"多余: {pv_in_fields - expected_in}"
    )

    pv_out_fields = {f.name for f in fields(PartialVolumeResult)}
    # ADR-0041 v7 F3（2026-09-25 冻结契约修订）：+1 vessel_shape_used
    expected_out = {
        "partial_volume_m3",
        "total_volume_m3",
        "head_volume_m3",
        "cylinder_volume_m3",
        "formula_ref",
        "vessel_shape_used",
    }
    assert pv_out_fields == expected_out, (
        f"PartialVolumeResult 字段不匹配。缺失: {expected_out - pv_out_fields}，"
        f"多余: {pv_out_fields - expected_out}"
    )

    # 不可变验证
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=1.0
    )
    with pytest.raises(FrozenInstanceError):
        inp.D_m = 2.0  # type: ignore[misc]

    result = calc_partial_volume(inp)
    with pytest.raises(FrozenInstanceError):
        result.partial_volume_m3 = 999.0  # type: ignore[misc]


def test_partial_volume_head_type_literal_torispherical():
    """V1.2 拼写修正：TORISPHERICAL（不是 TORISPHERIAL）。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="TORISPHERICAL", H_m=0.4
    )
    result = calc_partial_volume(inp)
    # 碟形封头深度 0.169·D = 0.3042; H=0.4 > b → 封头满 + 圆柱 0.096
    assert result.head_volume_m3 > 0
    assert result.cylinder_volume_m3 > 0
    # 验证拼写拒绝旧名
    with pytest.raises(VesselInputError):
        calc_partial_volume(
            PartialVolumeInput(
                D_m=1.8,
                L_m=4.5,
                head_type="TORISPHERIAL",  # type: ignore[arg-type]
                H_m=0.5,
            )
        )