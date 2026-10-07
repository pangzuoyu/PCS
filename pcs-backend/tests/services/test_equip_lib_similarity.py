"""设备库相似度计算（UI-SPEC §7.16；P7 S3-2）。

UI-SPEC 原文：「相似度 ≥90% 推荐，80~90% 需校核，<80% 仅展示。」
"""

from __future__ import annotations

import pytest

from app.services.equip_lib_similarity import (
    RECOMMEND,
    DISPLAY_ONLY,
    VERIFY,
    compute_similarity,
    flatten_standard_info,
)

_FULL = {
    "equipment_type": "PUMP",
    "type_code": "PUMP-CENTRIFUGAL-01",
    "material": "ZG230-450",
    "standard_drawing_no": "AB-1234",
    "weight_kg": 850.0,
    "key_dimensions": {"head_m": 120, "flow_m3h": 45, "rpm": 2950},
}

# 六个维度全不同
_DIFFERENT = {
    "equipment_type": "VESSEL",
    "type_code": "VESSEL-VERTICAL-99",
    "material": "SS316L",
    "standard_drawing_no": "XY-9999",
    "weight_kg": 12_000.0,
    "key_dimensions": {"diameter_mm": 3000, "height_mm": 8000},
}


def test_identical_scores_1_0():
    """完全相同 → 1.0（UI-SPEC 边界）."""
    r = compute_similarity(_FULL, dict(_FULL))
    assert r.score == pytest.approx(1.0), r.per_dimension
    assert r.tier == RECOMMEND


def test_completely_different_scores_below_0_5():
    """完全不同 → <0.5（UI-SPEC 边界）."""
    r = compute_similarity(_FULL, _DIFFERENT)
    assert r.score < 0.5, r.per_dimension
    assert r.tier == DISPLAY_ONLY


def test_missing_dimension_is_skipped_not_penalised():
    """一侧缺某维度 → 该维度不参与计分（缺数据 ≠ 不相似）.

    设备库里大量条目没有 weight_kg，若缺即判 0 分，全部设备都会被压到
    DISPLAY_ONLY，相似度就失去筛选意义。
    """
    partial = {k: v for k, v in _FULL.items() if k != "weight_kg"}
    r = compute_similarity(_FULL, partial)
    assert r.score == pytest.approx(1.0), r.per_dimension
    assert "weight_kg" not in r.per_dimension


def test_type_code_mismatch_drops_below_verify():
    """型号不同（余项相同）→ 掉出「需校核」档，落到仅展示."""
    other = {**_FULL, "type_code": "PUMP-SUBMERSIBLE-02"}
    r = compute_similarity(_FULL, other)
    assert r.tier == DISPLAY_ONLY, r.per_dimension


def test_tier_thresholds_match_spec():
    """档位边界严格按 UI-SPEC：≥0.9 推荐 / ≥0.8 需校核 / 其余仅展示."""
    from app.services.equip_lib_similarity import classify

    assert classify(0.95) == RECOMMEND
    assert classify(0.90) == RECOMMEND
    assert classify(0.89) == VERIFY
    assert classify(0.80) == VERIFY
    assert classify(0.79) == DISPLAY_ONLY
    assert classify(0.0) == DISPLAY_ONLY


def test_numeric_similarity_is_relative_not_absolute():
    """数值维度用相对差而非绝对差 —— 850kg 与 900kg 应高分，
    850kg 与 12000kg 应低分。绝对差会把所有泵的重量都判成「不像」。"""
    near = {**_FULL, "weight_kg": 900.0}
    far = {**_FULL, "weight_kg": 12_000.0}
    assert compute_similarity(_FULL, near).score > compute_similarity(_FULL, far).score


def test_key_dimensions_only_scores_shared_keys():
    """key_dimensions 只比共有键；无共有键则该维度跳过."""
    a = {"key_dimensions": {"dn": 100, "pn": 16}}
    b = {"key_dimensions": {"dn": 100, "something_else": 3}}
    r = compute_similarity(a, b)
    assert r.score == pytest.approx(1.0), r.per_dimension


def test_nothing_comparable_is_not_perfect_match():
    """两侧都无可比维度 → 不能报 1.0（「什么都不知道」≠「完全相同」）."""
    r = compute_similarity({}, {})
    assert r.score == 0.0
    assert r.tier == DISPLAY_ONLY


def test_flatten_standard_info_hoists_type_code():
    """content_json 嵌套结构 → 扁平可比结构。"""
    asset = {
        "equipment_type": "PUMP",
        "standard_info": {"type_code": "P-01", "material": "SS316", "weight_kg": 5.0},
    }
    flat = flatten_standard_info(asset)
    assert flat["type_code"] == "P-01"
    assert flat["material"] == "SS316"
    assert flat["weight_kg"] == 5.0
    assert flat["equipment_type"] == "PUMP"
