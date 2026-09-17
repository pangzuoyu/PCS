"""SUP-P5-PSV-002 V1.14 §4.3 Kb 4 阶段策略 + 合成 _KB_DATA 测试。

按 SPEC V1.14 §8 gate #10 全部 8 场景：

覆盖：
1. SPRING_LOADED + BP=0 → "none" / 1.0（标准定义）
2. SPRING_LOADED + BP=20 + LESER + 16% → manufacturer:LESER / 0.95
3. SPRING_LOADED + BP=20 + LESER + 21% → manufacturer:LESER / 0.90
4. SPRING_LOADED + BP=20 + LESER + 13% → 插值（10→16：1.00→0.95）
5. SPRING_LOADED + BP=20 + LESER+Consolidated + 16% → mixed / 0.955
6. SPRING_LOADED + BP=20 + Unknown + 16% → api520_fig30 / 0.93
7. PILOT_OPERATED + BP=20 + LESER + 16% → en4126 / 0.93（不取 LESER）
8. BALANCED_BELLOWS + BP=20 + LESER + 16% → manufacturer:LESER / 0.95

线性插值边界 + 边界 overpressure（10%、21%）独立测试。
"""
from __future__ import annotations

import pytest

from app.services.psv.kb_service import lookup_kb_with_priority

# ============================================================================
# §8 gate #10 全部 8 场景
# ============================================================================


def test_gate10_1_spring_zero_bp_standard():
    """场景 1：SPRING_LOADED + BP=0 → 标准定义 "none" / 1.0。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=0.0,
        overpressure_pct=10.0,
        valve_type="SPRING_LOADED",
    )
    assert kb == 1.0
    assert source == "none"


def test_gate10_2_leser_16pct():
    """场景 2：SPRING_LOADED + BP=20 + LESER + 16% → manufacturer:LESER / 0.95。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=16.0,
        valve_type="SPRING_LOADED",
        valve_brand="LESER",
    )
    assert kb == 0.95
    assert source == "manufacturer:LESER"


def test_gate10_3_leser_21pct():
    """场景 3：SPRING_LOADED + BP=20 + LESER + 21% → manufacturer:LESER / 0.90。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=21.0,
        valve_type="SPRING_LOADED",
        valve_brand="LESER",
    )
    assert kb == 0.90
    assert source == "manufacturer:LESER"


def test_gate10_4_leser_interpolation_13pct():
    """场景 4：SPRING_LOADED + BP=20 + LESER + 13% → 插值（10→16：1.00→0.95）。

    13 在 [10, 16] 区间，y = 1.00 + (0.95-1.00) * (13-10)/(16-10) = 1.00 - 0.025 = 0.975
    """
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=13.0,
        valve_type="SPRING_LOADED",
        valve_brand="LESER",
    )
    assert kb == pytest.approx(0.975)
    assert source == "manufacturer:LESER"


def test_gate10_5_mixed_avg():
    """场景 5：SPRING_LOADED + BP=20 + LESER+Consolidated + 16% → mixed / 0.955。

    (0.95 + 0.96) / 2 = 0.955
    """
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=16.0,
        valve_type="SPRING_LOADED",
        valve_brand="LESER+Consolidated",
    )
    assert kb == pytest.approx(0.955)
    assert source == "mixed:LESER+Consolidated"


def test_gate10_6_unknown_brand_fallback_api520():
    """场景 6：SPRING_LOADED + BP=20 + Unknown + 16% → api520_fig30 / 0.93。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=16.0,
        valve_type="SPRING_LOADED",
        valve_brand="Unknown_brand",
    )
    assert kb == 0.93
    assert source == "api520_fig30"


def test_gate10_7_pilot_uses_en4126():
    """场景 7：PILOT_OPERATED + BP=20 + LESER + 16% → en4126 / 0.93（不取 LESER 曲线）。

    PILOT_OPERATED 不查 brand → 直接 en4126 fallback。
    """
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=16.0,
        valve_type="PILOT_OPERATED",
        valve_brand="LESER",
    )
    assert kb == 0.93
    assert source == "en4126"


def test_gate10_8_balanced_bellows_uses_brand():
    """场景 8：BALANCED_BELLOWS + BP=20 + LESER + 16% → manufacturer:LESER / 0.95。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=16.0,
        valve_type="BALANCED_BELLOWS",
        valve_brand="LESER",
    )
    assert kb == 0.95
    assert source == "manufacturer:LESER"


# ============================================================================
# 边界 + brand normalize
# ============================================================================


def test_leser_10pct_boundary():
    """LESER + 10% → 边界 1.00。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=10.0,
        overpressure_pct=10.0,
        valve_type="SPRING_LOADED",
        valve_brand="LESER",
    )
    assert kb == 1.0
    assert source == "manufacturer:LESER"


def test_leser_above_max_clamps():
    """LESER + 25%（>max 21%）→ 钳制到 0.90。"""
    kb, _ = lookup_kb_with_priority(
        bp_pct=10.0,
        overpressure_pct=25.0,
        valve_type="SPRING_LOADED",
        valve_brand="LESER",
    )
    assert kb == 0.90


def test_leser_below_min_clamps():
    """LESER + 5%（<min 10%）→ 钳制到 1.00。"""
    kb, _ = lookup_kb_with_priority(
        bp_pct=10.0,
        overpressure_pct=5.0,
        valve_type="SPRING_LOADED",
        valve_brand="LESER",
    )
    assert kb == 1.0


def test_brand_with_manufacturer_prefix():
    """valve_brand 含 'manufacturer:' 前缀 → 仍能查到。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=10.0,
        overpressure_pct=16.0,
        valve_type="SPRING_LOADED",
        valve_brand="manufacturer:Consolidated",
    )
    assert kb == 0.96
    assert source == "manufacturer:Consolidated"


def test_no_brand_with_bp_falls_back():
    """SPRING_LOADED + BP=20 + 无 brand → 触发保守回退。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=16.0,
        valve_type="SPRING_LOADED",
        valve_brand=None,
    )
    assert kb == 0.93
    assert source == "api520_fig30"


def test_mixed_partial_unknown_falls_back():
    """mixed 中任一厂商不在数据 → 整个 fallback（保守）。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=16.0,
        valve_type="SPRING_LOADED",
        valve_brand="LESER+UnknownMFR",
    )
    assert source == "api520_fig30"
    assert kb == 0.93


def test_three_way_mixed_average():
    """3 厂商 mixed → 3 者平均。"""
    # 16%: (0.95 + 0.96 + 0.94) / 3 = 0.95
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=16.0,
        valve_type="SPRING_LOADED",
        valve_brand="LESER+Consolidated+Anderson_Greenwood",
    )
    assert kb == pytest.approx(0.95)
    assert source == "mixed:LESER+Consolidated+Anderson_Greenwood"


# ============================================================================
# OPEN-10-4 余项：单厂商路径全覆盖（Consolidated / Anderson_Greenwood）
# ============================================================================


def test_consolidated_10pct():
    """Consolidated 10% → Kb=1.00（满载边界；合成数据）。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=10.0,
        valve_type="SPRING_LOADED",
        valve_brand="Consolidated",
    )
    assert kb == pytest.approx(1.00)
    assert source == "manufacturer:Consolidated"


def test_consolidated_16pct():
    """Consolidated 16% → Kb=0.96（中间点）。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=16.0,
        valve_type="SPRING_LOADED",
        valve_brand="Consolidated",
    )
    assert kb == pytest.approx(0.96)
    assert source == "manufacturer:Consolidated"


def test_consolidated_21pct():
    """Consolidated 21% → Kb=0.92（满载边界）。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=21.0,
        valve_type="SPRING_LOADED",
        valve_brand="Consolidated",
    )
    assert kb == pytest.approx(0.92)
    assert source == "manufacturer:Consolidated"


def test_anderson_greenwood_10_16_21_full_curve():
    """Anderson_Greenwood 三档（10%/16%/21%）覆盖完整曲线。"""
    expected = [(10.0, 1.00), (16.0, 0.94), (21.0, 0.88)]
    for op, expected_kb in expected:
        kb, source = lookup_kb_with_priority(
            bp_pct=20.0,
            overpressure_pct=op,
            valve_type="SPRING_LOADED",
            valve_brand="Anderson_Greenwood",
        )
        assert kb == pytest.approx(expected_kb), f"op={op} 期望 {expected_kb} 实际 {kb}"
        assert source == "manufacturer:Anderson_Greenwood"


def test_anderson_greenwood_brand_with_manufacturer_prefix():
    """AG 'manufacturer:Anderson_Greenwood' 前缀形式 → 命中。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=16.0,
        valve_type="BALANCED_BELLOWS",
        valve_brand="manufacturer:Anderson_Greenwood",
    )
    assert kb == pytest.approx(0.94)
    assert source == "manufacturer:Anderson_Greenwood"


def test_three_way_mixed_at_21pct():
    """3 厂商 mixed @ 21% → (0.90 + 0.92 + 0.88) / 3 = 0.90。"""
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=21.0,
        valve_type="SPRING_LOADED",
        valve_brand="LESER+Consolidated+Anderson_Greenwood",
    )
    assert kb == pytest.approx(0.90)
    assert source == "mixed:LESER+Consolidated+Anderson_Greenwood"


def test_pilot_operated_ignores_brand_returns_en4126():
    """PILOT_OPERATED 一律 en4126，不取 LESER（专保守路径；EN 4126 标准要求）。"""
    # BP=0 SPRING 也强制 PILOT → en4126（策略 1 仅 SPRING）
    kb, source = lookup_kb_with_priority(
        bp_pct=20.0,
        overpressure_pct=16.0,
        valve_type="PILOT_OPERATED",
        valve_brand="LESER",
    )
    # en4126 保守曲线 @ 16% = 0.93（与 api520_fig30 共用 _CONSERVATIVE_KB_FALLBACK）
    assert kb == pytest.approx(0.93)
    assert source == "en4126"


def test_spring_zero_bp_with_brand_still_returns_none():
    """策略 1 优先：SPRING_LOADED + BP=0 + 指定品牌 → 仍返回 ("none", 1.0)。"""
    # 即便指定 LESER（标准定义优先于品牌查询）
    kb, source = lookup_kb_with_priority(
        bp_pct=0.0,
        overpressure_pct=16.0,
        valve_type="SPRING_LOADED",
        valve_brand="LESER",
    )
    assert kb == pytest.approx(1.00)
    assert source == "none"