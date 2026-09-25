"""COOL_TOWER 冷却塔 service（§3.2.4 P6-CT-001）。

按 SPEC §3.2.4 P6-CT-001 实施冷却塔选型与水耗计算：

- ``merkel`` 提供 ``calc_merkel_kav_l``：按 §3.2.4.1 Chebyshev 4 点法求
  冷却数 KaV/L（CTI ATC-105 标准；i_w 简化经验式 0~50°C 误差 <2%）。
- ``tower_curve`` 提供 ``calc_tower_curve_kav_l``：按 §3.2.4.2
  CTI ATC-105 特性曲线 KaV/L = C × (L/G)^(−m)（CTI/MANUFACTURER 双模）。
- ``water_balance`` 提供 ``calc_water_flow`` + ``calc_water_balance``：
  按 §3.2.4.3 循环水量 Q_w = H / (ρ × Cp × ΔT) + §3.2.4.4 补充水量
  M = E + D + B（蒸发 + 风吹 + 排污）。
- ``heat_aggregator`` 提供 ``aggregate_heat_duty``：按 §3.2.4.5 从
  heat_results 表汇总水冷 duty → H kW。
- ``fan_power`` 提供 ``calc_fan_power``：按 §3.2.4.6 CTI 1492 经验值
  P_fan = Q_air × Δp_total / (η_fan × η_motor × 1000)。
- ``cool_tower_persist_service`` 提供 5 service 函数（save /
  list / get / update / soft_delete）镜像 Task 23 flare_persist_service。

Task 24: merkel + tower_curve + water_balance 计算层（无 endpoint）。
Task 25: heat_load_aggregator + fan_power + persist + api。
"""
from __future__ import annotations

from app.services.cool_tower.cool_tower_persist_service import (  # P6-2 Task 25
    CoolTowerPersistInputError,
    get_cool_tower_result,
    list_cool_tower_results,
    save_cool_tower_result,
    soft_delete_cool_tower_result,
    update_cool_tower_result,
)
from app.services.cool_tower.fan_power import (  # P6-2 Task 25
    FanPowerInput,
    FanPowerInputError,
    FanPowerResult,
    calc_fan_power,
)
from app.services.cool_tower.heat_aggregator import (  # P6-2 Task 25
    HeatAggregatorInput,
    HeatAggregatorInputError,
    HeatAggregatorResult,
    aggregate_heat_duty,
)
from app.services.cool_tower.merkel import (  # P6-2 Task 24
    MerkelInput,
    MerkelInputError,
    MerkelResult,
    calc_merkel_kav_l,
)
from app.services.cool_tower.tower_curve import (  # P6-2 Task 24
    CurveSource,
    TowerCurveInput,
    TowerCurveInputError,
    TowerCurveResult,
    calc_tower_curve_kav_l,
)
from app.services.cool_tower.water_balance import (  # P6-2 Task 24
    WaterBalanceInput,
    WaterBalanceInputError,
    WaterBalanceResult,
    WaterFlowInput,
    WaterFlowInputError,
    WaterFlowResult,
    calc_water_balance,
    calc_water_flow,
)

__all__ = [
    # P6-2 Task 24 — merkel（§3.2.4.1 Chebyshev 4 点法）
    "MerkelInput",
    "MerkelResult",
    "MerkelInputError",
    "calc_merkel_kav_l",
    # P6-2 Task 24 — tower_curve（§3.2.4.2 CTI ATC-105 特性曲线）
    "CurveSource",
    "TowerCurveInput",
    "TowerCurveResult",
    "TowerCurveInputError",
    "calc_tower_curve_kav_l",
    # P6-2 Task 24 — water_balance（§3.2.4.3 + §3.2.4.4 循环水量 + 补充水量）
    "WaterFlowInput",
    "WaterFlowResult",
    "WaterFlowInputError",
    "calc_water_flow",
    "WaterBalanceInput",
    "WaterBalanceResult",
    "WaterBalanceInputError",
    "calc_water_balance",
    # P6-2 Task 25 — heat_aggregator（§3.2.4.5 水冷 duty 汇总）
    "HeatAggregatorInput",
    "HeatAggregatorResult",
    "HeatAggregatorInputError",
    "aggregate_heat_duty",
    # P6-2 Task 25 — fan_power（§3.2.4.6 风机功率 CTI 1492）
    "FanPowerInput",
    "FanPowerResult",
    "FanPowerInputError",
    "calc_fan_power",
    # P6-2 Task 25 — cool_tower_persist_service（CRUD + sign_status 流）
    "CoolTowerPersistInputError",
    "save_cool_tower_result",
    "list_cool_tower_results",
    "get_cool_tower_result",
    "update_cool_tower_result",
    "soft_delete_cool_tower_result",
]
