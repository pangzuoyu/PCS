"""P6-3 Task 31 OPEN_CHANNEL critical 测试（§3.2.6 第三项）。

按 SPEC §3.2.6 临界水深 + Froude 数：

    h_c = (q² / g)^(1/3)，q = Q/b
    Fr = v / √(g × h_m)，h_m = A / b

手算独立校核：

例 1（Q=2/b=2/h=1/g=9.81）：

    h_c = (q²/g)^(1/3) = (1/9.81)^(1/3) = 0.4666 m
    v = Q/A = 1 m/s；h_m = 1
    Fr = 1/√(9.81×1) = 0.3192（Fr<1 → 缓流）

例 2（h=0.4666 ≈ h_c）：

    Fr ≈ 1.0016 → critical

例 3（h=0.2）：

    v = 5 m/s；Fr = 5/√(9.81×0.2) = 3.5702（Fr>1 → 急流）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.open_channel import (  # noqa: E402
    CriticalInputError,
    calc_critical_depth,
    calc_froude_number,
)

# ============================================================================
# 1. h_c 手算校核（Q=2/b=2/g=9.80665 → h_c≈0.4666）
# ============================================================================


def test_critical_depth_basic() -> None:
    """Q=2/b=2/g=9.80665 → h_c = (1/9.80665)^(1/3) = 0.4671 m（手算）。

    手算：q = Q/b = 1
        h_c = (q²/g)^(1/3) = (1/9.80665)^(1/3) = 0.4671 m
    """
    h_c = calc_critical_depth(2.0, 2.0)
    assert h_c == pytest.approx(0.4671, rel=1e-3)
    # 单宽流量校核
    q = 2.0 / 2.0
    assert h_c == pytest.approx((q * q / 9.80665) ** (1.0 / 3.0), abs=1e-12)


# ============================================================================
# 2. Fr<1 缓流（Q=2/b=2/h=1）
# ============================================================================


def test_critical_froude_subcritical() -> None:
    """Q=2/b=2/h=1 → Fr=0.3193（Fr<1 → subcritical）。

    手算：v = Q/A = 2/2 = 1 m/s
        h_m = 1
        Fr = 1/√(9.80665×1) = 0.3193（<1 → 缓流）
    """
    Fr, v, regime = calc_froude_number(2.0, 2.0, 1.0)
    assert Fr == pytest.approx(0.3193, rel=1e-3)
    assert v == pytest.approx(1.0, abs=1e-9)
    assert regime == "subcritical"


# ============================================================================
# 3. Fr=1 临界态（h ≈ h_c）
# ============================================================================


def test_critical_froude_critical() -> None:
    """Q=2/b=2/h=h_c → Fr ≈ 1.0（critical）。"""
    h_c = calc_critical_depth(2.0, 2.0)
    Fr, v, regime = calc_froude_number(2.0, 2.0, h_c)
    assert Fr == pytest.approx(1.0, abs=1e-3)
    assert regime == "critical"


# ============================================================================
# 4. Fr>1 急流（Q=2/b=2/h=0.2）
# ============================================================================


def test_critical_froude_supercritical() -> None:
    """Q=2/b=2/h=0.2 → Fr=3.5702（Fr>1 → supercritical）。

    手算：v = 2/(2×0.2) = 5 m/s
        h_m = 0.2
        Fr = 5/√(9.80665×0.2) = 5/1.4007 = 3.5702（>1 → 急流）
    """
    Fr, v, regime = calc_froude_number(2.0, 2.0, 0.2)
    assert Fr == pytest.approx(3.5702, rel=1e-3)
    assert v == pytest.approx(5.0, abs=1e-9)
    assert regime == "supercritical"


# ============================================================================
# 5. 输入校验 — flow_rate 非正 → CriticalInputError
# ============================================================================


def test_critical_input_error_negative_flow() -> None:
    """Q = -1 → CriticalInputError（422）。"""
    with pytest.raises(CriticalInputError) as exc_info:
        calc_critical_depth(-1.0, 2.0)
    assert "flow_rate" in str(exc_info.value)


def test_critical_input_error_zero_depth() -> None:
    """h = 0 → CriticalInputError（422）。"""
    with pytest.raises(CriticalInputError) as exc_info:
        calc_froude_number(2.0, 2.0, 0.0)
    assert "depth" in str(exc_info.value)
