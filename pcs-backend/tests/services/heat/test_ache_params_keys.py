"""`ache_params` JSONB 的**唯一键名契约**。

## 为什么这条测试存在

`heat_data_service` 里有**两个活跃写入方**，键名词汇表不同：

| 写入方 | 写的键 |
|---|---|
| `_htri_ache_dict`（HTRI 导入） | `fan_count` / `air_inlet_temp` / `bundle_area` |
| `AcheParams.to_dict()`（手工录入） | 8 键（`fan_count` 起，`air_side_resistance_dist` 止） |

同一个概念两种拼法（`bundle_area` vs `bundle_area_m2`）—— 报表字段按其中
一种拼法登记时，另一来源的每一行都查出 NULL，而**报表不会报错**：它只是
一列空白。

`HeatResult.ache_params` 的列注释写的是 `fans/airside/fin/nozzle/
airside_resistance_distribution` —— **第三套词汇**，且与两个写入方都对不上。
所以本测试不钉某一侧，而是钉「所有写入方产出同一套键」。
"""
from __future__ import annotations

from app.services.heat.heat_data_service import AcheParams, _htri_ache_dict


def _minimal_ache_params() -> dict:
    return AcheParams(
        fan_count=4, fan_power_kw=25.0, bundle_area_m2=120.0,
        air_inlet_temp_k=308.15, altitude_m=50.0, fin_type="L-footed",
        tube_nozzle_count=2, air_side_resistance_dist={"a": 0.1},
    ).to_dict()


class _FakeHtri:
    """带满 ACHE 特征的最小 HTRI 解析结果。

    ⚠️ 几何字段也要列全：`HtriParsedData` 是 dataclass，属性齐全，
    所以 `_ache_with_geometry` 直接属性访问是对的（缺了就 AttributeError，
    而不是静默 None）。测试替身若漏属性，报错就落在这个替身上 ——
    补全即可，不要为了「让它跑过」把生产代码改成 `getattr(..., None)`。
    """

    version = "V8.0"
    case_name = "ACHE"
    fan_count = 4
    air_inlet_t_k = 308.15
    bundle_area_m2 = 120.0

    fin_height_mm = None
    fin_thickness_mm = None
    fin_root_diameter_mm = None
    over_fin_diameter_mm = None
    tip_clearance_mm = None
    air_humidity_percent = None
    fin_density_per_m = None
    fin_efficiency_percent = None
    unfinned_length_mm = None
    unheated_length_mm = None


def test_htri_import_writes_the_same_keys_as_manual_entry():
    canonical = set(_minimal_ache_params())
    from_htri = set(_htri_ache_dict(_FakeHtri()))
    assert from_htri == canonical, (
        f"HTRI 导入写的键与手工录入不一致。\n"
        f"  仅 HTRI 有：{sorted(from_htri - canonical)}\n"
        f"  仅手工录入有：{sorted(canonical - from_htri)}\n"
        "两套拼法并存时，报表按其中一种登记，另一半行的该列恒为 NULL 且不报错。")


def test_no_ache_data_stays_none():
    """无 ACHE 特征时必须落 None，不能落一个空 dict ——
    「这行不是空冷器」与「这行是空冷器但参数全空」在报表上是两件事。"""

    class _NoAche(_FakeHtri):
        fan_count = None
        air_inlet_t_k = None
        bundle_area_m2 = None

    assert _htri_ache_dict(_NoAche()) is None


# --- 第三个写入方：_ache_with_geometry ----------------------------------------
#
# ⚠️ `map_htri_to_heat_input` 落库走的是 `_ache_with_geometry`，
# 而上面两条契约只钉了 `_htri_ache_dict`。合并层漏一个键 =
# 「解析出来了、注册表登记了、导入时那一列永远 NULL 且不报错」——
# 正是本文件开头的那个故障，只是换了一层。


def test_merge_layer_writes_the_same_keys_as_manual_entry():
    canonical = set(_minimal_ache_params())
    from app.services.heat.heat_data_service import _ache_with_geometry

    assert set(_ache_with_geometry(_FakeHtri())) == canonical, (
        f"合并层键集与手工录入不一致。\n"
        f"  仅合并层有：{sorted(set(_ache_with_geometry(_FakeHtri())) - canonical)}\n"
        f"  仅手工录入有：{sorted(canonical - set(_ache_with_geometry(_FakeHtri())))}")


def test_zero_geometry_survives_the_merge():
    """⚠️ `Unfinned length` 的真实值是 **0.000**。

    0.0 是假值，任何 `k or v` / `dict.get(k) or v` 形式的兜底都会把它
    换成 None —— 落库时是一列空白，而报表不报错。这类 bug 在合成
    fixture 上永远看不见（None 也会「看起来对」），只有真实文件的
    0.000 才触发得出来。
    """
    from app.services.heat.heat_data_service import _ache_with_geometry

    class _WithZero(_FakeHtri):
        unfinned_length_mm = 0.0
        unheated_length_mm = 127.0
        fin_density_per_m = 433.1

    got = _ache_with_geometry(_WithZero())
    assert got["unfinned_length_mm"] == 0.0, \
        f"0 被当成「没值」丢了（实得 {got['unfinned_length_mm']!r}）"
    assert got["unheated_length_mm"] == 127.0
    assert got["fin_density_per_m"] == 433.1
