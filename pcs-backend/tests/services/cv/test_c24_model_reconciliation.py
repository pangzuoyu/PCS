"""P6-7 T5 (C-24): CV Masonelian 3-model 对账测试 (OPEN-P6-4-4 代码侧)。

加载 ``golden_c24_model_reconciliation.json`` 3 算例 + 通过 CvEngine.calculate()
验证 Masonelian_1973 / CHAPMAN_JANS / TONG 3 模型 vs 工艺室黄金 fixture：

- MASONELIAN_1973 / CHAPMAN_JANS: rel ≤ 1e-2（拟合公式 brief D5 <1%）
- TONG: rel ≤ 5e-2（简化初算，工艺室手算）

OPEN 关闭：OPEN-P6-4-4 代码侧。

测试 vs 黄金 fixture 协议：
1. fixture inputs 提供 P1_kpa / P2_kpa / FL / FF / Cf / vendor / valve_type；
   测试构造 CvEngine kwargs 时，P1 / P2 / dP_bar 由 P1_kpa/P2_kpa 推导
   （dP = P1 - P2，单位 bar）。
2. masonelian_model 从 fixture ``expected`` 取（与 service 3 模型枚举对齐）。
3. Q_m3h / SG / Pv / Pc 用工艺常用默认值（Q=100, SG=1.0, Pv=2 kPa, Pc=22 MPa
   — 与既有 test_cv_engine.py 既有用例保持一致）。
4. 容差：根据 fixture model 字段分支（MASONELIAN_1973 / CHAPMAN_JANS 1e-2；
   TONG 5e-2；与工艺室 baseline 容差协议一致）。
5. flash_steam_rate_kg_s 仅在 fixture expected > 0 时断言（fixture 0 时跳过
   —— 工艺室明示"无闪蒸"工况，避免工程近似 5% 上限钳制误判）。

fixture 边界 case：
- Case 1 (``c24_masonelian_1973_default_x_0p2``)：x=0.2 默认模型（D5 默认路径）
- Case 2 (``c24_chapman_jans_x_0p6``)：x=0.6 HYSYS 一致（D5 商业软件对账）
- Case 3 (``c24_tong_x_0p3``)：x=0.3 简化初算（D5 简化公式）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services.cv.cv_engine import CvEngine

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "golden_c24_model_reconciliation.json"
)


# ============================================================================
# Fixture 加载
# ============================================================================


def _load_cases() -> list[dict[str, Any]]:
    """加载黄金 fixture 3 算例。"""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["cases"]


# ============================================================================
# 测试：C-24 Masonelian / Chapman-Jans / Tong 3 模型对账（OPEN-P6-4-4）
# ============================================================================


@pytest.mark.parametrize(
    "case",
    _load_cases(),
    ids=lambda c: c["case_id"],
)
def test_c24_model_reconciliation(case: dict[str, Any]) -> None:
    """C-24 Masonelian 3 模型对账 vs 商业软件黄金 fixture（OPEN-P6-4-4）。

    验证：
        1. CvEngine.calculate() 输出的 ``fl`` 与 fixture ``fl_calculated`` 容差匹配
        2. ``masonelian_model`` 字段透传用户口径
        3. ``flash_steam_rate_kg_s`` 在 fixture 期望 > 0 时容差匹配（0 时跳过）

    Args:
        case: fixture 单算例 dict，含 inputs / expected / tolerance_rel
    """
    inp = case["inputs"]
    expected = case["expected"]
    model = expected["masonelian_model"]

    # 容差（rel）：MASONELIAN_1973 / CHAPMAN_JANS ≤ 1e-2，TONG ≤ 5e-2
    tol = 5e-2 if model == "TONG" else 1e-2

    # 推导 P1 / P2 / dP from fixture inputs（kPa → Pa）
    P1_pa = inp["P1_kpa"] * 1.0e3
    P2_pa = inp["P2_kpa"] * 1.0e3
    dP_bar = (P1_pa - P2_pa) / 1.0e5  # Pa → bar

    # 调 CvEngine.calculate()（P6-1 Task 8 + P6-4 Task 5 闪蒸修正）
    engine = CvEngine()
    result = engine.calculate(
        fluid_phase="LIQUID",
        # 流量 + 物性（与既有 test_cv_engine.py 默认值一致）
        Q_m3h=100.0,
        SG=1.0,
        dP_bar=dP_bar,
        # 阀门厂 + 修正系数（fixture 直接给出，绕过 vendor lookup 避免
        # valve_library key 约定（vendor, valve_model）顺序差异）
        FL=inp["FL"],
        FF=inp["FF"],
        Cf=inp["Cf"],
        # 物性：Pv 2 kPa（典型轻烃常温蒸汽压），Pc 22 MPa（典型水/轻烃临界压力）
        Pv=2000.0,
        Pc=22.0e6,
        # 工况
        P1_pa=P1_pa,
        P2_pa=P2_pa,
        # 3 模型口径
        masonelian_model=model,
    )

    # 1. masonelian_model 字段透传
    assert result["masonelian_model"] == model, (
        f"case {case['case_id']}: masonelian_model 应透传 {model!r}，"
        f"实际 {result['masonelian_model']!r}"
    )

    # 2. fl vs fixture（核心断言）
    actual_fl = result["fl"]
    expected_fl = expected["fl_calculated"]
    assert actual_fl == pytest.approx(expected_fl, rel=tol), (
        f"case {case['case_id']} ({model}): "
        f"fl {actual_fl:.6f} vs 黄金 {expected_fl:.6f} "
        f"(tol=rel {tol}，实际误差 "
        f"{abs(actual_fl - expected_fl) / expected_fl * 100:.2f}%)"
    )

    # 3. flash_steam_rate_kg_s（仅 fixture 期望 > 0 时断言）
    expected_flash = expected.get("flash_steam_rate_kg_s", 0.0)
    if expected_flash > 0:
        actual_flash = result["flash_steam_rate_kg_s"]
        assert actual_flash == pytest.approx(expected_flash, rel=tol), (
            f"case {case['case_id']} ({model}): "
            f"flash_steam_rate_kg_s {actual_flash:.6f} vs 黄金 {expected_flash:.6f} "
            f"(tol=rel {tol})"
        )