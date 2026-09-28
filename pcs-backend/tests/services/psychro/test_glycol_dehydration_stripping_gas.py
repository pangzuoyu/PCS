"""P6-8 T2 — Stripping Gas Rate 黄金 fixture 对账测试（OPEN-P6-6A-6 子任务 2）。

覆盖黄金 fixture `golden_c16_stripping_gas_rate.json` 3 算例：

  * c16_sgr_xls_e32_default      — XLS E32 基准 (T_reb=400°F, X=0.9938)
  * c16_sgr_t380_lower_reb       — 380°F 低温再沸器 (X=0.99)
  * c16_sgr_high_lean_300_clamped — 99.9 wt% 贫 TEG（T_reb=250°F 因服务 ge=300 钳制为 300°F）

WARNING：
  * 字面公式 `k_strip × (P_total_psi / P_sat_mmHg) × X/(1−X)` 存在单位混算
    （详见 task-1-report.md C-3 与 fixture _meta.formula_note）。
  * expected.sgr_scf_gal_teg 是服务字面输出（≈1e8..1e11）；XLS E32=0.4220
    工艺室 2026-11-15 对账后回归（P6-8 PICKUP 修复）。
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
    """T2 Stripping Gas Rate 黄金 fixture 对账（OPEN-P6-6A-6 子任务 2）。

    expected.sgr_scf_gal_teg 是服务字面公式输出（task-1-report.md C-3）：
    验证服务公式在不同 T / X 条件下输出一致性（不验证 XLS 工程对账，
    工程对账待工艺室 2026-11-15 Antoine 系数 + 公式修复后回归）。
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

    expected_sgr = case["expected"]["sgr_scf_gal_teg"]
    expected_p_sat = case["expected"]["p_sat_te_mmhg"]

    if expected_sgr > 0:
        assert abs(sgr - expected_sgr) / expected_sgr <= tol, (
            f"case {case['case_id']}: SGR {sgr:.6e} vs expected {expected_sgr:.6e} "
            f"(rel tol {tol})"
        )

    if expected_p_sat > 0:
        assert abs(p_sat - expected_p_sat) / expected_p_sat <= tol, (
            f"case {case['case_id']}: P_sat_te {p_sat:.6e} mmHg vs "
            f"expected {expected_p_sat:.6e} mmHg (rel tol {tol})"
        )