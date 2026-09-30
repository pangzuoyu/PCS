"""热虹吸循环安装高度计算 service（P5-0-1b T1 / SUP-010 §3.5）。

卧式 / 立式热虹吸蒸汽发生器（自循环）壳程压力平衡，求汽包与蒸汽发生器之间的
标高差 Hx 与最终安装高度 Hxo。数据来源 132汽包安装高度计算(2014.6.12).xls
（6 sheet），见 SUP-010 §2.1.3 gap 分析。

===== 物理模型（GPSA §20.4 壳程压力平衡；XLS P11 / P12 两项式）=====

自然循环热虹吸：汽包液柱与壳程两相流柱的密度差产生驱动压头，管线与壳程的
摩阻消耗该压头。XLS 把每段摩阻拆成「常数项 + 随 Hx 线性增长项」两项：

    损失（m 液柱）= P11 + P12 · Hx

驱动压头（以汽包液柱 m 计量）：

    驱动（m）= (ρ_drum - ρ_shell) / ρ_drum · Hx

平衡（驱动 = 损失）：

    Hx · [ (ρ_drum - ρ_shell)/ρ_drum - ΣP12 ] = ΣP11
    ⇒ Hx = ΣP11 / [ (ρ_drum - ρ_shell)/ρ_drum - ΣP12 ]

分母 ≤ 0 表示「驱动压头增长率 ≤ 摩阻增长率」——无论 Hx 取多大都不能建立
自然循环（几何/密度配置不成立），此时抛错而非返回 ∞。

===== P11 溯源（已对 XLS 数值独立复算）=====

入口管线单相段 Darcy 摩阻（以参考液柱 m 计量）：

    P11 = f · (L_eq / D_i) · v² / (2g)

用 SUP-010 §3.5 转录的 XLS 入口参数（f=0.008015、L=97.4 m、D=0.25 m、
v=2.6377 m/s、g=9.81）复算得 1.10759 m，XLS P11 = 1.1074 m，偏差 0.017%
（XLS 参数为 4~5 位有效数字舍入，偏差在舍入量级内）——公式结构确认。

出口管线为两相流、壳程为沸腾区，XLS 用各自的关联式算 P11；本 service 不
重建这两套关联式，**由调用方传入 XLS 算出的 P11 / P12**
（对应 SUP-010 §3.5 JSONB 的 pressure_drop_const / pressure_drop_coeff）。
这样 service 只负责「平衡求解」，物理关联式归属 XLS / 工艺室，避免在
PCS 内复制一套未经评审的两相流关联式。

===== 单位约定（工艺室 §5.2）=====

service / dataclass 层字段名带显式单位后缀（_m / _kg_m3 / _m_per_s /
_kg_per_h / _c）；DDL 列名保留 SUP-010 §3.5 逐字命名（不带后缀）。

不做：
- 不重建出口两相流 / 壳程沸腾区关联式（XLS / 工艺室职责）
- 不做立式 Martinelli Xtt / φ 计算（XLS 立式 2 sheet 职责；结果经
  circulation_drive_ratio 与 other_params 承载）
- 不落库（thermosiphon_persist_service 负责）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError

# ---------- 类型别名 ----------

CirculationType = Literal["HORIZONTAL", "VERTICAL"]
CheckResult = Literal["PASS", "FAIL"]

# ---------- 物理常量 ----------

#: 标准重力加速度 m/s²（工程惯例 9.81；XLS 复算用同值）
_G: Final[float] = 9.81

#: SUP-010 §3.5 声明的默认安全余量倍数
_DEFAULT_SAFETY_FACTOR: Final[float] = 1.5

#: 绝对零度 °C（drum_temperature_c 下界校验用）
_ABSOLUTE_ZERO_C: Final[float] = -273.15


# ---------- 异常 ----------


class ThermosiphonCirculationError(PcsError):
    """热虹吸循环安装高度计算输入不合法 / 无解（422）。"""

    code = "THERMOSIPHON_INPUT_ERROR"
    status = 422


# ---------- 公式溯源 ----------


@dataclass(frozen=True)
class ThermosiphonFormulaRef:
    """公式溯源（对齐 P5-0 sibling 的 formula_ref 结构化契约）。"""

    standard: str
    version: str
    clause: str
    source: str


# ---------- 输入 ----------


@dataclass(frozen=True)
class ThermosiphonCirculationInput:
    """热虹吸循环安装高度计算输入（frozen；单位后缀显式，工艺室 §5.2）。

    几何与物性：
      - circulation_type: HORIZONTAL / VERTICAL
      - shell_diameter_m: 壳程直径 Ds（m）
      - drum_diameter_m: 汽包直径（m）
      - drum_liquid_level_m: 汽包液位高 H1（m）
      - drum_liquid_density_kg_m3: 汽包内液体密度 ρ_drum（kg/m³）
      - shell_avg_density_kg_m3: 壳程两相流平均密度 ρ_shell（kg/m³）
      - drum_temperature_c: 汽包液体温度（°C；仅溯源 + 下界校验）

    阻力项（XLS P11 / P12；m 液柱 与 m/m）：
      - inlet_pressure_drop_const_m / inlet_pressure_drop_coeff
      - outlet_pressure_drop_const_m / outlet_pressure_drop_coeff
      - shell_pressure_drop_const_m / shell_pressure_drop_coeff

    余量：
      - safety_factor: 最终安装高度倍数（默认 1.5，SUP-010 §3.5）
    """

    circulation_type: CirculationType
    shell_diameter_m: float
    drum_diameter_m: float
    drum_liquid_level_m: float
    drum_liquid_density_kg_m3: float
    shell_avg_density_kg_m3: float
    drum_temperature_c: float = 0.0
    inlet_pressure_drop_const_m: float = 0.0
    inlet_pressure_drop_coeff: float = 0.0
    outlet_pressure_drop_const_m: float = 0.0
    outlet_pressure_drop_coeff: float = 0.0
    shell_pressure_drop_const_m: float = 0.0
    shell_pressure_drop_coeff: float = 0.0
    safety_factor: float = _DEFAULT_SAFETY_FACTOR


# ---------- 输出 ----------


@dataclass(frozen=True)
class ThermosiphonCirculationResult:
    """热虹吸循环安装高度计算结果（frozen）。"""

    installation_height_calc_m: float
    installation_height_final_m: float
    driving_coeff_per_m: float
    resistance_const_m: float
    resistance_coeff_per_m: float
    circulation_drive_ratio: float
    check_result: CheckResult
    formula_ref: ThermosiphonFormulaRef


# ---------- 沿程摩阻辅助（单相段，可独立验证）----------


def pipe_friction_head_m(
    *,
    friction_factor: float,
    equivalent_length_m: float,
    inner_diameter_m: float,
    velocity_m_per_s: float,
) -> float:
    """单相管线 Darcy 摩阻（以参考液柱 m 计量）。

    P11 = f · (L_eq / D_i) · v² / (2g)

    用于入口管线（单相）。出口两相流与壳程沸腾区用 XLS 各自关联式，
    不由本函数代算（见模块 docstring「不做」段）。

    Raises:
        ThermosiphonCirculationError: 任一参数 ≤ 0。
    """
    if friction_factor <= 0:
        raise ThermosiphonCirculationError(
            f"friction_factor={friction_factor} 必须 > 0"
        )
    if equivalent_length_m <= 0:
        raise ThermosiphonCirculationError(
            f"equivalent_length_m={equivalent_length_m} 必须 > 0"
        )
    if inner_diameter_m <= 0:
        raise ThermosiphonCirculationError(
            f"inner_diameter_m={inner_diameter_m} 必须 > 0"
        )
    if velocity_m_per_s <= 0:
        raise ThermosiphonCirculationError(
            f"velocity_m_per_s={velocity_m_per_s} 必须 > 0（零流量无自然循环）"
        )
    return (
        friction_factor
        * (equivalent_length_m / inner_diameter_m)
        * (velocity_m_per_s**2)
        / (2.0 * _G)
    )


# ---------- 校验 ----------


def _validate(inp: ThermosiphonCirculationInput) -> None:
    """输入校验（全部越界 → ThermosiphonCirculationError → 422）。"""
    if inp.circulation_type not in ("HORIZONTAL", "VERTICAL"):
        raise ThermosiphonCirculationError(
            f"circulation_type={inp.circulation_type} 必须是 HORIZONTAL / VERTICAL"
        )
    if inp.shell_diameter_m <= 0:
        raise ThermosiphonCirculationError(
            f"shell_diameter_m={inp.shell_diameter_m} 必须 > 0"
        )
    if inp.drum_diameter_m <= 0:
        raise ThermosiphonCirculationError(
            f"drum_diameter_m={inp.drum_diameter_m} 必须 > 0"
        )
    if inp.drum_liquid_level_m < 0:
        raise ThermosiphonCirculationError(
            f"drum_liquid_level_m={inp.drum_liquid_level_m} 必须 >= 0"
        )
    if inp.drum_liquid_density_kg_m3 <= 0:
        raise ThermosiphonCirculationError(
            f"drum_liquid_density_kg_m3={inp.drum_liquid_density_kg_m3} 必须 > 0"
        )
    if inp.shell_avg_density_kg_m3 <= 0:
        raise ThermosiphonCirculationError(
            f"shell_avg_density_kg_m3={inp.shell_avg_density_kg_m3} 必须 > 0"
        )
    if inp.drum_temperature_c <= _ABSOLUTE_ZERO_C:
        raise ThermosiphonCirculationError(
            f"drum_temperature_c={inp.drum_temperature_c} 低于绝对零度 "
            f"{_ABSOLUTE_ZERO_C} °C，物理不可能"
        )
    if inp.safety_factor <= 0:
        raise ThermosiphonCirculationError(
            f"safety_factor={inp.safety_factor} 必须 > 0"
        )
    for name in (
        "inlet_pressure_drop_const_m",
        "outlet_pressure_drop_const_m",
        "shell_pressure_drop_const_m",
    ):
        value = getattr(inp, name)
        if value < 0:
            raise ThermosiphonCirculationError(f"{name}={value} 必须 >= 0")
    for name in (
        "inlet_pressure_drop_coeff",
        "outlet_pressure_drop_coeff",
        "shell_pressure_drop_coeff",
    ):
        value = getattr(inp, name)
        if value < 0:
            raise ThermosiphonCirculationError(f"{name}={value} 必须 >= 0")


# ---------- 主入口 ----------


def calc_thermosiphon_circulation(
    inp: ThermosiphonCirculationInput,
) -> ThermosiphonCirculationResult:
    """热虹吸循环安装高度计算（壳程压力平衡，SUP-010 §3.5 / GPSA §20.4）。

    Hx = ΣP11 / [ (ρ_drum - ρ_shell)/ρ_drum - ΣP12 ]
    Hxo = safety_factor · Hx
    circulation_drive_ratio = 驱动压头(Hxo) / 总损失(Hxo)；>= 1 → PASS

    Raises:
        ThermosiphonCirculationError: 输入越界，或分母 <= 0（无解：驱动压头
            增长率不超摩阻增长率，任意 Hx 都不能建立自然循环）。
    """
    _validate(inp)

    resistance_const_m = (
        inp.inlet_pressure_drop_const_m
        + inp.outlet_pressure_drop_const_m
        + inp.shell_pressure_drop_const_m
    )
    resistance_coeff_per_m = (
        inp.inlet_pressure_drop_coeff
        + inp.outlet_pressure_drop_coeff
        + inp.shell_pressure_drop_coeff
    )
    # 驱动压头梯度（每米 Hx 产生的 m 液柱驱动压头）
    driving_coeff_per_m = (
        inp.drum_liquid_density_kg_m3 - inp.shell_avg_density_kg_m3
    ) / inp.drum_liquid_density_kg_m3

    if driving_coeff_per_m <= 0:
        raise ThermosiphonCirculationError(
            f"壳程平均密度 {inp.shell_avg_density_kg_m3} kg/m³ >= 汽包液体密度 "
            f"{inp.drum_liquid_density_kg_m3} kg/m³，无密度驱动压头，自然循环不成立"
        )

    denominator = driving_coeff_per_m - resistance_coeff_per_m
    if denominator <= 0:
        raise ThermosiphonCirculationError(
            f"平衡式无解：驱动梯度 {driving_coeff_per_m:.6f} m/m <= 摩阻梯度 "
            f"{resistance_coeff_per_m:.6f} m/m，任意安装高度都不能建立自然循环"
        )

    if resistance_const_m <= 0:
        raise ThermosiphonCirculationError(
            f"ΣP11={resistance_const_m} m 必须 > 0（无阻力项则平衡式退化为 Hx=0）"
        )

    height_calc_m = resistance_const_m / denominator
    height_final_m = height_calc_m * inp.safety_factor

    # 在最终安装高度上复核推动力 / 总压降比
    drive_at_final = driving_coeff_per_m * height_final_m
    resistance_at_final = resistance_const_m + resistance_coeff_per_m * height_final_m
    drive_ratio = drive_at_final / resistance_at_final
    check: CheckResult = "PASS" if drive_ratio >= 1.0 else "FAIL"

    return ThermosiphonCirculationResult(
        installation_height_calc_m=height_calc_m,
        installation_height_final_m=height_final_m,
        driving_coeff_per_m=driving_coeff_per_m,
        resistance_const_m=resistance_const_m,
        resistance_coeff_per_m=resistance_coeff_per_m,
        circulation_drive_ratio=drive_ratio,
        check_result=check,
        formula_ref=ThermosiphonFormulaRef(
            standard="GPSA",
            version="20.4",
            clause="Thermosiphon Circulation / Shell-side Pressure Balance",
            source=(
                "XLS 132汽包安装高度计算(2014.6.12) P11/P12 两项式；"
                "SUP-010 §3.5"
            ),
        ),
    )


__all__ = [
    "CirculationType",
    "CheckResult",
    "ThermosiphonCirculationError",
    "ThermosiphonFormulaRef",
    "ThermosiphonCirculationInput",
    "ThermosiphonCirculationResult",
    "pipe_friction_head_m",
    "calc_thermosiphon_circulation",
]
