"""COOL_TOWER 风机功率计算（§3.2.4.6）。

按 SPEC §3.2.4.6 P6-CT-001（CTI 1492 经验值）：

    P_fan_kw = (Q_air_m3_s × Δp_total_pa) / (η_fan × η_motor × 1000)

其中：

- ``Q_air_m3_s``：风机风量 m³/s（典型湿式逆流塔 1~30）
- ``Δp_total_pa``：风机全压 Pa（typ. 100~400 Pa）
- ``η_fan``：风机效率（轴流式 typ. 0.7，离心式 typ. 0.65；范围 (0, 1)）
- ``η_motor``：电机效率（typ. 0.85~0.95；范围 (0, 1)）
- ``×1000`` 把 W 转为 kW

不依赖 DB（纯计算函数）；输入 ``Q_air`` 来自 Task 25 Merkel 算出的
水气比反推或上游工程参数。

手算校核（Q=10/Δp=200/η_fan=0.7/η_motor=0.9）：

    P_fan_kw = 10 × 200 / (0.7 × 0.9 × 1000)
             = 2000 / 630
             = 3.1746031746... ≈ 3.1746 kW
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.exceptions import PcsError


@dataclass(frozen=True)
class FanPowerInput:
    """风机功率输入（§3.2.4.6）。

    字段：
    - q_air_m3_s: 风机风量 m³/s（>0）
    - delta_p_total_pa: 全压 Pa（>0）
    - fan_efficiency: 风机效率（0 < η_fan < 1）
    - motor_efficiency: 电机效率（0 < η_motor < 1）
    """

    q_air_m3_s: float  # 风机风量 m³/s
    delta_p_total_pa: float  # 全压 Pa
    fan_efficiency: float  # 风机效率
    motor_efficiency: float  # 电机效率


@dataclass(frozen=True)
class FanPowerResult:
    """风机功率输出（§3.2.4.6）。

    字段：
    - p_fan_kw: 风机功率 kW
    - formula_ref: 公式溯源标记 "API_521_§3.2.4.6"
    """

    p_fan_kw: float  # kW
    formula_ref: str = "API_521_§3.2.4.6"


class FanPowerInputError(PcsError):
    """风机功率输入不合法（422）。

    触发场景：Q_air <= 0 / Δp_total <= 0 / η_fan ∉ (0, 1) /
    η_motor ∉ (0, 1)。
    """

    code = "FAN_POWER_INPUT_ERROR"
    status = 422


def calc_fan_power(inp: FanPowerInput) -> FanPowerResult:
    """P_fan_kw = Q_air × Δp_total / (η_fan × η_motor × 1000)（§3.2.4.6）。

    实现步骤：

    1. 输入校验：Q_air > 0 / Δp_total > 0 / 0 < η_fan < 1 / 0 < η_motor < 1
    2. p_fan_kw = Q_air × Δp_total / (η_fan × η_motor × 1000)

    Args:
        inp: FanPowerInput（已冻结 dataclass）。

    Returns:
        FanPowerResult（含 p_fan_kw / formula_ref）。

    Raises:
        FanPowerInputError: 输入字段越界或非正（422）。
    """
    # 输入校验
    if inp.q_air_m3_s <= 0:
        raise FanPowerInputError(
            f"q_air_m3_s ({inp.q_air_m3_s}) 必须 > 0"
        )
    if inp.delta_p_total_pa <= 0:
        raise FanPowerInputError(
            f"delta_p_total_pa ({inp.delta_p_total_pa}) 必须 > 0"
        )
    if not 0 < inp.fan_efficiency < 1:
        raise FanPowerInputError(
            f"fan_efficiency ({inp.fan_efficiency}) 必须在 (0, 1) 区间"
        )
    if not 0 < inp.motor_efficiency < 1:
        raise FanPowerInputError(
            f"motor_efficiency ({inp.motor_efficiency}) 必须在 (0, 1) 区间"
        )

    # 风机功率（kW = W/1000）
    p_fan_kw = (
        inp.q_air_m3_s
        * inp.delta_p_total_pa
        / (inp.fan_efficiency * inp.motor_efficiency * 1000.0)
    )
    return FanPowerResult(p_fan_kw=p_fan_kw)


__all__ = [
    "FanPowerInput",
    "FanPowerResult",
    "FanPowerInputError",
    "calc_fan_power",
]