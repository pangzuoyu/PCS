"""Pipe 计算服务包（P4-2+）。

子模块：
- sizing_service：P4-2-1 管道选型（预定流速法 + 设定压力降法 + DN 圆整）
- wall_thickness_service：P4-2-2 壁厚计算（ASME B31.3 §304.1.2 直管壁厚 +
  Sch 系列圆整 + 许用应力温度插值）
- pressure_drop_service：P4-2-3 单相压降（Darcy-Weisbach + Colebrook +
  fittings K 值表 + ΔP/P₁ ≥ 10% 路由至两相计算）— P4-2-5 扩展 3 态
  流场 + confidence + get_fitting_k
- two_phase_service：P4-2-4 两相压降（Lockhart-Martinelli-Baker +
  简化 Mandhane 流型 + Chisholm 空泡率 + 流型/压降双因子校核）
- two_phase_persist：P4-2-4 两相压降落库 helper（写 two_phase_results 13 字段）
- pipe_chain_service：P4-2-5 链式管道压降（串/并联管段汇总 + 高程修正 +
  单/两相路由）— 透传 P4-2-5 3 态流场 + confidence 聚合
- pipe_chain_persist：P4-2-5 链式压降落库 + outlet_stream 收口
  （piping_results + create_outlet_stream PIPE_CALCULATED）
"""
from app.services.pipe.pipe_chain_persist import persist_pipe_chain_result
from app.services.pipe.pipe_chain_service import (
    FluidPhase,
    PipeChainInput,
    PipeChainInputError,
    PipeChainResult,
    PipeSegmentInput,
    calc_chain,
)
from app.services.pipe.pressure_drop_service import (
    Fitting,
    FittingKMeta,
    FittingType,
    FlowRegime3,
    PipeSegment,
    PressureDropCheck,
    PressureDropConfidence,
    PressureDropInputError,
    PressureDropRangeError,
    PressureDropResult,
    calc_pressure_drop,
    get_fitting_k,
    load_fittings_k_default,
)
from app.services.pipe.two_phase_persist import persist_two_phase_result
from app.services.pipe.two_phase_service import (
    FlowPattern,
    TwoPhaseCheck,
    TwoPhaseInput,
    TwoPhaseInputError,
    TwoPhaseResult,
    calc_two_phase,
)

__all__ = [
    "Fitting",
    "FittingKMeta",
    "FittingType",
    "FlowPattern",
    "FlowRegime3",
    "FluidPhase",
    "PipeChainInput",
    "PipeChainInputError",
    "PipeChainResult",
    "PipeSegment",
    "PipeSegmentInput",
    "PressureDropCheck",
    "PressureDropConfidence",
    "PressureDropInputError",
    "PressureDropRangeError",
    "PressureDropResult",
    "TwoPhaseCheck",
    "TwoPhaseInput",
    "TwoPhaseInputError",
    "TwoPhaseResult",
    "calc_chain",
    "calc_pressure_drop",
    "calc_two_phase",
    "get_fitting_k",
    "load_fittings_k_default",
    "persist_pipe_chain_result",
    "persist_two_phase_result",
]
