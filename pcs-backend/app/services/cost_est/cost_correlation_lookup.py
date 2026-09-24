"""成本关联式查 CONFIG（SPEC §3.2.8 第三项）。

设备类型 → ``cost = a + b · S^n`` 关联式（成本关联式库）：

- 塔器（``TOWER``）：``cost = a + b · (D)^n``，``D`` 直径（m）。
- 容器（``VESSEL``）：``cost = a + b · (V)^n``，``V`` 容积（m³）。
- 换热器（``HEAT_EXCHANGER``）：``cost = a + b · (A)^n``，``A`` 换热面积（m²）。
- 泵（``PUMP``）：``cost = a + b · (Q)^n``，``Q`` 流量（m³/h）。
- 压缩机（``COMPRESSOR``）：``cost = a + b · (P)^n``，``P`` 功率（kW）。
- 管路（``PIPING``）：``cost = a + b · (L·D)^n``，``L`` 长度（m），
  ``D`` 直径（mm）。

关联式数据来源：``cost_correlations`` CONFIG 表（G-数据，Task 35 落地）。

CEPT-V1.0 §3.2.8 — 成本关联式为参考级估算，偏差 ±30% 内；
仅作为投资预算阶段工具，不替代厂商报价。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.exceptions import PcsError


@dataclass(frozen=True)
class CostCorrelationInput:
    """成本关联式输入参数（frozen dataclass）。"""

    equipment_type: str  # TOWER / VESSEL / HEAT_EXCHANGER / PUMP / COMPRESSOR / PIPING
    scale_parameter: float  # S（直径/容积/面积/流量/功率/长度×直径）


@dataclass(frozen=True)
class CostCorrelationResult:
    """成本关联式计算结果（frozen dataclass）。"""

    estimated_cost: float  # cost（基准货币）
    correlation_id: str  # 关联式 ID
    equipment_type: str
    scale_parameter: float
    coefficient_a: float
    coefficient_b: float
    scaling_exponent_n: float
    formula_ref: str = "COST_CORRELATION_§3.2.8"


class CostCorrelationInputError(PcsError):
    """成本关联式输入不合法（422）。"""

    code = "COST_CORRELATION_INPUT_ERROR"
    status = 422


# === CONFIG 关联式 seed 数据（≥6 设备类型，落地到 cost_correlations 表）===
#
# 计算层（lookup_cost_correlation）内置兜底，与 CONFIG 表对齐；CONFIG 表
# 入口数据落在 Task 36 cost_est_persist_service 内进行 DB 读取（本任务
# 只交付计算 + ORM + seed）。
_COST_CORRELATIONS: dict[str, dict[str, object]] = {
    "TOWER": {
        "a": 15000.0, "b": 25000.0, "n": 0.85,
        "unit": "D(m)", "valid_range": (0.3, 8.0),
    },
    "VESSEL": {
        "a": 8000.0, "b": 12000.0, "n": 0.70,
        "unit": "V(m³)", "valid_range": (0.1, 200.0),
    },
    "HEAT_EXCHANGER": {
        "a": 5000.0, "b": 3500.0, "n": 0.65,
        "unit": "A(m²)", "valid_range": (1.0, 2000.0),
    },
    "PUMP": {
        "a": 3000.0, "b": 1200.0, "n": 0.55,
        "unit": "Q(m³/h)", "valid_range": (0.5, 5000.0),
    },
    "COMPRESSOR": {
        "a": 25000.0, "b": 18000.0, "n": 0.75,
        "unit": "P(kW)", "valid_range": (5.0, 20000.0),
    },
    "PIPING": {
        "a": 200.0, "b": 80.0, "n": 0.90,
        "unit": "L·D", "valid_range": (10.0, 5000.0),
    },
}


def lookup_cost_correlation(inp: CostCorrelationInput) -> CostCorrelationResult:
    """成本关联式查表 + 计算。

    Args:
        inp: ``CostCorrelationInput``（已冻结 dataclass）。

    Returns:
        ``CostCorrelationResult``（含 estimated_cost + 关联式元数据）。

    Raises:
        ``CostCorrelationInputError``：输入字段越界或设备类型未知（422）。
    """
    if inp.equipment_type not in _COST_CORRELATIONS:
        raise CostCorrelationInputError(f"未知 equipment_type: {inp.equipment_type}")
    if inp.scale_parameter <= 0:
        raise CostCorrelationInputError("scale_parameter 必须 > 0")

    corr = _COST_CORRELATIONS[inp.equipment_type]
    valid_lo, valid_hi = corr["valid_range"]  # type: ignore[misc]
    if inp.scale_parameter < valid_lo or inp.scale_parameter > valid_hi:
        raise CostCorrelationInputError(
            f"scale_parameter {inp.scale_parameter} 超出 {inp.equipment_type} "
            f"有效范围 [{valid_lo}, {valid_hi}]"
        )

    coefficient_a: float = corr["a"]  # type: ignore[assignment]
    coefficient_b: float = corr["b"]  # type: ignore[assignment]
    scaling_exponent_n: float = corr["n"]  # type: ignore[assignment]

    estimated_cost = coefficient_a + coefficient_b * (inp.scale_parameter ** scaling_exponent_n)

    return CostCorrelationResult(
        estimated_cost=estimated_cost,
        correlation_id=f"CC-{inp.equipment_type}-v1",
        equipment_type=inp.equipment_type,
        scale_parameter=inp.scale_parameter,
        coefficient_a=coefficient_a,
        coefficient_b=coefficient_b,
        scaling_exponent_n=scaling_exponent_n,
    )
