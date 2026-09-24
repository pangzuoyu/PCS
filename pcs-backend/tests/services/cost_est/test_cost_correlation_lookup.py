"""P6-3 Task 35 COST_EST cost_correlation_lookup 测试（§3.2.8 第三项）。

按 SPEC §3.2.8 成本关联式查 CONFIG：

    cost = a + b · S^n（6 设备类型）

手算独立校核（与 ``app/services/cost_est/cost_correlation_lookup``
内置 seed 数据严格对齐）：

例 1 TOWER（D=2.0m）：

    cost = 15000 + 25000 × 2.0^0.85 ≈ 15000 + 25000 × 1.8020 ≈ 60051

例 2 VESSEL（V=10 m³）：

    cost = 8000 + 12000 × 10^0.70 ≈ 8000 + 12000 × 5.0119 ≈ 68143

例 3 HEAT_EXCHANGER（A=100 m²）：

    cost = 5000 + 3500 × 100^0.65 ≈ 5000 + 3500 × 19.953 ≈ 74836

例 4 PUMP（Q=50 m³/h）：

    cost = 3000 + 1200 × 50^0.55 ≈ 3000 + 1200 × 9.1187 ≈ 13942

例 5 COMPRESSOR（P=500 kW）：

    cost = 25000 + 18000 × 500^0.75 ≈ 25000 + 18000 × 105.737 ≈ 1928326

例 6 PIPING（L·D=500）：

    cost = 200 + 80 × 500^0.90 ≈ 200 + 80 × 295.85 ≈ 23868

例 7 未知 equipment_type → 422

例 8 S 超出 valid_range → 422
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.cost_est import (  # noqa: E402
    CostCorrelationInput,
    CostCorrelationInputError,
    lookup_cost_correlation,
)

# =============================================================================
# 成本关联式查表 — 6 设备类型各 1 测试（valid input）+ 1 未知设备类型 + 1 范围越界
# =============================================================================


def _expected_cost(a: float, b: float, n: float, s: float) -> float:
    """手算 cost = a + b · S^n。"""
    return a + b * (s ** n)


def test_correlation_tower() -> None:
    """TOWER：D=2.0m → cost ≈ 60051。"""
    inp = CostCorrelationInput(equipment_type="TOWER", scale_parameter=2.0)
    result = lookup_cost_correlation(inp)
    expected = _expected_cost(15000.0, 25000.0, 0.85, 2.0)
    assert result.estimated_cost == pytest.approx(expected, rel=1e-9)
    assert result.equipment_type == "TOWER"
    assert result.coefficient_a == 15000.0
    assert result.coefficient_b == 25000.0
    assert result.scaling_exponent_n == 0.85
    assert result.correlation_id == "CC-TOWER-v1"
    assert result.formula_ref == "COST_CORRELATION_§3.2.8"


def test_correlation_vessel() -> None:
    """VESSEL：V=10 m³ → cost ≈ 68143。"""
    inp = CostCorrelationInput(equipment_type="VESSEL", scale_parameter=10.0)
    result = lookup_cost_correlation(inp)
    expected = _expected_cost(8000.0, 12000.0, 0.70, 10.0)
    assert result.estimated_cost == pytest.approx(expected, rel=1e-9)
    assert result.equipment_type == "VESSEL"
    assert result.scaling_exponent_n == 0.70


def test_correlation_heat_exchanger() -> None:
    """HEAT_EXCHANGER：A=100 m² → cost ≈ 74836。"""
    inp = CostCorrelationInput(equipment_type="HEAT_EXCHANGER", scale_parameter=100.0)
    result = lookup_cost_correlation(inp)
    expected = _expected_cost(5000.0, 3500.0, 0.65, 100.0)
    assert result.estimated_cost == pytest.approx(expected, rel=1e-9)
    assert result.equipment_type == "HEAT_EXCHANGER"
    assert result.scaling_exponent_n == 0.65


def test_correlation_pump() -> None:
    """PUMP：Q=50 m³/h → cost ≈ 13942。"""
    inp = CostCorrelationInput(equipment_type="PUMP", scale_parameter=50.0)
    result = lookup_cost_correlation(inp)
    expected = _expected_cost(3000.0, 1200.0, 0.55, 50.0)
    assert result.estimated_cost == pytest.approx(expected, rel=1e-9)
    assert result.equipment_type == "PUMP"
    assert result.scaling_exponent_n == 0.55


def test_correlation_compressor() -> None:
    """COMPRESSOR：P=500 kW → cost ≈ 1,928,326。"""
    inp = CostCorrelationInput(equipment_type="COMPRESSOR", scale_parameter=500.0)
    result = lookup_cost_correlation(inp)
    expected = _expected_cost(25000.0, 18000.0, 0.75, 500.0)
    assert result.estimated_cost == pytest.approx(expected, rel=1e-9)
    assert result.equipment_type == "COMPRESSOR"
    assert result.scaling_exponent_n == 0.75
    assert result.estimated_cost > 0.0


def test_correlation_piping() -> None:
    """PIPING：L·D=500 → cost ≈ 23868。"""
    inp = CostCorrelationInput(equipment_type="PIPING", scale_parameter=500.0)
    result = lookup_cost_correlation(inp)
    expected = _expected_cost(200.0, 80.0, 0.90, 500.0)
    assert result.estimated_cost == pytest.approx(expected, rel=1e-9)
    assert result.equipment_type == "PIPING"
    assert result.scaling_exponent_n == 0.90


def test_correlation_unknown_equipment() -> None:
    """未知 equipment_type → 422 CostCorrelationInputError。"""
    inp = CostCorrelationInput(equipment_type="UNKNOWN_TYPE", scale_parameter=10.0)
    with pytest.raises(CostCorrelationInputError) as exc:
        lookup_cost_correlation(inp)
    assert exc.value.status == 422
    assert exc.value.code == "COST_CORRELATION_INPUT_ERROR"
    assert "未知 equipment_type" in str(exc.value)


def test_correlation_out_of_range() -> None:
    """S 超出 valid_range → 422 CostCorrelationInputError。

    TOWER valid_range = (0.3, 8.0)；S=10.0 越界上沿。
    """
    inp = CostCorrelationInput(equipment_type="TOWER", scale_parameter=10.0)
    with pytest.raises(CostCorrelationInputError) as exc:
        lookup_cost_correlation(inp)
    assert exc.value.status == 422
    assert exc.value.code == "COST_CORRELATION_INPUT_ERROR"
    assert "有效范围" in str(exc.value)

    # scale_parameter <= 0
    with pytest.raises(CostCorrelationInputError) as exc2:
        lookup_cost_correlation(
            CostCorrelationInput(equipment_type="TOWER", scale_parameter=0.0)
        )
    assert exc2.value.status == 422
