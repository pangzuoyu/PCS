"""services 子目录 fixtures（最小集 — Task 2.7.1 将扩展到 9 fixture）。

Task 1.2 (ConfigStateMachine 5 态骨架) 需要：
- `actor`   — AuthUser-like；仅 user_id 字段
- `make_asset` — 创建 ConfigAsset + ConfigVersion 行并返回 bundle
- `db`      — 复用 tests/conftest.py 的 db_session 别名

注：当前 `_make` 返回 `(asset, version)` bundle，因为 `ConfigAsset.current_version` 是
字符串列（不是关系/对象），不能从 asset 直接拿到 ConfigVersion 实例。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import NamedTuple

import pytest
import pytest_asyncio

from app.models.config_domain import ConfigAsset, ConfigVersion


class _AuthUser(NamedTuple):
    """Task 1.2 最小 AuthUser-like；项目内无 AuthUser 类，使用 duck-typing。"""

    user_id: uuid.UUID


@pytest_asyncio.fixture
async def db(db_session) -> AsyncIterator:
    """db_session 别名（brief 使用的命名）。"""
    yield db_session


@pytest.fixture
def actor(user_id) -> _AuthUser:
    """触发者身份。仅暴露 user_id。"""
    return _AuthUser(user_id=user_id)


class _AssetBundle(NamedTuple):
    """make_asset 返回值：asset + version 一并创建供 state machine 使用。"""

    asset: ConfigAsset
    version: ConfigVersion


@pytest_asyncio.fixture
async def make_asset(db):
    """创建 ConfigAsset + ConfigVersion 配对，返回 bundle。

    asset.current_version 设为字符串 version_code（不是 FK，不是关系，
    是 schema 直接锁定的 String(50) 列 — P1 SUP-001 §2.1）。
    """

    async def _make(
        status: str = "DRAFT",
        category: str = "CATEGORY_1",
    ) -> _AssetBundle:
        asset = ConfigAsset(
            category=category,
            name=f"asset-{uuid.uuid4()}",
            current_version="v1",
            status=status,
            content_json={},
        )
        db.add(asset)
        await db.flush()
        version = ConfigVersion(
            asset_id=asset.asset_id,
            version_code="v1",
            content_json={},
            status=asset.status,
        )
        db.add(version)
        await db.flush()
        # 链接 via string column（schema 真实结构）
        asset.current_version = version.version_code
        await db.flush()
        return _AssetBundle(asset=asset, version=version)

    return _make
