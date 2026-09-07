from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import PipeClass, ProjectTemplate
from app.models.project_template_pipe_class import ProjectTemplatePipeClass
from app.schemas.project_template import ProjectTemplateConfig
from app.services.exceptions import PcsError


class ProjectTemplateService:
    @staticmethod
    def validate_config(raw: dict) -> ProjectTemplateConfig:
        """Pydantic v2 验证 default_config_json；失败抛 PcsError(TEMPLATE_CONFIG_INVALID)。"""
        try:
            return ProjectTemplateConfig.model_validate(raw)
        except Exception as e:
            raise PcsError(
                f"ProjectTemplate.default_config_json 验证失败：{e}",
                code="TEMPLATE_CONFIG_INVALID",
                status=422,
                details={"validation_error": str(e), "raw_keys": list(raw.keys())},
            ) from e

    @classmethod
    async def load(cls, db: AsyncSession, template_id: UUID) -> ProjectTemplate:
        """加载 ProjectTemplate，自动验证 default_config_json。"""
        tpl = await db.get(ProjectTemplate, template_id)
        if not tpl:
            raise PcsError(
                f"ProjectTemplate {template_id} 不存在",
                code="TEMPLATE_NOT_FOUND",
                status=404,
            )
        if tpl.default_config_json:
            cls.validate_config(tpl.default_config_json)
        return tpl

    # ----- INT-1：模板级默认等级（PC-OPEN-04 自动 fork 入口） -----

    @classmethod
    async def get_default_pipe_class_ids(
        cls, db: AsyncSession, template_id: UUID,
    ) -> list[str]:
        """PC-OPEN-04：取模板默认等级清单（按 class_id 排序）。"""
        rows = (await db.execute(
            select(ProjectTemplatePipeClass.class_id)
            .where(ProjectTemplatePipeClass.template_id == template_id)
            .order_by(ProjectTemplatePipeClass.class_id)
        )).all()
        return [r.class_id for r in rows]

    @classmethod
    async def get_pipe_code_template_id(
        cls, db: AsyncSession, template_id: UUID,
    ) -> UUID | None:
        """取模板指定的默认管道代码模板。"""
        tpl = await cls.load(db, template_id)
        return tpl.pipe_code_template_id

    @classmethod
    async def set_default_pipe_classes(
        cls,
        db: AsyncSession,
        template_id: UUID,
        class_ids: list[str],
        actor,
    ) -> None:
        """替换模板默认等级清单（PC-OPEN-04 写入；替换语义）。"""
        # 1. 校验等级存在（避免 FK 悬空）
        if class_ids:
            rows = (await db.execute(
                select(PipeClass.class_id).where(PipeClass.class_id.in_(class_ids))
            )).all()
            existing = {r.class_id for r in rows}
            missing = set(class_ids) - existing
            if missing:
                raise PcsError(
                    f"等级 {sorted(missing)} 不存在",
                    code="PIPE_CLASS_NOT_FOUND",
                    status=404,
                )
        # 2. 清空旧关联
        await db.execute(
            ProjectTemplatePipeClass.__table__.delete()
            .where(ProjectTemplatePipeClass.template_id == template_id)
        )
        # 3. 写入新关联
        for cid in class_ids:
            db.add(ProjectTemplatePipeClass(template_id=template_id, class_id=cid))
        await db.commit()