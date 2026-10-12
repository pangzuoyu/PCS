"""用户 2026-12-12 裁决落地的字段（P8c）。

| 裁决 | 落地 |
|---|---|
| 壁温进规格书 | `skin_temp_min` / `skin_temp_max` 两列 |
| 两相含量要显示 | `shell_params` / `tube_params` 各 4 个 wt% 键 |
| 管排数空冷器专属 | `tube_rows` 列，`exchanger_type=AIR_COOLER` |

## 为什么先钉「有没有写入方」

c1 拒绝登记过「ORM 上没有的字段」——那会「选得到、查出空列」。
**同样地拒绝登记「有列但没有写入方」的字段**：列在、手工能填，
但 HTRI 导入的那批行**全是 NULL**，而报表不报错，只是一整片空白。

所以本文件钉的是**两个写入方都产出同一套键**（bug-160 的教训），
以及「HTRI 导入路径**明确不填**这些字段」——后者是诚实的文档化，
不是缺陷藏起来。
"""
from __future__ import annotations

import pytest

from app.models.calc import HeatResult
from app.services.heat.heat_data_service import (AcheParams,
                                                 _htri_ache_dict,
                                                 _htri_cold_side_dict,
                                                 _htri_hot_side_dict)


def _cols() -> set[str]:
    return set(HeatResult.__table__.columns.keys())


# --- 壁温 ---------------------------------------------------------------------


def test_skin_temperature_columns_exist():
    """壁温进规格书（用户裁决）→ 两列 min/max。

    HTRI 的 `Skin temperature, Min/Max` 是一个标签两个值，所以是两个列，
    不是一个。
    """
    assert {"skin_temp_min", "skin_temp_max"} <= _cols(), \
        f"壁温列缺失；现有相关列：{sorted(c for c in _cols() if 'skin' in c or 'wall_t' in c)}"


def test_skin_temperature_is_registered_as_detail_common():
    from app.services.report.datasource_registry import DATASOURCES

    fields = DATASOURCES["HEAT_RESULTS"].fields
    assert "skin_temp_min" in fields and "skin_temp_max" in fields
    for name in ("skin_temp_min", "skin_temp_max"):
        assert fields[name].level == "DETAIL"
        # 壁温是管壁温度，管壳式/空冷器都有 → 不是某一类专属
        assert fields[name].exchanger_type is None, \
            f"{name} 被标成了某一类专属 —— 壁温两类都有"


# --- 管排数（空冷器专属）------------------------------------------------------


def test_tube_rows_column_exists_and_is_air_cooler_only():
    """管排数空冷器专属（用户裁决）→ 列 + `exchanger_type=AIR_COOLER`。"""
    assert "tube_rows" in _cols()
    from app.services.report.datasource_registry import DATASOURCES

    spec = DATASOURCES["HEAT_RESULTS"].fields["tube_rows"]
    assert spec.exchanger_type == "AIR_COOLER"
    assert spec.level == "DETAIL"


def test_tube_rows_is_not_repeatable_with_tube_passes():
    """`tube_passes`（管程数）与 `tube_rows`（管排数）是两个东西。

    HTRI 的 `Tubepasses/Tuberows | -- | 2 / | 4` 把两者并排写 —— 登记时
    容易只取第一个，于是「管程数」悄悄变成了「管排数」。
    """
    from app.services.report.datasource_registry import DATASOURCES

    fields = DATASOURCES["HEAT_RESULTS"].fields
    assert "tube_passes" in fields and "tube_rows" in fields
    assert fields["tube_passes"].exchanger_type is None, \
        "管程数是通用的，不能挂到空冷器名下"


# --- 两相含量 -----------------------------------------------------------------


TWO_PHASE_KEYS = {"vapor_wt_frac_in", "vapor_wt_frac_out",
                  "liquid_wt_frac_in", "liquid_wt_frac_out"}


def test_two_phase_keys_are_registered_for_both_sides():
    """两相含量要显示（用户裁决）→ 壳程/管程各 4 个 wt% 键。"""
    from app.services.report.datasource_registry import DATASOURCES

    fields = DATASOURCES["HEAT_RESULTS"].fields
    for container in ("shell_params", "tube_params"):
        for key in TWO_PHASE_KEYS:
            name = f"{container}.{key}"
            assert name in fields, f"{name} 未登记"
            assert fields[name].is_jsonb_key
            assert fields[name].level == "DETAIL"


@pytest.mark.parametrize("side_dict", [_htri_hot_side_dict, _htri_cold_side_dict])
def test_htri_side_writers_emit_the_two_phase_keys_explicitly(side_dict):
    """⚠️ 两个写入方必须产出**同一套键**（bug-160 的教训）。

    HTRI 解析器提不到两相含量，所以这里填 `None` —— 但**必须显式填**，
    不能省略：省略会让「哪些键存在」在两个来源间不一致，而下游按
    `if "vapor_wt_frac_in" in params` 判断时，两类行会走不同分支。
    """
    class _FakeHtri:
        hot_inlet_t_k = 320.0
        hot_outlet_t_k = 350.0
        hot_mass_flow_kgs = 17.8
        hot_cp_j_kgk = 2100.0
        cold_inlet_t_k = 300.0
        cold_outlet_t_k = 310.0
        cold_mass_flow_kgs = 17.0
        cold_cp_j_kgk = 2000.0

    got = side_dict(_FakeHtri())
    missing = TWO_PHASE_KEYS - set(got)
    assert not missing, f"缺少两相键（须显式置 None）：{sorted(missing)}"


def test_two_phase_keys_are_documented_as_not_populated_by_htri_import():
    """诚实文档化：HTRI 导入**不填**这些键。

    不是缺陷藏起来 —— 报表里这几列会是空的，而**没有任何一层会报错**。
    测试把这件事钉在源码里，将来补上解析时会被迫更新。
    """
    import inspect

    from app.services.heat import htri_parser

    src = inspect.getsource(htri_parser)
    assert "vapor_wt_frac" not in src, \
        "解析器已支持两相含量 —— 请同步更新本测试与 registry 的注释"


# --- 写入方一致性：ache_params 的翅片几何 ---------------------------------------


ACHE_GEOM_KEYS = {"fin_height_mm", "fin_thickness_mm", "fin_root_diameter_mm",
                  "over_fin_diameter_mm", "tip_clearance_mm"}


def _minimal_ache_params() -> AcheParams:
    """`AcheParams` 的原 8 个字段是必填 —— 构造一份合法的再查新字段。"""
    return AcheParams(
        fan_count=4, fan_power_kw=25.0, bundle_area_m2=120.0,
        air_inlet_temp_k=308.15, altitude_m=50.0, fin_type="L-footed",
        tube_nozzle_count=2, air_side_resistance_dist={"a": 0.1},
    )


def test_ache_params_now_carries_the_fin_geometry():
    """TODO-056 的第一批：Xace 报告里有的 5 个翅片/风机几何字段。

    `AcheParams` 加了字段，但 **HTRI 写入方也要跟着加**（bug-160）。
    """
    keys = set(_minimal_ache_params().to_dict())
    assert ACHE_GEOM_KEYS <= keys, \
        f"AcheParams 缺：{sorted(ACHE_GEOM_KEYS - keys)}"


def test_htri_ache_writer_key_set_matches_ache_params():
    """两个写入方的键集必须**逐字相同** —— bug-160 就是这里破的。"""

    class _FakeHtri:
        version = "V8.0"
        case_name = "ACHE"
        fan_count = 4
        air_inlet_t_k = 308.15
        bundle_area_m2 = 120.0

    assert set(_htri_ache_dict(_FakeHtri())) == set(_minimal_ache_params().to_dict())
