"""COST_EST 投资估算模块（SPEC §3.2.8）。

依据：六十法则（0.6 power scaling）+ CEPCI 调整（Chemical Engineering
Plant Cost Index）+ 成本关联式查 CONFIG。

模块导出：

- ``six_tenths_rule`` 提供 ``calc_six_tenths_rule``：容量/规模 scaling
  ``C₂ = C₁ × (S₂/S₁)^n``（n 默认 0.6）。
- ``cepci_adjustment`` 提供 ``calc_cepci_adjustment``：时间/通胀调整
  ``C₂ = C₁ × (CEPCI₂ / CEPCI₁)``。
- ``cost_correlation_lookup`` 提供 ``lookup_cost_correlation``：设备类型
  → 关联式 ``cost = a + b·S^n``。

不含 endpoint 挂载（Task 36）+ 不含落库（Task 36）+ 不含 G-03 CEPCI
数据录入（Task 18 已完成）。
"""
from app.services.cost_est.cepci_adjustment import (
    CepciAdjustmentInput,
    CepciAdjustmentInputError,
    CepciAdjustmentResult,
    calc_cepci_adjustment,
)
from app.services.cost_est.cost_correlation_lookup import (
    CostCorrelationInput,
    CostCorrelationInputError,
    CostCorrelationResult,
    lookup_cost_correlation,
)
from app.services.cost_est.six_tenths_rule import (
    SixTenthsRuleInput,
    SixTenthsRuleInputError,
    SixTenthsRuleResult,
    calc_six_tenths_rule,
)

__all__ = [
    "SixTenthsRuleInput",
    "SixTenthsRuleResult",
    "SixTenthsRuleInputError",
    "calc_six_tenths_rule",
    "CepciAdjustmentInput",
    "CepciAdjustmentResult",
    "CepciAdjustmentInputError",
    "calc_cepci_adjustment",
    "CostCorrelationInput",
    "CostCorrelationResult",
    "CostCorrelationInputError",
    "lookup_cost_correlation",
]
