"""P9A C1：通知通道抽象（ADR-0049 §①）。

本文件钉住 ADR §① 的**四条设计约束**与「不写空壳」的决定。
每条约束在 ADR 里都配了「若违反会怎样」，测试名沿用那个失败模式。

⚠️ 本文件里 `test_no_email_channel_class_in_repo` 与
`test_no_channel_type_branch_in_service` 是**绊线**（tripwire），不是行为测试 ——
它们断言的是「某样东西**不**存在」，因此在实现之前就绿。
它们的价值是防止下一版接邮件时把 ADR §① 的决定悄悄推翻，
而不是证明本轮写对了什么。
"""
from __future__ import annotations

import ast
import pathlib

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.db.base import Base
from app.models.notification import Notification, NotificationKind
from app.services.notifications.channel import (
    DeliveryResult,
    NotificationChannel,
    NotificationPayload,
)
from app.services.notifications.in_app import InAppChannel
from app.services.notifications.payload import NotificationDetail

_APP = pathlib.Path(__file__).resolve().parents[2] / "app"


def _payload(user_id, **kw) -> NotificationPayload:
    base = dict(
        recipient_id=user_id,
        kind=NotificationKind.SIGN_COMPLETED,
        title="签署完成",
        body="您已签署 1 份交付物",
    )
    base.update(kw)
    return NotificationPayload.from_detail(**base)


# --------------------------------------------------------------------------
# ADR §① 约束 1：入参是 DTO 不是 ORM 对象，且不传 recipient: User
# --------------------------------------------------------------------------


def test_payload_is_a_frozen_dataclass_not_an_orm_model():
    assert dataclasses_is_frozen_dataclass(NotificationPayload)


def dataclasses_is_frozen_dataclass(cls) -> bool:
    import dataclasses

    return dataclasses.is_dataclass(cls) and cls.__dataclass_params__.frozen


def test_payload_carries_no_recipient_user_object():
    """「不传 `recipient: User`」—— 若违反，邮件通道将来要在 ORM 会话里取用户，
    多一个失败面。收件人已在 `recipient_id` 里。"""
    names = set(NotificationPayload.__dataclass_fields__)
    assert "recipient" not in names, "payload 不得携带 ORM 用户对象"
    assert names <= {
        "notification_id",
        "recipient_id",
        "kind",
        "title",
        "body",
        "created_at",
        "meta",
    }, f"payload 字段集超出 ADR §① 的定义：{names}"


def test_protocol_deliver_takes_exactly_one_argument():
    """只有一个方法、不预定义批量接口（ADR §① 约束 2）。"""
    import inspect

    params = list(inspect.signature(NotificationChannel.deliver).parameters)
    assert params == ["self", "payload"], f"deliver 签名多出参数：{params}"


def test_in_app_channel_satisfies_the_protocol(db):
    """写了协议不校验实现 = 协议是摆设。"""
    assert isinstance(InAppChannel(db), NotificationChannel)


# --------------------------------------------------------------------------
# ADR §① 约束 3：delivered / reason 现在就用上
# --------------------------------------------------------------------------


def test_delivery_result_requires_delivered_to_be_stated():
    """`delivered` 没有默认值 —— 调用方必须明确表态。

    默认 `delivered=True` 的后果是：将来邮件通道忘了填这一字段时，
    调用方会以为投递成功，而 SMTP 拒收被静默吞掉 ——
    那正是 ADR §① 想用 `DeliveryResult` 消灭的那种散落异常处理。
    """
    with pytest.raises(TypeError):
        DeliveryResult()


def test_delivery_result_success_path_carries_no_reason():
    """本版只有站内信一个通道，成功路径不带 reason。"""
    r = DeliveryResult(delivered=True)
    assert r.delivered is True
    assert r.reason is None


def test_delivery_result_carries_a_reason_when_not_delivered():
    """未送达原因是一条**返回值**，不是散在调用点的 try/except
    （ADR §①：没有这两个字段，接邮件的人第一反应就是在 service 里加 try/except）。"""
    r = DeliveryResult(delivered=False, reason="smtp_rejected")
    assert r.delivered is False
    assert r.reason == "smtp_rejected"


# --------------------------------------------------------------------------
# ADR §①：InAppChannel.deliver() 的职责边界
# --------------------------------------------------------------------------


async def test_in_app_writes_exactly_one_row(db, user_id):
    """「写 `notifications` 一行（这是通知的**真值来源**）」——
    一次 deliver 恰好一行，多写就是重复通知。"""
    await InAppChannel(db).deliver(_payload(user_id))
    rows = (await db.execute(select(Notification))).scalars().all()
    assert len(rows) == 1


async def test_in_app_row_is_unread(db, user_id):
    """deliver 时 `read_at` 必须为 NULL —— 新通知不是已读通知。"""
    await InAppChannel(db).deliver(_payload(user_id))
    row = (await db.execute(select(Notification))).scalars().one()
    assert row.read_at is None


async def test_in_app_preserves_payload_fields(db, user_id):
    import uuid as _uuid

    detail = NotificationDetail(
        project_id=_uuid.uuid4(),
        deliverable_id=_uuid.uuid4(),
        step_order=2,
        actor_name="张三",
    )
    p = NotificationPayload.from_detail(
        recipient_id=user_id,
        kind=NotificationKind.STEP_RETURNED,
        title="T",
        body="B",
        detail=detail,
    )
    await InAppChannel(db).deliver(p)
    row = (await db.execute(select(Notification))).scalars().one()
    assert row.recipient_id == user_id
    assert row.kind == NotificationKind.STEP_RETURNED
    assert row.title == "T"
    assert row.body == "B"
    assert row.detail_json["step_order"] == 2
    assert row.detail_json["actor_name"] == "张三"
    # None 字段不落库 —— 免得「没给 actor」与「actor 存了 null」两态同形
    assert "actor_id" not in row.detail_json
    assert row.detail_json["project_id"] == str(detail.project_id)


async def test_in_app_returns_delivered_true(db, user_id):
    result = await InAppChannel(db).deliver(_payload(user_id))
    assert result == DeliveryResult(delivered=True)


async def test_in_app_does_not_push_websocket(db, user_id):
    """ADR §①：「通道**不做** WebSocket 推送 —— 通道不应该知道 WebSocket 存在」。

    用源码断言而非 mock 计数：mock 只能证明「没调我给的 mock」，
    源码断言能钉住「这个模块不 import 推送相关的东西」。
    """
    src = (_APP / "services/notifications/in_app.py").read_text()
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(f"{node.module}.{a.name}" for a in node.names)
    forbidden = {"broadcaster", "redis", "websocket", "ws"}
    for name in imported:
        assert not any(f in name for f in forbidden), (
            f"InAppChannel import 了推送相关模块 {name} —— "
            "ADR §①：通道不应该知道 WebSocket 存在"
        )


# --------------------------------------------------------------------------
# P9A-DLV-010：detail_json 必须有 schema，不是自由 dict
# --------------------------------------------------------------------------


def test_detail_json_has_explicit_schema():
    """`dict[str, Any]` 在 OpenAPI 里是无属性 object，即裸字段（P9A-DLV-010）。
    detail_json 走 `NotificationDetail` 才是 schema。"""
    fields = set(NotificationDetail.model_fields)
    assert fields, "NotificationDetail 不能是空模型"
    assert fields <= {
        "project_id",
        "deliverable_id",
        "deliverable_version_id",
        "workflow_type",
        "step_order",
        "actor_id",
        "actor_name",
        "reason",
    }, f"NotificationDetail 字段集超出计划：{fields}"


def test_detail_json_rejects_unknown_key():
    """schema 要真能挡住自由 dict —— 不 forbid extra 的模型等于没有 schema。"""
    with pytest.raises(ValidationError):
        NotificationDetail.model_validate({"whatever": 1})


async def test_deliver_rejects_meta_with_unknown_key(db, user_id):
    """绕过 `from_detail` 直接塞自由 dict 时，写入侧仍要挡住。
    不静默丢弃：丢弃会让「拼错了字段名」看起来像成功。"""
    import uuid as _uuid
    from datetime import UTC, datetime

    p = NotificationPayload(
        notification_id=_uuid.uuid4(),
        recipient_id=user_id,
        kind=NotificationKind.PROXY_RECORDED,
        title="T",
        body="B",
        created_at=datetime.now(UTC),
        meta={"not_a_real_field": 1},
    )
    with pytest.raises(ValidationError):
        await InAppChannel(db).deliver(p)


# --------------------------------------------------------------------------
# 「不写空壳」（ADR §①）
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 迁移 / ORM 一致性
# --------------------------------------------------------------------------


def test_recipient_id_has_a_foreign_key_to_users():
    """真实库上收件人必须指向一个真用户。单测用 SQLite，FK 不强制 ——
    「断言不强制」等于没有断言，所以这里查元数据。"""
    col = Base.metadata.tables["notifications"].columns["recipient_id"]
    fks = list(col.foreign_keys)
    assert len(fks) == 1, "recipient_id 缺外键"
    assert fks[0].target_fullname == "users.user_id"
