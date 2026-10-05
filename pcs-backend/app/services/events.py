"""事件骨架 — emit_event / register_listener / 幂等去重。

P7 Sprint 4 Task S4-0。落地 **D4 裁决 4A**：
    状态机保持所有门禁迁移的**单一权威**；业务模块（Supplier / UtilResults /
    EquipmentList）通过 `emit_event()` 发事件，**不直接调 state_machine**。
    事件需幂等（`event_id` 去重）；rollback 分阶段
    （事件撤回 / 门禁回滚 / CIA 反向恢复 — 第三阶段推迟 P8）。

设计要点（依据 `docs/PCS-NOTE-CIA-反向恢复-推到P8-2026-10-05.md`）：

1. **幂等凭据落 DB**（`EventIdempotency` 表），不落内存。去重是**业务正确性**
   要求，不能因进程重启失效。
2. **`payload_hash` 必带** —— 同一 `event_id` 携带不同 payload 是上游 bug，
   静默按先到者处理会掩盖问题，故显式抛 `EVENT_ID_CONFLICT`。
3. **`before` 快照走 `copy.deepcopy`** —— 浅拷贝在嵌套 dict/list 下会串：
   存的是引用，调用方事后改内层对象会污染已落库的快照。
4. **`before` 不只存 audit_logs** —— 后者有保留期清理策略，清理后无法再做
   反向恢复。`audit_logs.detail_json` 只记 `event_id` 引用与摘要。

用法::

    from app.core.events import emit_event, register_listener

    register_listener("actual_data_replaces_design", my_handler)

    await emit_event(
        session,
        "actual_data_replaces_design",
        event_id=uuid4(),
        before=existing.design_parameters_json,   # deepcopy 后存储
        after=new_design_parameters,
        equipment_id=equipment_id,
    )
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.system import EventIdempotency

# 事件类型 → listener 列表。注册表是**进程级**的：重启后 listener 需重新注册，
# 但幂等凭据在 DB 里，所以重启后重投同一 event_id 依然不会重复执行。
_LISTENERS: dict[str, list[Callable[[dict], Awaitable[None]]]] = {}

# 参与 payload_hash 计算的键 — 顺序固定, 确保同 payload 恒同 hash
_HASHED_KEYS = ("event_type", "before", "after")


def register_listener(
    event_type: str, listener: Callable[[dict], Awaitable[None]]
) -> None:
    """注册事件监听器（按注册顺序派发）."""
    _LISTENERS.setdefault(event_type, []).append(listener)


def clear_listeners() -> None:
    """清空全部监听器.

    ⚠️ **会一并清掉生产代码在模块导入时注册的 listener**
    （如 `cia_engine` 的 `cia_mark_stale` 处理者）—— 测试里用它做隔离会
    让事件静默无人处理，表现为「事件发了但状态没变」，极难排查。

    测试隔离请用 `snapshot_listeners()` + `restore_listeners()`。
    本函数仅用于「模拟进程重启」场景。
    """
    _LISTENERS.clear()


def snapshot_listeners() -> dict[str, list]:
    """快照当前注册表（浅拷贝外层 + 拷贝内层 list）.

    给测试做隔离用：每个测试前 snapshot，结束后 restore，
    生产 listener 不受影响。
    """
    return {k: list(v) for k, v in _LISTENERS.items()}


def restore_listeners(snapshot: dict[str, list]) -> None:
    """还原到 snapshot 状态（测试 teardown 用）."""
    _LISTENERS.clear()
    _LISTENERS.update({k: list(v) for k, v in snapshot.items()})


def _payload_hash(
    event_type: str, before: dict | None, after: dict | None
) -> str:
    """payload 指纹 — 同 event_id 不同 hash 即冲突.

    `json.dumps(sort_keys=True)` 保证 key 顺序不影响结果；
    `default=str` 兜底非 JSON 原生类型（如 UUID/Decimal）。
    """
    canonical = json.dumps(
        {
            "event_type": event_type,
            "before": before,
            "after": after,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _claim(
    session: AsyncSession,
    *,
    event_id: uuid.UUID,
    event_type: str,
    payload_hash: str,
    before: dict | None,
) -> bool:
    """尝试占用该 event_id.

    Returns:
        True  = 本次首次处理, 调用方应派发
        False = 幂等重投 (同 hash), 调用方不应派发

    Raises:
        PcsError 409 EVENT_ID_CONFLICT — 同 event_id 不同 payload
    """
    existing = (
        await session.execute(
            EventIdempotency.__table__.select().where(
                EventIdempotency.__table__.c.event_id == event_id
            )
        )
    ).first()
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise PcsError(
                code="EVENT_ID_CONFLICT",
                message=(
                    f"event_id {event_id} 已以不同 payload 处理过 "
                    f"(已存 hash={existing.payload_hash[:12]}…, "
                    f"本次={payload_hash[:12]}…)。"
                    "同一 event_id 携带不同 payload 是上游 bug。"
                ),
                status=409,
            )
        return False

    session.add(
        EventIdempotency(
            event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            before_json=before,
        )
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        # 并发下两个投递同时 claim → 后到者撞主键, 视为幂等重投
        await session.rollback()
        row = (
            await session.execute(
                EventIdempotency.__table__.select().where(
                    EventIdempotency.__table__.c.event_id == event_id
                )
            )
        ).first()
        if row is not None and row.payload_hash == payload_hash:
            return False
        raise PcsError(
            code="EVENT_ID_CONFLICT",
            message=f"event_id {event_id} 并发 claim 冲突: {exc}",
            status=409,
        ) from exc
    return True


async def emit_event(
    session: AsyncSession,
    event_type: str,
    *,
    event_id: uuid.UUID,
    before: dict | None = None,
    after: dict | None = None,
    **payload: Any,
) -> bool:
    """发布事件（D4 4A 的唯一触发入口）.

    Args:
        session: DB session — 幂等凭据落库用.
        event_type: 事件类型, 对应 register_listener 的键.
        event_id: 事件唯一 ID. **反向事件复用原 id** → 天然幂等.
        before: 覆盖前快照（P8 反向恢复来源）; deepcopy 后存储, 只读.
        after: 覆盖后值.
        **payload: 额外业务字段, 原样传给 listener.

    Returns:
        True  = 已派发
        False = 幂等重投, 未派发

    Raises:
        PcsError 409 EVENT_ID_CONFLICT — 同 event_id 不同 payload.
    """
    # deepcopy: 浅拷贝在嵌套结构下会串, 调用方事后改内层会污染已存快照
    before_snapshot = copy.deepcopy(before) if before is not None else None
    after_snapshot = copy.deepcopy(after) if after is not None else None
    payload_hash = _payload_hash(event_type, before_snapshot, after_snapshot)

    claimed = await _claim(
        session,
        event_id=event_id,
        event_type=event_type,
        payload_hash=payload_hash,
        before=before_snapshot,
    )
    if not claimed:
        return False

    event: dict[str, Any] = {
        "event_id": event_id,
        "event_type": event_type,
        "before": before_snapshot,
        "after": after_snapshot,
        **payload,
    }
    for listener in _LISTENERS.get(event_type, []):
        await listener(event)
    return True


__all__ = [
    "clear_listeners",
    "emit_event",
    "register_listener",
    "restore_listeners",
    "snapshot_listeners",
]
