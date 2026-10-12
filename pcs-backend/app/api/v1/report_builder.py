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

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.schemas.report_builder import (
    ReportBuilderDatasource,
    ReportBuilderDatasourceList,
    ReportBuilderField,
    ReportBuilderJoin,
    ReportDefCondition,
    ReportDefFilterGroup,
    ReportDefinitionList,
    ReportDefinitionOut,
    ReportDefinitionUpsert,
)
from app.services.exceptions import PcsError
from app.services.report import watermark
from app.services.report.datasource_registry import DATASOURCES, JOINS
from app.services.report.definition_service import DefinitionService

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
async def list_definitions(actor: ActorDep, db: DbDep) -> ReportDefinitionList:
    rows = await DefinitionService(db).list(user_id=actor.user_id)
    items = [ReportDefinitionOut(**_as_dict(r)) for r in rows]
    return ReportDefinitionList(items=items, total=len(items))


@router.get("/definitions/{def_id}", response_model=ReportDefinitionOut)
async def get_definition(
    def_id: uuid.UUID, actor: ActorDep, db: DbDep,
) -> ReportDefinitionOut:
    row = await DefinitionService(db).get(def_id=def_id, user_id=actor.user_id)
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
    }


# --- b3 版本与审批 -----------------------------------------------------------

#: 可发布/作废的角色。SPEC §3.2.2(6) 写「需审核角色审批通过」，没点名 ——
#: 落 REVIEWER（字面对应「审核」）。APPROVER 也放行：P2 的 CONFIG 审批流
#: 用的是它，两个审批角色只放一个会让用户在审批页被拒。
PUBLISH_ROLES = ("REVIEWER", "APPROVER", "SYSTEM_ADMIN")


@router.post("/definitions/{def_id}/publish", response_model=ReportDefinitionOut)
async def publish_definition(
    def_id: uuid.UUID, actor: ActorDep, db: DbDep,
) -> ReportDefinitionOut:
    """发布定义（DRAFT → PUBLISHED）。

    角色检查在**查行之前**：审核角色不该靠「哪些定义存在」来试探。
    """
    require_roles(actor, *PUBLISH_ROLES)
    row = await DefinitionService(db).publish(def_id=def_id)
    payload = _as_dict(row)
    await db.commit()
    return ReportDefinitionOut(**payload)


@router.post("/definitions/{def_id}/obsolete", response_model=ReportDefinitionOut)
async def obsolete_definition(
    def_id: uuid.UUID, actor: ActorDep, db: DbDep,
) -> ReportDefinitionOut:
    """作废定义（→ OBSOLETE）。仍可按 ID 追溯，但不再可执行、不进默认列表。"""
    require_roles(actor, *PUBLISH_ROLES)
    row = await DefinitionService(db).obsolete(def_id=def_id)
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
    max_rows: int | None = Field(default=None, ge=1, le=100_000)
    output_format: str | None = None


class ReportExecuteAccepted(BaseModel):
    task_id: str
    def_id: uuid.UUID
    def_version: str
    status: str = "QUEUED"


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
    row = await svc.get(def_id=def_id, user_id=actor.user_id)
    if row.status != "PUBLISHED":
        # 409 而不是 404：调用方已经通过 `get` 确认自己看得见这个定义，
        # 再用 404 说不存在是撒谎。状态码要说真话。
        raise PcsError(
            f"只有已发布的定义可执行，该定义当前是 {row.status}。",
            code="REPORT_DEFINITION_STATE", status=409,
        )

    from app.services.report import arq_queue
    task_id = await arq_queue.enqueue_definition_execution(
        def_id=str(row.def_id), project_id=str(row.project_id or ""),
        user_id=str(actor.user_id),
        filters=body.filters.model_dump() if body.filters else None,
        max_rows=body.max_rows, output_format=body.output_format,
    )
    return ReportExecuteAccepted(task_id=task_id, def_id=row.def_id,
                                 def_version=row.version)
