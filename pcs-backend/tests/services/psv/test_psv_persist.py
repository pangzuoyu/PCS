"""P5-3-6 PSV 落库 service dispatcher + helpers 单元测试。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §395-417 + SUP-P5-PSV-001 + ADR-0028 V1.1：

本测试只覆盖**纯函数 dispatcher + helpers**（不依赖 DB）：
- _dispatch_scenario_calc（4 种 scenario → ReliefCase）
- _default_standard_refs（API/7th 默认）
- _resolve_standard_profile 输入契约（profile 缺省走全局默认）

落库 + outlet_stream + 标准 profile upsert 走 tests/api/v1/test_psv_api.py 集成测试。
"""
from __future__ import annotations

import pytest

from app.services.psv import (
    ReliefCase,
)
from app.services.psv.psv_persist import (
    _default_standard_refs,
    _dispatch_scenario_calc,
)

# ============================================================================
# 1. _default_standard_refs
# ============================================================================


def test_default_standard_refs_api_path():
    """API/7th 默认标准引用：fire_case + relief_area + orifice 三件套。"""
    refs = _default_standard_refs()

    assert "fire_case" in refs
    assert refs["fire_case"]["standard"] == "API_521"
    assert refs["fire_case"]["version"] == "7th"
    assert "relief_area" in refs
    assert refs["relief_area"]["standard"] == "API_520"
    assert "orifice" in refs
    assert refs["orifice"]["standard"] == "API_526"


# ============================================================================
# 2. _dispatch_scenario_calc（4 种 scenario → ReliefCase）
# ============================================================================


def test_dispatch_fire_case():
    """FIRE scenario → FireCaseInput → ReliefCase.formula_ref 是 dict。"""
    relief_case = _dispatch_scenario_calc(
        scenario="FIRE",
        scenario_params={
            "D_m": 1.0,
            "H_m": 5.0,
            "liquid_level_fraction": 0.5,
            "environment_factor_F": 1.0,
            "h_fg_j_per_kg": 350_000.0,
        },
        standard="API",
        version="7th",
    )
    assert isinstance(relief_case, ReliefCase)
    assert relief_case.scenario == "FIRE"
    assert relief_case.relief_mass_flow_kgs > 0
    assert relief_case.relief_volume_flow_m3s > 0
    # formula_ref dict（API 521 火灾公式溯源）
    assert relief_case.formula_ref["standard"] == "API_521"
    assert relief_case.formula_ref["version"] == "7th"


def test_dispatch_closed_valve():
    """CLOSED_VALVE scenario → ClosedValveInput → ReliefCase。"""
    relief_case = _dispatch_scenario_calc(
        scenario="CLOSED_VALVE",
        scenario_params={
            "V_pipe_m3": 0.1,
            "rho_L_kg_m3": 850.0,
            "t_isolation_s": 60.0,
        },
        standard="API",
        version="7th",
    )
    assert relief_case.scenario == "CLOSED_VALVE"
    assert relief_case.relief_mass_flow_kgs == pytest.approx(0.1 * 850.0 / 60.0)
    assert relief_case.formula_ref["clause"] == "§5.15.2.3"


def test_dispatch_reaction_runaway():
    """REACTION_RUNAWAY scenario → ReactionRunawayInput → ReliefCase。"""
    relief_case = _dispatch_scenario_calc(
        scenario="REACTION_RUNAWAY",
        scenario_params={
            "Q_rxn_w": 100_000.0,
            "fraction_to_valve": 0.5,
        },
        standard="API",
        version="7th",
    )
    assert relief_case.scenario == "REACTION_RUNAWAY"
    # 默认 h_fg=350_000 J/kg：W = 100000 × 0.5 / 350000 ≈ 0.143
    assert relief_case.relief_mass_flow_kgs == pytest.approx(100_000.0 * 0.5 / 350_000.0)
    # 反应失控无体积流量输出（V1 简化）
    assert relief_case.relief_volume_flow_m3s == 0.0
    assert relief_case.formula_ref["clause"] == "§5.15.2.4"


def test_dispatch_thermal_expansion():
    """THERMAL_EXPANSION scenario → ThermalExpansionInput → ReliefCase。"""
    relief_case = _dispatch_scenario_calc(
        scenario="THERMAL_EXPANSION",
        scenario_params={
            "V_L_m3": 10.0,
            "rho_L_kg_m3": 1000.0,
            "beta_per_k": 0.0001,
            "delta_T_k": 100.0,
            "t_heat_s": 600.0,
        },
        standard="API",
        version="7th",
    )
    assert relief_case.scenario == "THERMAL_EXPANSION"
    # W = ρ_L × V_L × β × ΔT / t = 1000 × 10 × 1e-4 × 100 / 600 ≈ 0.167
    expected_w = 1000.0 * 10.0 * 0.0001 * 100.0 / 600.0
    assert relief_case.relief_mass_flow_kgs == pytest.approx(expected_w)
    assert relief_case.formula_ref["clause"] == "§5.15.2.5"


def test_dispatch_invalid_scenario_raises():
    """未知 scenario → PcsError(422, PSV_INPUT_ERROR)。"""
    from app.services.exceptions import PcsError

    with pytest.raises(PcsError) as exc_info:
        _dispatch_scenario_calc(
            scenario="UNKNOWN",  # type: ignore[arg-type]
            scenario_params={},
            standard="API",
            version="7th",
        )
    assert exc_info.value.code == "PSV_INPUT_ERROR"
    assert exc_info.value.status == 422


def test_dispatch_gb_v2024():
    """GB 2024 火灾工况 → ReliefCase.formula_ref.version=2024（API/GB 隔离）。"""
    relief_case = _dispatch_scenario_calc(
        scenario="FIRE",
        scenario_params={
            "D_m": 1.0,
            "H_m": 5.0,
            "liquid_level_fraction": 0.5,
            "environment_factor_F": 1.0,
            "h_fg_j_per_kg": 350_000.0,
        },
        standard="GB",
        version="2024",
    )
    assert relief_case.formula_ref["standard"] == "GB_T_150.1-2024"
    assert relief_case.formula_ref["version"] == "2024"
    assert "附录" in relief_case.formula_ref["clause"]


# ============================================================================
# 3. 集成测试：dispatcher → aggregate → relief_area → orifice 端到端
# ============================================================================


def test_dispatcher_to_aggregate_to_area_to_orifice():
    """4 个 service 串联：FIRE 火灾 → aggregate → relief_area → orifice。

    验证 P5-3-1/3/4/5 service 通过 psv_persist dispatcher 编排可正常串联。
    """
    from app.services.psv import (
        OrificeInput,
        ReliefAggregateInput,
        ReliefAreaInput,
        calc_relief_aggregate,
        calc_relief_area,
        select_orifice_api526,
    )

    # 1. dispatcher → ReliefCase
    relief_case = _dispatch_scenario_calc(
        scenario="FIRE",
        scenario_params={
            "D_m": 2.0,
            "H_m": 6.0,
            "liquid_level_fraction": 0.7,
            "environment_factor_F": 1.0,
            "h_fg_j_per_kg": 350_000.0,
        },
        standard="API",
        version="7th",
    )

    # 2. aggregate（单工况）
    aggregate = calc_relief_aggregate(ReliefAggregateInput(cases=(relief_case,)))
    assert aggregate.dominant_scenario == "FIRE"
    assert aggregate.max_relief_mass_flow_kgs == relief_case.relief_mass_flow_kgs

    # 3. relief_area
    area_result = calc_relief_area(
        ReliefAreaInput(
            relief_mass_flow_kgs=aggregate.max_relief_mass_flow_kgs,
            phase="GAS",
            P_back_pa=100_000.0,
            P_set_pa=200_000.0,
        ),
        standard="API",
    )
    assert area_result.area_required_m2 > 0

    # 4. orifice
    orifice = select_orifice_api526(
        OrificeInput(area_required_m2=area_result.area_required_m2),
    )
    assert orifice.selected_size in ("D", "E", "F", "G", "H", "J", "K", "L", "M",
                                      "N", "P", "Q", "R", "T")
    assert orifice.actual_area_m2 >= area_result.area_required_m2


# ============================================================================
# OPEN-10-4 余项：V1.14 §4.6 helpers + 18 列落库派生映射
# ============================================================================


def test_get_default_blowdown_gas_5pct():
    """_get_default_blowdown('GAS') → 0.05（V1.14 §3.5 联动规则）。"""
    from app.services.psv.psv_persist import _get_default_blowdown

    assert _get_default_blowdown("GAS") == 0.05


def test_get_default_blowdown_liquid_10pct():
    """_get_default_blowdown('LIQUID') → 0.10。"""
    from app.services.psv.psv_persist import _get_default_blowdown

    assert _get_default_blowdown("LIQUID") == 0.10


def test_get_default_blowdown_two_phase_10pct():
    """_get_default_blowdown('TWO_PHASE') → 0.10。"""
    from app.services.psv.psv_persist import _get_default_blowdown

    assert _get_default_blowdown("TWO_PHASE") == 0.10


def test_get_default_blowdown_unknown_medium_fallback():
    """未知 medium → _DEFAULT_BLOWDOWN_FRACTION（0.05）兜底。"""
    from app.services.psv.psv_persist import _get_default_blowdown

    assert _get_default_blowdown("UNKNOWN_MEDIUM_XYZ") == 0.05


def test_formula_ref_to_dict_basic():
    """_formula_ref_to_dict(dataclass FormulaRef) → 标准 dict 含 standard/version/clause。"""
    from app.services.psv.fire_case_service import FireCaseInput, calc_fire_case
    from app.services.psv.psv_persist import _formula_ref_to_dict

    result = calc_fire_case(
        FireCaseInput(
            D_m=1.0,
            H_m=5.0,
            liquid_level_fraction=0.5,
            environment_factor_F=1.0,
            h_fg_j_per_kg=350_000.0,
        ),
        standard="API",
        version="7th",
    )
    ref_dict = _formula_ref_to_dict(result.formula_ref)
    assert isinstance(ref_dict, dict)
    assert ref_dict["standard"] == "API_521"
    assert ref_dict["version"] == "7th"


def test_formula_ref_to_dict_handles_dict_input():
    """_formula_ref_to_dict 接收 dict 输入 → 直接透传（兼容历史 record）。"""
    from app.services.psv.psv_persist import _formula_ref_to_dict

    src = {"standard": "API_520", "version": "9th", "clause": "§5.3.1"}
    assert _formula_ref_to_dict(src) == src


def test_default_inlet_size_4_inch():
    """_DEFAULT_INLET_SIZE = '4 inch'（V1 锁定入口；§3.3 默认；P5-3-7 端点可覆盖）。"""
    from app.services.psv.psv_persist import _DEFAULT_INLET_SIZE

    assert _DEFAULT_INLET_SIZE == "4 inch"


def test_default_outlet_size_6_inch():
    """_DEFAULT_OUTLET_SIZE = '6 inch'（V1 锁定出口；§3.3 默认）。"""
    from app.services.psv.psv_persist import _DEFAULT_OUTLET_SIZE

    assert _DEFAULT_OUTLET_SIZE == "6 inch"


def test_blowdown_default_by_medium_persists_module():
    """_BLOWDOWN_DEFAULT_BY_MEDIUM 4 介质默认（GAS/VAPOR=5%, LIQUID/TWO_PHASE=10%）。"""
    from app.services.psv.psv_persist import _BLOWDOWN_DEFAULT_BY_MEDIUM

    assert _BLOWDOWN_DEFAULT_BY_MEDIUM["GAS"] == 0.05
    assert _BLOWDOWN_DEFAULT_BY_MEDIUM["VAPOR"] == 0.05
    assert _BLOWDOWN_DEFAULT_BY_MEDIUM["LIQUID"] == 0.10
    assert _BLOWDOWN_DEFAULT_BY_MEDIUM["TWO_PHASE"] == 0.10


def test_formula_version_constant():
    """_FORMULA_VERSION 是非空字符串（V1.14 §4.6 record_hash 协议标识）。"""
    from app.services.psv.psv_persist import _FORMULA_VERSION

    assert isinstance(_FORMULA_VERSION, str)
    assert len(_FORMULA_VERSION) > 0


def test_generate_tag_number_basic():
    """_generate_tag_number(project_id) → 'PSV-{8hex}' 格式（每次新生成 8 hex）。"""
    import uuid

    from app.services.psv.psv_persist import _generate_tag_number

    project_id = uuid.uuid4()
    tag1 = _generate_tag_number(project_id)
    tag2 = _generate_tag_number(project_id)
    # 前缀 PSV- + 8 hex（项目内由 DB unique 约束兜底）
    assert tag1.startswith("PSV-")
    assert len(tag1) == len("PSV-") + 8
    # 每次不同（UUID 随机）
    assert tag1 != tag2
    # project_id 参数当前未被使用（保留为接口签名）
    assert isinstance(project_id, uuid.UUID)


def test_generate_tag_number_format_8hex_uppercase():
    """_generate_tag_number 生成 8 位大写 hex（与 pcs_persist 其他模块一致）。"""
    import re
    import uuid

    from app.services.psv.psv_persist import _generate_tag_number

    tag = _generate_tag_number(uuid.uuid4())
    match = re.match(r"^PSV-([0-9A-F]{8})$", tag)
    assert match is not None, f"tag {tag} 不匹配 PSV-XXXXXXXX 格式"