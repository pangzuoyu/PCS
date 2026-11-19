"""组分别名 → CAS 号（**域数据**）—— P10-C · T4（TODO-156）。

## 为什么需要这个表

`composition_json` 的**键必须是 CAS**（`app/services/stream_service.py::
composition_mole_fraction_total` 的口径 + `PropertyAutoCompleter` 按 CAS 估物性）
⇒ ⇒ 解析出来的 PRO/II 组成**必须**先从「PRO/II 缩写」走到「CAS」。

链路是**两段**（各有一段真相源）：

```
PRO/II LIBID 名/缩写  ──alias_registry.resolve_alias("COMPONENT_NAME", …)──▶ 规范名
规范名                ──本表的 CAS_BY_COMPONENT────────────────────────────▶ CAS 号
```

⇒ ⇒ 第一段是**既有**的（`app/services/alias_registry.py`）⇒ ⇒ 本表是**第二段**。

## ⚠️⚠️ **待工艺室确认**（2026-11-19 · 用户裁决「我补 CAS 号并标注待确认」）

下面标 `⚠️ 待确认` 的 10 条是 **DMC 装置专用组分**（PRO/II 的 LIBID 缩写
PO / PROPCARB / DMCARB / 12PG / DIPRPGLY / TPG / AA / OXYLENE / MOXYPROH /
PROPALD）⇒ ⇒ 它们的 CAS 是按**公开的化学物质登记号**填的
⇒ ⇒ **未经工艺室逐条核对** ⇒ ⇒ 首次投产前请让工艺室确认一遍
⇒ ⇒ 已登记 **TODO-196**。

⚠️ **查不到 CAS ⇒ ⇒ 不许编**：本表没有的组分 ⇒ ⇒ 该流的组成**整个作废**
（⇒ `composition_json = None`）⇒ ⇒ **宁可没有组成，不要错组成**
（错组成 ⇒ 闪蒸算出错的结果 ⇒ 比「没有组成」危险得多）。

## 分子量

`mw_by_cas` 用 `chemicals` 包按 CAS 取 MW（`chemicals.MW`）
⇒ ⇒ 取不到 ⇒ ⇒ `None` ⇒ ⇒ 调用方**必须**据此放弃该流的组成。
"""
from __future__ import annotations

from functools import lru_cache

#: 规范名 → CAS 号（**单一真相源**）。
#:
#: ⚠️ 标 `待确认` 的 10 条见模块 docstring。
CAS_BY_COMPONENT: dict[str, str] = {
    # —— registry 里已有的规范名（多数来自公共化学品登记号）——
    "WATER": "7732-18-5",
    "CARBON_DIOXIDE": "124-38-9",
    "HYDROGEN_SULFIDE": "7783-06-4",
    "NITROGEN": "7727-37-9",
    "OXYGEN": "7782-44-7",
    "HYDROGEN": "1333-74-0",
    "AMMONIA": "7664-41-7",
    "METHANE": "74-82-8",
    "ETHANE": "74-84-0",
    "PROPANE": "74-98-6",
    "CARBON_MONOXIDE": "630-08-0",
    "SULFUR_DIOXIDE": "7446-09-5",
    "HYDROGEN_CHLORIDE": "7647-01-0",
    "CHLORINE": "7782-50-5",
    "N_BUTANE": "106-97-8",
    "ISO_BUTANE": "106-98-3",
    "N_PENTANE": "109-66-0",
    "N_HEXANE": "110-54-3",
    "N_HEPTANE": "142-82-5",
    "N_OCTANE": "111-65-9",
    "N_NONANE": "1634-04-4",
    "N_DECANE": "124-18-5",
    "ISOOCTANE": "540-84-1",
    "P_XYLENE": "106-42-3",
    "ETHANOL": "64-17-5",
    "METHANOL": "67-56-1",
    "BENZENE": "71-43-2",
    "ARGON": "7440-37-1",
    "HELIUM": "7440-59-7",
    "NEON": "7440-01-9",
    "KRYPTON": "7439-90-9",
    "XENON": "7440-63-3",
    # —— ⚠️ 待工艺室确认（DMC 装置专用 · 2026-11-19）——
    "PROPYLENE_OXIDE": "75-56-9",        # PO 环氧丙烷
    "PROPYLENE_CARBONATE": "108-32-7",   # PROPCARB 碳酸丙烯酯
    "DIMETHYL_CARBONATE": "616-38-6",    # DMCARB 碳酸二甲酯
    "PROPYLENE_GLYCOL": "57-55-6",       # 12PG 丙二醇
    "DIPROPYLENE_GLYCOL": "25265-29-4",  # DIPRPGLY 二丙二醇
    "TRIPROPYLENE_GLYCOL": "2463-75-4",  # TPG 三丙二醇
    "ACRYLIC_ACID": "79-10-7",           # AA 丙烯酸
    "O_XYLENE": "95-47-6",               # OXYLENE 邻二甲苯
    "METHOXYPROPANOL": "107-98-2",       # MOXYPROH 甲氧基丙醇
    "PROPIONALDEHYDE": "123-38-6",       # PROPALD 丙醛
}


def cas_for_component(canonical_name: str) -> str | None:
    """规范名 → CAS 号（查不到 ⇒ `None` ⇒ **不许编**）。"""
    if not canonical_name:
        return None
    return CAS_BY_COMPONENT.get(canonical_name.strip().upper())


@lru_cache(maxsize=512)
def mw_by_cas(cas: str) -> float | None:
    """CAS → 分子量（`chemicals` 包；取不到 ⇒ `None`）。

    ⚠️ **缓存**：CAS → MW 是**稳定**的（公开登记数据）⇒ ⇒ 缓存安全
    ⇒ ⇒ 免得每条物流都去查一次库。
    """
    if not cas:
        return None
    try:
        from chemicals import MW

        value = MW(cas)
    except Exception:  # noqa: BLE001 —— chemicals 对未知 CAS 会抛多种异常
        return None
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
