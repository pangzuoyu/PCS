"""进程级 session factory 的隔离 —— P10-B 评审 **#19** · P1。

## 为什么要有这个文件

车道的隔离**只**做在 `app.dependency_overrides[get_db]` 上 ⇒ ⇒
`app/db/session.py::get_async_session_factory()`（**模块级单例**）仍指
`pcs_pgtest` 的 **public schema** ⇒ ⇒ 下面两条路径读写的是**另一个房间**：

- `app/api/v1/ws.py:77`（WS 握手鉴权）
- `app/core/errors.py`（RBAC 拒绝的审计行 —— 评审 #10 的落点）

⇒ ⇒ 「真 app + 真库 + 同款路径」在这两条路径上**不成立** ⇒ ⇒ 而现有的
「不写 public」守卫**看不见它们**（守卫只跑 `POST /projects`）⇒ ⇒
本文件把**全局 factory** 也指向隔离 schema，并断言：

1. 全局 factory 连的 schema **就是**隔离 schema（`current_schema()`）；
2. 经全局 factory 写的行**只**出现在隔离 schema ⇒ public 一个字节不动。

⚠️ **断言形状**：断的是「schema 名」与「行落在哪」⇒ 断「连接成功」是空壳。
"""
from __future__ import annotations

import pytest

from app.core.db_guard import ALLOWED_LANE_DATABASES
from tests.e2e_flows.helpers import public_sync_url


@pytest.mark.e2e
async def test_global_session_factory_points_at_the_isolated_schema(
    e2e_client, e2e_schema
):
    """⚠️ **进程级 factory** 连的**是隔离 schema**（不是 public）。

    ⇒ `current_schema()` 就是隔离 schema 的名字
    ⇒ ⇒ `ws.py` / `errors.py` 这些**不经 `get_db`** 的路径与请求路径**同一个房间**。
    """
    from sqlalchemy import text

    from app.db.session import get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        schema = (
            await session.execute(text("SELECT current_schema()"))
        ).scalar_one()
        db = (await session.execute(text("SELECT current_database()"))).scalar_one()

    assert schema == e2e_schema, (
        f"全局 session factory 连的是 schema {schema!r}，不是隔离 schema "
        f"{e2e_schema!r} ⇒ 不经 get_db 的路径读写的是 public schema"
        "（评审 #19）"
    )
    assert db in ALLOWED_LANE_DATABASES, (
        f"全局 factory 连的库 {db!r} 不在车道白名单里（{sorted(ALLOWED_LANE_DATABASES)}）"
    )


@pytest.mark.e2e
async def test_rows_written_through_the_global_factory_stay_in_the_isolated_schema(
    e2e_client, e2e_schema
):
    """经**全局 factory** 写的行 ⇒ 只在隔离 schema ⇒ public **不变**。

    ⚠️ 断法：**先真写一行**（否则库里本来就没新行 ⇒ 「public 不变」是空壳）
    ⇒ ⇒ 且 public 断的是**写前/写后的快照相等**（不是「count == 0」）
    ⇒ ⇒ public 里**可能**已经有历史探针行 ⇒ 断「没变」才对。
    """
    from sqlalchemy import create_engine, text

    from app.db.session import get_async_session_factory
    from app.models.system import AuditLog

    probe_action = "E2E_GLOBAL_FACTORY_PROBE"

    # ⚠️ 用**独立连接**（不带 search_path）—— 用隔离 schema 的连接查 public
    # ⇒ 永远查不到 ⇒ 守卫恒绿 = 空壳。
    public_engine = create_engine(public_sync_url())

    def _public_count() -> int:
        with public_engine.connect() as conn:
            has_table = conn.execute(
                text("SELECT to_regclass('public.audit_logs')")
            ).scalar_one()
            if has_table is None:
                return 0
            return int(
                conn.execute(
                    text("SELECT count(*) FROM public.audit_logs WHERE action = :a"),
                    {"a": probe_action},
                ).scalar_one()
            )

    try:
        before = _public_count()

        factory = get_async_session_factory()
        async with factory() as session:
            session.add(
                AuditLog(
                    action=probe_action,
                    resource_type="PROBE",
                    resource_id=None,
                    detail_json={"probe": True},
                )
            )
            await session.commit()

        # ① 隔离 schema 里**看得见**这一行
        async with e2e_client._e2e_session_factory() as session:  # type: ignore[attr-defined]
            in_isolated = (
                await session.execute(
                    text("SELECT count(*) FROM audit_logs WHERE action = :a"),
                    {"a": probe_action},
                )
            ).scalar_one()
        assert in_isolated == 1, (
            f"隔离 schema 里探针行数 = {in_isolated}（期望 1）"
            "⇒ 全局 factory 没写进隔离 schema（评审 #19）"
        )

        # ② public schema **没变**
        after = _public_count()
    finally:
        public_engine.dispose()

    assert before == after, (
        f"public schema 被全局 factory 改了：{before} → {after}"
        "⇒ 不经 get_db 的路径写到了 public（评审 #19）"
    )
