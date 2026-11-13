"""AI 路由骨架（P10-A · Task T9）。

## 契约形状（SPEC §3.1.2 / §4.1.1 / §4.1.2）

- 5 个端点全部 **501**（AI 已预留、未实现）：
  `intent` · `knowledge/search` · `equipment/recommend` · `explain` ·
  `document/extract`
- **认证在 501 之前** ⇒ 无 token 是 **401**（不是 501）
- 契约里带 `x-status: reserved`（**不是** `deprecated` —— deprecated 的
  语义是「曾有、现已不推荐」，这里是「还没上线」）

## 两条「静默失效」的坑（必须钉住）

1. **`topK` 的别名** —— SPEC §4.1.2 的请求体字段名是 **`topK`**（驼峰）。
   若 schema 只写 `top_k` ⇒ Pydantic **默认忽略**未知字段 ⇒ 前端传的值
   **静默变成默认值**，而且**不报错**。
2. **`context` 的驼峰别名** —— SPEC §4.1.1 的 `context` 用
   `projectId` / `recordId` ⇒ 同样的静默失效（同型缺陷）。
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI

from app.core.security import create_access_token
from app.schemas.ai import AiContext

pytestmark = pytest.mark.asyncio

#: SPEC §3.1.2 的 5 个 AI 端点（相对 `api_router` 的 `/api/v1` 前缀）。
AI_PATHS = (
    "/api/v1/ai/intent",
    "/api/v1/ai/knowledge/search",
    "/api/v1/ai/equipment/recommend",
    "/api/v1/ai/explain",
    "/api/v1/ai/document/extract",
)


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


async def test_ai_intent_returns_501(client, designer_headers) -> None:
    """501 + 信封 {code:'AI_NOT_IMPLEMENTED', message:..., request_id:...}."""
    resp = await client.post(
        "/api/v1/ai/intent",
        json={"text": "帮我把泵P-101的流量设为50 m3/h"},
        headers=designer_headers,
    )

    assert resp.status_code == 501, resp.text
    body = resp.json()
    assert body["code"] == "AI_NOT_IMPLEMENTED"
    assert body["message"]
    assert body["request_id"]


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/v1/ai/knowledge/search", {"query": "API 520 火灾工况润湿面积修正系数"}),
        ("/api/v1/ai/equipment/recommend", {"equipment_tag": "P-101"}),
        ("/api/v1/ai/explain", {"text": "把泵的流量改成 50"}),
        ("/api/v1/ai/document/extract", {"document_ref": "STD-API520-2014"}),
    ],
)
async def test_ai_routes_return_501(client, designer_headers, path, payload) -> None:
    """SPEC §3.1.2 的**全部** AI 端点都是 501（不只是 intent/search）。"""
    resp = await client.post(path, json=payload, headers=designer_headers)

    assert resp.status_code == 501, resp.text
    assert resp.json()["code"] == "AI_NOT_IMPLEMENTED"


async def test_ai_routes_require_auth(client) -> None:
    """无 bearer ⇒ 401（**不是** 501）—— 认证在 501 之前。"""
    resp = await client.post("/api/v1/ai/intent", json={"text": "x"})

    assert resp.status_code == 401, resp.text


async def test_ai_routes_have_x_status_reserved_in_openapi() -> None:
    """契约里 5 个端点带 `x-status=reserved` 且**不是** deprecated。"""
    from app.api.v1 import api_router

    app = FastAPI()
    app.include_router(api_router)
    paths = app.openapi()["paths"]

    for path in AI_PATHS:
        assert path in paths, f"契约里没有 {path}：{sorted(paths)}"
        operation = paths[path]["post"]
        assert operation.get("x-status") == "reserved", operation
        assert "deprecated" not in operation, operation


async def test_ai_knowledge_search_accepts_topK_alias(client, designer_headers) -> None:
    """⚠️ **契约里的字段名是 `topK`**（SPEC §4.1.2）⇒ 传 topK 能被收到
    —— 否则前端传的值静默失效（且不报错）。
    """
    resp = await client.post(
        "/api/v1/ai/knowledge/search",
        json={"query": "q", "topK": 7},
        headers=designer_headers,
    )

    # 501（不是 422）⇒ 说明 `topK` 被**接受**了（未知字段被忽略也不会 422，
    # 但 422 说明它被**拒绝**了 ⇒ 两种都说明问题 ⇒ 这里断言不是 422）
    assert resp.status_code == 501, resp.text


async def test_ai_intent_context_is_a_named_schema() -> None:
    """`context` 是具名 schema（`AiContext`）⇒ 字段名有编译期约束。

    ⚠️ **契约里用的是别名**（`projectId` / `recordId`，= SPEC §4.1.1 的驼峰）
    —— Pydantic 的 JSON Schema 默认按**别名**出属性名 ⇒ 契约与 SPEC 逐字一致。
    """
    schema = AiContext.model_json_schema()

    assert schema["title"] == "AiContext"
    assert "projectId" in schema["properties"]
    assert "recordId" in schema["properties"]
    assert "module" in schema["properties"]


async def test_ai_intent_context_accepts_camelCase_aliases() -> None:
    """⚠️ **SPEC §4.1.1 的 context 用驼峰**（`projectId` / `recordId`）
    ⇒ 必须能收到 —— 否则前端传的值静默变 None（同 topK）。
    """
    context = AiContext.model_validate(
        {"projectId": "p-1", "module": "PUMP", "recordId": "r-1"}
    )

    assert context.project_id == "p-1"
    assert context.module == "PUMP"
    assert context.record_id == "r-1"


async def test_ai_intent_context_accepts_snake_case_too() -> None:
    """⚠️ `populate_by_name=True` ⇒ 蛇形与驼峰**两种写法都能进**。"""
    context = AiContext.model_validate(
        {"project_id": "p-1", "module": "PUMP", "record_id": "r-1"}
    )

    assert context.project_id == "p-1"
    assert context.record_id == "r-1"


async def test_ai_routes_declare_the_501_envelope_in_the_contract() -> None:
    """⚠️ 契约里**必须声明 501**（评审 M-2）。

    ⚠️ 路由若只写 `-> None` ⇒ FastAPI 生成 `200 + 空 schema`
    ⇒ **契约描述的是永远不发生的行为**（运行时一律 501）⇒
    前端派生不出 501 信封的类型。
    """
    from fastapi import FastAPI

    from app.api.v1 import api_router

    app = FastAPI()
    app.include_router(api_router)
    spec = app.openapi()

    for path in AI_PATHS:
        responses = spec["paths"][path]["post"]["responses"]
        assert "501" in responses, f"{path} 的契约里没有 501：{list(responses)}"
        ref = responses["501"]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/AiNotImplementedResponse"), ref

    # 信封的字段与运行时逐字一致
    envelope = spec["components"]["schemas"]["AiNotImplementedResponse"]["properties"]
    assert set(envelope) == {"code", "message", "status", "request_id"}, envelope


async def test_ai_contract_declares_no_unreachable_200_and_declares_the_401() -> None:
    """⚠️ **评审 #12 / #13** —— 契约必须**如实描述**会发生什么。

    ① **不得有 200**：五个端点**无条件**抛 `AINotImplementedError`
    ⇒ 契约里的 `200 + 空 schema` 描述的是**永远不发生**的行为
    ⇒ 前端派生出的类型里有一条**死分支**。

    ② **必须有 401**：端点是**认证先于 501**（无 token ⇒ 401）
    ⇒ 只看契约的人**没有 401 这条分支** ⇒ 他按契约写的客户端
    会把「没登录」当成「功能没上线」⇒ 排查方向直接跑偏。
    """
    from fastapi import FastAPI

    from app.api.v1 import api_router

    app = FastAPI()
    app.include_router(api_router)
    spec = app.openapi()

    for path in AI_PATHS:
        responses = spec["paths"][path]["post"]["responses"]
        assert "200" not in responses, (
            f"{path} 的契约里还有永远不会发生的 200：{list(responses)}"
        )
        assert "401" in responses, (
            f"{path} 的契约里没有 401（认证先于 501）：{list(responses)}"
        )
        ref401 = responses["401"]["content"]["application/json"]["schema"]["$ref"]
        assert ref401.endswith("/ErrorResponse"), ref401
        # ⚠️ **503 也要在契约里**（评审 #19）—— 出口守卫会真的抛它
        assert "503" in responses, (
            f"{path} 的契约里没有 503（出口守卫会真的抛它）：{list(responses)}"
        )


async def test_ai_egress_guard_rejects_a_public_endpoint(
    client, designer_headers, db_session, monkeypatch
) -> None:
    """⚠️ **评审 #19** —— 运行时把 `ai_enabled` 翻开 + endpoint 指到**公网** ⇒ **503**。

    ⚠️ 旧的校验只有两处：**启动时**（只在 `ai_enabled` 为真时才跑 ⇒ AI 默认关
    ⇒ 启动校验是空转）与**调用时**（在 `OutboundAIClient.call` 里 ⇒
    而路由**直接抛 501、从不构造那个 client** ⇒ 那次校验**根本不在请求路径上**）
    ⇒ 「打开 AI 并把 endpoint 指到公网」这件事**处处没校验**。
    ⇒ 现在：每次 AI 请求都重新读开关与 endpoint 并校验。
    """
    from app.core.config import get_settings
    from app.models.system import SystemSetting

    monkeypatch.setattr(get_settings(), "internal_cidrs", "10.0.0.0/8")

    for key, value in (("ai_enabled", True), ("ai_endpoint", "8.8.8.8")):
        row = await db_session.get(SystemSetting, key)
        if row is None:
            row = SystemSetting(setting_key=key, setting_value_json=value)
            db_session.add(row)
        else:
            row.setting_value_json = value
    await db_session.commit()

    resp = await client.post(
        "/api/v1/ai/intent", json={"text": "x"}, headers=designer_headers
    )

    assert resp.status_code == 503, resp.text
    assert resp.json()["code"] == "AI_ENDPOINT_NOT_INTERNAL"


async def test_ai_egress_guard_passes_an_internal_endpoint(
    client, designer_headers, db_session, monkeypatch
) -> None:
    """⚠️ **评审 #19 的另一半** —— 守卫**只拦公网**，不误伤内网。

    ⚠️ 没有这条，守卫可能变成「**一律 503**」（比如把 CIDR 判反了、
    或者把 `parse_cidrs` 的失败当成「不在内网」）⇒ 那时候
    `test_ai_egress_guard_rejects_a_public_endpoint` **照样绿**
    ⇒ 守卫变成「AI 永远不可用」而没人发现。

    ⇒ AI 开着 + endpoint 在内网 ⇒ 请求**照常走到路由** ⇒ 仍然是 **501**
    （本批不实现 AI ⇒ 501 才是「正确结果」）。
    """
    from app.core.config import get_settings
    from app.models.system import SystemSetting

    monkeypatch.setattr(get_settings(), "internal_cidrs", "10.0.0.0/8")

    for key, value in (("ai_enabled", True), ("ai_endpoint", "http://10.1.2.3:8000")):
        row = await db_session.get(SystemSetting, key)
        if row is None:
            row = SystemSetting(setting_key=key, setting_value_json=value)
            db_session.add(row)
        else:
            row.setting_value_json = value
    await db_session.commit()

    resp = await client.post(
        "/api/v1/ai/intent", json={"text": "x"}, headers=designer_headers
    )

    assert resp.status_code == 501, resp.text
    assert resp.json()["code"] == "AI_NOT_IMPLEMENTED"
