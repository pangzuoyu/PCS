"""P3.x SIM-38b/3: 塔盘数据全量 — TRAY COMPOSITIONS 全量集成（SIM-38b 闭环）。

在 SIM-38a PoC（块解析 proii_tray_compositions_poc）之上增量：
- UnitTrayCompositions：UNIT 头归属 + basis（MOLAR/WEIGHT）
- 全文解析状态机：
  - 「TRAY MOLAR/WEIGHT COMPOSITIONS」标记开 section
  - 翻页：页内 (CONT) UNIT 头不切断 section（页眉噪声由块解析器跳过）
  - 非 (CONT) UNIT 头 / 基准切换 / 其他 TRAY 段标题 → 结束当前 section
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.proii_tray_compositions_poc import (
    TrayCompositions,
    parse_tray_composition_blocks,
)


@dataclass
class UnitTrayCompositions:
    """单 UNIT 单基准（MOLAR/WEIGHT）的 TRAY COMPOSITIONS section。"""

    unit_no: str
    unit_name: str
    unit_desc: str | None = None
    basis: str = "MOLAR"
    blocks: list[TrayCompositions] = field(default_factory=list)


_UNIT_RE = re.compile(
    r"^\s*UNIT\s+(\d+)\s*,\s*'([^']+)'(?:\s*,\s*'([^']+)')?",
    re.IGNORECASE,
)
_UNIT_CONT_RE = re.compile(r"\(CONT\)\s*$", re.IGNORECASE)
_BASIS_RE = re.compile(
    r"^\s*TRAY\s+(MOLAR|WEIGHT)\s+COMPOSITIONS\s*$",
    re.IGNORECASE,
)
# 其他 TRAY 段标题 → 结束 section（精确动词枚举，bug-070 教训）
_OTHER_TRAY_TITLE_RE = re.compile(
    r"^\s*TRAY\s+"
    r"(SIZING|RATES|TRANSPORT|ENTHALPIES|RATING|LOADING|SELECTION)",
    re.IGNORECASE,
)


def parse_tray_compositions(text: str) -> list[UnitTrayCompositions]:
    """解析 .out 中全部 TRAY COMPOSITIONS section（per UNIT × 基准）。

    Args:
        text: .out 全文或片段

    Returns:
        UnitTrayCompositions 列表（每遇到一次 MOLAR/WEIGHT 标记产生一项）
    """
    entries: list[UnitTrayCompositions] = []
    current_unit: dict[str, str | None] = {"no": None, "name": None, "desc": None}
    # 当前 section 的行缓冲（标记行之后累积，结束时委托块解析器）
    buffer: list[str] | None = None
    current_entry: UnitTrayCompositions | None = None

    def _flush() -> None:
        """结束当前 section：缓冲委托块解析器。"""
        nonlocal buffer, current_entry
        if current_entry is not None and buffer is not None:
            current_entry.blocks = parse_tray_composition_blocks(
                "\n".join(buffer),
            )
        buffer = None
        current_entry = None

    for raw in text.splitlines():
        line = raw.rstrip()

        m_unit = _UNIT_RE.match(line)
        if m_unit:
            if buffer is not None and not _UNIT_CONT_RE.search(line):
                # 非 (CONT) UNIT 头：新 unit 的段开始 → 结束当前 section
                _flush()
            current_unit = {
                "no": m_unit.group(1),
                "name": m_unit.group(2),
                "desc": m_unit.group(3),
            }
            if buffer is not None:
                buffer.append(line)  # (CONT) 页眉：保留（块解析器跳过）
            continue

        m_basis = _BASIS_RE.match(line)
        if m_basis:
            _flush()
            current_entry = UnitTrayCompositions(
                unit_no=current_unit["no"] or "",
                unit_name=current_unit["name"] or "",
                unit_desc=current_unit["desc"],
                basis=m_basis.group(1).upper(),
            )
            entries.append(current_entry)
            buffer = []
            continue

        if _OTHER_TRAY_TITLE_RE.match(line):
            _flush()
            continue

        if buffer is not None:
            buffer.append(line)

    _flush()
    return entries


__all__ = [
    "UnitTrayCompositions",
    "parse_tray_compositions",
]