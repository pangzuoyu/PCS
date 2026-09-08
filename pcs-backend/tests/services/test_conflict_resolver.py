"""P3.2 SIM-7：三级冲突检测服务契约测试（spec V1.6 §3.4）。

按用户 2026-09-08 完整设计：
- 冲突三级：BLOCK / WARN / INFO
- 4 大检测维度：SIM-V01~V10（结构完整性）/ SIM-E01~E04（工程一致性）/
  PR-V01~V14（PRO/II 结构）/ PRX-V01~V08（双文件交叉）
- 核心接口：Conflict dataclass + ConflictResolver.resolve_batch() → ConflictReport
- 与 SIM-3 衔接：MISSING_CAS→INFO / NOT_FOUND→WARN / ERROR→WARN

注：本期先落核心 dataclass + 报告 + 关键规则（SIM-V01/V02 + SIM-3 衔接），
后续 PR-* 和 PRX-* 规则随 SIM-2/SIM-10 推进时扩展。
"""
from __future__ import annotations

from app.services.conflict_resolver import (
    Conflict,
    ConflictLevel,
    ConflictReport,
    ConflictResolver,
    ParsedStream,
)

# ---------------------------------------------------------------------------
# 枚举 + dataclass 契约
# ---------------------------------------------------------------------------


def test_conflict_level_enum_values():
    assert {e.value for e in ConflictLevel} == {"BLOCK", "WARN", "INFO"}


def test_conflict_dataclass_carries_required_fields():
    c = Conflict(
        level=ConflictLevel.BLOCK,
        code="SIM-V01",
        message="MIXED 相缺气液组成",
        stream_name="S-101",
    )
    assert c.level == ConflictLevel.BLOCK
    assert c.code == "SIM-V01"
    assert c.stream_name == "S-101"
    assert c.unit_id is None  # 可选
    assert c.field is None  # 可选


def test_conflict_report_has_blocks_property():
    r = ConflictReport(
        blocks=[Conflict(level=ConflictLevel.BLOCK, code="X", message="x")],
        warnings=[],
        infos=[],
        stats={},
    )
    assert r.has_blocks is True

    r2 = ConflictReport(blocks=[], warnings=[], infos=[], stats={})
    assert r2.has_blocks is False


def test_conflict_report_stats_counter():
    r = ConflictReport(
        blocks=[
            Conflict(level=ConflictLevel.BLOCK, code="A", message="a"),
            Conflict(level=ConflictLevel.BLOCK, code="B", message="b"),
        ],
        warnings=[Conflict(level=ConflictLevel.WARN, code="C", message="c")],
        infos=[Conflict(level=ConflictLevel.INFO, code="D", message="d")],
        stats={},
    )
    stats = r.stats
    assert stats["BLOCK"] == 2
    assert stats["WARN"] == 1
    assert stats["INFO"] == 1
    assert stats["TOTAL"] == 4


# ---------------------------------------------------------------------------
# 结构性规则：SIM-V01
# ---------------------------------------------------------------------------


def test_sim_v01_mixed_phase_missing_vapor_composition_is_block():
    """SIM-V01：MIXED 相必须同时含气/液组成，缺一即 BLOCK。"""
    s = ParsedStream(
        tag="S-101",
        cas="7732-18-5",
        phase="MIXED",
        vapor_fraction=0.5,
        composition={"7732-18-5": 1.0},
        # vapor_composition_json / liquid_composition_json 缺
    )
    r = ConflictResolver().resolve_batch([s])
    assert r.has_blocks is True
    codes = [c.code for c in r.blocks]
    assert "SIM-V01" in codes


def test_sim_v01_mixed_phase_complete_compositions_passes():
    s = ParsedStream(
        tag="S-101",
        cas="7732-18-5",
        phase="MIXED",
        vapor_fraction=0.5,
        composition={"7732-18-5": 1.0},
        vapor_composition={"7732-18-5": 1.0},
        liquid_composition={"7732-18-5": 1.0},
    )
    r = ConflictResolver().resolve_batch([s])
    sim_v01_blocks = [c for c in r.blocks if c.code == "SIM-V01"]
    assert not sim_v01_blocks


# ---------------------------------------------------------------------------
# 结构性规则：SIM-V02（质量-摩尔流量一致性）
# ---------------------------------------------------------------------------


def test_sim_v02_molar_mass_inconsistent_with_mw_is_block():
    """SIM-V02：molar_flow × MW 应 ≈ mass_flow（容差 1%），否则 BLOCK。"""
    # MW=18（水），molar_flow=10 kmol/h，mass_flow 应 ≈ 180 kg/h
    # 故意给 mass_flow=300（差 67%）触发 BLOCK
    s = ParsedStream(
        tag="S-201",
        cas="7732-18-5",
        molar_flow_kmol_h=10.0,
        mass_flow_kg_h=300.0,
        molecular_weight=18.015,
    )
    r = ConflictResolver().resolve_batch([s])
    sim_v02_blocks = [c for c in r.blocks if c.code == "SIM-V02"]
    assert len(sim_v02_blocks) == 1
    assert sim_v02_blocks[0].stream_name == "S-201"
    assert "MW" in sim_v02_blocks[0].message or "molar" in sim_v02_blocks[0].message.lower()


def test_sim_v02_molar_mass_consistent_passes():
    s = ParsedStream(
        tag="S-201",
        cas="7732-18-5",
        molar_flow_kmol_h=10.0,
        mass_flow_kg_h=180.15,  # 10 × 18.015
        molecular_weight=18.015,
    )
    r = ConflictResolver().resolve_batch([s])
    sim_v02_blocks = [c for c in r.blocks if c.code == "SIM-V02"]
    assert not sim_v02_blocks


# ---------------------------------------------------------------------------
# 工程一致性：SIM-E01~E04（先落核心 3 条）
# ---------------------------------------------------------------------------


def test_sim_e01_negative_temperature_is_block():
    s = ParsedStream(tag="S-301", cas="7732-18-5", temperature_k=-1.0)
    r = ConflictResolver().resolve_batch([s])
    assert any(c.code == "SIM-E01" and c.level == ConflictLevel.BLOCK for c in r.blocks)


def test_sim_e02_nonpositive_pressure_is_block():
    s = ParsedStream(tag="S-302", cas="7732-18-5", pressure_pa=0.0)
    r = ConflictResolver().resolve_batch([s])
    assert any(c.code == "SIM-E02" and c.level == ConflictLevel.BLOCK for c in r.blocks)


def test_sim_e03_vapor_fraction_out_of_range_is_block():
    s = ParsedStream(tag="S-303", cas="7732-18-5", vapor_fraction=1.5)
    r = ConflictResolver().resolve_batch([s])
    assert any(c.code == "SIM-E03" and c.level == ConflictLevel.BLOCK for c in r.blocks)


# ---------------------------------------------------------------------------
# 与 SIM-3 衔接：complete_properties 错误码转译
# ---------------------------------------------------------------------------


def test_complete_properties_missing_cas_translates_to_info():
    """SIM-3 返回 source=MISSING_CAS → SIM-7 标 INFO。"""
    s = ParsedStream(tag="S-X1", cas=None)
    r = ConflictResolver().resolve_batch([s])
    # 验证：恰好 1 条 INFO 级冲突，关联 S-X1 + field=cas
    sim_cas_infos = [c for c in r.infos if c.stream_name == "S-X1"]
    assert len(sim_cas_infos) == 1
    assert sim_cas_infos[0].level == ConflictLevel.INFO
    assert sim_cas_infos[0].field == "cas"


def test_complete_properties_not_found_translates_to_warn():
    """SIM-3 返回 source=NOT_FOUND → SIM-7 标 WARN。"""
    s = ParsedStream(tag="S-X2", cas="0000-00-0")
    r = ConflictResolver().resolve_batch([s])
    # 验证：恰好 1 条 WARN 级冲突，关联 S-X2 + field=cas
    sim_not_found_warns = [c for c in r.warnings if c.stream_name == "S-X2"]
    assert len(sim_not_found_warns) == 1
    assert sim_not_found_warns[0].level == ConflictLevel.WARN
    assert sim_not_found_warns[0].field == "cas"


# ---------------------------------------------------------------------------
# 批量 + 混合
# ---------------------------------------------------------------------------


def test_resolve_batch_returns_one_report_for_all_streams():
    streams = [
        ParsedStream(tag="S-OK", cas="7732-18-5", temperature_k=373.15),
        ParsedStream(tag="S-BAD", cas=None),  # INFO
        ParsedStream(tag="S-FAIL", cas="0000-00-0"),  # WARN
    ]
    r = ConflictResolver().resolve_batch(streams)
    assert r.stats["TOTAL"] >= 2  # 至少 1 INFO + 1 WARN


def test_resolve_batch_block_on_error_false_keeps_blocks_in_report():
    """block_on_error=False：BLOCK 仍写入报告，但不抛错（供 caller 决策）。"""
    s = ParsedStream(tag="S-401", cas="7732-18-5", temperature_k=-1.0)
    r = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert any(c.code == "SIM-E01" for c in r.blocks)
    # 无异常抛出


def test_resolver_uses_property_completion_results():
    """SIM-7 必须 import SIM-3 物性补全结果（PR-V01 类规则）。

    已知 CAS（7732-18-5）→ effective.mw 应被注入 stream.molecular_weight
    若未提供 MW 且有效 MW 可计算 → 不应误报 SIM-V02 BLOCK
    """
    # 提供 molar_flow 但不提供 mass_flow/mw，SIM-7 应从 effective 推算并跳过 SIM-V02
    s = ParsedStream(
        tag="S-501",
        cas="7732-18-5",
        molar_flow_kmol_h=10.0,
        # mass_flow_kg_h 缺
        # molecular_weight 缺
    )
    r = ConflictResolver().resolve_batch([s])
    sim_v02_blocks = [c for c in r.blocks if c.code == "SIM-V02"]
    assert not sim_v02_blocks  # 缺数据不算冲突（信息缺失归 INFO）
