"""P6-9-PICKUP-2 T2 — Stripping Gas Rate 公式反转 patch 后回归测试。

覆盖：
  * 黄金 fixture 3 算例（GPSA §20.4 Eq.20-5 + Antoine v5 plan A=15.30/B=8500）
  * XLS PR-018 E32 工况对账（T_reb=400°F, P=1000 psia, X=0.9938）

P6-9-PICKUP-2 F2 patch (2026-10-31):
  修复前公式 `k×(P_total/P_sat)×X/(1−X)` 比例项 + X-fraction 项双双反向，
  残差 4e12% vs XLS。修复后形式与 GPSA §20.4 Eq.20-5 一致：
  `SGR = k_strip × (P_sat,TEG/P_total) × (1-X)/X`（OPEN-P6-9-PICKUP-2-1 复盘）。

XLS PR-018 E32 基准 SGR ≈ 0.4220 scf/gal（工艺室 2026-10-31 确认基准工况，
GPSA §20.4 Eq.20-5 + Antoine v5 plan）；real-value tolerance check rel ≤ 5%。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.psychro.glycol_dehydration_service import (  # noqa: E402
    ReboilerStrippingInput,
    _calc_stripping_gas_rate_scf_gal_teg,
    calc_reboiler_stripping,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "golden_c16_stripping_gas_rate.json"
)


def _load_cases() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


# ============================================================================
# 黄金 fixture 对账（3 算例）
# ============================================================================


@pytest.mark.parametrize(
    "case",
    _load_cases(),
    ids=lambda c: c["case_id"],
)
def test_stripping_gas_rate(case: dict) -> None:
    """T2 Stripping Gas Rate 黄金 fixture 对账（P6-9-PICKUP-2 F2 patch 后）。

    expected.sgr_scf_gal_teg 是按 GPSA §20.4 Eq.20-5 修复后公式
    `k_strip × (P_sat/P_total) × (1-X)/X` 重算的实际值（task-2-brief.md Step 4）。
    P_sat_te_mmhg 仅依赖 T_reb + Antoine 系数（公式未动，应不变）。

    P6-9-PICKUP-2 patch 说明：删除 P6-8 PICKUP 引入的公式自洽检查
    (`sgr == sgr_recomputed` 1e-9 断言)，改为直接对账 fixture 期望值。
    """
    inp = ReboilerStrippingInput(
        water_removal_rate_lb_hr=2377.0,
        teg_circulation_rate_gal_lb=3.0,
        teg_density_lb_gal=9.32,
        reboiler_temperature_f=case["reboiler_temperature_f"],
        contactor_temperature_f=case["contactor_temperature_f"],
        contactor_pressure_psia=case["contactor_pressure_psia"],
        lean_glycol_concentration_wt_pct=case["lean_glycol_concentration_wt_pct"],
        reflux_ratio=0.25,
    )
    result = calc_reboiler_stripping(inp)
    tol = case["tolerance_rel"]

    sgr = result.sgr_scf_gal_teg
    p_sat = result.p_sat_te_mmhg

    expected_p_sat = case["expected"]["p_sat_te_mmhg"]
    expected_sgr = case["expected"]["sgr_scf_gal_teg"]

    # P_sat_te_mmhg 比对 fixture 期望（Antoine 系数不变，应一致）
    if expected_p_sat > 0:
        assert abs(p_sat - expected_p_sat) / expected_p_sat <= tol, (
            f"case {case['case_id']}: P_sat_te {p_sat:.6e} mmHg vs "
            f"expected {expected_p_sat:.6e} mmHg (rel tol {tol})"
        )

    # SGR 比对 fixture 期望（GPSA Eq.20-5 修复后实际值）
    if expected_sgr > 0:
        assert abs(sgr - expected_sgr) / expected_sgr <= tol, (
            f"case {case['case_id']}: SGR {sgr:.6e} scf/gal vs "
            f"expected {expected_sgr:.6e} scf/gal (rel tol {tol})"
        )


# ============================================================================
# XLS PR-018 E32 工况对账（OPEN-P6-6A-6 子任务 2, P6-9-PICKUP-2 F2 patch 验证）
# ============================================================================


def test_stripping_gas_xls_e32_reconciliation() -> None:
    """T2 XLS PR-018 E32=0.4220 scf/gal 对账（P6-9-PICKUP-2 F2 patch）。

    XLS PR-018 E32 工况：T_reb=400°F, P=1000 psia, X=0.9938
    工艺室 2026-10-31 确认基准 SGR ≈ 0.4220 scf/gal
    （GPSA §20.4 Eq.20-5 + Antoine v5 plan A=15.30/B=8500）。
    """
    _, sgr = _calc_stripping_gas_rate_scf_gal_teg(
        reboiler_temperature_f=400.0,
        contactor_temperature_f=120.0,
        contactor_pressure_psia=1000.0,
        lean_glycol_concentration_wt_pct=0.9938,  # 质量分率 (0..1)
    )
    xls_target = 0.4220
    assert sgr == pytest.approx(xls_target, rel=5e-2), (
        f"SGR {sgr:.6e} scf/gal vs XLS E32 {xls_target} scf/gal; "
        f"residual {abs(sgr - xls_target) / xls_target * 100:.1f}%"
    )