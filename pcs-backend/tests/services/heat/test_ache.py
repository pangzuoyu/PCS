"""ACHE 空冷器 + 焓值表 service 测试（P5-4-3 / Task 21）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md Task 21：
- `ache_params` JSONB 列写入读出（fan_count/fan_power/bundle_area/
  air_inlet_temp/altitude/fin/tube_nozzle/air_side_resistance_dist）
- `enthalpy_table_json` 多温度点物性 + Licensor 元数据（P5-OPEN-004）
- 焓值表 ≥10 温度点强校验（覆盖 LOW/AMBIENT/OPERATING 三段区间）
- save_ache_params / save_enthalpy_table 通过 heat_id 更新已落库 HeatResult

**Do-Not-Repeat**：HeatResult（继承 TaggedRecordMixin）: `tag_number`
NOT NULL（string unique per project）+ `project_id` + `workspace_id`。
fixture 必填字段以 `db.add → flush → refresh` 直接构造 ORM，
避免 ORM kwarg 拼装遗漏 NOT NULL。
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models.calc import HeatResult
from app.models.project import Project, Workspace
from app.services.heat.heat_data_service import (
    AcheParams,
    EnthalpyTable,
    EnthalpyTableEntry,
    HeatCalcInput,
    save_ache_params,
    save_enthalpy_table,
    save_heat_calc_result,
)

# ===== Fixtures =====


def _ache_params_sample() -> AcheParams:
    return AcheParams(
        fan_count=4,
        fan_power_kw=22.0,
        bundle_area_m2=125.0,
        air_inlet_temp_k=308.15,
        altitude_m=150.0,
        fin_type="L-footed",
        tube_nozzle_count=8,
        air_side_resistance_dist={
            "intake": 25.0,
            "bundle": 180.0,
            "plenum": 50.0,
            "discharge": 20.0,
        },
    )


def _enthalpy_table_sample(n: int = 10) -> EnthalpyTable:
    """生成 n 个温度点焓值样本（温度等步长 280K→360K）。"""
    fluid = "n-butane"
    t_start, t_end = 280.0, 360.0
    step = (t_end - t_start) / (n - 1)
    entries = [
        EnthalpyTableEntry(
            t_k=t_start + i * step,
            h_j_per_kg=1.8e3 + i * 2.1e3,
            cp_j_per_kg_k=2050.0 + i * 12.0,
            phase="LIQUID" if i < 5 else "TWO_PHASE" if i < 7 else "VAPOR",
        )
        for i in range(n)
    ]
    return EnthalpyTable(
        fluid_name=fluid,
        licensor="AspenTech",
        source_doc="Aspen Plus v12 NIST TDE 2024",
        valid_from=date(2024, 1, 1),
        valid_to=None,
        entries=entries,
    )


async def _seed_heat_result(db) -> tuple[uuid.UUID, uuid.UUID, HeatResult]:
    """HeatResult + 配套 project/workspace 落库。返回 (project_id, ws_id, record)。"""
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
            project_name="ache 测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=workspace_id,
        )
    )
    await db.commit()

    record = await save_heat_calc_result(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number="ACH-101",
        exchanger_category="AIR_COOL",
        inp=HeatCalcInput(equipment_no="ACH-101", duty=2_000_000.0),
    )
    await db.commit()
    return project_id, workspace_id, record


# ===== ACHE 字段 JSONB roundtrip =====


async def test_save_ache_params_roundtrip(db):
    """AcheParams → ache_params JSONB 列写读一致。"""
    _, _, record = await _seed_heat_result(db)

    await save_ache_params(
        db,
        heat_exchanger_id=record.heat_exchanger_id,
        params=_ache_params_sample(),
    )
    await db.commit()

    result = await db.get(HeatResult, record.heat_exchanger_id)
    assert result is not None
    assert result.ache_params is not None
    assert result.ache_params["fan_count"] == 4
    assert result.ache_params["fan_power_kw"] == pytest.approx(22.0)
    assert result.ache_params["bundle_area_m2"] == pytest.approx(125.0)
    assert result.ache_params["air_inlet_temp_k"] == pytest.approx(308.15)
    assert result.ache_params["altitude_m"] == pytest.approx(150.0)
    assert result.ache_params["fin_type"] == "L-footed"
    assert result.ache_params["tube_nozzle_count"] == 8
    # air_side_resistance_dist 嵌套 dict
    assert result.ache_params["air_side_resistance_dist"]["intake"] == pytest.approx(25.0)
    assert result.ache_params["air_side_resistance_dist"]["discharge"] == pytest.approx(20.0)


# ===== 焓值表 ≥10 温度点 =====


async def test_save_enthalpy_table_10_points_ok(db):
    """10 温度点焓值表落库成功（覆盖 LIQUID/TWO_PHASE/VAPOR 三段）。"""
    _, _, record = await _seed_heat_result(db)
    table = _enthalpy_table_sample(n=10)

    await save_enthalpy_table(
        db,
        heat_exchanger_id=record.heat_exchanger_id,
        table=table,
    )
    await db.commit()

    result = await db.get(HeatResult, record.heat_exchanger_id)
    assert result.enthalpy_table_json is not None
    payload = result.enthalpy_table_json
    assert payload["fluid_name"] == "n-butane"
    assert payload["licensor"] == "AspenTech"
    assert payload["source_doc"] == "Aspen Plus v12 NIST TDE 2024"
    assert payload["valid_from"] == "2024-01-01"
    assert payload["valid_to"] is None
    assert len(payload["entries"]) == 10
    # 三段 phase 都有
    phases = {e["phase"] for e in payload["entries"]}
    assert phases == {"LIQUID", "TWO_PHASE", "VAPOR"}
    # 第 1 个 entry 字段透传
    assert payload["entries"][0]["t_k"] == pytest.approx(280.0)
    assert payload["entries"][0]["h_j_per_kg"] == pytest.approx(1.8e3)


def test_enthalpy_table_rejects_under_10_points():
    """焓值表 < 10 温度点 → ValueError（强校验：覆盖低温/环境/操作三段）。"""
    with pytest.raises(ValueError, match="≥10"):
        EnthalpyTable(
            fluid_name="propane",
            licensor="AspenTech",
            source_doc="Aspen Plus v12",
            valid_from=date(2024, 1, 1),
            valid_to=None,
            entries=[
                EnthalpyTableEntry(
                    t_k=300.0 + i * 10.0,
                    h_j_per_kg=1.0e3 + i * 1.0e3,
                    cp_j_per_kg_k=2000.0,
                    phase="LIQUID",
                )
                for i in range(9)  # 9 个 → 拒绝
            ],
        )


async def test_enthalpy_table_licensor_metadata_passthrough(db):
    """Licensor 元数据透传（P5-OPEN-004 焓值来自 Licensor）。"""
    _, _, record = await _seed_heat_result(db)
    table = EnthalpyTable(
        fluid_name="propane",
        licensor="HTRI",
        source_doc="HTRI Xist v6.0 NIST TDE 2024",
        valid_from=date(2024, 6, 1),
        valid_to=date(2025, 12, 31),
        entries=[
            EnthalpyTableEntry(
                t_k=230.0 + i * 15.0,
                h_j_per_kg=2.0e3 + i * 1.5e3,
                cp_j_per_kg_k=2100.0,
                phase="VAPOR",
            )
            for i in range(10)
        ],
    )

    await save_enthalpy_table(
        db,
        heat_exchanger_id=record.heat_exchanger_id,
        table=table,
    )
    await db.commit()

    result = await db.get(HeatResult, record.heat_exchanger_id)
    assert result.enthalpy_table_json["licensor"] == "HTRI"
    assert result.enthalpy_table_json["valid_to"] == "2025-12-31"


# ===== 边界 =====


async def test_save_ache_params_nonexistent_heat_raises(db):
    """对不存在的 heat_id 更新 → 抛 ValueError。"""
    fake_id = uuid.uuid4()
    with pytest.raises(ValueError, match="not found"):
        await save_ache_params(
            db,
            heat_exchanger_id=fake_id,
            params=_ache_params_sample(),
        )


async def test_ache_and_enthalpy_independent_writes(db):
    """ache_params 与 enthalpy_table_json 独立可写（互不污染）。"""
    _, _, record = await _seed_heat_result(db)

    # 仅写 ache_params
    await save_ache_params(
        db,
        heat_exchanger_id=record.heat_exchanger_id,
        params=_ache_params_sample(),
    )
    await db.commit()
    mid = await db.get(HeatResult, record.heat_exchanger_id)
    assert mid.ache_params is not None
    assert mid.enthalpy_table_json is None  # 未写保持 None

    # 再写 enthalpy_table
    await save_enthalpy_table(
        db,
        heat_exchanger_id=record.heat_exchanger_id,
        table=_enthalpy_table_sample(n=12),
    )
    await db.commit()
    final = await db.get(HeatResult, record.heat_exchanger_id)
    assert final.ache_params is not None
    assert final.enthalpy_table_json is not None
    assert len(final.enthalpy_table_json["entries"]) == 12
