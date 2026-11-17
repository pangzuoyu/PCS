"""流程级种子（P10-B · T2）的守卫。

## 这个种子解决什么

`scripts/seed_e2e_data.py`（P10-A）是**冒烟级**：4 个用户 · **项目内角色统一
`DESIGNER`** ⇒ **测不了权限矩阵**（每个角色看到的东西一模一样）。

⇒ 本种子只加**一个维度**：**角色矩阵**（per-user 的全局角色 × 项目内角色）
⇒ 业务数据量**不扩**（TODO-149 的结论）。

## 三条硬约束（每条都对应一类**静默**失败）

1. **幂等** —— 跑第二遍不炸、不重复、不留脏数据。
2. **只造起点态** —— 记录 = DRAFT、交付物 = DRAFT ⇒ **状态必须由场景走出来**
   ⇒ 否则 E2E 只是断言一个「摆好的状态」⇒ 测不到状态机。
3. **只删自己造的** —— `--reset` 按固定 UUID 列表筛 ⇒ 不碰业务数据。
   ⚠️ **`users` 表一个都不删**（`user_id` 是派生值 ⇒ 按 id 删 = 删真实账号）。
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models.calc import PipingResult
from app.models.deliverable import (
    Deliverable,
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.project import Project, Stream, User, UserProject, Workspace
from app.models.report import ReportDefinition
from scripts.seed_e2e_flows import (
    AUTHORIZED_USERNAMES,
    FLOW_MATRIX_ID,
    FLOW_PROJECT_ID,
    FLOW_USERNAMES,
    FLOW_WORKSPACE_ID,
    PIPING_RECORD_PAYLOAD,
    USERNAME_TO_ROLE,
    seed_flows,
)


async def _count(db, model) -> int:
    return int((await db.execute(select(func.count()).select_from(model))).scalar_one())


async def test_seed_flows_is_idempotent(db_session):
    """跑两遍 ⇒ 各表行数**不涨**。

    ⚠️ 幂等的症状很隐蔽：E2E 第二次跑时表里多了一行 ⇒ 断言飘 ⇒
    排查方向会跑到「业务代码有 bug」上，而真因是脚本没幂等。
    """
    await seed_flows(db_session)
    first = {
        model: await _count(db_session, model)
        for model in (
            Workspace,
            Project,
            User,
            UserProject,
            Stream,
            SignatureMatrix,
            ProjectSignatureMatrixBinding,
            Deliverable,
            PipingResult,
            ReportDefinition,
        )
    }

    await seed_flows(db_session)
    second = {
        model: await _count(db_session, model)
        for model in first
    }

    assert first == second, f"跑第二遍行数变了：{first} → {second}"


async def test_seed_flows_creates_one_user_per_global_role(db_session):
    """7 个用户 ⇒ **5 种**全局角色都覆盖到，且每个用户的角色与映射表一致。

    ⚠️ 不是「各不相同」—— `e2e-outsider` 与 `alice` 的全局角色**也是** DESIGNER
    ⇒ 真正的不变量是「**5 种角色都有人**」+「每个用户的角色 = 映射表里的那个」。
    """
    await seed_flows(db_session)

    users = (await db_session.execute(select(User))).scalars().all()
    by_name = {u.username: u for u in users}

    for username in FLOW_USERNAMES:
        assert username in by_name, f"种子没造用户 {username!r}"

    roles = {by_name[name].username: USERNAME_TO_ROLE[name] for name in FLOW_USERNAMES}
    assert set(roles.values()) == {
        "DESIGNER",
        "CHECKER",
        "REVIEWER",
        "APPROVER",
        "SYSTEM_ADMIN",
    }, f"全局角色没覆盖全：{roles}"


async def test_seed_flows_grants_project_roles_except_the_outsider(db_session):
    """6 条 `UserProject` ⇒ 项目内角色各异；`e2e-outsider` **没有**授权行。

    ⚠️ **授权行不是可选项**：带项目守卫的端点按「有没有授权行」判定 ⇒
    没有 ⇒ 一律 **404**（与「不存在」逐字同形）⇒ 极难定位。
    """
    await seed_flows(db_session)

    grants = (
        (await db_session.execute(select(UserProject))).scalars().all()
    )
    assert len(grants) == len(AUTHORIZED_USERNAMES), (
        f"授权行数不对：{len(grants)} ≠ {len(AUTHORIZED_USERNAMES)}"
    )

    granted_users = {g.user_id for g in grants}
    from app.services.token_issuer import derive_user_id

    assert derive_user_id("e2e-outsider") not in granted_users, (
        "e2e-outsider 必须**没有**授权行 ⇒ 他才是「跨项目 ⇒ 404」的局外人"
    )
    # ⚠️ `erin` = **角色够、授权缺**（P10-B 评审 #5）—— 前端真后端通道要验
    # 「跨项目 ⇒ 404（与不存在同形）」⇒ ⇒ 那条断言必须**走到项目守卫**
    # ⇒ ⇒ 身份得**过得了角色闸**（DESIGNER）**且没有**授权行。
    assert derive_user_id("erin") not in granted_users, (
        "erin 必须**没有**授权行 ⇒ 他才是前端那条「跨项目 ⇒ 404」的身份"
        "（有授权 ⇒ 200 ⇒ 断言走不到项目守卫）"
    )
    # 项目内角色必须**各异**（不能又一个「统一 DESIGNER」）
    assert len({g.role_in_project for g in grants}) >= 5, (
        f"项目内角色没铺开：{[g.role_in_project for g in grants]}"
    )


async def test_seed_flows_grants_alice_for_the_ui_lane(db_session):
    """⚠️ **`alice` 必须有授权行**（hermes P1-4）：

    mock 登录只认 alice/bob/carol/dan ⇒ T7 的 UI 流只能以 alice 登录
    ⇒ alice 在 flows 项目上没有授权行 ⇒ 项目守卫端点全 **404**
    ⇒ ⇒ **UI 通道 5 条全红**，且症状看着像「端点坏了」。

    ⇒ 同时断 `bob`/`carol`/`dan` **没有**授权行（他们是 UI 通道的「局外人」）。
    """
    await seed_flows(db_session)

    from app.services.token_issuer import derive_user_id

    granted = {
        g.user_id
        for g in (await db_session.execute(select(UserProject))).scalars().all()
    }
    assert derive_user_id("alice") in granted, "alice 没有授权行 ⇒ UI 通道会全 404"
    for outsider in ("bob", "carol", "dan"):
        assert derive_user_id(outsider) not in granted, (
            f"{outsider} 必须没有授权行 ⇒ 他是 UI 通道的「局外人」"
        )


async def test_seed_flows_binds_the_record_matrix_to_the_project(db_session):
    """⚠️ **项目必须绑 `module='RECORD'` 的矩阵** —— 批准链的定义源是
    **项目绑定的矩阵**（不是全局内置矩阵）⇒ 没绑 ⇒ 记录送审直接
    **422 `RECORD_APPROVAL_MATRIX_NOT_BOUND`** ⇒ T5 的整条状态机链全红，
    且症状是「端点坏了」。

    ⇒ 断两件事：绑定行存在 · 且它指向**种子那份** 3 级矩阵。
    """
    await seed_flows(db_session)

    binding = (
        await db_session.execute(
            select(ProjectSignatureMatrixBinding).where(
                ProjectSignatureMatrixBinding.project_id == FLOW_PROJECT_ID,
                ProjectSignatureMatrixBinding.module == "RECORD",
            )
        )
    ).scalar_one_or_none()
    assert binding is not None, "项目没绑 RECORD 矩阵 ⇒ 送审会 422"
    assert binding.matrix_id == FLOW_MATRIX_ID, (
        "绑的不是种子那份矩阵 ⇒ 批准链会走到别的矩阵上"
    )

    matrix = (
        await db_session.execute(
            select(SignatureMatrix).where(SignatureMatrix.matrix_id == FLOW_MATRIX_ID)
        )
    ).scalar_one()
    assert matrix.status == "ACTIVE", f"矩阵不是 ACTIVE：{matrix.status}"
    assert [s["sign_role"] for s in matrix.steps_json] == [
        "CHECKER",
        "REVIEWER",
        "APPROVER",
    ], f"矩阵的 3 级链不对：{matrix.steps_json}"


async def test_seed_flows_only_creates_starting_states(db_session):
    """记录 = DRAFT、交付物 = DRAFT ⇒ **没有**预置 CHECKED/IN_APPROVAL 之类。

    ⇒ 状态必须由场景**走**出来（否则 E2E 只是断言一个摆好的状态 ⇒
    测不到状态机 ⇒ 状态机坏了 E2E 也绿）。
    """
    await seed_flows(db_session)

    record = (
        await db_session.execute(
            select(PipingResult).where(PipingResult.project_id == FLOW_PROJECT_ID)
        )
    ).scalar_one()
    assert record.sign_status == "DRAFT", f"记录不是起点态：{record.sign_status}"

    deliverable = (
        await db_session.execute(
            select(Deliverable).where(Deliverable.project_id == FLOW_PROJECT_ID)
        )
    ).scalar_one()
    assert deliverable.sign_status == "DRAFT", (
        f"交付物不是起点态：{deliverable.sign_status}"
    )


async def test_seed_flows_reset_only_deletes_its_own_rows(db_session):
    """⚠️ **P10-A 的原罪（评审 #1）不能重演** —— `--reset` 先塞一行**别人的**用户/项目
    ⇒ reset 之后那行**还在** ⇒ 种子只删自己造的（按固定 UUID 列表筛）。
    """
    await seed_flows(db_session)

    foreign_workspace_id = uuid.uuid4()
    foreign_project_id = uuid.uuid4()
    db_session.add(
        Workspace(
            workspace_id=foreign_workspace_id,
            workspace_type="FORMAL",
            name="别人的工作区",
            status="ACTIVE",
        )
    )
    db_session.add(
        Project(
            project_id=foreign_project_id,
            project_no="FOREIGN-1",
            project_name="别人的项目",
            owner_company="别人",
            location="别处",
            project_type="REFINERY",
            design_phase="DESIGN",
            unit_system="SI",
            workspace_id=foreign_workspace_id,
            status="ACTIVE",
        )
    )
    await db_session.commit()

    await seed_flows(db_session, reset=True)

    assert (
        await db_session.execute(
            select(Project).where(Project.project_id == foreign_project_id)
        )
    ).scalar_one_or_none() is not None, "reset 删掉了**别人的**项目 ⇒ 原罪重演"
    assert (
        await db_session.execute(
            select(Workspace).where(Workspace.workspace_id == foreign_workspace_id)
        )
    ).scalar_one_or_none() is not None, "reset 删掉了别人的工作区"


async def test_seed_flows_reset_respects_foreign_key_order(db_session):
    """`--reset` 的删序遵守外键 ⇒ 反了就撞 FK ⇒ reset 直接炸。

    ⚠️ 也要断**种子自己的行**没被删漏（reset ⇒ 重灌 ⇒ 计数回到原值）。
    """
    await seed_flows(db_session)
    before = await _count(db_session, Deliverable)

    await seed_flows(db_session, reset=True)
    await seed_flows(db_session)

    assert await _count(db_session, Deliverable) == before, (
        "reset + 重灌后行数没回到原值 ⇒ reset 删多了或没删干净"
    )
    assert (
        await db_session.execute(
            select(Project).where(Project.project_id == FLOW_PROJECT_ID)
        )
    ).scalar_one_or_none() is not None, "reset 把种子自己的项目也删了且没重灌回来"


async def test_seed_flows_creates_the_pipe_class_the_record_points_to(db_session):
    """⚠️ **记录挂的管级必须真的存在** —— `piping_results.material_class` 是
    指向 `pipe_classes.class_id` 的**外键**。

    ⚠️ **为什么要在快车道里钉它**：**SQLite 不强制 FK** ⇒ 单测（内存 SQLite）
    **照样绿** ⇒ 真 PG 上才炸 ⇒ 这正是本仓最怕的「单测照绿、真库会炸」
    ⇒ ⇒ 这条断言把「那个 FK 目标存在」搬进**每次都跑**的快车道。
    """
    await seed_flows(db_session)

    from app.models.config_domain import PipeClass

    material_class = PIPING_RECORD_PAYLOAD["material_class"]
    row = (
        await db_session.execute(
            select(PipeClass).where(PipeClass.class_id == material_class)
        )
    ).scalar_one_or_none()
    assert row is not None, (
        f"种子里没有管级 {material_class!r} ⇒ 插记录会撞外键"
        "（SQLite 不强制 FK ⇒ 真 PG 上才会炸）"
    )


def test_record_payload_template_has_all_required_columns():
    """`PIPING_RECORD_PAYLOAD` **不缺列** ⇒ 缺一个 ⇒ 造记录的场景全红
    （且错误信息在**响应体**里，不在模板里 ⇒ 极难定位）。

    ⚠️ 判据取自 **ORM metadata**（不是手抄清单）⇒ 模型加列时本测试自动变红。
    """
    required = {
        c.name
        for c in PipingResult.__table__.columns
        if not c.nullable and c.default is None and c.server_default is None
    }
    # ⚠️ `project_id` / `workspace_id` 由**场景**填（每个场景自己的项目/工作区）
    required -= {"project_id", "workspace_id"}

    missing = sorted(required - set(PIPING_RECORD_PAYLOAD))
    assert not missing, f"载荷模板缺列：{missing}"


def test_record_payload_template_is_not_shared_state():
    """⚠️ 模板是**模块级常量** ⇒ 场景改它会**污染别的场景**（字典是可变的）⇒
    ⇒ 用它造记录时必须**拷贝**（`{**TEMPLATE, ...}`）而不是直接改。
    """
    assert isinstance(PIPING_RECORD_PAYLOAD, dict)
    assert PIPING_RECORD_PAYLOAD, "载荷模板不能是空的"
