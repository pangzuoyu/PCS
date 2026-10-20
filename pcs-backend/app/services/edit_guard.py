"""编辑冲突 guard 的**能力声明**（ADR-0048 §⑥）。

P9A-4 的分工：
- **D1（本文件当前内容）**：静态声明 —— 每张可编辑表有哪些并发令牌。
- **D2**：阶梯实现 —— `check_conflict` / `record_edit_audit` / 409 契约。

## 为什么用显式映射，不用 ORM 反射

ADR-0048 §⑥ 记的教训：`cost_est_results` 曾经「登记在
`RECORD_TYPE_REGISTRY` 里、却没有 `record_hash` 列」——
反射把「ORM 有列」当成「表有能力」，而两者可能不一致。

⇒ **能力必须显式声明**。漏登记要抛 `UnregisteredTableError`
（`check_conflict` 不得静默走 `no_baseline` —— 那等于给没保护的东西
发「无冲突」通行证）。

## 两张表的区别（别混）

| 常量 | 含义 | 变更时机 |
|---|---|---|
| `TABLE_CAPABILITIES` | 该表**有**哪些并发令牌（能力） | 加列 / 改 schema 时 |
| `GUARDED_TABLES` | 该表的保存路径**已接上** DB 层冲突检测（接线） | D2 接线时 |

「有能力」≠「已接线」：D2 落地前，6 张可编辑表都有 `record_hash`（能力），
但**保存路径还没接** guard（未接线）⇒ 降级横幅必须按 `GUARDED_TABLES`
说话（§⑤ 的横幅是给用户的**事实陈述**，不是能力表）。
D2 的契约测试断言两张表**逐项相等** ⇒ 不会漂移。
"""
from __future__ import annotations

from dataclasses import dataclass


class UnregisteredTableError(LookupError):
    """表没有登记并发令牌能力。

    抛出而不是降级：`check_conflict` 对未登记的表**静默走 no_baseline**
    等于给没保护的东西发「无冲突」通行证（ADR-0048 §⑥）。
    """


@dataclass(frozen=True)
class TableCapability:
    """一张可编辑表的并发令牌能力（ADR-0048 §⑥）。"""

    has_record_hash: bool
    has_updated_at: bool


#: 全部有手动编辑端点的结果表（实测：`grep -rn '@router\.\(patch\|put\)' app/api/v1/*.py`）。
#: ⚠️ **只登记有编辑路径的表** —— 其余表保护的是一个不存在的并发。
TABLE_CAPABILITIES: dict[str, TableCapability] = {
    "cooling_tower_results": TableCapability(has_record_hash=True, has_updated_at=True),
    "filtration_results": TableCapability(has_record_hash=True, has_updated_at=True),
    "flare_system_results": TableCapability(has_record_hash=True, has_updated_at=True),
    "open_channel_results": TableCapability(has_record_hash=True, has_updated_at=True),
    "psychro_results": TableCapability(has_record_hash=True, has_updated_at=True),
    # cost_est_results：P9A-4 D0 刚补上 record_hash，但**没有 updated_at**
    # ⇒ 退化阶梯对它只有**一档**（record_hash），没有第二档兜底。
    "cost_est_results": TableCapability(has_record_hash=True, has_updated_at=False),
}

#: 保存路径**已接上** DB 层冲突检测的表。
#:
#: ⚠️ D1 阶段**为空** —— D2 还没接线 ⇒ 此刻**任何**表的保存路径都没有
#: 并发检出能力 ⇒ 降级横幅对所有表都要写「本次编辑无冲突检测」
#: （ADR-0048 §⑤：这不是可选的措辞优化）。
#: D2 接线时把 6 张表登记进来，届时横幅自动精确化。
GUARDED_TABLES: frozenset[str] = frozenset()


def capability_of(record_type: str) -> TableCapability:
    """查表能力。**未登记 ⇒ 抛 `UnregisteredTableError`**（不得静默降级）。"""
    try:
        return TABLE_CAPABILITIES[record_type]
    except KeyError as e:
        raise UnregisteredTableError(
            f"表 {record_type!r} 未登记并发令牌能力 —— "
            "登记前不得给它做冲突判定（ADR-0048 §⑥）"
        ) from e


def has_conflict_detection(record_type: str) -> bool:
    """该表的保存路径**是否已接上**冲突检测（降级横幅用）。"""
    return record_type in GUARDED_TABLES


__all__ = [
    "GUARDED_TABLES",
    "TABLE_CAPABILITIES",
    "TableCapability",
    "UnregisteredTableError",
    "capability_of",
    "has_conflict_detection",
]
