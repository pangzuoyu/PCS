"""P6-6A-6 v5.1 — Behr coefficients JSON sidecar load tests (M-4 dedupe to 4 tests).

Step 12 brief 要求: 4 tests 集中 8 spot check 残差验证 + load 行为验证。

覆盖:
  1. test_load_behr_coefficients_success — JSON 主系数非空 → 返回主系数
  2. test_load_behr_coefficients_fallback_when_missing — JSON 缺失 → fallback 系数 WARNING
  3. test_load_behr_coefficients_runtime_error_on_schema_invalid — JSON 主+fallback 均缺 → RuntimeError
  4. test_load_behr_coefficients_8_spot_checks_residual_within_5pct — 8 GPSA spot checks 残差 ≤ 5%

测试策略:
  - 测试 1/2/3 直接调用 _load_behr_coefficients() (模块私有) + 临时修改 JSON
  - 测试 4 使用 Day-0 Gate 实际拟合系数 + 公式再计算残差
  - 残差容差 ≤ 5% per Day-0 Gate max_rel_err=4.866% (Step 2 Day-0 Gate pass)
"""
from __future__ import annotations

import json
import math
import sys
from importlib import resources
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# P6-6A-6 v5.1 Ruling 9: 直接导入私有 _load_behr_coefficients (测试目的)
from app.services.psychro.glycol_dehydration_service import (  # noqa: E402
    _load_behr_coefficients,
    _BEHR_COEFFS,
)


# ---------------------------------------------------------------------------
# 8 GPSA Fig 20-2 spot checks (4T × 2P 矩阵抽样, 与 Day-0 Gate script 一致)
# ---------------------------------------------------------------------------

SPOTS = [
    (60, 1000, 16), (80, 1000, 31), (100, 1000, 50), (120, 1000, 70),
    (140, 1000, 95), (160, 1000, 130),
    (120, 500, 147), (120, 1500, 47),
]


# ---------------------------------------------------------------------------
# 1) JSON 主系数非空 → 返回主系数
# ---------------------------------------------------------------------------


def test_load_behr_coefficients_success():
    """behr_coefficients.json 主 log10_coefficients 数值完整 → _load 返回该系数。"""
    # 验证当前模块加载的 _BEHR_COEFFS 与 JSON 一致
    p = resources.files("app.services.psychro.data").joinpath(
        "behr_coefficients.json"
    )
    data = json.loads(p.read_text())

    expected = data["log10_coefficients"]
    assert expected is not None, "JSON log10_coefficients must not be null"
    assert all(
        isinstance(expected[k], (int, float))
        for k in ("A0", "A1", "A2", "A3")
    ), "JSON log10_coefficients A0-A3 must be numeric"

    # _load_behr_coefficients 直接调用结果
    coeffs = _load_behr_coefficients()
    for k in ("A0", "A1", "A2", "A3"):
        assert coeffs[k] == pytest.approx(expected[k], rel=1e-12)

    # 模块级 _BEHR_COEFFS 与 JSON 一致
    for k in ("A0", "A1", "A2", "A3"):
        assert _BEHR_COEFFS[k] == pytest.approx(expected[k], rel=1e-12)


# ---------------------------------------------------------------------------
# 2) JSON 缺失 → fallback 系数 (WARNING 不 crash)
# ---------------------------------------------------------------------------


def test_load_behr_coefficients_fallback_when_missing(monkeypatch):
    """JSON 文件 not found → _load 返回 _BEHR_FALLBACK_COEFS + WARNING log。

    v5.1 B-2 落实: importlib.resources 文件不存在 → fallback 系数,
    不 crash (区别 v3/v4 早期版本)。
    """
    import app.services.psychro.glycol_dehydration_service as _svc

    def _raise_fnf(pkg):
        raise FileNotFoundError("simulated missing JSON sidecar")

    monkeypatch.setattr(_svc.resources, "files", _raise_fnf)

    coeffs = _load_behr_coefficients()
    # fallback 系数 = _BEHR_FALLBACK_COEFS (4 字段 A0/A1/A2/A3)
    assert coeffs == {"A0": 1.0, "A1": 0.020, "A2": 0.0, "A3": -1.5}


# ---------------------------------------------------------------------------
# 3) JSON schema 无效 → RuntimeError
# ---------------------------------------------------------------------------


def test_load_behr_coefficients_runtime_error_on_schema_invalid(
    monkeypatch, tmp_path,
):
    """JSON 存在但 log10_coefficients 与 fallback_coefficients 均无 A0-A3 数值 → RuntimeError。

    v5.1 B-2: 启动期 fail-fast, 防止 silent wrong coefficients 进入生产。
    """
    from pathlib import Path

    bad_json = tmp_path / "behr_coefficients.json"
    bad_json.write_text(
        json.dumps({
            "form": "INVALID",
            "log10_coefficients": None,
            "fallback_coefficients": None,
        })
    )

    # 改 service 模块的 _load_behr_coefficients 函数内部使用 importlib.resources
    # 为更简洁：monkeypatch service module 的 resources import path
    import app.services.psychro.glycol_dehydration_service as _svc

    class _FakeAnchor:
        def joinpath(self, _name):
            return Path(str(bad_json))

    def _patched_files(pkg):
        if pkg == "app.services.psychro.data":
            return _FakeAnchor()
        raise AssertionError(f"unexpected pkg {pkg!r}")

    monkeypatch.setattr(_svc.resources, "files", _patched_files)

    with pytest.raises(RuntimeError, match="schema 无效"):
        _load_behr_coefficients()


# ---------------------------------------------------------------------------
# 4) 8 spot checks 残差 ≤ 5% (Day-0 Gate 验证)
# ---------------------------------------------------------------------------


def test_load_behr_coefficients_8_spot_checks_residual_within_5pct():
    """8 GPSA Fig 20-2 spot checks vs 主 log10_coefficients 拟合值 → max rel_err < 5%。

    P6-6A-6 v5.1 Day-0 Gate 选定形式 A (4-param log10 二次), 实际 max_rel_err=4.866%。
    本测试作为 Day-1 Gate 验证: 重跑 spot check, 残差一致。
    """
    coeffs = _load_behr_coefficients()
    a0, a1, a2, a3 = coeffs["A0"], coeffs["A1"], coeffs["A2"], coeffs["A3"]

    max_rel_err = 0.0
    residuals = []
    for t_f, p_psia, w_actual in SPOTS:
        log_w = a0 + a1 * t_f + a2 * t_f ** 2 + a3 * math.log10(p_psia)
        w_pred = 10 ** log_w
        rel_err = abs(w_pred - w_actual) / w_actual
        residuals.append({
            "T_F": t_f, "P_psia": p_psia,
            "W_actual": w_actual, "W_pred": w_pred,
            "rel_err": rel_err,
        })
        max_rel_err = max(max_rel_err, rel_err)

    # Day-0 Gate max_rel_err=4.866% ≤ 5% (Step 2 Gate pass)
    assert max_rel_err < 0.05, (
        f"max_rel_err={max_rel_err:.4%} 超 5% Day-0 Gate 阈值；残差表: {residuals}"
    )

    # 与 JSON calibration_max_rel_err 一致 (Day-1 Gate)
    p = resources.files("app.services.psychro.data").joinpath(
        "behr_coefficients.json"
    )
    data = json.loads(p.read_text())
    json_max = data.get("calibration_max_rel_err")
    assert json_max is not None
    assert max_rel_err == pytest.approx(json_max, abs=1e-4), (
        f"Day-1 Gate 不一致：脚本 max_rel_err={max_rel_err:.6f} "
        f"≠ JSON calibration_max_rel_err={json_max:.6f}"
    )
