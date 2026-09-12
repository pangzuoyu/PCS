"""P3.x SIM-33：气相 9 字段 + 液相命名对齐 + SIM-31 JSONB→ORM 迁移。

spec §1.2.1 + ADD-001 §3.5/§3.6：

**液相命名对齐**（path 1: alembic RENAME COLUMN）：
- density → liquid_density
- viscosity_dynamic → liquid_viscosity_dynamic
- viscosity_kinematic → liquid_viscosity_kinematic
- thermal_conductivity → liquid_thermal_conductivity
- specific_heat → liquid_specific_heat
- surface_tension → liquid_surface_tension
- compressibility_factor → liquid_compressibility_factor
- molecular_weight：不动（通用 MW）

**SIM-31 JSONB → ORM**（避免气液不对称）：
- std_liq_density → liquid_std_density
- liquid_mass_rate → liquid_mass_rate
- liq_actual_m3hr → liquid_actual_m3hr

**气相 9 字段**（spec §3.5 C/O）：
- vapor_mass_rate / vapor_actual_m3hr / vapor_normal_m3hr
- vapor_mw / vapor_density / vapor_z
- vapor_cp / vapor_viscosity / vapor_thermal_cond
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, Stream, Workspace

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        return proj

    return _make


def _make_stream(proj: Project, name: str = "S-101") -> Stream:
    return Stream(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        stream_name=name,
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
    )


# ---------------------------------------------------------------------------
# 1. 液相命名对齐：旧字段名不再存在
# ---------------------------------------------------------------------------


def test_liquid_columns_have_new_names():
    """液相物性字段已重命名为 liquid_ 前缀（spec §3.6）。"""
    cols = {c.name for c in Stream.__table__.columns}
    # 新名（必须存在）
    for new in (
        "liquid_density",
        "liquid_viscosity_dynamic",
        "liquid_viscosity_kinematic",
        "liquid_thermal_conductivity",
        "liquid_specific_heat",
        "liquid_surface_tension",
        "liquid_compressibility_factor",
    ):
        assert new in cols, f"液相字段 {new} 不存在（migration 未应用）"

    # 旧名（必须不存在；如存在则 rename 未生效）
    for old in (
        "density",
        "viscosity_dynamic",
        "viscosity_kinematic",
        "thermal_conductivity",
        "specific_heat",
        "surface_tension",
        "compressibility_factor",
    ):
        assert old not in cols, f"液相字段 {old} 仍存在（rename 未生效）"


def test_molecular_weight_unchanged():
    """molecular_weight 保持原名（通用 MW，气液相同，不重命名）。"""
    cols = {c.name for c in Stream.__table__.columns}
    assert "molecular_weight" in cols


# ---------------------------------------------------------------------------
# 2. 气相 9 字段 ORM 列
# ---------------------------------------------------------------------------


def test_vapor_columns_exist():
    """气相 9 字段（C/O）入 ORM 列。"""
    cols = {c.name for c in Stream.__table__.columns}
    for v in (
        "vapor_mass_rate",
        "vapor_actual_m3hr",
        "vapor_normal_m3hr",
        "vapor_mw",
        "vapor_density",
        "vapor_z",
        "vapor_cp",
        "vapor_viscosity",
        "vapor_thermal_cond",
    ):
        assert v in cols, f"气相字段 {v} 不存在（migration 未应用）"


# ---------------------------------------------------------------------------
# 3. SIM-31 JSONB → ORM 迁移
# ---------------------------------------------------------------------------


def test_liquid_jsonb_to_orm_columns_exist():
    """SIM-31 JSONB 3 字段已迁 ORM（避免气液不对称）。"""
    cols = {c.name for c in Stream.__table__.columns}
    for v in (
        "liquid_std_density",
        "liquid_mass_rate",
        "liquid_actual_m3hr",
    ):
        assert v in cols, f"液相字段 {v} 不存在（migration 未应用）"


# ---------------------------------------------------------------------------
# 4. 字段读写 round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_liquid_density_round_trip(db, make_project):
    proj = await make_project()
    stream = _make_stream(proj)
    stream.liquid_density = 950.0
    stream.liquid_viscosity_dynamic = 0.001
    db.add(stream)
    await db.commit()
    loaded = (
        await db.execute(select(Stream).where(Stream.stream_id == stream.stream_id))
    ).scalar_one()
    assert loaded.liquid_density == pytest.approx(950.0, abs=0.01)
    assert loaded.liquid_viscosity_dynamic == pytest.approx(0.001, abs=1e-6)


@pytest.mark.asyncio
async def test_vapor_fields_round_trip(db, make_project):
    """气相 9 字段写入读出。"""
    proj = await make_project()
    stream = _make_stream(proj)
    stream.vapor_mass_rate = 100.0
    stream.vapor_actual_m3hr = 5.0
    stream.vapor_normal_m3hr = 4.2
    stream.vapor_mw = 28.97
    stream.vapor_density = 1.2
    stream.vapor_z = 0.95
    stream.vapor_cp = 1.0
    stream.vapor_viscosity = 1.8e-5
    stream.vapor_thermal_cond = 0.025
    db.add(stream)
    await db.commit()
    loaded = (
        await db.execute(select(Stream).where(Stream.stream_id == stream.stream_id))
    ).scalar_one()
    assert loaded.vapor_mass_rate == 100.0
    assert loaded.vapor_z == pytest.approx(0.95, abs=1e-3)
    assert loaded.vapor_thermal_cond == pytest.approx(0.025, abs=1e-4)


@pytest.mark.asyncio
async def test_sim31_jsonb_to_orm_round_trip(db, make_project):
    """SIM-31 JSONB 3 字段迁 ORM 后可读写。"""
    proj = await make_project()
    stream = _make_stream(proj)
    stream.liquid_std_density = 850.0
    stream.liquid_mass_rate = 1200.0
    stream.liquid_actual_m3hr = 1.5
    db.add(stream)
    await db.commit()
    loaded = (
        await db.execute(select(Stream).where(Stream.stream_id == stream.stream_id))
    ).scalar_one()
    assert loaded.liquid_std_density == 850.0
    assert loaded.liquid_mass_rate == 1200.0
    assert loaded.liquid_actual_m3hr == 1.5


# ---------------------------------------------------------------------------
# 5. composition_normalizer: pack/unpack 已删除（JSONB 不再用）
# ---------------------------------------------------------------------------


def test_composition_normalizer_no_pack_unpack():
    """SIM-33 回调 SIM-31 JSONB 决策，pack/unpack 函数已删除。"""
    from app.services import composition_normalizer

    assert not hasattr(composition_normalizer, "pack_liquid_properties_json")
    assert not hasattr(composition_normalizer, "unpack_liquid_properties_json")


# ---------------------------------------------------------------------------
# 6. molecular_weight 兼容：通用 MW 不重命名
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_molecular_weight_still_writable(db, make_project):
    """molecular_weight（通用）仍可读写（液相对称使用同一字段）。"""
    proj = await make_project()
    stream = _make_stream(proj)
    stream.molecular_weight = 18.015  # 水
    db.add(stream)
    await db.commit()
    loaded = (
        await db.execute(select(Stream).where(Stream.stream_id == stream.stream_id))
    ).scalar_one()
    assert loaded.molecular_weight == 18.015