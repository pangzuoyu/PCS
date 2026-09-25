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
- ``cost_est_persist_service`` 提供 ``save_*_result``（3 calc → 落库）+
  ``*_service``（5 CRUD）入口（P6-3 Task 36）。

不含 endpoint 挂载（Task 36）+ 不含 G-03 CEPCI 数据录入（Task 18 已完成）。
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
from app.services.cost_est.cost_est_persist_service import (  # P6-3 Task 36
    CostEstPersistInputError,
    create_cost_est_result_direct,
    get_cost_est_result_service,
    list_cost_est_results_service,
    save_cepci_adjustment_result,
    save_cost_correlation_result,
    save_six_tenths_rule_result,
    soft_delete_cost_est_result_service,
    update_cost_est_result_service,
)
from app.services.cost_est.six_tenths_rule import (
    SixTenthsRuleInput,
    SixTenthsRuleInputError,
    SixTenthsRuleResult,
    calc_six_tenths_rule,
)

__all__ = [
    # 3 calc（Task 35）
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
    # persist + CRUD（P6-3 Task 36）
    "CostEstPersistInputError",
    "save_six_tenths_rule_result",
    "save_cepci_adjustment_result",
    "save_cost_correlation_result",
    "list_cost_est_results_service",
    "get_cost_est_result_service",
    "update_cost_est_result_service",
    "soft_delete_cost_est_result_service",
    "create_cost_est_result_direct",
]