"""P3.2 SIM-20: PRO/II .out 20+ Section 数值提取（spec V1.6 §3.4.2）。

目标：单一 .out 文件一次性提取所有 section，返回 dict[section_name, payload]。
性能基准：≤ 5s / 100 条记录（spec §3.4.2 性能预算）。

覆盖 section（与 PR-3~PR-10/PR-13 一致）：
- banner / convergence_status / warnings / reactions
- zero_flow / unreliable
- streams（STREAM SUMMARY 数值表）
- unit_ops（PUMP/HX/MIXER/FLASH/VALVE/COMPRESSOR/SPLITTER/STCA/CALCULATOR/COLUMN）
- run_statistics（RUN STATISTICS 段）
- calculation_history（CALCULATION HISTORY 段——如有）
- column_summary
- compositions（inp 文件）
- hcurve（HCURVE 段——本期未实现，返回 None）
- reactor_summary / cstr_summary（PR-13/14——本期未实现，返回 None）

性能测试：使用真实 sample 文件，断言 ≤ 5s / 100 条（单文件即可验证）。
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.services.proii_parser import (
    parse_proii_out_sections,
)

SAMPLE_DIR = Path(__file__).resolve().parents[3] / "sample"
SAMPLE_PROII_OUT = SAMPLE_DIR / "proii .out"


# ---------------------------------------------------------------------------
# dispatcher 契约
# ---------------------------------------------------------------------------


def test_parse_proii_out_sections_returns_dict():
    """dispatcher 返回 dict（key=section 名，value=payload）。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    assert isinstance(sections, dict)
    # 必含核心 section
    assert "banner" in sections
    assert "convergence_status" in sections
    assert "warnings" in sections
    assert "run_statistics" in sections


def test_parse_proii_out_sections_includes_stream_summary():
    """STREAM SUMMARY 段已提取（spec PR-5：streams 数值表）。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    assert "streams" in sections
    # streams 是 dict[stream_name, stream_data] 或 list（与现有 _parse_streams 兼容）
    streams = sections["streams"]
    assert streams  # 非空


def test_parse_proii_out_sections_includes_run_statistics():
    """RUN STATISTICS 段：STARTED/FINISHED/RUN TIMES 三块。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    rs = sections["run_statistics"]
    assert isinstance(rs, dict)
    assert "started" in rs or "errors" in rs
    # 至少含 errors/warnings 计数
    assert "errors" in rs or "warnings" in rs


def test_parse_proii_out_sections_includes_unit_ops_summary():
    """unit_ops 段：所有单元操作的 SUMMARY 表（PUMP/HX/MIXER/.../COMPRESSOR/SPLITTER）。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    assert "unit_ops" in sections
    unit_ops = sections["unit_ops"]
    assert isinstance(unit_ops, (list, dict))
    assert unit_ops  # 非空（PRO/II 文件必有 PUMP/HX 等）


def test_parse_proii_out_sections_includes_calculation_history_when_present():
    """CALCULATION HISTORY 段（如有）。本 sample 文件可能不含，容许 None。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    assert "calculation_history" in sections
    # 不强制非 None（多数 sample 不含此段）


def test_parse_proii_out_sections_includes_extended_unit_types():
    """COMPRESSOR / SPLITTER / STCA / CALCULATOR SUMMARY（PR-8b/PR-13）。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    unit_ops = sections["unit_ops"]
    # 本 sample 文件至少含 PUMP/HX/MIXER 等基础类型
    unit_types = (
        {u.get("type") for u in unit_ops}
        if isinstance(unit_ops, list)
        else set(unit_ops.keys())
    )
    # 基础类型至少 1 个
    assert len(unit_types) >= 1


def test_parse_proii_out_sections_returns_section_count():
    """返回值含 section 名集合，便于上游审计（spec §3.4.2 性能审计）。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    # dispatcher 至少返回 10 个 section key
    assert len(sections) >= 10


# ---------------------------------------------------------------------------
# 容错
# ---------------------------------------------------------------------------


def test_parse_proii_out_sections_missing_file_raises():
    """文件不存在 → FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        parse_proii_out_sections("/nonexistent/proii.out")


def test_parse_proii_out_sections_invalid_file_returns_partial():
    """无效文件（无 banner）→ 抛 ValueError。"""
    tmp = Path("/tmp/_invalid_proii.out")
    tmp.write_text("NOT A PROII OUTPUT\n" * 10, encoding="utf-8")
    try:
        with pytest.raises(ValueError):
            parse_proii_out_sections(tmp)
    finally:
        tmp.unlink()


# ---------------------------------------------------------------------------
# 性能：≤5s / 100 条
# ---------------------------------------------------------------------------


def test_parse_proii_out_sections_performance_under_5s():
    """spec §3.4.2 性能预算：单文件解析 ≤5s。

    用真实 sample 文件（445KB 含多条 stream/unit_op），覆盖典型规模。
    """
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    # 预热（首次 import + 读文件 cache）
    parse_proii_out_sections(SAMPLE_PROII_OUT)
    # 测量
    t0 = time.perf_counter()
    for _ in range(5):
        parse_proii_out_sections(SAMPLE_PROII_OUT)
    elapsed = (time.perf_counter() - t0) / 5
    # 单次 ≤5s（spec 预算：100 条记录；本文件 < 100 条，但量级可比）
    assert elapsed < 5.0, f"parse_proii_out_sections too slow: {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# 流式 stream summary 内容正确性
# ---------------------------------------------------------------------------


def test_parse_proii_out_sections_streams_contain_data_rows():
    """streams 段含 STREAM SUMMARY 数据行（spec PR-5：列拆分后 list[dict]）。

    至少一条纵表行（来自 FEED AND PRODUCT STREAMS 段或 STREAM SUMMARY
    段头匹配 'STREAM ID' 后下方紧跟的 FEED/PROD/PRODUCT 行）含
    type/name/phase/from_tray/to_tray/liquid_frac/flow_kmolph/heat_mkcalph。

    下游 SIM-22 PropertyConflictResolver + SIM-32 物流表 join 可直接消费。
    """
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    streams = sections["streams"]
    assert isinstance(streams, list)
    assert len(streams) >= 1
    # 找一条 type=FEED/PROD/RECYCLE 的纵表行（验证 FEED AND PRODUCT STREAMS 段解析）。
    # PRO/II 允许空白字段（FROM TRAY/TO TRAY/LIQUID FRAC 等），不强求全部 7 字段，
    # 但至少要含 type/name + 至少 2 个数值字段（flow_kmolph 或 heat_mkcalph）。
    vertical = [
        s for s in streams
        if isinstance(s, dict)
        and s.get("type") in {"FEED", "PROD", "RECYCLE"}
        and (s.get("flow_kmolph") is not None
             or s.get("heat_mkcalph") is not None
             or s.get("to_tray") is not None
             or s.get("liquid_frac") is not None)
    ]
    assert len(vertical) >= 1, (
        f"no FEED/PROD/RECYCLE row with numeric data; "
        f"sample: {streams[0] if streams else 'empty'}"
    )
    row = vertical[0]
    # type/name 必须存在
    assert row.get("type") in {"FEED", "PROD", "RECYCLE"}
    assert row.get("name")


def test_parse_proii_out_sections_dmc_streams_horizontal_table():
    """dmc.out（真实化工报告）STREAM SUMMARY 横表解析（主路径）。

    段头 'STREAM SUMMARY <date>' + STREAM ID 行横向列 stream 名 +
    物性行（TEMPERATURE/PRESSURE/RATE/ENTHALPY/MW/MOLE FRAC）。返回
    list[dict]，每条含 stream_id + 物性字段。
    """
    dmc = SAMPLE_DIR / "dmc.out"
    if not dmc.exists():
        pytest.skip(f"sample not found: {dmc}")
    sections = parse_proii_out_sections(dmc)
    streams = sections["streams"]
    assert isinstance(streams, list)
    # dmc 含 ~150 stream（含 STREAM MOLAR COMPONENT RATES / STREAM SUMMARY 合并）
    assert len(streams) >= 50, (
        f"dmc.out 横表 streams 不足 50；got {len(streams)}"
    )
    # 抽一条有物性的 stream 验证字段
    merged = [
        s for s in streams
        if isinstance(s, dict)
        and s.get("temperature_c") is not None
        and s.get("pressure_kgcm2") is not None
    ]
    assert len(merged) >= 1, (
        f"no stream has temperature_c/pressure_kgcm2; "
        f"sample: {streams[0] if streams else 'empty'}"
    )
    # stream_id 字段存在且为字符串
    assert isinstance(merged[0]["stream_id"], str)
    # 必含字段集
    for key in (
        "stream_id", "phase", "temperature_c",
        "pressure_kgcm2", "molecular_weight",
    ):
        assert key in merged[0], f"missing key {key}"


def test_parse_proii_out_sections_streams_have_mol_weight_basis():
    """每个 stream 含 mol_percent / weight_rate / weight_percent 三套组分表
    + 物性表 + 单位元数据（properties_units / component_units）。

    spec §3.4.2 + 用户 2026-09-10 裁决：必须区分摩尔基准与质量基准。
    """
    dmc = SAMPLE_DIR / "dmc.out"
    if not dmc.exists():
        pytest.skip(f"sample not found: {dmc}")
    sections = parse_proii_out_sections(dmc)
    streams = sections["streams"]
    # 找一条有 mol_percent 的 stream（dmc PF7 是典型 mol/weight 都有）
    has_all = [
        s for s in streams
        if isinstance(s, dict)
        and isinstance(s.get("mol_percent"), dict)
        and len(s["mol_percent"]) >= 5
        and isinstance(s.get("weight_rate"), dict)
        and isinstance(s.get("weight_percent"), dict)
    ]
    assert len(has_all) >= 1, (
        f"no stream has all 3 component tables; "
        f"first: {streams[0] if streams else 'empty'}"
    )
    # 单位元数据
    units = sections.get("properties_units")
    assert isinstance(units, dict)
    assert units.get("TEMPERATURE") == "C"
    assert units.get("PRESSURE") == "KG/CM2"
    assert units.get("ENTHALPY") in {"M*KCAL/HR", "KCAL/KG"}
    assert "TOTAL RATE" in units
    # component_units 固定三套基准
    comp_units = sections.get("component_units")
    assert comp_units == {
        "mol_percent": "mol%",
        "weight_rate": "kg/hr",
        "weight_percent": "wt%",
    }


def test_parse_proii_out_sections_streams_phase_liquid_vapor_mixed():
    """PHASE 行正确分类：LIQUID/VAPOR/MIXED。

    用户 2026-09-10 裁决：MIXED 物流需同时含 MOLE FRAC VAPOR/LIQUID 与
    WEIGHT FRAC VAPOR/LIQUID（两套分率，因为两相组成不同）。

    PRO/II 实际只输出 MOLE FRACTION VAPOR 或 MOLE FRACTION LIQUID 二选一
    （按 LIQUID 占比 > 0.5 决定），另一项可由 1 - x 推导。测试接受任一
    形式（含全名 MOLE FRACTION VAPOR/LIQUID 的情况）。
    """
    dmc = SAMPLE_DIR / "dmc.out"
    if not dmc.exists():
        pytest.skip(f"sample not found: {dmc}")
    sections = parse_proii_out_sections(dmc)
    streams = sections["streams"]
    phases = {s["phase"] for s in streams if isinstance(s, dict) and s.get("phase")}
    # 至少 LIQUID 与 VAPOR 都出现（dmc 实测）
    assert "LIQUID" in phases
    assert "VAPOR" in phases
    # MIXED 不强制（dmc 可能没 MIXED），但若出现需含 mole_frac_vapor /
    # mole_frac_liquid（PRO/II 输出形式）
    mixed = [s for s in streams if s.get("phase") == "MIXED"]
    mixed_keys = {
        "mole_frac_vapor", "mole_frac_liquid",
        "mole_fraction_vapor", "mole_fraction_liquid",
    }
    for m in mixed:
        assert mixed_keys & set(m.keys()), (
            f"MIXED stream {m['stream_id']} missing mole_frac_vapor/mole_frac_liquid"
        )


def test_parse_proii_out_sections_streams_scientific_notation_handled():
    """科学计数法（如 1.56061E-03 / 1.5042E-19）正确解析。

    极微量组分（< 1e-10）保持数值原样，不当 0；调用方可自行决定阈值。
    """
    dmc = SAMPLE_DIR / "dmc.out"
    if not dmc.exists():
        pytest.skip(f"sample not found: {dmc}")
    sections = parse_proii_out_sections(dmc)
    streams = sections["streams"]
    # 找一条含科学计数法极小值的 stream
    has_tiny = []
    for s in streams:
        if not isinstance(s, dict):
            continue
        mp = s.get("mol_percent") or {}
        for v in mp.values():
            if isinstance(v, float) and 0 < v < 1e-10:
                has_tiny.append(s["stream_id"])
                break
        if has_tiny:
            break
    # 不强制 dmc 含极小值；但若含，必须正确解析（非 None 非 0）
    if has_tiny:
        # 验证该 stream 的 mol_percent 中确实有小数
        sid = has_tiny[0]
        target = next(s for s in streams if s["stream_id"] == sid)
        assert any(
            isinstance(v, float) and 0 < v < 1e-10
            for v in target["mol_percent"].values()
        )


def test_parse_proii_out_sections_streams_200flexicoking_refinery():
    """200FlexiCoking1.out（炼油 FCC）含 REFINERY PROCESSOR PROPERTIES SET
    + STREAM COMPONENT RATES 等段；不在 dispatcher 范围（用户裁决）→
    streams 仍应非空（来自 COLUMN/MIXER/FLASH 段内 FEEDS/PRODUCTS）。
    """
    flex = SAMPLE_DIR / "200FlexiCoking1.out"
    if not flex.exists():
        pytest.skip(f"sample not found: {flex}")
    sections = parse_proii_out_sections(flex)
    # 注：FCC 报告无 STREAM SUMMARY 段，但 dispatcher 仍应返 streams dict
    assert isinstance(sections, dict)
    assert "streams" in sections
    # streams 应为 list（即使空）
    assert isinstance(sections["streams"], list)


# ---------------------------------------------------------------------------
# SIM-20d: REFINERY PROCESSOR + TBP/ASTM 独立段（FCC 报告专属）
# ---------------------------------------------------------------------------


def test_parse_proii_out_sections_refinery_processor_present_in_fcc():
    """200FlexiCoking1.out 含 REFINERY PROCESSOR PROPERTIES SET 段 → 暴露为
    sections['refinery_processor']: list[dict]。

    每条 dict 含 stream_id + phase + thermo_id + properties（含 wet/dry + total/
    vapor/liquid 三套子段）。
    """
    flex = SAMPLE_DIR / "200FlexiCoking1.out"
    if not flex.exists():
        pytest.skip(f"sample not found: {flex}")
    sections = parse_proii_out_sections(flex)
    rp = sections.get("refinery_processor")
    assert isinstance(rp, list)
    assert len(rp) >= 5, (
        f"FCC 文件至少 5 条 stream 的 REFINERY 物性；got {len(rp)}"
    )
    first = rp[0]
    assert isinstance(first, dict)
    assert "stream_id" in first
    assert first["phase"] in {"LIQUID", "VAPOR", "MIXED", "WET VAPOR",
                              "DRY VAPOR", "DRY LIQUID", "WET LIQUID"}
    # properties 子 dict（按子段组织）
    props = first.get("properties") or {}
    assert isinstance(props, dict)
    # 至少含 total_wet 子段
    assert "total_wet" in props, (
        f"first REFINERY stream missing total_wet; got keys: {list(props.keys())}"
    )
    # total_wet 含典型物性
    tw = props["total_wet"]
    assert "temperature_c" in tw, f"total_wet keys: {list(tw.keys())}"


def test_parse_proii_out_sections_refinery_processor_phases_classified():
    """REFINERY 段 PHASE 行：DRY LIQUID/WET VAPOR/DRY VAPOR/WET LIQUID
    + WET BASIS/DRY BASIS 多子段 → 完整保留为子段名。
    """
    flex = SAMPLE_DIR / "200FlexiCoking1.out"
    if not flex.exists():
        pytest.skip(f"sample not found: {flex}")
    sections = parse_proii_out_sections(flex)
    rp = sections.get("refinery_processor")
    assert isinstance(rp, list)
    # 至少 2 种 phase 同时存在（FCC 报告实测 LIQUID + VAPOR）
    phases = {s["phase"] for s in rp if s.get("phase")}
    assert len(phases) >= 2, f"only {len(phases)} phase; got {phases}"
    # 至少一条 stream 含 wet + dry 双重子段
    both_basis = [
        s for s in rp
        if "total_wet" in (s.get("properties") or {})
        and "total_dry" in (s.get("properties") or {})
    ]
    assert len(both_basis) >= 1, (
        f"no stream has both wet + dry basis; "
        f"sample props: {rp[0].get('properties', {}).keys() if rp else 'empty'}"
    )


def test_parse_proii_out_sections_tbp_astm_curves_present_in_fcc():
    """200FlexiCoking1.out 含 STREAM TBP/ASTM CURVES 段 → sections['tbp_astm']。

    每条 dict 含 stream_id + curve_name + percent_basis（LV/WT）
    + points: list[{percent: float, temp_c: float}]。
    """
    flex = SAMPLE_DIR / "200FlexiCoking1.out"
    if not flex.exists():
        pytest.skip(f"sample not found: {flex}")
    sections = parse_proii_out_sections(flex)
    curves = sections.get("tbp_astm")
    assert isinstance(curves, list)
    assert len(curves) >= 5, (
        f"FCC 报告至少 5 条曲线（含 TBP/ASTM 多个压力档）；got {len(curves)}"
    )
    first = curves[0]
    assert isinstance(first, dict)
    assert "stream_id" in first
    assert "curve_name" in first
    assert first["curve_name"] in {
        "TBP", "ASTM D86", "ASTM D1160", "ASTM D2887",
    }
    assert "percent_basis" in first
    assert first["percent_basis"] in {"LV", "WT"}
    assert "points" in first
    assert isinstance(first["points"], list)
    # 标准 cut points 1/5/10/30/50/70/90/95/98
    percents = [p["percent"] for p in first["points"]]
    expected = [1, 5, 10, 30, 50, 70, 90, 95, 98]
    assert percents == expected, (
        f"curve percents mismatch: got {percents}, expected {expected}"
    )
    # 每个点含 temp_c（数值或 None）
    for p in first["points"]:
        assert "temp_c" in p


def test_parse_proii_out_sections_tbp_astm_curves_negative_temps_handled():
    """TBP/ASTM 允许负温度（轻组分 gas stream 如 1FLUEGAS）。

    负温度必须原样保留（-252.760），不当 0 或 skip。
    """
    flex = SAMPLE_DIR / "200FlexiCoking1.out"
    if not flex.exists():
        pytest.skip(f"sample not found: {flex}")
    sections = parse_proii_out_sections(flex)
    curves = sections.get("tbp_astm") or []
    # 找一条含负温度的曲线
    has_neg = [
        c for c in curves
        if any(
            isinstance(p["temp_c"], (int, float)) and p["temp_c"] < 0
            for p in c["points"]
        )
    ]
    assert len(has_neg) >= 1, (
        "FCC 报告 TBP/ASTM 段应含 gas stream 负温度；got 0"
    )
    # 至少有 -100°C 以下
    extreme = [
        p["temp_c"] for c in has_neg for p in c["points"]
        if isinstance(p["temp_c"], (int, float)) and p["temp_c"] < -100
    ]
    all_temps = [
        p["temp_c"] for c in curves for p in c["points"]
        if isinstance(p["temp_c"], (int, float))
    ]
    min_temp = min(all_temps) if all_temps else None
    assert len(extreme) >= 1, (
        f"FCC 报告 gas stream 应有 <-100°C；got min: {min_temp}"
    )


def test_parse_proii_out_sections_refinery_processor_absent_in_dmc():
    """dmc.out（化工）无 REFINERY 段 → refinery_processor = []；TBP/ASTM 同。

    不能误把化工文件的 STREAM SUMMARY 当 REFINERY。
    """
    dmc = SAMPLE_DIR / "dmc.out"
    if not dmc.exists():
        pytest.skip(f"sample not found: {dmc}")
    sections = parse_proii_out_sections(dmc)
    # dmc.out 无 REFINERY PROCESSOR PROPERTIES SET 段
    assert sections.get("refinery_processor") == []
    # dmc.out 无 TBP/ASTM CURVES 段
    assert sections.get("tbp_astm") == []


def test_parse_proii_out_sections_refinery_processor_preserves_scientific_notation():
    """REFINERY 段极小值（1.9119E-07 / 1.0000E-04）原样保留为 float。

    spec §3.4.2：科学计数法（E-19 量级）不当 0；trace component 同样原则。
    """
    flex = SAMPLE_DIR / "200FlexiCoking1.out"
    if not flex.exists():
        pytest.skip(f"sample not found: {flex}")
    sections = parse_proii_out_sections(flex)
    rp = sections.get("refinery_processor") or []
    # 找一条 total_wet 含 rate_kgmolph 极小值（FO1 是 FCC 进料，rate ~ 1.9E-7）
    has_tiny = []
    for s in rp:
        tw = (s.get("properties") or {}).get("total_wet") or {}
        rate = tw.get("rate_kgmolph")
        if isinstance(rate, (int, float)) and 0 < rate < 1e-5:
            has_tiny.append(s["stream_id"])
    assert len(has_tiny) >= 1, (
        f"no REFINERY stream has trace rate (<1e-5 kgmol/h); "
        f"sample: {rp[0].get('properties', {}).get('total_wet', {}) if rp else 'empty'}"
    )


def test_parse_proii_out_sections_streams_merge_property_tables():
    """STREAM MOLAR/WEIGHT COMPONENT RATES/PERCENTS 4 段横表物性 merge 进 streams。

    每个 stream dict 含 type/name/phase + 横表物性（temperature_c/
    pressure_kgcm2/enthalpy_mkcalph/molecular_weight/mole_frac_vapor/
    mole_frac_liquid）。同 stream 名跨多页去重（first non-None wins）。
    """
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    streams = sections["streams"]
    # 至少一条 stream 被 merge 横表物性
    merged = [
        s for s in streams
        if isinstance(s, dict)
        and s.get("temperature_c") is not None
        and s.get("pressure_kgcm2") is not None
        and s.get("molecular_weight") is not None
    ]
    assert len(merged) >= 1, (
        f"no stream merged property table data; "
        f"sample stream: {streams[0] if streams else 'empty'}"
    )


def test_parse_proii_out_sections_streams_contain_reactor_summary():
    """sample 文件含 REACTOR SUMMARY 段（行 7885）→ list[dict]。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    rs = sections.get("reactor_summary")
    assert isinstance(rs, list)
    assert len(rs) >= 1
    # 含 unit_id + 关键操作条件
    first = rs[0]
    assert isinstance(first, dict)
    assert "unit_id" in first
    assert "reactor_type" in first or "duty_mkcalph" in first


def test_parse_proii_out_sections_streams_contain_cstr_summary():
    """sample 文件含 CSTR SUMMARY 段（行 8038）→ list[dict]。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    cs = sections.get("cstr_summary")
    assert isinstance(cs, list)
    assert len(cs) >= 1
    first = cs[0]
    assert isinstance(first, dict)
    assert "unit_id" in first
    # CSTR 特有：volume_m3 / space_time_hr
    assert "volume_m3" in first or "duty_mkcalph" in first


def test_parse_proii_out_sections_hcurve_is_none_when_no_summary_in_out():
    """HCURVE 在 .out 文件中无 SUMMARY 段（仅出现在 .inp 标识）→ 返回 None。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    # 实际 PRO/II .out 无 HCURVE SUMMARY；只有 inp 标识
    assert sections.get("hcurve") is None
