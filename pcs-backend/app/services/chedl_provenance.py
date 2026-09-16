"""ChEDL 包装层 provenance（Task 26 + V1.9 GSTACK P2 provenance 结构化）。

ChEDLProvenance 是 frozen dataclass，记录每个 ChEDL 包装函数的运行时元数据：
- chEDL_function: 原始 ChEDL 函数完整名（如 "fluids.separator.v_Souders_Brown"）
- chEDL_version: 锁定的 ChEDL 版本（如 "1.3.1"）
- known_limitations: 已知限制（用户决策依据，至少 1 项）
- fallback_available: 是否有 fallback（true 时 chEDL_function 仍指向原函数）
- fallback_formula_ref: fallback 实现追溯（fallback_available=True 时必填）

Provenance 是不可变快照（frozen），用于：
1. 可观测接口（get_chedl_provenance()）
2. 升级流程决策依据（ADR-0030 决策 8 触发条件之一）
3. 公式溯源字段（formula_ref.source 关联）

关联：
- ADR-0030 V1.1 accepted（决策 5 dir() 核验 + 决策 8 升级流程）
- V1.8 F-13-2 ChEDL 包装层
- V1.9 GSTACK P0/P2（P0 时序修正：包装层在 Task 26 显式创建；P2 provenance 结构化）
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChEDLProvenance:
    """ChEDL 包装函数 provenance 元数据（不可变快照）。"""

    chEDL_function: str
    chEDL_version: str
    known_limitations: list[str] = field(default_factory=list)
    fallback_available: bool = False
    fallback_formula_ref: str | None = None


__all__ = ["ChEDLProvenance"]