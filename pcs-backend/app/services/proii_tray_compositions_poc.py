"""P3.x SIM-38a: 塔盘数据 PoC — TRAY COMPOSITIONS 单 Section 解析。

块结构（每块 1-2 塔板，列对齐）：

                              TRAY 1                      TRAY 2
     COMPONENT              X          Y                X          Y
                       ----------  ----------      ----------  ----------
    1 H2O                 0.00000     0.00000         0.00000     0.00000
    ...

  RATE, KG-MOL/HR           12.04    2.59E-01           15.81       12.30

- X = 液相分率，Y = 汽相分率（MOLAR 摩尔 / WEIGHT 质量，由调用方切片定界）
- 列对齐：dashes 段起点 = 值列起点（1 塔板 2 列 / 2 塔板 4 列）
- RATE 行 = 各塔板液/汽相流率（KG-MOL/HR 或 KG/HR，单位不区分）

深度解析（LOADING/RATING + 全 unit 翻页 + WEIGHT 基准区分）留待
SIM-38b（2.5d）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TrayCompositionRow:
    """单组件行（X/Y 与块内 tray_numbers 一一对应）。"""

    comp_no: int
    comp_name: str
    x: list[float] = field(default_factory=list)  # 液相分率（每塔板一值）
    y: list[float] = field(default_factory=list)  # 汽相分率（每塔板一值）


@dataclass
class TrayCompositions:
    """TRAY COMPOSITIONS 单块（1-2 塔板）。"""

    tray_numbers: list[int] = field(default_factory=list)
    rows: list[TrayCompositionRow] = field(default_factory=list)
    liquid_rates: list[float | None] = field(default_factory=list)
    vapor_rates: list[float | None] = field(default_factory=list)


# TRAY 头行：TRAY 1 / TRAY 1   TRAY 2
_TRAY_HEADER_RE = re.compile(r"^\s*TRAY\s+(\d+)(?:\s+TRAY\s+(\d+))?\s*$")
# 组件行：<comp_no> <NAME> + 数值（由列切片提取）
_COMP_ROW_RE = re.compile(r"^\s{2,}(\d+)\s+(\S+)\s")
_RATE_ROW_RE = re.compile(r"^\s*RATE,")
_SCI_FLOAT_RE = re.compile(r"^-?\d*\.?\d+(?:[Ee][+-]?\d+)?$")


def _column_starts_from_dashes(dashes_line: str) -> list[int]:
    """dashes 行每段 '-' 起点 = 值列起点（2 或 4 列）。"""
    starts: list[int] = []
    i = 0
    n = len(dashes_line)
    while i < n:
        if dashes_line[i] == "-":
            starts.append(i)
            while i < n and dashes_line[i] == "-":
                i += 1
        else:
            i += 1
    return starts


def _slice_by_columns(line: str, starts: list[int]) -> list[float | None]:
    """按列起点切取数值；无法解析的列置 None。"""
    values: list[float | None] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(line)
        token = line[start:end].strip() if start < len(line) else ""
        if token and _SCI_FLOAT_RE.match(token):
            values.append(float(token))
        else:
            values.append(None)
    return values


def parse_tray_composition_blocks(text: str) -> list[TrayCompositions]:
    """解析 TRAY COMPOSITIONS 段内的块序列（PoC：单 section 文本）。

    Args:
        text: section 内容片段（调用方负责从 .out 切片定界；
              MOLAR/WEIGHT 基准由切片来源决定）

    Returns:
        TrayCompositions 块列表（TRAY 头行重新开块）
    """
    blocks: list[TrayCompositions] = []
    current: TrayCompositions | None = None
    column_starts: list[int] = []

    for raw in text.splitlines():
        line = raw.rstrip()

        m = _TRAY_HEADER_RE.match(line)
        if m:
            current = TrayCompositions(
                tray_numbers=[int(g) for g in m.groups() if g],
            )
            blocks.append(current)
            column_starts = []
            continue
        if current is None:
            continue

        # dashes 行 → 记录列起点
        if line.lstrip().startswith("----"):
            detected = _column_starts_from_dashes(line)
            if len(detected) in (2, 4):
                column_starts = detected
            continue

        # RATE 行 → 液/汽相流率（X 列奇数位 / Y 列偶数位）；RATE 行收尾块
        if _RATE_ROW_RE.match(line):
            if column_starts:
                vals = _slice_by_columns(line, column_starts)
                current.liquid_rates = vals[0::2]
                current.vapor_rates = vals[1::2]
            current = None
            continue

        # 组件行 → X/Y 按列切片
        m_comp = _COMP_ROW_RE.match(line)
        if m_comp and column_starts:
            values = _slice_by_columns(line, column_starts)
            current.rows.append(TrayCompositionRow(
                comp_no=int(m_comp.group(1)),
                comp_name=m_comp.group(2),
                x=values[0::2],
                y=values[1::2],
            ))
            continue

        # 空行：仅结束组件行区（RATE 行仍属本块），不重置块

    return blocks


__all__ = [
    "TrayCompositionRow",
    "TrayCompositions",
    "parse_tray_composition_blocks",
]