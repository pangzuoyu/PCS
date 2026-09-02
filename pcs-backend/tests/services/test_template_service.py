"""TemplateService tests (Task 2.6).

文件上传 + sha256 + Jinja2 占位符渲染。

Schema 适应：
- TemplateFile.version 是 NOT NULL String(50)；fixture 必须显式填充。
- TemplateFile 没有 sha256 列（sha 编码在文件名 {sha}.{file_name} 中）；
  因此 sha256 验证通过读回文件并比对字节完成，而非 tpl.sha256 属性。
- sample_template 是本地 fixture（每用例一个新 UUID），留给 Task 2.7.1 conftest
  整体改写时再上提。
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from app.models.config_domain import TemplateFile
from app.services.template_service import TemplateRenderError, TemplateService


@pytest_asyncio.fixture
async def sample_template(db) -> AsyncIterator[TemplateFile]:
    """每个用例一份 TemplateFile（独立 UUID + 不 commit）。

    模板内容已写入 tmp_path，render() 可直接读取。
    """
    file_bytes = b"<html>{{title}}</html>"
    sha = hashlib.sha256(file_bytes).hexdigest()
    # 通过 storage_root 路径契约生成文件（与 TemplateService.upload 一致）
    file_name = "report.html.j2"
    storage_root = uuid.uuid4().hex  # 占位，实际 render 时通过 tmp_path 重写
    file_path = f"{storage_root}/{sha}.{file_name}"
    tpl = TemplateFile(
        asset_id=uuid.uuid4(),
        name=file_name,
        file_type="html",
        file_path=file_path,
        placeholders_json={"vars": ["title"]},
        version="v1",  # 防御性：model.version NOT NULL String(50)
        status="DRAFT",
    )
    db.add(tpl)
    await db.flush()
    yield tpl


async def test_upload_writes_file_and_records_sha256(db, tmp_path):
    svc = TemplateService(db, storage_root=tmp_path)
    file_bytes = b"<html>{{title}}</html>"
    _ = await svc.upload(
        asset_id=uuid.uuid4(),
        file_bytes=file_bytes,
        file_name="report.html.j2",
        file_type="html",
    )
    # sha256 仅作为文件名一部分落盘；通过读回文件验证完整性
    expected_sha = hashlib.sha256(file_bytes).hexdigest()
    stored = (tmp_path / f"{expected_sha}.report.html.j2").read_bytes()
    assert stored == file_bytes


async def test_render_substitutes_placeholders(db, tmp_path, sample_template):
    # 关键：sample_template.file_path 指向 tmp_path 才能 render() 读得到
    file_bytes = b"<html>{{title}}</html>"
    file_name = sample_template.name
    expected_sha = hashlib.sha256(file_bytes).hexdigest()
    file_path = tmp_path / f"{expected_sha}.{file_name}"
    file_path.write_bytes(file_bytes)
    sample_template.file_path = str(file_path)
    await db.flush()

    svc = TemplateService(db, storage_root=tmp_path)
    rendered = await svc.render(sample_template.template_id, {"title": "P&ID Report"})
    assert "P&ID Report" in rendered


async def test_render_unknown_placeholder_raises(db, tmp_path, sample_template):
    file_bytes = b"<html>{{title}}</html>"
    file_name = sample_template.name
    expected_sha = hashlib.sha256(file_bytes).hexdigest()
    file_path = tmp_path / f"{expected_sha}.{file_name}"
    file_path.write_bytes(file_bytes)
    sample_template.file_path = str(file_path)
    await db.flush()

    svc = TemplateService(db, storage_root=tmp_path)
    with pytest.raises(TemplateRenderError):
        await svc.render(sample_template.template_id, {"undefined_var": 1})
