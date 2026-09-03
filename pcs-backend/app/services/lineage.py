"""血缘追踪（Sprint 3）。

三件套：
- LineageTracker：低层写入 data_lineage 表
- @lineage 装饰器：自动捕获 record 写入并落血缘
- lineage_ctx 上下文管理器：业务显式声明 source 列表

设计要点：
- data_lineage.parent_lineage_id 自指 FK，构建版本链
- 记录 hash 通过 record_hash 字段或 _compute_hash() 计算
- 装饰器零侵入：未装饰的 record 不影响功能
"""

from __future__ import annotations

import hashlib
import json as _json
import uuid
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from functools import wraps
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import DataLineage

if TYPE_CHECKING:
    from app.models.mixins import RecordMixin


# 当前请求的 lineage 上下文（线程/协程隔离）
_active_ctx: ContextVar[dict | None] = ContextVar("lineage_ctx", default=None)


def _compute_hash(record: Any) -> str:
    """SHA-256 of record 列属性；用作 data_lineage 引用 + CIA 比对基准。

    读取顺序：state.dict → committed_state。**禁止** getattr fallback：
    expire 后 getattr 会触发 sync lazy-load，在 async 上下文失败（MissingGreenlet）。
    """
    from sqlalchemy import inspect as _inspect

    mapper_cols = [
        c.key for c in record.__table__.columns if not c.primary_key
    ]
    state = _inspect(record)
    committed = state.committed_state or {}
    payload: dict = {}
    for k in mapper_cols:
        v = state.dict.get(k)
        if v is None:
            v = committed.get(k)
        payload[k] = v
    raw = _json.dumps(payload, default=str, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _record_pk(record: RecordMixin) -> uuid.UUID:
    """提取 PK UUID；expire 后走 committed_state 取上次写入值。"""
    from sqlalchemy import inspect as _inspect

    mapper = _inspect(record.__class__)
    if mapper is None:
        raise TypeError(f"cannot inspect mapper for {record.__class__.__name__}")
    pk_name = mapper.primary_key[0].name
    state = _inspect(record)
    if state is None:
        raise TypeError(f"cannot inspect state for {record.__class__.__name__}")
    # 1. in-memory dict
    val = state.dict.get(pk_name)
    # 2. 已经 expire：fallback 到 committed_state（保留上次 flush 写入值）
    if val is None and state.expired:
        committed = state.committed_state or {}
        val = committed.get(pk_name)
    # 3. 最后兜底：直接 getattr
    if val is None:
        val = getattr(record, pk_name, None)
    if not isinstance(val, uuid.UUID):
        raise TypeError(
            f"record PK must be UUID, got {type(val).__name__} "
            f"(record may not be flushed yet)"
        )
    return val


class LineageTracker:
    """data_lineage 写入门面。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def track(
        self,
        *,
        record: RecordMixin,
        source: str,
        change_summary: str | None = None,
        change_diff: dict | None = None,
        actor_user_id: uuid.UUID | None = None,
        source_ref_type: str | None = None,
        source_ref_id: uuid.UUID | None = None,
    ) -> DataLineage:
        """写入一条 data_lineage 记录。先 flush 让 record PK 落库。"""
        await self.session.flush()
        entry = DataLineage(
            record_type=record.__class__.__name__,
            record_id=_record_pk(record),
            source=source,
            source_ref_type=source_ref_type,
            source_ref_id=source_ref_id,
            actor_user_id=actor_user_id,
            change_summary=change_summary,
            change_diff_json=change_diff,
            occurred_at=datetime.now(UTC),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def latest(
        self,
        *,
        record_type: str,
        record_id: uuid.UUID,
    ) -> DataLineage | None:
        """查某 record 最新一条血缘记录。"""
        from sqlalchemy import select

        return (
            await self.session.execute(
                select(DataLineage)
                .where(
                    DataLineage.record_type == record_type,
                    DataLineage.record_id == record_id,
                )
                .order_by(DataLineage.occurred_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def upstream(
        self,
        *,
        record_type: str,
        record_id: uuid.UUID,
        max_depth: int = 10,
    ) -> list[DataLineage]:
        """沿 parent_lineage_id 链向上回溯祖先节点（不包含起点）。"""
        from sqlalchemy import select

        chain: list[DataLineage] = []
        cur = await self.latest(record_type=record_type, record_id=record_id)
        for _ in range(max_depth):
            if cur is None or cur.parent_lineage_id is None:
                break
            parent = (
                await self.session.execute(
                    select(DataLineage).where(
                        DataLineage.lineage_id == cur.parent_lineage_id
                    )
                )
            ).scalar_one_or_none()
            if parent is None:
                break
            chain.append(parent)
            cur = parent
        return chain

    async def downstream(
        self,
        *,
        lineage_id: uuid.UUID,
        max_depth: int = 10,
    ) -> list[DataLineage]:
        """递归查以 lineage_id 为 parent_lineage_id 的下游记录。"""
        from sqlalchemy import select

        result: list[DataLineage] = []
        frontier = [lineage_id]
        seen: set[uuid.UUID] = {lineage_id}
        for _ in range(max_depth):
            if not frontier:
                break
            children = (
                (
                    await self.session.execute(
                        select(DataLineage).where(
                            DataLineage.parent_lineage_id.in_(frontier)
                        )
                    )
                )
                .scalars()
                .all()
            )
            new_frontier: list[uuid.UUID] = []
            for c in children:
                if c.lineage_id in seen:
                    continue
                seen.add(c.lineage_id)
                result.append(c)
                new_frontier.append(c.lineage_id)
            frontier = new_frontier
        return result


def lineage(*, sources: tuple[str, ...] = (), summary: str | None = None):
    """装饰器：包裹的函数返回 record，自动落 data_lineage。

    sources 必填元组；如需动态 source，使用 lineage_ctx。
    函数签名：async def f(session, record, actor_user_id) -> RecordMixin
    """

    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            result = await fn(*args, **kwargs)
            session = _resolve_session(args, kwargs)
            actor = _resolve_actor(args, kwargs)
            tracker = LineageTracker(session)
            ctx = _active_ctx.get()
            for rec in _iter_records(result):
                src_list = list(sources)
                if ctx and ctx.get("sources"):
                    src_list.extend(ctx["sources"])
                parent_id = ctx.get("parent_lineage_id") if ctx else None
                for src in src_list or ["USER"]:
                    entry = await tracker.track(
                        record=rec,
                        source=src,
                        change_summary=summary,
                        change_diff={"hash": _compute_hash(rec)},
                        actor_user_id=actor,
                        source_ref_type=ctx.get("source_ref_type") if ctx else None,
                        source_ref_id=ctx.get("source_ref_id") if ctx else None,
                    )
                    if parent_id is not None:
                        entry.parent_lineage_id = parent_id
            return result

        return wrapper

    return decorator


class lineage_ctx:
    """上下文管理器：在 with 块内为装饰器补充 source / parent_lineage_id。

    用法：
        with lineage_ctx(sources=("AI",), parent_lineage_id=parent.id):
            await some_service.do_change(record)
    """

    def __init__(
        self,
        *,
        sources: tuple[str, ...] | None = None,
        parent_lineage_id: uuid.UUID | None = None,
        source_ref_type: str | None = None,
        source_ref_id: uuid.UUID | None = None,
    ):
        self._data = {
            "sources": sources or (),
            "parent_lineage_id": parent_lineage_id,
            "source_ref_type": source_ref_type,
            "source_ref_id": source_ref_id,
        }
        self._token: Token[dict | None] | None = None

    def __enter__(self):
        self._token = _active_ctx.set(self._data)
        return self

    def __exit__(self, *exc):
        if self._token is not None:
            _active_ctx.reset(self._token)

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, *exc):
        self.__exit__(*exc)


def _resolve_session(args: tuple, kwargs: dict) -> AsyncSession:
    """从函数参数推断 AsyncSession。"""
    for v in list(args) + list(kwargs.values()):
        if isinstance(v, AsyncSession):
            return v
    raise TypeError("no AsyncSession in args/kwargs")


def _resolve_actor(args: tuple, kwargs: dict) -> uuid.UUID | None:
    """从函数参数推断 actor_user_id。"""
    for v in list(args) + list(kwargs.values()):
        if isinstance(v, uuid.UUID):
            return v
    return None


def _iter_records(result: Any):
    """装饰器结果可能是单 record 或 list of records。"""
    if result is None:
        return []
    if isinstance(result, list):
        return result
    return [result]


# 公开 API
__all__ = [
    "LineageTracker",
    "lineage",
    "lineage_ctx",
    "_compute_hash",
]