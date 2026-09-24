"""COOL_TOWER 冷却塔 service（§3.2.4 P6-CT-001）。

按 SPEC §3.2.4 P6-CT-001 实施冷却塔选型与水耗计算：

- ``merkel`` 提供 ``calc_merkel_kav_l``：按 §3.2.4.1 Chebyshev 4 点法求
  冷却数 KaV/L（CTI ATC-105 标准；i_w 简化经验式 0~50°C 误差 <2%）。
- ``tower_curve`` 提供 ``calc_tower_curve_kav_l``：按 §3.2.4.2
  CTI ATC-105 特性曲线 KaV/L = C × (L/G)^(−m)（CTI/MANUFACTURER 双模）。
- ``water_balance`` 提供 ``calc_water_flow`` + ``calc_water_balance``：
  按 §3.2.4.3 循环水量 Q_w = H / (ρ × Cp × ΔT) + §3.2.4.4 补充水量
  M = E + D + B（蒸发 + 风吹 + 排污）。

Task 24: merkel + tower_curve + water_balance 计算层（无 endpoint）。
Task 25: heat_load_aggregator + fan_power + persist + api。
"""
from __future__ import annotations

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
]
