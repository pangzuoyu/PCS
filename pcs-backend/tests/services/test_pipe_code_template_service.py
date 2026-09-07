"""PipeCodeTemplateService 集成测试（FMT-2）。

覆盖：公司级 CRUD + 5 态 + 项目 fork + 项目 5 态 + 项目 config_name 唯一。
"""
import uuid
from collections import namedtuple

import pytest
import pytest_asyncio

from app.models.project import Project, Workspace
from app.services.exceptions import PcsError
from app.services.pipe_code_template_service import PipeCodeTemplateService

_VALID_FMT = {
    "separator": "-",
    "segments": [
        {"key": "sym", "type": "stream_symbol", "length": 10, "position": 1},
        {"key": "seq", "type": "auto_increment", "length": 3, "position": 2},
    ],
}


def _payload(name="T-1", **kw):
    base = dict(
        template_name=name,
        description="desc",
        format_definition_json=kw.pop("fmt", _VALID_FMT),
        version="1",
    )
    base.update(kw)
    return base


@pytest_asyncio.fixture
async def make_project(db):
    async def _make():
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="测试项目",
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
    return _make


# ---------- 公司级 ----------


async def test_create_company_happy_path(db, actor):
    t = await PipeCodeTemplateService.create_company(
        db, data=_payload(), actor=actor,
    )
    assert t.template_name == "T-1"
    assert t.status == "DRAFT"
    assert t.asset_id is not None


async def test_create_company_duplicate_raises_409(db, actor):
    await PipeCodeTemplateService.create_company(db, data=_payload(), actor=actor)
    with pytest.raises(PcsError) as e:
        await PipeCodeTemplateService.create_company(
            db, data=_payload(), actor=actor,
        )
    assert e.value.status == 409
    assert e.value.code == "PIPE_CODE_TEMPLATE_DUP"


async def test_get_missing_raises_404(db):
    with pytest.raises(PcsError) as e:
        await PipeCodeTemplateService.get(db, uuid.uuid4())
    assert e.value.status == 404


async def test_list_company_orders_by_name(db, actor):
    await PipeCodeTemplateService.create_company(
        db, data=_payload(name="B-1"), actor=actor,
    )
    await PipeCodeTemplateService.create_company(
        db, data=_payload(name="A-1"), actor=actor,
    )
    rows = await PipeCodeTemplateService.list_company(db)
    assert [r.template_name for r in rows] == ["A-1", "B-1"]


async def test_update_company_updates_fields(db, actor):
    t = await PipeCodeTemplateService.create_company(db, data=_payload(), actor=actor)
    upd = await PipeCodeTemplateService.update_company(
        db, t.template_id,
        data={"description": "新描述", "version": "2"},
        actor=actor,
    )
    assert upd.description == "新描述"
    assert upd.version == "2"


async def test_state_machine_flow(db, actor):
    t = await PipeCodeTemplateService.create_company(db, data=_payload(), actor=actor)
    await PipeCodeTemplateService.submit(db, t.template_id, actor=actor)
    await PipeCodeTemplateService.approve(db, t.template_id, actor=actor)
    pub = await PipeCodeTemplateService.publish(db, t.template_id, actor=actor)
    assert pub.status == "PUBLISHED"


async def test_delete_company_blocked_when_forked(db, actor, make_project):
    t = await PipeCodeTemplateService.create_company(db, data=_payload(), actor=actor)
    await PipeCodeTemplateService.submit(db, t.template_id, actor=actor)
    await PipeCodeTemplateService.approve(db, t.template_id, actor=actor)
    await PipeCodeTemplateService.publish(db, t.template_id, actor=actor)
    proj = await make_project()
    await PipeCodeTemplateService.fork_to_project(
        db, project_id=proj.project_id, template_id=t.template_id,
        config_name="CFG-1", actor=actor,
    )
    with pytest.raises(PcsError) as e:
        await PipeCodeTemplateService.delete_company(db, t.template_id, actor=actor)
    assert e.value.code == "PIPE_CODE_TEMPLATE_IN_USE"


# ---------- 项目级 ----------


async def test_fork_to_project_creates_draft(db, actor, make_project):
    t = await PipeCodeTemplateService.create_company(db, data=_payload(), actor=actor)
    await PipeCodeTemplateService.submit(db, t.template_id, actor=actor)
    await PipeCodeTemplateService.approve(db, t.template_id, actor=actor)
    await PipeCodeTemplateService.publish(db, t.template_id, actor=actor)
    proj = await make_project()
    cfg = await PipeCodeTemplateService.fork_to_project(
        db, project_id=proj.project_id, template_id=t.template_id,
        config_name="CFG-FORK", actor=actor,
    )
    assert cfg.status == "DRAFT"
    assert cfg.source_template_id == t.template_id
    assert cfg.snapshot_json == t.format_definition_json


async def test_fork_duplicate_config_name_raises_409(db, actor, make_project):
    t = await PipeCodeTemplateService.create_company(db, data=_payload(), actor=actor)
    proj = await make_project()
    await PipeCodeTemplateService.fork_to_project(
        db, project_id=proj.project_id, template_id=t.template_id,
        config_name="DUP", actor=actor,
    )
    with pytest.raises(PcsError) as e:
        await PipeCodeTemplateService.fork_to_project(
            db, project_id=proj.project_id, template_id=t.template_id,
            config_name="DUP", actor=actor,
        )
    assert e.value.code == "PROJECT_PIPE_CODE_CONFIG_DUP"


async def test_create_project_config_happy(db, actor, make_project):
    proj = await make_project()
    cfg = await PipeCodeTemplateService.create_project_config(
        db, project_id=proj.project_id,
        config_name="CFG-NEW",
        format_definition_json=_VALID_FMT, actor=actor,
    )
    assert cfg.source_template_id is None
    assert cfg.status == "DRAFT"


async def test_project_config_5_state_flow(db, actor, make_project):
    proj = await make_project()
    cfg = await PipeCodeTemplateService.create_project_config(
        db, project_id=proj.project_id,
        config_name="CFG-FLOW",
        format_definition_json=_VALID_FMT, actor=actor,
    )
    s1 = await PipeCodeTemplateService.submit_project(
        db, config_id=cfg.config_id, actor=actor,
    )
    assert s1.status == "PENDING"
    s2 = await PipeCodeTemplateService.approve_project(
        db, config_id=cfg.config_id, actor=actor,
    )
    assert s2.status == "APPROVED"
    s3 = await PipeCodeTemplateService.publish_project(
        db, config_id=cfg.config_id, actor=actor,
    )
    assert s3.status == "PUBLISHED"


async def test_project_config_reject_returns_to_draft(db, actor, make_project):
    proj = await make_project()
    cfg = await PipeCodeTemplateService.create_project_config(
        db, project_id=proj.project_id, config_name="C-1",
        format_definition_json=_VALID_FMT, actor=actor,
    )
    await PipeCodeTemplateService.submit_project(db, config_id=cfg.config_id, actor=actor)
    rej = await PipeCodeTemplateService.reject_project(
        db, config_id=cfg.config_id, actor=actor,
    )
    assert rej.status == "DRAFT"


async def test_project_config_bad_transition_raises_409(db, actor, make_project):
    proj = await make_project()
    cfg = await PipeCodeTemplateService.create_project_config(
        db, project_id=proj.project_id, config_name="C-2",
        format_definition_json=_VALID_FMT, actor=actor,
    )
    # 直接 publish（DRAFT→PUBLISHED）应失败
    with pytest.raises(PcsError) as e:
        await PipeCodeTemplateService.publish_project(
            db, config_id=cfg.config_id, actor=actor,
        )
    assert e.value.code == "PROJECT_PIPE_CODE_CONFIG_BAD_TRANSITION"


async def test_update_project_config_locked_after_publish(db, actor, make_project):
    proj = await make_project()
    cfg = await PipeCodeTemplateService.create_project_config(
        db, project_id=proj.project_id, config_name="C-3",
        format_definition_json=_VALID_FMT, actor=actor,
    )
    await PipeCodeTemplateService.submit_project(db, config_id=cfg.config_id, actor=actor)
    await PipeCodeTemplateService.approve_project(db, config_id=cfg.config_id, actor=actor)
    await PipeCodeTemplateService.publish_project(db, config_id=cfg.config_id, actor=actor)
    with pytest.raises(PcsError) as e:
        await PipeCodeTemplateService.update_project_config(
            db, config_id=cfg.config_id,
            format_definition_json=_VALID_FMT, actor=actor,
        )
    assert e.value.code == "PROJECT_PIPE_CODE_CONFIG_LOCKED"


# ---------------------------------------------------------------------------
# FMT-OPEN-02: 模板 PUBLISH 触发 CIAEngine 传播，下游 fork 与新内容发散者 → OBSOLETE
# ---------------------------------------------------------------------------

_AuthUser = namedtuple("_AuthUser", ["user_id"])


@pytest.fixture
def company_actor():
    """公司级动作需要 .user_id 属性（ConfigStateMachine 直接读 actor.user_id）。"""
    return _AuthUser(user_id=uuid.uuid4())


_FMT_V1 = {
    "separator": "-",
    "segments": [
        {"key": "sym", "type": "stream_symbol", "length": 10, "position": 1},
        {"key": "seq", "type": "auto_increment", "length": 3, "position": 2},
    ],
}

_FMT_V2 = {
    "separator": "_",  # 唯一字段改动即可触发 hash 不一致
    "segments": [
        {"key": "sym", "type": "stream_symbol", "length": 10, "position": 1},
        {"key": "seq", "type": "auto_increment", "length": 3, "position": 2},
    ],
}


async def test_template_publish_propagates_stale_to_downstream_forks(
    db, company_actor, make_project,
):
    """模板 v2 发布后，引用 v1 已发布的 fork → OBSOLETE（snapshot 与新内容发散）。"""
    proj = await make_project()

    # 1. 公司模板 v1：DRAFT → PENDING → APPROVED（停在 APPROVED，fork 走项目级独立机）
    tpl = await PipeCodeTemplateService.create_company(
        db, data=_payload(name="PROP-TPL", fmt=_FMT_V1), actor=company_actor,
    )
    await PipeCodeTemplateService.submit(db, tpl.template_id, actor=company_actor)
    await PipeCodeTemplateService.approve(db, tpl.template_id, actor=company_actor)
    assert tpl.status == "APPROVED"

    # 2. fork 到项目 → snapshot = v1 格式；推到 PUBLISHED
    cfg = await PipeCodeTemplateService.fork_to_project(
        db, project_id=proj.project_id, template_id=tpl.template_id,
        config_name="default", actor=company_actor,
    )
    await PipeCodeTemplateService.submit_project(
        db, config_id=cfg.config_id, actor=company_actor,
    )
    await PipeCodeTemplateService.approve_project(
        db, config_id=cfg.config_id, actor=company_actor,
    )
    await PipeCodeTemplateService.publish_project(
        db, config_id=cfg.config_id, actor=company_actor,
    )
    assert cfg.status == "PUBLISHED"

    # 3. 公司模板改格式（状态仍 APPROVED，仅内容/版本字段变）
    await PipeCodeTemplateService.update_company(
        db, tpl.template_id,
        data={"format_definition_json": _FMT_V2, "version": "2"},
        actor=company_actor,
    )

    # 4. 公司模板 v2 发布 → CIAEngine.propagate_from_source 触发
    await PipeCodeTemplateService.publish(
        db, tpl.template_id, actor=company_actor,
    )

    # 5. 验证 fork 已变 OBSOLETE（snapshot 与新模板格式发散）
    after = await PipeCodeTemplateService.get_project_config(
        db, config_id=cfg.config_id,
    )
    assert after.status == "OBSOLETE"


async def test_template_publish_no_change_keeps_forks_published(
    db, company_actor, make_project,
):
    """模板重新发布且内容未变 → fork 维持 PUBLISHED（hash 一致即不动作）。"""
    proj = await make_project()

    tpl = await PipeCodeTemplateService.create_company(
        db, data=_payload(name="NOOP-TPL", fmt=_FMT_V1), actor=company_actor,
    )
    await PipeCodeTemplateService.submit(db, tpl.template_id, actor=company_actor)
    await PipeCodeTemplateService.approve(db, tpl.template_id, actor=company_actor)
    cfg = await PipeCodeTemplateService.fork_to_project(
        db, project_id=proj.project_id, template_id=tpl.template_id,
        config_name="default", actor=company_actor,
    )
    await PipeCodeTemplateService.submit_project(
        db, config_id=cfg.config_id, actor=company_actor,
    )
    await PipeCodeTemplateService.approve_project(
        db, config_id=cfg.config_id, actor=company_actor,
    )
    await PipeCodeTemplateService.publish_project(
        db, config_id=cfg.config_id, actor=company_actor,
    )

    # 内容未变；触发 publish：APPROVED → PUBLISHED
    await PipeCodeTemplateService.publish(
        db, tpl.template_id, actor=company_actor,
    )

    after = await PipeCodeTemplateService.get_project_config(
        db, config_id=cfg.config_id,
    )
    assert after.status == "PUBLISHED"
