"""CoefficientService tests (Task 2.5).

CRUD + 批量修改 + 审计落库。

Schema 适应：
- CoefficientTable.version 是 NOT NULL String(50)；fixture 必须显式填充。
- sample_table 是本地 fixture（每用例一个新 UUID 名字 + commit/rollback 隔离），
  留给 Task 2.7.1 conftest 整体改写时再上提。
- AuditLog.resource_id 列是 String(100)，存的是 str(uuid)；
  brief 给的查询 `resource_id == uuid_object` 由 SA 端走 bind processor 转字符串。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.config_domain import CoefficientTable
from app.models.enums import AuditAction
from app.models.system import AuditLog
from app.services.coefficient_service import (
    CoefficientNotFoundError,
    CoefficientService,
)


@pytest_asyncio.fixture
async def sample_table(db) -> AsyncIterator[CoefficientTable]:
    """每个用例一份 CoefficientTable（独立 UUID 名 + 不 commit）。"""
    table = CoefficientTable(
        asset_id=uuid.uuid4(),
        name=f"sample-{uuid.uuid4()}",
        applicable_range="0<T<200°C",
        data_json={
            "headers": ["row_label", "value1", "unit"],
            "rows": [["condition_A", 1.0, "MPa"]],
        },
        version="v1",
        status="DRAFT",
    )
    db.add(table)
    await db.flush()
    yield table


async def test_create_table(db):
    svc = CoefficientService(db)
    table = await svc.create_table(
        asset_id=uuid.uuid4(),
        name="摩阻系数",
        data_json={
            "headers": ["row_label", "value1", "unit"],
            "rows": [["condition_A", 1.0, "MPa"]],
        },
        applicable_range="0<T<200°C",
    )
    assert table.table_id is not None
    assert table.data_json["headers"][0] == "row_label"


async def test_bulk_update_replaces_data_json(db, sample_table):
    svc = CoefficientService(db)
    new_data = {"headers": ["x"], "rows": [[1.0]], "applicable_range": None}
    updated = await svc.bulk_update(sample_table.table_id, new_data, actor=uuid.uuid4())
    assert updated.data_json["headers"] == ["x"]
    # 审计写入
    audit = (
        await db.execute(
            select(AuditLog).where(AuditLog.resource_id == str(sample_table.table_id))
        )
    ).scalars().first()
    assert audit is not None
    assert audit.action == AuditAction.CONFIG_VERSION_CREATED


async def test_bulk_update_unknown_table_raises(db):
    svc = CoefficientService(db)
    with pytest.raises(CoefficientNotFoundError):
        await svc.bulk_update(uuid.uuid4(), {}, actor=uuid.uuid4())


async def test_query_returns_table(db, sample_table):
    svc = CoefficientService(db)
    t = await svc.query(sample_table.table_id)
    assert t.name == sample_table.name