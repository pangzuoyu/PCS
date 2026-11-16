"""E2E-017：AI 端点 501 + 审计行落库（P10-B · T6）。

## ⚠️ 两段式（不引 Redis / worker）

1. **入队** —— spy `app.core.ai_audit_middleware.enqueue_ai_audit_log`
   ⇒ 断言「**被调了**」且**参数对**（request_id / status_code / endpoint）
   ⇒ ⚠️ **只断落库会漏掉中间件那段**（压根没入队时照样绿）
2. **落库** —— 直调 `app.workers.ai_audit_tasks.write_ai_audit_log`
   ⇒ **真 PG** 里 `ai_audit_log` 有一行

⇒ **不起 ARQ worker**（车道不引 Redis / worker 进程）
⇒ ⚠️ 「真过 Redis + worker」那一段仍未覆盖 ⇒ **TODO-155**。

## ⚠️ 桩的是「消费者侧的绑定」

`app/core/ai_audit_middleware.py` 是 `from app.services.ai.arq_queue import
enqueue_ai_audit_log` ⇒ ⇒ 要桩**消费者侧**那个名字
（**定义处**那个名字桩不到 ⇒ 桩了等于没桩 —— bug-2162 的教训）。
"""
from __future__ import annotations

import pytest


@pytest.mark.e2e
async def test_e2e_017_ai_endpoint_returns_501_and_the_audit_row_is_persisted(
    e2e_client, role_headers, monkeypatch
):
    """① 端点 501 ② 入队被调且参数对 ③ 直调写库任务 ⇒ 真 PG 里有一行。"""
    from app.core import ai_audit_middleware

    calls: list[dict] = []

    async def _fake_enqueue(**kwargs) -> None:
        calls.append(kwargs)

    # ⚠️ 桩**消费者侧**的绑定（中间件模块里的那个名字）
    monkeypatch.setattr(
        ai_audit_middleware, "enqueue_ai_audit_log", _fake_enqueue, raising=True
    )

    # ① 端点：501 + AI_NOT_IMPLEMENTED
    resp = await e2e_client.post(
        "/api/v1/ai/intent",
        json={"text": "E2E 场景的意图", "context": None},
        headers=role_headers("DESIGNER"),
    )
    assert resp.status_code == 501, (
        f"AI 端点应返回 501 ⇒ {resp.status_code} {resp.text[:200]}"
    )
    assert resp.json().get("code") == "AI_NOT_IMPLEMENTED", (
        f"错误码不对：{resp.text[:200]}"
    )

    # ② 入队被调了 + 参数对
    assert calls, "中间件**没入队** ⇒ 审计链断了（只断落库会漏掉这一段）"
    fields = calls[0]
    assert fields.get("request_id"), f"入队参数缺 request_id：{sorted(fields)}"
    assert fields.get("status_code") == 501, (
        f"入队的 status_code 不对：{fields.get('status_code')}"
    )
    assert "/ai/" in str(fields.get("endpoint", "")), (
        f"入队的 endpoint 不对：{fields.get('endpoint')}"
    )

    # ③ 直调写库任务 ⇒ 真 PG 里真有一行
    from app.workers.ai_audit_tasks import write_ai_audit_log

    factory = e2e_client._e2e_session_factory  # type: ignore[attr-defined]
    await write_ai_audit_log(
        {"session_factory": factory, "job_id": "e2e-017", "job_try": 1}, **fields
    )

    from sqlalchemy import text as _text

    async with factory() as session:
        rows = (
            await session.execute(
                _text(
                    "SELECT request_id, endpoint, status_code FROM ai_audit_log "
                    "WHERE request_id = :rid"
                ),
                {"rid": fields["request_id"]},
            )
        ).mappings().all()
    assert len(rows) == 1, f"审计行数不对：{len(rows)}（要 1 行）"
    assert rows[0]["status_code"] == 501, f"落库的 status_code 不对：{rows[0]}"
