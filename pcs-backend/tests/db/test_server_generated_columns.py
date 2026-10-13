"""服务端生成列：为什么必须 `await db.refresh(row)`（TODO-049）。

## 这条 bug 的完整故事（三层，每层都骗过人）

**症状**：报表定义改一次返回 500（`MissingGreenlet`）。UPDATE flush 之后
`updated_at`（`onupdate=func.now()`，服务端生成）被标记 expired，
commit 后再读它是一次隐式 SELECT，落在同步上下文里 → 炸。

**第一层骗局 —— 测试替身比被测物更宽容**：
`tests/conftest.py` 的 `db_session` fixture 设了 `expire_on_flush=False`，
生产 factory 没设。于是走 fixture 的单测全绿，走 HTTP 的红。
**替身替掉了缺陷本身**，所以缺陷测不出来。

**第二层骗局 —— 「补上那个设置」不成立**：
看上去只要在生产 factory 也设 `expire_on_flush=False` 就对齐了。实测：

```
expire_on_flush = False
expired after flush: ['updated_at']        ← 照样 expired
read updated_at FAIL -> MissingGreenlet
```

`onupdate=func.now()` 的值是**SQL 表达式在数据库里算出来的**，
SQLAlchemy 无从知道结果，所以 flush 后**必定**标记 expired。
`expire_on_flush` 只管「本来已加载的属性」，管不了服务端表达式列。

⚠️ 这一层是本文件存在的理由：那两条断言都写在别处很容易被"顺手补一个
设置"糊弄过去。这里把它**钉成一条会红的测试**。

## 真正的修法

service 返回 ORM 行前显式 `await db.refresh(row)` —— 一次真实 SELECT，
把服务端算出的值取回来。`definition_service` 的 update/publish/obsolete
已这么做；下面的测试钉住它别被改回去。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.models.report import ReportDefinition


def _row(name: str = "原始名字") -> ReportDefinition:
    return ReportDefinition(
        def_id=uuid.uuid4(), project_id=None, name=name, category="c",
        description="", output_format="pdf", max_rows=100,
        version="0.1.0", status="DRAFT", shared_with="ALL_USERS",
        definition_json={"DataSources": [{"source": "EQUIP_LIST"}],
         "SelectedFields": [{"source": "EQUIP_LIST", "field": "tag_number", "alias": "位号", "order": 0, "visible": True}]},
    )


@pytest.fixture
async def one_table_engine():
    """只建 `report_definitions` 一张表。

    ⚠️ 不是 `Base.metadata.create_all` —— SQLite 渲染不了其他表的 JSONB
    （conftest 有垫片，这里没有）。建一张够测这条规则了。
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: ReportDefinition.__table__.create(c))
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_expire_on_flush_false_does_not_help_server_generated_columns(
        one_table_engine):
    """⚠️ **前车之鉴的钉子**：加 `expire_on_flush=False` 救不了这类列。

    有人（包括本会话）会认为「生产 factory 少了测试 fixture 那个设置，
    补上就修好了」。这条测试让那个信念**当场失效**：即使设了它，
    `updated_at` 依然 expired、依然 MissingGreenlet。
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    class _EofFalse(AsyncSession):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.sync_session.expire_on_flush = False

    factory = async_sessionmaker(one_table_engine, expire_on_commit=False,
                                 class_=_EofFalse)
    async with factory() as s:
        assert s.sync_session.expire_on_flush is False
        row = _row()
        s.add(row)
        await s.flush()
        await s.commit()

        row.name = "改了"
        await s.flush()

        # 关键：设了 expire_on_flush=False，它**仍然** expired
        assert "updated_at" in inspect(row).expired_attributes, \
            ("`updated_at` 没有被标记 expired —— SQLAlchemy 的行为变了？"
             "若真如此，本文件关于「必须 refresh」的论证需要重新审视。")
        with pytest.raises(Exception):
            _ = row.updated_at          # MissingGreenlet


@pytest.mark.asyncio
async def test_refresh_makes_the_column_readable(one_table_engine):
    """真正的修法：`await db.refresh(row)` 之后读得到值。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(one_table_engine, expire_on_commit=False)
    async with factory() as s:
        row = _row()
        s.add(row)
        await s.flush()
        await s.commit()

        row.name = "改了"
        await s.flush()
        assert "updated_at" in inspect(row).expired_attributes

        await s.refresh(row)            # ← definition_service 里的那一行
        assert "updated_at" not in inspect(row).expired_attributes
        assert row.name == "改了"


@pytest.mark.asyncio
async def test_definition_service_update_does_not_trip_missinggreenlet(db_session):
    """⚠️ **端到端**：走 service 层改一次，读返回值不得炸。

    这条是本文件真正的守卫 —— 上面两条是机理，这条是后果。
    机理会变（SQLAlchemy 升级），后果不会。
    """
    from app.services.report.definition_service import DefinitionService

    svc = DefinitionService(db_session)
    user_id = uuid.uuid4()
    created = await svc.create(
        name="QA 名字", category="c", description="",
        output_format="pdf", shared_with="ALL_USERS",
        definition_json={"DataSources": [{"source": "EQUIP_LIST"}],
         "SelectedFields": [{"source": "EQUIP_LIST", "field": "tag_number", "alias": "位号", "order": 0, "visible": True}]},
        user_id=user_id,
    )

    updated = await svc.update(
        def_id=created.def_id, user_id=user_id,
        name="改过的名字", category="c", description="",
        output_format="pdf", max_rows=100, shared_with="ALL_USERS",
        definition_json={"DataSources": [{"source": "EQUIP_LIST"}],
         "SelectedFields": [{"source": "EQUIP_LIST", "field": "tag_number", "alias": "位号", "order": 0, "visible": True}]},
    )

    assert updated.name == "改过的名字"
    # ⚠️ 这一行就是当初炸的地方：读服务端生成的列。
    assert updated.updated_at is not None
