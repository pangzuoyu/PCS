"""restriction_engine ISO 5167 + 多级降压 + 闪蒸校核 + HEM 模型（P6-1 Task 12 + P6-2 S-01）。

完整实现 SPEC §3.2.2.1~4 + 评审委员会 2026-09-24 闪蒸路径裁决：
- §3.2.2.1 限流孔板 ISO 5167-2（Reader-Harris 3 项截断 + ISO 5167-2 ε）
- §3.2.2.2 文丘里 ISO 5167-4（C 取典型 0.99 + ISO 5167-4 κ=1.4 ε）
- §3.2.2.3 喷嘴 ISO 5167-3（ISA 1932 完整 + ISO 5167-3 κ=1.4 ε）
- §3.2.2.4 多级降压（等分 dP + 单级阻塞流校核）
- §3.2.2.1 闪蒸校核：调 P4 flash_service.calc_pure_fluid_bubble_point_pa 求 P_sat；
  若 P_outlet < P_sat → 闪蒸，切换 HEM 模型（API STD 520 Annex C）

设计要点：
- 不调 fluids.*（依 ADR-0030 V1.1 决策 6）；
  基础公式经 chedl_wrapper.flow_meter_*（Task 3 已落地）。
- 闪蒸校核走 P4 flash_service（calc_pure_fluid_bubble_point_pa adapter 包装
  SATURATION 纯组分饱和）；**禁止保留 P1<50 kPa 启发式**（红线）。
- 闪蒸工况走 HEM 模型（API STD 520 Annex C 均相平衡 + Moody 滑脱修正）。
- 组装 13 键 payload 对齐 RestrictionResult ORM（SPEC §3.2.2.6）+ flash 元数据
  （P_sat_pa / vapor_fraction_at_outlet / model_used）。
- 多级降压判定：单级 dP 大于 70% 总 dP 视为阻塞流（工程经验式，等分 dP 简易判据）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services import chedl_wrapper
from app.services.flash import flash_service

# ============================================================================
# 单元计算函数（4 个独立 helper；Task 13 service 层组合）
# ============================================================================


def _compute_orifice(
    D: float, d: float, Re_D: float, P1: float, dP: float, rho1: float
) -> tuple[float, float, float]:
    """限流孔板（C, ε, Re_D）— ISO 5167-2 Reader-Harris/Gallagher 3 项截断。

    复用 chedl_wrapper.flow_meter_orifice（Task 3 Path A 自研）；
    Re_D 由入参直接透传（流场计算由调用方提供）。
    """
    C, epsilon = chedl_wrapper.flow_meter_orifice(
        D_m=D, d_m=d, Re_D=Re_D, P1_pa=P1, dP_pa=dP, rho1=rho1
    )
    return (C, epsilon, Re_D)


def _compute_venturi(
    D: float, d: float, Re_D: float, P1: float, dP: float, rho1: float
) -> tuple[float, float, float]:
    """文丘里（C, ε, Re_D）— ISO 5167-4 铸造标准 C=0.99 + κ=1.4 ε。

    复用 chedl_wrapper.flow_meter_venturi（Task 3 Path A 自研）。
    """
    C, epsilon = chedl_wrapper.flow_meter_venturi(
        D_m=D, d_m=d, Re_D=Re_D, P1_pa=P1, dP_pa=dP, rho1=rho1
    )
    return (C, epsilon, Re_D)


def _compute_nozzle(
    D: float, d: float, Re_D: float, P1: float, dP: float, rho1: float
) -> tuple[float, float, float]:
    """喷嘴（C, ε, Re_D）— ISO 5167-3 ISA 1932 完整 + κ=1.4 ε。

    复用 chedl_wrapper.flow_meter_nozzle（Task 3 Path A 自研）。
    """
    C, epsilon = chedl_wrapper.flow_meter_nozzle(
        D_m=D, d_m=d, Re_D=Re_D, P1_pa=P1, dP_pa=dP, rho1=rho1
    )
    return (C, epsilon, Re_D)


def _compute_multi_stage(
    total_dP_pa: float, stages: int, single_stage_dP_pa: float = 0.0
) -> tuple[float, bool]:
    """多级降压（每级 dP, choked）— 等分 dP + 单级阻塞流判据。

    公式：
        per_stage_dP = total_dP_pa / stages

    阻塞流判据（工程经验式，Task 3 简化口径）：
        单级 dP ≥ 0.7 × total_dP_pa（单级承担过大份额视为临界流）
        或 single_stage_dP_pa > per_stage_dP（用户指定单级超过均分值）

    Args:
        total_dP_pa: 总压差 Pa
        stages: 级数（必须 ≥ 1；>5 需单独评估 P6-OPEN-007）
        single_stage_dP_pa: 单级 dP（用户指定；默认 0 = 仅按均分判据）

    Returns:
        (per_stage_dP_pa, choked)
    """
    if stages < 1:
        raise ValueError(f"_compute_multi_stage stages 必须 ≥ 1：stages={stages}")
    if total_dP_pa <= 0:
        raise ValueError(
            f"_compute_multi_stage total_dP_pa 必须正数：total_dP_pa={total_dP_pa}"
        )
    per_stage_dP = total_dP_pa / stages
    choked = (single_stage_dP_pa > per_stage_dP) or (per_stage_dP >= 0.7 * total_dP_pa)
    return (per_stage_dP, choked)


# ============================================================================
# P6-2 S-01：闪蒸校核 + HEM 模型（API STD 520 Annex C）
# ============================================================================


@dataclass(frozen=True)
class FlashCheckResult:
    """闪蒸校核结果（P6-2 S-01 替换 P1<50 kPa 启发式）。

    字段：
    - flashing：是否闪蒸（P_outlet < P_sat）
    - P_sat_pa：上游泡点压力 Pa（流体已知时由 flash_service 给出；不可知则为 None）
    - vapor_fraction_at_outlet：节流后工况气相分率（0~1；非闪蒸为 0.0）
    - model_used：调用的物理模型（ISO_5167 或 HEM）
    - error_code：flash_service 异常时的错误码（无异常时为 None）
        - "fluid_unknown" / "T_supercritical" / "T_unphysical"
    """

    flashing: bool
    P_sat_pa: float | None
    vapor_fraction_at_outlet: float
    model_used: Literal["ISO_5167", "HEM"]
    error_code: str | None = None


@dataclass(frozen=True)
class HEMResult:
    """HEM 模型流量计算结果（API STD 520 Annex C）。

    字段：
    - G_hem_kg_s：HEM 流量 kg/s（正比于 Cd·A·sqrt(F_t²·ρ_hem·dP)）
    - rho_hem_kg_m3：HEM 均相密度 kg/m³（1/(x/ρ_v + (1-x)/ρ_l)）
    - F_t：Moody 滑脱因子（sqrt((1-x) + x·sqrt(ρ_l/ρ_v))）
    - x_vapor_outlet：节流后气相分率（0~1）
    """

    G_hem_kg_s: float
    rho_hem_kg_m3: float
    F_t: float
    x_vapor_outlet: float


def calc_restriction_hem(
    *,
    Cd: float,
    A_m2: float,
    dP_pa: float,
    rho_l_kg_m3: float,
    rho_v_kg_m3: float,
    x_vapor_outlet: float,
) -> HEMResult:
    """闪蒸工况流量（API STD 520 Annex C HEM + Moody 滑脱，P6-2 S-01）。

    HEM (Homogeneous Equilibrium Model)：
    - 均相密度：ρ_hem = 1/(x/ρ_v + (1-x)/ρ_l)
    - Moody 滑脱因子：F_t = sqrt((1-x) + x·sqrt(ρ_l/ρ_v))
    - 流量：G_hem = Cd · A · sqrt(F_t² · ρ_hem · dP)

    Args:
        Cd: 流出系数（无量纲；ISO 5167 单相 C 或 HEM 工况 Cd ≈ C_iso）
        A_m2: 节流孔面积 m²
        dP_pa: 节流压差 Pa
        rho_l_kg_m3: 液体密度 kg/m³
        rho_v_kg_m3: 气体密度 kg/m³
        x_vapor_outlet: 节流后工况气相分率（0~1；调用方提供）

    Returns:
        HEMResult(G_hem_kg_s, rho_hem_kg_m3, F_t, x_vapor_outlet)

    Raises:
        ValueError: A_m2/dP_pa 非正；rho_l/rho_v 非正；x_vapor_outlet ∉ [0, 1]
    """
    if A_m2 <= 0:
        raise ValueError(f"calc_restriction_hem A_m2 必须正数：A_m2={A_m2}")
    if dP_pa <= 0:
        raise ValueError(f"calc_restriction_hem dP_pa 必须正数：dP_pa={dP_pa}")
    if rho_l_kg_m3 <= 0:
        raise ValueError(
            f"calc_restriction_hem rho_l_kg_m3 必须正数：rho_l_kg_m3={rho_l_kg_m3}"
        )
    if rho_v_kg_m3 <= 0:
        raise ValueError(
            f"calc_restriction_hem rho_v_kg_m3 必须正数：rho_v_kg_m3={rho_v_kg_m3}"
        )
    if not 0.0 <= x_vapor_outlet <= 1.0:
        raise ValueError(
            f"calc_restriction_hem x_vapor_outlet 必须在 [0, 1]："
            f"x_vapor_outlet={x_vapor_outlet}"
        )

    # 1) HEM 均相密度（双相密度调和）
    # 单相退化：x = 0 → ρ_hem = ρ_l；x = 1 → ρ_hem = ρ_v
    rho_hem = 1.0 / (x_vapor_outlet / rho_v_kg_m3 + (1.0 - x_vapor_outlet) / rho_l_kg_m3)

    # 2) Moody 滑脱因子（F_t² = (1-x) + x·sqrt(ρ_l/ρ_v)）
    F_t = ((1.0 - x_vapor_outlet) + x_vapor_outlet * (rho_l_kg_m3 / rho_v_kg_m3) ** 0.5) ** 0.5

    # 3) HEM 流量
    G_hem_kg_s = Cd * A_m2 * (F_t**2 * rho_hem * dP_pa) ** 0.5

    return HEMResult(
        G_hem_kg_s=G_hem_kg_s,
        rho_hem_kg_m3=rho_hem,
        F_t=F_t,
        x_vapor_outlet=x_vapor_outlet,
    )


def _approximate_vapor_fraction_at_outlet(
    *, P_outlet_pa: float, P_sat_pa: float
) -> float:
    """节流后工况气相分率近似估算（P_outlet < P_sat 时使用）。

    工程经验式（P6-2 S-01 MVP）：
    - P_outlet >= P_sat → x = 0（无闪蒸）
    - P_outlet < P_sat → x ≈ 1 - P_outlet/P_sat（线性近似；保守不低估气相）

    更精确的 HEM x 需 composition + PT_FLASH 求解，本任务 MVP 用线性近似；
    后续 P6-OPEN-008 评估是否升级到 PT_FLASH 精确求解。

    Args:
        P_outlet_pa: 节流后压力 Pa
        P_sat_pa: 上游泡点压力 Pa

    Returns:
        x_vapor ∈ [0, 1]
    """
    if P_outlet_pa >= P_sat_pa or P_sat_pa <= 0:
        return 0.0
    # 线性近似：节流后压力越低，气相分率越高
    return min(1.0, max(0.0, 1.0 - P_outlet_pa / P_sat_pa))


async def check_flashing(
    *,
    fluid: str | None,
    upstream_T_K: float | None,
    P1_pa: float,
    P_outlet_pa: float,
) -> FlashCheckResult:
    """闪蒸校核（替换 P1<50 kPa 启发式，P6-2 S-01 评审委员会裁决）。

    流程：
    1. 调 P4 flash_service.calc_pure_fluid_bubble_point_pa(fluid, T_K) 求 P_sat
    2. P_outlet < P_sat → flashing=True（节流后压力低于泡点 → 闪蒸）
    3. 估算节流后气相分率（_approximate_vapor_fraction_at_outlet）

    Args:
        fluid: 流体名（WATER / PROPANE 等）；None 时不闪蒸（graceful fallback）
        upstream_T_K: 上游温度 K；None 时不闪蒸
        P1_pa: 上游绝压 Pa（仅用于校验 >0）
        P_outlet_pa: 节流后压力 Pa（P1_pa - dP_pa）

    Returns:
        FlashCheckResult 含 flashing / P_sat_pa / vapor_fraction / model_used
    """
    if fluid is None or upstream_T_K is None or P1_pa <= 0:
        # 缺关键输入 → 保守不闪蒸 + 走 ISO 5167；调用方负责提供 fluid/T_K
        return FlashCheckResult(
            flashing=False,
            P_sat_pa=None,
            vapor_fraction_at_outlet=0.0,
            model_used="ISO_5167",
            error_code="missing_input" if (fluid is None or upstream_T_K is None) else None,
        )

    try:
        P_sat_pa = flash_service.calc_pure_fluid_bubble_point_pa(
            fluid=fluid, T_K=upstream_T_K
        )
    except flash_service.SaturationInputError:
        # 流体名不识别 → 保守不闪蒸 + 标记 error_code（工艺工程师需修 fluid 名）
        return FlashCheckResult(
            flashing=False,
            P_sat_pa=None,
            vapor_fraction_at_outlet=0.0,
            model_used="ISO_5167",
            error_code="fluid_unknown",
        )
    except flash_service.SaturationRangeError:
        # T > Tc 超临界 → 闪蒸概念不适用；走 ISO 5167
        return FlashCheckResult(
            flashing=False,
            P_sat_pa=None,
            vapor_fraction_at_outlet=0.0,
            model_used="ISO_5167",
            error_code="T_supercritical",
        )

    # 闪蒸判定：节流后压力 < 泡点压力 → 闪蒸
    flashing = P_outlet_pa < P_sat_pa
    vapor_fraction = _approximate_vapor_fraction_at_outlet(
        P_outlet_pa=P_outlet_pa, P_sat_pa=P_sat_pa
    )
    model = "HEM" if flashing else "ISO_5167"

    return FlashCheckResult(
        flashing=flashing,
        P_sat_pa=P_sat_pa,
        vapor_fraction_at_outlet=vapor_fraction,
        model_used=model,  # type: ignore[arg-type]
    )


# ============================================================================
# RestrictionEngine 主入口（P6-1 Task 12 + P6-2 S-01 闪蒸校核）
# ============================================================================


class RestrictionEngine:
    """限制装置（孔板/文丘里/喷嘴/多级降压）计算引擎（P6-1 + P6-2 S-01）。

    入口：calculate(**kwargs) → dict（async；P6-2 S-01 升级）
    - device_type: "ORIFICE" / "VENTURI" / "NOZZLE" / "MULTI_STAGE"
    - 依据 device_type 分流到 _compute_orifice/venturi/nozzle/multi_stage
    - 闪蒸校核：调 check_flashing 决定 model_used（ISO_5167 / HEM）
    - 组装 13 键 payload 对齐 RestrictionResult ORM（SPEC §3.2.2.6）
      + flash 元数据（P_sat_pa / vapor_fraction_at_outlet / model_used）

    详细 Pydantic RestrictionCalculateRequest（按 SPEC §3.2.2.6 schema）由
    Task 14 接入；本任务最小字段 + dict 返回以解耦 restriction_persist 落地。
    """

    # 默认标准代码（SPEC §3.2.2 默认 ISO-5167 系列；与 cv_engine 的 API-60534 不同）
    _DEFAULT_STANDARD_PROFILE = "ISO-5167"
    _DEFAULT_DESIGN_STAGE = "BASIC"
    _DEFAULT_FLUID_PHASE = "LIQUID"
    _DEFAULT_RESTRICTION_TYPE = "ORIFICE"
    # 闪蒸校核缺省 fluid（多数节流装置为水/烃主流工况；按 spec §3.2.2.1 水优先）
    _DEFAULT_FLUID = "WATER"
    _DEFAULT_UPSTREAM_T_K = 298.15  # 25 °C 标况

    # device_type → 字符串映射（v3_1 stub 列 restriction_type 兼容用）
    _DEVICE_TO_RESTRICTION_TYPE: dict[str, str] = {
        "ORIFICE": "ORIFICE",
        "VENTURI": "VENTURI",
        "NOZZLE": "NOZZLE",
        "MULTI_STAGE": "MULTI_STAGE",
    }

    async def calculate(self, **kwargs: Any) -> dict[str, Any]:
        """主入口：依据 device_type 分流计算 + 闪蒸校核切换模型，返回 payload。

        必需 kwargs（按 device_type 分流）：
        - 公共：D_pipe_m, d_solved_m, Re_D, P1_pa, dP_pa, rho1
        - 仅 MULTI_STAGE：stages（默认 1）
        - 可选：fluid_phase, design_stage, standard_profile_code, mu, stages,
          fluid, upstream_T_K, rho_l_kg_m3, rho_v_kg_m3, x_vapor_outlet

        Returns:
            dict 含 RestrictionResult ORM 13 SPEC §3.2.2.6 字段 + flash 元数据：
            - flashing, P_sat_pa, vapor_fraction_at_outlet, model_used

        Raises:
            ValueError: device_type 不在白名单 / 几何参数异常
        """
        device_type: str = kwargs.get("device_type")
        if device_type not in self._DEVICE_TO_RESTRICTION_TYPE:
            raise ValueError(
                f"RestrictionEngine.calculate device_type 必须 ∈ "
                f"{{ORIFICE/VENTURI/NOZZLE/MULTI_STAGE}}：实际 {device_type!r}"
            )

        # 解析公共字段
        D = kwargs.get("D_pipe_m")
        d = kwargs.get("d_solved_m")
        Re_D = kwargs.get("Re_D")
        P1 = kwargs.get("P1_pa")
        dP = kwargs.get("dP_pa")
        rho1 = kwargs.get("rho1")

        # 几何
        beta_ratio = d / D if (D and d) else 0.0

        # 闪蒸校核（P6-2 S-01：替换 P1<50 kPa 启发式）
        fluid = kwargs.get("fluid", self._DEFAULT_FLUID)
        upstream_T_K = kwargs.get("upstream_T_K", self._DEFAULT_UPSTREAM_T_K)
        P_outlet = (P1 - dP) if (P1 is not None and dP is not None) else 0.0
        flash_check = await check_flashing(
            fluid=fluid,
            upstream_T_K=upstream_T_K,
            P1_pa=P1 if P1 is not None else 0.0,
            P_outlet_pa=P_outlet,
        )

        # 初始化 13 键 payload（SPEC §3.2.2.6 平铺 13 列 + flash 元数据）
        payload: dict[str, Any] = {
            "device_type": device_type,
            "D_pipe_m": D if D is not None else 0.0,
            "d_solved_m": d if d is not None else 0.0,
            "beta_ratio": beta_ratio,
            "C_discharge": None,
            "epsilon": None,
            "Re_D": Re_D,
            "delta_P_pa": dP if dP is not None else 0.0,
            "delta_omega_pa": None,
            "choked": False,
            "flashing": flash_check.flashing,
            "stages": kwargs.get("stages", 1),
            "design_stage": kwargs.get("design_stage", self._DEFAULT_DESIGN_STAGE),
            # P6-2 S-01 flash 元数据
            "P_sat_pa": flash_check.P_sat_pa,
            "vapor_fraction_at_outlet": flash_check.vapor_fraction_at_outlet,
            "model_used": flash_check.model_used,
            "fluid": fluid,
            "upstream_T_K": upstream_T_K,
            "flash_error_code": flash_check.error_code,
        }

        # HEM 模型分支（闪蒸工况）：计算 G_hem 占位（G_hem_kg_s 暂不入 ORM
        # 列；output_json 容器承载；C_discharge 保留 ISO 5167 值供持久化）
        if flash_check.flashing:
            # HEM 物理量计算需要 rho_l/rho_v/x_vapor；service 层负责补
            rho_l_hem = kwargs.get("rho_l_kg_m3")
            rho_v_hem = kwargs.get("rho_v_kg_m3")
            x_vapor_hem = kwargs.get(
                "x_vapor_outlet", flash_check.vapor_fraction_at_outlet
            )
            if (
                rho_l_hem is not None
                and rho_v_hem is not None
                and payload["C_discharge"] is None  # 留到 ISO 5167 段填
            ):
                # 单装置走 HEM：Cd 暂用 0.62（孔板中值），A 用孔口面积 πd²/4
                Cd_hem = 0.62 if device_type == "ORIFICE" else 0.97
                dA_m2 = 3.14159265 * d**2 / 4.0 if d else 0.0
                try:
                    hem = calc_restriction_hem(
                        Cd=Cd_hem,
                        A_m2=dA_m2,
                        dP_pa=dP if dP is not None else 0.0,
                        rho_l_kg_m3=rho_l_hem,
                        rho_v_kg_m3=rho_v_hem,
                        x_vapor_outlet=x_vapor_hem,
                    )
                    payload["G_hem_kg_s"] = hem.G_hem_kg_s
                    payload["rho_hem_kg_m3"] = hem.rho_hem_kg_m3
                    payload["F_t"] = hem.F_t
                except ValueError:
                    payload["G_hem_kg_s"] = None
                    payload["rho_hem_kg_m3"] = None
                    payload["F_t"] = None

        # 分流计算（ISO 5167 路径）
        if device_type == "MULTI_STAGE":
            # 多级降压：等分 dP + 阻塞流判据；C/ε 由首孔板承担（取 orifice 计算）
            stages = payload["stages"]
            single_stage_dP = kwargs.get("single_stage_dP_pa", 0.0)
            per_stage_dP, choked = _compute_multi_stage(
                total_dP_pa=dP or 0.0,
                stages=stages,
                single_stage_dP_pa=single_stage_dP,
            )
            payload["delta_omega_pa"] = per_stage_dP
            payload["choked"] = choked
            # 多级视为串联，每级仍走孔板公式（取首级作为代表）
            if D and d and Re_D and P1 and dP and rho1:
                C, epsilon, _ = _compute_orifice(
                    D=D, d=d, Re_D=Re_D, P1=P1, dP=dP, rho1=rho1
                )
                payload["C_discharge"] = C
                payload["epsilon"] = epsilon
        else:
            # 单装置（ORIFICE / VENTURI / NOZZLE）— 共用 _compute_X 签名
            if D and d and Re_D and P1 and dP and rho1:
                if device_type == "ORIFICE":
                    C, epsilon, _ = _compute_orifice(
                        D=D, d=d, Re_D=Re_D, P1=P1, dP=dP, rho1=rho1
                    )
                elif device_type == "VENTURI":
                    C, epsilon, _ = _compute_venturi(
                        D=D, d=d, Re_D=Re_D, P1=P1, dP=dP, rho1=rho1
                    )
                else:  # NOZZLE
                    C, epsilon, _ = _compute_nozzle(
                        D=D, d=d, Re_D=Re_D, P1=P1, dP=dP, rho1=rho1
                    )
                payload["C_discharge"] = C
                payload["epsilon"] = epsilon
                # 阻塞流简化判据：dP/P1 > 0.5（气体工程经验，Task 3 v1.0 不细分）
                payload["choked"] = dP / P1 > 0.5

        # 标准代码 + 设计阶段 + 标准 profile（占位默认；Task 14 接 schema）
        payload["standard_profile_code"] = kwargs.get(
            "standard_profile_code", self._DEFAULT_STANDARD_PROFILE
        )
        # 显式覆盖 design_stage（若 kwargs 显式传）
        if "design_stage" in kwargs:
            payload["design_stage"] = kwargs["design_stage"]

        return payload


__all__ = [
    "_compute_orifice",
    "_compute_venturi",
    "_compute_nozzle",
    "_compute_multi_stage",
    "calc_restriction_hem",
    "HEMResult",
    "check_flashing",
    "FlashCheckResult",
    "RestrictionEngine",
]