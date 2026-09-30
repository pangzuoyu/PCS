"""P6-8 T9r — Behr grid 加载测试 (OPEN-P6-6A-9.5 代码侧闭环)。

工艺室 2026-09-29 第三批交付 v3 grid (查表 + 双线性插值) 替代经验公式拟合
(4-param / Katz 5-param / Behr 3-param 均失败)。

覆盖:
  1. test_load_behr_grids_success — JSON grid 段 → 返回 BehrGrid general+high_acid
  2. test_load_behr_grids_runtime_error_when_missing — JSON 缺失 → RuntimeError
  3. test_load_behr_grids_runtime_error_on_schema_invalid — JSON 缺 grid 段 → RuntimeError
  4. test_load_behr_grids_spot_check_120F_1000psia — v3 grid 标定点
     general=93.0 / high_acid=93.5 (T=120°F / P=1000 psia, grid 节点直接读出)

测试策略:
  - 直接调用 _load_behr_grids() (模块私有) + 临时修改 JSON
  - spot check 验证 grid 标定点与 v3 calibration 表一致
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# P6-8 T9r — 直接导入私有 _load_behr_grids / _BEHR_GRIDS (测试目的)
from app.services.psychro._glycol_dehydration.behr import (  # noqa: E402
    _BEHR_GRIDS,
    BehrGrid,
    _bilinear_interp_behr,
    _load_behr_grids,
)

# ---------------------------------------------------------------------------
# 1) JSON grid 段 → 返回 BehrGrid general+high_acid
# ---------------------------------------------------------------------------


def test_load_behr_grids_success():
    """pcs-backend/data/behr_coefficients.json v3 grid 段 → general+high_acid 双 baseline。

    验证:
      - _BEHR_GRIDS 包含 general + high_acid
      - BehrGrid dataclass 字段 (t_grid / p_grid / w_grid) 完整
      - 模块级 _BEHR_GRIDS 与 _load_behr_grids() 直接调用结果一致
    """
    grids = _load_behr_grids()

    assert set(grids.keys()) == {"general", "high_acid"}
    for name in ("general", "high_acid"):
        g = grids[name]
        assert isinstance(g, BehrGrid)
        assert g.name == name
        assert len(g.t_grid) == 7  # T ∈ [60, 80, 100, 120, 140, 160, 200]
        assert len(g.p_grid) == 4  # P ∈ [500, 1000, 1500, 2000]
        assert len(g.w_grid) == len(g.t_grid)
        assert all(len(row) == len(g.p_grid) for row in g.w_grid)

    # 模块级 _BEHR_GRIDS 与 _load_behr_grids() 一致
    assert set(_BEHR_GRIDS.keys()) == set(grids.keys())
    for name, g in grids.items():
        assert _BEHR_GRIDS[name].t_grid == g.t_grid
        assert _BEHR_GRIDS[name].p_grid == g.p_grid
        assert _BEHR_GRIDS[name].w_grid == g.w_grid


# ---------------------------------------------------------------------------
# 2) JSON 缺失 → RuntimeError (P6-8 T9r fail-fast)
# ---------------------------------------------------------------------------


def test_load_behr_grids_runtime_error_when_missing(monkeypatch, tmp_path):
    """JSON 文件缺失 → RuntimeError (启动期 fail-fast, 防 silent wrong coefficients)。"""
    # 把 _BEHR_GRID_PATH 重定向到不存在的路径
    import app.services.psychro._glycol_dehydration.behr as _svc

    missing_path = tmp_path / "behr_coefficients_missing.json"
    monkeypatch.setattr(_svc, "_BEHR_GRID_PATH", missing_path)

    with pytest.raises(RuntimeError, match="Behr grid JSON 缺失"):
        _load_behr_grids()


# ---------------------------------------------------------------------------
# 3) JSON schema 无效 → RuntimeError
# ---------------------------------------------------------------------------


def test_load_behr_grids_runtime_error_on_schema_invalid(monkeypatch, tmp_path):
    """JSON 存在但缺 'grid' dict 段 → RuntimeError (防 silent wrong coefficients)。"""
    import app.services.psychro._glycol_dehydration.behr as _svc

    bad_json = tmp_path / "behr_coefficients_bad.json"
    bad_json.write_text(
        json.dumps({
            "_meta": {"open_item": "INVALID"},
            # 缺 'grid' 段
        })
    )
    monkeypatch.setattr(_svc, "_BEHR_GRID_PATH", bad_json)

    with pytest.raises(RuntimeError, match="schema 无效"):
        _load_behr_grids()


def test_load_behr_grids_runtime_error_on_missing_baseline(monkeypatch, tmp_path):
    """JSON grid 段缺 baseline (general/high_acid) → RuntimeError。"""
    import app.services.psychro._glycol_dehydration.behr as _svc

    bad_json = tmp_path / "behr_coefficients_partial.json"
    bad_json.write_text(
        json.dumps({
            "grid": {
                "general": {  # 仅 general, 缺 high_acid
                    "t_grid_f": [60, 200],
                    "p_grid_psia": [500, 2000],
                    "w_grid_lb_per_mmscf": [[1.0, 0.5], [10.0, 5.0]],
                },
            },
        })
    )
    monkeypatch.setattr(_svc, "_BEHR_GRID_PATH", bad_json)

    with pytest.raises(RuntimeError, match="grid.high_acid"):
        _load_behr_grids()


# ---------------------------------------------------------------------------
# 4) v3 grid 标定点 (T=120°F / P=1000 psia) — 工艺室 2026-09-29 标定
# ---------------------------------------------------------------------------


def test_load_behr_grids_spot_check_120F_1000psia():
    """v3 grid 直接节点验证: general(120°F/1000 psia)=93.0; high_acid=93.5。

    工艺室 2026-09-29 第三批交付 v3 标定值；OPEN-P6-6A-9.5 闭环核心证据。
    """
    # grid 直接节点 (T=120°F, P=1000 psia) — w_grid[3][1]
    assert _BEHR_GRIDS["general"].w_grid[3][1] == 93.0
    assert _BEHR_GRIDS["high_acid"].w_grid[3][1] == 93.5


def test_bilinear_interp_grid_node_exact_match():
    """双线性插值在 grid 节点上精确还原 (无插值误差)。"""
    # T=120°F, P=1000 psia — 通用节点验证
    w_general, extrap = _bilinear_interp_behr(
        _BEHR_GRIDS["general"], 120.0, 1000.0,
    )
    w_high_acid, extrap_ha = _bilinear_interp_behr(
        _BEHR_GRIDS["high_acid"], 120.0, 1000.0,
    )
    assert extrap is False  # 节点查询无 clamp
    assert extrap_ha is False
    assert w_general == pytest.approx(93.0, rel=1e-12)
    assert w_high_acid == pytest.approx(93.5, rel=1e-12)


def test_bilinear_interp_out_of_domain_emits_extrap_flag():
    """越界 T/P → clamp 到最近节点 + extrap_used=True。

    注: extrap 仅在 helper 层返回, _calc_behr_water_content_lb_per_mmscf 把它
    转成 WARNING "BEHR_GRID_EXTRAPOLATED: ..." 透出。
    """
    # T=300°F (网格上限 200°F) → clamp 到 200°F
    w, extrap = _bilinear_interp_behr(
        _BEHR_GRIDS["general"], 300.0, 1000.0,
    )
    assert extrap is True
    # P=1000 psia 在 general grid T=200°F 行 → w_grid[6][1] = 320.0
    assert w == pytest.approx(320.0, rel=1e-12)
