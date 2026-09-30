"""热虹吸循环安装高度 service 测试（P5-0-1b T1 / SUP-010 §3.5）。

按 SUP-010 §3.5 + GPSA §20.4 壳程压力平衡：

覆盖 4 类：
- **XLS 独立复算**：`pipe_friction_head_m` 对 XLS 入口参数复算，与 XLS P11
  = 1.1074 m 比对（5 位有效数字一致）——公式结构与单位基准的溯源锚点
- **golden 3 算例**（低 / 中 / 高流量）：与 golden_thermosiphon_circulation.json
  比对，浮点 math.isclose(rel_tol=0.01)
- **边界**：最小流量 / 零阻力梯度 / 负温度 / 密度倒置 / 无解分母
- **异常**：输入非法 → ThermosiphonCirculationError（code THERMOSIPHON_INPUT_ERROR）
- **dataclass contract**：ThermosiphonCirculationInput / Result 均 frozen=True

**Do-Not-Repeat**（P5-0-1b T1 2026-09-30）：fixture 是 **PARTIAL**（`_meta.status`），
数值分两级，结构化标注在 `_meta.ground_truth_status` + 逐 case `provenance` / `status`：

- `xls_verified` 段（status = `xls_verified`）是 XLS 原始值（SUP-010 §3.5 转录），
  已由 `pipe_friction_head_m` 独立复算验证（1.10732 vs 1.1074 m，5 位有效数字一致）
  —— **可直接作 XLS 对账依据**。
- `cases[]`（status = `pending_xls`）的 Hx / Hxo 是本仓 service 依 XLS 公式结构生成的
  **回归锁定值，不是 XLS 原始输出**；出口 / 壳程阻力项与两相流密度为工程占位值
  —— **禁止用作 XLS 对账依据**。

这些值仍然参与断言，因为它们锁的是**公式行为**（流量↑ → Hx↑、Hxo = 1.5·Hx、
推动力比 > 1 等），换成 XLS 真值后行为不变、断言继续有效。
XLS 授权恢复后需整体替换 cases[] 并把 `_meta.status` 改回 verified。
"""
from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path

import pytest

from app.services.exceptions import PcsError
from app.services.heat.thermosiphon_service import (
    ThermosiphonCirculationError,
    ThermosiphonCirculationInput,
    ThermosiphonCirculationResult,
    calc_thermosiphon_circulation,
    pipe_friction_head_m,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN = json.loads(
    (FIXTURES_DIR / "golden_thermosiphon_circulation.json").read_text(encoding="utf-8")
)
_TOL = GOLDEN["_meta"]["deviation_tolerance_rel"]


def _case(name: str) -> dict:
    for c in GOLDEN["cases"]:
        if c["name"] == name:
            return c
    raise KeyError(name)


def _base_input(**overrides) -> ThermosiphonCirculationInput:
    """以 med_flow 算例为基线，覆盖单字段做边界测试。"""
    return ThermosiphonCirculationInput(
        **{**_case("med_flow")["input"], **overrides}
    )


# =============================================================================
# XLS 独立复算（公式溯源锚点）
# =============================================================================


def test_inlet_p11_matches_xls_source():
    """XLS 入口参数复算 P11 与 XLS 值 1.1074 m 一致（rel 1%）。

    这是本 service 唯一的 XLS 原始数值锚点：确认 P11 = f·(L/D)·v²/(2g)
    （m 液柱 / Darcy / g=9.81）公式结构与单位基准正确。
    """
    line = GOLDEN["xls_verified"]["inlet_line"]
    computed = pipe_friction_head_m(
        friction_factor=line["friction_factor"],
        equivalent_length_m=line["equivalent_length_m"],
        inner_diameter_m=line["inner_diam_m"],
        velocity_m_per_s=line["velocity_m_per_s"],
    )
    expected = GOLDEN["xls_verified"]["expected_pressure_drop_const_m"]
    assert math.isclose(computed, expected, rel_tol=0.01)
    # fixture 自记录的复算值与本次运行一致（幂等）
    assert math.isclose(
        computed,
        GOLDEN["xls_verified"]["computed_pressure_drop_const_m"],
        rel_tol=1e-9,
    )


# =============================================================================
# golden 3 算例（低 / 中 / 高流量）
# =============================================================================


@pytest.mark.parametrize("name", ["low_flow", "med_flow", "high_flow"])
def test_golden_balance_matches_fixture(name: str):
    """3 算例：service 输出与 golden fixture 比对（rel_tol 1%）。"""
    case = _case(name)
    result = calc_thermosiphon_circulation(
        ThermosiphonCirculationInput(**case["input"])
    )
    expected = case["expected"]
    assert math.isclose(
        result.installation_height_calc_m,
        expected["installation_height_calc_m"],
        rel_tol=_TOL,
    )
    assert math.isclose(
        result.installation_height_final_m,
        expected["installation_height_final_m"],
        rel_tol=_TOL,
    )
    assert math.isclose(
        result.circulation_drive_ratio,
        expected["circulation_drive_ratio"],
        rel_tol=_TOL,
    )
    assert result.check_result == expected["check_result"]


def test_golden_final_height_applies_safety_factor():
    """Hxo = safety_factor · Hx（SUP-010 §3.5 default 1.5）。"""
    case = _case("med_flow")
    result = calc_thermosiphon_circulation(
        ThermosiphonCirculationInput(**case["input"])
    )
    assert math.isclose(
        result.installation_height_final_m,
        result.installation_height_calc_m * case["input"]["safety_factor"],
        rel_tol=1e-9,
    )


def test_height_monotonic_with_flow():
    """流量升高 → 入口摩阻 ∝ W → Hx 单调升高（物理合理性）。"""
    heights = [
        calc_thermosiphon_circulation(
            ThermosiphonCirculationInput(**_case(n)["input"])
        ).installation_height_calc_m
        for n in ("low_flow", "med_flow", "high_flow")
    ]
    assert heights[0] < heights[1] < heights[2]


def test_formula_ref_carries_xls_provenance():
    """formula_ref 溯源到 XLS + GPSA §20.4（service 层承载，不入 DDL）。"""
    result = calc_thermosiphon_circulation(_base_input())
    assert result.formula_ref.standard == "GPSA"
    assert "132汽包安装高度计算" in result.formula_ref.source


# =============================================================================
# fixture ground-truth 契约（防 derived 段被误当 XLS 对账依据）
# =============================================================================


def test_fixture_declares_partial_ground_truth_status():
    """fixture 顶层必须声明 PARTIAL + 结构化 ground_truth_status 三段。

    XLS 6 sheet 尚未提取（权限受阻），cases[] 是 derived 回归锁定值。
    本断言确保这个事实**写在文件里**而不是靠后人记忆——避免 T2-T5 误用。
    """
    assert GOLDEN["_meta"]["status"] == "PARTIAL"
    gts = GOLDEN["_meta"]["ground_truth_status"]
    assert set(gts) == {"xls_verified", "derived", "pending"}


def test_every_case_carries_provenance_and_status():
    """每个算例必须带 provenance + status；derived 算例 status 必须是 pending_xls。

    强制约束：任何 derived 算例一旦被当成 verified 使用，断言即失败。
    """
    assert GOLDEN["cases"], "fixture 不得为空"
    for case in GOLDEN["cases"]:
        assert case["provenance"].startswith("derived"), case["name"]
        assert case["status"] == "pending_xls", (
            f"{case['name']} 是 derived 值，必须保持 status=pending_xls，"
            f"直到 XLS 真值替换（当前 {case['status']}）"
        )
    assert GOLDEN["xls_verified"]["status"] == "xls_verified"


# =============================================================================
# 边界
# =============================================================================


def test_boundary_minimum_flow():
    """最小流量：P11 → 0 时 Hx 单调下降，仍为正（未退化）。"""
    result = calc_thermosiphon_circulation(
        _base_input(inlet_pressure_drop_const_m=1e-6)
    )
    assert result.installation_height_calc_m > 0
    assert result.installation_height_calc_m < _case("med_flow")["expected"][
        "installation_height_calc_m"
    ]


def test_boundary_zero_resistance_coefficient_is_pure_darcy():
    """ΣP12 = 0 → Hx = ΣP11 / 驱动梯度（无几何项，退化为纯阻力平衡）。"""
    result = calc_thermosiphon_circulation(
        _base_input(
            inlet_pressure_drop_coeff=0.0,
            outlet_pressure_drop_coeff=0.0,
            shell_pressure_drop_coeff=0.0,
        )
    )
    assert result.resistance_coeff_per_m == 0.0
    assert math.isclose(
        result.installation_height_calc_m,
        result.resistance_const_m / result.driving_coeff_per_m,
        rel_tol=1e-9,
    )


def test_boundary_negative_temperature_rejected():
    """负温度：低于绝对零度 → ThermosiphonCirculationError。"""
    with pytest.raises(ThermosiphonCirculationError, match="绝对零度"):
        calc_thermosiphon_circulation(_base_input(drum_temperature_c=-300.0))


def test_boundary_drive_ratio_stays_pass_at_1p5_margin():
    """1.5 倍余量下推动力 / 总压降 > 1 → PASS（余量确实有效）。"""
    result = calc_thermosiphon_circulation(_base_input())
    assert result.check_result == "PASS"
    assert result.circulation_drive_ratio > 1.0


# =============================================================================
# 异常
# =============================================================================


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"shell_diameter_m": 0.0}, "shell_diameter_m"),
        ({"drum_diameter_m": -1.0}, "drum_diameter_m"),
        ({"drum_liquid_level_m": -0.1}, "drum_liquid_level_m"),
        ({"drum_liquid_density_kg_m3": 0.0}, "drum_liquid_density_kg_m3"),
        ({"shell_avg_density_kg_m3": 0.0}, "shell_avg_density_kg_m3"),
        ({"safety_factor": 0.0}, "safety_factor"),
        ({"inlet_pressure_drop_const_m": -1.0}, "inlet_pressure_drop_const_m"),
        ({"inlet_pressure_drop_coeff": -0.1}, "inlet_pressure_drop_coeff"),
    ],
)
def test_input_errors_raise_thermosiphon_error(overrides: dict, match: str):
    """输入越界 → ThermosiphonCirculationError（422）。"""
    with pytest.raises(ThermosiphonCirculationError, match=match):
        calc_thermosiphon_circulation(_base_input(**overrides))


def test_inverted_density_no_driving_head():
    """壳程密度 >= 汽包密度 → 无密度驱动压头 → 报错。"""
    with pytest.raises(ThermosiphonCirculationError, match="无密度驱动压头"):
        calc_thermosiphon_circulation(
            _base_input(shell_avg_density_kg_m3=900.0, drum_liquid_density_kg_m3=865.0)
        )


def test_no_solution_when_resistance_gradient_exceeds_drive():
    """ΣP12 >= 驱动梯度 → 任意 Hx 都无解 → 报错（不返回 ∞）。"""
    with pytest.raises(ThermosiphonCirculationError, match="平衡式无解"):
        calc_thermosiphon_circulation(_base_input(inlet_pressure_drop_coeff=0.5))


def test_zero_total_resistance_rejected():
    """ΣP11 = 0 → 平衡式退化为 Hx = 0 → 报错。"""
    with pytest.raises(ThermosiphonCirculationError, match="ΣP11"):
        calc_thermosiphon_circulation(
            _base_input(
                inlet_pressure_drop_const_m=0.0,
                outlet_pressure_drop_const_m=0.0,
                shell_pressure_drop_const_m=0.0,
            )
        )


def test_error_is_pcs_error_subclass_with_422():
    """ThermosiphonCirculationError 继承 PcsError，code/status 固定。"""
    assert issubclass(ThermosiphonCirculationError, PcsError)
    assert ThermosiphonCirculationError.code == "THERMOSIPHON_INPUT_ERROR"
    assert ThermosiphonCirculationError.status == 422


@pytest.mark.parametrize(
    "kwargs",
    [
        {"friction_factor": 0.0},
        {"equivalent_length_m": 0.0},
        {"inner_diameter_m": -0.1},
        {"velocity_m_per_s": 0.0},
    ],
)
def test_pipe_friction_head_rejects_invalid(kwargs: dict):
    """pipe_friction_head_m 参数越界 → ThermosiphonCirculationError。"""
    base = {
        "friction_factor": 0.008015,
        "equivalent_length_m": 97.4,
        "inner_diameter_m": 0.25,
        "velocity_m_per_s": 2.6377,
    }
    with pytest.raises(ThermosiphonCirculationError):
        pipe_friction_head_m(**{**base, **kwargs})


# =============================================================================
# dataclass contract
# =============================================================================


def test_input_dataclass_is_frozen():
    """ThermosiphonCirculationInput frozen=True（不可变契约）。"""
    inp = _base_input()
    assert dataclasses.is_dataclass(inp)
    with pytest.raises(dataclasses.FrozenInstanceError):
        inp.shell_diameter_m = 99.0  # type: ignore[misc]


def test_result_dataclass_is_frozen():
    """ThermosiphonCirculationResult frozen=True（不可变契约）。"""
    result = calc_thermosiphon_circulation(_base_input())
    assert isinstance(result, ThermosiphonCirculationResult)
    assert dataclasses.is_dataclass(result)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.installation_height_calc_m = 0.0  # type: ignore[misc]


def test_service_layer_fields_carry_unit_suffixes():
    """工艺室 §5.2：service 层字段名带显式单位后缀（DDL 层不带）。"""
    for f in dataclasses.fields(ThermosiphonCirculationInput):
        assert (
            f.name.endswith(
                ("_m", "_m3", "_c", "_m_per_s", "_per_m", "_factor", "_coeff")
            )
            or f.name == "circulation_type"
        ), f"字段 {f.name} 缺单位后缀"


# =============================================================================
# 持久化契约（ORM 列名不带单位后缀，SUP-010 §3.5 逐字命名）
# =============================================================================


def test_orm_columns_match_sup_010_ddl():
    """ORM 11 业务列 + 4 JSONB 容器按 SUP-010 §3.5 逐字命名。"""
    from app.models.calc import ThermosiphonCirculationResult as Orm

    cols = set(Orm.__table__.columns.keys())
    for name in (
        "equipment_tag",
        "equipment_name",
        "circulation_type",
        "shell_diameter",
        "drum_diameter",
        "drum_liquid_level",
        "installation_height_calc",
        "installation_height_final",
        "safety_factor",
        "check_result",
        "circulation_drive_ratio",
        "inlet_pipe_params",
        "outlet_pipe_params",
        "shell_side_params",
        "other_params",
    ):
        assert name in cols, f"缺 SUP-010 §3.5 列 {name}"
    # UNIQUE(project_id, equipment_tag)
    uniq = {
        tuple(sorted(c.name for c in uc.columns))
        for uc in Orm.__table__.constraints
        if uc.__class__.__name__ == "UniqueConstraint"
    }
    assert ("equipment_tag", "project_id") in uniq


def test_record_type_registered_in_calc_lineage():
    """calc_lineage.RECORD_TYPE_REGISTRY 已注册（ADR-0031 统一收口）。"""
    from app.services.calc_lineage import RECORD_TYPE_REGISTRY

    assert "ThermosiphonCirculationResult" in RECORD_TYPE_REGISTRY
