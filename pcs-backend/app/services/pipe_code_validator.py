"""FMT 验证规则（SUP-002 §12，9 条）。

| ID | 规则 | 严重度 |
|----|------|--------|
| FMT-V01 | 恰有一个 auto_increment 段 | ERROR |
| FMT-V02 | 恰有一个 stream_symbol 段 | ERROR |
| FMT-V03 | 分段 key 唯一 | ERROR |
| FMT-V04 | 相邻段不能都无分隔符 | ERROR |
| FMT-V05 | 总长度 ≤ 50 字符 | ERROR |
| FMT-V06 | 枚举段 values 非空 | ERROR |
| FMT-V07 | stream_symbol 段 key 在项目有效符号表内 | ERROR |
| FMT-V08 | 项目级配置名（project_id 内）唯一 | ERROR |
| FMT-V09 | auto_increment 段建议位于末位/靠近末位 | WARN |
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"


@dataclass
class FmtValidationResult:
    rule_id: str
    severity: Severity
    message: str
    field: str | None = None


_VALID_SEGMENT_TYPES = {
    "stream_symbol",
    "enum",
    "auto_increment",
    "free_text",
    "constant",
    "delimiter",
}


class PipeCodeValidator:
    """FMT 9 条规则 + helper。"""

    @classmethod
    def validate_format_definition(
        cls,
        fmt: dict,
        *,
        project_symbol_keys: Iterable[str] | None = None,
        existing_config_names: Iterable[str] | None = None,
        project_config_name: str | None = None,
    ) -> list[FmtValidationResult]:
        results: list[FmtValidationResult] = []
        if not isinstance(fmt, dict):
            return [FmtValidationResult(
                "FMT-V01", Severity.ERROR,
                "format_definition_json 必须是 dict", None,
            )]
        segments = fmt.get("segments") or []
        separator = fmt.get("separator", "") or ""

        # FMT-V01 恰有一个 auto_increment
        ai = [s for s in segments if s.get("type") == "auto_increment"]
        if len(ai) != 1:
            results.append(FmtValidationResult(
                "FMT-V01", Severity.ERROR,
                f"auto_increment 段必须恰有一个，实际 {len(ai)}", "segments",
            ))

        # FMT-V02 恰有一个 stream_symbol
        ss = [s for s in segments if s.get("type") == "stream_symbol"]
        if len(ss) != 1:
            results.append(FmtValidationResult(
                "FMT-V02", Severity.ERROR,
                f"stream_symbol 段必须恰有一个，实际 {len(ss)}", "segments",
            ))

        # FMT-V03 分段 key 唯一
        keys = [s.get("key") for s in segments if s.get("key")]
        dups = sorted({k for k in keys if keys.count(k) > 1})
        if dups:
            results.append(FmtValidationResult(
                "FMT-V03", Severity.ERROR,
                f"分段 key 重复 {dups}", "segments",
            ))

        # FMT-V04 相邻段不能都无分隔符（delimiter 段本身是分隔符，跳过）
        for i in range(len(segments) - 1):
            cur, nxt = segments[i], segments[i + 1]
            if cur.get("type") == "delimiter" or nxt.get("type") == "delimiter":
                continue
            cur_sep = cur.get("separator", separator)
            if not cur_sep:
                results.append(FmtValidationResult(
                    "FMT-V04", Severity.ERROR,
                    f"相邻段 {cur.get('key')!s} / {nxt.get('key')!s} 缺分隔符",
                    "segments",
                ))

        # FMT-V05 总长度 ≤ 50（按段长累加 + 段间分隔符）
        total = 0
        if segments:
            total += sum(
                int(s.get("length", 1) or 1)
                for s in segments
                if s.get("type") != "delimiter"
            )
            total += len(str(separator)) * max(0, len(segments) - 1)
        if total > 50:
            results.append(FmtValidationResult(
                "FMT-V05", Severity.ERROR,
                f"格式总长度 {total} > 50", "segments",
            ))

        # FMT-V06 枚举段 values 非空
        for s in segments:
            if s.get("type") == "enum" and not s.get("values"):
                results.append(FmtValidationResult(
                    "FMT-V06", Severity.ERROR,
                    f"枚举段 {s.get('key')!s} values 不能为空", s.get("key"),
                ))

        # FMT-V07 stream_symbol 段 key 在项目有效符号表内
        if project_symbol_keys is not None and ss:
            sym_key = ss[0].get("key")
            if sym_key and sym_key not in project_symbol_keys:
                results.append(FmtValidationResult(
                    "FMT-V07", Severity.ERROR,
                    f"stream_symbol 段 {sym_key!s} 不在项目有效符号表", sym_key,
                ))

        # FMT-V08 项目级配置名（project_id 内）唯一
        if (
            existing_config_names is not None
            and project_config_name
            and project_config_name in existing_config_names
        ):
            results.append(FmtValidationResult(
                "FMT-V08", Severity.ERROR,
                f"项目内已存在配置名 {project_config_name}", "config_name",
            ))

        # FMT-V09 auto_increment 段建议位于末位或靠近末位（距离末位 ≤ 2）
        if ai:
            ai_pos = next(
                (i for i, s in enumerate(segments) if s.get("type") == "auto_increment"),
                -1,
            )
            # delimiter 段算"无意义"占位，仍按其在数组中位置算
            if ai_pos < len(segments) - 2:
                results.append(FmtValidationResult(
                    "FMT-V09", Severity.WARN,
                    f"auto_increment 段位于位置 {ai_pos + 1}，建议末位或靠近末位",
                    "segments",
                ))

        return results

    @classmethod
    def has_errors(cls, results: list[FmtValidationResult]) -> bool:
        return any(r.severity == Severity.ERROR for r in results)


__all__ = [
    "FmtValidationResult",
    "PipeCodeValidator",
    "Severity",
]
