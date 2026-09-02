"""commit_or_rollback — 事务边界包装（Task 2.8 / P2 Sprint 1）。

使用方式：
    async with commit_or_rollback(db):
        ...

设计要点：
- asynccontextmanager：caller 用 async with 包裹业务逻辑。
- yield 出的就是 session（保持原有 cursor/会话引用不变）。
- yield 内任意异常都会触发 rollback，再 re-raise — 让 FastAPI
  exception_handlers 接管错误响应。
- 成功路径（无异常）执行 commit。
- 业务代码不需要再手动调用 session.commit() / session.rollback()。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def commit_or_rollback(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """事务边界：yield 出 session，退出时按结果 commit 或 rollback。

    用法：
        async with commit_or_rollback(db):
            asset = await svc.create_asset(...)
            # yield 块内若有异常 → rollback；正常退出 → commit
    """
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise