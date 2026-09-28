"""P6-8 T4 — Lean Glycol Concentration 服务路径测试（OPEN-P6-6A-6 子任务 4）。

覆盖黄金 fixture `golden_c16_lean_glycol.json` 3 算例：

  * c16_lean_glycol_t380_sgr0                  — T=380°F + SGR=0 → 98.8 wt%
  * c16_lean_glycol_t400_sgr0_xls_e29_interp   — T=400°F + SGR=0 → 99.3 wt% (XLS E29 基准)
  * c16_lean_glycol_t400_sgr3                  — T=400°F + SGR=3 → 99.7 wt%

数据点完整性验证：
  * GPSA Fig 20-4 数据点 reference = 4 个

WARNING 字段透出验证：
  * T∈(380, 400) 区间 → `warnings` 含 `LEAN_GLYCOL_INTERPOLATION_PARTIAL` 字符串
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
    _calc_lean_glycol_concentration_wt_pct,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_c16_lean_glycol.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _load_cases() -> list[dict]:
    return _load_fixture()["cases"]


# ============================================================================
# 黄金 fixture 对账（3 算例）
# ============================================================================


@pytest.mark.parametrize(
    "case",
    _load_cases(),
    ids=lambda c: c["case_id"],
)
def test_lean_glycol_concentration(case: dict) -> None:
    """T4 Lean Glycol Concentration 黄金 fixture 对账（OPEN-P6-6A-6 子任务 4）。"""
    tol = case.get("tolerance_rel", _load_fixture()["tolerance_rel"])
    lean, _warnings = _calc_lean_glycol_concentration_wt_pct(
        case["reboiler_temperature_f"],
        case["stripping_gas_scf_gal"],
    )
    expected = case["expected"]["lean_glycol_concentration_wt_pct"]
    assert abs(lean - expected) / expected <= tol, (
        f"case {case['case_id']}: lean {lean} vs expected {expected} (rel tol {tol})"
    )


# ============================================================================
# 数据点完整性验证
# ============================================================================


def test_lean_glycol_data_points() -> None:
    """T4 GPSA Fig 20-4 4 数据点完整性。"""
    data = _load_fixture()
    assert len(data["data_points_reference"]) == 4


# ============================================================================
# WARNING 字段透出验证
# ============================================================================


def test_warning_partial_interpolation_in_band() -> None:
    """T∈(380, 400) 区间 → WARNING 必透出 `LEAN_GLYCOL_INTERPOLATION_PARTIAL`。"""
    _lean, warnings = _calc_lean_glycol_concentration_wt_pct(
        reboiler_temperature_f=390.0,
        stripping_gas_scf_gal=0.0,
    )
    assert any("LEAN_GLYCOL_INTERPOLATION_PARTIAL" in w for w in warnings), (
        f"T=390°F 区间应触发 WARNING，实际: {warnings}"
    )


def test_warning_absent_at_known_data_points() -> None:
    """T=380/T=400 段（SGR 在数据点）→ WARNING 不触发。"""
    for t_f, sgr in [(380.0, 0.0), (400.0, 0.0), (400.0, 3.0), (400.0, 6.0)]:
        _lean, warnings = _calc_lean_glycol_concentration_wt_pct(t_f, sgr)
        assert warnings == [], (
            f"T={t_f} SGR={sgr} 不应触发 WARNING，实际: {warnings}"
        )


def test_t400_sgr_clamp_below_first_point() -> None:
    """T=400°F + SGR<0 → 钳到首点 99.3 wt%。"""
    lean, _warnings = _calc_lean_glycol_concentration_wt_pct(400.0, -1.0)
    assert abs(lean - 99.3) < 1e-9


def test_t400_sgr_clamp_above_last_point() -> None:
    """T=400°F + SGR>6 → 钳到末点 99.9 wt%。"""
    lean, _warnings = _calc_lean_glycol_concentration_wt_pct(400.0, 10.0)
    assert abs(lean - 99.9) < 1e-9


def test_t_below_380_returns_first_point() -> None:
    """T<380°F → 钳到 380°F 数据点 98.8 wt%。"""
    lean, _warnings = _calc_lean_glycol_concentration_wt_pct(350.0, 0.0)
    assert abs(lean - 98.8) < 1e-9
