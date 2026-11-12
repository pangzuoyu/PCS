"""AI 审计写库的**真 PG** 幂等（PG 车道 · P10-A · T10 的补充）。

## 为什么单测不够

单测跑在**内存 SQLite** 上 ⇒ 走的是「先查后插 + catch IntegrityError」
那条分支 ⇒ **完全碰不到** PG 的 `INSERT ... ON CONFLICT`。
⇒ 而 PG 那条分支**曾经是坏的**：`ON CONFLICT (request_id)` 匹配不到
**partial** 唯一索引（`WHERE request_id IS NOT NULL`）⇒ PG 抛
`InvalidColumnReferenceError: there is no unique or exclusion constraint
matching the ON CONFLICT specification`
⇒ **单测全绿、真库每次写审计都炸**。

⚠️ 这正是本仓最怕的形状：**单测照绿、真库会炸**（CLAUDE.md「漂移盲区」）。
⇒ 本文件把「PG 上写两次只有一行」钉死。

## 手法（沿用 `tests/api/v1/test_stream_batch_concurrency_pg.py`）

隔离 schema ⇒ 在它上面 `alembic upgrade head` ⇒ 用
`options=-csearch_path=<schema>` 连过去 ⇒ 测完 `DROP SCHEMA ... CASCADE`
⇒ 开发库一个字节都不动。

⚠️ `pg` marker 的用例平时被 `pytest.skip` 静默跳过 ⇒ 绿灯**证明不了**
它们跑过 ⇒ **必须**经 `scripts/pytest_pg.sh`（唯一入口）跑。
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

#: 本文件在 `tests/services/ai/`（与 `tests/api/v1/` 同深度）⇒
#: `parents[3]` = `pcs-backend`（`alembic.ini` 与 `.env` 都在那儿）。
#: ⚠️ 取 `parents[4]`（仓库根）⇒ 子进程 cwd 里**没有** `alembic.ini`
#: ⇒ alembic 报「No 'script_location' key found in configuration」。
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
def test_ai_audit_write_is_idempotent_on_real_postgres():
    """⚠️ **真 PG** 上写两次同一 `request_id` ⇒ 只有一行（不抛）。

    ⚠️ 这条用例**曾经红过**：PG 的 `ON CONFLICT (request_id)` 匹配不到
    partial 唯一索引 ⇒ 抛 `InvalidColumnReferenceError` ⇒ **每次写 AI 审计
    都会炸**（而单测全绿）。
    """
    url = _pg_url()
    if url is None:
        pytest.skip(
            "无 PostgreSQL URL —— 引擎级验证须经 scripts/pytest_pg.sh 跑（唯一入口）"
        )

    schema = f"iso_ai_audit_{uuid.uuid4().hex[:8]}"
    scoped_url = url + ("&" if "?" in url else "?") + f"options=-csearch_path={schema}"
    script = r'''
import asyncio, os, uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.system import AiAuditLog
from app.workers.ai_audit_tasks import write_ai_audit_log


async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    ctx = {"session_factory": maker}

    def fields(request_id):
        return {
            "request_id": request_id,
            "client_request_id": None,
            "endpoint": "/api/v1/ai/intent",
            "status_code": 501,
            "duration_ms": 3,
            "sanitized_request_hash": "sha256:deadbeef",
            "response_summary": "AI_NOT_IMPLEMENTED",
            "model_version": None,
            "user_id": None,
        }

    req_a = str(uuid.uuid4())
    # ⚠️ **写两次**（模拟重投）⇒ 不得抛、且只有一行
    await write_ai_audit_log(ctx, **fields(req_a))
    await write_ai_audit_log(ctx, **fields(req_a))

    req_b = str(uuid.uuid4())
    await write_ai_audit_log(ctx, **fields(req_b))

    # ⚠️ **超长字段**（客户端可控）：`X-Request-ID` 可以是任意长度 ⇒
    #    PG 的 `varchar(128)` 超长 ⇒ `22001 string_data_right_truncation`
    #    ⇒ 若不截断 ⇒ **这一行审计被静默丢弃**（调用方毫无感知）
    #    ⇒ 审计表对「用超长头探测」的行为**完全失明**。
    req_c = str(uuid.uuid4())
    long_fields = fields(req_c)
    long_fields["client_request_id"] = "x" * 200
    await write_ai_audit_log(ctx, **long_fields)

    async with maker() as s:
        count_a = (
            await s.execute(
                select(func.count()).select_from(AiAuditLog).where(
                    AiAuditLog.request_id == req_a
                )
            )
        ).scalar_one()
        count_b = (
            await s.execute(
                select(func.count()).select_from(AiAuditLog).where(
                    AiAuditLog.request_id == req_b
                )
            )
        ).scalar_one()
        count_c = (
            await s.execute(
                select(func.count()).select_from(AiAuditLog).where(
                    AiAuditLog.request_id == req_c
                )
            )
        ).scalar_one()
        stored = (
            await s.execute(
                select(AiAuditLog.client_request_id).where(
                    AiAuditLog.request_id == req_c
                )
            )
        ).scalar_one_or_none()
        total = (
            await s.execute(select(func.count()).select_from(AiAuditLog))
        ).scalar_one()

    assert count_a == 1, f"同一 request_id 写了 {count_a} 行（应恰好 1 行）"
    assert count_b == 1, f"另一个 request_id 写了 {count_b} 行"
    assert count_c == 1, (
        f"超长 client_request_id 让这一行审计**被丢弃**了（count={count_c}）"
        " ⇒ 审计表对「用超长头探测」完全失明"
    )
    assert stored is not None and len(stored) <= 128, (
        f"落库的 client_request_id 长度 {len(stored or '')} > 128 ⇒ 未截断"
    )
    assert total == 3, f"表里共 {total} 行（应恰好 3 行）"

    await engine.dispose()
    print("AI_AUDIT_PG_OK")


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
            f"AI 审计写库脚本失败:\n{result.stdout}\n{result.stderr}"
        )
        assert "AI_AUDIT_PG_OK" in result.stdout, result.stdout
    finally:
        subprocess.run(
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
            timeout=300,
        )
