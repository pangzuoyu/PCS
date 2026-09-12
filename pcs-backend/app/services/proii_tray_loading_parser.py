"""P3.x SIM-38b/1: 塔盘数据全量 — TRAY LOADING REPORT 解析（SIM-38b 第 1 批）。

格式参考（sample/proii .out 4.17）：
- 表 A：VAPOR TO TRAY + LIQUID FROM TRAY（12 数值列）
- 表 B：VAPOR FROM TRAY + LIQUID TO TRAY（列同构）
- vapor 6 列：TEMP/PRESSURE/MW/RATE/DENSITY/VISCOSITY
- liquid 6 列：TEMP/MW/RATE/DENSITY/VISCOSITY/SURFACE TENSION
- 特殊行：REBOILER（无 vapor 值）/ CONDENSER（无 liquid 值）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class VaporLoading:
    """vapor 侧 6 列。"""

    temp_c: float
    pressure: float
    mw: float
    rate: float
    density: float
    viscosity: float


@dataclass
class LiquidLoading:
    """liquid 侧 6 列。"""

    temp_c: float
    mw: float
    rate: float
    density: float
    viscosity: float
    surface_tension: float


@dataclass
class TrayLoadingRow:
    """单塔板行（归属表 A 或表 B，由 UnitTrayLoading 容器区分）。"""

    tray: int
    label: str | None = None  # REBOILER / CONDENSER / None
    vapor: VaporLoading | None = None
    liquid: LiquidLoading | None = None


@dataclass
class UnitTrayLoading:
    """单 UNIT 的 TRAY LOADING REPORT（双子表）。"""

    unit_no: str
    unit_name: str
    unit_desc: str | None = None
    vapor_to_tray: list[TrayLoadingRow] = field(default_factory=list)
    vapor_from_tray: list[TrayLoadingRow] = field(default_factory=list)


def _try_floats(tokens: list[str]) -> list[float] | None:
    """全部 token 转 float；任一失败返回 None。"""
    try:
        return [float(t) for t in tokens]
    except ValueError:
        return None


def _parse_vapor(vals: list[float]) -> VaporLoading:
    return VaporLoading(
        temp_c=vals[0], pressure=vals[1], mw=vals[2],
        rate=vals[3], density=vals[4], viscosity=vals[5],
    )


def _parse_liquid(vals: list[float]) -> LiquidLoading:
    return LiquidLoading(
        temp_c=vals[0], mw=vals[1], rate=vals[2],
        density=vals[3], viscosity=vals[4], surface_tension=vals[5],
    )


def parse_tray_loading(text: str) -> list[UnitTrayLoading]:
    """解析 .out 中全部 TRAY LOADING REPORT（per UNIT）。

    状态机：UNIT 头归属；REPORT 标记开块；「VAPOR TO TRAY」/
    「VAPOR FROM TRAY」表头切换子表模式；数据行按 token 数识别
    （满行 13 / 特殊行 8 含 REBOILER|CONDENSER 关键字）。

    Args:
        text: .out 全文或片段

    Returns:
        UnitTrayLoading 列表（每遇到一次 REPORT 标记产生一项）
    """
    units: list[UnitTrayLoading] = []
    current_unit: dict[str, str | None] = {"no": None, "name": None, "desc": None}
    mode: str | None = None  # "to" | "from" | None
    int_re = re.compile(r"^\d+$")

    unit_re = re.compile(
        r"^\s*UNIT\s+(\d+)\s*,\s*'([^']+)'(?:\s*,\s*'([^']+)')?",
        re.IGNORECASE,
    )

    for raw in text.splitlines():
        line = raw.rstrip()

        m_unit = unit_re.match(line)
        if m_unit:
            current_unit = {
                "no": m_unit.group(1),
                "name": m_unit.group(2),
                "desc": m_unit.group(3),
            }
            mode = None
            continue

        stripped_upper = line.strip().upper()
        if stripped_upper == "TRAY LOADING REPORT":
            units.append(UnitTrayLoading(
                unit_no=current_unit["no"] or "",
                unit_name=current_unit["name"] or "",
                unit_desc=current_unit["desc"],
            ))
            mode = None
            continue
        if not units:
            continue

        # 子表头：含 VAPOR TO/FROM TRAY 关键词的分组行
        if "VAPOR TO TRAY" in stripped_upper:
            mode = "to"
            continue
        if "VAPOR FROM TRAY" in stripped_upper:
            mode = "from"
            continue
        if mode is None:
            continue

        tokens = line.split()
        if len(tokens) < 8 or not int_re.match(tokens[0]):
            continue
        unit = units[-1]
        tray = int(tokens[0])

        if "REBOILER" in stripped_upper:
            vals = _try_floats(tokens[-6:])
            if vals is None:
                continue
            row = TrayLoadingRow(
                tray=tray, label="REBOILER",
                vapor=None, liquid=_parse_liquid(vals),
            )
        elif "CONDENSER" in stripped_upper:
            vals = _try_floats(tokens[1:7])
            if vals is None:
                continue
            row = TrayLoadingRow(
                tray=tray, label="CONDENSER",
                vapor=_parse_vapor(vals), liquid=None,
            )
        else:
            if len(tokens) != 13:
                continue
            v_vals = _try_floats(tokens[1:7])
            l_vals = _try_floats(tokens[7:13])
            if v_vals is None or l_vals is None:
                continue
            row = TrayLoadingRow(
                tray=tray, label=None,
                vapor=_parse_vapor(v_vals), liquid=_parse_liquid(l_vals),
            )

        if mode == "to":
            unit.vapor_to_tray.append(row)
        else:
            unit.vapor_from_tray.append(row)

    return units


__all__ = [
    "VaporLoading",
    "LiquidLoading",
    "TrayLoadingRow",
    "UnitTrayLoading",
    "parse_tray_loading",
]