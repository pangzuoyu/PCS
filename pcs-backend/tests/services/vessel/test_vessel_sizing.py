"""P5-1-1 vessel_service 核心：calc_vessel_sizing 测试。

按 PCS-PLAN V1.3 §115-134 + ADR-0032：
- 6 例 golden fixture（4 容器类型 × 卧式/立式）
- K 因子边界 0.04/0.10/0.15
- SI 单位（m/s）
- 与手算 + ChEDL 交叉验证偏差 ≤1%
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services import chedl_wrapper
from app.services.vessel.vessel_service import (
    VesselInputError,
    VesselSizingInput,
    VesselSizingResult,
    calc_vessel_sizing,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_vessel_souders_brown.json"


def _load_golden_cases() -> list[dict]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["cases"]


def _case_to_input(c: dict) -> VesselSizingInput:
    return VesselSizingInput(
        vessel_type=c["vessel_type"],
        rho_L_kg_m3=c["rho_L_kg_m3"],
        rho_V_kg_m3=c["rho_V_kg_m3"],
        liquid_flow_m3_s=c["liquid_flow_m3_s"],
        vapor_flow_m3_s=c["vapor_flow_m3_s"],
        residence_time_min=c["residence_time_min"],
        K_factor_ms=c["K_factor_ms"],
    )


# ============================================================================
# 1. Golden fixture 6 例
# ============================================================================


@pytest.mark.parametrize("case", _load_golden_cases(), ids=lambda c: c["id"])
def test_golden_vessel_sizing(case):
    """6 例 golden fixture：V_max / D_min / liquid_volume / check / confidence 全字段。"""
    inp = _case_to_input(case)
    result = calc_vessel_sizing(inp)

    exp = case["expected"]

    # V_max 偏差 ≤1%
    assert math.isclose(result.V_max_ms, exp["V_max_ms"], rel_tol=0.01), (
        f"{case['id']} V_max={result.V_max_ms} 期望 {exp['V_max_ms']}"
    )
    # D_min 偏差 ≤1%
    assert math.isclose(result.D_min_m, exp["D_min_m"], rel_tol=0.01), (
        f"{case['id']} D_min={result.D_min_m} 期望 {exp['D_min_m']}"
    )
    # liquid_volume 偏差 ≤1%
    assert math.isclose(result.liquid_volume_m3, exp["liquid_volume_m3"], rel_tol=0.01), (
        f"{case['id']} liquid_volume={result.liquid_volume_m3} 期望 {exp['liquid_volume_m3']}"
    )
    # 离散字段精确匹配
    assert result.vessel_type == case["vessel_type"]
    assert result.check_result == exp["check_result"]
    assert result.confidence == exp["confidence"]
    assert math.isclose(result.K_factor_ms, case["K_factor_ms"], rel_tol=1e-6)


# ============================================================================
# 2. ChEDL 交叉验证（≤1% 偏差）
# ============================================================================


def test_chedl_v_Souders_Brown_cross_validation():
    """与 ChEDL fluids.separator.v_Souders_Brown 交叉验证偏差 ≤1%。

    PCS-PLAN §129 V1.7 问题1 ChEDL 函数签名确认：返回 V_max 还是 K 因子？
    chedl_wrapper.v_Souders_Brown(K, rhol, rhog) 返回 V_max（与手算一致）。
    """
    inp = VesselSizingInput(
        vessel_type="VERTICAL",
        rho_L_kg_m3=850.0,
        rho_V_kg_m3=1.2,
        liquid_flow_m3_s=0.005,
        vapor_flow_m3_s=0.5,
        residence_time_min=5.0,
        K_factor_ms=0.10,
    )
    result = calc_vessel_sizing(inp)

    chedl_v_max = chedl_wrapper.v_Souders_Brown(
        K=0.10, rhol=850.0, rhog=1.2
    )
    assert math.isclose(result.V_max_ms, chedl_v_max, rel_tol=0.01), (
        f"业务层 V_max={result.V_max_ms} ChEDL={chedl_v_max} 偏差 >1%"
    )


# ============================================================================
# 3. K 因子边界（0.04/0.10/0.15）
# ============================================================================


@pytest.mark.parametrize("K,vessel_type", [
    (0.01, "VERTICAL"),    # 立式下界 = 物理下界
    (0.05, "VERTICAL"),    # 立式上界（边界 MEDIUM）
    (0.05, "HORIZONTAL"),  # 卧式下界（边界 MEDIUM）
    (0.11, "HORIZONTAL"),  # 卧式上界（边界 MEDIUM）
    (0.04, "WITH_DEMISTER"), # 除沫器下界（边界 MEDIUM）
    (0.10, "WITH_DEMISTER"), # 除沫器上界（边界 MEDIUM）
])
def test_K_factor_boundary(K, vessel_type):
    """K 因子 vessel_type 子区间边界值应落入 MEDIUM 保守区间（不抛异常）。

    ADR-0032 V1.1 决策 2：vessel_type 子区间边界值视为 MEDIUM（保守）。
    """
    inp = VesselSizingInput(
        vessel_type=vessel_type,
        rho_L_kg_m3=850.0,
        rho_V_kg_m3=1.2,
        liquid_flow_m3_s=0.005,
        vapor_flow_m3_s=0.5,
        residence_time_min=5.0,
        K_factor_ms=K,
    )
    result = calc_vessel_sizing(inp)
    # 边界值不抛异常；置信度按 ADR-0032 V1.1：边界 → MEDIUM
    assert result.V_max_ms > 0
    assert result.confidence == "MEDIUM"


# ============================================================================
# 4. 边界异常
# ============================================================================


def test_zero_liquid_flow_raises():
    """liquid_flow_m3_s = 0 应抛 VesselInputError（无持液计算意义）。"""
    with pytest.raises(VesselInputError) as exc_info:
        calc_vessel_sizing(VesselSizingInput(
            vessel_type="VERTICAL",
            rho_L_kg_m3=850.0, rho_V_kg_m3=1.2,
            liquid_flow_m3_s=0.0, vapor_flow_m3_s=0.5,
            residence_time_min=5.0, K_factor_ms=0.10,
        ))
    assert "liquid_flow" in str(exc_info.value).lower() or "input" in str(exc_info.value).lower()


def test_K_factor_out_of_range_raises():
    """K 因子 < 0.01 或 > 1.0 应抛 VesselInputError（超出物理合理范围）。"""
    with pytest.raises(VesselInputError):
        calc_vessel_sizing(VesselSizingInput(
            vessel_type="VERTICAL",
            rho_L_kg_m3=850.0, rho_V_kg_m3=1.2,
            liquid_flow_m3_s=0.005, vapor_flow_m3_s=0.5,
            residence_time_min=5.0, K_factor_ms=2.0,  # 远超 0.15 上限
        ))


def test_rho_L_less_than_rho_V_raises():
    """ρ_L < ρ_V 物理不合理（液相比气相轻不可能），应抛 VesselInputError。"""
    with pytest.raises(VesselInputError):
        calc_vessel_sizing(VesselSizingInput(
            vessel_type="VERTICAL",
            rho_L_kg_m3=1.0, rho_V_kg_m3=10.0,  # 倒置
            liquid_flow_m3_s=0.005, vapor_flow_m3_s=0.5,
            residence_time_min=5.0, K_factor_ms=0.10,
        ))


# ============================================================================
# 5. 停留时间分支（V1.6：vertical 3~5 min / horizontal 5~10 min）
# ============================================================================


def test_vertical_default_residence_time_3_to_5_min():
    """立式容器默认停留时间区间 3~5 min。"""
    inp = VesselSizingInput(
        vessel_type="VERTICAL",
        rho_L_kg_m3=850.0, rho_V_kg_m3=1.2,
        liquid_flow_m3_s=0.005, vapor_flow_m3_s=0.5,
        residence_time_min=0.0,  # 触发默认
        K_factor_ms=0.10,
    )
    result = calc_vessel_sizing(inp)
    # 默认值应在 [3, 5] min 区间
    assert 3.0 <= result.residence_time_min <= 5.0


def test_horizontal_default_residence_time_5_to_10_min():
    """卧式容器默认停留时间区间 5~10 min。"""
    inp = VesselSizingInput(
        vessel_type="HORIZONTAL",
        rho_L_kg_m3=1000.0, rho_V_kg_m3=1.2,
        liquid_flow_m3_s=0.008, vapor_flow_m3_s=0.8,
        residence_time_min=0.0,  # 触发默认
        K_factor_ms=0.12,
    )
    result = calc_vessel_sizing(inp)
    assert 5.0 <= result.residence_time_min <= 10.0


# ============================================================================
# 6. 数据类契约
# ============================================================================


def test_vessel_sizing_result_is_frozen_dataclass():
    """VesselSizingResult 必须是 frozen dataclass（不可变 + 可哈希）。"""
    from dataclasses import FrozenInstanceError, fields

    # 含 8 字段
    field_names = {f.name for f in fields(VesselSizingResult)}
    expected = {
        "V_max_ms", "D_min_m", "liquid_volume_m3", "vessel_type",
        "K_factor_ms", "residence_time_min", "check_result", "confidence",
    }
    assert field_names == expected, (
        f"VesselSizingResult 字段不匹配。缺失: {expected - field_names}，"
        f"多余: {field_names - expected}"
    )

    # 不可变
    result = calc_vessel_sizing(VesselSizingInput(
        vessel_type="VERTICAL",
        rho_L_kg_m3=850.0, rho_V_kg_m3=1.2,
        liquid_flow_m3_s=0.005, vapor_flow_m3_s=0.5,
        residence_time_min=5.0, K_factor_ms=0.10,
    ))
    with pytest.raises(FrozenInstanceError):
        result.V_max_ms = 999.0  # type: ignore[misc]