"""流程级 E2E 种子 —— P10-B（`scripts/seed_e2e_flows.py`）。

## 它解决什么

`scripts/seed_e2e_data.py`（P10-A）是**冒烟级**：4 个用户 · **项目内角色统一
`DESIGNER`** ⇒ **测不了权限矩阵**（每个角色看到的东西一模一样 ⇒
「越权 ⇒ 404」这类断言一条都写不出来）。

⇒ 本种子只加**一个维度**：**角色矩阵**（per-user 的全局角色 × 项目内角色）
⇒ **业务数据量不扩**（TODO-149 的结论：种子只够跑冒烟，但缺的是**角色维度**）。

## 三条硬约束（每条都对应一类**静默**失败）

1. **幂等** —— 跑第二遍不炸、不重复、不留脏数据。
   不幂等的症状很隐蔽：E2E 第二次跑时表里多了一行 ⇒ 断言飘 ⇒
   排查方向会跑到「业务代码有 bug」上，而真因是脚本没幂等。
2. **只造起点态** —— 记录 = DRAFT、交付物 = DRAFT ⇒ **状态必须由场景走出来**
   ⇒ 否则 E2E 只是断言一个「摆好的状态」⇒ 状态机坏了 E2E 也绿。
3. **只删自己造的** —— `--reset` 按固定 UUID 列表筛 ⇒ 不碰业务数据。
   ⚠️ **`users` 表一个都不删**（`user_id` 是**派生值**
   `uuid5(NAMESPACE_DNS, username)` ⇒ 与真实 LDAP 账号的 id **完全相同**
   ⇒ 按 id 删 = **删掉真实账号**（`roles` / `status` / `token_version` 全丢，
   其 `user_projects` 授权行被 CASCADE）⇒ 而下次登录会把它**重建为 ACTIVE**
   ⇒ **被停用的账号被悄悄启用**。

## 授权行（`user_projects`）不是可选项

带项目守卫的端点按「该用户对该项目**有没有授权行**」判定 ⇒
没有授权行 ⇒ **一律 404**（与「不存在」逐字同形）⇒ E2E 看到的全是 404，
而 404 在这个系统里**长得和「资源不存在」一模一样**⇒ 极难定位。

## 用法

    uv run python scripts/seed_e2e_flows.py            # 幂等灌种子
    uv run python scripts/seed_e2e_flows.py --reset    # 先删自己的行再灌
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PipingResult
from app.models.config_domain import PipeClass
from app.models.deliverable import (
    Deliverable,
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.project import (
    Project,
    Stream,
    User,
    UserProject,
    Workspace,
)
from app.models.report import ReportDefinition
from app.services.token_issuer import derive_user_id


def _uid(name: str) -> uuid.UUID:
    """固定 UUID（`uuid5` 派生 ⇒ 跨机器一致 ⇒ 幂等的基础）。"""
    return uuid.uuid5(uuid.NAMESPACE_DNS, name)


# ---------------------------------------------------------------------------
# 固定 id
# ---------------------------------------------------------------------------

#: 工作区（FORMAL）。
FLOW_WORKSPACE_ID = _uid("pcs-e2e-flows-workspace")
#: 项目（绑 `module='RECORD'` 签署矩阵）。
FLOW_PROJECT_ID = _uid("pcs-e2e-flows-project")
#: 记录级签署矩阵（3 级：CHECKER → REVIEWER → APPROVER）。
FLOW_MATRIX_ID = _uid("pcs-e2e-flows-matrix")
#: 起点交付物（DRAFT · 计算书）。
FLOW_DELIVERABLE_ID = _uid("pcs-e2e-flows-deliverable")
#: 起点记录（DRAFT · `PipingResult`）。
FLOW_RECORD_ID = _uid("pcs-e2e-flows-piping-result")
#: 自定义报表定义。
FLOW_REPORT_DEF_ID = _uid("pcs-e2e-flows-report-def")
#: 管级（`pipe_classes`）—— `piping_results.material_class` 是指向它的外键
#: ⇒ 记录必须挂一个**真实存在**的管级 ⇒ 种子得先造它。
#: ⚠️ `class_id` 是 **VARCHAR(50)**（不是 UUID）⇒ 值是字符串。
FLOW_PIPE_CLASS_ID = "E2E-SEED-CS"

#: 种子物流（管段）名 ⇒ `stream_id` 同样派生。
FLOW_STREAM_NAMES: tuple[str, ...] = ("E2E-FLOW-S-001", "E2E-FLOW-S-002")


def _stream_id(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"pcs-e2e-flow-stream-{name}")


#: 种子物流的 id（**有序** ⇒ `FLOW_STREAM_NAMES` 的顺序）。
#:
#: ⚠️ **必须是模块级常量** —— 计算链场景要拿「源物流」的 id ⇒
#: 若只能从种子返回值里取 ⇒ 场景就得先调种子 ⇒ 耦合 ⇒ 且 id 的真相源会散成两处。
FLOW_STREAM_IDS: tuple[uuid.UUID, ...] = tuple(
    _stream_id(name) for name in FLOW_STREAM_NAMES
)


# ---------------------------------------------------------------------------
# 角色矩阵
# ---------------------------------------------------------------------------

#: 种子用户（**7** 个）。
#:
#: ⚠️ `alice` 是给**前端真后端通道**（T7）准备的：mock 登录只认
#: `alice`/`bob`/`carol`/`dan`（`app/api/v1/mock_auth.py::MOCK_USERS`）
#: ⇒ 种子里的 `e2e-*` **一个都登不进去** ⇒ UI 流必须有一个能登录且有授权的人。
#:
#: ⚠️ `bob`/`carol`/`dan` **故意不授权** ⇒ 他们是 UI 通道里的「局外人」。
FLOW_USERNAMES: tuple[str, ...] = (
    "e2e-designer",
    "e2e-checker",
    "e2e-reviewer",
    "e2e-approver",
    "e2e-admin",
    "e2e-outsider",
    "alice",
)

#: 用户名 → **全局**角色（JWT claim）。
#:
#: ⚠️ 「全局角色 ≠ 项目内角色」：状态机按**全局**判（`TRANSITION_ROLES`）·
#: 项目守卫按**项目内**判 ⇒ 两个维度都要有 ⇒ 不能一个角色打天下。
USERNAME_TO_ROLE: dict[str, str] = {
    "e2e-designer": "DESIGNER",
    "e2e-checker": "CHECKER",
    "e2e-reviewer": "REVIEWER",
    "e2e-approver": "APPROVER",
    "e2e-admin": "SYSTEM_ADMIN",
    # ⚠️ 同为 DESIGNER，但**没有**授权行 ⇒ 跨项目 ⇒ 404（验「与不存在同形」）
    "e2e-outsider": "DESIGNER",
    # ⚠️ 为 UI 通道准备（mock 登录能登）⇒ 后端场景**不得**解析到它
    "alice": "DESIGNER",
}

#: 全局角色 → **有授权**的种子用户（**唯一**映射 ⇒ `role_headers(<role>)` 用它）。
#:
#: ⚠️ **只列有授权的人** —— `e2e-outsider` / `alice` 不在表里 ⇒
#: 要用他们必须**显式点名**（`role_headers(username="e2e-outsider")`）
#: ⇒ 否则正常场景会拿到局外人的 token ⇒ **全部变 404**（症状像「端点坏了」）。
ROLE_TO_USERNAME: dict[str, str] = {
    "DESIGNER": "e2e-designer",
    "CHECKER": "e2e-checker",
    "REVIEWER": "e2e-reviewer",
    "APPROVER": "e2e-approver",
    "SYSTEM_ADMIN": "e2e-admin",
}

#: 用户名 → **项目内**角色（`user_projects.role_in_project`）。
#:
#: ⚠️ 合法值 6 个：DESIGNER / CHECKER / APPROVER / REVIEWER / VIEWER / PROJECT_LEAD
#: ⇒ **没有 `TEST_VIEWER`**（SPEC 的 AUTH-E2E-11/12 因此延到 P10-C）。
USERNAME_TO_PROJECT_ROLE: dict[str, str] = {
    "e2e-designer": "DESIGNER",
    "e2e-checker": "CHECKER",
    "e2e-reviewer": "REVIEWER",
    "e2e-approver": "APPROVER",
    "e2e-admin": "VIEWER",
    "alice": "DESIGNER",
    # ⚠️ `e2e-outsider` **故意没有**授权行（⇒ 跨项目 ⇒ 404）
}

#: 有授权的用户（`UserProject` 行数 = 它的长度）。
AUTHORIZED_USERNAMES: tuple[str, ...] = tuple(USERNAME_TO_PROJECT_ROLE)


# ---------------------------------------------------------------------------
# 载荷模板（D8：一份真相源 ⇒ 9 个场景不各写一份）
# ---------------------------------------------------------------------------

#: 造 DRAFT 记录（`PipingResult`）的**载荷模板**。
#:
#: ⚠️ **为什么要有模板**：`PipingResult` 有 **21 个必填业务列** ⇒ 逐场景传
#: payload = 同一个 21 字段字典抄 **9 遍** ⇒ 改一处要改九处 ⇒ 漏一处 ⇒
#: 那个场景全红（且错误在**响应体**里，不在模板里 ⇒ 极难定位）。
#:
#: ⚠️ **是模块级常量** ⇒ 场景**不得**直接改它 ⇒ 必须 `{**TEMPLATE, ...}` 拷贝。
#: ⇒ 「必填列不缺」由 `tests/scripts/test_seed_e2e_flows.py` 钉住
#: （判据取自 **ORM metadata** ⇒ 模型加列时测试自动变红）。
PIPING_RECORD_PAYLOAD: dict[str, Any] = {
    "seq_no": 1,
    "line_no": "E2E-L-001",
    "line_size": "DN150",
    # ⚠️ **必须是一个真实存在的管级 id** —— `piping_results.material_class`
    # 是指向 `pipe_classes.class_id` 的外键 ⇒ 种子会造那一行
    # ⇒ ⚠️ **SQLite 不强制 FK** ⇒ 单测（内存 SQLite）**照样绿** ⇒ 真 PG 上才炸
    # ⇒ 这正是「单测照绿、真库会炸」的形状 ⇒ 由 **PG 车道**兜住。
    "material_class": FLOW_PIPE_CLASS_ID,
    "fluid_code": "N2",
    "fluid_name": "氮气",
    "fluid_phase": "GAS",
    "fluid_category": "NORMAL",
    "toxic_class": "无毒",
    "pipe_grade": "20#",
    "insulation_code": "H",
    "insulation_thickness": 50.0,
    "paint_code": "GY",
    "tracing_type": "TE",
    "holding_temp": 20.0,
    "source_pid": "P&ID-E2E-001",
    "line_from": "E2E-边界-1",
    "line_to": "E2E-边界-2",
    "norm_oper_press": 0.6,
    "max_oper_press": 0.8,
    "norm_oper_temp": 30.0,
    "max_oper_temp": 50.0,
    "design_press": 1.0,
    "design_temp": 60.0,
    "piping_category": "工艺管道",
    "pressure_test_medium": "水",
    "pressure_test_press": 1.5,
    "check_class": "I",
    "remark": "E2E 种子记录",
}


# ---------------------------------------------------------------------------
# get-or-create（house pattern）
# ---------------------------------------------------------------------------


async def _get_or_create(db: AsyncSession, match: Any, build: Callable[[], Any]) -> Any:
    """**本仓的 get-or-create 形状**（house pattern · 评审 #9）。

    ⚠️ **为什么不能是「裸 SELECT ⇒ 见空 ⇒ INSERT」**：
    两个并发跑（compose 的 `seed` 一次性容器 + 手工再跑一次）会**都**看到
    「空」⇒ 都 INSERT ⇒ **输家撞唯一约束** ⇒ 而旧形状里那个 `flush()` 抛出的
    `IntegrityError` 会**污染整笔事务** ⇒ 脚本直接炸。

    ⇒ 三步（照 `docs/solutions/database-issues/`
    `get-or-create-default-row-race-savepoint-reread.md`）：
    ① `db.add` + `flush` 在 **`begin_nested()`（savepoint）之内**
    ② 撞 `IntegrityError` ⇒ **回滚 savepoint**（整笔事务仍然可用）
    ③ **重读赢家**（**只读；绝不 update**）⇒ 返回它
    """
    existing = (await db.execute(match)).scalar_one_or_none()
    if existing is not None:
        return existing
    entity = build()
    try:
        async with db.begin_nested():
            db.add(entity)
            await db.flush()
    except IntegrityError:
        winner = (await db.execute(match)).scalar_one_or_none()
        if winner is not None:
            return winner
        raise
    return entity


# ---------------------------------------------------------------------------
# reset（只删自己造的 · 遵守外键顺序）
# ---------------------------------------------------------------------------


async def _delete_own_rows(db: AsyncSession) -> None:
    """删掉**种子集合**的行（不碰业务数据）。

    ⚠️ **删除顺序必须遵守外键约束**：

        deliverables → piping_results → report_definitions
        → project_signature_matrix_bindings → streams → user_projects
        → signature_matrices → projects → workspaces

    ⚠️ **`users` 表一个都不删**（评审 #1 · 2026-11-12）—— `user_id` 是**派生值**
    ⇒ 与真实 LDAP 账号的 id **完全相同** ⇒ 按 id 删 = **删掉真实账号**
    ⇒ 其 `user_projects` 授权行被 `ondelete="CASCADE"` 连带删掉
    ⇒ 而下次登录会把这个行**重建为 ACTIVE** ⇒ **被停用的账号被悄悄启用**。
    ⇒ 已存在的用户行连 `status` / `roles` 都不许改。
    """
    project_ids = [FLOW_PROJECT_ID]

    await db.execute(delete(Deliverable).where(Deliverable.project_id.in_(project_ids)))
    await db.execute(delete(PipingResult).where(PipingResult.project_id.in_(project_ids)))
    await db.execute(
        delete(ReportDefinition).where(ReportDefinition.project_id.in_(project_ids))
    )
    await db.execute(
        delete(ProjectSignatureMatrixBinding).where(
            ProjectSignatureMatrixBinding.project_id.in_(project_ids)
        )
    )
    await db.execute(delete(Stream).where(Stream.project_id.in_(project_ids)))
    await db.execute(delete(UserProject).where(UserProject.project_id.in_(project_ids)))
    await db.execute(
        delete(SignatureMatrix).where(SignatureMatrix.matrix_id == FLOW_MATRIX_ID)
    )
    await db.execute(delete(PipeClass).where(PipeClass.class_id == FLOW_PIPE_CLASS_ID))
    await db.execute(delete(Project).where(Project.project_id.in_(project_ids)))
    await db.execute(
        delete(Workspace).where(Workspace.workspace_id == FLOW_WORKSPACE_ID)
    )
    await db.commit()


# ---------------------------------------------------------------------------
# 各类实体
# ---------------------------------------------------------------------------


async def _ensure_workspace(db: AsyncSession) -> Workspace:
    """建/取种子工作区（FORMAL）。

    ⚠️ `Project.workspace_id` 是 NOT NULL ⇒ 没有工作区就**建不出项目**
    ⇒ 工作区是种子链的第一环。
    """
    return await _get_or_create(
        db,
        select(Workspace).where(Workspace.workspace_id == FLOW_WORKSPACE_ID),
        lambda: Workspace(
            workspace_id=FLOW_WORKSPACE_ID,
            workspace_type="FORMAL",
            name="E2E Flows Workspace",
            status="ACTIVE",
        ),
    )


async def _ensure_project(db: AsyncSession, workspace: Workspace) -> Project:
    return await _get_or_create(
        db,
        select(Project).where(Project.project_id == FLOW_PROJECT_ID),
        lambda: Project(
            project_id=FLOW_PROJECT_ID,
            project_no="E2E-FLOW-0001",
            project_name="E2E Flows Project",
            owner_company="E2E Owner",
            location="E2E Site",
            project_type="REFINERY",
            design_phase="DESIGN",
            unit_system="SI",
            workspace_id=workspace.workspace_id,
            status="ACTIVE",
        ),
    )


async def _ensure_users(db: AsyncSession) -> list[User]:
    """建/取种子用户。

    ⚠️ `roles` 写**空数组** —— 与 `ensure_user_row` 同款：
    **真实登录会覆盖** `users.roles`（不是合并）⇒ 预置角色也白写。
    ⚠️ `roles` **不影响鉴权**（ACL 的权威是 JWT 的 role claim）⇒ 空数组安全。

    ⚠️⚠️ **已存在的用户行一个字段都不许改**（评审 #1）——
    `user_id` 是派生值 ⇒ 与真实 LDAP 账号的 id 相同 ⇒ 改 `status`
    就等于**把被停用的账号悄悄启用**。
    """
    users: list[User] = []
    for username in FLOW_USERNAMES:
        user_id = derive_user_id(username)
        users.append(
            await _get_or_create(
                db,
                select(User).where(User.user_id == user_id),
                lambda user_id=user_id, username=username: User(
                    user_id=user_id,
                    username=username,
                    display_name=username,
                    roles=[],
                    ad_groups=[],
                    status="ACTIVE",
                ),
            )
        )
    return users


async def _ensure_grants(
    db: AsyncSession, users: list[User], project: Project
) -> None:
    """建/取 `UserProject` 授权行（项目守卫的判据）。

    ⚠️ **每个用户的项目内角色不同** —— 这正是本种子的核心（TODO-149）：
    统一角色的种子**测不了权限矩阵**。
    """
    for user in users:
        role_in_project = USERNAME_TO_PROJECT_ROLE.get(user.username)
        if role_in_project is None:
            # ⚠️ `e2e-outsider` **故意不授权** ⇒ 他是「跨项目 ⇒ 404」的局外人
            continue
        await _get_or_create(
            db,
            select(UserProject).where(
                UserProject.user_id == user.user_id,
                UserProject.project_id == project.project_id,
            ),
            lambda user=user, role_in_project=role_in_project: UserProject(
                user_id=user.user_id,
                project_id=project.project_id,
                role_in_project=role_in_project,
            ),
        )


async def _ensure_streams(
    db: AsyncSession, project: Project, workspace: Workspace
) -> int:
    """建/取种子物流（管段，含组成与物性）。返回物流条数。"""
    for index, name in enumerate(FLOW_STREAM_NAMES):
        sid = _stream_id(name)
        await _get_or_create(
            db,
            select(Stream).where(Stream.stream_id == sid),
            lambda sid=sid, index=index, name=name: Stream(
                stream_id=sid,
                project_id=project.project_id,
                workspace_id=workspace.workspace_id,
                stream_name=name,
                description="E2E 流程级种子物流",
                data_mode="CHEMICAL",
                phase="LIQUID",
                source="SIM_IMPORT" if index else "MANUAL",
                source_type="SIM_IMPORT" if index else "MANUAL_ENTRY",
                composition_json={"7732-18-5": 1.0},
                vapor_composition_json={"7732-18-5": 1.0},
                property_estimation_json={
                    "normal_oper_press": 0.6,
                    "normal_oper_temp": 30.0,
                    "molar_flow": 100.0,
                },
                stream_properties_json={"phase": "LIQUID"},
                # ⚠️ **CHECKED** —— 计算链的入口守卫
                # （`app/services/calc_entry.py::check_calc_inputs`）要求
                # 输入物流 `sign_status == CHECKED` ⇒ DRAFT ⇒ **403
                # `STREAM_NOT_CHECKED`** ⇒ 计算链场景全红。
                # ⚠️ 「只造起点态」不冲突：物流是计算链的**输入**，
                # **CHECKED 就是它的起点**；要「走」状态的是**记录**
                # （T5 的场景各自造 DRAFT 记录 ⇒ D7）。
                sign_status="CHECKED",
                approval_depth=1,
            ),
        )
    return len(FLOW_STREAM_NAMES)


#: 记录级签署矩阵的 3 级链（CHECKER → REVIEWER → APPROVER）。
#:
#: ⚠️ **第 1 步不能是 DESIGNER** —— `submit-approval` 的**自审闸**
#: （`APPROVAL_SELF_REVIEW_FORBIDDEN`）在「提交人自己的角色出现在链里」时
#: 403 ⇒ 提交人是 DESIGNER ⇒ 链里不能有 DESIGNER ⇒ 否则**整条链走不通**。
FLOW_MATRIX_STEPS: list[dict[str, Any]] = [
    {
        "step_order": 1,
        "sign_role": "CHECKER",
        "required": True,
        "can_self_check": True,
        "can_skip": False,
    },
    {
        "step_order": 2,
        "sign_role": "REVIEWER",
        "required": True,
        "can_self_check": True,
        "can_skip": False,
    },
    {
        "step_order": 3,
        "sign_role": "APPROVER",
        "required": True,
        "can_self_check": True,
        "can_skip": False,
    },
]


async def _ensure_pipe_class(db: AsyncSession) -> PipeClass:
    """建/取管级（`pipe_classes`）。

    ⚠️ **必须有它** —— `piping_results.material_class` 是指向
    `pipe_classes.class_id` 的**外键** ⇒ 没有这一行 ⇒ 插记录直接撞 FK。
    ⚠️ ⚠️ **SQLite 不强制 FK** ⇒ 单测（内存 SQLite）**照样绿** ⇒
    真 PG 上才炸 ⇒ 这正是「单测照绿、真库会炸」的形状 ⇒
    ⇒ 本行由 **PG 车道**兜住（`scripts/pytest_e2e.sh`）。
    """
    return await _get_or_create(
        db,
        select(PipeClass).where(PipeClass.class_id == FLOW_PIPE_CLASS_ID),
        lambda: PipeClass(
            class_id=FLOW_PIPE_CLASS_ID,
            class_name="E2E 种子管级",
            material_standard="GB/T 150",
            base_material="20#",
            corrosion_allowance=1.5,
            design_pressure=1.0,
            design_temperature=60.0,
            allowable_stress_json={"20#": 137.0},
            dn_series_json={"DN150": 1.0},
            sch_series_json={"DN150": 40.0},
            flange_class="PN16",
            source="E2E_SEED",
            version="1",
        ),
    )


async def _ensure_matrix(db: AsyncSession) -> SignatureMatrix:
    """建/取记录级签署矩阵（3 级）。"""
    return await _get_or_create(
        db,
        select(SignatureMatrix).where(SignatureMatrix.matrix_id == FLOW_MATRIX_ID),
        lambda: SignatureMatrix(
            matrix_id=FLOW_MATRIX_ID,
            matrix_name="E2E_FLOWS_RECORD_3_LEVEL",
            module="RECORD",
            doc_type="CALCULATION_BOOK",
            version_purpose="DESIGN",
            steps_json=list(FLOW_MATRIX_STEPS),
            status="ACTIVE",
        ),
    )


async def _ensure_matrix_binding(
    db: AsyncSession, project: Project, matrix: SignatureMatrix
) -> None:
    """把矩阵绑到项目（`module='RECORD'`）。

    ⚠️ **没有绑定 ⇒ 记录送审直接 422 `RECORD_APPROVAL_MATRIX_NOT_BOUND`**
    ⇒ 批准链的定义源 = **项目绑定的矩阵**（不是全局内置矩阵）。
    """
    await _get_or_create(
        db,
        select(ProjectSignatureMatrixBinding).where(
            ProjectSignatureMatrixBinding.project_id == project.project_id,
            ProjectSignatureMatrixBinding.module == "RECORD",
        ),
        lambda: ProjectSignatureMatrixBinding(
            project_id=project.project_id,
            module="RECORD",
            matrix_id=matrix.matrix_id,
        ),
    )


async def _ensure_deliverable(
    db: AsyncSession, project: Project, matrix: SignatureMatrix
) -> Deliverable:
    """建/取起点交付物（DRAFT · 计算书）。

    ⚠️ **`sign_status` 必须是 DRAFT** —— 交付物的 4 态是
    DRAFT/PENDING/APPROVED/OBSOLETE ⇒ 预置成别的 ⇒ 场景的「走完流程」断言飘。
    """
    return await _get_or_create(
        db,
        select(Deliverable).where(Deliverable.deliverable_id == FLOW_DELIVERABLE_ID),
        lambda: Deliverable(
            deliverable_id=FLOW_DELIVERABLE_ID,
            project_id=project.project_id,
            deliverable_type="CALCULATION_BOOK",
            scope_type="PROJECT_ALL",
            scope_value="ALL",
            doc_no="E2E-FLOW-DOC-0001",
            doc_no_mode="MANUAL",
            title="E2E 流程级种子计算书",
            current_rev="1",
            version_purpose="DESIGN",
            sign_status="DRAFT",
            matrix_id=matrix.matrix_id,
        ),
    )


async def _ensure_record(
    db: AsyncSession, project: Project, workspace: Workspace
) -> PipingResult:
    """建/取起点记录（DRAFT · `PipingResult`）。

    ⚠️ 用**载荷模板**（D8）⇒ 一处真相源 ⇒ 场景不各写一份 21 字段字典。
    ⚠️ **拷贝**模板（`{**TEMPLATE}`）⇒ 场景改自己的副本不会污染模板。
    """
    return await _get_or_create(
        db,
        select(PipingResult).where(PipingResult.pipe_id == FLOW_RECORD_ID),
        lambda: PipingResult(
            pipe_id=FLOW_RECORD_ID,
            project_id=project.project_id,
            workspace_id=workspace.workspace_id,
            **{**PIPING_RECORD_PAYLOAD},
        ),
    )


async def _ensure_report_definition(
    db: AsyncSession, project: Project
) -> ReportDefinition:
    """建/取自定义报表定义（E2E-015 用）。"""
    return await _get_or_create(
        db,
        select(ReportDefinition).where(ReportDefinition.def_id == FLOW_REPORT_DEF_ID),
        lambda: ReportDefinition(
            def_id=FLOW_REPORT_DEF_ID,
            project_id=project.project_id,
            name="E2E 流程级报表定义",
            category="CUSTOM",
            description="E2E 种子",
            definition_json={
                "datasource": "streams",
                "fields": ["stream_name", "phase"],
                "filters": {},
            },
            output_format="XLSX",
            max_rows=1000,
            version=1,
            status="PUBLISHED",
        ),
    )


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


async def seed_flows(db: AsyncSession, *, reset: bool = False) -> dict[str, int]:
    """幂等灌流程级种子数据。

    Args:
        db: 调用方给 session（⚠️ 本函数**自己 commit** —— 幂等重灌要求
            「查→插→提交」是一个整体；调用方若还要接着写数据，请**另开
            一个 session** 或在调用后显式判断）。
        reset: True ⇒ 先删掉**种子集合**的行再重灌（不碰业务数据）。

    Returns:
        各实体的**行数**（种子集合当前有多少行）。
        ⚠️ 不是「本次新建了几行」⇒ **跑两遍返回同一个值就是幂等的直接证据**。

    ⚠️ 必须有可调用入口（只有 `if __name__ == "__main__"` 的话单测没法传 session）。
    """
    if reset:
        await _delete_own_rows(db)

    workspace = await _ensure_workspace(db)
    project = await _ensure_project(db, workspace)
    users = await _ensure_users(db)
    await _ensure_grants(db, users, project)
    streams = await _ensure_streams(db, project, workspace)
    await _ensure_pipe_class(db)
    matrix = await _ensure_matrix(db)
    await _ensure_matrix_binding(db, project, matrix)
    await _ensure_deliverable(db, project, matrix)
    await _ensure_record(db, project, workspace)
    await _ensure_report_definition(db, project)

    await db.commit()

    return {
        "workspaces": 1,
        "projects": 1,
        "users": len(users),
        "user_projects": len(AUTHORIZED_USERNAMES),
        "streams": streams,
        "signature_matrices": 1,
        "project_signature_matrix_bindings": 1,
        "deliverables": 1,
        "records": 1,
        "report_definitions": 1,
    }


async def _main(reset: bool) -> None:
    from app.db.session import get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        counts = await seed_flows(session, reset=reset)

    summary: dict[str, Any] = counts
    print(
        "流程级种子数据完成："
        + " · ".join(f"{key}={value}" for key, value in sorted(summary.items()))
    )


if __name__ == "__main__":  # pragma: no cover — 脚本入口
    parser = argparse.ArgumentParser(description="灌流程级 E2E 种子数据（幂等）")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="先删掉种子集合自己的行再重灌（不碰业务数据）",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.reset))


__all__ = [
    "AUTHORIZED_USERNAMES",
    "FLOW_DELIVERABLE_ID",
    "FLOW_MATRIX_ID",
    "FLOW_MATRIX_STEPS",
    "FLOW_PIPE_CLASS_ID",
    "FLOW_PROJECT_ID",
    "FLOW_RECORD_ID",
    "FLOW_REPORT_DEF_ID",
    "FLOW_STREAM_IDS",
    "FLOW_STREAM_NAMES",
    "FLOW_USERNAMES",
    "FLOW_WORKSPACE_ID",
    "PIPING_RECORD_PAYLOAD",
    "ROLE_TO_USERNAME",
    "USERNAME_TO_PROJECT_ROLE",
    "USERNAME_TO_ROLE",
    "seed_flows",
]
