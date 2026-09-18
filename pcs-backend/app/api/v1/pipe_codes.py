"""管道代码 API（FMT-4 / SUP-002 §11.5/§12）。

端点布局：
- 公司级模板 CRUD + 5 态流：``/pipe-code-templates``
- 项目级配置 CRUD + fork + 5 态流：``/projects/{project_id}/pipe-code-configs``
- 生成/验证：``/pipe-codes/generate`` ``/pipe-codes/validate``
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.services.pipe_code_generator import PipeCodeGenerator
from app.services.pipe_code_template_service import PipeCodeTemplateService

router = APIRouter(tags=["pipe-codes"])


# ---------- 请求/响应模型 ----------


class CreateTemplateRequest(BaseModel):
    template_name: str
    description: str | None = None
    format_definition_json: dict
    version: str | None = "1"


class UpdateTemplateRequest(BaseModel):
    description: str | None = None
    format_definition_json: dict | None = None
    version: str | None = None


class ForkProjectConfigRequest(BaseModel):
    template_id: UUID
    config_name: str


class CreateProjectConfigRequest(BaseModel):
    config_name: str
    format_definition_json: dict


class UpdateProjectConfigRequest(BaseModel):
    format_definition_json: dict


class GenerateRequest(BaseModel):
    project_id: UUID
    input_segments: dict = {}


class ValidateRequest(BaseModel):
    project_id: UUID
    code: str


# ---------- 公司级模板 ----------


@router.get("/pipe-code-templates")
async def list_templates(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.list_company(db)


@router.post("/pipe-code-templates", status_code=201)
async def create_template(
    payload: CreateTemplateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.create_company(
        db, data=payload.model_dump(), actor=user,
    )


@router.get("/pipe-code-templates/{template_id}")
async def get_template(
    template_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.get(db, template_id)


@router.put("/pipe-code-templates/{template_id}")
async def update_template(
    template_id: UUID,
    payload: UpdateTemplateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.update_company(
        db, template_id, data=payload.model_dump(exclude_none=True), actor=user,
    )


@router.delete("/pipe-code-templates/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await PipeCodeTemplateService.delete_company(db, template_id, actor=user)


@router.post("/pipe-code-templates/{template_id}/submit")
async def submit_template(
    template_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.submit(db, template_id, actor=user)


@router.post("/pipe-code-templates/{template_id}/approve")
async def approve_template(
    template_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "REVIEWER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.approve(db, template_id, actor=user)


@router.post("/pipe-code-templates/{template_id}/publish")
async def publish_template(
    template_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "APPROVER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.publish(db, template_id, actor=user)


@router.post("/pipe-code-templates/{template_id}/obsolete")
async def obsolete_template(
    template_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "REVIEWER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.obsolete(db, template_id, actor=user)


# ---------- 项目级配置 ----------


@router.get("/projects/{project_id}/pipe-code-configs")
async def list_project_configs(
    project_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.list_project(db, project_id=project_id)


@router.post(
    "/projects/{project_id}/pipe-code-configs/fork", status_code=201,
)
async def fork_project_config(
    project_id: UUID,
    payload: ForkProjectConfigRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """POST fork 公司模板到项目（201 Created）。

    步骤：
    1. ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN（项目级模板 fork 工艺侧权限）
    2. 调 PipeCodeTemplateService.fork_to_project：取公司模板 →
       查重 (project_id, config_name) 命中 → PROJECT_PIPE_CODE_CONFIG_DUP 409
    3. 新增 ProjectPipeCodeConfig（DRAFT，source_template_id 表 fork 来源，
       snapshot_json 与 format_definition_json 都拷贝模板内容）
    4. service 提交（已 commit），返回新行

    与 create_project_config 区别：本端点基于现有公司模板 fork，源可追溯；
    create_project_config 项目自创，无 source_template_id 与 snapshot。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.fork_to_project(
        db,
        project_id=project_id,
        template_id=payload.template_id,
        config_name=payload.config_name,
        actor=user,
    )


@router.post("/projects/{project_id}/pipe-code-configs", status_code=201)
async def create_project_config(
    project_id: UUID,
    payload: CreateProjectConfigRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """POST 项目内自建管号配置（201 Created）。

    步骤：
    1. ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN
    2. 调 PipeCodeTemplateService.create_project_config：
       查重 (project_id, config_name) 命中 → PROJECT_PIPE_CODE_CONFIG_DUP 409
    3. 新增 ProjectPipeCodeConfig（DRAFT，source_template_id=None 表项目自创，
       snapshot_json=None 表非 fork 来的快照）
    4. format_definition_json 由调用方直接传入（不拷贝模板）
    5. service 提交（已 commit），返回新行

    与 fork_project_config 区别：本端点 source_template_id=None，无 snapshot，
    后续不会被 CIAEngine.propagate_from_source 同步；纯项目本地管号定义。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.create_project_config(
        db,
        project_id=project_id,
        config_name=payload.config_name,
        format_definition_json=payload.format_definition_json,
        actor=user,
    )


@router.put("/projects/{project_id}/pipe-code-configs/{config_id}")
async def update_project_config(
    project_id: UUID,
    config_id: UUID,
    payload: UpdateProjectConfigRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """PUT 替换项目内管号配置 format_definition_json。

    步骤：
    1. ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN
    2. 调 PipeCodeTemplateService.update_project_config：
       - 查行（不存在 → PROJECT_PIPE_CODE_CONFIG_NOT_FOUND 404）
       - 状态校验：仅 DRAFT/PENDING 允许编辑
       - 其他（APPROVED/PUBLISHED/OBSOLETE）→
         PROJECT_PIPE_CODE_CONFIG_LOCKED（409）
       - 整段替换 format_definition_json（非合并）
    3. status 由 submit_project/approve_project/reject_project/
       publish_project/obsolete_project 五态机管控，本端点不动 status
    4. service 提交（已 commit），返回更新行

    与 update_company（公司模板）区别：项目级有锁定检查 + 走 _project_transition
    轻量状态机；公司级直接落库、无锁定（靠 ConfigStateMachine PUBLISH 防御）。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.update_project_config(
        db,
        config_id=config_id,
        format_definition_json=payload.format_definition_json,
        actor=user,
    )


@router.delete(
    "/projects/{project_id}/pipe-code-configs/{config_id}", status_code=204,
)
async def delete_project_config(
    project_id: UUID,
    config_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """DELETE 项目内管号配置（204 No Content，硬删除）。

    步骤：
    1. ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN
    2. 转发到 PipeCodeTemplateService.delete_project_config
    3. service 层做引用检查：若 ProjectPipeCodeSequence（已生成管号序列）
       仍引用此 config_id → PROJECT_PIPE_CODE_CONFIG_IN_USE 409
    4. service 提交（已 commit），204 No Content（FastAPI status_code 控制响应体为空）

    与 obsolete_project_config 区别：obsolete 是软作废（status→OBSOLETE，
    历史记录可查）；delete 是物理删除（行消失，需先无引用）。
    推项目级管号配置场景首选 obsolete；delete 仅用于误建清理。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await PipeCodeTemplateService.delete_project_config(
        db, config_id=config_id, actor=user,
    )


@router.post("/projects/{project_id}/pipe-code-configs/{config_id}/submit")
async def submit_project_config(
    project_id: UUID,
    config_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """POST 项目管号配置 submit（DRAFT → PENDING + Audit）。

    步骤：
    1. ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN
    2. 转发 PipeCodeTemplateService.submit_project → _project_transition('SUBMIT')
    3. 状态校验：DRAFT 才能 SUBMIT，其他 → PROJECT_PIPE_CODE_CONFIG_BAD_TRANSITION 409
    4. 写 Audit（CONFIG_ASSET_SUBMITTED，detail 含 from→to + project_id）

    五态机端点组：submit / approve / reject / publish / obsolete；
    区别：公司模板走 ConfigStateMachine；项目级走 _project_transition 轻量状态机。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.submit_project(
        db, config_id=config_id, actor=user,
    )


@router.post("/projects/{project_id}/pipe-code-configs/{config_id}/approve")
async def approve_project_config(
    project_id: UUID,
    config_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """POST 项目管号配置 approve（PENDING → APPROVED + Audit）。

    步骤：
    1. ACL：REVIEWER / SYSTEM_ADMIN（区别 submit：工艺 vs 审核）
    2. 转发 PipeCodeTemplateService.approve_project → _project_transition('APPROVE')
    3. 状态校验：仅 PENDING 才能 APPROVE，其他 →
       PROJECT_PIPE_CODE_CONFIG_BAD_TRANSITION 409
    4. 写 Audit（CONFIG_ASSET_APPROVED，detail 含 from→to + project_id）

    与 reject_project_config 区别：approve 入 APPROVED；reject 回退到 DRAFT
    并保留 review context 用于后续重提。
    """
    require_roles(user, "REVIEWER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.approve_project(
        db, config_id=config_id, actor=user,
    )


@router.post("/projects/{project_id}/pipe-code-configs/{config_id}/reject")
async def reject_project_config(
    project_id: UUID,
    config_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """POST 项目管号配置 reject（PENDING → DRAFT + Audit + review context）。

    步骤：
    1. ACL：REVIEWER / SYSTEM_ADMIN
    2. 转发 PipeCodeTemplateService.reject_project → _project_transition('REJECT')
    3. 状态校验：仅 PENDING 才能 REJECT，其他 →
       PROJECT_PIPE_CODE_CONFIG_BAD_TRANSITION 409
    4. 写 Audit（CONFIG_ASSET_REJECTED，detail 含 from→to + project_id + review_note）
    5. 回退到 DRAFT（而非 OBSOLETE），工艺方可重提

    与 approve_project_config 区别：approve 入 APPROVED（成功流转）；
    reject 回 DRAFT（带 review context 备注），区别于 obsolete（强制作废）。
    """
    require_roles(user, "REVIEWER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.reject_project(
        db, config_id=config_id, actor=user,
    )


@router.post("/projects/{project_id}/pipe-code-configs/{config_id}/publish")
async def publish_project_config(
    project_id: UUID,
    config_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """POST 项目管号配置 publish（APPROVED → PUBLISHED + Audit）。

    步骤：
    1. ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN
    2. 转发 PipeCodeTemplateService.publish_project → _project_transition('PUBLISH')
    3. 状态校验：仅 APPROVED 才能 PUBLISH，其他 →
       PROJECT_PIPE_CODE_CONFIG_BAD_TRANSITION 409
    4. 写 Audit（CONFIG_ASSET_PUBLISHED，detail 含 from→to + project_id）

    与 approve_project_config 区别：approve 入 APPROVED（审核通过）；
    publish 入 PUBLISHED（生效供 PipeCodeGenerator.generate 选用）。

    项目级 publish 不像公司模板那样需要 APPROVER 角色（PROJECT_PIPE_CODE_CONFIG
    走轻量 _project_transition），PROCESS_CONTROLLER 即可触发。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.publish_project(
        db, config_id=config_id, actor=user,
    )


@router.post("/projects/{project_id}/pipe-code-configs/{config_id}/obsolete")
async def obsolete_project_config(
    project_id: UUID,
    config_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """POST 项目管号配置 obsolete（任何态 → OBSOLETE + Audit，终止态）。

    步骤：
    1. ACL：PROCESS_CONTROLLER / REVIEWER / SYSTEM_ADMIN
    2. 转发 PipeCodeTemplateService.obsolete_project → _project_transition('OBSOLETE')
    3. 状态校验：DRAFT/PENDING/APPROVED/PUBLISHED 均能转 OBSOLETE；
       已经是 OBSOLETE → PROJECT_PIPE_CODE_CONFIG_BAD_TRANSITION 409
    4. 写 Audit（CONFIG_ASSET_OBSOLETED，detail 含 from→to + project_id + reason）

    与 reject_project_config 区别：reject 仅 PENDING→DRAFT（回退）；
    obsolete 任何态都能转 OBSOLETE（终止态，强制作废）。

    与 publish_project_config 区别：publish 是 APPROVED→PUBLISHED（正向生效）；
    obsolete 是任意→OBSOLETE（强制作废）。
    """
    require_roles(user, "PROCESS_CONTROLLER", "REVIEWER", "SYSTEM_ADMIN")
    return await PipeCodeTemplateService.obsolete_project(
        db, config_id=config_id, actor=user,
    )


# ---------- 生成/验证 ----------


@router.post("/pipe-codes/generate")
async def generate_pipe_code(
    payload: GenerateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """POST /pipe-codes/generate：按项目模板生成下一个管号。

    步骤：
    1. ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    2. 调 PipeCodeGenerator.generate：按 payload.project_id 取有效模板，
       解析 input_segments → 走 format_definition_json 合并 + 占位符替换
       → 取 ProjectPipeCodeSequence 自增 1 → 落库
    3. 返回 {"code": code_str}（仅最新生成的字符串）

    与 /pipe-codes/validate 区别：generate 走完整流程 + 落库 + 取号；
    validate 仅 dry-run，不入 DB。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    code = await PipeCodeGenerator.generate(
        db, payload.project_id, payload.input_segments,
    )
    return {"code": code}


@router.post("/pipe-codes/validate")
async def validate_pipe_code(
    payload: ValidateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """POST /pipe-codes/validate：管号格式校验（不落库，仅 dry-run）。

    步骤：
    1. ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    2. 调 PipeCodeGenerator.validate 解析 payload.code（按项目内有效模板）
       → 返回 Outcome{valid, errors, segments}
    3. 异常转 500（保留原 try/except 契约：内部异常统一 500，避免泄漏）
    4. 返回 {valid, errors[], segments[]} — 前端用于实时校验，不入库

    无副作用：不写 Audit、不改 DB（与 /pipe-codes/generate 区别在于
    generate-fn 走完整流程落库 + 取号）。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        outcome = await PipeCodeGenerator.validate(
            db, payload.project_id, payload.code,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {
        "valid": outcome.valid,
        "errors": outcome.errors,
        "segments": outcome.segments,
    }
