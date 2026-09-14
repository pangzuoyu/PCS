"""P4-2-2 WallThicknessService 单元测试。

覆盖：
1. seamless golden：P=2.0, D=168.3, S=138, E=1, Y=0.4 → t≈1.213 mm
2. welded golden：同上 + W=0.85 → t≈1.425 mm
3. nominal + c：t_calc + c_mm → t_nom
4. round_to_schedule：DN150 t_nom=3.213 → SCH 10 (3.40 mm)（最小满足 ≥ t_nom）
5. get_allowable_stress：已知 material + 设计温度 → S（温度插值中位）
6. 边界：P=0 → t=0；D=0 / S=0 → raise ValueError
7. 超界温度：设计温度超出许用应力表 → raise

Golden 溯源：
- ASME B31.3 2018/2020 §304.1.2（直管壁厚计算公式）
- ASME B36.10 / B36.19（Sch 标准系列壁厚表，固化于 service 顶部常量）
- _ASME_B31_3_A1（许用应力，溯源 CommonService._ASME_B31_3_A1，5 牌号 × 6 温度点）
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services.common_service import CommonService
from app.services.pipe.wall_thickness_service import (
    WallThicknessInputError,
    WallThicknessTempOOBError,
    calc_wall_thickness_seamless,
    calc_wall_thickness_welded,
    get_allowable_stress,
    nominal_thickness,
    round_to_schedule,
)

# ---------------------------------------------------------------------------
# Golden fixture 加载
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_wall_thickness.json"
GOLDEN = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1) seamless golden（公式：t = P·D / (2·(S·E + P·Y))）
# ---------------------------------------------------------------------------


def test_calc_wall_thickness_seamless_golden():
    """seamless：P=2.0, D=168.3, S=138, E=1.0, Y=0.4 → t≈1.213 mm（容差 0.01）。"""
    golden = GOLDEN["seamless_basic"]
    t = calc_wall_thickness_seamless(
        P_MPa=golden["P_MPa"],
        D_mm=golden["D_mm"],
        S_MPa=golden["S_MPa"],
        E=golden["E"],
        Y=golden["Y"],
    )
    assert math.isclose(t, golden["t_calc_mm"], abs_tol=golden["tolerance"])


def test_calc_wall_thickness_seamless_zero_P_returns_zero():
    """P=0（无内压） → t=0（公式自然为零）。"""
    t = calc_wall_thickness_seamless(
        P_MPa=0.0, D_mm=168.3, S_MPa=138.0, E=1.0, Y=0.4
    )
    assert t == pytest.approx(0.0, abs=1e-12)


def test_calc_wall_thickness_seamless_zero_D_raises():
    """D=0（管径退化） → 公式除零，raise InputError。"""
    with pytest.raises(WallThicknessInputError):
        calc_wall_thickness_seamless(
            P_MPa=2.0, D_mm=0.0, S_MPa=138.0, E=1.0, Y=0.4
        )


def test_calc_wall_thickness_seamless_zero_S_raises():
    """S=0（许用应力为零） → 物理非法，raise InputError。"""
    with pytest.raises(WallThicknessInputError):
        calc_wall_thickness_seamless(
            P_MPa=2.0, D_mm=168.3, S_MPa=0.0, E=1.0, Y=0.4
        )


# ---------------------------------------------------------------------------
# 2) welded golden（公式：t = P·D / (2·(S·E·W + P·Y))）
# ---------------------------------------------------------------------------


def test_calc_wall_thickness_welded_golden():
    """welded：同上 + W=0.85 → t≈1.425 mm（容差 0.01）。"""
    golden = GOLDEN["welded_basic"]
    t = calc_wall_thickness_welded(
        P_MPa=golden["P_MPa"],
        D_mm=golden["D_mm"],
        S_MPa=golden["S_MPa"],
        E=golden["E"],
        Y=golden["Y"],
        W=golden["W"],
    )
    assert math.isclose(t, golden["t_calc_mm"], abs_tol=golden["tolerance"])


def test_calc_wall_thickness_welded_zero_D_raises():
    """welded D=0 → raise InputError。"""
    with pytest.raises(WallThicknessInputError):
        calc_wall_thickness_welded(
            P_MPa=2.0, D_mm=0.0, S_MPa=138.0, E=1.0, Y=0.4, W=0.85
        )


def test_calc_wall_thickness_welded_zero_S_raises():
    """welded S=0 → raise InputError。"""
    with pytest.raises(WallThicknessInputError):
        calc_wall_thickness_welded(
            P_MPa=2.0, D_mm=168.3, S_MPa=0.0, E=1.0, Y=0.4, W=0.85
        )


# ---------------------------------------------------------------------------
# 3) nominal + c
# ---------------------------------------------------------------------------


def test_nominal_thickness_adds_corrosion_allowance():
    """t_nom = t_calc + c_mm；c=2 → t_nom = 1.213 + 2 = 3.213。"""
    golden = GOLDEN["seamless_basic"]
    t_nom = nominal_thickness(t_calc=golden["t_calc_mm"], c_mm=2.0)
    assert math.isclose(t_nom, golden["t_nom_with_c_2"], abs_tol=0.01)


def test_nominal_thickness_zero_c_returns_calc():
    """c=0 → t_nom == t_calc。"""
    assert nominal_thickness(t_calc=1.213, c_mm=0.0) == pytest.approx(1.213)


def test_nominal_thickness_negative_c_raises():
    """c < 0 → 物理非法，raise InputError。"""
    with pytest.raises(WallThicknessInputError):
        nominal_thickness(t_calc=1.0, c_mm=-0.5)


# ---------------------------------------------------------------------------
# 4) round_to_schedule（ASME B36.10/B36.19 Sch 标准系列）
# ---------------------------------------------------------------------------


def test_round_to_schedule_dn150_t_nom_3_213_picks_sch10():
    """DN150 (168.3 mm) t_nom=3.213 → SCH 10 (3.40 mm)（最小满足 ≥ t_nom）。"""
    golden = GOLDEN["schedule_rounding"]
    result = round_to_schedule(t_nom=golden["t_nom_mm"], DN_mm=golden["DN_mm"])
    assert result == golden["schedule_round"]
    assert result == "SCH 10"


def test_round_to_schedule_dn150_exact_sch40_match():
    """DN150 t_nom=3.91 → SCH 40（精确命中）。"""
    result = round_to_schedule(t_nom=3.91, DN_mm=168.3)
    assert result == "SCH 40"


def test_round_to_schedule_dn50_exact_sch40_match():
    """DN50 (60.3 mm) t_nom=3.91 → SCH 40 / STD。"""
    # DN50 SCH 40 = 3.91；STD = 3.91 → 同样最小满足值
    result = round_to_schedule(t_nom=3.91, DN_mm=60.3)
    assert result in ("SCH 40", "STD")


def test_round_to_schedule_dn_below_minimum_raises():
    """DN < DN15 (21.3 mm) → 无标准 Sch，raise InputError。"""
    with pytest.raises(WallThicknessInputError):
        round_to_schedule(t_nom=1.0, DN_mm=10.0)


def test_round_to_schedule_dn_above_maximum_raises():
    """DN > DN600 (610 mm) → 不在固化表内，raise InputError。"""
    with pytest.raises(WallThicknessInputError):
        round_to_schedule(t_nom=10.0, DN_mm=700.0)


def test_round_to_schedule_t_nom_zero_picks_thinnest():
    """t_nom=0 → 选最薄的标准 Sch（SCH 5S / SCH 5，取决于 DN 是否支持）。"""
    # DN150 SCH 5 = 2.77；最小正值
    result = round_to_schedule(t_nom=0.0, DN_mm=168.3)
    assert result == "SCH 5"


def test_round_to_schedule_dn_with_no_match_raises():
    """DN 在表内但所有 Sch 都 < t_nom → raise InputError（需要更厚管或更换材料）。"""
    # DN15 (21.3) 最大 Sch XXS = 7.47；t_nom = 100 → 全部不满足
    with pytest.raises(WallThicknessInputError):
        round_to_schedule(t_nom=100.0, DN_mm=21.3)


# ---------------------------------------------------------------------------
# 5) get_allowable_stress（基于 CommonService.allowable_stress）
# ---------------------------------------------------------------------------


def test_get_allowable_stress_exact_table_point():
    """A106-GrB @ 200°C（节点温度） → 113.8 MPa，interpolated=False。"""
    result = get_allowable_stress(material="A106-GrB", design_temp_C=200.0)
    assert math.isclose(result["stress_mpa"], 113.8, abs_tol=0.1)
    assert result["interpolated"] is False
    assert result["material"] == "A106-GrB"
    assert result["source"] == "ASME_B31.3_TABLE_A1"


def test_get_allowable_stress_interpolation_midpoint():
    """A106-GrB @ 150°C（节点温度间） → 在 prev=100°C / next=200°C 邻接节点间线性插值。

    正确插值：table[100]=124.1, table[200]=113.8，ratio=0.5
    → 124.1 + 0.5*(113.8 - 124.1) = 118.95 MPa。
    """
    result = get_allowable_stress(material="A106-GrB", design_temp_C=150.0)
    assert result["interpolated"] is True
    assert math.isclose(result["stress_mpa"], 118.95, abs_tol=0.1)


def test_get_allowable_stress_lower_node():
    """A106-GrB @ 38°C（最低节点） → 137.9 MPa。"""
    result = get_allowable_stress(material="A106-GrB", design_temp_C=38.0)
    assert math.isclose(result["stress_mpa"], 137.9, abs_tol=0.1)
    assert result["interpolated"] is False


def test_get_allowable_stress_unknown_material_raises():
    """未知 material → raise 422。"""
    with pytest.raises(WallThicknessInputError):
        get_allowable_stress(material="UNKNOWN-MATERIAL-XYZ", design_temp_C=100.0)


def test_get_allowable_stress_temp_above_range_raises():
    """温度 > 上限 → raise WallThicknessTempOOBError。"""
    with pytest.raises(WallThicknessTempOOBError):
        get_allowable_stress(material="A106-GrB", design_temp_C=2000.0)


def test_get_allowable_stress_temp_below_range_raises():
    """温度 < 下限（38°C）→ raise WallThicknessTempOOBError。"""
    with pytest.raises(WallThicknessTempOOBError):
        get_allowable_stress(material="A106-GrB", design_temp_C=-50.0)


def test_get_allowable_stress_returns_common_service_payload():
    """get_allowable_stress 返回字典结构与 CommonService.allowable_stress 一致。"""
    result = get_allowable_stress(material="304-SS", design_temp_C=200.0)
    # 直接对照 CommonService 同输入输出（确保单一真源）
    common = CommonService.allowable_stress("304-SS", 200.0)
    assert result == common