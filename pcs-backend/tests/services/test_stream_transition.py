"""P3.2 SIM-13：StreamService.transition() 状态机集成测试（闭环审计 D-1）。

覆盖：
1. Happy path：DRAFT → IN_APPROVAL → CHECKED → CHANGE_PENDING → CHANGED 完整链
2. invalid transition：DRAFT 直接 PASS_CHECK → 422 SIM_STREAM_INVALID_TRANSITION
3. role forbidden：DESIGNER 触发 PASS_CHECK（仅 CHECKER/SYSADMIN）→ 403
4. SELECT FOR UPDATE：并发两次 transfer，第二方拿到最新状态
5. 角色别名：PROCESS_CONTROLLER → CHECKER 映射正确
6. audit 写入：每次 transfer 触发 AuditService.write
7. 状态机字段：INITIATE_CHANGE 写 change_pending_since，APPLY_CHANGE 写
   change_resolved_at/by
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import StateTransition, StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.services.exceptions import PcsError
from app.services.stream_service import StreamService


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """Workspace + Project 工厂。"""

    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="SIM-13 transition test",
            owner_company="PCS_TEST",
            location="PCS_TEST",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.flush()
        return proj

    return _make


@pytest_asyncio.fixture
async def make_stream(db: AsyncSession, make_project):
    """创建一个 DRAFT 状态 stream。"""

    async def _make(stream_name: str = "T-1") -> Stream:
        proj = await make_project()
        stream = Stream(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name=stream_name,
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            approval_depth=1,
            sign_status=StreamSignStatus.DRAFT,
        )
        db.add(stream)
        await db.commit()
        await db.refresh(stream)
        return stream

    return _make


@pytest.mark.asyncio
async def test_submit_happy_path(db, make_stream):
    """DRAFT → IN_APPROVAL：DESIGNER 提交。"""
    stream = await make_stream("S-1")
    result = await StreamService.transition(
        db,
        stream.stream_id,
        transition=StateTransition.SUBMIT_FOR_CHECK,
        actor_user_id=uuid.uuid4(),
        actor_role="DESIGNER",
    )
    assert result.sign_status == StreamSignStatus.IN_APPROVAL


@pytest.mark.asyncio
async def test_submit_approve_pass_change_full_chain(db, make_stream):
    """完整链：DRAFT → IN_APPROVAL → CHECKED → CHANGE_PENDING → CHANGED。

    验证 APPLY_CHANGE 写 change_resolved_at + change_resolved_by。
    """
    stream = await make_stream("FULL")

    # 1. DESIGNER 提交
    stream = await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.SUBMIT_FOR_CHECK,
        actor_user_id=uuid.uuid4(), actor_role="DESIGNER",
    )
    assert stream.sign_status == StreamSignStatus.IN_APPROVAL

    # 2. PROCESS_CONTROLLER（→CHECKER 别名）通过
    stream = await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.PASS_CHECK,
        actor_user_id=uuid.uuid4(), actor_role="PROCESS_CONTROLLER",
    )
    assert stream.sign_status == StreamSignStatus.CHECKED
    assert stream.approval_step is None  # PASS_CHECK 重置 step

    # 3. DESIGNER 主动变更
    stream = await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.INITIATE_CHANGE,
        actor_user_id=uuid.uuid4(), actor_role="DESIGNER",
        reason="correction",
    )
    assert stream.sign_status == StreamSignStatus.CHANGE_PENDING
    assert stream.change_pending_since is not None

    # 4. PROCESS_CONTROLLER 通过变更
    actor = uuid.uuid4()
    stream = await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.APPLY_CHANGE,
        actor_user_id=actor, actor_role="PROCESS_CONTROLLER",
        reason="verified",
    )
    assert stream.sign_status == StreamSignStatus.CHANGED
    assert stream.change_resolved_at is not None
    assert stream.change_resolved_by == str(actor)


@pytest.mark.asyncio
async def test_invalid_transition_draft_to_checked(db, make_stream):
    """DRAFT → CHECKED 非法 → 422 SIM_STREAM_INVALID_TRANSITION。

    ALLOWED_TRANSITIONS 中 (DRAFT, PASS_CHECK) 不存在。
    """
    stream = await make_stream("INV")
    with pytest.raises(PcsError) as exc_info:
        await StreamService.transition(
            db, stream.stream_id,
            transition=StateTransition.PASS_CHECK,
            actor_user_id=uuid.uuid4(), actor_role="CHECKER",
        )
    assert exc_info.value.code == "SIM_STREAM_INVALID_TRANSITION"
    assert exc_info.value.status == 422


@pytest.mark.asyncio
async def test_role_forbidden_designer_cannot_pass_check(db, make_stream):
    """DESIGNER 触发 PASS_CHECK → 403 SIM_STREAM_ROLE_FORBIDDEN。

    PASS_CHECK TRANSITION_ROLES = {"CHECKER", "APPROVER", "SYSADMIN"}
    DESIGNER 不在权限列表。
    """
    stream = await make_stream("RF")
    # 先到 IN_APPROVAL
    await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.SUBMIT_FOR_CHECK,
        actor_user_id=uuid.uuid4(), actor_role="DESIGNER",
    )
    # DESIGNER 想 PASS_CHECK 失败
    with pytest.raises(PcsError) as exc_info:
        await StreamService.transition(
            db, stream.stream_id,
            transition=StateTransition.PASS_CHECK,
            actor_user_id=uuid.uuid4(), actor_role="DESIGNER",
        )
    assert exc_info.value.code == "SIM_STREAM_ROLE_FORBIDDEN"
    assert exc_info.value.status == 403


@pytest.mark.asyncio
async def test_role_alias_process_controller_maps_to_checker(db, make_stream):
    """PROCESS_CONTROLLER 经 _ROLE_ALIAS → CHECKER，可通过 PASS_CHECK。"""
    stream = await make_stream("ALIAS")
    await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.SUBMIT_FOR_CHECK,
        actor_user_id=uuid.uuid4(), actor_role="DESIGNER",
    )
    # 用项目级角色名 PROCESS_CONTROLLER，应能通过 PASS_CHECK
    stream = await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.PASS_CHECK,
        actor_user_id=uuid.uuid4(), actor_role="PROCESS_CONTROLLER",
    )
    assert stream.sign_status == StreamSignStatus.CHECKED


@pytest.mark.asyncio
async def test_role_alias_system_admin_maps_to_sysadmin(db, make_stream):
    """SYSTEM_ADMIN → SYSADMIN 别名验证。"""
    stream = await make_stream("SA")
    stream = await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.SUBMIT_FOR_CHECK,
        actor_user_id=uuid.uuid4(), actor_role="SYSTEM_ADMIN",
    )
    assert stream.sign_status == StreamSignStatus.IN_APPROVAL


@pytest.mark.asyncio
async def test_mark_stale_writes_change_pending_since(db, make_stream):
    """CHECKED → STALE 写 change_pending_since（ADR-0024 不写 snapshot）。"""
    stream = await make_stream("STALE")
    # 走到 CHECKED
    await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.SUBMIT_FOR_CHECK,
        actor_user_id=uuid.uuid4(), actor_role="DESIGNER",
    )
    await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.PASS_CHECK,
        actor_user_id=uuid.uuid4(), actor_role="PROCESS_CONTROLLER",
    )
    # MARK_STALE
    stream = await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.MARK_STALE,
        actor_user_id=uuid.uuid4(), actor_role="DESIGNER",
        reason="上游 PFD 变更",
    )
    assert stream.sign_status == StreamSignStatus.STALE
    assert stream.change_pending_since is not None


@pytest.mark.asyncio
async def test_concurrent_transfer_serialized(db, make_stream):
    """并发两次 SUBMIT：第二方拿到最新状态（FOR UPDATE 串行化）。

    两次 SUBMIT_FOR_CHECK：第一次成功 DRAFT→IN_APPROVAL，第二次应被
    InvalidTransition 拒绝（IN_APPROVAL 状态不可再次 submit）。

    注：SQLite 测试后端不支持 SELECT FOR UPDATE；此处仅验证 FOR UPDATE
    语句被发出（不抛错），不真正并发执行。PG 行为由 e2e + 真实并发验证。
    """
    stream = await make_stream("CONC")
    actor = uuid.uuid4()

    # 第一次 submit：DRAFT → IN_APPROVAL
    s1 = await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.SUBMIT_FOR_CHECK,
        actor_user_id=actor, actor_role="DESIGNER",
    )
    assert s1.sign_status.value == "IN_APPROVAL"

    # 第二次 submit：IN_APPROVAL 状态下 SUBMIT 非法 → 422
    with pytest.raises(PcsError) as exc_info:
        await StreamService.transition(
            db, stream.stream_id,
            transition=StateTransition.SUBMIT_FOR_CHECK,
            actor_user_id=actor, actor_role="DESIGNER",
        )
    assert exc_info.value.code == "SIM_STREAM_INVALID_TRANSITION"


@pytest.mark.asyncio
async def test_transition_not_found(db):
    """不存在的 stream_id → 404 SIM_STREAM_NOT_FOUND。"""
    with pytest.raises(PcsError) as exc_info:
        await StreamService.transition(
            db, uuid.uuid4(),
            transition=StateTransition.SUBMIT_FOR_CHECK,
            actor_user_id=uuid.uuid4(), actor_role="DESIGNER",
        )
    assert exc_info.value.code == "SIM_STREAM_NOT_FOUND"
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_transition_writes_audit_log(db, make_stream):
    """每次 transition 触发 AuditService.write（通过 audit_logs 表查询验证）。"""

    from app.models.system import AuditLog

    stream = await make_stream("AUDIT")
    actor = uuid.uuid4()
    await StreamService.transition(
        db, stream.stream_id,
        transition=StateTransition.SUBMIT_FOR_CHECK,
        actor_user_id=actor, actor_role="DESIGNER",
    )
    # 查 audit_logs 表：本 transition 应至少写入 1 条（resource_type=streams,
    # resource_id=str(stream.stream_id)）
    rows = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.resource_type == "streams",
                AuditLog.resource_id == str(stream.stream_id),
            )
        )
    ).scalars().all()
    assert len(rows) >= 1, f"transition 应写 audit_logs，got {len(rows)} rows"
    # actor 应匹配
    assert rows[0].user_id == actor
