"""SUP-P5-PSV-002 V1.14 §4.4 apply_cdtp_correction 边界 + 错误码测试。

按 SPEC V1.14 §4.4：
- 输入校验：set_pressure > 0；superimposed_bp >= 0；CDTP > 0
- 错误码：PSV_INVALID_SET_PRESSURE / PSV_INVALID_SUPERIMPOSED_BP / PSV_CDTP_NON_POSITIVE

覆盖：
- happy path：200_000 Pa set - 50_000 Pa superimposed = 150_000 Pa
- 边界：superimposed=0 → 等于 set_pressure（PASS）
- 边界：CDTP = 0 临界点 → raise
- 错误：set_pressure = 0 / 负数
- 错误：superimposed 负数
- 错误：superimposed > set_pressure（CDTP 负数）
"""
from __future__ import annotations

import pytest

from app.services.exceptions import PcsError
from app.services.psv.cdtp import apply_cdtp_correction

# ============================================================================
# Happy path
# ============================================================================


def test_cdtp_basic_200k_set_minus_50k_superimposed():
    """set=200_000, superimposed=50_000 → CDTP=150_000 Pa。"""
    assert apply_cdtp_correction(200_000.0, 50_000.0) == 150_000.0


def test_cdtp_zero_superimposed_returns_set_pressure():
    """superimposed=0 → CDTP = set_pressure（SUPERIMPOSED 但无叠加 → 退化为零背压路径）。"""
    assert apply_cdtp_correction(180_000.0, 0.0) == 180_000.0


def test_cdtp_high_pressure_lpg_service():
    """高压 LPG 工况：set=2.5 MPa, superimposed=0.5 MPa → CDTP=2.0 MPa。"""
    assert apply_cdtp_correction(2_500_000.0, 500_000.0) == 2_000_000.0


# ============================================================================
# 错误码 — set_pressure 非正
# ============================================================================


def test_cdtp_set_pressure_zero_rejected():
    """set_pressure=0 → 422 PSV_INVALID_SET_PRESSURE。"""
    with pytest.raises(PcsError) as exc_info:
        apply_cdtp_correction(0.0, 0.0)
    assert exc_info.value.code == "PSV_INVALID_SET_PRESSURE"
    assert exc_info.value.status == 422
    assert exc_info.value.details["set_pressure_pa"] == 0.0


def test_cdtp_set_pressure_negative_rejected():
    """set_pressure=-1000 → 422 PSV_INVALID_SET_PRESSURE。"""
    with pytest.raises(PcsError) as exc_info:
        apply_cdtp_correction(-1_000.0, 0.0)
    assert exc_info.value.code == "PSV_INVALID_SET_PRESSURE"


# ============================================================================
# 错误码 — superimposed 非正
# ============================================================================


def test_cdtp_superimposed_negative_rejected():
    """superimposed=-1000 → 422 PSV_INVALID_SUPERIMPOSED_BP（前置拦截）。"""
    with pytest.raises(PcsError) as exc_info:
        apply_cdtp_correction(200_000.0, -1_000.0)
    assert exc_info.value.code == "PSV_INVALID_SUPERIMPOSED_BP"
    assert exc_info.value.details["superimposed_ba_pa"] == -1_000.0


# ============================================================================
# 错误码 — CDTP 非正（背压超过设定压力）
# ============================================================================


def test_cdtp_superimposed_equals_set_pressure_rejected():
    """superimposed == set_pressure → CDTP=0 → 422 PSV_CDTP_NON_POSITIVE。"""
    with pytest.raises(PcsError) as exc_info:
        apply_cdtp_correction(200_000.0, 200_000.0)
    assert exc_info.value.code == "PSV_CDTP_NON_POSITIVE"
    assert exc_info.value.details["cdtp_pa"] == 0.0


def test_cdtp_superimposed_exceeds_set_pressure_rejected():
    """superimposed > set_pressure → CDTP 负数 → 422 PSV_CDTP_NON_POSITIVE。"""
    with pytest.raises(PcsError) as exc_info:
        apply_cdtp_correction(100_000.0, 150_000.0)
    assert exc_info.value.code == "PSV_CDTP_NON_POSITIVE"
    assert exc_info.value.details["cdtp_pa"] == -50_000.0


def test_cdtp_validation_priority_set_pressure_first():
    """set_pressure=0 + superimposed 异常 → 优先报 PSV_INVALID_SET_PRESSURE。"""
    with pytest.raises(PcsError) as exc_info:
        apply_cdtp_correction(0.0, -100.0)
    # set_pressure 检查在前（避免掩盖更基础的错误）
    assert exc_info.value.code == "PSV_INVALID_SET_PRESSURE"


def test_cdtp_validation_priority_superimposed_second():
    """set_pressure 正常 + superimposed 负 → PSV_INVALID_SUPERIMPOSED_BP。"""
    with pytest.raises(PcsError) as exc_info:
        apply_cdtp_correction(200_000.0, -1.0)
    assert exc_info.value.code == "PSV_INVALID_SUPERIMPOSED_BP"


# ============================================================================
# OPEN-10-4 余项：cdtp 边界 + 复合错码 details 完整性
# ============================================================================


def test_cdtp_non_positive_details_contains_all_three_fields():
    """PSV_CDTP_NON_POSITIVE details 含 set/superimposed/cdtp 三字段（P5-OPEN-10 §4.4 契约）。"""
    with pytest.raises(PcsError) as exc_info:
        apply_cdtp_correction(100_000.0, 200_000.0)
    assert exc_info.value.code == "PSV_CDTP_NON_POSITIVE"
    details = exc_info.value.details
    assert details["set_pressure_pa"] == 100_000.0
    assert details["superimposed_ba_pa"] == 200_000.0
    assert details["cdtp_pa"] == -100_000.0


def test_cdtp_at_exactly_half_set_pressure():
    """边界：superimposed = set/2 → CDTP = set/2（精确分割；常用于 §6 决策 7 复算）。"""
    assert apply_cdtp_correction(200_000.0, 100_000.0) == 100_000.0