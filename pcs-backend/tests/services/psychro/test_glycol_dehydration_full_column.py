import json
import math
from pathlib import Path

import pytest

from app.services.psychro.glycol_dehydration_service import (
    _calc_full_column_diameter_in,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_c16_full_column_diameter.json"


def _load_fixture():
    return json.loads(FIXTURE_PATH.read_text())


def _load_cases():
    return _load_fixture()["cases"]


@pytest.mark.parametrize(
    "case",
    _load_cases(),
    ids=lambda c: c["case_id"],
)
def test_full_column_diameter_k_7_1121(case):
    """T3 Full Column Diameter vs XLS E40 (K=7.1121 6 工况标定, OPEN-P6-6A-6 子任务 3)"""
    tolerance_rel = _load_fixture()["tolerance_rel"]
    D_calc = _calc_full_column_diameter_in(case["Q_mmscfd"])
    D_xls = case["xls_e40_in"]
    assert abs(D_calc - D_xls) / D_xls <= tolerance_rel, (
        f"case {case['case_id']}: D_calc {D_calc} vs XLS {D_xls}"
    )


def test_full_column_k_statistics():
    """T3 K=7.1121 CV=1.05% 验证（ADR-0045 Rev B）"""
    D_values = [
        _calc_full_column_diameter_in(c["Q_mmscfd"]) for c in _load_cases()
    ]
    Q_values = [c["Q_mmscfd"] for c in _load_cases()]
    K_values = [D / math.sqrt(Q) for D, Q in zip(D_values, Q_values, strict=True)]
    mean_K = sum(K_values) / len(K_values)
    cv_pct = abs((max(K_values) - min(K_values)) / mean_K) * 100
    assert cv_pct < 5.0, f"K CV {cv_pct:.2f}% > 5% 容差（ADR-0045 Rev B）"