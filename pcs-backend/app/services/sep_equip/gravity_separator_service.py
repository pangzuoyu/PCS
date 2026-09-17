"""P5-2-3 重力沉降器（Stokes + Intermediate + Newton 三区）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md 行 232-245 + ADR-0032 V1.1 风格：
- ChEDL 优先（V1.8 F-13-2 包装层规则）
- 调 chedl_wrapper.v_terminal（D, rhop, rho, mu, Method=None）
  → ChEDL 内部 Stokes/Intermediate/Newton 三区迭代收敛
- 本函数**外加**三区判定（基于 ChEDL 收敛后的 Re_p）
- 叶片/纤维效率系数（spec §3.2.2：VANE 0.5 / FIBER 0.3）
- 沉降室长度：L = H_set × V_h / V_t × efficiency_factor
- SI 单位（m, m/s, kg/m³, Pa·s）
- 纯函数（frozen dataclass → frozen dataclass），不触 DB；落库属 P5-2-4

公式：
- Re_p = ρ_f × V_t × D / μ
- 三区：Re_p < 0.1 → STOKES；0.1~1000 → INTERMEDIATE；> 1000 → NEWTON
- L_chamber = H_set × V_h / V_t × efficiency_factor
  - efficiency_factor: PLAIN=1.0 / VANE=0.5 / FIBER=0.3

来源：
- Stokes 1851（终端速度经典解）
- ChEDL `fluids.v_terminal`（drag_sphere 内置三区迭代收敛；P5-1-1 包装层就绪）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from app.services import chedl_wrapper
from app.services.exceptions import PcsError

# 类型别名
Region = Literal["STOKES", "INTERMEDIATE", "NEWTON"]
SeparatorType = Literal["PLAIN", "VANE", "FIBER"]

# 物理常量
_G: Final[float] = 9.80665  # m/s²

# Re_p 三区边界（无量纲）
_RE_STOKES_MAX: Final[float] = 0.1
_RE_INTERMEDIATE_MAX: Final[float] = 1000.0

# 沉降室几何边界
_HEIGHT_SETTING_MIN: Final[float] = 0.01  # 沉降高度最小 10 mm
_D_PARTICLE_MIN: Final[float] = 1.0e-7  # 颗粒直径最小 0.1 μm

# 叶片/纤维效率系数（spec §3.2.2）
_EFF_PLAIN: Final[float] = 1.0
_EFF_VANE: Final[float] = 0.5
_EFF_FIBER: Final[float] = 0.3

# chamber_width 估算系数（无宽高比时取典型值）
_WIDTH_HEIGHT_RATIO: Final[float] = 0.5  # 沉降室宽：高 ≈ 0.5：1


class GravitySeparatorInputError(PcsError):
    """重力沉降器输入物理量不合法（422）。"""

    code = "GRAVITY_SEPARATOR_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class GravitySeparatorInput:
    """calc_gravity_separator 输入参数（frozen dataclass）。

    物理量 SI 单位：
      - 颗粒直径 m
      - 密度 kg/m³
      - 黏度 Pa·s
      - 沉降高度 m
      - 水平流速 m/s
    """

    d_particle_m: float
    rho_particle_kg_m3: float
    rho_fluid_kg_m3: float
    mu_fluid_pa_s: float
    height_setting_m: float  # 沉降室有效高度（H_set）
    horizontal_velocity_ms: float  # 水平气流/液流速度
    separator_type: SeparatorType = "PLAIN"


@dataclass(frozen=True)
class GravitySeparatorResult:
    """calc_gravity_separator 输出结果（frozen dataclass）。

    字段：
      - settling_velocity_ms：颗粒终端沉降速度（ChEDL 收敛解）
      - re_particle：颗粒雷诺数（ρ_f × V_t × D / μ）
      - region：STOKES / INTERMEDIATE / NEWTON
      - chamber_length_m：沉降室长度（L = H × V_h / V_t × eff_factor）
      - chamber_width_m：沉降室宽度（H × width_height_ratio）
      - separator_type：PLAIN / VANE / FIBER
    """

    settling_velocity_ms: float
    re_particle: float
    region: Region
    chamber_length_m: float
    chamber_width_m: float
    separator_type: SeparatorType


# ---------------------------------------------------------------------------
# 内部：校验 + 效率系数 + 三区判定
# ---------------------------------------------------------------------------


def _validate_input(inp: GravitySeparatorInput) -> None:
    """输入物理量边界校验。"""
    if inp.d_particle_m < _D_PARTICLE_MIN:
        raise GravitySeparatorInputError(
            f"d_particle_m={inp.d_particle_m} 必须 ≥ {_D_PARTICLE_MIN}"
        )
    if inp.rho_particle_kg_m3 <= inp.rho_fluid_kg_m3:
        raise GravitySeparatorInputError(
            f"ρ_p={inp.rho_particle_kg_m3} 必须 > ρ_f={inp.rho_fluid_kg_m3}"
            "（颗粒比流体重才能沉降）"
        )
    if inp.mu_fluid_pa_s <= 0:
        raise GravitySeparatorInputError(
            f"mu_fluid_pa_s={inp.mu_fluid_pa_s} 必须 > 0"
        )
    if inp.height_setting_m < _HEIGHT_SETTING_MIN:
        raise GravitySeparatorInputError(
            f"height_setting_m={inp.height_setting_m} 必须 ≥ {_HEIGHT_SETTING_MIN}"
        )
    if inp.horizontal_velocity_ms <= 0:
        raise GravitySeparatorInputError(
            f"horizontal_velocity_ms={inp.horizontal_velocity_ms} 必须 > 0"
        )
    if inp.separator_type not in ("PLAIN", "VANE", "FIBER"):
        raise GravitySeparatorInputError(
            f"separator_type={inp.separator_type} 不在 ['PLAIN', 'VANE', 'FIBER']"
        )


def _classify_re(re_particle: float) -> Region:
    """Re_p → 三区判定。"""
    if re_particle < _RE_STOKES_MAX:
        return "STOKES"
    if re_particle < _RE_INTERMEDIATE_MAX:
        return "INTERMEDIATE"
    return "NEWTON"


def _efficiency_factor(sep_type: SeparatorType) -> float:
    """叶片/纤维效率系数（spec §3.2.2）。"""
    if sep_type == "PLAIN":
        return _EFF_PLAIN
    if sep_type == "VANE":
        return _EFF_VANE
    return _EFF_FIBER  # FIBER


# ---------------------------------------------------------------------------
# 公共入口
# ---------------------------------------------------------------------------


def calc_gravity_separator(inp: GravitySeparatorInput) -> GravitySeparatorResult:
    """计算颗粒终端沉降速度 + 沉降室几何（按三区自动判定 + 效率系数）。

    流程：
      1. 校验输入
      2. 调 chedl_wrapper.v_terminal 收三区迭代收敛解
      3. Re_p = ρ_f × V_t × D / μ → 三区判定
      4. 沉降室长度：L = H × V_h / V_t × eff_factor
      5. 沉降室宽度：W = H × width_height_ratio

    返回 frozen dataclass；纯函数不触 DB。
    """
    _validate_input(inp)

    # ChEDL 三区迭代收敛（Stokes / Intermediate / Newton 自动切换）
    v_t_ms = chedl_wrapper.v_terminal(
        D=inp.d_particle_m,
        rhop=inp.rho_particle_kg_m3,
        rho=inp.rho_fluid_kg_m3,
        mu=inp.mu_fluid_pa_s,
    )

    # 颗粒雷诺数（基于 ChEDL 收敛 V_t）
    re_p = (
        inp.rho_fluid_kg_m3 * v_t_ms * inp.d_particle_m / inp.mu_fluid_pa_s
    )
    region = _classify_re(re_p)

    # 沉降室几何
    eff = _efficiency_factor(inp.separator_type)
    chamber_length_m = (
        inp.height_setting_m * inp.horizontal_velocity_ms / v_t_ms * eff
    )
    chamber_width_m = inp.height_setting_m * _WIDTH_HEIGHT_RATIO

    return GravitySeparatorResult(
        settling_velocity_ms=v_t_ms,
        re_particle=re_p,
        region=region,
        chamber_length_m=chamber_length_m,
        chamber_width_m=chamber_width_m,
        separator_type=inp.separator_type,
    )