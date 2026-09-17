"""HeatResultsService 测试（P5-4-2 / Task 20）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md Task 20：
- 39 新标量 roundtrip（DICT V3.7 §3.1 字段名映射，SUP-009 §3.1.1-3.1.6）
- 9 旧标量兼容（heat_results 表 P4 上游字段保留）
- 3 新 JSONB 字段（shell_params / tube_params / ache_params）
- tag_number NOT NULL（TaggedRecordMixin 强制）

**Do-Not-Repeat**：`HeatResult`（继承 `TaggedRecordMixin`）: `tag_number`
NOT NULL（string unique per project）+ `project_id` + `workspace_id`。
测试 fixture 必填字段以 `db.add → flush → refresh` 直接构造 ORM，
避免 ORM kwarg 拼装遗漏 NOT NULL。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.calc import HeatResult
from app.models.project import Project, Workspace
from app.services.heat.heat_data_service import (
    HeatCalcInput,
    map_htri_to_heat_input,
    save_heat_calc_result,
)


def _sample_input() -> HeatCalcInput:
    """39 + 9 + 3 JSONB + 5 旧 JSONB 全字段填充样本。"""
    return HeatCalcInput(
        # === 9 旧 ===
        equipment_no="E-201",
        equipment_name="基本手算换热器",
        duty=1_000_000.0,
        effective_area=10.0,
        hot_inlet_pressure=500.0,
        hot_outlet_pressure=480.0,
        cold_inlet_pressure=300.0,
        cold_outlet_pressure=320.0,
        u_overall=500.0,
        # === §3.1.1 基础标识 7 ===
        exchanger_type="BEM",
        orientation="Horizontal",
        units_series=1,
        units_parallel=1,
        shells_per_unit=1,
        total_area_gross=12.5,
        total_area_eff=10.0,
        # === §3.1.2 通用热工 8 ===
        lmtd=42.5,
        mtd_corrected=40.0,
        emtd=38.0,
        overdesign_percent=10.0,
        u_service=450.0,
        u_calculated=500.0,
        u_clean=600.0,
        heat_exchange_area=10.0,
        # === §3.1.4 通用几何 9 ===
        tube_count=150,
        tube_od=19.05,
        tube_id=15.75,
        tube_wall_thickness=1.65,
        tube_length=3.0,
        tube_pitch=25.4,
        tube_layout="30",
        tube_material="SS304",
        tube_passes=2,
        # === §3.1.5 壳程几何 10 ===
        shell_id=600.0,
        shell_design_pressure=1000.0,
        shell_design_temp=200.0,
        baffle_type="PERPEND",
        baffle_cut_percent=25.0,
        baffle_spacing=400.0,
        baffle_inlet_spacing=300.0,
        seal_strip_count=4,
        passlane_seal_rod_count=2,
        impingement_plate="Yes",
        # === §3.1.6 热阻分布 5 ===
        thermal_resistance_shell=30.0,
        thermal_resistance_tube=25.0,
        thermal_resistance_fouling=20.0,
        thermal_resistance_metal=15.0,
        thermal_resistance_bond=10.0,
        # === 3 新 JSONB ===
        shell_params={
            "fluid_name": "hydrocarbon",
            "mass_flow": 5000.0,
            "temp_in": 423.15,
            "temp_out": 383.15,
            "fouling_res": 0.0002,
        },
        tube_params={
            "fluid_name": "cooling_water",
            "mass_flow": 6000.0,
            "temp_in": 308.15,
            "temp_out": 348.15,
        },
        ache_params={
            "fan_count": 2,
            "air_inlet_temp": 308.15,
            "altitude": 100,
            "fin_type": "L-footed",
        },
        # === 5 旧 JSONB（兼容）===
        air_side_json={"altitude_m": 100, "fin_density": 9},
        design_conditions_json={"design_pressure_kpa": 1000},
        enthalpy_table_json={"t_dependence": [293.15, 313.15, 333.15, 353.15]},
        input_json={"src": "htri_xist_v6_basic.txt"},
        output_json={"status": "OK"},
    )


async def _seed_project_workspace(db) -> tuple[uuid.UUID, uuid.UUID]:
    """HeatResult FK 必需：project + workspace（循环依赖处理：ws 先 flush）。"""
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
            project_name="heat 测试项目",
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


# ===== 39 + 9 + JSONB roundtrip =====


async def test_save_39_new_fields_roundtrip(db):
    """39 新标量 + 9 旧 + 3 JSONB 全字段 roundtrip（DICT V3.7 §3.1）。"""
    project_id, workspace_id = await _seed_project_workspace(db)

    saved = await save_heat_calc_result(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number="E-201",
        exchanger_category="SHELL_TUBE",
        inp=_sample_input(),
    )
    await db.commit()

    # 读回
    result = await db.get(HeatResult, saved.heat_exchanger_id)
    assert result is not None

    # 9 旧
    assert result.equipment_no == "E-201"
    assert result.equipment_name == "基本手算换热器"
    assert result.duty == pytest.approx(1_000_000.0)
    assert result.effective_area == pytest.approx(10.0)
    assert result.hot_inlet_pressure == pytest.approx(500.0)
    assert result.u_overall == pytest.approx(500.0)

    # §3.1.1
    assert result.exchanger_type == "BEM"
    assert result.orientation == "Horizontal"
    assert result.shells_per_unit == 1
    assert result.total_area_gross == pytest.approx(12.5)

    # §3.1.2
    assert result.lmtd == pytest.approx(42.5)
    assert result.u_clean == pytest.approx(600.0)
    assert result.heat_exchange_area == pytest.approx(10.0)

    # §3.1.4
    assert result.tube_count == 150
    assert result.tube_od == pytest.approx(19.05)
    assert result.tube_layout == "30"
    assert result.tube_passes == 2

    # §3.1.5
    assert result.shell_id == pytest.approx(600.0)
    assert result.baffle_type == "PERPEND"
    assert result.baffle_cut_percent == pytest.approx(25.0)
    assert result.impingement_plate == "Yes"

    # §3.1.6
    assert result.thermal_resistance_shell == pytest.approx(30.0)
    assert result.thermal_resistance_bond == pytest.approx(10.0)

    # 3 新 JSONB
    assert result.shell_params["fluid_name"] == "hydrocarbon"
    assert result.tube_params["mass_flow"] == pytest.approx(6000.0)
    assert result.ache_params["fan_count"] == 2

    # 5 旧 JSONB（兼容）
    assert result.design_conditions_json["design_pressure_kpa"] == 1000


# ===== 9 旧字段兼容（无新字段时）=====


async def test_save_legacy_9_fields_compat(db):
    """仅设 9 旧字段时落库正常（兼容 P4 上游数据；新字段为 None）。"""
    project_id, workspace_id = await _seed_project_workspace(db)
    legacy = HeatCalcInput(equipment_no="E-OLD", duty=500_000.0)

    saved = await save_heat_calc_result(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number="E-OLD",
        exchanger_category="SHELL_TUBE",
        inp=legacy,
    )
    await db.commit()

    result = await db.get(HeatResult, saved.heat_exchanger_id)
    assert result.equipment_no == "E-OLD"
    assert result.duty == pytest.approx(500_000.0)
    # 新字段为空
    assert result.exchanger_type is None
    assert result.lmtd is None
    assert result.tube_count is None
    assert result.shell_params is None


# ===== tag_number NOT NULL 强制 =====


async def test_save_requires_tag_number(db):
    """未填 tag_number → IntegrityError（TaggedRecordMixin NOT NULL）。"""
    project_id, workspace_id = await _seed_project_workspace(db)
    with pytest.raises(IntegrityError):
        await save_heat_calc_result(
            db,
            project_id=project_id,
            workspace_id=workspace_id,
            tag_number=None,  # type: ignore[arg-type]
            exchanger_category="SHELL_TUBE",
            inp=_sample_input(),
        )


# ===== HTRI → HeatCalcInput 映射（与 Task 19 衔接）=====


async def test_map_htri_to_heat_input_xist_v6_basic():
    """HtriParsedData → HeatCalcInput 字段映射（基本手算样本）。"""
    from app.services.heat.htri_parser import parse_htri

    fixture = (
        __import__("pathlib").Path(__file__).parent
        / "fixtures"
        / "htri_xist_v6_basic.txt"
    )
    htri = parse_htri(fixture)

    inp = map_htri_to_heat_input(
        htri=htri, equipment_no="E-201", equipment_name="HEAT-E-201"
    )

    assert inp.duty == pytest.approx(1_000_000.0)
    assert inp.u_overall == pytest.approx(500.0)
    assert inp.effective_area == pytest.approx(10.0)
    assert inp.tube_count == 150
    assert inp.tube_length == pytest.approx(3.0)
    assert inp.shell_id == pytest.approx(600.0)  # mm（fixture 0.600 m）
    assert inp.baffle_spacing == pytest.approx(400.0)  # mm
    assert inp.shell_params["fluid_name"] == "hot"  # 占位标签，由 mapper 决定
    assert inp.tube_params["fluid_name"] == "cold"


# ===== HTRI → 落库端到端 =====


async def test_save_from_htri_end_to_end(db):
    """HTRI 解析 → HeatCalcInput → 落库 roundtrip（覆盖 P5-4-1 + P5-4-2 衔接）。"""
    from pathlib import Path

    from app.services.heat.htri_parser import parse_htri

    project_id, workspace_id = await _seed_project_workspace(db)
    htri = parse_htri(
        Path(__file__).parent / "fixtures" / "htri_xist_v6_basic.txt"
    )
    inp = map_htri_to_heat_input(
        htri=htri, equipment_no="E-201", equipment_name="HEAT-E-201"
    )

    saved = await save_heat_calc_result(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number="E-201",
        exchanger_category="SHELL_TUBE",
        inp=inp,
    )
    await db.commit()

    result = await db.get(HeatResult, saved.heat_exchanger_id)
    assert result.duty == pytest.approx(1_000_000.0)
    assert result.effective_area == pytest.approx(10.0)
    assert result.tube_count == 150
    assert result.shell_id == pytest.approx(600.0)