"""手工录入路径能真的写进这三列（否则新列永远进不了数据）。"""
from __future__ import annotations

import uuid

import pytest

from app.services.heat.heat_data_service import HeatCalcInput, save_heat_calc_result


@pytest.mark.asyncio
async def test_manual_entry_persists_the_three_confirmed_fields(db):
    inp = HeatCalcInput(
        tube_rows=8, skin_temp_min=39.2, skin_temp_max=93.4,
    )
    row = await save_heat_calc_result(
        db, project_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
        tag_number="E-301", exchanger_category="AIR_COOL", inp=inp)
    assert row.tube_rows == 8
    assert row.skin_temp_min == pytest.approx(39.2)
    assert row.skin_temp_max == pytest.approx(93.4)
