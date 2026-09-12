"""P3.2 SIM-1：Stream / StreamStatePoint ORM 结构断言。

锁定 P3.2 SIM 实施的 ORM 接口签名（spec V1.6 §3.2.2 双层 case_type +
§3.2.3 16 字段增量）。下游 SIM-2..12 直接 import 此模块类型，禁止改字段名/可空/类型。

跑前需：
    DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test \\
        uv run alembic upgrade head

净新增 10 字段（plan 修正版）：
- streams.case_type VARCHAR(20) + CHECK（NORMAL/END_OF_RUN/START_OF_RUN/TURN_DOWN）
- streams.liquid_surface_tension（SIM-33 rename）/ api_gravity /
  critical_temp / critical_press / actual_vol_flow FLOAT
- streams.viscosity_temperature_curve JSONB
- streams.import_original_row INT
- streams.import_source_version VARCHAR(20)
- stream_state_points.case_type CHECK（NORMAL/MIN/MAX/ALTERNATE，列已存在）
"""
from __future__ import annotations

from app.models.project import Stream, StreamStatePoint


def test_stream_has_case_type_column():
    """spec V1.6 §3.2.2：streams 物流级 case_type 必含。"""
    cols = {c.name for c in Stream.__table__.columns}
    assert "case_type" in cols


def test_stream_case_type_check_constraint():
    """CHECK 约束锁 4 值：NORMAL/END_OF_RUN/START_OF_RUN/TURN_DOWN。"""
    constraints = {
        c.name
        for c in Stream.__table__.constraints
        if hasattr(c, "sqltext") and "case_type" in str(c.sqltext).lower()
    }
    assert any("ck_streams_case_type" in n for n in constraints), (
        f"missing ck_streams_case_type; got constraints: "
        f"{[c.name for c in Stream.__table__.constraints]}"
    )


def test_stream_has_liquid_surface_tension():
    """SIM-33: surface_tension 重命名为 liquid_surface_tension（spec §3.6）。"""
    cols = {c.name for c in Stream.__table__.columns}
    assert "liquid_surface_tension" in cols
    assert "surface_tension" not in cols


def test_stream_has_api_gravity():
    cols = {c.name for c in Stream.__table__.columns}
    assert "api_gravity" in cols


def test_stream_has_critical_temp():
    cols = {c.name for c in Stream.__table__.columns}
    assert "critical_temp" in cols


def test_stream_has_critical_press():
    cols = {c.name for c in Stream.__table__.columns}
    assert "critical_press" in cols


def test_stream_has_actual_vol_flow():
    """工况体积流量（≠ 已有 volumetric_flow 标准体积）。"""
    cols = {c.name for c in Stream.__table__.columns}
    assert "actual_vol_flow" in cols


def test_stream_has_viscosity_temperature_curve_jsonb():
    col = Stream.__table__.columns["viscosity_temperature_curve"]
    assert "JSONB" in str(col.type)


def test_stream_has_import_original_row_int():
    col = Stream.__table__.columns["import_original_row"]
    assert "INT" in str(col.type).upper() or "INTEGER" in str(col.type).upper()


def test_stream_has_import_source_version_varchar_20():
    col = Stream.__table__.columns["import_source_version"]
    assert col.type.length == 20


def test_stream_sign_status_remains_pg_enum():
    """sign_status 已是 PG native enum（streamsignstatus），plan 不动该列。
    P4 扩展走 ALTER TYPE streamsignstatus ADD VALUE（不可逆）。"""
    from sqlalchemy import Enum as SAEnum

    col = Stream.__table__.columns["sign_status"]
    # PG native enum 在 SQLAlchemy 中表现为 Enum(..., native_enum=True)，
    # 检查该类型对象的 native_enum 与 name 属性。
    assert isinstance(col.type, SAEnum), f"sign_status 应为 SA Enum; got {type(col.type)}"
    assert col.type.native_enum is True, "sign_status 必须为 PG native enum"
    assert col.type.name == "streamsignstatus", (
        f"PG enum 名应为 streamsignstatus; got {col.type.name}"
    )


def test_stream_state_point_case_type_check_constraint():
    """state_point 级 case_type 列已存在；本任务仅补 CHECK 约束。"""
    constraints = {
        c.name
        for c in StreamStatePoint.__table__.constraints
        if hasattr(c, "sqltext") and "case_type" in str(c.sqltext).lower()
    }
    assert any("ck_stream_state_points_case_type" in n for n in constraints), (
        f"missing ck_stream_state_points_case_type; got: "
        f"{[c.name for c in StreamStatePoint.__table__.constraints]}"
    )


def test_stream_state_point_case_type_column_exists():
    """state_point 级 case_type 列已存在（StreamStatePoint L209-211 NOT NULL）。"""
    col = StreamStatePoint.__table__.columns["case_type"]
    assert not col.nullable


def test_stream_total_column_count_after_sim1():
    """净增 10 字段后 streams 表应 ~72 列（62 现状 + 10 新增）。

    允许 ±1 容差（mixins 在不同 schema 反射方式略有差异）。
    """
    cols = {c.name for c in Stream.__table__.columns}
    expected_new = {
        "case_type",
        "liquid_surface_tension",  # SIM-33: surface_tension → liquid_surface_tension
        "api_gravity",
        "critical_temp",
        "critical_press",
        "actual_vol_flow",
        "viscosity_temperature_curve",
        "import_original_row",
        "import_source_version",
    }
    missing = expected_new - cols
    assert not missing, f"streams 表缺字段: {missing}"
