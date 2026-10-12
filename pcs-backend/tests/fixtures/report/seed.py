"""Golden 测试的种子数据 —— 每种报表 2–3 组。

**必须走 ORM 构造**：conftest 的建表来自 `SA_Base.metadata.create_all`，
只有 ORM 写入才与之匹配（直接写裸 SQL 会绕过 ORM 的默认值与约束语义）。

⚠️ **必填列必须逐条填**（cerebrum 的 Do-Not-Repeat）：
本仓多数结果表继承 `TaggedRecordMixin`，`tag_number` / `project_id` /
`workspace_id` 是 NOT NULL 且无默认；JSONB 容器列同样 NOT NULL。
少填一列就是一条 IntegrityError，而错误信息不会告诉你是哪一列漏了。
故下面每张表的构造都把必填列写全，并在注释里标注来源。
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import (HeatResult, PipingResult, PsvResult, PumpResult,
                             VesselResult)
from app.models.equipment import EquipmentList
from app.models.project import Stream
from app.models.util import UtilResults


def _json(**kw):
    """JSONB 容器列的统一构造点 —— 避免各处漏 key。"""
    return kw


async def make_report_seed(db: AsyncSession, project_id: uuid.UUID,
                           report_type: str, workspace_id: uuid.UUID | None = None,
                           ) -> list[uuid.UUID]:
    """按 report_type 造种子记录，返回其主键列表（供 collect 的 IN 过滤用）。"""
    ws = workspace_id or uuid.uuid4()
    builder = _BUILDERS[report_type]
    rows = await builder(db, project_id, ws)
    await db.flush()
    return [getattr(r, _PK[report_type]) for r in rows]


_PK = {
    "PIPING_CALC_BOOK": "pipe_id", "PUMP_DATA_TABLE": "pump_id",
    "PSV_DATA_TABLE": "psv_id", "VESSEL_DATA_TABLE": "vessel_id",
    "HEAT_SPEC": "heat_exchanger_id", "EQUIPMENT_LIST": "equipment_id",
    "UTILITY_BALANCE": "util_result_id", "ENERGY_CALC_BOOK": "util_result_id",
    "ENTRUST_CONDITION": "util_result_id", "PIPING_LIST": "pipe_id",
}


async def _seed_equipment(db, project_id, ws):
    rows = [
        EquipmentList(
            type_code="PUMP-101", tag_number="PUMP-101",
            equipment_name="天然气输送泵 101", equipment_description="离心泵",
            vendor="ACME", vendor_model="CP-50", equipment_status="设计",
            actual_data_status="未确认", design_parameters_json=_json(power_kw=25.5),
            project_id=project_id, workspace_id=ws),
        EquipmentList(
            type_code="PUMP-102", tag_number="PUMP-102",
            equipment_name="工艺水循环泵 102", equipment_description="离心泵",
            vendor="ACME", vendor_model="CP-80", equipment_status="设计",
            actual_data_status="未确认", design_parameters_json=_json(power_kw=45.0),
            project_id=project_id, workspace_id=ws),
    ]
    db.add_all(rows)
    return rows


async def _seed_piping(db, project_id, ws):
    common = dict(project_id=project_id, workspace_id=ws, piping_category="工艺管道",
                  fluid_phase="气", check_class="Class 300",
                  pressure_test_medium="水", pressure_test_press=2.5)
    rows = [
        PipingResult(seq_no=1, line_no="1001-A1-N-1001", line_size="DN50",
                     material_class="20#", fluid_code="NG", fluid_name="天然气",
                     fluid_category="可燃", source_pid="P-101",
                     line_from="V-101", line_to="E-201",
                     norm_oper_press=0.6, max_oper_press=0.8,
                     norm_oper_temp=40.0, max_oper_temp=60.0,
                     design_press=1.0, design_temp=80.0, **common),
        PipingResult(seq_no=2, line_no="1002-A1-W-1002", line_size="DN80",
                     material_class="304", fluid_code="PW", fluid_name="工艺水",
                     fluid_category="一般", source_pid="P-102",
                     line_from="P-102", line_to="T-301",
                     norm_oper_press=0.4, max_oper_press=0.5,
                     norm_oper_temp=30.0, max_oper_temp=50.0,
                     design_press=0.8, design_temp=70.0, **common),
    ]
    db.add_all(rows)
    return rows


async def _seed_pump(db, project_id, ws):
    def _pump(tag, head, power):
        return PumpResult(
            tag_number=tag, project_id=project_id, workspace_id=ws,
            basic_info_json=_json(medium="天然气", duty="连续"),
            fluid_properties_json=_json(density_kg_m3=0.72, viscosity_pa_s=1.1e-5),
            flow_rates_json=_json(flow_m3_s=0.05, head_m=head, speed_rpm=2950),
            suction_calculation_json=_json(npsha_m=3.2, h_friction_m=0.8,
                                           h_elevation_m=1.1),
            discharge_calculation_json=_json(_discharge_pipe_chain_used=True),
            differential_pressure_json=_json(operating_head_m=head, rated_head_m=head * 1.05),
            design_pressure_json=_json(system_pressure_pa=8e5, vapor_pressure_pa=1e5),
            power_consumption_json=_json(estimated_power_kw=power),
            actual_head=head, actual_efficiency=0.72,
        )

    rows = [_pump("PUMP-101", 45.0, 25.5), _pump("PUMP-102", 60.0, 45.0)]
    db.add_all(rows)
    return rows


async def _seed_psv(db, project_id, ws):
    rows = [
        PsvResult(tag_number="PSV-101", project_id=project_id, workspace_id=ws,
                  set_pressure=0.9, relief_capacity=12.5, orifice_area=0.0032,
                  blowdown=0.1, orifice_designation="D", inlet_size="DN50",
                  outlet_size="DN80", relief_scenario="超压"),
        PsvResult(tag_number="PSV-102", project_id=project_id, workspace_id=ws,
                  set_pressure=1.2, relief_capacity=18.0, orifice_area=0.0045,
                  blowdown=0.1, orifice_designation="D", inlet_size="DN80",
                  outlet_size="DN100", relief_scenario="火灾"),
    ]
    db.add_all(rows)
    return rows


async def _seed_vessel(db, project_id, ws):
    rows = [
        VesselResult(tag_number="V-101", project_id=project_id, workspace_id=ws,
                     input_json=_json(sizing=_json(volume_m3=10.0),
                                      hydraulics=_json(volume_m3=10.0, diameter_m=2.4,
                                                       length_m=3.5)),
                     output_json=_json(sizing=_json(liquid_volume_m3=8.5, check="OK"),
                                       hydraulics=_json(volume_m3=10.0, diameter_m=2.4,
                                                        length_m=3.5)),
                     residence_time_s=300.0),
    ]
    db.add_all(rows)
    return rows


async def _seed_heat(db, project_id, ws):
    rows = [
        HeatResult(tag_number="E-201", equipment_no="E-201",
                   project_id=project_id, workspace_id=ws,
                   exchanger_category="管壳式",
                   design_conditions_json=_json(hot_in="天然气", cold_in="工艺水"),
                   input_json=_json(flow_hot=1.2, flow_cold=2.0),
                   output_json=_json(duty_kw=180.0, area_m2=42.0),
                   duty=180.0, effective_area=42.0, u_overall=650.0),
    ]
    db.add_all(rows)
    return rows


async def _seed_util(db, project_id, ws):
    rows = [
        UtilResults(project_id=project_id, workspace_id=ws,
                    consumption_json=_json(electricity_kwh=120000),
                    business_date=dt.date(2026, 1, 31), electrical_power_kwh_yr=120000.0,
                    fuel_gas_consumption_nm3_yr=85000.0,
                    steam_consumption_t_yr=620.0,
                    cooling_water_consumption_t_yr=15000.0,
                    annual_total_energy=0.0, total_toe=0.0,
                    total_standard_coal_kg=0.0, tolerance_status="OK"),
        UtilResults(project_id=project_id, workspace_id=ws,
                    consumption_json=_json(electricity_kwh=98000),
                    business_date=dt.date(2026, 2, 28), electrical_power_kwh_yr=98000.0,
                    fuel_gas_consumption_nm3_yr=71000.0,
                    steam_consumption_t_yr=540.0,
                    cooling_water_consumption_t_yr=13000.0,
                    annual_total_energy=0.0, total_toe=0.0,
                    total_standard_coal_kg=0.0, tolerance_status="OK"),
    ]
    db.add_all(rows)
    return rows


async def _seed_stream(db, project_id, ws):
    rows = [
        Stream(project_id=project_id, workspace_id=ws, stream_name="NG-FEED",
               data_mode="实测", source_type="设计", approval_depth=0,
               description="原料天然气"),
    ]
    db.add_all(rows)
    return rows


_BUILDERS = {
    "PIPING_CALC_BOOK": _seed_piping, "PUMP_DATA_TABLE": _seed_pump,
    "PSV_DATA_TABLE": _seed_psv, "VESSEL_DATA_TABLE": _seed_vessel,
    "HEAT_SPEC": _seed_heat, "EQUIPMENT_LIST": _seed_equipment,
    "UTILITY_BALANCE": _seed_util, "ENERGY_CALC_BOOK": _seed_util,
    "ENTRUST_CONDITION": _seed_util, "PIPING_LIST": _seed_piping,
}

__all__ = ["make_report_seed"]

async def make_bulk_seed(db: AsyncSession, project_id: uuid.UUID, report_type: str,
                         count: int, workspace_id: uuid.UUID | None = None) -> list[uuid.UUID]:
    """造 `count` 条种子记录（性能基准用）。

    为什么单独一个入口：性能测试真正要的是**行数量**，而 `make_report_seed`
    每类只造 2–3 条。第一版基准直接调 `make_report_seed` 然后在测试里
    造了一个**从未被使用**的 rows 列表 —— 实际跑的是 2 行，阈值 10s
    轻松满足，**看着绿，其实没测过 1 万行**。

    构造逻辑复用 `_seed_*` 的同一套必填列知识：把第一个种子行复制 N 份
    并改掉唯一键，避免「为了造数据另写一份 ORM 构造」而漏必填列。
    """
    ws = workspace_id or uuid.uuid4()
    base = await _BUILDERS[report_type](db, project_id, ws)
    await db.flush()
    pk_attr = _PK[report_type]
    originals = list(base)
    first = originals[0]

    # ⚠️ 不能用 `copy.deepcopy(first)` —— 它连 `_sa_instance_state` 一起复制，
    # 新对象仍带着同一个 identity key，SQLAlchemy 直接报
    # "another instance with key ... is already present in this session"。
    # 正确做法：从 mapper 的列值**重建**一个新实例 —— 必填列的知识仍然来自
    # 那一个已验证可用的种子行，不会因为另写一份 ORM 构造而漏列。
    column_names = [c.name for c in first.__table__.columns]
    extra = []
    for i in range(1, count):
        values = {n: getattr(first, n) for n in column_names if n != pk_attr}
        row = type(first)(**values)
        setattr(row, pk_attr, uuid.uuid4())
        if hasattr(row, "tag_number"):          # TaggedRecordMixin 要求唯一
            setattr(row, "tag_number", f"BULK-{i:06d}")
        extra.append(row)
    db.add_all(extra)
    await db.flush()
    return [getattr(r, pk_attr) for r in originals + extra][:count]


__all__ = ["make_report_seed", "make_bulk_seed"]
