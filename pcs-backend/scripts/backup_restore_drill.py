"""备份**演练**：把库 dump 出来 ⇒ 再恢复到一个临时库 ⇒ ⇒ **验证恢复出来的库能用**。

## 为什么要有这个（计划 `docs/superpowers/plans/2026-11-23-p10-c-deploy-observability.md` T1 · 备份演练）

「有备份脚本」**不等于**「备份有用」⇒ ⇒ ⇒ 真出事时才发现恢复出来是坏的
⇒ ⇒ ⇒ ⇒ 那时候已经晚了 ⇒ ⇒ ⇒ ⇒ ⇒ 所以要**定期演练**。

⇒ ⇒ 本脚本是**可验证**的演练：恢复完 ⇒ ⇒ ⇒ **断言**
① 恢复库的 migration revision == code head
② `alembic check` 在恢复库上 exit 0（⇒ ⇒ ORM 与恢复出来的 schema 一致）
③ 关键表的**行数**与源库一致（⇒ ⇒ 数据没丢）
⇒ ⇒ ⇒ 任一条不满足 ⇒ ⇒ ⇒ **非零退出** ⇒ ⇒ ⇒ 演练失败是可被发现的。

## ⚠️ 口令**不出现在命令行**

`pg_dump` / `psql` 用 `PGPASSWORD` **环境变量**（不是命令行参数）
⇒ ⇒ ⇒ 命令行里只有 host/port/user/db ⇒ ⇒ ⇒ 不进 shell 历史、不进进程表。

## 用法

    cd pcs-backend
    uv run python scripts/backup_restore_drill.py --dry-run   # 只做 dump，不恢复
    uv run python scripts/backup_restore_drill.py

⚠️ **只读源库**（`pg_dump` 是只读的）⇒ ⇒ ⇒ 不污染开发库。
⚠️ 临时库在**结束时被删掉**（`finally`）⇒ ⇒ ⇒ 失败也不留垃圾。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlparse

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

#: 关键表（**行数必须一致** ⇒ ⇒ ⇒ 数据没丢）⇒ ⇒ ⇒ 挑「业务上最重要 + 行数不多」的
KEY_TABLES = ("projects", "users", "user_projects", "streams", "workspaces")


def _db_parts() -> tuple[str, int, str, str, str]:
    """从 `.env` 的 `DATABASE_URL` 解析出 (host, port, user, password, dbname)。

    ⚠️ 口令**只在进程内** ⇒ ⇒ ⇒ 不出现在命令行 / 环境导出不必要的地方。
    """
    from dotenv import dotenv_values

    url = dotenv_values(_BACKEND_ROOT / ".env").get("DATABASE_URL")
    if not url:
        raise SystemExit("[ERROR] `.env` 里没有 DATABASE_URL")
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://"))
    return (
        parsed.hostname or "localhost",
        parsed.port or 5432,
        parsed.username or "pcs",
        parsed.password or "",
        (parsed.path or "/pcs").lstrip("/"),
    )


def _run(cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd, timeout=1800)


def _psql_env(password: str) -> dict[str, str]:
    """给 `psql` / `pg_dump` 用的环境（口令走 `PGPASSWORD` ⇒ ⇒ 不上命令行）。"""
    env = dict(os.environ)
    env["PGPASSWORD"] = password
    return env


def _scalar(psql: list[str], env: dict[str, str], sql: str) -> str:
    """跑一条 SQL ⇒ ⇒ 取第一行第一列。"""
    result = _run([*psql, "-tAc", sql], env=env)
    if result.returncode != 0:
        raise SystemExit(f"[ERROR] SQL 失败：{sql}\n{result.stderr}")
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="备份演练（dump → 恢复 → 断言）。")
    parser.add_argument("--dry-run", action="store_true", help="只做 dump，不恢复不验证")
    args = parser.parse_args(argv)

    host, port, user, password, dbname = _db_parts()
    env = _psql_env(password)
    psql_base = ["psql", "-h", host, "-p", str(port), "-U", user, "-d"]

    with tempfile.TemporaryDirectory(prefix="pcs-drill-") as tmp:
        dump_path = Path(tmp) / "backup.sql"
        print(f"[1/5] dump 源库 {dbname} → {dump_path.name}")
        dumped = _run(
            ["pg_dump", "-h", host, "-p", str(port), "-U", user, "-d", dbname, "-Fc", "-f", str(dump_path)],
            env=env,
        )
        if dumped.returncode != 0:
            print(f"[ERROR] pg_dump 失败：{dumped.stderr}", file=sys.stderr)
            return 1
        size_mb = dump_path.stat().st_size / 1024 / 1024
        print(f"      dump 大小 {size_mb:.2f} MB")
        if args.dry_run:
            print("[DRY-RUN] 未恢复、未验证")
            return 0

        drill_db = f"pcs_backup_drill_{uuid.uuid4().hex[:8]}"
        print(f"[2/5] 建临时库 {drill_db}")
        created = _run(["createdb", "-h", host, "-p", str(port), "-U", user, drill_db], env=env)
        if created.returncode != 0:
            print(f"[ERROR] createdb 失败：{created.stderr}", file=sys.stderr)
            return 1

        try:
            print(f"[3/5] 恢复到 {drill_db}")
            restored = _run(
                ["pg_restore", "-h", host, "-p", str(port), "-U", user, "-d", drill_db, "--no-owner", str(dump_path)],
                env=env,
            )
            if restored.returncode != 0:
                print(f"[ERROR] pg_restore 失败：{restored.stderr}", file=sys.stderr)
                return 1

            print("[4/5] 断言 ① 恢复库的 revision == code head")
            src_rev = _scalar([*psql_base, dbname], env, "SELECT version_num FROM alembic_version")
            dst_rev = _scalar([*psql_base, drill_db], env, "SELECT version_num FROM alembic_version")
            if src_rev != dst_rev:
                print(f"[ERROR] revision 不一致：源={src_rev} 恢复={dst_rev}", file=sys.stderr)
                return 1
            print(f"      revision = {dst_rev} ✔")

            print("[5/5] 断言 ②③ 行数一致 + alembic check")
            for table in KEY_TABLES:
                src_n = _scalar([*psql_base, dbname], env, f"SELECT count(*) FROM {table}")
                dst_n = _scalar([*psql_base, drill_db], env, f"SELECT count(*) FROM {table}")
                if src_n != dst_n:
                    print(
                        f"[ERROR] {table} 行数不一致：源={src_n} 恢复={dst_n} ⇒ ⇒ 数据丢了",
                        file=sys.stderr,
                    )
                    return 1
                print(f"      {table}: {dst_n} 行 ✔")

            # ⇒ ⇒ `alembic check` 在**恢复库**上跑 ⇒ ⇒ ⇒ 验证「恢复出来的 schema
            # ⇒ ⇒ ⇒ 与 ORM 一致」⇒ ⇒ ⇒ ⇒ （这是「备份有用」的真正判据）
            drill_url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{drill_db}"
            check = _run(
                ["uv", "run", "--frozen", "alembic", "check"],
                env={**os.environ, "DATABASE_URL": drill_url},
                cwd=_BACKEND_ROOT,
            )
            if check.returncode != 0:
                print(
                    f"[ERROR] `alembic check` 在恢复库上失败（exit {check.returncode}）\n"
                    f"{check.stdout}\n{check.stderr}",
                    file=sys.stderr,
                )
                return 1
            print("      alembic check exit 0 ✔")

            print("[OK] 备份演练通过 ⇒ ⇒ 恢复出来的库可用")
            return 0
        finally:
            dropped = _run(["dropdb", "-h", host, "-p", str(port), "-U", user, "--if-exists", drill_db], env=env)
            if dropped.returncode != 0:
                print(f"[WARN] 临时库 {drill_db} 删不掉 ⇒ ⇒ 手工清", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
