r"""P3.x SIM-38b/2: 塔盘数据全量 — TRAY RATING RESULTS 解析（SIM-38b 第 2 批）。

两版本格式（单位不同不区分，仅取数值）：
- PRO/II 4.17：TRAY RATING RESULTS，9 列
  TRAY VAPOR LIQUID VLOAD DIAM FF PRES_DROP GPM/LWI BACKUP_PCT
- PRO/II 8.x：TRAY RATING AT SELECTED DESIGN TRAY，10 列（FF 后多 NP）
  TRAY VAPOR LIQUID VLOAD DIAM FF NP PRES_DROP RATE BACKUP_PCT

段切换守卫精确枚举（bug-070 教训）：宽守卫 r'^TRAY\s' 会误杀
RATING 表自身列头行（TRAY VAPOR LIQUID...）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TrayRatingRow:
    """单塔板水力学核算行（9/10 列双格式）。"""

    tray: int
    vapor_rate: float
    liquid_rate: float
    vload: float
    diameter_mm: float
    ff: float
    pres_drop: float
    weir_rate: float
    backup_pct: float
    np: int | None = None  # 8.x 格式独有（通道数）


@dataclass
class UnitTrayRating:
    """单 UNIT 的 TRAY RATING 结果。"""

    unit_no: str
    unit_name: str
    unit_desc: str | None = None
    rows: list[TrayRatingRow] = field(default_factory=list)


def _try_floats(tokens: list[str]) -> list[float] | None:
    """全部 token 转 float；任一失败返回 None。"""
    try:
        return [float(t) for t in tokens]
    except ValueError:
        return None


def parse_tray_rating(text: str) -> list[UnitTrayRating]:
    """解析 .out 中全部 TRAY RATING 段（per UNIT，双版本格式）。

    状态机：UNIT 头归属；「TRAY RATING RESULTS」（4.17）/
    「TRAY RATING AT SELECTED DESIGN TRAY」（8.x）标记开表；
    数据行按 token 数识别（9 列 / 10 列）。

    Args:
        text: .out 全文或片段

    Returns:
        UnitTrayRating 列表（每遇到一次标记产生一项）
    """
    units: list[UnitTrayRating] = []
    current_unit: dict[str, str | None] = {"no": None, "name": None, "desc": None}
    active = False
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
            active = False
            continue

        stripped_upper = line.strip().upper()
        if stripped_upper in (
            "TRAY RATING RESULTS",
            "TRAY RATING AT SELECTED DESIGN TRAY",
        ):
            units.append(UnitTrayRating(
                unit_no=current_unit["no"] or "",
                unit_name=current_unit["name"] or "",
                unit_desc=current_unit["desc"],
            ))
            active = True
            continue
        # 兄弟段标题 → 退出表模式（精确枚举，防误杀列头行，bug-070）
        if re.match(
            r"^\s*TRAY\s+"
            r"(SIZING|RATES|TRANSPORT|ENTHALPIES|LOADING|COMPOSITIONS|SELECTION)",
            line,
            re.IGNORECASE,
        ):
            active = False
            continue
        if not active or not units:
            continue

        tokens = line.split()
        if len(tokens) not in (9, 10) or not int_re.match(tokens[0]):
            continue
        vals = _try_floats(tokens)
        if vals is None:
            continue

        if len(vals) == 10:
            # 8.x：tray vapor liquid vload diam ff np pres_drop weir backup
            row = TrayRatingRow(
                tray=int(vals[0]),
                vapor_rate=vals[1],
                liquid_rate=vals[2],
                vload=vals[3],
                diameter_mm=vals[4],
                ff=vals[5],
                np=int(vals[6]),
                pres_drop=vals[7],
                weir_rate=vals[8],
                backup_pct=vals[9],
            )
        else:
            # 4.17：tray vapor liquid vload diam ff pres_drop weir backup
            row = TrayRatingRow(
                tray=int(vals[0]),
                vapor_rate=vals[1],
                liquid_rate=vals[2],
                vload=vals[3],
                diameter_mm=vals[4],
                ff=vals[5],
                pres_drop=vals[6],
                weir_rate=vals[7],
                backup_pct=vals[8],
                np=None,
            )
        units[-1].rows.append(row)

    return units


__all__ = [
    "TrayRatingRow",
    "UnitTrayRating",
    "parse_tray_rating",
]