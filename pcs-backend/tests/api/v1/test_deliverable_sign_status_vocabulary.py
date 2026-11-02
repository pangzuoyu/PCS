"""交付物 `sign_status` 的**词表必须在契约产物里** —— P9B-2F（评审 #6）。

## 为什么单独一个文件

`sign_status` 的**运行时**取值早就是干净的裸词表值（`DRAFT` / `PENDING` /
`APPROVED` / `OBSOLETE`）—— PE-1 修掉了 `"DeliverableSignStatus.APPROVED"`
那种枚举类名泄漏。但**契约面**上它仍是一个裸 `{"type": "string"}` ⇒

- 任何按 OpenAPI 生成/校验客户端的消费者**看不到有哪几个值**；
- 词表一旦漂移（比如有人改回 `str(...)` 或加一个别名），**没有任何漂移检查
  会红** —— 契约没记词表 ⇒ 契约无从判漂移；
- 前端因此只能**手写**一份四值 union（`src/api/deliverables.ts`）⇒ 与
  后端脱钩（这正是 bug-2040 记的那类漂移根因）。

⇒ 本文件钉的是**生成的 OpenAPI 里 `sign_status` 带 `enum`**（不是「源码里
写了某个类型」—— 后者对着错的那个写法也是绿的）。
"""
from __future__ import annotations

import pytest

from app.models.enums import DeliverableSignStatus

#: 交付物签审状态 4 态（与 `DeliverableSignStatus` 同源）。
EXPECTED_VALUES = {s.value for s in DeliverableSignStatus}


def _enum_values(spec: dict, node: dict) -> list | None:
    """从 OpenAPI 的一个 property 节点里挖出 `enum` 词表。

    容忍 pydantic v2 的两种包装：直接 `$ref`（指向 components 里的枚举）与
    `allOf`（字段带 description/default 时 pydantic 会这么包）。
    """
    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        return _enum_values(spec, spec["components"]["schemas"][name])
    if "allOf" in node:
        for sub in node["allOf"]:
            found = _enum_values(spec, sub)
            if found is not None:
                return found
        return None
    return node.get("enum")


@pytest.mark.parametrize(
    "schema_name",
    ["DeliverableResponse", "DeliverableSnapshotResponse"],
)
def test_openapi_declares_the_sign_status_vocabulary(schema_name):
    """⚠️ 改代码前**必须**红 —— 契约里现在只有 `{"type": "string"}`。"""
    from app.main import app

    spec = app.openapi()
    schema = spec["components"]["schemas"][schema_name]
    node = schema["properties"]["sign_status"]
    values = _enum_values(spec, node)
    assert values is not None, (
        f"{schema_name}.sign_status 在契约里没有 enum（词表缺失）⇒ "
        "按契约生成的客户端看不到有哪几个值 ⇒ 词表漂移无人可查"
    )
    assert set(values) == EXPECTED_VALUES, (
        f"{schema_name}.sign_status 的词表与 DeliverableSignStatus 不一致：{values}"
    )


def test_the_vocabulary_is_not_the_nine_state_record_one():
    """⚠️ 交付物是 **4 态**（DRAFT/PENDING/APPROVED/OBSOLETE），**不是**记录侧的
    9 态（`RecordSignStatus9`）。两套词表长得像 ⇒ 复制粘贴最容易出错。"""
    assert EXPECTED_VALUES == {"DRAFT", "PENDING", "APPROVED", "OBSOLETE"}
    assert "CHECKED" not in EXPECTED_VALUES
    assert "STALE" not in EXPECTED_VALUES
