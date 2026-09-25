"""P6-2 Task 24 COOL_TOWER tower_curve 测试（SPEC §3.2.4.2）。

按 SPEC §3.2.4.2 P6-CT-001 + CTI ATC-105 特性曲线 KaV/L = C × (L/G)^(−m)：

- 4 单元测试（不依赖 DB；纯计算函数）：
  1. test_tower_curve_basic_cti：c=1.5, m=0.7, l_g=1.0 → kav_l=1.5；CTI 模式
  2. test_tower_curve_basic_manufacturer：c=2.0, m=0.6, l_g=1.0 → kav_l=2.0；
     MANUFACTURER 模式（厂商实测）
  3. test_tower_curve_l_g_scaling：l_g=2.0 → kav_l=c×2^(−m)
  4. test_tower_curve_input_validation：c<=0 / m<0 / l_g<=0 → TowerCurveInputError
  5. test_tower_curve_formula_ref：formula_ref == "API_CTI_ATC-105_§3.2.4.2"

测试模式参照 ``tests/services/flare/test_header_sizing.py``。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.cool_tower import (  # noqa: E402
    TowerCurveInput,
    TowerCurveInputError,
    TowerCurveResult,
    calc_tower_curve_kav_l,
)
from app.services.exceptions import PcsError  # noqa: E402

# ============================================================================
# 1. 基础 CTI 典型值
# ============================================================================


def test_tower_curve_basic_cti() -> None:
    """c=1.5, m=0.7, l_g=1.0 → kav_l = 1.5 × 1^(−0.7) = 1.5（恒等）；CTI 模式。"""
    inp = TowerCurveInput(c=1.5, m=0.7, l_g_ratio=1.0, curve_source="CTI")
    r = calc_tower_curve_kav_l(inp)
    assert isinstance(r, TowerCurveResult)
    assert r.kav_l == pytest.approx(1.5, abs=1e-12)
    assert r.curve_source == "CTI"


# ============================================================================
# 2. MANUFACTURER 厂商实测
# ============================================================================


def test_tower_curve_basic_manufacturer() -> None:
    """c=2.0, m=0.6, l_g=1.0 → kav_l = 2.0 × 1^(−0.6) = 2.0；MANUFACTURER 模式。"""
    inp = TowerCurveInput(
        c=2.0, m=0.6, l_g_ratio=1.0, curve_source="MANUFACTURER"
    )
    r = calc_tower_curve_kav_l(inp)
    assert isinstance(r, TowerCurveResult)
    assert r.kav_l == pytest.approx(2.0, abs=1e-12)
    assert r.curve_source == "MANUFACTURER"


# ============================================================================
# 3. l_g 缩放（幂律）
# ============================================================================


def test_tower_curve_l_g_scaling() -> None:
    """l_g=2.0 → kav_l = c × 2^(−m)（幂律缩放）。

    c=1.5, m=0.7, l_g=2.0 → kav_l = 1.5 × 2^(−0.7) ≈ 1.5 × 0.61557 ≈ 0.9234。
    """
    inp = TowerCurveInput(c=1.5, m=0.7, l_g_ratio=2.0)
    r = calc_tower_curve_kav_l(inp)
    expected = 1.5 * (2.0 ** (-0.7))
    assert r.kav_l == pytest.approx(expected, rel=1e-12)


# ============================================================================
# 4. 输入校验
# ============================================================================


def test_tower_curve_input_validation() -> None:
    """c <= 0 / m < 0 / l_g <= 0 → TowerCurveInputError（422）。"""
    # c <= 0
    with pytest.raises(TowerCurveInputError):
        calc_tower_curve_kav_l(TowerCurveInput(c=0.0, m=0.7, l_g_ratio=1.0))
    with pytest.raises(TowerCurveInputError):
        calc_tower_curve_kav_l(TowerCurveInput(c=-1.0, m=0.7, l_g_ratio=1.0))
    # m < 0
    with pytest.raises(TowerCurveInputError):
        calc_tower_curve_kav_l(TowerCurveInput(c=1.5, m=-0.1, l_g_ratio=1.0))
    # l_g <= 0
    with pytest.raises(TowerCurveInputError):
        calc_tower_curve_kav_l(TowerCurveInput(c=1.5, m=0.7, l_g_ratio=0.0))
    with pytest.raises(TowerCurveInputError):
        calc_tower_curve_kav_l(TowerCurveInput(c=1.5, m=0.7, l_g_ratio=-1.0))


# ============================================================================
# 5. formula_ref 溯源标记
# ============================================================================


def test_tower_curve_formula_ref() -> None:
    """formula_ref == "API_CTI_ATC-105_§3.2.4.2"（CTI ATC-105 §3.2.4.2 锁定）。"""
    inp = TowerCurveInput(c=1.5, m=0.7, l_g_ratio=1.0)
    r = calc_tower_curve_kav_l(inp)
    assert r.formula_ref == "API_CTI_ATC-105_§3.2.4.2"


# ============================================================================
# 6. PcsError 继承校验
# ============================================================================


def test_tower_curve_input_error_is_pcs_error() -> None:
    """TowerCurveInputError 是 PcsError 子类；status=422。"""
    try:
        calc_tower_curve_kav_l(TowerCurveInput(c=0.0, m=0.7, l_g_ratio=1.0))
    except TowerCurveInputError as err:
        assert isinstance(err, PcsError)
        assert err.status == 422
        assert err.code.startswith("TOWER_CURVE_")
