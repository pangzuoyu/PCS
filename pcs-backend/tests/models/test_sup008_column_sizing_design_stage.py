"""P5-OPEN-005 V1.3 落地遗漏补齐：column_sizing design_stage 列存在性。

SUP-008 §8.4 OPEN-009：VESSEL/PSV/COLUMN 三表 design_stage NOT NULL
（BASIC default）。column_sizing 表 design_stage 字段已由 P5-OPEN-005
迁移落地，但 pcs_test DB 校验一直 FAIL（CAVEAT-1 测试集），本测试确认
ORM 字段 + DB 列均存在 + server_default 'BASIC'。

P6-3 Task 30 迁移 p6_3_002 以 ADD COLUMN IF NOT EXISTS 兜底：DB 已有则
no-op；DB 缺失则补 NOT NULL + server_default 'BASIC'。
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect as _inspect
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import dispose_engines_async, get_async_session_factory
from app.models.calc import ColumnSizingResult

# 仅 pcs_test 库生效（防误查 pcs 开发库）
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason="DB schema 校验仅允许 pcs_test 库（防误查 pcs 开发库）；"
    "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test",
)


def test_column_sizing_orm_has_design_stage_column() -> None:
    """ColumnSizingResult ORM 必须含 design_stage 列（SUP-008 §8.4 OPEN-009）。"""
    cols = {c.key for c in _inspect(ColumnSizingResult).columns}
    assert "design_stage" in cols, (
        f"ColumnSizingResult 缺 design_stage 列：{sorted(cols)}"
    )


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_column_sizing_db_design_stage_column_exists() -> None:
    """pcs_test 库 column_sizing 表 design_stage 列存在（DB schema 校验）。"""
    await dispose_engines_async()
    try:
        factory = get_async_session_factory()
        async with factory() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = 'column_sizing'
                          AND column_name = 'design_stage'
                        """
                    )
                )
            ).mappings().one()
        assert row is not None, "column_sizing.design_stage 列在 pcs_test 库缺失"
        # V1.3 落地遗漏：NOT NULL 约束
        assert row["is_nullable"] == "NO", (
            f"column_sizing.design_stage 应 NOT NULL，实际 is_nullable={row['is_nullable']}"
        )
    finally:
        await dispose_engines_async()


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_column_sizing_db_design_stage_server_default_basic() -> None:
    """pcs_test 库 column_sizing.design_stage server_default = 'BASIC'。

    V1.3 落地遗漏补齐：P6-3 Task 30 迁移以 ADD COLUMN IF NOT EXISTS 兜底，
    缺列时补 NOT NULL DEFAULT 'BASIC'。
    """
    await dispose_engines_async()
    try:
        factory = get_async_session_factory()
        async with factory() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT column_default
                        FROM information_schema.columns
                        WHERE table_name = 'column_sizing'
                          AND column_name = 'design_stage'
                        """
                    )
                )
            ).mappings().one()
        default = (row["column_default"] or "").lower()
        assert "basic" in default, (
            f"column_sizing.design_stage server_default 应含 'BASIC'，"
            f"实际={default!r}"
        )
    finally:
        await dispose_engines_async()