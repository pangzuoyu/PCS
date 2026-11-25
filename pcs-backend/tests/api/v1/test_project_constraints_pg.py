"""项目**词表 CHECK 约束**在真 PG 上的行为（P10-K · W-2 / W-2c / W-3b）。

## 为什么必须真 PG

`projects.unit_system` / `projects.status` / `project_templates.status` 的
`CHECK` 约束是**迁移 `p10_006`** 加的 ⇒ ⇒ ⇒ **ORM 声明它 ≠ DB 真的有它**
⇒ ⇒ ⇒ 默认车道（内存 SQLite）**从 ORM metadata 建表** ⇒ ⇒ ⇒ ⇒ 它**永远绿**
⇒ ⇒ ⇒ ⇒ 真库有没有这条约束 ⇒ ⇒ ⇒ ⇒ **只有真 PG 能证**。

⚠️ `pg` marker 的用例平时被 `pytest.skip` 静默跳过 ⇒ ⇒ ⇒ **必须**经
`scripts/pytest_pg.sh`（唯一入口）跑。

## 隔离 schema（不碰开发库）

沿用 `tests/api/v1/test_stream_batch_concurrency_pg.py` 的做法：建隔离 schema
⇒ 在它上面 `alembic upgrade head` ⇒ 用 `options=-csearch_path=<schema>`
⇒ 测完 `DROP SCHEMA ... CASCADE` ⇒ 开发库一个字节都不动。
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _pg_url() -> str | None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        env_file = ROOT / ".env"
        if env_file.exists():
            from dotenv import dotenv_values

            url = dotenv_values(env_file).get("DATABASE_URL")
    return url if url and url.startswith("postgres") else None


@pytest.mark.pg
def test_project_and_template_vocabularies_are_enforced_by_db_checks():
    """⚠️ **三条 CHECK 真的在库里**（ORM 声明 ≠ DB 约束）。

    - `projects.unit_system` ∉ {SI, US} ⇒ ⇒ ⇒ **CHECK 违例**；
    - `projects.status` ∉ {DRAFT, ACTIVE} ⇒ ⇒ ⇒ **CHECK 违例**；
    - `project_templates.status` ∉ {DRAFT, PUBLISHED, OBSOLETE} ⇒ ⇒ ⇒ **违例**；
    - 合法值 ⇒ ⇒ ⇒ **能插进去**（约束不是「全拒」）。

    ⇒ ⇒ ⇒ 约束被删了 ⇒ ⇒ ⇒ 这条用例**就红** ⇒ ⇒ ⇒ ⇒ 这就是它的全部价值。
    """
    url = _pg_url()
    if url is None:
        pytest.skip(
            "无 PostgreSQL URL —— 引擎级验证须经 scripts/pytest_pg.sh 跑（唯一入口）"
        )

    schema = f"iso_projck_{uuid.uuid4().hex[:8]}"
    scoped_url = url + ("&" if "?" in url else "?") + f"options=-csearch_path={schema}"
    script = r'''
import asyncio, os, uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.config_domain import ProjectTemplate
from app.models.project import Project, Workspace


async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as db:
        ws = Workspace(workspace_type="FORMAL", name="WS-CHECK", status="ACTIVE")
        db.add(ws)
        await db.flush()
        pid = uuid.uuid4()
        db.add(Project(
            project_id=pid,
            project_no="P-CHECK",
            project_name="词表约束测试",
            owner_company="PCS",
            location="惠州",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            status="ACTIVE",
            workspace_id=ws.workspace_id,
        ))
        await db.commit()

    async def expect_check_violation(label, make_row):
        async with maker() as s:
            s.add(make_row())
            try:
                await s.commit()
            except IntegrityError as e:
                await s.rollback()
                print(f"{label}: CHECK_VIOLATION_OK")
                return
        raise AssertionError(f"{label}: 非法值**插进去了** ⇒ CHECK 约束不存在或没生效")

    def bad_unit():
        return Project(
            project_id=uuid.uuid4(),
            project_no=f"P-BADU-{uuid.uuid4().hex[:6]}",
            project_name="非法单位制",
            owner_company="PCS",
            location="惠州",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="公制",
            status="ACTIVE",
        )

    def bad_status():
        return Project(
            project_id=uuid.uuid4(),
            project_no=f"P-BADS-{uuid.uuid4().hex[:6]}",
            project_name="非法状态",
            owner_company="PCS",
            location="惠州",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            status="ARCHIVED",
        )

    def bad_template_status():
        return ProjectTemplate(
            name=f"tpl-bad-{uuid.uuid4().hex[:6]}",
            industry="CHEMICAL",
            default_config_json={},
            version="1.0.0",
            status="ACTIVE",
        )

    def bad_template_unit():
        # ⚠️ 模板的**默认单位制**（P10-K · TODO-210 · D1）—— 同款 CHECK
        return ProjectTemplate(
            name=f"tpl-badu-{uuid.uuid4().hex[:6]}",
            industry="CHEMICAL",
            default_config_json={},
            version="1.0.0",
            status="DRAFT",
            unit_system="公制",
        )

    await expect_check_violation("unit_system", bad_unit)
    await expect_check_violation("status", bad_status)
    await expect_check_violation("template_status", bad_template_status)
    await expect_check_violation("template_unit_system", bad_template_unit)

    # ⇒ ⇒ ⇒ 合法值**能插进去**（约束不是「全拒」）
    async with maker() as s:
        s.add(ProjectTemplate(
            name=f"tpl-ok-{uuid.uuid4().hex[:6]}",
            industry="CHEMICAL",
            default_config_json={},
            version="1.0.0",
            status="PUBLISHED",
        ))
        await s.commit()
    print("LEGAL_VALUES_OK")

    await engine.dispose()
    print("PROJECT_CHECKS_OK")


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
            f"CHECK 约束脚本失败:\n{result.stdout}\n{result.stderr}"
        )
        assert "PROJECT_CHECKS_OK" in result.stdout, result.stdout
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
