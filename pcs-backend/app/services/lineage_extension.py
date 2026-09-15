"""P4-TASK0 lineage D4/D5 扩展 helper（ADR-0031 残余）。

DataLineage 表四列扩展（写入路径）：
- record_hash_at_track：本次收口时 record.record_hash
- source_record_hash：上游 record_hash（无上游时退化 = record_hash）
- formula_version_at_track：本次公式版本
- config_version：上游配置版本（占位字段，本批未传）

设计要点：
- 纯函数式更新（不改 finalize_calc_record 既有契约），调用方在每次
  track 后调用本 helper 补字段。
- 与 record_hash 写入路径解耦：D4/D5 是 lineage 元数据，hash 写入是
  记录属性 — 两者互不影响。
"""
from __future__ import annotations

from typing import Any, Protocol


class _HasHash(Protocol):
    record_hash: str


def attach_lineage_d45(
    lineage_entry: Any,
    *,
    record: _HasHash,
    formula_version: str,
    source_record_hash: str | None = None,
    config_version: str | None = None,
) -> None:
    """向 DataLineage 行注入 P4-TASK0 D4/D5 字段。

    Args:
        lineage_entry: 已 add() 但未 commit 的 DataLineage 行
        record: 收口的源 record（必须已含 record_hash）
        formula_version: 本次收口公式版本
        source_record_hash: 上游 record_hash；None 时退化为 record_hash
        config_version: 上游配置版本；本批占位（多数调用方不传）

    副作用：直接修改 lineage_entry 的四个属性（不 commit）。
    """
    lineage_entry.record_hash_at_track = record.record_hash
    lineage_entry.source_record_hash = (
        source_record_hash if source_record_hash is not None else record.record_hash
    )
    lineage_entry.formula_version_at_track = formula_version
    lineage_entry.config_version = config_version


__all__ = ["attach_lineage_d45"]
