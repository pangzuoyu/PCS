"""电折标口径按项目产品类别强制 (用户裁决 2026-10-05「按 project 产品类型强制」).

GB 30251-2024 §6.1.5 + 附录A 表A.2 注:
    炼油、乙烯能耗计算中电折标系数选择**等价值**, 其余产品选择**当量值**。

原实现: electricity_value_type 默认 "EQUIVALENT" (当量值), 由调用方任意传。
      POST /util/energy-summary/aggregate 根本不传 → 炼油项目静默用当量值,
      系数差 0.21/0.086 = 2.44 倍, 无任何告警。

本测试锁定新口径:
    Project.product_category ∈ {REFINING, ETHYLENE, OTHER} (CHECK + NOT NULL)
    REFINING / ETHYLENE ⇒ EQUIVALENT_VALUE (0.21 kg标油/kWh)
    其余                      ⇒ EQUIVALENT      (0.086 kg标油/kWh)
    显式传值与产品类别冲突 ⇒ 422 ELECTRICITY_VALUE_TYPE_MISMATCH (fail-closed)
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.enums import ProductCategory
from app.models.project import Project, Workspace
from app.models.util import UtilityPowerItem
from app.services.util.utility_energy_summary_service import (
    derive_electricity_value_type,
    summarize_energy_year,
)

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


async def _make_project(
    db: AsyncSession,
    *,
    product_category: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    """建 Workspace + Project (Project 有 NOT NULL 必填列, 必须先有 workspace)."""
    workspace_id = uuid.uuid4()
    db.add(Workspace(workspace_id=workspace_id, workspace_type="FORMAL", name="WS"))
    project_id = uuid.uuid4()
    db.add(
        Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"P-{project_id.hex[:8]}",
            project_name="test",
            owner_company="test",
            location="test",
            project_type="CHEMICAL",
            design_phase="EXECUTIVE_DESIGN",
            unit_system="SI",
            product_category=product_category,
        )
    )
    await db.commit()
    return project_id, workspace_id


async def _add_electricity(db: AsyncSession, project_id, workspace_id) -> None:
    db.add(
        UtilityPowerItem(
            project_id=project_id,
            workspace_id=workspace_id,
            equipment_tag="P-1",
            motor_power_kw=100.0,
            operating_hours_per_year=1000.0,
            load_factor=1.0,
            annual_consumption_kwh=1000.0,
        )
    )
    await db.commit()


@pytest_asyncio.fixture
async def seeded_factors(db_session: AsyncSession):
    """注入电折标双口径系数 (GB 30251-2024 附录A 表A.1 序号12)."""
    from app.models.config import ConfigEnergyConversionFactor

    db_session.add_all(
        [
            ConfigEnergyConversionFactor(
                energy_type="ELECTRICITY",
                value_type="EQUIVALENT",
                toe_factor=0.086,
                standard_coal_factor=0.122857,
                source="GB_30251_2024_APPENDIX_A",
            ),
            ConfigEnergyConversionFactor(
                energy_type="ELECTRICITY",
                value_type="EQUIVALENT_VALUE",
                toe_factor=0.21,
                standard_coal_factor=0.30,
                source="GB_30251_2024_APPENDIX_A",
            ),
        ]
    )
    await db_session.commit()
    yield


# ---------------------------------------------------------------------------
# 1. ProductCategory enum
# ---------------------------------------------------------------------------


def test_product_category_has_three_values():
    assert {m.value for m in ProductCategory} == {
        "REFINING",
        "ETHYLENE",
        "OTHER",
    }


# ---------------------------------------------------------------------------
# 2. derive_electricity_value_type 纯函数
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("product_category", "expected"),
    [
        ("REFINING", "EQUIVALENT_VALUE"),  # 炼油 — §6.1.5 强制等价值
        ("ETHYLENE", "EQUIVALENT_VALUE"),  # 乙烯 — §6.1.5 强制等价值
        ("OTHER", "EQUIVALENT"),  # 其余产品 — 当量值
        (None, "EQUIVALENT"),  # 无产品类别 → 当量值 (最保守, 等于历史默认)
        ("refining", "EQUIVALENT_VALUE"),  # 大小写不敏感
        ("UNKNOWN_BOGUS", "EQUIVALENT"),  # 未知值不当炼油 (fail-safe 而非 fail-open)
    ],
)
def test_derive_electricity_value_type(product_category, expected):
    assert derive_electricity_value_type(product_category) == expected


# ---------------------------------------------------------------------------
# 3. Project.product_category 列
# ---------------------------------------------------------------------------


def test_project_has_product_category_column():
    cols = Project.__table__.columns
    assert "product_category" in cols
    assert cols["product_category"].nullable is False


def test_project_product_category_has_check_constraint():
    """CHECK 约束: 只允许 3 个枚举值 (防止写入 test/t/CHEMICAL 这类垃圾)."""
    checks = [
        c
        for c in Project.__table__.constraints
        if isinstance(c, __import__("sqlalchemy").CheckConstraint)
    ]
    assert checks, "Project 缺 CheckConstraint"
    joined = " ".join(str(c.sqltext) for c in checks)
    assert "product_category" in joined
    for value in ("REFINING", "ETHYLENE", "OTHER"):
        assert value in joined


# ---------------------------------------------------------------------------
# 4. service: 不传 → 按产品类别推导
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_omitted_defaults_to_refining_equivalent_value(
    db_session, seeded_factors
):
    """炼油项目不传 electricity_value_type ⇒ 自动用等价值 (0.21)."""
    project_id, workspace_id = await _make_project(
        db_session, product_category="REFINING"
    )
    await _add_electricity(db_session, project_id, workspace_id)

    summary = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2026,
    )
    assert summary.electricity_value_type == "EQUIVALENT_VALUE"
    # 1000 kWh × 0.21 = 210 kg标油 = 0.21 t
    assert summary.total_toe == pytest.approx(0.21, rel=1e-6)


@pytest.mark.asyncio
async def test_omitted_defaults_to_other_equivalent(db_session, seeded_factors):
    """非炼油项目不传 ⇒ 当量值 (0.086)."""
    project_id, workspace_id = await _make_project(
        db_session, product_category="OTHER"
    )
    await _add_electricity(db_session, project_id, workspace_id)

    summary = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2026,
    )
    assert summary.electricity_value_type == "EQUIVALENT"
    # 1000 kWh × 0.086 = 86 kg标油 = 0.086 t
    assert summary.total_toe == pytest.approx(0.086, rel=1e-6)


@pytest.mark.asyncio
async def test_ethylene_project_uses_equivalent_value(db_session, seeded_factors):
    """乙烯装置同属 §6.1.5 强制等价值."""
    project_id, workspace_id = await _make_project(
        db_session, product_category="ETHYLENE"
    )
    await _add_electricity(db_session, project_id, workspace_id)

    summary = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2026,
    )
    assert summary.electricity_value_type == "EQUIVALENT_VALUE"


# ---------------------------------------------------------------------------
# 5. service: 显式传值冲突 → 422 (fail-closed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explicit_equivalent_on_refining_raises_422(
    db_session, seeded_factors
):
    """炼油项目显式传当量值 ⇒ 拒绝, 不静默降级."""
    project_id, workspace_id = await _make_project(
        db_session, product_category="REFINING"
    )
    await _add_electricity(db_session, project_id, workspace_id)

    with pytest.raises(PcsError) as exc:
        await summarize_energy_year(
            db=db_session,
            project_id=project_id,
            workspace_id=workspace_id,
            business_year=2026,
            electricity_value_type="EQUIVALENT",
        )
    assert exc.value.code == "ELECTRICITY_VALUE_TYPE_MISMATCH"
    assert exc.value.status == 422
    assert "REFINING" in exc.value.message


@pytest.mark.asyncio
async def test_explicit_equivalent_value_on_other_raises_422(
    db_session, seeded_factors
):
    """非炼油项目显式传等价值 ⇒ 拒绝 (防止虚高能耗)."""
    project_id, workspace_id = await _make_project(
        db_session, product_category="OTHER"
    )
    await _add_electricity(db_session, project_id, workspace_id)

    with pytest.raises(PcsError) as exc:
        await summarize_energy_year(
            db=db_session,
            project_id=project_id,
            workspace_id=workspace_id,
            business_year=2026,
            electricity_value_type="EQUIVALENT_VALUE",
        )
    assert exc.value.code == "ELECTRICITY_VALUE_TYPE_MISMATCH"
    assert exc.value.status == 422


@pytest.mark.asyncio
async def test_explicit_matching_value_passes(db_session, seeded_factors):
    """显式传值与产品类别一致 ⇒ 放行."""
    project_id, workspace_id = await _make_project(
        db_session, product_category="REFINING"
    )
    await _add_electricity(db_session, project_id, workspace_id)

    summary = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2026,
        electricity_value_type="EQUIVALENT_VALUE",
    )
    assert summary.electricity_value_type == "EQUIVALENT_VALUE"


# ---------------------------------------------------------------------------
# 6. 无 Project 行 ⇒ 无产品类别政策, 保持历史宽松 (向后兼容)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_project_row_accepts_explicit_value(db_session, seeded_factors):
    """项目元数据缺失时无口径政策可依 ⇒ 尊重显式传入值 (向后兼容 + warning)."""
    project_id, workspace_id = uuid.uuid4(), uuid.uuid4()
    await _add_electricity(db_session, project_id, workspace_id)

    summary = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2026,
        electricity_value_type="EQUIVALENT_VALUE",
    )
    assert summary.electricity_value_type == "EQUIVALENT_VALUE"
