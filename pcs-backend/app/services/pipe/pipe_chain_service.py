"""P4-2-5：链式管道压降服务（串/并联管段汇总 + 高程修正 + 单/两相路由）。

公式与路由：
- 单管段：复用 P4-2-3 ``calc_pressure_drop``（Darcy-Weisbach + Colebrook +
  fittings K 值表）+ P4-2-4 ``calc_two_phase``（Lockhart-Martinelli-Baker +
  简化 Mandhane 流型 + Chisholm 空泡率 + 流型/压降双因子校核）。
- 串联：``total_dp = Σ dp_friction_i + Σ dp_fittings_i + Σ ρg·Δz_i``
  （dp 单位 Pa；高程修正：正 Δz 向上 → 加 ρgΔz 抗重力）。
- 路由：任一管段 ``need_two_phase=True``（P4-2-3 内部判据 / 显式 TWO_PHASE
  相）→ 整体 ``need_two_phase=True``；两相段 dp/dz × L = dp 段贡献。
- outlet_pressure = P_inlet - total_dp（高程已含在 dp 内）。

设计要点：
- dataclass(frozen=True) 保证输入不可变（与 P4-2-3 / P4-2-4 对齐）。
- ``calc_chain`` 纯函数：只接 dataclass，返回 dataclass；不触 DB。
- 两相段必须显式给齐 liquid/gas 质量流量（不隐式按 vapor_fraction 分割 —
  service 不知道源流 vfrac；API 层负责从 source stream 读 vfrac 后拆分）。
- ``persist_pipe_chain_result`` 单独模块（pipe_chain_persist.py）落库 +
  outlet，复用 P4-1-3 ``create_outlet_stream``（``source_type="PIPE_CALCULATED"``）。

边界：
- segments 为空 → PipeChainInputError（422）
- P1_pa ≤ 0 → PipeChainInputError（422）
- parallel_branches ≠ 1 → PipeChainInputError（本批仅支持串联）
- 两相段缺 liquid/gas 物性或质量流量 → PipeChainInputError
- 任一管段物性非法 → 透传 P4-2-3 / P4-2-4 异常（不二次包装）

不做：
- 不实现真正的并联汇总（等流量/等压降分支求解）— 任务批注：本批仅串联
  入口（``parallel_branches=1`` 串联；>1 抛错）
- 不实现热损失（outlet_temperature_K 暂为 None；P4-2-6 接管）
- 不隐式分割两相质量流（API 层显式传入 liquid/gas mass_flow）
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Final, Literal

from app.services.exceptions import PcsError
from app.services.pipe.pressure_drop_service import (
    Fitting,
    FlowRegime3,
    PipeSegment,
    PressureDropCheck,
    PressureDropConfidence,
    calc_pressure_drop,
)
from app.services.pipe.two_phase_service import (
    FlowPattern,
    TwoPhaseInput,
    calc_two_phase,
)

# 流体相字面量（与 P4-2-3 / P4-2-4 对齐）
FluidPhase = Literal["LIQUID", "VAPOR", "TWO_PHASE"]

# 物理：g = 9.80665 m/s²（ISO 80000-3）
_G: Final[float] = 9.80665


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class PipeChainInputError(PcsError):
    """PipeChain 输入错误（业务非法）。

    触发场景：
    - segments 为空
    - inlet_pressure_pa ≤ 0（上游压力退化）
    - parallel_branches ≠ 1（本批仅串联）
    - 两相段缺 liquid/gas 物性或质量流量
    """

    code = "PIPE_CHAIN_INPUT_ERROR"
    status = 422


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipeSegmentInput:
    """单管段输入（链式管道单元）。

    Attributes:
        fluid_phase: 流相（LIQUID / VAPOR / TWO_PHASE）— VAPOR 对应 P4-2-3 的
            GAS/STEAM 默认物性；两相段必须显式给齐 liquid/gas 物性 + 质量流。
        mass_flow_kg_s: 单相质量流量 (kg/s)；两相段忽略（改用 liquid/gas
            质量流量）
        density_kg_m3: 单相密度 (kg/m³)；两相段忽略
        viscosity_pa_s: 单相动力粘度 (Pa·s)；两相段忽略
        pipe_diameter_m: 管内径 (m)
        pipe_roughness_m: 绝对粗糙度 (m)
        length_m: 直管长度 (m)
        inclination_deg: 倾角 (°；0=水平，90=垂直向上)
        elevation_change_m: 段入口→出口高程变化 (m；正=向上)
        surface_tension_n_m: 表面张力 (N/m)；两相段必须
        liquid_density_kg_m3: 液相密度 (kg/m³)；两相段必须
        liquid_viscosity_pa_s: 液相动力粘度 (Pa·s)；两相段必须
        gas_density_kg_m3: 气相密度 (kg/m³)；两相段必须
        gas_viscosity_pa_s: 气相动力粘度 (Pa·s)；两相段必须
        liquid_mass_flow_kg_s: 液相质量流量 (kg/s)；两相段必须
        gas_mass_flow_kg_s: 气相质量流量 (kg/s)；两相段必须
        fittings: 管件列表（局部阻力；单相段使用）
    """

    fluid_phase: FluidPhase
    mass_flow_kg_s: float
    density_kg_m3: float
    viscosity_pa_s: float
    pipe_diameter_m: float
    pipe_roughness_m: float
    length_m: float
    inclination_deg: float = 0.0
    elevation_change_m: float = 0.0
    surface_tension_n_m: float | None = None
    liquid_density_kg_m3: float | None = None
    liquid_viscosity_pa_s: float | None = None
    gas_density_kg_m3: float | None = None
    gas_viscosity_pa_s: float | None = None
    liquid_mass_flow_kg_s: float | None = None
    gas_mass_flow_kg_s: float | None = None
    fittings: list[Fitting] = field(default_factory=list)


@dataclass(frozen=True)
class PipeChainInput:
    """链式管道总输入。

    Attributes:
        project_id: 项目 UUID
        workspace_id: 工作区 UUID
        source_stream_id: 入口流 UUID（CHECKED 守卫）
        tag_number: 链位号（写入 piping_results.line_no）
        segments: 管段列表（≥ 1）
        inlet_pressure_pa: 入口压力 (Pa；上游 P1)
        inlet_temperature_K: 入口温度 (K；预留位，本批不参与热损失)
        parallel_branches: 并联支路数（占位；本批仅支持 = 1 全串联）
    """

    project_id: uuid.UUID
    workspace_id: uuid.UUID
    source_stream_id: uuid.UUID
    tag_number: str
    segments: list[PipeSegmentInput]
    inlet_pressure_pa: float
    inlet_temperature_K: float | None = None
    parallel_branches: int = 1


@dataclass(frozen=True)
class PipeChainResult:
    """链式管道压降计算结果。

    Attributes:
        total_dp_pa: 总压降 (Pa) = Σ dp_i + Σ ρg·Δz_i
        total_length_m: 总长度 (m) = Σ L_i
        total_K: 总局部阻力系数 (Σ K_i)
        dp_per_segment_pa: 各段压降贡献 (Pa，与 segments 等长)
        need_two_phase: 任一段 TWO_PHASE / 路由触发 → True
        velocity_m_s: 入口段表观速度 (m/s)
        reynolds: 入口段雷诺数
        friction_factor: 入口段 Darcy 摩阻 f
        flow_pattern: 两相流型（仅 need_two_phase=True 时；单相为 None）
        outlet_pressure_pa: 出口压力 (Pa) = P1 - total_dp
        pressure_gradient_kpa_m: 链压降梯度 (kPa/m) = total_dp/1000 / total_L
        flow_regimes: 各段流场分类（与 segments 等长；LAMINAR/TRANSITION/TURBULENT；
            两相段标记为 'TURBULENT' 占位）
        check_result: 链整体校核档位 PASS / WARNING / FAIL；任一段
            TRANSITION → 强制 WARNING
        check_result_reason: 链整体校核原因；TRANSITION 时为
            'TRANSITION_REGIME'
        confidence: 链整体置信度 HIGH / MEDIUM / LOW；任一段 LOW → 整体 LOW；
            其次任一段 MEDIUM → 整体 MEDIUM；全 HIGH → 整体 HIGH。
            两相段默认 MEDIUM（P4-2-4 不下钻 3 态流场；保留口径一致）。
    """

    total_dp_pa: float
    total_length_m: float
    total_K: float
    dp_per_segment_pa: list[float]
    need_two_phase: bool
    velocity_m_s: float
    reynolds: float
    friction_factor: float
    flow_pattern: FlowPattern | None
    outlet_pressure_pa: float
    pressure_gradient_kpa_m: float
    flow_regimes: list[FlowRegime3]
    check_result: PressureDropCheck
    check_result_reason: str | None
    confidence: PressureDropConfidence


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _fittings_k_sum(seg: PipeSegmentInput) -> float:
    """管段 fittings 局部阻力 K 之和（仅单相段用；两相段 K=0 由 P4-2-4 自带）。

    P4-2-5 K 表 v2 schema：每条 FittingKMeta 含 k / reynolds_applicable /
    k_factor_confidence / source；当前按 Crane 固定 K 取 meta.k。
    """
    from app.services.pipe.pressure_drop_service import _K_TABLE

    total = 0.0
    for f in seg.fittings:
        if f.K is not None:
            total += f.K
        else:
            total += _K_TABLE[f.type].k
    return total


# Confidence 聚合优先级（P4-2-5 链式规则）
_CONFIDENCE_RANK: Final[dict[PressureDropConfidence, int]] = {
    "HIGH": 0,
    "MEDIUM": 1,
    "LOW": 2,
}


def _aggregate_confidence(
    per_segment: list[PressureDropConfidence],
) -> PressureDropConfidence:
    """链整体 confidence：任一段 LOW → 整体 LOW；其次 MEDIUM；全 HIGH → HIGH。

    聚合规则：取"最差"等级（rank 最大者）。
    - LOW (2) > MEDIUM (1) > HIGH (0)
    - 任一 LOW → 整体 LOW
    - 否则任一 MEDIUM → 整体 MEDIUM
    - 全 HIGH → 整体 HIGH
    """
    if not per_segment:
        return "HIGH"  # 0 段兜底（理论上不会到这：segments 校验非空）
    # rank 最大 = 等级最低（LOW=2 最高）
    worst_rank = max(_CONFIDENCE_RANK[c] for c in per_segment)
    for level, rank in _CONFIDENCE_RANK.items():
        if rank == worst_rank:
            return level
    return "HIGH"  # unreachable


def _require_two_phase_props(seg: PipeSegmentInput, idx: int) -> None:
    """两相段必须显式给齐 5 个物性 + 2 个质量流。"""
    missing: list[str] = []
    if seg.surface_tension_n_m is None:
        missing.append("surface_tension_n_m")
    if seg.liquid_density_kg_m3 is None:
        missing.append("liquid_density_kg_m3")
    if seg.liquid_viscosity_pa_s is None:
        missing.append("liquid_viscosity_pa_s")
    if seg.gas_density_kg_m3 is None:
        missing.append("gas_density_kg_m3")
    if seg.gas_viscosity_pa_s is None:
        missing.append("gas_viscosity_pa_s")
    if seg.liquid_mass_flow_kg_s is None:
        missing.append("liquid_mass_flow_kg_s")
    if seg.gas_mass_flow_kg_s is None:
        missing.append("gas_mass_flow_kg_s")
    if missing:
        raise PipeChainInputError(
            f"段 {idx}：TWO_PHASE 段必须显式给齐 {missing}",
            details={"segment_index": idx, "missing": missing},
        )


# ---------------------------------------------------------------------------
# 入口：calc_chain
# ---------------------------------------------------------------------------


def calc_chain(inp: PipeChainInput) -> PipeChainResult:
    """链式管道压降计算（串联管段汇总 + 高程修正 + 单/两相路由）。

    流程：
    1. 入口校验：segments 非空 + P1 > 0 + parallel_branches == 1
    2. 段内：单相走 ``calc_pressure_drop``；两相走 ``calc_two_phase``（dp =
       pressure_gradient_kpa_m × L_m）
    3. 高程修正：每段 ``ρg·Δz`` 累加（两相段用液相密度作简化；P4-2-6+ 接管
       mixture density）
    4. 汇总：total_dp / total_length / total_K + per-segment dp
    5. 入口段：velocity / Re / f 作为代表（链整体特征；下游段仅在审计日志可见）

    Args:
        inp: 链式管道输入

    Returns:
        PipeChainResult：链整体 + 各段贡献 + outlet 压力

    Raises:
        PipeChainInputError: segments 空 / P1 ≤ 0 / 并联支路 / 两相段缺物性
        透传 PressureDropInputError / PressureDropRangeError / TwoPhaseInputError
    """
    # --- 1. 入口校验 ---
    if not inp.segments:
        raise PipeChainInputError(
            "PipeChain segments 不能为空（至少 1 段）",
            details={"segments_count": 0},
        )
    if inp.inlet_pressure_pa <= 0.0:
        raise PipeChainInputError(
            f"inlet_pressure_pa={inp.inlet_pressure_pa} 必须 > 0",
            details={"inlet_pressure_pa": inp.inlet_pressure_pa},
        )
    if inp.parallel_branches != 1:
        raise PipeChainInputError(
            f"parallel_branches={inp.parallel_branches} 暂不支持（仅 = 1 串联）",
            details={"parallel_branches": inp.parallel_branches},
        )

    # --- 2. 段内计算 + 高程 + 局部阻力累加 ---
    total_dp = 0.0
    total_length = 0.0
    total_K = 0.0
    dp_per_seg: list[float] = []
    need_two_phase_overall = False
    flow_pattern_overall: FlowPattern | None = None
    inlet_velocity = 0.0
    inlet_reynolds = 0.0
    inlet_f = 0.0
    # P4-2-5：链整体 confidence / flow_regimes / check_result 聚合
    flow_regimes: list[FlowRegime3] = []
    confidences: list[PressureDropConfidence] = []
    has_transition = False

    for i, seg in enumerate(inp.segments):
        if seg.fluid_phase == "TWO_PHASE":
            # --- 两相段 ---
            _require_two_phase_props(seg, i)
            # type-narrowing: 校验后所有字段必填
            assert seg.surface_tension_n_m is not None
            assert seg.liquid_density_kg_m3 is not None
            assert seg.liquid_viscosity_pa_s is not None
            assert seg.gas_density_kg_m3 is not None
            assert seg.gas_viscosity_pa_s is not None
            assert seg.liquid_mass_flow_kg_s is not None
            assert seg.gas_mass_flow_kg_s is not None
            tp_inp = TwoPhaseInput(
                liquid_mass_flow=seg.liquid_mass_flow_kg_s,
                gas_mass_flow=seg.gas_mass_flow_kg_s,
                liquid_density=seg.liquid_density_kg_m3,
                gas_density=seg.gas_density_kg_m3,
                liquid_viscosity=seg.liquid_viscosity_pa_s,
                gas_viscosity=seg.gas_viscosity_pa_s,
                surface_tension=seg.surface_tension_n_m,
                pipe_diameter_m=seg.pipe_diameter_m,
                pipe_roughness_m=seg.pipe_roughness_m,
                inclination_deg=seg.inclination_deg,
                L_m=seg.length_m,
                P1_pa=inp.inlet_pressure_pa,
            )
            tp_res = calc_two_phase(tp_inp)
            dp_seg = tp_res.pressure_gradient * 1000.0 * seg.length_m  # kPa/m × m → Pa
            # 高程：两相段按液相密度简化（P4-2-6+ 接管 mixture density）
            dp_elev = seg.liquid_density_kg_m3 * _G * seg.elevation_change_m
            dp_total_seg = dp_seg + dp_elev
            dp_per_seg.append(dp_total_seg)
            total_dp += dp_total_seg
            total_length += seg.length_m
            # 入口段特征（首段为两相时记 liquid_velocity 作为代表）
            if i == 0:
                inlet_velocity = tp_res.liquid_velocity
                inlet_reynolds = 0.0  # 两相段无单一 Re
                inlet_f = 0.0
            need_two_phase_overall = True
            flow_pattern_overall = tp_res.flow_pattern
            # P4-2-5：两相段占位 'TURBULENT' + confidence=MEDIUM
            # （P4-2-4 不下钻 3 态流场；保留口径一致）
            flow_regimes.append("TURBULENT")
            confidences.append("MEDIUM")
        else:
            # --- 单相段（LIQUID / VAPOR）---
            phase_str = "LIQUID" if seg.fluid_phase == "LIQUID" else "GAS"
            Q = seg.mass_flow_kg_s / seg.density_kg_m3
            ps = PipeSegment(
                L_m=seg.length_m,
                D_m=seg.pipe_diameter_m,
                roughness_m=seg.pipe_roughness_m,
                fluid_density=seg.density_kg_m3,
                fluid_viscosity=seg.viscosity_pa_s,
                flow_rate_m3s=Q,
                fittings=seg.fittings,
            )
            pd_res = calc_pressure_drop(
                ps, P1_pa=inp.inlet_pressure_pa, fluid_phase=phase_str
            )
            # 高程：液相段用液密度；气相段用气密度（VAPOR=GAS）
            rho_for_elev = seg.density_kg_m3
            dp_elev = rho_for_elev * _G * seg.elevation_change_m
            dp_total_seg = (
                pd_res.dp_friction_pa + pd_res.dp_fittings_pa + dp_elev
            )
            dp_per_seg.append(dp_total_seg)
            total_dp += dp_total_seg
            total_length += seg.length_m
            total_K += _fittings_k_sum(seg)
            if i == 0:
                A = math.pi * seg.pipe_diameter_m ** 2 / 4.0
                inlet_velocity = Q / A if A > 0.0 else 0.0
                inlet_reynolds = pd_res.reynolds
                inlet_f = pd_res.friction_factor
            # P4-2-5：单相段透传流态 + confidence
            flow_regimes.append(pd_res.flow_regime)
            confidences.append(pd_res.confidence)
            if pd_res.flow_regime == "TRANSITION":
                has_transition = True
            if pd_res.need_two_phase:
                need_two_phase_overall = True
                # 单相路由到两相：本链无 flow_pattern；保持 None

    outlet_pressure = inp.inlet_pressure_pa - total_dp
    pressure_gradient_kpa_m = (
        total_dp / 1000.0 / total_length if total_length > 0.0 else 0.0
    )

    # P4-2-5：链整体 confidence / check_result 聚合
    chain_confidence = _aggregate_confidence(confidences)
    if has_transition:
        chain_check: PressureDropCheck = "WARNING"
        chain_check_reason: str | None = "TRANSITION_REGIME"
    else:
        chain_check = "PASS"
        chain_check_reason = None

    return PipeChainResult(
        total_dp_pa=total_dp,
        total_length_m=total_length,
        total_K=total_K,
        dp_per_segment_pa=dp_per_seg,
        need_two_phase=need_two_phase_overall,
        velocity_m_s=inlet_velocity,
        reynolds=inlet_reynolds,
        friction_factor=inlet_f,
        flow_pattern=flow_pattern_overall,
        outlet_pressure_pa=outlet_pressure,
        pressure_gradient_kpa_m=pressure_gradient_kpa_m,
        flow_regimes=flow_regimes,
        check_result=chain_check,
        check_result_reason=chain_check_reason,
        confidence=chain_confidence,
    )


__all__ = [
    "FluidPhase",
    "PipeChainInput",
    "PipeChainInputError",
    "PipeChainResult",
    "PipeSegmentInput",
    "calc_chain",
]
