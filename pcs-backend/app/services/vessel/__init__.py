"""P5-1 vessel_service 容器计算模块。

P6-4 T3 扩展（V1.2 接口冻结至 2027-03-25，见 ADR-0040）：
- calc_partial_volume / calc_wetted_area / mass_iteration_loop
- PartialVolumeInput/Result / WettedAreaInput/Result / MassIterationInput/Result
- MassIterationNotConvergedError
"""
from app.services.vessel.vessel_service import (
    MassIterationInput,
    MassIterationNotConvergedError,
    MassIterationResult,
    PartialVolumeInput,
    PartialVolumeResult,
    VesselHydraulicsInput,
    VesselHydraulicsResult,
    VesselInputError,
    VesselSizingInput,
    VesselSizingResult,
    WettedAreaInput,
    WettedAreaResult,
    calc_partial_volume,
    calc_vessel_hydraulics,
    calc_vessel_sizing,
    calc_wetted_area,
    mass_iteration_loop,
)

__all__ = [
    # P5-1 既有符号（P5-1-1/2 冻结前）
    "VesselHydraulicsInput",
    "VesselHydraulicsResult",
    "VesselSizingInput",
    "VesselSizingResult",
    "calc_vessel_hydraulics",
    "calc_vessel_sizing",
    # 异常类
    "VesselInputError",
    "MassIterationNotConvergedError",
    # P6-4 T3 C-12 接口（V1.2 冻结至 2027-03-25，ADR-0040）
    "PartialVolumeInput",
    "PartialVolumeResult",
    "WettedAreaInput",
    "WettedAreaResult",
    "MassIterationInput",
    "MassIterationResult",
    "calc_partial_volume",
    "calc_wetted_area",
    "mass_iteration_loop",
]