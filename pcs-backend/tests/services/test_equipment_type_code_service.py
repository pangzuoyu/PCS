"""S1-3 EquipmentTypeCodeService seed 测试（P7-Sprint 1 T1.5）。

覆盖：
1. seed_defaults 幂等（第二次返回 0）
2. seed 后 EquipmentTypeCode 行数 ≥ 30（核心子集；80 全清单留工艺工程师 follow-up）
3. 关键 code 全部登记（P/E/T/V/C/A/M/ST/CT/PSV/PVRV/F — per brief SPEC §3.2.1 (3)）
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipment import EquipmentTypeCode
from app.services.equipment_type_code_service import (
    KEY_TYPE_CODES,
    EquipmentTypeCodeService,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_defaults_creates_key_codes(db_session: AsyncSession):
    """seed_defaults 创建 KEY_TYPE_CODES 全部条目。"""
    count = await EquipmentTypeCodeService.seed_defaults(db_session)

    # 关键 codes 全部登记（per brief + SPEC V1.4 §3.2.1 (3) 核心子集）
    stmt = select(EquipmentTypeCode.type_code).where(
        EquipmentTypeCode.project_id.is_(None),
        EquipmentTypeCode.type_code.in_(KEY_TYPE_CODES),
    )
    found = set((await db_session.execute(stmt)).scalars().all())
    missing = set(KEY_TYPE_CODES) - found
    assert not missing, f"missing key type codes: {missing}"

    # M7 fix: 严格断言 (==31) 替代宽松断言 (>=30)，catch silent seed-list regression
    # 当前 SEED_TYPE_CODES 共 31 entries；扩展/缩减时必须同步更新此断言
    assert count == 31, f"expected 31 SEED_TYPE_CODES entries, got {count}"


@pytest.mark.asyncio
async def test_seed_defaults_is_idempotent(db_session: AsyncSession):
    """seed_defaults 幂等：第二次调用返回 0 行新增。"""
    c1 = await EquipmentTypeCodeService.seed_defaults(db_session)
    c2 = await EquipmentTypeCodeService.seed_defaults(db_session)
    assert c1 >= 30
    assert c2 == 0  # 幂等


@pytest.mark.asyncio
async def test_seed_defaults_categorizes_correctly(db_session: AsyncSession):
    """seed defaults 包含 STATIC/ROTATING/PACKAGE/ELECTRICAL/INSTRUMENT/OTHER 6 类。"""
    await EquipmentTypeCodeService.seed_defaults(db_session)

    stmt = select(EquipmentTypeCode.category).where(
        EquipmentTypeCode.project_id.is_(None)
    )
    cats = set((await db_session.execute(stmt)).scalars().all())
    expected_cats = {"STATIC", "ROTATING", "PACKAGE", "ELECTRICAL", "INSTRUMENT", "OTHER"}
    assert expected_cats.issubset(cats), f"missing categories: {expected_cats - cats}"
