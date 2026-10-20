"""P9A 收口：通知列表的 500ms 预算（ADR-0049 §③ / SPEC §7.2「待办/通知 ≤500ms」）。

## 为什么补这条

SPEC §7.2 的 P9A 验收写「待办/通知 ≤500ms」。**待办**那一半有自动化验收
（`tests/api/v1/test_todos.py::test_todo_sql_and_parse_both_within_budget`，
造 300 个待签交付物后分段计时）；**通知**这一半**没有任何性能断言** ——
全仓 `tests/` 里只有 `test_todos.py` 断言 500ms，通知查询（列表 + 未读计数）
只验正确性、不验耗时。

⇒ 「验收标准里有一条，代码也实现了，但没人证明它达标」——
这正是「已实现 ≠ 被验收」的形状。

## 这条测试**测的是什么、不测什么**

测的是**端到端延迟**（HTTP → service → SQL → 序列化 → JSON），
在**造到预期数据量**之后。

⚠️ **不测生产 p99**：这里是内存 SQLite，往返是微秒级；生产的真实数字取决于
网络与 DB。本测试的价值与 `test_todos.py` 同款：① 打印实测值而不只断言通过；
② 钉住「未读计数在大量行下不退化」这个**性质**（`unread_count` 走
partial index `ix_notifications_recipient_unread`；列表走
`ix_notifications_recipient_created` 排 `created_at DESC`）；
③ 一旦有人把列表查询改成全表扫 + Python 过滤，这两条会先红。

⚠️ **小表下测不出真实性能** —— 500ms 是假达标（`test_todos.py` 头注同款）。
⇒ 这里造 **2800 行**（目标收件人 800 + 20 个他人各 100），
量级接近「一个 30 天保留期里活跃用户的收件箱」。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from time import perf_counter
from urllib.parse import quote

import pytest
from sqlalchemy import insert

from app.core.security import create_access_token
from app.models.notification import Notification, NotificationKind

pytestmark = [pytest.mark.asyncio, pytest.mark.slow]

#: SPEC §7.2 的上界（与 `test_todos.py` 同值）。
BUDGET_MS = 500.0

#: 目标收件人的通知条数（30 天保留期内的高活跃用户量级）。
TARGET_ROWS = 800

#: 目标收件人里未读的条数（铃铛红点要数的那部分）。
TARGET_UNREAD = 300

#: 其他收件人的人数与人均条数 —— 撑大表，让目标收件人的查询**真的**要过滤。
OTHER_RECIPIENTS = 20
OTHER_ROWS_EACH = 100

#: 列表默认条数（与 `app/api/v1/notifications.py` 的 `limit` 默认值一致）。
DEFAULT_LIMIT = 50


def _token(user_id: uuid.UUID) -> str:
    return create_access_token(
        subject=f"u-{user_id}", role="DESIGNER", extra={"user_id": str(user_id)}
    )


async def _seed(db, recipient: uuid.UUID, *, now: datetime) -> int:
    """造数据。返回目标收件人的总条数。

    ⚠️ `created_at` **显式**给：SQLite 的 `server_default=func.now()` 只到**秒**，
    而列表按 `created_at DESC, notification_id DESC` 排序 ⇒ 全部同秒时
    排序靠 tiebreaker，测不出「按时间翻页」这个性质。
    """
    base = now - timedelta(days=30)
    # 均匀铺满 30 天（800 条 ≈ 每 54 分钟一条）⇒ `after=now-15d` 能切出约一半。
    step = timedelta(days=30) / TARGET_ROWS
    rows = []
    for i in range(TARGET_ROWS):
        rows.append(
            {
                "notification_id": uuid.uuid4(),
                "recipient_id": recipient,
                "kind": NotificationKind.SIGN_COMPLETED.value,
                "title": f"通知 {i}",
                "body": "正文",
                "detail_json": None,
                # 前 TARGET_UNREAD 条未读（read_at=None），其余已读
                "read_at": None if i < TARGET_UNREAD else now - timedelta(hours=1),
                "created_at": base + step * i,
            }
        )
    other_rows = []
    for _r in range(OTHER_RECIPIENTS):
        other = uuid.uuid4()
        for i in range(OTHER_ROWS_EACH):
            other_rows.append(
                {
                    "notification_id": uuid.uuid4(),
                    "recipient_id": other,
                    "kind": NotificationKind.SIGN_COMPLETED.value,
                    "title": f"他人通知 {i}",
                    "body": "正文",
                    "detail_json": None,
                    "read_at": None,
                    "created_at": base + step * i,
                }
            )
    await db.execute(insert(Notification), rows + other_rows)
    await db.commit()
    return TARGET_ROWS


async def test_notification_list_and_unread_count_within_budget(
    client, db, user_id, capsys
):
    """列表 + 未读计数在**预期数据量**下 ≤ 500ms，且计数正确。

    ⚠️ 断言**两件事**：耗时（指标）+ `unread_count`（正确性）。
    只断言耗时会漏掉「快了但数错了」—— 未读计数错 = 铃铛红点错 = 用户
    不知道自己漏了什么，而那**正是**通知要解决的事。
    """
    now = datetime.now(UTC)
    await _seed(db, user_id, now=now)

    t0 = perf_counter()
    resp = await client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {_token(user_id)}"},
    )
    elapsed_ms = (perf_counter() - t0) * 1000

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == DEFAULT_LIMIT, "默认 limit 应为 50"
    assert body["unread_count"] == TARGET_UNREAD, (
        f"未读计数 {body['unread_count']} != {TARGET_UNREAD}"
    )
    with capsys.disabled():
        print(
            f"\n[通知 500ms] 端到端 {elapsed_ms:.1f}ms"
            f"（表内 {TARGET_ROWS + OTHER_RECIPIENTS * OTHER_ROWS_EACH} 行 / "
            f"目标收件人 {TARGET_ROWS} 条 / 未读 {TARGET_UNREAD}）"
        )
    assert elapsed_ms <= BUDGET_MS, f"通知列表耗时 {elapsed_ms:.1f}ms，超过 500ms 预算"


async def test_notification_list_after_pagination_within_budget(
    client, db, user_id, capsys
):
    """断线重连的补齐路径（`?after=<last_seen>`）同样要在预算内。

    ⚠️ 这条**不是**重复第一条：`after` 走的是**另一个索引**
    （`ix_notifications_recipient_created` 的范围扫描），而列表默认路径
    还带 `ORDER BY created_at DESC` 的排序列。
    ⇒ 只测默认路径 ⇒ 「重连补齐慢」这类退化**测不出来**。
    """
    now = datetime.now(UTC)
    await _seed(db, user_id, now=now)
    # ⚠️ 必须 URL 编码：ISO 带时区偏移（`+00:00`）里的 `+` 在查询串里是**空格**
    # ⇒ 不编码就是 422（`unexpected extra characters at the end of the input`）。
    # ⚠️ 切点取 **1 天前**：800 条铺满 30 天 ⇒ 1 天内约 26 条（< limit 50）。
    # 切点若取 15 天前，切出约 400 条 ⇒ 仍被 limit 截成 50 ⇒
    # **`after` 被静默忽略时这条也绿**（返回的还是最新 50 条）⇒ 断言失效。
    cutoff = now - timedelta(days=1)
    after = quote(cutoff.isoformat(), safe="")

    t0 = perf_counter()
    resp = await client.get(
        f"/api/v1/notifications?after={after}",
        headers={"Authorization": f"Bearer {_token(user_id)}"},
    )
    elapsed_ms = (perf_counter() - t0) * 1000

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # ⚠️ **条数必须少于 limit** —— 这是「`after` 真的过滤了」的判据。
    # 只断言「有 50 条」的话，`after` 参数被静默忽略时也会绿。
    assert 0 < len(body["items"]) < DEFAULT_LIMIT, (
        f"返回 {len(body['items'])} 条 —— after 过滤多半没生效"
    )
    # ⚠️ SQLite 不存时区 ⇒ 取回的 `created_at` 是 **naive** ⇒ 两侧都去时区再比。
    def _naive(dt: datetime) -> datetime:
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    assert all(
        _naive(datetime.fromisoformat(item["created_at"])) > _naive(cutoff)
        for item in body["items"]
    ), "返回了不晚于 after 的行 —— after 过滤没生效"
    with capsys.disabled():
        print(
            f"\n[通知 500ms · after 补齐] 端到端 {elapsed_ms:.1f}ms"
            f"（命中 {len(body['items'])} 条）"
        )
    assert elapsed_ms <= BUDGET_MS, (
        f"通知补齐耗时 {elapsed_ms:.1f}ms，超过 500ms 预算"
    )
