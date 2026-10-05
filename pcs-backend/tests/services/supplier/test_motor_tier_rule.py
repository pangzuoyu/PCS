"""电机功率判定改为「对轴功率卡分档下限」 (P7 Sprint 4 S4-2 规则修订).

**原规则是错的**。SPEC §3.2.4(2) 写「实际电机额定功率 vs 设计电机功率 偏差 ±10%」，
但电机**按系列选取**（YB/IEC 档位），设计与实际落在相邻档就是 ±20% 以上的正常选型结果。
该规则量的是「供应商选了几档」，不是「设备好不好」。

改为 API 610 的电机裕量分档下限 —— 真正该校核的是「电机够不够驱动这台泵」，
与系列档位无关，也不会因档位差误报：

| 泵轴功率 P_a | 电机功率下限 |
|---|---|
| < 22 kW | 1.25 × P_a |
| 22 – 55 kW | 1.15 × P_a |
| > 55 kW | 1.10 × P_a |

**为什么不能拍一个 1.25**：蜡油加氢实测 —— 132-P-101A/B 轴功率 2214 kW、选配电机
2500 kW，比值 **1.129**，按 1.25 会判成不合格，但它是 2214 kW 的大泵，
1.10 即可 —— 标准允许。
"""

from __future__ import annotations

import pytest

from app.services.supplier.deviation_service import (
    QUALIFIED,
    UNQUALIFIED,
    DeviationRule,
    evaluate,
    motor_tier_factor,
)

RULE = DeviationRule(
    parameter="电机额定功率",
    kind="MOTOR_TIER_FLOOR",
    spec_ref="API 610 电机裕量分档: <22kW 1.25 / 22-55kW 1.15 / >55kW 1.10",
)


# ---------------------------------------------------------------------------
# 1. 分档因子
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shaft_kw,expected",
    [
        (4.63, 1.25),      # 132-P-406A/B 实际档位
        (20.97, 1.25),     # 132-P-401
        (21.99, 1.25),     # 21.99 < 22 → 仍小泵档
        (22.0, 1.15),      # 边界 22 → 中档
        (24.48, 1.15),     # 132-P-103A/B
        (55.0, 1.15),      # 边界 55 → 仍中档
        (55.01, 1.10),     # 55.01 > 55 → 大泵档
        (2214.06, 1.10),   # 132-P-101A/B
    ],
)
def test_motor_tier_factor(shaft_kw, expected):
    assert motor_tier_factor(shaft_kw) == expected


def test_motor_tier_factor_rejects_non_positive():
    """轴功率 0 或负 → 无档位可卡（不能当成 1.25 蒙混过关）."""
    assert motor_tier_factor(0) is None
    assert motor_tier_factor(-5) is None
    assert motor_tier_factor(None) is None


# ---------------------------------------------------------------------------
# 2. 判定: actual(电机) vs floor(轴功率)
# ---------------------------------------------------------------------------


def test_meets_floor_is_qualified():
    """电机达到分档下限 → 合格（不论电机比下限高多少）."""
    got = evaluate(RULE, design=24.48, actual=37.0)   # 1.15 档, 下限 28.2
    assert got.verdict == QUALIFIED


def test_below_floor_is_unqualified():
    got = evaluate(RULE, design=24.48, actual=25.0)   # 下限 28.2
    assert got.verdict == UNQUALIFIED
    assert "28.2" in got.note


def test_large_pump_not_failed_by_flat_1_25():
    """⚠️ 这条是改规则的核心动机: 2214 kW 大泵比值 1.129, 拍 1.25 会误判."""
    got = evaluate(RULE, design=2214.06, actual=2500.0)
    assert got.verdict == QUALIFIED
    assert "1.10" in got.note or "2435" in got.note


def test_small_pump_still_gets_full_1_25():
    """小泵档 1.25 是实的 —— 4.63 kW 轴功率配 5.0 kW 电机（比值 1.08）不合格."""
    got = evaluate(RULE, design=4.63, actual=5.0)     # 下限 5.79
    assert got.verdict == UNQUALIFIED


def test_series_step_up_is_not_a_deviation():
    """设计 37 kW / 实际 45 kW（相邻系列档）→ 只要达下限就合格, 不判偏差."""
    got = evaluate(RULE, design=24.48, actual=45.0)
    assert got.verdict == QUALIFIED


# ---------------------------------------------------------------------------
# 3. 缺输入 → 不可判 (fail-closed, 不得当成合格)
# ---------------------------------------------------------------------------


def test_missing_design_shaft_power_unverdictable():
    got = evaluate(RULE, design=None, actual=45.0)
    assert got.verdict not in (QUALIFIED, UNQUALIFIED)
    assert got.deviation_pct is None


def test_missing_actual_motor_power_unverdictable():
    got = evaluate(RULE, design=24.48, actual=None)
    assert got.verdict not in (QUALIFIED, UNQUALIFIED)


def test_zero_shaft_power_unverdictable():
    got = evaluate(RULE, design=0, actual=45.0)
    assert got.verdict not in (QUALIFIED, UNQUALIFIED)
    assert "0" in got.note


# ---------------------------------------------------------------------------
# 4. 蜡油加氢 16 台泵全量回归 (基础设计表, 真实数据)
# ---------------------------------------------------------------------------


def test_all_wax_pumps_with_motor_pass_the_tier():
    """基础设计表 16 台电机泵全部满足分档下限 —— 换规则后无一假性不合格."""
    from scripts.p7_open_012_t5_r1_verification import PUMP_DESIGN

    checked = 0
    for tag, d in PUMP_DESIGN.items():
        motor = d.get("电机额定功率")
        shaft = d.get("轴功率")
        if motor is None or shaft is None:
            continue
        got = evaluate(RULE, design=shaft, actual=motor)
        assert got.verdict == QUALIFIED, f"{tag}: {got.note}"
        checked += 1
    assert checked == 16


def test_bad_values_excluded_from_pump_design():
    """坏值按用户裁决 3 放弃不用 —— 不得混进设计数据."""
    from scripts.p7_open_012_t5_r1_verification import PUMP_DESIGN, PUMP_DESIGN_EXCLUDED

    assert "132-P-105A/B/C/D" in PUMP_DESIGN_EXCLUDED
    assert "132-P-105A/B/C/D" not in PUMP_DESIGN
