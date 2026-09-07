"""SUP-002 PC-4: 项目级 fork + snapshot 绑定 + 有效值解析 + 5 态轻量状态机（V1.4 §2.4）。

覆盖：
1. test_fork_creates_project_class_with_snapshot       fork 创建 ProjectPipeClass + snapshot
2. test_fork_then_override_then_effective              fork → 覆写 → effective 合并
3. test_fork_duplicate_same_source_returns_existing    同 source 二次 fork 幂等返回现有行
4. test_new_project_class_without_source               项目全新创建（source_class_id=NULL）
5. test_get_effective_recursive_merge                  override 中嵌套 dict 与 snapshot 深合并
6. test_project_class_state_machine_submit_approve_publish  DRAFT→PENDING→APPROVED→PUBLISHED
7. test_project_class_state_machine_invalid_transition       PUBLISHED→submit 409
8. test_project_approval_writes_config_approvals             approve 写 config_approvals 行

契约要点（V1.4 §2.4）：
- snapshot_json 包含公司级 13 字段（fork 时锁定）
- override_json 仅存被覆写字段（顶层标量/列表覆写，dict 字段深合并）
- 5 态：DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE
- DRAFT/PENDING 可改 override_json；APPROVED/PUBLISHED/OBSOLETE 不可改
- approve/reject 写 config_approvals.project_class_id（PC-1 列）
"""
from __future__ import annotations

import uuid
from collections import namedtuple

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.config_domain import ConfigApproval, PipeClass, ProjectPipeClass
from app.models.project import Project, Workspace
from app.schemas.pipe_class import PipeClassCreate
from app.services.exceptions import PcsError
from app.services.pipe_class_service import (
    PipeClassService,
    ProjectPipeClassStateMachine,
    _build_snapshot,
    _deep_merge,
)


# ---------------------------------------------------------------------------
# Fixtures（本地：与 test_pipe_class_service.make_project 同模式）
# ---------------------------------------------------------------------------


def _payload(class_id="A1", **kw):
    base = dict(
        class_id=class_id, class_name="管道等级 A1", material_standard="GB/T 8163",
        base_material="20#",
        corrosion_allowance=1.5, design_pressure=2.5, design_temperature=200.0,
        dn_series_json={"min": 15, "max": 350},
        sch_series_json={"15": "40", "25": "40", "50": "40", "100": "40", "350": "STD"},
        flange_class="PN25", source="COMPANY_STD", version="PC-V1.0",
    )
    base.update(kw)
    return PipeClassCreate(**base)


@pytest_asyncio.fixture
async def make_project(db):
    """最小 Project：先建 Workspace 再建 Project（避免 use_alter 循环 FK 报错）。"""

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


@pytest_asyncio.fixture
async def make_company_class(db):
    """建一个公司级 PipeClass（DRAFT），含 base_material=20#。

    注：PipeClassBase schema 当前不含 base_material（P2 Sprint 1 旧契约），
    所以 create() 不会自动写入；fixture 内 flush 后单独补 base_material 字段，
    保证 snapshot_json["base_material"] 真实反映公司级值。
    """

    async def _make(class_id="A1"):
        pc = await PipeClassService.create(db, payload=_payload(class_id=class_id))
        pc.base_material = "20#"
        await db.flush()
        return pc

    return _make


_AuthUser = namedtuple("_AuthUser", ["user_id"])


@pytest.fixture
def actor():
    """最小 actor：service 层只用 user_id。"""
    return _AuthUser(user_id=uuid.uuid4())


# ---------------------------------------------------------------------------
# 单元（helper / state machine）
# ---------------------------------------------------------------------------


def test_deep_merge_recursive_for_nested_dicts():
    base = {"a": 1, "b": {"x": 10, "y": 20}, "c": [1, 2, 3]}
    override = {"b": {"y": 99, "z": 30}, "c": "replaced"}
    merged = _deep_merge(base, override)
    assert merged == {"a": 1, "b": {"x": 10, "y": 99, "z": 30}, "c": "replaced"}


def test_build_snapshot_contains_13_fields():
    pc = PipeClass(
        class_id="X1", class_name="X", material_standard="GB/T 8163",
        base_material="20#", corrosion_allowance=1.5,
        design_pressure=2.5, design_temperature=200.0,
        dn_series_json={"min": 15, "max": 350},
        sch_series_json={"15": "40"},
        flange_class="PN25", source="COMPANY_STD", version="v1", status="PUBLISHED",
    )
    snap = _build_snapshot(pc)
    expected_keys = {
        "class_name", "material_standard", "base_material",
        "corrosion_allowance", "design_pressure", "design_temperature",
        "dn_series_json", "sch_series_json", "flange_class",
        "fitting_type", "allowable_stress_json", "branch_table_json", "version",
    }
    assert set(snap.keys()) == expected_keys
    assert snap["class_name"] == "X"
    assert snap["base_material"] == "20#"
    assert snap["version"] == "v1"


def test_state_machine_can_transition_table():
    sm = ProjectPipeClassStateMachine
    # 合法路径
    assert sm.can_transition("DRAFT", "submit")
    assert sm.can_transition("DRAFT", "obsolete")
    assert sm.can_transition("PENDING", "approve")
    assert sm.can_transition("PENDING", "reject")
    assert sm.can_transition("APPROVED", "publish")
    assert sm.can_transition("APPROVED", "obsolete")
    assert sm.can_transition("PUBLISHED", "obsolete")
    # 非法
    assert not sm.can_transition("PUBLISHED", "submit")
    assert not sm.can_transition("PUBLISHED", "approve")
    assert not sm.can_transition("OBSOLETE", "obsolete")
    assert not sm.can_transition("OBSOLETE", "submit")


def test_state_machine_action_to_status():
    sm = ProjectPipeClassStateMachine
    assert sm.next_status("submit") == "PENDING"
    assert sm.next_status("approve") == "APPROVED"
    assert sm.next_status("reject") == "DRAFT"
    assert sm.next_status("publish") == "PUBLISHED"
    assert sm.next_status("obsolete") == "OBSOLETE"


# ---------------------------------------------------------------------------
# 1. fork：建快照
# ---------------------------------------------------------------------------


async def test_fork_creates_project_class_with_snapshot(
    db, make_project, make_company_class, actor
):
    proj = await make_project()
    company_pc = await make_company_class("A1")
    ppc = await PipeClassService.fork_to_project(
        db, project_id=proj.project_id, class_id=company_pc.class_id, actor=actor,
    )
    assert ppc.project_class_id is not None
    assert ppc.source_class_id == company_pc.class_id
    assert ppc.class_name == company_pc.class_name
    assert ppc.snapshot_json is not None
    assert ppc.snapshot_json["base_material"] == "20#"
    assert ppc.snapshot_json["design_pressure"] == 2.5
    assert ppc.snapshot_json["flange_class"] == "PN25"
    assert ppc.override_json == {}
    assert ppc.status == "DRAFT"


# ---------------------------------------------------------------------------
# 2. fork + override + effective
# ---------------------------------------------------------------------------


async def test_fork_then_override_then_effective(
    db, make_project, make_company_class, actor
):
    proj = await make_project()
    company_pc = await make_company_class("A1")
    ppc = await PipeClassService.fork_to_project(
        db, project_id=proj.project_id, class_id=company_pc.class_id, actor=actor,
    )
    await PipeClassService.update_project_override(
        db,
        project_class_id=ppc.project_class_id,
        override={"corrosion_allowance": 3.2, "design_pressure": 5.0},
        actor=actor,
    )
    effective = await PipeClassService.get_effective(
        db, project_id=proj.project_id, class_name=ppc.class_name,
    )
    assert effective["corrosion_allowance"] == 3.2  # 覆写值
    assert effective["design_pressure"] == 5.0      # 覆写值
    # 快照值未被覆写
    assert effective["base_material"] == "20#"
    assert effective["flange_class"] == "PN25"


# ---------------------------------------------------------------------------
# 3. fork 幂等：同 source 二次 fork 返回现有行
# ---------------------------------------------------------------------------


async def test_fork_duplicate_same_source_returns_existing(
    db, make_project, make_company_class, actor
):
    proj = await make_project()
    company_pc = await make_company_class("A1")
    ppc1 = await PipeClassService.fork_to_project(
        db, project_id=proj.project_id, class_id=company_pc.class_id, actor=actor,
    )
    ppc2 = await PipeClassService.fork_to_project(
        db, project_id=proj.project_id, class_id=company_pc.class_id, actor=actor,
    )
    assert ppc1.project_class_id == ppc2.project_class_id  # 同一行


# ---------------------------------------------------------------------------
# 4. 项目全新创建（source_class_id=NULL）
# ---------------------------------------------------------------------------


async def test_new_project_class_without_source(
    db, make_project, actor
):
    proj = await make_project()
    data = {
        "class_name": "PROJECT_SPECIAL_A1",
        "material_standard": "GB/T 14976",
        "base_material": "316L",
        "corrosion_allowance": 2.0,
        "design_pressure": 4.0,
        "design_temperature": 250.0,
        "dn_series_json": {"min": 15, "max": 200},
        "sch_series_json": {"15": "40S"},
        "flange_class": "PN40",
        "fitting_type": "BUTT_WELD",
        "allowable_stress_json": {"table": "TABLE_U1"},
        "branch_table_json": None,
        "version": "PC-V1.0",
    }
    ppc = await PipeClassService.create_project_class(
        db,
        project_id=proj.project_id,
        class_name="PROJECT_SPECIAL_A1",
        data=data,
        actor=actor,
    )
    assert ppc.source_class_id is None
    assert ppc.snapshot_json is None
    assert ppc.override_json == data
    assert ppc.status == "DRAFT"

    # effective 应返回 override_json
    effective = await PipeClassService.get_effective(
        db, project_id=proj.project_id, class_name="PROJECT_SPECIAL_A1",
    )
    assert effective == data


# ---------------------------------------------------------------------------
# 5. effective 嵌套 dict 字段深合并（PC-4 必跑）
# ---------------------------------------------------------------------------


async def test_get_effective_recursive_merge(
    db, make_project, make_company_class, actor
):
    proj = await make_project()
    company_pc = await make_company_class("A1")
    ppc = await PipeClassService.fork_to_project(
        db, project_id=proj.project_id, class_id=company_pc.class_id, actor=actor,
    )
    # override 仅覆写 sch_series_json 中的 DN200
    await PipeClassService.update_project_override(
        db,
        project_class_id=ppc.project_class_id,
        override={"sch_series_json": {"DN200": ["80"]}},
        actor=actor,
    )
    effective = await PipeClassService.get_effective(
        db, project_id=proj.project_id, class_name=ppc.class_name,
    )
    # DN15/DN50 等其他 DN 应保留（来自 snapshot）
    assert effective["sch_series_json"]["DN200"] == ["80"]
    # snapshot 中其他 DN 仍存在（merge）
    assert effective["sch_series_json"].get("15") == "40"
    assert effective["sch_series_json"].get("50") == "40"


# ---------------------------------------------------------------------------
# 6. 状态机：完整 DRAFT→PENDING→APPROVED→PUBLISHED（PC-4 必跑）
# ---------------------------------------------------------------------------


async def test_project_class_state_machine_submit_approve_publish(
    db, make_project, make_company_class, actor
):
    proj = await make_project()
    company_pc = await make_company_class("A1")
    ppc = await PipeClassService.fork_to_project(
        db, project_id=proj.project_id, class_id=company_pc.class_id, actor=actor,
    )
    assert ppc.status == "DRAFT"

    ppc = await PipeClassService.submit_project_class(
        db, project_class_id=ppc.project_class_id, actor=actor,
    )
    assert ppc.status == "PENDING"

    ppc = await PipeClassService.approve_project_class(
        db, project_class_id=ppc.project_class_id, actor=actor, role="REVIEWER",
    )
    assert ppc.status == "APPROVED"

    ppc = await PipeClassService.publish_project_class(
        db, project_class_id=ppc.project_class_id, actor=actor,
    )
    assert ppc.status == "PUBLISHED"


# ---------------------------------------------------------------------------
# 7. 状态机：非法转移 409（PC-4 必跑）
# ---------------------------------------------------------------------------


async def test_project_class_state_machine_invalid_transition(
    db, make_project, make_company_class, actor
):
    proj = await make_project()
    company_pc = await make_company_class("A1")
    ppc = await PipeClassService.fork_to_project(
        db, project_id=proj.project_id, class_id=company_pc.class_id, actor=actor,
    )
    # 推到 PUBLISHED
    await PipeClassService.submit_project_class(
        db, project_class_id=ppc.project_class_id, actor=actor,
    )
    await PipeClassService.approve_project_class(
        db, project_class_id=ppc.project_class_id, actor=actor, role="REVIEWER",
    )
    await PipeClassService.publish_project_class(
        db, project_class_id=ppc.project_class_id, actor=actor,
    )
    # PUBLISHED 再 submit → 409
    with pytest.raises(PcsError) as e:
        await PipeClassService.submit_project_class(
            db, project_class_id=ppc.project_class_id, actor=actor,
        )
    assert e.value.status == 409
    assert e.value.code == "PROJECT_PIPE_CLASS_BAD_TRANSITION"


# ---------------------------------------------------------------------------
# 8. approve 写 config_approvals（PC-4 必跑）
# ---------------------------------------------------------------------------


async def test_project_approval_writes_config_approvals(
    db, make_project, make_company_class, actor
):
    proj = await make_project()
    company_pc = await make_company_class("A1")
    ppc = await PipeClassService.fork_to_project(
        db, project_id=proj.project_id, class_id=company_pc.class_id, actor=actor,
    )
    await PipeClassService.submit_project_class(
        db, project_class_id=ppc.project_class_id, actor=actor,
    )
    await PipeClassService.approve_project_class(
        db, project_class_id=ppc.project_class_id, actor=actor, role="REVIEWER",
    )
    # 查 config_approvals
    approvals = (await db.execute(
        select(ConfigApproval).where(
            ConfigApproval.project_class_id == ppc.project_class_id
        )
    )).scalars().all()
    assert len(approvals) == 1
    a = approvals[0]
    assert a.version_id is None
    assert a.project_class_id == ppc.project_class_id
    assert a.approver_role == "REVIEWER"
    assert a.decision == "APPROVED"
    assert a.approver_id == actor.user_id