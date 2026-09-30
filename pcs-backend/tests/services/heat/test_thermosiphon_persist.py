"""热虹吸循环安装高度落库测试（P5-0-1b T1 / SUP-010 §3.5）。

验证 ThermosiphonCirculationPersistService.persist_calculate：
- ORM 落库 11 业务列（DDL 逐字命名，不带单位后缀）
- 4 JSONB 容器写入 + 服务层补 P11/P12 / avg_density
- formula_ref / input_json / output_json 只在 other_params 内（不入 DDL）
- record_hash 16 hex（ADR-0031 统一收口）
- UNIQUE(project_id, equipment_tag) 重复写入被 DB 拒绝
"""
from __future__ import annotations

import re
import uuid

import pytest

from app.models.project import Project, Workspace
from app.services.heat.thermosiphon_persist_service import (
    ThermosiphonCirculationPersistService,
)

_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


def _input_kwargs() -> dict:
    return {
        "circulation_type": "HORIZONTAL",
        "shell_diameter_m": 1.6,
        "drum_diameter_m": 2.4,
        "drum_liquid_level_m": 1.2,
        "drum_liquid_density_kg_m3": 865.0,
        "shell_avg_density_kg_m3": 500.0,
        "drum_temperature_c": 215.0,
        "inlet_pressure_drop_const_m": 1.1073228721942285,
        "inlet_pressure_drop_coeff": 0.01137,
        "outlet_pressure_drop_const_m": 0.85,
        "outlet_pressure_drop_coeff": 0.015,
        "shell_pressure_drop_const_m": 0.30,
        "shell_pressure_drop_coeff": 0.010,
        "safety_factor": 1.5,
    }


async def _seed_project_workspace(db) -> tuple[uuid.UUID, uuid.UUID]:
    workspace_id = uuid.uuid4()
    db.add(
        Workspace(
            workspace_id=workspace_id,
            workspace_type="FORMAL",
            name=f"ws-{uuid.uuid4().hex[:8]}",
        )
    )
    await db.flush()
    project_id = uuid.uuid4()
    db.add(
        Project(
            project_id=project_id,
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="thermosiphon persist 测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=workspace_id,
        )
    )
    await db.commit()
    return project_id, workspace_id


@pytest.mark.asyncio
async def test_persist_writes_business_columns_and_hash(db):
    """落库 11 业务列 + record_hash 16 hex。"""
    project_id, workspace_id = await _seed_project_workspace(db)
    record = await ThermosiphonCirculationPersistService.persist_calculate(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        equipment_tag="E-106",
        equipment_name="卧式热虹吸蒸汽发生器",
        input_kwargs=_input_kwargs(),
    )
    assert record.thermosiphon_id
    assert record.equipment_tag == "E-106"
    assert record.circulation_type == "HORIZONTAL"
    assert record.installation_height_calc > 0
    assert record.installation_height_final > record.installation_height_calc
    assert record.safety_factor == 1.5
    assert record.check_result == "PASS"
    assert _HASH_RE.match(record.record_hash), record.record_hash


@pytest.mark.asyncio
async def test_persist_fills_jsonb_containers(db):
    """4 JSONB 容器 + 服务层补 P11/P12 / avg_density + formula_ref 落 other_params。"""
    project_id, workspace_id = await _seed_project_workspace(db)
    record = await ThermosiphonCirculationPersistService.persist_calculate(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        equipment_tag="E-206",
        equipment_name=None,
        input_kwargs=_input_kwargs(),
        inlet_pipe_params={"velocity_m_per_s": 2.6377, "inner_diam_m": 0.25},
    )
    # 入口容器保留调用方字段 + 服务层补 P11/P12
    assert record.inlet_pipe_params["velocity_m_per_s"] == 2.6377
    assert record.inlet_pipe_params["pressure_drop_const"] == 1.1073228721942285
    assert record.inlet_pipe_params["pressure_drop_coeff"] == 0.01137
    # 出口 / 壳程容器由服务层补
    assert record.outlet_pipe_params["pressure_drop_const"] == 0.85
    assert record.shell_side_params["avg_density"] == 500.0
    # formula_ref / input_json / output_json 只在 other_params（不入 DDL）
    other = record.other_params
    assert other["formula_ref"]["standard"] == "GPSA"
    assert other["input_json"]["drum_liquid_density_kg_m3"] == 865.0
    assert other["output_json"]["check_result"] == "PASS"
    assert "formula_version" in other["output_json"]


@pytest.mark.asyncio
async def test_persist_preserves_caller_other_params(db):
    """调用方 other_params（XLS 立式 Martinelli 等）不被覆盖丢失。"""
    project_id, workspace_id = await _seed_project_workspace(db)
    record = await ThermosiphonCirculationPersistService.persist_calculate(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        equipment_tag="R-104",
        equipment_name="立式热虹吸蒸汽发生器",
        input_kwargs={**_input_kwargs(), "circulation_type": "VERTICAL"},
        other_params={"martinelli_Xtt": 12.3, "phi": 0.87},
    )
    assert record.circulation_type == "VERTICAL"
    assert record.other_params["martinelli_Xtt"] == 12.3
    assert record.other_params["phi"] == 0.87
    assert "formula_ref" in record.other_params


@pytest.mark.asyncio
async def test_persist_enforces_unique_equipment_tag(db):
    """UNIQUE(project_id, equipment_tag)：同项目重复位号被 DB 拒绝。"""
    from sqlalchemy.exc import IntegrityError

    project_id, workspace_id = await _seed_project_workspace(db)
    await ThermosiphonCirculationPersistService.persist_calculate(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        equipment_tag="E-106",
        equipment_name=None,
        input_kwargs=_input_kwargs(),
    )
    with pytest.raises(IntegrityError):
        await ThermosiphonCirculationPersistService.persist_calculate(
            db,
            project_id=project_id,
            workspace_id=workspace_id,
            equipment_tag="E-106",
            equipment_name=None,
            input_kwargs=_input_kwargs(),
        )
