"""P4-1-2 step 1：PT_FLASH 单元测试。

覆盖（最小 4 类）：
1. PT_FLASH golden（丙烷+正丁烷）：vfrac / y_vapor / x_liquid ≤ 1e-12
2. PT_FLASH 单调性：T 扫描 250K→400K @ 1MPa，vfrac 非递减
3. PT_FLASH 边界：T = T_bubble → vfrac≈0；T = T_dew → vfrac≈1（容差 1e-6）
4. 错误输入：zs 归一化失败 → raise CompositionSumError

其余 7 种 flash 测试（PH/PS/BUBBLE/DEW/SATURATION）留待后续 step（step 2-N）。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services.exceptions import PcsError
from app.services.flash import flash_service
from app.services.flash.flash_service import PT_FLASH, PTFlashResult
from app.services.flash.thermo_factory import (
    CompositionSumError,
    ThermoInterface,
    UnknownSystemTypeError,
    build_thermo,
)

# ---------------------------------------------------------------------------
# Golden fixture 加载
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_pt_flash.json"
GOLDEN = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1) PT_FLASH golden（丙烷+正丁烷）— 单相 + 两相各一组
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case_key",
    [
        "propane_butane_300K_1MPa",  # 亚冷液单相（vfrac=0）
        "propane_butane_335K_1MPa",  # 两相区域（vfrac≈0.32）
    ],
)
def test_pt_flash_matches_golden(case_key):
    """golden fixture：vapor_fraction / y_vapor / x_liquid ≤ 1e-12。"""
    golden = GOLDEN[case_key]
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    res = PT_FLASH(zs, golden["T_K"], golden["P_Pa"], thermo)

    assert math.isclose(res.vapor_fraction, golden["vapor_fraction"], abs_tol=golden["tolerance"])
    for y_actual, y_golden in zip(res.y_vapor, golden["y_vapor"], strict=True):
        assert math.isclose(y_actual, y_golden, abs_tol=golden["tolerance"])
    for x_actual, x_golden in zip(res.x_liquid, golden["x_liquid"], strict=True):
        assert math.isclose(x_actual, x_golden, abs_tol=golden["tolerance"])


def test_pt_flash_y_and_x_sum_to_one():
    """质量约束：y_vapor 和 x_liquid 都归一化到 1。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    res = PT_FLASH(zs, 335.0, 1e6, thermo)
    assert math.isclose(sum(res.y_vapor), 1.0, abs_tol=1e-12)
    assert math.isclose(sum(res.x_liquid), 1.0, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# 2) PT_FLASH 单调性（温度扫描）
# ---------------------------------------------------------------------------


def test_pt_flash_vapor_fraction_monotonic_with_T():
    """T 250K → 400K @ 1MPa：vfrac 非递减（浮点容差 1e-12）。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    prev = -1.0
    for T in [250.0, 280.0, 300.0, 320.0, 330.0, 335.0, 340.0, 345.0, 360.0, 400.0]:
        res = PT_FLASH(zs, T, 1e6, thermo)
        assert res.vapor_fraction >= prev - 1e-12, (
            f"T={T}K: vfrac={res.vapor_fraction} < prev={prev}"
        )
        prev = res.vapor_fraction


# ---------------------------------------------------------------------------
# 3) PT_FLASH 边界：T=T_bubble → vfrac≈0；T=T_dew → vfrac≈1
# ---------------------------------------------------------------------------


def _bubble_P(thermo: ThermoInterface, T: float, zs: list[float]) -> float:
    """内部：泡点压力（Pa）。P_bubble = sum(zs[i] * Psat_i(T))。"""
    return sum(zs[i] * thermo.Psat(i, T) for i in range(len(zs)))


def _dew_P(thermo: ThermoInterface, T: float, zs: list[float]) -> float:
    """内部：露点压力（Pa）。P_dew = 1 / sum(zs[i] / Psat_i(T))。"""
    return 1.0 / sum(zs[i] / thermo.Psat(i, T) for i in range(len(zs)))


def test_pt_flash_vfrac_zero_at_bubble_T_and_one_at_dew_T():
    """边界：T_bubble 时 vfrac≈0（刚汽化开始），T_dew 时 vfrac≈1（露点结束）。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)

    # 解 T_bubble（T 使 P_bubble=1MPa）
    from scipy.optimize import brentq

    T_bubble = brentq(
        lambda T: _bubble_P(thermo, T, zs) - 1e6, 200.0, 500.0, xtol=1e-6
    )
    T_dew = brentq(
        lambda T: _dew_P(thermo, T, zs) - 1e6, 200.0, 500.0, xtol=1e-6
    )
    assert T_bubble < T_dew  # sanity

    # T = T_bubble 时 vfrac ≈ 0
    res_bubble = PT_FLASH(zs, T_bubble, 1e6, thermo)
    assert math.isclose(res_bubble.vapor_fraction, 0.0, abs_tol=1e-6)

    # T = T_dew 时 vfrac ≈ 1
    res_dew = PT_FLASH(zs, T_dew, 1e6, thermo)
    assert math.isclose(res_dew.vapor_fraction, 1.0, abs_tol=1e-6)


# ---------------------------------------------------------------------------
# 4) 错误输入：zs 归一化失败 → raise CompositionSumError
# ---------------------------------------------------------------------------


def test_pt_flash_with_unnormalized_zs_normalizes_silently():
    """sum=1.5 等"可归一化"输入自动归一化（不报错），与 build_thermo 一致。"""
    zs, cass = [0.75, 0.75], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    # 归一化后 = [0.5, 0.5]；flash 不报错
    res = PT_FLASH([0.75, 0.75], 335.0, 1e6, thermo)
    assert 0.0 <= res.vapor_fraction <= 1.0


def test_pt_flash_with_negative_zs_raises_composition_error():
    """PT_FLASH 不直接做归一化，但 build_thermo 在构造时就 raise CompositionSumError。"""
    with pytest.raises(CompositionSumError):
        build_thermo("LIGHT_HYDROCARBON", [-0.1, 1.1], ["74-98-6", "106-97-8"])


def test_pt_flash_with_empty_zs_raises_composition_error():
    """空 zs → CompositionSumError。"""
    with pytest.raises(CompositionSumError):
        build_thermo("LIGHT_HYDROCARBON", [], [])


def test_pt_flash_unknown_system_type_raises():
    """未知 system_type → UnknownSystemTypeError。"""
    with pytest.raises(UnknownSystemTypeError):
        build_thermo("UNKNOWN_X", [1.0], ["74-82-8"])


def test_pt_flash_error_inherits_pcs_error():
    """异常链：CompositionSumError 继承 PcsError（422 风格）。"""
    with pytest.raises(PcsError):
        build_thermo("BAD", [1.0], ["74-82-8"])


# ---------------------------------------------------------------------------
# 模块导出检查
# ---------------------------------------------------------------------------


def test_flash_service_module_exports_minimum_symbols():
    """step 1 模块导出：仅 PTFlashResult + PT_FLASH。"""
    required = {"PTFlashResult", "PT_FLASH"}
    assert required.issubset(set(dir(flash_service)))


def test_pt_flash_result_is_named_tuple():
    """PTFlashResult 是 NamedTuple（兼容 tuple 解包）。"""
    r = PTFlashResult(0.5, [0.6, 0.4], [0.3, 0.7])
    assert r.vapor_fraction == 0.5
    v, y, x = r
    assert v == 0.5
    assert y == [0.6, 0.4]
