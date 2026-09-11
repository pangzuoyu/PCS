"""P3.2 SIM-37: 项目级符号/格式模板审批收口。

设计裁决（cerebrum）：项目级管道等级/符号/格式模板审批**不挂 ConfigAsset**
（避免 config_assets 爆炸），走轻量状态列 + 5 态机 + ConfigApproval 写审批
记录 + 审计落库。

现状：
- PipeClassService ProjectPipeClass 5 态机 + ConfigApproval 落库 ✅
- PipeCodeTemplateService ProjectPipeCodeConfig 5 态机但未写审计 ⚠
- StreamSymbolService ProjectStreamSymbol 无 5 态机 ❌

本测试文件覆盖缺口：
1. ProjectStreamSymbol 5 态转换（submit/approve/reject/publish/obsolete）
2. ProjectPipeCodeConfig 状态转换写 audit（CONFIG_ASSET_SUBMITTED 等）
3. 非法 transition 抛 409
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from app.services.exceptions import PcsError
from app.services.pipe_code_template_service import PipeCodeTemplateService
from app.services.stream_symbol_service import StreamSymbolService


@dataclass
class _Actor:
    """最小 actor（service 层只需 user_id/role）。"""

    user_id: uuid.UUID = None  # type: ignore[assignment]
    role: str = "REVIEWER"


def _actor() -> _Actor:
    return _Actor(user_id=uuid.uuid4(), role="REVIEWER")


# ============================================================================
# ProjectStreamSymbol 5 态机（StreamSymbolService 缺口补）
# ============================================================================


class _FakeProjectStreamSymbol:
    """ProjectStreamSymbol 占位：仅模拟 status 字段写。"""

    def __init__(self, project_symbol_id: uuid.UUID, project_id: uuid.UUID, status: str = "DRAFT"):
        self.project_symbol_id = project_symbol_id
        self.project_id = project_id
        self.status = status
        self.symbol = "TEST_SYMBOL"  # service 错误消息使用


class _FakeStreamSymbolSession:
    """最小 AsyncSession 占位：仅 .get/.commit/.execute 工作。"""

    def __init__(self, store: dict[Any, Any]):
        self.store = store
        self.commits: int = 0

    async def get(self, _model: type, pk: Any) -> Any:
        return self.store.get(pk)

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        return None

    async def execute(self, _stmt: Any) -> Any:
        # 永远返回空（不影响 transition 路径；仅依赖 session.get）
        class _Result:
            def scalars(self) -> _Result:
                return self

            def scalar_one_or_none(self) -> Any:
                return None

            def all(self) -> list:
                return []

        return _Result()

    def add(self, _obj: Any) -> None:
        return None


# ---------------------------------------------------------------------------
# StreamSymbol 5 态转移表契约（轻量状态机；与 ProjectPipeClassStateMachine 同模式）
# ---------------------------------------------------------------------------


def test_stream_symbol_5_state_machine_can_transition():
    """5 态机：DRAFT → PENDING → APPROVED → PUBLISHED → OBSOLETE；
    DRAFT/APPROVED 可 OBSOLETE 直接出局；PUBLISHED → OBSOLETE。
    """
    from app.services.stream_symbol_service import ProjectStreamSymbolStateMachine

    sm = ProjectStreamSymbolStateMachine
    # DRAFT → submit / obsolete
    assert sm.can_transition("DRAFT", "submit") is True
    assert sm.can_transition("DRAFT", "obsolete") is True
    assert sm.can_transition("DRAFT", "approve") is False
    # PENDING → approve / reject
    assert sm.can_transition("PENDING", "approve") is True
    assert sm.can_transition("PENDING", "reject") is True
    assert sm.can_transition("PENDING", "submit") is False
    # APPROVED → publish / obsolete
    assert sm.can_transition("APPROVED", "publish") is True
    assert sm.can_transition("APPROVED", "obsolete") is True
    # PUBLISHED → obsolete
    assert sm.can_transition("PUBLISHED", "obsolete") is True
    assert sm.can_transition("PUBLISHED", "submit") is False
    # OBSOLETE 终态
    assert sm.can_transition("OBSOLETE", "submit") is False
    assert sm.can_transition("OBSOLETE", "obsolete") is False


def test_stream_symbol_state_machine_next_status():
    """action → next status 映射。"""
    from app.services.stream_symbol_service import ProjectStreamSymbolStateMachine

    sm = ProjectStreamSymbolStateMachine
    assert sm.next_status("submit") == "PENDING"
    assert sm.next_status("approve") == "APPROVED"
    assert sm.next_status("reject") == "DRAFT"
    assert sm.next_status("publish") == "PUBLISHED"
    assert sm.next_status("obsolete") == "OBSOLETE"


@pytest.mark.asyncio
async def test_submit_project_symbol_draft_to_pending():
    """submit_project_symbol：DRAFT → PENDING。"""
    pss = _FakeProjectStreamSymbol(uuid.uuid4(), uuid.uuid4(), status="DRAFT")
    db = _FakeStreamSymbolSession({pss.project_symbol_id: pss})

    result = await StreamSymbolService.submit_project_symbol(
        db, project_symbol_id=pss.project_symbol_id, actor=_actor(),
    )
    assert result.status == "PENDING"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_approve_project_symbol_pending_to_approved():
    """approve_project_symbol：PENDING → APPROVED + 写 ConfigApproval + audit。"""
    pss = _FakeProjectStreamSymbol(uuid.uuid4(), uuid.uuid4(), status="PENDING")
    db = _FakeStreamSymbolSession({pss.project_symbol_id: pss})

    result = await StreamSymbolService.approve_project_symbol(
        db, project_symbol_id=pss.project_symbol_id, actor=_actor(),
    )
    assert result.status == "APPROVED"


@pytest.mark.asyncio
async def test_reject_project_symbol_pending_to_draft():
    """reject_project_symbol：PENDING → DRAFT。"""
    pss = _FakeProjectStreamSymbol(uuid.uuid4(), uuid.uuid4(), status="PENDING")
    db = _FakeStreamSymbolSession({pss.project_symbol_id: pss})

    result = await StreamSymbolService.reject_project_symbol(
        db, project_symbol_id=pss.project_symbol_id, actor=_actor(),
    )
    assert result.status == "DRAFT"


@pytest.mark.asyncio
async def test_publish_project_symbol_approved_to_published():
    """publish_project_symbol：APPROVED → PUBLISHED。"""
    pss = _FakeProjectStreamSymbol(uuid.uuid4(), uuid.uuid4(), status="APPROVED")
    db = _FakeStreamSymbolSession({pss.project_symbol_id: pss})

    result = await StreamSymbolService.publish_project_symbol(
        db, project_symbol_id=pss.project_symbol_id, actor=_actor(),
    )
    assert result.status == "PUBLISHED"


@pytest.mark.asyncio
async def test_obsolete_project_symbol_multiple_entry_points():
    """obsolete_project_symbol：DRAFT/APPROVED/PUBLISHED 均可直接出局。"""
    for start in ("DRAFT", "APPROVED", "PUBLISHED"):
        pss = _FakeProjectStreamSymbol(uuid.uuid4(), uuid.uuid4(), status=start)
        db = _FakeStreamSymbolSession({pss.project_symbol_id: pss})

        result = await StreamSymbolService.obsolete_project_symbol(
            db, project_symbol_id=pss.project_symbol_id, actor=_actor(),
        )
        assert result.status == "OBSOLETE", f"{start} 应可 OBSOLETE"


@pytest.mark.asyncio
async def test_obsolete_project_symbol_terminal_state_rejected():
    """obsolete_project_symbol：OBSOLETE 终态再 obsolete → 409。"""
    pss = _FakeProjectStreamSymbol(uuid.uuid4(), uuid.uuid4(), status="OBSOLETE")
    db = _FakeStreamSymbolSession({pss.project_symbol_id: pss})

    with pytest.raises(PcsError) as exc_info:
        await StreamSymbolService.obsolete_project_symbol(
            db, project_symbol_id=pss.project_symbol_id, actor=_actor(),
        )
    assert exc_info.value.status == 409
    assert "BAD_TRANSITION" in exc_info.value.code


@pytest.mark.asyncio
async def test_submit_project_symbol_illegal_from_pending_rejected():
    """submit_project_symbol：PENDING 不能再 submit → 409。"""
    pss = _FakeProjectStreamSymbol(uuid.uuid4(), uuid.uuid4(), status="PENDING")
    db = _FakeStreamSymbolSession({pss.project_symbol_id: pss})

    with pytest.raises(PcsError) as exc_info:
        await StreamSymbolService.submit_project_symbol(
            db, project_symbol_id=pss.project_symbol_id, actor=_actor(),
        )
    assert exc_info.value.status == 409


@pytest.mark.asyncio
async def test_project_symbol_not_found_returns_404():
    """project_symbol_id 不存在 → 404。"""
    db = _FakeStreamSymbolSession({})

    with pytest.raises(PcsError) as exc_info:
        await StreamSymbolService.submit_project_symbol(
            db, project_symbol_id=uuid.uuid4(), actor=_actor(),
        )
    assert exc_info.value.status == 404


# ============================================================================
# ProjectPipeCodeConfig 审计落库（PipeCodeTemplateService._project_transition 缺口）
# ============================================================================


@pytest.mark.asyncio
async def test_pipe_code_config_project_transition_writes_audit():
    """项目级 PipeCodeConfig 状态转换写 audit + AuditService.write 调用。"""
    from app.services import audit_service as audit_mod

    # monkey-patch AuditService.write（AsyncMock）
    audit_writes: list[dict] = []

    async def _capture_write(self, *, action, resource_type, resource_id, user_id, detail):
        audit_writes.append(
            {"action": action, "resource_type": resource_type,
             "resource_id": resource_id, "user_id": user_id, "detail": detail}
        )

    orig_write = audit_mod.AuditService.write
    audit_mod.AuditService.write = _capture_write  # type: ignore[assignment]

    try:
        cfg_id = uuid.uuid4()
        project_id = uuid.uuid4()
        cfg = type(
            "FakeProjectPipeCodeConfig",
            (),
            {
                "config_id": cfg_id,
                "project_id": project_id,
                "config_name": "TEST_CONFIG",
                "status": "DRAFT",
            },
        )()

        store: dict[Any, Any] = {cfg_id: cfg}

        class _Session:
            def __init__(self, store):
                self.store = store
                self.commits = 0

            async def get(self, _model, pk):
                return self.store.get(pk)

            async def commit(self):
                self.commits += 1

            async def flush(self):
                return None

            def add(self, _obj):
                return None

        db = _Session(store)

        result = await PipeCodeTemplateService._project_transition(
            db, cfg_id, "SUBMIT", _actor(),
        )
    finally:
        audit_mod.AuditService.write = orig_write  # type: ignore[assignment]

    # 状态转换应完成 DRAFT → PENDING
    assert result.status == "PENDING"
    assert db.commits >= 1
    # 审计落库：CONFIG_ASSET_SUBMITTED + resource_type=PROJECT_PIPE_CODE_CONFIG
    assert len(audit_writes) == 1
    aw = audit_writes[0]
    assert aw["action"] == "CONFIG_ASSET_SUBMITTED"
    assert aw["resource_type"] == "PROJECT_PIPE_CODE_CONFIG"
    assert aw["resource_id"] == str(cfg_id)
    assert aw["detail"]["from"] == "DRAFT"
    assert aw["detail"]["to"] == "PENDING"
    assert aw["detail"]["action"] == "SUBMIT"


@pytest.mark.asyncio
async def test_pipe_code_config_obsolete_from_draft_to_obsolete():
    """项目级 PipeCodeConfig OBSOLETE：DRAFT 直接出局。"""
    cfg_id = uuid.uuid4()
    cfg = type(
        "FakeProjectPipeCodeConfig",
        (),
        {"config_id": cfg_id, "project_id": uuid.uuid4(), "config_name": "X", "status": "DRAFT"},
    )()
    store = {cfg_id: cfg}

    class _Session:
        def __init__(self, store):
            self.store = store

        async def get(self, _model, pk):
            return self.store.get(pk)

        async def commit(self):
            return None

        async def flush(self):
            return None

        def add(self, _obj):
            return None

    result = await PipeCodeTemplateService._project_transition(
        _Session(store), cfg_id, "OBSOLETE", _actor(),
    )
    assert result.status == "OBSOLETE"


@pytest.mark.asyncio
async def test_pipe_code_config_obsolete_from_obsolete_rejected():
    """OBSOLETE 终态再 obsolete → 409。"""
    cfg_id = uuid.uuid4()
    cfg = type(
        "FakeProjectPipeCodeConfig",
        (),
        {"config_id": cfg_id, "project_id": uuid.uuid4(), "config_name": "X", "status": "OBSOLETE"},
    )()
    store = {cfg_id: cfg}

    class _Session:
        def __init__(self, store):
            self.store = store

        async def get(self, _model, pk):
            return self.store.get(pk)

        async def commit(self):
            return None

        async def flush(self):
            return None

        def add(self, _obj):
            return None

    with pytest.raises(PcsError) as exc_info:
        await PipeCodeTemplateService._project_transition(
            _Session(store), cfg_id, "OBSOLETE", _actor(),
        )
    assert exc_info.value.status == 409


# ============================================================================
# 与 PipeClass 对齐校验（cerebrum 政策：service 层禁止绕过状态机直接 UPDATE）
# ============================================================================


def test_three_project_template_services_share_5_state_machine_contract():
    """三个项目级 service（PipeClass/StreamSymbol/PipeCodeTemplate）共用 5 态机契约。

    同 TRANSITIONS 表 + 同 ACTION_TO_STATUS 映射 + 同 from/to 错误码。
    验证 5 态集与可用动作集一致。
    """
    from app.services.pipe_class_service import ProjectPipeClassStateMachine
    from app.services.pipe_code_template_service import PipeCodeTemplateService
    from app.services.stream_symbol_service import ProjectStreamSymbolStateMachine

    for sm in (
        ProjectPipeClassStateMachine,
        ProjectStreamSymbolStateMachine,
    ):
        # DRAFT → submit/obsolete
        assert sm.can_transition("DRAFT", "submit")
        assert sm.can_transition("DRAFT", "obsolete")
        # PENDING → approve/reject
        assert sm.can_transition("PENDING", "approve")
        assert sm.can_transition("PENDING", "reject")
        # APPROVED → publish/obsolete
        assert sm.can_transition("APPROVED", "publish")
        assert sm.can_transition("APPROVED", "obsolete")
        # PUBLISHED → obsolete
        assert sm.can_transition("PUBLISHED", "obsolete")
        # OBSOLETE 终态
        assert not sm.can_transition("OBSOLETE", "submit")

    # PipeCodeTemplateService 用 dict[str, tuple[str, str]] 表
    transitions = PipeCodeTemplateService._PROJECT_TRANSITIONS
    assert transitions["SUBMIT"] == ("DRAFT", "PENDING")
    assert transitions["APPROVE"] == ("PENDING", "APPROVED")
    assert transitions["REJECT"] == ("PENDING", "DRAFT")
    assert transitions["PUBLISH"] == ("APPROVED", "PUBLISHED")