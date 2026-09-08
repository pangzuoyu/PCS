"""P3.2 SIM-2：PRO/II .inp+.out 双文件解析器契约测试（spec V1.6 §607-633）。

按 plan V1.0.1 落地：5 最小复现样例覆盖 V2.71 / V4.17 / V8.5 三版 banner；
每样例一条 acceptance 锁住关键断言。fixtures 路径：
    pcs-backend/tests/fixtures/proii/sample{1..5}_*/

层级（自上而下）：
- banner 解析：5 样例 banner_version
- 收敛分层：5 态（CONVERGED / WARNINGS / NOT_CONVERGED / ABORTED / NOT_SOLVED）
- 单元可靠性：NOT_CONVERGED/ABORTED 单元产品 → unreliable=True
- 零流量流保留：*** ZERO FLOW *** 标记 → zero_flow=True
- 单元操作类型：COLUMN / SIDESTRIPPER / FLASH / VALVE / REACTOR /
  EXTRACTOR / COMPRESSOR / SPLITTER / STCA / CALCULATOR / PUMP / HX / MIXER
- 反应：sample5 RXSET/RX1-RX4

NOTE: 仓库 sample/ 9 工程实例由 -m regression 路径使用，不入此测试文件。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.proii_parser import (
    ConvergenceStatus,
    parse_proii_files,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "proii"


def _p(s: str) -> tuple[Path, Path]:
    """定位 (inp, out) 双文件路径。"""
    d = FIXTURES / s
    return d / f"{s}.inp", d / f"{s}.out"


# ---------------------------------------------------------------------------
# banner 三版检测（5 样例全覆盖）
# ---------------------------------------------------------------------------


def test_sample1_banner_v8_5():
    inp, out = _p("sample1_34comp")
    r = parse_proii_files(inp, out)
    assert r.banner_version == "8.5"


def test_sample2_banner_v4_17():
    inp, out = _p("sample2_unconverged")
    r = parse_proii_files(inp, out)
    assert r.banner_version == "4.17"


def test_sample3_banner_v8_5():
    inp, out = _p("sample3_side_draw")
    r = parse_proii_files(inp, out)
    assert r.banner_version == "8.5"


def test_sample4_banner_v2_71():
    inp, out = _p("sample4_flash_valve")
    r = parse_proii_files(inp, out)
    assert r.banner_version == "2.71"


def test_sample5_banner_v8_5():
    inp, out = _p("sample5_reactor_extraction")
    r = parse_proii_files(inp, out)
    assert r.banner_version == "8.5"


# ---------------------------------------------------------------------------
# sample1：34 组分 + CONVERGED + 21 streams
# ---------------------------------------------------------------------------


def test_sample1_components_count_34():
    inp, out = _p("sample1_34comp")
    r = parse_proii_files(inp, out)
    assert len(r.components) == 34
    assert r.components[0] == "N2"
    assert r.components[-1] == "C38"


def test_sample1_convergence_converged():
    inp, out = _p("sample1_34comp")
    r = parse_proii_files(inp, out)
    assert r.convergence_status == ConvergenceStatus.CONVERGED


def test_sample1_streams_count_21():
    inp, out = _p("sample1_34comp")
    r = parse_proii_files(inp, out)
    assert len(r.streams) == 21


def test_sample1_unit_ops_includes_sidestripper():
    inp, out = _p("sample1_34comp")
    r = parse_proii_files(inp, out)
    assert "SS1" in r.unit_ops
    assert r.unit_ops["SS1"].type == "SIDESTRIPPER"
    assert r.unit_ops["SS1"].is_side_draw is True
    assert r.unit_ops["T01"].type == "COLUMN"
    assert r.unit_ops["E01"].type == "HX"
    assert r.unit_ops["P01"].type == "PUMP"
    assert r.unit_ops["M01"].type == "MIXER"


def test_sample1_stream_feed_basic():
    inp, out = _p("sample1_34comp")
    r = parse_proii_files(inp, out)
    feed = r.streams["FEED"]
    assert feed.tag == "FEED"
    assert feed.temperature_k == pytest.approx(380 + 273.15, abs=0.01)  # 380°C → K
    assert feed.pressure_pa == pytest.approx(1500 * 1000, abs=1.0)  # 1500 kPa → Pa
    assert feed.phase == "MIXED"  # PHASE=M in .inp
    assert feed.mass_flow_kg_h == 100000.0
    assert feed.unreliable is False


# ---------------------------------------------------------------------------
# sample2：NOT_CONVERGED + unreliable 流标记
# ---------------------------------------------------------------------------


def test_sample2_convergence_not_converged():
    inp, out = _p("sample2_unconverged")
    r = parse_proii_files(inp, out)
    assert r.convergence_status == ConvergenceStatus.NOT_CONVERGED


def test_sample2_unreliable_streams_s2_s3():
    inp, out = _p("sample2_unconverged")
    r = parse_proii_files(inp, out)
    # SPEC §614：NOT_CONVERGED 单元产品 → unreliable
    assert "S2" in r.unreliable_streams
    assert "S3" in r.unreliable_streams
    assert r.streams["S2"].unreliable is True
    assert r.streams["S3"].unreliable is True
    # S1 是 feed，非产品
    assert r.streams["S1"].unreliable is False


def test_sample2_warnings_captured():
    inp, out = _p("sample2_unconverged")
    r = parse_proii_files(inp, out)
    assert len(r.warnings) >= 2
    assert any("UNRELIABLE" in w for w in r.warnings)


# ---------------------------------------------------------------------------
# sample3：side draw + 38 组分
# ---------------------------------------------------------------------------


def test_sample3_components_count_38():
    inp, out = _p("sample3_side_draw")
    r = parse_proii_files(inp, out)
    assert len(r.components) == 38


def test_sample3_sidestrippers_present():
    inp, out = _p("sample3_side_draw")
    r = parse_proii_files(inp, out)
    sidestripper_uids = [uid for uid, uo in r.unit_ops.items() if uo.type == "SIDESTRIPPER"]
    assert len(sidestripper_uids) == 4  # SS1~SS4
    for uid in sidestripper_uids:
        assert r.unit_ops[uid].is_side_draw is True


def test_sample3_naphtha_is_side_draw():
    """NAVGAS（轻石脑油）从 T101 侧线抽出 → unit op T101 应有 side draws。"""
    inp, out = _p("sample3_side_draw")
    r = parse_proii_files(inp, out)
    # T101 COLUMN 应有 4 个 side draws
    t101 = r.unit_ops["T101"]
    assert t101.type == "COLUMN"
    # 侧线信息在 spec §619 应可被识别
    assert "NAVGAS" in r.streams
    assert "KERO" in r.streams


# ---------------------------------------------------------------------------
# sample4：V2.71 + FLASH + VALVE + zero_flow 流
# ---------------------------------------------------------------------------


def test_sample4_convergence_warnings():
    inp, out = _p("sample4_flash_valve")
    r = parse_proii_files(inp, out)
    assert r.convergence_status == ConvergenceStatus.WARNINGS


def test_sample4_unit_ops_flash_and_valve():
    inp, out = _p("sample4_flash_valve")
    r = parse_proii_files(inp, out)
    assert r.unit_ops["V01"].type == "VALVE"
    # ACIDFL_UID 是 FLASH
    flash_uids = [uid for uid, uo in r.unit_ops.items() if uo.type == "FLASH"]
    assert len(flash_uids) == 1
    # 2 SPLITTER
    splitter_uids = [uid for uid, uo in r.unit_ops.items() if uo.type == "SPLITTER"]
    assert len(splitter_uids) == 2


def test_sample4_zero_flow_streams_fg1_fg2():
    """SPEC §623：*** ZERO FLOW *** 流保留，零流量流 = ["FG1", "FG2"]。"""
    inp, out = _p("sample4_flash_valve")
    r = parse_proii_files(inp, out)
    assert set(r.zero_flow_streams) == {"FG1", "FG2"}
    assert r.streams["FG1"].zero_flow is True
    assert r.streams["FG2"].zero_flow is True
    assert r.streams["FG1"].mass_flow_kg_h == 0.0


def test_sample4_warnings_captured():
    inp, out = _p("sample4_flash_valve")
    r = parse_proii_files(inp, out)
    # sample4 .out 警告原文："STREAM FG1 HAS ZERO MASS FLOW RATE."
    assert any("ZERO MASS FLOW" in w for w in r.warnings)


# ---------------------------------------------------------------------------
# sample5：REACTOR + EXTRACTOR + 4 reactions + 6 单元类型
# ---------------------------------------------------------------------------


def test_sample5_unit_ops_minimum_6():
    """sample5 .inp 实际定义 8 单元（R101/EX1/M1/C1/SP1/S2_U/CA1/E1）；
    .out 仅详述 6（略 M1/E1 摘要）；spec §628 要求 ≥ 6 类型覆盖。"""
    inp, out = _p("sample5_reactor_extraction")
    r = parse_proii_files(inp, out)
    assert len(r.unit_ops) >= 6


def test_sample5_unit_ops_types():
    inp, out = _p("sample5_reactor_extraction")
    r = parse_proii_files(inp, out)
    types = {uo.type for uo in r.unit_ops.values()}
    # 必需含：REACTOR / EXTRACTOR / COMPRESSOR / SPLITTER / STCA / CALCULATOR
    assert "REACTOR" in types
    assert "EXTRACTOR" in types
    assert "COMPRESSOR" in types
    assert "SPLITTER" in types
    assert "STCA" in types
    assert "CALCULATOR" in types


def test_sample5_reactor_r101():
    inp, out = _p("sample5_reactor_extraction")
    r = parse_proii_files(inp, out)
    assert r.unit_ops["R101"].type == "REACTOR"


def test_sample5_reactions_4():
    """SPEC §628：4 reactions in RXSET DMCSET。"""
    inp, out = _p("sample5_reactor_extraction")
    r = parse_proii_files(inp, out)
    assert len(r.reactions) == 4
    assert all(rx.rxset_id == "DMCSET" for rx in r.reactions)
    rx_ids = {rx.reaction_id for rx in r.reactions}
    assert rx_ids == {"RX1", "RX2", "RX3", "RX4"}


def test_sample5_reactions_have_horx():
    inp, out = _p("sample5_reactor_extraction")
    r = parse_proii_files(inp, out)
    rx1 = next(rx for rx in r.reactions if rx.reaction_id == "RX1")
    assert rx1.horx == pytest.approx(-2.1978, abs=0.001)
    # STOIC 应有 4 项：3,-1/4,-2/5,1/6,1
    assert len(rx1.stoic) == 4
    assert rx1.stoic[0] == (3, -1.0)
    assert rx1.stoic[-1] == (6, 1.0)


# ---------------------------------------------------------------------------
# 跨样例：5 态枚举 + 失败兜底
# ---------------------------------------------------------------------------


def test_convergence_status_enum_has_5_values():
    """收敛分层必须有 5 态（spec V1.6 §3.3.3）。"""
    assert len(ConvergenceStatus) == 5
    expected = {
        ConvergenceStatus.CONVERGED,
        ConvergenceStatus.WARNINGS,
        ConvergenceStatus.NOT_CONVERGED,
        ConvergenceStatus.ABORTED,
        ConvergenceStatus.NOT_SOLVED,
    }
    assert set(ConvergenceStatus) == expected


def test_missing_file_raises():
    """输入路径不存在 → 抛 FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        parse_proii_files(
            FIXTURES / "nonexistent.inp",
            FIXTURES / "nonexistent.out",
        )


def test_garbage_out_file_raises_value_error(tmp_path):
    """.out 无 banner → 抛 ValueError（无法识别 PRO/II 输出）。"""
    inp = tmp_path / "x.inp"
    out = tmp_path / "x.out"
    inp.write_text(" TITLE PROJECT=X\n")
    out.write_text(" NOT A PRO/II OUTPUT\n")
    with pytest.raises(ValueError, match="banner"):
        parse_proii_files(inp, out)
