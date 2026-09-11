"""P3.2 SIM-36: PRO/II reaction kinetics 提取（spec V1.6 §3.3.3）。

spec §3.3.3 PROIIReaction 字段：
- id
- stoichiometry: list[tuple[lib_id, coef]]
- horx_heat / ref_component / ref_temp / ref_phase
- kinetics: dict（PEXP/ACTIVATION/TEXPONENT/KORDER）

格式差异：
1. 单行旧格式（sample5）：REACTION ID=RX1  STOIC:3,-1/...  HORX=-2.1978  CONV MODEL
2. 多行新格式（dmc.inp/out）：REACTION ID=RX1 \n STOICHIOMETRY ... \n
   HORX HEAT=-2.1978,REFCOMP=3,REFTEMP=25,REFPHASE=L \n KINETICS PEXP(...)=... \n
   KORDER 3,1/4,1/...

Reaction dataclass 契约：
- 旧字段 `horx` 保留（向后兼容 sample5 测试）
- 新字段 `horx_heat/ref_component/ref_temp/ref_phase/kinetics/korder`
  （spec §3.3.3 完整结构）
"""
from __future__ import annotations

import pytest

from app.services.proii_parser import Reaction, _parse_reactions

# ---------------------------------------------------------------------------
# 单行旧格式（COMPAT：sample5 fixture）
# ---------------------------------------------------------------------------


def test_legacy_single_line_horx_back_compat():
    """sample5 单行格式：horx 字段保留（向后兼容）。"""
    text = (
        "RXSET ID=DMCSET\n"
        "REACTION ID=RX1  STOIC: 3,-1/4,-2/5,1/6,1     HORX=-2.1978  CONV MODEL\n"
    )
    rxs = _parse_reactions(text)
    assert len(rxs) == 1
    rx = rxs[0]
    assert rx.rxset_id == "DMCSET"
    assert rx.reaction_id == "RX1"
    assert rx.horx == pytest.approx(-2.1978, abs=0.001)
    # 新字段在单行格式下为 None（无 KINETICS/KORDER/REF*）
    assert rx.kinetics is None
    assert rx.korder is None
    assert rx.ref_component is None
    assert rx.ref_temp is None
    assert rx.ref_phase is None


def test_legacy_horx_value_also_populates_horx_heat():
    """单行 HORX=X → horx_heat 同步（spec §3.3.3 字段统一）。"""
    text = (
        "RXSET ID=S1\n"
        "REACTION ID=R1  STOIC: 1,-1/2,1   HORX=-10.5  CONV MODEL\n"
    )
    rx = _parse_reactions(text)[0]
    assert rx.horx == pytest.approx(-10.5, abs=0.001)
    assert rx.horx_heat == pytest.approx(-10.5, abs=0.001)


# ---------------------------------------------------------------------------
# 多行新格式（dmc.inp/out 风格，spec §3.3.3 完整结构）
# ---------------------------------------------------------------------------


def test_multi_line_reaction_full_structure():
    """多行格式：STOIC + HORX(HEAT/REFCOMP/REFTEMP/REFPHASE) + KINETICS + KORDER。"""
    text = (
        "RXDATA\n"
        "RXSET ID=DMC\n"
        "REACTION ID=DMC+\n"
        "  STOICHIOMETRY 3,-1/4,-2/5,1/6,1\n"
        "  HORX HEAT=-2.1978,REFCOMP=3,REFTEMP=25,REFPHASE=L\n"
        "  KINETICS PEXP(MIN,G,LIT)=9785,ACTIVATION=9.615,TEXPONENT=0\n"
        "  KORDER 3,1/4,1/5,0/6,0\n"
        "REACTION ID=DMC-\n"
        "  STOICHIOMETRY 3,1/4,2/5,-1/6,-1\n"
        "  HORX HEAT=2.1978,REFCOMP=3,REFTEMP=25,REFPHASE=L\n"
        "  KINETICS PEXP(MIN)=1.9723E6,ACTIVATION=11.771,TEXPONENT=0\n"
        "  KORDER 3,0/4,-1/5,1/6,1\n"
    )
    rxs = _parse_reactions(text)
    assert len(rxs) == 2
    assert {rx.rxset_id for rx in rxs} == {"DMC"}
    assert {rx.reaction_id for rx in rxs} == {"DMC+", "DMC-"}


def test_multi_line_stoichiometry_parsed():
    """多行 STOICHIOMETRY 段：4 个组分对。"""
    text = (
        "RXSET ID=DMC\n"
        "REACTION ID=DMC+\n"
        "  STOICHIOMETRY 3,-1/4,-2/5,1/6,1\n"
        "  HORX HEAT=-2.1978\n"
        "  KINETICS PEXP(MIN,G,LIT)=9785\n"
    )
    rx = _parse_reactions(text)[0]
    assert len(rx.stoic) == 4
    assert rx.stoic[0] == (3, -1.0)
    assert rx.stoic[1] == (4, -2.0)
    assert rx.stoic[2] == (5, 1.0)
    assert rx.stoic[3] == (6, 1.0)


def test_multi_line_horx_all_ref_fields():
    """HORX 多 key=val：HEAT/REFCOMP/REFTEMP/REFPHASE 全部提取。"""
    text = (
        "RXSET ID=S1\n"
        "REACTION ID=R1\n"
        "  STOICHIOMETRY 1,1\n"
        "  HORX HEAT=-2.1978,REFCOMP=3,REFTEMP=25,REFPHASE=L\n"
        "  KINETICS PEXP=100\n"
    )
    rx = _parse_reactions(text)[0]
    assert rx.horx_heat == pytest.approx(-2.1978, abs=0.001)
    assert rx.ref_component == 3
    assert rx.ref_temp == pytest.approx(25.0, abs=0.01)
    assert rx.ref_phase == "L"


def test_multi_line_kinetics_dict():
    """KINETICS 段：PEXP/ACTIVATION/TEXPONENT 三参数。"""
    text = (
        "RXSET ID=S1\n"
        "REACTION ID=R1\n"
        "  STOICHIOMETRY 1,1\n"
        "  HORX HEAT=-1.0,REFCOMP=1,REFTEMP=25,REFPHASE=L\n"
        "  KINETICS PEXP(MIN,G,LIT)=9785,ACTIVATION=9.615,TEXPONENT=0\n"
    )
    rx = _parse_reactions(text)[0]
    assert rx.kinetics is not None
    # 键名保留原始字符串（含括号参数）
    assert "PEXP(MIN,G,LIT)" in rx.kinetics
    assert rx.kinetics["PEXP(MIN,G,LIT)"] == pytest.approx(9785.0, abs=0.01)
    assert rx.kinetics["ACTIVATION"] == pytest.approx(9.615, abs=0.001)
    assert rx.kinetics["TEXPONENT"] == pytest.approx(0.0, abs=0.01)


def test_multi_line_kinetics_scientific_notation():
    """KINETICS PEXP=1.9723E6 科学计数法。"""
    text = (
        "RXSET ID=S1\n"
        "REACTION ID=R1\n"
        "  STOICHIOMETRY 1,1\n"
        "  HORX HEAT=1.0\n"
        "  KINETICS PEXP(MIN)=1.9723E6,ACTIVATION=11.771,TEXPONENT=0\n"
    )
    rx = _parse_reactions(text)[0]
    assert rx.kinetics["PEXP(MIN)"] == pytest.approx(1.9723e6, rel=1e-4)
    assert rx.kinetics["ACTIVATION"] == pytest.approx(11.771, abs=0.001)


def test_multi_line_korder_dict():
    """KORDER 段：libid → order 字典。"""
    text = (
        "RXSET ID=S1\n"
        "REACTION ID=R1\n"
        "  STOICHIOMETRY 1,-1/2,1\n"
        "  HORX HEAT=-1.0\n"
        "  KINETICS PEXP=100\n"
        "  KORDER 3,1/4,1/5,0/6,0\n"
    )
    rx = _parse_reactions(text)[0]
    assert rx.korder == {3: 1.0, 4: 1.0, 5: 0.0, 6: 0.0}


# ---------------------------------------------------------------------------
# 边界 / 缺失
# ---------------------------------------------------------------------------


def test_no_rxdata_no_reactions():
    """无 RXDATA 段 → 空列表。"""
    text = "TITLE PROJECT=DEMO\nSTREAM DATA\nEND\n"
    assert _parse_reactions(text) == []


def test_rxset_without_reactions_emits_none():
    """空 RXSET（无 REACTION 子段）→ 空列表。"""
    text = "RXSET ID=EMPTY\nEND\n"
    assert _parse_reactions(text) == []


def test_horx_heat_only_minimal():
    """HORX 仅 HEAT= 字段（无 REFCOMP/REFTEMP/REFPHASE）→ 仅 horx_heat。"""
    text = (
        "RXSET ID=S1\n"
        "REACTION ID=R1\n"
        "  STOICHIOMETRY 1,1\n"
        "  HORX HEAT=-2.1978\n"
    )
    rx = _parse_reactions(text)[0]
    assert rx.horx_heat == pytest.approx(-2.1978, abs=0.001)
    assert rx.ref_component is None
    assert rx.ref_temp is None
    assert rx.ref_phase is None
    assert rx.kinetics is None
    assert rx.korder is None


def test_horx_without_heat_keyword_skips():
    """HORX 行无 HEAT= → horx_heat=None（兜底）。"""
    text = (
        "RXSET ID=S1\n"
        "REACTION ID=R1\n"
        "  STOICHIOMETRY 1,1\n"
        "  HORX SOMETHING=ELSE\n"
    )
    rx = _parse_reactions(text)[0]
    assert rx.horx_heat is None


def test_multiple_rxsets_grouped_correctly():
    """多 RXSET：reactions 按 RXSET 分组（rxset_id 正确归属）。"""
    text = (
        "RXSET ID=SET_A\n"
        "REACTION ID=A1\n"
        "  STOICHIOMETRY 1,1\n"
        "  HORX HEAT=1.0\n"
        "RXSET ID=SET_B\n"
        "REACTION ID=B1\n"
        "  STOICHIOMETRY 1,1\n"
        "  HORX HEAT=2.0\n"
    )
    rxs = _parse_reactions(text)
    assert len(rxs) == 2
    by_id = {rx.reaction_id: rx for rx in rxs}
    assert by_id["A1"].rxset_id == "SET_A"
    assert by_id["A1"].horx_heat == pytest.approx(1.0)
    assert by_id["B1"].rxset_id == "SET_B"
    assert by_id["B1"].horx_heat == pytest.approx(2.0)


def test_kinetics_with_non_numeric_value_stored_as_string():
    """KINETICS 段含非数值参数（如 PEXP=POWER_FORMULA）→ 字符串保留。"""
    text = (
        "RXSET ID=S1\n"
        "REACTION ID=R1\n"
        "  STOICHIOMETRY 1,1\n"
        "  HORX HEAT=1.0\n"
        "  KINETICS PEXP=POWER_FORMULA\n"
    )
    rx = _parse_reactions(text)[0]
    assert rx.kinetics is not None
    assert rx.kinetics["PEXP"] == "POWER_FORMULA"


# ---------------------------------------------------------------------------
# Reaction dataclass 字段契约
# ---------------------------------------------------------------------------


def test_reaction_dataclass_has_required_spec_v1_6_3_3_3_fields():
    """spec §3.3.3 PROIIReaction 字段契约：dataclass 暴露完整 9 字段。

    旧字段 horx 保留（sample5 backward compat）。
    """
    rx = Reaction(
        rxset_id="S1",
        reaction_id="R1",
        stoic=[(1, -1.0), (2, 1.0)],
        horx=-1.0,
        horx_heat=-1.0,
        ref_component=1,
        ref_temp=25.0,
        ref_phase="L",
        kinetics={"PEXP": 100.0},
        korder={1: 1.0, 2: 0.0},
    )
    assert rx.rxset_id == "S1"
    assert rx.reaction_id == "R1"
    assert rx.horx == -1.0  # 兼容字段
    assert rx.horx_heat == -1.0
    assert rx.ref_component == 1
    assert rx.ref_temp == 25.0
    assert rx.ref_phase == "L"
    assert rx.kinetics == {"PEXP": 100.0}
    assert rx.korder == {1: 1.0, 2: 0.0}


def test_reaction_minimal_construction_defaults_none():
    """Reaction 仅必填 4 字段（rxset_id/reaction_id/stoic/horx）→ 其余默认 None。"""
    rx = Reaction(
        rxset_id="S1",
        reaction_id="R1",
        stoic=[(1, 1.0)],
        horx=None,
    )
    assert rx.horx is None
    assert rx.horx_heat is None
    assert rx.ref_component is None
    assert rx.ref_temp is None
    assert rx.ref_phase is None
    assert rx.kinetics is None
    assert rx.korder is None


# ---------------------------------------------------------------------------
# real fixture: dmc.inp/.out 完整结构
# ---------------------------------------------------------------------------


def test_real_dmc_inp_reactions():
    """sample/dmc.inp 含 2 反应（DMC+/DMC-），全部 spec §3.3.3 字段可提取。"""
    from pathlib import Path

    sample = Path("/home/pangzy/code_project/PCS/sample/dmc.inp")
    if not sample.exists():
        pytest.skip("sample/dmc.inp 不存在（仓库级 fixture）")
    text = sample.read_text(encoding="utf-8", errors="replace")
    rxs = _parse_reactions(text)
    assert len(rxs) == 2
    by_id = {rx.reaction_id: rx for rx in rxs}
    assert set(by_id.keys()) == {"DMC+", "DMC-"}

    plus = by_id["DMC+"]
    assert plus.rxset_id == "DMC"
    assert plus.horx_heat == pytest.approx(-2.1978, abs=0.001)
    assert plus.ref_component == 3
    assert plus.ref_temp == pytest.approx(25.0, abs=0.01)
    assert plus.ref_phase == "L"
    assert plus.kinetics is not None
    assert plus.kinetics["PEXP(MIN,G,LIT)"] == pytest.approx(9785.0, abs=0.1)
    assert plus.kinetics["ACTIVATION"] == pytest.approx(9.615, abs=0.001)
    assert plus.kinetics["TEXPONENT"] == pytest.approx(0.0, abs=0.01)
    assert plus.korder == {3: 1.0, 4: 1.0, 5: 0.0, 6: 0.0}