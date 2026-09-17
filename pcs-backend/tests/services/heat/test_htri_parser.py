"""HTRI parser + version detection 测试（P5-4-1 / Task 19）。

覆盖 PCS-PLAN-P5-DEVICE-EQUIPMENT.md Task 19 step 3：
- 3 例（基本 / 管壳 / 空冷）
- 5 例版本探测（白名单 v1/v2 + 不支持 v99 + 0/空文件）
- 解析失败异常
- ≤10s 性能
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.services.heat.htri_parser import (
    HTRI_VERSION_SUPPORTED,
    HtriParsedData,
    HtriParseError,
    HtriVersionUnsupportedError,
    detect_version,
    parse_htri,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> Path:
    return FIXTURES / name


# ===== 解析：3 例（基本 / 管壳 / 空冷） =====


def test_parse_xist_v6_basic_hand_calc():
    """Plan 手算样本：Q=1MW, U=500 W/m²K, A=10.0 m²。"""
    data = parse_htri(_fixture("htri_xist_v6_basic.txt"))
    assert isinstance(data, HtriParsedData)
    assert data.version == "Xist_v6"
    assert data.case_name == "HEAT-E-201 Basic Hand-Parse"
    assert data.heat_duty_w == pytest.approx(1_000_000.0, rel=1e-3)
    assert data.overall_u_w_m2k == pytest.approx(500.0, rel=1e-3)
    assert data.area_required_m2 == pytest.approx(10.0, rel=1e-3)
    assert data.shell_dia_m == pytest.approx(0.600, rel=1e-3)
    assert data.tube_length_m == pytest.approx(3.000, rel=1e-3)
    assert data.tube_count == 150
    assert data.baffle_spacing_m == pytest.approx(0.400, rel=1e-3)
    # 物性
    assert data.hot_inlet_t_k == pytest.approx(423.15, rel=1e-3)
    assert data.hot_outlet_t_k == pytest.approx(383.15, rel=1e-3)
    assert data.cold_inlet_t_k == pytest.approx(308.15, rel=1e-3)
    assert data.cold_outlet_t_k == pytest.approx(348.15, rel=1e-3)
    assert data.hot_mass_flow_kgs == pytest.approx(1.389, rel=1e-3)
    assert data.cold_mass_flow_kgs == pytest.approx(1.667, rel=1e-3)


def test_parse_xchanger_v8_shell_tube():
    """管壳式（Xchanger_Suite_v8 + BEM 固定管板）。"""
    data = parse_htri(_fixture("htri_xchanger_v8_shell_tube.txt"))
    assert data.version == "Xchanger_Suite_v8"
    assert data.case_name == "HEAT-E-301 Shell and Tube BEM"
    assert data.heat_duty_w == pytest.approx(850_000.0, rel=1e-3)
    assert data.overall_u_w_m2k == pytest.approx(650.0, rel=1e-3)
    assert data.area_required_m2 == pytest.approx(8.50, rel=1e-3)
    assert data.tube_count == 198


def test_parse_xist_v6_air_cooled():
    """空冷器（ACHE — fan_count / air_inlet_t / bundle_area）。"""
    data = parse_htri(_fixture("htri_xist_v6_air_cooled.txt"))
    assert data.version == "Xist_v6"
    assert data.case_name == "HEAT-A-101 Air Cooled ACHE"
    assert data.heat_duty_w == pytest.approx(450_000.0, rel=1e-3)
    assert data.overall_u_w_m2k == pytest.approx(45.0, rel=1e-3)
    assert data.area_required_m2 == pytest.approx(12.0, rel=1e-3)
    assert data.air_inlet_t_k == pytest.approx(308.15, rel=1e-3)
    assert data.bundle_area_m2 == pytest.approx(12.5, rel=1e-3)
    assert data.fan_count == 2
    # ACHE 没有 cold side
    assert data.cold_inlet_t_k is None


# ===== 版本探测：5 例 =====


def test_detect_version_xist_v6():
    assert detect_version(_fixture("htri_xist_v6_basic.txt")) == "Xist_v6"


def test_detect_version_xchanger_v8():
    assert detect_version(_fixture("htri_xchanger_v8_shell_tube.txt")) == "Xchanger_Suite_v8"


def test_detect_version_xist_v6_air_cooled():
    assert detect_version(_fixture("htri_xist_v6_air_cooled.txt")) == "Xist_v6"


def test_detect_version_unsupported_v99_raises():
    """不支持版本 → HtriVersionUnsupportedError 含升级指引 URL。"""
    with pytest.raises(HtriVersionUnsupportedError) as exc_info:
        parse_htri(_fixture("htri_unsupported_v99.txt"))
    assert exc_info.value.detected_version == "Xist_v99"
    assert exc_info.value.versions_supported == HTRI_VERSION_SUPPORTED
    assert exc_info.value.upgrade_url  # 非空 URL


def test_detect_version_empty_file_returns_none():
    """空文件 → detect_version 返回 None（无法判别）。"""
    assert detect_version(_fixture("htri_empty.txt")) is None


# ===== 解析失败 =====


def test_parse_empty_file_raises():
    with pytest.raises(HtriParseError):
        parse_htri(_fixture("htri_empty.txt"))


def test_parse_corrupted_file_raises():
    with pytest.raises(HtriParseError):
        parse_htri(_fixture("htri_corrupted.txt"))


# ===== 白名单常量 =====


def test_supported_versions_list():
    """白名单默认 ['Xist_v6','Xchanger_Suite_v8']，可扩展。"""
    assert "Xist_v6" in HTRI_VERSION_SUPPORTED
    assert "Xchanger_Suite_v8" in HTRI_VERSION_SUPPORTED


# ===== 性能 =====


def test_parse_under_10s():
    """≤10s 性能（plan step 3 要求）。"""
    start = time.perf_counter()
    for _ in range(5):
        parse_htri(_fixture("htri_xist_v6_basic.txt"))
    elapsed = time.perf_counter() - start
    assert elapsed < 10.0, f"parse_htri 5 次耗时 {elapsed:.2f}s 超过 10s 上限"