"""SUP-P5-PSV-002 V1.14 §3.8 波纹管材料-介质兼容矩阵测试。

按 SPEC V1.14 §3.8：

覆盖：
- 6 材料 × forbidden 条件（HASTELLOY_C276 / ALLOY_C22 / SS316L /
  INCONEL_625 / INCONEL_718 / ALLOY_400 各 1 forbidden case）
- 1 无 service_note 通过（None + 不匹配字符均不抛错）
- get_bellows_material_info / get_matching_forbidden_condition 单元测试
"""
from __future__ import annotations

import pytest

from app.services.exceptions import PsvBellowsIncompatible
from app.services.psv.bellows_compat import (
    BELLOWS_MATERIAL_COMPAT,
    get_bellows_material_info,
    get_matching_forbidden_condition,
    validate_bellows_compat,
)


# ============================================================================
# 1. 6 材料 forbidden 条件 → 抛 PsvBellowsIncompatible（PSV_BELLOWS_INCOMPATIBLE 422）
# ============================================================================


def test_hastelloy_c276_forbidden_oxidizing_acid():
    """HASTELLOY_C276 + 强氧化性介质 → 抛 422。"""
    with pytest.raises(PsvBellowsIncompatible) as exc_info:
        validate_bellows_compat("HASTELLOY_C276", "本工段为热浓硝酸介质，强氧化性介质工况")
    err = exc_info.value
    assert err.code == "PSV_BELLOWS_INCOMPATIBLE"
    assert err.status == 422
    assert "HASTELLOY_C276" in str(err)
    assert "强氧化性介质" in str(err)
    assert err.details["forbidden_condition"] == "强氧化性介质"
    assert err.details["material"] == "HASTELLOY_C276"
    # ASTM 标准必含 B 575
    assert "ASTM B 575" in err.details["astm"]


def test_alloy_c22_forbidden_oxidizing_acid():
    """ALLOY_C22 + 强氧化性介质 → 抛 422。"""
    with pytest.raises(PsvBellowsIncompatible) as exc_info:
        validate_bellows_compat("ALLOY_C22", "高温 + 强氧化性介质")
    err = exc_info.value
    assert err.code == "PSV_BELLOWS_INCOMPATIBLE"
    assert "ALLOY_C22" in str(err)


def test_ss316l_forbidden_chloride_scc():
    """SS316L + 氯化物应力腐蚀开裂 → 抛 422（500 ppm 保守阈值标记）。"""
    with pytest.raises(PsvBellowsIncompatible) as exc_info:
        validate_bellows_compat("SS316L", "介质含氯化物应力腐蚀开裂风险")
    err = exc_info.value
    assert err.code == "PSV_BELLOWS_INCOMPATIBLE"
    assert err.details["forbidden_condition"] == "氯化物应力腐蚀开裂"
    assert err.details["conservative_threshold_ppm"] == 500


def test_inconel_625_forbidden_hf():
    """INCONEL_625 + 高温高浓度氢氟酸 → 抛 422。"""
    with pytest.raises(PsvBellowsIncompatible) as exc_info:
        validate_bellows_compat("INCONEL_625", "高温高浓度氢氟酸工况需专项评估")
    err = exc_info.value
    assert err.code == "PSV_BELLOWS_INCOMPATIBLE"
    assert "氢氟酸" in str(err)


def test_inconel_718_forbidden_high_sulfur():
    """INCONEL_718 + 高温高硫环境 → 抛 422。"""
    with pytest.raises(PsvBellowsIncompatible) as exc_info:
        validate_bellows_compat("INCONEL_718", "高温高硫环境 — 含硫化合物腐蚀加速")
    err = exc_info.value
    assert err.code == "PSV_BELLOWS_INCOMPATIBLE"
    assert "高硫" in str(err)


def test_alloy_400_forbidden_wet_h2s():
    """ALLOY_400 + 湿 H₂S → 抛 422。"""
    with pytest.raises(PsvBellowsIncompatible) as exc_info:
        validate_bellows_compat("ALLOY_400", "本系统含湿 H₂S + 游离水分")
    err = exc_info.value
    assert err.code == "PSV_BELLOWS_INCOMPATIBLE"
    assert "湿 H₂S" in str(err)


# ============================================================================
# 2. 无 service_note / 不匹配 → 不抛错
# ============================================================================


def test_none_service_note_passes():
    """service_note=None → 不抛错（无信息可判断）。"""
    # 任何材料 + None 都不应抛错
    for material in ("HASTELLOY_C276", "SS316L", "ALLOY_400"):
        validate_bellows_compat(material, None)  # 不抛错


def test_non_matching_service_note_passes():
    """service_note 不包含任何 forbidden condition → 不抛错。"""
    # HASTELLOY_C276 + "蒸汽"（不触发强氧化） → 不抛
    validate_bellows_compat("HASTELLOY_C276", "本工段为清洁蒸汽，300°C")
    # ALLOY_400 + "海水"（匹配"湿 H₂S"？ 不，dry H2S 才对；海水也不匹配任何 forbidden）
    validate_bellows_compat("ALLOY_400", "海水冷却系统")


# ============================================================================
# 3. get_bellows_material_info / get_matching_forbidden_condition
# ============================================================================


def test_get_bellows_material_info_returns_dict():
    """get_bellows_material_info 返回完整条目。"""
    info = get_bellows_material_info("SS316L")
    assert info["astm"] == ["ASTM A 240", "ASTM A 312"]
    assert len(info["forbidden"]) == 1
    assert info["forbidden"][0]["condition"] == "氯化物应力腐蚀开裂"


def test_get_matching_forbidden_condition_none():
    """不匹配条件 → 返回 None。"""
    assert get_matching_forbidden_condition("HASTELLOY_C276", "清洁蒸汽") is None
    assert get_matching_forbidden_condition("HASTELLOY_C276", None) is None
    assert get_matching_forbidden_condition("HASTELLOY_C276", "") is None


def test_matrix_count_6_materials():
    """BELLOWS_MATERIAL_COMPAT 包含 6 材料。"""
    expected = {"HASTELLOY_C276", "ALLOY_C22", "SS316L", "INCONEL_625", "INCONEL_718", "ALLOY_400"}
    assert set(BELLOWS_MATERIAL_COMPAT.keys()) == expected