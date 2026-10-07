"""API 载荷结构覆盖率闸 —— 前端类型能不能自动生成，就看这里。

## 它做什么

遍历 `app.openapi()` 的 `components.schemas`，找出所有**类型为 `object` 或
`array`、但没有 `properties` / `items`** 的字段 —— 它们在 OpenAPI 契约里
**没有结构定义**。

`pcs-frontend` 的类型靠 `openapi-typescript` 从 OpenAPI 生成
（`src/types/api.d.ts`，由 pre-commit 的 G-08 门禁自动同步）。对这类字段，
生成出来就是个光秃秃的 `object` / `any[]`，前端**只能继续手写类型** ——
那正是 TODO-039/041 想消灭的东西。

## 为什么是「只拦倒退」

同 `check_payload_model_coverage.py` 的理由，但这个闸**不需要登记表** ——
「这个载荷有没有定义」是 OpenAPI 自身的属性，不是人工映射判断，所以全部推导，
零维护。§3.4 那个闸需要登记表是因为它比对的两端（ORM comment ↔ Pydantic
description）都要人工声明对应关系；这里没有这个问题。

- `裸字段数 <= 基线` → 0
- `裸字段数 > 基线` → 1（有人新写了一个没定义的载荷）
- 已定义字段被改成裸的 → 1

基线只允许**往下调**，且下调必须在提交里说明是修好了哪几个。

## 现状

259 个 schema 中，141 个 object/array 字段里有 **71 个是裸类型**。
这与本体论 §3.4 约束① 是同一笔债的两个观测面：一个在 ORM 侧（JSONB 列无嵌套
Pydantic 模型，0/25），一个在 API 侧（本闸量到的 71）。做完 §3.4 约束①，
这边自然下降。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

# 裸载荷字段数上限。只允许往下调（修好了就下调），涨了即视为倒退。
BASELINE_BARE_FIELDS = 71

# 这些键出现任一即视为「已定义」，不计入裸字段
_TYPED_KEYS = ("$ref", "allOf", "oneOf", "anyOf", "prefixItems")


@dataclass
class Result:
    """一次检查的结论."""

    total_schemas: int = 0
    total_payload_fields: int = 0
    bare_fields: int = 0
    bare_by_schema: dict[str, list[str]] = field(default_factory=dict)

    @property
    def regression(self) -> bool:
        return self.bare_fields > BASELINE_BARE_FIELDS


def _is_bare(prop: dict) -> bool:
    """该字段是否是「声明了 object/array 却没有结构」。

    ⚠️ 只看顶层 type 是 object/array —— `additionalProperties` 的裸 dict、
    标量字段都不算，那些前端本来就能生成。
    """
    if any(k in prop for k in _TYPED_KEYS):
        return False
    if prop.get("type") not in ("object", "array"):
        return False
    # 有 properties（object）或 items（array）就是有结构
    return not prop.get("properties") and not prop.get("items")


def check() -> Result:
    """跑一次全量检查。"""
    from app.main import app

    schemas = app.openapi().get("components", {}).get("schemas", {})
    result = Result(total_schemas=len(schemas))
    for name, schema in sorted(schemas.items()):
        for field_name, prop in (schema.get("properties") or {}).items():
            if not isinstance(prop, dict):
                continue
            if prop.get("type") not in ("object", "array"):
                continue
            result.total_payload_fields += 1
            if _is_bare(prop):
                result.bare_fields += 1
                result.bare_by_schema.setdefault(name, []).append(field_name)
    return result


def main() -> int:
    r = check()
    pct = (
        0.0
        if r.total_payload_fields == 0
        else round(100.0 * (1 - r.bare_fields / r.total_payload_fields), 1)
    )
    print(
        f"API 载荷结构覆盖: {r.total_payload_fields - r.bare_fields}"
        f"/{r.total_payload_fields} ({pct}%)，基线要求裸字段 <= {BASELINE_BARE_FIELDS}"
    )
    print(
        f"当前: {r.bare_fields} 个裸 object/array（{r.total_schemas} 个 schema 全体扫描）"
    )

    if r.regression:
        print(f"\nFAIL: 裸载荷字段从 {BASELINE_BARE_FIELDS} 涨到 {r.bare_fields}，倒退 "
              f"{r.bare_fields - BASELINE_BARE_FIELDS} 个。")
        print("  闸没有登记表，说不出**是哪几个**新增的（只比总数）。")
        print("  定位方法：git stash 后再跑一次，或 "
              "`git diff HEAD~1 -- app/schemas app/api` 逐个核对新增字段。")
        print("  下面列的是**全部**欠账，不是新增的那几个：")
        _print_top(r, limit=15)
        return 1

    if r.bare_fields < BASELINE_BARE_FIELDS:
        print(
            f"\n提示: 裸字段已从 {BASELINE_BARE_FIELDS} 降到 {r.bare_fields}。"
            f"若是有意修复，请把 BASELINE_BARE_FIELDS 下调到 {r.bare_fields} 并在提交里说明。"
        )

    print(f"\n欠账明细（{r.bare_fields} 个，不阻断；修 §3.4 约束① 时自然下降）:")
    _print_top(r, limit=15)
    return 0


def _print_top(r: Result, limit: int) -> None:
    rows = sorted(r.bare_by_schema.items(), key=lambda kv: -len(kv[1]))
    for name, fields in rows[:limit]:
        shown = ", ".join(fields[:5]) + ("…" if len(fields) > 5 else "")
        print(f"  {name}: {len(fields)}  [{shown}]")
    if len(rows) > limit:
        rest = sum(len(v) for _, v in rows[limit:])
        print(f"  …… 另有 {len(rows) - limit} 个 schema，合计 {rest} 个字段")


if __name__ == "__main__":
    sys.exit(main())
