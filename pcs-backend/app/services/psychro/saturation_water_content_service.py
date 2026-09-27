"""饱和水含量 service（P6-4 C-17 / SPEC §3.2.5 P6-PSY-001）。

按 SPEC §3.2.5 计算饱和湿空气水含量（RH=1.0）：

- 核心算法：``chedl_wrapper.humid_air_humidity_ratio(T_K, RH=1.0, P_pa)`` —
  直调 CoolProp.HumidAirProp.HAPropsSI（ADR-0030 V1.2 G-02 锁定包装层）。
  饱和 W 定义即 RH=1.0 时的湿度比；**不**新增 wrapper 函数（ADR-0030 决策 6）。
- D14 性能优化：``@functools.lru_cache(maxsize=4096)`` 缓存 4096 个
  (T, P, acid_gas_composition) 组合（饱和 W 计算频繁；项目典型工况覆盖）。
- 3 独立单位输出（不混用）：
  - saturation_w_kg_kg: kg 水 / kg 干空气（摩尔比基础；无量纲）
  - saturation_w_mg_sm3: mg 水 / Sm³ 干空气（标准立方米；西欧常用）
  - saturation_w_lb_per_mmscf: lb 水 / MMscf 干空气（北美工程常用）
- 酸性气校正（ISO 18453 简式）：CO2/H2S > 40 mol% 时按 ISO 18453 简式校正
  系数 < 1.05（SPEC §3.2.5 §3.9.2 酸性气处理路径；纯工况可关）。
- 温度越界：< -50°C 或 > 100°C 返回 WARNING（不抛错；response 标
  ``temperature_out_of_range``；SPEC §3.2.5 安全范围约定）。
- 公式版本标记：``SATURATION_W_v1.0-p6-4-task4``（与 psychro_persist 体系对齐）。

**适用范围（Scope，OPEN-P6-6A-1 / Ruling 9 wording formalization）**：

本 service **仅适用于湿空气**（~79% N₂ + 21% O₂ + 微量 CO₂/Ar，工作流
体 dry air）。算法基于 ASHRAE RP-1845 / CoolProp HAPropsSI，输出三档
单位均为 **dry air 基准**（kg 水 / kg 干空气 / mg/Sm³ 干空气 / lb/MMscf
干空气）。

**不适用于（OUT OF SCOPE，Ruling 9 working fluid defect）**：

- 天然气 / 烃类气体饱和水含量 —— 应使用 Behr 相关式（McKetta-Wehe /
  Carson-Davis / GPSA Fig. 20-XX 系列），分母是 wet gas 而非 dry air，
  算法族与本 service 不同。
- 强公式 0.1% 容差不适用于 Behr vs HAPropsSI 跨算法对比 —— P6-6A
  T9 对账显示两者在典型工况下偏差 10-30%（非 0.1%）。

**Ruling 9 三层注册**（P6-6A 批 9 Ruling 登记）：

- mapping_defect.ruling_id = ``Ruling_9_working_fluid_defect_natural_gas_vs_humid_air``
- 9 项 out_of_scope：bit-for-bit value match / Behr 系数 / 酸性气校正精度 /
  wet/dry gas 语义 / Imperial/SI 双套 / T/P 限值 / 转换数据块 / 备注块
- 5 cases 对账仅验证 unit conversion EXACT + OoM band + sanity assertions

**批 B 立项评估**：落地 Behr natural gas water content 作为 PCS 新
service（``calc_behr_natural_gas_water_content``）以覆盖 XLS-PR-019 物理
范围；或维持现状仅 SPEC V1.2 注明 working fluid 差异 + 双算法族并存。
工程团队裁决（OPEN-P6-6A-6 同源）。

ashrae 黄金对账（SPEC §3.2.5 D5 三级验收）：
- 10 点 ASHRAE Fundamentals 2021 Table 1（温度 -10~80°C × 101.325 kPa）
- 强公式 ASHRAE_RP-1845_CoolProp（HAPropsSI）参考值 rel=1e-3（<0.1%）。
- fixture 路径：``tests/services/psychro/fixtures/golden_saturation_w_ashrae.json``。

注：lru_cache 包裹 dataclass 实例对象时需注意 hashability — 这里
``SaturationWaterContentInput`` 含酸性气 composition dict（unhashable），
所以 cache 必须建立在 ``_cache_key_tuple`` 上，而不是直接传 dataclass。
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field

from app.services import chedl_wrapper
from app.services.exceptions import PcsError

# 公式版本（psychro_persist_service 对齐锚点）
_FORMULA_VERSION = "SATURATION_W_v1.0-p6-4-task4"

# D14 lru_cache 大小（饱和 W 计算 4096 个 (T, P, acid_gas_composition) 组合）
_LRU_CACHE_SIZE = 4096

# 温度安全范围（SPEC §3.2.5 §3.9.2 约定）
_T_MIN_C = -50.0
_T_MAX_C = 100.0

# CoolProp.HumidAirProp.HAPropsSI 有效域（工程约束；约 ~100 atm 上限）。
# 100 atm ≈ 1.01325e7 Pa ≈ 1470 psia；2000 psia（13.79 MPa）超出。
_P_MAX_PA = 1.01325e7

# 酸性气校正阈值（CO2 + H2S 摩尔分率；SPEC §3.2.5 §3.9.2 注释）
_ACID_GAS_THRESHOLD = 0.40

# 酸性气校正系数上限（ISO 18453 简式；防止异常放大）
_ACID_GAS_CORR_MAX = 1.05

# 标准干空气密度（kg/Sm³；0°C 101.325 kPa 下；用于 mg/Sm³ 与 kg/kg 换算）
# ASHRAE Fundamentals 2021 §1.1 给出 1.2923 kg/Sm³（标准干空气）。
_STANDARD_DRY_AIR_DENSITY_KG_SM3 = 1.2923

# 单位换算常数（lb water / MMscf dry air ↔ mg/Sm³ dry air）：
#   1 lb = 453.59237 g
#   1 m³ = 35.3146667215 ft³
#   1 MMscf = 1e6 scf
#   → 1 mg/Sm³ = 1e-3 g/m³ = (1e-3 / 453.59237) lb/m³
#     × (1 m³ / 35.3146667215 ft³) × 1e6 scf/MMscf
#     = (1e-3 × 1e6) / (453.59237 × 35.3146667215)
#     = 1000 / 16018.466...
#     ≈ 0.062428 lb/MMscf per mg/Sm³
_MG_SM3_TO_LB_PER_MMSCF = 0.062428

# 压力单位（chedl_wrapper 接受 Pa；input 接收 kPa）
_KPA_TO_PA = 1000.0


class SaturationWaterContentInputError(PcsError):
    """饱和水含量输入不合法（422）。

    触发场景：
    - temperature_c < -273.15（绝对零度以下；物理不可达）
    - pressure_kpa <= 0（非正压力）
    """

    code = "SATURATION_W_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class SaturationWaterContentInput:
    """饱和水含量输入（frozen=True 确保 lru_cache key 稳定）。

    字段：
    - temperature_c: 干球温度 °C（SPEC §3.2.5；范围 -50~100°C，超界返 WARNING）
    - pressure_kpa: 大气压力 kPa（默认 101.325；> 0）
    - acidic_gas_composition: 酸性气摩尔分率 dict（默认空）；
      ISO 18453 简式校正仅在 CO2+H2S > 40 mol% 时触发
    - units: 单位制（"METRIC" SI 制 / "IMPERIAL" 英制；不影响算法，仅影响入参约定）
    """

    temperature_c: float
    pressure_kpa: float = 101.325
    acidic_gas_composition: dict[str, float] = field(default_factory=dict)
    units: str = "METRIC"

    def __post_init__(self) -> None:
        # 物理极值（绝对零度以下 / 非正压力）— 业务层越界（-50/100°C）放行，
        # 仅 WARNING。
        if self.temperature_c < -273.15:
            raise SaturationWaterContentInputError(
                f"temperature_c={self.temperature_c} 低于绝对零度"
            )
        if self.pressure_kpa <= 0.0:
            raise SaturationWaterContentInputError(
                f"pressure_kpa={self.pressure_kpa} 必须正数"
            )
        if self.units not in ("METRIC", "IMPERIAL"):
            raise SaturationWaterContentInputError(
                f"units={self.units!r} 仅支持 METRIC/IMPERIAL"
            )

    def cache_key(self) -> tuple:
        """生成 lru_cache key 用的 hashable tuple。

        注意：lru_cache **不**直接 cache dataclass 实例（dataclass 已 frozen
        可 hash，但 dict 默认 unhashable）。手动转 frozenset(items) 保证 hashable。
        """
        return (
            float(self.temperature_c),
            float(self.pressure_kpa),
            frozenset(self.acidic_gas_composition.items()),
            self.units,
        )


@dataclass(frozen=True)
class SaturationWaterContentResult:
    """饱和水含量结果（frozen=True）。

    字段：
    - saturation_w_kg_kg: kg 水 / kg 干空气（基础摩尔比；无量纲）
    - saturation_w_mg_sm3: mg 水 / Sm³ 干空气（西欧常用）
    - saturation_w_lb_per_mmscf: lb 水 / MMscf 干空气（北美常用）
    - saturation_T_c: 计算时实际使用的干球温度 °C
    - temperature_out_of_range: True/False（< -50°C 或 > 100°C）
    - warning_message: 越界警告（None 表示无警告）
    - acidic_gas_correction_applied: True/False（CO2+H2S > 40 mol%）
    - acidic_gas_correction_factor: ISO 18453 简式校正系数（默认 1.0）
    - formula_ref: 公式溯源标记 "ASHRAE_RP-1845_CoolProp"
    """

    saturation_w_kg_kg: float
    saturation_w_mg_sm3: float
    saturation_w_lb_per_mmscf: float
    saturation_T_c: float
    temperature_out_of_range: bool
    warning_message: str | None
    acidic_gas_correction_applied: bool
    acidic_gas_correction_factor: float
    formula_ref: str


def _iso_18453_correction(
    composition: dict[str, float],
) -> tuple[float, bool]:
    """ISO 18453 酸性气简式校正（CO2 + H2S 摩尔分率）。

    简化模型：当 (CO2 + H2S) 摩尔分率 > 40% 时，校正系数
        f = 1 + 0.05 × (x_CO2 + x_H2S - 0.40) / 0.60
    上限 1.05（SPEC §3.2.5 §3.9.2 约束）。

    Args:
        composition: 摩尔分率 dict（如 {"CO2": 0.30, "H2S": 0.20}）。

    Returns:
        (correction_factor, applied) — 校正系数与是否实际应用标记。
        未达阈值时返回 (1.0, False)；达到阈值时返回 (f, True)。
    """
    if not composition:
        return (1.0, False)
    x_co2 = float(composition.get("CO2", 0.0))
    x_h2s = float(composition.get("H2S", 0.0))
    x_acid = x_co2 + x_h2s
    if x_acid <= _ACID_GAS_THRESHOLD:
        return (1.0, False)
    # 线性插值（40% → 1.0；100% → 1.05）
    raw = 1.0 + 0.05 * (x_acid - _ACID_GAS_THRESHOLD) / (
        1.0 - _ACID_GAS_THRESHOLD
    )
    factor = min(raw, _ACID_GAS_CORR_MAX)
    return (factor, True)


def _to_unit_outputs(w_kg_kg: float) -> tuple[float, float]:
    """kg/kg → (mg/Sm³, lb/MMscf) 双换算（独立字段；不混用）。

    公式（SPEC §3.2.5 §3.9.2）：
        mg/Sm³ = W (kg/kg) × ρ_dry_air (kg/Sm³) × 1e6 (mg/kg)
        lb/MMscf = mg/Sm³ × 0.062428

    Returns:
        (w_mg_sm3, w_lb_per_mmscf)
    """
    w_mg_sm3 = w_kg_kg * _STANDARD_DRY_AIR_DENSITY_KG_SM3 * 1.0e6
    w_lb_per_mmscf = w_mg_sm3 * _MG_SM3_TO_LB_PER_MMSCF
    return (w_mg_sm3, w_lb_per_mmscf)


@functools.lru_cache(maxsize=_LRU_CACHE_SIZE)
def _calc_saturation_w_cached(
    temperature_c: float,
    pressure_kpa: float,
    acid_gas_key: frozenset,
) -> float:
    """饱和水含量计算（lru_cache 内部 helper）。

    饱和 W = RH=1.0 时的 humidity_ratio（直调 chedl_wrapper）：
        W_sat_kg_kg = chedl_wrapper.humid_air_humidity_ratio(
            T_K = T_c + 273.15, RH = 1.0, P_pa = P_kpa × 1000
        )

    cache key 包含全部输入参数（temperature_c / pressure_kpa /
    acidic_gas_composition frozen items），避免 hash 冲突。

    Args:
        temperature_c: 干球温度 °C。
        pressure_kpa: 大气压力 kPa。
        acid_gas_key: frozenset(composition.items)；unhashable dict 的 hash 替身。

    Returns:
        饱和水含量 kg/kg dry air。
    """
    del acid_gas_key  # 仅用于 cache key；计算本身用 chedl_wrapper 不读该字段
    t_k = temperature_c + 273.15
    p_pa = pressure_kpa * _KPA_TO_PA
    return chedl_wrapper.humid_air_humidity_ratio(t_k, 1.0, p_pa)


def calc_saturation_water_content(
    inp: SaturationWaterContentInput,
) -> SaturationWaterContentResult:
    """饱和水含量 service 入口（SPEC §3.2.5 P6-PSY-001 显式 W_sat）。

    流程：
        1. 温度越界检查（-50~100°C；超界 → WARNING，不抛错）
        2. ISO 18453 酸性气简式校正（CO2+H2S > 40 mol%）
        3. 直调 ``chedl_wrapper.humid_air_humidity_ratio(T, RH=1.0, P)``
        4. 应用校正系数（默认 1.0）
        5. 三单位换算（kg/kg / mg/Sm³ / lb/MMscf）
        6. 组装 result dataclass

    注：核心计算走 ``_calc_saturation_w_cached``（lru_cache 4096）；
    校正/换算在 cache 之外应用（保持 cache 命中无副作用）。

    注：CoolProp.HumidAirProp 在温压越界（如 T = 100°C × 101.325 kPa 时
    x_w=1.00092 > CoolProp 上限 0.94145）抛 ``ValueError``；service 层捕获
    并以 ``NaN`` + 强 WARNING 表达（SPEC §3.2.5 "WARNING，不抛错" 约定）。
    物理极值越界（T<-273.15 / P<=0）由 SCHEMA 层先拦，service 不抛错。

    Args:
        inp: 饱和水含量输入。

    Returns:
        SaturationWaterContentResult（frozen；含 3 单位 + 越界标记 +
        酸性气校正标记 + 公式溯源；越界且 CoolProp 拒绝时 3 单位为 NaN）。
    """
    out_of_range = (
        inp.temperature_c < _T_MIN_C or inp.temperature_c > _T_MAX_C
        or (inp.pressure_kpa * _KPA_TO_PA) > _P_MAX_PA
    )
    warning_message: str | None = None
    if out_of_range:
        warning_message = (
            f"temperature_c={inp.temperature_c} / pressure_kpa="
            f"{inp.pressure_kpa} 超出 SPEC §3.2.5 安全范围 "
            f"[T={_T_MIN_C}~{_T_MAX_C}°C, P<=~100 atm]；"
            "CoolProp 结果仅参考"
        )

    # 酸性气校正（ISO 18453 简式）
    acid_factor, acid_applied = _iso_18453_correction(
        inp.acidic_gas_composition
    )

    # 核心计算（lru_cache 缓存 4096 个 (T, P, composition) 组合）
    acid_key = frozenset(inp.acidic_gas_composition.items())
    try:
        w_raw = _calc_saturation_w_cached(
            inp.temperature_c, inp.pressure_kpa, acid_key
        )
    except ValueError as e:
        # CoolProp 拒绝计算（温压超出 HAPropsSI 有效域；如 100°C × 1 atm
        # 时 x_w=1.00092 > CoolProp 上限 0.94145；SPEC §3.2.5 "不抛错" 约定）：
        # 吞下异常并以 NaN + 增强 WARNING 表达。所有 ValueError 都按此处理
        # （SCHEMA 层已拦截 T<-273.15/P<=0 等真正非法输入；此处 ValueError
        # 都是 CoolProp 域内边界问题）。
        warning_message = (
            f"{warning_message or ''} | CoolProp 拒绝计算"
            f"（HAPropsSI 越界）：{e}"
        ).lstrip(" |")
        nan = float("nan")
        return SaturationWaterContentResult(
            saturation_w_kg_kg=nan,
            saturation_w_mg_sm3=nan,
            saturation_w_lb_per_mmscf=nan,
            saturation_T_c=inp.temperature_c,
            temperature_out_of_range=out_of_range,
            warning_message=warning_message,
            acidic_gas_correction_applied=acid_applied,
            acidic_gas_correction_factor=acid_factor,
            formula_ref="ASHRAE_RP-1845_CoolProp",
        )
    w_corrected = w_raw * acid_factor

    w_mg_sm3, w_lb_per_mmscf = _to_unit_outputs(w_corrected)

    return SaturationWaterContentResult(
        saturation_w_kg_kg=w_corrected,
        saturation_w_mg_sm3=w_mg_sm3,
        saturation_w_lb_per_mmscf=w_lb_per_mmscf,
        saturation_T_c=inp.temperature_c,
        temperature_out_of_range=out_of_range,
        warning_message=warning_message,
        acidic_gas_correction_applied=acid_applied,
        acidic_gas_correction_factor=acid_factor,
        formula_ref="ASHRAE_RP-1845_CoolProp",
    )


def calc_saturation_water_content_metric(
    temperature_c: float,
    pressure_kpa: float = 101.325,
    acidic_gas_composition: dict[str, float] | None = None,
) -> SaturationWaterContentResult:
    """饱和水含量便捷入口（公制 SI；T_c + P_kpa 直传）。

    Imperial 工程常用入口在调用方自行把 T_F 换 °C、P_psia 换 kPa 后调用本函数。
    本函数不做单位换算（确保数值一致性）；单位制约定由 schema 层标注。

    Args:
        temperature_c: 干球温度 °C。
        pressure_kpa: 大气压力 kPa。
        acidic_gas_composition: 酸性气摩尔分率 dict（None → 无校正）。

    Returns:
        SaturationWaterContentResult（公制）。
    """
    return calc_saturation_water_content(
        SaturationWaterContentInput(
            temperature_c=temperature_c,
            pressure_kpa=pressure_kpa,
            acidic_gas_composition=acidic_gas_composition or {},
            units="METRIC",
        )
    )


__all__ = [
    "SaturationWaterContentInput",
    "SaturationWaterContentResult",
    "SaturationWaterContentInputError",
    "calc_saturation_water_content",
    "calc_saturation_water_content_metric",
]


# 显式版本 / cache 信息（用于运维 + 测试断言）
calc_saturation_water_content._formula_version = _FORMULA_VERSION  # type: ignore[attr-defined]
calc_saturation_water_content._lru_cache_size = _LRU_CACHE_SIZE  # type: ignore[attr-defined]