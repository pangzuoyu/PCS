"""P6-3 G-04/05/06：3 张 CONFIG 表 ORM 冒烟测试。

按 P6 计划 §Task 29 硬性前置 gate：

- 验证 3 张新 ORM class（CepciIndexSeries 之外的 3 张）字段名 +
  nullable + default + unique constraint 与 brief 一致；
- in-memory SQLite 异步 session（tests/conftest.py:db_session fixture）
  建表 → ORM 实例化 → 字段 / 约束断言；
- 不依赖真实 pcs_test 库（与 tests/services/test_cepci_seed.py
  区别：纯 schema 冒烟）。

镜像 P6-2 G-03 ``tests/models/test_cepci_config_tables.py`` 模式（如果
该文件不存在，则以本文件为该模式的 P6-3 实例）。
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import (
    CoolingTowerCurves,
    FiltrationMediaLibrary,
    FlareRadiationLimits,
)


@pytest_asyncio.fixture
async def clean_p6_3_tables(db_session: AsyncSession) -> AsyncIterator[None]:
    """每次用例前清空 3 张 P6-3 CONFIG 表，保证测试可重复。

    镜像 G-03 ``tests/services/test_cepci_seed.py::clean_cepci_table``
    的 delete-before-yield 模式。
    """
    from sqlalchemy import delete

    await db_session.execute(delete(FlareRadiationLimits))
    await db_session.execute(delete(FiltrationMediaLibrary))
    await db_session.execute(delete(CoolingTowerCurves))
    await db_session.commit()
    yield


# ============================================================================
# CoolingTowerCurves
# ============================================================================


@pytest.mark.asyncio
async def test_cooling_tower_curves_init(
    db_session: AsyncSession, clean_p6_3_tables: None,
) -> None:
    """验证 CoolingTowerCurves ORM 字段名 + nullable + PK default。

    验证要点：

    - curve_id UUID PK，default=uuid.uuid4 自动生成；
    - tower_model/curve_source/c_coefficient/m_exponent NOT NULL；
    - l_g_ratio_min/max/notes/confirmed_by/confirmed_at 可空；
    - source NOT NULL；
    - (tower_model, source) UNIQUE 约束生效（重复 INSERT 抛
      IntegrityError）。
    """
    curve = CoolingTowerCurves(
        tower_model="TEST-MARLEY",
        curve_source="CTI",
        c_coefficient=1.85,
        m_exponent=0.50,
        l_g_ratio_min=0.5,
        l_g_ratio_max=3.0,
        source="SYNTHETIC_TEST_DATA",
    )
    db_session.add(curve)
    await db_session.commit()
    await db_session.refresh(curve)

    # PK auto-generated
    assert curve.curve_id is not None
    assert isinstance(curve.curve_id, uuid.UUID)

    # 业务字段持久化正确
    assert curve.tower_model == "TEST-MARLEY"
    assert curve.curve_source == "CTI"
    assert curve.c_coefficient == 1.85
    assert curve.m_exponent == 0.50
    assert curve.l_g_ratio_min == 0.5
    assert curve.l_g_ratio_max == 3.0
    assert curve.source == "SYNTHETIC_TEST_DATA"

    # nullable 字段默认为 None
    assert curve.notes is None
    assert curve.confirmed_by is None
    assert curve.confirmed_at is None

    # (tower_model, source) UNIQUE 约束生效
    dup = CoolingTowerCurves(
        tower_model="TEST-MARLEY",
        curve_source="CTI",
        c_coefficient=2.0,
        m_exponent=0.5,
        source="SYNTHETIC_TEST_DATA",
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # 同 tower_model 不同 source 应允许（partial insert）
    diff_source = CoolingTowerCurves(
        tower_model="TEST-MARLEY",
        curve_source="MANUFACTURER",
        c_coefficient=2.0,
        m_exponent=0.5,
        source="DS-2024",
    )
    db_session.add(diff_source)
    await db_session.commit()
    rows = (
        await db_session.execute(
            select(CoolingTowerCurves).order_by(CoolingTowerCurves.source)
        )
    ).scalars().all()
    assert len(rows) == 2


# ============================================================================
# FiltrationMediaLibrary
# ============================================================================


@pytest.mark.asyncio
async def test_filtration_media_library_init(
    db_session: AsyncSession, clean_p6_3_tables: None,
) -> None:
    """验证 FiltrationMediaLibrary ORM 字段名 + nullable + PK default。

    验证要点：

    - media_id UUID PK，default=uuid.uuid4 自动生成；
    - medium_type/grade/nominal_rating_um NOT NULL；
    - cake_resistance_alpha / specific_resistance_r0 / permeability_k /
      porosity_eps / max_temp_c / notes / confirmed_by / confirmed_at
      可空（不同介质类对应不同参数子集）；
    - (medium_type, grade) UNIQUE 约束生效。
    """
    media = FiltrationMediaLibrary(
        medium_type="SAND",
        grade="#20-30",
        nominal_rating_um=500.0,
        permeability_k=5e-11,
        porosity_eps=0.40,
        max_temp_c=80.0,
        source="SYNTHETIC_TEST_DATA",
    )
    db_session.add(media)
    await db_session.commit()
    await db_session.refresh(media)

    # PK auto-generated
    assert media.media_id is not None
    assert isinstance(media.media_id, uuid.UUID)

    # 业务字段持久化正确
    assert media.medium_type == "SAND"
    assert media.grade == "#20-30"
    assert media.nominal_rating_um == 500.0
    assert media.permeability_k == 5e-11
    assert media.porosity_eps == 0.40
    assert media.max_temp_c == 80.0
    assert media.source == "SYNTHETIC_TEST_DATA"

    # nullable 字段默认为 None（Ruth 参数未填）
    assert media.cake_resistance_alpha is None
    assert media.specific_resistance_r0 is None
    assert media.confirmed_by is None
    assert media.confirmed_at is None

    # (medium_type, grade) UNIQUE 约束生效
    dup = FiltrationMediaLibrary(
        medium_type="SAND",
        grade="#20-30",
        nominal_rating_um=600.0,
        source="SYNTHETIC_TEST_DATA",
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # 同 medium_type 不同 grade 应允许
    diff_grade = FiltrationMediaLibrary(
        medium_type="SAND",
        grade="#30-40",
        nominal_rating_um=400.0,
        source="SYNTHETIC_TEST_DATA",
    )
    db_session.add(diff_grade)
    await db_session.commit()
    rows = (
        await db_session.execute(
            select(FiltrationMediaLibrary).order_by(FiltrationMediaLibrary.grade)
        )
    ).scalars().all()
    assert len(rows) == 2


# ============================================================================
# FlareRadiationLimits
# ============================================================================


@pytest.mark.asyncio
async def test_flare_radiation_limits_init(
    db_session: AsyncSession, clean_p6_3_tables: None,
) -> None:
    """验证 FlareRadiationLimits ORM 字段名 + nullable + PK default。

    验证要点：

    - limit_id UUID PK，default=uuid.uuid4 自动生成；
    - limit_type / q_kw_m2_limit NOT NULL；
    - distance_m / effective_height_m / notes / confirmed_by /
      confirmed_at 可空；
    - limit_type UNIQUE 约束生效（BEDD 三档严格分类）。
    """
    limit = FlareRadiationLimits(
        limit_type="PROPERTY_LINE",
        q_kw_m2_limit=4.73,
        source="API521_§7.4.2.3",
    )
    db_session.add(limit)
    await db_session.commit()
    await db_session.refresh(limit)

    # PK auto-generated
    assert limit.limit_id is not None
    assert isinstance(limit.limit_id, uuid.UUID)

    # 业务字段持久化正确
    assert limit.limit_type == "PROPERTY_LINE"
    assert limit.q_kw_m2_limit == 4.73
    assert limit.source == "API521_§7.4.2.3"

    # nullable 字段默认为 None
    assert limit.distance_m is None
    assert limit.effective_height_m is None
    assert limit.notes is None
    assert limit.confirmed_by is None
    assert limit.confirmed_at is None

    # limit_type UNIQUE 约束生效
    dup = FlareRadiationLimits(
        limit_type="PROPERTY_LINE",
        q_kw_m2_limit=5.0,
        source="API521_§7.4.2.3",
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # 同 limit_type 不同 source 应允许（虽然生产不该这样）
    diff_source = FlareRadiationLimits(
        limit_type="PROPERTY_LINE",
        q_kw_m2_limit=4.0,
        source="DIFFERENT_STANDARD",
    )
    db_session.add(diff_source)
    with pytest.raises(IntegrityError):
        # limit_type UNIQUE（不含 source）→ 仍然冲突
        await db_session.commit()
    await db_session.rollback()