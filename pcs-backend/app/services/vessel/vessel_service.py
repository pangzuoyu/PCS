"""P5-1 vessel_service（Souders-Brown + 流体力学）。

按 ADR-0032 V1.0 + PCS-PLAN-P5-DEVICE-EQUIPMENT.md §136-163：
- ChEDL 分层（业务代码禁直接 import fluids，统一 chedl_wrapper）
- K 因子单位约定 SI m/s
- 停留时间按 vessel_type 分支（vertical=3~5 min / horizontal=5~10 min）
- 流体力学：排空 / 液位-容积 / 溢流 / 放空（V1.9 F-13-5 双套测试 pattern）
- 纯函数不触 DB（P5-1-4 才落库）
- 输入/输出均为 frozen dataclass（不可变 + 可哈希）

公式：
  V_max = K × √((ρ_L - ρ_V) / ρ_V)        [Souders-Brown, m/s]
  D_min = √(4 × Q_v / (π × V_max))         [m]
  V_liq = Q_L × t_residence                [m³]
  t_empty = (A_tank / (Cd · A_orifice)) · √(2·h0/g)   [重力排空积分结果, s]
  Q_overflow = Cd · A_overflow · √(2·g·h_overflow)   [溢流口出流, m³/s]

与 ChEDL `fluids.separator.v_Souders_Brown(K, rhol, rhog)` 交叉验证 ≤1%。
fluids 1.3.1 不提供 time_to_empty / tank_level_to_volume，包装层 fallback 自研（V1.9 F-13-5）。
"""
from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass
from typing import Final, Literal

from app.services import chedl_wrapper
from app.services.exceptions import PcsError

# 类型别名
VesselType = Literal["VERTICAL", "HORIZONTAL", "WITH_DEMISTER"]
CheckResult = Literal["PASS", "WARNING", "FAIL"]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
# 容器方位（区分重力排空公式适用性）：
#   "vertical" — 立式，A_tank 常数（π·D²/4），t_empty 公式严格适用
#   "horizontal" — 卧式，A_tank 随 h 变化（椭圆截面），t_empty 仅供参考
VesselOrientation = Literal["vertical", "horizontal"]

# 物理常量（ISO 80000-3）
_PI: Final[float] = math.pi

# K 因子边界（SI m/s，PCS-PLAN §134 + ADR-0032 V1.1 决策 2）
_K_LOW_BOUND: Final[float] = 0.01   # 物理下限
_K_HIGH_BOUND: Final[float] = 1.0   # 物理上限
# vessel_type 子区间（开区间，边界值视为 MEDIUM 保守；影响 HIGH/MEDIUM 判定）
# ADR-0032 V1.1 OPEN-2 用户裁决（保守经典值）
_K_VERTICAL_TYPICAL: Final[tuple[float, float]] = (0.01, 0.05)        # 立式
_K_HORIZONTAL_TYPICAL: Final[tuple[float, float]] = (0.05, 0.11)      # 卧式
_K_WITH_DEMISTER_TYPICAL: Final[tuple[float, float]] = (0.04, 0.10)   # 带除沫器

# 停留时间区间（ADR-0032 决策 3，V1.6 关注项修正）
_RESIDENCE_VERTICAL_MIN_MAX: Final[tuple[float, float]] = (3.0, 5.0)
_RESIDENCE_HORIZONTAL_MIN_MAX: Final[tuple[float, float]] = (5.0, 10.0)
_RESIDENCE_WITH_DEMISTER_MIN_MAX: Final[tuple[float, float]] = (3.0, 5.0)


class VesselInputError(PcsError):
    """vessel 输入物理量不合法（422）。"""

    code = "VESSEL_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class VesselSizingInput:
    """calc_vessel_sizing 输入参数（frozen dataclass）。

    物理量 SI 单位：
      - 密度 kg/m³
      - 流量 m³/s
      - 停留时间 min
      - K 因子 m/s
    """

    vessel_type: VesselType
    rho_L_kg_m3: float
    rho_V_kg_m3: float
    liquid_flow_m3_s: float
    vapor_flow_m3_s: float
    residence_time_min: float
    K_factor_ms: float


@dataclass(frozen=True)
class VesselSizingResult:
    """calc_vessel_sizing 输出结果（frozen dataclass）。

    字段：
      - V_max_ms: 允许最大气速（Souders-Brown）
      - D_min_m: 容器最小直径（基于 V_max + Q_v 流量）
      - liquid_volume_m3: 持液量（Q_L × t_residence）
      - vessel_type: 容器类型
      - K_factor_ms: 实际使用 K 因子
      - residence_time_min: 实际使用停留时间（输入 0 时用 vessel_type 默认区间中值）
      - check_result: PASS / WARNING / FAIL
      - confidence: HIGH / MEDIUM / LOW
    """

    V_max_ms: float
    D_min_m: float
    liquid_volume_m3: float
    vessel_type: VesselType
    K_factor_ms: float
    residence_time_min: float
    check_result: CheckResult
    confidence: Confidence


def _validate_input(inp: VesselSizingInput) -> None:
    """输入物理量边界校验。"""
    if inp.liquid_flow_m3_s <= 0:
        raise VesselInputError(
            f"liquid_flow_m3_s={inp.liquid_flow_m3_s} 必须 > 0"
        )
    if inp.vapor_flow_m3_s <= 0:
        raise VesselInputError(
            f"vapor_flow_m3_s={inp.vapor_flow_m3_s} 必须 > 0"
        )
    if inp.rho_L_kg_m3 <= 0 or inp.rho_V_kg_m3 <= 0:
        raise VesselInputError(
            f"密度必须 > 0（ρ_L={inp.rho_L_kg_m3}, ρ_V={inp.rho_V_kg_m3}）"
        )
    if inp.rho_L_kg_m3 <= inp.rho_V_kg_m3:
        raise VesselInputError(
            f"ρ_L={inp.rho_L_kg_m3} 必须 > ρ_V={inp.rho_V_kg_m3}（液相比气相重）"
        )
    if not (_K_LOW_BOUND <= inp.K_factor_ms <= _K_HIGH_BOUND):
        raise VesselInputError(
            f"K_factor_ms={inp.K_factor_ms} 超出物理合理范围 "
            f"[{_K_LOW_BOUND}, {_K_HIGH_BOUND}]"
        )


def _resolve_residence_time(inp: VesselSizingInput) -> float:
    """停留时间解析：输入 0 时按 vessel_type 默认区间取中值。"""
    if inp.residence_time_min > 0:
        return inp.residence_time_min
    if inp.vessel_type == "VERTICAL":
        lo, hi = _RESIDENCE_VERTICAL_MIN_MAX
    elif inp.vessel_type == "HORIZONTAL":
        lo, hi = _RESIDENCE_HORIZONTAL_MIN_MAX
    else:  # WITH_DEMISTER
        lo, hi = _RESIDENCE_WITH_DEMISTER_MIN_MAX
    return (lo + hi) / 2.0


def _classify_K_factor(K: float, vessel_type: VesselType) -> Confidence:
    """K 因子置信度分类（vessel_type 子区间，开区间，边界 MEDIUM）。

    ADR-0032 V1.1 决策 2：vessel_type 子区间影响 HIGH/MEDIUM 判定（保守经典值）。
      - VERTICAL：(0.01, 0.05) → 子区间内 HIGH，边界值 MEDIUM
      - HORIZONTAL：(0.05, 0.11) → 同上
      - WITH_DEMISTER：(0.04, 0.10) → 同上

    Returns:
        "HIGH"：K 严格落在 vessel_type 子区间内（典型工况）
        "MEDIUM"：K 为边界值 或 子区间外但 [0.01, 1.0] 内（保守）
    """
    if vessel_type == "VERTICAL":
        lo, hi = _K_VERTICAL_TYPICAL
    elif vessel_type == "HORIZONTAL":
        lo, hi = _K_HORIZONTAL_TYPICAL
    else:  # WITH_DEMISTER
        lo, hi = _K_WITH_DEMISTER_TYPICAL
    if lo < K < hi:
        return "HIGH"
    return "MEDIUM"


def calc_vessel_sizing(inp: VesselSizingInput) -> VesselSizingResult:
    """计算容器最小直径 + 持液量。

    公式：
      V_max = K × √((ρ_L - ρ_V) / ρ_V)    [Souders-Brown]
      D_min = √(4 × Q_v / (π × V_max))     [m]
      V_liq = Q_L × t_residence            [m³]

    返回 frozen dataclass；纯函数不触 DB。

    Raises:
        VesselInputError: 输入物理量越界（密度倒置 / 流量 ≤0 / K 因子越界）。
    """
    _validate_input(inp)

    # 停留时间（输入 0 时按 vessel_type 默认区间中值）
    t_residence_min = _resolve_residence_time(inp)
    t_residence_s = t_residence_min * 60.0

    # ChEDL 分层：业务层 V_max 走 chedl_wrapper（与 ChEDL 直调交叉验证）
    v_max_chedl = chedl_wrapper.v_Souders_Brown(
        K=inp.K_factor_ms,
        rhol=inp.rho_L_kg_m3,
        rhog=inp.rho_V_kg_m3,
    )

    # 手算 V_max（与 ChEDL 交叉验证 ≤1%；实际取 ChEDL 值以保持口径一致）
    v_max_manual = inp.K_factor_ms * math.sqrt(
        (inp.rho_L_kg_m3 - inp.rho_V_kg_m3) / inp.rho_V_kg_m3
    )
    if not math.isclose(v_max_manual, v_max_chedl, rel_tol=0.01):
        raise VesselInputError(
            f"V_max 手算 {v_max_manual:.4f} vs ChEDL {v_max_chedl:.4f} 偏差 >1%"
        )

    # 容器最小直径
    d_min_m = math.sqrt(4.0 * inp.vapor_flow_m3_s / (_PI * v_max_chedl))

    # 持液量
    liquid_volume_m3 = inp.liquid_flow_m3_s * t_residence_s

    # 置信度
    confidence = _classify_K_factor(inp.K_factor_ms, inp.vessel_type)

    # check_result：基于 confidence + K 边界
    check_result: CheckResult = "PASS" if confidence == "HIGH" else "WARNING"

    return VesselSizingResult(
        V_max_ms=v_max_chedl,
        D_min_m=d_min_m,
        liquid_volume_m3=liquid_volume_m3,
        vessel_type=inp.vessel_type,
        K_factor_ms=inp.K_factor_ms,
        residence_time_min=t_residence_min,
        check_result=check_result,
        confidence=confidence,
    )


# ============================================================================
# P5-1-2 vessel 流体力学校核（fluids.tanks 排空/液位-容积/溢流/放空）
# ============================================================================


@dataclass(frozen=True)
class VesselHydraulicsInput:
    """calc_vessel_hydraulics 输入参数（frozen dataclass）。

    物理量 SI 单位：
      - 长度 m
      - 流量 m³/s
      - 无量纲 Cd（流量系数，0~1）
      - 呼吸因子 thermal_breathing_factor（API 2000 / ISO 28300）

    ⚠️ orientation 决定 t_empty 公式适用性：
      - "vertical"：严格适用（立式圆柱罐 A_tank 常数）
      - "horizontal"：仅供参考（卧式罐 A_tank 随 h 变化）
    """

    D_m: float
    L_m: float
    h0_m: float
    d_orifice_m: float
    Cd_orifice: float
    Q_in_liquid_m3_s: float
    d_overflow_m: float
    h_overflow_m: float
    Cd_overflow: float
    orientation: VesselOrientation
    thermal_breathing_factor: float = 1.0


@dataclass(frozen=True)
class VesselHydraulicsResult:
    """calc_vessel_hydraulics 输出结果（frozen dataclass）。

    字段：
      - empty_time_s: 重力排空时间估算（s，**仅 vertical 严格适用**）
      - overflow_ok: True = 进液量 < 溢流口能力；False = 溢流
      - level_volume_curve_json: 液位-容积曲线 JSON 串（11 采样点）
      - vent_capacity_m3_s: PVRV thermal breathing capacity = 1.2 × tf × V_total / 3600
      - applicable_orientation: 结果严格适用的容器方位（当前实现仅 vertical 严格）
    """

    empty_time_s: float
    overflow_ok: bool
    level_volume_curve_json: str
    vent_capacity_m3_s: float
    applicable_orientation: VesselOrientation


def _validate_hydraulics_input(inp: VesselHydraulicsInput) -> None:
    """VesselHydraulicsInput 边界校验。"""
    if inp.D_m <= 0 or inp.L_m <= 0 or inp.h0_m <= 0:
        raise VesselInputError(
            f"容器几何必须 > 0（D={inp.D_m}, L={inp.L_m}, h0={inp.h0_m}）"
        )
    if inp.d_orifice_m <= 0 or inp.Cd_orifice <= 0:
        raise VesselInputError(
            f"排空口参数非法（d={inp.d_orifice_m}, Cd={inp.Cd_orifice}）"
        )
    if inp.d_overflow_m <= 0 or inp.h_overflow_m <= 0 or inp.Cd_overflow <= 0:
        raise VesselInputError(
            f"溢流口参数非法（d={inp.d_overflow_m}, h={inp.h_overflow_m}, "
            f"Cd={inp.Cd_overflow}）"
        )
    if inp.Q_in_liquid_m3_s < 0:
        raise VesselInputError(
            f"Q_in_liquid_m3_s={inp.Q_in_liquid_m3_s} 不能为负"
        )
    if inp.thermal_breathing_factor <= 0:
        raise VesselInputError(
            f"thermal_breathing_factor={inp.thermal_breathing_factor} 必须 > 0"
        )


def _compute_empty_time(inp: VesselHydraulicsInput) -> float:
    """排空时间（重力出流积分）。

    公式：t = (A_tank / (Cd · A_orifice)) · √(2·h0/g)

    ⚠️ 适用性边界（用户评审 2026-09-17）：
      - 仅严格适用于**立式圆柱罐**（A_tank 假设为常数 π·D²/4）
      - 卧式罐 A_tank 随 h 变化（液面为椭圆截面）→ 偏差显著（>5%）
      - 卧式罐重力排空到底的工程场景少见（常泵抽）；如需精确请用 P5-3
        Task 17 接管后的迭代积分实现
      - 运行时：calc_vessel_hydraulics 在 orientation == "horizontal"
        时自动发 UserWarning（非拒绝，详见调用层）

    注：包装层 chedl_wrapper.time_to_empty 在 fluids 1.3.1 不存在时降级为自研
    实现（V1.9 F-13-5）。业务侧统一调包装层，无需关心底层来源。
    """
    return chedl_wrapper.time_to_empty(
        D_tank=inp.D_m,
        h0=inp.h0_m,
        d_orifice=inp.d_orifice_m,
        Cd=inp.Cd_orifice,
    )


def _check_overflow(inp: VesselHydraulicsInput) -> tuple[bool, float]:
    """溢流校核：Q_in vs 溢流口出流能力。

    溢流口出流能力 = Cd × A_overflow × √(2·g·h_overflow)
    进液量 < 能力 → 不溢流（overflow_ok=True）

    Returns:
        (overflow_ok, capacity_m3_s)
    """
    g = 9.80665
    A_overflow = math.pi * (inp.d_overflow_m / 2.0) ** 2
    capacity_m3_s = inp.Cd_overflow * A_overflow * math.sqrt(2.0 * g * inp.h_overflow_m)
    overflow_ok = inp.Q_in_liquid_m3_s < capacity_m3_s
    return overflow_ok, capacity_m3_s


def _compute_level_volume_curve(inp: VesselHydraulicsInput) -> str:
    """液位-容积曲线 JSON。

    11 个采样点：h = 0, 0.1D, 0.2D, ..., 1.0D（按封头 + 圆柱几何）。
    包装层 chedl_wrapper.tank_level_to_volume 在 fluids 1.3.1 缺失时降级自研
    （V1.9 F-13-5，2:1 椭圆封头 + 圆柱主体分段积分）。

    Returns:
        JSON 字符串：{"h=0.00": 0.0, "h=0.20": ..., "h=2.00": ...}
    """
    levels = [inp.D_m * i / 10.0 for i in range(11)]
    curve = {
        f"h={h:.2f}m": round(
            chedl_wrapper.tank_level_to_volume(D=inp.D_m, h=h, head_type="ellipse"),
            4,
        )
        for h in levels
    }
    return json.dumps(curve, ensure_ascii=False)


def _compute_vent_capacity(inp: VesselHydraulicsInput) -> float:
    """放空能力（PVRV 呼吸量参考，简化工程估算）。

    标准来源：API 2000 7th Ed. §4.3.3（Tank Venting — Normal Venting） +
              ISO 28300:2008 §6（Pressure/Vacuum Relief）。
    本实现为简化估算（仅 thermal breathing，**不含** working breathing
    —— 后者由 P5-3 Task 17 breathing_valve_service 接管）。

    公式：Q_thermal = 1.2 × thermal_factor × V_total / 3600  [m³/s]
      - 1.2 = API 2000 §4.3.3.2 推荐 20% 安全余量系数（thermal only）
      - thermal_factor = API 2000 表 4 (Y 系数，按罐体类型 + 闪点分类)
        —— 默认 1.0 代表普通固定顶罐；用户按工况查表覆盖
      - V_total = π·(D/2)²·L（圆柱主体，封头段 < 5% 体积已忽略）
      - 3600 = m³/h → m³/s 转换

    ⚠️ V1.0 历史 bug：早期实现用 `/60`（m³/min），与字段名 m3_s 不一致；
       P5-1-2 hotfix 修正为 `/3600`。

    Args:
        inp: VesselHydraulicsInput（必须 D_m, L_m > 0）

    Returns:
        PVRV thermal breathing capacity，单位 m³/s
    """
    V_total = math.pi * (inp.D_m / 2.0) ** 2 * inp.L_m
    return 1.2 * inp.thermal_breathing_factor * V_total / 3600.0


def calc_vessel_hydraulics(inp: VesselHydraulicsInput) -> VesselHydraulicsResult:
    """计算 vessel 流体力学 4 项：排空 / 溢流校核 / 液位-容积 / 放空能力。

    PCS-PLAN-P5-DEVICE-EQUIPMENT.md §136-163 接口契约：
      - empty_time_s: 重力排空时间（**仅 vertical 严格适用**）
      - overflow_ok: 溢流校核布尔
      - level_volume_curve_json: 液位-容积曲线 JSON 串
      - vent_capacity_m3_s: PVRV thermal breathing capacity（API 2000 §4.3.3）
      - applicable_orientation: 严格适用的方位（当前固定 "vertical"）

    卧式罐运行时警告（用户评审 2026-09-17 补强）：
      input.orientation == "horizontal" 时发 UserWarning（不拒绝），
      result.applicable_orientation 仍为 "vertical"（数据可追溯）。

    包装层降级（V1.9 F-13-5）：fluids 1.3.1 缺失 time_to_empty / tank_level_to_volume
    → chedl_wrapper 走 fallback 自研实现，业务侧无感。

    Returns:
        frozen dataclass；纯函数不触 DB。
    """
    _validate_hydraulics_input(inp)

    # 卧式罐 t_empty 适用性警告（用户评审 2026-09-17）
    if inp.orientation == "horizontal":
        warnings.warn(
            "t_empty 公式仅严格适用于立式罐（orientation='vertical'）；"
            "卧式罐 A_tank 随 h 变化，结果偏差 > 5%，仅供参考。"
            "backlog：P5-3 Task 17 breathing_valve_service 接管后补迭代积分。",
            UserWarning,
            stacklevel=2,
        )

    empty_time_s = _compute_empty_time(inp)
    overflow_ok, _ = _check_overflow(inp)
    level_volume_curve_json = _compute_level_volume_curve(inp)
    vent_capacity_m3_s = _compute_vent_capacity(inp)

    return VesselHydraulicsResult(
        empty_time_s=empty_time_s,
        overflow_ok=overflow_ok,
        level_volume_curve_json=level_volume_curve_json,
        vent_capacity_m3_s=vent_capacity_m3_s,
        applicable_orientation="vertical",
    )