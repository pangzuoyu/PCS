"""P3.x SIM-37b/2: PRO/II 8.x 炼油版全量解析 — TBP + LIGHTEND（6 parser 第 2 批）。

格式参考（sample/200FlexiCoking1.out + huafeng140_FCC2015.out）：
- TBP 输入声明（与 D86 同构，复用 parse_distillation_points）：
    TBP STREAM=1SLURRYR, DATA=0,400/10,430/30,...,95,698, TEMP=C
  - DATA 首 token 起始 vol%（可非 0，如 huafeng FO1 DATA=5,...）
- LIGHTEND 轻端分析：
    LIGHTEND STREAM=1C, COMPOSITION(WT)=19,0.9/20,4.51/.../26,0.41, &
         PERCENT(WT)=17.51, NORMALIZE
  - 组件对 comp_id,value（/ 分隔）
  - 可选 PERCENT(WT)=（轻端总质量百分数）+ NORMALIZE 关键字
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.proii_assay_d86_parser import (
    _join_continued_lines_simple,
    parse_distillation_points,
)


@dataclass
class TBPCurve:
    """PRO/II 实沸点 (TBP) 蒸馏曲线。

    字段：
    - stream_id: 物流 ID
    - temp_unit: 温度单位（C/F）
    - points: 蒸馏点列表 [(temp, vol_pct), ...]，按 vol_pct 升序
    """

    stream_id: str
    temp_unit: str = "C"
    points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class LightendComposition:
    """PRO/II LIGHTEND 轻端分析。

    字段：
    - stream_id: 物流 ID
    - basis: 组成基准（WT/M）
    - components: 组件对 [(comp_id, value), ...]
    - percent_wt: 轻端总质量百分数（PERCENT(WT)=，可选）
    - normalized: 是否含 NORMALIZE 关键字
    """

    stream_id: str
    basis: str = "WT"
    components: list[tuple[int, float]] = field(default_factory=list)
    percent_wt: float | None = None
    normalized: bool = False


# ----------------------------------------------------------------------------
# TBP 解析
# ----------------------------------------------------------------------------


def parse_tbp_curves(text: str) -> list[TBPCurve]:
    """解析 PRO/II TBP 蒸馏曲线输入声明。

    Args:
        text: .out 全文或片段

    Returns:
        TBPCurve 列表
    """
    joined = _join_continued_lines_simple(text)
    curves: list[TBPCurve] = []

    # 与 D86 同构：DATA 段多逗号非贪婪匹配到行尾可选 TEMP
    tbp_re = re.compile(
        r"^\s*TBP\s+STREAM\s*=\s*([^,\s]+)\s*,\s*DATA\s*=\s*(.+?)"
        r"(?:\s*,\s*TEMP\s*=\s*([CF]))?\s*$",
        re.IGNORECASE,
    )

    for line in joined.splitlines():
        m = tbp_re.match(line)
        if not m:
            continue
        stream_id = m.group(1).strip()
        data_blob = m.group(2).strip()
        temp_unit = (m.group(3) or "C").upper()

        points = parse_distillation_points(data_blob)
        if not points:
            continue

        curves.append(TBPCurve(
            stream_id=stream_id,
            temp_unit=temp_unit,
            points=points,
        ))

    return curves


# ----------------------------------------------------------------------------
# LIGHTEND 解析
# ----------------------------------------------------------------------------


def parse_lightend_compositions(text: str) -> list[LightendComposition]:
    """解析 PRO/II LIGHTEND 轻端分析声明。

    Args:
        text: .out 全文或片段

    Returns:
        LightendComposition 列表
    """
    joined = _join_continued_lines_simple(text)
    results: list[LightendComposition] = []

    lightend_re = re.compile(
        r"^\s*LIGHTEND\s+STREAM\s*=\s*([^,\s]+)\s*,\s*"
        r"COMPOSITION\((WT|M)\)\s*=\s*(.+?)"
        r"(?:\s*,\s*PERCENT\(WT\)\s*=\s*([\d.]+))?"
        r"(?:\s*,\s*(NORMALIZE))?\s*$",
        re.IGNORECASE,
    )

    for line in joined.splitlines():
        m = lightend_re.match(line)
        if not m:
            continue
        stream_id = m.group(1).strip()
        basis = m.group(2).upper()
        comp_blob = m.group(3).strip()
        percent_wt = float(m.group(4)) if m.group(4) else None
        normalized = m.group(5) is not None

        # 组件对：comp_id,value / comp_id,value / ...
        components: list[tuple[int, float]] = []
        for pair in comp_blob.split("/"):
            pair = pair.strip()
            if not pair:
                continue
            parts = pair.split(",")
            if len(parts) != 2:
                continue
            try:
                components.append((int(parts[0]), float(parts[1])))
            except ValueError:
                continue

        results.append(LightendComposition(
            stream_id=stream_id,
            basis=basis,
            components=components,
            percent_wt=percent_wt,
            normalized=normalized,
        ))

    return results


__all__ = [
    "TBPCurve",
    "LightendComposition",
    "parse_tbp_curves",
    "parse_lightend_compositions",
]