from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import ProjectTemplate
from app.schemas.project_template import ProjectTemplateConfig
from app.services.exceptions import PcsError


class ProjectTemplateService:
    @staticmethod
    def validate_config(raw: dict) -> ProjectTemplateConfig:
        """Pydantic v2 验证 default_config_json；失败抛 PcsError(TEMPLATE_CONFIG_INVALID)."""
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
