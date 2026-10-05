"""供应商偏差报告引擎 (P7 Sprint 4 Task S4-2 / SPEC V1.4 §3.2.4).

SPEC §3.2.4(2) 的允许偏差表**以泵为例**，6 条规则的判定类型是异构的 —— 不是
一个统一的百分比带：

| 实际数据字段        | 允许偏差                | 判定类型        |
|---------------------|-------------------------|-----------------|
| 流量-扬程曲线        | 额定点扬程 +5%/-0%      | 非对称带         |
| 实际效率曲线         | 设计流量下 ≥95% 设计值  | 下限比例         |
| 实际NPSHr           | 不得超过设计值          | 单边上限         |
| 实际电机额定功率     | 偏差 ±10%               | 对称带（方向敏感）|
| 实际转速、叶轮直径   | 允许差异，需重新校核性能 | 恒需复核         |
| 厂家型号、材质       | 不得低于设计要求         | 序数（人工）     |

后两行**没有数值阈值**；表头又明写「以泵为例」，故非泵设备参数必然落不到规则。
引擎对「无规则」「缺设计值」返回第 4 档 `UNVERDICTABLE`（不可判），且不可确认 ——
fail-closed：把「判不了」标成「合格」会让 SPEC §3.2.4(4) 的确认门禁形同虚设。
"""

from __future__ import annotations

import pytest

from app.services.supplier.deviation_service import (
    UNVERDICTABLE,
    UNQUALIFIED,
    WARNING,
    DeviationRule,
    evaluate,
    verdict_color,
)


def _dev(actual: float, design: float) -> float | None:
    """偏差% —— 与 service 同口径，测试里独立重算一次。"""
    return None if design == 0 else (actual - design) / design * 100.0


# ---------------------------------------------------------------------------
# 1. 扬程 —— 非对称带「额定点 +5%/-0%」
# ---------------------------------------------------------------------------


RULE_HEAD = DeviationRule(
    parameter="扬程", kind="ASYMMETRIC_BAND", lower=0.0, upper=5.0,
    spec_ref="SPEC §3.2.4(2) 实际流量-扬程曲线",
)


@pytest.mark.parametrize(
    "actual,expected",
    [
        (32.0, "QUALIFIED"),   # dev 0%        边界内
        (33.0, "QUALIFIED"),   # dev +3.125%   边界内
        (33.6, "QUALIFIED"),   # dev +5%       上边界（闭）
        (34.0, "WARNING"),     # dev +6.25%    超上限但扬程偏大可接受
        (31.9, "UNQUALIFIED"),  # dev -0.3125%  低于 -0% → 达不到设计扬程
        (32.0 - 0.01, "UNQUALIFIED"),
    ],
)
def test_head_asymmetric_band(actual, expected):
    got = evaluate(RULE_HEAD, design=32.0, actual=actual)
    assert got.verdict == expected


# ---------------------------------------------------------------------------
# 2. 效率 —— 下限比例「设计流量下实际效率 ≥95% 设计值」
# ---------------------------------------------------------------------------


RULE_EFF = DeviationRule(
    parameter="效率", kind="MIN_RATIO", ratio=0.95,
    spec_ref="SPEC §3.2.4(2) 实际效率曲线",
)


@pytest.mark.parametrize(
    "actual,expected",
    [
        (75.0, "QUALIFIED"),   # ratio 1.00
        (71.4, "QUALIFIED"),   # ratio 0.952  刚过线
        (71.25, "QUALIFIED"),  # ratio 0.95   边界（闭）
        (71.0, "UNQUALIFIED"), # ratio 0.9467 低于标准
    ],
)
def test_efficiency_min_ratio(actual, expected):
    assert evaluate(RULE_EFF, design=75.0, actual=actual).verdict == expected


# ---------------------------------------------------------------------------
# 3. NPSHr —— 单边上限「不得超过设计值」
# ---------------------------------------------------------------------------


RULE_NPSH = DeviationRule(
    parameter="NPSHr", kind="MAX_ONLY", spec_ref="SPEC §3.2.4(2) 实际NPSHr",
)


@pytest.mark.parametrize(
    "actual,expected",
    [
        (3.0, "QUALIFIED"),    # 等于设计值（闭）
        (2.5, "QUALIFIED"),    # 低于设计值 → 余量更大
        (3.5, "UNQUALIFIED"),  # 超过设计值 → 汽蚀风险
    ],
)
def test_npshr_max_only(actual, expected):
    assert evaluate(RULE_NPSH, design=3.0, actual=actual).verdict == expected


# ---------------------------------------------------------------------------
# 4. 电机额定功率 —— 对称带 ±10%，方向敏感
# ---------------------------------------------------------------------------


RULE_MOTOR = DeviationRule(
    parameter="电机额定功率", kind="SYMMETRIC_BAND", lower=-10.0, upper=10.0,
    spec_ref="SPEC §3.2.4(2) 实际电机额定功率",
)


@pytest.mark.parametrize(
    "actual,expected",
    [
        (55.0, "QUALIFIED"),    # 0%
        (60.5, "QUALIFIED"),   # +10% 上边界（闭）
        (49.5, "QUALIFIED"),   # -10% 下边界（闭）
        (62.0, "WARNING"),     # +12.7%  电机偏大，耗资但可用
        (48.0, "UNQUALIFIED"), # -12.7%  电机偏小 → 工艺要求不满足
    ],
)
def test_motor_power_symmetric_band(actual, expected):
    assert evaluate(RULE_MOTOR, design=55.0, actual=actual).verdict == expected


# ---------------------------------------------------------------------------
# 5. 转速 / 叶轮直径 —— 恒需复核（SPEC: 允许差异，需重新校核性能）
# ---------------------------------------------------------------------------


RULE_RECHECK = DeviationRule(
    parameter="转速", kind="RECHECK_ALWAYS", spec_ref="SPEC §3.2.4(2) 实际转速、叶轮直径",
)


def test_recheck_always_warns_and_flags():
    """零差异也标警告 —— SPEC 说「需重新校核性能」，校核未做就不能算合格."""
    got = evaluate(RULE_RECHECK, design=2950.0, actual=2950.0)
    assert got.verdict == WARNING
    assert got.requires_recheck is True


def test_recheck_flags_on_difference_too():
    got = evaluate(RULE_RECHECK, design=2950.0, actual=3000.0)
    assert got.verdict == WARNING
    assert got.requires_recheck is True


# ---------------------------------------------------------------------------
# 6. 材质 —— 序数比较，机器判不了
# ---------------------------------------------------------------------------


RULE_MATERIAL = DeviationRule(
    parameter="材质", kind="MANUAL_CHECK", spec_ref="SPEC §3.2.4(2) 厂家型号、材质",
)


def test_material_is_unverdictable_not_qualified():
    """序数比较 → 不可判 + 需人工核对。绝不标「合格」."""
    got = evaluate(RULE_MATERIAL, design="316L", actual="304")
    assert got.verdict == UNVERDICTABLE
    assert got.requires_manual_check is True


# ---------------------------------------------------------------------------
# 7. 缺设计值 → 不可判（用户裁决「设计值留空」的直接后果）
# ---------------------------------------------------------------------------


def test_missing_design_value_is_unverdictsable():
    got = evaluate(RULE_HEAD, design=None, actual=32.0)
    assert got.verdict == UNVERDICTABLE
    assert got.deviation_pct is None


def test_missing_actual_value_is_unverdictsable():
    got = evaluate(RULE_HEAD, design=32.0, actual=None)
    assert got.verdict == UNVERDICTABLE


def test_zero_design_value_does_not_divide_by_zero():
    """设计值 0 → 百分比偏差无定义，不可判；不得 ZeroDivisionError 500."""
    got = evaluate(RULE_HEAD, design=0.0, actual=32.0)
    assert got.verdict == UNVERDICTABLE


# ---------------------------------------------------------------------------
# 8. 颜色映射（SPEC §3.2.4(3)）
# ---------------------------------------------------------------------------


def test_verdict_colors_match_spec():
    assert verdict_color("QUALIFIED") == "绿色"
    assert verdict_color(WARNING) == "黄色"
    assert verdict_color(UNQUALIFIED) == "红色"
    # 不可判是本引擎新增的第 4 档（SPEC 表内含 2 条无数值阈值规则）
    assert verdict_color(UNVERDICTABLE) == "灰色"


def test_verdict_label_matches_spec():
    assert verdict_color("QUALIFIED") is not None
    from app.services.supplier.deviation_service import verdict_label

    assert verdict_label("QUALIFIED") == "合格"
    assert verdict_label(WARNING) == "警告"
    assert verdict_label(UNQUALIFIED) == "不合格"
    assert verdict_label(UNVERDICTABLE) == "不可判"
