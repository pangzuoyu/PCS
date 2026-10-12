"""htri_parser 增强：用户 2026-12-12 裁决要进规格书的字段。

## ⚠️ 先说清楚这个 parser 目前的真实边界

`sample/` 下 4 个真实 HTRI 文件（`dmc.out` / `200FlexiCoking1.out` /
`huafeng140_FCC2015.out` / `proii .out`）**全都解析不了** —— 它们是
HTRI **输入卡**（`DUTY 1,1/2,12` 是输入语法），首行不是版本横幅，
`detect_version` 直接返回 None。

parser 一直是对着 `tests/services/heat/fixtures/*.txt` 里**手写的合成
fixture** 开发的（`Key: value` 简化格式）。所以本次增强是**在既有格式上
加字段**，不是让它读懂真实 HTRI 输出 —— 后者是另一件事，见 TODOS.md。

## 多值字段的两种分隔符

HTRI 的「一标签多值」字段用 `/` 或 `,` 分隔，且**同一份报表里两种都出现**：
`Skin temperature: 39.24/91.03`（斜杠）与 `Tubepasses/Tuberows: 2/4`（斜杠）。
而 `A-101.xls` 的 Xace 报表里是 `39.24 | 91.03`（竖线，Excel 表格）。
本 parser 只认前两种纯文本形式；竖线形式属 Excel 解析（另一条链路）。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.heat.htri_parser import parse_htri

HEAD = "HTRI Xist v6.0 Output Report\n"
COMMON = ("Case Name: T\nHeat Duty: 450.0 kW\nOverall U: 45.0 W/m2K\n"
          "Area Required: 12.0 m2\n")


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "htri.txt"
    p.write_text(HEAD + COMMON + body, encoding="utf-8")
    return p


@pytest.mark.asyncio
async def test_skin_temperature_min_max(tmp_path):
    """壁温进规格书 → 成对的 min/max。"""
    d = parse_htri(_write(tmp_path, "Skin Temperature: 39.24/91.03\n"))
    assert d.skin_temp_min_c == pytest.approx(39.24)
    assert d.skin_temp_max_c == pytest.approx(91.03)


@pytest.mark.asyncio
async def test_tube_rows_is_parsed_independently_of_tube_passes(tmp_path):
    """⚠️ `Tubepasses/Tuberows: 2/4` —— 管程数 2、管排数 4。

    登记时最容易只取第一个数，于是「管程数」悄悄变成「管排数」，
    而两者在报表里是两个字段（用户裁决：管排数空冷器专属）。
    """
    d = parse_htri(_write(tmp_path, "Tubepasses/Tuberows: 2/4\n"))
    assert d.tube_rows == 4, "取了第一个数 —— 那是管程数不是管排数"


@pytest.mark.asyncio
async def test_two_phase_fractions_hot_side(tmp_path):
    """两相含量要显示 → 汽/液 × 进出口，4 个值。"""
    d = parse_htri(_write(
        tmp_path, "Vapor: 85.42/2.70\nLiquid: 14.58/97.30\n"))
    assert d.vapor_wt_frac_in == pytest.approx(85.42)
    assert d.vapor_wt_frac_out == pytest.approx(2.70)
    assert d.liquid_wt_frac_in == pytest.approx(14.58)
    assert d.liquid_wt_frac_out == pytest.approx(97.30)


@pytest.mark.asyncio
async def test_fin_geometry_all_five(tmp_path):
    """TODO-056 第一批：5 个翅片/风机几何字段。"""
    d = parse_htri(_write(tmp_path, (
        "Fin Height: 12.700\n"
        "Fin Thickness: 0.406\n"
        "Fin Root Diameter: 19.050\n"
        "Over Fin Diameter: 19.862\n"
        "Tip Clearance: 9.525\n")))
    assert d.fin_height_mm == pytest.approx(12.7)
    assert d.fin_thickness_mm == pytest.approx(0.406)
    assert d.fin_root_diameter_mm == pytest.approx(19.05)
    assert d.over_fin_diameter_mm == pytest.approx(19.862)
    assert d.tip_clearance_mm == pytest.approx(9.525)


@pytest.mark.asyncio
async def test_missing_new_fields_are_none_not_errors(tmp_path):
    """缺新字段必须解析成功、值为 None —— 不能因为一个新键就把整份文件判废。

    老版本 HTRI 报表没有翅片几何；一份整体有效、只是缺新字段的文件
    被判 `HtriParseError`，等于**一次升级就让全部历史导入失败**。
    """
    d = parse_htri(_write(tmp_path, "Tube Count: 2716\n"))
    assert d.tube_count == 2716
    assert d.skin_temp_min_c is None
    assert d.tube_rows is None


@pytest.mark.asyncio
async def test_single_value_multi_field_does_not_raise(tmp_path):
    """只有一个值的「多值」字段 → 后半段为 None，不抛。"""
    d = parse_htri(_write(tmp_path, "Skin Temperature: 39.24\n"))
    assert d.skin_temp_min_c == pytest.approx(39.24)
    assert d.skin_temp_max_c is None


# --- 端到端：解析 → 落库 -------------------------------------------------------
#
# ⚠️ 「parser 能解析出值」不等于「值进了数据库」。中间隔着
# `map_htri_to_heat_input` 的字段映射 —— 那一层漏一个 key 就是
# 「解析了、报表里还是空的」，而没有任何一层会报错。


@pytest.mark.asyncio
async def test_parsed_values_actually_reach_the_database(tmp_path, db):
    """htri_parser 解析出的新字段必须真的落进 heat_results。"""
    import uuid

    from app.services.heat.heat_data_service import map_htri_to_heat_input, save_heat_calc_result

    p = tmp_path / "htri.txt"
    p.write_text(HEAD + COMMON + (
        "Shell Diameter: 1.600 m\nTube Length: 6.000 m\nTube Count: 2716\n"
        "Baffle Spacing: 0.450 m\n"
        "Skin Temperature: 39.24/91.03\n"
        "Tubepasses/Tuberows: 2/4\n"
        "Vapor: 85.42/2.70\nLiquid: 14.58/97.30\n"
        "Fan Count: 2\nBundle Area: 120.0 m2\nAir Inlet T: 308.15 K\n"
        "Hot Inlet T: 423.15 K\nHot Outlet T: 353.15 K\n"
        "Hot Mass Flow: 0.800 kg/s\nHot Cp: 2100 J/kg·K\n"
    ), encoding="utf-8")

    inp = map_htri_to_heat_input(parse_htri(p), equipment_no="E-401")
    row = await save_heat_calc_result(
        db, project_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
        tag_number="E-401", exchanger_category="AIR_COOL", inp=inp)

    assert row.skin_temp_min == pytest.approx(39.24), "壁温 min 没落库"
    assert row.skin_temp_max == pytest.approx(91.03), "壁温 max 没落库"
    assert row.tube_rows == 4, "管排数没落库（或取了管程数 2）"

    for key, want in (("vapor_wt_frac_in", 85.42), ("vapor_wt_frac_out", 2.70),
                      ("liquid_wt_frac_in", 14.58), ("liquid_wt_frac_out", 97.30)):
        assert row.shell_params[key] == pytest.approx(want), f"{key} 没落库"

    # 翅片几何：值可以是 None（本文件没给），但**键必须在** ——
    # 下游按 `in` 判断时，缺键与 None 会走不同分支。
    for key in ("fin_height_mm", "fin_thickness_mm", "fin_root_diameter_mm",
                "over_fin_diameter_mm", "tip_clearance_mm"):
        assert key in row.ache_params, f"{key} 不在 ache_params —— 键集漏了"


@pytest.mark.asyncio
async def test_fin_geometry_reaches_database_when_present(tmp_path, db):
    """本文件给了翅片几何 → 值也要真的进去（不只是键存在）。"""
    import uuid

    from app.services.heat.heat_data_service import map_htri_to_heat_input, save_heat_calc_result

    p = tmp_path / "htri.txt"
    p.write_text(HEAD + COMMON + (
        "Fan Count: 2\nBundle Area: 120.0 m2\nAir Inlet T: 308.15 K\n"
        "Fin Height: 12.700\nFin Thickness: 0.406\n"
        "Fin Root Diameter: 19.050\nOver Fin Diameter: 19.862\n"
        "Tip Clearance: 9.525\n"
    ), encoding="utf-8")

    inp = map_htri_to_heat_input(parse_htri(p), equipment_no="E-402")
    row = await save_heat_calc_result(
        db, project_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
        tag_number="E-402", exchanger_category="AIR_COOL", inp=inp)

    assert row.ache_params["fin_height_mm"] == pytest.approx(12.7)
    assert row.ache_params["tip_clearance_mm"] == pytest.approx(9.525)
    assert row.ache_params["over_fin_diameter_mm"] == pytest.approx(19.862)
