"""HEAT 持久化 service 测试（P5-4-5 / Task 23）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md V1.0 §Task 23：
- import_htri_heat_result：HTRI 解析 → 落库 heat_results + finalize + outlet
  （source_stream_id 提供时创建 HEAT_CALCULATED outlet，change_type=HEAT_EXCHANGE）
- estimate_heat_weight：estimate_weight → output_json.total_weight_kg / weight_segments
  / weight_formula_ref（P7 UTIL 消费）
- heat_results.duty 字段可读（与 9 旧 P4 上游值共享 1 列 per ADR-0027 V1.0 决策 5）

**Do-Not-Repeat**：HeatResult（继承 TaggedRecordMixin）: `tag_number`
NOT NULL（string unique per project）+ `project_id` + `workspace_id`。
fixture 必填字段以 `db.add → flush → refresh` 直接构造 ORM，
避免 ORM kwarg 拼装遗漏 NOT NULL。
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.models.calc import HeatResult
from app.models.project import Project, Stream, Workspace
from app.services.heat.heat_persist import (
    estimate_heat_weight,
    import_htri_heat_result,
)
from app.services.heat.htri_parser import HtriParsedData
from app.services.heat.weight_estimate_service import WeightEstimateInput

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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
            project_name="heat-persist 测试项目",
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


async def _seed_source_stream(
    db, *, project_id: uuid.UUID, workspace_id: uuid.UUID
) -> Stream:
    """源流（HEAT 计算入口流）。"""
    stream = Stream(
        stream_id=uuid.uuid4(),
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-HEAT-IN-{uuid.uuid4().hex[:6].upper()}",
        case_type="NORMAL",
        data_mode="MEASURED",
        source_type="MEASURED",
        sign_status="CHECKED",
        approval_depth=0,
        composition_json={},
    )
    db.add(stream)
    await db.commit()
    return stream


def _htri_fixture() -> HtriParsedData:
    """复用 Task 19 fixture HTRI Xist v6.0 basic 算例。"""
    from app.services.heat.htri_parser import parse_htri

    return parse_htri(FIXTURES_DIR / "htri_xist_v6_basic.txt")


# ===== import_htri_heat_result 端到端 =====


async def test_import_htri_heat_result_end_to_end(db):
    """HTRI 解析 → 落库 heat_results + finalize（无源流，MVP 用例）。"""

    project_id, workspace_id = await _seed_project_workspace(db)
    htri = _htri_fixture()

    record, outlet = await import_htri_heat_result(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        equipment_no="E-201",
        equipment_name="HEAT-E-201",
        tag_number="E-201",
        exchanger_category="SHELL_TUBE",
        htri=htri,
    )
    await db.commit()

    # 1. HeatResult 落库（47 字段平铺）
    result = await db.get(HeatResult, record.heat_exchanger_id)
    assert result is not None
    assert result.tag_number == "E-201"
    assert result.exchanger_category == "SHELL_TUBE"
    # HTRI 字段映射（来自 map_htri_to_heat_input）
    assert result.duty == pytest.approx(1_000_000.0)
    assert result.tube_count == 150
    assert result.shell_id == pytest.approx(600.0)  # mm

    # 2. record_hash 已写（finalize_calc_record 收口）
    assert result.record_hash is not None
    assert len(result.record_hash) == 16  # 16 hex per ADR-0031

    # 3. 无 source_stream_id 时不创建 outlet
    assert outlet is None


async def test_import_htri_heat_result_creates_heat_outlet(db):
    """提供 source_stream_id 时创建 HEAT_CALCULATED outlet，change_type=HEAT_EXCHANGE。"""
    project_id, workspace_id = await _seed_project_workspace(db)
    source = await _seed_source_stream(
        db, project_id=project_id, workspace_id=workspace_id
    )
    htri = _htri_fixture()

    record, outlet = await import_htri_heat_result(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        equipment_no="E-201",
        equipment_name="HEAT-E-201",
        tag_number="E-201",
        exchanger_category="SHELL_TUBE",
        htri=htri,
        source_stream_id=source.stream_id,
    )
    await db.commit()

    # outlet 已创建
    assert outlet is not None
    assert outlet.source_type == "HEAT_CALCULATED"
    assert outlet.upstream_stream_id == source.stream_id
    assert outlet.upstream_equipment_type == "HEAT"
    # sign_status=DRAFT（calc 入口守卫兜底）
    from app.models.enums import StreamSignStatus

    assert outlet.sign_status == StreamSignStatus.DRAFT
    # stream_properties_json 含 HEAT_EXCHANGE 元数据
    assert outlet.stream_properties_json["change_type"] == "HEAT_EXCHANGE"
    assert outlet.stream_properties_json["heat_exchanger_id"] == str(
        record.heat_exchanger_id
    )
    assert outlet.stream_properties_json["duty_w"] == pytest.approx(1_000_000.0)


async def test_import_htri_rejects_cross_project_source(db):
    """源流 project_id 与 heat project_id 不一致 → HeatProjectMismatchError。"""
    from app.services.heat.heat_persist import HeatProjectMismatchError

    # 项目 A：heat 落库
    project_a, ws_a = await _seed_project_workspace(db)
    # 项目 B：源流
    project_b, ws_b = await _seed_project_workspace(db)
    source_b = await _seed_source_stream(
        db, project_id=project_b, workspace_id=ws_b
    )
    htri = _htri_fixture()

    with pytest.raises(HeatProjectMismatchError):
        await import_htri_heat_result(
            db,
            project_id=project_a,
            workspace_id=ws_a,
            equipment_no="E-201",
            equipment_name="HEAT-E-201",
            tag_number="E-201",
            exchanger_category="SHELL_TUBE",
            htri=htri,
            source_stream_id=source_b.stream_id,
        )


# ===== estimate_heat_weight（P7 UTIL 消费）=====


async def test_estimate_heat_weight_writes_output_json(db):
    """estimate_weight → output_json.total_weight_kg + weight_segments + weight_formula_ref。"""
    project_id, workspace_id = await _seed_project_workspace(db)
    htri = _htri_fixture()
    record, _ = await import_htri_heat_result(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        equipment_no="E-201",
        equipment_name="HEAT-E-201",
        tag_number="E-201",
        exchanger_category="SHELL_TUBE",
        htri=htri,
    )
    await db.commit()

    # 用 BEM golden 输入估算重量
    weight_input = WeightEstimateInput(
        tema_type="BEM",
        shell_id_m=1.0,
        shell_length_m=5.0,
        shell_thickness_m=0.012,
        material="carbon_steel",
        head_count=2,
        head_straight_m=0.025,
        flange_count=2,
        flange_class="300#",
        flange_size_dn=600,
        nozzle_count=4,
        nozzle_size_dn=100,
        saddle_count=2,
        saddle_size_dn=600,
        tube_count=200,
        tube_od_m=0.01905,
        tube_thickness_m=0.00165,
        tube_length_m=5.0,
        baffle_count=10,
        baffle_diameter_m=0.8,
        baffle_thickness_m=0.005,
    )
    updated, wres = await estimate_heat_weight(
        db, heat_id=record.heat_exchanger_id, weight_input=weight_input
    )
    await db.commit()

    # output_json 三个 weight 字段落地
    assert updated.output_json["total_weight_kg"] == pytest.approx(
        wres.total.weight_kg
    )
    assert updated.output_json["weight_segments"]["shell_cylinder_kg"] == pytest.approx(
        wres.shell_cylinder.weight_kg
    )
    assert updated.output_json["weight_segments"]["tube_kg"] == pytest.approx(
        wres.tube.weight_kg
    )
    # formula_ref 顶层含 TEMA 版本
    assert updated.output_json["weight_formula_ref"]["tema_version"] == "TEMA 9th Ed."

    # 读回 HeatResult 验证
    reloaded = await db.get(HeatResult, record.heat_exchanger_id)
    assert reloaded.output_json["total_weight_kg"] == pytest.approx(
        wres.total.weight_kg
    )
    # record_hash 已刷新（output_json 变更 → 重算）
    assert reloaded.record_hash is not None
    assert len(reloaded.record_hash) == 16


async def test_estimate_heat_weight_nonexistent_heat_raises(db):
    """heat_id 不存在 → PcsError code=HEAT_NOT_FOUND。"""
    from app.services.exceptions import PcsError

    fake_id = uuid.uuid4()
    with pytest.raises(PcsError) as exc_info:
        await estimate_heat_weight(
            db,
            heat_id=fake_id,
            weight_input=WeightEstimateInput(
                tema_type="BEM",
                shell_id_m=1.0,
                shell_length_m=5.0,
                shell_thickness_m=0.012,
            ),
        )
    assert exc_info.value.code == "HEAT_NOT_FOUND"
    assert exc_info.value.status == 404


# ===== duty 字段可读（P7 UTIL 综合能耗消费）=====


async def test_heat_results_duty_readable_for_util(db):
    """heat_results.duty 字段可读（P7 UTIL 综合能耗查询 / ADR-0027 决策 5 共享列）。"""
    project_id, workspace_id = await _seed_project_workspace(db)
    htri = _htri_fixture()
    record, _ = await import_htri_heat_result(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        equipment_no="E-201",
        equipment_name="HEAT-E-201",
        tag_number="E-201",
        exchanger_category="SHELL_TUBE",
        htri=htri,
    )
    await db.commit()

    reloaded = await db.get(HeatResult, record.heat_exchanger_id)
    assert reloaded.duty == pytest.approx(1_000_000.0)  # 1 MW from HTRI fixture
    assert reloaded.duty > 0  # P7 UTIL 可直接用作能耗输入
