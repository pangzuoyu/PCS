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

from app.models.config_domain import ConfigAsset, ConfigVersion, DocNoSequence, NumberingTemplate
from app.models.enums import ConfigStatus


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


# ---------------------------------------------------------------------------
# Task 5.1 fixture（ReportService.config_asset_status 专用）
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def sample_assets_and_versions(db, make_asset):
    """Task 5.1 测试夹具：覆盖按 category × status 聚合的所有维度。

    数据规模：
    - CATEGORY_2: 3 个独立 asset × 各 1 个 PUBLISHED version → 3 PUBLISHED
    - CATEGORY_3: 1 个 asset × 5 个 version（DRAFT/PENDING/APPROVED/
      PUBLISHED/OBSOLETE 各 1）→ 每个状态各 1

    注：报告按 VERSION 聚合（不取 latest），所以 1 个 asset 多 version 自然
    计数 5 次。
    """
    for _ in range(3):
        await make_asset(
            status=ConfigStatus.PUBLISHED.value,
            category="CATEGORY_2",
        )
    # CATEGORY_3: 1 个 asset，5 个 version 各 status
    asset = ConfigAsset(
        category="CATEGORY_3",
        name=f"cat3-{uuid.uuid4()}",
        current_version="v1",
        status=ConfigStatus.DRAFT.value,
        content_json={},
    )
    db.add(asset)
    await db.flush()
    statuses_in_order = [
        ConfigStatus.DRAFT.value,
        ConfigStatus.PENDING.value,
        ConfigStatus.APPROVED.value,
        ConfigStatus.PUBLISHED.value,
        ConfigStatus.OBSOLETE.value,
    ]
    for i, s in enumerate(statuses_in_order, start=1):
        version = ConfigVersion(
            asset_id=asset.asset_id,
            version_code=f"v{i}",
            content_json={},
            status=s,
        )
        db.add(version)
        await db.flush()


# ---------------------------------------------------------------------------
# Task 5.2 fixture（ReportService.doc_no_sequence_usage 专用）
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def sample_doc_no_sequences(db) -> list[DocNoSequence]:
    """Task 5.2 测试夹具：2 个 NumberingTemplate × 各自 1 个 DocNoSequence。

    数据规模：
    - Template-A（name 字母序在前）：current_value=50
    - Template-B：current_value=30

    返回 list 供 ``sample_doc_no_sequences[0].template_id`` 索引。
    """
    template_a = NumberingTemplate(
        template_name="Template-A",
        description="fixture template A",
        segments_json={"segments": []},
    )
    template_b = NumberingTemplate(
        template_name="Template-B",
        description="fixture template B",
        segments_json={"segments": []},
    )
    db.add_all([template_a, template_b])
    await db.flush()

    seq_a = DocNoSequence(
        project_id=uuid.uuid4(),
        template_id=template_a.template_id,
        scope_key="scope_A",
        current_value=50,
    )
    seq_b = DocNoSequence(
        project_id=uuid.uuid4(),
        template_id=template_b.template_id,
        scope_key="scope_B",
        current_value=30,
    )
    db.add_all([seq_a, seq_b])
    await db.flush()
    return [seq_a, seq_b]


@pytest_asyncio.fixture
async def sample_template_with_zero_counter(db) -> DocNoSequence:
    """Task 5.2 零计数 fixture：1 个 Template + 1 个 DocNoSequence(current_value=0)。

    用于验证 ``HAVING SUM(...) > 0`` 把零计数模板过滤掉 → 该 template 不
    应出现在 doc_no_sequence_usage 结果中。
    """
    template = NumberingTemplate(
        template_name="ZeroCounter",
        description="fixture zero counter",
        segments_json={"segments": []},
    )
    db.add(template)
    await db.flush()

    seq = DocNoSequence(
        project_id=uuid.uuid4(),
        template_id=template.template_id,
        scope_key="scope_zero",
        current_value=0,
    )
    db.add(seq)
    await db.flush()
    return seq
