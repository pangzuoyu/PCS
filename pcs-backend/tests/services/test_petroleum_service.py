# pcs-backend/tests/services/test_petroleum_service.py
"""Riazi-Daubert 估算 + 虚拟组分切割测试（Task 1.9.3 / ADR-0019 / P2 §3.2.4）。

基准：n-癸烷 Tb=174.1°C SG=0.73，文献真值 MW=142.3 / Tc=617.7K / Pc=2.11MPa / ω=0.4923。
广义关联式对纯组分典型偏差 5-10%，断言带宽按此放宽。
"""
import pytest

from app.services.exceptions import PcsError
from app.services.petroleum_service import PetroleumService


def test_estimate_n_decane():
    r = PetroleumService.estimate(174.1, 0.73)
    assert 140 <= r["mw"] <= 165          # 计算值 ≈152
    assert 600 <= r["tc_k"] <= 630        # ≈613.5
    assert 1.7 <= r["pc_mpa"] <= 2.3      # ≈1.98
    assert 0.3 <= r["omega"] <= 0.7       # ≈0.494
    assert r["tb_k"] == pytest.approx(447.25, abs=0.1)
    assert 0.3 <= r["nu_20c_cst"] <= 3.0  # Twu(1985) 真值 ≈0.92 cSt（馏分式放宽带宽）


def test_estimate_input_validation():
    with pytest.raises(PcsError):
        PetroleumService.estimate(174.1, 1.5)   # SG 越界
    with pytest.raises(PcsError):
        PetroleumService.estimate(1000.0, 0.8)  # Tb 越界


def test_vapor_pressure_positive_and_below_pc():
    p = PetroleumService.vapor_pressure(174.1, 0.73, 100.0)
    assert 0.0 < p < 1.7  # 常识：癸烷 100°C 饱和蒸气压 ~0.02 MPa 量级，且远低于 Pc


def test_cut_default_25c():
    cuts = PetroleumService.cut_pseudo_components(150.0, 260.0)
    widths = {round(c["tb_end_c"] - c["tb_start_c"], 6) for c in cuts[:-1]}
    assert widths == {25.0}          # 中间段恒 25
    assert len(cuts) >= 4            # 110/25 → 至少 5 段（ceil）
    assert cuts[0]["tb_start_c"] == 150.0 and cuts[-1]["tb_end_c"] == 260.0
    assert cuts[-1]["tb_end_c"] - cuts[-1]["tb_start_c"] <= 25.0 + 1e-9  # 末段吸收余数 ≤25
    assert all("mw" in c and "tc_k" in c for c in cuts)  # 每段自带估算物性


def test_cut_custom_width_and_validation():
    cuts = PetroleumService.cut_pseudo_components(100.0, 140.0, cut_width_c=20.0)
    assert len(cuts) == 2
    with pytest.raises(PcsError):
        PetroleumService.cut_pseudo_components(200.0, 100.0)  # start >= end
    with pytest.raises(PcsError):
        PetroleumService.cut_pseudo_components(100.0, 200.0, cut_width_c=0)
