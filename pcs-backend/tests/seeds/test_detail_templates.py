"""DETAIL 模板资产入库测试（Task 1.10.2, V1.4 P2-OPEN-005）。

3 个测试：
1. test_upload_auto_increments_seq — 验证 TemplateService.upload 自动续号
2. test_detail_121_a_101_metadata_loadable — ACHE 空冷器 33 列元数据
3. test_detail_131_e_102_eor_metadata_loadable — SHELL_TUBE 管壳式 23 列元数据

注：test_upload_auto_increments_seq 需先创建 ConfigAsset（DB 模板文件表 asset_id
存在 FK 到 config_assets，p2_sprint1_config_layer_fix 迁移已生效）。
"""
import uuid
from pathlib import Path

import pytest

from app.db.session import get_async_session_factory
from app.models.config_domain import ConfigAsset
from app.services.template_service import TemplateService


async def _create_asset(session) -> uuid.UUID:
    asset = ConfigAsset(
        category="CATEGORY_1",
        name=f"asset-{uuid.uuid4()}",
        current_version="v1",
        status="DRAFT",
        content_json={},
    )
    session.add(asset)
    await session.flush()
    return asset.asset_id


@pytest.mark.asyncio
async def test_upload_auto_increments_seq():
    """模板上传时 template_version_seq 自动递增（async instance method）"""
    factory = get_async_session_factory()
    async with factory() as session:
        asset_id_1 = await _create_asset(session)
        svc = TemplateService(session=session, storage_root=Path("/tmp/seq_test"))
        first = await svc.upload(
            asset_id=asset_id_1,
            file_bytes=b"x", file_name="tpl1.xlsx", file_type="xlsx",
        )
        await session.commit()
    async with factory() as session:
        asset_id_2 = await _create_asset(session)
        svc = TemplateService(session=session, storage_root=Path("/tmp/seq_test"))
        second = await svc.upload(
            asset_id=asset_id_2,
            file_bytes=b"y", file_name="tpl2.xlsx", file_type="xlsx",
        )
        await session.commit()
    assert second.template_version_seq == first.template_version_seq + 1


def test_detail_121_a_101_metadata_loadable():
    """加载 121-A-101 DETAIL 模板元数据"""
    from app.services.template_service import load_seed_metadata
    metadata = load_seed_metadata("detail_121_a_101")
    assert metadata["device_type"] == "ACHE"  # 空冷器
    assert metadata["column_count"] == 33
    assert metadata["htri_version"]


def test_detail_131_e_102_eor_metadata_loadable():
    from app.services.template_service import load_seed_metadata
    metadata = load_seed_metadata("detail_131_e_102_eor")
    assert metadata["device_type"] == "SHELL_TUBE"  # 管壳式
    assert metadata["column_count"] == 23