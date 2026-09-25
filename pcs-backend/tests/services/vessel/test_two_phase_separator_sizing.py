"""P6-4 T2 C-08 两相分离器 sizing 单元测试（SPEC §3.4.2 V1.2）。

按 WS-CA-PR-010 Rev A 5 段计算验证：
  1. 油/水/气体积流量（bbl/d, MMscfd）
  2. 混合相密度（体积加权平均）
  3. Souders-Brown Vmax = K × √((ρL − ρV) / ρV)
  4. 气相 CSA 校核（最小 CSA 85% 利用率 vs 实际 π·D²/4）
  5. 喷嘴动量校核 + 仪表控制高度 + 停留时间

V1.2 关键约束（与 V1.0/V1.1 区别 — 严禁污染）：
  - 服务名：two_phase_separator_sizing_service（**非** vessel_weight_estimate_service）
  - 计算内容：5 段 sizing（**非**重量估算）
  - V1.2 新增字段：oil_sg / water_sg / gas_sg
  - 消费 T3 (C-12) calc_partial_volume 接口（dataclass 输入非 positional）
  - V1.0 污染禁止：不复用 heat/weight_estimate_service.py；不抽 WeightSegment；
    不加 vessel_results.weight_kg 列（见 D7 ADR-0040 / SPEC §3.4.2 V1.2）

5 黄金 fixture + 7 单元测试（fixture-driven + 边界 + 反推校验）。
强公式段（stage1~stage5）期望值相对误差 <0.1%；K 因子表插值段 <1%。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services.vessel.two_phase_separator_sizing_service import (
    TwoPhaseSeparatorSizingError,
    TwoPhaseSeparatorSizingInput,
    TwoPhaseSeparatorSizingResult,
    calc_two_phase_separator_sizing,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# 5 黄金 fixture（V1.2 P6-4 T2）
GOLDEN_FIXTURES = [
    FIXTURES_DIR / "golden_sizing_vertical.json",
    FIXTURES_DIR / "golden_sizing_horizontal.json",
    FIXTURES_DIR / "golden_sizing_horizontal_3phase.json",
    FIXTURES_DIR / "golden_sizing_spherical.json",
    FIXTURES_DIR / "golden_sizing_nozzle_momentum.json",
]


def _load_golden_cases() -> list[tuple[str, dict]]:
    """加载所有 5 黄金 fixture，返回 (fixture_name, case_dict) 列表。"""
    cases: list[tuple[str, dict]] = []
    for fixture_path in GOLDEN_FIXTURES:
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        for case in data["cases"]:
            cases.append((fixture_path.stem, case))
    return cases


def _case_to_input(c: dict) -> TwoPhaseSeparatorSizingInput:
    """把 fixture case dict 转为 TwoPhaseSeparatorSizingInput（frozen dataclass）。"""
    return TwoPhaseSeparatorSizingInput(
        vessel_shape=c["vessel_shape"],
        diameter_m=c["diameter_m"],
        length_m=c["length_m"],
        head_type=c["head_type"],
        operating_pressure_kpa=c["operating_pressure_kpa"],
        operating_temperature_c=c["operating_temperature_c"],
        oil_mass_rate_kg_d=c["oil_mass_rate_kg_d"],
        water_mass_rate_kg_d=c["water_mass_rate_kg_d"],
        gas_mass_rate_kg_d=c["gas_mass_rate_kg_d"],
        oil_density_kg_m3=c["oil_density_kg_m3"],
        water_density_kg_m3=c["water_density_kg_m3"],
        gas_density_kg_m3=c["gas_density_kg_m3"],
        oil_sg=c["oil_sg"],
        water_sg=c["water_sg"],
        gas_sg=c["gas_sg"],
        gas_mw_kg_kmol=c["gas_mw_kg_kmol"],
        k_factor=c["k_factor"],
        nozzle_inlet_momentum_limit_kg_m_s2=c["nozzle_inlet_momentum_limit_kg_m_s2"],
        nozzle_outlet_momentum_limit_kg_m_s2=c["nozzle_outlet_momentum_limit_kg_m_s2"],
        instrument_response_time_s=c["instrument_response_time_s"],
        n_vessels=c["n_vessels"],
    )


def _assert_close_pct(actual: float, expected: float, tol_pct: float, label: str) -> None:
    """相对误差 < tol_pct% 的浮点对照。"""
    if expected == 0.0:
        assert abs(actual) < 1e-9, f"{label}: actual={actual} expected=0"
        return
    rel_err = abs(actual - expected) / abs(expected) * 100.0
    assert rel_err < tol_pct, (
        f"{label}: actual={actual:.6f} expected={expected:.6f} "
        f"rel_err={rel_err:.4f}% tol={tol_pct}%"
    )


# ============================================================================
# 1. 5 黄金 fixture（V1.2 完全重写）— 覆盖立式/卧式单相/卧式三相/球罐/喷嘴动量
# ============================================================================


@pytest.mark.parametrize(
    "fixture_name,case",
    _load_golden_cases(),
    ids=lambda x: x["id"] if isinstance(x, dict) else x,
)
def test_golden_two_phase_separator_sizing(fixture_name, case):
    """5 黄金 fixture 全字段对照（强公式段 <0.1%）。

    覆盖：
      - golden_sizing_vertical：VERTICAL 单相气液 + 2:1_ELLIPTICAL 封头
      - golden_sizing_horizontal：HORIZONTAL 单相气液 + HEMISPHERICAL 封头
      - golden_sizing_horizontal_3phase：HORIZONTAL 三相（油+水+气）
      - golden_sizing_spherical：SPHERICAL 球罐（length=0 + HEMISPHERICAL）
      - golden_sizing_nozzle_momentum：喷嘴动量边界（小动量限值 → 较大 ID）
    """
    inp = _case_to_input(case)
    result = calc_two_phase_separator_sizing(inp)
    exp = case["expected"]
    tol = exp["tol_pct"]

    # Stage 1 体积流量
    _assert_close_pct(result.oil_vol_rate_bbl_d, exp["oil_vol_rate_bbl_d"], tol, "oil_bbl")
    _assert_close_pct(result.water_vol_rate_bbl_d, exp["water_vol_rate_bbl_d"], tol, "water_bbl")
    _assert_close_pct(result.gas_vol_rate_mmscfd, exp["gas_vol_rate_mmscfd"], tol, "gas_mmscfd")

    # Stage 2 混合相密度
    _assert_close_pct(result.mixed_density_kg_m3, exp["mixed_density_kg_m3"], tol, "rho_mix")

    # Stage 3 Souders-Brown Vmax
    _assert_close_pct(result.vmax_m_s, exp["vmax_m_s"], tol, "vmax")

    # Stage 4 CSA 校核
    _assert_close_pct(result.csa_min_m2, exp["csa_min_m2"], tol, "csa_min")
    _assert_close_pct(result.csa_actual_m2, exp["csa_actual_m2"], tol, "csa_actual")

    # Stage 5a 喷嘴动量
    _assert_close_pct(result.nozzle_inlet_min_id_m, exp["nozzle_inlet_min_id_m"], tol, "ID_in")
    _assert_close_pct(result.nozzle_outlet_min_id_m, exp["nozzle_outlet_min_id_m"], tol, "ID_out")

    # Stage 5b 仪表控制高度 + 5c 控制体积
    _assert_close_pct(result.control_height_m, exp["control_height_m"], tol, "control_height_m")
    _assert_close_pct(result.control_volume_m3, exp["control_volume_m3"], tol, "control_volume_m3")

    # Stage 5d 停留时间
    _assert_close_pct(result.residence_time_s, exp["residence_time_s"], tol, "residence_time_s")

    # formula_ref 必含 T3 几何 + WS-CA-PR-010 sizing 两部分（合并而非覆盖）
    assert isinstance(result.formula_ref, dict)
    # T3 几何公式键（calc_partial_volume 必有：head / cylinder / total）
    t3_keys = {"head", "cylinder", "total"}
    assert t3_keys.issubset(result.formula_ref.keys()), (
        f"{case['id']} T3 几何 formula_ref 缺失: "
        f"{t3_keys - set(result.formula_ref.keys())}"
    )
    # WS-CA-PR-010 sizing 公式键（T2 自身）
    sizing_keys = {
        "stage1_volumetric", "stage2_mixed_density", "stage3_souders_brown",
        "stage4_csa", "stage5_nozzle", "stage5_control", "stage5_residence",
        "ws_ca_pr_010_sizing",
    }
    assert sizing_keys.issubset(result.formula_ref.keys()), (
        f"{case['id']} sizing formula_ref 缺失: "
        f"{sizing_keys - set(result.formula_ref.keys())}"
    )


# ============================================================================
# 2. 喷嘴动量越界：小动量限值 → 较大喷嘴 ID（与 fixture 数值校验）
# ============================================================================


def test_nozzle_momentum_inverse_relation():
    """入口动量限值 N_inlet 越小 → 入口喷嘴 ID 越大（ID = √(4m²/(π·N·ρ_mix))）。

    物理意义：动量 F = m·v 限值越紧（越小），需要的流通面积越大 → ID 越大。
    """
    base_kwargs = dict(
        vessel_shape="HORIZONTAL",
        diameter_m=1.5,
        length_m=4.0,
        head_type="2:1_ELLIPTICAL",
        operating_pressure_kpa=400.0,
        operating_temperature_c=55.0,
        oil_mass_rate_kg_d=80000.0,
        water_mass_rate_kg_d=0.0,
        gas_mass_rate_kg_d=60000.0,
        oil_density_kg_m3=850.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=15.0,
        oil_sg=0.8509,
        water_sg=1.0,
        gas_sg=12.2449,
        gas_mw_kg_kmol=22.0,
        k_factor=0.07,
        instrument_response_time_s=25.0,
        n_vessels=1,
    )

    # 大动量限值（500 N·s）→ 小 ID
    inp_loose = TwoPhaseSeparatorSizingInput(
        **base_kwargs,
        nozzle_inlet_momentum_limit_kg_m_s2=500.0,
        nozzle_outlet_momentum_limit_kg_m_s2=500.0,
    )
    # 小动量限值（50 N·s）→ 大 ID（缩小 10x → ID 放大约 √10≈3.16 倍）
    inp_tight = TwoPhaseSeparatorSizingInput(
        **base_kwargs,
        nozzle_inlet_momentum_limit_kg_m_s2=50.0,
        nozzle_outlet_momentum_limit_kg_m_s2=30.0,
    )

    r_loose = calc_two_phase_separator_sizing(inp_loose)
    r_tight = calc_two_phase_separator_sizing(inp_tight)

    # 入口限值 500 → 50（缩小 10×）→ ID 放大 √10 ≈ 3.162 倍
    ratio_inlet = r_tight.nozzle_inlet_min_id_m / r_loose.nozzle_inlet_min_id_m
    assert math.isclose(ratio_inlet, math.sqrt(10.0), rel_tol=0.01), (
        f"入口 ID 比例: {ratio_inlet:.4f} 期望 √10≈3.162"
    )

    # 出口限值 500 → 30（缩小 ~16.67×）→ ID 放大 √16.67 ≈ 4.083 倍
    ratio_outlet = r_tight.nozzle_outlet_min_id_m / r_loose.nozzle_outlet_min_id_m
    assert math.isclose(ratio_outlet, math.sqrt(500.0 / 30.0), rel_tol=0.01), (
        f"出口 ID 比例: {ratio_outlet:.4f} 期望 √(500/30)≈4.083"
    )

    # 喷嘴 ID 必须 > 0（不能为负或 0）
    assert r_tight.nozzle_inlet_min_id_m > 0
    assert r_tight.nozzle_outlet_min_id_m > 0


# ============================================================================
# 3. 停留时间边界（极端小流量 → 大停留时间）
# ============================================================================


def test_residence_time_extreme_low_flow():
    """极小质量流量 → 大停留时间（边界检验）。

    Q_total = 1 kg/d → residence_time 应 > 1000 s（V_per_vessel ~0.01 m³ / Q ~1e-5 m³/s）。
    """
    inp = TwoPhaseSeparatorSizingInput(
        vessel_shape="VERTICAL",
        diameter_m=0.5,
        length_m=1.0,
        head_type="FLAT",
        operating_pressure_kpa=200.0,
        operating_temperature_c=40.0,
        # 极小流量
        oil_mass_rate_kg_d=1.0,
        water_mass_rate_kg_d=0.0,
        gas_mass_rate_kg_d=1.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=10.0,
        oil_sg=0.8008,
        water_sg=1.0,
        gas_sg=8.1633,
        gas_mw_kg_kmol=18.0,
        k_factor=0.10,
        nozzle_inlet_momentum_limit_kg_m_s2=100.0,
        nozzle_outlet_momentum_limit_kg_m_s2=50.0,
        instrument_response_time_s=30.0,
        n_vessels=1,
    )
    result = calc_two_phase_separator_sizing(inp)
    # 极小流量 → 停留时间应 > 1000 s
    assert result.residence_time_s > 1000.0, (
        f"residence_time_s={result.residence_time_s:.1f} 应 > 1000 s（极小流量）"
    )
    # V_per_vessel 仍为有限正值（calc_partial_volume 正常输出）
    assert result.control_volume_m3 > 0


def test_residence_time_decreases_with_higher_flow():
    """停留时间随流量增大而单调减小（V 固定 → t ∝ 1/Q）。"""
    base_kwargs = dict(
        vessel_shape="VERTICAL",
        diameter_m=1.0,
        length_m=2.0,
        head_type="2:1_ELLIPTICAL",
        operating_pressure_kpa=300.0,
        operating_temperature_c=50.0,
        oil_density_kg_m3=850.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=10.0,
        oil_sg=0.8509,
        water_sg=1.0,
        gas_sg=8.1633,
        gas_mw_kg_kmol=18.0,
        k_factor=0.10,
        nozzle_inlet_momentum_limit_kg_m_s2=200.0,
        nozzle_outlet_momentum_limit_kg_m_s2=100.0,
        instrument_response_time_s=30.0,
        n_vessels=1,
    )

    inp_low = TwoPhaseSeparatorSizingInput(
        **base_kwargs,
        oil_mass_rate_kg_d=10000.0,
        water_mass_rate_kg_d=0.0,
        gas_mass_rate_kg_d=10000.0,
    )
    inp_high = TwoPhaseSeparatorSizingInput(
        **base_kwargs,
        oil_mass_rate_kg_d=100000.0,
        water_mass_rate_kg_d=0.0,
        gas_mass_rate_kg_d=100000.0,
    )
    r_low = calc_two_phase_separator_sizing(inp_low)
    r_high = calc_two_phase_separator_sizing(inp_high)
    # 流量 10× → 停留时间 0.1×
    assert r_low.residence_time_s > r_high.residence_time_s, (
        f"低流量停留 {r_low.residence_time_s:.1f} 应 > 高流量停留 {r_high.residence_time_s:.1f}"
    )
    ratio = r_low.residence_time_s / r_high.residence_time_s
    assert math.isclose(ratio, 10.0, rel_tol=0.01), (
        f"停留时间比 {ratio:.4f} 期望 ≈10.0（流量 10×）"
    )


# ============================================================================
# 4. SG 反推一致性校验（V1.2 新增）
# ============================================================================


def test_sg_consistency_validation_rejects_mismatch():
    """SG 与 density 反推不一致（>1%）应抛 TwoPhaseSeparatorSizingError。

    V1.2 SPEC §3.4.2 反推公式：
      oil_sg = oil_density_kg_m3 / 999.0
      water_sg 同
      gas_sg = gas_density_kg_m3 / 1.225
    """
    base_kwargs = dict(
        vessel_shape="VERTICAL",
        diameter_m=1.0,
        length_m=2.0,
        head_type="2:1_ELLIPTICAL",
        operating_pressure_kpa=300.0,
        operating_temperature_c=50.0,
        oil_mass_rate_kg_d=10000.0,
        water_mass_rate_kg_d=0.0,
        gas_mass_rate_kg_d=10000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=10.0,
        oil_sg=0.8008,
        water_sg=1.0,
        gas_mw_kg_kmol=18.0,
        k_factor=0.10,
        nozzle_inlet_momentum_limit_kg_m_s2=200.0,
        nozzle_outlet_momentum_limit_kg_m_s2=100.0,
        instrument_response_time_s=30.0,
        n_vessels=1,
    )
    # 故意把 gas_sg 改成与 density 反推不符（density=10 → sg=8.16；这里填 5.0）
    inp_bad = TwoPhaseSeparatorSizingInput(
        **base_kwargs,
        gas_sg=5.0,
    )
    with pytest.raises(TwoPhaseSeparatorSizingError) as exc_info:
        calc_two_phase_separator_sizing(inp_bad)
    assert "gas_sg" in str(exc_info.value)


def test_sg_consistency_validation_passes_within_tolerance():
    """SG 与 density 反推在 1% 容差内应通过校验。"""
    inp = TwoPhaseSeparatorSizingInput(
        vessel_shape="VERTICAL",
        diameter_m=1.0,
        length_m=2.0,
        head_type="2:1_ELLIPTICAL",
        operating_pressure_kpa=300.0,
        operating_temperature_c=50.0,
        oil_mass_rate_kg_d=10000.0,
        water_mass_rate_kg_d=0.0,
        gas_mass_rate_kg_d=10000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=10.0,
        # SG 略偏离（0.5% 误差，在 1% 容差内）
        oil_sg=0.8008 * 1.005,
        water_sg=1.0 * 1.005,
        gas_sg=8.1633 * 1.005,
        gas_mw_kg_kmol=18.0,
        k_factor=0.10,
        nozzle_inlet_momentum_limit_kg_m_s2=200.0,
        nozzle_outlet_momentum_limit_kg_m_s2=100.0,
        instrument_response_time_s=30.0,
        n_vessels=1,
    )
    result = calc_two_phase_separator_sizing(inp)
    assert result.vmax_m_s > 0


# ============================================================================
# 5. 物理量边界异常
# ============================================================================


def test_negative_diameter_raises():
    """diameter_m ≤ 0 应抛 TwoPhaseSeparatorSizingError。"""
    with pytest.raises(TwoPhaseSeparatorSizingError) as exc_info:
        calc_two_phase_separator_sizing(TwoPhaseSeparatorSizingInput(
            vessel_shape="VERTICAL",
            diameter_m=-1.0,
            length_m=2.0,
            head_type="2:1_ELLIPTICAL",
            operating_pressure_kpa=300.0,
            operating_temperature_c=50.0,
            oil_mass_rate_kg_d=10000.0,
            water_mass_rate_kg_d=0.0,
            gas_mass_rate_kg_d=10000.0,
            oil_density_kg_m3=800.0,
            water_density_kg_m3=1000.0,
            gas_density_kg_m3=10.0,
            oil_sg=0.8008,
            water_sg=1.0,
            gas_sg=8.1633,
            gas_mw_kg_kmol=18.0,
            k_factor=0.10,
            nozzle_inlet_momentum_limit_kg_m_s2=200.0,
            nozzle_outlet_momentum_limit_kg_m_s2=100.0,
            instrument_response_time_s=30.0,
            n_vessels=1,
        ))
    assert "diameter" in str(exc_info.value).lower()


def test_oil_density_less_than_gas_density_raises():
    """ρ_oil < ρ_gas 物理不合理（液相比气相轻不可能），应抛 TwoPhaseSeparatorSizingError。"""
    with pytest.raises(TwoPhaseSeparatorSizingError) as exc_info:
        calc_two_phase_separator_sizing(TwoPhaseSeparatorSizingInput(
            vessel_shape="VERTICAL",
            diameter_m=1.0,
            length_m=2.0,
            head_type="2:1_ELLIPTICAL",
            operating_pressure_kpa=300.0,
            operating_temperature_c=50.0,
            oil_mass_rate_kg_d=10000.0,
            water_mass_rate_kg_d=0.0,
            gas_mass_rate_kg_d=10000.0,
            # 倒置：oil 5 < gas 10
            oil_density_kg_m3=5.0,
            water_density_kg_m3=1000.0,
            gas_density_kg_m3=10.0,
            oil_sg=5.0 / 999.0,
            water_sg=1.0,
            gas_sg=8.1633,
            gas_mw_kg_kmol=18.0,
            k_factor=0.10,
            nozzle_inlet_momentum_limit_kg_m_s2=200.0,
            nozzle_outlet_momentum_limit_kg_m_s2=100.0,
            instrument_response_time_s=30.0,
            n_vessels=1,
        ))
    msg = str(exc_info.value).lower()
    assert "ρ_oil" in str(exc_info.value) or "oil_density" in msg


def test_k_factor_out_of_range_raises():
    """K 因子 < 0.01 或 > 1.0 应抛 TwoPhaseSeparatorSizingError。"""
    with pytest.raises(TwoPhaseSeparatorSizingError):
        calc_two_phase_separator_sizing(TwoPhaseSeparatorSizingInput(
            vessel_shape="VERTICAL",
            diameter_m=1.0,
            length_m=2.0,
            head_type="2:1_ELLIPTICAL",
            operating_pressure_kpa=300.0,
            operating_temperature_c=50.0,
            oil_mass_rate_kg_d=10000.0,
            water_mass_rate_kg_d=0.0,
            gas_mass_rate_kg_d=10000.0,
            oil_density_kg_m3=800.0,
            water_density_kg_m3=1000.0,
            gas_density_kg_m3=10.0,
            oil_sg=0.8008,
            water_sg=1.0,
            gas_sg=8.1633,
            gas_mw_kg_kmol=18.0,
            k_factor=2.0,  # 远超 1.0 上界
            nozzle_inlet_momentum_limit_kg_m_s2=200.0,
            nozzle_outlet_momentum_limit_kg_m_s2=100.0,
            instrument_response_time_s=30.0,
            n_vessels=1,
        ))


# ============================================================================
# 6. T3 calc_partial_volume 衔接（V1.2 关键约束）
# ============================================================================


def test_calc_partial_volume_integration_via_formula_ref():
    """T3 calc_partial_volume formula_ref 必须出现在 result.formula_ref（不覆盖）。

    V1.2 SPEC §3.4.2 + D7 ADR-0040：T2 必须复用 T3 calc_partial_volume 接口；
    formula_ref 应合并 T3 几何公式 + T2 sizing 公式（合并而非覆盖）。
    """
    inp = TwoPhaseSeparatorSizingInput(
        vessel_shape="HORIZONTAL",
        diameter_m=2.0,
        length_m=6.0,
        head_type="HEMISPHERICAL",
        operating_pressure_kpa=600.0,
        operating_temperature_c=70.0,
        oil_mass_rate_kg_d=100000.0,
        water_mass_rate_kg_d=0.0,
        gas_mass_rate_kg_d=80000.0,
        oil_density_kg_m3=850.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=12.0,
        oil_sg=0.8509,
        water_sg=1.0,
        gas_sg=9.7959,
        gas_mw_kg_kmol=19.5,
        k_factor=0.08,
        nozzle_inlet_momentum_limit_kg_m_s2=150.0,
        nozzle_outlet_momentum_limit_kg_m_s2=80.0,
        instrument_response_time_s=60.0,
        n_vessels=1,
    )
    result = calc_two_phase_separator_sizing(inp)

    # formula_ref 包含 T3 几何公式（calc_partial_volume 输出：head / cylinder / total）
    t3_keys = {"head", "cylinder", "total"}
    assert t3_keys.issubset(result.formula_ref.keys())

    # 包含 T2 sizing 公式（WS-CA-PR-010）
    sizing_keys = {"stage3_souders_brown", "stage4_csa", "stage5_nozzle", "ws_ca_pr_010_sizing"}
    assert sizing_keys.issubset(result.formula_ref.keys())

    # 控制体积 > 0（calc_partial_volume 正常输出）
    assert result.control_volume_m3 > 0
    # 停留时间 > 0
    assert result.residence_time_s > 0


# ============================================================================
# 7. 数据类契约（frozen + 字段完整性）
# ============================================================================


def test_result_is_frozen_dataclass_with_15_fields():
    """TwoPhaseSeparatorSizingResult 必须是 frozen dataclass。

    14 字段：12 数值 + imperial_conversion + formula_ref。
    """
    from dataclasses import FrozenInstanceError, fields

    field_names = {f.name for f in fields(TwoPhaseSeparatorSizingResult)}
    expected = {
        "oil_vol_rate_bbl_d",
        "water_vol_rate_bbl_d",
        "gas_vol_rate_mmscfd",
        "mixed_density_kg_m3",
        "vmax_m_s",
        "csa_min_m2",
        "csa_actual_m2",
        "nozzle_inlet_min_id_m",
        "nozzle_outlet_min_id_m",
        "control_height_m",
        "control_volume_m3",
        "residence_time_s",
        "imperial_conversion",
        "formula_ref",
    }
    assert field_names == expected, (
        f"TwoPhaseSeparatorSizingResult 字段不匹配。缺失: {expected - field_names}，"
        f"多余: {field_names - expected}"
    )

    # 不可变
    result = calc_two_phase_separator_sizing(TwoPhaseSeparatorSizingInput(
        vessel_shape="VERTICAL",
        diameter_m=1.0,
        length_m=2.0,
        head_type="2:1_ELLIPTICAL",
        operating_pressure_kpa=300.0,
        operating_temperature_c=50.0,
        oil_mass_rate_kg_d=10000.0,
        water_mass_rate_kg_d=0.0,
        gas_mass_rate_kg_d=10000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=10.0,
        oil_sg=0.8008,
        water_sg=1.0,
        gas_sg=8.1633,
        gas_mw_kg_kmol=18.0,
        k_factor=0.10,
        nozzle_inlet_momentum_limit_kg_m_s2=200.0,
        nozzle_outlet_momentum_limit_kg_m_s2=100.0,
        instrument_response_time_s=30.0,
        n_vessels=1,
    ))
    with pytest.raises(FrozenInstanceError):
        result.vmax_m_s = 999.0  # type: ignore[misc]


def test_imperial_units_population():
    """imperial_units=True 时 imperial_conversion 字段应填充（双单位转换）。"""
    inp = TwoPhaseSeparatorSizingInput(
        vessel_shape="VERTICAL",
        diameter_m=1.0,
        length_m=2.0,
        head_type="2:1_ELLIPTICAL",
        operating_pressure_kpa=300.0,
        operating_temperature_c=50.0,
        oil_mass_rate_kg_d=10000.0,
        water_mass_rate_kg_d=0.0,
        gas_mass_rate_kg_d=10000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=10.0,
        oil_sg=0.8008,
        water_sg=1.0,
        gas_sg=8.1633,
        gas_mw_kg_kmol=18.0,
        k_factor=0.10,
        nozzle_inlet_momentum_limit_kg_m_s2=200.0,
        nozzle_outlet_momentum_limit_kg_m_s2=100.0,
        instrument_response_time_s=30.0,
        n_vessels=1,
        imperial_units=True,
    )
    result = calc_two_phase_separator_sizing(inp)
    assert result.imperial_conversion is not None
    # 8 个键：vmax_ft_s, csa_min_ft2, csa_actual_ft2, nozzle_inlet_min_id_in,
    # nozzle_outlet_min_id_in, control_height_ft, residence_time_min, rho_mix_lb_ft3
    expected_keys = {
        "vmax_ft_s", "csa_min_ft2", "csa_actual_ft2",
        "nozzle_inlet_min_id_in", "nozzle_outlet_min_id_in",
        "control_height_ft", "residence_time_min", "rho_mix_lb_ft3",
    }
    assert set(result.imperial_conversion.keys()) == expected_keys
    # vmax_ft_s 应 ≈ vmax_m_s / 0.3048
    assert math.isclose(
        result.imperial_conversion["vmax_ft_s"],
        result.vmax_m_s / 0.3048,
        rel_tol=1e-6,
    )