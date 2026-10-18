"""并发同内容导出不得连带回滚调用方的事务（评审 #22）。

## 缺陷

`_upsert_report_file` 在撞唯一约束时这样恢复：

```python
except IntegrityError:
    await db.rollback()          # ← 回滚的是**调用方的整笔事务**
    return (await db.execute(select(ReportFile)...)).scalar_one()
```

`db` 是**共享 session**，`rollback()` 丢掉的是这一笔事务里**所有**未提交的
写入 —— 不只是自己那次失败的 INSERT。调用方在 `store_rendered` 之前做的
任何写入（`report_builder_tasks` 里的 `_build_style`、先前 `audit.write`
留下的 pending `AuditLog` 行）会一起消失，而且**不报任何错**：
它们只是没被提交。

## 为什么这个竞态难在测试里复现

要命中 `except` 分支，得让「查不到」与「插时冲突」之间发生一次提交 ——
真正的双连接竞态。直接跑两个 session 是撞不上的：B 先提交，A 的 SELECT
就会看到它，走早返回分支，`except` 根本不执行。

所以本文件**显式制造那个窗口**：把 `_upsert_report_file` 里那次
「按 content_hash 查已有行」的 SELECT 短路成空结果，代表
「我查的时候它不在，别人在我查之后插进去了」。这比真起两个协程
去抢一个微秒窗口可靠，也不依赖调度。

## ⚠️ 第一版这个假执行器是**空操作**，两条测试都是空洞地绿的

第一版靠 `"content_hash" in str(stmt.whereclause)` 判断「这是不是那次
content_hash 查询」。实测 `str(Select.whereclause)` 是**空串**（SQLAlchemy
2.0 上这个属性并不给出可匹配的文本），条件从未命中 ⇒ 短路从未发生 ⇒
`existing` 被正常查到 ⇒ **早返回分支**，`except IntegrityError` 根本没执行，
自然没有 `rollback()`，自然也没有数据丢失 ⇒ 测试绿。

把「测试通过」读成「事务没有被回滚」，而实际是「**回滚从未被触发**」。
两个都叫绿，含义完全相反。这是
`docs/solutions/testing-issues/sqlite-staticpool-hides-uncommitted.md`
里第三级假绿的又一例：**功能从未执行**。

改成**按调用序数**短路（第一次 `db.execute` 是 content_hash 查询，
其后一律放行）—— 不依赖语句文本，也不依赖方言渲染。

## 为什么用**文件库**

主题就是「未提交的写入有没有被回滚掉」，而 `:memory:` 的 `StaticPool`
让所有 session 共享一条连接 —— 观测不到跨连接的事务可见性
（`docs/solutions/testing-issues/sqlite-staticpool-hides-uncommitted.md`）。
文件库才有真正的每连接事务。
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base as _SA_Base
from app.models.report import ReportFile
from app.models.system import AuditLog
from app.services.report import report_service

pytestmark = pytest.mark.asyncio


def _content_hash() -> str:
    return uuid.uuid4().hex


async def _engine(tmp_path, name="concurrent"):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/{name}.db")
    async with engine.begin() as conn:
        await conn.run_sync(_SA_Base.metadata.create_all)
    return engine


class _EmptyScalar:
    """`.scalar_one_or_none()` 返回 None 的替身。"""

    def scalar_one_or_none(self):
        return None


def _first_call_short_circuited(db):
    """把**第一次** `db.execute` 短路成「查不到」，其后放行。

    `_upsert_report_file` 的第一次 execute 就是「按 content_hash 查已有行」，
    短路它 ⇒ `existing is None` ⇒ 走 INSERT ⇒ 撞上别人已提交的那行 ⇒
    进入 `except IntegrityError`。第二次 execute（except 里的恢复查询）
    必须放行，否则拿回来的 `row` 是 None 而不是别人的行。

    按**调用序数**而非语句文本 —— 第一版按文本判（`str(stmt.whereclause)`
    含 'content_hash'）实测恒不命中，短路从未发生，两条测试空洞地绿。
    """
    real = db.execute
    state = {"n": 0}

    async def fake(stmt, *a, **kw):
        state["n"] += 1
        if state["n"] == 1:
            return _EmptyScalar()
        return await real(stmt, *a, **kw)

    return fake


async def test_concurrent_collision_does_not_discard_the_callers_pending_writes(tmp_path):
    """**核心断言**：别人的并发插入不该让**我**这一笔事务里的别的写入蒸发。

    观测点在 `db.commit()` 之后从**另一个 session** 读 —— 因为要证明的是
    「它真的进了库」，而不是「它还在 session 的 pending 列表里」。
    """
    engine = await _engine(tmp_path)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    digest = _content_hash()
    audit_id = uuid.uuid4()

    # 别人先提交了同一 content_hash 的行
    async with maker() as seed:
        seed.add(ReportFile(
            report_file_id=uuid.uuid4(), project_id=None, content_hash=digest,
            file_path="r.pdf", file_format="pdf", size_bytes=3, status="SUCCEEDED",
            has_assumption_page=False,
        ))
        await seed.commit()
    winner_id = None
    async with maker() as peek:
        from sqlalchemy import select
        winner_id = (await peek.execute(
            select(ReportFile).where(ReportFile.content_hash == digest)
        )).scalar_one().report_file_id

    # 我的这一笔事务：先写一条**无关的**审计行（flush，不提交）
    async with maker() as db:
        db.add(AuditLog(user_id=None, action="TEST", resource_type="report",
                        resource_id=None, detail_json={"marker": "caller"},
                        ip=None))
        await db.flush()

        # 制造竞态窗口：让「查已有行」查不到 ⇒ INSERT 必然撞约束
        db.execute = _first_call_short_circuited(db)  # type: ignore[method-assign]
        try:
            row = await report_service._upsert_report_file(
                db, project_id=None, content_hash=digest, relpath="r.pdf",
                size=3, fmt="pdf", has_assumption=False,
                report_file_id=uuid.uuid4())
        finally:
            del db.execute
        # 复用别人那一行（去重语义）
        assert row.report_file_id == winner_id
        await db.commit()

    # 从另一个 session 读：调用方那条审计行还在吗？
    async with maker() as verify:
        from sqlalchemy import select
        marks = (await verify.execute(
            select(AuditLog).where(AuditLog.detail_json.like('%caller%'))
        )).scalars().all()

    await engine.dispose()
    assert len(marks) == 1, (
        f"调用方同事务里的 AuditLog 被并发冲突的 rollback 连带丢了"
        f"（现在剩 {len(marks)} 条）—— `db.rollback()` 回滚的不只是自己那次"
        f"失败的 INSERT，而是共享 session 的整笔事务。应改用 SAVEPOINT"
    )


async def test_collision_still_returns_the_winners_row(tmp_path):
    """去重语义不能因为改了事务处理而丢：撞约束后仍要拿到别人那行。"""
    engine = await _engine(tmp_path, "winner")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    digest = _content_hash()

    async with maker() as seed:
        seed.add(ReportFile(
            report_file_id=uuid.uuid4(), project_id=None, content_hash=digest,
            file_path="r.pdf", file_format="pdf", size_bytes=3, status="SUCCEEDED",
            has_assumption_page=False,
        ))
        await seed.commit()

    async with maker() as db:
        db.execute = _first_call_short_circuited(db)  # type: ignore[method-assign]
        try:
            row = await report_service._upsert_report_file(
                db, project_id=None, content_hash=digest, relpath="r.pdf",
                size=3, fmt="pdf", has_assumption=False,
                report_file_id=uuid.uuid4())
        finally:
            del db.execute
        await db.commit()

    async with maker() as check:
        from sqlalchemy import select
        n = (await check.execute(
            select(ReportFile).where(ReportFile.content_hash == digest)
        )).scalars().all()
        assert len(n) == 1, f"content_hash={digest} 应仍只有一行，实际 {len(n)}"

    await engine.dispose()
    assert row is not None
