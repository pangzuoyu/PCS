"""批量「提交校对」的 HTTP 面（P9B-3b · T3）。

守四件事：

1. **207 Multi-Status**：一条成功 + 一条失败 ⇒ 仍然 207（不是 200 也不是 500）；
2. **ACL**：非 `DESIGNER` / `PROCESS_CONTROLLOR` / `SYSTEM_ADMIN` ⇒ 整批 403
   （与单条端点同口径）；
3. **上限**：超过 `stream.batch_submit_limit` ⇒ 422 `SIM_STREAM_BATCH_LIMIT_EXCEEDED`；
4. **审计 N+1**：真正转移的每条 1 条 `RECORD_TRANSITION` + 批次 1 条
   `STREAM_BATCH_SUBMITTED`（幂等命中**不**写 `RECORD_TRANSITION`）。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.models.system import AuditLog

pytestmark = pytest.mark.asyncio

BATCH_URL = "/api/v1/streams/batch-submit"


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-viewer", role="VIEWER")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    await db.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="批量提交测试",
        owner_company="测试业主",
        location="测试地点",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db.add(proj)
    await db.commit()
    return proj


async def _make_draft(db: AsyncSession, proj, name: str) -> Stream:
    stream = Stream(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        stream_name=name,
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        source="MANUAL",
        phase="LIQUID",
        temp=80.0,
        press=200.0,
        mass_flow=1000.0,
        composition_json={"7732-18-5": 1.0},
        sign_status=StreamSignStatus.DRAFT,
        # ⚠️ `approval_depth` 是 Stream 上**唯一没有默认值**的 NOT NULL 列
        #   ⇒ 取值与 `StreamService.create` 一致（1 步校对）。
        approval_depth=1,
    )
    db.add(stream)
    await db.commit()
    await db.refresh(stream)
    return stream


async def test_batch_submit_returns_207_with_both_lists(
    client, db_session, make_project, designer_headers
):
    """⚠️ 一条成功 + 一条失败 ⇒ **207**，两张清单各自完整。"""
    proj = make_project
    good = await _make_draft(db_session, proj, "GOOD")
    missing = uuid.uuid4()

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(good.stream_id), str(missing)]},
        headers=designer_headers,
    )

    assert resp.status_code == 207, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert [s["stream_id"] for s in body["succeeded"]] == [str(good.stream_id)]
    assert body["succeeded"][0]["from_status"] == "DRAFT"
    assert body["succeeded"][0]["to_status"] == "IN_APPROVAL"
    # ⚠️ `status` 是**判别字段**（前端与调用方都靠它分流 ⇒ 必须真的在契约里）
    assert body["succeeded"][0]["status"] == "succeeded"
    assert [f["stream_id"] for f in body["failed"]] == [str(missing)]
    assert body["failed"][0]["reason"] == "SIM_STREAM_NOT_FOUND"
    assert body["failed"][0]["status"] == "failed"
    assert body["dry_run"] is False


async def test_batch_submit_requires_allowed_role(
    client, db_session, make_project, viewer_headers
):
    """越权 ⇒ **整批 403**（与单条端点同口径）。"""
    proj = make_project
    stream = await _make_draft(db_session, proj, "S-1")

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(stream.stream_id)]},
        headers=viewer_headers,
    )

    assert resp.status_code == 403, resp.text
    await db_session.refresh(stream)
    assert stream.sign_status.value == "DRAFT", "被拒的批次却改了状态"


async def test_batch_submit_rejects_empty_list(client, designer_headers):
    """空列表 ⇒ 422（请求体校验）。"""
    resp = await client.post(
        BATCH_URL, json={"stream_ids": []}, headers=designer_headers
    )
    assert resp.status_code == 422, resp.text


async def test_batch_submit_enforces_configured_limit(
    client, db_session, make_project, designer_headers
):
    """D4：把上限改成 1 ⇒ 提交 2 条 ⇒ 422 `SIM_STREAM_BATCH_LIMIT_EXCEEDED`。"""
    from app.services.system_setting_service import seed_defaults, update_batch

    proj = make_project
    s1 = await _make_draft(db_session, proj, "S-1")
    s2 = await _make_draft(db_session, proj, "S-2")

    await seed_defaults(db_session)
    await db_session.commit()
    await update_batch(
        db_session, {"stream.batch_submit_limit": 1}, actor_user_id=uuid.uuid4()
    )
    await db_session.commit()

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(s1.stream_id), str(s2.stream_id)]},
        headers=designer_headers,
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "SIM_STREAM_BATCH_LIMIT_EXCEEDED", resp.text
    await db_session.refresh(s1)
    await db_session.refresh(s2)
    assert s1.sign_status.value == "DRAFT", "超限的批次却执行了"
    assert s2.sign_status.value == "DRAFT"


async def test_batch_submit_writes_n_plus_one_audits(
    client, db_session, make_project, designer_headers
):
    """D3：审计 **N+1** 条（N 条 `RECORD_TRANSITION` + 1 条批次）。"""
    proj = make_project
    s1 = await _make_draft(db_session, proj, "S-1")
    s2 = await _make_draft(db_session, proj, "S-2")

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(s1.stream_id), str(s2.stream_id)]},
        headers=designer_headers,
    )
    assert resp.status_code == 207, resp.text
    batch_id = resp.json()["batch_id"]

    transitions = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "RECORD_TRANSITION")
            )
        )
        .scalars()
        .all()
    )
    assert len(transitions) == 2, f"应有 2 条单条审计，实际 {len(transitions)}"

    batch_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "STREAM_BATCH_SUBMITTED")
            )
        )
        .scalars()
        .all()
    )
    assert len(batch_rows) == 1, f"应有 1 条批次审计，实际 {len(batch_rows)}"
    assert batch_rows[0].resource_id == batch_id
    detail = batch_rows[0].detail_json or {}
    assert detail["total"] == 2
    assert len(detail["succeeded"]) == 2
    # ⚠️ **审计完整性**（委员会 2026-11-03 · D3 约束 2）：本端点**没有项目守卫**
    #    ⇒ 审计是唯一的事后追溯手段 ⇒ 这六个字段缺一不可（测试必须钉住）。
    assert detail["batch_id"] == batch_id
    assert detail["dry_run"] is False
    assert detail["requester_user_id"], "审计里没有操作人 ⇒ 事后追不到人"
    assert detail["requester_role"]
    assert sorted(detail["succeeded_ids"]) == sorted(
        [str(s1.stream_id), str(s2.stream_id)]
    )
    assert detail["failed_ids"] == []


async def test_batch_audit_resource_id_equals_response_batch_id(
    client, db_session, make_project, designer_headers
):
    """⚠️ **追溯链的完整性**：审计的 `resource_id` 必须**等于**响应的 `batch_id`。

    这是「跳过 D9（不改审计页）但保持追溯链可用」的最后一道保险 ——
    审计页靠 `resource_type=STREAM_BATCH` + `resource_id=<batch_id>` 查这一批
    ⇒ 两者若不等（一个用 `uuid4()` 一个用别的），**用户拿着响应里的 batch_id
    也查不到** ⇒ 「怎么查」写在 docstring 里也是空话。
    """
    proj = make_project
    s1 = await _make_draft(db_session, proj, "S-1")

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(s1.stream_id)]},
        headers=designer_headers,
    )
    assert resp.status_code == 207, resp.text
    batch_id = resp.json()["batch_id"]

    rows = (
        (
            await db_session.execute(
                select(AuditLog)
                .where(AuditLog.action == "STREAM_BATCH_SUBMITTED")
                .where(AuditLog.resource_id == batch_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, (
        f"用响应里的 batch_id={batch_id} 查不到批次审计 ⇒ 追溯链断了"
    )
    assert rows[0].resource_type == "STREAM_BATCH"


async def test_idempotent_hit_writes_no_second_transition_audit(
    client, db_session, make_project, designer_headers
):
    """⚠️ Review Focus #2：已 `IN_APPROVAL` ⇒ 记成功但**不写** `RECORD_TRANSITION`。"""
    proj = make_project
    s1 = await _make_draft(db_session, proj, "S-1")
    s1.sign_status = StreamSignStatus.IN_APPROVAL
    await db_session.commit()

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(s1.stream_id)]},
        headers=designer_headers,
    )

    assert resp.status_code == 207, resp.text
    body = resp.json()
    assert body["succeeded"][0]["note"] == "already_in_approval"

    transitions = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "RECORD_TRANSITION")
            )
        )
        .scalars()
        .all()
    )
    assert len(transitions) == 0, "幂等命中却写了单条转移审计"


async def test_dry_run_writes_no_audit_at_all(
    client, db_session, make_project, designer_headers
):
    """⚠️ Review Focus #3：预演 ⇒ **审计表零新增**（连批次那条也没有）。"""
    proj = make_project
    s1 = await _make_draft(db_session, proj, "S-1")

    resp = await client.post(
        BATCH_URL,
        json={"stream_ids": [str(s1.stream_id)], "dry_run": True},
        headers=designer_headers,
    )

    assert resp.status_code == 207, resp.text
    assert resp.json()["dry_run"] is True
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert rows == [], f"预演写了 {len(rows)} 条审计"
    await db_session.refresh(s1)
    assert s1.sign_status.value == "DRAFT"
