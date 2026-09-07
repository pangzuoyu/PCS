"""SYM 验证规则（SUP-002 §4.2/§7 派生 6 条）。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"


@dataclass
class SymValidationResult:
    rule_id: str
    severity: Severity
    message: str
    field: str | None = None


VALID_CATEGORIES = {"PROCESS", "UTILITY", "OFFSITE", "AMINE", "REFRIGERATION"}


class StreamSymbolValidator:
    @classmethod
    def validate(
        cls,
        data: dict[str, Any],
        *,
        project_existing_symbols: list[str] | None = None,
    ) -> list[SymValidationResult]:
        results: list[SymValidationResult] = []
        sym = (data.get("symbol") or "").strip()
        name = (data.get("name") or "").strip()
        category = (data.get("category") or "").strip()

        # SYM-V01 symbol 1-10 字符
        if not sym or len(sym) > 10:
            results.append(
                SymValidationResult(
                    "SYM-V01",
                    Severity.ERROR,
                    f"symbol {sym!r} 长度须 1-10 字符",
                    "symbol",
                )
            )

        # SYM-V02 name 非空
        if not name:
            results.append(
                SymValidationResult(
                    "SYM-V02",
                    Severity.ERROR,
                    "name 不能为空",
                    "name",
                )
            )

        # SYM-V03 项目内重名（仅项目级）
        if project_existing_symbols is not None and sym and sym in project_existing_symbols:
            results.append(
                SymValidationResult(
                    "SYM-V03",
                    Severity.ERROR,
                    f"项目内已存在符号 {sym}",
                    "symbol",
                )
            )

        # SYM-V04 category 不在白名单（warn）
        if category and category not in VALID_CATEGORIES:
            results.append(
                SymValidationResult(
                    "SYM-V04",
                    Severity.WARN,
                    f"category {category} 不在白名单 {sorted(VALID_CATEGORIES)}",
                    "category",
                )
            )

        return results

    @classmethod
    def validate_fork_snapshot(cls, snapshot: dict | None) -> SymValidationResult | None:
        """SYM-V05 fork 必须带完整快照。"""
        if not snapshot or not isinstance(snapshot, dict):
            return SymValidationResult(
                "SYM-V05",
                Severity.ERROR,
                "fork 后 snapshot_json 缺失或非字典",
                "snapshot_json",
            )
        required = {"symbol", "name"}
        missing = required - snapshot.keys()
        if missing:
            return SymValidationResult(
                "SYM-V05",
                Severity.ERROR,
                f"snapshot 缺字段 {sorted(missing)}",
                "snapshot_json",
            )
        return None

    @classmethod
    def has_errors(cls, results: list[SymValidationResult]) -> bool:
        return any(r.severity == Severity.ERROR for r in results)