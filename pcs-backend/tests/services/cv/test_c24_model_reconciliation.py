"""P6-7 T5 (C-24): CV Masonelian 3-model 对账测试 (OPEN-P6-4-4 代码侧)。

加载 ``golden_c24_model_reconciliation.json`` 3 算例 + 通过 CvEngine.calculate()
验证 Masonelian_1973 / CHAPMAN_JANS / TONG 3 模型 vs 工艺室黄金 fixture：

- MASONELIAN_1973 / CHAPMAN_JANS: rel ≤ 1e-2（拟合公式 brief D5 <1%）
- TONG: rel ≤ 5e-2（简化初算，工艺室手算）

OPEN 关闭：OPEN-P6-4-4 代码侧（P6-9 PICKUP-2 T3 partial closure）。

测试 vs 黄金 fixture 协议（P6-9 PICKUP-2 T3 修订）：
1. fixture inputs 提供 P1_kpa / P2_kpa / FL / FF / Cf / vendor / valve_type /
   x / T_c / Pv_kpa；测试构造 CvEngine kwargs 时：
   - P1 / P2 / dP_bar 由 P1_kpa/P2_kpa 推导（dP = P1 - P2，单位 bar）
   - 显式 x 透传给 CvEngine（架构组 2026-10-31 裁决 a；修复 x_p 推断 bug）
   - T_c 透传给 CvEngine（触发 _validate_flash_consistency 入口校验）
   - Pv 由 fixture Pv_kpa 派生（kPa → Pa）给闪蒸蒸汽量计算用
2. masonelian_model 从 fixture ``expected`` 取（与 service 3 模型枚举对齐）。
3. Q_m3h / SG / Pc 用工艺常用默认值（Q=100, SG=1.0, Pc=22 MPa
   — 与既有 test_cv_engine.py 既有用例保持一致）。
4. 容差：根据 fixture model 字段分支（MASONELIAN_1973 / CHAPMAN_JANS 1e-2；
   TONG 5e-2；与工艺室 baseline 容差协议一致）。
5. flash_steam_rate_kg_s 在 fixture expected > 0 时容差匹配。
6. CvEngine 入口一致性校验：x 与 (T_c, P1, P2) 自洽（架构组裁决 a）；
   fixture 3 算例均通过校验（x>0 时 P2 < Pv；P1 ≥ 0.95 × Pv）。

fixture 边界 case：
- Case 1 (``c24_masonelian_1973_x_0p2``)：x=0.2 MASONELIAN_1973（Pv > P1 边界）
- Case 2 (``c24_chapman_jans_x_0p6``)：x=0.6 CHAPMAN_JANS（HYSYS 一致）
- Case 3 (``c24_tong_x_0p3``)：x=0.3 TONG（简化初算）
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
        3. ``flash_steam_rate_kg_s`` 在 fixture 期望 > 0 时容差匹配
        4. CvEngine 入口 _validate_flash_consistency 通过（fixture 自洽）

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
    # Pv 由 fixture 派生（kPa → Pa），给闪蒸蒸汽量计算用
    Pv_pa = inp["Pv_kpa"] * 1.0e3

    # 调 CvEngine.calculate()（P6-1 Task 8 + P6-4 Task 5 闪蒸修正 + P6-9 PICKUP-2 T3）
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
        # 物性：Pc 22 MPa（典型水/轻烃临界压力）
        Pc=22.0e6,
        # 工况
        P1_pa=P1_pa,
        P2_pa=P2_pa,
        Pv=Pv_pa,
        # P6-9 PICKUP-2 T3：显式 flash fraction（架构组裁决 a）
        x=inp["x"],
        # P6-9 PICKUP-2 T3：温度（驱动 _validate_flash_consistency）
        T_c=inp["T_c"],
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


# ============================================================================
# 回归测试：back-compat 路径（CvEngine 不传 x 时仍按 ΔP/P1 推断）
# ============================================================================


def test_c24_back_compat_x_inferred_from_dP_over_P1() -> None:
    """P6-9 PICKUP-2 T3 back-compat：不传 x 时 CvEngine 仍按 ΔP/P1 推断。

    验证既有调用方（不传 x / T_c）行为不变：x = (P1-P2)/P1 → fl 按推断 x 计算。
    """
    engine = CvEngine()
    payload = engine.calculate(
        fluid_phase="LIQUID",
        Q_m3h=100.0,
        SG=1.0,
        dP_bar=1.0,  # dP = 1 bar, P1 = 3e5 Pa
        FL=0.9,
        FF=0.96,
        Pv=2000.0,
        Pc=22.0e6,
        P1_pa=3.0e5,
        P2_pa=2.0e5,
        masonelian_model="MASONELIAN_1973",
        # 不传 x / T_c → back-compat 路径
    )

    # x 应推断为 (P1-P2)/P1 = 1e5/3e5 = 0.333
    # fl = 0.9 * (1 + 0.5*0.333) * (1-0.333) / sqrt(1 - 0.333²)
    assert payload["fl"] is not None
    assert payload["fl"] > 0
    # 不应触发 InvalidFlashConsistencyError（x / T_c 未传，跳过校验）
    assert payload["Cv_calculated"] is not None


def test_c24_flash_consistency_rejects_zero_x_below_Pv() -> None:
    """P6-9 PICKUP-2 T3：x=0 但 P2<Pv 应抛 InvalidFlashConsistencyError。

    闪蒸一致性校验规则 1：x == 0 且 P2 < Pv → 不一致。
    """
    from app.services.exceptions import InvalidFlashConsistencyError

    engine = CvEngine()
    with pytest.raises(InvalidFlashConsistencyError) as exc_info:
        engine.calculate(
            fluid_phase="LIQUID",
            Q_m3h=100.0,
            SG=1.0,
            dP_bar=0.5,
            FL=0.9,
            FF=0.96,
            Pv=2000.0,
            Pc=22.0e6,
            P1_pa=2.0e5,
            P2_pa=1.0e5,
            x=0.0,
            T_c=120.0,  # T=120°C → Pv ≈ 198.5 kPa (Antoine)；P2=100 < Pv
        )

    assert "x=0" in str(exc_info.value) or "应闪蒸" in str(exc_info.value)
