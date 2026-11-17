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
    "PUBLIC_SCHEMA",
    "assert_allowed_lane_database",
    "current_database_name",
    "current_schema_name",
    "db_name_from_url",
    "factory_database_url",
    "is_isolated_lane_context",
]


#: **允许**的目标库（显式枚举 ⇒ 可审计 ⇒ 新库要么加进来要么就是拒绝）。
ALLOWED_LANE_DATABASES: frozenset[str] = frozenset({"pcs_pgtest", "pcs_test"})

#: `public` schema 名 —— 「当前 schema 就是 public」⇒ **不是**隔离上下文。
PUBLIC_SCHEMA = "public"


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


async def current_schema_name(session: Any) -> str:
    """查**真实连接**的 schema 名（`current_schema()`）。

    ⚠️ 隔离 schema 是靠 `search_path` 设的 ⇒ ⇒ `current_schema()` 返回的
    就是那个隔离 schema 的名字 ⇒ ⇒ 它是「**是不是隔离上下文**」的判据。
    """
    from sqlalchemy import text

    result = await session.execute(text("SELECT current_schema()"))
    return str(result.scalar_one())


async def is_isolated_lane_context(session: Any) -> bool:
    """当前连接是不是**车道隔离上下文**（白名单库 + 非 public schema）。

    ⚠️ **两条都要满足**（缺一条即拒绝 ⇒ fail-closed）：

    ① `current_database()` ∈ `ALLOWED_LANE_DATABASES`（真判据：连上去的那个库）
    ② `current_schema()` ≠ `public`（有人把 `search_path` 指到了专用 schema）

    ⚠️ **为什么还要 ②** —— 两条车道**共用同一个库**（`pcs_pgtest`）⇒ ⇒
    只看库名 ⇒ PG 车道（public schema）也会被当成「车道上下文」⇒ ⇒ 那条
    ⇒ 车道写的是**共享** schema ⇒ ⇒ 用「schema 不是 public」把「隔离」认出来。
    """
    db_name = await current_database_name(session)
    if db_name not in ALLOWED_LANE_DATABASES:
        return False
    return await current_schema_name(session) != PUBLIC_SCHEMA


def factory_database_url(factory: Any) -> str | None:
    """session factory **真正会连**的 URL（从它绑定的 engine 上取）。

    ⚠️ 取不到 ⇒ `None` ⇒ 调用方按「不知道 ⇒ 拒绝」处理（fail-closed）。
    ⚠️ **为什么要从 engine 取而不是从 settings 取** —— 判据必须是
    「**这条连接**会去哪儿」，而不是「配置里写了什么」。
    """
    bind = getattr(factory, "kw", {}).get("bind")
    url = getattr(bind, "url", None)
    return str(url) if url is not None else None
