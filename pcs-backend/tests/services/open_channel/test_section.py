"""P6-3 Task 31 OPEN_CHANNEL section 测试（§3.2.6 第二项）。

按 SPEC §3.2.6 最优水力断面：

- 矩形 b/h = 2，R = h/2
- 梯形 b/h = 2(√(1+m²) − m)，R = h/2
- 圆形二分法反解

手算独立校核：

例 1（RECT Q=2/n=0.013/S=0.001）：

    k = Q × n / √S = 2 × 0.013 / 0.031623 = 0.8220
    h^(8/3) = k / 2^(1/3) = 0.6524
    h = 0.6524^(3/8) = 0.8522 m
    b = 2h = 1.7044 m

例 2（TRAP Q=2/n=0.013/S=0.001/m=1）：

    h^(8/3) = k × 2^(2/3) / (2√2 − 1) = 0.7136
    h = 0.8811 m
    b = 2h(√2 − 1) = 0.7300 m
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.open_channel import (  # noqa: E402
    SectionInput,
    SectionInputError,
    calc_optimal_section,
)

# ============================================================================
# 1. RECT 最优断面（Q=2/n=0.013/S=0.001 → h≈0.8522, b≈1.7044）
# ============================================================================


def test_section_rect_optimal() -> None:
    """RECT Q=2/n=0.013/S=0.001 → h=0.8522, b=1.7044（手算）。

    手算：k = Q×n/√S = 0.8220
        h^(8/3) = k / 2^(1/3) = 0.6524
        h = 0.6524^(3/8) = 0.8522 m
        b = 2h = 1.7044 m
        R = h/2 = 0.4261（最优断面特征）
        Q_check ≈ 2.000（反算流量）
    """
    r = calc_optimal_section(
        SectionInput(
            channel_type="RECT",
            flow_rate=2.0,
            slope=0.001,
            manning_n=0.013,
        )
    )
    assert r.depth == pytest.approx(0.8522, rel=1e-3)
    assert r.bottom_width == pytest.approx(1.7044, rel=1e-3)
    # b/h = 2 最优断面特征
    assert r.bottom_width == pytest.approx(2 * r.depth, rel=1e-9)
    # R = h/2
    assert r.hydraulic_radius == pytest.approx(r.depth / 2, rel=1e-9)
    # Q_check ≈ flow_rate
    assert r.flow_rate_check == pytest.approx(2.0, rel=1e-3)
    assert r.formula_ref == "SECTION_§3.2.6"
    assert r.diameter is None


# ============================================================================
# 2. TRAP 最优断面（Q=2/n=0.013/S=0.001/m=1 → h≈0.8811, b≈0.7300）
# ============================================================================


def test_section_trap_optimal() -> None:
    """TRAP Q=2/n=0.013/S=0.001/m=1 → h=0.8811, b=0.7300（手算）。

    手算：h^(8/3) = k × 2^(2/3) / (2√2 − 1) = 0.7136
        h = 0.8811 m
        b = 2h(√2 − 1) = 0.7300 m
        R = h/2 = 0.4406（最优断面特征）
    """
    r = calc_optimal_section(
        SectionInput(
            channel_type="TRAP",
            flow_rate=2.0,
            slope=0.001,
            manning_n=0.013,
            side_slope=1.0,
        )
    )
    assert r.depth == pytest.approx(0.8811, rel=1e-3)
    assert r.bottom_width == pytest.approx(0.7300, rel=1e-3)
    # R = h/2
    assert r.hydraulic_radius == pytest.approx(r.depth / 2, rel=1e-9)
    # Q_check ≈ flow_rate
    assert r.flow_rate_check == pytest.approx(2.0, rel=1e-3)
    assert r.formula_ref == "SECTION_§3.2.6"


# ============================================================================
# 3. CIRC 最优断面（二分法反解 → h ∈ (0, d]）
# ============================================================================


def test_section_circ_optimal() -> None:
    """CIRC Q=0.2/n=0.013/S=0.001/d=1.0 → 二分法反解 h（h ≤ d）。

    Q=0.2 < Q_full（满流 ≈ 0.478），故二分法有解。
    """
    r = calc_optimal_section(
        SectionInput(
            channel_type="CIRC",
            flow_rate=0.2,
            slope=0.001,
            manning_n=0.013,
            diameter=1.0,
        )
    )
    # h 必须 ≤ d
    assert 0 < r.depth <= r.diameter
    # R > 0
    assert r.hydraulic_radius > 0
    # Q_check 应 ≈ flow_rate
    assert r.flow_rate_check == pytest.approx(0.2, rel=1e-3)
    assert r.bottom_width is None
    assert r.diameter == 1.0
    assert r.formula_ref == "SECTION_§3.2.6"


# ============================================================================
# 4. 输入校验 — TRAP 缺 side_slope → SectionInputError
# ============================================================================


def test_section_input_error_trap_no_side_slope() -> None:
    """TRAP 缺 side_slope → SectionInputError（422）。"""
    with pytest.raises(SectionInputError) as exc_info:
        calc_optimal_section(
            SectionInput(
                channel_type="TRAP",
                flow_rate=2.0,
                slope=0.001,
                manning_n=0.013,
                side_slope=None,
            )
        )
    assert "side_slope" in str(exc_info.value)


def test_section_input_error_circ_no_diameter() -> None:
    """CIRC 缺 diameter → SectionInputError（422）。"""
    with pytest.raises(SectionInputError) as exc_info:
        calc_optimal_section(
            SectionInput(
                channel_type="CIRC",
                flow_rate=1.0,
                slope=0.001,
                manning_n=0.013,
                diameter=None,
            )
        )
    assert "diameter" in str(exc_info.value)


def test_section_input_error_negative_flow() -> None:
    """flow_rate = -1 → SectionInputError（422）。"""
    with pytest.raises(SectionInputError) as exc_info:
        calc_optimal_section(
            SectionInput(
                channel_type="RECT",
                flow_rate=-1.0,
                slope=0.001,
                manning_n=0.013,
            )
        )
    assert "flow_rate" in str(exc_info.value)
