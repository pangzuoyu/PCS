"""T5 Case 4 扩类 — 氮气 / 净化压缩空气 / 低温余热走真实子表 (P7 Sprint 4 Task S4-4).

**这块证据此前完全缺失**: 所有 T5 验证都基于合成 fixture, 只有电 / 燃料气 / 蒸汽
三类。XLS `能耗` sheet 里的**氮气、净化压缩空气从未走过 P7-6B 新建的
`utility_gas_media` / `utility_low_temp_heat` 两张表** —— 没有真实算例验证过它们。

溯源（`sample/1216D132惠州蜡油加氢装置计算14.7.17计算 - 副本.xlsx` → `能耗` sheet
→ 「能耗计算」块「消耗 数量」列，**不是**「能耗折算值」列）：

| 项目 | XLS 数量 | 备注 |
|---|---|---|
| 9 净化压缩空气 | 630 Nm3/h | 与汇总块 10.5 Nm3/min × 60 自洽 ✓ |
| 11 氮气 | 60 Nm3/h | ⚠️ 与汇总块「3/50 Nm3/min」对不上，见下 |

**⚠️ 两处 XLS 自身的问题（不采用其折标值，只取消耗量）**：
1. 氮气汇总块写 `3/50 Nm3/min 连续/间断`，`能耗计算` 块写 `60 Nm3/h`。
   3×60=180 ≠ 60，50×60=3000 ≠ 60，两者自相矛盾。取 `60`（`能耗计算` 块是本簿
   实际喂进折算的数字），**但该矛盾必须留档**。
2. 氮气的「MJ/Nm3」列写 `0.15` —— **0.15 是 kg标油/Nm3，不是 MJ/Nm3**。
   GB 30251-2024 附录A 序号 33 氮气 = 0.15 kg标油/m³ = **6.28 MJ/m³**。
   XLS 把 kg标油 数值填进了 MJ 列，**低估 41.87 倍**。

低温余热：`低温热` 在本簿**不存在**（只有 `项目信息` 的低温热水 105/65℃ 系统参数，
不是回收热量）。故 `LOW_TEMP_ITEMS` 为空 —— 不编造。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.asyncio


async def test_gas_media_items_are_sourced_from_xls():
    """扩类的两项消耗量必须带溯源常量, 且单位是 Nm3/h."""
    from scripts.p7_open_012_t5_r1_verification import GAS_MEDIA_ITEMS

    mediums = {row[1] for row in GAS_MEDIA_ITEMS}
    assert mediums == {"NITROGEN", "PURIFIED_AIR"}


async def test_gas_media_nitrogen_matches_xls_quantity():
    from scripts.p7_open_012_t5_r1_verification import GAS_MEDIA_ITEMS

    n2 = next(r for r in GAS_MEDIA_ITEMS if r[1] == "NITROGEN")
    assert n2[2] == pytest.approx(60.0)      # Nm3/h, XLS 能耗计算 r11
    assert n2[3] == 8400                      # 年小时
    assert n2[4] == pytest.approx(504000.0)   # 60 × 8400


async def test_gas_media_purified_air_matches_xls_quantity():
    from scripts.p7_open_012_t5_r1_verification import GAS_MEDIA_ITEMS

    air = next(r for r in GAS_MEDIA_ITEMS if r[1] == "PURIFIED_AIR")
    assert air[2] == pytest.approx(630.0)     # 10.5 Nm3/min × 60, 两处自洽
    assert air[4] == pytest.approx(5292000.0)  # 630 × 8400


async def test_low_temp_items_empty_because_xls_has_none():
    """XLS 无低温余热量 → 常量必须为空, 不许编造一个数填进去."""
    from scripts.p7_open_012_t5_r1_verification import LOW_TEMP_ITEMS

    assert LOW_TEMP_ITEMS == ()


async def test_gb_reference_includes_nitrogen_and_air():
    """独立基准必须自己把介质算进去 —— 只加 seed 不加基准等于没验."""
    from scripts.p7_open_012_t5_r1_verification import _gb30251_reference

    ref = _gb30251_reference()
    assert "NITROGEN" in ref["coefficient_conformance"]
    assert "INSTRUMENT_AIR_PURIFIED" in ref["coefficient_conformance"]


async def test_gb_reference_nitrogen_uses_kg_standard_not_xls_mj():
    """⚠️ XLS 把 0.15 kg标油 填进了 MJ 列 (低估 41.87 倍), 基准必须用附录A 6.28."""
    from scripts.p7_open_012_t5_r1_verification import _gb30251_reference

    entry = _gb30251_reference()["coefficient_conformance"]["NITROGEN"]
    assert entry["pcs_kgoe_per_nm3"] == pytest.approx(0.15)   # kg标油
    assert entry["std_mj_per_nm3"] == pytest.approx(6.28)     # MJ
    assert entry["xls_mj_per_nm3"] == pytest.approx(0.15)     # XLS 错值, 留档
    assert entry["xls_deviation_pct"] > 90.0                  # 低估 >90%


async def test_gb_reference_purified_air_mj_matches_standard():
    from scripts.p7_open_012_t5_r1_verification import _gb30251_reference

    entry = _gb30251_reference()["coefficient_conformance"]["INSTRUMENT_AIR_PURIFIED"]
    assert entry["pcs_kgoe_per_nm3"] == pytest.approx(0.038)
    assert entry["std_mj_per_nm3"] == pytest.approx(1.59)
    assert entry["deviation_pct"] == pytest.approx(0.0, abs=1e-6)


async def test_gb_reference_total_includes_gas_media():
    """总能耗必须含介质项 —— 只改系数不改总量等于没扩类."""
    from scripts.p7_open_012_t5_r1_verification import (
        GAS_MEDIA_ITEMS,
        _gb30251_reference,
    )

    ref = _gb30251_reference()
    n2_nm3 = next(r[4] for r in GAS_MEDIA_ITEMS if r[1] == "NITROGEN")
    air_nm3 = next(r[4] for r in GAS_MEDIA_ITEMS if r[1] == "PURIFIED_AIR")
    expected_gas_mj = n2_nm3 * 6.28 + air_nm3 * 1.59
    assert ref["gas_media_mj"] == pytest.approx(expected_gas_mj)
    assert ref["annual_total_energy_mj"] > expected_gas_mj  # 总量含它
