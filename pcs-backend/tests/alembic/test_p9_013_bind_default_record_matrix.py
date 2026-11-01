"""`p9_013`（存量项目回填默认 RECORD 矩阵）的迁移形状断言 —— P9B-2 · Batch F。

⚠️ 本文件只断言**迁移与运行时一致**（默认矩阵的定义 / 回填的幂等 / 降级口径），
**不跑真库升级** —— 真库升级的验证口径见 `scripts/check_migration_idempotency.py`
+ `alembic check`（每库各一次，退出码 **255**）。

## 最要紧的一条：迁移里的矩阵定义 ≡ 服务常量

⚠️ 服务 `_get_or_create_default_record_matrix` 是**按名字找**已有矩阵的
⇒ **矩阵的步骤来自 DB 行**，不是来自服务常量 ⇒ 服务改了 `DEFAULT_RECORD_STEPS`
而迁移没改 ⇒ 老库的矩阵还是**旧步骤** ⇒ 「谁该签这一步」有两个答案，
**没有任何报错**。

⇒ 这条断言是那个分叉的**唯一**闸门。

## 为什么**直接 import 迁移模块**（而不是 AST 解析）

迁移里的 SQL 是 f-string（把矩阵名 / 模块 / 步骤内联进去）⇒ AST 只能看到
`{_MATRIX_NAME}` 这样的**占位** ⇒ 断言「SQL 里有没有那个名字」就成了断言
「占位符拼对了」⇒ **测不到真正要守的东西**。⇒ 直接 import，拿**求值后的
SQL** 来断言。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from app.services.signature_matrix_service import SignatureMatrixService

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "p9_013_bind_default_record_matrix.py"
)


def _load():
    """import 迁移模块（无副作用：只定义常量与函数）。"""
    spec = importlib.util.spec_from_file_location("p9_013_migration", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_exists_and_is_chained_to_p9_012():
    """`revision = p9_013` / `down_revision = p9_012`（p9_012 是当前 head）。"""
    assert MIGRATION.exists(), "p9_013 迁移文件不存在"
    module = _load()
    assert module.revision == "p9_013"
    assert module.down_revision == "p9_012", (
        f"down_revision 应为 p9_012（当前 head），实际 {module.down_revision}"
    )


def test_migration_matrix_definition_matches_service_constants():
    """⚠️ **迁移里的默认矩阵 ≡ 服务常量**（名字 / 模块 / 步骤）。"""
    module = _load()
    assert module._MATRIX_NAME == SignatureMatrixService.DEFAULT_RECORD_MATRIX_NAME
    assert module._MODULE == SignatureMatrixService.RECORD_MODULE
    steps = json.loads(module._STEPS_JSON)
    assert steps == [dict(s) for s in SignatureMatrixService.DEFAULT_RECORD_STEPS], (
        "迁移里的默认矩阵步骤与服务常量不一致 —— "
        "服务是**按名字找**矩阵的 ⇒ 定义漂了 ⇒ 老库用旧步骤、新库用新步骤 ⇒ "
        "「谁该签这一步」有两个答案且不报错。"
    )


def test_backfill_only_touches_projects_without_record_binding():
    """回填**只**给没有 RECORD 绑定的项目补（已有绑定的人工决定不被夺走）。"""
    module = _load()
    sql = module._CREATE_BINDINGS
    assert "NOT EXISTS" in sql
    assert "b.project_id = p.project_id AND b.module = 'RECORD'" in sql
    # ⚠️ **不许**无条件 INSERT（会把已有绑定换成默认矩阵）
    assert sql.count("INSERT INTO project_signature_matrix_bindings") == 1


def test_default_matrix_is_created_only_when_missing():
    """默认矩阵**有就复用**（`(matrix_name, status)` 唯一 ⇒ 天然幂等）。"""
    module = _load()
    sql = module._CREATE_MATRIX
    assert "WHERE NOT EXISTS" in sql
    assert "matrix_name = 'DEFAULT_RECORD_3_LEVEL' AND status = 'ACTIVE'" in sql
    # ⚠️ 步骤必须**真的**进 SQL（不是占位符）
    assert '"sign_role": "CHECKER"' in sql


def test_downgrade_deletes_bindings_but_keeps_the_matrix_row():
    """降级删**绑定**、留**矩阵行**（矩阵是全局模板，删了会让新建项目的绑定悬空）。"""
    module = _load()
    sql = module._DROP_BINDINGS
    assert "DELETE FROM project_signature_matrix_bindings" in sql
    assert "DELETE FROM signature_matrices" not in sql
    # ⚠️ 降级也**只**删 module=RECORD 的绑定
    assert "WHERE module = 'RECORD'" in sql


# ---------------------------------------------------------------------------
# 追问 2（委员会升级为 P2）：至少一次**真跑引擎**
# ---------------------------------------------------------------------------


def _pg_url() -> str | None:
    """PostgreSQL URL：`DATABASE_URL` 环境变量优先，否则 `.env`（不出现在命令行）。"""
    import os

    url = os.environ.get("DATABASE_URL")
    if not url:
        env_file = Path(__file__).resolve().parents[2] / ".env"
        if env_file.exists():
            from dotenv import dotenv_values

            url = dotenv_values(env_file).get("DATABASE_URL")
    return url if url and url.startswith("postgres") else None


def test_p9_013_runs_on_fresh_postgres_schema():
    """p9_013 的 SQL（`gen_random_uuid()` / `::jsonb`）在 SQLite 上跑不了 ⇒
    单测从未**执行**过它 —— 首次执行留给生产是不可接受的（委员会追问 2）。

    这里在**隔离 schema** 上从零 `alembic upgrade head`（CLAUDE.md 配方：
    DATABASE_URL 进程内派生、口令不落命令行、URL 不带 %），断言：
    1. 全链升级到 head 不炸；
    2. p9_013 的 ①号 INSERT 真的插出了 `DEFAULT_RECORD_3_LEVEL`（ACTIVE、3 步）。

    无 PG（CI 单测 job）⇒ skip —— CI 的 fresh-PG `api-drift` job 承担同口径验证。
    """
    import os
    import subprocess
    import sys
    import uuid

    import pytest

    url = _pg_url()
    if url is None:
        pytest.skip(
            "无 PostgreSQL URL（DATABASE_URL / .env）——"
            "该验证由 CI fresh-PG api-drift job 承担"
        )

    schema = f"iso_p9_013_{uuid.uuid4().hex[:8]}"
    root = Path(__file__).resolve().parents[2]

    script = f"""
import asyncio, os, re, sys
os.environ["DATABASE_URL"] = re.sub(
    r"(\\?|$)", r"?options=-csearch_path={schema}\\1", os.environ["DATABASE_URL"], count=1
)
from alembic import command
from alembic.config import Config
cfg = Config("alembic.ini")
command.upgrade(cfg, "head")
command.current(cfg)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT matrix_name, status, steps_json FROM signature_matrices "
                    "WHERE matrix_name = 'DEFAULT_RECORD_3_LEVEL'"
                )
            )
        ).first()
    await engine.dispose()
    assert row is not None, "p9_013 的 INSERT 没插出默认矩阵"
    assert row[1] == "ACTIVE", row
    import json
    steps = row[2] if isinstance(row[2], list) else json.loads(row[2])
    assert [s["sign_role"] for s in steps] == ["CHECKER", "REVIEWER", "APPROVER"], steps
    print("P9_013_ENGINE_OK")
asyncio.run(main())
"""
    try:
        # 建隔离 schema（用原 URL，不带 options）
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import asyncio, os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["BASE_PG_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA {schema}"))
    await engine.dispose()
asyncio.run(main())
""",
            ],
            env={**os.environ, "BASE_PG_URL": url},
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, f"CREATE SCHEMA 失败:\n{result.stderr}"

        result = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "DATABASE_URL": url},
            cwd=root,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert result.returncode == 0, f"upgrade/断言失败:\n{result.stdout}\n{result.stderr}"
        assert "P9_013_ENGINE_OK" in result.stdout
    finally:
        subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import asyncio, os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["BASE_PG_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS {schema} CASCADE"))
    await engine.dispose()
asyncio.run(main())
""",
            ],
            env={**os.environ, "BASE_PG_URL": url},
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )


def test_p9_013_p9_012_downgrade_upgrade_roundtrip():
    """⚠️ 评审 B-5：两条新迁移的 `downgrade` 从未在任何引擎上执行过。

    在隔离 schema 上走完整环：`head → p9_012 → head` ⇒
    - p9_013 降级删绑定（矩阵行保留）⇒ 重升级 ⇒ 默认矩阵**仍恰好一行**、
      回填逻辑可重入；
    - p9_012 降级把列加回来（含约定名 FK）⇒ 再升级 ⇒ 列再删 ⇒ 不炸、不漂。
    ⚠️ 降级**有损**（绑定被删 = 用户配置不恢复）—— 这里不断言绑定存活，
    只断言链路可走 + 升级侧幂等。
    """
    import os
    import subprocess
    import sys
    import uuid

    import pytest

    url = _pg_url()
    if url is None:
        pytest.skip("无 PostgreSQL URL —— 该验证由 CI fresh-PG job 承担")

    schema = f"iso_rt_{uuid.uuid4().hex[:8]}"
    root = Path(__file__).resolve().parents[2]

    script = f"""
import asyncio, os, re
os.environ["DATABASE_URL"] = re.sub(
    r"(\\?|$)", r"?options=-csearch_path={schema}\\1", os.environ["DATABASE_URL"], count=1
)
from alembic import command
from alembic.config import Config
cfg = Config("alembic.ini")
command.upgrade(cfg, "head")
command.downgrade(cfg, "p9_011")   # p9_013 + p9_012 都降掉
command.upgrade(cfg, "head")       # 再升回 head
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as conn:
        n = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM signature_matrices "
                    "WHERE matrix_name = 'DEFAULT_RECORD_3_LEVEL' AND status = 'ACTIVE'"
                )
            )
        ).scalar()
        # ⚠️ information_schema **不受 search_path 约束**（public 库也有同名表）
        # ⇒ 必须按 current_schema() 限定，否则 public 升到 p9_014 后计数跨库
        # 相加、断言值随 public 的迁移状态漂移。
        has_col = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = 'deliverables' "
                    "AND column_name = 'parent_deliverable_id'"
                )
            )
        ).scalar()
        snap_col = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = 'flash_results' "
                    "AND column_name = 'approval_chain_snapshot'"
                )
            )
        ).scalar()
    await engine.dispose()
    assert n == 1, f"环后默认矩阵应恰 1 行, got {{n}}"
    assert has_col == 0, "p9_012 重升级后死列应再被删掉"
    assert snap_col == 1, "p9_014 的快照列应存在"
    print("ROUNDTRIP_OK")
asyncio.run(main())
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             f"""
import asyncio, os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["BASE_PG_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA {schema}"))
    await engine.dispose()
asyncio.run(main())
"""],
            env={**os.environ, "BASE_PG_URL": url},
            cwd=root, capture_output=True, text=True, timeout=300,
        )
        assert result.returncode == 0, f"CREATE SCHEMA 失败:\n{result.stderr}"
        result = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "DATABASE_URL": url},
            cwd=root, capture_output=True, text=True, timeout=900,
        )
        assert result.returncode == 0, f"roundtrip 失败:\n{result.stdout}\n{result.stderr}"
        assert "ROUNDTRIP_OK" in result.stdout
    finally:
        subprocess.run(
            [sys.executable, "-c",
             f"""
import asyncio, os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["BASE_PG_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS {schema} CASCADE"))
    await engine.dispose()
asyncio.run(main())
"""],
            env={**os.environ, "BASE_PG_URL": url},
            cwd=root, capture_output=True, text=True, timeout=120,
        )
