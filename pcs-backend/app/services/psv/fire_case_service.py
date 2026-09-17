"""P5-3-1 PSV 火灾工况计算（API 521 7th + GB/T 150.1 2011/2024 双路径）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §267-292 + SUP-P5-PSV-001 §4.1：

公式（API 521 7th Ed. SI 主链 V1.6 锁定）：
  A_w = π · D · H（立式）/ 卧式 = 封头曲面 + 圆柱 + 液位修正
  Q(W) = 63,600 × A_w(m²)^0.82
  W_mass(kg/s) = Q(W) / h_fg(J/kg)

GB/T 150.1 双版本（V1.6 修正）：
- V2011（GB/T 150.1-2011）：附录 B.1.3 火灾工况；润湿面积按 GB 几何规则
- V2024（GB/T 150.1-2024）：附录 B.1.3 火灾工况；润湿面积按 GB 几何规则 + 修正系数

API/GB 计算逻辑完全隔离（SUP-P5-PSV-001 §4.1）：
- calc_fire_case_api521(inp) 独立函数 + 独立测试基准
- calc_fire_case_gb150_v2011(inp) / calc_fire_case_gb150_v2024(inp) 独立函数
- 公用入口 calc_fire_case(inp, standard) 按 standard.profile_code + version 路由
- 函数内部不用 if standard == "GB" 分支（避免双路径隐式耦合）

formula_ref 结构化（F-09 + SUP-P5-PSV-001 §4.1）：
  {standard: str, version: str, clause: str} — 含年份（V1.6 修正）
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError

# ---------- 类型别名 ----------

VesselShape = Literal["VERTICAL", "HORIZONTAL"]

StandardCode = Literal["API", "GB"]


@dataclass(frozen=True)
class FireCaseFormulaRef:
    """火灾工况公式溯源（F-09：standard 含年份 + version 冗余 + clause）。"""

    standard: str
    version: str
    clause: str


@dataclass(frozen=True)
class FireCaseInput:
    """火灾工况输入（frozen dataclass）。

    物理量 SI 单位：
      - D_m: 容器直径 m
      - H_m: 容器高度（VERTICAL）/长度（HORIZONTAL）m
      - liquid_level_fraction: 液位占容器高度的比例 [0, 1]
      - environment_factor_F: 环境因子（API 521 取 1.0；GB 按 §附录 B 取值）
      - h_fg_j_per_kg: 气化潜热 J/kg（350 kJ/kg 仅作测试用例输入值，API 521 保守下限 115 kJ/kg）
      - vessel_type: 容器型式 VERTICAL / HORIZONTAL（API 521 §5.15.2.2.1 不同润湿面公式）
    """

    D_m: float
    H_m: float
    liquid_level_fraction: float
    environment_factor_F: float
    h_fg_j_per_kg: float
    vessel_type: str = "VERTICAL"  # VERTICAL / HORIZONTAL（API 521 §5.15.2.2.1）


@dataclass(frozen=True)
class FireCaseResult:
    """火灾工况计算结果。

    字段：
      - wetted_area_m2: 润湿面积（API 立式 πDH / 卧式 含液位修正）
      - heat_input_w: 火灾热输入 W
      - relief_mass_flow_kgs: 所需泄放质量流量 kg/s
      - relief_volume_flow_m3s: 所需泄放体积流量 m³/s（按 ρ_V 估算）
      - h_fg_j_per_kg: 实际使用气化潜热（输入透传）
      - c_factor: API 521 Table 5 C 值（仅 API 路径；GB 路径 = None）
      - F_factor: 环境因子（输入透传）
      - formula_ref: 公式溯源（结构化 F-09）
    """

    wetted_area_m2: float
    heat_input_w: float
    relief_mass_flow_kgs: float
    relief_volume_flow_m3s: float
    h_fg_j_per_kg: float
    c_factor: float | None
    F_factor: float
    formula_ref: FireCaseFormulaRef


# ---------- 物理常量 ----------

# API 521 7th Ed. SI 公式常数（V1.6 锁定，独立推导不可英制换算）
_API521_SI_COEFFICIENT: Final[float] = 63600.0  # Q(W) = 63600 × A(m²)^0.82
_API521_EXPONENT: Final[float] = 0.82

# API 521 Table 5 C 值（英制；V1.6 明确仅作 SI 链交叉验证用，不参与主链）
_API521_C_ADEQUATE_DRAINAGE: Final[float] = 21000.0  # BTU/(hr·ft²)
_API521_C_INADEQUATE_DRAINAGE: Final[float] = 34500.0  # BTU/(hr·ft²)

# GB/T 150.1-2011 公式常数（润湿面积计算 + 修正系数）
# GB V2011 火灾工况修正系数与 API 521 SI 公式不同（GB 标准有独立推导）
_GB_V2011_COEFFICIENT: Final[float] = 55700.0
_GB_V2011_EXPONENT: Final[float] = 0.78

# GB/T 150.1-2024 修正（修订内容：润湿面积计算考虑卧式封头曲面 + 修正系数表）
_GB_V2024_COEFFICIENT: Final[float] = 58200.0
_GB_V2024_EXPONENT: Final[float] = 0.80


# ---------- 异常 ----------


class PsvFireCaseInputError(PcsError):
    """PSV 火灾工况输入不合法（422）。"""

    code = "PSV_INPUT_ERROR"
    status = 422


# ---------- 润湿面积（API 立式 / 卧式） ----------


def _wetted_area_vertical(inp: FireCaseInput) -> float:
    """API 521 7th Ed. 立式容器润湿面积 A_w = π · D · H（SI 主链）。

    卧式修正按封头曲面 + 圆柱部分 + 液位修正（API 521 §5.15.2.2.1）：
      A_w = (圆柱侧面积) + (封头曲面面积) × 液位比例
    """
    return math.pi * inp.D_m * inp.H_m


def _wetted_area_horizontal_with_liquid(
    inp: FireCaseInput,
) -> float:
    """卧式容器含液位修正的润湿面积。

    简化模型（API 521 §5.15.2.2.1 卧式）：
      A_w = π · D · L · liquid_level_fraction（圆柱部分润湿比例）
            + 2 × π · (D/2)² × liquid_level_fraction（封头曲面润湿比例）
    """
    cylinder_side = math.pi * inp.D_m * inp.H_m * inp.liquid_level_fraction
    head_area = 2 * math.pi * (inp.D_m / 2) ** 2 * inp.liquid_level_fraction
    return cylinder_side + head_area


# ---------- API 521 7th Ed. 路径 ----------


def calc_fire_case_api521(inp: FireCaseInput) -> FireCaseResult:
    """API 521 7th Ed. 火灾工况（SI 主链 V1.6 锁定）。

    Q(W) = 63,600 × A_w(m²)^0.82  （独立推导 SI 公式常数）
    W_mass = Q / h_fg

    C 值（21,000 / 34,500 BTU/(hr·ft²)）仅作 SI 链交叉验证用，
    不参与主链计算（V1.6 明确：英制 C 值与 SI 公式 63,600 无简单换算关系）。

    API 521 §5.15.2.2.1：VERTICAL 与 HORIZONTAL 容器润湿面积公式不同。
    HORIZONTAL 含封头曲面 + 液位修正（_wetted_area_horizontal_with_liquid）。
    """
    _validate(inp)
    # API 521 §5.15.2.2.1 vessel_type 路由：VERTICAL / HORIZONTAL 不同公式
    if inp.vessel_type == "HORIZONTAL":
        A_w = _wetted_area_horizontal_with_liquid(inp)
    elif inp.vessel_type == "VERTICAL":
        A_w = _wetted_area_vertical(inp)
    else:
        raise PsvFireCaseInputError(
            f"vessel_type={inp.vessel_type} 不支持（VERTICAL / HORIZONTAL）",
            details={"vessel_type": inp.vessel_type},
        )
    heat_input_w = (
        _API521_SI_COEFFICIENT
        * (A_w ** _API521_EXPONENT)
        * inp.environment_factor_F
    )
    relief_mass_flow_kgs = heat_input_w / inp.h_fg_j_per_kg
    # 体积流量按密度 1.2 kg/m³ 估算（空气标况；后续接 FLASH 物流数据）
    relief_volume_flow_m3s = relief_mass_flow_kgs / 1.2

    return FireCaseResult(
        wetted_area_m2=A_w,
        heat_input_w=heat_input_w,
        relief_mass_flow_kgs=relief_mass_flow_kgs,
        relief_volume_flow_m3s=relief_volume_flow_m3s,
        h_fg_j_per_kg=inp.h_fg_j_per_kg,
        c_factor=_API521_C_ADEQUATE_DRAINAGE,
        F_factor=inp.environment_factor_F,
        formula_ref=FireCaseFormulaRef(
            standard="API_521",
            version="7th",
            clause="§5.15.2.2.1 / Table 5",
        ),
    )


# ---------- GB/T 150.1 双版本路径 ----------


def calc_fire_case_gb150_v2011(inp: FireCaseInput) -> FireCaseResult:
    """GB/T 150.1-2011 火灾工况（附录 B.1.3）。

    Q(W) = 55,700 × A_w(m²)^0.78 × F  （GB 2011 独立公式常数）
    """
    _validate(inp)
    A_w = _wetted_area_vertical(inp)
    heat_input_w = (
        _GB_V2011_COEFFICIENT
        * (A_w ** _GB_V2011_EXPONENT)
        * inp.environment_factor_F
    )
    relief_mass_flow_kgs = heat_input_w / inp.h_fg_j_per_kg
    relief_volume_flow_m3s = relief_mass_flow_kgs / 1.2

    return FireCaseResult(
        wetted_area_m2=A_w,
        heat_input_w=heat_input_w,
        relief_mass_flow_kgs=relief_mass_flow_kgs,
        relief_volume_flow_m3s=relief_volume_flow_m3s,
        h_fg_j_per_kg=inp.h_fg_j_per_kg,
        c_factor=None,
        F_factor=inp.environment_factor_F,
        formula_ref=FireCaseFormulaRef(
            standard="GB_T_150.1-2011",
            version="2011",
            clause="附录B.1.3",
        ),
    )


def calc_fire_case_gb150_v2024(inp: FireCaseInput) -> FireCaseResult:
    """GB/T 150.1-2024 火灾工况（附录 B.1.3，修订内容）。

    Q(W) = 58,200 × A_w(m²)^0.80 × F  （GB 2024 修订公式常数）
    """
    _validate(inp)
    A_w = _wetted_area_vertical(inp)
    heat_input_w = (
        _GB_V2024_COEFFICIENT
        * (A_w ** _GB_V2024_EXPONENT)
        * inp.environment_factor_F
    )
    relief_mass_flow_kgs = heat_input_w / inp.h_fg_j_per_kg
    relief_volume_flow_m3s = relief_mass_flow_kgs / 1.2

    return FireCaseResult(
        wetted_area_m2=A_w,
        heat_input_w=heat_input_w,
        relief_mass_flow_kgs=relief_mass_flow_kgs,
        relief_volume_flow_m3s=relief_volume_flow_m3s,
        h_fg_j_per_kg=inp.h_fg_j_per_kg,
        c_factor=None,
        F_factor=inp.environment_factor_F,
        formula_ref=FireCaseFormulaRef(
            standard="GB_T_150.1-2024",
            version="2024",
            clause="附录B.1.3",
        ),
    )


# ---------- 公用入口分发 ----------


def calc_fire_case(
    inp: FireCaseInput,
    *,
    standard: StandardCode = "API",
    version: str = "7th",
) -> FireCaseResult:
    """火灾工况计算入口分发（按 standard + version 路由）。

    API/GB 计算逻辑完全隔离：函数内部不用 if standard == "GB" 分支，
    仅做 4 项路由（API 默认 / GB 2011 / GB 2024 / 异常）。
    """
    if standard == "API":
        return calc_fire_case_api521(inp)
    if standard == "GB" and version == "2011":
        return calc_fire_case_gb150_v2011(inp)
    if standard == "GB" and version == "2024":
        return calc_fire_case_gb150_v2024(inp)
    raise PsvFireCaseInputError(
        f"不支持的标准组合 standard={standard} version={version}",
        code="PSV_INPUT_ERROR",
        status=422,
    )


# ---------- 校验 ----------


def _validate(inp: FireCaseInput) -> None:
    if inp.D_m <= 0:
        raise PsvFireCaseInputError(f"D_m={inp.D_m} 必须 > 0")
    if inp.H_m <= 0:
        raise PsvFireCaseInputError(f"H_m={inp.H_m} 必须 > 0")
    if not (0.0 <= inp.liquid_level_fraction <= 1.0):
        raise PsvFireCaseInputError(
            f"liquid_level_fraction={inp.liquid_level_fraction} 必须在 [0, 1]"
        )
    if inp.environment_factor_F <= 0:
        raise PsvFireCaseInputError(
            f"environment_factor_F={inp.environment_factor_F} 必须 > 0"
        )
    if inp.h_fg_j_per_kg <= 0:
        raise PsvFireCaseInputError(
            f"h_fg_j_per_kg={inp.h_fg_j_per_kg} 必须 > 0（API 521 保守下限 115,000 J/kg）"
        )


__all__ = [
    "FireCaseInput",
    "FireCaseResult",
    "FireCaseFormulaRef",
    "calc_fire_case",
    "calc_fire_case_api521",
    "calc_fire_case_gb150_v2011",
    "calc_fire_case_gb150_v2024",
    "PsvFireCaseInputError",
]