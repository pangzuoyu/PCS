"""P3.x SIM-37b/1: PRO/II 8.x 炼油版全量解析 — ASSAY + D86（6 parser 第 1 批）。

格式参考（spec V1.1 §3.3.X + sample/200FlexiCoking1.out）：
- ASSAY 声明：
    ASSAY CONVERSION=API94, CURVEFIT=IMPROVED, KVRECONCILE=TAILS
    CUTPOINTS TBPCUTS=30,650,23,DEFAULT
- D86 蒸馏曲线输出：
    D86 STREAM=1NAPHTHA, DATA=0,50/5,57/10,62/20,..., TEMP=C
  - 跨行 `&` + 下一行缩进续行
  - DATA 第一个数为起始 vol%（通常 0），后续「temp/vol」对
  - 末尾孤立 temp（如 190）+ 100%vol

Parser 产物：
- AssayDeclaration（conversion/curve_fit/kv_reconcile/cut_points_tbp_cuts/cut_points_default）
- D86Curve（stream_id/temp_unit/points 升序）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class AssayDeclaration:
    """PRO/II ASSAY 输入数据声明。

    字段：
    - conversion: 转换方法（API94/ASTM86/TBP/D86 等）
    - curve_fit: 曲线拟合方式（IMPROVED/NONE 等）
    - kv_reconcile: KV 调和方式（TAILS/NONE 等）
    - cut_points_tbp_cuts: TBP 切割点列表（如 [30, 650, 23]）
    - cut_points_default: TBPCUTS 含 DEFAULT 关键字
    """

    conversion: str
    curve_fit: str | None = None
    kv_reconcile: str | None = None
    cut_points_tbp_cuts: list[int] | None = None
    cut_points_default: bool = False


@dataclass
class D86Curve:
    """PRO/II ASTM D86 蒸馏曲线。

    字段：
    - stream_id: 物流 ID
    - temp_unit: 温度单位（C/F）
    - points: 蒸馏点列表 [(temp, vol_pct), ...]，按 vol_pct 升序
    """

    stream_id: str
    temp_unit: str = "C"
    points: list[tuple[float, float]] = field(default_factory=list)


# ----------------------------------------------------------------------------
# ASSAY 解析
# ----------------------------------------------------------------------------


def _join_continued_lines_simple(text: str) -> str:
    """PRO/II 续行拼接：行尾 `&` + 下一行拼接为单行。

    返回拼接后的行列表。
    """
    raw_lines = text.splitlines()
    joined: list[str] = []
    buf: list[str] = []
    for line in raw_lines:
        if buf:
            if line.rstrip().endswith("&"):
                buf.append(line.strip().rstrip("&").rstrip())
                continue
            buf.append(line.strip())
            joined.append(" ".join(buf))
            buf = []
        else:
            stripped = line.strip()
            if stripped.endswith("&"):
                buf.append(stripped.rstrip("&").rstrip())
                continue
            joined.append(line)
    if buf:
        joined.append(" ".join(buf))
    return "\n".join(joined)


def parse_assay_declarations(text: str) -> list[AssayDeclaration]:
    """解析 PRO/II ASSAY 输入数据声明。

    Args:
        text: .out 全文或片段

    Returns:
        AssayDeclaration 列表（按文本顺序）
    """
    joined = _join_continued_lines_simple(text)
    declarations: list[AssayDeclaration] = []
    pending: AssayDeclaration | None = None

    assay_re = re.compile(r"^\s*ASSAY\b\s*(.*)$", re.IGNORECASE)
    cutpoints_re = re.compile(
        r"^\s*CUTPOINTS\s+TBPCUTS\s*=\s*(.+)$",
        re.IGNORECASE,
    )
    kv_re = re.compile(r"^\s*(CONVERSION|CURVEFIT|KVRECONCILE)\s*=\s*([^,\s]+)",
                      re.IGNORECASE)

    for line in joined.splitlines():
        m_assay = assay_re.match(line)
        if m_assay:
            # 新声明 → 落盘上一个（如果有）
            if pending is not None:
                declarations.append(pending)
            rest = m_assay.group(1).strip()
            # 提取 CONVERSION/CURVEFIT/KVRECONCILE 三个键值
            conversion = None
            curve_fit = None
            kv_reconcile = None
            # 逐对扫描 KEY=VAL（用正则定位，每个键值后清掉匹配片段）
            scan = rest
            for _ in range(10):  # 安全上限
                m_kv = kv_re.match(scan)
                if not m_kv:
                    break
                key = m_kv.group(1).upper()
                val = m_kv.group(2).strip()
                if key == "CONVERSION":
                    conversion = val
                elif key == "CURVEFIT":
                    curve_fit = val
                elif key == "KVRECONCILE":
                    kv_reconcile = val
                # 推进：跳过这一对，继续扫描
                scan = scan[m_kv.end():].lstrip(",").lstrip()
            pending = AssayDeclaration(
                conversion=conversion or "",
                curve_fit=curve_fit,
                kv_reconcile=kv_reconcile,
                cut_points_tbp_cuts=None,
                cut_points_default=False,
            )
            continue

        m_cutpoints = cutpoints_re.match(line)
        if m_cutpoints and pending is not None:
            rest = m_cutpoints.group(1).strip()
            # TBPCUTS=N1,N2,N3[,DEFAULT]
            parts = [p.strip() for p in rest.split(",")]
            nums: list[int] = []
            default_flag = False
            for p in parts:
                if p.upper() == "DEFAULT":
                    default_flag = True
                else:
                    try:
                        nums.append(int(p))
                    except ValueError:
                        # 非数字，保留为「异常」标记 — 但契约中此处只取整数切割点
                        pass
            pending.cut_points_tbp_cuts = nums
            pending.cut_points_default = default_flag
            continue

    if pending is not None:
        declarations.append(pending)

    return declarations


# ----------------------------------------------------------------------------
# D86 解析
# ----------------------------------------------------------------------------


def parse_distillation_points(data_blob: str) -> list[tuple[float, float]]:
    """解析蒸馏曲线 DATA 段为 (temp, vol_pct) 点列（D86/TBP 同构复用）。

    格式：首 token 为起始 vol%（通常 0，可非 0，跳过），后续 temp/vol 对
    以 `/` 分隔；末尾孤立 temp 为 100% 末点。

    Args:
        data_blob: DATA= 之后的原始字符串（如 "0,50/5,57/10,...,190"）

    Returns:
        (temp, vol_pct) 列表；无法解析返回空 list
    """
    tokens = [t.strip() for t in data_blob.split(",") if t.strip()]
    if not tokens:
        return []

    points: list[tuple[float, float]] = []
    try:
        _initial_vol = float(tokens[0])  # 起始 vol%（跳过）
    except ValueError:
        return []
    rest = tokens[1:]
    i = 0
    while i < len(rest):
        tok = rest[i]
        if "/" in tok:
            ts, vs = tok.split("/", 1)
            try:
                points.append((float(ts), float(vs)))
            except ValueError:
                pass
            i += 1
        else:
            if i + 1 < len(rest) and "/" not in rest[i + 1]:
                # 两个孤立 token → (temp, vol) 末点对
                try:
                    points.append((float(tok), float(rest[i + 1])))
                except ValueError:
                    pass
                i += 2
            else:
                # 单孤立 temp → 100% 末点
                try:
                    points.append((float(tok), 100.0))
                except ValueError:
                    pass
                i += 1
    return points


def parse_d86_curves(text: str) -> list[D86Curve]:
    """解析 PRO/II D86 蒸馏曲线。

    Args:
        text: .out 全文或片段

    Returns:
        D86Curve 列表
    """
    joined = _join_continued_lines_simple(text)
    curves: list[D86Curve] = []

    # D86 行：开头 D86 关键字，后跟 STREAM=... DATA=... TEMP=...
    # DATA 段内含多个逗号（temp/vol 对分隔），用非贪婪 .+? 匹配到行尾可选 TEMP
    d86_re = re.compile(
        r"^\s*D86\s+STREAM\s*=\s*([^,\s]+)\s*,\s*DATA\s*=\s*(.+?)"
        r"(?:\s*,\s*TEMP\s*=\s*([CF]))?\s*$",
        re.IGNORECASE,
    )

    for line in joined.splitlines():
        m = d86_re.match(line)
        if not m:
            continue
        stream_id = m.group(1).strip()
        data_blob = m.group(2).strip()
        temp_unit = (m.group(3) or "C").upper()

        points = parse_distillation_points(data_blob)
        if not points:
            continue

        curves.append(D86Curve(
            stream_id=stream_id,
            temp_unit=temp_unit,
            points=points,
        ))

    return curves


__all__ = [
    "AssayDeclaration",
    "D86Curve",
    "parse_assay_declarations",
    "parse_d86_curves",
    "parse_distillation_points",
]