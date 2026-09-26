"""C-23 FLARE 噪声（API 521 §6.4 + ISO 9613-2 + A 加权声压级）。

按 SPEC §3.10.3 V1.5：
- API 521 §6.4 火焰声功率 L_w ≈ 145 dB(A)（参考 10 MW 火焰）
- ISO 9613-2 衰减 L_p(r) = L_w - 20·log10(r) - A_atm·r/1000 + D
- A 加权声压级 dB(A)
- Leq,24h 等效连续声级

M-1 v2 BLOCKER: 无 imperial_units 字段（FLARE 物理量仅 SI）
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from app.services.exceptions import PcsError

_API_521_REFERENCE_LW_DBA: Final[float] = 145.0
_REFERENCE_FLAME_POWER_KW: Final[float] = 10.0

_DEFAULT_ATM_ABS_DB_PER_KM: Final[float] = 1.5

_24H_IN_MINUTES: Final[float] = 1440.0


class FlareNoiseInputError(PcsError):
    code = "FLARE_NOISE_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class FlareNoiseInput:
    flame_power_kw: float
    receiver_distance_m: float
    frequency_hz: float = 500.0
    atmospheric_absorption_db_per_km: float = _DEFAULT_ATM_ABS_DB_PER_KM
    directivity_factor_db: float = 3.0
    event_duration_min: float = 1.0
    n_events_per_24h: int = 1


@dataclass(frozen=True)
class FlareNoiseResult:
    sound_pressure_level_dbA: float
    leq_24h_dbA: float
    flame_power_kw_used: float
    directivity_factor_db_used: float
    formula_ref: dict[str, str]


def _validate_input(inp: FlareNoiseInput) -> None:
    if inp.flame_power_kw <= 0:
        raise FlareNoiseInputError(f"Q_flame={inp.flame_power_kw} 必须 > 0")
    if inp.receiver_distance_m <= 0:
        raise FlareNoiseInputError(f"r={inp.receiver_distance_m} 必须 > 0")
    if inp.frequency_hz <= 0:
        raise FlareNoiseInputError(f"f={inp.frequency_hz} 必须 > 0")
    if inp.atmospheric_absorption_db_per_km < 0:
        raise FlareNoiseInputError("大气吸收系数必须 ≥ 0")
    if inp.event_duration_min <= 0:
        raise FlareNoiseInputError("事件持续时间必须 > 0")
    if inp.n_events_per_24h < 1:
        raise FlareNoiseInputError("事件频次必须 ≥ 1")


def _flame_power_to_lw(flame_power_kw: float) -> float:
    return _API_521_REFERENCE_LW_DBA + 10.0 * math.log10(
        flame_power_kw / _REFERENCE_FLAME_POWER_KW
    )


def calc_flare_noise(inp: FlareNoiseInput) -> FlareNoiseResult:
    """API 521 §6.4 + ISO 9613-2 A 加权声压级 + Leq,24h。

    Args:
        inp: FlareNoiseInput（含 Q_flame_kw / r_m / f_hz / A_atm / D /
            T_event_min / N_per_24h）。

    Returns:
        FlareNoiseResult（含 sound_pressure_level_dbA / leq_24h_dbA /
        flame_power_kw_used / directivity_factor_db_used / formula_ref）。

    Raises:
        FlareNoiseInputError: 输入字段越界或非正（422）。
    """
    _validate_input(inp)

    L_w = _flame_power_to_lw(inp.flame_power_kw)
    L_p = (
        L_w
        - 20.0 * math.log10(inp.receiver_distance_m)
        - inp.atmospheric_absorption_db_per_km * inp.receiver_distance_m / 1000.0
        + inp.directivity_factor_db
    )

    leq = L_p + 10.0 * math.log10(
        inp.event_duration_min * inp.n_events_per_24h / _24H_IN_MINUTES
    )

    return FlareNoiseResult(
        sound_pressure_level_dbA=L_p,
        leq_24h_dbA=leq,
        flame_power_kw_used=inp.flame_power_kw,
        directivity_factor_db_used=inp.directivity_factor_db,
        formula_ref={
            "source_power": "API 521 §6.4 (10 MW ref 145 dB(A))",
            "attenuation": "ISO 9613-2 L_p(r) = L_w - 20·log10(r) - A·r/1000 + D",
            "leq": "ISO 1996 Leq,24h = L_p + 10·log10(T_event·N / T_ref)",
        },
    )


__all__ = [
    "FlareNoiseInput",
    "FlareNoiseInputError",
    "FlareNoiseResult",
    "calc_flare_noise",
]