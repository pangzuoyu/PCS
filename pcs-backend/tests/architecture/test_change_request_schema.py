"""变更动作的**入参 schema 名字**必须说得清（TODO-084 第 5 条）。

## 为什么单独立一个契约测试

变更动作（`initiate-change` / `apply-change` / `abandon-change`）此前复用
`ObsoleteRequest`（「**弃用**记录」的请求体）⇒ 生成的 OpenAPI 里，
「发起变更」的入参类型名叫 **`ObsoleteRequest`** ⇒ 前端 `src/types/api.d.ts`
里也是 ⇒ 读契约的人（和写代码的人）会把「发起变更」误读成「弃用」。

⚠️ 这类漂移**不会让任何既有测试变红**：请求体**字段完全一样**（都只有
`reason`）⇒ 行为正确、只是**名字**骗人 ⇒ 只能靠**读 OpenAPI** 钉住。
"""
from __future__ import annotations

import pytest

#: 变更动作端点（都是「变更动作」，入参都只有 reason）。
CHANGE_ACTION_PATHS = [
    "/api/v1/records/{module}/{record_id}/initiate-change",
    "/api/v1/records/{module}/{record_id}/apply-change",
    "/api/v1/records/{module}/{record_id}/abandon-change",
]

#: 弃用端点 —— 它**就该**用 ObsoleteRequest（不许一起改掉）。
OBSOLETE_PATH = "/api/v1/records/{module}/{record_id}/obsolete"


@pytest.fixture(scope="module")
def openapi() -> dict:
    from app.main import app

    return app.openapi()


def _request_schema_ref(openapi: dict, path: str) -> str:
    schema = (
        openapi["paths"][path]["post"]["requestBody"]["content"]["application/json"][
            "schema"
        ]
    )
    return schema.get("$ref", "")


@pytest.mark.parametrize("path", CHANGE_ACTION_PATHS, ids=lambda p: p.split("/")[-1])
def test_change_action_does_not_reuse_the_obsolete_request_schema(openapi: dict, path: str):
    """变更动作的入参**不许**叫 `ObsoleteRequest`（那是弃用的）。"""
    ref = _request_schema_ref(openapi, path)
    assert "ObsoleteRequest" not in ref, (
        f"{path} 的入参仍叫 ObsoleteRequest ⇒ 契约里「发起变更」长得像「弃用」"
    )
    assert ref, f"{path} 的请求体没有 schema 引用（契约缺形状）"


def test_obsolete_endpoint_still_uses_the_obsolete_request_schema(openapi: dict):
    """反向对照：弃用端点**仍用** `ObsoleteRequest`（别把守卫修成反了）。"""
    ref = _request_schema_ref(openapi, OBSOLETE_PATH)
    assert "ObsoleteRequest" in ref
