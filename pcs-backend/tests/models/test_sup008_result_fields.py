"""P4-0-2 SUP-008 表扩展迁移验证测试。

验证 pcs_test 库已运行 ``p4_sup008_result_fields``：

- piping_results +11 列（line_description / pipe_type / max_flow_factor /
  selected_diameter / liquid_velocity_max / gas_velocity_max /
  pressure_drop_per_100m / selected_pipe_size / recommended_pipe_size /
  check_result / velocity_range_reference）
- pump_results +5 列（selected_pump_model / selected_motor_model /
  selected_motor_power / pump_operation + design_stage(BASIC default)）
- psv_results / vessel_results +design_stage（BASIC default）
- two_phase_results 新表（13 列：PK + input/output JSONB + 业务字段 + 时间戳）
- 6 个 PG enum（pipe_type / check_result / pump_operation / design_stage /
  flow_pattern / two_phase_check）

跑前需（CLAUDE.md 测试前检查）：
    DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test \\
        uv run alembic upgrade head
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import dispose_engines_async, get_async_session_factory

# 列名 → (data_type, character_maximum_length)
_PIPING_COLS = {
    "line_description": ("character varying", 200),
    "max_flow_factor": ("double precision", None),
    "selected_diameter": ("double precision", None),
    "liquid_velocity_max": ("double precision", None),
    "gas_velocity_max": ("double precision", None),
    "pressure_drop_per_100m": ("double precision", None),
    "selected_pipe_size": ("character varying", 20),
    "recommended_pipe_size": ("character varying", 20),
    "velocity_range_reference": ("character varying", 100),
    # 2 个 enum（PG 渲染为 USER-DEFINED 类型，长度 None）
    "pipe_type": ("USER-DEFINED", None),
    "check_result": ("USER-DEFINED", None),
}

# 列名 → (data_type, character_maximum_length)
_PUMP_NEW_COLS = {
    "selected_pump_model": ("character varying", 100),
    "selected_motor_model": ("character varying", 100),
    "selected_motor_power": ("double precision", None),
    # 2 个 enum
    "pump_operation": ("USER-DEFINED", None),
    "design_stage": ("USER-DEFINED", None),
}

# two_phase_results 13 字段（含 PK + JSONB + 业务 + 时间戳）
# 注：Bx / By 是 PG 大小写敏感列（双字符全大写未自动小写）
_TWO_PHASE_COLS = {
    "two_phase_calc_id": ("uuid", None),
    "input_json": ("jsonb", None),
    "output_json": ("jsonb", None),
    "Bx": ("double precision", None),
    "By": ("double precision", None),
    "flow_pattern": ("USER-DEFINED", None),
    "two_phase_check": ("USER-DEFINED", None),
    "liquid_velocity": ("double precision", None),
    "gas_velocity": ("double precision", None),
    "pressure_gradient": ("double precision", None),
    "void_fraction": ("double precision", None),
    "calc_method": ("character varying", 50),
    "created_at": ("timestamp with time zone", None),
}

# 6 个 enum：类型名 → 期望值集合（顺序严格）
_ENUM_VALUES = {
    "pipe_type_enum": (
        "PUMP_SUCTION",
        "PUMP_DISCHARGE",
        "SELF_FLOW",
        "HEATING_STEAM",
        "TWO_PHASE",
    ),
    "check_result_enum": ("PASS", "FAIL", "WARNING"),
    "pump_operation_enum": ("NORMAL", "STANDBY", "OFF"),
    "design_stage_enum": ("BASIC", "DETAIL"),
    "flow_pattern_enum": (
        "ANNULAR",
        "MIST",
        "BUBBLE",
        "SLUG",
        "STRATIFIED",
        "WAVE",
    ),
    "two_phase_check_enum": ("PASS", "WARNING", "FAIL"),
}

# 安全守卫：仅当 database_url 指向 pcs_test 才执行（仿 test_calc_audit_fields）
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason="迁移验证仅允许 pcs_test 库；"
           "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test",
)


@pytest_asyncio.fixture(autouse=True)
async def _reset_async_engine() -> AsyncIterator[None]:
    """每次用例 reset 全局 async engine（绑定当前 event loop）。"""
    await dispose_engines_async()
    yield
    await dispose_engines_async()


async def _fetch_column_rows(table: str, cols: tuple[str, ...]) -> list[dict]:
    factory = get_async_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                """
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_name = :t
                  AND column_name = ANY(:cols)
                """
            ),
            {"t": table, "cols": list(cols)},
        )
        return [dict(r) for r in result.mappings().all()]


# === piping_results 11 列 ===

@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_piping_eleven_columns_exist() -> None:
    """piping_results 11 新列均存在且可空。"""
    rows = await _fetch_column_rows("piping_results", tuple(_PIPING_COLS))
    got = {r["column_name"]: r["is_nullable"] for r in rows}
    assert got == {c: "YES" for c in _PIPING_COLS}, f"piping_results: {got}"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_piping_column_types() -> None:
    """piping_results 11 新列类型断言。"""
    rows = await _fetch_column_rows("piping_results", tuple(_PIPING_COLS))
    got = {
        r["column_name"]: (r["data_type"], r["character_maximum_length"])
        for r in rows
    }
    assert got == _PIPING_COLS, f"piping_results: {got}"


# === pump_results 5 列 ===

@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_pump_five_columns_exist() -> None:
    """pump_results 5 新列：4 列 nullable + design_stage NOT NULL default BASIC。"""
    rows = await _fetch_column_rows("pump_results", tuple(_PUMP_NEW_COLS))
    got = {r["column_name"]: r["is_nullable"] for r in rows}
    # design_stage NOT NULL；其余可空
    expected_nullable = dict.fromkeys(_PUMP_NEW_COLS, "YES")
    expected_nullable["design_stage"] = "NO"
    assert got == expected_nullable, f"pump_results: {got}"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_pump_column_types() -> None:
    """pump_results 5 新列类型断言。"""
    rows = await _fetch_column_rows("pump_results", tuple(_PUMP_NEW_COLS))
    got = {
        r["column_name"]: (r["data_type"], r["character_maximum_length"])
        for r in rows
    }
    assert got == _PUMP_NEW_COLS, f"pump_results: {got}"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_pump_design_stage_server_default_basic() -> None:
    """pump_results.design_stage server_default = 'BASIC'::design_stage_enum。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT column_default
                    FROM information_schema.columns
                    WHERE table_name = 'pump_results'
                      AND column_name = 'design_stage'
                    """
                )
            )
        ).mappings().one()
    default = (row["column_default"] or "").lower()
    assert "basic" in default, f"pump_results.design_stage default={default!r}"


# === psv_results / vessel_results design_stage ===

@_ONLY_PCS_TEST
@pytest.mark.asyncio
@pytest.mark.parametrize("table", ["psv_results", "vessel_results"])
async def test_design_stage_column_exists_not_null(table: str) -> None:
    """psv_results / vessel_results 设计阶段列存在 + NOT NULL。"""
    rows = await _fetch_column_rows(table, ("design_stage",))
    assert rows and rows[0]["is_nullable"] == "NO", f"{table}: {rows}"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
@pytest.mark.parametrize("table", ["psv_results", "vessel_results"])
async def test_design_stage_server_default_basic(table: str) -> None:
    """psv_results / vessel_results 设计阶段 server_default = 'BASIC'。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT column_default
                    FROM information_schema.columns
                    WHERE table_name = :t
                      AND column_name = 'design_stage'
                    """
                ),
                {"t": table},
            )
        ).mappings().one()
    default = (row["column_default"] or "").lower()
    assert "basic" in default, f"{table}.design_stage default={default!r}"


# === two_phase_results 新表 ===

@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_two_phase_results_table_exists() -> None:
    """two_phase_results 表在 information_schema.tables 中存在。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_name = 'two_phase_results'
                      AND table_schema = 'public'
                    """
                )
            )
        ).mappings().one_or_none()
    assert row is not None, "two_phase_results 表不存在"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_two_phase_results_thirteen_columns() -> None:
    """two_phase_results 13 字段存在性 + 类型断言。"""
    rows = await _fetch_column_rows("two_phase_results", tuple(_TWO_PHASE_COLS))
    got = {
        r["column_name"]: (r["data_type"], r["character_maximum_length"])
        for r in rows
    }
    assert got == _TWO_PHASE_COLS, f"two_phase_results: {got}"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_two_phase_results_pk_is_uuid() -> None:
    """two_phase_calc_id 是 uuid 类型 PK。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_name = 'two_phase_results'
                      AND column_name = 'two_phase_calc_id'
                    """
                )
            )
        ).mappings().one()
    assert row["data_type"] == "uuid", f"PK type={row['data_type']!r}"


# === 6 个 PG enum 值域 ===

@_ONLY_PCS_TEST
@pytest.mark.asyncio
@pytest.mark.parametrize("type_name,expected", list(_ENUM_VALUES.items()))
async def test_enum_values(type_name: str, expected: tuple[str, ...]) -> None:
    """6 个 enum 存在 + 值集合完全等于预期（顺序严格）。"""
    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT enumlabel
                    FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    WHERE t.typname = :name
                    ORDER BY e.enumsortorder
                    """
                ),
                {"name": type_name},
            )
        ).scalars().all()
    assert tuple(rows) == expected, (
        f"{type_name}: expected={expected!r}, got={tuple(rows)!r}"
    )