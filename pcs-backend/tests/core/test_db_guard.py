"""目标库白名单守卫（P10-B 评审 #8 · P1）。

## 为什么要有它

E2E 车道（`tests/e2e_flows/`）与流程种子脚本（`scripts/seed_e2e_flows.py`）
都会**建 schema / 跑迁移 / 灌种子** ⇒ ⇒ 一旦它们指向了**开发库 `pcs`** ⇒
⇒ 就在开发库里建隔离 schema + 灌 7 个用户 + 授权行 ⇒ ⇒ **污染开发数据**。

⇒ 守卫按**真实连接的库名**（`current_database()`，不是 URL 字符串）判定 ⇒
⇒ 只允许 `pcs_pgtest` / `pcs_test` ⇒ 其余（含 `pcs`）**fail-closed**。

⚠️ **不用 `PCS_E2E_LANE` 当判据** —— 它只是个环境变量 ⇒ 谁都能设 ⇒
⇒ 判据必须是**连上去的那个库**。
"""
from __future__ import annotations

import pytest

from app.core.db_guard import (
    ALLOWED_LANE_DATABASES,
    LaneDatabaseNotAllowed,
    assert_allowed_lane_database,
    current_database_name,
    db_name_from_url,
)


def test_allowed_set_is_explicit_and_excludes_the_dev_db():
    """白名单**显式**枚举 ⇒ 且**不含**开发库 `pcs`。"""
    assert "pcs" not in ALLOWED_LANE_DATABASES
    assert ALLOWED_LANE_DATABASES == frozenset({"pcs_pgtest", "pcs_test"})


@pytest.mark.parametrize("db_name", sorted(ALLOWED_LANE_DATABASES))
def test_allowed_databases_pass(db_name: str):
    assert assert_allowed_lane_database(db_name, purpose="E2E 车道") == db_name


@pytest.mark.parametrize("db_name", ["pcs", "postgres", "template1", "", None])
def test_other_databases_are_rejected(db_name):
    """**开发库 `pcs` 与其它库一律拒绝** ⇒ fail-closed。"""
    with pytest.raises(LaneDatabaseNotAllowed) as exc:
        assert_allowed_lane_database(db_name, purpose="E2E 车道")
    # ⚠️ 错误信息要**说清拒的是哪个库** + **怎么改**（否则排查只能猜）
    assert str(db_name) in str(exc.value) or "None" in str(exc.value)
    assert "pcs_pgtest" in str(exc.value)


def test_db_name_from_url_reads_the_path():
    """URL 的**路径段**就是库名（不是 host、不是 user）。"""
    assert db_name_from_url("postgresql+psycopg://u:p@localhost:5432/pcs") == "pcs"
    assert (
        db_name_from_url("postgresql+psycopg://u:p@localhost:5433/pcs_pgtest")
        == "pcs_pgtest"
    )
    # ⚠️ 带查询串的 URL 也不能把查询当成库名
    assert (
        db_name_from_url("postgresql+psycopg://u:p@h:5432/pcs?options=-cx%3Dy")
        == "pcs"
    )
    assert db_name_from_url("not-a-url") is None


async def test_current_database_name_reads_the_live_connection():
    """判据来自**真实连接**（`current_database()`）⇒ 不是 URL 字符串。"""

    class _Result:
        def scalar_one(self):
            return "pcs_pgtest"

    class _Session:
        def __init__(self):
            self.statements: list[str] = []

        async def execute(self, statement):
            self.statements.append(str(statement))
            return _Result()

    session = _Session()
    assert await current_database_name(session) == "pcs_pgtest"
    assert "current_database()" in session.statements[0]
