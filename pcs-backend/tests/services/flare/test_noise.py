"""P6-5 Task C4 FLARE C-23 噪声（API 521 §6.4 + ISO 9613-2 + A 加权声压级）。

按 SPEC §3.10.3 V1.5 + API 521 7th Ed. §6.4 + ISO 9613-2：
- API 521 §6.4 火焰声功率 L_w ≈ 145 dB(A)（参考 10 MW 火焰）
- 标度律：L_w(Q) = 145 + 10·log10(Q/10)
- ISO 9613-2 衰减 L_p(r) = L_w - 20·log10(r) - A_atm·r/1000 + D
- Leq,24h 等效连续声级 = L_p + 10·log10(T_event·N / T_ref)

测试模式参照 ``tests/services/flare/test_dispersion.py``（纯计算函数，
无 DB / Mock session）。共 9 测试 = 6 brief 业务 + 1 frozen-pattern
（D7 接口冻结）+ 1 PcsError 契约 + 1 golden fixture 一致性。
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.exceptions import PcsError  # noqa: E402
from app.services.flare.noise_service import (  # noqa: E402
    FlareNoiseInput,
    FlareNoiseInputError,
    FlareNoiseResult,
    calc_flare_noise,
)

# ============================================================================
# 1. API 521 §6.4 参考距离声压级（10 m / 10 MW）
# ============================================================================


def test_api521_noise_at_reference_distance():
    """API 521 §6.4 火焰噪声参考声功率 145 dB(A) @ 10 MW。

    L_p(r) = L_w - 20·log10(r) - A_atm·r/1000 + D
    L_w = 145 + 10·log10(10/10) = 145；r=10m；A=1.5 dB/km；D=+3
    → L_p = 145 - 20·log10(10) - 1.5e-3·10 + 3 = 145 - 20 - 0.015 + 3 = 127.985
    """
    inp = FlareNoiseInput(
        flame_power_kw=10.0,
        receiver_distance_m=10.0,
        frequency_hz=500.0,
        atmospheric_absorption_db_per_km=1.5,
        directivity_factor_db=3.0,
    )
    result = calc_flare_noise(inp)
    expected_db = 145.0 - 20.0 * math.log10(10.0) - 1.5e-3 * 10.0 + 3.0
    assert math.isclose(result.sound_pressure_level_dbA, expected_db, rel_tol=1e-3)


# ============================================================================
# 2. ISO 9613-2 长距离大气吸收（1000 m）
# ============================================================================


def test_iso9613_atmospheric_absorption_long_range():
    """ISO 9613-2 长距离：L_p = L_w - 20·log10(r) - A_atm·r/1000 + D。

    L_w=145; r=1000m; A=1.5; D=+3
    → L_p = 145 - 60 - 1.5 + 3 = 86.5 dB(A)
    """
    inp = FlareNoiseInput(
        flame_power_kw=10.0,
        receiver_distance_m=1000.0,
        frequency_hz=500.0,
        atmospheric_absorption_db_per_km=1.5,
        directivity_factor_db=3.0,
    )
    result = calc_flare_noise(inp)
    expected_db = 145.0 - 20.0 * math.log10(1000.0) - 1.5 + 3.0
    assert math.isclose(result.sound_pressure_level_dbA, expected_db, rel_tol=1e-3)


# ============================================================================
# 3. 8 倍距规则（每加倍距离 -6 dB(A)）
# ============================================================================


def test_eight_times_distance_rule():
    """8 倍距规则：每加倍距离衰减 6 dB(A)（-20·log10(2) ≈ -6.02）。

    100m → 200m 距离加倍，几何衰减 -6 dB。设 A_atm=0 隔离纯几何衰减
    （默认 A=1.5 dB/km 在 100→200m 区间额外引入 0.15 dB 衰减，会污染断言）。
    """
    base = FlareNoiseInput(
        flame_power_kw=10.0,
        receiver_distance_m=100.0,
        frequency_hz=500.0,
        atmospheric_absorption_db_per_km=0.0,
    )
    double = FlareNoiseInput(
        flame_power_kw=10.0,
        receiver_distance_m=200.0,
        frequency_hz=500.0,
        atmospheric_absorption_db_per_km=0.0,
    )
    r_base = calc_flare_noise(base)
    r_double = calc_flare_noise(double)
    delta = r_double.sound_pressure_level_dbA - r_base.sound_pressure_level_dbA
    assert math.isclose(delta, -20.0 * math.log10(2.0), abs_tol=0.01)


# ============================================================================
# 4. Leq,24h 等效连续声级
# ============================================================================


def test_leq_24h_continuous_level():
    """Leq,24h：单事件暴露转 24h 平均。

    T_event = 10 min, N = 6 / 24h, T_ref = 1440 min
    Leq,24h = L_p + 10·log10(T_event·N / T_ref)
            = L_p + 10·log10(10·6/1440) = L_p + 10·log10(0.04167) ≈ L_p - 13.80
    """
    inp = FlareNoiseInput(
        flame_power_kw=10.0,
        receiver_distance_m=100.0,
        frequency_hz=500.0,
        event_duration_min=10.0,
        n_events_per_24h=6,
    )
    result = calc_flare_noise(inp)
    expected_leq = result.sound_pressure_level_dbA + 10.0 * math.log10(
        10.0 * 6.0 / 1440.0
    )
    assert math.isclose(result.leq_24h_dbA, expected_leq, rel_tol=1e-3)


# ============================================================================
# 5. 距离越界（F2 boundary）
# ============================================================================


def test_invalid_distance_raises():
    """receiver_distance_m 必须 > 0。"""
    inp = FlareNoiseInput(
        flame_power_kw=10.0,
        receiver_distance_m=0.0,
        frequency_hz=500.0,
    )
    with pytest.raises(FlareNoiseInputError):
        calc_flare_noise(inp)


# ============================================================================
# 6. 火焰功率越界（F2 boundary）
# ============================================================================


def test_invalid_flame_power_raises():
    """flame_power_kw 必须 > 0。"""
    inp = FlareNoiseInput(
        flame_power_kw=0.0,
        receiver_distance_m=100.0,
        frequency_hz=500.0,
    )
    with pytest.raises(FlareNoiseInputError):
        calc_flare_noise(inp)


# ============================================================================
# 7. 数据类契约（frozen dataclass，D7 接口冻结 — batch consistency）
# ============================================================================


def test_noise_result_is_frozen():
    """FlareNoiseInput / FlareNoiseResult 字段冻结校验 + formula_ref 必填。

    与 P6-5 batch A1-C3 一致的 frozen pattern：D7 接口冻结保证下游
    persistence 层不会因字段重命名/增删而崩溃。
    """
    in_fields = {f.name for f in fields(FlareNoiseInput)}
    expected_in = {
        "flame_power_kw",
        "receiver_distance_m",
        "frequency_hz",
        "atmospheric_absorption_db_per_km",
        "directivity_factor_db",
        "event_duration_min",
        "n_events_per_24h",
    }
    assert in_fields == expected_in

    out_fields = {f.name for f in fields(FlareNoiseResult)}
    expected_out = {
        "sound_pressure_level_dbA",
        "leq_24h_dbA",
        "flame_power_kw_used",
        "directivity_factor_db_used",
        "formula_ref",
    }
    assert out_fields == expected_out

    # formula_ref 必须非空 dict（必填溯源字段）
    inp = FlareNoiseInput(
        flame_power_kw=10.0,
        receiver_distance_m=100.0,
        frequency_hz=500.0,
    )
    res = calc_flare_noise(inp)
    assert isinstance(res.formula_ref, dict)
    assert len(res.formula_ref) >= 3  # source_power / attenuation / leq

    # 冻结：修改触发 FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        inp.receiver_distance_m = 200.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        res.leq_24h_dbA = 80.0  # type: ignore[misc]


# ============================================================================
# Golden fixture 一致性（数值基准回归）
# ============================================================================


def test_noise_matches_golden_fixture():
    """对照 ``golden_noise_api521.json`` 数值基准（rel=1e-6）。

    防 L_w=145 漂移 / ISO 9613-2 分母写错 / 8 倍距 6 dB 系数漏 / Leq 公式
    缺失 N（事件频次）等 regression。
    """
    fixture_path = Path(__file__).parent / "fixtures" / "golden_noise_api521.json"
    if not fixture_path.exists():
        pytest.skip("golden_noise_api521.json 尚未生成（task C4 创建）")
    with fixture_path.open() as f:
        cases = json.load(f)

    for case in cases:
        inp = FlareNoiseInput(
            flame_power_kw=case["flame_power_kw"],
            receiver_distance_m=case["receiver_distance_m"],
            frequency_hz=case.get("frequency_hz", 500.0),
            atmospheric_absorption_db_per_km=case.get(
                "atmospheric_absorption_db_per_km", 1.5
            ),
            directivity_factor_db=case.get("directivity_factor_db", 3.0),
            event_duration_min=case.get("event_duration_min", 1.0),
            n_events_per_24h=case.get("n_events_per_24h", 1),
        )
        res = calc_flare_noise(inp)
        for k, v_expected in case["expected"].items():
            v_actual = getattr(res, k)
            assert v_actual == pytest.approx(v_expected, rel=1e-6), (
                f"golden mismatch case {case['name']}.{k}: "
                f"actual={v_actual} expected={v_expected}"
            )


# ============================================================================
# PcsError code/status 校验（与 flare_tip / dispersion 一致）
# ============================================================================


def test_noise_input_error_inherits_pcs_error():
    """FlareNoiseInputError 继承 PcsError，code=FLARE_NOISE_INPUT_ERROR, status=422。"""
    assert issubclass(FlareNoiseInputError, PcsError)
    assert FlareNoiseInputError.code == "FLARE_NOISE_INPUT_ERROR"
    assert FlareNoiseInputError.status == 422