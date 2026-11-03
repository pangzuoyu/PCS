"""批次「提交校对」的地基能力（P9B-3b · T1）。

本文件先只放四件**可复用**的小能力（后续 T2 的批次 service 全部依赖它们）：

1. `composition_mole_fraction_total` —— 组成合计口径（**单一来源**）；
2. `get_setting_value` —— 读系统参数（批次上限从这儿取）；
3. `AuditAction.STREAM_BATCH_SUBMITTED` —— 批次审计动作；
4. `build_stream_for_update_stmt` / `select_stream_for_update` —— **唯一**的
   加锁读入口（单条提交与批量提交共用；`populate_existing=True` 是 C-1 的修复点）。

⚠️ 为什么组成口径要抽到 service：批次端点与单条端点**必须同一口径** ⇒
口径写在 router 里时，service 层只能反向 import 路由模块（分层倒挂）⇒ 抽。
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction, StreamSignStatus
from app.models.project import Stream
from app.services.stream_service import composition_mole_fraction_total
from app.services.system_setting_service import get_setting_value

pytestmark = pytest.mark.asyncio


def _stream(**kw) -> Stream:
    """构造一个**不落库**的 Stream（只测组成口径，不碰 DB）。"""
    return Stream(
        stream_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        stream_name="S-1",
        sign_status=StreamSignStatus.DRAFT,
        **kw,
    )


async def test_composition_total_none_means_no_composition():
    """`composition_json = None` ⇒ **跳过**（纯物质，无组成）。"""
    assert composition_mole_fraction_total(_stream(composition_json=None)) is None


async def test_composition_total_empty_object_is_zero():
    """`composition_json = {}` ⇒ 合计 0.0（⇒ 落在范围外 ⇒ **拒绝**，与「未填写」同义）。"""
    assert composition_mole_fraction_total(_stream(composition_json={})) == 0.0


async def test_composition_total_sums_fractions():
    """有内容 ⇒ 合计 = 各组分之和（值域 0~1 的小数，**不是**百分数）。"""
    total = composition_mole_fraction_total(
        _stream(composition_json={"7732-18-5": 0.6, "7440-23-5": 0.387})
    )
    assert total == pytest.approx(0.987)


async def test_get_setting_value_returns_stored_value(db_session: AsyncSession):
    """键存在 ⇒ 返回它的值。"""
    from app.services.system_setting_service import seed_defaults

    await seed_defaults(db_session)
    await db_session.commit()

    assert await get_setting_value(db_session, "stream.batch_submit_limit", default=7) == 100


async def test_get_setting_value_falls_back_to_default(db_session: AsyncSession):
    """键**不存在** ⇒ 返回 `default`（不抛异常 ⇒ 上限读不到时批次仍能跑）。"""
    assert await get_setting_value(db_session, "no.such.key", default=42) == 42


async def test_batch_audit_action_exists():
    """批次审计动作必须**存在**于枚举里（否则写审计时退化成裸字符串 ⇒ 审计页筛不出来）。"""
    assert AuditAction.STREAM_BATCH_SUBMITTED.value == "STREAM_BATCH_SUBMITTED"
