"""AI 审计中间件（P10-A · Task T11 · Review Focus #1 #2）。

## 两条最容易漏的

1. **认证失败也要留痕**（`user_id=None`）—— 否则攻击者拿无效 token 探测
   AI 端点时**不留痕** ⇒ 审计表对探测行为完全失明。
2. **读完 body 后下游仍要能收到 body** —— 纯 ASGI 中间件若吞了 body，
   AI 路由会报 **422** 而不是 501 ⇒ **症状与「参数错」无法区分**。

## ⚠️ 为什么不能用 `client` fixture

`tests/conftest.py::client` 自建**最小 FastAPI app**（只有
`install_exception_handlers` + `api_router`）⇒ **不挂任何 middleware**
⇒ 中间件根本不在链路里 ⇒ 用它测中间件 = **测了个寂寞**。
⇒ 本文件用 `ai_client` fixture：走 `create_app()` 工厂 ⇒ **真实中间件链**。
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import create_access_token
from app.db.session import get_db
from app.models.system import AiAuditLog

pytestmark = pytest.mark.asyncio

#: 超过这个大小就不哈希（**大 body 不进审计表的哈希列**）。
MAX_HASH_BYTES = 1024 * 1024


@pytest_asyncio.fixture
async def ai_client(db_engine):
    """走 `create_app()` 的客户端 ⇒ **真实中间件链**（含 AI 审计中间件）。"""
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    # ⚠️ 一个**必定抛异常**的 AI 路径（用来验「下游未产生响应」时的审计）。
    #    ⚠️ 不能靠 monkeypatch 路由函数 —— 路由在 app 创建时就注册了，
    #    改模块属性**不会**换掉已注册的处理函数。
    @app.post("/api/v1/ai/_test_boom")
    async def _boom() -> None:
        raise RuntimeError("下游炸了")

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def recorded_audits(monkeypatch) -> list[dict]:
    """截住中间件的入队（**不真连 Redis**）。

    ⚠️ **autouse**：本模块的**每个**用例都必须拦住入队 ——
    否则没用 `recorded_audits` 的那两条会**真的把 job 入进 Redis**
    ⇒ 单测污染队列（实测：这些 job 后来被 worker 捡到 ⇒ 队列里躺着
    一堆测试残留）。
    ⇒ autouse + 每个用例自己从 `recorded_audits` 里读断言。

    ⚠️ **patch 的是中间件模块里的那个引用**
    （`app.core.ai_audit_middleware.enqueue_ai_audit_log`），
    **不是**源模块 `app.services.ai.arq_queue` ⇒ 因为中间件是
    `from ... import enqueue_ai_audit_log`（**绑定了名字**），
    patch 源模块**不会**影响中间件手里的引用。
    """
    import app.core.ai_audit_middleware as mw

    calls: list[dict] = []

    async def fake_enqueue(**fields):
        calls.append(fields)
        return True

    monkeypatch.setattr(mw, "enqueue_ai_audit_log", fake_enqueue)
    return calls


async def _count(db) -> int:
    return int((await db.execute(select(func.count()).select_from(AiAuditLog))).scalar_one())


async def test_ai_request_body_still_reaches_pydantic(ai_client, designer_headers) -> None:
    """⚠️ **Review Focus #2** —— 中间件读 body 后，下游仍能校验 body
    ⇒ 缺字段 ⇒ **422**（不是 501）。
    """
    resp = await ai_client.post(
        "/api/v1/ai/intent",
        json={"not_text": "x"},
        headers=designer_headers,
    )

    assert resp.status_code == 422, resp.text


async def test_request_id_is_server_generated_uuid(ai_client, designer_headers) -> None:
    """响应 X-Request-ID 是**标准 UUID 串**（36 位带连字符）。"""
    resp = await ai_client.post(
        "/api/v1/ai/intent", json={"text": "x"}, headers=designer_headers
    )

    request_id = resp.headers["X-Request-ID"]
    assert len(request_id) == 36
    uuid.UUID(request_id)


async def test_client_request_id_is_stored_not_generated(
    ai_client, designer_headers, recorded_audits
) -> None:
    """带 X-Request-ID ⇒ 审计里 client_request_id = 该值；不带 ⇒ None
    （**服务端不造**）。
    """
    resp = await ai_client.post(
        "/api/v1/ai/intent",
        json={"text": "x"},
        headers={**designer_headers, "X-Request-ID": "client-abc-123"},
    )

    assert resp.status_code == 501, resp.text
    assert recorded_audits, "审计没入队"
    assert recorded_audits[-1]["client_request_id"] == "client-abc-123"


async def test_audit_is_written_even_when_auth_fails(ai_client, recorded_audits) -> None:
    """⚠️ **Review Focus #1** —— 无效 token ⇒ 仍然落审计，user_id=None。"""
    resp = await ai_client.post(
        "/api/v1/ai/intent",
        json={"text": "x"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert resp.status_code == 401, resp.text
    assert recorded_audits, "认证失败 ⇒ 审计没入队（审计表对探测行为失明）"
    assert recorded_audits[-1]["user_id"] is None


async def test_non_ai_paths_are_not_audited(ai_client, designer_headers, recorded_audits) -> None:
    """`/api/v1/health` 不进 AI 审计（中间件按前缀过滤）。"""
    resp = await ai_client.get("/api/v1/health", headers=designer_headers)

    assert resp.status_code == 200, resp.text
    assert recorded_audits == []


async def test_audit_is_enqueued_not_written_inline(
    ai_client, db_session, designer_headers, recorded_audits
) -> None:
    """审计**异步**（入队）⇒ 端点不因审计写库慢而变慢。

    ⇒ 断言：**表里没有行**（写库发生在 worker 侧），但**入队发生了**。
    """
    resp = await ai_client.post(
        "/api/v1/ai/intent", json={"text": "x"}, headers=designer_headers
    )

    assert resp.status_code == 501, resp.text
    assert recorded_audits, "没有入队"
    assert await _count(db_session) == 0, "审计被**同步**写库了（应当异步）"


async def test_audit_records_500_when_no_response_is_sent(
    ai_client, designer_headers, recorded_audits
) -> None:
    """⚠️ 下游异常**未产生响应**时 ⇒ status_code 记 **500**
    （不是 None、不是 0）。
    """
    with pytest.raises(RuntimeError):
        await ai_client.post(
            "/api/v1/ai/_test_boom", json={"text": "x"}, headers=designer_headers
        )

    assert recorded_audits, "异常路径没有留痕"
    assert recorded_audits[-1]["status_code"] == 500


async def test_large_body_is_not_hashed(
    ai_client, designer_headers, recorded_audits
) -> None:
    """⚠️ body 超过**审计上限** ⇒ `sanitized_request_hash` 为 **None**（不哈希大 body）。

    ⚠️ **评审 #3 后行为变了**：上限从「1 MB 哈希窗口」变成
    `settings.ai_max_request_body_bytes`（256 KB）⇒ 超限直接 **413**，
    且**不再进路由**（body 根本没被读进内存）⇒ 审计行照写、hash 留空。
    """
    from app.core.config import get_settings

    cap = get_settings().ai_max_request_body_bytes
    big = "x" * (cap + 1024)

    resp = await ai_client.post(
        "/api/v1/ai/intent", json={"text": big}, headers=designer_headers
    )

    assert resp.status_code == 413, resp.text
    assert recorded_audits[-1]["sanitized_request_hash"] is None


async def test_small_body_is_hashed(ai_client, designer_headers, recorded_audits) -> None:
    """body ≤ 1MB ⇒ 有哈希（且是 `sha256:` 前缀）。"""
    resp = await ai_client.post(
        "/api/v1/ai/intent", json={"text": "x"}, headers=designer_headers
    )

    assert resp.status_code == 501, resp.text
    digest = recorded_audits[-1]["sanitized_request_hash"]
    assert digest and digest.startswith("sha256:")


async def test_audit_records_the_endpoint_and_duration(
    ai_client, designer_headers, recorded_audits
) -> None:
    """审计里带**端点路径**与**耗时**。"""
    resp = await ai_client.post(
        "/api/v1/ai/intent", json={"text": "x"}, headers=designer_headers
    )

    assert resp.status_code == 501, resp.text
    audit = recorded_audits[-1]
    assert audit["endpoint"] == "/api/v1/ai/intent"
    assert audit["duration_ms"] >= 0
    assert audit["status_code"] == 501
    assert audit["response_summary"] == "AI_NOT_IMPLEMENTED"


async def test_audit_records_the_authenticated_user(
    ai_client, designer_headers, recorded_audits
) -> None:
    """认证成功 ⇒ user_id 是**派生值**（与登录路径同口径）。"""
    resp = await ai_client.post(
        "/api/v1/ai/intent", json={"text": "x"}, headers=designer_headers
    )

    assert resp.status_code == 501, resp.text
    assert recorded_audits[-1]["user_id"] == uuid.uuid5(
        uuid.NAMESPACE_DNS, "test-designer"
    )


async def test_oversized_body_is_truncated_not_buffered(
    ai_client, designer_headers, recorded_audits
) -> None:
    """⚠️ **超大 body ⇒ 413**（评审 #3），而不是把服务撑爆。

    ⚠️ 中间件在**认证之前**就读 body ⇒ 未认证的客户端也能触发 ⇒
    没有上限 ⇒ 内存放大 / OOM 风险。
    ⇒ 上限之上：**按 content-length 先拒**（body 根本不进内存）⇒ **413**；
    且**审计行照写**（hash 留空）⇒ 契约 R2「失败也要留痕」不被破坏。
    """
    from app.core.config import get_settings

    cap = get_settings().ai_max_request_body_bytes
    oversized = "x" * (cap + 1024)

    resp = await ai_client.post(
        "/api/v1/ai/intent", json={"text": oversized}, headers=designer_headers
    )

    assert resp.status_code == 413, resp.text
    assert recorded_audits[-1]["sanitized_request_hash"] is None


# === 评审 #3 / #29 / #17 / #18（2026-11-12 评审修复批） ===


async def test_neighbour_path_under_api_v1_ai_is_not_audited(
    ai_client, designer_headers, recorded_audits
) -> None:
    """⚠️ **评审 #29** —— 审计前缀必须**有路径边界**。

    旧判定是 `path.startswith("/api/v1/ai")` ⇒ `/api/v1/ai-anything`
    这类**邻居路径**也会被审计（body 被读、被哈希、被入队）⇒
    未认证请求可以把它当**任意的哈希停顿入口**（见评审 #4）。
    """
    resp = await ai_client.post(
        "/api/v1/ai-anything", json={"text": "x"}, headers=designer_headers
    )

    assert resp.status_code == 404, resp.text
    assert recorded_audits == [], "邻居路径不该进 AI 审计"


async def test_oversized_body_is_rejected_with_413_and_still_audited(
    ai_client, designer_headers, recorded_audits
) -> None:
    """⚠️ **评审 #3** —— 超上限的 body ⇒ **413**（不是 422），且**仍留审计行**。

    旧行为：截断 body ⇒ 下游 JSON 解析失败 ⇒ 422 ⇒ 与「参数错」混在一起；
    且 10 MB 的 body **先被完整读进内存**（未认证即可触发）。
    新行为：**按 content-length 先拒**（413），**不读 body**，
    但**审计行照写**（hash 留空）⇒ 契约 R2「失败也要留痕」不被破坏。
    """
    from app.core.config import get_settings

    cap = get_settings().ai_max_request_body_bytes
    big = "x" * (cap + 1024)

    resp = await ai_client.post(
        "/api/v1/ai/intent", json={"text": big}, headers=designer_headers
    )

    assert resp.status_code == 413, resp.text
    assert recorded_audits, "超限请求也要留审计行"
    assert recorded_audits[-1]["sanitized_request_hash"] is None


async def test_deeply_nested_body_still_leaves_an_audit_row(
    ai_client, designer_headers, recorded_audits
) -> None:
    """⚠️ **评审 #17** —— 深层嵌套 body ⇒ **审计行照写**（不被异常打断）。

    ⚠️ 这里的响应码可能是 **500** —— 但**不是审计路径造成的**：
    FastAPI 的 422 信封会把**整个非法输入**回显出来 ⇒ `jsonable_encoder`
    对 ~1000 层嵌套**自己**就 `RecursionError` ⇒ 500。
    那是**既有的**通用缺陷（任何端点收到深层 JSON 都一样），与本批无关
    ⇒ 已登记 bug-2161 / TODO-151。

    ⇒ 本用例只钉 #17 的契约：**审计行必须落**（异常不得逃出审计记录路径）。
    """
    payload = "[" * 1000 + "]" * 1000

    try:
        resp = await ai_client.post(
            "/api/v1/ai/intent",
            content=payload,
            headers={**designer_headers, "Content-Type": "application/json"},
        )
        status = resp.status_code
    except RecursionError:
        # ⚠️ **既有的**通用缺陷（bug-2161）：FastAPI 的 422 信封会把**整个
        # 非法输入**回显 ⇒ `jsonable_encoder` 对 ~1000 层嵌套自己就
        # `RecursionError` ⇒ 异常**逃出 app**（任何端点收到深层 JSON 都一样，
        # 与本批无关）。⇒ 这里只关心：**审计路径没被它打断**。
        status = 500

    assert recorded_audits, "深层 body 也必须留审计行"
    assert recorded_audits[-1]["status_code"] in (422, 500), recorded_audits[-1]
    assert status < 600


async def test_audit_hash_is_computed_off_the_event_loop(
    ai_client, designer_headers, recorded_audits, monkeypatch
) -> None:
    """⚠️ **评审 #18** —— 哈希必须**离开事件循环**。

    `hash_sanitized` 是同步 CPU（解析 → 递归脱敏 → 再序列化 → sha256），
    直接在 async 中间件里调 ⇒ 整个事件循环被占住。
    ⇒ 必须走 `asyncio.to_thread`。
    """
    import asyncio

    calls: list[object] = []
    original = asyncio.to_thread

    async def spy(fn, *args, **kwargs):
        calls.append(fn)
        return await original(fn, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", spy)

    resp = await ai_client.post(
        "/api/v1/ai/intent", json={"text": "x"}, headers=designer_headers
    )

    assert resp.status_code == 501, resp.text
    assert calls, "哈希没有走 asyncio.to_thread ⇒ 仍在事件循环上"


async def test_audit_row_request_id_matches_the_response(
    ai_client, designer_headers, recorded_audits
) -> None:
    """⚠️ **评审 #2** —— 审计行的 `request_id` 必须**钉住**。

    ⚠️ `request_id` 是审计行的**幂等键**，也是 501 信封回给客户端的那个 id
    ⇒ 而写库任务在 `request_id` 为空时**直接 return、不写行**
    ⇒ 只要中间件哪天不再传它，**整张审计表会静默为空**，
    而本文件所有断言**照样全绿**（它们从不断言 `request_id`）。

    ⇒ 断言三处**同值**：响应头 `X-Request-ID` == 501 信封的 `request_id`
    == 审计行的 `request_id`。
    """
    resp = await ai_client.post(
        "/api/v1/ai/intent", json={"text": "x"}, headers=designer_headers
    )

    assert resp.status_code == 501, resp.text
    header_id = resp.headers["X-Request-ID"]
    envelope_id = resp.json()["request_id"]
    assert header_id == envelope_id, (header_id, envelope_id)
    assert recorded_audits, "审计没入队"
    assert recorded_audits[-1]["request_id"] == header_id, recorded_audits[-1]
