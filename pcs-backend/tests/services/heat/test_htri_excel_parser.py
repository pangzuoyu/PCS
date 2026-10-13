"""htri 报表的 **Excel 版**解析。

用户 2026-10-13 澄清：`sample/A-101.xls` 就是 HTRI 文件的 Excel 版。
所以真实样本一直都在 —— TODO-059 说的「缺样本」是错的，真实问题是
**parser 读错了格式**：它在解析 `Key: value` 的纯文本，而 HTRI 报表是
「标签 + 单位 + 数值」的固定宽度表格。

## 布局（两份真实文件实测）

    Xace  A-101.xls          TEMA  131-E-102-EOR.xls
    表头 Process Conditions   表头 Fluid Allocation
         |  Outside | Tubeside     |  Shell Side | Tube Side
    值列   6 / 10 | 14 / 16        值列   6 / 10 | 14 / 18

**每行的形状**：`标签(列0) | 单位(列2~5) | 值…`。第二组标签在列 10
（`Actual U` / `Area` / `Tube OD` …），标签与单位之间隔着合并单元格。

**分界列必须从表头行推**：两份文件的侧名不同（Outside/Tubeside vs
Shell Side/Tube Side），列位也不同（14/16 vs 14/18）。硬编码 12 会在
其中一份上静默取错侧的值 —— 而报表不会报错，只是温度对不上。
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.services.heat.htri_excel_parser import (
    HtriExcelParseError,
    parse_htri_excel,
)

SAMPLE = Path(__file__).resolve().parents[3].parent / "sample"
XACE = SAMPLE / "A-101.xls"
TEMA = SAMPLE / "131-E-102-EOR.xls"


def _need(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"{path.name} 不在 sample/")


@pytest.mark.asyncio
async def test_xace_core_fields():
    """Xace（空冷器）的基本热工字段。"""
    _need(XACE)
    d = parse_htri_excel(XACE)
    assert d.exchanger_kind == "AIR_COOLER"
    assert d.heat_duty_w == pytest.approx(0.3103e6, rel=1e-3), "热负荷 0.310 MW"
    assert d.area_required_m2 == pytest.approx(580.567, rel=1e-3)
    assert d.bundle_area_m2 == pytest.approx(580.567, rel=1e-3)


@pytest.mark.asyncio
async def test_xace_two_phase_and_skin_temperature():
    """用户 2026-12-12 裁决要显示的字段，必须从真实报表里真读得出来。"""
    _need(XACE)
    d = parse_htri_excel(XACE)
    # `Weight fraction vapor, In/Out | 1.0 | 1.0 | 1.0 | 0.117`
    # ⚠️ **热侧 = 管程侧**：Xace 的 TUBE 是工艺侧（131.79→54.99 降温）。
    # 热侧 = 管程侧（TUBE）= 后两个值 1.0 / 0.117
    assert d.vapor_wt_frac_in == pytest.approx(1.0), "气相含量取错侧了"
    assert d.vapor_wt_frac_out == pytest.approx(0.117)
    # 冷侧（空气侧 OUTSIDE）= 前两个值，都是 1.0
    assert d.cold_vapor_wt_frac_in == pytest.approx(1.0)
    # `Skin temperature, Min/Max | (Deg C) | 39.24 | 91.03 | 39.60 | 93.42`
    assert d.skin_temp_min_c == pytest.approx(39.60), "取的是空气侧还是管程侧？"
    assert d.skin_temp_max_c == pytest.approx(93.42)


@pytest.mark.asyncio
async def test_xace_tube_rows_is_not_tube_passes():
    """`Number of passes | 2.0` 与 `Number of rows | 4.0` 是两个字段。"""
    _need(XACE)
    d = parse_htri_excel(XACE)
    assert d.tube_passes == 2
    assert d.tube_rows == 4


@pytest.mark.asyncio
async def test_tema_shell_tube_core_fields():
    """TEMA（管壳式）走同一套解析 —— 且**不**套空冷器专属字段。"""
    _need(TEMA)
    d = parse_htri_excel(TEMA)
    assert d.exchanger_kind == "SHELL_TUBE"
    assert d.heat_duty_w == pytest.approx(44711e3, rel=1e-3), "Heat Exchanged 44711 kW"
    assert d.area_required_m2 == pytest.approx(1945.40, rel=1e-3), "Surf/Unit 毛面积"
    assert d.shell_id_mm == pytest.approx(1600.0)
    assert d.bundle_area_m2 is None, "管壳式没有风机束区面积"


@pytest.mark.asyncio
async def test_side_boundary_comes_from_the_header_not_a_hardcoded_column():
    """⚠️ 两份文件的侧名列位不同（14/16 vs 14/18），分界必须从表头推。

    硬编码分界列的后果不是报错 —— 是**静默取到另一侧的值**：
    Xace 的管程进口温度 131.79 与空气侧 32.00 差 4 倍，报表照样出，
    只是温度完全不对。
    """
    _need(XACE)
    _need(TEMA)
    x = parse_htri_excel(XACE)
    t = parse_htri_excel(TEMA)
    # 两份都应把**管程侧**的值放到 tube_* 字段
    assert x.hot_inlet_t_c == pytest.approx(131.79), "Xace 管程进口温度"
    # TEMA：壳程被加热（186.25→326.10）= 冷侧；管程冷凝（400.20→279.72）= 热侧
    assert t.cold_inlet_t_c == pytest.approx(186.25), "TEMA 冷侧（壳程）进口温度"
    assert t.hot_inlet_t_c == pytest.approx(400.20), "TEMA 热侧（管程）进口温度"


@pytest.mark.asyncio
async def test_unknown_file_raises_a_specific_error():
    """读不出报表结构时报**明确的错**，不是静默返回空结果。"""
    tmp = Path("/tmp") / "not-htri.xlsx"
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.append(["随便", "什么"])
    wb.save(tmp)
    with pytest.raises(HtriExcelParseError):
        parse_htri_excel(tmp)
    tmp.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_parsed_excel_feeds_the_same_persistence_path(db):
    """Excel 版解析结果必须能直接喂给现成的落库链路 ——
    另起一条写入路径就是两份「谁在写 heat_results」的真相来源。"""
    _need(XACE)
    from app.services.heat.heat_data_service import map_htri_to_heat_input, save_heat_calc_result

    inp = map_htri_to_heat_input(parse_htri_excel(XACE), equipment_no="E-901")
    row = await save_heat_calc_result(
        db, project_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
        tag_number="E-901", exchanger_category="AIR_COOL", inp=inp)
    assert row.duty == pytest.approx(0.3103e6, rel=1e-3)
    assert row.skin_temp_min == pytest.approx(39.60)
    assert row.tube_rows == 4


@pytest.mark.asyncio
async def test_reads_every_worksheet_not_just_the_first():
    """⚠️ 用户提示过的点：Xace 有 4 个 sheet。

    `Output Summary`（50 个标签）只占一半，另一半在 `Final Results`。
    只读第一个会漏字段 —— 而漏读**不报错**，只是少几个值。
    """
    _need(XACE)
    from app.services.heat.htri_excel_parser import _read_rows

    sheets = _read_rows(XACE)
    assert len(sheets) >= 3, f"只读到 {len(sheets)} 个 sheet"
    # 只有一张表能拿到侧表头 —— 诊断表没有，但它们仍应被跳过而不是报错
    d = parse_htri_excel(XACE)
    # Final Results 独有的字段（Output Summary 里没有）
    assert d.tip_clearance_mm is not None or d.extended_area_m2 is not None, \
        "第二张工作表的字段一个都没读到 —— 可能只读了第一个 sheet"


@pytest.mark.asyncio
async def test_power_conversion_uses_the_unit_not_the_magnitude():
    """⚠️ TEMA `Heat Exchanged 44711 kW` 与某个 W 单位的 44711 无法从数字
    区分。猜大小 = 1000 倍误差，而报表照出，只是热负荷离谱。"""
    _need(TEMA)
    d = parse_htri_excel(TEMA)
    assert d.heat_duty_w == pytest.approx(44711e3, rel=1e-3)


# --- TODO-056 剩余 5 个 ACHE 字段 ----------------------------------------------
#
# 真实 `A-101.xls` 的 `2 - Final Results` 里确实有这 5 个标签（实测行）：
#   `Air humidity` / `Fins per unit length` / `Fin efficiency` /
#   `Unfinned length` / `Unheated length`
# 它们此前既不在 `AcheParams`、也不在注册表 —— 真实报表里有、我们取不到。


@pytest.mark.asyncio
async def test_remaining_ache_fields_are_parsed_from_the_real_report():
    _need(XACE)
    d = parse_htri_excel(XACE)
    # ⚠️ `Air humidity` 在这份报表里**只有标签和单位、没有值**：
    #   `[2 - Final Results] r13` = (16,'Air humidity') (20,'(%)')，中间为空。
    #   所以 None 是**正确**的解析结果 —— 写成 50.0 会是我编的数字，
    # 而它让这条测试一直红着，看起来像 parser 有 bug。
    # 断言「是 None」是为了在 HTRI 哪天开始给值时**红一次**提醒复核。
    assert d.air_humidity_percent is None, \
        (f"报表里 Air humidity 仍无值；解析器却给出了 {d.air_humidity_percent} "
         "—— 要么 HTRI 开始输出了（好事，该钉具体数），要么 parser 在编数")
    assert d.fin_density_per_m == pytest.approx(433.1), \
        f"Fins per unit length 取不到（实得 {d.fin_density_per_m}）"
    assert d.fin_efficiency_percent == pytest.approx(80.0)
    assert d.unfinned_length_mm == pytest.approx(0.0)
    assert d.unheated_length_mm == pytest.approx(127.0)


@pytest.mark.asyncio
async def test_tip_clearance_is_not_silently_none():
    """`Tip clearance` 上一轮登记了却取不到值 —— 登记了不等于有数据。

    这条把「登记了但恒为 None」钉成可失败的断言：那正是 c1 拒绝登记
    「ORM 上没有的字段」的同一个理由，只是这次是**解析器**没覆盖到。
    """
    _need(XACE)
    d = parse_htri_excel(XACE)
    assert d.tip_clearance_mm is not None, \
        "Tip clearance 已登记却恒为 None —— 字段树里选得到、查出来是空列"


@pytest.mark.asyncio
async def test_the_five_new_fields_reach_the_registry():
    """解析出来的字段必须**注册** —— 只有 parser 没有注册表 = 报表选不到。"""
    from app.services.report.datasource_registry import DATASOURCES

    fields = DATASOURCES["HEAT_RESULTS"].fields
    for name in ("ache_params.air_humidity_percent",
                 "ache_params.fin_density_per_m",
                 "ache_params.fin_efficiency_percent",
                 "ache_params.unfinned_length_mm",
                 "ache_params.unheated_length_mm"):
        assert name in fields, f"{name} 未注册 —— 解析出来了但报表里选不到"
        assert fields[name].exchanger_type == "AIR_COOLER"
        assert fields[name].level == "DETAIL"
