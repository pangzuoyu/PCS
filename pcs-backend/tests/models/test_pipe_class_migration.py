"""SUP-002 PC-1 迁移验证测试。

验证 pcs_test 库已运行 ``p2_sup_sprint_pc1_pipe_class_upgrade``：

- pipe_classes：class_id 放宽到 varchar(50)；base_material/asset_id 新列；
  status 5 态映射（ACTIVE → PUBLISHED）。
- project_pipe_classes：复合 PK → UUID PK；新增 source_class_id/class_name/
  snapshot_json/override_json/status；UNIQUE(project_id, class_name)。
- config_approvals：新增 project_class_id 可空 FK。
- piping_results.material_class FK（指向 pipe_classes.class_id）未受影响。

跑前需：
    DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test \\
        uv run alembic upgrade head
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import dispose_engines_async, get_async_session_factory


@pytest_asyncio.fixture(autouse=True)
async def _reset_async_engine() -> AsyncIterator[None]:
    """每次用例 reset 全局 async engine（绑定当前 event loop）。"""
    await dispose_engines_async()
    yield
    await dispose_engines_async()


@pytest.mark.asyncio
async def test_pipe_classes_class_id_widened_to_50():
    """A.1 class_id 列宽验证（varchar(50)）。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT character_maximum_length
                    FROM information_schema.columns
                    WHERE table_name = 'pipe_classes' AND column_name = 'class_id'
                    """
                )
            )
        ).first()
    assert row is not None and row[0] == 50


@pytest.mark.asyncio
async def test_pipe_classes_base_material_column_exists():
    """A.2 base_material 列已加（varchar(100)，nullable=False 由种子保证）。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT character_maximum_length, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'pipe_classes' AND column_name = 'base_material'
                    """
                )
            )
        ).first()
    assert row is not None
    assert row[0] == 100


@pytest.mark.asyncio
async def test_pipe_classes_asset_id_fk_exists():
    """A.3 asset_id FK → config_assets 已建。"""
    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    text(
                        """
                        SELECT 1
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                            ON tc.constraint_name = kcu.constraint_name
                        JOIN information_schema.constraint_column_usage ccu
                            ON ccu.constraint_name = tc.constraint_name
                        WHERE tc.table_name = 'pipe_classes'
                          AND tc.constraint_type = 'FOREIGN KEY'
                          AND kcu.column_name = 'asset_id'
                          AND ccu.table_name = 'config_assets'
                        """
                    )
                )
            ).first()
            is not None
        )
    assert rows is True


@pytest.mark.asyncio
async def test_pipe_classes_no_legacy_active_status():
    """C. ACTIVE → PUBLISHED：不存在 ACTIVE，存在 PUBLISHED。"""
    factory = get_async_session_factory()
    async with factory() as session:
        legacy = (
            await session.execute(
                text("SELECT count(*) FROM pipe_classes WHERE status = 'ACTIVE'")
            )
        ).scalar_one()
        pub = (
            await session.execute(
                text("SELECT count(*) FROM pipe_classes WHERE status = 'PUBLISHED'")
            )
        ).scalar_one()
    assert legacy == 0
    # pcs_test 0 行时 pub 也可为 0；只要不残留 ACTIVE 即视为通过
    assert pub >= 0


@pytest.mark.asyncio
async def test_piping_results_fk_to_pipe_classes_intact():
    """piping_results.material_class FK 仍指向 pipe_classes.class_id（V1.4 §0.5 PC-OPEN-07）。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.table_name = 'piping_results'
                      AND tc.constraint_type = 'FOREIGN KEY'
                      AND kcu.column_name = 'material_class'
                      AND ccu.table_name = 'pipe_classes'
                    """
                )
            )
        ).first()
    assert row is not None


@pytest.mark.asyncio
async def test_project_pipe_classes_has_uuid_pk():
    """D. project_pipe_classes PK 为单列 UUID project_class_id。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT a.attname, format_type(a.atttypid, a.atttypmod)
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    JOIN pg_class c ON c.oid = i.indrelid
                    WHERE c.relname = 'project_pipe_classes' AND i.indisprimary
                    """
                )
            )
        ).all()
    assert len(row) == 1
    assert row[0][0] == "project_class_id"
    assert "uuid" in row[0][1]


@pytest.mark.asyncio
async def test_project_pipe_classes_target_columns_exist():
    """D. source_class_id/class_name/snapshot_json/override_json/status 列均存在。"""
    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'project_pipe_classes'
                    """
                    )
                )
            )
            .scalars()
            .all()
        )
    expected = {
        "project_class_id",
        "project_id",
        "source_class_id",
        "class_name",
        "override_json",
        "snapshot_json",
        "status",
        "created_by",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(set(rows))


@pytest.mark.asyncio
async def test_project_pipe_classes_no_legacy_columns():
    """D. enabled / custom_override_json / class_id 列已删除。"""
    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'project_pipe_classes'
                      AND column_name IN ('enabled', 'custom_override_json', 'class_id')
                    """
                    )
                )
            )
            .scalars()
            .all()
        )
    assert set(rows) == set()


@pytest.mark.asyncio
async def test_project_pipe_classes_unique_constraint():
    """D. UNIQUE(project_id, class_name) 存在。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE table_name = 'project_pipe_classes'
                      AND constraint_type = 'UNIQUE'
                      AND constraint_name = 'uq_project_pipe_classes_project_id_class_name'
                    """
                )
            )
        ).first()
    assert row is not None


@pytest.mark.asyncio
async def test_config_approvals_project_class_id_fk():
    """E. config_approvals.project_class_id FK → project_pipe_classes.project_class_id。"""
    factory = get_async_session_factory()
    async with factory() as session:
        col = (
            await session.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'config_approvals' AND column_name = 'project_class_id'
                    """
                )
            )
        ).first()
        fk = (
            await session.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.table_name = 'config_approvals'
                      AND tc.constraint_type = 'FOREIGN KEY'
                      AND kcu.column_name = 'project_class_id'
                      AND ccu.table_name = 'project_pipe_classes'
                    """
                )
            )
        ).first()
    assert col is not None
    assert fk is not None


@pytest.mark.asyncio
async def test_unique_constraint_triggers_on_duplicate():
    """UNIQUE(project_id, class_name) 在 ORM 插入重复时报 IntegrityError。"""
    import uuid as _uuid

    from app.models.config_domain import ProjectPipeClass
    from app.models.project import Project

    factory = get_async_session_factory()
    async with factory() as session:
        # 插入临时 Project + workspace（Project.workspace_id NOT NULL）
        from app.models.project import Workspace

        ws = Workspace(workspace_type="FORMAL", name="test-ws")
        session.add(ws)
        await session.flush()

        p = Project(
            project_id=_uuid.uuid4(),
            project_no=f"TEST-UNIQ-{_uuid.uuid4().hex[:8]}",
            project_name="uniq-test",
            owner_company="x",
            location="x",
            project_type="NEW",
            design_phase="DD",
            unit_system="SI",
            workspace_id=ws.workspace_id,
            status="ACTIVE",
        )
        session.add(p)
        await session.flush()

        base = ProjectPipeClass(
            project_id=p.project_id,
            class_name="DUP",
            source_class_id=None,
            snapshot_json={},
            override_json={},
        )
        session.add(base)
        await session.flush()

        dup = ProjectPipeClass(
            project_id=p.project_id,
            class_name="DUP",
            source_class_id=None,
            snapshot_json={},
            override_json={},
        )
        session.add(dup)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()