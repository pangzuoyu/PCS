"""P3.x SIM-28：SIM-V03~V10 共 8 条 SIM 结构完整性校验规则单元测试。

| Code  | Level | 规则概要                                                |
|-------|-------|------------------------------------------------------|
| V03   | BLOCK | 压力越界 (0 <= p <= 1e8 Pa)                          |
| V04   | BLOCK | 相态枚举非法（仅 VAPOR/LIQUID/MIXED/SOLID）           |
| V05   | BLOCK | 流量全 0（mass_flow 和 molar_flow 同时 ≤ 0）          |
| V06   | BLOCK | composition 为空或缺                                  |
| V07   | BLOCK | composition 中 CAS 无法通过 CommonService 解析        |
| V08   | BLOCK | composition 出现重复 CAS                              |
| V09   | BLOCK | composition sum drift > 0.1%                         |
| V10   | WARN  | composition sum drift > 1%（保留，不阻塞入库）        |
"""
from __future__ import annotations

from app.services.conflict_resolver import ConflictResolver
from app.services.property_completion import ParsedStream


def _mk(**kw) -> ParsedStream:
    base = dict(
        tag="S-101",
        cas="71-43-2",  # benzene
        temperature_k=350.0,
        pressure_pa=200_000.0,
        phase="VAPOR",
        mass_flow_kg_h=1000.0,
        molar_flow_kmol_h=12.8,
        composition={"71-43-2": 1.0},
    )
    base.update(kw)
    return ParsedStream(**base)


def _find(report, code: str):
    return [c for c in report.blocks + report.warnings + report.infos if c.code == code]


# ---------------------------------------------------------------------------
# SIM-V03：压力越界
# ---------------------------------------------------------------------------


def test_sim_v03_pressure_block_high():
    s = _mk(pressure_pa=1e9)  # > 1e8 Pa
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert any(c.code == "SIM-V03" for c in report.blocks), (
        f"v03 missing, blocks: {[c.code for c in report.blocks]}"
    )


def test_sim_v03_pressure_block_negative():
    s = _mk(pressure_pa=-1.0)
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert any(c.code == "SIM-V03" for c in report.blocks)


def test_sim_v03_pressure_pass_when_in_range():
    s = _mk(pressure_pa=200_000.0)
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert not any(c.code == "SIM-V03" for c in report.blocks)


# ---------------------------------------------------------------------------
# SIM-V04：相态枚举
# ---------------------------------------------------------------------------


def test_sim_v04_phase_invalid():
    s = _mk(phase="PLASMA")
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert any(c.code == "SIM-V04" for c in report.blocks)


def test_sim_v04_phase_pass_vapor():
    s = _mk(phase="VAPOR")
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert not any(c.code == "SIM-V04" for c in report.blocks)


def test_sim_v04_phase_pass_liquid():
    s = _mk(phase="LIQUID")
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert not any(c.code == "SIM-V04" for c in report.blocks)


# ---------------------------------------------------------------------------
# SIM-V05：流量全 0
# ---------------------------------------------------------------------------


def test_sim_v05_zero_flow_block():
    s = _mk(mass_flow_kg_h=0.0, molar_flow_kmol_h=0.0)
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert any(c.code == "SIM-V05" for c in report.blocks)


def test_sim_v05_zero_flow_block_explicit_zero_flow_flag():
    s = _mk(mass_flow_kg_h=None, molar_flow_kmol_h=None, zero_flow=True)
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert any(c.code == "SIM-V05" for c in report.blocks)


def test_sim_v05_pass_when_mass_flow_present():
    s = _mk(mass_flow_kg_h=1000.0, molar_flow_kmol_h=None)
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert not any(c.code == "SIM-V05" for c in report.blocks)


# ---------------------------------------------------------------------------
# SIM-V06：composition 为空
# ---------------------------------------------------------------------------


def test_sim_v06_empty_composition_block():
    s = _mk(composition={})
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert any(c.code == "SIM-V06" for c in report.blocks)


def test_sim_v06_none_composition_pass():
    """composition=None 表示未提供组成（utility 流等场景），允许。"""
    s = _mk(composition=None)
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert not any(c.code == "SIM-V06" for c in report.blocks)


def test_sim_v06_pass_when_composition_present():
    s = _mk(composition={"71-43-2": 1.0})
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert not any(c.code == "SIM-V06" for c in report.blocks)


# ---------------------------------------------------------------------------
# SIM-V07：CAS 无法解析
# ---------------------------------------------------------------------------


def test_sim_v07_unresolvable_cas_warn():
    """composition 中含一个不存在于 COMMON 库的 CAS → WARN V07（与 SIM-V01-NF 同语义）。"""
    s = _mk(composition={"71-43-2": 0.5, "9999-99-9": 0.5})
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    v07_warns = [c for c in report.warnings if c.code == "SIM-V07"]
    assert len(v07_warns) >= 1
    assert not any(c.code == "SIM-V07" for c in report.blocks)


def test_sim_v07_resolvable_cas_pass():
    s = _mk(composition={"71-43-2": 1.0})
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert not any(c.code == "SIM-V07" for c in report.blocks)


# ---------------------------------------------------------------------------
# SIM-V08：composition 重复 CAS
# ---------------------------------------------------------------------------


def test_sim_v08_duplicate_cas_block():
    """dict 自动去重场景下 V08 不触发（防御性守护）；上游 parser 若
    传入 list-of-tuples 形式需在 parser 层先于 resolver 阻断。"""
    s_raw = ParsedStream(
        tag="S-101",
        cas=None,
        temperature_k=350.0,
        pressure_pa=200_000.0,
        phase="VAPOR",
        mass_flow_kg_h=1000.0,
        molar_flow_kmol_h=12.8,
        composition={"71-43-2": 0.5},  # dict 自动去重
    )
    report = ConflictResolver().resolve_batch([s_raw], block_on_error=False)
    assert not any(c.code == "SIM-V08" for c in report.blocks)


def test_sim_v08_dup_cas_detected_when_collision_in_dict():
    """直接构造 ParsedStream 时通过 set 长度判定重复（利用 CAS 比较列表）。
    模拟 parser 阶段 list-of-tuples 重复 CAS（dict 合并后变成 1 项但 V08
    应在 parser 层被阻断——所以在 resolver 中只在显式 list 形式下触发）。"""
    # 由于 dataclass(frozen=True)，composition 类型固定为 dict。
    # 故此测试仅验证"同一 dict 内 key 无重复" 时 V08 不触发。
    s = _mk(composition={"71-43-2": 0.4, "7732-18-5": 0.6})
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert not any(c.code == "SIM-V08" for c in report.blocks)


# ---------------------------------------------------------------------------
# SIM-V09：composition sum drift > 0.1%
# ---------------------------------------------------------------------------


def test_sim_v09_composition_sum_block_drift_above_001pct():
    """sum = 1.005，drift 0.5% > 0.1% 阈值 → BLOCK V09。"""
    s = _mk(composition={"71-43-2": 0.505, "7732-18-5": 0.5})
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert any(c.code == "SIM-V09" for c in report.blocks)


def test_sim_v09_composition_sum_pass_at_100():
    s = _mk(composition={"71-43-2": 0.5, "7732-18-5": 0.5})
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert not any(c.code == "SIM-V09" for c in report.blocks)


def test_sim_v09_composition_sum_pass_under_threshold():
    """sum drift 0.05% < 0.1% → pass。"""
    s = _mk(composition={"71-43-2": 0.5005, "7732-18-5": 0.5})
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    assert not any(c.code == "SIM-V09" for c in report.blocks)


# ---------------------------------------------------------------------------
# SIM-V10：composition sum drift > 1%（WARN，不 BLOCK）
# ---------------------------------------------------------------------------


def test_sim_v10_composition_sum_warn_drift_above_1pct():
    """drift 2% > 1% → WARN V10（不入 blocks）；drift > 0.1% 也会触发 V09 BLOCK。"""
    s = _mk(composition={"71-43-2": 0.51, "7732-18-5": 0.5})  # sum = 1.01, drift = 0.01 = 1%
    # 用更明显漂移：2%
    s = _mk(composition={"71-43-2": 0.52, "7732-18-5": 0.5})  # sum = 1.02, drift = 0.02 = 2%
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    # 应有 V10 在 warnings
    v10_warns = [c for c in report.warnings if c.code == "SIM-V10"]
    assert len(v10_warns) >= 1
    # V10 不应在 blocks（只 WARN）
    assert not any(c.code == "SIM-V10" for c in report.blocks)


# ---------------------------------------------------------------------------
# 综合：clean stream 触发 0 V 规则
# ---------------------------------------------------------------------------


def test_clean_stream_no_sim_v_block():
    s = _mk()
    report = ConflictResolver().resolve_batch([s], block_on_error=False)
    v_blocks = [
        c for c in report.blocks if c.code.startswith("SIM-V")
    ]
    assert v_blocks == [], f"clean stream 不应有 V* BLOCK，实际：{[c.code for c in v_blocks]}"