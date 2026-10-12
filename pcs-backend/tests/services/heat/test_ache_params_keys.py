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
    """带满 ACHE 特征的最小 HTRI 解析结果。"""

    version = "V8.0"
    case_name = "ACHE"
    fan_count = 4
    air_inlet_t_k = 308.15
    bundle_area_m2 = 120.0


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
