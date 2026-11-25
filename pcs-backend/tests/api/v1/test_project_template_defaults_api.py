"""模板的「默认单位制」（D1）+「BEDD 默认值」（D3）—— P10-K · TODO-210。

## 两条人裁（2026-11-25 · §7.10.6 复核后逐条裁定）

- **D1** —— 模板的单位制是**默认值** ⇒ ⇒ ⇒ **用户显式选过 ⇒ ⇒ ⇒ 不覆盖**
  ⇒ ⇒ ⇒ 「用户动没动过」**由调用方说**（`unit_system_source`）⇒ ⇒ ⇒
  **后端不猜**（猜错 = 静默推翻用户的显式选择 ⇒ ⇒ ⇒ 本仓最恨的那类事故）。
- **D3** —— 模板的 BEDD 默认值**只填空缺** ⇒ ⇒ ⇒ 与「输入清单」**完全同款**
  （按 key 幂等）⇒ ⇒ ⇒ 重复 apply **不丢用户数据**。

## 为什么用 `strict_client`

默认 `client` fixture 把项目守卫 mock 成永远 True ⇒ ⇒ ⇒ 在它上面测
「越权被拒」是**空断言** ⇒ ⇒ ⇒ 本组要测 404/403 ⇒ ⇒ ⇒ 必须用 conftest 的
**`strict_client`**（走真守卫）⇒ ⇒ ⇒ ⇒ 且**不自建** client ——
自建 client 的文件集合是**冻结的**（`tests/test_strict_client_ratchet.py`）。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.config_domain import ProjectTemplate
from app.models.enums import ProjectTemplateStatus
from app.models.project import Project, Workspace

pytestmark = pytest.mark.asyncio


def _admin_headers() -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject='admin-user', role='SYSTEM_ADMIN')}"
    }


async def _make_project(db: AsyncSession) -> uuid.UUID:
    workspace_id = uuid.uuid4()
    db.add(
        Workspace(
            workspace_id=workspace_id,
            workspace_type="FORMAL",
            name="WS-DEFAULTS",
            status="ACTIVE",
        )
    )
    await db.flush()
    project_id = uuid.uuid4()
    db.add(
        Project(
            project_id=project_id,
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="默认值测试项目",
            owner_company="PCS",
            location="惠州",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            status="DRAFT",
            workspace_id=workspace_id,
        )
    )
    await db.commit()
    return project_id


async def _make_template(
    db: AsyncSession,
    *,
    name: str,
    unit_system: str | None = None,
    bedd_defaults: dict | None = None,
) -> ProjectTemplate:
    tpl = ProjectTemplate(
        name=name,
        industry="CHEMICAL",
        default_config_json={"stream_approval": {"max_depth": 2}},
        version="1.0.0",
        status=ProjectTemplateStatus.PUBLISHED.value,
        unit_system=unit_system,
        bedd_defaults_json=bedd_defaults,
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def _apply(client, project_id: uuid.UUID, template_id: uuid.UUID, **body):
    payload = {"template_id": str(template_id), **body}
    return await client.post(
        f"/api/v1/projects/{project_id}/apply-template",
        headers=_admin_headers(),
        json=payload,
    )


async def _get_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    return (
        await db.execute(select(Project).where(Project.project_id == project_id))
    ).scalar_one()


# ---------------------------------------------------------------------------
# D1 · 默认单位制
# ---------------------------------------------------------------------------


async def test_template_unit_system_applies_when_user_did_not_choose(
    db_session, strict_client
):
    """⚠️ **用户没动过** ⇒ ⇒ ⇒ 模板的默认单位制**生效**（D1）。"""
    tpl = await _make_template(db_session, name="T-US", unit_system="US")
    project_id = await _make_project(db_session)

    r = await _apply(strict_client, project_id, tpl.template_id, unit_system_source="TEMPLATE")
    assert r.status_code == 200, r.text

    row = await _get_project(db_session, project_id)
    assert row.unit_system == "US"
    assert r.json()["segments"]["unit_system"] == "applied:US"


async def test_template_unit_system_does_not_override_user_choice(
    db_session, strict_client
):
    """⚠️ **用户显式选过 ⇒ ⇒ ⇒ 不覆盖**（D1 · 用户的显式选择优先）。"""
    tpl = await _make_template(db_session, name="T-US-2", unit_system="US")
    project_id = await _make_project(db_session)

    r = await _apply(strict_client, project_id, tpl.template_id, unit_system_source="FORM")
    assert r.status_code == 200, r.text

    row = await _get_project(db_session, project_id)
    assert row.unit_system == "SI"
    assert r.json()["segments"]["unit_system"] == "kept_form_value"


async def test_unit_system_source_defaults_to_form(db_session, strict_client):
    """⚠️ **不传来源 ⇒ ⇒ ⇒ 默认 `FORM`**（保守：不动用户的值）。"""
    tpl = await _make_template(db_session, name="T-US-3", unit_system="US")
    project_id = await _make_project(db_session)

    r = await _apply(strict_client, project_id, tpl.template_id)
    assert r.status_code == 200, r.text

    row = await _get_project(db_session, project_id)
    assert row.unit_system == "SI"


async def test_template_without_unit_system_changes_nothing(db_session, strict_client):
    """⚠️ 模板**没带**默认单位制（NULL）⇒ ⇒ ⇒ **什么都不做**。"""
    tpl = await _make_template(db_session, name="T-NO-US")
    project_id = await _make_project(db_session)

    r = await _apply(strict_client, project_id, tpl.template_id, unit_system_source="TEMPLATE")
    assert r.status_code == 200, r.text
    assert r.json()["segments"]["unit_system"] == "skipped_no_template_default"

    row = await _get_project(db_session, project_id)
    assert row.unit_system == "SI"


async def test_unit_system_source_must_be_known_value(db_session, strict_client):
    """⚠️ 非法来源 ⇒ ⇒ ⇒ **422**（不是静默当 FORM）。"""
    tpl = await _make_template(db_session, name="T-BAD-SRC", unit_system="US")
    project_id = await _make_project(db_session)

    r = await _apply(strict_client, project_id, tpl.template_id, unit_system_source="WHATEVER")
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# D3 · BEDD 默认值
# ---------------------------------------------------------------------------


async def test_bedd_defaults_fill_only_empty_fields(db_session, strict_client):
    """⚠️ **只填空缺** ⇒ ⇒ ⇒ 用户已填的**不动**（D3 · 与「输入清单」同款）。"""
    tpl = await _make_template(
        db_session,
        name="T-BEDD",
        bedd_defaults={
            "meteorology.pressure": 101.325,
            "meteorology.temperature": 25.0,
        },
    )
    project_id = await _make_project(db_session)
    # ⇒ ⇒ ⇒ 用户**先**填了温度（30）⇒ ⇒ ⇒ 模板的 25 **不该**覆盖它
    # ⚠️ 用 ORM 写（不是裸 SQL）⇒ ⇒ ⇒ JSONB 列在 SQLite 上不能直接绑 dict。
    row = await _get_project(db_session, project_id)
    row.bedd_json = {"meteorology": {"temperature": 30.0}}
    await db_session.commit()

    r = await _apply(strict_client, project_id, tpl.template_id)
    assert r.status_code == 200, r.text
    assert r.json()["segments"]["bedd_defaults"] == "filled:1"

    row = await _get_project(db_session, project_id)
    # ⚠️ **必须 refresh** —— 本会话在 apply **之前**读过这一行 ⇒ ⇒ ⇒
    #   identity map 里是**旧值** ⇒ ⇒ ⇒ apply 是在**另一个**会话里做的
    #   ⇒ ⇒ ⇒ 不 refresh ⇒ ⇒ ⇒ 读到的是**旧快照**（看着像「没生效」）。
    await db_session.refresh(row)
    doc = row.bedd_json or {}
    assert doc["meteorology"]["temperature"] == 30.0, "用户的值被模板覆盖了"
    assert doc["meteorology"]["pressure"] == 101.325, "空缺没被填上"


async def test_bedd_defaults_reject_unknown_field_path(db_session, strict_client):
    """⚠️ **不存在的字段路径 ⇒ ⇒ ⇒ 422**（不是静默丢弃）。"""
    tpl = await _make_template(
        db_session, name="T-BEDD-BAD", bedd_defaults={"meteorology.nope": 1}
    )
    project_id = await _make_project(db_session)

    r = await _apply(strict_client, project_id, tpl.template_id)
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "TEMPLATE_BEDD_DEFAULTS_INVALID"


async def test_bedd_defaults_are_idempotent(db_session, strict_client):
    """⚠️ 重复 apply ⇒ ⇒ ⇒ **幂等**（已填的不动 ⇒ 第二次 `filled:0`）。"""
    tpl = await _make_template(
        db_session,
        name="T-BEDD-IDEM",
        bedd_defaults={"meteorology.pressure": 101.325},
    )
    project_id = await _make_project(db_session)

    first = await _apply(strict_client, project_id, tpl.template_id)
    assert first.status_code == 200, first.text
    assert first.json()["segments"]["bedd_defaults"] == "filled:1"

    second = await _apply(strict_client, project_id, tpl.template_id)
    assert second.status_code == 200, second.text
    assert second.json()["segments"]["bedd_defaults"] == "filled:0"
