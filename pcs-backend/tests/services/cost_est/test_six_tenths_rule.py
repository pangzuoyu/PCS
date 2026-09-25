"""P6-3 Task 35 COST_EST sixty_tenths_rule 测试（§3.2.8 第一项）。

按 SPEC §3.2.8 六十法则：

    C₂ = C₁ × (S₂ / S₁)^n，n 默认 0.6

手算独立校核：

例 1（C₁=10000 / S₁=1 / S₂=2 / n=0.6）：

    ratio = 2
    C₂ = 10000 × 2^0.6 ≈ 10000 × 1.5157 ≈ 15157

例 2（C₁=10000 / S₁=1 / S₂=2 / n=0.55）：

    C₂ = 10000 × 2^0.55 ≈ 10000 × 1.4648 ≈ 14648

例 3（S₁=S₂=1）：

    ratio = 1；C₂ = C₁ = 10000（不变）

例 4（C₁=100000 / S₁=10 / S₂=100 / n=0.6）：

    ratio = 10
    C₂ = 100000 × 10^0.6 ≈ 100000 × 3.9811 ≈ 398107

4 例手算与公式直接计算偏差 < 5%（教科书 2^0.6 = 1.5157 精确值）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.cost_est import (  # noqa: E402
    SixTenthsRuleInput,
    SixTenthsRuleInputError,
    calc_six_tenths_rule,
)

# =============================================================================
# 手算独立校核（示例）
# =============================================================================


def _approx_equal(actual: float, expected: float, rel: float = 0.05) -> bool:
    """相对误差小于 ``rel``（默认 5%）视为通过。"""
    if expected == 0.0:
        return abs(actual) < 1e-12
    return abs(actual - expected) / abs(expected) < rel


# =============================================================================
# 六法则 4 单元测试
# =============================================================================


def test_six_tenths_basic() -> None:
    """教科书例：C₁=10000 / S₁=1 / S₂=2 → C₂ ≈ 15157（偏差 < 5%）。"""
    inp = SixTenthsRuleInput(reference_cost=10000.0, reference_scale=1.0, target_scale=2.0)
    result = calc_six_tenths_rule(inp)
    # 2^0.6 ≈ 1.5157166...
    assert _approx_equal(result.target_cost, 10000.0 * (2.0 ** 0.6), rel=0.005)
    assert result.scaling_exponent == 0.6
    assert _approx_equal(result.ratio, 2.0, rel=1e-9)
    assert result.formula_ref == "SIX_TENTHS_RULE_§3.2.8"


def test_six_tenths_custom_exponent() -> None:
    """自定义指数 n=0.55（适用特定设备如泵 / 压缩机）。"""
    inp = SixTenthsRuleInput(reference_cost=10000.0, reference_scale=1.0, target_scale=2.0)
    result = calc_six_tenths_rule(inp, scaling_exponent=0.55)
    # 2^0.55 ≈ 1.4648...
    assert _approx_equal(result.target_cost, 10000.0 * (2.0 ** 0.55), rel=0.005)
    assert result.scaling_exponent == 0.55


def test_six_tenths_same_scale() -> None:
    """S₁ = S₂ 时 ratio = 1，C₂ = C₁（不变）。"""
    inp = SixTenthsRuleInput(reference_cost=42000.0, reference_scale=5.0, target_scale=5.0)
    result = calc_six_tenths_rule(inp)
    assert result.target_cost == pytest.approx(42000.0, rel=1e-9)
    assert result.ratio == pytest.approx(1.0, rel=1e-9)


def test_six_tenths_input_error() -> None:
    """S₁=0 / S₂=0 / n=2.0 等异常输入 → 422 SixTenthsRuleInputError。"""
    # S₁=0
    with pytest.raises(SixTenthsRuleInputError) as exc1:
        calc_six_tenths_rule(
            SixTenthsRuleInput(reference_cost=100.0, reference_scale=0.0, target_scale=1.0)
        )
    assert exc1.value.status == 422
    assert exc1.value.code == "SIX_TENTHS_RULE_INPUT_ERROR"

    # S₂=0
    with pytest.raises(SixTenthsRuleInputError) as exc2:
        calc_six_tenths_rule(
            SixTenthsRuleInput(reference_cost=100.0, reference_scale=1.0, target_scale=0.0)
        )
    assert exc2.value.status == 422

    # scaling_exponent=2.0 越界
    with pytest.raises(SixTenthsRuleInputError) as exc3:
        calc_six_tenths_rule(
            SixTenthsRuleInput(reference_cost=100.0, reference_scale=1.0, target_scale=2.0),
            scaling_exponent=2.0,
        )
    assert exc3.value.status == 422

    # reference_cost 负数
    with pytest.raises(SixTenthsRuleInputError) as exc4:
        calc_six_tenths_rule(
            SixTenthsRuleInput(reference_cost=-1.0, reference_scale=1.0, target_scale=2.0)
        )
    assert exc4.value.status == 422
