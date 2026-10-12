"""数据源注册表契约（纯元数据）。

三个闸：
1. **数量**：SPEC §3.2.2(1) 定死 13 个数据源，多一个是超范围，少一个是缺口。
2. **JOIN 白名单**：SPEC §1.3 只批 5 对，多一条都不行（P8-OPEN-005 关闭决议）。
3. **registry ↔ ORM 一致性**：登记的字段必须真在表上（列或 JSONB 子键）——
   ORM 改字段名而 registry 不改，用户在 REPORT_BUILDER 字段树里点到那个字段
   才报 500，这是「契约一端不存在」的经典漂移（架构审查发现，参照
   check_payload_model_coverage.py 模式）。
"""
import pytest

from app.db.base import Base
from app.services.exceptions import PcsError
from app.services.report.datasource_registry import (
    DATASOURCES,
    JOINS,
    join_key_for,
)


def test_thirteen_datasources_registered():
    assert len(DATASOURCES) == 13
    assert set(DATASOURCES) == {
        "EQUIP_LIST", "PIPING_RESULTS", "STREAMS", "PSV_RESULTS", "PUMP_RESULTS",
        "VESSEL_RESULTS", "HEAT_RESULTS", "UTIL_RESULTS", "INPUT_CHECKLIST",
        "DATALINEAGE", "PROJECTS", "SUPPLIERS", "CONFIG_ASSETS",
    }


def test_each_datasource_has_tag_and_core_fields():
    """每个数据源至少 3 个字段 —— 空注册等于没有这个数据源。"""
    for key, ds in DATASOURCES.items():
        assert len(ds.fields) >= 3, f"{key} 字段过少：{list(ds.fields)}"
        for fname, spec in ds.fields.items():
            assert spec.type in ("string", "number", "date", "enum"), \
                f"{key}.{fname} 非法类型 {spec.type}"
            assert spec.label, f"{key}.{fname} 缺中文标签"


def test_join_rules_match_spec_whitelist():
    """SPEC §1.3 只批了 5 对 JOIN，多一条都不行。"""
    assert len(JOINS) == 5
    assert join_key_for("EQUIP_LIST", "PUMP_RESULTS") == ("tag_number", "tag_number")
    assert join_key_for("EQUIP_LIST", "VESSEL_RESULTS") == ("tag_number", "tag_number")
    assert join_key_for("EQUIP_LIST", "HEAT_RESULTS") == ("tag_number", "tag_number")
    assert join_key_for("EQUIP_LIST", "PSV_RESULTS") == ("tag_number", "tag_number")
    # 第 5 对：SPEC 授权的降级 —— equipment_list 无 vendor_id，
    # 按 EQUIP_LIST.vendor = SUPPLIERS.supplier_name 关联（WARN 级）
    assert join_key_for("EQUIP_LIST", "SUPPLIERS") == ("vendor", "supplier_name")


def test_join_is_symmetric():
    """join_key_for(a,b) 与 (b,a) 返回镜像 —— 调用方不该关心源的顺序。"""
    a, b = join_key_for("EQUIP_LIST", "PUMP_RESULTS")
    b2, a2 = join_key_for("PUMP_RESULTS", "EQUIP_LIST")
    assert (a, b) == (a2, b2)


def test_unsupported_join_raises_explicit_error():
    with pytest.raises(PcsError) as e:
        join_key_for("EQUIP_LIST", "STREAMS")
    assert e.value.code == "REPORT_BUILDER_JOIN_NOT_SUPPORTED"
    assert e.value.status == 400


def test_join_fields_exist_in_orm():
    """JOIN 键也必须真在表上 —— 键不存在，白名单就是纸面的。"""
    for j in JOINS:
        for key, field in ((j.a, j.a_field), (j.b, j.b_field)):
            table = Base.metadata.tables[DATASOURCES[key].model]
            assert field in table.columns.keys(), \
                f"JOIN 键 {key}.{field} 不在表 {DATASOURCES[key].model} 上"


def test_registry_fields_exist_in_orm():
    """**registry 与 ORM 会漂移的闸**（架构审查发现）。

    ORM 改字段名而 registry 不改 → REPORT_BUILDER 的字段树指向不存在的列，
    用户点进去才报 500。
    """
    for key, ds in DATASOURCES.items():
        cols = set(Base.metadata.tables[ds.model].columns.keys())
        for fname, spec in ds.fields.items():
            if fname in cols:
                continue
            # JSONB 容器里的已知键允许不在列上（如 pump 的 flow_m3_s）
            assert spec.is_jsonb_key, f"{key}.{fname} 在 ORM 表 {ds.model} 里不存在"
            container = fname.split(".", 1)[0]
            assert container in cols, \
                f"{key}.{fname} 的容器列 {container} 也不在表上 —— 键名编错了"


def test_piping_maps_to_line_list_table():
    """PIPING_RESULTS 是「管道一览表」→ piping_results（83 列的线表），
    **不是** pipe_network_results（水力计算网络结果）。

    这两个名字只差一个词，语义完全不同。钉住映射，防止后人「顺手改对仗」。"""
    assert DATASOURCES["PIPING_RESULTS"].model == "piping_results"
    assert "line_no" in DATASOURCES["PIPING_RESULTS"].fields


def test_registry_has_no_query_logic():
    """本模块**只放元数据** —— 出现 select/execute/text 即违宪（查询在 T5b）。"""
    import inspect

    from app.services.report import datasource_registry as m

    src = inspect.getsource(m)
    for banned in ("select(", "session.execute", "text(", "sqlalchemy"):
        assert banned not in src, f"注册表里出现了查询逻辑：{banned}"