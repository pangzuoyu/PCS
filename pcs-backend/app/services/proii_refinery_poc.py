"""P3.x SIM-37a: PRO/II 8.x 炼油版 PoC — 关键字识别。

PoC 范围：识别 PRO/II 8.x 炼油版报告中的 7 类关键字（+ 1 类输出段）：
- ASSAY（输入数据声明）
- D86（ASTM D86 蒸馏曲线）
- TBP（实沸点蒸馏曲线）
- LIGHTEND（轻端分析）
- REFSTREAM（参考物流）
- TRAY SIZING（塔盘尺寸计算）
- REFINERY PROCESSOR（炼油处理器属性集）
- STREAM TBP/ASTM CURVES（输出段，深度解析已存在 SIM-20d）

PoC 产物：
- RefinerySection enum（8 类）
- RefineryReport dataclass（含 sections/counts/line_numbers/source_file + to_dict）
- RefinerySectionDetector.detect_from_text / detect_from_file

注意：本模块仅关键字识别（PoC）。深度解析留待 SIM-37b（4d 全量）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar


class RefinerySection(str, Enum):
    """PRO/II 8.x 炼油版 8 类关键字枚举。"""

    ASSAY = "ASSAY"
    D86 = "D86"
    TBP = "TBP"
    LIGHTEND = "LIGHTEND"
    REFSTREAM = "REFSTREAM"
    TRAY_SIZING = "TRAY_SIZING"
    REFINERY_PROCESSOR = "REFINERY_PROCESSOR"
    TBP_ASTM_CURVES = "TBP_ASTM_CURVES"


# 关键字识别表（每类关键字一个或多个识别模式，作为子串在大写化行中匹配）。
# 注：ASSAY/D86/TBP/LIGHTEND/REFSTREAM/REFINERY_PROCESSOR 关键字为独立行，
# 含前后空白即可；TRAY SIZING 含 1 空格；TBP/ASTM CURVES 含 1 斜杠。
REFINERY_SECTION_KEYWORDS: dict[RefinerySection, tuple[str, ...]] = {
    RefinerySection.ASSAY: ("ASSAY",),
    RefinerySection.D86: ("D86",),
    RefinerySection.TBP: ("TBP",),
    RefinerySection.LIGHTEND: ("LIGHTEND",),
    RefinerySection.REFSTREAM: ("REFSTREAM",),
    RefinerySection.TRAY_SIZING: ("TRAY SIZING",),
    RefinerySection.REFINERY_PROCESSOR: ("REFINERY PROCESSOR",),
    RefinerySection.TBP_ASTM_CURVES: ("STREAM TBP/ASTM CURVES",),
}


@dataclass
class RefineryReport:
    """炼油版识别报告 dataclass。

    字段：
    - sections: 识别到的 section 集合（去重）
    - counts: 每个 section 命中次数（多页 TRAY SIZING 计数）
    - line_numbers: 每个 section 首次出现的 1-based 行号（调试定位用）
    - source_file: 来源文件路径（可选）

    派生属性：
    - has_refinery: sections 非空
    """

    sections: set[RefinerySection] = field(default_factory=set)
    counts: dict[RefinerySection, int] = field(default_factory=dict)
    line_numbers: dict[RefinerySection, int] = field(default_factory=dict)
    source_file: str | None = None

    @property
    def has_refinery(self) -> bool:
        """True iff 至少识别到一个炼油关键字。"""
        return bool(self.sections)

    def to_dict(self) -> dict:
        """JSON 序列化友好字典（sections 排序，counts/line_numbers 按 enum 排序）。"""
        return {
            "sections": sorted(s.value for s in self.sections),
            "counts": {s.value: self.counts.get(s, 0) for s in RefinerySection},
            "line_numbers": {
                s.value: self.line_numbers[s]
                for s in RefinerySection
                if s in self.line_numbers
            },
            "source_file": self.source_file,
            "has_refinery": self.has_refinery,
        }


class RefinerySectionDetector:
    """PRO/II 炼油版关键字识别器（PoC）。"""

    # 优先级：长的关键字优先匹配，避免 TBP 子串误吃 TBP/ASTM CURVES 的情形
    # 注意：先尝试 STREAM TBP/ASTM CURVES → 命中即归类到 TBP_ASTM_CURVES；
    # 再尝试 ASSAY → 注意 ASSAY 子串可能出现在 ASTM（区分大小写）— 我们大小写不敏感
    # 但优先匹配多词关键字以避歧义。
    _SECTION_ORDER: ClassVar[tuple[RefinerySection, ...]] = (
        RefinerySection.TBP_ASTM_CURVES,  # STREAM TBP/ASTM CURVES 必须先于 TBP
        RefinerySection.REFINERY_PROCESSOR,  # REFINERY PROCESSOR 必须先于 REFINERY 类
        RefinerySection.TRAY_SIZING,  # TRAY SIZING 必须先于单 TRAY（防误）
        RefinerySection.LIGHTEND,
        RefinerySection.REFSTREAM,
        RefinerySection.ASSAY,
        RefinerySection.D86,
        RefinerySection.TBP,
    )

    @classmethod
    def _classify_line(cls, raw_line: str) -> RefinerySection | None:
        """对单行文本进行关键字分类；返回首个匹配的 section 或 None。

        大小写不敏感（PRO/II 关键字虽常大写，但用户 PoC 文本可能含小写样本）。
        """
        # 移除首尾空白 + 大写化
        s = raw_line.strip().upper()
        if not s:
            return None
        for section in cls._SECTION_ORDER:
            for kw in REFINERY_SECTION_KEYWORDS[section]:
                # 使用单词边界匹配以避免误识别：
                # - ASSAY 必须独立行（行首或前面非字母），不被 ASSAYLIB 误吃
                # - D86 必须独立行，不被 AD860 误吃
                # 实现：检查行首是否为关键字起始，且关键字结束位置为行尾空白/换行/标点
                idx = s.find(kw)
                if idx == -1:
                    continue
                # 验证前缀：行首或非字母
                if idx > 0 and s[idx - 1].isalpha():
                    continue
                # 验证后缀：行尾或非字母
                end = idx + len(kw)
                if end < len(s) and s[end].isalpha():
                    continue
                return section
        return None

    @classmethod
    def detect_from_text(cls, text: str, *, source_file: str | None = None) -> RefineryReport:
        """从文本中识别炼油关键字。"""
        sections: set[RefinerySection] = set()
        counts: dict[RefinerySection, int] = {}
        line_numbers: dict[RefinerySection, int] = {}

        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            section = cls._classify_line(raw_line)
            if section is None:
                continue
            sections.add(section)
            counts[section] = counts.get(section, 0) + 1
            # 仅记录首现行号
            line_numbers.setdefault(section, lineno)

        return RefineryReport(
            sections=sections,
            counts=counts,
            line_numbers=line_numbers,
            source_file=source_file,
        )

    @classmethod
    def detect_from_file(cls, file_path: Path | str) -> RefineryReport:
        """从文件中识别炼油关键字。"""
        path = Path(file_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        return cls.detect_from_text(text, source_file=str(path))


__all__ = [
    "RefinerySection",
    "REFINERY_SECTION_KEYWORDS",
    "RefineryReport",
    "RefinerySectionDetector",
]