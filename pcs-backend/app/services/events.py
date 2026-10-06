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

    from app.services.events import emit_event, register_listener

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

# event_id 派生的命名空间 — 固定不变, 是确定性 id 跨进程/跨重启稳定的前提。
# 用 uuid5 从 URL 命名空间派生而非随手写死, 便于日后追溯其来源。
NS_EVENT = uuid.uuid5(uuid.NAMESPACE_URL, "pcs.p7.events")


# 事件类型 → 「本就没有 listener 也属正常」的清单（审查 #28）。
#
# `actual_data_replaces_design` / `actual_data_check_submitted` 的消费者是 P8 的
# 反向恢复，那之前它们就是 **claim-only**：claim 成功即完成，监听与否无关。
# 相反 `cia_mark_stale` 无 listener **一定是 bug** —— 它的处理者就是 FSM 转移本身，
# 没人听就等于转移没发生，而调用方却会以为标记成功了。
#
# ⚠️ 勿把「无 listener = 错误」一刀切套到所有事件上。
CLAIM_ONLY_EVENTS = frozenset(
    {"actual_data_replaces_design", "actual_data_check_submitted"}
)


def has_listener(event_type: str) -> bool:
    """该事件类型当前是否有人监听.

    调用方用它区分「无 listener 属正常（claim-only）」与「无 listener 是配置错误」。
    `CIAEngine.scan_stale` 据此决定要不要把一次 STALE 标记计入返回值 —— 修复前
    它无条件 `marked += 1`，于是 listener 缺失时操作者拿到一个虚假的「已标记 N 台」。
    """
    return bool(_LISTENERS.get(event_type))


def derive_event_id(
    event_type: str,
    before: dict | None,
    after: dict | None,
    *,
    scope: str,
) -> uuid.UUID:
    """从业务操作确定性派生 event_id（审查 #3）.

    语义：**一次业务事实 = 一个 id**。同一 `scope`（通常是设备 id）下重复发出
    「before → after 这一次替换」是幂等的，不会二次派发；发出不同的 before/after
    则是另一条事实，拿到新 id 正常入库。

    这修掉的是 `uuid4()` 造成的去重结构性不可达：此前没有任何 producer 能产出
    碰撞的 event_id，`_claim` 的幂等表、`payload_hash` 冲突检测、竞态处理全都
    无法生效。副作用是重复校核不再发出「before 等于上一个 after」的第二条事件
    —— 那会让 P8 的按序反向恢复把实际数据写回设计位。

    ⚠️ 哈希输入**只含** event_type + before + after（即 `_HASHED_KEYS`），不含
    timestamp / request_id / iat / actor。掺入这些字段会让每次重投都得到不同 id，
    幂等彻底失效。改动 `_HASHED_KEYS` 前先想清楚这一点。
    """
    return uuid.uuid5(
        NS_EVENT,
        f"{event_type}:{scope}:{_payload_hash(event_type, before, after)}",
    )


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
    # ⚠️ 原子性约束（P7-S4 审查 #2+#3）：本函数的 IntegrityError 分支若用
    # `session.rollback()`，回滚的是**调用方整个待写状态**而不只是 claim 行 ——
    # `pass_check` 在 emit_event 前已 flush `actual_data_status=CONFIRMED`，一并丢弃，
    # 且对外谎报「并发 claim 冲突」。因此 rollback 必须换成 savepoint
    # （`session.begin_nested()`），且**必须与 `event_id` 改为确定性派生（uuid5）
    # 同提交**。理由：今天该路径不可达，仅因无任何 producer 能产出碰撞的 event_id；
    # 一旦改 uuid5，并发双击在 READ COMMITTED 下双方 INSERT、后到者撞主键，路径立刻可达。
    # #3 是 #2 的**解除掩盖条件**，顺序不能颠倒，严禁拆分 cherry-pick。
    existing = (
        await session.execute(
            EventIdempotency.__table__.select().where(
                EventIdempotency.__table__.c.event_id == event_id
            )
        )
    ).first()
    if existing is not None:
        if existing.payload_hash != payload_hash:
            # 与 except 分支的 hash 不同出口同一语义，detail 形状保持一致，
            # 客户端只需按 detail.retryable 分流，不必按出错位置区分。
            raise PcsError(
                code="EVENT_ID_CONFLICT",
                message=(
                    f"event_id {event_id} 已以不同 payload 处理过 "
                    f"(已存 hash={existing.payload_hash[:12]}…, "
                    f"本次={payload_hash[:12]}…)。"
                    "同一 event_id 携带不同 payload 是上游 bug，重试无用。"
                ),
                status=409,
                detail={"retryable": False, "event_id": str(event_id)},
            )
        return False

    try:
        # savepoint 而非 rollback —— 审查 #2 的数据丢失根因。
        # `session.rollback()` 回滚的是**调用方整个事务**：`session.flush()` 冲刷的是
        # 调用方全部待写状态，`pass_check` 恰好在 emit_event 前 flush 了
        # `actual_data_status=CONFIRMED`，会被这一句连同 claim 行一起丢掉，
        # 而调用方收到的是「并发 claim 冲突」这个误导性错误。
        async with session.begin_nested():
            session.add(
                EventIdempotency(
                    event_id=event_id,
                    event_type=event_type,
                    payload_hash=payload_hash,
                    before_json=before,
                )
            )
            await session.flush()
    except IntegrityError as exc:
        # 并发下两个投递同时 claim → 后到者撞主键, 视为幂等重投。
        # 上面只回滚了 savepoint，调用方的事务与其已写入的数据完好无损。
        #
        # ⚠️ 三个出口语义不同，不可一概报「并发冲突」（审查 #2 后半段）——
        # 统一说成冲突 + 标 retryable，会把真正的上游 bug 伪装成瞬时并发，
        # 运维无限重试、日志刷爆、该查的根因被埋掉。
        row = (
            await session.execute(
                EventIdempotency.__table__.select().where(
                    EventIdempotency.__table__.c.event_id == event_id
                )
            )
        ).first()
        if row is not None:
            if row.payload_hash == payload_hash:
                # 同 payload 的真并发 —— 第二个事务本就该被幂等吞掉，不派发。
                return False
            # hash 不同 = 同一 event_id 携带不同 payload，与顶部早返回分支同一条件。
            # 这是上游 bug，**重试无用**：重试多少次都会撞同一行。
            raise PcsError(
                code="EVENT_ID_CONFLICT",
                message=(
                    f"event_id {event_id} 已以不同 payload 处理过 "
                    f"(已存 hash={row.payload_hash[:12]}…, 本次={payload_hash[:12]}…)。"
                    "同一 event_id 携带不同 payload 是上游 bug，重试无用。"
                ),
                status=409,
                detail={"retryable": False, "event_id": str(event_id)},
            )
        # 撞了主键却查不到行：对方事务此刻尚未对本读可见。这是**唯一**值得
        # 上游重试的情形 —— 如实标出，否则可恢复的并发被直接判成失败。
        raise PcsError(
            code="EVENT_ID_CONFLICT",
            message=(
                f"event_id {event_id} 已被并发事务 claim 但尚未可见，请重试 "
                f"(底层错误: {exc})。"
            ),
            status=409,
            detail={"retryable": True, "event_id": str(event_id)},
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

    # ⚠️ claim 与派发必须在**同一个** savepoint 里（审查 #10）——
    # claim 行一旦先于派发 flush 落库，而 listener 随后抛错且无补偿，数据库里就会
    # 留下一行断言「转移发生过」的幂等凭据，而转移根本没发生。可达路径:
    # `CIAEngine._scan_one_class` → `_mark_stale_via_fsm` 对已过 CHECKED/CHANGED 的记录
    # 抛 InvalidTransition，被外层 `except Exception: continue` 吞掉后事务照常提交。
    # P8 反向恢复或后续审计一旦信任该表，就会跳过这些记录。
    #
    # 修法: 任一 listener 抛错 → 本 savepoint 回滚（含 `_claim` 内部嵌套 savepoint
    # 插入的 claim 行）→ 异常继续上抛。调用方接住后 claim 不复存在，重投会重新派发，
    # 不会被静默当成「已处理」。调用方的其余写入与事务完好无损。
    async with session.begin_nested():
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
        # 事件类型区分（P7-S4 审查 #28）：空 listener 列表**不是**一律的 bug。
        # - `cia_mark_stale` 类：无 listener = 配置错误，调用方（如 CIAEngine.scan_stale）
        #   不应据此递增「已标记 N 台」计数，否则报给操作者的数字是错的。
        # - `actual_data_replaces_design`：P8 挂上反向恢复 listener 之前本就是
        #   claim-only，claim 成功即完成，监听与否无关。
        # 用 `CLAIM_ONLY_EVENTS` 白名单表达此区分，勿一刀切地「无 listener 即失败」。
        for listener in _LISTENERS.get(event_type, []):
            await listener(event)

    return True


__all__ = [
    "CLAIM_ONLY_EVENTS",
    "NS_EVENT",
    "clear_listeners",
    "derive_event_id",
    "emit_event",
    "has_listener",
    "register_listener",
    "restore_listeners",
    "snapshot_listeners",
]
