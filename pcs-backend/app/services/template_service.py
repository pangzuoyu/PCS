"""TemplateService — 模板文件上传 + sha256 + Jinja2 渲染（Task 2.6）。

薄包装：TemplateFile CRUD + 本地文件系统写入 + Jinja2 渲染 + 审计。

实现注意（与 brief 偏差，防御性）：
1. TemplateFile.version 列 NOT NULL String(50) 无默认值；upload() 显式填 "v1"。
2. TemplateFile 无 sha256 列；sha 仅编码在文件名 {sha}.{file_name} 中，
   测试通过读回文件验证一致性。
3. 补全 brief 缺失的 AsyncSession / Path / UUID 导入。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

from jinja2 import Environment, StrictUndefined, TemplateError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import TemplateFile
from app.models.enums import AuditAction
from app.models.htri_template import VALID_HTRI_DEVICE_TYPES, HtriTemplateSchema
from app.services.audit_service import AuditService
from app.services.exceptions import PcsError


class TemplateRenderError(Exception):
    """模板渲染失败或查不到 template_id 时抛出。"""


class TemplateService:
    def __init__(self, session: AsyncSession, storage_root: Path):
        self.session = session
        self.storage_root = Path(storage_root)
        self.audit = AuditService(session)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.jinja = Environment(undefined=StrictUndefined)

    async def upload(
        self,
        *,
        asset_id: UUID,
        file_bytes: bytes,
        file_name: str,
        file_type: str,
    ) -> TemplateFile:
        sha = hashlib.sha256(file_bytes).hexdigest()
        path = self.storage_root / f"{sha}.{file_name}"
        path.write_bytes(file_bytes)
        # V1.4 P2-OPEN-005：自动续 template_version_seq
        result = await self.session.execute(
            select(func.coalesce(func.max(TemplateFile.template_version_seq), 0))
        )
        next_seq = (result.scalar() or 0) + 1
        tpl = TemplateFile(
            asset_id=asset_id,
            name=file_name,
            file_type=file_type,
            file_path=str(path),
            placeholders_json={"vars": []},
            version="v1",
            template_version_seq=next_seq,
            status="DRAFT",
        )
        self.session.add(tpl)
        await self.session.flush()
        return tpl

    async def render(self, template_id: UUID, context: dict) -> str:
        tpl = await self.session.get(TemplateFile, template_id)
        if tpl is None:
            raise TemplateRenderError(f"未找到 template_id={template_id}")
        body = Path(tpl.file_path).read_text(encoding="utf-8")
        try:
            return self.jinja.from_string(body).render(**context)
        except TemplateError as e:
            raise TemplateRenderError(str(e)) from e

    async def update_placeholders(
        self,
        template_id: UUID,
        placeholders_json: dict,
        *,
        actor: UUID,
    ) -> TemplateFile:
        tpl = await self.session.get(TemplateFile, template_id)
        if tpl is None:
            raise TemplateRenderError(f"未找到 template_id={template_id}")
        tpl.placeholders_json = placeholders_json
        await self.session.flush()
        await self.audit.write(
            user_id=actor,
            action=AuditAction.CONFIG_VERSION_CREATED,
            resource_type="template_file",
            resource_id=str(template_id),
        )
        return tpl

    async def register_htri_schema(
        self,
        *,
        device_type: str,
        column_count: int,
        version: str = "HTRI-V1.0",
        columns_json: list | None = None,
        source_file_ref: str | None = None,
        tema_type: str | None = None,
    ) -> HtriTemplateSchema:
        """注册 HTRI 解析模板 schema（V1.4 P2-OPEN-005，async instance method 匹配现有签名）"""
        if device_type not in VALID_HTRI_DEVICE_TYPES:
            raise PcsError(
                f"未知 HTRI device_type: {device_type}",
                code="HTRI_INVALID_DEVICE_TYPE",
                status=422,
                details={"valid_types": sorted(VALID_HTRI_DEVICE_TYPES)},
            )
        schema = HtriTemplateSchema(
            device_type=device_type, column_count=column_count,
            columns_json=columns_json or [], version=version,
            source_file_ref=source_file_ref, tema_type=tema_type,
        )
        self.session.add(schema)
        await self.session.flush()
        return schema


# 模块级函数（非实例方法），用于加载 JSON seed 元数据
def load_seed_metadata(template_id: str) -> dict:
    """加载 DETAIL 模板元数据（V1.4 P2-OPEN-005）"""
    seeds_dir = Path(__file__).parent.parent / "seeds" / "templates"
    file_map = {
        "detail_121_a_101": seeds_dir / "detail_121_a_101.json",
        "detail_131_e_102_eor": seeds_dir / "detail_131_e_102_eor.json",
    }
    if template_id not in file_map:
        raise PcsError(f"未知 DETAIL 模板：{template_id}", code="TEMPLATE_NOT_FOUND", status=404)
    return json.loads(file_map[template_id].read_text(encoding="utf-8"))
