"""P3.x SIM-37b/3: PRO/II 8.x 炼油版全量解析 — REFSTREAM + TRAY SIZING（6 parser 第 3 批）。

格式参考（sample/huafeng140_FCC2015.out + 200FlexiCoking1.out）：
- REFSTREAM 输入声明（PROPERTY 行内参数）：
    PROPERTY STREAM=5R, REFSTREAM=5
    PROPERTY STREAM=17R, TEMPERATURE=270, REFSTREAM=17, RATE(M)=1000
  - REFSTREAM=<被引用物流>；可选 TEMPERATURE=/RATE(M|WT)= 覆盖
- TRAY SIZING 输出（per UNIT 两表）：
    UNIT 5, 'T204B', 'STRIPPER'  (Cont)
    TRAY SIZING MECHANICAL DATA  → section 配置（塔板号/程/间距/系数/型式/最小径）
    TRAY SIZING RESULTS          → per-tray 11 列（汽液负荷/设计径 FF/邻档/NP）
  - 无关段（DOWNCOMER/TRAY RATING 等）按列数 + 数值性自然跳过
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.proii_assay_d86_parser import _join_continued_lines_simple


@dataclass
class RefStreamDeclaration:
    """PRO/II 参考物流声明（PROPERTY 行内 REFSTREAM=）。

    字段：
    - stream_id: 新物流 ID（引用者）
    - ref_stream_id: 被引用物流 ID
    - temperature: 覆盖温度（可选）
    - rate: 覆盖流量（可选）
    - rate_basis: 流量基准（M/Wt，可选）
    """

    stream_id: str
    ref_stream_id: str
    temperature: float | None = None
    rate: float | None = None
    rate_basis: str | None = None


@dataclass
class TraySizingSection:
    """TRAY SIZING MECHANICAL DATA 单 section 配置行。"""

    section_no: int
    tray_numbers: str
    tray_passes: str
    tray_spacing_mm: float
    system_factor: float
    tray_type: str
    min_diameter_mm: float


@dataclass
class TraySizingResult:
    """TRAY SIZING RESULTS 单塔板行（11 列）。"""

    tray: int
    vapor_m3s: float
    liquid_m3s: float
    vload_m3s: float
    design_dia_mm: float
    design_ff: float
    next_smaller_dia_mm: float
    next_smaller_ff: float
    next_larger_dia_mm: float
    next_larger_ff: float
    np: int


@dataclass
class UnitTraySizing:
    """单 UNIT 的 TRAY SIZING 结果（MECHANICAL + RESULTS 两表）。"""

    unit_no: str
    unit_name: str
    unit_desc: str | None = None
    sections: list[TraySizingSection] = field(default_factory=list)
    results: list[TraySizingResult] = field(default_factory=list)


# ----------------------------------------------------------------------------
# REFSTREAM 解析
# ----------------------------------------------------------------------------


def parse_refstream_declarations(text: str) -> list[RefStreamDeclaration]:
    """解析 PROPERTY 行内的 REFSTREAM= 参考物流声明。

    Args:
        text: .out 全文或片段

    Returns:
        RefStreamDeclaration 列表（无 REFSTREAM 的 PROPERTY 行不产出）
    """
    joined = _join_continued_lines_simple(text)
    decls: list[RefStreamDeclaration] = []

    property_re = re.compile(
        r"^\s*PROPERTY\s+STREAM\s*=\s*([^,\s]+)\s*,\s*(.+)$",
        re.IGNORECASE,
    )
    refstream_re = re.compile(r"REFSTREAM\s*=\s*([^,\s]+)", re.IGNORECASE)
    temp_re = re.compile(r"TEMPERATURE\s*=\s*(-?[\d.]+)", re.IGNORECASE)
    rate_re = re.compile(r"RATE\s*\((M|WT)\)\s*=\s*(-?[\d.]+)", re.IGNORECASE)

    for line in joined.splitlines():
        m = property_re.match(line)
        if not m:
            continue
        stream_id = m.group(1).strip()
        rest = m.group(2)
        m_ref = refstream_re.search(rest)
        if not m_ref:
            continue

        temperature = None
        m_temp = temp_re.search(rest)
        if m_temp:
            temperature = float(m_temp.group(1))

        rate = None
        rate_basis = None
        m_rate = rate_re.search(rest)
        if m_rate:
            rate_basis = m_rate.group(1).upper()
            rate = float(m_rate.group(2))

        decls.append(RefStreamDeclaration(
            stream_id=stream_id,
            ref_stream_id=m_ref.group(1).strip(),
            temperature=temperature,
            rate=rate,
            rate_basis=rate_basis,
        ))

    return decls


# ----------------------------------------------------------------------------
# TRAY SIZING 解析
# ----------------------------------------------------------------------------


def _try_floats(tokens: list[str]) -> list[float] | None:
    """全部 token 转 float；任一失败返回 None。"""
    try:
        return [float(t) for t in tokens]
    except ValueError:
        return None


def parse_tray_sizing(text: str) -> list[UnitTraySizing]:
    """解析 .out 中全部 TRAY SIZING 块（per UNIT）。

    状态机：UNIT 头记录归属元数据；MECHANICAL DATA / RESULTS 标记切换
    表模式；数据行按列数 + 全数值性识别（非数据行自然跳过）。无关段
    （DOWNCOMER/TRAY RATING 等）行列数不符自动忽略。

    Args:
        text: .out 全文或片段

    Returns:
        UnitTraySizing 列表（每遇到一次 MECHANICAL DATA 产生一项）
    """
    units: list[UnitTraySizing] = []
    current_unit: dict[str, str | None] = {"no": None, "name": None, "desc": None}
    mode: str | None = None  # "mech" | "results" | None

    unit_re = re.compile(
        r"^\s*UNIT\s+(\d+)\s*,\s*'([^']+)'(?:\s*,\s*'([^']+)')?",
        re.IGNORECASE,
    )
    int_re = re.compile(r"^\d+$")

    for raw in text.splitlines():
        line = raw.rstrip()

        # UNIT 头：更新归属元数据
        m_unit = unit_re.match(line)
        if m_unit:
            current_unit = {
                "no": m_unit.group(1),
                "name": m_unit.group(2),
                "desc": m_unit.group(3),
            }
            mode = None
            continue

        # 表标记
        stripped_upper = line.strip().upper()
        if stripped_upper == "TRAY SIZING MECHANICAL DATA":
            units.append(UnitTraySizing(
                unit_no=current_unit["no"] or "",
                unit_name=current_unit["name"] or "",
                unit_desc=current_unit["desc"],
            ))
            mode = "mech"
            continue
        if stripped_upper == "TRAY SIZING RESULTS":
            mode = "results"
            continue
        # 其他 TRAY 段标题（RATING/DOWNCOMER/SELECTION/COMPOSITIONS/LOADING）
        # → 退出表模式防误收；注意不能匹配 RESULTS 表自己的列头行
        # （"TRAY VAPOR LIQUID ..."），故精确列出段标题动词
        if re.match(
            r"^\s*TRAY\s+"
            r"(SIZING\s+DOWNCOMER|RATING|SELECTION|COMPOSITIONS|LOADING)",
            line,
            re.IGNORECASE,
        ):
            mode = None
            continue
        if not units or mode is None:
            continue

        tokens = line.split()
        unit = units[-1]

        if mode == "mech":
            # SECTION <tray 范围 tokens...> PASSES SPACING FACTOR TYPE MIN_DIA
            # 尾 5 列布局：[passes, spacing, factor, type, min_dia]
            if len(tokens) < 7 or not int_re.match(tokens[0]):
                continue
            tail = tokens[-5:]
            nums = _try_floats([tail[1], tail[2], tail[4]])
            if nums is None:
                continue
            spacing, factor, min_dia = nums
            unit.sections.append(TraySizingSection(
                section_no=int(tokens[0]),
                tray_numbers=" ".join(tokens[1:-5]),
                tray_passes=tail[0],
                tray_spacing_mm=spacing,
                system_factor=factor,
                tray_type=tail[3].upper(),
                min_diameter_mm=min_dia,
            ))
        elif mode == "results":
            # TRAY VAPOR LIQUID VLOAD DIA FF SM_DIA SM_FF LG_DIA LG_FF NP
            if len(tokens) != 11 or not int_re.match(tokens[0]):
                continue
            vals = _try_floats(tokens)
            if vals is None:
                continue
            unit.results.append(TraySizingResult(
                tray=int(vals[0]),
                vapor_m3s=vals[1],
                liquid_m3s=vals[2],
                vload_m3s=vals[3],
                design_dia_mm=vals[4],
                design_ff=vals[5],
                next_smaller_dia_mm=vals[6],
                next_smaller_ff=vals[7],
                next_larger_dia_mm=vals[8],
                next_larger_ff=vals[9],
                np=int(vals[10]),
            ))

    return units


__all__ = [
    "RefStreamDeclaration",
    "TraySizingSection",
    "TraySizingResult",
    "UnitTraySizing",
    "parse_refstream_declarations",
    "parse_tray_sizing",
]