"""PipeCodeTemplateService — 公司级 CRUD + 项目级 fork（SUP-002 §11/§12）。

公司级（pipe_code_templates）：5 态 DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE，
复用 ConfigStateMachine（与 SYM-2/PC-3 模式一致）。

项目级（project_pipe_code_configs）：fork 或全新创建；5 态自管轻量状态机
（不挂 ConfigApproval，因 V1.4 §四、#1 修订）。

SIM-37（2026-09-11）：项目级 5 态转移补 audit.write（与 PipeClass 项目级
模式一致；cerebrum Do-Not-Repeat：service 层禁止绕过状态机直接 UPDATE）。

FMT-OPEN-01：项目级 auto_increment 在 service 层用串行获取 sequence_key
（pipe_code_generator.PipeCodeGenerator._next_sequence），由 ORM 层
ProjectPipeCodeSequence 表持久化计数。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import ConfigAsset, ConfigVersion
from app.models.enums import AuditAction, ConfigTransition
from app.models.pipe_code_template import (
    PipeCodeTemplate,
    ProjectPipeCodeConfig,
)
from app.services.audit_service import AuditService
from app.services.config_state_machine import (
    ConfigStateMachine,
    InvalidTransitionError,
)
from app.services.exceptions import PcsError


class PipeCodeTemplateService:
    # ====================================================================
    # 公司级
    # ====================================================================

    @classmethod
    async def list_company(
        cls, db: AsyncSession, *, status: str | None = None,
    ) -> list[PipeCodeTemplate]:
        stmt = select(PipeCodeTemplate)
        if status:
            stmt = stmt.where(PipeCodeTemplate.status == status)
        stmt = stmt.order_by(PipeCodeTemplate.template_name)
        return list((await db.execute(stmt)).scalars())

    @classmethod
    async def get(
        cls, db: AsyncSession, template_id: uuid.UUID,
    ) -> PipeCodeTemplate:
        t = await db.get(PipeCodeTemplate, template_id)
        if t is None:
            raise PcsError(
                f"模板 {template_id} 不存在",
                code="PIPE_CODE_TEMPLATE_NOT_FOUND",
                status=404,
            )
        return t

    @classmethod
    async def create_company(
        cls,
        db: AsyncSession,
        *,
        data: dict[str, Any],
        actor: Any,
    ) -> PipeCodeTemplate:
        """创建公司级管号模板（unique template_name）。

        步骤：
        1. 按 template_name 唯一约束查重，命中 → PIPE_CODE_TEMPLATE_DUP（409）
        2. 挂载 ConfigAsset（CATEGORY_5 / PIPE_CODE_TEMPLATE，V1.4 §0.5
           INT-OPEN-01，资产化追踪）
        3. 插入 PipeCodeTemplate 行（DRAFT 状态 + format_definition_json）
        4. 写 Audit（CONFIG_ASSET_CREATED，detail 含 template_name）

        返回新建的 PipeCodeTemplate（commit 由调用方负责）。
        """
        existing = (
            await db.execute(
                select(PipeCodeTemplate).where(
                    PipeCodeTemplate.template_name == data["template_name"],
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise PcsError(
                f"模板 {data['template_name']} 已存在",
                code="PIPE_CODE_TEMPLATE_DUP",
                status=409,
            )
        # ConfigAsset 挂载（V1.4 §0.5/INT-OPEN-01）
        asset = ConfigAsset(
            category="CATEGORY_5",
            asset_subtype="PIPE_CODE_TEMPLATE",
            name=data["template_name"],
            current_version=str(data.get("version", "1")),
            status="DRAFT",
            created_by=getattr(actor, "user_id", None),
        )
        db.add(asset)
        await db.flush()
        t = PipeCodeTemplate(
            template_name=data["template_name"],
            description=data.get("description"),
            format_definition_json=data["format_definition_json"],
            asset_id=asset.asset_id,
            status="DRAFT",
            version=str(data.get("version", "1")),
            created_by=getattr(actor, "user_id", None),
        )
        db.add(t)
        await AuditService(db).write(
            action=AuditAction.CONFIG_ASSET_CREATED,
            resource_type="CONFIG",
            resource_id=str(asset.asset_id),
            user_id=getattr(actor, "user_id", None),
            detail={
                "template_name": t.template_name,
                "asset_subtype": "PIPE_CODE_TEMPLATE",
            },
        )
        await db.commit()
        return t

    @classmethod
    async def update_company(
        cls,
        db: AsyncSession,
        template_id: uuid.UUID,
        *,
        data: dict[str, Any],
        actor: Any,
    ) -> PipeCodeTemplate:
        t = await cls.get(db, template_id)
        if "description" in data:
            t.description = data["description"]
        if "format_definition_json" in data:
            t.format_definition_json = data["format_definition_json"]
        if "version" in data:
            t.version = data["version"]
        await db.commit()
        return t

    @classmethod
    async def delete_company(
        cls,
        db: AsyncSession,
        template_id: uuid.UUID,
        *,
        actor: Any,
    ) -> None:
        t = await cls.get(db, template_id)
        ref = (
            await db.execute(
                select(ProjectPipeCodeConfig.config_id).where(
                    ProjectPipeCodeConfig.source_template_id == template_id,
                ).limit(1)
            )
        ).first()
        if ref:
            raise PcsError(
                f"模板 {t.template_name} 已被项目 fork，不可删除",
                code="PIPE_CODE_TEMPLATE_IN_USE",
                status=409,
            )
        if t.asset_id:
            asset = await db.get(ConfigAsset, t.asset_id)
            if asset:
                await db.delete(asset)
        await db.delete(t)
        await db.commit()

    @classmethod
    async def submit(
        cls, db: AsyncSession, template_id: uuid.UUID, *, actor: Any,
    ) -> PipeCodeTemplate:
        return await cls._transition(db, template_id, ConfigTransition.SUBMIT, actor)

    @classmethod
    async def approve(
        cls, db: AsyncSession, template_id: uuid.UUID, *, actor: Any,
    ) -> PipeCodeTemplate:
        return await cls._transition(db, template_id, ConfigTransition.APPROVE, actor)

    @classmethod
    async def publish(
        cls, db: AsyncSession, template_id: uuid.UUID, *, actor: Any,
    ) -> PipeCodeTemplate:
        t = await cls._transition(db, template_id, ConfigTransition.PUBLISH, actor)
        # FMT-OPEN-02：模板 PUBLISH 后扫描下游 fork，snapshot 与新内容发散者 → OBSOLETE。
        # _transition 已 commit；CIAEngine 走新事务。
        from app.services.cia_engine import CIAEngine

        n = await CIAEngine(db).propagate_from_source(
            source_type="pipe_code_template",
            source_id=str(template_id),
        )
        if n:
            await db.commit()
        return t

    @classmethod
    async def obsolete(
        cls, db: AsyncSession, template_id: uuid.UUID, *, actor: Any,
    ) -> PipeCodeTemplate:
        return await cls._transition(db, template_id, ConfigTransition.OBSOLETE, actor)

    @classmethod
    async def _transition(
        cls,
        db: AsyncSession,
        template_id: uuid.UUID,
        action: ConfigTransition,
        actor: Any,
    ) -> PipeCodeTemplate:
        t = await cls.get(db, template_id)
        if not t.asset_id:
            raise PcsError(
                f"模板 {t.template_name} 未挂 ConfigAsset",
                code="PIPE_CODE_TEMPLATE_NO_ASSET",
                status=409,
            )
        asset = await db.get(ConfigAsset, t.asset_id)
        version = (
            await db.execute(
                select(ConfigVersion).where(ConfigVersion.asset_id == asset.asset_id)
                .order_by(ConfigVersion.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if version is None:
            version = ConfigVersion(
                asset_id=asset.asset_id,
                version_code=t.version,
                content_json=t.format_definition_json,
                status="DRAFT",
            )
            db.add(version)
            await db.flush()
        sm = ConfigStateMachine(db)
        try:
            await sm.transition(asset, version, action=action, actor=actor)
        except InvalidTransitionError as e:
            raise PcsError(
                str(e), code="PIPE_CODE_TEMPLATE_BAD_TRANSITION", status=409,
            ) from e
        t.status = asset.status
        await db.commit()
        return t

    # ====================================================================
    # 项目级
    # ====================================================================

    @classmethod
    async def fork_to_project(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        template_id: uuid.UUID,
        config_name: str,
        actor: Any,
    ) -> ProjectPipeCodeConfig:
        t = await cls.get(db, template_id)
        # FMT-V08 项目内 config_name 唯一
        dup = (
            await db.execute(
                select(ProjectPipeCodeConfig).where(
                    ProjectPipeCodeConfig.project_id == project_id,
                    ProjectPipeCodeConfig.config_name == config_name,
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise PcsError(
                f"项目内已存在配置名 {config_name}",
                code="PROJECT_PIPE_CODE_CONFIG_DUP",
                status=409,
            )
        cfg = ProjectPipeCodeConfig(
            project_id=project_id,
            source_template_id=template_id,
            config_name=config_name,
            format_definition_json=t.format_definition_json,
            snapshot_json=t.format_definition_json,
            status="DRAFT",
            created_by=getattr(actor, "user_id", None),
        )
        db.add(cfg)
        await db.commit()
        return cfg

    @classmethod
    async def create_project_config(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        config_name: str,
        format_definition_json: dict,
        actor: Any,
    ) -> ProjectPipeCodeConfig:
        dup = (
            await db.execute(
                select(ProjectPipeCodeConfig).where(
                    ProjectPipeCodeConfig.project_id == project_id,
                    ProjectPipeCodeConfig.config_name == config_name,
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise PcsError(
                f"项目内已存在配置名 {config_name}",
                code="PROJECT_PIPE_CODE_CONFIG_DUP",
                status=409,
            )
        cfg = ProjectPipeCodeConfig(
            project_id=project_id,
            source_template_id=None,
            config_name=config_name,
            format_definition_json=format_definition_json,
            snapshot_json=None,
            status="DRAFT",
            created_by=getattr(actor, "user_id", None),
        )
        db.add(cfg)
        await db.commit()
        return cfg

    @classmethod
    async def get_project_config(
        cls,
        db: AsyncSession,
        *,
        config_id: uuid.UUID,
    ) -> ProjectPipeCodeConfig:
        cfg = await db.get(ProjectPipeCodeConfig, config_id)
        if cfg is None:
            raise PcsError(
                f"项目配置 {config_id} 不存在",
                code="PROJECT_PIPE_CODE_CONFIG_NOT_FOUND",
                status=404,
            )
        return cfg

    @classmethod
    async def update_project_config(
        cls,
        db: AsyncSession,
        *,
        config_id: uuid.UUID,
        format_definition_json: dict,
        actor: Any,
    ) -> ProjectPipeCodeConfig:
        cfg = await cls.get_project_config(db, config_id=config_id)
        if cfg.status not in ("DRAFT", "PENDING"):
            raise PcsError(
                f"项目配置 {cfg.config_name} 状态 {cfg.status} 不可编辑",
                code="PROJECT_PIPE_CODE_CONFIG_LOCKED",
                status=409,
            )
        cfg.format_definition_json = format_definition_json
        await db.commit()
        return cfg

    @classmethod
    async def delete_project_config(
        cls,
        db: AsyncSession,
        *,
        config_id: uuid.UUID,
        actor: Any,
    ) -> None:
        cfg = await db.get(ProjectPipeCodeConfig, config_id)
        if cfg is None:
            return
        await db.delete(cfg)
        await db.commit()

    @classmethod
    async def list_project(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
    ) -> list[ProjectPipeCodeConfig]:
        rows = (
            await db.execute(
                select(ProjectPipeCodeConfig).where(
                    ProjectPipeCodeConfig.project_id == project_id,
                ).order_by(ProjectPipeCodeConfig.config_name)
            )
        ).scalars()
        return list(rows)

    @classmethod
    async def submit_project(
        cls, db: AsyncSession, *, config_id: uuid.UUID, actor: Any,
    ) -> ProjectPipeCodeConfig:
        return await cls._project_transition(db, config_id, "SUBMIT", actor)

    @classmethod
    async def approve_project(
        cls, db: AsyncSession, *, config_id: uuid.UUID, actor: Any,
    ) -> ProjectPipeCodeConfig:
        return await cls._project_transition(db, config_id, "APPROVE", actor)

    @classmethod
    async def reject_project(
        cls, db: AsyncSession, *, config_id: uuid.UUID, actor: Any,
    ) -> ProjectPipeCodeConfig:
        return await cls._project_transition(db, config_id, "REJECT", actor)

    @classmethod
    async def publish_project(
        cls, db: AsyncSession, *, config_id: uuid.UUID, actor: Any,
    ) -> ProjectPipeCodeConfig:
        return await cls._project_transition(db, config_id, "PUBLISH", actor)

    @classmethod
    async def obsolete_project(
        cls, db: AsyncSession, *, config_id: uuid.UUID, actor: Any,
    ) -> ProjectPipeCodeConfig:
        return await cls._project_transition(db, config_id, "OBSOLETE", actor)

    # 轻量 5 态映射（不挂 ConfigApproval，因 V1.4 §四、#1）
    _PROJECT_TRANSITIONS: dict[str, tuple[str, str]] = {
        "SUBMIT": ("DRAFT", "PENDING"),
        "APPROVE": ("PENDING", "APPROVED"),
        "REJECT": ("PENDING", "DRAFT"),
        "PUBLISH": ("APPROVED", "PUBLISHED"),
    }

    @classmethod
    async def _project_transition(
        cls,
        db: AsyncSession,
        config_id: uuid.UUID,
        action: str,
        actor: Any,
    ) -> ProjectPipeCodeConfig:
        cfg = await cls.get_project_config(db, config_id=config_id)
        old_status = cfg.status
        if action == "OBSOLETE":
            # OBSOLETE 允许多入口（DRAFT / APPROVED / PUBLISHED）
            if cfg.status in ("DRAFT", "APPROVED", "PUBLISHED"):
                cfg.status = "OBSOLETE"
            else:
                raise PcsError(
                    f"项目配置 {cfg.config_name} 当前 {cfg.status} 不能 OBSOLETE",
                    code="PROJECT_PIPE_CODE_CONFIG_BAD_TRANSITION",
                    status=409,
                )
        else:
            transition = cls._PROJECT_TRANSITIONS.get(action)
            if transition is None:
                raise PcsError(
                    f"未知动作 {action}", code="BAD_ACTION", status=422,
                )
            from_state, to_state = transition
            if cfg.status != from_state:
                raise PcsError(
                    f"项目配置 {cfg.config_name} 当前 "
                    f"{cfg.status} 不能 {action}（期望 {from_state}）",
                    code="PROJECT_PIPE_CODE_CONFIG_BAD_TRANSITION",
                    status=409,
                )
            cfg.status = to_state
        # SIM-37：项目级 5 态转移写审计（cerebrum Do-Not-Repeat：service 层
        # 禁止绕过状态机直接 UPDATE；审计 + 状态机原子化）。
        new_status = cfg.status
        audit_action_map = {
            "SUBMIT": AuditAction.CONFIG_ASSET_SUBMITTED,
            "APPROVE": AuditAction.CONFIG_ASSET_APPROVED,
            "REJECT": AuditAction.CONFIG_ASSET_REJECTED,
            "PUBLISH": AuditAction.CONFIG_ASSET_PUBLISHED,
            "OBSOLETE": AuditAction.CONFIG_ASSET_OBSOLETED,
        }
        await AuditService(db).write(
            action=audit_action_map[action],
            resource_type="PROJECT_PIPE_CODE_CONFIG",
            resource_id=str(cfg.config_id),
            user_id=getattr(actor, "user_id", None),
            detail={
                "from": old_status,
                "to": new_status,
                "action": action,
                "project_id": str(cfg.project_id),
            },
        )
        await db.commit()
        return cfg


__all__ = ["PipeCodeTemplateService"]
