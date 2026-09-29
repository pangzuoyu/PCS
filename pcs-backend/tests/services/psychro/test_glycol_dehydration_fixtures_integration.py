"""P6-8 T6 — 黄金 fixtures 4 子模块完整性 check (OPEN-P6-6A-6 集成)。

覆盖 P6-8 T1-T4 黄金 fixture：

  * T1 ``golden_c16_reboiler_stripping.json`` —
    Reboiler Duty + Stripping Gas Rate (子任务 1+2)
  * T2 ``golden_c16_stripping_gas_rate.json`` —
    Stripping Gas Rate XLS E32 / 380°F / 250→300°F 钳制 (子任务 2)
  * T3 ``golden_c16_full_column_diameter.json`` —
    Full Column Diameter K=7.1121 6 工况 (子任务 3)
  * T4 ``golden_c16_lean_glycol.json`` —
    Lean Glycol Concentration GPSA Fig 20-4 (子任务 4)

本测试仅 verify fixture 文件存在性 + ``_meta`` 字段完整性，不重做数值对账
（数值对账见 T1-T4 各专属 test_*.py）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_FIXTURE_NAMES = (
    "golden_c16_reboiler_stripping.json",
    "golden_c16_stripping_gas_rate.json",
    "golden_c16_full_column_diameter.json",
    "golden_c16_lean_glycol.json",
)


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


# ============================================================================
# 4 子模块 fixture 完整性 check
# ============================================================================


def test_p6_8_4_submodules_fixtures_completeness() -> None:
    """T6 4 子模块黄金 fixture 完整性 check (OPEN-P6-6A-6 集成)"""
    # T1: Reboiler Duty + Stripping Gas Rate
    reb_strip = _load("golden_c16_reboiler_stripping.json")
    assert len(reb_strip["cases"]) >= 1
    assert any("reboiler" in c["case_id"] for c in reb_strip["cases"])

    # T2: Stripping Gas Rate
    sgr = _load("golden_c16_stripping_gas_rate.json")
    assert len(sgr["cases"]) >= 3
    assert any("xls_e32" in c["case_id"] for c in sgr["cases"])

    # T3: Full Column Diameter
    fcd = _load("golden_c16_full_column_diameter.json")
    assert len(fcd["cases"]) == 6
    assert fcd["k_recommended"] == 7.1121

    # T4: Lean Glycol
    lg = _load("golden_c16_lean_glycol.json")
    assert len(lg["cases"]) >= 3
    assert len(lg["data_points_reference"]) == 4


# ============================================================================
# 4 子模块 fixture _meta.source 文档化
# ============================================================================


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_p6_8_4_submodules_source_attribution(fixture_name: str) -> None:
    """T6 4 子模块 fixture _meta.source/delivered_by 文档化（工艺室 2026-10-31 提供）。"""
    data = _load(fixture_name)
    meta = data["_meta"]
    assert "open_item" in meta
    assert "delivered_by" in meta
    assert "source" in meta
    # T3 fixture 由工艺室 2026-10-15 提供；其他 3 个为 2026-10-31。统一以"工艺室"前缀断言。
    assert "工艺室" in meta["delivered_by"]


# ============================================================================
# 4 子模块 fixture OPEN-P6-6A-6 标签一致性
# ============================================================================


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_p6_8_4_submodules_consistency(fixture_name: str) -> None:
    """T6 4 子模块 fixture 都标 OPEN-P6-6A-6（integration tag 一致性）。"""
    data = _load(fixture_name)
    assert "OPEN-P6-6A-6" in data["_meta"]["open_item"]