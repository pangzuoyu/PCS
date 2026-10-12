"""detail_level 分级（ADR-0028「detail_level 选择」）。

**只有 HEAT_RESULTS 一个数据源有分级。** 其他 12 个源在 BASIC 下照常可用 ——
给所有源都套分级，会让「一份 BASIC 报表连设备字段都选不了」。

## 为什么校验在**写入定义**时做，而不是执行时

执行时校验已经晚了：用户已经配好了过滤条件、排好了序、改完了名字，
最后一步被拒。而分级本来就是**定义自身**的属性（ADR：「报表定义中增加
detailLevel 字段」），在定义存进去之前核对是唯一说得通的位置。
"""
from __future__ import annotations

from typing import Any, Literal

from app.services.exceptions import PcsError
from app.services.report.datasource_registry import DATASOURCES

DetailLevel = Literal["BASIC", "DETAIL"]

#: 唯一参与分级的数据源。其余源的 `level` 全是 None。
LEVELLED_SOURCES = frozenset({"HEAT_RESULTS"})

_LEVELS: tuple[str, ...] = ("BASIC", "DETAIL")


def check_level(level: str) -> str:
    """校验分级枚举。**大小写敏感**。

    拼错不能静默当 DETAIL：BASIC 定义升级成 DETAIL 会平白多出 40 列，
    而 ADR 的分级标准（BASIC 不含几何/热阻明细）当场失效。
    """
    if level not in _LEVELS:
        raise PcsError(
            f"未知的 detail_level：{level!r}。可用：{list(_LEVELS)}。"
            "**大小写敏感** —— 静默当成 DETAIL 会让 BASIC 报表平白多出 40 列。",
            code="REPORT_DETAIL_LEVEL_INVALID", status=400,
        )
    return level


def fields_visible_at(source: str, level: str, *,
                       want: list[str] | None = None) -> list[str]:
    """返回该分级下**可见**的字段名。

    - 分级只对 `LEVELLED_SOURCES` 生效；其余源原样返回
    - BASIC 看到 `level in (None, "BASIC")` 的字段；
      DETAIL 看到全部
    - `want` 非空时，校验它每一项在该分级下可见，不可见则 400
    """
    check_level(level)
    ds = DATASOURCES.get(source)
    if ds is None:
        raise PcsError(f"未知数据源：{source}",
                       code="REPORT_DATASOURCE_UNKNOWN", status=400)
    if source not in LEVELLED_SOURCES:
        return list(want) if want is not None else sorted(ds.fields)

    if want is None:
        return sorted(n for n, s in ds.fields.items()
                      if level == "DETAIL" or s.level in (None, "BASIC"))

    bad = [f for f in want if level == "BASIC" and ds.fields[f].level == "DETAIL"]
    if bad:
        raise PcsError(
            f"detail_level=BASIC 的报表不能选 DETAIL 字段：{sorted(bad)}。"
            "要么把这些字段的 visible 置 false，要么把定义的 detail_level "
            "改成 DETAIL（ADR-0028「分级标准」：BASIC 不含几何/热阻明细）。",
            code="REPORT_DETAIL_LEVEL_VIOLATION", status=400,
        )
    return list(want)


def validate_definition(defn: dict[str, Any]) -> None:
    """整份定义的分级核对：每个 `SelectedFields` 项都要在该级可见。

    `visible=False` 的字段**也要过这一关** —— 它存在定义里，将来有人改成
    可见就会撞上一个 BASIC 定义里本不该有的字段。放过去等于把问题推到
    更远的地方。
    """
    level = defn.get("detailLevel") or "BASIC"
    check_level(level)
    for sel in defn.get("SelectedFields") or []:
        src = sel.get("source")
        fields_visible_at(src, level, want=[sel.get("field")])


__all__ = ["DetailLevel", "LEVELLED_SOURCES", "check_level",
           "fields_visible_at", "validate_definition"]