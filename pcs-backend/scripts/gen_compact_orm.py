#!/usr/bin/env python3
"""从 ORM metadata 生成 `docs/schema_compact_orm.md`（TODO-103 · P9B-3 · T1）。

## 为什么要有这个脚本

`docs/schema_compact_orm.md` 此前是 **2026-09-02 的手工快照**（53 张表），
而 ORM 现有 **107** 张表 ⇒ 文件缺 54 张 ⇒ 被当成「照这张表手写 SQL」的依据时
**照着查不到的表去写 SQL**（TODO-103）。

⇒ 本脚本把那个文件变成**派生产物**：改 mixin 后重跑一次即可，
文件不再靠人手维护 ⇒ **不可能再过期**。

## 格式（沿用现有文件的 `col|type!` 风格）

- 每张表一行：`### <表名>` + 缩进两空格的列清单；
- 列：`列名|类型`，NOT NULL 加 `!` 后缀；
- 类型缩写：`str` / `int` / `float` / `bool` / `dec` / `dt` / `date` /
  `text` / `jsonb` / `INET` / `CHAR`（UUID）；
- 主键 / 外键标记：`CHARPK` / `CHARFK` / `CHARPKFK` / `strPK` / `strFK`；
- 行尾 `[UNIQUE: a+b; c]` 列出唯一约束。

## 用法

```bash
cd pcs-backend && uv run python scripts/gen_compact_orm.py
```

⚠️ **生成物，勿手改** —— 要改表结构就去改 ORM / 迁移，然后重跑本脚本。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

DEFAULT_OUTPUT = _BACKEND_ROOT / "docs" / "schema_compact_orm.md"

# SQLAlchemy 类型 → 文件里的缩写（**与历史文件逐字一致**，见 docs/solutions）
_TYPE_ABBR = {
    "String": "str",
    "Text": "text",
    "Integer": "int",
    "BigInteger": "int",
    "Float": "float",
    "Boolean": "bool",
    "Numeric": "dec",
    "DateTime": "dt",
    "Date": "date",
    "JSON": "jsonb",
    "JSONB": "jsonb",
    "Enum": "str",
    "INET": "INET",
    "Uuid": "CHAR",
    "UUID": "CHAR",
    "LargeBinary": "bytes",
}

# 归类（**手工维护的分类轴**，不是从 metadata 推的）——
# ⚠️ 只有「表归到哪一节」是手工的；**列清单本身全部派生**。
#    新表若没归类，会落到「其它」节（而不是**消失**）。
_SECTION_ORDER = [
    ("项目与物流", ["projects", "streams", "stream_state_points"]),
    ("配置层", [
        "config_assets", "config_versions", "config_approvals",
        "formula_definitions", "coefficient_tables", "template_files",
        "project_templates", "pipe_classes", "project_pipe_classes",
        "numbering_templates", "doc_no_sequences",
    ]),
    ("计算模块", [
        "piping_results", "pump_results", "psv_results", "vessel_results",
        "heat_results", "cv_results", "flash_results", "pipe_network_results",
        "restriction_results", "flare_system_results", "cooling_tower_results",
        "psychro_results", "sep_equip_results", "filtration_results",
        "cost_est_results", "open_channel_results",
    ]),
    ("交付物层", [
        "deliverables", "deliverable_versions", "deliverable_record_bindings",
        "signature_matrices", "project_signature_matrix_bindings",
        "customer_approval_attachments",
    ]),
    ("变更管理", ["change_notice_details", "record_change_snapshots"]),
    ("集成层", ["equipment_list", "equipment_type_codes", "equipment_lib", "suppliers"]),
    ("流程横切", [
        "data_lineage", "project_input_checklist", "workspaces",
        "audit_logs", "users", "system_settings",
    ]),
    ("报表层", ["report_definitions", "report_execution_logs"]),
    ("AI预留", ["document_chunks", "ai_audit_log"]),
    ("许可", ["license_configs"]),
]


def _column_token(column) -> str:
    """列 → `列名|类型`（含 PK/FK 标记与 NOT NULL 的 `!`）。"""
    abbr = _TYPE_ABBR.get(type(column.type).__name__, type(column.type).__name__)
    if column.primary_key:
        abbr += "PK"
    if column.foreign_keys:
        abbr += "FK"
    if not column.nullable:
        abbr += "!"
    return f"{column.name}|{abbr}"


def _unique_suffix(table) -> str:
    """表的唯一约束 → `  [UNIQUE: a+b; c]`（没有则空串）。

    ⚠️ **必须排序** —— `table.constraints` 是个 **set** ⇒ 迭代顺序随进程
    （PYTHONHASHSEED）⇒ 不排序的话每次重跑生成物都不同 ⇒
    「改了 ORM 忘了重跑」那条守卫会**假红**，而 diff 也没法看。
    ⇒ 按**约束名**排序（名字在本仓是稳定的 `uq_<table>_<语义>`）。
    """
    from sqlalchemy import UniqueConstraint

    groups = sorted(
        (
            (con.name or "", "+".join(c.name for c in con.columns))
            for con in table.constraints
            if isinstance(con, UniqueConstraint)
        )
    )
    if not groups:
        return ""
    return f"  [UNIQUE: {'; '.join(g for _, g in groups)}]"


def render(metadata) -> str:
    """metadata（`Base.metadata`）→ 完整 markdown。"""
    from sqlalchemy import UniqueConstraint  # noqa: F401  (供 _unique_suffix 使用)

    tables = {name: metadata.tables[name] for name in metadata.tables}
    assigned: set[str] = set()
    sections: list[tuple[str, list[str]]] = []

    for title, names in _SECTION_ORDER:
        present = [n for n in names if n in tables]
        assigned.update(present)
        if present:
            sections.append((title, present))

    # ⚠️ 未归类的表**也要列出** —— 归类轴是人维护的，列清单不是。
    rest = sorted(set(tables) - assigned)
    if rest:
        sections.append(("其它", rest))

    out = [
        "# PCS 紧凑对照表（ORM 版 · **生成物**）",
        f"> 生成时间：{datetime.now(timezone.utc).date().isoformat()} | "
        "来源：app/models/*.py（**生成物，勿手改**）",
        "> 重新生成：`cd pcs-backend && uv run python scripts/gen_compact_orm.py`",
        f"> 表数量：**{len(tables)}**（= ORM metadata 的全部表）",
        "",
        "⚠️ 本文件是 `SA_Base.metadata` 的**派生**产物 ⇒ 表/列不会过期。",
        "完整真值永远 = `app/models/*.py`；本文件只供「快速查一张表的字段」用。",
    ]
    for title, names in sections:
        out.append("")
        out.append(f"## {title}({len(names)})")
        for name in names:
            table = tables[name]
            cols = ", ".join(_column_token(c) for c in table.columns)
            out.append(f"### {name}")
            out.append(f"  {cols}{_unique_suffix(table)}")
    return "\n".join(out) + "\n"


def main() -> int:
    import app.models  # noqa: F401  触发全部 model 注册
    from app.db.base import Base

    output = DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(Base.metadata), encoding="utf-8")
    print(f"OK schema_compact_orm.md: {len(Base.metadata.tables)} tables ({output})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
