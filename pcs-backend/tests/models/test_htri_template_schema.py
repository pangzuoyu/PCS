"""HTRI 解析模板 schema 测试（Task 1.10.3，V1.4 P2-OPEN-005）。

3 个测试：
1. test_register_htri_schema_ache — ACHE 33 列注册
2. test_register_htri_schema_shell_tube — SHELL_TUBE 23 列 + BEM
3. test_register_htri_schema_invalid_device_type — 未知 device_type 抛
   PcsError(code=HTRI_INVALID_DEVICE_TYPE)
"""
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from app.db.session import dispose_engines_async, get_async_session_factory
from app.services.template_service import TemplateService


@pytest_asyncio.fixture(autouse=True)
async def _reset_async_engine() -> AsyncIterator[None]:
    """每个用例 reset 全局 async engine（绑定当前 event loop）。

    `get_async_session_factory()` 是模块级单例，跨 event loop 复用会触发
    "Future attached to a different loop"。每次用例前后 dispose 一次即可。
    """
    await dispose_engines_async()
    yield
    await dispose_engines_async()


@pytest.mark.asyncio
async def test_register_htri_schema_ache():
    factory = get_async_session_factory()
    async with factory() as session:
        svc = TemplateService(session=session, storage_root=Path("/tmp/htri_test"))
        schema = await svc.register_htri_schema(
            device_type="ACHE", column_count=33, version="HTRI-V5.0",
            source_file_ref="121-A-101.xls",
        )
    assert schema.device_type == "ACHE"
    assert schema.column_count == 33

@pytest.mark.asyncio
async def test_register_htri_schema_shell_tube():
    factory = get_async_session_factory()
    async with factory() as session:
        svc = TemplateService(session=session, storage_root=Path("/tmp/htri_test"))
        schema = await svc.register_htri_schema(
            device_type="SHELL_TUBE", column_count=23, version="HTRI-V5.0",
            source_file_ref="131-E-102-EOR.xls", tema_type="BEM",
        )
    assert schema.device_type == "SHELL_TUBE"
    assert schema.tema_type == "BEM"

@pytest.mark.asyncio
async def test_register_htri_schema_invalid_device_type():
    from app.services.exceptions import PcsError
    factory = get_async_session_factory()
    async with factory() as session:
        svc = TemplateService(session=session, storage_root=Path("/tmp/htri_test"))
        with pytest.raises(PcsError) as exc:
            await svc.register_htri_schema(device_type="UNKNOWN", column_count=10)
    assert exc.value.code == "HTRI_INVALID_DEVICE_TYPE"
