"""`CAS_BY_COMPONENT` 的**离线棘轮** —— 每个 CAS 号都必须站得住。

## 为什么有这三条（2026-11-23 · bug-2197）

那 10 条 DMC 组分的 CAS 号是 2026-11-19 **凭记忆填**的 ⇒ ⇒ 事后用公开源
逐条核对 ⇒ ⇒ **查出 3 条错的**：

| 组分 | 错号 | 错在哪 | 正号 |
|---|---|---|---|
| `ISO_BUTANE` | `106-98-3` | **校验位不过** | `75-28-5` |
| `DIPROPYLENE_GLYCOL` | `25265-29-4` | **校验位不过** | `25265-71-8` |
| `TRIPROPYLENE_GLYCOL` | `2463-75-4` | 校验位**过**，但没有源把它指向三丙二醇 | `24800-44-0` |

⇒ ⇒ 这三条断言就是那三条错号的**自动化凶手**：

1. **校验位**（CAS 末位是校验位 ⇒ ⇒ 格式错一眼看穿 ⇒ ⇒ **纯算术 · 零网络**）
2. **`chemicals` 离线库能取到 MW**（⇒ ⇒ 「这个号指向一个**真实存在**的物质」）
   —— `autoload=False` ⇒ ⇒ **不打网络** ⇒ ⇒ 默认车道零外网依赖
3. **分子量钉死**（⇒ ⇒ 换一个「也能查到、校验位也过、但不是本组分」的号
   ⇒ ⇒ **也会红**）⇒ ⇒ 第 2 条挡不住的那一类，交给第 3 条

⇒ ⇒ ⚠️ 第 2 条**单独不够**：「真号指向别的物质」时它照样绿 ⇒ ⇒ 必须配第 3 条。

## 联网核对是**手工**的（不是 pytest）

CI 无外网 ⇒ ⇒ 联网那一半在 `scripts/verify_component_cas.py`
（PubChem 双向查 + 官方源）⇒ ⇒ 本文件只守**离线可判**的那部分。
"""
from __future__ import annotations

import re

import pytest

from app.services.component_cas import CAS_BY_COMPONENT

#: CAS 形态：`DDD-DD-D`（末位是校验位）
_CAS_RE = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")


def _check_digit_ok(cas: str) -> bool:
    """CAS 校验位 —— 标准算法：末位是校验位，其余位**自右往左**加权求和 mod 10。"""
    m = _CAS_RE.match(cas)
    if not m:
        return False
    body = m.group(1) + m.group(2)
    total = sum(int(d) * i for i, d in enumerate(reversed(body), start=1))
    return total % 10 == int(m.group(3))


@pytest.mark.parametrize("canonical,cas", sorted(CAS_BY_COMPONENT.items()))
def test_every_cas_passes_its_check_digit(canonical: str, cas: str) -> None:
    """**格式关**：CAS 末位是校验位 ⇒ ⇒ 校验位不过 ⇒ ⇒ 它不是 CAS 号（是编的）。"""
    assert _CAS_RE.match(cas), f"{canonical}: {cas!r} 不是 CAS 形态"
    assert _check_digit_ok(cas), (
        f"{canonical}: {cas!r} 的 CAS 校验位不对 ⇒ ⇒ 这是**手抄错的号**，"
        "不是「待确认」⇒ ⇒ 去 https://commonchemistry.cas.org 查真号"
    )


@pytest.mark.parametrize("canonical,cas", sorted(CAS_BY_COMPONENT.items()))
def test_every_cas_resolves_in_the_offline_chemicals_db(canonical: str, cas: str) -> None:
    """**存在关**：这个号必须指向一个**真实登记**的物质。

    ⇒ ⇒ 查不到 ⇒ ⇒ `mw_by_cas` 返回 `None` ⇒ ⇒ 那条流的组成会被**整个作废**
    ⇒ ⇒ 闪蒸算不了（安全的失败）⇒ ⇒ 但功能已经丢了。
    """
    from chemicals import MW

    try:
        value = MW(cas, autoload=False)  # ⚠️ autoload=False ⇒ ⇒ 不打网络
    except Exception as exc:  # noqa: BLE001 —— chemicals 对未知 CAS 会抛多种异常
        pytest.fail(f"{canonical}: chemicals 库不认识 {cas!r} ⇒ {exc}")
    assert value is not None, f"{canonical}: {cas!r} 在 chemicals 库里取不到 MW"


#: 组分 → **分子量**（域事实）⇒ ⇒ 换 CAS 号必须**故意**改这里
#:
#: ⚠️ 这 11 条 = 10 条 DMC 组分 + 1 条 2026-11-23 修掉的 `ISO_BUTANE`
_PINNED_MW: tuple[tuple[str, float], ...] = (
    ("PROPYLENE_OXIDE", 58.079),          # 75-56-9   环氧丙烷 C3H6O
    ("PROPYLENE_CARBONATE", 102.089),     # 108-32-7  碳酸丙烯酯 C4H6O3
    ("DIMETHYL_CARBONATE", 90.078),       # 616-38-6  碳酸二甲酯 C3H6O3
    ("PROPYLENE_GLYCOL", 76.094),         # 57-55-6   丙二醇 C3H8O2
    ("DIPROPYLENE_GLYCOL", 134.174),      # 25265-71-8 二丙二醇 C6H14O3
    ("TRIPROPYLENE_GLYCOL", 192.253),     # 24800-44-0 三丙二醇 C9H20O4
    ("ACRYLIC_ACID", 72.063),             # 79-10-7   丙烯酸 C3H4O2
    ("O_XYLENE", 106.165),                # 95-47-6   邻二甲苯 C8H10
    ("METHOXYPROPANOL", 90.121),          # 107-98-2  甲氧基丙醇 C4H10O2
    ("PROPIONALDEHYDE", 58.079),          # 123-38-6  丙醛 C3H6O
    ("ISO_BUTANE", 58.122),               # 75-28-5   异丁烷 C4H10
)


@pytest.mark.parametrize("canonical,expected_mw", _PINNED_MW)
def test_pinned_components_keep_their_molecular_weight(canonical: str, expected_mw: float) -> None:
    """**身份关**：分子量钉死 ⇒ ⇒ 「号指向别的物质」也红。

    ⇒ ⇒ 第 2 条挡不住的那一类（校验位过 · 库里查得到 · 但不是本组分）就靠这条。
    """
    from chemicals import MW

    cas = CAS_BY_COMPONENT[canonical]
    value = MW(cas, autoload=False)
    assert value == pytest.approx(expected_mw, abs=0.01), (
        f"{canonical}: {cas!r} 的分子量是 {value}，钉死值是 {expected_mw} "
        "⇒ ⇒ 这个号指向的不是本组分 ⇒ ⇒ 查权威源后**同时**改 CAS 与本文件"
    )
