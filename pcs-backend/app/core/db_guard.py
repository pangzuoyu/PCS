"""目标库白名单守卫 —— E2E 车道 / 种子脚本（P10-B 评审 #8 · P1）。

## 为什么要有它

E2E 车道（`tests/e2e_flows/`）与流程种子脚本（`scripts/seed_e2e_flows.py`）
都会**建 schema / 跑迁移 / 灌种子** ⇒ ⇒ 一旦它们指向了**开发库 `pcs`** ⇒
⇒ 就在开发库里建隔离 schema + 灌 7 个用户 + 授权行 ⇒ ⇒ **污染开发数据**。

## 判据：**真实连接的库名**（不是 URL 字符串、不是环境变量）

- ⚠️ **不用 `PCS_E2E_LANE` 当判据** —— 它只是个环境变量 ⇒ 谁都能设 ⇒
  ⇒ 判据必须是**连上去的那个库**（`current_database()`）。
- URL 的库名只当**快速预筛**（连都不连就拒 ⇒ 不给误操作留窗口）⇒
  ⇒ 真正的判据是 `current_database()`。

## 白名单

只允许**专用的测试库**：`pcs_pgtest`（compose 的 postgres-pgtest · 宿主 5433）·
`pcs_test`（5432 上的专用测试库）⇒ ⇒ **开发库 `pcs` 与系统库一律拒绝**。

⚠️ **fail-closed**：库名取不到（None / 空 / URL 解析不出）⇒ **当作拒绝**
⇒ ⇒ 「不知道连到哪」**不等于**「连对了」。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ALLOWED_LANE_DATABASES",
    "LaneDatabaseNotAllowed",
    "assert_allowed_lane_database",
    "current_database_name",
    "db_name_from_url",
]


#: **允许**的目标库（显式枚举 ⇒ 可审计 ⇒ 新库要么加进来要么就是拒绝）。
ALLOWED_LANE_DATABASES: frozenset[str] = frozenset({"pcs_pgtest", "pcs_test"})


class LaneDatabaseNotAllowed(RuntimeError):
    """目标库不在白名单 ⇒ **fail-closed**（不降级、不放行）。"""


def db_name_from_url(url: str) -> str | None:
    """从 PG URL 的**路径段**取库名；取不到 ⇒ `None`。

    ⚠️ 只当**快速预筛**用 —— 真判据是 `current_database()`（见模块 docstring）。
    """
    if not url or "://" not in url:
        return None
    path = url.split("://", 1)[1]
    # ⚠️ 去掉查询串/参数（`?options=-csearch_path=…`）⇒ 别把它当库名
    path = path.split("?", 1)[0].split("#", 1)[0]
    # ⚠️ 去掉 host:port（最后一个 `@` 之后）
    host_part = path.rsplit("@", 1)[-1]
    segments = host_part.split("/")
    if len(segments) < 2:
        return None
    name = segments[-1].strip()
    return name or None


def assert_allowed_lane_database(db_name: str | None, *, purpose: str) -> str:
    """库名不在白名单 ⇒ **抛 `LaneDatabaseNotAllowed`**；在 ⇒ 原样返回。

    ⚠️ `None` / 空串 ⇒ **当作拒绝**（fail-closed）。
    """
    if not db_name or db_name not in ALLOWED_LANE_DATABASES:
        allowed = ", ".join(sorted(ALLOWED_LANE_DATABASES))
        raise LaneDatabaseNotAllowed(
            f"{purpose}：目标库 {db_name!r} **不在白名单** ⇒ 拒绝执行。"
            f"允许的库：{allowed}。"
            "⇒ 若是本机开发库（pcs）⇒ **绝不能**用它跑车道/种子；"
            "⇒ 改用 compose 的 postgres-pgtest（pcs_pgtest · 宿主 5433）："
            "`docker compose --profile pg up -d postgres-pgtest`。"
        )
    return db_name


async def current_database_name(session: Any) -> str:
    """查**真实连接**的库名（`current_database()`）。"""
    from sqlalchemy import text

    result = await session.execute(text("SELECT current_database()"))
    return str(result.scalar_one())
