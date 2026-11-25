"""公司级报表定义的**同名唯一性**（PG 车道 · P10-J-T1 · T1-6）。

## 为什么必须真 PG

`report_definitions` 上的唯一约束是

```python
UniqueConstraint("project_id", "name",
                 name="uq_report_definitions_project_name",
                 postgresql_nulls_not_distinct=True)
```

⚠️ **`postgresql_nulls_not_distinct=True` 是 PG 独有的** ⇒ ⇒ ⇒
SQLite **不支持**（SQLite 的 `UNIQUE` 把 `NULL` 视作互不相等）
⇒ ⇒ ⇒ 在默认车道（内存 SQLite）里，**两条同名公司级定义能插进去**
⇒ ⇒ ⇒ 约束被删了、或者 `nulls_not_distinct` 没生效，默认车道**照绿**
⇒ ⇒ ⇒ 这条约束**只有真 PG 能证**。

⚠️ `pg` marker 的用例平时被 `pytest.skip` 静默跳过 ⇒ 绿灯**证明不了**
它们跑过 ⇒ **必须**经 `scripts/pytest_pg.sh`（唯一入口）跑。

## ⚠️ 为什么必须**直连 ORM**，不走 API

`definition_service._reject_duplicate()` 是**应用层** SELECT ⇒ ⇒ ⇒
走 API 建第二条同名定义时，它**先**抛 409 `REPORT_DEFINITION_DUPLICATE`
⇒ ⇒ ⇒ **永远碰不到 DB 约束** ⇒ ⇒ ⇒ 约束被删了那条测试**照样绿**
⇒ ⇒ ⇒ **假证据**。

⇒ ⇒ ⇒ 本用例**绕开服务层**，直接 `db.add(...)` ⇒ ⇒ ⇒ 真打到约束。

## 隔离 schema（不碰开发库）

沿用 `tests/api/v1/test_stream_batch_concurrency_pg.py` 的做法：
建一个隔离 schema ⇒ 在它上面 `alembic upgrade head` ⇒ 用
`options=-csearch_path=<schema>` 让应用连到它 ⇒ 测完 `DROP SCHEMA ... CASCADE`
⇒ 开发库一个字节都不动。

⚠️ **口令不上命令行** ⇒ URL 只在**进程内**派生（`DATABASE_URL` 环境变量
传给子进程，不出现在 argv 里）。
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

# ⚠️ 本文件在 `tests/api/v1/` ⇒ `parents[3]` 才是仓库根（alembic.ini 在那里）
ROOT = Path(__file__).resolve().parents[3]


def _pg_url() -> str | None:
    """PostgreSQL URL：`DATABASE_URL` 环境变量优先，否则 `.env`。"""
    url = os.environ.get("DATABASE_URL")
    if not url:
        env_file = ROOT / ".env"
        if env_file.exists():
            from dotenv import dotenv_values

            url = dotenv_values(env_file).get("DATABASE_URL")
    return url if url and url.startswith("postgres") else None


@pytest.mark.pg
def test_company_level_definition_name_is_unique_nulls_not_distinct():
    """⚠️ **同名公司级定义必须撞 DB 约束**（`nulls_not_distinct` 才算数）。

    - **两条 `project_id IS NULL` 且同名** ⇒ ⇒ ⇒ 必须抛 `IntegrityError`
      （`uq_report_definitions_project_name`）⇒ ⇒ ⇒
      ⚠️ 若这里能插进去 ⇒ ⇒ ⇒ 说明 `nulls_not_distinct` 没生效或约束被删了
      ⇒ ⇒ ⇒ 后果：公司级模板**可以重名** ⇒ ⇒ ⇒ 执行面板的定义下拉里
      **两个长得一样的项** ⇒ ⇒ ⇒ 用户选哪个全靠猜 ⇒ ⇒ ⇒ **不可接受**；
    - **一条公司级 + 一条项目级，同名** ⇒ ⇒ ⇒ 必须**能共存**
      （`NULL` 与某个 uuid 是**不同的值** ⇒ ⇒ ⇒ 约束按
      `(project_id, name)` 组合判 ⇒ ⇒ ⇒ 不同作用域可以同名）。

    ⇒ ⇒ ⇒ 这两条断言合起来 = 「约束**在**、且**语义正确**」。
    """
    url = _pg_url()
    if url is None:
        pytest.skip(
            "无 PostgreSQL URL —— 引擎级验证须经 scripts/pytest_pg.sh 跑（唯一入口）"
        )

    schema = f"iso_repdef_{uuid.uuid4().hex[:8]}"
    scoped_url = url + ("&" if "?" in url else "?") + f"options=-csearch_path={schema}"
    script = r'''
import asyncio, os, uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.project import Project, Workspace
from app.models.report import ReportDefinition

DEF_JSON = {
    "DataSources": [{"source": "PUMP_RESULTS"}],
    "SelectedFields": [],
    "FilterConditions": [],
    "SortBy": [],
    "MaxRows": 10000,
    "OutputFormat": "pdf",
}


def make_def(name: str, project_id=None):
    return ReportDefinition(
        name=name,
        category="设备类",
        description="",
        definition_json=DEF_JSON,
        output_format="pdf",
        max_rows=10000,
        version="0.1.0",
        status="PUBLISHED",
        shared_with="ALL_USERS",
        project_id=project_id,
    )


async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as db:
        ws = Workspace(workspace_type="FORMAL", name="ws-repdef")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no="P-REPDEF",
            project_name="同名约束测试",
            owner_company="业主",
            location="地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.flush()
        await db.commit()
        pid = proj.project_id

    # ---- ① 两条**同名公司级**定义 ⇒ 必须撞约束 ------------------------
    async with maker() as s:
        s.add(make_def("泵数据表"))
        await s.commit()

    collided = False
    try:
        async with maker() as s:
            s.add(make_def("泵数据表"))
            await s.commit()
    except IntegrityError as e:
        collided = True
        print("INTEGRITY_ERROR_OK:", str(e.orig)[:200])
    assert collided, (
        "两条同名公司级定义**插进去了** ⇒ `uq_report_definitions_project_name` "
        "的 `postgresql_nulls_not_distinct` 没生效（或约束被删了）"
        "⇒ 公司级模板可以重名 ⇒ 执行面板里两个长得一样的项 ⇒ 用户靠猜"
    )

    # ---- ② 公司级 + 项目级**同名** ⇒ 必须能共存 ------------------------
    # （`NULL` 与 uuid 是不同的值 ⇒ 约束按 (project_id, name) 组合判）
    async with maker() as s:
        s.add(make_def("泵数据表", project_id=pid))
        await s.commit()

    async with maker() as s:
        # ⚠️ AsyncSession **没有** `.query()`（那是同步 Session 的 API）
        #    ⇒ ⇒ ⇒ 用 `select()` + `execute()`。
        from sqlalchemy import select

        rows = (await s.execute(
            select(ReportDefinition).where(ReportDefinition.name == "泵数据表")
        )).scalars().all()
        assert len(rows) == 2, f"期望 2 条（1 公司级 + 1 项目级），实得 {len(rows)}"
        nulls = [r for r in rows if r.project_id is None]
        scoped = [r for r in rows if r.project_id is not None]
        assert len(nulls) == 1 and len(scoped) == 1, rows

    await engine.dispose()
    print("REPORT_DEF_UNIQUENESS_OK")


asyncio.run(main())
'''

    try:
        created = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import asyncio, os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["BASE_PG_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA " + os.environ["ISO_SCHEMA"]))
    await engine.dispose()
asyncio.run(main())
""",
            ],
            env={**os.environ, "BASE_PG_URL": url, "ISO_SCHEMA": schema},
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert created.returncode == 0, f"CREATE SCHEMA 失败:\n{created.stderr}"

        upgraded = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import os
from alembic import command
from alembic.config import Config
cfg = Config("alembic.ini")
command.upgrade(cfg, "head")
print("UPGRADE_OK")
""",
            ],
            env={**os.environ, "DATABASE_URL": scoped_url},
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=900,
        )
        assert upgraded.returncode == 0, f"alembic upgrade 失败:\n{upgraded.stderr}"
        assert "UPGRADE_OK" in upgraded.stdout, upgraded.stdout

        result = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "DATABASE_URL": scoped_url},
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert result.returncode == 0, (
            f"同名约束脚本失败:\n{result.stdout}\n{result.stderr}"
        )
        assert "REPORT_DEF_UNIQUENESS_OK" in result.stdout, result.stdout
    finally:
        cleanup = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import asyncio, os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["BASE_PG_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS " + os.environ["ISO_SCHEMA"] + " CASCADE"))
    await engine.dispose()
asyncio.run(main())
""",
            ],
            env={**os.environ, "BASE_PG_URL": url, "ISO_SCHEMA": schema},
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert cleanup is not None and cleanup.returncode == 0, (
            f"DROP SCHEMA {schema} 失败（隔离 schema 可能残留在库里）:\n"
            f"{cleanup.stdout}\n{cleanup.stderr}"
        )
