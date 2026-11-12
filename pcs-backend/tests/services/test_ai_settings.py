"""AI 开关与配置（P10-A · Task T4）。

## 为什么 AI 的开关**只在 `system_settings`**（不在 env）

env 侧如果也有一个 `AI_ENABLED` ⇒ 就有**两个**开关 ⇒ 语义必然是 AND ⇒
管理员在页面上翻了开关却**没生效**（因为 env 那道还关着）⇒
「改了配置没用」是最难查的一类问题。
⇒ **单一真相源 = `system_settings.ai_enabled`**（偏离登记 D13）。

## 分工

- **env**（部署级，改了要重启）：`ai_endpoint` · `internal_cidrs` · `ai_mask_person_name`
- **system_settings**（管理员可编辑、运行时）：6 个 AI 键
  ⇒ 前端参数页**显示全部键** ⇒ AI 键**自动可见**（前端无需改）。
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.system import SystemSetting
from app.services.system_setting_service import DEFAULT_SETTINGS, seed_defaults

#: 6 个 AI 键 + 期望默认值（SPEC §4.1.3）。
AI_KEYS: dict[str, object] = {
    "ai_enabled": False,
    "ai_model_version": None,
    "ai_endpoint": None,
    "ai_timeout": 30,
    "ai_max_tokens": 4096,
    "ai_temperature": 0.1,
}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    token = create_access_token(subject="test-admin", role="SYSTEM_ADMIN")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def seeded(db_session: AsyncSession) -> AsyncSession:
    await seed_defaults(db_session)
    await db_session.commit()
    return db_session


async def test_ai_settings_defaults(db_session: AsyncSession) -> None:
    """6 个 AI 键存在且默认值正确。"""
    defaults = {item["key"]: item["value"] for item in DEFAULT_SETTINGS}

    for key, expected in AI_KEYS.items():
        assert key in defaults, f"DEFAULT_SETTINGS 少了 {key}"
        assert defaults[key] == expected, f"{key} 默认值 {defaults[key]!r} ≠ {expected!r}"


async def test_ai_settings_are_seeded_into_the_table(
    seeded: AsyncSession,
) -> None:
    """启动钩子（`seed_defaults`）把 6 个 AI 键灌进表 ⇒ 参数页不是空白。"""
    rows = (
        (await seeded.execute(select(SystemSetting))).scalars().all()
    )
    values = {row.setting_key: row.setting_value_json for row in rows}

    for key, expected in AI_KEYS.items():
        assert key in values, f"表里没有 {key}"
        assert values[key] == expected, f"{key} 落库值 {values[key]!r} ≠ {expected!r}"


async def test_ai_settings_keys_are_visible_in_the_admin_page(
    client, seeded: AsyncSession, admin_headers: dict[str, str]
) -> None:
    """参数页列出**全部**键 ⇒ AI 键自动可见（前端无需改）。

    ⚠️ 这是「前端不用改」的**依据** —— 若哪天参数页改成只显示白名单键，
    这条测试会红 ⇒ 前端要同步改。
    """
    resp = await client.get("/api/v1/system-settings", headers=admin_headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    keys = {item["setting_key"] for item in body}
    for key in AI_KEYS:
        assert key in keys, f"参数页看不到 {key}"


async def test_env_has_no_ai_switch() -> None:
    """⚠️ env 侧**不设** `AI_ENABLED` ⇒ 只有一个开关（单一真相源）。

    env 有第二个开关 ⇒ 两处语义 AND ⇒ 管理员改了页面不生效 ⇒ 最难查的一类问题。
    """
    from app.core.config import Settings

    assert "ai_enabled" not in Settings.model_fields
    # 但 env 侧的**部署级**配置必须在
    assert "ai_endpoint" in Settings.model_fields
    assert "internal_cidrs" in Settings.model_fields
    assert "ai_mask_person_name" in Settings.model_fields
