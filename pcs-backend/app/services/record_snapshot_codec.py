"""记录快照的**数据编解码**（TODO-087）。

## 为什么有这个模块

`record_change_snapshots.data_snapshot_json` 此前**恒为 `{}`** ——
`state_machine._create_snapshot_if_needed` 建快照时**只写哈希**，不写数据
⇒「撤销 / 放弃变更」时快照里**没有任何东西可恢复** ⇒
**撤销不撤销任何东西**（记录带着改动回到 CHECKED）。

⇒ 本模块把「记录的业务数据」编码进 JSONB，并在恢复时解码回 ORM 值。

## 编码约定（JSONB 装不下的类型 ⇒ 打标签）

JSONB 只能装 `null / bool / int / float / str / list / dict` ⇒
UUID / datetime / date / Decimal / Enum 必须打标签：

```json
{"__t__": "uuid", "v": "…"}      {"__t__": "datetime", "v": "…"}
{"__t__": "date", "v": "…"}      {"__t__": "decimal", "v": "…"}
{"__t__": "enum", "v": "FIRE"}   {"__t__": "str", "v": "…"}
```

解码按标签还原；**枚举列**统一按列类型的 `enum_class` 还原成**成员**
（否则 SQLAlchemy 绑一个裸字符串会 LookupError）。

## 快照**不**装什么

- **主键**（各表 PK 列名不同 ⇒ 按 mapper 取）
- **归属列**（`project_id` / `workspace_id` —— 换了记录就换了归属）
- **审计列**（`created_at` / `created_by` / `updated_at`）
- **状态机 / 流程列**（`sign_status` / `approval_*` / `change_*` /
  `obsoleted_*` / `reversal_*` / `stale_*` / `hash_changed` /
  `changed_fields` / `locked_by_deliverable`）
  ⇒ 这些由**转移本身**维护，恢复它们会与「当前处于哪个状态」打架。

⚠️ **`record_hash` 装着** —— 它是「变更前的数据指纹」⇒ 撤销后必须回到
变更前的哈希，否则「记录到底改过没有」这个判据会拿**撤销后**的哈希去比
（TODO-077 的 `_assert_change_modified`）。
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect

# 快照**不**采集的列（归属 / 审计 / 状态机流程列）。
# ⚠️ `record_hash` **不在**这里 —— 它是要恢复的「数据指纹」。
SNAPSHOT_SKIP_COLUMNS: frozenset[str] = frozenset(
    {
        # 归属
        "project_id",
        "workspace_id",
        # 审计时间戳
        "created_at",
        "created_by",
        "updated_at",
        # 状态机 / 签署流程
        "sign_status",
        "approval_step",
        "approval_depth",
        "approval_role",
        "locked_by_deliverable",
        # 变更流程（ADR-0002）
        "change_pending_since",
        "change_resolved_by",
        "change_resolved_at",
        "change_abandoned_at",
        "change_abandoned_reason",
        # 作废流程（ADR-0009）
        "obsoleted_reason",
        "obsoleted_by",
        "obsoleted_at",
        "obsoleted_via_deliverable_id",
        # 撤销流程（ADR-0010）
        "reversal_requested_at",
        "reversal_requested_by",
        "reversal_reason",
        "reversal_approved_by",
        "reversal_approved_at",
        # 计算血缘审计（ADR-0031）
        "stale_resolution_path",
        "hash_changed",
        "changed_fields",
    }
)


def record_pk(record: Any) -> uuid.UUID:
    """记录主键 UUID（各表 PK 列名不同 ⇒ 按 mapper 取）。

    ⚠️ 不能用 `getattr(record, "record_id", None)` —— 只有部分表的 PK 叫
    `record_id`（`relief_results` 叫 `relief_id`、`streams` 叫 `stream_id`…）
    ⇒ 那种写法在别的表上**恒为 None** ⇒ 快照永远查不到（TODO-087）。
    """
    mapper = inspect(record.__class__)
    if mapper is None:
        raise TypeError(f"cannot inspect mapper for {record.__class__.__name__}")
    pk = mapper.primary_key[0]
    val = getattr(record, pk.name)
    if not isinstance(val, uuid.UUID):
        raise TypeError(f"record PK must be UUID, got {type(val).__name__}")
    return val


def _local_table(record: Any):
    """记录映射到的表（非 ORM 对象 ⇒ None）。"""
    try:
        mapper = inspect(record.__class__)
    except Exception:  # noqa: BLE001 —— 非映射类：没有表就没有快照数据
        return None
    if mapper is None:
        return None
    return mapper.local_table


def _encode(value: Any) -> Any:
    """把一个 Python 值编码成 JSONB 装得下的东西（装不下 ⇒ 打标签）。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    # ⚠️ 枚举必须在 `str` 之前判：`class X(str, Enum)` 的成员**也是 str**
    #    ⇒ 放行会让 JSONB 里落的是「枚举成员的字符串内容」而不是标签。
    if isinstance(value, enum.Enum):
        return {"__t__": "enum", "v": value.value}
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, uuid.UUID):
        return {"__t__": "uuid", "v": str(value)}
    if isinstance(value, datetime):
        return {"__t__": "datetime", "v": value.isoformat()}
    if isinstance(value, date):
        return {"__t__": "date", "v": value.isoformat()}
    if isinstance(value, Decimal):
        return {"__t__": "decimal", "v": str(value)}
    if isinstance(value, dict):
        return {str(k): _encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    return {"__t__": "str", "v": str(value)}


def _decode(value: Any, column_type: Any) -> Any:
    """把 JSONB 里的值解码回 ORM 认得的类型。"""
    if isinstance(value, dict) and set(value.keys()) == {"__t__", "v"}:
        tag = value["__t__"]
        raw = value["v"]
        if tag == "uuid":
            return uuid.UUID(raw)
        if tag == "datetime":
            return datetime.fromisoformat(raw)
        if tag == "date":
            return date.fromisoformat(raw)
        if tag == "decimal":
            return Decimal(raw)
        # enum / str：交给下面的枚举列统一处理
        if tag == "str":
            return raw
        return raw
    # 枚举列：统一还原成**成员**（裸字符串绑枚举列会 LookupError）
    enum_class = getattr(column_type, "enum_class", None)
    if enum_class is not None and value is not None and not isinstance(value, enum_class):
        try:
            return enum_class(value)
        except (ValueError, KeyError):
            return value
    return value


def capture_record_data(record: Any) -> dict[str, Any]:
    """采集记录的业务数据（JSONB 可存 + 可还原）。

    返回 `{列名: 编码后的值}`；**跳过**主键 / 归属 / 审计 / 状态机流程列
    （见 `SNAPSHOT_SKIP_COLUMNS`）。
    """
    table = _local_table(record)
    if table is None:
        return {}
    try:
        pk_names = {c.name for c in inspect(record.__class__).primary_key}
    except Exception:  # noqa: BLE001 —— 没有 mapper ⇒ 没有 PK 可排除
        pk_names = set()
    data: dict[str, Any] = {}
    for col in table.columns:
        if col.name in pk_names or col.name in SNAPSHOT_SKIP_COLUMNS:
            continue
        data[col.name] = _encode(getattr(record, col.name, None))
    return data


def apply_snapshot_data(record: Any, data: dict[str, Any] | None) -> int:
    """把快照里的数据还原到 record（返回还原的列数）。

    - 快照里没有的列 ⇒ **不动**（不清空）
    - 快照里的列在表上不存在 ⇒ 跳过（老快照 / 老表结构 ⇒ 不炸）
    - ⚠️ **非 ORM 对象**（没有可解析的表 ⇒ 只有测试替身会走到）⇒ 没有列类型
      可依 ⇒ 直接落**原值**（能按标签还原的仍按标签还原）。
    """
    if not data:
        return 0
    table = _local_table(record)
    restored = 0
    for name, raw in data.items():
        if table is not None:
            col = table.columns.get(name)
            if col is None:
                continue
            value = _decode(raw, col.type)
        else:
            value = _decode(raw, None)
        if not hasattr(record, name):
            continue
        setattr(record, name, value)
        restored += 1
    return restored
