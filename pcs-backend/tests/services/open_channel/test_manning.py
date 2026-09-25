"""P6-3 Task 31 OPEN_CHANNEL manning 测试（§3.2.6 第一项）。

按 SPEC §3.2.6 Manning 公式：

    Q = (1/n) × A × R^(2/3) × √S

手算独立校核（3 例，体现本模块 docstring）：

例 1（RECT b=2/h=1/n=0.013/S=0.001）：

    A = 2 m²；P = 4 m；R = 0.5 m
    Q = (1/0.013) × 2 × 0.5^(2/3) × √0.001
      = 76.9231 × 2 × 0.6299605 × 0.0316228
      = 3.0649 m³/s

例 2（TRAP b=1/m=1/h=1/n=0.025/S=0.002）：

    A = (1+1)×1 = 2 m²；P = 1 + 2×1×√2 = 3.8284 m
    R = 0.5224 m；R^(2/3) = 0.6484
    Q = (1/0.025) × 2 × 0.6484 × √0.002
      = 40 × 2 × 0.6484 × 0.044721
      = 2.320 m³/s

例 3（CIRC d=2/h=1/n=0.013/S=0.001，半充满）：

    θ = 2 × arccos(0) = π rad
    A = (4/4) × (π − sin π)/2 = π/2 ≈ 1.5708 m²
    P = 2 × π ≈ 6.2832 m；R = 0.25 m；R^(2/3) = 0.39685
    Q = (1/0.013) × 1.5708 × 0.39685 × √0.001
      = 76.9231 × 1.5708 × 0.39685 × 0.0316228
      = 1.516 m³/s

3 例手算与公式直接计算偏差 = 0%（公式自洽）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.open_channel import (  # noqa: E402
    ManningInput,
    ManningInputError,
    calc_manning_flow,
)

# ============================================================================
# 1. RECT 手算校核（b=2/h=1/n=0.013/S=0.001 → Q ≈ 3.0649）
# ============================================================================


def test_manning_rect_basic() -> None:
    """RECT b=2/h=1/n=0.013/S=0.001 → Q = 3.0649 m³/s（手算）。

    手算：A = 2 m²；P = 4 m；R = 0.5 m
        Q = (1/0.013) × 2 × 0.5^(2/3) × √0.001
          = 76.9231 × 2 × 0.6299605 × 0.0316228
          = 3.0649 m³/s
    """
    r = calc_manning_flow(
        ManningInput(
            channel_type="RECT",
            bottom_width=2.0,
            side_slope=None,
            diameter=None,
            depth=1.0,
            manning_n=0.013,
            slope=0.001,
        )
    )
    assert r.flow_rate == pytest.approx(3.0649, rel=1e-3)
    assert r.area == pytest.approx(2.0, abs=1e-9)
    assert r.wetted_perimeter == pytest.approx(4.0, abs=1e-9)
    assert r.hydraulic_radius == pytest.approx(0.5, abs=1e-9)
    assert r.formula_ref == "MANNING_§3.2.6"


# ============================================================================
# 2. TRAP 手算校核（b=1/m=1/h=1/n=0.025/S=0.002 → Q ≈ 2.320）
# ============================================================================


def test_manning_trap_basic() -> None:
    """TRAP b=1/m=1/h=1/n=0.025/S=0.002 → Q = 2.320 m³/s（手算）。

    手算：A = (1+1)×1 = 2 m²；P = 1 + 2×1×√2 = 3.8284 m
        R = 0.5224 m；R^(2/3) = 0.6484
        Q = (1/0.025) × 2 × 0.6484 × √0.002
          = 40 × 2 × 0.6484 × 0.044721
          = 2.320 m³/s
    """
    r = calc_manning_flow(
        ManningInput(
            channel_type="TRAP",
            bottom_width=1.0,
            side_slope=1.0,
            diameter=None,
            depth=1.0,
            manning_n=0.025,
            slope=0.002,
        )
    )
    assert r.flow_rate == pytest.approx(2.320, rel=1e-3)
    assert r.area == pytest.approx(2.0, abs=1e-9)
    assert r.wetted_perimeter == pytest.approx(1.0 + 2 * 1.41421356, abs=1e-6)
    assert r.formula_ref == "MANNING_§3.2.6"


# ============================================================================
# 3. CIRC 手算校核（d=2/h=1/n=0.013/S=0.001，半充满 → Q ≈ 1.516）
# ============================================================================


def test_manning_circ_half_full() -> None:
    """CIRC d=2/h=1/n=0.013/S=0.001（半充满）→ Q = 1.516 m³/s（手算）。

    手算：θ = 2 arccos(0) = π；A = π/2 ≈ 1.5708 m²
        P = 2π ≈ 6.2832 m；R = 0.25 m
        Q = (1/0.013) × 1.5708 × 0.25^(2/3) × √0.001
          = 76.9231 × 1.5708 × 0.39685 × 0.0316228
          = 1.516 m³/s
    """
    r = calc_manning_flow(
        ManningInput(
            channel_type="CIRC",
            bottom_width=0.0,
            side_slope=None,
            diameter=2.0,
            depth=1.0,
            manning_n=0.013,
            slope=0.001,
        )
    )
    assert r.flow_rate == pytest.approx(1.516, rel=1e-3)
    assert r.area == pytest.approx(1.5707963, rel=1e-4)
    assert r.wetted_perimeter == pytest.approx(6.2831853, rel=1e-4)
    assert r.hydraulic_radius == pytest.approx(0.25, abs=1e-9)


# ============================================================================
# 4. 输入校验 — manning_n=-1 → ManningInputError
# ============================================================================


def test_manning_input_error_n_negative() -> None:
    """manning_n = -1 → ManningInputError（422）。"""
    with pytest.raises(ManningInputError) as exc_info:
        calc_manning_flow(
            ManningInput(
                channel_type="RECT",
                bottom_width=2.0,
                side_slope=None,
                diameter=None,
                depth=1.0,
                manning_n=-1.0,
                slope=0.001,
            )
        )
    assert "manning_n" in str(exc_info.value)


def test_manning_input_error_slope_zero() -> None:
    """slope = 0 → ManningInputError（422）。"""
    with pytest.raises(ManningInputError) as exc_info:
        calc_manning_flow(
            ManningInput(
                channel_type="RECT",
                bottom_width=2.0,
                side_slope=None,
                diameter=None,
                depth=1.0,
                manning_n=0.013,
                slope=0.0,
            )
        )
    assert "slope" in str(exc_info.value)


def test_manning_input_error_trap_no_side_slope() -> None:
    """TRAP 缺 side_slope → ManningInputError（422）。"""
    with pytest.raises(ManningInputError) as exc_info:
        calc_manning_flow(
            ManningInput(
                channel_type="TRAP",
                bottom_width=1.0,
                side_slope=None,
                diameter=None,
                depth=1.0,
                manning_n=0.025,
                slope=0.002,
            )
        )
    assert "TRAP" in str(exc_info.value) or "side_slope" in str(exc_info.value)


# ============================================================================
# 5. velocity 必为正
# ============================================================================


def test_manning_velocity_positive() -> None:
    """任意合法输入 → v > 0。"""
    r = calc_manning_flow(
        ManningInput(
            channel_type="RECT",
            bottom_width=2.0,
            side_slope=None,
            diameter=None,
            depth=1.0,
            manning_n=0.013,
            slope=0.001,
        )
    )
    assert r.velocity > 0
    assert r.velocity == pytest.approx(r.flow_rate / r.area, rel=1e-9)


# ============================================================================
# 6. P = b + 2h 矩形断面湿周校核
# ============================================================================


def test_manning_perimeter_check_rect() -> None:
    """RECT b=2/h=1 → P = 4 m（湿周校核）。"""
    r = calc_manning_flow(
        ManningInput(
            channel_type="RECT",
            bottom_width=2.0,
            side_slope=None,
            diameter=None,
            depth=1.0,
            manning_n=0.013,
            slope=0.001,
        )
    )
    assert r.wetted_perimeter == pytest.approx(4.0, abs=1e-9)
