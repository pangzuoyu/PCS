"""P6-7 T5 (C-24): CV 24 厂商 × 阀型 FL/FF/Cf 系数测试 (OPEN-P6-4-4 代码侧)。

加载 ``golden_c24_valve_library.json`` 24 厂商组合 + 验证 FL / FF / Cf
无量纲系数字段值。

测试要点（OPEN-P6-4-4）：
1. fixture 共 6 厂商（MASONELIAN / FISHER / SAMSON / EMERSON / KOSO / YAMATAKE）
   × 4 阀型（GLOBE / BALL / BUTTERFLY / DIAPHRAGM）= 24 组合
2. 每组合校验 FL ∈ (0, 1] / FF ∈ (0, 1] / Cf ∈ (0, 1] 字段范围
3. 不调 service（fixture 直接验证加载 + 字段边界；P6-5 工艺室接管时切换到
   DB CONFIG 表 / 工艺工程师实测值）

设计原则：
- pytest.mark.parametrize 跑 24 组合（每组合 1 test id）
- fixture 加载用 ``json`` + ``Path``（与既有 test_flashing_correction.py 一致）
- 不传 vendor / valve_model 给 cv_engine（绕过 _VALVE_LIBRARY key 顺序差异：
  业务 fixture 用 (vendor, valve_type) 二维平铺，service _VALVE_LIBRARY 用
  (valve_type, vendor_model) tuple key —— 字段值直接比对可避免约定不一致）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "golden_c24_valve_library.json"
)


# ============================================================================
# Fixture 加载 + 24 组合展开
# ============================================================================


def _expand_library() -> list[dict[str, Any]]:
    """展开 fixture 24 厂商组合为列表（vendor × valve_type 平铺）。

    Returns:
        list[dict]: 每元素含 vendor / valve_type / FL / FF / Cf / source_page
    """
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    library: dict[str, dict[str, dict[str, Any]]] = data["valve_library"]

    cases: list[dict[str, Any]] = []
    for vendor, valves in library.items():
        for valve_type, coeffs in valves.items():
            cases.append(
                {
                    "vendor": vendor,
                    "valve_type": valve_type,
                    "FL": coeffs["FL"],
                    "FF": coeffs["FF"],
                    "Cf": coeffs["Cf"],
                    "source_page": coeffs.get("source_page", ""),
                }
            )
    return cases


# ============================================================================
# 测试：C-24 24 厂商 × 阀型 FL/FF/Cf 字段值（OPEN-P6-4-4）
# ============================================================================


def test_c24_valve_library_size_24() -> None:
    """C-24 24 厂商库 fixture 完整性：vendor × valve_type = 24 组合。

    6 厂商（MASONELIAN/FISHER/SAMSON/EMERSON/KOSO/YAMATAKE）×
    4 阀型（GLOBE/BALL/BUTTERFLY/DIAPHRAGM）= 24（与 SPEC §3.2.1 表 3.2.1-3
    D5 验收一致）。
    """
    cases = _expand_library()
    assert len(cases) == 24, (
        f"应展开 24 厂商组合（6×4），实际 {len(cases)}"
    )

    # 厂商唯一性 + 阀型唯一性
    vendors = {c["vendor"] for c in cases}
    valve_types = {c["valve_type"] for c in cases}
    assert len(vendors) == 6, f"应 6 个厂商，实际 {len(vendors)}: {vendors}"
    assert len(valve_types) == 4, (
        f"应 4 个阀型，实际 {len(valve_types)}: {valve_types}"
    )


@pytest.mark.parametrize(
    "case",
    _expand_library(),
    ids=lambda c: f"{c['vendor']}_{c['valve_type']}",
)
def test_c24_valve_library_coefficients(case: dict[str, Any]) -> None:
    """C-24 24 厂商 × 阀型 FL/FF/Cf 系数字段值测试（OPEN-P6-4-4）。

    验证工艺室黄金 fixture 24 组合字段值边界：
        - FL ∈ (0, 1.0]（压力恢复系数，无量纲）
        - FF ∈ (0, 1.0]（临界压力比系数，无量纲）
        - Cf ∈ (0, 1.0]（阀门几何系数，无量纲）

    Args:
        case: 单组合 dict，含 vendor / valve_type / FL / FF / Cf
    """
    vendor = case["vendor"]
    valve_type = case["valve_type"]
    FL = case["FL"]
    FF = case["FF"]
    Cf = case["Cf"]

    # FL：压力恢复系数（典型 0.5~0.95，越下界抛 InvalidFLFFError）
    assert 0 < FL <= 1.0, (
        f"{vendor}/{valve_type} FL={FL} 越界（必须在 (0, 1.0]）"
    )

    # FF：临界压力比系数（典型 0.85~0.98）
    assert 0 < FF <= 1.0, (
        f"{vendor}/{valve_type} FF={FF} 越界（必须在 (0, 1.0]）"
    )

    # Cf：阀门几何系数（典型 0.8~1.0）
    assert 0 < Cf <= 1.0, (
        f"{vendor}/{valve_type} Cf={Cf} 越界（必须在 (0, 1.0]）"
    )