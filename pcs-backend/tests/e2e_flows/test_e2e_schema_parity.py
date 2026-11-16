"""E2E-018：两库 schema 版本一致（P10-B · T6）。

## ⚠️ **必须一库一个进程**（CLAUDE.md §测试前检查 · 2026-11-01 实测打脸）

alembic 的 `settings` 是 **pydantic 缓存实例** ⇒ **同一进程内**第二次改
`DATABASE_URL` **不生效** ⇒ 两个库都读到第一个库 ⇒ 输出**无法区分**
⇒ ⇒ 「看着两库一致，其实只查了一个」⇒ ⇒ **各起一个独立子进程**。

## ⚠️ 不能只信命令输出

CLAUDE.md 记着一次「`current` 打出 `(head)`、`check` 打出
`No new upgrade operations detected`（exit 0）⇒ 看着全绿，**实际根本没在
`pcs_test` 上跑**」⇒ ⇒ **直查库的 `alembic_version`** ⇒ 而不只是看命令的输出。

⚠️ **口令只在环境变量里**（子进程继承 `DATABASE_URL`，不写命令行）。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]

#: 读 `alembic_version` 的子进程脚本（**只读**，不改任何东西）。
_READ_REVISION = """
import os, sys
from sqlalchemy import create_engine, text
url = os.environ["DATABASE_URL"].replace("+asyncpg", "+psycopg")
engine = create_engine(url)
with engine.connect() as conn:
    print(conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one())
engine.dispose()
"""


def _revision_of(url: str) -> str:
    """**独立子进程**读一个库的 `alembic_version`。"""
    result = subprocess.run(
        [sys.executable, "-c", _READ_REVISION],
        cwd=BACKEND_ROOT,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"读 schema 版本失败：\n{result.stdout}\n{result.stderr}"
    )
    return result.stdout.strip()


@pytest.mark.e2e
async def test_e2e_018_pcs_and_pcs_test_schema_versions_match():
    """两库（`pcs` / `pcs_test`）的 `alembic_version` **相同**。

    ⚠️ **不一致就登记**（本批不修）⇒ 断言直接红 ⇒ 差在哪一眼看得见。
    """
    from dotenv import dotenv_values

    dev_url = dotenv_values(BACKEND_ROOT / ".env").get("DATABASE_URL")
    assert dev_url, "`.env` 里没有 DATABASE_URL ⇒ 没法做两库对比"
    test_url = re.sub(r"/pcs(\?|$)", r"/pcs_test\1", dev_url)
    assert test_url != dev_url, f"两库 URL 派不出来：{dev_url}"

    pcs_rev = _revision_of(dev_url)
    pcs_test_rev = _revision_of(test_url)

    assert pcs_rev == pcs_test_rev, (
        f"两库 schema 版本不一致：pcs={pcs_rev} · pcs_test={pcs_test_rev}"
        "⇒ 登记偏离（本批不修）"
    )
