"""P3.2 SIM-9：状态点级冲突检测服务契约测试（spec V1.6 §3.4）。

按用户 2026-09-08 设计：复用 SIM-7 ConflictResolver 核心 + 状态点级规则
（SIM-SV01~V10，NORMAL/MIN/MAX/ALTERNATE 边界 + stream 关联完整性）。

本期落定核心 5 规则：
- SIM-SV01：case_type 不在 4 值枚举内 → BLOCK
- SIM-SV02：state point 缺温度/压力 → BLOCK
- SIM-SV03：composition 摩尔分率和 ≠ 1.0（容差 0.5%）→ WARN
- SIM-SV04：state point 关联 stream_name 不在 parent_streams → BLOCK
- SIM-SV05：同 (stream_name, case_type) 重复 → BLOCK
"""
from __future__ import annotations

from app.services.conflict_resolver import (
    ConflictLevel,
    ConflictResolver,
    ParsedStatePoint,
)

# ---------------------------------------------------------------------------
# dataclass 契约
# ---------------------------------------------------------------------------


def test_parsed_state_point_dataclass_basic():
    sp = ParsedStatePoint(
        state_point_id="sp-001",
        stream_name="S-101",
        state_label="设计工况",
        case_type="NORMAL",
        temperature_k=373.15,
        pressure_pa=101325.0,
        composition={"7732-18-5": 1.0},
    )
    assert sp.stream_name == "S-101"
    assert sp.case_type == "NORMAL"
    assert sp.composition == {"7732-18-5": 1.0}


# ---------------------------------------------------------------------------
# SIM-SV01：case_type 枚举校验
# ---------------------------------------------------------------------------


def test_sim_sv01_invalid_case_type_is_block():
    sp = ParsedStatePoint(
        state_point_id="sp-001",
        stream_name="S-101",
        state_label="X",
        case_type="INVALID",  # 非法
        temperature_k=373.15,
        pressure_pa=101325.0,
        composition={"7732-18-5": 1.0},
    )
    r = ConflictResolver().resolve_state_points([sp], parent_streams=["S-101"])
    assert any(c.code == "SIM-SV01" and c.level == ConflictLevel.BLOCK for c in r.blocks)


def test_sim_sv01_valid_case_types_pass():
    for valid in ("NORMAL", "MIN", "MAX", "ALTERNATE"):
        sp = ParsedStatePoint(
            state_point_id=f"sp-{valid}",
            stream_name="S-101",
            state_label=valid,
            case_type=valid,
            temperature_k=373.15,
            pressure_pa=101325.0,
            composition={"7732-18-5": 1.0},
        )
        r = ConflictResolver().resolve_state_points([sp], parent_streams=["S-101"])
        assert not [c for c in r.blocks if c.code == "SIM-SV01"]


# ---------------------------------------------------------------------------
# SIM-SV02：缺温度/压力
# ---------------------------------------------------------------------------


def test_sim_sv02_missing_temperature_is_block():
    sp = ParsedStatePoint(
        state_point_id="sp-001",
        stream_name="S-101",
        state_label="X",
        case_type="NORMAL",
        temperature_k=None,  # 缺
        pressure_pa=101325.0,
        composition={"7732-18-5": 1.0},
    )
    r = ConflictResolver().resolve_state_points([sp], parent_streams=["S-101"])
    assert any(c.code == "SIM-SV02" for c in r.blocks)


def test_sim_sv02_missing_pressure_is_block():
    sp = ParsedStatePoint(
        state_point_id="sp-001",
        stream_name="S-101",
        state_label="X",
        case_type="NORMAL",
        temperature_k=373.15,
        pressure_pa=None,  # 缺
        composition={"7732-18-5": 1.0},
    )
    r = ConflictResolver().resolve_state_points([sp], parent_streams=["S-101"])
    assert any(c.code == "SIM-SV02" for c in r.blocks)


# ---------------------------------------------------------------------------
# SIM-SV03：composition 摩尔分率和不归 1（容差 0.5%）
# ---------------------------------------------------------------------------


def test_sim_sv03_composition_sum_off_is_block():
    """spec 工艺实践参考：偏差 > 1% → BLOCK（拒绝保存）。"""
    sp = ParsedStatePoint(
        state_point_id="sp-001",
        stream_name="S-101",
        state_label="X",
        case_type="NORMAL",
        temperature_k=373.15,
        pressure_pa=101325.0,
        composition={"7732-18-5": 0.7, "74-82-8": 0.2},  # sum=0.9，差 10%
    )
    r = ConflictResolver().resolve_state_points([sp], parent_streams=["S-101"])
    assert any(
        c.code == "SIM-SV03" and c.level == ConflictLevel.BLOCK for c in r.blocks
    )


def test_sim_sv03_composition_sum_1_passes():
    sp = ParsedStatePoint(
        state_point_id="sp-001",
        stream_name="S-101",
        state_label="X",
        case_type="NORMAL",
        temperature_k=373.15,
        pressure_pa=101325.0,
        composition={"7732-18-5": 0.6, "74-82-8": 0.4},  # sum=1.0
    )
    r = ConflictResolver().resolve_state_points([sp], parent_streams=["S-101"])
    assert not [c for c in r.warnings if c.code == "SIM-SV03"]
    assert not [c for c in r.blocks if c.code == "SIM-SV03"]


def test_sim_sv03_composition_sum_tolerance_two_tier():
    """容差双层：≤0.1% 通过 / (0.1%, 1%] WARN / >1% BLOCK。

    - sum=0.999 (0.1% 偏差) → 通过
    - sum=0.995 (0.5% 偏差) → WARN
    - sum=0.985 (1.5% 偏差) → BLOCK
    """
    sp_ok = ParsedStatePoint(
        state_point_id="sp-ok",
        stream_name="S-101",
        state_label="X",
        case_type="NORMAL",
        temperature_k=373.15,
        pressure_pa=101325.0,
        composition={"7732-18-5": 0.9995},  # 偏差 0.05% < 0.1%
    )
    r = ConflictResolver().resolve_state_points([sp_ok], parent_streams=["S-101"])
    assert not [c for c in r.warnings if c.code == "SIM-SV03"]
    assert not [c for c in r.blocks if c.code == "SIM-SV03"]

    sp_warn = ParsedStatePoint(
        state_point_id="sp-warn",
        stream_name="S-101",
        state_label="X",
        case_type="NORMAL",
        temperature_k=373.15,
        pressure_pa=101325.0,
        composition={"7732-18-5": 0.995},  # 偏差 0.5%
    )
    r = ConflictResolver().resolve_state_points([sp_warn], parent_streams=["S-101"])
    assert any(
        c.code == "SIM-SV03" and c.level == ConflictLevel.WARN for c in r.warnings
    )

    sp_block = ParsedStatePoint(
        state_point_id="sp-block",
        stream_name="S-101",
        state_label="X",
        case_type="NORMAL",
        temperature_k=373.15,
        pressure_pa=101325.0,
        composition={"7732-18-5": 0.985},  # 偏差 1.5%
    )
    r = ConflictResolver().resolve_state_points([sp_block], parent_streams=["S-101"])
    assert any(
        c.code == "SIM-SV03" and c.level == ConflictLevel.BLOCK for c in r.blocks
    )


# ---------------------------------------------------------------------------
# SIM-SV04：stream 关联完整性
# ---------------------------------------------------------------------------


def test_sim_sv04_orphan_state_point_is_block():
    """state point 关联的 stream_name 不在 parent_streams → BLOCK（孤立）。"""
    sp = ParsedStatePoint(
        state_point_id="sp-001",
        stream_name="S-ORPHAN",  # 不在 parent_streams
        state_label="X",
        case_type="NORMAL",
        temperature_k=373.15,
        pressure_pa=101325.0,
        composition={"7732-18-5": 1.0},
    )
    r = ConflictResolver().resolve_state_points(
        [sp], parent_streams=["S-101", "S-102"]
    )
    assert any(c.code == "SIM-SV04" and c.level == ConflictLevel.BLOCK for c in r.blocks)


def test_sim_sv04_existing_stream_passes():
    sp = ParsedStatePoint(
        state_point_id="sp-001",
        stream_name="S-101",
        state_label="X",
        case_type="NORMAL",
        temperature_k=373.15,
        pressure_pa=101325.0,
        composition={"7732-18-5": 1.0},
    )
    r = ConflictResolver().resolve_state_points([sp], parent_streams=["S-101"])
    assert not [c for c in r.blocks if c.code == "SIM-SV04"]


# ---------------------------------------------------------------------------
# SIM-SV05：(stream_name, case_type) 唯一性
# ---------------------------------------------------------------------------


def test_sim_sv05_duplicate_state_point_is_block():
    """同 (stream_name, case_type) 出现多次 → BLOCK。"""
    base = dict(
        state_label="X",
        temperature_k=373.15,
        pressure_pa=101325.0,
        composition={"7732-18-5": 1.0},
    )
    sp1 = ParsedStatePoint(state_point_id="sp-1", stream_name="S-101", case_type="NORMAL", **base)
    sp2 = ParsedStatePoint(state_point_id="sp-2", stream_name="S-101", case_type="NORMAL", **base)
    r = ConflictResolver().resolve_state_points([sp1, sp2], parent_streams=["S-101"])
    assert any(c.code == "SIM-SV05" and c.level == ConflictLevel.BLOCK for c in r.blocks)


def test_sim_sv05_different_case_types_pass():
    """同 stream 不同 case_type 应允许。"""
    base = dict(
        state_label="X",
        temperature_k=373.15,
        pressure_pa=101325.0,
        composition={"7732-18-5": 1.0},
    )
    sp_normal = ParsedStatePoint(
        state_point_id="sp-n", stream_name="S-101", case_type="NORMAL", **base
    )
    sp_max = ParsedStatePoint(
        state_point_id="sp-m", stream_name="S-101", case_type="MAX", **base
    )
    r = ConflictResolver().resolve_state_points(
        [sp_normal, sp_max], parent_streams=["S-101"]
    )
    assert not [c for c in r.blocks if c.code == "SIM-SV05"]


# ---------------------------------------------------------------------------
# 批量 + 混合
# ---------------------------------------------------------------------------


def test_resolve_state_points_batch_returns_unified_report():
    sps = [
        ParsedStatePoint(  # OK
            state_point_id="sp-1",
            stream_name="S-101",
            state_label="设计工况",
            case_type="NORMAL",
            temperature_k=373.15,
            pressure_pa=101325.0,
            composition={"7732-18-5": 1.0},
        ),
        ParsedStatePoint(  # BLOCK: invalid case
            state_point_id="sp-2",
            stream_name="S-101",
            state_label="X",
            case_type="BOGUS",
            temperature_k=373.15,
            pressure_pa=101325.0,
            composition={"7732-18-5": 1.0},
        ),
        ParsedStatePoint(  # WARN: composition sum 0.5% deviation
            state_point_id="sp-3",
            stream_name="S-102",
            state_label="Y",
            case_type="MIN",
            temperature_k=350.0,
            pressure_pa=100000.0,
            composition={"7732-18-5": 0.995},
        ),
    ]
    r = ConflictResolver().resolve_state_points(sps, parent_streams=["S-101", "S-102"])
    assert r.stats["BLOCK"] >= 1
    assert r.stats["WARN"] >= 1
    assert r.has_blocks is True
    assert r.has_warnings is True


def test_resolve_state_points_empty_list_returns_empty_report():
    r = ConflictResolver().resolve_state_points([], parent_streams=[])
    assert r.stats["TOTAL"] == 0
    assert r.has_blocks is False
