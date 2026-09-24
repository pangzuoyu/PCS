"""P6-3 Task 35 COST_EST cepci_adjustment 测试（§3.2.8 第二项）。

按 SPEC §3.2.8 CEPCI 调整：

    C₂ = C₁ × (CEPCI₂ / CEPCI₁)

手算独立校核：

例 1（C₁=10000 / CEPCI₁=600 / CEPCI₂=700）：

    ratio = 700/600 ≈ 1.1667
    C₂ = 10000 × 1.1667 ≈ 11666.67

例 2（CEPCI₁=CEPCI₂=600）：

    ratio = 1
    C₂ = C₁ = 10000（不变）

例 3（CEPCI₂ < CEPCI₁ → 通货膨胀 / 紧缩场景）：

    C₁=10000 / CEPCI₁=700 / CEPCI₂=600 → ratio = 0.8571
    C₂ = 10000 × 0.8571 ≈ 8571.43

例 4（CEPCI 0 越界）：

    CEPCI₁=0 → 422 CepciAdjustmentInputError

联用验证（红线 13+14）：C_target = C_base × (S/S_base)^0.6 × (CEPCI₂/CEPCI₁)
    例：C₁=10000 / S₁=10 / S₂=20 / CEPCI₁=600 / CEPCI₂=700
    → ratio_six_tenths = 2^0.6 ≈ 1.5157
    → ratio_cepci ≈ 1.1667
    → C_target ≈ 10000 × 1.5157 × 1.1667 ≈ 17682
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.cost_est import (  # noqa: E402
    CepciAdjustmentInput,
    CepciAdjustmentInputError,
    SixTenthsRuleInput,
    calc_cepci_adjustment,
    calc_six_tenths_rule,
)

# =============================================================================
# CEPCI 调整 4 单元测试
# =============================================================================


def test_cepci_basic() -> None:
    """C₁=10000 / CEPCI₁=600 / CEPCI₂=700 → C₂ ≈ 11666.67。"""
    inp = CepciAdjustmentInput(reference_cost=10000.0, reference_cepci=600.0, target_cepci=700.0)
    result = calc_cepci_adjustment(inp)
    expected_ratio = 700.0 / 600.0
    assert result.target_cost == pytest.approx(10000.0 * expected_ratio, rel=1e-9)
    assert result.cepci_ratio == pytest.approx(expected_ratio, rel=1e-9)
    assert result.formula_ref == "CEPCI_ADJUSTMENT_§3.2.8"


def test_cepci_no_change() -> None:
    """CEPCI₁=CEPCI₂ → ratio=1，C₂=C₁（不变）。"""
    inp = CepciAdjustmentInput(reference_cost=12345.0, reference_cepci=600.0, target_cepci=600.0)
    result = calc_cepci_adjustment(inp)
    assert result.target_cost == pytest.approx(12345.0, rel=1e-9)
    assert result.cepci_ratio == pytest.approx(1.0, rel=1e-9)


def test_cepci_deflation() -> None:
    """CEPCI₂ < CEPCI₁（紧缩场景）→ C₂ < C₁。"""
    inp = CepciAdjustmentInput(reference_cost=10000.0, reference_cepci=700.0, target_cepci=600.0)
    result = calc_cepci_adjustment(inp)
    # ratio = 600/700 ≈ 0.8571
    assert result.target_cost == pytest.approx(10000.0 * (600.0 / 700.0), rel=1e-9)
    assert result.target_cost < 10000.0
    assert result.cepci_ratio == pytest.approx(600.0 / 700.0, rel=1e-9)


def test_cepci_input_error() -> None:
    """CEPCI=0 / 负数 → 422 CepciAdjustmentInputError。"""
    # CEPCI₁=0
    with pytest.raises(CepciAdjustmentInputError) as exc1:
        calc_cepci_adjustment(
            CepciAdjustmentInput(reference_cost=100.0, reference_cepci=0.0, target_cepci=700.0)
        )
    assert exc1.value.status == 422
    assert exc1.value.code == "CEPCI_ADJUSTMENT_INPUT_ERROR"

    # CEPCI₂=-1.0
    with pytest.raises(CepciAdjustmentInputError) as exc2:
        calc_cepci_adjustment(
            CepciAdjustmentInput(reference_cost=100.0, reference_cepci=600.0, target_cepci=-1.0)
        )
    assert exc2.value.status == 422

    # reference_cost < 0
    with pytest.raises(CepciAdjustmentInputError) as exc3:
        calc_cepci_adjustment(
            CepciAdjustmentInput(reference_cost=-1.0, reference_cepci=600.0, target_cepci=700.0)
        )
    assert exc3.value.status == 422


def test_cepci_combined_with_six_tenths() -> None:
    """红线 13+14：CEPCI 公式与 0.6 scaling 联用。

    C_target = C_base × (S_target / S_base)^0.6 × (CEPCI₂ / CEPCI₁)
    """
    # Step 1：六法则 scale-up（C₁ 10000 / S₁=10 / S₂=20）
    six_inp = SixTenthsRuleInput(
        reference_cost=10000.0, reference_scale=10.0, target_scale=20.0
    )
    six_result = calc_six_tenths_rule(six_inp)
    assert six_result.target_cost == pytest.approx(10000.0 * (2.0 ** 0.6), rel=1e-9)

    # Step 2：CEPCI 时间调整（六法则结果 / CEPCI₁=600 / CEPCI₂=700）
    cepci_inp = CepciAdjustmentInput(
        reference_cost=six_result.target_cost,
        reference_cepci=600.0,
        target_cepci=700.0,
    )
    cepci_result = calc_cepci_adjustment(cepci_inp)
    expected = 10000.0 * (2.0 ** 0.6) * (700.0 / 600.0)
    assert cepci_result.target_cost == pytest.approx(expected, rel=1e-9)
    # 手工对照：10000 × 1.5157 × 1.1667 ≈ 17682
    assert 17600 < cepci_result.target_cost < 17800
