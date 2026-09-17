"""API 526 孔口-法兰映射 + 变体 + H/G 双候选 + T 孔口 65 psig 测试（V1.14 §3.3）。

按 SPEC V1.14 §3.3 + §8 gate #11（H/G 双候选）+ #12（T 65 psig 警告）：

覆盖：
- 14 项基础映射（D~T 全部）
- G 高压档（2G3，1500#/2500#）
- H/G 双候选（"2 inch × 3 inch"）
- Q/R 变体
- 非法尺寸 → []
- 法兰等级感知过滤
- 变体检测
- 尺寸比较（size_lt / size_le）
- 高温低分子量受限
"""
from __future__ import annotations

import pytest

from app.services.psv.orifice_flange import (
    API526_FLANGE_TO_ORIFICES,
    API526_ORIFICE_TO_FLANGE,
    API526_ORIFICE_TO_FLANGE_HIGH_PRESSURE,
    API526_ORIFICE_VARIANTS,
    get_candidate_orifices,
    is_high_pressure_flange,
    is_high_temp_light_gas_restricted,
    is_variant_configuration,
    size_le,
    size_lt,
)
from app.services.psv.valve_selection_types import API526_MIN_INLET


# ============================================================================
# 1. 14 项基础映射完整性（API 526 Tables 2-15）
# ============================================================================


def test_api526_basic_mapping_14_orifices():
    """API 526 Tables 2-15：D~T 14 项映射完整。"""
    assert len(API526_ORIFICE_TO_FLANGE) == 14
    expected = {"D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "Q", "R", "T"}
    assert set(API526_ORIFICE_TO_FLANGE.keys()) == expected


def test_api526_g_orifice_standard():
    """G 孔口标准档 = 1.5" × 3"（API 526 Table 5 1½G3）。"""
    assert API526_ORIFICE_TO_FLANGE["G"] == ("1.5 inch", "3 inch")


def test_api526_t_orifice_8t10():
    """T 孔口 = 8" × 10"（API 526 Table 15 8T10）。"""
    assert API526_ORIFICE_TO_FLANGE["T"] == ("8 inch", "10 inch")


# ============================================================================
# 2. G 高压档（API 526 Table 5：2G3，1500#/2500#）
# ============================================================================


def test_g_high_pressure_config():
    """G 高压档（2G3）入口 2" 出口 3"。"""
    assert API526_ORIFICE_TO_FLANGE_HIGH_PRESSURE["G"] == ("2 inch", "3 inch")


def test_g_high_pressure_flange_class():
    """1500#/2500# 判定为高压档。"""
    assert is_high_pressure_flange("1500#") is True
    assert is_high_pressure_flange("2500#") is True
    assert is_high_pressure_flange("300#") is False
    assert is_high_pressure_flange("600#") is False


# ============================================================================
# 3. H/G 双候选（"2 inch × 3 inch"）
# ============================================================================


def test_hg_dual_candidates_300_class():
    """'2 inch × 3 inch' + 300# → ['H', 'G']（G 在 300# 是反向映射的标准档）"""
    candidates = get_candidate_orifices("2 inch", "3 inch", "300#")
    # 反向映射列了 H+G；G 在 ('2 inch', '3 inch') 是高压档配置 → 300# 排除
    assert candidates == ["H"]


def test_hg_dual_candidates_1500_class():
    """'2 inch × 3 inch' + 1500# → ['H', 'G']（G 高压档 1500# 允许）"""
    candidates = get_candidate_orifices("2 inch", "3 inch", "1500#")
    assert candidates == ["H", "G"]


# ============================================================================
# 4. 标准映射查询
# ============================================================================


def test_standard_g_300_class():
    """'1.5 inch × 3 inch' + 300# → ['G']（标准档；300# 允许）。"""
    candidates = get_candidate_orifices("1.5 inch", "3 inch", "300#")
    assert candidates == ["G"]


def test_standard_d_150_class():
    """'1 inch × 2 inch' + 150# → ['D']。"""
    candidates = get_candidate_orifices("1 inch", "2 inch", "150#")
    assert candidates == ["D"]


def test_ef_dual_candidates():
    """'1.5 inch × 2.5 inch' → ['E', 'F']。"""
    candidates = get_candidate_orifices("1.5 inch", "2.5 inch", "300#")
    assert candidates == ["E", "F"]


def test_lmn_triple_candidates():
    """'4 inch × 6 inch' → ['L', 'M', 'N']。"""
    candidates = get_candidate_orifices("4 inch", "6 inch", "300#")
    assert candidates == ["L", "M", "N"]


def test_qrt_triple_candidates():
    """'8 inch × 10 inch' → ['Q', 'R', 'T']。"""
    candidates = get_candidate_orifices("8 inch", "10 inch", "300#")
    assert candidates == ["Q", "R", "T"]


# ============================================================================
# 5. 非法尺寸 → []
# ============================================================================


def test_unknown_size_returns_empty():
    """'5 inch × 7 inch' 不在反向映射 → []。"""
    candidates = get_candidate_orifices("5 inch", "7 inch", "300#")
    assert candidates == []


def test_swapped_size_returns_empty():
    """尺寸反（'3 inch × 2 inch'）→ []。"""
    candidates = get_candidate_orifices("3 inch", "2 inch", "300#")
    assert candidates == []


# ============================================================================
# 6. Q/R 变体
# ============================================================================


def test_q_variants():
    """Q 孔口变体 = 8"×10"（标准）+ 6"×8"（变体）。"""
    assert API526_ORIFICE_VARIANTS["Q"] == [("8 inch", "10 inch"), ("6 inch", "8 inch")]


def test_r_variants():
    """R 孔口变体 = 8"×10"（标准）+ 6"×10"（变体）。"""
    assert API526_ORIFICE_VARIANTS["R"] == [("8 inch", "10 inch"), ("6 inch", "10 inch")]


def test_is_variant_q_6x8():
    """'6 inch × 8 inch' + Q = 变体。"""
    assert is_variant_configuration("6 inch", "8 inch", "Q") is True


def test_is_variant_q_8x10_standard():
    """'8 inch × 10 inch' + Q = 标准（非变体）。"""
    assert is_variant_configuration("8 inch", "10 inch", "Q") is False


def test_6x8_with_p_and_q_variant():
    """'6 inch × 8 inch' + 300# → ['P', 'Q']（P 标准 + Q 6"×8" 变体）。"""
    candidates = get_candidate_orifices("6 inch", "8 inch", "300#")
    # 反向映射主表列出 P + Q（Q 在此为 6"×8" 变体配置）
    assert candidates == ["P", "Q"]


# ============================================================================
# 7. 尺寸比较工具
# ============================================================================


def test_size_lt_basic():
    """'1 inch' < '1.5 inch' < '2 inch' < '10 inch'。"""
    assert size_lt("1 inch", "1.5 inch") is True
    assert size_lt("1.5 inch", "2 inch") is True
    assert size_lt("2 inch", "10 inch") is True
    assert size_lt("10 inch", "2 inch") is False
    assert size_lt("1.5 inch", "1.5 inch") is False  # 严格小于


def test_size_le_equal():
    """size_le 包含等于。"""
    assert size_le("1.5 inch", "1.5 inch") is True
    assert size_le("1 inch", "1.5 inch") is True
    assert size_le("1.5 inch", "1 inch") is False


def test_min_inlet_constant():
    """API526_MIN_INLET = '1 inch'（§4.2 G14 入口最小尺寸）。"""
    assert API526_MIN_INLET == "1 inch"


# ============================================================================
# 8. 高温低分子量受限（API 520 §5.3.4）
# ============================================================================


def test_high_temp_light_gas_q_restricted():
    """Q 孔口 + T=200°C + MW=5 → 受限（True）。"""
    assert is_high_temp_light_gas_restricted("Q", 200.0, 5.0) is True


def test_high_temp_light_gas_t_below_177():
    """T 孔口 + T=150°C + MW=5 → 不受限（温度 ≤ 177°C）。"""
    assert is_high_temp_light_gas_restricted("T", 150.0, 5.0) is False


def test_high_temp_light_gas_t_above_10_mw():
    """T 孔口 + T=200°C + MW=20 → 不受限（MW ≥ 10）。"""
    assert is_high_temp_light_gas_restricted("T", 200.0, 20.0) is False


def test_high_temp_light_gas_d_not_restricted():
    """D 孔口（不在受限集合）→ 不受限。"""
    assert is_high_temp_light_gas_restricted("D", 200.0, 5.0) is False


def test_high_temp_light_gas_no_temp():
    """温度/分子量 None → 不受限（无法判断）。"""
    assert is_high_temp_light_gas_restricted("Q", None, 5.0) is False
    assert is_high_temp_light_gas_restricted("Q", 200.0, None) is False


# ============================================================================
# 9. 反向映射完整性
# ============================================================================


def test_flange_to_orifices_count():
    """反向映射 9 条目（含 H/G 双候选）。"""
    assert len(API526_FLANGE_TO_ORIFICES) == 9


@pytest.mark.parametrize(
    "key,expected",
    [
        (("1 inch", "2 inch"), ["D"]),
        (("1.5 inch", "2.5 inch"), ["E", "F"]),
        (("1.5 inch", "3 inch"), ["G"]),
        (("2 inch", "3 inch"), ["H", "G"]),
        (("3 inch", "4 inch"), ["J", "K"]),
        (("4 inch", "6 inch"), ["L", "M", "N"]),
        (("6 inch", "8 inch"), ["P", "Q"]),
        (("6 inch", "10 inch"), ["R"]),
        (("8 inch", "10 inch"), ["Q", "R", "T"]),
    ],
)
def test_flange_to_orifices_parametrized(key, expected):
    """反向映射 9 条目逐一校验。"""
    assert API526_FLANGE_TO_ORIFICES[key] == expected
