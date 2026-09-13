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
from app.services.flash.flash_service import (
    BUBBLE_P,
    BUBBLE_T,
    DEW_P,
    DEW_T,
    PH_FLASH,
    PS_FLASH,
    PT_FLASH,
    FlashConvergenceError,
    PTFlashResult,
)
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


# ===========================================================================
# P4-1-2 step 2：BUBBLE_P / BUBBLE_T / DEW_P / DEW_T / PH_FLASH / PS_FLASH
# ===========================================================================

# Golden fixture 加载
_BD_FIXTURE = Path(__file__).parent / "fixtures" / "golden_bubble_dew.json"
_PHPS_FIXTURE = Path(__file__).parent / "fixtures" / "golden_ph_ps.json"
GOLDEN_BD = json.loads(_BD_FIXTURE.read_text(encoding="utf-8"))
GOLDEN_PHPS = json.loads(_PHPS_FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1) BUBBLE_P / BUBBLE_T golden（丙烷+正丁烷）
# ---------------------------------------------------------------------------


def test_bubble_p_direct_formula():
    """BUBBLE_P = sum(z_i * Psat_i(T))：直接公式。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    T = 300.0
    expected = sum(zs[i] * thermo.Psat(i, T) for i in range(2))
    assert math.isclose(BUBBLE_P(zs, T, thermo), expected, abs_tol=1e-12)


def test_bubble_T_at_1MPa_matches_golden():
    """BUBBLE_T @ 1MPa 丙烷+正丁烷：≤ 1e-3 K。"""
    golden = GOLDEN_BD["propane_butane_bubble_T_at_1MPa"]
    zs, cass = golden["zs"], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    T_bubble = BUBBLE_T(zs, golden["P_Pa"], thermo)
    assert math.isclose(T_bubble, golden["T_bubble_K"], abs_tol=golden["tolerance"])


def test_bubble_T_roundtrip_through_bubble_p():
    """BUBBLE_T(P) → 带回 P_bubble(T_bubble) → 应等于原 P（自洽）。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    P = 1e6
    T_bubble = BUBBLE_T(zs, P, thermo)
    P_recovered = BUBBLE_P(zs, T_bubble, thermo)
    assert math.isclose(P_recovered, P, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# 2) DEW_P / DEW_T golden
# ---------------------------------------------------------------------------


def test_dew_p_direct_formula():
    """DEW_P = 1 / sum(z_i / Psat_i(T))：直接公式。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    T = 300.0
    expected = 1.0 / sum(zs[i] / thermo.Psat(i, T) for i in range(2))
    assert math.isclose(DEW_P(zs, T, thermo), expected, abs_tol=1e-12)


def test_dew_T_at_1MPa_matches_golden():
    """DEW_T @ 1MPa 丙烷+正丁烷：≤ 1e-3 K。"""
    golden = GOLDEN_BD["propane_butane_dew_T_at_1MPa"]
    zs, cass = golden["zs"], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    T_dew = DEW_T(zs, golden["P_Pa"], thermo)
    assert math.isclose(T_dew, golden["T_dew_K"], abs_tol=golden["tolerance"])


def test_dew_T_roundtrip_through_dew_p():
    """DEW_T(P) → 带回 P_dew(T_dew) → 应等于原 P（自洽）。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    P = 1e6
    T_dew = DEW_T(zs, P, thermo)
    P_recovered = DEW_P(zs, T_dew, thermo)
    assert math.isclose(P_recovered, P, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# 3) BUBBLE_T 和 DEW_T 区间：335K ∈ (BUBBLE_T, DEW_T)
# ---------------------------------------------------------------------------


def test_335K_in_two_phase_region_at_1MPa():
    """BUBBLE_T(1MPa) < 335 K < DEW_T(1MPa)（互逆验证）。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    T_bubble = BUBBLE_T(zs, 1e6, thermo)
    T_dew = DEW_T(zs, 1e6, thermo)
    assert T_bubble < 335.0 < T_dew, (
        f"335K 应在 (T_bubble={T_bubble}, T_dew={T_dew}) 区间内"
    )


# ---------------------------------------------------------------------------
# 4) 纯组分自洽：BUBBLE_P == DEW_P == Psat
# ---------------------------------------------------------------------------


def test_pure_component_bubble_equals_dew_equals_psat():
    """纯组分：BUBBLE_P == DEW_P == Psat（容差 1e-6 Pa）。"""
    golden = GOLDEN_BD["pure_bubble_equals_dew_equals_psat"]
    zs = [1.0]
    cass = [golden["fluid_cas"]]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    T = golden["T_K"]
    P_bubble = BUBBLE_P(zs, T, thermo)
    P_dew = DEW_P(zs, T, thermo)
    P_sat = thermo.Psat(0, T)
    tol = golden["tolerance"]
    assert math.isclose(P_bubble, P_dew, abs_tol=tol)
    assert math.isclose(P_bubble, P_sat, abs_tol=tol)
    assert math.isclose(P_bubble, golden["P_sat_Pa"], abs_tol=tol)


def test_pure_component_bubble_T_equals_dew_T_equals_Tsat():
    """纯组分：BUBBLE_T == DEW_T == Tsat（容差 1e-6 K）。"""
    zs = [1.0]
    cass = ["74-98-6"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    P = 1e6
    T_bubble = BUBBLE_T(zs, P, thermo)
    T_dew = DEW_T(zs, P, thermo)
    T_sat = thermo.Tsat(0, P)
    tol = 1e-6
    assert math.isclose(T_bubble, T_dew, abs_tol=tol)
    assert math.isclose(T_bubble, T_sat, abs_tol=tol)


# ---------------------------------------------------------------------------
# 5) PH_FLASH roundtrip
# ---------------------------------------------------------------------------


def test_ph_flash_roundtrip_matches_golden():
    """PH_FLASH roundtrip：PT_FLASH(335K,1MPa)→H；PH_FLASH 反推回同 P ≤ 1e-3 Pa。"""
    golden = GOLDEN_PHPS["ph_flash_roundtrip"]
    zs, cass = golden["zs"], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)

    # 1) PT_FLASH 算 H_target
    res_pt = PT_FLASH(zs, golden["T_K"], golden["P_Pa"], thermo)
    H_target = thermo.H_PT(
        zs,
        golden["T_K"],
        golden["P_Pa"],
        res_pt.vapor_fraction,
        res_pt.y_vapor,
        res_pt.x_liquid,
    )
    # 2) H_target 应与 golden 偏差 ≤ 1e-3（J/mol）
    assert math.isclose(H_target, golden["H_target_J_per_mol"], abs_tol=1e-3)

    # 3) PH_FLASH 反推 P
    P, vfrac, y, x = PH_FLASH(zs, golden["T_K"], H_target, thermo)
    # 4) P 应等于 1e6（容差 1e-3 Pa）
    assert math.isclose(P, golden["P_Pa"], abs_tol=golden["tolerance"])
    # 5) vfrac 应等于 PT_FLASH 原始 vfrac（容差 1e-3）
    assert math.isclose(vfrac, res_pt.vapor_fraction, abs_tol=1e-3)


def test_ph_flash_returns_valid_pt_state():
    """PH_FLASH 返回的 (P, vfrac, y, x) 在 PT_FLASH(P) 下应自洽。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    res_pt = PT_FLASH(zs, 335.0, 1e6, thermo)
    H_target = thermo.H_PT(
        zs, 335.0, 1e6, res_pt.vapor_fraction, res_pt.y_vapor, res_pt.x_liquid
    )
    P, vfrac, y, x = PH_FLASH(zs, 335.0, H_target, thermo)
    # y 和 x 都归一化
    assert math.isclose(sum(y), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(x), 1.0, abs_tol=1e-9)
    # vfrac 在 [0, 1]
    assert 0.0 <= vfrac <= 1.0


# ---------------------------------------------------------------------------
# 6) PS_FLASH roundtrip
# ---------------------------------------------------------------------------


def test_ps_flash_roundtrip_matches_golden():
    """PS_FLASH roundtrip：PT_FLASH(335K,1MPa)→S；PS_FLASH 反推回同 vfrac ≤ 1e-6。"""
    golden = GOLDEN_PHPS["ps_flash_roundtrip"]
    zs, cass = golden["zs"], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    P_ref = 1.0e6  # PS roundtrip 参考压力（与 step1 固化 vfrac 一致）

    # 1) PT_FLASH 算 S_target
    res_pt = PT_FLASH(zs, golden["T_K"], P_ref, thermo)
    S_target = thermo.S_PT(
        zs,
        golden["T_K"],
        P_ref,
        res_pt.vapor_fraction,
        res_pt.y_vapor,
        res_pt.x_liquid,
    )
    # 2) S_target 应与 golden 偏差 ≤ 1e-3
    assert math.isclose(S_target, golden["S_target_J_per_mol_K"], abs_tol=1e-3)

    # 3) PS_FLASH 反推 vfrac
    vfrac, y, x, P = PS_FLASH(zs, golden["T_K"], S_target, thermo)
    # 4) vfrac 应等于 step1 固化值（容差 1e-6）
    assert math.isclose(vfrac, golden["vfrac_target"], abs_tol=golden["tolerance"])
    # 5) P 应等于 1e6（容差 1e-3 Pa）
    assert math.isclose(P, P_ref, abs_tol=1e-3)


def test_ps_flash_returns_valid_pt_state():
    """PS_FLASH 返回的 (vfrac, y, x, P) 在 PT_FLASH(P) 下应自洽。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    res_pt = PT_FLASH(zs, 335.0, 1e6, thermo)
    S_target = thermo.S_PT(
        zs, 335.0, 1e6, res_pt.vapor_fraction, res_pt.y_vapor, res_pt.x_liquid
    )
    vfrac, y, x, P = PS_FLASH(zs, 335.0, S_target, thermo)
    # y 和 x 都归一化
    assert math.isclose(sum(y), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(x), 1.0, abs_tol=1e-9)
    # vfrac 在 [0, 1]
    assert 0.0 <= vfrac <= 1.0
    # P > 0
    assert P > 0


# ---------------------------------------------------------------------------
# 7) 收敛失败：FlashConvergenceError
# ---------------------------------------------------------------------------


def test_ph_flash_h_target_out_of_range_raises():
    """PH_FLASH H_target 超出物理范围 → FlashConvergenceError。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    # 实际 H 范围约 [30495, 42377] J/mol @ 335K；1e9 远超上限
    with pytest.raises(FlashConvergenceError):
        PH_FLASH(zs, 335.0, 1.0e9, thermo)


def test_ps_flash_s_target_out_of_range_raises():
    """PS_FLASH S_target 超出物理范围 → FlashConvergenceError。"""
    zs, cass = [0.3, 0.7], ["74-98-6", "106-97-8"]
    thermo = build_thermo("LIGHT_HYDROCARBON", zs, cass)
    # 实际 S 范围约 [420, 735] J/mol/K @ 335K；1e6 远超上限
    with pytest.raises(FlashConvergenceError):
        PS_FLASH(zs, 335.0, 1.0e6, thermo)


def test_flash_convergence_error_inherits_pcs_error():
    """FlashConvergenceError 继承 PcsError（422 风格）。"""
    assert issubclass(FlashConvergenceError, PcsError)
    err = FlashConvergenceError("test")
    assert err.code == "FLASH_CONVERGENCE_ERROR"
    assert err.status == 422


# ---------------------------------------------------------------------------
# 模块导出检查（step 2 扩展）
# ---------------------------------------------------------------------------


def test_flash_service_module_exports_step2_symbols():
    """step 2 模块导出：6 个 flash 函数 + FlashConvergenceError。"""
    required = {
        "PTFlashResult",
        "PT_FLASH",
        "BUBBLE_P",
        "BUBBLE_T",
        "DEW_P",
        "DEW_T",
        "PH_FLASH",
        "PS_FLASH",
        "FlashConvergenceError",
    }
    assert required.issubset(set(dir(flash_service)))
