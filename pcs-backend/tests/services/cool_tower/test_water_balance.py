"""P6-2 Task 24 COOL_TOWER water_balance 测试（SPEC §3.2.4.3 + §3.2.4.4）。

按 SPEC §3.2.4 P6-CT-001：

- 8 单元测试（不依赖 DB；纯计算函数）：
  1. test_water_flow_basic：H=1000 kW, ΔT=10 K → q_w = 0.02389 m³/s（手算）
  2. test_water_flow_heat_load_scaling：H 加倍 → q_w 加倍
  3. test_water_flow_m3_h_conversion：q_w_m3_h = q_w_m3_s × 3600
  4. test_water_flow_input_validation：heat<=0 / delta_t<=0 / rho<=0 /
     cp<=0 → WaterFlowInputError
  5. test_water_balance_basic：q_w=0.023885, ΔT=10, cycle=4, drift=0.001
     → E=4.17e-4 / D=2.39e-5 / B=1.15e-4 / M=5.56e-4
  6. test_water_balance_cycle_ratio_scaling：cycle=5 → B 减小
  7. test_water_balance_blowdown_clamp_to_zero：drift=0.05（极大）→ blowdown=0
  8. test_water_balance_input_validation：cycle<=1 / drift>0.1 / q_w<=0
     → WaterBalanceInputError
  9. test_water_flow_formula_ref / test_water_balance_formula_ref：
     formula_ref 锁定

验收（SPEC §3.2.4.7）：蒸发损失 vs 经验法 1% ΔT ≤ 5%。
    E / q_w ≈ ΔT × Cp / h_vap = 10 × 4.187 / 2400 ≈ 1.74% ΔT（典型 ≤5%）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.cool_tower import (  # noqa: E402
    WaterBalanceInput,
    WaterBalanceInputError,
    WaterBalanceResult,
    WaterFlowInput,
    WaterFlowInputError,
    WaterFlowResult,
    calc_water_balance,
    calc_water_flow,
)
from app.services.exceptions import PcsError  # noqa: E402

# ============================================================================
# §3.2.4.3 循环水量
# ============================================================================


# 1. 基础工况（手算校核）
def test_water_flow_basic() -> None:
    """H=1000 kW, ΔT=10 K → q_w_m3_s = 1000/(1000×4.187×10) ≈ 0.02389 m³/s。

    手算：q_w_m3_s = 1000 / (1000 × 4.187 × 10) = 0.023885
          q_w_m3_h = 0.023885 × 3600 = 85.99 m³/h
    验收（SPEC §3.2.4.7）：vs 手算 ≤2%。
    """
    inp = WaterFlowInput(heat_load_kw=1000.0, delta_t_k=10.0)
    r = calc_water_flow(inp)
    assert isinstance(r, WaterFlowResult)
    assert r.q_w_m3_s == pytest.approx(0.023885, rel=1e-4)
    assert r.q_w_m3_h == pytest.approx(85.99, rel=1e-3)


# 2. heat_load 缩放（线性正比）
def test_water_flow_heat_load_scaling() -> None:
    """H 加倍 → q_w 加倍（线性正比）。"""
    inp_1k = WaterFlowInput(heat_load_kw=1000.0, delta_t_k=10.0)
    inp_2k = WaterFlowInput(heat_load_kw=2000.0, delta_t_k=10.0)
    r1 = calc_water_flow(inp_1k)
    r2 = calc_water_flow(inp_2k)
    assert r2.q_w_m3_s == pytest.approx(2.0 * r1.q_w_m3_s, rel=1e-12)


# 3. m³/s ↔ m³/h 单位换算
def test_water_flow_m3_h_conversion() -> None:
    """q_w_m3_h = q_w_m3_s × 3600（恒等）。"""
    inp = WaterFlowInput(heat_load_kw=500.0, delta_t_k=5.0)
    r = calc_water_flow(inp)
    assert r.q_w_m3_h == pytest.approx(r.q_w_m3_s * 3600.0, rel=1e-12)


# 4. 输入校验
def test_water_flow_input_validation() -> None:
    """heat<=0 / delta_t<=0 / rho<=0 / cp<=0 → WaterFlowInputError（422）。"""
    # heat <= 0
    with pytest.raises(WaterFlowInputError):
        calc_water_flow(WaterFlowInput(heat_load_kw=0.0, delta_t_k=10.0))
    with pytest.raises(WaterFlowInputError):
        calc_water_flow(WaterFlowInput(heat_load_kw=-1.0, delta_t_k=10.0))
    # delta_t <= 0
    with pytest.raises(WaterFlowInputError):
        calc_water_flow(WaterFlowInput(heat_load_kw=1000.0, delta_t_k=0.0))
    with pytest.raises(WaterFlowInputError):
        calc_water_flow(WaterFlowInput(heat_load_kw=1000.0, delta_t_k=-1.0))
    # rho <= 0
    with pytest.raises(WaterFlowInputError):
        calc_water_flow(
            WaterFlowInput(heat_load_kw=1000.0, delta_t_k=10.0, rho_w=0.0)
        )
    # cp <= 0
    with pytest.raises(WaterFlowInputError):
        calc_water_flow(
            WaterFlowInput(heat_load_kw=1000.0, delta_t_k=10.0, cp_w=0.0)
        )


# 5. formula_ref
def test_water_flow_formula_ref() -> None:
    """formula_ref == "API_CTI_ATC-105_§3.2.4.3"（CTI ATC-105 §3.2.4.3 锁定）。"""
    inp = WaterFlowInput(heat_load_kw=1000.0, delta_t_k=10.0)
    r = calc_water_flow(inp)
    assert r.formula_ref == "API_CTI_ATC-105_§3.2.4.3"


# ============================================================================
# §3.2.4.4 补充水量
# ============================================================================


# 6. 基础工况（手算校核）
def test_water_balance_basic() -> None:
    """q_w=0.023885/ΔT=10/cycle=4/drift=0.001 → 手算 E/D/B/M。

    手算：
        E = 0.023885 × 10 × 4.187 / 2400 = 4.17e-4 m³/s
        D = 0.001 × 0.023885 = 2.39e-5 m³/s
        B = E/3 − D = 1.39e-4 − 2.39e-5 = 1.15e-4 m³/s
        M = E + D + B = 5.56e-4 m³/s
    验收（SPEC §3.2.4.7）：E / q_w ≈ 1.74% ΔT ≤ 5%。
    """
    inp = WaterBalanceInput(
        q_w_m3_s=0.023885, delta_t_k=10.0, cp_w=4.187, h_vap=2400.0,
        cycle_ratio=4.0, drift_fraction=0.001,
    )
    r = calc_water_balance(inp)
    assert isinstance(r, WaterBalanceResult)
    # 蒸发
    assert r.evaporation_m3_s == pytest.approx(4.17e-4, rel=1e-3)
    # 风吹
    assert r.drift_m3_s == pytest.approx(2.39e-5, rel=1e-3)
    # 排污
    assert r.blowdown_m3_s == pytest.approx(1.15e-4, rel=5e-3)
    # 总补充水
    assert r.makeup_m3_s == pytest.approx(5.56e-4, rel=5e-3)
    # SPEC §3.2.4.7 验收：E/q_w ≤ 5% ΔT
    assert r.evaporation_m3_s / inp.q_w_m3_s <= 0.05


# 7. cycle_ratio 缩放（cycle 越大 → B 越小）
def test_water_balance_cycle_ratio_scaling() -> None:
    """cycle=5 → B = E/4 − D < B(cycle=4)（cycle 越大排污越小）。"""
    inp_c4 = WaterBalanceInput(
        q_w_m3_s=0.023885, delta_t_k=10.0, cycle_ratio=4.0, drift_fraction=0.001,
    )
    inp_c5 = WaterBalanceInput(
        q_w_m3_s=0.023885, delta_t_k=10.0, cycle_ratio=5.0, drift_fraction=0.001,
    )
    r4 = calc_water_balance(inp_c4)
    r5 = calc_water_balance(inp_c5)
    # cycle 越大 → B 越小（分母 (cycle-1) 越大）
    assert r5.blowdown_m3_s < r4.blowdown_m3_s
    # M 也相应减小
    assert r5.makeup_m3_s < r4.makeup_m3_s


# 8. blowdown 工程下限 clamp（drift 极大 → B < 0 → clamp 0）
def test_water_balance_blowdown_clamp_to_zero() -> None:
    """drift=0.05（极大，远超典型 0.001~0.002）→ B = E/3 − D < 0
    → clamp 0（工程下限保留 0，不截断负值）。

    E = 0.023885 × 10 × 4.187 / 2400 = 4.17e-4
    D = 0.05 × 0.023885 = 1.19e-3 ≫ E/3 = 1.39e-4 → B < 0 → 0
    """
    inp = WaterBalanceInput(
        q_w_m3_s=0.023885, delta_t_k=10.0, cycle_ratio=4.0,
        drift_fraction=0.05,
    )
    r = calc_water_balance(inp)
    assert r.blowdown_m3_s == 0.0
    # M = E + D + 0
    assert r.makeup_m3_s == pytest.approx(
        r.evaporation_m3_s + r.drift_m3_s, rel=1e-12
    )


# 9. 输入校验
def test_water_balance_input_validation() -> None:
    """cycle<=1 / drift>0.1 / q_w<=0 → WaterBalanceInputError（422）。"""
    base = dict(q_w_m3_s=0.02, delta_t_k=10.0)
    # q_w <= 0
    with pytest.raises(WaterBalanceInputError):
        calc_water_balance(WaterBalanceInput(q_w_m3_s=0.0, delta_t_k=10.0))
    with pytest.raises(WaterBalanceInputError):
        calc_water_balance(WaterBalanceInput(q_w_m3_s=-1.0, delta_t_k=10.0))
    # delta_t < 0
    with pytest.raises(WaterBalanceInputError):
        calc_water_balance(
            WaterBalanceInput(q_w_m3_s=0.02, delta_t_k=-1.0)
        )
    # cp <= 0
    with pytest.raises(WaterBalanceInputError):
        calc_water_balance(WaterBalanceInput(**base, cp_w=0.0))
    # h_vap <= 0
    with pytest.raises(WaterBalanceInputError):
        calc_water_balance(WaterBalanceInput(**base, h_vap=0.0))
    # cycle_ratio <= 1
    with pytest.raises(WaterBalanceInputError):
        calc_water_balance(WaterBalanceInput(**base, cycle_ratio=1.0))
    with pytest.raises(WaterBalanceInputError):
        calc_water_balance(WaterBalanceInput(**base, cycle_ratio=0.5))
    # drift_fraction > 0.1
    with pytest.raises(WaterBalanceInputError):
        calc_water_balance(WaterBalanceInput(**base, drift_fraction=0.2))
    # drift_fraction < 0
    with pytest.raises(WaterBalanceInputError):
        calc_water_balance(WaterBalanceInput(**base, drift_fraction=-0.1))


# 10. formula_ref
def test_water_balance_formula_ref() -> None:
    """formula_ref == "API_CTI_ATC-105_§3.2.4.4"（CTI ATC-105 §3.2.4.4 锁定）。"""
    inp = WaterBalanceInput(q_w_m3_s=0.023885, delta_t_k=10.0)
    r = calc_water_balance(inp)
    assert r.formula_ref == "API_CTI_ATC-105_§3.2.4.4"


# 11. PcsError 继承校验
def test_water_flow_and_balance_input_errors_are_pcs_errors() -> None:
    """WaterFlowInputError + WaterBalanceInputError 是 PcsError 子类；status=422。"""
    # WaterFlow
    try:
        calc_water_flow(WaterFlowInput(heat_load_kw=0.0, delta_t_k=10.0))
    except WaterFlowInputError as err:
        assert isinstance(err, PcsError)
        assert err.status == 422
        assert err.code.startswith("WATER_FLOW_")
    # WaterBalance
    try:
        calc_water_balance(WaterBalanceInput(q_w_m3_s=0.0, delta_t_k=10.0))
    except WaterBalanceInputError as err:
        assert isinstance(err, PcsError)
        assert err.status == 422
        assert err.code.startswith("WATER_BALANCE_")
