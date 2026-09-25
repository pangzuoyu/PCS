"""P6-2 Task 24 COOL_TOWER Merkel 测试（SPEC §3.2.4.1）。

按 SPEC §3.2.4.1 P6-CT-001 + CTI ATC-105 Chebyshev 4 点法：

- 6 单元测试（不依赖 DB；纯计算函数）：
  1. test_merkel_basic_air：手算校核 t1=40/t2=30/ia=80/l_g=1.0 →
     KaV/L ≈ 1.271（Magnus 累积误差 <2%；abs tol < 0.05）
  2. test_merkel_formula_ref：formula_ref == "API_CTI_ATC-105_§3.2.4.1"
  3. test_merkel_l_g_ratio_scaling：l_g=2.0 → kav_l 减半（线性反比）
  4. test_merkel_t1_le_t2_raises：T1 <= T2 → MerkelInputError
  5. test_merkel_negative_ia_raises：ia < 0 → MerkelInputError
  6. test_merkel_zero_l_g_raises：l_g_ratio <= 0 → MerkelInputError
  7. test_merkel_ia_too_high_raises：ia=200 kJ/kg（节点 i_w <= ia）→ 422

测试模式参照 ``tests/services/flare/test_flare_tip.py``（纯计算函数，
无 DB / Mock session）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.cool_tower import (  # noqa: E402
    MerkelInput,
    MerkelInputError,
    MerkelResult,
    calc_merkel_kav_l,
)
from app.services.exceptions import PcsError  # noqa: E402

# ============================================================================
# 1. 基础空气工况（手算校核）
# ============================================================================


def test_merkel_basic_air() -> None:
    """t1=40/t2=30/ia=80/l_g=1.0 → 手算校核 KaV/L ≈ 0.981。

    手算（Chebyshev 4 点法；T_water_i = t2 + (T_i + 1) × ΔT / 2）：
        ΔT = 10
        节点 1: T=-0.794498, T_water=30+0.2055×10=31.0275
            i_w ≈ 105.22 → 1/(105.22−80) ≈ 0.03965
        节点 2: T=-0.187985, T_water=30+0.8120×10/2=34.0601
            i_w ≈ 123.06 → 1/(123.06−80) ≈ 0.02322
        节点 3: T=+0.187985, T_water=30+1.1880×10/2=35.9399
            i_w ≈ 135.46 → 1/(135.46−80) ≈ 0.01803
        节点 4: T=+0.794498, T_water=30+1.7945×10/2=38.9725
            i_w ≈ 157.95 → 1/(157.95−80) ≈ 0.01283
        Σ = 0.09373
        KaV/L = (4.187/1.0) × (10/4) × 0.09373 ≈ 0.9811

    注：brief §3.2.4.1 节点 2~4 的 T_water 数值（32.030/32.970/34.488）
    与公式 T_water = t2 + (T+1) × ΔT / 2 不一致（应为 34.06/35.94/38.97）；
    本测试用公式推导值 0.9811（Magnus 0~50°C 误差 <2%）。
    """
    inp = MerkelInput(t1_c=40.0, t2_c=30.0, ia_kj_kg=80.0, l_g_ratio=1.0)
    r = calc_merkel_kav_l(inp)
    assert isinstance(r, MerkelResult)
    assert r.kav_l == pytest.approx(0.9811, abs=0.05)


# ============================================================================
# 2. formula_ref 溯源标记
# ============================================================================


def test_merkel_formula_ref() -> None:
    """formula_ref == "API_CTI_ATC-105_§3.2.4.1"（CTI ATC-105 §3.2.4.1 锁定）。"""
    inp = MerkelInput(t1_c=40.0, t2_c=30.0, ia_kj_kg=80.0)
    r = calc_merkel_kav_l(inp)
    assert r.formula_ref == "API_CTI_ATC-105_§3.2.4.1"


# ============================================================================
# 3. l_g_ratio 缩放（线性反比）
# ============================================================================


def test_merkel_l_g_ratio_scaling() -> None:
    """l_g_ratio 加倍 → kav_l 减半（KaV/L = (C_w / l_g) × ... → 线性反比）。"""
    inp_lg1 = MerkelInput(t1_c=40.0, t2_c=30.0, ia_kj_kg=80.0, l_g_ratio=1.0)
    inp_lg2 = MerkelInput(t1_c=40.0, t2_c=30.0, ia_kj_kg=80.0, l_g_ratio=2.0)
    r1 = calc_merkel_kav_l(inp_lg1)
    r2 = calc_merkel_kav_l(inp_lg2)
    # kav_l(l_g=2) = kav_l(l_g=1) / 2
    assert r2.kav_l == pytest.approx(r1.kav_l / 2.0, rel=1e-12)


# ============================================================================
# 4. 输入校验 — T1 <= T2
# ============================================================================


def test_merkel_t1_le_t2_raises() -> None:
    """T1 <= T2 → MerkelInputError（物理上必须 T1 > T2）。"""
    # T1 == T2
    inp_eq = MerkelInput(t1_c=30.0, t2_c=30.0, ia_kj_kg=80.0)
    with pytest.raises(MerkelInputError):
        calc_merkel_kav_l(inp_eq)
    # T1 < T2
    inp_lt = MerkelInput(t1_c=30.0, t2_c=40.0, ia_kj_kg=80.0)
    with pytest.raises(MerkelInputError):
        calc_merkel_kav_l(inp_lt)


# ============================================================================
# 5. 输入校验 — ia < 0
# ============================================================================


def test_merkel_negative_ia_raises() -> None:
    """ia < 0 → MerkelInputError（空气焓不能为负）。"""
    inp = MerkelInput(t1_c=40.0, t2_c=30.0, ia_kj_kg=-1.0)
    with pytest.raises(MerkelInputError):
        calc_merkel_kav_l(inp)


# ============================================================================
# 6. 输入校验 — l_g_ratio <= 0
# ============================================================================


def test_merkel_zero_l_g_raises() -> None:
    """l_g_ratio <= 0 → MerkelInputError（l_g 必须 > 0；不能为 0 或负）。"""
    inp_zero = MerkelInput(t1_c=40.0, t2_c=30.0, ia_kj_kg=80.0, l_g_ratio=0.0)
    with pytest.raises(MerkelInputError):
        calc_merkel_kav_l(inp_zero)
    inp_neg = MerkelInput(t1_c=40.0, t2_c=30.0, ia_kj_kg=80.0, l_g_ratio=-1.0)
    with pytest.raises(MerkelInputError):
        calc_merkel_kav_l(inp_neg)


# ============================================================================
# 7. 节点饱和 — ia 过高 → 节点 i_w(T) <= ia → 物理不合理
# ============================================================================


def test_merkel_ia_too_high_raises() -> None:
    """ia=200 kJ/kg（已接近 40°C 饱和 i_w ≈ 154）→ 至少 1 个节点
    i_w(T_water) <= ia → MerkelInputError（空气已饱和，无法继续冷却）。

    工程场景：上游给定空气工况极端湿润；拒绝计算并提示重新选型。
    """
    inp = MerkelInput(t1_c=40.0, t2_c=30.0, ia_kj_kg=200.0)
    with pytest.raises(MerkelInputError):
        calc_merkel_kav_l(inp)


# ============================================================================
# 8. PcsError 继承校验（与 flare/* InputError 同源 PcsError）
# ============================================================================


def test_merkel_input_error_is_pcs_error() -> None:
    """MerkelInputError 是 PcsError 子类；status=422；code 以 MERKEL_ 开头。

    验证 service 层异常模式（与 flare/* InputError 一致），Task 25 endpoint
    注册可复用 _to_http(err) envelope。
    """
    inp = MerkelInput(t1_c=40.0, t2_c=40.0, ia_kj_kg=80.0)
    try:
        calc_merkel_kav_l(inp)
    except MerkelInputError as err:
        assert isinstance(err, PcsError)
        assert err.status == 422
        assert err.code.startswith("MERKEL_")
