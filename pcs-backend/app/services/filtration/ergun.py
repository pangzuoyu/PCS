"""Ergun 方程过滤介质阻力（SPEC §3.2.7 第三项 — 深层过滤）。

Ergun 方程（1952）：

    ΔP/L = 150 · μ · (1−ε)² / ε³ · v_s / dp² + 1.75 · ρ · (1−ε) / ε³ · v_s² / dp

其中：

- ``ΔP/L`` — 单位床层压降（Pa/m）
- ``μ`` — 流体粘度（Pa·s）
- ``ε`` — 床层空隙率（无量纲，典型 0.3~0.6）
- ``v_s`` — 表观流速（m/s，基于空管截面）
- ``dp`` — 颗粒直径（m）
- ``ρ`` — 流体密度（kg/m³）
- ``L`` — 床层厚度（m）

适用范围：颗粒雷诺数 Re_p = (ρ · v_s · dp) / μ · 1/(1−ε) ∈ [0.001, 1000]。
深层过滤：v_s ≈ 1e-4 ~ 1e-3 m/s；过滤介质用砂 / 无烟煤 / 活性炭。

介质物性查 ``filtration_media_library`` 表（G-05 数据）：含 dp / ε / ρs。
ERGUN_PACKING 的 ``nominal_rating_um`` = 0.0 占位，本模块读取时忽略（介质阻力由
dp / ε / 床层厚度主导，标称精度仅用于颗粒捕集分级）。

单位校核（dimensional check）：

    [μ · v_s / dp²] = Pa·s · m/s / m² = Pa·s / m = Pa·s/m
    乘以无量纲 150·(1−ε)²/ε³ → Pa·s/m
    乘以 1/m 床层 → Pa/m  ✓（第一项）

    [ρ · v_s² / dp] = kg/m³ · (m/s)² / m = kg/(m²·s²) = Pa·s²/m²·s² = Pa/m ✓（第二项）

手算独立校核（3 例）：

例 1（水+砂 v_s=1e-3/ε=0.4/dp=0.5e-3/μ=1e-3/ρ=1000/L=1）：

    eps = 0.4；1−eps = 0.6；eps³ = 0.064
    laminar = 150 · 1e-3 · 0.36 / 0.064 · 1e-3 / (0.5e-3)²
            = 0.84375 · 1e-3 / 2.5e-7
            ≈ 3375 Pa/m → ΔP_laminar = 3375 Pa（层流主导）

    turbulent = 1.75 · 1000 · 0.6 / 0.064 · (1e-3)² / 0.5e-3
              = 16406.25 · 1e-6 / 5e-4
              ≈ 32.8125 Pa/m → ΔP_turbulent = 32.8125 Pa（紊流可忽略）

    ΔP_total ≈ 3407.8125 Pa（层流主导 ✓）

    Re_p = 1000 · 1e-3 · 0.5e-3 / 1e-3 / 0.6 ≈ 0.8333 ∈ [0.001, 1000] ✓

例 2（高流速 v_s=1.0，其余同例 1）：

    laminar = 150 · 1e-3 · 0.36 / 0.064 · 1 / 2.5e-7
            ≈ 3.375e6 Pa/m
    turbulent = 1.75 · 1000 · 0.6 / 0.064 · 1 / 5e-4
              ≈ 3.28125e7 Pa/m
    turbulent ≈ 9.72 × laminar（v_s² 项主导）✓
    Re_p = 1000 · 1 · 0.5e-3 / 1e-3 / 0.6 ≈ 833.3（接近上限 1000）

例 3（ε=0 或 ε=1）：

    raise ErgunInputError（床层空隙率必须在 (0, 1) 严格开区间）

P6-OPEN-001（G-01 degraded）决议：禁止 import fluids.filtration，
本模块采用自研兜底（参照 ADR-0030 V1.2 决策 7）。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.exceptions import PcsError


@dataclass(frozen=True)
class ErgunInput:
    """Ergun 方程输入（§3.2.7 第三项）。

    字段：

    - ``superficial_velocity``：v_s（m/s，≥0）
    - ``bed_porosity``：ε（无量纲，严格 (0, 1)）
    - ``particle_diameter``：dp（m，>0）
    - ``fluid_viscosity``：μ（Pa·s，>0）
    - ``fluid_density``：ρ（kg/m³，>0）
    - ``bed_length``：L（m，>0）
    """

    superficial_velocity: float
    bed_porosity: float
    particle_diameter: float
    fluid_viscosity: float
    fluid_density: float
    bed_length: float


@dataclass(frozen=True)
class ErgunResult:
    """Ergun 方程输出（§3.2.7）。

    字段：

    - ``pressure_drop``：ΔP（Pa）
    - ``pressure_drop_per_length``：ΔP / L（Pa/m）
    - ``reynolds_particle``：Re_p = ρ · v_s · dp / μ / (1−ε)（无量纲）
    - ``laminar_term``：150 · μ · (1−ε)² / ε³ · v_s / dp²（Pa/m）
    - ``turbulent_term``：1.75 · ρ · (1−ε) / ε³ · v_s² / dp（Pa/m）
    - ``formula_ref``：公式溯源标记，恒等于 "ERGUN_§3.2.7"
    """

    pressure_drop: float
    pressure_drop_per_length: float
    reynolds_particle: float
    laminar_term: float
    turbulent_term: float
    formula_ref: str = "ERGUN_§3.2.7"


class ErgunInputError(PcsError):
    """Ergun 方程输入不合法（422）。

    触发场景：

    - bed_porosity ∉ (0, 1) 严格开区间
    - particle_diameter / fluid_viscosity / fluid_density / bed_length 非正
    - superficial_velocity < 0
    """

    code = "ERGUN_INPUT_ERROR"
    status = 422


def calc_ergun_pressure_drop(inp: ErgunInput) -> ErgunResult:
    """Ergun 方程床层压降计算（§3.2.7 第三项）。

    公式：

    .. code-block:: text

        ΔP/L = 150·μ·(1−ε)²/ε³·v_s/dp² + 1.75·ρ·(1−ε)/ε³·v_s²/dp

    实现步骤：

    1. 输入校验：ε ∈ (0, 1) 严格开区间；dp / μ / ρ / L > 0；v_s ≥ 0
    2. 计算层流项 laminar = 150 · μ · (1−ε)² / ε³ · v_s / dp²
    3. 计算紊流项 turbulent = 1.75 · ρ · (1−ε) / ε³ · v_s² / dp
    4. ΔP / L = laminar + turbulent
    5. ΔP = (ΔP / L) · L
    6. Re_p = ρ · v_s · dp / μ / (1−ε)

    Args:
        inp: ErgunInput（已冻结 dataclass）。

    Returns:
        ErgunResult（含 ΔP / ΔP/L / Re_p / 两分量）。

    Raises:
        ErgunInputError: 输入字段越界或非正（422）。
    """
    if inp.bed_porosity <= 0 or inp.bed_porosity >= 1:
        raise ErgunInputError(
            f"bed_porosity ({inp.bed_porosity}) 必须在 (0, 1) 严格开区间"
        )
    if inp.particle_diameter <= 0:
        raise ErgunInputError(
            f"particle_diameter ({inp.particle_diameter}) 必须 > 0"
        )
    if inp.fluid_viscosity <= 0:
        raise ErgunInputError(
            f"fluid_viscosity ({inp.fluid_viscosity}) 必须 > 0"
        )
    if inp.fluid_density <= 0:
        raise ErgunInputError(
            f"fluid_density ({inp.fluid_density}) 必须 > 0"
        )
    if inp.bed_length <= 0:
        raise ErgunInputError(
            f"bed_length ({inp.bed_length}) 必须 > 0"
        )
    if inp.superficial_velocity < 0:
        raise ErgunInputError(
            f"superficial_velocity ({inp.superficial_velocity}) 必须 ≥ 0"
        )

    eps = inp.bed_porosity
    one_minus_eps = 1.0 - eps
    eps_cubed = eps ** 3

    # 层流项（粘性损失）— 150 · μ · (1−ε)² / ε³ · v_s / dp²
    laminar = (
        150.0
        * inp.fluid_viscosity
        * (one_minus_eps ** 2)
        / eps_cubed
        * inp.superficial_velocity
        / (inp.particle_diameter ** 2)
    )

    # 紊流项（惯性损失）— 1.75 · ρ · (1−ε) / ε³ · v_s² / dp
    turbulent = (
        1.75
        * inp.fluid_density
        * one_minus_eps
        / eps_cubed
        * (inp.superficial_velocity ** 2)
        / inp.particle_diameter
    )

    dp_per_L = laminar + turbulent
    dp = dp_per_L * inp.bed_length

    # 颗粒雷诺数（用于边界判定，Ergun 适用范围 0.001~1000）
    re_p = (
        inp.fluid_density
        * inp.superficial_velocity
        * inp.particle_diameter
        / inp.fluid_viscosity
        / one_minus_eps
    )

    return ErgunResult(
        pressure_drop=dp,
        pressure_drop_per_length=dp_per_L,
        reynolds_particle=re_p,
        laminar_term=laminar,
        turbulent_term=turbulent,
    )


__all__ = [
    "ErgunInput",
    "ErgunResult",
    "ErgunInputError",
    "calc_ergun_pressure_drop",
]