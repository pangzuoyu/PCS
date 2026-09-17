"""P5-3-5 PSV 呼吸阀（API 2000 Venting Atmospheric and Low-Pressure Storage Tanks）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §370-394 + API 2000 7th Ed.：

常压储罐呼吸阀（PV Valve）：
- 吸气工况：储罐抽出物料 → 真空 → 大气进入
- 排气工况：储罐进料 + 热膨胀 → 正压 → 气体排出

API 2000 §5.4 呼吸阀计算：
- inbreath_capacity_m3h: 吸气能力（防止真空变形）
- outbreath_capacity_m3h: 排气能力（防止超压）
- pressure_setting: 正压起跳压力
- vacuum_setting: 负压起跳压力
- thermal_breathing_factor: 热呼吸因子（API 2000 Table 4）

V1 简化输出：
- pressure_setting_pa
- vacuum_setting_pa
- recommended_size_inches（基于能力选择 2"/3"/4"/6"/8"/10"/12"）

formula_ref 结构化（F-09）：API_2000 + 7th + §5.4
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError

# ---------- 类型别名 ----------


BreathingValveSize = Literal["2", "3", "4", "6", "8", "10", "12"]


@dataclass(frozen=True)
class BreathingValveFormulaRef:
    """呼吸阀公式溯源（F-09）。"""

    standard: str
    version: str
    clause: str


# ---------- API 2000 标准尺寸能力表（V1 简化） ----------


# 格式：(size_inches, inbreath_capacity_m3h, outbreath_capacity_m3h)
_API2000_SIZE_TABLE: Final[tuple[tuple[BreathingValveSize, float, float], ...]] = (
    ("2", 250.0, 350.0),
    ("3", 600.0, 850.0),
    ("4", 1100.0, 1500.0),
    ("6", 2500.0, 3500.0),
    ("8", 4500.0, 6000.0),
    ("10", 7000.0, 9500.0),
    ("12", 10000.0, 13500.0),
)


# ---------- 输入输出 ----------


@dataclass(frozen=True)
class BreathingValveInput:
    """呼吸阀选型输入。

    物理量 SI 单位：
      - inbreath_flow_m3h: 吸气流量 m³/h
      - outbreath_flow_m3h: 排气流量 m³/h
      - P_design_pa: 储罐设计压力 Pa（确定压力/真空设定）
      - thermal_breathing_factor: 热呼吸因子（API 2000 Table 4，典型 1.0~1.5）
    """

    inbreath_flow_m3h: float
    outbreath_flow_m3h: float
    P_design_pa: float
    thermal_breathing_factor: float = 1.0


@dataclass(frozen=True)
class BreathingValveResult:
    """呼吸阀选型结果。

    字段：
      - pressure_setting_pa: 正压起跳压力 Pa（API 2000 惯例：约 P_design × 0.9）
      - vacuum_setting_pa: 负压起跳压力 Pa（绝对值）
      - recommended_size_inches: 推荐尺寸 inches
      - inbreath_capacity_m3h: 实际吸气能力
      - outbreath_capacity_m3h: 实际排气能力
      - formula_ref: 公式溯源
    """

    pressure_setting_pa: float
    vacuum_setting_pa: float
    recommended_size_inches: BreathingValveSize
    inbreath_capacity_m3h: float
    outbreath_capacity_m3h: float
    formula_ref: BreathingValveFormulaRef


# ---------- 异常 ----------


class PsvBreathingValveInputError(PcsError):
    """PSV 呼吸阀选型输入不合法（422）。"""

    code = "PSV_INPUT_ERROR"
    status = 422


# ---------- 选型实现 ----------


def calc_breathing_valve_api2000(inp: BreathingValveInput) -> BreathingValveResult:
    """API 2000 §5.4 呼吸阀选型。

    - pressure_setting = P_design × 0.9 （起跳压力 ≈ 90% 设计压力）
    - vacuum_setting = P_design × 0.05 （绝对值，常压储罐 5% 设计压力真空）
    - 选 inbreath 与 outbreath 均能覆盖需求的最小尺寸
    """
    _validate(inp)

    # 压力/真空设定
    pressure_setting_pa = inp.P_design_pa * 0.9
    vacuum_setting_pa = inp.P_design_pa * 0.05

    # 应用热呼吸因子（放大需求流量）
    required_in = inp.inbreath_flow_m3h * inp.thermal_breathing_factor
    required_out = inp.outbreath_flow_m3h * inp.thermal_breathing_factor

    # 选最小能覆盖两个需求的尺寸
    selected: BreathingValveSize | None = None
    selected_in_cap: float = 0.0
    selected_out_cap: float = 0.0
    for size, in_cap, out_cap in _API2000_SIZE_TABLE:
        if in_cap >= required_in and out_cap >= required_out:
            selected = size
            selected_in_cap = in_cap
            selected_out_cap = out_cap
            break

    if selected is None:
        # 超出最大尺寸 → 选 12"
        selected = "12"
        selected_in_cap = _API2000_SIZE_TABLE[-1][1]
        selected_out_cap = _API2000_SIZE_TABLE[-1][2]

    return BreathingValveResult(
        pressure_setting_pa=pressure_setting_pa,
        vacuum_setting_pa=vacuum_setting_pa,
        recommended_size_inches=selected,
        inbreath_capacity_m3h=selected_in_cap,
        outbreath_capacity_m3h=selected_out_cap,
        formula_ref=BreathingValveFormulaRef(
            standard="API_2000",
            version="7th",
            clause="§5.4",
        ),
    )


# ---------- 校验 ----------


def _validate(inp: BreathingValveInput) -> None:
    if inp.inbreath_flow_m3h <= 0:
        raise PsvBreathingValveInputError(
            f"inbreath_flow_m3h={inp.inbreath_flow_m3h} 必须 > 0"
        )
    if inp.outbreath_flow_m3h <= 0:
        raise PsvBreathingValveInputError(
            f"outbreath_flow_m3h={inp.outbreath_flow_m3h} 必须 > 0"
        )
    if inp.P_design_pa <= 0:
        raise PsvBreathingValveInputError(f"P_design_pa={inp.P_design_pa} 必须 > 0")
    if inp.thermal_breathing_factor <= 0:
        raise PsvBreathingValveInputError(
            f"thermal_breathing_factor={inp.thermal_breathing_factor} 必须 > 0"
        )


__all__ = [
    "BreathingValveSize",
    "BreathingValveFormulaRef",
    "BreathingValveInput",
    "BreathingValveResult",
    "calc_breathing_valve_api2000",
    "PsvBreathingValveInputError",
]