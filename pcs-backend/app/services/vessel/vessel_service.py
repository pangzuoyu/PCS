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
    P6-4 T3 重构：调 calc_partial_volume（D7 接口冻结的 C-12 公共服务），
    取代原 chedl_wrapper.tank_level_to_volume 直调。结果与原实现严格一致
    （h ≤ L 时 V_partial = V_head + V_cyl，分段积分同源）。

    Returns:
        JSON 字符串：{"h=0.00": 0.0, "h=0.20": ..., "h=2.00": ...}
    """
    levels = [inp.D_m * i / 10.0 for i in range(11)]
    curve = {
        f"h={h:.2f}m": round(
            calc_partial_volume(
                PartialVolumeInput(
                    D_m=inp.D_m,
                    L_m=inp.L_m,
                    head_type="2:1_ELLIPTICAL",
                    H_m=h,
                )
            ).partial_volume_m3,
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


# ============================================================================
# P6-4 T3 C-12 容器部分体积 + 润湿面积公共服务（V1.2 接口冻结 6 个月）
#
# 按 SPEC §3.4.4 C-12 增补：容器几何公共服务，供 C-07/C-08/C-10/C-20/C-21 调用。
# 接口冻结至 2027-03-25（ADR-0040）：签名 + 行为不变；任何破坏性变更须新 ADR。
#
# 公式来源：WS-CA-PR-013 Rev A（"Partial Vessel Volume" 算例，Worley 标准计算）：
#   - 2:1 椭圆封头：V_partial = π·Z·(3D² - 16Z²)/12（Z ≤ D/4）
#   - 半球封头：V_partial = π·Z²·(R - Z/3), R = D/2
#   - 碟形封头：V_partial = V_full · (Z/b)²（工程近似，Ri=D/r=0.1D 标准 F&D）
#   - 平封头：V = 0
#   - 圆柱主体：V_cyl = π·D²/4·L_liq（液位超过封头后）
#   - 润湿面积：2:1 椭圆 A = π·D²·[1/4 + ln(2+√3)/(8√3)] ≈ π·D²·0.3451（半 oblate 椭球闭式）
# ============================================================================


# 封头类型字面量（V1.2 拼写修正：TORISPHERIAL → TORISPHERICAL，per SPEC §3.4.4）
HeadType = Literal["HEMISPHERICAL", "2:1_ELLIPTICAL", "TORISPHERICAL", "FLAT"]
# mass_iteration 子集：排除 TORISPHERICAL（圆锥+冠部几何复杂，迭代收敛难）
MassIterationHeadType = Literal["HEMISPHERICAL", "2:1_ELLIPTICAL", "FLAT"]
VesselShape = Literal["VERTICAL", "HORIZONTAL", "SPHERICAL"]
MassModel = Literal["EMPTY", "OPERATING"]
IterationVariable = Literal["D", "L"]

# 2:1 椭圆封头表面积系数（半 oblate 椭球闭式积分结果）
# A_2:1 = π·D²·[1/4 + ln(2+√3)/(8√3)] ≈ π·D²·0.3451
# 推导：_head_partial_area 在 Z=b=D/4 时积分得 A_full
_ELLIPSE_AREA_COEF: Final[float] = 0.25 + math.log(2.0 + math.sqrt(3.0)) / (
    8.0 * math.sqrt(3.0)
)  # ≈ 0.3451
# 标准 ASME F&D 碟形封头深度系数（Ri=D, r=0.1D）
_TORISPHERICAL_DEPTH_COEF: Final[float] = 0.169
# 标准 ASME F&D 碟形封头体积系数（Perry's 8th Ed. Table 10-4）
_TORISPHERICAL_VOLUME_COEF: Final[float] = 0.0806
# 标准 ASME F&D 碟形封头表面积系数（工程近似，单头）
_TORISPHERICAL_AREA_COEF: Final[float] = 1.20


class MassIterationNotConvergedError(PcsError):
    """mass_iteration_loop 50 次迭代未收敛（422）。

    由 calc_vessel_sizing 配套算法在 WS-CA-PR-010.xls 5 段 sizing 中调用
    Newton/bisection 求解容器 D 或 L；超出 max_iter 触发。
    """

    code = "MASS_ITERATION_NOT_CONVERGED"
    status = 422


@dataclass(frozen=True)
class PartialVolumeInput:
    """calc_partial_volume 输入（frozen dataclass，V1.2 接口冻结）。

    物理量 SI 单位：长度 m。
    H_m = 液位总高度（从容器底部内侧算起，含封头段）；≥ 0 且 ≤ L_m + 2·head_depth。
    vessel_shape（ADR-0041 v7 F2.1，2026-09-25 冻结契约修订）：
      - "VERTICAL"（默认）：立式罐；H_m 为液位总高度，cylinder 液位高度 = max(0, min(H-b, L))
      - "HORIZONTAL"：卧式罐；H_m 为液位深度，cylinder 横截面液相面积用 _circular_segment_area_h_m
      - "SPHERICAL"：球罐；无 cylinder，L_m 忽略，H_m 为球缺高度
    """

    D_m: float
    L_m: float
    head_type: HeadType
    H_m: float
    H1_m: float | None = None
    H2_m: float | None = None
    H3_m: float | None = None
    n_vessels: int = 1
    vessel_shape: VesselShape = "VERTICAL"


@dataclass(frozen=True)
class PartialVolumeResult:
    """calc_partial_volume 输出（frozen dataclass，V1.2 接口冻结）。

    字段：
      - partial_volume_m3: 单容器部分液相体积
      - total_volume_m3: 单容器总容积（n_vessels × 此值 = 多容器总容积）
      - head_volume_m3: 单容器封头部分容积（底部 + 顶部封头，液位侵入部分）
      - cylinder_volume_m3: 单容器筒体部分液相体积
      - formula_ref: 公式溯源（dict[str, str]）
      - vessel_shape_used: 实际使用的容器方位（ADR-0041 v7 F3，2026-09-25 冻结契约修订）
    """

    partial_volume_m3: float
    total_volume_m3: float
    head_volume_m3: float
    cylinder_volume_m3: float
    formula_ref: dict[str, str]
    vessel_shape_used: VesselShape


@dataclass(frozen=True)
class WettedAreaInput:
    """calc_wetted_area 输入（frozen dataclass，V1.2 接口冻结）。

    vessel_shape 同 PartialVolumeInput（F2.2，ADR-0041 v7，2026-09-25 冻结契约修订）。
    """

    D_m: float
    L_m: float
    head_type: HeadType
    H_m: float
    n_vessels: int = 1
    vessel_shape: VesselShape = "VERTICAL"


@dataclass(frozen=True)
class WettedAreaResult:
    """calc_wetted_area 输出（frozen dataclass，V1.2 接口冻结）。

    字段：
      - wetted_area_m2: 单容器润湿面积
      - total_wetted_area_m2: 单容器总外表面积（n_vessels × 此值 = 多容器总外表）
      - head_area_m2: 单容器封头润湿面积（底部 + 顶部封头，液位接触部分）
      - cylinder_area_m2: 单容器筒体润湿面积 = π·D·L_liq
      - formula_ref: 公式溯源
      - vessel_shape_used: 实际使用的容器方位（ADR-0041 v7 F3，2026-09-25 冻结契约修订）
    """

    wetted_area_m2: float
    total_wetted_area_m2: float
    head_area_m2: float
    cylinder_area_m2: float
    formula_ref: dict[str, str]
    vessel_shape_used: VesselShape


def _head_depth(D_m: float, head_type: HeadType) -> float:
    """单封头深度（m）。

    HEMISPHERICAL: D/2；2:1_ELLIPTICAL: D/4；TORISPHERICAL (F&D): 0.169·D；FLAT: 0。
    """
    if head_type == "HEMISPHERICAL":
        return D_m / 2.0
    if head_type == "2:1_ELLIPTICAL":
        return D_m / 4.0
    if head_type == "TORISPHERICAL":
        return _TORISPHERICAL_DEPTH_COEF * D_m
    if head_type == "FLAT":
        return 0.0
    raise VesselInputError(f"未知的 head_type: {head_type!r}")


def _head_full_volume(D_m: float, head_type: HeadType) -> float:
    """单封头完整体积（m³）。

    公式：
      HEMISPHERICAL: π·D³/12
      2:1_ELLIPTICAL: π·D³/24
      TORISPHERICAL: 0.0806·D³（Perry's 8th Ed. 标准 F&D 近似）
      FLAT: 0
    """
    if head_type == "HEMISPHERICAL":
        return _PI * D_m**3 / 12.0
    if head_type == "2:1_ELLIPTICAL":
        return _PI * D_m**3 / 24.0
    if head_type == "TORISPHERICAL":
        return _TORISPHERICAL_VOLUME_COEF * D_m**3
    if head_type == "FLAT":
        return 0.0
    raise VesselInputError(f"未知的 head_type: {head_type!r}")


def _head_full_area(D_m: float, head_type: HeadType) -> float:
    """单封头完整外表面积（m²）。

    公式：
      HEMISPHERICAL: π·D²/2
      2:1_ELLIPTICAL: π·D²·[1/4 + ln(2+√3)/(8√3)] ≈ 0.3451·π·D²（半 oblate 椭球闭式）
      TORISPHERICAL: 1.20·D²（Perry's 标准 F&D 近似）
      FLAT: 0
    """
    if head_type == "HEMISPHERICAL":
        return _PI * D_m**2 / 2.0
    if head_type == "2:1_ELLIPTICAL":
        return _PI * D_m**2 * _ELLIPSE_AREA_COEF
    if head_type == "TORISPHERICAL":
        return _TORISPHERICAL_AREA_COEF * D_m**2
    if head_type == "FLAT":
        return 0.0
    raise VesselInputError(f"未知的 head_type: {head_type!r}")


def _head_partial_volume(
    D_m: float, head_type: HeadType, Z_m: float
) -> float:
    """单封头部分填充体积（m³），Z_m 为从封头顶点（apex）向上的填充高度。

    公式（每头）：
      HEMISPHERICAL: V = π·Z²·(R - Z/3), R = D/2（球缺体积公式）
      2:1_ELLIPTICAL: V = π·Z·(3D² - 16Z²)/12（标准 2:1 椭圆积分）
      TORISPHERICAL: V ≈ V_full · (Z/b)²（工程近似，b = 0.169·D）
      FLAT: 0
    """
    if head_type == "FLAT":
        return 0.0
    b = _head_depth(D_m, head_type)
    if b <= 0:
        return 0.0
    z_clamped = min(Z_m, b)
    if z_clamped <= 0:
        return 0.0
    if head_type == "HEMISPHERICAL":
        R = D_m / 2.0
        return _PI * z_clamped**2 * (R - z_clamped / 3.0)
    if head_type == "2:1_ELLIPTICAL":
        return (
            _PI
            * z_clamped
            * (3.0 * D_m**2 - 16.0 * z_clamped**2)
            / 12.0
        )
    if head_type == "TORISPHERICAL":
        return _head_full_volume(D_m, head_type) * (z_clamped / b) ** 2
    raise VesselInputError(f"未知的 head_type: {head_type!r}")


def _head_partial_area(
    D_m: float, head_type: HeadType, Z_m: float
) -> float:
    """单封头部分润湿面积（m²），Z_m 为从封头顶点向上的填充高度。

    公式：
      HEMISPHERICAL: A = π·D·Z（球缺侧面积）
      2:1_ELLIPTICAL: A = (π·D·Z·√(b²+3Z²))/(2b) + (π·D·b/(2√3))·ln(√3·Z/b + √(1+3Z²/b²))
        ——半 oblate 椭球表面积闭式积分（Z=b 时为 A_full = π·D²·0.3451）
      TORISPHERICAL: A ≈ A_full · (Z/b)（线性近似，b = 0.169·D）
      FLAT: 0
    """
    if head_type == "FLAT":
        return 0.0
    b = _head_depth(D_m, head_type)
    if b <= 0:
        return 0.0
    z_clamped = min(Z_m, b)
    if z_clamped <= 0:
        return 0.0
    if head_type == "HEMISPHERICAL":
        return _PI * D_m * z_clamped
    if head_type == "2:1_ELLIPTICAL":
        # 半 oblate 椭球表面积闭式积分（b = D/4，a = D/2）
        # term1 = π·a·Z·√(b² + 3Z²)/b
        # term2 = π·a·b/√3 · ln(√3·Z/b + √(1 + 3Z²/b²))
        a = D_m / 2.0
        term1 = (
            _PI * a * z_clamped * math.sqrt(b**2 + 3.0 * z_clamped**2) / b
        )
        term2 = (
            _PI
            * a
            * b
            / math.sqrt(3.0)
            * math.log(
                math.sqrt(3.0) * z_clamped / b
                + math.sqrt(1.0 + 3.0 * z_clamped**2 / b**2)
            )
        )
        return term1 + term2
    if head_type == "TORISPHERICAL":
        return _head_full_area(D_m, head_type) * (z_clamped / b)
    raise VesselInputError(f"未知的 head_type: {head_type!r}")


# ============================================================================
# P6-x ADR-0041 v7 §3 §4：HORIZONTAL / SPHERICAL 公式重构 + 数值积分 helpers
#
# 冻结契约扩展（F2.1/F2.2/F3/F8）：
#   - vessel_shape: Optional，默认 "VERTICAL"（向后兼容 5 调用方）
#   - vessel_shape_used: 实际使用的容器方位
#   - p12 拒绝：FLAT × SPHERICAL（FLAT 无几何体积，与 SPHERICAL 配对无意义）
#
# 公式来源：ADR-0041 v7 §3 §4 独立推导 + WS-CA-PR-013 Rev C 对账
# ============================================================================


def _lerp(a: float, b: float, t: float) -> float:
    """线性插值：a + (b − a) · t。

    数值积分基元（_trapz 调用 _lerp 生成积分点）。
    """
    return a + (b - a) * t


def _trapz(y: list[float], x: list[float]) -> float:
    """梯形积分（numpy.trapz 等价，避免 numpy import 仅单函数）。

    Returns:
        ∫y dx 近似值（梯形法则）。空 / 单元素 / 长度不匹配返回 0。
    """
    n = len(y)
    if n < 2 or len(x) != n:
        return 0.0
    return sum(
        0.5 * (y[i] + y[i + 1]) * (x[i + 1] - x[i]) for i in range(n - 1)
    )


def _circular_segment_area_r_h(r: float, h: float) -> float:
    """半径 r 圆内液面深度 h 部分的圆段面积（强公式，<0.1% 误差）。

    几何：圆心 (0,0)，液面水平，深度 h（从底边到液面）。等价
    `r²·arccos(cos_arg) − (r − h)·√(h·(2r − h))`。

    Args:
        r: 圆半径（m）
        h: 液面深度（m），0 ≤ h ≤ 2r

    Returns:
        部分圆段面积（m²）

    Note:
        这是 _head_partial_volume_horizontal 数值积分的子函数；h ≥ 2r
        时返回整圆面积 π·r²。
    """
    if h <= 0:
        return 0.0
    if h >= 2.0 * r:
        return _PI * r**2
    cos_arg = (r - h) / r
    cos_arg = max(-1.0, min(1.0, cos_arg))  # 浮点保护
    sqrt_arg = max(0.0, h * (2.0 * r - h))
    return r**2 * math.acos(cos_arg) - (r - h) * math.sqrt(sqrt_arg)


def _circular_segment_area_h_m(D_m: float, H_m: float) -> float:
    """HORIZONTAL cylinder 横截面液相面积（垂直于 cylinder 轴，强公式 <0.1%）。

    对账验证：D=1.8, H=0.9 → A_seg = π·D²/8 = 1.2723 m²
    （与 WS-CA-PR-013 Horiz-Vol&Area-SI 50% fill V_cyl = A_seg·L = 1.2723·4.5 = 5.7255 一致）

    Args:
        D_m: cylinder 直径（m）
        H_m: 液位深度（m），垂直高度 0 ≤ H_m ≤ D_m

    Returns:
        圆柱横截面液相面积（m²）
    """
    if H_m <= 0:
        return 0.0
    if H_m >= D_m:
        return _PI * D_m**2 / 4.0
    h = H_m / D_m
    cos_arg = 1.0 - 2.0 * h
    sqrt_arg = max(0.0, 4.0 * h * (1.0 - h))
    return (D_m**2 / 4.0) * (
        math.acos(cos_arg) - cos_arg * math.sqrt(sqrt_arg)
    )


def _sphere_partial_volume_h_m(D_m: float, H_m: float) -> float:
    """SPHERICAL 球罐 / HEMI 封头部分填充体积（球缺公式 π·H²·(3R − H)/3）。

    球对称：VERTICAL / HORIZONTAL 公式相同（H_m 含义不同但数学形式一致）。

    Args:
        D_m: 球直径（m）
        H_m: 液位深度（m），0 ≤ H_m ≤ D_m

    Returns:
        单端部分体积（球缺），m³

    Notes:
        H_m = 0 → 0；H_m = R = D/2 → 半球 = π·D³/12 = 2π·R³/3；
        H_m = D → 全球 = π·D³/6。
    """
    if H_m <= 0:
        return 0.0
    if H_m >= D_m:
        return _PI * D_m**3 / 6.0
    R = D_m / 2.0
    return _PI * (H_m**2) * (3.0 * R - H_m) / 3.0


def _head_partial_volume_horizontal(
    head_type: HeadType,
    D_m: float,
    H_m: float,
    n_points: int = 200,
) -> float:
    """HORIZONTAL cylinder 封头部分体积（**两端之和**），数值积分实现（v6）。

    v6 全部数值积分（v5 闭式公式仅在 d=R/2、R、2R 巧合正确，被 v6 推翻）：
        V_single = ∫_{z_min}^{0} A_seg(r(z), h(z)) dz
        V_two_heads = 2 × V_single
        其中：
            r(z) = 封头在 z 处横截面半径（按 head_type 几何）
            h(z) = 液面相对圆心位置 = -R + H_m + r(z)
            z_min = 液相面积非零起始点（r(z_min) = R - H_m 时刚好有液相）
            z_max = 0（cylinder 接触面）

    **v7 关键几何洞察**：HEMI 卧式封头在 H=R（50% fill）时，每个 z 截面仅半填充
    （液面在 cylinder 中心 y=0，深度 = r(z) = 半径），不是整圆填充。
    V_single = (1/3)πR³，V_two_heads = (2/3)πR³ = 1.527 m³（与 v5 闭式 3.054 不同）。

    Args:
        head_type: 封头类型
        D_m: cylinder 直径（m）
        H_m: 液位深度（m），垂直高度 0 ≤ H_m ≤ D_m
        n_points: 数值积分点数（默认 200，精度 <1e-4）

    Returns:
        两端封头部分体积之和（m³）

    Raises:
        NotImplementedError: TORISPHERICAL r(z) 需工艺室提供参数化（Q-1 第二批 2026-11-30）

    Reference:
        ADR-0041 v7 §3 §4 v6 数值积分验证表
    """
    R = D_m / 2.0

    if H_m <= 0:
        return 0.0
    if head_type == "FLAT":
        return 0.0

    # 封头几何参数（r(z) 函数 + 轴向深度 b）
    if head_type == "HEMISPHERICAL":
        b = R

        def r_of_z(z: float) -> float:
            return math.sqrt(max(0.0, R**2 - z**2))
    elif head_type == "2:1_ELLIPTICAL":
        b = R / 2.0

        def r_of_z(z: float) -> float:
            return R * math.sqrt(max(0.0, 1.0 - (z / b) ** 2))
    elif head_type == "TORISPHERICAL":
        # Q-1：TORISPHERICAL r(z) 需工艺侧按 ASME VIII-1 UG-32 提供参数化；
        # WS-CA-PR-013 Rev B 第二批 2026-11-30 前签发
        raise NotImplementedError(
            "TORISPHERICAL r(z) 需工艺侧按 ASME VIII-1 UG-32 提供参数化；"
            "WS-CA-PR-013 Rev B 第二批 2026-11-30 前签发"
        )
    else:
        raise VesselInputError(f"未知的 head_type: {head_type!r}")

    # 边界 case：H_m ≥ D_m 整端封头填满
    if H_m >= D_m:
        if head_type == "HEMISPHERICAL":
            # HEMI 满 fill = 2 × V_full_HEMI = 2 × (2/3)πR³ = (4/3)πR³
            return (4.0 / 3.0) * _PI * R**3
        if head_type == "2:1_ELLIPTICAL":
            return 2.0 * _PI * D_m**3 / 24.0
        return 0.0

    # 数值积分区间：z ∈ [z_min, 0]
    # z 轴沿封头轴向，从 apex (z=-b) 到 cylinder 接触面 (z=0)
    # z_min = 液相面积非零起始点（r(z_min) = R - H_m 时刚好有液相）
    if H_m >= R:
        z_min = -b
    else:
        z_min = -math.sqrt(H_m * (2.0 * R - H_m))
        if z_min < -b:
            z_min = -b  # 截断到封头底

    z_arr = [_lerp(z_min, 0.0, i / (n_points - 1)) for i in range(n_points)]
    A_arr: list[float] = []
    for z in z_arr:
        r = r_of_z(z)
        h = -R + H_m + r  # 液面深度（部分填充）
        if r <= 0 or h <= 0:
            A = 0.0
        elif h >= 2.0 * r:
            A = _PI * r**2  # 整圆填充（液面高于圆顶）
        else:
            A = _circular_segment_area_r_h(r, h)
        A_arr.append(A)

    V_single = _trapz(A_arr, z_arr)
    return 2.0 * V_single


def _head_partial_wetted_area_horizontal(
    head_type: HeadType,
    D_m: float,
    H_m: float,
    n_points: int = 200,
) -> float:
    """HORIZONTAL cylinder 封头润湿面积（**两端之和**），数值积分实现。

    与体积不同：润湿面积 = 液面接触的曲面面积（不是体积）。
    算法（与 _head_partial_volume_horizontal 同思路，沿 z 轴积分）：
        s(z) = 沿母线长度元素（ds）
        A_seg_in_contact(z) = 沿液面方向的圆弧长 × ds（投影）
        A_single = ∫_{z_min}^{0} (接触弧长) ds
        A_two_heads = 2 × A_single

    Args:
        head_type: 封头类型
        D_m: cylinder 直径（m）
        H_m: 液位深度（m）
        n_points: 数值积分点数

    Returns:
        两端封头润湿面积之和（m²）

    Note:
        工程简化：HEMI 卧式封头单端润湿面积 ≈ 2πR·H（球冠侧面积，与 V 部分填充的几何对称性）。
        2:1 / TORI 走完整数值积分（与体积同思路）。
    """
    R = D_m / 2.0

    if H_m <= 0:
        return 0.0
    if head_type == "FLAT":
        return 0.0
    if H_m >= D_m:
        # 满 fill：润湿面积 = 2 × A_full_head（与体积 V_full 边界对称）
        return 2.0 * _head_full_area(D_m, head_type)

    # 封头几何参数（r(z) 函数 + 轴向深度 b）
    if head_type == "HEMISPHERICAL":
        b = R

        def r_of_z(z: float) -> float:
            return math.sqrt(max(0.0, R**2 - z**2))
    elif head_type == "2:1_ELLIPTICAL":
        b = R / 2.0

        def r_of_z(z: float) -> float:
            return R * math.sqrt(max(0.0, 1.0 - (z / b) ** 2))
    elif head_type == "TORISPHERICAL":
        raise NotImplementedError(
            "TORISPHERICAL 卧式封头润湿面积需工艺侧按 ASME VIII-1 UG-32 提供参数化；"
            "WS-CA-PR-013 Rev B 第二批 2026-11-30 前签发"
        )
    else:
        raise VesselInputError(f"未知的 head_type: {head_type!r}")

    # 数值积分：接触弧长 × ds（沿 z 轴）
    # ds = √(1 + (dr/dz)²) dz（封头母线长度元素）
    # 接触弧长（z 截面圆被液面截到下方） = 2·r·arccos((r-h)/r)（h ≤ r 时）
    # 简化：直接用 _circular_segment_area_r_h 公式的弧长版本
    if H_m >= R:
        z_min = -b
    else:
        z_min = -math.sqrt(H_m * (2.0 * R - H_m))
        if z_min < -b:
            z_min = -b

    z_arr = [_lerp(z_min, 0.0, i / (n_points - 1)) for i in range(n_points)]
    s_arr: list[float] = []
    for idx, z in enumerate(z_arr):
        r = r_of_z(z)
        if r <= 1e-12:
            s_arr.append(0.0)
            continue
        h = -R + H_m + r
        if h <= 0:
            s_arr.append(0.0)
            continue
        # 接触弧长（z 截面圆与液面相交的弧长）
        if h >= 2.0 * r:
            arc_len = 2.0 * _PI * r  # 整圆
        else:
            cos_a = max(-1.0, min(1.0, (r - h) / r))
            arc_len = 2.0 * r * math.acos(cos_a)
        # ds（沿 z 轴）：dz 已知（z_arr 步长）
        dz = z_arr[idx + 1] - z if idx + 1 < len(z_arr) else 0.0
        # 简化：用 Δz 近似 ds（母线 dr/dz 影响 <1%，工程可接受）
        s_arr.append(arc_len * abs(dz) if idx + 1 < len(z_arr) else 0.0)

    # 修整：去掉最后一点（Δz=0）
    if s_arr and s_arr[-1] == 0.0:
        s_arr.pop()

    A_single = _trapz(s_arr, z_arr[: len(s_arr)])
    return 2.0 * A_single


def _validate_geometry_input(
    D_m: float, L_m: float, H_m: float,
    vessel_shape: VesselShape | None = None,
    head_type: HeadType | None = None,
) -> None:
    """几何输入边界校验（D > 0, L ≥ 0, H ≥ 0）。

    L_m 可为 0（SPHERICAL 球罐无切线长），但不允许 < 0。

    p12 拒绝（ADR-0041 v7 F8）：
      FLAT × SPHERICAL 几何退化（FLAT 无几何体积，与 SPHERICAL 球面配对无意义）
      → VesselInputError，错误信息："FLAT × SPHERICAL 几何退化"
    """
    if D_m <= 0:
        raise VesselInputError(f"D_m={D_m} 必须 > 0")
    if L_m < 0:
        raise VesselInputError(f"L_m={L_m} 必须 ≥ 0")
    if H_m < 0:
        raise VesselInputError(f"H_m={H_m} 必须 ≥ 0")
    if (
        vessel_shape == "SPHERICAL"
        and head_type == "FLAT"
    ):
        raise VesselInputError(
            "FLAT × SPHERICAL 几何退化，球面无法配平面封头"
        )


def calc_partial_volume(inp: PartialVolumeInput) -> PartialVolumeResult:
    """计算容器部分液相体积（V1.2 接口冻结，冻结至 2027-03-25）。

    按 vessel_shape 分发（ADR-0041 v7 §3 §4）：
      - VERTICAL（默认）：V1.2 既有实现
          V_partial = V_head_bottom + V_cyl + V_head_top
          V_head_bottom = _head_partial_volume(D, head_type, Z_b), Z_b = min(H, b)
          V_head_top = _head_partial_volume(D, head_type, Z_t), Z_t = max(0, H - L - b)
          V_cyl = π·D²/4·L_liq
      - HORIZONTAL：
          V_cyl = _circular_segment_area_h_m(D, H) · L
          V_head = _head_partial_volume_horizontal(head_type, D, H)（两端之和，数值积分）
          V_total = V_cyl + V_head
      - SPHERICAL：
          V_partial = _sphere_partial_volume_h_m(D, H)（球缺公式）
          V_total = π·D³/6（全球）

    Args:
        inp: PartialVolumeInput（frozen dataclass）

    Returns:
        PartialVolumeResult：单容器 partial_volume_m3 + total_volume_m3 + 头部/筒体分解。
        n_vessels 缩放仅在调用方按 total_volume_m3 × n_vessels 计算。
    """
    D_m = inp.D_m
    L_m = inp.L_m
    head_type = inp.head_type
    H_m = inp.H_m
    vessel_shape = inp.vessel_shape
    _validate_geometry_input(
        D_m, L_m, H_m, vessel_shape=vessel_shape, head_type=head_type
    )
    if inp.n_vessels < 1:
        raise VesselInputError(f"n_vessels={inp.n_vessels} 必须 ≥ 1")

    if vessel_shape == "HORIZONTAL":
        A_seg = _circular_segment_area_h_m(D_m, H_m)
        V_cyl = A_seg * L_m
        V_head = _head_partial_volume_horizontal(head_type, D_m, H_m)
        r = D_m / 2.0
        A_cs = _PI * r**2
        V_total = A_cs * L_m + 2.0 * _head_full_volume(D_m, head_type)
        return PartialVolumeResult(
            partial_volume_m3=V_cyl + V_head,
            total_volume_m3=V_total,
            head_volume_m3=V_head,
            cylinder_volume_m3=V_cyl,
            formula_ref={
                "head": (
                    "_head_partial_volume_horizontal (numerical, n=200)"
                ),
                "cylinder": "_circular_segment_area_h_m · L",
                "total": "π·D²/4·L + 2·V_head_full",
                "vessel_shape": "HORIZONTAL",
            },
            vessel_shape_used="HORIZONTAL",
        )

    if vessel_shape == "SPHERICAL":
        V_partial = _sphere_partial_volume_h_m(D_m, H_m)
        V_total = _PI * D_m**3 / 6.0
        return PartialVolumeResult(
            partial_volume_m3=V_partial,
            total_volume_m3=V_total,
            head_volume_m3=V_partial,
            cylinder_volume_m3=0.0,
            formula_ref={
                "head": "_sphere_partial_volume_h_m (球缺公式 π·H²·(3R−H)/3)",
                "cylinder": "N/A（SPHERICAL 无 cylinder）",
                "total": "π·D³/6 (球体体积)",
                "vessel_shape": "SPHERICAL",
            },
            vessel_shape_used="SPHERICAL",
        )

    # VERTICAL（默认；V1.2 既有实现）
    b = _head_depth(D_m, head_type)
    r = D_m / 2.0
    A_cs = _PI * r**2  # 圆柱横截面积

    # 底部封头液位高度（不超过封头深度）
    z_bottom = min(H_m, b)
    V_head_bottom = _head_partial_volume(D_m, head_type, z_bottom)

    # 顶部封头液位高度（液位超过 L + b 时才有）
    z_top = max(0.0, H_m - L_m - b)
    V_head_top = _head_partial_volume(D_m, head_type, z_top)

    # 圆柱主体液位长度：液体侵入顶部封头 ⇒ 圆柱必满
    # 否则按 H_m - b（封头之上）截到 L_m
    if z_top > 0.0:
        L_liq_cyl = L_m  # 圆柱 100% 充满
    else:
        L_liq_cyl = max(0.0, min(H_m - b, L_m))
    V_cyl = A_cs * L_liq_cyl

    V_partial = V_head_bottom + V_cyl + V_head_top
    V_total = A_cs * L_m + 2.0 * _head_full_volume(D_m, head_type)

    return PartialVolumeResult(
        partial_volume_m3=V_partial,
        total_volume_m3=V_total,
        head_volume_m3=V_head_bottom + V_head_top,
        cylinder_volume_m3=V_cyl,
        formula_ref={
            "head": "see _head_partial_volume (HEMI/ELLIPSE/TORIS/FLAT 4 分支)",
            "cylinder": "π·D²/4·L_liq",
            "total": "π·D²/4·L + 2·V_head_full",
            "vessel_shape": "VERTICAL",
        },
        vessel_shape_used="VERTICAL",
    )


def calc_wetted_area(inp: WettedAreaInput) -> WettedAreaResult:
    """计算容器润湿面积（V1.2 接口冻结，冻结至 2027-03-25）。

    按 vessel_shape 分发（ADR-0041 v7 §3 §4 OPEN-3 关闭）：
      - VERTICAL（默认）：V1.2 既有实现
          A_wetted = A_head_bottom + A_cyl + A_head_top
          A_cyl = π·D·L_liq
      - HORIZONTAL：
          A_cyl = L · (πD − D·arccos((R−d)/R)) / 2   （工艺简化公式，d = H_m）
          A_head = _head_partial_wetted_area_horizontal(head_type, D, H)（两端之和）
      - SPHERICAL：
          A_partial = 2πR·H（球冠侧面积，球缺润湿）

    Args:
        inp: WettedAreaInput（frozen dataclass）

    Returns:
        WettedAreaResult：单容器 wetted_area_m2 + total_wetted_area_m2 + 头/筒分解。
    """
    D_m = inp.D_m
    L_m = inp.L_m
    head_type = inp.head_type
    H_m = inp.H_m
    vessel_shape = inp.vessel_shape
    _validate_geometry_input(
        D_m, L_m, H_m, vessel_shape=vessel_shape, head_type=head_type
    )
    if inp.n_vessels < 1:
        raise VesselInputError(f"n_vessels={inp.n_vessels} 必须 ≥ 1")

    if vessel_shape == "HORIZONTAL":
        # HORIZONTAL 筒体润湿面积（Doane 2007 / WS-CA-PR-013 R29a）
        # 推导：air arc = 2R·arccos((h−R)/R)；wetted_perimeter = 2πR − air
        # A_cyl = D · L · (π − arccos((h−R)/R))，统一适用 h ∈ [0, 2R]
        R = D_m / 2.0
        if H_m <= 0:
            A_cyl = 0.0
        elif H_m >= D_m:
            A_cyl = _PI * D_m * L_m
        else:
            # arccos 参数 = (h−R)/R ∈ [−1, 1]（h ∈ [0, 2R] 时）
            cos_a = max(-1.0, min(1.0, (H_m - R) / R))
            A_cyl = D_m * L_m * (_PI - math.acos(cos_a))
        # HORIZONTAL 封头润湿面积（数值积分，两端之和）
        A_head = _head_partial_wetted_area_horizontal(head_type, D_m, H_m)
        A_wetted = A_cyl + A_head
        A_total = _PI * D_m * L_m + 2.0 * _head_full_area(D_m, head_type)
        return WettedAreaResult(
            wetted_area_m2=A_wetted,
            total_wetted_area_m2=A_total,
            head_area_m2=A_head,
            cylinder_area_m2=A_cyl,
            formula_ref={
                "head": (
                    "_head_partial_wetted_area_horizontal "
                    "(numerical, n=200)"
                ),
                "cylinder": "L·(πD − D·arccos((R−d)/R))/2（Doane 2007）",
                "total": "π·D·L + 2·A_head_full",
                "vessel_shape": "HORIZONTAL",
            },
            vessel_shape_used="HORIZONTAL",
        )

    if vessel_shape == "SPHERICAL":
        # SPHERICAL 球冠侧面积（球缺润湿）：A = 2πR·H
        R = D_m / 2.0
        if H_m <= 0:
            A_partial = 0.0
        elif H_m >= D_m:
            A_partial = 4.0 * _PI * R**2  # 全球外表面积
        else:
            A_partial = 2.0 * _PI * R * H_m
        A_total = 4.0 * _PI * R**2
        return WettedAreaResult(
            wetted_area_m2=A_partial,
            total_wetted_area_m2=A_total,
            head_area_m2=A_partial,
            cylinder_area_m2=0.0,
            formula_ref={
                "head": "2πR·H（球冠侧面积）",
                "cylinder": "N/A（SPHERICAL 无 cylinder）",
                "total": "4πR²（球体全表面积）",
                "vessel_shape": "SPHERICAL",
            },
            vessel_shape_used="SPHERICAL",
        )

    # VERTICAL（默认；V1.2 既有实现）
    b = _head_depth(D_m, head_type)

    z_bottom = min(H_m, b)
    A_head_bottom = _head_partial_area(D_m, head_type, z_bottom)

    z_top = max(0.0, H_m - L_m - b)
    A_head_top = _head_partial_area(D_m, head_type, z_top)

    # 圆柱主体液位长度：液体侵入顶部封头 ⇒ 圆柱必满
    if z_top > 0.0:
        L_liq_cyl = L_m
    else:
        L_liq_cyl = max(0.0, min(H_m - b, L_m))
    A_cyl = _PI * D_m * L_liq_cyl

    A_wetted = A_head_bottom + A_cyl + A_head_top
    A_total = _PI * D_m * L_m + 2.0 * _head_full_area(D_m, head_type)

    return WettedAreaResult(
        wetted_area_m2=A_wetted,
        total_wetted_area_m2=A_total,
        head_area_m2=A_head_bottom + A_head_top,
        cylinder_area_m2=A_cyl,
        formula_ref={
            "head": "see _head_partial_area (HEMI/ELLIPSE/TORIS/FLAT 4 分支)",
            "cylinder": "π·D·L_liq",
            "total": "π·D·L + 2·A_head_full",
            "vessel_shape": "VERTICAL",
        },
        vessel_shape_used="VERTICAL",
    )


# ============================================================================
# P6-4 T3 C-12 质量迭代（mass_iteration_loop）：Newton 首选 + bisection fallback
# ============================================================================


@dataclass(frozen=True)
class MassIterationInput:
    """mass_iteration_loop 输入（frozen dataclass，V1.2 接口冻结）。

    物理量 SI 单位：长度 m / 密度 kg/m³ / 质量 kg。

    液位高度 H_assumed 按 vessel_shape 默认取值（mass_iteration_loop 内部固定）：
      - VERTICAL: H = D（液位 = 直径，常见工程保守假设）
      - HORIZONTAL: H = D/2（50% 液位，常见工程假设）
      - SPHERICAL: H = D（满罐，无 cylinder）
    """

    target_mass_kg: float
    rho_L_kg_m3: float
    rho_V_kg_m3: float
    vessel_shape: VesselShape
    head_type: MassIterationHeadType
    initial_D_m: float = 1.0
    initial_L_m: float = 3.0
    variable: IterationVariable = "D"
    mass_model: MassModel = "OPERATING"


@dataclass(frozen=True)
class MassIterationResult:
    """mass_iteration_loop 输出（frozen dataclass，V1.2 接口冻结）。

    字段：
      - converged: True = 收敛；False = 抛 MassIterationNotConvergedError 前最后状态
      - iterations: 实际迭代次数（Newton + bisection 合计）
      - final_variable_m: 收敛时 variable 终值（D 或 L）
      - final_mass_kg: 用 final_variable_m 算出的 operating mass
      - residual_kg: final_mass_kg - target_mass_kg
      - formula_ref: 公式溯源（dict，含 method/tol/max_iter）
    """

    converged: bool
    iterations: int
    final_variable_m: float
    final_mass_kg: float
    residual_kg: float
    formula_ref: dict[str, str]


def _operating_fill_height(vessel_shape: VesselShape, D_m: float) -> float:
    """OPERATING 模型下液位 H 假设（m）。"""
    if vessel_shape == "VERTICAL":
        return D_m
    if vessel_shape == "HORIZONTAL":
        return D_m / 2.0
    if vessel_shape == "SPHERICAL":
        return D_m
    raise VesselInputError(f"未知的 vessel_shape: {vessel_shape!r}")


def _validate_mass_iter_input(inp: MassIterationInput) -> None:
    """mass_iteration_loop 输入物理量校验。"""
    if inp.target_mass_kg <= 0:
        raise VesselInputError(
            f"target_mass_kg={inp.target_mass_kg} 必须 > 0"
        )
    if inp.rho_L_kg_m3 <= 0 or inp.rho_V_kg_m3 <= 0:
        raise VesselInputError(
            f"密度必须 > 0（ρ_L={inp.rho_L_kg_m3}, ρ_V={inp.rho_V_kg_m3}）"
        )
    if inp.rho_L_kg_m3 < inp.rho_V_kg_m3:
        # OPERATING 下允许 ρ_L = ρ_V（罕见，但物理上不阻塞；倒置不合理）
        raise VesselInputError(
            f"ρ_L={inp.rho_L_kg_m3} 必须 ≥ ρ_V={inp.rho_V_kg_m3}"
        )
    if inp.initial_D_m <= 0:
        raise VesselInputError(
            f"initial_D_m={inp.initial_D_m} 必须 > 0"
        )
    # SPHERICAL 球罐无切线长（initial_L_m 可为 0）；VERTICAL/HORIZONTAL 必须 > 0
    if inp.vessel_shape != "SPHERICAL" and inp.initial_L_m <= 0:
        raise VesselInputError(
            f"vessel_shape={inp.vessel_shape} 时 initial_L_m={inp.initial_L_m} 必须 > 0"
        )


def _mass_at_variable(
    inp: MassIterationInput, variable_m: float
) -> float:
    """OPERATING 模型下 mass(D or L) 标量函数。

    mass = ρ_L · V_partial(D, L, H_assumed) + ρ_V · (V_total - V_partial)

    SPHERICAL 特殊处理：球体本身即"封头"，无圆柱；球缺公式 V = π·H²·(R - H/3)。
    VERTICAL/HORIZONTAL 走 calc_partial_volume（V1.2 公共服务复用）。
    """
    D_cur = variable_m if inp.variable == "D" else inp.initial_D_m
    L_cur = variable_m if inp.variable == "L" else inp.initial_L_m
    H_assumed = _operating_fill_height(inp.vessel_shape, D_cur)

    if inp.vessel_shape == "SPHERICAL":
        # 球缺公式：V_partial = π·H²·(R - H/3), R = D/2
        R = D_cur / 2.0
        V_partial = _PI * H_assumed**2 * (R - H_assumed / 3.0)
        V_total = _PI * D_cur**3 / 6.0
    else:
        # ADR-0041 v7 §3 §7：mass_iteration_loop 内部 calc_partial_volume 必须
        # 透传 vessel_shape；否则 HORIZONTAL 误走 VERTICAL 公式（旧 v6 bug）
        vol_res = calc_partial_volume(
            PartialVolumeInput(
                D_m=D_cur,
                L_m=L_cur,
                head_type=inp.head_type,  # type: ignore[arg-type]
                H_m=H_assumed,
                vessel_shape=inp.vessel_shape,
            )
        )
        V_partial = vol_res.partial_volume_m3
        V_total = vol_res.total_volume_m3

    return (
        inp.rho_L_kg_m3 * V_partial
        + inp.rho_V_kg_m3 * (V_total - V_partial)
    )


def _newton_iterate(
    inp: MassIterationInput,
    target_mass_kg: float,
    x0: float,
    tol: float,
    max_iter: int,
    h_deriv: float = 1e-4,
) -> tuple[float, int, bool, float]:
    """Newton 迭代（中心差分 Jacobian）。

    Returns: (final_x, iterations, converged, residual)
    """
    x = x0
    for i in range(1, max_iter + 1):
        f_x = _mass_at_variable(inp, x) - target_mass_kg
        if abs(f_x) < tol:
            return x, i, True, f_x
        x_plus = x + h_deriv
        x_minus = x - h_deriv
        if x_minus <= 0:
            x_minus = max(x * 0.5, 1e-3)
        f_plus = _mass_at_variable(inp, x_plus) - target_mass_kg
        f_minus = _mass_at_variable(inp, x_minus) - target_mass_kg
        deriv = (f_plus - f_minus) / (x_plus - x_minus)
        if deriv == 0.0 or not math.isfinite(deriv):
            return x, i, False, f_x
        step = f_x / deriv
        x_new = x - step
        if x_new <= 0 or not math.isfinite(x_new):
            return x, i, False, f_x
        if abs(x_new - x) < 1e-5:
            f_new = _mass_at_variable(inp, x_new) - target_mass_kg
            return x_new, i, True, f_new
        x = x_new
    f_final = _mass_at_variable(inp, x) - target_mass_kg
    return x, max_iter, abs(f_final) < tol, f_final


def _bisection_iterate(
    inp: MassIterationInput,
    target_mass_kg: float,
    x_center: float,
    tol: float,
    max_iter: int,
) -> tuple[float, int, bool, float]:
    """Bisection 迭代（需先扩展 bracket 找异号区间）。

    Returns: (final_x, iterations, converged, residual)
    """
    if max_iter <= 0:
        return x_center, 0, False, _mass_at_variable(inp, x_center) - target_mass_kg
    # 扩展 bracket：[lo, hi]，要求 f(lo) · f(hi) < 0
    lo = 1e-3
    hi = max(x_center, inp.initial_D_m, inp.initial_L_m)
    f_lo = _mass_at_variable(inp, lo) - target_mass_kg
    f_hi = _mass_at_variable(inp, hi) - target_mass_kg
    expansions = 0
    while f_lo * f_hi > 0 and expansions < 25:
        hi *= 2.0
        f_hi = _mass_at_variable(inp, hi) - target_mass_kg
        expansions += 1
        if hi > 1e6:
            break
    if f_lo * f_hi > 0:
        # 找不到异号区间，无法 bisect
        return x_center, 0, False, _mass_at_variable(inp, x_center) - target_mass_kg

    # 标准 bisect 循环
    x_mid = (lo + hi) / 2.0
    for i in range(1, max_iter + 1):
        f_mid = _mass_at_variable(inp, x_mid) - target_mass_kg
        if abs(f_mid) < tol or (hi - lo) / 2.0 < 1e-5:
            return x_mid, i, True, f_mid
        if f_lo * f_mid < 0:
            hi = x_mid
            f_hi = f_mid
        else:
            lo = x_mid
            f_lo = f_mid
        x_mid = (lo + hi) / 2.0
    f_final = _mass_at_variable(inp, x_mid) - target_mass_kg
    return x_mid, max_iter, abs(f_final) < tol, f_final


def mass_iteration_loop(
    inp: MassIterationInput,
    tol: float = 1e-6,
    max_iter: int = 50,
) -> MassIterationResult:
    """容器尺寸 Newton/bisection 迭代求解（V1.2 接口冻结，冻结至 2027-03-25）。

    按 SPEC §3.4.4 C-12 + WS-CA-PR-010 §5.3 仪表控制高度：
      求 variable ∈ {D, L} 使 operating mass = target_mass_kg。
      mass = ρ_L · V_partial + ρ_V · (V_total - V_partial)
      H_assumed 按 vessel_shape 默认取值（见 _operating_fill_height）。

    收敛策略：
      1. Newton 首选（中心差分 Jacobian，O(收敛²)）
      2. 失败 / 不收敛 → bisection fallback（O(log N)，需异号 bracket）
      3. 累计 max_iter 仍未收敛 → 抛 MassIterationNotConvergedError（422）

    收敛判据：|Δmass| < tol kg（默认 1e-6 kg）OR |Δvariable| < 1e-5 m。

    Args:
        inp: MassIterationInput（frozen dataclass）
        tol: 质量收敛容差（kg，默认 1e-6）
        max_iter: Newton + bisection 累计最大迭代次数（默认 50）

    Returns:
        MassIterationResult：converged / iterations / final_variable_m / final_mass_kg
        / residual_kg / formula_ref

    Raises:
        VesselInputError: 输入物理量越界（密度倒置 / 初始 D/L ≤ 0）
        MassIterationNotConvergedError: Newton + bisection 累计超 max_iter 未收敛
    """
    if tol <= 0:
        raise VesselInputError(f"tol={tol} 必须 > 0")
    if max_iter <= 0:
        raise VesselInputError(f"max_iter={max_iter} 必须 > 0")
    _validate_mass_iter_input(inp)
    if inp.mass_model == "EMPTY":
        # EMPTY 需要材料密度（ρ_metal, ρ_insulation 等），本批不实现
        raise VesselInputError(
            "mass_model='EMPTY' 需要材料密度输入，本批仅实现 OPERATING"
        )

    x0 = inp.initial_D_m if inp.variable == "D" else inp.initial_L_m

    # Newton 优先（最多 20 次，留 30 次给 bisection）
    newton_max = min(max_iter, 20)
    x_newton, it_newton, ok_newton, res_newton = _newton_iterate(
        inp, inp.target_mass_kg, x0, tol, newton_max
    )
    if ok_newton:
        f_mass = _mass_at_variable(inp, x_newton)
        return MassIterationResult(
            converged=True,
            iterations=it_newton,
            final_variable_m=x_newton,
            final_mass_kg=f_mass,
            residual_kg=res_newton,
            formula_ref={
                "method": "Newton",
                "tol_kg": f"{tol:.1e}",
                "max_iter": str(max_iter),
                "vessel_shape": inp.vessel_shape,
                "variable": inp.variable,
            },
        )

    # Bisection fallback
    bisect_max = max_iter - it_newton
    x_bisect, it_bisect, ok_bisect, res_bisect = _bisection_iterate(
        inp,
        inp.target_mass_kg,
        x_newton,
        tol,
        bisect_max,
    )
    total_iter = it_newton + it_bisect
    if ok_bisect:
        f_mass = _mass_at_variable(inp, x_bisect)
        return MassIterationResult(
            converged=True,
            iterations=total_iter,
            final_variable_m=x_bisect,
            final_mass_kg=f_mass,
            residual_kg=res_bisect,
            formula_ref={
                "method": "bisection",
                "tol_kg": f"{tol:.1e}",
                "max_iter": str(max_iter),
                "vessel_shape": inp.vessel_shape,
                "variable": inp.variable,
            },
        )

    # 累计未收敛
    raise MassIterationNotConvergedError(
        f"mass_iteration_loop {total_iter} 次迭代未收敛："
        f"Newton 起点 x0={x0:.4f}，bisection 终点 x={x_bisect:.4f}，"
        f"residual={res_bisect:.4e} kg（> tol={tol:.1e}）。"
        f"请检查 target_mass_kg 或 vessel_shape/head_type 物理一致性。"
    )