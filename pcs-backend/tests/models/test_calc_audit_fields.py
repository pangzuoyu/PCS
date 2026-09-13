"""P4-0-1 审计字段迁移验证测试。

验证 pcs_test 库已运行 ``p4_calc_audit_fields``：
streams / piping_results / pump_results / flash_results / pipe_network_results
五表各加 3 列：
- stale_resolution_path character varying(30) NULL
- hash_changed boolean NULL default false
- changed_fields jsonb NULL

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

_TABLES = (
    "streams",
    "piping_results",
    "pump_results",
    "flash_results",
    "pipe_network_results",
)

# 列名 → (data_type, character_maximum_length)
_EXPECTED_TYPES = {
    "stale_resolution_path": ("character varying", 30),
    "hash_changed": ("boolean", None),
    "changed_fields": ("jsonb", None),
}

# 安全守卫：仅当 database_url 指向 pcs_test 才执行（仿 test_alembic_roundtrip）
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


@_ONLY_PCS_TEST
@pytest.mark.asyncio
@pytest.mark.parametrize("table", _TABLES)
async def test_audit_three_columns_exist(table: str) -> None:
    """存在性：3 审计列均在且可空（is_nullable = YES）。"""
    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    text(
                        """
                        SELECT column_name, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = :t
                          AND column_name IN (
                              'stale_resolution_path', 'hash_changed', 'changed_fields'
                          )
                        """
                    ),
                    {"t": table},
                )
            )
            .mappings()
            .all()
        )
    got = {r["column_name"]: r["is_nullable"] for r in rows}
    assert got == {c: "YES" for c in _EXPECTED_TYPES}, f"{table}: {got}"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
@pytest.mark.parametrize("table", _TABLES)
async def test_audit_column_types(table: str) -> None:
    """类型断言：varchar(30) / boolean / jsonb。"""
    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    text(
                        """
                        SELECT column_name, data_type, character_maximum_length
                        FROM information_schema.columns
                        WHERE table_name = :t
                          AND column_name IN (
                              'stale_resolution_path', 'hash_changed', 'changed_fields'
                          )
                        """
                    ),
                    {"t": table},
                )
            )
            .mappings()
            .all()
        )
    got = {
        r["column_name"]: (r["data_type"], r["character_maximum_length"]) for r in rows
    }
    assert got == _EXPECTED_TYPES, f"{table}: {got}"
