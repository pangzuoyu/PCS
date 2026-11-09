"""批量/单条「提交校对」的**真并发**（PG 车道 · P9B-3b · T4）。

## 为什么必须真 PG

SQLite 把 `SELECT ... FOR UPDATE` 编译成空串 ⇒ 单测里的「并发」只是
**顺序执行** ⇒ 证明不了行锁。⇒ 真并发必须在 PG 上用**两个连接**跑。

⚠️ `pg` marker 的用例平时被 `pytest.skip` 静默跳过 ⇒ 绿灯**证明不了**
它们跑过 ⇒ **必须**经 `scripts/pytest_pg.sh`（唯一入口）跑。

## 隔离 schema（不碰开发库）

沿用 `tests/alembic/test_p9_013_bind_default_record_matrix.py` 的做法：
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

# ⚠️ 本文件在 `tests/api/v1/`（比 `tests/alembic/` 的先例**深一层**）⇒
#   `parents[2]` 是 `tests`（不是仓库根）⇒ alembic 子进程的 cwd 里就**没有**
#   `alembic.ini` ⇒ `Config("alembic.ini")` 拿到空配置 ⇒
#   "No 'script_location' key found in configuration" ⇒ 这里必须 `parents[3]`。
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
def test_concurrent_submit_same_stream_one_wins_one_rejected():
    """⚠️ **最关键的测试**：并发提交同一条 stream ⇒ **一胜一拒**（行锁真的生效）。

    - 单条端点：两个并发 `submit_batch` 之外的 `StreamService.transition`
      ⇒ 一个成功（DRAFT → IN_APPROVAL），另一个 **422
      `SIM_STREAM_INVALID_TRANSITION`**（它拿到锁时状态已是 IN_APPROVAL）；
    - 批量端点：因 D5 幂等 ⇒ 两个都返回成功，但**只有一条真正转移**
      （`RECORD_TRANSITION` 审计**恰好 1 条**）。

    ⇒ 「行锁被绕过」的两种表现（两次都转移 / 审计两条）都会让本用例红。
    """
    url = _pg_url()
    if url is None:
        pytest.skip(
            "无 PostgreSQL URL —— 引擎级验证须经 scripts/pytest_pg.sh 跑（唯一入口）"
        )

    schema = f"iso_batch_{uuid.uuid4().hex[:8]}"
    # ⚠️ 隔离 schema 的 URL = 原 URL **追加** `options=-csearch_path=<schema>`
    #    （`?` 还是 `&` 看原 URL 有没有 query）。
    #    ⚠️ `alembic/env.py` 用 `settings.database_url`（pydantic-settings：
    #    **环境变量优先于 .env**）⇒ 把 scoped URL 放进子进程的 `DATABASE_URL`
    #    就能让 alembic 建表到隔离 schema ⇒ 开发库 public schema 一个字节不动。
    scoped_url = url + ("&" if "?" in url else "?") + f"options=-csearch_path={schema}"
    script = r'''
import asyncio, os, uuid
# ⚠️ `DATABASE_URL` 已由父进程派生成「指向隔离 schema」的版本 ⇒ 直接用。

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.errors import PcsError
from app.models.enums import StateTransition
from app.models.project import Project, Stream, User, UserProject, Workspace
from app.services.stream_batch_service import submit_batch
from app.services.stream_service import StreamService


async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as db:
        ws = Workspace(workspace_type="FORMAL", name="ws-conc")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no="P-CONC",
            project_name="并发测试",
            owner_company="业主",
            location="地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.flush()
        stream = Stream(
            project_id=proj.project_id,
            workspace_id=ws.workspace_id,
            stream_name="S-CONC",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            source="MANUAL",
            phase="LIQUID",
            temp=80.0,
            press=200.0,
            mass_flow=1000.0,
            composition_json={"7732-18-5": 1.0},
            sign_status="DRAFT",
            # ⚠️ `approval_depth` 是 streams 上**唯一没有默认值**的 NOT NULL 列
            #   （cerebrum Do-Not-Repeat：写 DB fixture 前必查 NOT NULL 列）
            approval_depth=1,
        )
        db.add(stream)
        stream2 = Stream(
            project_id=proj.project_id,
            workspace_id=ws.workspace_id,
            stream_name="S-CONC-2",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            source="MANUAL",
            phase="LIQUID",
            temp=80.0,
            press=200.0,
            mass_flow=1000.0,
            composition_json={"7732-18-5": 1.0},
            sign_status="DRAFT",
            approval_depth=1,
        )
        db.add(stream2)
        await db.commit()
        sid = stream.stream_id
        sid2 = stream2.stream_id

        # ⚠️ P9B-4 紧急批次 T4：批次 service 现在**逐条**做项目守卫 ⇒
        #    操作人必须有该项目的授权行，否则每条都判成「不存在」。
        #    ⇒ 这里给一个**固定**操作人建 `users` 行 + `user_projects` 行。
        #    （⚠️ 真 PG 上 FK **强制** ⇒ `users` 行必须先建。）
        actor_id = uuid.uuid5(uuid.NAMESPACE_DNS, "pg-conc-actor")
        if await db.get(User, actor_id) is None:
            db.add(
                User(
                    user_id=actor_id,
                    username="pg-conc-actor",
                    display_name="pg-conc-actor",
                    roles=[],
                    ad_groups=[],
                    status="ACTIVE",
                )
            )
            await db.flush()
        db.add(
            UserProject(
                user_id=actor_id,
                project_id=proj.project_id,
                role_in_project="DESIGNER",
                granted_by=actor_id,
            )
        )
        await db.commit()

    # ---- ① 单条：并发两次 ⇒ 一胜一拒 -------------------------------
    async def submit_once():
        async with maker() as s:
            try:
                await StreamService.transition(
                    s, sid,
                    transition=StateTransition.SUBMIT_FOR_CHECK,
                    actor_user_id=uuid.uuid4(),
                    actor_role="DESIGNER",
                )
                return "ok"
            except PcsError as e:
                return e.code

    results = await asyncio.gather(submit_once(), submit_once())
    assert sorted(results) == ["SIM_STREAM_INVALID_TRANSITION", "ok"], results

    # ---- ② 批量：并发两次 ⇒ 都成功，但只有一条真正转移 ---------------
    async with maker() as s:
        await s.execute(
            Stream.__table__.update()
            .where(Stream.stream_id == sid)
            .values(sign_status="DRAFT")
        )
        await s.commit()

    from sqlalchemy import func, select
    from app.models.system import AuditLog

    async def transition_audit_count():
        async with maker() as s:
            return (
                await s.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.action == "RECORD_TRANSITION")
                    .where(AuditLog.resource_id == str(sid))
                )
            ).scalar_one()

    # ⚠️ 取**增量**：① 已经写过 1 条 ⇒ 绝对值不是 1
    before = await transition_audit_count()

    async def batch_once():
        async with maker() as s:
            res = await submit_batch(
                s, [sid],
                actor_user_id=actor_id,
                actor_role="DESIGNER",
            )
            return res

    r1, r2 = await asyncio.gather(batch_once(), batch_once())
    notes = [item.note for res in (r1, r2) for item in res.succeeded]
    assert "already_in_approval" in notes, (
        f"并发批次里没有幂等命中：{r1} / {r2}"
    )

    after = await transition_audit_count()
    assert after - before == 1, (
        f"并发批次写了 {after - before} 条单条转移审计（应恰好 1 条）⇒ 行锁被绕过"
    )

    # ---- ③ 提前返回路径**必须释放行锁**（否则锁跨条目累积 ⇒ 死锁环）----
    # 场景：两个并发批次，**重叠的物流、顺序相反**，且都撞上「幂等命中」
    #       （已 IN_APPROVAL ⇒ 提前返回 ⇒ 若不释放锁 ⇒ 交叉等待 ⇒ 死锁）。
    # ⚠️ 用**两个连接**（两个 session）⇒ 同库不同事务 ⇒ 行锁真的互斥。
    async with maker() as s:
        for target in (sid, sid2):
            await s.execute(
                Stream.__table__.update()
                .where(Stream.stream_id == target)
                .values(sign_status="IN_APPROVAL")
            )
        await s.commit()

    import asyncio as _asyncio

    async def batch_ids(ids):
        async with maker() as s:
            res = await submit_batch(
                s, ids,
                actor_user_id=actor_id,
                actor_role="DESIGNER",
            )
            return res

    # ⚠️ **超时保护**：真有死锁 ⇒ PG 在 deadlock_timeout 后中止一方 ⇒
    #    抛 DeadlockDetected ⇒ 我们**希望**它红（⇒ 修法失效）。
    try:
        r_a, r_b = await _asyncio.wait_for(
            _asyncio.gather(
                batch_ids([sid, sid2]),
                batch_ids([sid2, sid]),
            ),
            timeout=30,
        )
    except _asyncio.TimeoutError as e:
        raise AssertionError(
            "两个顺序相反的并发批次卡住 ⇒ 死锁（提前返回路径没释放行锁）"
        ) from e
    except Exception as e:
        # ⚠️ PG 的死锁中止会以 OperationalError/DeadlockDetected 冒出来
        raise AssertionError(
            f"并发批次报错（死锁？）: {type(e).__name__}: {e}"
        ) from e

    # 两个批次都应成功（幂等命中 ⇒ 记成功）
    assert len(r_a.succeeded) == 2, r_a
    assert len(r_b.succeeded) == 2, r_b

    await engine.dispose()
    print("P9B3B_CONCURRENCY_OK")


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
            # ⚠️ **scoped_url** ⇒ 表建在隔离 schema 里（pydantic-settings：
            #    环境变量优先于 .env ⇒ `settings.database_url` 就是 scoped URL）
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
            f"并发脚本失败:\n{result.stdout}\n{result.stderr}"
        )
        assert "P9B3B_CONCURRENCY_OK" in result.stdout, result.stdout
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
