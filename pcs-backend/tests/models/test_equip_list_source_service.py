"""P7 Task S1-2：equipment_list 补 SourceService（SPEC V1.4 §3.2.1（2）来源组 V1.4 新增）。

背景（R=1 source-verify 结论，见 .superpowers/sdd/2026-10-01-p7-complete-sprint/
task-s1-2-report.md）：

- `EquipmentList` ORM **早已存在**（app/models/equipment.py:58），映射
  `equipment_list` 表 96 列，字段组逐条对应 DICT-002 §3.1–§3.5 /
  SPEC V1.4 §3.2.1（2）十字段组（§一来源 ~ §九工程），历史迁移
  dd47298c9c38（建表）+ p1_sprint3_equipment_status_columns（3 状态列）已落。
- plan brief 的「新建 app/models/equip_list.py 重建 EquipmentList」前提不成立：
  同一 MetaData 内重复映射 `equipment_list` 会直接抛
  `InvalidRequestError: Table 'equipment_list' is already defined`，且 brief
  代码块的部分列名（po_number / gpe_spec / data_sources:JSON）与既有
  DICT-002 命名（purchase_order_number / gpe_spec_number / data_sources:String）
  冲突。故本任务按「加法补丁」执行：只在既有 ORM 上补 V1.4 唯一缺口
  `source_service`，并补迁移。

本测试覆盖 4 组契约：
1. V1.4 SourceService 列存在（String(64) 可空）+ 来源三件套完整
2. SPEC V1.4 §3.2.1（2）十字段组抽样仍在（防「加法补丁」误伤既有字段）
3. S1-1 三字段（stale_resolution_path / hash_changed / changed_fields）经
   TaggedRecordMixin 落在 equipment_list 上
4. `equipment_list` 只被注册一次（守卫 brief 的重复建表陷阱复发）

DB schema 校验见同文件 test_p7_s1_001_migration_*（迁移可逆性）。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import class_mapper

from app.models.equipment import EquipmentList

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_MIGRATION_PATH = (
    _BACKEND_DIR / "alembic" / "versions" / "p7_s1_001_equipment_list_source_service.py"
)


def _orm_columns(model) -> set[str]:
    """通过 SQLAlchemy Table 反射读取 ORM 字段名集合（沿用 test_psv_open_009 模式）。"""
    return {c.key for c in inspect(model).columns}


def _load_migration():
    spec = importlib.util.spec_from_file_location("p7_s1_001_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================================================================
# 1. V1.4 SourceService 列
# ============================================================================


def test_equipment_list_has_source_service_column() -> None:
    """equipment_list 必须含 source_service（SPEC V1.4 §3.2.1（2）来源组 V1.4 新增）。"""
    assert "source_service" in _orm_columns(EquipmentList), (
        "equipment_list 缺 V1.4 新增列 source_service（区分同模块多子服务，"
        "per SPEC V1.4 §3.2.1（2）来源组）"
    )


def test_source_service_is_nullable_string64() -> None:
    """source_service 契约：String(64) + 可空（历史行无来源服务，不回填）。"""
    col = EquipmentList.__table__.c.source_service
    assert isinstance(col.type, sa.String), f"source_service 应为 String，实为 {col.type!r}"
    assert col.type.length == 64, f"source_service 长度应为 64，实为 {col.type.length}"
    assert col.nullable, "source_service 应可空（V1.4 新增，历史行不回填）"


def test_equipment_list_source_traceability_trio_present() -> None:
    """溯源三件套完整：SourceModule + SourceService(V1.4) + SourceRecordID。"""
    cols = _orm_columns(EquipmentList)
    missing = {"source_module", "source_service", "source_record_id"} - cols
    assert not missing, f"设备记录溯源三件套缺列：{missing}"


# ============================================================================
# 2. SPEC V1.4 §3.2.1（2）十字段组抽样（防加法补丁误伤既有字段）
# ============================================================================


def test_equipment_list_spec_v14_field_groups_preserved() -> None:
    """SPEC V1.4 §3.2.1（2）十字段组各取代表列，全部仍在既有 ORM 上。"""
    field_groups = {
        "标识": ("tag_number", "equipment_description", "equipment_name_cn", "package_no"),
        "类型": ("type_code", "equipment_sub_type", "equipment_category", "is_pressure_vessel"),
        "来源": ("source_module", "source_service", "source_record_id", "in_package",
                 "data_sources"),
        "状态": ("equipment_status", "calc_status", "sign_status", "actual_data_status"),
        "设计参数": ("design_parameters_json",),
        "采购": ("vendor", "alternate_vendor", "order_date", "purchase_order_number",
                 "cost", "gpe_spec_number"),
        "图纸": ("approval_drawing_received_date", "certified_drawing_received_date"),
        "交付": ("delivery_date", "actual_received_date", "forecast_on_site",
                 "storage_location"),
        "安装": ("installation_location", "installation_contract_number",
                 "installation_notes"),
        "重量": ("empty_weight", "full_weight", "weigh_cells", "net_weight"),
        "工程": ("process_engineer", "detail_engineer", "flowsheet_drawing_number",
                 "pid_drawing_number"),
    }
    cols = _orm_columns(EquipmentList)
    missing = {
        group: [c for c in expected if c not in cols]
        for group, expected in field_groups.items()
    }
    missing = {group: gaps for group, gaps in missing.items() if gaps}
    assert not missing, f"SPEC V1.4 §3.2.1（2）字段组缺列：{missing}"


# ============================================================================
# 3. S1-1 三字段（RecordMixin 链）
# ============================================================================


def test_equipment_list_carries_s1_1_audit_trio() -> None:
    """S1-1 三字段经 TaggedRecordMixin 落在 equipment_list 上（门禁审计前置）。"""
    missing = {"stale_resolution_path", "hash_changed", "changed_fields"} - _orm_columns(
        EquipmentList
    )
    assert not missing, f"equipment_list 缺 S1-1 审计三字段：{missing}"


# ============================================================================
# 4. equipment_list 只注册一次（守卫 brief 重复建表陷阱）
# ============================================================================


def test_equipment_list_table_registered_once() -> None:
    """`equipment_list` 在 Base.metadata 中只映射一次（plan brief 曾要求新建同名 ORM）。

    同 MetaData 重复映射同一表名会在 import 期抛 InvalidRequestError；此断言在
    SQLite create_all 之前就把「第二个 equipment_list ORM」的复发挡在测试层。
    """
    import app.models  # noqa: F401  # 触发全部 ORM 注册
    from app.db.base import Base

    assert "equipment_list" in Base.metadata.tables, "equipment_list 未注册到 metadata"

    mapped_classes = [
        mapper.class_
        for mapper in Base.registry.mappers
        if mapper.local_table is Base.metadata.tables["equipment_list"]
    ]
    assert len(mapped_classes) == 1, (
        f"equipment_list 被 {len(mapped_classes)} 个 ORM 类映射：{mapped_classes}；"
        "同名重复映射会在 import 期抛 InvalidRequestError"
    )
    assert mapped_classes[0] is EquipmentList
    # 反查 sanity：EquipmentList 确实映射到该表（避免 class_mapper 未触达）
    assert class_mapper(EquipmentList).local_table.name == "equipment_list"


# ============================================================================
# 5. 迁移 p7_s1_001 可逆性（SQLite in-memory，不依赖 pcs_test）
# ============================================================================


def _sqlite_engine_with_stub_equipment_list():
    """建一个最小 equipment_list 桩表（SQLite in-memory）。

    真实链路上该表 96 列由 dd47298c9c38 + p1_sprint3 建出；本测试只关心
    p7_s1_001 的 add_column / drop_column 互逆，故桩表够用且不依赖 pcs_test。
    """
    engine = create_engine("sqlite://")
    with engine.connect() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE equipment_list ("
                "  equipment_id CHAR(32) PRIMARY KEY,"
                "  tag_number VARCHAR(50)"
                ")"
            )
        )
        conn.commit()
    return engine


def _column_names(engine) -> set[str]:
    with engine.connect() as conn:
        return {c["name"] for c in inspect(conn).get_columns("equipment_list")}


def test_p7_s1_001_migration_adds_then_drops_source_service() -> None:
    """p7_s1_001：upgrade 加 source_service，downgrade 精确还原（双向可逆）。"""
    mod = _load_migration()
    assert mod.revision == "p7_s1_001"

    engine = _sqlite_engine_with_stub_equipment_list()
    assert "source_service" not in _column_names(engine)

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mod.upgrade()
        conn.commit()
    after_up = _column_names(engine)
    assert "source_service" in after_up, f"upgrade 未加 source_service：{sorted(after_up)}"
    assert "tag_number" in after_up, "upgrade 误伤既有列"

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mod.downgrade()
        conn.commit()
    after_down = _column_names(engine)
    assert "source_service" not in after_down, "downgrade 未删 source_service"
    assert after_down == {"equipment_id", "tag_number"}, (
        f"downgrade 未精确还原 schema：{sorted(after_down)}"
    )
    engine.dispose()


def test_p7_s1_001_chains_on_previous_head() -> None:
    """p7_s1_001 的 down_revision 指向本迁移落地前的 alembic HEAD（单链不断裂）。"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    mod = _load_migration()
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)

    assert script.get_revision(mod.revision).down_revision == mod.down_revision, (
        "p7_s1_001 已入迁移图，但其 down_revision 与模块声明不一致"
    )
    assert script.get_revision(mod.down_revision) is not None, (
        f"down_revision {mod.down_revision} 不在迁移图中（迁移链断裂）"
    )
    # p7_s1_001 必须入图（未删改）：walk_revisions 含 p7_s1_001
    # 不断言 single-head —— 下一迁移（S1-3 / Sprint 2）落地即换 head。
    assert any(r.revision == mod.revision for r in script.walk_revisions()), (
        f"alembic 迁移图中无 {mod.revision}（迁移被删改或未入图）"
    )
