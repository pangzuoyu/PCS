"""restriction_engine ISO 5167 + 多级降压计算核心（P6-1 Task 12）。

完整实现 SPEC §3.2.2.1~4：
- §3.2.2.1 限流孔板 ISO 5167-2（Reader-Harris 3 项截断 + ISO 5167-2 ε）
- §3.2.2.2 文丘里 ISO 5167-4（C 取典型 0.99 + ISO 5167-4 κ=1.4 ε）
- §3.2.2.3 喷嘴 ISO 5167-3（ISA 1932 完整 + ISO 5167-3 κ=1.4 ε）
- §3.2.2.4 多级降压（等分 dP + 单级阻塞流校核）

设计要点：
- 不调 fluids.*（依 ADR-0030 V1.1 决策 6）；
  基础公式经 chedl_wrapper.flow_meter_*（Task 3 已落地）。
- 不引入 Pydantic schema（Task 14 才接 RestrictionCalculateRequest）；
  本任务 RestrictionEngine.calculate() 接收 **kwargs 最小必要字段 + 返回 dict。
- 组装 13 键 payload 对齐 RestrictionResult ORM（SPEC §3.2.2.6）。
- 多级降压判定：单级 dP 大于 70% 总 dP 视为阻塞流（工程经验式，等分 dP 简易判据）。
"""
from __future__ import annotations

from typing import Any, Literal

from app.services import chedl_wrapper

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
# RestrictionEngine 主入口（P6-1 Task 12）
# ============================================================================


class RestrictionEngine:
    """限制装置（孔板/文丘里/喷嘴/多级降压）计算引擎（P6-1 Task 12）。

    入口：calculate(**kwargs) → dict
    - device_type: "ORIFICE" / "VENTURI" / "NOZZLE" / "MULTI_STAGE"
    - 依据 device_type 分流到 _compute_orifice/venturi/nozzle/multi_stage
    - 组装 13 键 payload 对齐 RestrictionResult ORM（SPEC §3.2.2.6）

    详细 Pydantic RestrictionCalculateRequest（按 SPEC §3.2.2.6 schema）由
    Task 14 接入；本任务最小字段 + dict 返回以解耦 restriction_persist（Task 13）落地。
    """

    # 默认标准代码（SPEC §3.2.2 默认 ISO-5167 系列；与 cv_engine 的 API-60534 不同）
    _DEFAULT_STANDARD_PROFILE = "ISO-5167"
    _DEFAULT_DESIGN_STAGE = "BASIC"
    _DEFAULT_FLUID_PHASE = "LIQUID"
    _DEFAULT_RESTRICTION_TYPE = "ORIFICE"

    # device_type → 字符串映射（v3_1 stub 列 restriction_type 兼容用）
    _DEVICE_TO_RESTRICTION_TYPE: dict[str, str] = {
        "ORIFICE": "ORIFICE",
        "VENTURI": "VENTURI",
        "NOZZLE": "NOZZLE",
        "MULTI_STAGE": "MULTI_STAGE",
    }

    def calculate(self, **kwargs: Any) -> dict[str, Any]:
        """主入口：依据 device_type 分流计算，返回 RestrictionResult 13 键 payload。

        必需 kwargs（按 device_type 分流）：
        - 公共：D_pipe_m, d_solved_m, Re_D, P1_pa, dP_pa, rho1
        - 仅 MULTI_STAGE：stages（默认 1）
        - 可选：fluid_phase, design_stage, standard_profile_code, mu, stages

        Returns:
            dict 含 RestrictionResult ORM 13 SPEC §3.2.2.6 字段。
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

        # 初始化 13 键 payload（SPEC §3.2.2.6 平铺 13 列）
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
            "flashing": False,
            "stages": kwargs.get("stages", 1),
            "design_stage": kwargs.get("design_stage", self._DEFAULT_DESIGN_STAGE),
        }

        # 分流计算
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

        # 闪蒸判定（液体 + P1 接近蒸汽压）— 工程简化：Pv 默认 2000 Pa（25°C 水）
        # 完整 FLASH 联校核留 P6+ Task 扩展；本任务仅做启发式简化判据。
        fluid_phase: Literal["LIQUID", "GAS"] = kwargs.get(
            "fluid_phase", self._DEFAULT_FLUID_PHASE
        )
        if fluid_phase == "LIQUID" and P1 is not None and P1 > 0:
            # 简化：P1 < 50 kPa 视为可能闪蒸（饱和蒸汽压假设 ≈ 23 kPa @25°C）
            if P1 < 50_000.0:
                payload["flashing"] = True

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
    "RestrictionEngine",
]