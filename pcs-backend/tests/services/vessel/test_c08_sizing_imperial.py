"""P6-7 T4 C-08 两相分离器 sizing imperial_conversion 测试 (OPEN-P6-4-3 Path A)。

Path A 决议（用户 2026-10-31 裁决）：C-08 已从重量估算（vessel_weight_estimate_service，
已删除）改为 sizing 路径（two_phase_separator_sizing_service）。本测试验证
imperial_units=True 时 imperial_conversion 字段（dict）的双单位转换：

  - vmax_m_s → vmax_ft_s              （/0.3048）
  - csa_m2 → csa_ft2                  （/0.09290304）
  - nozzle_id_m → nozzle_id_in        （/0.0254）
  - control_height_m → control_height_ft （/0.3048）
  - residence_time_s → residence_time_min （/60）
  - density_kg_m3 → density_lb_ft3    （×0.062428）

3 算例：HORIZONTAL + VERTICAL + SPHERICAL。SI 与 imperial_expected 均来自
golden_c08_sizing_imperial.json（service 实测 baseline；工艺室 2026-11-15
前提供黄金值前用 service 输出作 baseline，rel ≤ 2e-2 容差冗余覆盖微调）。

关联：
  - 服务：app.services.vessel.two_phase_separator_sizing_service
    （P6-4 V1.2 重写后的正确服务名；非 vessel_weight_estimate_service）
  - 原始 fixture：tests/services/vessel/fixtures/golden_c08_imperial.json
    （保留为文档性参考，反映工艺室原始重量语义意图，本测试不动）
  - OPEN-P6-4-3：代码侧关闭（重新定义为"C-08 两相分离器 sizing imperial 闭环"）
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.vessel.two_phase_separator_sizing_service import (
    TwoPhaseSeparatorSizingInput,
    calc_two_phase_separator_sizing,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "golden_c08_sizing_imperial.json"
)


def _load_cases() -> list[dict]:
    """加载 golden_c08_sizing_imperial.json 3 算例。"""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["cases"]


def _build_input(si_inputs: dict) -> TwoPhaseSeparatorSizingInput:
    """把 fixture si_inputs 转为 TwoPhaseSeparatorSizingInput（frozen dataclass）。"""
    return TwoPhaseSeparatorSizingInput(**si_inputs)


def _assert_rel_close(
    actual: float, expected: float, tol_rel: float, label: str,
) -> None:
    """相对误差 ≤ tol_rel 的对照（expected=0 时跳过）。"""
    if expected == 0.0:
        return
    rel_err = abs(actual - expected) / abs(expected)
    assert rel_err <= tol_rel, (
        f"{label}: actual={actual:.6f} expected={expected:.6f} "
        f"rel_err={rel_err:.6f} tol={tol_rel}"
    )


# ============================================================================
# 主测试：3 算例 SI + imperial_conversion 字段验证（rel ≤ 2e-2 容差）
# ============================================================================


@pytest.mark.parametrize(
    "case",
    _load_cases(),
    ids=lambda c: c["case_id"],
)
def test_c08_sizing_si_and_imperial(case):
    """C-08 两相分离器 sizing SI + imperial_conversion 测试（OPEN-P6-4-3 Path A）。

    验证两步：
      1. SI 字段对照 si_expected（result 顶层属性）
      2. imperial_conversion dict 字段对照 imperial_expected（imperial_units=True
         时填充；非空则验证，None 则跳过）
    """
    si_inputs = case["si_inputs"]
    si_expected = case["si_expected"]
    imperial_expected = case["imperial_expected"]
    tol_rel = case["tolerance_rel"]

    inp = _build_input(si_inputs)
    # 验证 imperial_units=True 已传入（fixture 输入标记）
    assert inp.imperial_units is True, (
        f"{case['case_id']}: imperial_units 应为 True（fixture 保证）"
    )

    result = calc_two_phase_separator_sizing(inp)

    # 1) SI 字段验证（result 顶层属性）
    for key, expected_val in si_expected.items():
        actual_val = getattr(result, key)
        _assert_rel_close(actual_val, expected_val, tol_rel, f"SI {key}")

    # 2) imperial_conversion 字段验证（dict 形式）
    assert result.imperial_conversion is not None, (
        f"{case['case_id']}: imperial_units=True 但 imperial_conversion 为 None"
    )
    imp_actual = result.imperial_conversion
    # imperial_conversion 必有 8 字段（服务契约）
    expected_imp_keys = {
        "vmax_ft_s", "csa_min_ft2", "csa_actual_ft2",
        "nozzle_inlet_min_id_in", "nozzle_outlet_min_id_in",
        "control_height_ft", "residence_time_min", "rho_mix_lb_ft3",
    }
    assert set(imp_actual.keys()) == expected_imp_keys, (
        f"{case['case_id']}: imperial_conversion 键不匹配。缺失: "
        f"{expected_imp_keys - set(imp_actual.keys())}，多余: "
        f"{set(imp_actual.keys()) - expected_imp_keys}"
    )

    for key, expected_val in imperial_expected.items():
        actual_val = imp_actual.get(key)
        assert actual_val is not None, (
            f"{case['case_id']}: imperial_conversion 缺 {key}"
        )
        _assert_rel_close(actual_val, expected_val, tol_rel, f"imp {key}")


# ============================================================================
# 转换因子守恒校验（独立单元：3 算例必满足 SI × factor = imp）
# ============================================================================


@pytest.mark.parametrize(
    "case",
    _load_cases(),
    ids=lambda c: c["case_id"],
)
def test_c08_imperial_conversion_factor_consistency(case):
    """imperial_conversion 必须由 SI × 标准转换因子导出（rel ≤ 1e-6 严格）。

    物理因子（SI → Imperial）：
      - 速度 m/s → ft/s    ：× (1/0.3048)
      - 面积 m² → ft²       ：× (1/0.09290304)
      - 长度 m → in         ：× (1/0.0254)
      - 时间 s → min        ：× (1/60)
      - 密度 kg/m³ → lb/ft³ ：× 0.062428
    """
    inp = _build_input(case["si_inputs"])
    result = calc_two_phase_separator_sizing(inp)
    assert result.imperial_conversion is not None
    imp = result.imperial_conversion

    # 速度
    assert imp["vmax_ft_s"] == pytest.approx(result.vmax_m_s / 0.3048, rel=1e-6)
    # 面积
    assert imp["csa_min_ft2"] == pytest.approx(
        result.csa_min_m2 / 0.09290304, rel=1e-6,
    )
    assert imp["csa_actual_ft2"] == pytest.approx(
        result.csa_actual_m2 / 0.09290304, rel=1e-6,
    )
    # 长度（喷嘴 ID）
    assert imp["nozzle_inlet_min_id_in"] == pytest.approx(
        result.nozzle_inlet_min_id_m / 0.0254, rel=1e-6,
    )
    assert imp["nozzle_outlet_min_id_in"] == pytest.approx(
        result.nozzle_outlet_min_id_m / 0.0254, rel=1e-6,
    )
    # 控制高度
    assert imp["control_height_ft"] == pytest.approx(
        result.control_height_m / 0.3048, rel=1e-6,
    )
    # 时间
    assert imp["residence_time_min"] == pytest.approx(
        result.residence_time_s / 60.0, rel=1e-6,
    )
    # 密度
    assert imp["rho_mix_lb_ft3"] == pytest.approx(
        result.mixed_density_kg_m3 * 0.062428, rel=1e-6,
    )