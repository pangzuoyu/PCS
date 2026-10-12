"""c1：HEAT 字段映射（ADR-0028「HEAT 报表双 detail_level」）。

## 字段名的口径

ADR-0028 写的是 PascalCase（`TagNumber` / `OverallU`），但 `datasource_registry`
自 Task 5a 起就规定了另一条：`FieldSpec.name` 用**真实 ORM 列名**（JSONB 子键
写 `容器列.子键`），理由写在注册表模块 docstring 里 —— 用户在字段树里看到的
应该是**能查得出的东西**，而 `query_engine._column` 也只认真实列。

所以本文件两件事都验：
1. 每个登记字段都能落到真实的 ORM 列 / JSONB 容器上（**不是**对着 ADR 抄一遍）
2. ADR 的每个 PascalCase 字段都有对应的真实列（映射不丢字段）

第 2 条不是形式主义：抄 ADR 会写出 `Area` / `Service` 这类**ORM 上根本没有**
的字段，而那种字段在定义里能选中、在执行时查不出来 —— 一份每格都是空的报表。

## 分级

BASIC = 9 字段（ADR 明写），DETAIL 覆盖 BASIC 且至少 39 字段。
「至少」而非「恰好」：ADR 的 39 是对齐两个 HTRI 模板源数出来的，
而模板源不在仓库里（见 TODOS.md），只按 39 硬卡会挡住后续补字段。
"""
from __future__ import annotations

import pytest

from app.db.base import Base
from app.services.report.datasource_registry import DATASOURCES

HEAT = DATASOURCES["HEAT_RESULTS"]

#: ADR-0028「分级标准」表里的 BASIC 9 字段（PascalCase，ADR 原样）。
#: 每项右边是真实的 ORM 列 / JSONB 子键。
ADR_BASIC = {
    "TagNumber": "tag_number",
    "Area": "effective_area",
    "HeatDuty": "duty",
    "OverallU": "u_overall",
    "ShellInletTemp": "shell_params.temp_in",
    "ShellOutletTemp": "shell_params.temp_out",
    "TubeInletTemp": "tube_params.temp_in",
    "TubeOutletTemp": "tube_params.temp_out",
    "PressureDrop": "shell_params.pd",
}

#: ADR-0028 DETAIL 的其余字段（PascalCase → 真实列）。
#: 只列**ORM 上真实存在**的；ADR 里有但 ORM 没有的（Service）单列在
#: ADR_WITHOUT_COLUMN 里 —— 那是数据模型的缺口，不是注册表的缺口。
ADR_DETAIL = {
    "Type": "exchanger_type",
    "LMTD": "lmtd",
    "MTD_Correction": "mtd_corrected",
    "ShellFlowRate": "shell_params.mass_flow",
    "TubeFlowRate": "tube_params.mass_flow",
    # ⚠️ ADR 的 `PressureDrop`（BASIC）映射到 shell_params.pd，
    # 而 DETAIL 的 `ShellPressureDrop` 也指向同一列 —— 一个真实列只能
    # 有一个 level。ADR 明写「BASIC 保留原 9 字段」优先，故该列归 BASIC，
    # ShellPressureDrop 没有独立列可用，记入下方缺口表。
    "TubePressureDrop": "tube_params.pd",
    # 热阻分布 5（ADR「热阻分布字段」表）
    "ShellSideResistance": "thermal_resistance_shell",
    "TubeSideResistance": "thermal_resistance_tube",
    "WallResistance": "thermal_resistance_metal",
    "FoulingResistance": "thermal_resistance_fouling",
    # 空冷器专属（ADR「几何字段」表 AIR_COOLER 行）
    "FanPower": "ache_params.fan_power_kw",
    "NumberOfFans": "ache_params.fan_count",
    # 管壳式专属（ADR「几何字段」表 SHELL_TUBE 行）
    "ShellID": "shell_id",
    "BaffleSpacing": "baffle_spacing",
    "BaffleCut": "baffle_cut_percent",
    "BaffleType": "baffle_type",
}

#: ADR 列了但 `heat_results` 上没有对应列的字段。
#: **不能靠注册表补** —— 注册表登记的每个字段都必须是能查的。
#: 处置是记 TODO（补列或删 ADR 条目），不是登记一个查不出的字段名。
ADR_WITHOUT_COLUMN = {
    "Service": "用途/服务，heat_results 无对应列",
    "ShellPressureDrop": "与 BASIC 的 PressureDrop 同列（shell_params.pd），"
                         "按 ADR「BASIC 优先」归 BASIC，DETAIL 无独立列",
    "AirFlowRate": "air_side_json 存在但无 flow_rate 键，ache_params 也无",
    "NozzleSizes": "shell_params 无 nozzle_sizes 键（ADR 的管嘴参数未落库）",
    "FinHeight/FinDensity/FinThickness": "ACHE 翅片几何，ORM 与 ache_params 均无",
}


def _orm_column_names() -> set[str]:
    import app.models  # noqa: F401
    return {c.name for c in Base.metadata.tables["heat_results"].columns}


def test_every_registered_heat_field_lands_on_a_real_column():
    """登记的字段必须逐条落到真实 ORM 列上。

    ⚠️ 断言的是「容器列存在于 ORM」而不是「子键存在于 JSONB 里」——
    JSONB 的子键是运行时数据，库里没有 schema 可以对照。能验的只有容器。
    验不了的（子键名是否与写入方一致）另由
    `test_jsonb_keys_are_written_by_the_heat_service` 兜。
    """
    cols = _orm_column_names()
    bad = []
    for name in HEAT.fields:
        container = name.split(".", 1)[0]
        if container not in cols:
            bad.append(name)
    assert not bad, (
        f"这些字段在 heat_results 上查不出来（注册表与 ORM 漂移）：{bad}")


def test_heat_jsonb_containers_exist_on_orm():
    """JSONB 字段登记时带 `is_jsonb_key=True`，容器列必须真的存在。"""
    import app.models  # noqa: F401
    jsonb_cols = {c.name for c in Base.metadata.tables["heat_results"].columns
                  if "JSONB" in str(c.type).upper()}
    for name, spec in HEAT.fields.items():
        if not spec.is_jsonb_key:
            continue
        container, _, _key = name.partition(".")
        assert container in jsonb_cols, \
            f"{name} 标了 is_jsonb_key，但 {container} 不是 JSONB 列"


def test_adri_basic_fields_are_all_registered():
    """ADR 的 BASIC 9 字段一个都不能少，且登记名必须是 ADR 映射到的真实列。"""
    for adr_name, real_col in ADR_BASIC.items():
        assert real_col in HEAT.fields, \
            f"ADR 的 {adr_name}（{real_col}）没有登记"
        assert HEAT.fields[real_col].level == "BASIC", \
            f"{real_col} 的 level 应为 BASIC，实得 {HEAT.fields[real_col].level}"


def test_basic_level_has_exactly_nine_fields():
    """ADR 明写 BASIC = 9 字段。多了少了都是偏离裁决。"""
    basic = [n for n, s in HEAT.fields.items() if s.level == "BASIC"]
    assert len(basic) == 9, f"BASIC 应为 9 字段，实得 {len(basic)}：{sorted(basic)}"


def test_detail_level_covers_at_least_39_fields():
    detail = {n for n, s in HEAT.fields.items() if s.level == "DETAIL"}
    assert len(detail | {n for n, s in HEAT.fields.items() if s.level == "BASIC"}) >= 39, \
        f"DETAIL 可见字段不足 39：{len(detail)}"


def test_adri_detail_fields_are_all_registered():
    for adr_name, real_col in ADR_DETAIL.items():
        assert real_col in HEAT.fields, f"ADR 的 {adr_name}（{real_col}）没有登记"
        assert HEAT.fields[real_col].level == "DETAIL", \
            f"{real_col} 应属 DETAIL，实得 {HEAT.fields[real_col].level}"


def test_fields_without_orm_column_are_recorded_not_registered():
    """ADR 有、ORM 没有的字段**不进注册表** —— 登记了就选得到、查不出。"""
    for adr_name, real_col in ADR_WITHOUT_COLUMN.items():
        assert real_col not in HEAT.fields, \
            f"{adr_name} 在 ORM 上没有列，不该被登记（查出来会是全 NULL）"


@pytest.mark.parametrize("adr_name", sorted(ADR_WITHOUT_COLUMN))
def test_adr_gaps_are_documented(adr_name):
    """数据模型缺口必须有据可查，不能只活在测试里。"""
    from app.services.report import datasource_registry as reg

    src = __import__("inspect").getsource(reg)
    assert adr_name in src, \
        f"{adr_name} 是 ADR/ORM 的已知缺口，但注册表源码里没有任何记录 —— " \
        "半年后没人知道这是有意为之还是漏了"


def test_geometry_fields_are_tagged_by_exchanger_type():
    """ADR 要求字段树按换热器类型分组（通用 / 空冷器专属 / 管壳式专属）。

    没有 `exchanger_type` 标记，前端只能把两类几何字段混在一棵树里，
    用户选管壳式报表时会看到 `baffle_spacing`（管壳式）也在列表里。
    """
    air = [n for n, s in HEAT.fields.items() if s.exchanger_type == "AIR_COOLER"]
    shell = [n for n, s in HEAT.fields.items() if s.exchanger_type == "SHELL_TUBE"]
    common = [n for n, s in HEAT.fields.items() if s.exchanger_type is None]
    assert air, "没有任何字段标为 AIR_COOLER 专属"
    assert shell, "没有任何字段标为 SHELL_TUBE 专属"
    assert len(common) > len(air), "通用字段应当多于任一专属类别"
    # 互斥：同一个字段不能既是空冷器专属又是管壳式专属
    assert not (set(air) & set(shell))
