"""记录编辑审计读端点（`GET /records/{module}/{record_id}/edits`）—— P9B-2 · T1。

## 为什么需要它

SPEC §6.21 P9A-LCK-006 要求 409 弹窗提供「查看差异」，而差异内容在**编辑审计**
里（`audit_logs` 的 `RECORD_EDITED`）。但唯一的读端点 `GET /audit-logs`
**限 SYSTEM_ADMIN** ⇒ 普通 DESIGNER 拿到冲突弹窗却**点不开差异**。

⚠️ **`audit_logs` 表没有 `project_id`** ⇒ 授权只能靠
「`resource_type` + `resource_id` → 反查记录 → 记录的项目」。

## `changed_fields` 是**字段名列表**，不是值

一次大改版几十 KB，审计里只记字段名（ADR-0048 §⑦）。本端点**原样透传**，
**不**去回查旧值 —— 回查旧值需要快照表，而那是另一个设计（TODO）。

## 越权 404 必须用 `_guard_client`

默认 `client` fixture 把 `check_user_project_access` mock 成恒 True ⇒
在它上面测「越权被拒」是**空断言**：守卫根本没跑。
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import CostEstResult
from app.models.enums import AuditAction
from app.models.system import AuditLog

pytestmark = pytest.mark.asyncio

_MODULE = "cooling_tower_result"


@pytest.fixture
def auth(sample_user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {sample_user_token}"}


@contextlib.asynccontextmanager
async def _guard_client(db_engine):
    """独立 client —— **不**套 conftest 的 `check_user_project_access` bypass mock。"""
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.api.v1 import api_router
    from app.core.errors import install_exception_handlers
    from app.db.session import get_db

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app = FastAPI(title="PCS Test Guard")
    install_exception_handlers(app)
    app.include_router(api_router)
    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def _cooling_tower_body(**overrides) -> dict:
    body = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "tag_number": f"CT-{uuid.uuid4().hex[:8]}",
        "standard_profile_code": "CTI_ATC_105",
        "calc_type": "MERKEL",
        "sign_status": "DRAFT",
        "duty_kw": 1500.0,
        "water_flow_m3h": 360.0,
        "makeup_water_m3h": 7.2,
        "fan_power_kw": 3.1746,
        "merkel_integral": 0.9811,
        "input_json": {"t1_c": 40, "t2_c": 30},
        "output_json": {"kav_l": 0.9811},
    }
    body.update(overrides)
    return body


async def _make_record(client, auth) -> tuple[uuid.UUID, str]:
    """建一条 cooling_tower 记录 ⇒ (record_id, record_hash)。"""
    resp = await client.post(
        "/api/v1/cool-tower/results", json=_cooling_tower_body(), headers=auth
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return uuid.UUID(data["id"]), data["record_hash"]


async def _seed_edit(
    db: AsyncSession,
    *,
    record_id: uuid.UUID,
    changed_fields: list[str] | None = None,
    overwrote_stale_baseline: bool = False,
    action: str = AuditAction.RECORD_EDITED.value,
    occurred_at: datetime | None = None,
    resource_type: str = _MODULE,
    detail: dict | None = None,
) -> uuid.UUID:
    """写一条编辑审计（形状与 `edit_guard.record_edit_audit` 一致）。"""
    if detail is None:
        detail = {
            "changed_fields": changed_fields or [],
            "overwrote_stale_baseline": overwrote_stale_baseline,
        }
    row = AuditLog(
        user_id=uuid.uuid4(),
        action=action,
        resource_type=resource_type,
        resource_id=str(record_id),
        detail_json=detail,
        occurred_at=occurred_at or datetime.now(UTC),
    )
    db.add(row)
    await db.commit()
    return row.audit_id


def _url(record_id: uuid.UUID, module: str = _MODULE, suffix: str = "") -> str:
    return f"/api/v1/records/{module}/{record_id}/edits{suffix}"


# ---------------------------------------------------------------------------
# 基本读取
# ---------------------------------------------------------------------------


async def test_lists_record_edits_with_changed_fields(client, auth, db_session):
    """两条 `RECORD_EDITED` ⇒ 2 条 items，`changed_fields` 正确。"""
    record_id, _hash = await _make_record(client, auth)
    await _seed_edit(db_session, record_id=record_id, changed_fields=["duty_kw"])
    await _seed_edit(
        db_session, record_id=record_id, changed_fields=["duty_kw", "fan_power_kw"]
    )

    resp = await client.get(_url(record_id), headers=auth)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["record_type"] == _MODULE
    assert body["record_id"] == str(record_id)
    assert body["total"] == 2
    assert len(body["items"]) == 2
    fields = {tuple(i["changed_fields"]) for i in body["items"]}
    assert fields == {("duty_kw",), ("duty_kw", "fan_power_kw")}


async def test_only_record_edited_actions_are_listed(client, auth, db_session):
    """别的 action 的审计行**不出现**（如 `RECORD_CREATED` / `RECORD_UPDATED`）。

    ⚠️ 不得用「该记录最近一条审计」泛匹配去凑（ADR-0048 §⑦ 强制）。
    """
    record_id, _hash = await _make_record(client, auth)
    await _seed_edit(
        db_session,
        record_id=record_id,
        action=AuditAction.RECORD_CREATED.value,
        changed_fields=["x"],
    )
    await _seed_edit(
        db_session,
        record_id=record_id,
        action=AuditAction.RECORD_UPDATED.value,
        changed_fields=["y"],
    )
    await _seed_edit(db_session, record_id=record_id, changed_fields=["duty_kw"])

    resp = await client.get(_url(record_id), headers=auth)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["changed_fields"] == ["duty_kw"]


async def test_other_records_edits_are_not_listed(client, auth, db_session):
    """A 记录的编辑历史不得出现在 B 记录下。"""
    a, _ = await _make_record(client, auth)
    b, _ = await _make_record(client, auth)
    await _seed_edit(db_session, record_id=a, changed_fields=["duty_kw"])

    resp = await client.get(_url(b), headers=auth)

    assert resp.status_code == 200, resp.text
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


async def test_overwrote_stale_baseline_flag_is_reported(client, auth, db_session):
    """「覆盖了无法校验的基线」这个标记要透出来（ADR-0048 §⑦）。"""
    record_id, _hash = await _make_record(client, auth)
    await _seed_edit(
        db_session,
        record_id=record_id,
        changed_fields=["duty_kw"],
        overwrote_stale_baseline=True,
    )

    resp = await client.get(_url(record_id), headers=auth)

    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["overwrote_stale_baseline"] is True


# ---------------------------------------------------------------------------
# 授权 / 模块解析
# ---------------------------------------------------------------------------


async def test_other_project_record_is_404(db_engine, db_session, auth):
    """别人项目的记录 ⇒ 404（按**项目**守卫，不是按审计行）。

    ⚠️ **本测试不能请求 `client` fixture** —— 它的 monkeypatch 会把
    `check_user_project_access` mock 成恒 True，**在整个测试期间**都生效
    （monkeypatch 是函数作用域）⇒ 在它旁边测「越权被拒」是**空断言**。
    ⇒ 记录**直接在 DB 里造**（不走 `client`）。
    """
    record_id = uuid.uuid4()
    db_session.add(
        CostEstResult(
            cost_est_id=record_id,
            equipment_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            estimated_cost=1000.0,
            cost_index_year=2026,
        )
    )
    await db_session.commit()

    async with _guard_client(db_engine) as ac:
        resp = await ac.get(_url(record_id, module="CostEstResult"), headers=auth)

    assert resp.status_code == 404
    # ⚠️ 只断言 404 会在「端点还不存在」时也绿 ⇒ 断**消息**（路由未命中说的是
    #    "Not Found"，项目守卫说的是 "Project not found: ..."）。
    assert "Project not found" in resp.json()["message"]


async def test_unknown_module_is_422_with_code(client, auth):
    """未知 module ⇒ 422 `RECORD_MODULE_UNKNOWN`（不是 404）。"""
    resp = await client.get(
        f"/api/v1/records/NotARecordType/{uuid.uuid4()}/edits", headers=auth
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "RECORD_MODULE_UNKNOWN"


async def test_module_without_sign_status_still_works(client, auth, db_session):
    """缺 9 态列的模块（`cost_est`）也能用（`need_mixin=False`）⇒ 200。

    ⚠️ 编辑历史对**任何有归属项目**的记录都开放 —— 没有 `sign_status` 的表
    也能查它改过什么。
    """
    record_id = uuid.uuid4()
    db_session.add(
        CostEstResult(
            cost_est_id=record_id,
            equipment_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            estimated_cost=1000.0,
            cost_index_year=2026,
        )
    )
    await db_session.commit()
    await _seed_edit(
        db_session,
        record_id=record_id,
        changed_fields=["estimated_cost"],
        resource_type="CostEstResult",
    )

    resp = await client.get(_url(record_id, module="CostEstResult"), headers=auth)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["record_type"] == "CostEstResult"
    assert body["total"] == 1
    assert body["items"][0]["changed_fields"] == ["estimated_cost"]


async def test_unknown_record_is_404_with_code(client, auth):
    """记录不存在 ⇒ 404 且带 code（只断言 404 会在端点不存在时就绿）。"""
    resp = await client.get(_url(uuid.uuid4()), headers=auth)

    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "RECORD_NOT_FOUND"


# ---------------------------------------------------------------------------
# 坏数据 / 分页
# ---------------------------------------------------------------------------


async def test_malformed_detail_json_yields_empty_changed_fields(
    client, auth, db_session
):
    """`detail_json` 畸形 ⇒ `changed_fields == []` 且**不 500**。"""
    record_id, _hash = await _make_record(client, auth)
    await _seed_edit(db_session, record_id=record_id, detail={})
    await _seed_edit(
        db_session, record_id=record_id, detail={"changed_fields": "not-a-list"}
    )

    resp = await client.get(_url(record_id), headers=auth)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["changed_fields"] == []


async def test_pagination_keeps_total(client, auth, db_session):
    """`?limit=1` ⇒ 1 条，但 `total` 仍是全部条数。"""
    record_id, _hash = await _make_record(client, auth)
    for i in range(3):
        await _seed_edit(db_session, record_id=record_id, changed_fields=[f"f{i}"])

    resp = await client.get(_url(record_id), headers=auth, params={"limit": 1})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["total"] == 3


async def test_newest_first_ordering(client, auth, db_session):
    """最新在前（时间倒序）。"""
    record_id, _hash = await _make_record(client, auth)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(3):
        await _seed_edit(
            db_session,
            record_id=record_id,
            changed_fields=[f"f{i}"],
            occurred_at=base.replace(minute=i),
        )

    resp = await client.get(_url(record_id), headers=auth)

    assert resp.status_code == 200, resp.text
    assert [i["changed_fields"][0] for i in resp.json()["items"]] == ["f2", "f1", "f0"]


# ---------------------------------------------------------------------------
# 端到端：真的编辑 ⇒ 真的能被读出来
# ---------------------------------------------------------------------------


async def test_real_edit_is_listed(client, auth):
    """走真的 PATCH ⇒ 真的写审计 ⇒ 本端点真的读得出来。

    ⚠️ 前面几条是**手写**审计行；这一条证明端点读的是**真实链路**写出的行
    （形状一致 ⇒ 不会只对手写形状生效）。
    """
    record_id, record_hash = await _make_record(client, auth)
    resp = await client.patch(
        f"/api/v1/cool-tower/results/{record_id}",
        json={"duty_kw": 20.0, "fan_power_kw": 9.9, "expected_hash": record_hash},
        headers=auth,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(_url(record_id), headers=auth)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["changed_fields"] == ["duty_kw", "fan_power_kw"]
