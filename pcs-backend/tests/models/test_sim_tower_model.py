"""P3.x SIM-16: sim_tower_results 表 + COLUMN SUMMARY 解析 测试。

spec §5.5 + audit V2.0 E-1：sim_tower_results 表存档 COLUMN 单元的
- 基础元数据（uid / num_stages / condenser / reboiler / feeds / products）
- 4 类 JSON 数据：tray_data_json / compositions_json / loading_json / rating_json

FK：sim_tower_results.import_id → sim_imports.import_id（ON DELETE CASCADE）
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, Workspace
from app.models.sim_import import SimImport, SimImportStatus, SimImportType
from app.models.sim_tower import SimTowerResult

# ---------------------------------------------------------------------------
# fixtures
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


@pytest_asyncio.fixture
async def make_sim_import(db, make_project):
    async def _make(status=SimImportStatus.PREVIEW) -> SimImport:
        proj = await make_project()
        now = datetime.now(UTC)
        sim_import = SimImport(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            import_type=SimImportType.PROII,
            status=status,
            source_file_name="sample.inp",
            convergence_status="CONVERGED",
            banner_version="V8.5",
            preview_streams_json={"streams": []},
            warnings_json=[],
            created_by=uuid.uuid4(),
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
        db.add(sim_import)
        await db.commit()
        return sim_import

    return _make


# ---------------------------------------------------------------------------
# 模型契约
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sim_tower_result_create_and_persist(db, make_sim_import):
    """sim_tower_results 表可写入 + 读取 + FK 级联到 sim_imports。"""
    sim_import = await make_sim_import()
    tower = SimTowerResult(
        import_id=sim_import.import_id,
        tower_uid="T01",
        tower_name="脱乙烷塔",
        tower_type="COLUMN",
        num_stages=30,
        condenser_type="TOTAL",
        reboiler_type="KETTLE",
        feed_stages_json=[{"stream_id": "F", "stage": 15}],
        product_streams_json=["D", "B"],
        tray_data_json={"stages": [{"stage": i, "temp_k": 300 + i * 0.5} for i in range(1, 31)]},
        compositions_json={"stage_15": {"C2H4": 0.4, "C2H6": 0.6}},
        loading_json={"stage_15": {"vapor_load": 0.7, "liquid_load": 0.5}},
        rating_json={"overall": "OK"},
        is_unreliable=False,
    )
    db.add(tower)
    await db.commit()
    assert tower.tower_id is not None

    # 直接读回
    stmt = select(SimTowerResult).where(SimTowerResult.tower_id == tower.tower_id)
    loaded = (await db.execute(stmt)).scalar_one()
    assert loaded.tower_uid == "T01"
    assert loaded.num_stages == 30
    assert loaded.condenser_type == "TOTAL"
    assert loaded.feed_stages_json == [{"stream_id": "F", "stage": 15}]
    assert loaded.product_streams_json == ["D", "B"]
    assert len(loaded.tray_data_json["stages"]) == 30
    assert loaded.compositions_json["stage_15"]["C2H4"] == 0.4
    assert loaded.rating_json["overall"] == "OK"


@pytest.mark.asyncio
async def test_sim_tower_cascade_on_sim_import_delete(db, make_sim_import):
    """sim_imports 行删除 → sim_tower_results 行 CASCADE 删除。

    注：SQLite in-memory 默认关闭 FK 约束；PG 端 cascade 由迁移 ON DELETE CASCADE 保证。
    本测试改用 FK 元数据契约验证（避免启用 FK 破坏既有依赖）。
    """
    from sqlalchemy import create_engine, inspect

    from app.core.config import get_settings

    eng = create_engine(get_settings().database_url)
    insp = inspect(eng)
    fks = insp.get_foreign_keys("sim_tower_results")
    target = [f for f in fks if f["referred_table"] == "sim_imports"]
    assert len(target) == 1, f"expected 1 FK to sim_imports, got {len(fks)}"
    fk = target[0]
    # PG inspector 把 ondelete 放在 options dict 下
    ondelete = fk.get("options", {}).get("ondelete", "").upper()
    assert ondelete == "CASCADE", f"expected CASCADE, got {ondelete!r}"
    assert sorted(fk["constrained_columns"]) == ["import_id"]
    assert fk["referred_columns"] == ["import_id"]
    eng.dispose()


def test_sim_tower_table_name():
    """表名契约：sim_tower_results（spec §5.5）。"""
    assert SimTowerResult.__tablename__ == "sim_tower_results"
