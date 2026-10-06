"""泵设计参数接线 (P7 Sprint 4 · S4-2 设计值缺口收口).

`EquipmentList.design_parameters_json` 此前**无任何写入方**（恒 NULL）—— 偏差报告
与确认流程因此在生产路径上恒为「缺设计值（不可判）」。

数据源: `sample/1216D132*.xlsx` → `机泵选型(基础设计)` sheet（转置：列=泵，行=参数）。
位号与已同步进 `utility_power_items` / `EquipmentList` 的 `tag_number` 逐台吻合。

本模块负责把转录的设计值**落到** `design_parameters_json`，格式与
`actual_data_json` 对称: ``{参数名: {"value": float, "unit": str}}``。
"""

from __future__ import annotations

import uuid

import pytest

from app.services.equip_list.pump_design_data import (
    PUMP_DESIGN,
    PUMP_DESIGN_EXCLUDED,
    design_params_for_tag,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# 1. 数据形态
# ---------------------------------------------------------------------------


def test_design_data_lives_in_service_not_acceptance_script():
    """设计值是生产数据, 不该住在 T5 验收脚本里（那是测试资产, 不是数据源）."""
    from pathlib import Path

    import app.services.equip_list.pump_design_data as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "PUMP_DESIGN" in src
    assert "p7_open_012" not in src, "设计数据不得反向依赖 T5 验收脚本"


def test_design_covers_the_16_electric_pumps():
    with_motor = {t: d for t, d in PUMP_DESIGN.items() if d.get("电机额定功率")}
    assert len(with_motor) == 16
    # 液力透平没有电机 —— 该留 None, 不该编一个
    assert PUMP_DESIGN["132-P-101-T"]["电机额定功率"] is None


def test_bad_values_excluded_with_reasons():
    """坏值按用户裁决排除, 且必须留理由 —— 免得日后有人「顺手」加回来."""
    assert "132-P-105A/B/C/D" in PUMP_DESIGN_EXCLUDED
    assert "132-P-105A/B/C/D" not in PUMP_DESIGN
    for tag in PUMP_DESIGN_EXCLUDED:
        assert PUMP_DESIGN_EXCLUDED[tag], f"{tag} 排除必须带理由"


def test_axis_power_present_for_every_motor_pump():
    """电机裕量规则以轴功率为参照量 —— 缺了就判不了, 必须在数据层先保证."""
    for tag, d in PUMP_DESIGN.items():
        if d.get("电机额定功率") is not None:
            assert d.get("轴功率"), f"{tag} 有电机但缺轴功率"


# ---------------------------------------------------------------------------
# 2. 形状转换
# ---------------------------------------------------------------------------


def test_design_params_for_tag_uses_jsonb_envelope():
    got = design_params_for_tag("132-P-101A/B")
    assert got["轴功率"] == {"value": 2214.06, "unit": "kW"}
    assert got["扬程"] == {"value": 2100.0, "unit": "m"}


def test_design_params_carry_units():
    got = design_params_for_tag("132-P-101A/B")
    assert got["效率"]["unit"] == "-"
    assert got["NPSHr"]["unit"] == "m"
    assert got["转速"]["unit"] == "r/min"


def test_design_params_skip_none_values():
    """None 不进 JSONB —— 否则下游会把「空」读成 0."""
    got = design_params_for_tag("132-P-101-T")
    assert "电机额定功率" not in got
    assert "轴功率" in got


def test_design_params_unknown_tag_returns_empty():
    assert design_params_for_tag("NOT-A-PUMP") == {}


# ---------------------------------------------------------------------------
# 3. 落库
# ---------------------------------------------------------------------------


async def _make_equipment(db_session, tag):
    from app.models.equipment import EquipmentList

    eq = EquipmentList(
        project_id=PROJECT_ID, workspace_id=uuid.uuid4(), tag_number=tag,
        equipment_name=tag, type_code="P-100", actual_data_status="NOT_ENTERED",
    )
    db_session.add(eq)
    await db_session.commit()
    return eq


PROJECT_ID = uuid.uuid4()


async def test_apply_writes_design_parameters_json(db_session):
    from sqlalchemy import select

    from app.models.equipment import EquipmentList
    from app.services.equip_list.pump_design_data import apply_design_parameters

    await _make_equipment(db_session, "132-P-101A/B")
    n = await apply_design_parameters(db_session, PROJECT_ID)
    assert n == 1

    eq = (
        await db_session.execute(
            select(EquipmentList).where(EquipmentList.project_id == PROJECT_ID)
        )
    ).scalar_one()
    assert eq.design_parameters_json["轴功率"]["value"] == 2214.06


async def test_apply_is_idempotent(db_session):
    """重复跑不产生副作用 —— 脚本会被反复执行.

    审查 #14 之后「幂等」的含义细化为：**值不变，且第二次不再宣称要写**。
    已有非空设计值默认跳过（`overwrite=False`），故第二次返回 0 而不是 1 ——
    这正是「不绕过设计签署」的体现。数据仍是幂等的：值一字未改。
    """
    from app.services.equip_list.pump_design_data import apply_design_parameters

    eq = await _make_equipment(db_session, "132-P-101A/B")
    assert await apply_design_parameters(db_session, PROJECT_ID) == 1
    first = dict(eq.design_parameters_json)

    assert await apply_design_parameters(db_session, PROJECT_ID) == 0, (
        "已有设计值的设备默认应被跳过, 而不是被无声覆盖"
    )
    assert eq.design_parameters_json == first, "重复执行不得改动已有设计值"

    # 显式 overwrite 才允许覆盖, 覆盖后仍写入同一份数据
    assert await apply_design_parameters(
        db_session, PROJECT_ID, overwrite=True
    ) == 1
    assert eq.design_parameters_json == first


async def test_apply_dry_run_does_not_commit(db_session):
    """dry_run：内存态改了但**不落库** —— 脚本不加 `--apply` 时的默认行为。"""
    from app.services.equip_list.pump_design_data import apply_design_parameters

    eq = await _make_equipment(db_session, "132-P-101A/B")
    assert await apply_design_parameters(db_session, PROJECT_ID, dry_run=True) == 1
    assert eq.design_parameters_json is not None, "dry-run 仍应在内存态算出将写的值"

    await db_session.rollback()
    await db_session.refresh(eq)
    assert eq.design_parameters_json is None, "dry-run 不得留下已落库的痕迹"


async def test_apply_skips_unknown_tags(db_session):
    """库里有的设备若不在设计表内, 不得被写空对象覆盖已有值."""
    from app.services.equip_list.pump_design_data import apply_design_parameters

    eq = await _make_equipment(db_session, "217-C-201")
    eq.design_parameters_json = {"已有值": {"value": 1.0, "unit": "x"}}
    await db_session.commit()

    assert await apply_design_parameters(db_session, PROJECT_ID) == 0
    await db_session.refresh(eq)
    assert eq.design_parameters_json == {"已有值": {"value": 1.0, "unit": "x"}}


async def test_apply_does_not_touch_actual_data(db_session):
    """设计值写入不得碰 actual_data_json / actual_data_status."""
    from app.services.equip_list.pump_design_data import apply_design_parameters

    eq = await _make_equipment(db_session, "132-P-101A/B")
    eq.actual_data_json = {"扬程": {"value": 2100.0, "unit": "m"}}
    eq.actual_data_status = "CONFIRMED"
    await db_session.commit()

    await apply_design_parameters(db_session, PROJECT_ID)
    await db_session.refresh(eq)
    assert eq.actual_data_json == {"扬程": {"value": 2100.0, "unit": "m"}}
    assert eq.actual_data_status == "CONFIRMED"


async def test_apply_crosses_projects_safely(db_session):
    """只作用于指定 project —— 别的项目的同位号设备不得被动."""
    from app.services.equip_list.pump_design_data import apply_design_parameters

    other = await _make_equipment(db_session, "132-P-101A/B")
    other.project_id = uuid.uuid4()
    await db_session.commit()

    assert await apply_design_parameters(db_session, PROJECT_ID) == 0
    await db_session.refresh(other)
    assert other.design_parameters_json is None


# ---------------------------------------------------------------------------
# 4. 端到端: 设计值接上后, 偏差报告能出真实结论（不再是恒「不可判」）
# ---------------------------------------------------------------------------


async def test_deviation_report_now_produces_real_verdicts(db_session):
    """**本模块存在的全部意义**: 此前偏差报告恒为「缺设计值（不可判）」.

    写入设计值 + 录入实测值 → 必须出真实档位, 且电机规则按轴功率分档判。
    """
    from app.services.equip_list.pump_design_data import apply_design_parameters
    from app.services.supplier.actual_data_service import record_actual_data
    from app.services.supplier.deviation_report import build_report, can_confirm

    eq = await _make_equipment(db_session, "132-P-101A/B")
    assert await apply_design_parameters(db_session, PROJECT_ID) == 1
    await db_session.refresh(eq)

    # 设计侧（XLS）: 轴功率 2214.06 kW / 扬程 2100 m / 电机 2500 kW
    # 实测侧: 应检集须**录齐**（#8）—— SPEC §3.2.4(2) 六条是并集, 只录一条不得确认。
    # 扬程 2130 m (偏 +1.43%, 合格) + 电机 2600 kW (地板 2214.06*1.10 = 2435.5, 合格)
    # + NPSHr / 效率 / 转速 三项补齐
    await record_actual_data(db_session, eq, [
        {"name": "扬程", "value": 2130.0, "unit": "m"},
        {"name": "效率", "value": 95.0, "unit": "%"},
        {"name": "NPSHr", "value": 2.0, "unit": "m"},
        {"name": "电机额定功率", "value": 2600.0, "unit": "kW"},
        {"name": "转速", "value": 2982.0, "unit": "r/min"},
    ])

    report = build_report(eq)
    assert report.rows, "报告不应为空"
    unverdictable = [(r.parameter, r.note) for r in report.rows
                     if r.verdict == "UNVERDICTABLE"]
    assert not unverdictable, f"应检参数录齐后仍有不可判行: {unverdictable}"
    # 扬程 +5%/-0% 非对称带 → 2130 偏 +1.43% → 合格
    head = next(r for r in report.rows if r.parameter == "扬程")
    assert head.verdict == "QUALIFIED"
    # 电机按 API 610 分档: 2214.06 × 1.10 = 2435.5 → 2600 达标 → 合格
    motor = next(r for r in report.rows if r.parameter == "电机额定功率")
    assert motor.verdict == "QUALIFIED"
    assert "2435" in motor.note
    assert can_confirm(report) is True


async def test_deviation_report_flags_undersized_motor(db_session):
    """电机低于分档下限 → 不合格且阻断确认 —— 这才是本规则真正要抓的东西."""
    from app.services.equip_list.pump_design_data import apply_design_parameters
    from app.services.supplier.actual_data_service import record_actual_data
    from app.services.supplier.deviation_report import build_report, can_confirm

    eq = await _make_equipment(db_session, "132-P-101A/B")
    await apply_design_parameters(db_session, PROJECT_ID)
    await db_session.refresh(eq)

    def _entries(motor_kw: float) -> list[dict]:
        """应检集录齐 + 指定电机功率（#8: 只录一项不得确认）。"""
        return [
            {"name": "扬程", "value": 2130.0, "unit": "m"},
            {"name": "效率", "value": 95.0, "unit": "%"},
            {"name": "NPSHr", "value": 2.0, "unit": "m"},
            {"name": "电机额定功率", "value": motor_kw, "unit": "kW"},
            {"name": "转速", "value": 2982.0, "unit": "r/min"},
        ]

    # 2500 kW 电机: 恰好卡 1.10 档 (下限 2435.5), 达标
    await record_actual_data(db_session, eq, _entries(2500.0))
    assert can_confirm(build_report(eq)) is True

    # 改成 2300 kW: 低于 2214.06 × 1.10 = 2435.5 → 不合格
    await record_actual_data(db_session, eq, _entries(2300.0))
    report = build_report(eq)
    motor_row = next(r for r in report.rows if r.parameter == "电机额定功率")
    assert motor_row.verdict == "UNQUALIFIED"
    assert can_confirm(report) is False
