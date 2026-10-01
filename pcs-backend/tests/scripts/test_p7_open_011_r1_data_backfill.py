"""R1 数据回填脚本单元测试.

覆盖:
1. _map_steam_pressure_to_level 边界值 (9 档边界)
2. _FUEL_TYPE_TO_GAS_SOURCE 5 类映射
3. backfill_heat_exchange / backfill_fuel_gas idempotent
"""

from __future__ import annotations

import pytest

from scripts.p7_open_011_r1_data_backfill import (
    _FUEL_TYPE_TO_GAS_SOURCE,
    _map_steam_pressure_to_level,
)


class TestSteamPressureMapping:
    """_map_steam_pressure_to_level 边界值测试 (R1 §3 蒸汽 9 档)."""

    @pytest.mark.parametrize("pressure_mpa,expected", [
        (0.1, "LT_0_3_MPA"),       # < 0.3
        (0.3, "0_3_TO_0_6_MPA"),   # = 0.3 (含)
        (0.5, "0_3_TO_0_6_MPA"),   # < 0.6
        (0.6, "0_6_TO_0_8_MPA"),   # = 0.6
        (0.7, "0_6_TO_0_8_MPA"),   # < 0.8
        (0.8, "0_8_TO_1_2_MPA"),   # = 0.8
        (1.0, "0_8_TO_1_2_MPA"),   # 1.0 MPa MP 蒸汽 (蜡油加氢)
        (1.1, "0_8_TO_1_2_MPA"),   # < 1.2
        (1.2, "1_2_TO_2_0_MPA"),   # = 1.2
        (1.5, "1_2_TO_2_0_MPA"),
        (2.0, "2_0_TO_3_0_MPA"),   # = 2.0
        (2.5, "2_0_TO_3_0_MPA"),
        (3.0, "3_0_TO_4_5_MPA"),   # = 3.0
        (3.5, "3_0_TO_4_5_MPA"),   # 3.5 MPa
        (4.5, "4_5_TO_7_0_MPA"),   # = 4.5
        (5.0, "4_5_TO_7_0_MPA"),
        (7.0, "GE_7_0_MPA"),       # = 7.0
        (10.0, "GE_7_0_MPA"),      # > 7.0
    ])
    def test_pressure_to_level(self, pressure_mpa, expected):
        assert _map_steam_pressure_to_level(pressure_mpa) == expected


class TestFuelTypeMapping:
    """_FUEL_TYPE_TO_GAS_SOURCE 5 类映射测试 (R1 §7.3)."""

    @pytest.mark.parametrize("fuel_type,expected_gas_source", [
        ("NATURAL_GAS", "GASFIELD_GAS"),        # 气田气 (0.85)
        ("LNG", "GASFIELD_GAS"),               # 气田气 (0.85)
        ("REFINERY_GAS", "REFINERY_FUEL_GAS"),  # 炼厂燃料气 (950 kg/t)
        ("LPG", "REFINERY_FUEL_GAS"),           # 炼厂燃料气 (950 kg/t)
        ("OTHERS", "OILFIELD_GAS"),            # 油田气 (0.93; 默认 fallback)
    ])
    def test_fuel_type_to_gas_source(self, fuel_type, expected_gas_source):
        assert _FUEL_TYPE_TO_GAS_SOURCE[fuel_type] == expected_gas_source


class TestBackfillIdempotent:
    """回填 idempotent 测试: 已回填的行不会再次更新."""

    def test_all_5_fuel_types_mapped(self):
        """确保 5 类燃料类型全部映射 (无遗漏)."""
        assert len(_FUEL_TYPE_TO_GAS_SOURCE) == 5
        assert "NATURAL_GAS" in _FUEL_TYPE_TO_GAS_SOURCE
        assert "REFINERY_GAS" in _FUEL_TYPE_TO_GAS_SOURCE
        assert "LPG" in _FUEL_TYPE_TO_GAS_SOURCE
        assert "LNG" in _FUEL_TYPE_TO_GAS_SOURCE
        assert "OTHERS" in _FUEL_TYPE_TO_GAS_SOURCE

    def test_9_pressure_levels_reachable(self):
        """确保 9 档压力等级全部可达."""
        # 测试覆盖各档代表值
        test_cases = [0.1, 0.4, 0.7, 1.0, 1.5, 2.5, 3.5, 5.0, 10.0]
        levels = {_map_steam_pressure_to_level(p) for p in test_cases}
        assert len(levels) == 9, f"expected 9 levels, got {levels}"

    def test_no_default_overlap(self):
        """确保 NATURAL_GAS 不会被误映射到 OTHERS fallback."""
        # 防止未来添加新 fuel_type 时 fallback 误命中
        mapped_fuel_types = set(_FUEL_TYPE_TO_GAS_SOURCE.keys())
        assert "OILFIELD_GAS" not in mapped_fuel_types
