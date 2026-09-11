"""P3.2 SIM-22: PropertyConflictResolver 物性冲突解决（spec V1.6 §3.6 ADD-002）。

spec V1.6 §3.6 三原则：
1. 数学一致性 > 用户输入（硬冲突阻止保存）
2. 实测数据 > 模型计算（物性类字段：用户值优先，标记偏差）
3. 精确计算 > 用户估计（分子量/换算流量：计算值优先，用户输入忽略）

USER_PRIORITY 字段（6 个，实测优先）：liquid_density, liquid_viscosity,
vapor_density, surface_tension, rvp, tvp。偏差阈值 per field：
    liquid_density: 10% / liquid_viscosity: 20% / vapor_density: 10% /
    surface_tension: 15% / rvp: 10% / tvp: 10%
偏差 > 阈值 → WARN（用户值已采用但警告）；否则 INFO（通过）。

CALCULATED_PRIORITY 字段（3 个，精确计算优先）：molecular_weight,
total_molar_flow, total_mass_flow。用户填了但偏差 > 1% → WARN；effective
始终取 calculated（用户输入被忽略）。

effective 计算：effective = calculated ⊕ user_provided（user 顶层键覆写
calculated），但 CALCULATED_PRIORITY_FIELDS 例外（始终取 calculated）。

输出字段（conflict_resolutions_json）：{"<field>": {"strategy": "USER_PROVIDED"|"CALCULATED",
"diff_pct": float, "severity": "BLOCK"|"WARN"|"INFO", "message": str}, ...}
"""
from __future__ import annotations

import pytest

from app.services.property_conflict_resolver import (
    CALCULATED_PRIORITY_FIELDS,
    USER_PRIORITY_FIELDS,
    ConflictResolution,
    ConflictSeverity,
    PropertyConflictResolver,
)

# ---------------------------------------------------------------------------
# enum + dataclass + 字段集 契约
# ---------------------------------------------------------------------------


def test_conflict_severity_enum_values():
    """BLOCK / WARN / INFO 三级。"""
    assert {e.value for e in ConflictSeverity} == {"BLOCK", "WARN", "INFO"}


def test_conflict_resolution_dataclass_carries_required_fields():
    c = ConflictResolution(
        severity=ConflictSeverity.WARN,
        field="liquid_density",
        user_value=900.0,
        calculated_value=803.0,
        resolution="USER_VALUE",
        message="用户值与计算值偏差 12.1%",
    )
    assert c.severity == ConflictSeverity.WARN
    assert c.field == "liquid_density"
    assert c.user_value == 900.0
    assert c.calculated_value == 803.0
    assert c.resolution == "USER_VALUE"
    assert "12.1%" in c.message


def test_user_priority_fields_set():
    """USER_PRIORITY 字段 6 个（含偏差阈值）。"""
    assert set(USER_PRIORITY_FIELDS.keys()) == {
        "liquid_density",
        "liquid_viscosity",
        "vapor_density",
        "liquid_surface_tension",  # SIM-33: surface_tension 重命名
        "rvp",
        "tvp",
    }
    assert USER_PRIORITY_FIELDS["liquid_density"] == pytest.approx(0.10)
    assert USER_PRIORITY_FIELDS["liquid_viscosity"] == pytest.approx(0.20)


def test_calculated_priority_fields_set():
    """CALCULATED_PRIORITY 字段 3 个（精确计算优先）。"""
    assert set(CALCULATED_PRIORITY_FIELDS.keys()) == {
        "molecular_weight",
        "total_molar_flow",
        "total_mass_flow",
    }


# ---------------------------------------------------------------------------
# USER_PRIORITY 字段
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    ["liquid_density", "liquid_viscosity", "vapor_density",
     "liquid_surface_tension", "rvp", "tvp"],  # SIM-33 rename
)
def test_user_priority_deviation_within_threshold_emits_info(field):
    """偏差 ≤ 阈值 → INFO（用户值已采用）。"""
    thr = USER_PRIORITY_FIELDS[field]
    calc = 1000.0
    user = calc * (1 + thr * 0.5)  # 偏差 = 50% 阈值
    r = PropertyConflictResolver()
    cs = r.resolve(user_props={field: user}, calc_props={field: calc})
    assert len(cs) == 1
    assert cs[0].severity == ConflictSeverity.INFO
    assert cs[0].resolution == "USER_VALUE"


@pytest.mark.parametrize(
    "field",
    ["liquid_density", "liquid_viscosity", "vapor_density",
     "liquid_surface_tension", "rvp", "tvp"],  # SIM-33 rename
)
def test_user_priority_deviation_exceeds_threshold_emits_warn(field):
    """偏差 > 阈值 → WARN（用户值已采用但警告）。"""
    thr = USER_PRIORITY_FIELDS[field]
    calc = 1000.0
    user = calc * (1 + thr * 2.0)  # 偏差 = 200% 阈值
    r = PropertyConflictResolver()
    cs = r.resolve(user_props={field: user}, calc_props={field: calc})
    assert len(cs) == 1
    assert cs[0].severity == ConflictSeverity.WARN
    assert cs[0].resolution == "USER_VALUE"


# ---------------------------------------------------------------------------
# CALCULATED_PRIORITY 字段
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    ["molecular_weight", "total_molar_flow", "total_mass_flow"],
)
def test_calculated_priority_deviation_within_tolerance_no_conflict(field):
    """CALCULATED_PRIORITY 偏差 ≤ 1% → 无冲突（用户值接近计算值）。"""
    calc = 100.0
    user = calc * 1.005  # 偏差 0.5% < 1%
    r = PropertyConflictResolver()
    cs = r.resolve(user_props={field: user}, calc_props={field: calc})
    assert cs == []


@pytest.mark.parametrize(
    "field",
    ["molecular_weight", "total_molar_flow", "total_mass_flow"],
)
def test_calculated_priority_deviation_exceeds_tolerance_emits_warn(field):
    """CALCULATED_PRIORITY 偏差 > 1% → WARN（计算值优先，用户输入被忽略）。"""
    calc = 100.0
    user = calc * 1.5  # 偏差 50% > 1%
    r = PropertyConflictResolver()
    cs = r.resolve(user_props={field: user}, calc_props={field: calc})
    assert len(cs) == 1
    assert cs[0].severity == ConflictSeverity.WARN
    assert cs[0].resolution == "CALCULATED_VALUE"
    assert cs[0].field == field


def test_calculated_priority_zero_calc_value_skips():
    """calculated=0 时无法算偏差，跳过（避免 ZeroDivisionError）。"""
    r = PropertyConflictResolver()
    cs = r.resolve(
        user_props={"molecular_weight": 100.0},
        calc_props={"molecular_weight": 0.0},
    )
    assert cs == []


# ---------------------------------------------------------------------------
# missing fields & non-numeric values
# ---------------------------------------------------------------------------


def test_missing_user_value_skips():
    """user_provided 无该字段 → 跳过（无冲突）。"""
    r = PropertyConflictResolver()
    cs = r.resolve(
        user_props={"liquid_density": 900.0},
        calc_props={"liquid_density": 800.0, "vapor_density": 5.0},
    )
    # 仅 liquid_density 进入比较
    assert len(cs) == 1
    assert cs[0].field == "liquid_density"


def test_missing_calc_value_skips():
    """calc 无该字段 → 跳过（无冲突）。"""
    r = PropertyConflictResolver()
    cs = r.resolve(
        user_props={"liquid_density": 900.0, "vapor_density": 4.0},
        calc_props={"liquid_density": 800.0},
    )
    assert len(cs) == 1
    assert cs[0].field == "liquid_density"


def test_unknown_field_skipped():
    """未注册字段 → 不进冲突列表（避免污染）。"""
    r = PropertyConflictResolver()
    cs = r.resolve(
        user_props={"random_field": 1.0},
        calc_props={"random_field": 2.0},
    )
    assert cs == []


def test_non_numeric_value_skipped():
    """非数值字段（如字符串）→ 跳过（不抛错）。"""
    r = PropertyConflictResolver()
    cs = r.resolve(
        user_props={"liquid_density": "abc"},
        calc_props={"liquid_density": 800.0},
    )
    assert cs == []


# ---------------------------------------------------------------------------
# effective = calculated ⊕ user_provided
# ---------------------------------------------------------------------------


def test_effective_user_overrides_calculated_for_user_priority_field():
    """USER_PRIORITY 字段：user 顶层键覆写 calculated。"""
    r = PropertyConflictResolver()
    eff = r.compute_effective(
        user_props={"liquid_density": 900.0},
        calc_props={"liquid_density": 800.0},
    )
    assert eff["liquid_density"] == 900.0


def test_effective_calculated_wins_for_calculated_priority_field():
    """CALCULATED_PRIORITY 字段：始终取 calculated，用户输入被忽略。"""
    r = PropertyConflictResolver()
    eff = r.compute_effective(
        user_props={"molecular_weight": 50.0},
        calc_props={"molecular_weight": 30.0},
    )
    assert eff["molecular_weight"] == 30.0


def test_effective_merges_independent_fields():
    """有效字段集 = calculated ∪ user_provided（互不冲突字段）。"""
    r = PropertyConflictResolver()
    eff = r.compute_effective(
        user_props={"liquid_density": 900.0},
        calc_props={"molecular_weight": 30.0},
    )
    assert eff["liquid_density"] == 900.0
    assert eff["molecular_weight"] == 30.0


def test_effective_only_calc_when_user_empty():
    """user_provided 空 → effective = calculated。"""
    r = PropertyConflictResolver()
    eff = r.compute_effective(
        user_props={}, calc_props={"mw": 30.0, "tc": 305.0}
    )
    assert eff == {"mw": 30.0, "tc": 305.0}


def test_effective_only_user_when_calc_empty():
    """calc 空 → effective = user_provided（USER_PRIORITY 字段透传）。"""
    r = PropertyConflictResolver()
    eff = r.compute_effective(
        user_props={"liquid_density": 900.0}, calc_props={}
    )
    assert eff == {"liquid_density": 900.0}


# ---------------------------------------------------------------------------
# 全流程：resolve + effective + conflict_resolutions_json
# ---------------------------------------------------------------------------


def test_full_resolution_produces_conflict_dict_for_streams_json():
    """全流程：resolve + compute_effective + conflict_resolutions_json 输出。

    输入：
        user_provided = {MW: 30.0, liquid_density: 900.0}
        calculated    = {MW: 30.5, liquid_density: 850.0, source: Joback}
    预期：
        effective = {MW: 30.5, liquid_density: 900.0, source: Joback}
        conflict_resolutions_json = {
            "MW": {
                "strategy": "CALCULATED", "diff_pct": 1.67,
                "severity": "INFO", "message": "..."
            },
            "liquid_density": {
                "strategy": "USER_PROVIDED", "diff_pct": 5.88,
                "severity": "INFO", "message": "..."
            }
        }
    """
    r = PropertyConflictResolver()
    user_props = {"molecular_weight": 30.0, "liquid_density": 900.0}
    calc_props = {
        "molecular_weight": 30.5,
        "liquid_density": 850.0,
        "source": "Joback",
    }
    cs = r.resolve(user_props=user_props, calc_props=calc_props)
    eff = r.compute_effective(user_props=user_props, calc_props=calc_props)
    conflict_dict = r.to_conflict_resolutions_json(cs)
    # effective: MW=CALC 优先，liquid_density=USER，source=CALC
    assert eff["molecular_weight"] == 30.5
    assert eff["liquid_density"] == 900.0
    assert eff["source"] == "Joback"
    # conflict_dict: MW + liquid_density
    assert set(conflict_dict.keys()) == {"molecular_weight", "liquid_density"}
    assert conflict_dict["molecular_weight"]["strategy"] == "CALCULATED"
    assert conflict_dict["liquid_density"]["strategy"] == "USER_PROVIDED"
    # diff_pct = |30.0-30.5|/30.5 ≈ 1.639
    assert conflict_dict["molecular_weight"]["diff_pct"] == pytest.approx(1.639, abs=0.01)


def test_resolve_returns_empty_when_no_overlap():
    """两套字段完全不相交 → resolve 返回空。"""
    r = PropertyConflictResolver()
    cs = r.resolve(
        user_props={"liquid_density": 900.0},
        calc_props={"vapor_density": 5.0},
    )
    assert cs == []


def test_resolve_with_block_level_phase_conflict_extension():
    """扩展点：硬冲突（如相态/T/P 矛盾）由上游 SIM-7 conflict_resolver 产生
    PropertyConflictResolver 不重复实现 BLOCK 物性冲突。

    但 BLOCK 类型应可在严重偏差下产出（如 liquid_density 偏差 > 50% 视为
    严重异常——但 spec 没要求；spec 三级不含 BLOCK 在 USER_PRIORITY 内）。

    本契约：PropertyConflictResolver 只产出 WARN / INFO（硬冲突归
    ConflictResolver）。
    """
    r = PropertyConflictResolver()
    # 极大偏差（10x）
    cs = r.resolve(
        user_props={"liquid_density": 10000.0},
        calc_props={"liquid_density": 100.0},
    )
    assert len(cs) == 1
    assert cs[0].severity == ConflictSeverity.WARN  # 即使极大偏差也是 WARN
    assert cs[0].resolution == "USER_VALUE"


def test_resolve_batch_multiple_fields():
    """批量：4 字段组合，3 WARN + 1 INFO。"""
    r = PropertyConflictResolver()
    user = {
        "liquid_density": 900.0,   # vs 800 → 12.5% > 10% → WARN
        "liquid_viscosity": 1.2,   # vs 1.0 → 20% == 20% → 临界值视为 INFO（≤）
        "rvp": 60.0,               # vs 50 → 20% > 10% → WARN
        "molecular_weight": 30.0,  # vs 30.5 → 1.64% > 1% → WARN
    }
    calc = {
        "liquid_density": 800.0,
        "liquid_viscosity": 1.0,
        "rvp": 50.0,
        "molecular_weight": 30.5,
    }
    cs = r.resolve(user_props=user, calc_props=calc)
    by_field = {c.field: c for c in cs}
    assert by_field["liquid_density"].severity == ConflictSeverity.WARN
    assert by_field["liquid_viscosity"].severity == ConflictSeverity.INFO
    assert by_field["rvp"].severity == ConflictSeverity.WARN
    assert by_field["molecular_weight"].severity == ConflictSeverity.WARN
    assert by_field["molecular_weight"].resolution == "CALCULATED_VALUE"
