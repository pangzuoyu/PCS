"""**执行级**的测试栈守卫（评审 #22 · 2026-11-12）。

## 为什么需要它

`tests/scripts/test_compose_test_profile.py` 只 **yaml.safe_load** 了
`docker-compose.yml` ⇒ 它断言的是「文件里**声明**了哪些字符串」⇒ 而

- `alembic upgrade head` 在 `pcs_pgtest` 上**真的**成功吗？
- `scripts/seed_e2e_data.py` 在**真 PG** 上**真的**能跑吗？
- seed **真的**幂等吗（跑两遍行数不涨）？

这三件事**从来没被执行过** ⇒ 那个守门是**空壳**（跟本批的架构守卫同病：
断言的形状与被守的东西无关）。

⇒ 本文件**真跑**那两条命令（migrate + seed），并**直查库**核对结果。

## 为什么跑的是「命令」而不是「compose 服务」

compose 的 `migrate` / `seed` 两个一次性服务，**内容**就是这两条命令
（`alembic upgrade head` / `python scripts/seed_e2e_data.py`），差别只在
「在容器里跑」还是「在宿主 venv 里跑」。

⇒ 本守卫跑**命令本体**（宿主 venv ⇒ 同一个 lock、同一份代码、**同一个库**
`pcs_pgtest`）⇒ 断言的是**实质**（迁移落没落 / 种子落没落 / 幂不幂等）。

⚠️ **为什么不在这里跑 compose 服务**：容器里 `uv run --frozen` 要
**重装一遍依赖 + 重下 ~600 MB**（实测 15~40 分钟，且本机 PyPI 抖动时
会卡住）⇒ 把它放进**每次都跑**的车道 ⇒ 车道的耗时与网络可用性绑死
⇒ 一次网络抖动就把车道变红，而**那不是产品缺陷**。

⇒ compose **路径**（README 里那条「怎么起测试栈」）由
`scripts/compose_test_stack.sh` 负责（它自己 fail-closed）⇒
**手动跑 / 发布前跑**，不进车道。

## 车道约定

⚠️ **只在 PG 车道里跑**（`@pytest.mark.pg`）⇒ 平时被静默跳过
⇒ **必须**经 `scripts/pytest_pg.sh`（唯一入口）跑。
⇒ 判据 = **PG 车道自己导出的** `TEST_DATABASE_URL`（指向 `pcs_pgtest`）
⇒ 默认车道没有这个变量 ⇒ 跳过（不是「验过了」）。

⚠️ **口令**只在环境变量里（`scripts/pytest_pg.sh` 已经导出了）
⇒ 本文件**不**碰口令、不写命令行。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

#: 后端根目录（`pcs-backend/`）。
BACKEND_ROOT = Path(__file__).resolve().parents[2]

#: 种子脚本（compose 的 `seed` 服务跑的就是它）。
SEED_SCRIPT = BACKEND_ROOT / "scripts" / "seed_e2e_data.py"

#: 种子必须造出行的表（与 `scripts/seed_e2e_data.py` 的口径一致）。
SEED_TABLES = ("workspaces", "projects", "users", "user_projects", "streams")


def _lane_url() -> str | None:
    """PG 车道的库 URL（`scripts/pytest_pg.sh` 导出的 `TEST_DATABASE_URL`）。"""
    url = os.environ.get("TEST_DATABASE_URL", "")
    return url or None


def _sync_url(url: str) -> str:
    """async URL → sync URL（本守卫用**同步**引擎直查库）。"""
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://").replace(
        "+asyncpg", "+psycopg"
    )


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env={**os.environ},  # DATABASE_URL 由车道导出 ⇒ 子进程继承
        capture_output=True,
        text=True,
        timeout=900,
    )


def _count(engine, table: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())


@pytest.mark.pg
def test_migrate_and_seed_really_run_on_the_test_database() -> None:
    """真跑 migrate + seed（两遍）⇒ 直查库核对 ⇒ 全程在**真 PG**上。

    ⚠️ **幂等的直接证据**：seed 跑**两遍** ⇒ `user_projects` / `streams`
    的行数**不能涨**（涨了 ⇒ 种子不是幂等 ⇒ 换台机器起测试栈会翻倍）。
    """
    url = _lane_url()
    if url is None or "pcs_pgtest" not in url:
        pytest.skip(
            "不在 PG 车道里（无 TEST_DATABASE_URL）⇒ 须经 scripts/pytest_pg.sh 跑"
        )

    # ① 迁移 —— 必须能在**真 PG** 上跑到 head
    migrated = _run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_ROOT
    )
    assert migrated.returncode == 0, (
        f"alembic upgrade head 失败：\n{migrated.stdout}\n{migrated.stderr}"
    )

    current = _run(
        [sys.executable, "-m", "alembic", "current"], cwd=BACKEND_ROOT
    )
    assert current.returncode == 0, current.stderr
    assert current.stdout.strip(), f"alembic current 没有输出：{current.stdout!r}"

    # ② 种子 —— 第一遍
    seeded = _run([sys.executable, str(SEED_SCRIPT)], cwd=BACKEND_ROOT)
    assert seeded.returncode == 0, (
        f"seed 失败（第一遍）：\n{seeded.stdout}\n{seeded.stderr}"
    )

    engine = create_engine(_sync_url(url))
    try:
        before = {t: _count(engine, t) for t in SEED_TABLES}

        # ③ 种子 —— 第二遍（**幂等**）
        seeded2 = _run([sys.executable, str(SEED_SCRIPT)], cwd=BACKEND_ROOT)
        assert seeded2.returncode == 0, (
            f"seed 失败（第二遍 ⇒ 不幂等）：\n{seeded2.stdout}\n{seeded2.stderr}"
        )

        after = {t: _count(engine, t) for t in SEED_TABLES}

        # ④ 直查库 —— 迁移落地 + 种子落地 + 幂等
        with engine.connect() as conn:
            revision = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert revision, "alembic_version 表是空的 ⇒ migrate 没落地"

        for table in SEED_TABLES:
            assert before[table] >= 1, (
                f"表 {table} 里没有种子行（count={before[table]}）⇒ seed 没落地"
            )
        for table in ("user_projects", "streams"):
            assert after[table] == before[table], (
                f"{table} 行数变了（{before[table]} → {after[table]}）⇒ seed 不幂等"
            )
    finally:
        engine.dispose()
