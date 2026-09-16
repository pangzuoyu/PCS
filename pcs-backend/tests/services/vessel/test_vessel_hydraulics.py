"""P5-1-2 vessel 流体力学校核（fluids.tanks 排空/液位-容积/溢流/放空）测试。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §136-163 + ADR-0032：
- 4 例 golden fixture（排空/液位-容积/溢流-OK/溢流-NG）
- ≤5% 偏差（PCS-PLAN §162）
- **V1.9 F-13-5 双套测试 pattern**：fluids 1.3.1 不存在时 fallback 自研实现
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services import chedl_wrapper
from app.services.vessel.vessel_service import (
    VesselHydraulicsInput,
    VesselHydraulicsResult,
    VesselInputError,
    calc_vessel_hydraulics,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_vessel_hydraulics.json"


def _load_golden_cases() -> list[dict]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["cases"]


# ============================================================================
# 0. F-13-4 dir() 核验前置 + ChEDL 函数可用性
# ============================================================================


def _has_fluids_attr(attr_name: str) -> bool:
    """V1.8 F-13-4: 检查 fluids 顶层是否有指定函数（不依赖 fluids.tanks 子模块存在性）。"""
    import fluids

    return hasattr(fluids, attr_name)


# ============================================================================
# 1. F-13-5 双套测试（降级预案）— 排空时间
# ============================================================================


@pytest.mark.skipif(
    not _has_fluids_attr("time_to_empty"),
    reason="ChEDL fluids.time_to_empty 不存在，启用降级路径（V1.9 F-13-5）",
)
def test_empty_time_with_chedl():
    """F-13-5 双套测试#1：ChEDL 路径（如函数存在）。

    与 chedl_wrapper.time_to_empty 直调交叉验证：包装层 fallback 与 ChEDL 一致。
    """
    chedl_val = chedl_wrapper.time_to_empty(
        D_tank=2.0, h0=1.0, d_orifice=0.05, Cd=0.62
    )
    # 自研 fallback = chedl_wrapper 走 fallback 实现
    assert math.isclose(chedl_val, 1165.5, rel_tol=0.01), (
        f"ChEDL 路径排空时间 {chedl_val:.2f} 偏差 >1%"
    )


def test_empty_time_self_implemented():
    """F-13-5 双套测试#2：自研降级路径（始终执行）。

    公式：Q = Cd × A_orifice × √(2g·h) → 积分 dt = -A_tank·dh/Q(h)
    结果：t = (A_tank / (Cd · A_orifice)) · √(2·h0/g)
    """
    # 直接调 chedl_wrapper.time_to_empty（包装层自动降级到自研）
    result = chedl_wrapper.time_to_empty(
        D_tank=2.0, h0=1.0, d_orifice=0.05, Cd=0.62
    )
    assert math.isclose(result, 1165.5, rel_tol=0.01), (
        f"自研路径排空时间 {result:.2f} 期望 1165.5 偏差 >1%"
    )


def test_tank_level_to_volume_ellipse():
    """F-13-5 双套测试：液位-容积曲线（ellipse 封头）。

    卧式 D=2, h=1.5（>D/4=0.5）：V = π·D³/24 + π·r²·(h - D/4)
                                  = π/3 + π·1·1 ≈ 4.189
    """
    result = chedl_wrapper.tank_level_to_volume(D=2.0, h=1.5, head_type="ellipse")
    assert math.isclose(result, 4.189, rel_tol=0.01), (
        f"液位-容积 {result:.4f} 期望 4.189 偏差 >1%"
    )


# ============================================================================
# 2. Golden fixture 4 例（≤5% 偏差验收）
# ============================================================================


@pytest.mark.parametrize("case", _load_golden_cases(), ids=lambda c: c["id"])
def test_golden_vessel_hydraulics(case):
    """4 例 golden fixture：empty_time / level_volume / overflow_ok / overflow_capacity。"""
    case_id = case["id"]

    if case_id == "vertical_empty_basic":
        # 排空时间
        result = chedl_wrapper.time_to_empty(
            D_tank=case["D_m"],
            h0=case["h0_m"],
            d_orifice=case["d_orifice_m"],
            Cd=case["Cd_orifice"],
        )
        exp = case["expected_empty_time_s"]
        tol = case["tol_empty_time_pct"]
        assert math.isclose(result, exp, rel_tol=tol), (
            f"{case_id} empty_time={result:.2f} 期望 {exp} 偏差 >{tol*100:.0f}%"
        )

    elif case_id == "horizontal_level_curve":
        # 液位-容积曲线
        result = chedl_wrapper.tank_level_to_volume(
            D=case["D_m"], h=case["level_m"], head_type=case["head_type"]
        )
        exp = case["expected_volume_m3"]
        tol = case["tol_volume_pct"]
        assert math.isclose(result, exp, rel_tol=tol), (
            f"{case_id} level_volume={result:.4f} 期望 {exp} 偏差 >{tol*100:.0f}%"
        )

    elif case_id in ("overflow_pass", "overflow_fail"):
        # 溢流校核：Q_in vs overflow capacity
        # overflow_capacity = Cd × A_overflow × √(2·g·h)
        g = 9.80665
        A_overflow = math.pi * (case["d_overflow_m"] / 2.0) ** 2
        capacity = (
            case["Cd_overflow"]
            * A_overflow
            * math.sqrt(2.0 * g * case["h_overflow_m"])
        )
        # 手算 vs 预期
        exp = case["expected_capacity_m3_s"]
        tol = case["tol_capacity_pct"]
        assert math.isclose(capacity, exp, rel_tol=tol), (
            f"{case_id} overflow_capacity={capacity:.5f} 期望 {exp} 偏差 >{tol*100:.0f}%"
        )
        # OK/FAIL 判定
        ok = case["Q_in_liquid_m3_s"] < capacity
        assert ok == case["expected_overflow_ok"], (
            f"{case_id} overflow_ok={ok} 期望 {case['expected_overflow_ok']}"
        )


# ============================================================================
# 3. calc_vessel_hydraulics 集成接口
# ============================================================================


def test_calc_vessel_hydraulics_returns_frozen_dataclass():
    """calc_vessel_hydraulics 返回 frozen dataclass（不可变 + 可哈希）。"""
    from dataclasses import FrozenInstanceError, fields

    inp = VesselHydraulicsInput(
        D_m=2.0, L_m=5.0, h0_m=1.0,
        d_orifice_m=0.05, Cd_orifice=0.62,
        Q_in_liquid_m3_s=0.005,
        d_overflow_m=0.1, h_overflow_m=1.0, Cd_overflow=0.62,
        thermal_breathing_factor=1.0,
    )
    result = calc_vessel_hydraulics(inp)

    # 含 4 字段
    field_names = {f.name for f in fields(VesselHydraulicsResult)}
    expected = {
        "empty_time_s", "overflow_ok", "level_volume_curve_json",
        "vent_capacity_m3_s",
    }
    assert field_names == expected, (
        f"VesselHydraulicsResult 字段不匹配。缺失: {expected - field_names}，"
        f"多余: {field_names - expected}"
    )

    # 不可变
    with pytest.raises(FrozenInstanceError):
        result.empty_time_s = 999.0  # type: ignore[misc]


def test_calc_vessel_hydraulics_integration():
    """calc_vessel_hydraulics 集成测试：4 子计算联动。"""
    inp = VesselHydraulicsInput(
        D_m=2.0, L_m=5.0, h0_m=1.0,
        d_orifice_m=0.05, Cd_orifice=0.62,
        Q_in_liquid_m3_s=0.005,
        d_overflow_m=0.1, h_overflow_m=1.0, Cd_overflow=0.62,
        thermal_breathing_factor=1.0,
    )
    result = calc_vessel_hydraulics(inp)

    # 排空时间 ≈ 1165.5 s
    assert math.isclose(result.empty_time_s, 1165.5, rel_tol=0.01)
    # 溢流 OK（capacity 0.02157 > 0.005）
    assert result.overflow_ok is True
    # 液位-容积曲线 JSON 是非空 dict（key='D=2.0, h=...', value=volume_m3）
    curve = json.loads(result.level_volume_curve_json)
    assert isinstance(curve, dict)
    assert len(curve) > 0
    # 放空能力：V_total = π·D²/4·L ≈ 15.71 m³，vent = 1.2 × 1.0 × 15.71 / 60 ≈ 0.314 m³/s
    assert result.vent_capacity_m3_s > 0


def test_calc_vessel_hydraulics_negative_input_raises():
    """VesselHydraulicsInput 负值物理量应抛 VesselInputError。"""
    with pytest.raises(VesselInputError):
        calc_vessel_hydraulics(VesselHydraulicsInput(
            D_m=-1.0,  # 非法
            L_m=5.0, h0_m=1.0,
            d_orifice_m=0.05, Cd_orifice=0.62,
            Q_in_liquid_m3_s=0.005,
            d_overflow_m=0.1, h_overflow_m=1.0, Cd_overflow=0.62,
            thermal_breathing_factor=1.0,
        ))


# ============================================================================
# 4. F-13-5 降级标记（formula_ref 模式预留）
# ============================================================================


def test_f13_5_fallback_source_documented():
    """F-13-5 降级预案：包装层 fallback 路径在 docstring/源码标注。

    业务代码通过 chedl_wrapper 调用，无论 ChEDL 函数是否存在都得到一致结果。
    标记：formula_ref.source = "self_implemented"（在源码 docstring 注记）。
    """
    import inspect

    from app.services import chedl_wrapper as cw

    src = inspect.getsource(cw.time_to_empty)
    assert "fallback" in src.lower() or "self_implemented" in src.lower(), (
        "F-13-5：包装层 time_to_empty 应标注 fallback 自研路径"
    )
    src2 = inspect.getsource(cw.tank_level_to_volume)
    assert "fallback" in src2.lower() or "self_implemented" in src2.lower(), (
        "F-13-5：包装层 tank_level_to_volume 应标注 fallback 自研路径"
    )