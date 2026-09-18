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
        """SYM-V01..V04 规则校验（SUP-002 §4.2/§7 派生）。

        步骤：
        1. 取 data.symbol/name/category 并 strip（容忍空白输入）
        2. SYM-V01 ERROR：symbol 长度须 1-10 字符（空或 >10）
        3. SYM-V02 ERROR：name 不能为空
        4. SYM-V03 ERROR：项目内 symbol 重名（仅当传入
           project_existing_symbols 时检查；公司级跳过）
        5. SYM-V04 WARN：category 不在 VALID_CATEGORIES 白名单（不阻断）
        6. 返回 SymValidationResult 列表（按规则顺序；调用方按 severity 决定
           拦截/警告）

        不做 SQL 查重；project_existing_symbols 由 service 层预先查询注入。
        """
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