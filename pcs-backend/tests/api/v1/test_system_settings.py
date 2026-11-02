"""系统参数 CRUD（§7.20.1 · P9B-3 · T4）。

## 硬约束：批量 + **原子**

委员会 2026-11-02 裁决「硬约束 1」：系统参数页一次改多个参数 ⇒
**一次 PUT**（body 是 `{key: value}` 的 map）⇒ 事务内**要么全改、要么全不改**。
⚠️ 不做「每个键一个 PATCH」—— 那会让「保存」变成 N 个请求且中途失败留半改状态。
⇒ 本文件的核心断言就是**原子性**：一个键非法 ⇒ **一个键都不改**。

## 权限

系统参数是**全局**开关（会话超时、编辑锁 TTL……）⇒ 只给 `SYSTEM_ADMIN`。
漏一处 `require_roles` 就是一条越权路径 ⇒ 非管理员的 403 是硬断言。

## 「表存在」≠「API 存在」

`system_settings` 表**早就存在**（`app/models/system.py`），但此前**零 API**
⇒ 本文件是它的**第一个**对外形状 ⇒ 「表存在」不等于「有端点」。
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.system import AuditLog, SystemSetting

pytestmark = pytest.mark.asyncio

#: seed 出来的默认键（与 service 的 DEFAULT_SETTINGS 一一对应）。
SEED_KEYS = (
    "session.timeout_minutes",
    "notification.retention_days",
    "edit_lock.ttl_minutes",
    "edit_lock.renew_enabled",
    "record.self_check_allowed",
    "equip_list.auto_sync_enabled",
    "stream.batch_submit_limit",
)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    token = create_access_token(subject="test-admin", role="SYSTEM_ADMIN")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def seeded(db_session: AsyncSession) -> AsyncSession:
    """seed 默认参数（启动钩子在真库做这件事，测试里手动做）。"""
    from app.services.system_setting_service import seed_defaults

    await seed_defaults(db_session)
    await db_session.commit()
    return db_session


async def _read_value(db: AsyncSession, key: str):
    row = await db.get(SystemSetting, key)
    return None if row is None else row.setting_value_json


# ---------------------------------------------------------------------------
# 断言 1：GET —— 管理员能读，非管理员 403
# ---------------------------------------------------------------------------


async def test_get_settings_requires_system_admin(client, seeded, designer_headers):
    """非 SYSTEM_ADMIN ⇒ 403（系统参数是全局开关）。"""
    resp = await client.get("/api/v1/system-settings", headers=designer_headers)

    assert resp.status_code == 403, resp.text


async def test_get_settings_returns_all_seeded_keys(client, seeded, admin_headers):
    """SYSTEM_ADMIN ⇒ 200 + 全部默认键都在列表里。"""
    resp = await client.get("/api/v1/system-settings", headers=admin_headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    keys = {item["setting_key"] for item in body}
    assert keys == set(SEED_KEYS), body
    for item in body:
        assert "setting_value_json" in item, item
        assert "updated_at" in item, item


# ---------------------------------------------------------------------------
# 断言 2：PUT —— 一次提交全部改动 + **一条**审计
# ---------------------------------------------------------------------------


async def test_put_updates_all_keys_and_writes_one_audit(client, seeded, admin_headers):
    """两个键一次 PUT ⇒ 两个都变 + **一条** SYSTEM_SETTINGS_UPDATED 审计。"""
    resp = await client.put(
        "/api/v1/system-settings",
        json={
            "settings": {
                "session.timeout_minutes": 45,
                "edit_lock.ttl_minutes": 15,
            }
        },
        headers=admin_headers,
    )

    assert resp.status_code == 200, resp.text
    updated = {item["setting_key"]: item["setting_value_json"] for item in resp.json()["updated"]}
    assert updated["session.timeout_minutes"] == 45
    assert updated["edit_lock.ttl_minutes"] == 15

    rows = (
        (
            await seeded.execute(
                select(AuditLog).where(AuditLog.action == "SYSTEM_SETTINGS_UPDATED")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"应恰好一条审计，实际 {len(rows)}"
    detail = rows[0].detail_json or {}
    assert set(detail.get("keys", [])) == {
        "session.timeout_minutes",
        "edit_lock.ttl_minutes",
    }, detail


# ---------------------------------------------------------------------------
# 断言 3（P2-1 / 硬约束 1 的核心）：**原子性**
# ---------------------------------------------------------------------------


async def test_put_with_unknown_key_changes_nothing(client, seeded, admin_headers):
    """⚠️ 批次里有一个**不存在的键** ⇒ 404 ⇒ **另一个合法键的值没变**。

    这正是「一次 PUT + 事务内全改或全不改」的意义：半改状态会让管理员
    以为自己保存成功，而实际只有一部分生效。
    """
    before = await _read_value(seeded, "session.timeout_minutes")

    resp = await client.put(
        "/api/v1/system-settings",
        json={
            "settings": {
                "session.timeout_minutes": 999,
                "no.such.key": 1,
            }
        },
        headers=admin_headers,
    )

    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "SYSTEM_SETTING_NOT_FOUND", resp.text

    after = await _read_value(seeded, "session.timeout_minutes")
    assert after == before, "非法批次里合法键的值被改了 ⇒ 违反原子性"


# ---------------------------------------------------------------------------
# 断言 4：seed 幂等（启动两次不多写、也不覆盖管理员改过的值）
# ---------------------------------------------------------------------------


async def test_seed_is_idempotent(db_session: AsyncSession):
    """启动两次 ⇒ 不多写行、且**不覆盖**管理员改过的值。"""
    from app.services.system_setting_service import DEFAULT_SETTINGS, seed_defaults

    await seed_defaults(db_session)
    await db_session.commit()
    await db_session.execute(
        update(SystemSetting)
        .where(SystemSetting.setting_key == "session.timeout_minutes")
        .values(setting_value_json={"v": 999})
    )
    await db_session.commit()
    await seed_defaults(db_session)
    await db_session.commit()

    rows = (await db_session.execute(select(SystemSetting))).scalars().all()
    assert len(rows) == len(DEFAULT_SETTINGS), "重复 seed 写出了重复行"
    kept = next(r for r in rows if r.setting_key == "session.timeout_minutes")
    assert kept.setting_value_json == {"v": 999}, "seed 覆盖了管理员改过的值"
