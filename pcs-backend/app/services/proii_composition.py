"""PRO/II 组成 → **摩尔分率**（P10-C · T4 · TODO-156）。

## 为什么要有这一层

`.inp` 里的 `COMPOSITION(M|W)=…` 给的是**百分数** + **基准（M/W）**
⇒ ⇒ 而 `composition_json` 的口径是 **{CAS: 摩尔分率}（和为 1.0）**
⇒ ⇒ 中间必须有一次换算：

| PRO/II 基准 | 换算 |
|---|---|
| `COMPOSITION(M)` | 百分数 → 小数 → **就是**摩尔分率 ⇒ 归一 |
| `COMPOSITION(W)` | 百分数 → 小数 → **质量**分率 ⇒ 质量→摩尔（按 MW）⇒ 归一 |

⇒ ⇒ 质量→摩尔用**既有**的 `app/services/composition_normalizer.py`
（`normalize_composition_mass_to_mole`）⇒ ⇒ 不重写一份换算。

## ⚠️ **有一个组分解析不出来 ⇒ ⇒ 整个组成作废**

「宁可没有组成，不要错组成」—— 缺一个组分的组成送进闪蒸 ⇒ ⇒ 算出**错**的结果
⇒ ⇒ 比 `composition_json = None`（下游会走「没有组成 ⇒ 需要人工补」）
**危险得多** ⇒ ⇒ 所以：**全有或全无**。

⇒ ⇒ 返回 `(组成 | None, 未解析的组分名列表)` ⇒ ⇒ 调用方把后者写进
warnings ⇒ ⇒ 用户看得见「哪几个组分没认出来」。

## ⚠️ **归一的口径**

组成门禁（`app/api/v1/streams.py::_composition_gate`）要求
**100±0.5%** ⇒ ⇒ 本模块**总是**把结果归一到 **1.0**（和 = 100.00%）
⇒ ⇒ 门禁必然过 ⇒ ⇒ 而**原始**和不为 100 的流（样例里 S18 = 99.9648%）
**被归一后**落在门禁内 ⇒ ⇒ 这是**有意的**：门禁判的是「录入者填的组成
自洽吗」，而导入的组成是**机器算出来的**（PRO/II 自己可能没归一）
⇒ ⇒ 归一后仍要过 ⇒ ⇒ 归一是对的行为。
"""
from __future__ import annotations

from app.services.component_cas import cas_for_component, mw_by_cas
from app.services.composition_normalizer import (
    CompositionMassToMoleError,
    normalize_composition_mass_to_mole,
)
from app.services.proii_parser import ProiiComposition

#: 组成门禁的容差（与 `streams.py::_composition_gate` 同口径：100±0.5%）。
#:
#: ⚠️ 本模块**总是**归一到 1.0 ⇒ ⇒ 偏差恒为 0 ⇒ ⇒ 这个常量只是**断言用**
#: （「归一后与 1 的偏差 ≤ 容差」）⇒ ⇒ 门禁那边才是真判据。
COMPOSITION_TOTAL_TOLERANCE = 0.005


def to_mole_fractions(
    composition: ProiiComposition,
) -> tuple[dict[str, float] | None, list[str]]:
    """PRO/II 组成 → `{CAS: 摩尔分率}`（**归一到 1.0**）。

    Args:
        composition: `ProiiComposition`（基准 + 百分数分率）

    Returns:
        `(组成 | None, 未解析的组分名列表)`
        ⇒ ⇒ 组成为 `None` ⇔ **有组分没认出来**（⇒ ⇒ 全有或全无）
    """
    if not composition.fractions:
        return None, []

    # ── 1) 组分名 → CAS ────────────────────────────────────────────────
    cas_by_component: dict[str, str] = {}
    unresolved: list[str] = []
    for name in composition.fractions:
        cas = cas_for_component(name)
        if cas is None:
            unresolved.append(name)
        else:
            cas_by_component[name] = cas
    if unresolved:
        # ⚠️ **全有或全无**：缺一个组分 ⇒ ⇒ 整个组成作废。
        return None, sorted(unresolved)

    # ── 2) 百分数 → 小数 ──────────────────────────────────────────────
    fractions = {
        cas_by_component[name]: value / 100.0
        for name, value in composition.fractions.items()
    }

    # ── 3) 基准 → 摩尔分率 ────────────────────────────────────────────
    if composition.basis == "W":
        mw = {cas: mw_by_cas(cas) for cas in fractions}
        missing_mw = [cas for cas, value in mw.items() if value is None]
        if missing_mw:
            # ⚠️ MW 缺失 ⇒ ⇒ 同样**全有或全无**（不能拿缺 MW 的组分凑数）。
            return None, sorted(f"__no_mw__:{cas}" for cas in missing_mw)
        try:
            mole = normalize_composition_mass_to_mole(
                fractions, {cas: float(value) for cas, value in mw.items() if value}
            )
        except CompositionMassToMoleError:
            return None, ["__normalize_failed__"]
    else:
        # ⚠️ `COMPOSITION(M)` ⇒ 本来就是摩尔分率 ⇒ ⇒ 只需归一。
        total = sum(fractions.values())
        if total <= 0:
            return None, ["__nonpositive_total__"]
        mole = {cas: value / total for cas, value in fractions.items()}

    return mole, []
