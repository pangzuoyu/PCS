"""P4-4-2：NPSHa 计算服务（吸入侧管线阻力 + 汽蚀余量 + 沿用 P4-2 精度护栏）。

公式（ANSI/HI 9.6.6-2016）：
    NPSHa = (Ps - Pv) / (rho * g) - h_loss
其中：
    Ps       上游系统压力（容器 / 罐 / 上游泵出口），Pa
    Pv       工况温度下液体饱和蒸汽压，Pa
    rho      液体密度，kg/m³
    g        9.80665 m/s²（ISO 80000-3）
    h_loss   吸入管段总阻力（m 液柱），含摩擦 + 高程差
             = (sum(dp_i) / (rho*g)) + delta_z
             （管件 K 已含在 dp_fittings_pa 内 — P4-2-3 一并算出）

精度护栏（沿用 P4-2-5 worst-wins + R1 裁决）：
    - 吸入侧任一段 confidence=LOW 或 flow_regime=TRANSITION
      → 强制 WARNING（reason="SUCTION_LOW_RE_UNCERTAINTY"），禁止 PASS
    - 吸入侧 confidence=MEDIUM → 可 PASS，但 result metadata confidence=MEDIUM
    - 全 HIGH + 全 TURBULENT → 可 PASS（confidence=HIGH）

不做：
- 不联动 outlet_stream（P4-1-3，P4-4-4 接管）
- 不落库 / 不创建 calc_record（P4-0-1 / P4-4-4）
- 不算 NPSHr（厂家给定，由调用方传入）
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.services.exceptions import PcsError

if TYPE_CHECKING:
    from app.services.pipe.pipe_chain_service import (
        PipeChainInput,
        PipeChainResult,
    )

# 物理：g = 9.80665 m/s²（ISO 80000-3，与 P4-2-5 对齐）
_G: float = 9.80665

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
CheckResult = Literal["PASS", "WARNING", "FAIL"]


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class NPSHaInputError(PcsError):
    """NPSHa 输入错误（业务非法）。"""

    code = "NPSHA_INPUT_ERROR"
    status = 422


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NPSHaInput:
    """NPSHa 计算输入。

    Attributes:
        project_id: 项目 UUID
        workspace_id: 工作区 UUID
        source_stream_id: 源流 UUID
        tag_number: 泵位号
        system_pressure_pa: 上游系统压力 Ps（Pa；必须 > vapor_pressure_pa）
        vapor_pressure_pa: 饱和蒸汽压 Pv（Pa；>=0）
        fluid_density_kg_m3: 液体密度（kg/m³；>0）
        fluid_viscosity_pa_s: 液体动力粘度（Pa·s；>0；预留—本批未用，留给 P4-4-3+）
        suction_pipe_chain: 吸入侧管段链（P4-2-5）
        elevation_change_m: 液位到泵入口高程差（m；正数=抬升，会降低 NPSHa）
    """

    project_id: uuid.UUID
    workspace_id: uuid.UUID
    source_stream_id: uuid.UUID
    tag_number: str
    system_pressure_pa: float
    vapor_pressure_pa: float
    fluid_density_kg_m3: float
    fluid_viscosity_pa_s: float
    suction_pipe_chain: PipeChainInput
    elevation_change_m: float = 0.0


@dataclass(frozen=True)
class NPSHaResult:
    """NPSHa 计算结果。

    Attributes:
        npsha_m: 汽蚀余量（m 液柱）
        h_friction_m: 摩擦阻力（m 液柱；管件 K 包含在 dp_fittings_pa 中，
            此处统一以 dp_friction / dp_fittings 拆分上报）
        h_fittings_m: 管件局部阻力（m 液柱）
        h_elevation_m: 高程差（m 液柱；正数=抬升）
        suction_confidence: 吸入侧整体置信度（worst-wins：LOW > MEDIUM > HIGH）
        flow_regime_summary: 各流态段数（{"LAMINAR": n, "TRANSITION": n,
            "TURBULENT": n}）
        check_result: 校核档 PASS / WARNING / FAIL
        check_result_reason: 校核原因（NEGATIVE_MARGIN / SUCTION_LOW_RE_UNCERTAINTY /
            None）
        margin_m: NPSHa - NPSHr（m；npshr_m 未提供则为 None）
        margin_pct: margin / NPSHr × 100（%；npshr_m 未提供则为 None）
    """

    npsha_m: float
    h_friction_m: float
    h_fittings_m: float
    h_elevation_m: float
    suction_confidence: Confidence
    flow_regime_summary: dict[str, int]
    check_result: CheckResult
    check_result_reason: str | None
    margin_m: float | None = None
    margin_pct: float | None = None


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _validate_input(inp: NPSHaInput) -> None:
    if inp.system_pressure_pa <= inp.vapor_pressure_pa:
        raise NPSHaInputError(
            f"system_pressure_pa 必须 > vapor_pressure_pa "
            f"（Ps={inp.system_pressure_pa}, Pv={inp.vapor_pressure_pa}）"
        )
    if inp.vapor_pressure_pa < 0.0:
        raise NPSHaInputError(
            f"vapor_pressure_pa 必须 >= 0（got {inp.vapor_pressure_pa}）"
        )
    if inp.fluid_density_kg_m3 <= 0.0:
        raise NPSHaInputError(
            f"fluid_density_kg_m3 必须 > 0（got {inp.fluid_density_kg_m3}）"
        )
    if inp.fluid_viscosity_pa_s <= 0.0:
        raise NPSHaInputError(
            f"fluid_viscosity_pa_s 必须 > 0（got {inp.fluid_viscosity_pa_s}）"
        )


def _summarize_regimes(regimes: list[str]) -> dict[str, int]:
    """统计 flow_regime 分布。"""
    out = {"LAMINAR": 0, "TRANSITION": 0, "TURBULENT": 0}
    for r in regimes:
        if r in out:
            out[r] += 1
    return out


# ---------------------------------------------------------------------------
# 入口：calc_npsha
# ---------------------------------------------------------------------------


def calc_npsha(
    inp: NPSHaInput,
    npshr_m: float | None = None,
) -> NPSHaResult:
    """NPSHa 计算（含精度护栏）。

    流程：
    1. 输入校验（Ps > Pv / rho > 0 / mu > 0）
    2. 调 pipe_chain_service.calc_chain 拿 total_dp + confidence + flow_regimes
    3. h_loss = total_dp / (rho * g) + elevation_change_m
       （h_friction / h_fittings 按 dp_friction / dp_fittings 比例拆分；
        chain 不直接给 ratio → 这里按 total_dp 近似分配：h_friction =
        h_loss * dp_friction/(dp_friction+dp_fittings)，其中
        dp_fittings = total_dp * total_K / (total_K + f*L/D)，简化用
        chain.reynolds + friction_factor 推算 — 简化路径下若不可分则
        h_friction = h_loss - h_elevation, h_fittings = 0）
    4. NPSHa = (Ps - Pv) / (rho * g) - h_loss
    5. 精度护栏：任一吸入段 confidence=LOW 或 TRANSITION → 强制 WARNING
    6. margin = NPSHa - NPSHr（若提供 NPSHr）；margin < 0 → check_result=FAIL

    Args:
        inp: NPSHa 输入
        npshr_m: 厂家必需 NPSH（m；可选）

    Returns:
        NPSHaResult

    Raises:
        NPSHaInputError: 输入越界
        透传 PipeChainInputError / PressureDropInputError / TwoPhaseInputError
    """
    _validate_input(inp)

    # 1) 调 P4-2-5 链式服务（沿用 worst-wins + TRANSITION 检测）
    from app.services.pipe.pipe_chain_service import calc_chain

    chain_res: PipeChainResult = calc_chain(inp.suction_pipe_chain)

    # 2) 拆分 h_loss 为摩擦 / 管件 / 高程
    rho_g = inp.fluid_density_kg_m3 * _G
    total_h_loss = chain_res.total_dp_pa / rho_g
    h_elevation = inp.elevation_change_m
    # 摩擦 vs 管件拆分：管件按 total_K 和 f·L/D 比例估分
    # dp_fittings = total_K × ρv²/2；dp_friction = f × L/D × ρv²/2
    # ratio_fittings = total_K / (total_K + f × L/D)
    f_L_over_D = (
        chain_res.friction_factor * chain_res.total_length_m
        / max(chain_res.total_length_m, 1e-12) if chain_res.total_length_m > 0.0
        else 0.0
    )
    # 简化：仅当首段为单相（f_L_over_D 来自 chain.reynolds+friction_factor）
    # 才拆分；两相段无 f → 全算摩擦
    if chain_res.friction_factor > 0.0 and chain_res.total_length_m > 0.0:
        denom = chain_res.total_K + f_L_over_D
        if denom > 0.0:
            ratio_fittings = chain_res.total_K / denom
        else:
            ratio_fittings = 0.0
    else:
        ratio_fittings = 0.0
    h_fittings = total_h_loss * ratio_fittings
    h_friction = total_h_loss - h_fittings

    # 3) NPSHa
    static_head_m = (inp.system_pressure_pa - inp.vapor_pressure_pa) / rho_g
    npsha_m = static_head_m - total_h_loss - h_elevation

    # 4) 精度护栏（沿用 P4-2-5 worst-wins + TRANSITION/LOW 强制 WARNING）
    regime_summary = _summarize_regimes(chain_res.flow_regimes)
    has_transition = regime_summary.get("TRANSITION", 0) > 0
    suction_confidence = chain_res.confidence

    check_result: CheckResult
    check_reason: str | None
    if suction_confidence == "LOW" or has_transition:
        check_result = "WARNING"
        check_reason = "SUCTION_LOW_RE_UNCERTAINTY"
    else:
        check_result = "PASS"
        check_reason = None

    # 5) margin
    margin_m: float | None = None
    margin_pct: float | None = None
    if npshr_m is not None:
        if npshr_m <= 0.0:
            raise NPSHaInputError(
                f"npshr_m 必须 > 0（got {npshr_m}）"
            )
        margin_m = npsha_m - npshr_m
        margin_pct = margin_m / npshr_m * 100.0
        # 负 margin → 强制 FAIL（覆盖 WARNING/PASS）
        if margin_m < 0.0:
            check_result = "FAIL"
            check_reason = "NEGATIVE_MARGIN"

    return NPSHaResult(
        npsha_m=npsha_m,
        h_friction_m=h_friction,
        h_fittings_m=h_fittings,
        h_elevation_m=h_elevation,
        suction_confidence=suction_confidence,
        flow_regime_summary=regime_summary,
        check_result=check_result,
        check_result_reason=check_reason,
        margin_m=margin_m,
        margin_pct=margin_pct,
    )


__all__ = [
    "NPSHaInput",
    "NPSHaInputError",
    "NPSHaResult",
    "calc_npsha",
]
