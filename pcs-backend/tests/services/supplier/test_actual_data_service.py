"""供应商实际数据录入 — 手工 UI 路径 (P7 Sprint 4 Task S4-1).

ADR-0025: 设备从「设计值」流转到「实际值」。`EquipmentList` 已有
`actual_data_status` 状态列 (NOT_ENTERED/PENDING_CONFIRM/CONFIRMED/NEED_RECALC),
但**没有承载实际值本身的字段** —— 本 Task 补 `actual_data_json`。

录入入口是**手工 UI 页面** (S4-1 裁决): 要求供应商填统一 Excel 不现实,
故无 Excel 批量导入路径, 设备方逐项在页面上录入。

注意: `design_parameters_json` 是**设计**值不是实测值 (由 PUMP_DESIGN 回填写入),
不能拿它做录入校验的依据; 校验是「每项 name+value+unit, name 去重, value 必须数值」。
"""

from __future__ import annotations

import uuid

import pytest

from app.core.errors import PcsError

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


async def _make_equipment(db_session, **overrides):
    from app.models.equipment import EquipmentList

    base = dict(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        tag_number=overrides.pop("tag_number", f"EQ-{uuid.uuid4().hex[:8]}"),
        equipment_name="测试设备",
        type_code=overrides.pop("type_code", "V-100"),
        actual_data_status="NOT_ENTERED",
    )
    base.update(overrides)
    eq = EquipmentList(**base)
    db_session.add(eq)
    await db_session.commit()
    await db_session.refresh(eq)
    return eq


# ---------------------------------------------------------------------------
# 1. 手动录入
# ---------------------------------------------------------------------------


async def test_manual_entry_records_actual_data(db_session):
    """手动录入 → actual_data_json 落库 + 状态转 PENDING_CONFIRM."""
    from app.services.supplier.actual_data_service import record_actual_data

    eq = await _make_equipment(db_session)
    out = await record_actual_data(
        db_session, eq,
        [
            {"name": "设计温度", "value": 102.0, "unit": "℃"},
            {"name": "设计压力", "value": 1.65, "unit": "MPa"},
        ],
    )
    assert out.actual_data_status == "PENDING_CONFIRM"
    assert out.actual_data_json == {
        "设计温度": {"value": 102.0, "unit": "℃"},
        "设计压力": {"value": 1.65, "unit": "MPa"},
    }


async def test_manual_entry_replaces_previous(db_session):
    """二次录入整体替换（非合并）—— 避免上轮残留值混入偏差计算."""
    from app.services.supplier.actual_data_service import record_actual_data

    eq = await _make_equipment(db_session)
    await record_actual_data(
        db_session, eq, [{"name": "设计温度", "value": 100.0, "unit": "℃"}]
    )
    out = await record_actual_data(
        db_session, eq, [{"name": "设计压力", "value": 1.6, "unit": "MPa"}]
    )
    assert set(out.actual_data_json) == {"设计压力"}


async def test_manual_entry_accepts_negative_value(db_session):
    """低温工况实测值可为负（如冬季设计温度）—— 不做正值假设."""
    from app.services.supplier.actual_data_service import record_actual_data

    eq = await _make_equipment(db_session)
    out = await record_actual_data(
        db_session, eq, [{"name": "最低设计温度", "value": -25.5, "unit": "℃"}]
    )
    assert out.actual_data_json["最低设计温度"]["value"] == -25.5


# ---------------------------------------------------------------------------
# 2. 校验 (ACTUAL_DATA_VALIDATION 422)
# ---------------------------------------------------------------------------


async def test_non_numeric_value_raises(db_session):
    """value 非数值 → ACTUAL_DATA_VALIDATION 422."""
    from app.services.supplier.actual_data_service import record_actual_data

    eq = await _make_equipment(db_session)
    with pytest.raises(PcsError) as exc:
        await record_actual_data(
            db_session, eq,
            [{"name": "设计温度", "value": "一百多度", "unit": "℃"}],
        )
    assert exc.value.code == "ACTUAL_DATA_VALIDATION"
    assert exc.value.status == 422


async def test_numeric_string_value_rejected(db_session):
    """字符串数字也拒 —— 供应商表里 "100" 与 100 混用会让偏差百分比行为不可预期."""
    from app.services.supplier.actual_data_service import record_actual_data

    eq = await _make_equipment(db_session)
    with pytest.raises(PcsError) as exc:
        await record_actual_data(
            db_session, eq, [{"name": "设计温度", "value": "100", "unit": "℃"}]
        )
    assert exc.value.code == "ACTUAL_DATA_VALIDATION"


async def test_duplicate_name_raises(db_session):
    """同名参数重复 → 报错 (否则 JSONB 静默覆盖, 录入者不会知道)."""
    from app.services.supplier.actual_data_service import record_actual_data

    eq = await _make_equipment(db_session)
    with pytest.raises(PcsError) as exc:
        await record_actual_data(
            db_session, eq,
            [
                {"name": "设计温度", "value": 100.0, "unit": "℃"},
                {"name": "设计温度", "value": 102.0, "unit": "℃"},
            ],
        )
    assert exc.value.code == "ACTUAL_DATA_VALIDATION"


async def test_blank_name_raises(db_session):
    from app.services.supplier.actual_data_service import record_actual_data

    eq = await _make_equipment(db_session)
    with pytest.raises(PcsError):
        await record_actual_data(
            db_session, eq, [{"name": "  ", "value": 1.0, "unit": "x"}]
        )


async def test_empty_list_raises(db_session):
    """空录入无意义 → 拒绝 (否则状态转了却无数据)."""
    from app.services.supplier.actual_data_service import record_actual_data

    eq = await _make_equipment(db_session)
    with pytest.raises(PcsError):
        await record_actual_data(db_session, eq, [])


async def test_failed_validation_does_not_advance_status(db_session):
    """校验失败 → 状态不得转 PENDING_CONFIRM (否则 UI 显示"已录入"却无值)."""
    from app.services.supplier.actual_data_service import record_actual_data

    eq = await _make_equipment(db_session)
    with pytest.raises(PcsError):
        await record_actual_data(
            db_session, eq, [{"name": "设计温度", "value": "abc", "unit": "℃"}]
        )
    await db_session.refresh(eq)
    assert eq.actual_data_status == "NOT_ENTERED"
    assert eq.actual_data_json is None


# ---------------------------------------------------------------------------
# 3. model 层
# ---------------------------------------------------------------------------


def test_equipment_list_has_actual_data_json_column():
    from app.models.equipment import EquipmentList

    cols = {c.name for c in EquipmentList.__table__.columns}
    assert "actual_data_json" in cols
    assert "actual_data_status" in cols  # 既有状态列保留


# ---------------------------------------------------------------------------
# entries 长度上限（审查 #1）
# ---------------------------------------------------------------------------


def test_normalize_entries_rejects_over_limit() -> None:
    """`entries` 无上限时单次 PUT 可造出任意大的报告，两个导出器都整体物化。

    服务层同步加闸 —— schema 的 `max_length` 只封 API 路径，`normalize_entries`
    是所有调用方的共同入口，闸必须在这里也有一道。
    """
    from app.core.errors import PcsError
    from app.services.supplier.actual_data_service import normalize_entries

    ok = [{"name": f"参数{i}", "value": float(i), "unit": ""} for i in range(50)]
    assert len(normalize_entries(ok)) == 50  # 边界内放行

    too_many = ok + [{"name": "溢出", "value": 1.0, "unit": ""}]
    with pytest.raises(PcsError) as exc:
        normalize_entries(too_many)
    assert exc.value.code == "ACTUAL_DATA_VALIDATION"
    assert "50" in exc.value.message, "报错须说明上限值，否则录入者不知该删到几条"


def test_actual_data_request_schema_caps_entries() -> None:
    """schema 侧同样封顶 —— 越界应在 422 就被挡下，不进 service。"""
    from pydantic import ValidationError

    from app.schemas.supplier import ActualDataEntryRequest

    entries = [{"name": f"参数{i}", "value": float(i)} for i in range(50)]
    assert len(ActualDataEntryRequest(entries=entries).entries) == 50

    with pytest.raises(ValidationError):
        ActualDataEntryRequest(entries=entries + [{"name": "x", "value": 1.0}])
