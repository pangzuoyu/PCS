"""P6-3 Task 31 OPEN_CHANNEL jump 测试（§3.2.6 第四项）。

按 SPEC §3.2.6 Bélanger 方程 + 能量损失 + 跃型判定：

    h₂/h₁ = 0.5 × (√(1 + 8 × Fr₁²) − 1)
    ΔE = (h₂ − h₁)³ / (4 × h₁ × h₂)

跃型分类：

- Fr₁ ∈ [1.0, 1.7)：WAVY（波状）
- Fr₁ ∈ [1.7, 2.5)：WEAK（弱）
- Fr₁ ∈ [2.5, 4.5)：OSCILLATING（振荡）
- Fr₁ ∈ [4.5, 9.0)：STEADY（稳定）
- Fr₁ ≥ 9.0：STRONG（强）

手算独立校核：

例 1（h₁=0.5/v₁=5）：

    Fr₁ = 5/√(9.80665×0.5) = 5/2.215 = 2.258
    h₂ = 0.25 × (√41.79 − 1) = 0.25 × 5.464 = 1.366 m
    ΔE = (0.866)³ / (2 × 1.366) = 0.6496 / 2.732 = 0.2378 m
    Fr₁ ∈ [1.7, 2.5) → WEAK

例 2（h₁=0.5/Fr₁=5.0）：

    h₂ = 0.25 × (√201 − 1) = 0.25 × 13.178 = 3.295 m
    ΔE = (2.795)³ / 6.590 = 21.81 / 6.590 = 3.310 m
    Fr₁ ∈ [4.5, 9.0) → STEADY

例 3（h₁=0.5/Fr₁=1.5）：

    h₂ = 0.25 × (√19 − 1) = 0.25 × 3.359 = 0.8398 m
    ΔE = (0.3398)³ / 1.6796 = 0.03923 / 1.6796 = 0.02336 m
    Fr₁ ∈ [1.0, 1.7) → WAVY
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.open_channel import (  # noqa: E402
    JumpInput,
    JumpInputError,
    calc_hydraulic_jump,
)

# ============================================================================
# 1. Bélanger 方程验证（h₁=0.5/v₁=5 → h₂≈1.366）
# ============================================================================


def test_jump_basic() -> None:
    """h₁=0.5/v₁=5 → h₂=1.366 m；Fr₁=2.258；ΔE=0.2378 m；WEAK（手算）。

    手算：Fr₁ = 5/√(9.80665×0.5) = 5/2.2150 = 2.258
        h₂ = (0.5/2) × (√(1+8×2.258²) − 1)
          = 0.25 × (√41.79 − 1)
          = 0.25 × 5.464
          = 1.366 m
        ΔE = (1.366−0.5)³ / (4×0.5×1.366) = 0.6496/2.732 = 0.2378 m
        Fr₁ ∈ [1.7, 2.5) → WEAK
    """
    r = calc_hydraulic_jump(JumpInput(h1=0.5, v1=5.0))
    assert r.fr1 == pytest.approx(2.258, rel=1e-3)
    assert r.h2 == pytest.approx(1.366, rel=1e-3)
    assert r.energy_loss == pytest.approx(0.2378, rel=1e-3)
    assert r.jump_type == "WEAK"
    assert r.v2 == pytest.approx(5.0 * 0.5 / r.h2, rel=1e-9)
    assert r.formula_ref == "JUMP_§3.2.6"


# ============================================================================
# 2. 能量损失公式（Bélanger 推导）
# ============================================================================


def test_jump_energy_loss_formula() -> None:
    """ΔE = (h₂ − h₁)³ / (4 × h₁ × h₂)（公式独立验证）。"""
    r = calc_hydraulic_jump(JumpInput(h1=1.0, v1=6.0))
    delta_h = r.h2 - 1.0
    expected_de = (delta_h ** 3) / (4.0 * 1.0 * r.h2)
    assert r.energy_loss == pytest.approx(expected_de, rel=1e-9)
    # 能量损失必为正（h₂ > h₁）
    assert r.energy_loss > 0


# ============================================================================
# 3. 5 档跃型判定（boundary 1.7 / 2.5 / 4.5 / 9.0）
# ============================================================================


def test_jump_classify_wavy() -> None:
    """Fr₁=1.5 → WAVY（波状）。"""
    # v1 such that Fr1 = 1.5: v1 = 1.5 × √(g × h1)
    v1 = 1.5 * math.sqrt(9.80665 * 0.5)
    r = calc_hydraulic_jump(JumpInput(h1=0.5, v1=v1))
    assert r.jump_type == "WAVY"


def test_jump_classify_weak() -> None:
    """Fr₁=2.0 → WEAK（弱水跃）。"""
    v1 = 2.0 * math.sqrt(9.80665 * 0.5)
    r = calc_hydraulic_jump(JumpInput(h1=0.5, v1=v1))
    assert r.jump_type == "WEAK"


def test_jump_classify_oscillating() -> None:
    """Fr₁=3.0 → OSCILLATING（振荡水跃）。"""
    v1 = 3.0 * math.sqrt(9.80665 * 0.5)
    r = calc_hydraulic_jump(JumpInput(h1=0.5, v1=v1))
    assert r.jump_type == "OSCILLATING"


def test_jump_classify_steady() -> None:
    """Fr₁=5.0 → STEADY（稳定水跃）。"""
    v1 = 5.0 * math.sqrt(9.80665 * 0.5)
    r = calc_hydraulic_jump(JumpInput(h1=0.5, v1=v1))
    assert r.jump_type == "STEADY"


def test_jump_classify_strong() -> None:
    """Fr₁=10.0 → STRONG（强水跃）。"""
    v1 = 10.0 * math.sqrt(9.80665 * 0.5)
    r = calc_hydraulic_jump(JumpInput(h1=0.5, v1=v1))
    assert r.jump_type == "STRONG"


# ============================================================================
# 4. 输入校验 — Fr1<1 → JumpInputError
# ============================================================================


def test_jump_input_error_subcritical() -> None:
    """Fr₁<1（v1=1.0/h1=1.0，g=9.80665）→ JumpInputError（422）。

    v1=1.0 → Fr₁ = 1.0/√9.80665 = 0.319 < 1（缓流，无经典水跃）。
    """
    with pytest.raises(JumpInputError) as exc_info:
        calc_hydraulic_jump(JumpInput(h1=1.0, v1=1.0))
    assert "Fr1" in str(exc_info.value) or "水跃" in str(exc_info.value)


def test_jump_input_error_negative_h1() -> None:
    """h1 = -1 → JumpInputError（422）。"""
    with pytest.raises(JumpInputError) as exc_info:
        calc_hydraulic_jump(JumpInput(h1=-1.0, v1=5.0))
    assert "h1" in str(exc_info.value)
