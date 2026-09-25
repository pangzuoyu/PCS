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
    """

    D_m: float
    L_m: float
    head_type: HeadType
    H_m: float
    n_vessels: int = 1


@dataclass(frozen=True)
class PartialVolumeResult:
    """calc_partial_volume 输出（frozen dataclass，V1.2 接口冻结）。

    字段：
      - partial_volume_m3: 单容器部分液相体积
      - total_volume_m3: 单容器总容积（n_vessels × 此值 = 多容器总容积）
      - head_volume_m3: 单容器封头部分容积（底部 + 顶部封头，液位侵入部分）
      - cylinder_volume_m3: 单容器筒体部分液相体积
      - formula_ref: 公式溯源（dict[str, str]）
    """

    partial_volume_m3: float
    total_volume_m3: float
    head_volume_m3: float
    cylinder_volume_m3: float
    formula_ref: dict[str, str]


@dataclass(frozen=True)
class WettedAreaInput:
    """calc_wetted_area 输入（frozen dataclass，V1.2 接口冻结）。"""

    D_m: float
    L_m: float
    head_type: HeadType
    H_m: float
    n_vessels: int = 1


@dataclass(frozen=True)
class WettedAreaResult:
    """calc_wetted_area 输出（frozen dataclass，V1.2 接口冻结）。

    字段：
      - wetted_area_m2: 单容器润湿面积
      - total_wetted_area_m2: 单容器总外表面积（n_vessels × 此值 = 多容器总外表）
      - head_area_m2: 单容器封头润湿面积（底部 + 顶部封头，液位接触部分）
      - cylinder_area_m2: 单容器筒体润湿面积 = π·D·L_liq
      - formula_ref: 公式溯源
    """

    wetted_area_m2: float
    total_wetted_area_m2: float
    head_area_m2: float
    cylinder_area_m2: float
    formula_ref: dict[str, str]


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


def _validate_geometry_input(D_m: float, L_m: float, H_m: float) -> None:
    """几何输入边界校验（D/L/H > 0）。"""
    if D_m <= 0:
        raise VesselInputError(f"D_m={D_m} 必须 > 0")
    if L_m <= 0:
        raise VesselInputError(f"L_m={L_m} 必须 > 0")
    if H_m < 0:
        raise VesselInputError(f"H_m={H_m} 必须 ≥ 0")


def calc_partial_volume(inp: PartialVolumeInput) -> PartialVolumeResult:
    """计算容器部分液相体积（V1.2 接口冻结，冻结至 2027-03-25）。

    按 SPEC §3.4.4 C-12 算法：
      V_partial = V_head_bottom + V_cyl + V_head_top
      其中：
        - V_head_bottom = _head_partial_volume(D, head_type, Z_b), Z_b = min(H, b)
        - V_head_top = _head_partial_volume(D, head_type, Z_t), Z_t = max(0, H - L - b)
        - V_cyl = π·D²/4·L_liq, L_liq = max(0, min(H - b, L) - max(0, H - L - b))

    Args:
        inp: PartialVolumeInput（frozen dataclass）

    Returns:
        PartialVolumeResult：单容器 partial_volume_m3 + total_volume_m3 + 头部/筒体分解。
        n_vessels 缩放仅在调用方按 total_volume_m3 × n_vessels 计算；
        partial_volume_m3 为单容器值，便于 C-07/C-08 sizing 等单容器模块直接复用。
    """
    D_m = inp.D_m
    L_m = inp.L_m
    head_type = inp.head_type
    H_m = inp.H_m
    _validate_geometry_input(D_m, L_m, H_m)
    if inp.n_vessels < 1:
        raise VesselInputError(f"n_vessels={inp.n_vessels} 必须 ≥ 1")

    b = _head_depth(D_m, head_type)
    r = D_m / 2.0
    A_cs = _PI * r**2  # 圆柱横截面积

    # 底部封头液位高度（不超过封头深度）
    z_bottom = min(H_m, b)
    V_head_bottom = _head_partial_volume(D_m, head_type, z_bottom)

    # 顶部封头液位高度（液位超过 L + b 时才有）
    z_top = max(0.0, H_m - L_m - b)
    V_head_top = _head_partial_volume(D_m, head_type, z_top)

    # 圆柱主体液位长度（不超过 L）
    L_liq_bottom = max(0.0, H_m - b)  # 液位从底部封头顶起算
    L_liq_top = max(0.0, H_m - L_m - b)  # 液位从顶部封头顶起算（向下）
    L_liq_cyl = max(0.0, min(L_liq_bottom, L_m) - L_liq_top)
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
        },
    )


def calc_wetted_area(inp: WettedAreaInput) -> WettedAreaResult:
    """计算容器润湿面积（V1.2 接口冻结，冻结至 2027-03-25）。

    按 SPEC §3.4.4 C-12 算法：
      A_wetted = A_head_bottom + A_cyl + A_head_top
      其中：
        - A_head_bottom = _head_partial_area(D, head_type, Z_b)
        - A_head_top = _head_partial_area(D, head_type, Z_t)
        - A_cyl = π·D·L_liq

    Args:
        inp: WettedAreaInput（frozen dataclass）

    Returns:
        WettedAreaResult：单容器 wetted_area_m2 + total_wetted_area_m2 + 头/筒分解。
    """
    D_m = inp.D_m
    L_m = inp.L_m
    head_type = inp.head_type
    H_m = inp.H_m
    _validate_geometry_input(D_m, L_m, H_m)
    if inp.n_vessels < 1:
        raise VesselInputError(f"n_vessels={inp.n_vessels} 必须 ≥ 1")

    b = _head_depth(D_m, head_type)

    z_bottom = min(H_m, b)
    A_head_bottom = _head_partial_area(D_m, head_type, z_bottom)

    z_top = max(0.0, H_m - L_m - b)
    A_head_top = _head_partial_area(D_m, head_type, z_top)

    L_liq_bottom = max(0.0, H_m - b)
    L_liq_top = max(0.0, H_m - L_m - b)
    L_liq_cyl = max(0.0, min(L_liq_bottom, L_m) - L_liq_top)
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
        },
    )