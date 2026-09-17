"""换热器重量估算 service 测试（P5-4-4 / Task 22）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md V1.8 §Task 22：
- 5 段壳体拆分（cylinder + heads + flanges + nozzles + saddles）
- TEMA 9th + ASME VIII-1 + ASME B16.5 + NB/T 47065 公式参考
- tube / baffle / channels 独立计算
- total = shell_total + tube + baffle + channels
- formula_ref 字段断言
- BEM 固定管板 + AEM U 型管 2 算例（与 golden JSON 偏差 ≤10%）
- 材质密度切换（carbon_steel 7850 vs SS304 8000）

**Do-Not-Repeat**（plan V1.8 F-13-2 决策）：fluids/chemicals **完全无对应函数**，
本 task 全部自研；不引 ChEDL 包装层。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.heat.weight_estimate_service import (
    WeightEstimateInput,
    estimate_weight,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_golden(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


# ===== cylinder 几何精确（直接验证公式）=====


def test_cylinder_geometry_exact():
    """cylinder = π·D·L·t·ρ（薄壁圆筒展开），与手算一致 ±1%。"""
    inp = WeightEstimateInput(
        tema_type="BEM",
        shell_id_m=1.0,
        shell_length_m=5.0,
        shell_thickness_m=0.012,
        material="carbon_steel",
        # 其余默认（无 tube/baffle）
    )
    result = estimate_weight(inp)
    expected = 3.14159265 * 1.0 * 5.0 * 0.012 * 7850.0  # = 1479.7
    assert result.shell_cylinder.weight_kg == pytest.approx(expected, rel=0.01)


# ===== BEM 固定管板算例（与 golden JSON 比对）=====


def test_bem_golden_weight_match():
    """BEM 算例：service 输出与 golden_weight_bem.json ground truth 一致。"""
    golden = _load_golden("golden_weight_bem.json")
    inp = WeightEstimateInput(**golden["input"])
    result = estimate_weight(inp)

    # cylinder 几何精确（plan V1.0 强调 ±1%）
    assert result.shell_cylinder.weight_kg == pytest.approx(
        golden["expected_weights_kg"]["shell_cylinder"], rel=0.01
    )
    # total 偏差 ≤10%（vs 商业软件 / plan V1.0 估算）
    assert result.total.weight_kg == pytest.approx(
        golden["expected_weights_kg"]["total"], rel=0.10
    )


def test_bem_formula_ref_present():
    """BEM 算例 formula_ref 字段标注完整（5 段壳体各自来源 + 顶层 TEMA 版本）。"""
    golden = _load_golden("golden_weight_bem.json")
    inp = WeightEstimateInput(**golden["input"])
    result = estimate_weight(inp)

    # 5 段壳体各自 formula_ref 非空 + 标注标准
    assert "ASME" in result.shell_heads.formula_ref
    assert "B16.5" in result.shell_flanges.formula_ref
    assert "B16.9" in result.shell_nozzles.formula_ref
    assert "NB/T 47065" in result.shell_saddles.formula_ref
    assert "几何" in result.shell_cylinder.formula_ref

    # 顶层 formula_ref
    assert result.formula_ref["tema_version"] == "TEMA 9th Ed."
    assert "cylinder" in result.formula_ref
    assert "heads" in result.formula_ref


def test_bem_shell_total_equals_sum_of_5_segments():
    """shell_total_weight_kg = 5 段壳体分量累加。"""
    golden = _load_golden("golden_weight_bem.json")
    inp = WeightEstimateInput(**golden["input"])
    result = estimate_weight(inp)

    sum5 = (
        result.shell_cylinder.weight_kg
        + result.shell_heads.weight_kg
        + result.shell_flanges.weight_kg
        + result.shell_nozzles.weight_kg
        + result.shell_saddles.weight_kg
    )
    assert result.shell_total.weight_kg == pytest.approx(sum5, rel=1e-9)


def test_bem_total_equals_shell_plus_tube_baffle_channels():
    """total_weight_kg = shell_total + tube + baffle + channels。"""
    golden = _load_golden("golden_weight_bem.json")
    inp = WeightEstimateInput(**golden["input"])
    result = estimate_weight(inp)

    expected = (
        result.shell_total.weight_kg
        + result.tube.weight_kg
        + result.baffle.weight_kg
        + result.channels.weight_kg
    )
    assert result.total.weight_kg == pytest.approx(expected, rel=1e-9)


# ===== AEM U 型管算例（baffle/channels = 0）=====


def test_aem_golden_weight_match():
    """AEM U 型管算例：baffle=0, channels=0（无折流板/管箱）。"""
    golden = _load_golden("golden_weight_aem.json")
    inp = WeightEstimateInput(**golden["input"])
    result = estimate_weight(inp)

    # baffle / channels = 0
    assert result.baffle.weight_kg == 0.0
    assert result.channels.weight_kg == 0.0
    # total 偏差 ≤10%
    assert result.total.weight_kg == pytest.approx(
        golden["expected_weights_kg"]["total"], rel=0.10
    )


# ===== 材质密度切换 =====


def test_material_density_carbon_vs_ss304():
    """碳钢 7850 vs SS304 8000：cylinder 比例应约 8000/7850 ≈ 1.019。"""
    base = {
        "tema_type": "BEM",
        "shell_id_m": 1.0,
        "shell_length_m": 5.0,
        "shell_thickness_m": 0.012,
    }
    carbon = estimate_weight(WeightEstimateInput(**base, material="carbon_steel"))
    ss304 = estimate_weight(WeightEstimateInput(**base, material="SS304"))

    ratio = ss304.shell_cylinder.weight_kg / carbon.shell_cylinder.weight_kg
    assert ratio == pytest.approx(8000.0 / 7850.0, rel=1e-6)


# ===== 边界：零参数 =====


def test_zero_tube_baffle_yields_zero():
    """tube_count=0 / baffle_count=0 时对应段 weight=0（不抛错）。"""
    inp = WeightEstimateInput(
        tema_type="BEM",
        shell_id_m=1.0,
        shell_length_m=5.0,
        shell_thickness_m=0.012,
        tube_count=0,
        baffle_count=0,
    )
    result = estimate_weight(inp)
    assert result.tube.weight_kg == 0.0
    assert result.baffle.weight_kg == 0.0
    # channels 仍按 BEM 有
    assert result.channels.weight_kg > 0.0
