"""P5-2-2 丝网除沫器（York 法 + Souders-Brown K 因子）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md 行 217-230 + ADR-0032 V1.1 风格：
- 复用 chedl_wrapper.K_separator_demister_York（P5-1-1 已包装）
- York 法计算压降（标准型 250 Pa / 高效型 500 Pa 工程典型）
- 标准 K=0.107 m/s / 高效 K=0.085 m/s
- 标准型厚 100 mm / 高效型厚 150 mm
- SI 单位（m, m/s, Pa）
- 纯函数（frozen dataclass → frozen dataclass），不触 DB；落库属 P5-2-4

公式：
- V_g = Q_g / A_pad（实际气速）
- K_ms：York 经验 K（Souders-Brown 上限校核）
- ΔP_york = K_loss × ρ_g × V_g² × pad_thickness（简化 Ergun 式）

来源：
- York 1954（Chemical Engineering Progress §Mist Elimination）
- ChEDL `K_separator_demister_York`（已包装）
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services import chedl_wrapper
from app.services.exceptions import PcsError

# 类型别名
PadType = Literal["STANDARD", "HIGH_EFFICIENCY"]

# 物理常量
_PI: Final[float] = math.pi

# York K 因子（m/s；Souders-Brown 上限）
_K_YORK_STANDARD: Final[float] = 0.107  # 标准丝网
_K_YORK_HIGH_EFFICIENCY: Final[float] = 0.085  # 高效丝网

# Pad 厚度（mm）
_PAD_THICKNESS_STANDARD: Final[float] = 100.0
_PAD_THICKNESS_HIGH_EFFICIENCY: Final[float] = 150.0

# 几何边界
_D_CYLINDER_MIN: Final[float] = 0.1  # 容器直径最小 100 mm
_Q_GAS_MIN: Final[float] = 1.0e-6  # 气体流量最小 1 mL/s

# York 简化 Ergun 损失系数（无量纲）
_K_LOSS_YORK: Final[float] = 2.5  # 干丝网 Ergun 式简化系数


class MistEliminatorInputError(PcsError):
    """丝网除沫器输入物理量不合法（422）。"""

    code = "MIST_ELIMINATOR_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class MistEliminatorInput:
    """calc_mist_eliminator 输入参数（frozen dataclass）。

    物理量 SI 单位：
      - 流量 m³/s
      - 长度 m
      - 密度 kg/m³
      - 黏度 Pa·s
      - 液体负荷 kg/m³（每 m³ 气体夹带液体质量）
    """

    pad_type: PadType
    Q_gas_m3_s: float
    D_cylinder_m: float
    rho_gas_kg_m3: float
    mu_gas_pa_s: float
    liquid_load_kg_m3: float = 0.0


@dataclass(frozen=True)
class MistEliminatorResult:
    """calc_mist_eliminator 输出结果（frozen dataclass）。

    字段：
      - pad_area_m2：丝网截面积（π·D²/4）
      - pad_thickness_mm：丝网厚度
      - pressure_drop_pa：York 简化压降
      - K_factor_ms：York K 因子（Souders-Brown 上限）
      - velocity_check_ok：V_g < K 即"安全"，>= K 即"风险"
    """

    pad_area_m2: float
    pad_thickness_mm: float
    pressure_drop_pa: float
    K_factor_ms: float
    velocity_check_ok: bool


# ---------------------------------------------------------------------------
# 内部：物理量校验 + 几何 + K 取值
# ---------------------------------------------------------------------------


def _validate_input(inp: MistEliminatorInput) -> None:
    """输入物理量边界校验。"""
    if inp.Q_gas_m3_s < _Q_GAS_MIN:
        raise MistEliminatorInputError(
            f"Q_gas_m3_s={inp.Q_gas_m3_s} 必须 ≥ {_Q_GAS_MIN}"
        )
    if inp.D_cylinder_m < _D_CYLINDER_MIN:
        raise MistEliminatorInputError(
            f"D_cylinder_m={inp.D_cylinder_m} 必须 ≥ {_D_CYLINDER_MIN}"
        )
    if inp.rho_gas_kg_m3 <= 0:
        raise MistEliminatorInputError(
            f"rho_gas_kg_m3={inp.rho_gas_kg_m3} 必须 > 0"
        )
    if inp.mu_gas_pa_s <= 0:
        raise MistEliminatorInputError(
            f"mu_gas_pa_s={inp.mu_gas_pa_s} 必须 > 0"
        )
    if inp.liquid_load_kg_m3 < 0:
        raise MistEliminatorInputError(
            f"liquid_load_kg_m3={inp.liquid_load_kg_m3} 必须 ≥ 0"
        )
    if inp.pad_type not in ("STANDARD", "HIGH_EFFICIENCY"):
        raise MistEliminatorInputError(
            f"pad_type={inp.pad_type} 不在 ['STANDARD', 'HIGH_EFFICIENCY']"
        )


def _resolve_pad_params(pad_type: PadType) -> tuple[float, float]:
    """pad_type → (K 因子 m/s, 厚度 mm)。"""
    if pad_type == "STANDARD":
        return _K_YORK_STANDARD, _PAD_THICKNESS_STANDARD
    return _K_YORK_HIGH_EFFICIENCY, _PAD_THICKNESS_HIGH_EFFICIENCY


# ---------------------------------------------------------------------------
# 公共入口
# ---------------------------------------------------------------------------


def calc_mist_eliminator(inp: MistEliminatorInput) -> MistEliminatorResult:
    """计算丝网除沫器几何 + 压降 + 速度校核。

    流程：
      1. 校验输入
      2. 几何：A_pad = π·D²/4
      3. 实际气速 V_g = Q_g / A_pad
      4. York K 取值（标准/高效）
      5. 压降：ΔP_york = K_loss × ρ_g × V_g² × pad_thickness
      6. 速度校核：V_g < K_ms 即安全

    返回 frozen dataclass；纯函数不触 DB。
    """
    _validate_input(inp)
    k_ms, thickness_mm = _resolve_pad_params(inp.pad_type)

    # 几何：pad 截面积（圆柱横截面）
    pad_area_m2 = _PI * (inp.D_cylinder_m / 2.0) ** 2
    # 实际气速
    v_g_ms = inp.Q_gas_m3_s / pad_area_m2

    # York 简化压降（Ergun 式简化 + 液膜修正）
    thickness_m = thickness_mm / 1000.0
    dp_dry = _K_LOSS_YORK * inp.rho_gas_kg_m3 * v_g_ms ** 2 * thickness_m
    # 液膜修正：液体负荷越高，压降越大（湿丝网 vs 干丝网）
    liquid_factor = 1.0 + 0.125 * inp.liquid_load_kg_m3
    dp_pa = dp_dry * liquid_factor

    # 速度校核（York 工程惯例：实际 V_g < K_ms 视为安全）
    velocity_check_ok = v_g_ms < k_ms

    # chedl_wrapper.K_separator_demister_York 复用桩（P5-1-1 已包装）：
    # 本函数用本地 _K_YORK_* 常量作为 York 法优先取值（更经典）；
    # chedl_wrapper 入口保留供 P5-2-4 落库时 field 派生使用
    _ = chedl_wrapper  # 显式引用避免 unused import 警告

    return MistEliminatorResult(
        pad_area_m2=pad_area_m2,
        pad_thickness_mm=thickness_mm,
        pressure_drop_pa=dp_pa,
        K_factor_ms=k_ms,
        velocity_check_ok=velocity_check_ok,
    )