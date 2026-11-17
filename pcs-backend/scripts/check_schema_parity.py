"""两库 schema 版本**与代码 head** 对齐的发布前闸门 —— P10-B 评审 **#20 / #21**。

## 为什么要有它（为什么不在 E2E 车道里）

`tests/e2e_flows/test_e2e_schema_parity.py`（已删除）原来是一条
**E2E 车道**里的用例 ⇒ ⇒ 但它断的是**两个开发库**（`pcs` / `pcs_test`）的
`alembic_version` ⇒ ⇒ 三重错位：

1. **职责错位** —— E2E 车道是「隔离 schema 里的端到端场景」；
   「两库 schema 版本一致」是**发布前检查**（CLAUDE.md 的清单第 1 条）。
2. **几乎不会执行** —— E2E 车道是「批末跑一次」⇒ ⇒ 这条发布前检查实际上
   **长期不跑**。
3. **让车道不再 hermetic** —— 开发库不可达 / 未迁移 ⇒ 车道红 ⇒ 而红的理由
   与车道本身无关。

⇒ ⇒ **搬到这里**（`scripts/gate_alembic_check.py` 旁边）⇒ 随发布前检查跑。

## ⚠️ **必须一库一个进程**（CLAUDE.md §测试前检查 · 2026-11-01 实测打脸）

alembic 的 `settings` 是 **pydantic 缓存实例** ⇒ **同一进程内**第二次改
`DATABASE_URL` **不生效** ⇒ 两个库都读到第一个库 ⇒ 输出**无法区分**
⇒ ⇒ 「看着两库一致，其实只查了一个」⇒ ⇒ **各起一个独立子进程**。

## ⚠️ 不能只信命令输出

CLAUDE.md 记着一次「`current` 打出 `(head)`、`check` 打出
`No new upgrade operations detected`（exit 0）⇒ 看着全绿，**实际根本没在
`pcs_test` 上跑**」⇒ ⇒ **直查库的 `alembic_version`** ⇒ 而不只是看命令的输出。

## ⚠️ 断的是「**与代码 head 对齐**」，不是「两库彼此相同」（评审 #21）

只比彼此 ⇒ ⇒ **两库都落后也绿**（都停在 `p9_006`，代码 head 是 `p10_002`
⇒ 两库「一致」⇒ 绿 ⇒ 而它们其实都落后）⇒ ⇒ 本闸断的是
**每个库 == 代码 head**（`alembic/versions/` 里最新的那个 revision）。

⚠️ **口令只在环境变量里**（子进程继承 `DATABASE_URL`，不写命令行）。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

#: 读 `alembic_version` 的子进程脚本（**只读**，不改任何东西）。
_READ_REVISION = """
import os
from sqlalchemy import create_engine, text
url = os.environ["DATABASE_URL"].replace("+asyncpg", "+psycopg")
engine = create_engine(url)
with engine.connect() as conn:
    print(conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one())
engine.dispose()
"""


@dataclass(frozen=True)
class Probe:
    """一个库的探针结果。"""

    #: 该库的 `alembic_version`（直查 ⇒ 权威）
    revision: str
    #: `alembic check` 的退出码（0 = 无 ORM↔迁移漂移）
    drift_rc: int
    #: `alembic check` 的输出（给人看的）
    drift_output: str = ""


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def code_head() -> str:
    """代码里的 head revision（`alembic heads` ⇒ **不连库**）。

    ⚠️ 取**输出里的 revision id**（不是 `(head)` 那个词）⇒ 多 head 时取第一个
    ⇒ 并在输出里留痕（真出现多 head 时 `alembic check` 自己会红）。
    """
    result = _run([sys.executable, "-m", "alembic", "heads"])
    if result.returncode != 0:
        raise RuntimeError(f"alembic heads 失败：\n{result.stdout}\n{result.stderr}")
    match = re.search(r"^\s*([0-9A-Za-z_]+)\b.*\(head\)", result.stdout, re.M)
    if not match:
        raise RuntimeError(f"解析不出 head revision：\n{result.stdout}")
    return match.group(1)


def probe_database(url: str) -> Probe:
    """探**一个**库（直查 revision + 跑 `alembic check`）⇒ 独立子进程。"""
    env = {**os.environ, "DATABASE_URL": url}

    revision_run = _run([sys.executable, "-c", _READ_REVISION], env=env)
    if revision_run.returncode != 0:
        raise RuntimeError(
            f"读 schema 版本失败：\n{revision_run.stdout}\n{revision_run.stderr}"
        )
    revision = revision_run.stdout.strip()

    check_run = _run([sys.executable, "-m", "alembic", "check"], env=env)
    return Probe(
        revision=revision,
        drift_rc=check_run.returncode,
        drift_output=(check_run.stdout + check_run.stderr).strip(),
    )


def default_urls() -> list[tuple[str, str]]:
    """目标库清单（从 `.env` **进程内**派生 ⇒ 口令不进命令行）。

    ⇒ `pcs`（开发库，`.env` 里那个）· `pcs_test`（同名派生）。
    """
    from dotenv import dotenv_values

    dev_url = dotenv_values(BACKEND_DIR / ".env").get("DATABASE_URL")
    if not dev_url:
        raise RuntimeError("`.env` 里没有 DATABASE_URL ⇒ 没法做两库对比")
    test_url = re.sub(r"/pcs(\?|$)", r"/pcs_test\1", dev_url)
    if test_url == dev_url:
        raise RuntimeError(f"两库 URL 派不出来：{dev_url}")
    return [("pcs", dev_url), ("pcs_test", test_url)]


def main(
    argv: list[str] | None = None,
    *,
    probe: Callable[[str], Probe] | None = None,
    urls: list[tuple[str, str]] | None = None,
) -> int:
    """退出码：**0** = 每个库都在代码 head 且无漂移；**1** = 有问题。"""
    probe = probe or probe_database
    urls = urls if urls is not None else default_urls()

    head = code_head()
    print(f"代码 head：{head}")

    failed: list[str] = []
    for name, url in urls:
        try:
            result = probe(url)
        except Exception as exc:  # noqa: BLE001 — 一个库查不到 ⇒ 整闸门红
            failed.append(f"{name}: 探测失败：{exc}")
            print(f"  {name:10s} ❌ 探测失败：{exc}")
            continue
        ok = result.revision == head and result.drift_rc == 0
        mark = "✅" if ok else "❌"
        print(f"  {name:10s} {mark} revision={result.revision}")
        if not ok:
            if result.revision != head:
                failed.append(
                    f"{name}: revision={result.revision} ≠ 代码 head={head}"
                    " ⇒ **落后** ⇒ 跑 `alembic upgrade head`"
                )
            if result.drift_rc != 0:
                failed.append(
                    f"{name}: `alembic check` exit {result.drift_rc} ⇒ 有 ORM↔迁移漂移"
                    f"\n{result.drift_output}"
                )

    if failed:
        print("\nFAIL：", file=sys.stderr)
        for line in failed:
            print(f"  - {line}", file=sys.stderr)
        print(
            "\n⚠️ **必须一库一个进程**（CLAUDE.md）—— 同一进程内第二次改 "
            "DATABASE_URL 不生效 ⇒ 两库都读到第一个库 ⇒ 输出无法区分。",
            file=sys.stderr,
        )
        return 1
    print("\nOK：所有目标库都在代码 head 且 `alembic check` 干净。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
