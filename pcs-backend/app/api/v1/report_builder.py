"""`/api/v1/report-builder` 路由（Phase 2，REPORT_BUILDER）。

本文件**只放定义管理的端点**，不放查询执行 —— 执行走 `/report`（固定 10 类）
与 `/report-builder/{def_id}/execute`（自定义定义）。

## b1：字段树为什么连 JOIN 白名单一起下发

字段树是前端字段选择器的唯一数据源。JOIN 白名单（`datasource_registry.JOINS`
的 5 对）是**另一份**必须下发的声明：后端 `join_key_for` 对白名单外的组合
直接抛 `REPORT_BUILDER_JOIN_NOT_SUPPORTED`（400），前端若自己按名称猜关联，
猜错的表现是「选得了、跑不了」—— 用户填完整个报表才撞墙。

因此：**只下发白名单里的对**，且**逐字来自注册表**，不接受请求参数扩充。
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.acl import REVIEW_ROLES
from app.db.session import get_db
from app.models.report import ReportExecutionLog
from app.schemas.report_builder import (
    ReportBuilderDatasource,
    ReportBuilderDatasourceList,
    ReportBuilderField,
    ReportBuilderJoin,
    ReportDefCondition,
    ReportDefFilterGroup,
    ReportDefinitionList,
    ReportDefinitionOut,
    ReportDefinitionReviewItem,
    ReportDefinitionReviewList,
    ReportDefinitionUpsert,
)
from app.services.exceptions import PcsError
from app.services.notifications.notify import publish
from app.services.report import watermark
from app.services.report.datasource_registry import DATASOURCES, JOINS
from app.services.user_project_service import require_project_access_or_404
from app.services.report.definition_service import (
    DEFINITION_STATUSES,
    MAX_ROWS_CEILING,
    DefinitionService,
)

router = APIRouter(prefix="/report-builder", tags=["report-builder"])

ActorDep = Annotated[_Actor, Depends(current_actor)]
DbDep = Annotated["AsyncSession", Depends(get_db)]


@router.get("/datasources", response_model=ReportBuilderDatasourceList)
async def list_datasources(actor: ActorDep) -> ReportBuilderDatasourceList:
    """13 个可选数据源的字段树 + 5 对 JOIN 白名单。

    **需要认证**：响应等价于一份内部表结构与列名的清单。
    """
    return ReportBuilderDatasourceList(
        datasources=[
            ReportBuilderDatasource(
                key=ds.key,
                label=ds.label,
                model=ds.model,
                # 字段按名字排序：注册表里主键是循环后补进去的，
                # dict 顺序不保证稳定，不排序的话同一次改动会让 UI 顺序跳动。
                fields=[
                    ReportBuilderField(
                        name=name,
                        type=spec.type,
                        label=spec.label,
                        is_jsonb_key=spec.is_jsonb_key,
                        # ADR-0028：字段树按 detail_level 与换热器类型分组。
                        # 两个字段都是 None = 通用字段，任何分级都能选。
                        level=spec.level,
                        exchanger_type=spec.exchanger_type,
                    )
                    for name, spec in sorted(ds.fields.items())
                ],
            )
            for ds in sorted(DATASOURCES.values(), key=lambda d: d.key)
        ],
        joins=[
            ReportBuilderJoin(a=j.a, a_field=j.a_field, b=j.b, b_field=j.b_field,
                              degrade_warn=j.degrade_warn)
            for j in JOINS
        ],
    )

# --- b2 定义 CRUD -----------------------------------------------------------

#: 输出格式白名单。直接取 `watermark.EXPORT_FORMATS` —— b8 落地 CSV 后
#: 两边不再各持一份。第一版这里写死 `{pdf, xlsx, docx}`（注释说「CSV 属
#: b8」），结果就是 CSV 落地后这个白名单没跟着改，用户在输出格式下拉框里
#: 仍然选不到 CSV —— 缺陷在别处、根因在两份清单。
_RENDERABLE_FORMATS = frozenset(watermark.EXPORT_FORMATS)


def _reject_bad_format(fmt: str) -> None:
    """未知输出格式 400。

    不能静默接受：用户在表单里选了 `csv`，定义保存成功、审批通过、
    执行时才失败 —— 那时他已经填完了所有条件。写进来时就拒。
    """
    if fmt not in _RENDERABLE_FORMATS:
        raise PcsError(
            f"暂不支持输出格式 {fmt!r}，可用：{sorted(_RENDERABLE_FORMATS)}",
            code="REPORT_OUTPUT_FORMAT_UNSUPPORTED", status=400,
        )


@router.post("/definitions", response_model=ReportDefinitionOut, status_code=201)
async def create_definition(
    body: ReportDefinitionUpsert, actor: ActorDep, db: DbDep,
) -> ReportDefinitionOut:
    """新建定义。落 DRAFT，仅创建人可见（SPEC §3.2.2(6)）。"""
    _reject_bad_format(body.output_format)
    svc = DefinitionService(db)
    row = await svc.create(
        user_id=actor.user_id, name=body.name, category=body.category,
        description=body.description, output_format=body.output_format,
        definition_json=body.definition_json.model_dump(), shared_with=body.shared_with,
        project_id=body.project_id, max_rows=body.max_rows,
        # ⚠️ **roles 要传下去** —— service 层要判「这个人对 `project_id`
        # 有没有授权」⇒ ⇒ 而 SYSTEM_ADMIN 是全局 bypass ⇒ ⇒ 判据是角色。
        actor_roles=list(actor.roles),
    )
    # ⚠️ **先序列化再 commit**，不是反过来。
    # UPDATE flush 之后，`updated_at`（onupdate=func.now()，服务端生成）
    # 会被 SQLAlchemy 标记为 expired —— 而生产 session（app/db/session.py:82）
    # **只设了 expire_on_commit=False，没设 expire_on_flush=False**。于是
    # commit 后再读它就是一次隐式 SELECT，落在同步上下文里 →
    # MissingGreenlet → 500。
    # 测试的 db_session fixture 恰好设了 expire_on_flush=False，
    # 只改 fixture 会得到「测试绿、生产红」。
    payload = _as_dict(row)
    await db.commit()
    return ReportDefinitionOut(**payload)


@router.get("/definitions", response_model=ReportDefinitionList)
async def list_definitions(
    actor: ActorDep, db: DbDep,
    status: str | None = Query(
        None, description="按状态收窄：DRAFT / PUBLISHED / OBSOLETE"),
) -> ReportDefinitionList:
    """列出可见定义。`status` 是**进一步收窄**，见 `DefinitionService.list`。

    ⚠️ 此前签名里**没有任何查询参数**，而前端
    `ReportDefinitionListPage` 的状态筛选一直把 `status` 发过来
    （该文件 docstring 明写「它作为查询参数发给后端，不在本地裁剪」）。
    参数被**静默丢弃** ⇒ 200 + 全量 ⇒ 用户选「已发布」列表纹丝不动，
    **零报错**。症状是「筛选看起来坏了但没报错」。

    未知状态词 400 而不是忽略：静默忽略正是本缺陷的病根 ——
    参数拼错 / 状态词写错 / 契约改名，三种错都表现为「筛选不生效」，
    用户无从分辨是哪一种。
    """
    if status is not None and status not in DEFINITION_STATUSES:
        raise PcsError(
            f"未知的定义状态 {status!r}，支持 {sorted(DEFINITION_STATUSES)}。",
            code="REPORT_DEFINITION_INVALID_STATUS", status=400,
        )
    # ⚠️ **roles 要传下去**（2026-11-19 · TODO-192 #10）⇒ ⇒ SYSTEM_ADMIN 的
    # 全局 bypass 在**可见性**这一侧也生效 ⇒ ⇒ 否则 admin「能 publish
    # 却 GET 不到」（两处口径不一致的根因）。
    rows = await DefinitionService(db).list(
        user_id=actor.user_id, status=status, actor_roles=list(actor.roles))
    items = [ReportDefinitionOut(**_as_dict(r)) for r in rows]
    return ReportDefinitionList(items=items, total=len(items))


@router.get("/definitions/pending-review", response_model=ReportDefinitionReviewList)
async def list_pending_review(
    actor: ActorDep, db: DbDep,
) -> ReportDefinitionReviewList:
    """「待我审核」队列 —— **只读视图**（2026-11-23 · P10-I · T1 · TODO-197）。

    ## 它解的是哪个洞

    「创建 ⇒ 交给审核者 ⇒ 审核者发布」这条链，**在 UI 上断在第二环**：
    - 创建人 ⇒ ⇒ **403 自审**（`publish()` 禁自审）
    - 审核者 ⇒ ⇒ **在列表页看不见别人的草稿**（`visible_clause`：草稿只有创建人可见）
    ⇒ ⇒ ⇒ 「那个发布按钮对所有角色 100% 死」⇒ ⇒ ⇒ SPEC §3.2.2 在 UI 上不成立。

    ⇒ ⇒ 本端点给审核者**一条能看见可审草稿的路**（只读元数据）⇒ ⇒
    ⇒ ⇒ 配合编辑器页外的「发布」动作（不进编辑器）⇒ ⇒ 链就通了。

    ## 口径（**与 `visible_clause` 分离** —— 人裁约束 2）

    | 草稿类型 | 我可见 | 条件 |
    |---|---|---|
    | 公司级（`project_id IS NULL`）| ✔ | `REVIEWER+` |
    | 项目级 | ✔ | `REVIEWER+` ∧ 我在该项目有 `user_projects` 授权 |
    | 项目级 · 我无授权 | ✘ | ——（即使我是 `REVIEWER`）|
    | `created_by == 我` | ✘ | ——（自审禁止 ⇒ 与 `publish()` 的 **403** 一致）|
    | `shared_with == CREATOR_ONLY` | ✘ | ——（它没有「发布」这个动作）|

    ⚠️ **这组规则同时写进了 service 层 `pending_review()` 的 docstring**
    ⇒ ⇒ 不是只写在实现里 ⇒ ⇒ 下一个维护者不会误以为「队列 = 所有 DRAFT」。

    ## ⚠️ **路由顺序**（FastAPI 按声明顺序匹配）

    本端点**必须**声明在 `GET /definitions/{def_id}` **之前**
    ⇒ ⇒ 否则 `/definitions/pending-review` 会先撞上 `{def_id}`
    ⇒ ⇒ ⇒ 表现是 **422**（`def_id` 不是 UUID）而不是「队列」。

    ## ⚠️ **为什么这里不调 `require_roles`**

    角色闸在 **service 层**（与过滤同处一地 ⇒ ⇒ 端点漏调也绕不过）
    ⇒ ⇒ 同一条件**只有一个错误码** `REPORT_DEFINITION_ROLE_REQUIRED`
    ⇒ ⇒ （若端点也 `require_roles` ⇒ ⇒ HTTPException 的 `HTTP_403`
    ⇒ ⇒ 与 service 的码**并存** ⇒ ⇒ 前端按 code 分流要处理两个 ⇒ ⇒ 口径分裂）。
    """
    rows = await DefinitionService(db).pending_review(
        user_id=actor.user_id, actor_roles=list(actor.roles))
    items = [
        ReportDefinitionReviewItem(
            def_id=r.def_id,
            name=r.name,
            category=r.category,
            description=r.description,
            created_by=r.created_by,
            project_id=r.project_id,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return ReportDefinitionReviewList(items=items, total=len(items))


@router.get("/definitions/{def_id}", response_model=ReportDefinitionOut)
async def get_definition(
    def_id: uuid.UUID, actor: ActorDep, db: DbDep,
) -> ReportDefinitionOut:
    # ⚠️ **roles 要传下去**（2026-11-19 · TODO-192 #10）—— 同上。
    row = await DefinitionService(db).get(
        def_id=def_id, user_id=actor.user_id, actor_roles=list(actor.roles))
    return ReportDefinitionOut(**_as_dict(row))


@router.put("/definitions/{def_id}", response_model=ReportDefinitionOut)
async def update_definition(
    def_id: uuid.UUID, body: ReportDefinitionUpsert, actor: ActorDep, db: DbDep,
) -> ReportDefinitionOut:
    _reject_bad_format(body.output_format)
    row = await DefinitionService(db).update(
        def_id=def_id, user_id=actor.user_id, name=body.name,
        category=body.category, description=body.description,
        output_format=body.output_format, definition_json=body.definition_json.model_dump(),
        shared_with=body.shared_with, max_rows=body.max_rows,
        project_id=body.project_id,
        # ⚠️ **2026-11-18 · ce-code-review（TODO-192 #2）**：把**角色**传下去
        # ⇒ ⇒ service 层判「改挂到那个项目有没有授权」时，SYSTEM_ADMIN 的
        # ⇒ ⇒ **全局 bypass** 才生效 ⇒ ⇒ 与 `create` / `publish` **同口径**。
        actor_roles=list(actor.roles),
    )
    payload = _as_dict(row)   # 见 create_definition 的注释：先序列化再 commit
    await db.commit()
    return ReportDefinitionOut(**payload)


def _as_dict(row) -> dict:
    """ORM 行 → 响应字典。

    `definition_json` 走 JSONB 往返后可能带非 JSON 原生类型（UUID/日期），
    这里交给 Pydantic 再序列化一次，比手工清洗每个键可靠。
    """
    return {
        "def_id": row.def_id,
        "project_id": row.project_id,
        "name": row.name,
        "category": row.category,
        "description": row.description,
        "definition_json": row.definition_json,
        "output_format": row.output_format,
        "max_rows": row.max_rows,
        "version": row.version,
        "status": row.status,
        "shared_with": row.shared_with,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        # --- 「被退回」标记（P10-J · T2 · TODO-197b）---
        # ⚠️ **必须在这里显式列出来** ⇒ ⇒ ⇒ 这份字典是**手写的字段清单**
        # ⇒ ⇒ ⇒ ORM 上加了列而这里没加 ⇒ ⇒ ⇒ 响应里**静默少一个字段**
        # ⇒ ⇒ ⇒ ⇒ ⇒ 前端判据 `rejected_at != null` 会**永远为假**
        # ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ 「被退回」badge **永远不亮**。
        "rejected_at": row.rejected_at,
        "rejected_by": row.rejected_by,
        "reject_reason": row.reject_reason,
    }


# --- b3 版本与审批 -----------------------------------------------------------

#: 可发布/作废的角色 —— ⚠️ **2026-11-23（P10-I · T1 · hermes A-3）**：
#: 此前**这里**与 `definition_service.py::OBSOLETE_ROLES` **各写了一份**
#: 同一组角色 ⇒ ⇒ 改一处忘了另一处**没有任何测试会发现**
#: ⇒ ⇒ 现在**唯一一份**在 `app.core.acl::REVIEW_ROLES`
#: （core 是 api 与 service **都能** import 的那一层 ⇒ ⇒ 层规则：service 不 import api）。
#:
#: SPEC §3.2.2(6) 写「需审核角色审批通过」，没点名 —— 落 REVIEWER（字面对应「审核」）。
#: APPROVER 也放行：P2 的 CONFIG 审批流用的是它，两个审批角色只放一个
#: 会让用户在审批页被拒。


@router.post("/definitions/{def_id}/publish", response_model=ReportDefinitionOut)
async def publish_definition(
    def_id: uuid.UUID, actor: ActorDep, db: DbDep,
) -> ReportDefinitionOut:
    """发布定义（DRAFT → PUBLISHED）。

    角色检查在**查行之前**：审核角色不该靠「哪些定义存在」来试探。
    """
    require_roles(actor, *REVIEW_ROLES)
    # ⚠️ **职责分离在 service 层**（人裁决 2026-11-18 · TODO-172）：
    # ① **禁自审**（创建人自己是 REVIEWER 也不行）② **审核者要对定义的项目
    # 有授权** ③ **公司级模板不做项目判定**（否则永远没人能审）
    # ⇒ ⇒ 端点只负责**角色闸**；判定在 service ⇒ ⇒ 端点漏调也绕不过。
    row = await DefinitionService(db).publish(
        def_id=def_id,
        actor_user_id=actor.user_id,
        actor_roles=list(actor.roles),
    )
    payload = _as_dict(row)
    await db.commit()
    return ReportDefinitionOut(**payload)


class ReportDefinitionRejectRequest(BaseModel):
    """「打回」的请求体 —— **只有原因**（P10-J · T2 · TODO-197b）。"""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="打回原因（**创建人要看得懂要改什么** ⇒ ⇒ 不能为空）",
    )


@router.post("/definitions/{def_id}/reject", response_model=ReportDefinitionOut)
async def reject_definition(
    def_id: uuid.UUID,
    body: ReportDefinitionRejectRequest,
    actor: ActorDep,
    db: DbDep,
) -> ReportDefinitionOut:
    """**打回**一份草稿（P10-J · T2 · TODO-197b · 2026-11-24 人裁四问全定）。

    ## ⚠️ **状态不变** —— 只加「被退回」标记

    人裁 ① = 「退回 DRAFT + 一个『被退回』标记」⇒ ⇒ ⇒ 草稿本来就在 DRAFT
    ⇒ ⇒ ⇒ **9 态机一个字不改** ⇒ ⇒ ⇒ 可见性 / 执行资格 / 列表过滤都不用改。

    ## ⚠️ **打完回它就不在审核队列里了**

    队列口径 = `rejected_at IS NULL` ⇒ ⇒ ⇒ 审核者刚打完回 ⇒ ⇒ 它若还在队列里
    ⇒ ⇒ ⇒ 就是「点了必失败」⇒ ⇒ ⇒ 等创建人改稿（`update()` 清标记）⇒ ⇒ ⇒ 自动回来。

    ## 角色闸在**端点层**（与 `publish` 同款）⇒ ⇒ 职责分离（禁自审 / 项目授权）
    在 **service 层** ⇒ ⇒ ⇒ 端点漏调也绕不过。
    """
    require_roles(actor, *REVIEW_ROLES)
    outcome = await DefinitionService(db).reject(
        def_id=def_id,
        actor_user_id=actor.user_id,
        actor_roles=list(actor.roles),
        actor_username=actor.username,
        reason=body.reason,
    )
    # ⚠️ **响应体在 commit 之前组装**（commit 后 ORM 属性会 expired
    # ⇒ ⇒ ⇒ 再读就是一次隐式 SELECT 落在同步上下文里 ⇒ MissingGreenlet）
    payload = _as_dict(outcome.row)
    # ⚠️ **通知行与业务变更同一事务**（ADR-0049 §①）⇒ ⇒ ⇒ **推送在 commit 之后**
    # ⇒ ⇒ ⇒ 提交前推送 ⇒ ⇒ ⇒ 用户收到一条会被回滚的通知（phantom notification）
    await db.commit()
    await publish(outcome.pending_notifications)
    return ReportDefinitionOut(**payload)


@router.post("/definitions/{def_id}/obsolete", response_model=ReportDefinitionOut)
async def obsolete_definition(
    def_id: uuid.UUID, actor: ActorDep, db: DbDep,
) -> ReportDefinitionOut:
    """作废定义（→ OBSOLETE）。仍可按 ID 追溯，但不再可执行、不进默认列表。

    ⚠️⚠️ **角色闸不在这里**（2026-11-19 · TODO-190 人裁决）：
    端点原来对 `obsolete` 一律 `require_roles(PUBLISH_ROLES)` ⇒ ⇒ **创建人
    （哪怕只是 DESIGNER）连自己的草稿都删不掉** ⇒ ⇒ 与「DRAFT 保留创建人
    自救通道」**直接冲突** ⇒ ⇒ ⇒ 「没人能删草稿」的死角。
    ⇒ ⇒ 现在：**角色闸在 service 层、按状态分档**
    （`obsolete()`：PUBLISHED 要审核角色 · DRAFT 只要创建人）
    ⇒ ⇒ ⇒ 端点只负责**把身份传下去**。
    """
    # ⚠️ **刻意不调 `require_roles`** —— 见上面那段注释。
    # ⚠️ **2026-11-18 · ce-code-review（TODO-192 #4）**：把**身份**传下去
    # ⇒ ⇒ service 层判「作废者对该定义的项目有没有授权」（无权 ⇒ ⇒ 404）
    # ⇒ ⇒ ⇒ 与 `publish()` 的项目授权**同口径**。
    row = await DefinitionService(db).obsolete(
        def_id=def_id, actor_user_id=actor.user_id, actor_roles=list(actor.roles),
    )
    payload = _as_dict(row)
    await db.commit()
    return ReportDefinitionOut(**payload)


# --- b7 执行 -----------------------------------------------------------------


class ReportExecuteRequest(BaseModel):
    """执行请求体。

    全部可选：不传就是「按定义原样执行」。`filters` / `max_rows` 是**临时**
    调整（SPEC §3.2.2(5)），不回写定义，只进执行日志的快照。
    """

    # 联合类型：临时条件既可以是一整个 AND/OR 组，也可以是单个叶子条件
    filters: ReportDefFilterGroup | ReportDefCondition | None = None
    max_rows: int | None = Field(default=None, ge=1, le=MAX_ROWS_CEILING)
    output_format: str | None = None


class ReportExecuteAccepted(BaseModel):
    task_id: str
    def_id: uuid.UUID
    def_version: str
    status: str = "QUEUED"


class ReportExecutionStatus(BaseModel):
    """**按 `task_id` 查执行进度**（b11 时序契约的一环）。

    `report_file_id` 在生成完成前为 `None` —— 那正是「还在跑」的信号。
    前端拿到它就去 `/report/{file_id}/status` 拿文件状态、再下载。

    ## 状态来源（2026-10-13 改，TODO-064）

    此前这里是**合成**的：`report_file_id` 有值 → FINISHED，否则 → RUNNING。
    现在直接读 `report_execution_logs.status`（p8_007 加的列），
    回收器才有地方写下「已僵死 → FAILED」。

    ⚠️ 仍保留 `report_file_id` 那次校正：它是**唯一**证明文件已存在的字段，
    两者理论上一致，不一致时以它为准更安全。
    """

    task_id: str
    def_id: uuid.UUID
    # ⚠️ **枚举**而不是裸 `str`（2026-10-14 修，评审 P3 #28）。
    # FAILED 一直可达，而且它**正是这一列存在的理由**（TODO-064）——
    # 回收器把僵死的行改判成 FAILED。裸 `str` 让 OpenAPI 里没有 enum，
    # 生成的客户端既无法枚举状态、也无法把 FAILED 与未知值区分开；
    # 照旧词表写的客户端会把 FAILED 当成「还在跑」。
    #
    # 此前 docstring 与字段注释都只写了三种状态，FAILED 是可达却没写的那一种。
    status: Literal["QUEUED", "RUNNING", "FINISHED", "FAILED"]
    report_file_id: uuid.UUID | None = None


@router.get("/executions/{task_id}", response_model=ReportExecutionStatus)
async def execution_status(task_id: str, actor: ActorDep,
                           db: DbDep) -> ReportExecutionStatus:
    """轮询执行进度。**查不到就是 404**，不返回占位的 PENDING。

    返回占位值会让前端分不清「任务不存在」（应当立刻停止轮询）与
    「任务还在跑」（应当继续），于是对着一个不存在的任务转到超时。
    """
    row = (await db.execute(
        select(ReportExecutionLog).where(ReportExecutionLog.task_id == task_id)
    )).scalar_one_or_none()
    if row is None:
        raise PcsError(f"执行任务不存在：{task_id}",
                       code="REPORT_EXECUTION_NOT_FOUND", status=404)
    # 可见性：执行日志没有直接的权限列，按**定义**走 —— 复用
    # `DefinitionService.get`（它已内建「DRAFT 仅创建人可见」判定）。
    # 在这里另写一遍可见性规则就等于有两份规则，而两份会漂移。
    await DefinitionService(db).get(def_id=row.def_id, user_id=actor.user_id)
    # ⚠️ 直接读 `row.status`，**不用 `report_file_id IS NULL` 合成**
    # （TODO-064）。合成版分不出「已入队」「正在跑」「已经僵死」三种 ——
    # 而回收器需要给第三种留下位置，否则被它标 FAILED 的行在轮询端点
    # 看起来仍像「还在跑」，前端无限转圈。
    # `report_file_id` 仍以它为准做一次校正：它是**唯一**证明文件已存在的
    # 字段，理论上 status 与它必须一致，不一致时以它为准更安全。
    status = "FINISHED" if row.report_file_id else (row.status or "QUEUED")
    return ReportExecutionStatus(
        task_id=task_id, def_id=row.def_id, status=status,
        report_file_id=row.report_file_id)


@router.post("/definitions/{def_id}/execute",
             response_model=ReportExecuteAccepted, status_code=202)
async def execute_definition_endpoint(
    def_id: uuid.UUID, actor: ActorDep, db: DbDep,
    body: ReportExecuteRequest | None = None,
) -> ReportExecuteAccepted:
    """执行已发布的定义 —— **返回 202 + task_id，不同步出文件**。

    10k 行 PDF ≈ 10 CPU-秒，同步跑会阻塞整个 event loop（b7 决策）。
    实际取数与渲染在 ARQ 任务体里做。
    """
    body = body or ReportExecuteRequest()
    if body.output_format:
        _reject_bad_format(body.output_format)

    svc = DefinitionService(db)
    # ⚠️ **roles 要传下去**（2026-11-19 · TODO-192 #10）—— admin 要能执行
    # 自己无权项目的定义（与 publish / GET 同口径 ⇒ ⇒ 三处不漂）。
    row = await svc.get(def_id=def_id, user_id=actor.user_id,
                       actor_roles=list(actor.roles))

    # ⚠️⚠️ **scope 项目的授权判定（早失败）**（P10-F · TODO-174 · high）
    # ⇒ ⇒ 位置：`row` 取到之后、**落执行日志 / 入队之前**
    # ⇒ ⇒ ⇒ 端点直接 **404**（而不是 202 之后任务失败 ⇒ ⇒ 用户只看到
    # ⇒ ⇒ 「执行失败」⇒ ⇒ 说不清是「没权限」还是「系统坏了」）。
    # ⇒ ⇒ ⚠️ `ReportExecuteRequest` **没有** `project_id` 字段 ⇒ ⇒
    # ⇒ ⇒ scope 只能来自定义 ⇒ ⇒ 与 `execute_definition` 里的算法一致。
    # ⇒ ⇒ 无权 ⇒ ⇒ 404（与「不存在」同形 ⇒ ⇒ 不泄露项目存在性）。
    if row.project_id is not None:
        await require_project_access_or_404(
            db, user_id=actor.user_id, project_id=row.project_id,
            actor_roles=list(actor.roles),
        )

    if row.status != "PUBLISHED":
        # 409 而不是 404：调用方已经通过 `get` 确认自己看得见这个定义，
        # 再用 404 说不存在是撒谎。状态码要说真话。
        raise PcsError(
            f"只有已发布的定义可执行，该定义当前是 {row.status}。",
            code="REPORT_DEFINITION_STATE", status=409,
        )

    from app.services.report import arq_queue

    # ⚠️ **顺序：先落库，再入队**（2026-10-14 修，评审 P1 #3）。
    # 原先反过来（入队 → 建行 → commit），三个窗口全是真故障：
    #   1. worker 抢在 commit 之前跑完并调 `_link_report_file`，而那行还不存在
    #      ⇒ report_file_id 回填丢失、轮询对一个**已经出了文件**的任务回答 404；
    #   2. 端点在 commit 之前失败 ⇒ 文件存在而审计行完全没有；
    #   3. `_link_report_file` 的 UPDATE 没有 rowcount 检查，丢得悄无声息。
    #
    # 顺序反过来就必须**自选** task_id：ARQ 允许 `_job_id`
    # （`arq/connections.py:148`）。否则 task_id 只能由入队返回，
    # 「先落库」就无从谈起 —— 这不是偏好问题，是那个顺序的硬约束。
    task_id = uuid.uuid4().hex

    # ⚠️ **执行日志行在这里建，不在任务体里**（2026-10-13 修，E2E 实测）。
    # 原先由 `execute_definition` 建，于是「202 已返回、worker 还没消费」这段
    # 窗口里轮询端点只能 404 —— 而前端把**任何**错误都当终态失败
    # （`ReportExecutePage`：`catch → stopPolling → setPhase('failed')`）。
    # 实测这个定义要 0.4 秒、真实 10k 行 PDF 约 10 秒（ADR-P8-004），
    # 也就是**每一次**执行都会先报一次失败，而任务其实正在跑并会成功。
    #
    # 端点 docstring 说「查不到就是 404，好让前端分不清不存在与还在跑」——
    # 那个理由成立的前提正是**行从入队就存在**。修法是让前提成真，
    # 而不是让前端去容忍 404：容忍之后 404 又同时意味着两件事。
    #
    # 任务体那边改成**就地更新**这一行（`task_id` 命中即 update），
    # 所以这不会产生第二条日志。
    db.add(ReportExecutionLog(
        def_id=row.def_id, def_version=row.version,
        condition_snapshot={
            "queued_at": dt.datetime.now(dt.UTC).isoformat(),
            "def_id": str(row.def_id),
            "project_id": str(row.project_id or ""),
            "filters": body.filters.model_dump() if body.filters else None,
            "max_rows": body.max_rows,
            "output_format": body.output_format or row.output_format,
            # 快照由任务体在真正执行时补全（含 SelectedFields/SortBy 等），
            # 这一份是「入队时申报了什么」，两者不冲突：快照列只有一个，
            # 任务体覆盖它。⚠️ 覆盖会丢掉申报值 —— 所以申报值也留在
            # `queued_at` 同一层结构里，便于事后区分「申报」与「实际」。
        },
        row_count=0,                       # QUEUED 阶段还没有行数
        output_format=body.output_format or row.output_format,
        executed_by=actor.user_id,
        is_temporary_adjust=body.filters is not None,
        task_id=task_id,                   # 生成前 report_file_id 为 NULL
    ))
    await db.commit()      # 端点负责 commit（与本仓其它写端点一致）
    # ⚠️ 入队在 commit **之后**：这时 worker 无论多快，那一行都在库里了。
    try:
        await arq_queue.enqueue_definition_execution(
            def_id=str(row.def_id), project_id=str(row.project_id or ""),
            user_id=str(actor.user_id),
            # ⚠️ **roles 也要进队列** —— 任务体里那道 scope 授权判定要判
            # ⇒ ⇒ SYSTEM_ADMIN bypass（判据是角色）⇒ ⇒ 没有角色就误伤超级用户。
            roles=list(actor.roles),
            filters=body.filters.model_dump() if body.filters else None,
            max_rows=body.max_rows, output_format=body.output_format,
            job_id=task_id,
        )
    except PcsError:
        # 入队失败：把已经落库的那一行改判 FAILED，否则它会一直挂在
        # QUEUED 上等 15 分钟后被回收器收掉 —— 用户看到的是「等了 15 分钟
        # 才失败」，而真实原因（队列不可用）是当场就该知道的。
        # 同 `/report/generate` 的 `_fail_pending`。
        from sqlalchemy import select as _sel

        stale = (await db.execute(_sel(ReportExecutionLog).where(
            ReportExecutionLog.task_id == task_id))).scalar_one_or_none()
        if stale is not None:
            stale.status = "FAILED"
            stale.condition_snapshot = {
                **(dict(stale.condition_snapshot or {})),
                "enqueue_failed_at": dt.datetime.now(dt.UTC).isoformat(),
                "enqueue_error": "任务未入队（队列不可用）",
            }
            await db.commit()
        raise
    return ReportExecuteAccepted(task_id=task_id, def_id=row.def_id,
                                 def_version=row.version)
