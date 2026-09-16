"""P5-1-1 vessel_service 核心（Souders-Brown + D_min + 停留时间）。

按 ADR-0032 V1.0（P5-1-1 起草）：
- ChEDL 分层（业务代码禁直接 import fluids，统一 chedl_wrapper）
- K 因子单位约定 SI m/s
- 停留时间按 vessel_type 分支（vertical=3~5 min / horizontal=5~10 min）
- 纯函数不触 DB（P5-1-4 才落库）
- 输入/输出均为 frozen dataclass（不可变 + 可哈希）

公式：
  V_max = K × √((ρ_L - ρ_V) / ρ_V)        [Souders-Brown, m/s]
  D_min = √(4 × Q_v / (π × V_max))         [m]
  V_liq = Q_L × t_residence                [m³]

与 ChEDL `fluids.separator.v_Souders_Brown(K, rhol, rhog)` 交叉验证 ≤1%。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services import chedl_wrapper
from app.services.exceptions import PcsError

# 类型别名
VesselType = Literal["VERTICAL", "HORIZONTAL", "WITH_DEMISTER"]
CheckResult = Literal["PASS", "WARNING", "FAIL"]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]

# 物理常量（ISO 80000-3）
_PI: Final[float] = math.pi

# K 因子边界（SI m/s，PCS-PLAN §134 + ADR-0032 决策 2）
_K_LOW_BOUND: Final[float] = 0.01   # 物理下限
_K_HIGH_BOUND: Final[float] = 1.0   # 物理上限
# 典型区间：开区间 (0.04, 0.15)，边界值视为 MEDIUM（保守）
# vessel_type 推荐子区间（仅供 SPEC 修订对齐参考，不影响 HIGH/MEDIUM 判定）：
#   - VERTICAL / WITH_DEMISTER: (0.04, 0.10)
#   - HORIZONTAL: (0.07, 0.15)
_K_TYPICAL_MIN: Final[float] = 0.04  # GPSA K 因子下界（PCS-PLAN §134）
_K_TYPICAL_MAX: Final[float] = 0.15  # GPSA K 因子上界（PCS-PLAN §134）

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
    """K 因子置信度分类（开区间 (0.04, 0.15)：边界值视为 MEDIUM）。

    典型区间 = GPSA 全范围 (0.04, 0.15) 开区间。vessel_type 不影响 HIGH/MEDIUM 判定
    （仅影响推荐子区间，详 ADR-0032 决策 2 注记）。

    K 严格落在 (0.04, 0.15) 内 → HIGH（典型工况）
    K = 0.04 或 0.15（边界值）→ MEDIUM（保守）
    K < 0.04 或 K > 0.15 → MEDIUM（区间外）

    Note:
        vessel_type 参数保留供未来扩展（如除沫器特殊逻辑）；当前不影响判定。
    """
    del vessel_type  # 未使用，保留接口供扩展
    if _K_TYPICAL_MIN < K < _K_TYPICAL_MAX:
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