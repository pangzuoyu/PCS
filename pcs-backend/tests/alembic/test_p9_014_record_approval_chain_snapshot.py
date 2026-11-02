"""`p9_014`（记录表加 `approval_chain_snapshot`）的迁移形状断言 —— P9B-2F（评审 #5）。

## 为什么要这个文件

迁移里**硬编码**了 20 张表名（`p9_014_record_approval_chain_snapshot._TABLES`）——
不 import 应用模型（迁移自包含）。硬编码的代价是**会漂**：

- 哪天有人加第 21 张 `RecordMixin` 表 ⇒ ORM 元数据多了 `approval_chain_snapshot`
  列，**真库**没有 ⇒ 单测照绿（单测从 ORM metadata 建表）⇒ 第一次症状是
  该记录类型每次读都 `column does not exist` ⇒ 而整个套件还是绿的。
- 迁移自己的 docstring 也承认这个盲区（「漏表 ⇒ `alembic check` 立刻报漂移
  （红），单测**不会**」）—— 而 `alembic check` 只在**当前连着的那个库**上
  成立（CLAUDE.md「漂移盲区」），不是每次提交都跑。

⇒ 本文件把那份硬编码清单**钉在 ORM 上**：ORM 的 `RecordMixin` 叶子表集合
必须 ≡ 迁移的 `_TABLES`。这条**不需要 PG** ⇒ 每个 commit 都跑。

另一半（列的**类型与可空性**）只能在真引擎上验 ⇒ 隔离 schema 的降级环，
需要本地有 PostgreSQL（没有则 skip）。

## 与 `test_p9_013_bind_default_record_matrix.py` 的分工

那个文件验的是 p9_013（默认 RECORD 矩阵回填）；本文件验 p9_014（快照列）。
两者都用「隔离 schema + 子进程 alembic」的同一套手法。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "p9_014_record_approval_chain_snapshot.py"
)


def _load():
    """import 迁移模块（无副作用：只定义常量与函数）。"""
    spec = importlib.util.spec_from_file_location("p9_014_migration", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _orm_record_mappers() -> dict:
    """从 ORM 元数据反查 `RecordMixin` 的**叶子**表 ⇒ {表名: Mapper}。

    「叶子」= 没有更进一步的子类 ⇒ 中间 mixin（`TaggedRecordMixin`）本身
    没有表，不算。
    """
    from sqlalchemy import inspect

    from app.models.mixins import RecordMixin

    out: dict = {}
    stack = [RecordMixin]
    while stack:
        cls = stack.pop()
        for sub in cls.__subclasses__():
            if sub.__subclasses__():
                stack.append(sub)
                continue
            mapper = inspect(sub, raiseerr=False)
            table = getattr(mapper, "local_table", None)
            if table is not None:
                out[table.name] = mapper
    return out


def _orm_record_tables() -> set[str]:
    """`RecordMixin` 叶子表的**表名**集合（迁移清单的权威来源）。"""
    return set(_orm_record_mappers())


# ---------------------------------------------------------------------------
# 1. 清单与 ORM 同步（不需要 PG ⇒ 每个 commit 都跑）
# ---------------------------------------------------------------------------


def test_migration_is_chained_to_p9_013():
    """`revision = p9_014` / `down_revision = p9_013`。"""
    assert MIGRATION.exists(), "p9_014 迁移文件不存在"
    module = _load()
    assert module.revision == "p9_014"
    assert module.down_revision == "p9_013"


def test_migration_table_list_matches_the_orm():
    """⚠️ 评审 #5：迁移的硬编码清单必须 **≡ ORM 的 RecordMixin 叶子表**。

    两个方向都要查：
    - 迁移多 ⇒ 真库多出没用的列（噪声，且 downgrade 会去 drop 不存在的列）；
    - 迁移少 ⇒ **真库缺列** ⇒ 该记录类型每次读都 `column does not exist`，
      而单测照绿（单测从 ORM metadata 建表）—— 这就是本条存在的理由。
    """
    module = _load()
    orm_tables = _orm_record_tables()
    migration_tables = set(module._TABLES)

    missing = orm_tables - migration_tables
    assert not missing, (
        f"ORM 里有这些 RecordMixin 表，而 p9_014 的清单里没有：{sorted(missing)} "
        "⇒ 真库不会加 `approval_chain_snapshot` 列 ⇒ 该记录类型读起来 "
        "'column does not exist'，而单测照绿"
    )
    extra = migration_tables - orm_tables
    assert not extra, (
        f"p9_014 的清单里有这些表，但它们已经不是 RecordMixin 叶子表：{sorted(extra)} "
        "⇒ 请同步更新迁移清单（要么补回 ORM，要么从清单里删掉）"
    )


def test_migration_table_list_has_no_duplicates():
    """清单里不能有重复项（重复 ⇒ `add_column` 跑两遍 ⇒ 第二次报错）。"""
    module = _load()
    assert len(module._TABLES) == len(set(module._TABLES))


def test_orm_column_name_matches_the_migration():
    """ORM 的列名必须与迁移建的列名**逐字一致**（每张叶子表都要有这列）。"""
    module = _load()
    assert module._COLUMN == "approval_chain_snapshot"
    missing = [
        table
        for table, mapper in _orm_record_mappers().items()
        if module._COLUMN not in mapper.columns
    ]
    assert not missing, f"这些 RecordMixin 表的 ORM 上没有 {module._COLUMN} 列：{missing}"


# ---------------------------------------------------------------------------
# 2. 真引擎：列的类型 / 可空性 / 降级环（需要本地 PostgreSQL，没有则 skip）
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


def test_p9_014_column_is_jsonb_and_nullable_on_every_record_table():
    """在**隔离 schema** 上从零 `alembic upgrade head` ⇒ 20 张表都有
    `approval_chain_snapshot`，且类型是 **jsonb**、**可空**。

    ⚠️ 为什么要在真引擎上验：类型（jsonb）与可空性是 **DB 层**的属性，
    单测（SQLite 从 metadata 建表）**看不到**真实 PG 的行为。
    ⚠️ 为什么可空是有意的：存量 IN_APPROVAL 行没有快照 ⇒ 读路径对
    `IS NULL` 回退（`records_actions._legacy_chain_snapshot` 从审计流水
    反推提交人）。

    无 PG ⇒ skip。**本仓没有任何自动化作业跑它**（CI 的 api-drift job 只跑
    `alembic upgrade head`，不跑后端 pytest）⇒ 要验就在本地手动跑这个文件。
    """
    import os
    import subprocess
    import sys
    import uuid

    import pytest

    url = _pg_url()
    if url is None:
        pytest.skip(
            "无 PostgreSQL URL（DATABASE_URL / .env）—— "
            "本仓无自动化 PG 测试通道（CI api-drift job 不跑后端 pytest），"
            "需本地有 PG 时手动跑本文件"
        )

    schema = f"iso_p9_014_{uuid.uuid4().hex[:8]}"
    root = Path(__file__).resolve().parents[2]
    tables = sorted(_orm_record_tables())

    script = f"""
import asyncio, os, re
os.environ["DATABASE_URL"] = re.sub(
    r"(\\?|$)", r"?options=-csearch_path={schema}\\1", os.environ["DATABASE_URL"], count=1
)
from alembic import command
from alembic.config import Config
cfg = Config("alembic.ini")
command.upgrade(cfg, "head")
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TABLES = {tables!r}

async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT table_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND column_name = 'approval_chain_snapshot'"
                )
            )
        ).all()
    await engine.dispose()
    found = {{r[0]: (r[1], r[2]) for r in rows}}
    missing = [t for t in TABLES if t not in found]
    assert not missing, f"这些表缺 approval_chain_snapshot 列: {{missing}}"
    wrong_type = [t for t in TABLES if found[t][0] != "jsonb"]
    assert not wrong_type, f"这些表的列不是 jsonb: {{[(t, found[t]) for t in wrong_type]}}"
    not_null = [t for t in TABLES if found[t][1] != "YES"]
    assert not not_null, f"这些表的列不该 NOT NULL: {{not_null}}"
    print("P9_014_ENGINE_OK")

asyncio.run(main())
"""
    cleanup = None
    try:
        create = subprocess.run(
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
        assert create.returncode == 0, f"CREATE SCHEMA 失败:\n{create.stderr}"

        result = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "DATABASE_URL": url},
            cwd=root, capture_output=True, text=True, timeout=900,
        )
        assert result.returncode == 0, f"upgrade/断言失败:\n{result.stdout}\n{result.stderr}"
        assert "P9_014_ENGINE_OK" in result.stdout
    finally:
        cleanup = subprocess.run(
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
        # ⚠️ 清理失败**必须**报出来（评审 #18）：静默吞掉 ⇒ 隔离 schema 留在
        # 开发库里，而 DDL 已经落地 ⇒ 下次跑会撞「schema 已存在」。
        # ⚠️ 判定放在 try/finally **之后**（不在 finally 里）：finally 里抛的
        #    异常会**顶掉**正在传播的原始异常 ⇒ 真正的失败原因会被这条掩盖。
    assert cleanup is not None and cleanup.returncode == 0, (
        f"DROP SCHEMA {schema} 失败（隔离 schema 可能残留在库里）:\n"
        f"{cleanup.stdout}\n{cleanup.stderr}"
    )


def test_p9_014_downgrade_drops_the_column():
    """降级环：`head → p9_013 → head` ⇒ 列被删掉、再被加回来。

    ⚠️ 降级**有损**：在飞的冻结链随列一起没了 —— 这是 runbook R-3 要写明的
    代价（回滚 p9_014 ⇒ 在飞批准链丢失）。
    """
    import os
    import subprocess
    import sys
    import uuid

    import pytest

    url = _pg_url()
    if url is None:
        pytest.skip("无 PostgreSQL URL —— 需本地有 PG 时手动跑本文件")

    schema = f"iso_rt14_{uuid.uuid4().hex[:8]}"
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
command.downgrade(cfg, "p9_013")     # 只退 p9_014
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def count_cols():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as conn:
        n = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND column_name = 'approval_chain_snapshot'"
                )
            )
        ).scalar()
    await engine.dispose()
    return n
async def main():
    assert await count_cols() == 0, "降级后列应被删掉"
    command.upgrade(cfg, "head")
    assert await count_cols() == 20, "重升级后 20 张表都该有该列"
    print("P9_014_ROUNDTRIP_OK")
asyncio.run(main())
"""
    cleanup = None
    try:
        create = subprocess.run(
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
        assert create.returncode == 0, f"CREATE SCHEMA 失败:\n{create.stderr}"

        result = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "DATABASE_URL": url},
            cwd=root, capture_output=True, text=True, timeout=900,
        )
        assert result.returncode == 0, f"roundtrip 失败:\n{result.stdout}\n{result.stderr}"
        assert "P9_014_ROUNDTRIP_OK" in result.stdout
    finally:
        cleanup = subprocess.run(
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
        # ⚠️ 判定放在 try/finally **之后**（不在 finally 里）：finally 里抛的
        #    异常会**顶掉**正在传播的原始异常 ⇒ 真正的失败原因会被这条掩盖。
    assert cleanup is not None and cleanup.returncode == 0, (
        f"DROP SCHEMA {schema} 失败（隔离 schema 可能残留在库里）:\n"
        f"{cleanup.stdout}\n{cleanup.stderr}"
    )
