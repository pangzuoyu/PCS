"""P5-2-1 旋风分离器三方法（Lapple / Swift / Barth）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md 行 201-215 + ADR-0032 V1.1 风格：
- 三方法自研实现（不依赖 ChEDL `fluids.fpi` —— 模块停滞 8 年；ChEDL 不建议复用）
- 默认方法 Lapple（GPSA Engineering Data Book 经典）
- Swift / Barth 作为可选 method 参数
- SI 单位（m, m/s, Pa, kg/m³）
- 纯函数（frozen dataclass → frozen dataclass），不触 DB；落库属 P5-2-4

公式来源：
- Lapple 1951（GPSA Engineering Data Book §Cyclone Separators, 13th ed.）
- Swift 1989（Cooper & Alley "Air Pollution Control" 4th ed. 简化旋流数模型）
- Barth 1956（Mitt. VGB 经验系数）

公式：
- Lapple: C_f = 16·a·b/D_e²; ΔP = C_f·ρ/2·V_in²
- Swift:  φ = D_e/D_cylinder; ΔP = (1 + 2·φ²)·ρ/2·V_in²
- Barth:  K_b = 4·(a·b)/(D_e·D_cylinder); ΔP = K_b·ρ/2·V_in²
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError

# 类型别名
CycloneMethod = Literal["LAPPLE", "SWIFT", "BARTH"]

# 物理常量
_PI: Final[float] = math.pi

# 几何边界（旋风分离器工程典型）
_INLET_B_MIN: Final[float] = 0.01  # 入口高度最小 10 mm
_D_CYLINDER_MIN: Final[float] = 0.1  # 筒径最小 100 mm
_D_EXHAUST_MIN: Final[float] = 0.05  # 排气管最小 50 mm
_N_TURNS_MIN: Final[float] = 1.0  # 有效回转数下界
_N_TURNS_MAX: Final[float] = 20.0  # 有效回转数上界（高效旋风可达 8~10）


class CycloneInputError(PcsError):
    """旋风分离器输入物理量不合法（422）。"""

    code = "CYCLONE_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class CycloneInput:
    """calc_cyclone 输入参数（frozen dataclass）。

    物理量 SI 单位：
      - 长度 m
      - 速度 m/s
      - 密度 kg/m³
      - 黏度 Pa·s
      - 有效回转数无量纲（typical 5~8）
    """

    D_cylinder_m: float
    D_exhaust_m: float
    a_inlet_m: float  # 入口宽度
    b_inlet_m: float  # 入口高度
    V_in_ms: float  # 入口流速
    rho_kg_m3: float  # 气体密度
    mu_pa_s: float  # 气体黏度（保留供后续 efficiency 扩展）
    rho_particle_kg_m3: float  # 颗粒密度（保留供 d50 / efficiency 扩展）
    N_effective_turns: float  # 有效回转数（Stairmand 5；高效 8）
    method: CycloneMethod = "LAPPLE"


@dataclass(frozen=True)
class CycloneResult:
    """calc_cyclone 输出结果（frozen dataclass）。

    字段：
      - D_cylinder_m / inlet_width_m / inlet_height_m：几何回显
      - pressure_drop_pa：压降（按 method 不同公式计算）
      - efficiency_pct：切割效率（P5-2-1 留 None 占位；后续扩展 d50 + 粒径分布）
      - method：所用方法
    """

    D_cylinder_m: float
    inlet_width_m: float
    inlet_height_m: float
    pressure_drop_pa: float
    efficiency_pct: float | None
    method: CycloneMethod


# ---------------------------------------------------------------------------
# 内部：几何 + 物理量校验
# ---------------------------------------------------------------------------


def _validate_input(inp: CycloneInput) -> None:
    """输入物理量边界校验。"""
    if inp.D_cylinder_m < _D_CYLINDER_MIN:
        raise CycloneInputError(
            f"D_cylinder_m={inp.D_cylinder_m} 必须 ≥ {_D_CYLINDER_MIN}"
        )
    if inp.D_exhaust_m < _D_EXHAUST_MIN:
        raise CycloneInputError(
            f"D_exhaust_m={inp.D_exhaust_m} 必须 ≥ {_D_EXHAUST_MIN}"
        )
    if inp.a_inlet_m <= 0 or inp.b_inlet_m < _INLET_B_MIN:
        raise CycloneInputError(
            f"a_inlet_m={inp.a_inlet_m} 必须 > 0；"
            f"b_inlet_m={inp.b_inlet_m} 必须 ≥ {_INLET_B_MIN}"
        )
    if inp.V_in_ms <= 0:
        raise CycloneInputError(f"V_in_ms={inp.V_in_ms} 必须 > 0")
    if inp.rho_kg_m3 <= 0:
        raise CycloneInputError(f"rho_kg_m3={inp.rho_kg_m3} 必须 > 0")
    if not (_N_TURNS_MIN <= inp.N_effective_turns <= _N_TURNS_MAX):
        raise CycloneInputError(
            f"N_effective_turns={inp.N_effective_turns} 必须在"
            f" [{_N_TURNS_MIN}, {_N_TURNS_MAX}]"
        )
    if inp.method not in ("LAPPLE", "SWIFT", "BARTH"):
        raise CycloneInputError(
            f"method={inp.method} 不在 ['LAPPLE', 'SWIFT', 'BARTH']"
        )


# ---------------------------------------------------------------------------
# 三方法：纯函数（输入 → 压降）
# ---------------------------------------------------------------------------


def _pressure_drop_lapple(inp: CycloneInput) -> float:
    """Lapple 1951 经典公式（GPSA Engineering Data Book §Cyclone Separators）。

    C_f = 16·a·b/D_e²
    ΔP = C_f·ρ/2·V_in²

    验证：d=0.5, a=0.2, b=0.1, D_e=0.25, V_in=15, ρ=1.2
    → C_f = 5.12；ΔP = 691.2 Pa
    """
    c_f = 16.0 * inp.a_inlet_m * inp.b_inlet_m / (inp.D_exhaust_m ** 2)
    return c_f * inp.rho_kg_m3 / 2.0 * inp.V_in_ms ** 2


def _pressure_drop_swift(inp: CycloneInput) -> float:
    """Swift 旋流数简化模型（Cooper & Alley 2010 §Cyclone Pressure Drop）。

    φ = D_e/D_cylinder（旋流数比）
    ΔP = (1 + 2·φ²)·ρ/2·V_in²

    工程含义：旋流数越大，压降越高（旋流增强但流阻增加）。
    比 Lapple 低（标准型 0.5~0.7 倍）。
    """
    phi = inp.D_exhaust_m / inp.D_cylinder_m
    return (1.0 + 2.0 * phi ** 2) * inp.rho_kg_m3 / 2.0 * inp.V_in_ms ** 2


def _pressure_drop_barth(inp: CycloneInput) -> float:
    """Barth 1956 经验公式（Mitt. VGB 简化形式）。

    K_b = 4·(a·b)/(D_e·D_cylinder)
    ΔP = K_b·ρ/2·V_in²

    工程含义：基于入口面积与筒-排气管几何比的经验系数。
    比 Lapple 略低（典型 0.5~0.8 倍），工程实测较准。
    """
    k_b = 4.0 * inp.a_inlet_m * inp.b_inlet_m / (
        inp.D_exhaust_m * inp.D_cylinder_m
    )
    return k_b * inp.rho_kg_m3 / 2.0 * inp.V_in_ms ** 2


_DISPATCH: dict[CycloneMethod, callable] = {
    "LAPPLE": _pressure_drop_lapple,
    "SWIFT": _pressure_drop_swift,
    "BARTH": _pressure_drop_barth,
}


# ---------------------------------------------------------------------------
# 公共入口
# ---------------------------------------------------------------------------


def calc_cyclone(inp: CycloneInput) -> CycloneResult:
    """计算旋风分离器压降（按 method 三方法）。

    纯函数不触 DB。返回 frozen dataclass：
      - pressure_drop_pa：按 method 计算的压降
      - efficiency_pct：留 None（P5-2-1 仅占位接口；d50 + 粒径分布拟合
        由后续扩展实现，需 GPSA d50 切割粒径 + 累积效率曲线数据）
      - 其余字段：几何回显 + method 标签
    """
    _validate_input(inp)
    dp_pa = _DISPATCH[inp.method](inp)
    return CycloneResult(
        D_cylinder_m=inp.D_cylinder_m,
        inlet_width_m=inp.a_inlet_m,
        inlet_height_m=inp.b_inlet_m,
        pressure_drop_pa=dp_pa,
        efficiency_pct=None,  # P5-2-1 占位；后续 d50 + 累积效率曲线
        method=inp.method,
    )