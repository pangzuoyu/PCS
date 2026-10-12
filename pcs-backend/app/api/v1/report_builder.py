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
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.schemas.report_builder import (
    ReportBuilderDatasource,
    ReportBuilderDatasourceList,
    ReportBuilderField,
    ReportBuilderJoin,
    ReportDefinitionList,
    ReportDefinitionOut,
    ReportDefinitionUpsert,
)
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

#: 输出格式白名单。与 `schemas/report.SUPPORTED_OUTPUT_FORMATS` 同源，
#: 但**故意独立取** —— 那边还带着 CSV 的历史包袱（Excel/CSV 走 xlsx 渲染器），
#: 这里只认真能渲染出来的。CSV 落地（b8）后合并。
_RENDERABLE_FORMATS = {"pdf", "xlsx", "docx"}


def _reject_bad_format(fmt: str) -> None:
    """未知输出格式 400。

    不能静默接受：用户在表单里选了 `csv`，定义保存成功、审批通过、
    执行时才失败 —— 那时他已经填完了所有条件。写进来时就拒。
    """
    if fmt not in _RENDERABLE_FORMATS:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"暂不支持输出格式 {fmt!r}，可用：{sorted(_RENDERABLE_FORMATS)}"
            "（CSV 属 b8，本批未落地）",
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
