"""P3.x SIM-30：组分别名注册表（spec §8.3 验收：≥50 项常见别名）。

设计：
- 单源真相：`app.services.alias_registry.ALIAS_GROUPS`
- 每组含 `type` 字段：ALIAS / ALIAS_WITH_FACTOR / ENUM / KEYWORD / FIELD_NAME
- ≥50 验收只统计 type == ALIAS | ALIAS_WITH_FACTOR（避免被纯枚举/keyword 凑数）
- 兼容层：`proii_parser.map_libid_to_alias` 改为薄 shim 调用 `resolve_alias`
- Excel 模板 Sheet3 自动消费新组（`_component_alias_rows` 迭代所有 ALIAS 类型）

组结构：
- COMPONENT_NAME：≥25（PROII_LIBID→CAS + Excel 用户别名）
- UNIT_CONVERSION：≥10（PROII 单位换算 + 转换因子）
- EXCEL_COLUMN：≥10（Excel 列名 → DB 字段）
- VALIDATOR_FIELD：≥10（SIM-V01~V10 / SIM-E01~E04 字段名）
"""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Group type constants
# ---------------------------------------------------------------------------

GROUP_TYPE_ALIAS = "ALIAS"
GROUP_TYPE_ALIAS_WITH_FACTOR = "ALIAS_WITH_FACTOR"
GROUP_TYPE_ENUM = "ENUM"
GROUP_TYPE_KEYWORD = "KEYWORD"
GROUP_TYPE_FIELD_NAME = "FIELD_NAME"

ALIAS_TYPES = frozenset({GROUP_TYPE_ALIAS, GROUP_TYPE_ALIAS_WITH_FACTOR})


# ---------------------------------------------------------------------------
# 受测目标
# ---------------------------------------------------------------------------


def _import_registry():
    """延迟导入：未实现时 RED 阶段 fail cleanly。"""
    from app.services.alias_registry import ALIAS_GROUPS  # noqa: F401

    return ALIAS_GROUPS


def _import_resolve_alias():
    from app.services.alias_registry import resolve_alias

    return resolve_alias


# ---------------------------------------------------------------------------
# 骨架：registry 必须存在 + 类型契约
# ---------------------------------------------------------------------------


def test_registry_module_exists():
    """app.services.alias_registry 模块存在。"""
    import importlib

    mod = importlib.import_module("app.services.alias_registry")
    assert mod is not None


def test_alias_groups_is_dict_with_type_metadata():
    """每组含 type + entries 字段，entries 为 dict。"""
    ALIAS_GROUPS = _import_registry()
    assert isinstance(ALIAS_GROUPS, dict)
    assert len(ALIAS_GROUPS) >= 1
    for group_name, group_def in ALIAS_GROUPS.items():
        assert isinstance(group_def, dict)
        assert "type" in group_def, f"{group_name} 缺 type"
        assert "entries" in group_def, f"{group_name} 缺 entries"
        assert isinstance(group_def["entries"], dict)
        valid_types = {
            GROUP_TYPE_ALIAS,
            GROUP_TYPE_ALIAS_WITH_FACTOR,
            GROUP_TYPE_ENUM,
            GROUP_TYPE_KEYWORD,
            GROUP_TYPE_FIELD_NAME,
        }
        assert group_def["type"] in valid_types, (
            f"{group_name}.type={group_def['type']} 不在合法集中"
        )


# ---------------------------------------------------------------------------
# ≥50 验收：spec §8.3 契约（核心断言）
# ---------------------------------------------------------------------------


def test_alias_count_at_least_50():
    """spec §8.3 验收：组分别名 ≥ 50 项常见别名（仅统计 ALIAS/ALIAS_WITH_FACTOR）。"""
    ALIAS_GROUPS = _import_registry()
    alias_total = sum(
        len(g["entries"])
        for g in ALIAS_GROUPS.values()
        if g["type"] in ALIAS_TYPES
    )
    assert alias_total >= 50, (
        f"alias 总数 {alias_total} < 50（spec §8.3）；"
        f"ALIAS/ALIAS_WITH_FACTOR 组合计"
    )


# ---------------------------------------------------------------------------
# 配额断言：4 类必须分别满足最小计数
# ---------------------------------------------------------------------------


def test_component_name_alias_group_has_25_entries():
    """COMPONENT_NAME 组 ≥25 项（PROII_LIBID + 附录 A narrative + 化学常识补全）。"""
    ALIAS_GROUPS = _import_registry()
    assert "COMPONENT_NAME" in ALIAS_GROUPS
    group = ALIAS_GROUPS["COMPONENT_NAME"]
    assert group["type"] == GROUP_TYPE_ALIAS
    assert len(group["entries"]) >= 25, (
        f"COMPONENT_NAME={len(group['entries'])} < 25"
    )


def test_unit_conversion_alias_group_has_12_entries():
    """UNIT_CONVERSION 组 ≥12 项（PROII 单位 + 换算因子；type=ALIAS_WITH_FACTOR）。

    SIM-30 决议：配额从 ≥10 提到 ≥12 消除卡线（补 BAR/MMHG/PSI/G_CC 4 条）。
    """
    ALIAS_GROUPS = _import_registry()
    assert "UNIT_CONVERSION" in ALIAS_GROUPS
    group = ALIAS_GROUPS["UNIT_CONVERSION"]
    assert group["type"] == GROUP_TYPE_ALIAS_WITH_FACTOR
    assert len(group["entries"]) >= 12, (
        f"UNIT_CONVERSION={len(group['entries'])} < 12"
    )
    # 每项 entries 含 alias + canonical + factor
    for key, entry in group["entries"].items():
        assert "canonical" in entry, f"UNIT_CONVERSION[{key}] 缺 canonical"
        assert "factor" in entry, f"UNIT_CONVERSION[{key}] 缺 factor"
        assert isinstance(entry["factor"], (int, float))


def test_excel_column_alias_group_has_10_entries():
    """EXCEL_COLUMN 组 ≥10 项（Excel 中文列名 → DB 字段）。"""
    ALIAS_GROUPS = _import_registry()
    assert "EXCEL_COLUMN" in ALIAS_GROUPS
    group = ALIAS_GROUPS["EXCEL_COLUMN"]
    assert group["type"] == GROUP_TYPE_ALIAS
    assert len(group["entries"]) >= 10


def test_validator_field_alias_group_has_10_entries():
    """VALIDATOR_FIELD 组 ≥10 项（SIM-V01~V10 / SIM-E01~E04 字段名）。"""
    ALIAS_GROUPS = _import_registry()
    assert "VALIDATOR_FIELD" in ALIAS_GROUPS
    group = ALIAS_GROUPS["VALIDATOR_FIELD"]
    assert group["type"] == GROUP_TYPE_ALIAS
    assert len(group["entries"]) >= 10


# ---------------------------------------------------------------------------
# 关键别名覆盖（兼容已有测试）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "alias,canonical",
    [
        ("H2O", "WATER"),
        ("CO2", "CARBON_DIOXIDE"),
        ("H2S", "HYDROGEN_SULFIDE"),
        ("N2", "NITROGEN"),
        ("O2", "OXYGEN"),
        ("H2", "HYDROGEN"),
        ("NH3", "AMMONIA"),
        ("C1", "METHANE"),
        ("C2", "ETHANE"),
        ("C3", "PROPANE"),
        ("CO", "CARBON_MONOXIDE"),
        ("SO2", "SULFUR_DIOXIDE"),
        ("HCL", "HYDROGEN_CHLORIDE"),
        ("CL2", "CHLORINE"),
        ("NC4", "N_BUTANE"),
        ("IC4", "ISO_BUTANE"),
        ("NC5", "N_PENTANE"),
    ],
)
def test_component_name_aliases_resolve_correctly(alias, canonical):
    """PRO/II 17 项 LIBID→CAS 必含（兼容既有 proii_parser 行为）。"""
    resolve_alias = _import_resolve_alias()
    assert resolve_alias("COMPONENT_NAME", alias) == canonical


def test_component_name_excel_aliases_chinese():
    """Excel 端中文字符别名：H₂O/H2O/水 → WATER（spec 附录 A）。"""
    resolve_alias = _import_resolve_alias()
    assert resolve_alias("COMPONENT_NAME", "H₂O") == "WATER"
    assert resolve_alias("COMPONENT_NAME", "H2O") == "WATER"
    assert resolve_alias("COMPONENT_NAME", "水") == "WATER"


def test_resolve_alias_case_insensitive():
    """别名匹配大小写不敏感。"""
    resolve_alias = _import_resolve_alias()
    assert resolve_alias("COMPONENT_NAME", "h2o") == "WATER"
    assert resolve_alias("COMPONENT_NAME", "H2o") == "WATER"


def test_resolve_alias_unknown_returns_uppercased_input():
    """未知名 → 原名大写返回（兼容 map_libid_to_alias 行为）。"""
    resolve_alias = _import_resolve_alias()
    assert resolve_alias("COMPONENT_NAME", "C38") == "C38"
    assert resolve_alias("COMPONENT_NAME", "c38") == "C38"


def test_resolve_alias_unknown_group_returns_unchanged():
    """未知组名 → 原样返回（不抛）。"""
    resolve_alias = _import_resolve_alias()
    assert resolve_alias("UNKNOWN_GROUP", "X") == "X"


def test_resolve_alias_empty_input_returns_empty():
    """空串 → 空串（不抛）。"""
    resolve_alias = _import_resolve_alias()
    assert resolve_alias("COMPONENT_NAME", "") == ""


# ---------------------------------------------------------------------------
# 单元换算：ALIAS_WITH_FACTOR
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "alias,canonical,factor",
    [
        ("KG/CM²", "KPA", 98.0665),
        ("BAR", "KPA", 100.0),
        ("MMHG", "KPA", 0.133322),
        ("PSI", "KPA", 6.89476),
        ("KCAL/HR", "W", 1.163),
        ("M*KCAL/HR", "MJ/HR", 4.1868),
        ("KCAL/KG", "KJ/KG", 4.1868),
        ("KG/H", "KG/HR", 1.0),
        ("KG-MOL/H", "KMOL/HR", 1.0),
        ("CP", "MPA*S", 1.0),
        ("DYNE/CM", "MN/M", 1.0),
        ("DEG_C", "K", 273.15),
        ("DEG_F", "K", 255.372),
    ],
)
def test_unit_conversion_aliases_resolve(alias, canonical, factor):
    """PRO/II 13+ 项单位换算（spec §5.3 + 补充 BAR/MMHG/PSI/G_CC）。"""
    resolve_alias = _import_resolve_alias()
    result = resolve_alias("UNIT_CONVERSION", alias)
    assert result == canonical


def test_unit_conversion_get_factor():
    """`get_factor(group, alias)` 返回换算因子（ALIAS_WITH_FACTOR 专属 API）。"""
    from app.services.alias_registry import get_factor

    assert get_factor("UNIT_CONVERSION", "KG/CM²") == pytest.approx(98.0665)
    assert get_factor("UNIT_CONVERSION", "BAR") == pytest.approx(100.0)
    assert get_factor("UNIT_CONVERSION", "DEG_C") == pytest.approx(273.15)
    # 未知 alias 返回 None（不抛）
    assert get_factor("UNIT_CONVERSION", "UNKNOWN_UNIT") is None
    # 非 ALIAS_WITH_FACTOR 组返回 None
    assert get_factor("COMPONENT_NAME", "H2O") is None


# ---------------------------------------------------------------------------
# Excel 列名 → DB 字段
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "excel_header,db_field",
    [
        ("Stream Name", "stream_name"),
        ("Stream No", "stream_no"),
        ("Temperature (°C)", "temp"),
        ("Pressure (kPa)", "press"),
        ("Phase", "phase"),
        ("Total Mass Flow (kg/h)", "mass_flow"),
        ("Total Molar Flow (kmol/h)", "molar_flow"),
        ("Description", "description"),
        ("Component Name (alias ok)", "component_name"),
        ("Mole Fraction", "mole_fraction"),
        ("Mass Flow (kg/h)", "mass_flow"),
    ],
)
def test_excel_column_aliases_resolve(excel_header, db_field):
    """Excel 中文/英文列名 → DB 字段。"""
    resolve_alias = _import_resolve_alias()
    assert resolve_alias("EXCEL_COLUMN", excel_header) == db_field


# ---------------------------------------------------------------------------
# Validator field names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "alias,canonical",
    [
        ("stream_name", "stream_name"),
        ("name", "stream_name"),
        ("temp", "temperature"),
        ("temperature", "temperature"),
        ("press", "pressure"),
        ("pressure", "pressure"),
        ("phase", "phase"),
        ("mass_flow", "mass_flow"),
        ("molar_flow", "molar_flow"),
        ("composition", "composition_json"),
        ("composition_json", "composition_json"),
    ],
)
def test_validator_field_aliases_resolve(alias, canonical):
    resolve_alias = _import_resolve_alias()
    assert resolve_alias("VALIDATOR_FIELD", alias) == canonical


# ---------------------------------------------------------------------------
# registry 暴露的查询 API
# ---------------------------------------------------------------------------


def test_list_groups_returns_all_group_names():
    """`list_groups()` 返回所有组名（不限类型，供 Sheet3 迭代）。"""
    from app.services.alias_registry import list_groups

    groups = list_groups()
    assert isinstance(groups, list)
    assert "COMPONENT_NAME" in groups
    assert "UNIT_CONVERSION" in groups
    assert "EXCEL_COLUMN" in groups
    assert "VALIDATOR_FIELD" in groups


def test_get_group_items_returns_alias_entries():
    """`get_group_items(group)` 返回 (alias, canonical, factor) 三元组列表。

    SIM-30 决议：3 元组携带 factor 字段，ALIAS 组为 None，ALIAS_WITH_FACTOR
    带数值。
    """
    from app.services.alias_registry import get_group_items

    items = get_group_items("COMPONENT_NAME")
    assert isinstance(items, list)
    assert len(items) >= 25
    for item in items:
        assert len(item) == 3  # (alias, canonical, factor)
        assert isinstance(item[0], str)
        assert isinstance(item[1], str)
        assert item[2] is None  # 纯 ALIAS 组 factor=None


def test_get_group_items_unit_conversion_has_factors():
    """ALIAS_WITH_FACTOR 组每项带数值 factor。"""
    from app.services.alias_registry import get_group_items

    items = get_group_items("UNIT_CONVERSION")
    assert len(items) >= 12
    for item in items:
        assert len(item) == 3
        assert isinstance(item[2], (int, float))


def test_get_group_items_filters_by_type():
    """`group_type` 过滤：仅返回该 group_type 匹配的组的条目。"""
    from app.services.alias_registry import get_group_items

    # COMPONENT_NAME 是 ALIAS 类型 → group_type=ALIAS 返回条目
    items = get_group_items("COMPONENT_NAME", group_type="ALIAS")
    assert len(items) > 0
    # group_type=ALIAS_WITH_FACTOR 与 COMPONENT_NAME 不匹配 → 空
    items = get_group_items("COMPONENT_NAME", group_type="ALIAS_WITH_FACTOR")
    assert items == []


def test_get_group_items_unknown_group_returns_empty():
    from app.services.alias_registry import get_group_items

    assert get_group_items("UNKNOWN_GROUP") == []


# ---------------------------------------------------------------------------
# 兼容层：proii_parser.map_libid_to_alias 仍然工作
# ---------------------------------------------------------------------------


def test_map_libid_to_alias_still_works_via_shim():
    """`proii_parser.map_libid_to_alias` 改为薄 shim，行为不变。"""
    from app.services.proii_parser import map_libid_to_alias

    assert map_libid_to_alias("H2O") == "WATER"
    assert map_libid_to_alias("C38") == "C38"
    assert map_libid_to_alias("h2o") == "WATER"
    assert map_libid_to_alias("") == ""


def test_proii_component_aliases_backward_compat_shim():
    """`PROII_COMPONENT_ALIASES` 保留作为 shim（属性直接 = COMPONENT_NAME.entries）。"""
    from app.services.proii_parser import PROII_COMPONENT_ALIASES

    # 兼容旧测试：17 项 LIBID 必含
    assert len(PROII_COMPONENT_ALIASES) >= 17
    must_have = {"H2O", "CO2", "H2S", "N2", "O2", "H2", "NH3", "C1",
                 "C2", "C3", "CO", "SO2", "HCL", "CL2", "NC4", "IC4", "NC5"}
    missing = must_have - PROII_COMPONENT_ALIASES.keys()
    assert not missing, f"missing: {missing}"


# ---------------------------------------------------------------------------
# excel_parser.COMPONENT_ALIASES 整合
# ---------------------------------------------------------------------------


def test_excel_component_aliases_migrated():
    """excel_parser 原 3 项 COMPONENT_ALIASES 已合并入 registry，导入路径仍兼容。"""
    from app.services.excel_parser import COMPONENT_ALIASES  # noqa: F401

    assert "H2O" in COMPONENT_ALIASES
    assert COMPONENT_ALIASES["H2O"] == "WATER"


# ---------------------------------------------------------------------------
# Excel 模板 Sheet3 自动消费新组
# ---------------------------------------------------------------------------


def test_excel_template_includes_aliases_from_registry():
    """generate_excel_template Sheet3 输出 ≥50 行（来自 registry 的 ALIAS 组）。"""
    from io import BytesIO

    from openpyxl import load_workbook

    from app.services.import_service import generate_excel_template

    buf = generate_excel_template()
    wb = load_workbook(filename=BytesIO(buf))
    ws3 = wb["别名表"]
    rows = list(ws3.iter_rows(min_row=2, values_only=True))  # 跳过表头
    # Sheet3 行数 ≥ 50 + 至少 4 个不同 Group 列
    assert len(rows) >= 50, f"Sheet3 行数 {len(rows)} < 50"
    groups = {r[0] for r in rows if r[0]}
    assert "COMPONENT_NAME" in groups
    assert "UNIT_CONVERSION" in groups
    assert "EXCEL_COLUMN" in groups
    assert "VALIDATOR_FIELD" in groups


# ---------------------------------------------------------------------------
# Sheet3 列结构契约（SIM-30 决议：4 列）
# ---------------------------------------------------------------------------


def test_excel_template_sheet3_columns():
    """Sheet3 表头 = [Group, Alias, Standard, Factor]。"""
    from io import BytesIO

    from openpyxl import load_workbook

    from app.services.import_service import generate_excel_template

    wb = load_workbook(filename=BytesIO(generate_excel_template()))
    ws3 = wb["别名表"]
    header = [c.value for c in ws3[1]]
    assert header == ["Group", "Alias", "Standard", "Factor"]


def test_excel_template_sheet3_unit_conversion_has_factors():
    """Sheet3 UNIT_CONVERSION 行的 Factor 列应有数值（ALIAS_WITH_FACTOR）。"""
    from io import BytesIO

    from openpyxl import load_workbook

    from app.services.import_service import generate_excel_template

    wb = load_workbook(filename=BytesIO(generate_excel_template()))
    ws3 = wb["别名表"]
    # 找到 UNIT_CONVERSION 行
    uc_rows = [r for r in ws3.iter_rows(min_row=2, values_only=True) if r[0] == "UNIT_CONVERSION"]
    assert len(uc_rows) >= 12
    for row in uc_rows:
        assert row[3] not in (None, ""), f"UNIT_CONVERSION row 缺 Factor: {row}"


def test_excel_template_sheet3_component_name_factor_empty():
    """Sheet3 COMPONENT_NAME 行的 Factor 列为空（纯 ALIAS）。"""
    from io import BytesIO

    from openpyxl import load_workbook

    from app.services.import_service import generate_excel_template

    wb = load_workbook(filename=BytesIO(generate_excel_template()))
    ws3 = wb["别名表"]
    cn_rows = [r for r in ws3.iter_rows(min_row=2, values_only=True) if r[0] == "COMPONENT_NAME"]
    assert len(cn_rows) >= 25
    for row in cn_rows:
        assert row[3] in (None, ""), f"COMPONENT_NAME row Factor 应空: {row}"
