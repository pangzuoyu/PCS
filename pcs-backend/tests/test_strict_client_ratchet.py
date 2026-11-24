"""**`strict_client` 覆盖的棘轮**（P10-F · F3 · 2026-11-18 人裁决）。

## 为什么要有这个测试

⚠️ **默认的 `client` fixture 把项目守卫 mock 成永远 True**
（`UserProjectService.check_user_project_access`）⇒ ⇒ 于是：

> **凡是用默认 `client` 跑的「越权被拒」断言，都是 no-op** ——
> 把端点里的授权调用**删掉**，测试**照样绿**。

⇒ ⇒ 这是 ce review #5（角色闸挡在项目守卫前 ⇒ `403 === 403` ⇒ 项目守卫
**一次都没执行**）**同族的病** ⇒ ⇒ **测试环境的 mock 让授权判定变成空转**。

⇒ ⇒ F3 审计的「已覆盖」结论因此有个**前提**：那条断言必须**用 `strict_client`**
⇒ ⇒ 只用默认 `client` 的断言**不算数**。

⇒ ⇒ **棘轮**：审计每推进一个「带项目维度」的端点 ⇒ ⇒ 就得补一条
`strict_client` 断言 ⇒ ⇒ ⇒ 本测试让这件事**可执行、可检查**。

## ⚠️ **从「计数」改成「清单」**（2026-11-18 · ce-code-review · TODO-192 #11）

此前台账是**一个数**（`AUDITED_PROJECT_SCOPED_ENDPOINTS = 2`）⇒ ⇒ 棘轮拿它跟
「`strict_client` 测试函数数」比 ⇒ ⇒ 而仓里那条数早已 17+ ⇒ ⇒ ⇒
**棘轮永远不会红** ⇒ ⇒ ⇒ 形同虚设（评审员实测：阈值 2 · 实际 17+）。

⇒ ⇒ 现在台账是**路径清单**（`tests/conftest.py`）⇒ ⇒ 棘轮**逐条**查：
⇒ ⇒ **清单里的每一条路径，都必须有一个 `strict_client` 测试真的提到它**
⇒ ⇒ ⇒ 删掉那条断言 ⇒ ⇒ ⇒ 立刻红。
⇒ ⇒ 另有一条**下限**（`AUDITED_PROJECT_SCOPED_ENDPOINTS_MIN`）⇒ ⇒ 防止
「悄悄把一条从清单里删掉」⇒ ⇒ ⇒ 只增不减。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.conftest import (
    AUDITED_PROJECT_SCOPED_ENDPOINTS,
    AUDITED_PROJECT_SCOPED_ENDPOINTS_MIN,
    STRICT_CLIENT_TEST_MIN,
)

TESTS_DIR = Path(__file__).resolve().parent

#: 测试里出现的 URL（f-string 里的 `{...}` 归一化成 `{}` ⇒ ⇒ 才可比）
_URL_RE = re.compile(r"/api/v1/[A-Za-z0-9_\-/\{\}\[\]'\.\(\):]*")


def _normalise(path: str) -> str:
    """路径模板归一化：`{ws.workspace_id}` ⇒ ⇒ `{}` ⇒ ⇒ 与 `{workspace_id}` 可比。"""
    return re.sub(r"\{[^}]*\}", "{}", path)


def _strict_client_test_count() -> int:
    """用到 `strict_client` 的**测试函数**数（按 AST 数 ⇒ 不受排版影响）。"""
    count = 0
    for path in TESTS_DIR.rglob("test_*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — 解析不了的测试文件跳过
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            args = node.args
            names = {
                a.arg
                for a in (args.posonlyargs + args.args + args.kwonlyargs)
            }
            if "strict_client" in names:
                count += 1
    return count


def _strict_client_urls() -> set[str]:
    """**所有** `strict_client` 测试里出现过的 URL（已归一化）。

    ⚠️ 扫**整个测试函数体**（不是只扫字符串常量）⇒ ⇒ f-string 拼接出来的
    URL（`f"/api/v1/records/piping/{pipe_id}"`）也算 ⇒ ⇒ ⇒ 不会漏。
    """
    urls: set[str] = set()
    for path in TESTS_DIR.rglob("test_*.py"):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover — 解析不了的测试文件跳过
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            args = node.args
            names = {
                a.arg
                for a in (args.posonlyargs + args.args + args.kwonlyargs)
            }
            if "strict_client" not in names:
                continue
            segment = ast.get_source_segment(source, node) or ""
            for match in _URL_RE.finditer(segment):
                urls.add(_normalise(match.group(0)))
    return urls


def test_every_audited_project_scoped_endpoint_has_a_strict_client_assertion() -> None:
    """⚠️ **棘轮（逐条）**：清单里的每个端点 ⇒ ⇒ 都要有 `strict_client` 断言。

    ⇒ ⇒ 删掉那条断言 ⇒ ⇒ 这里红 ⇒ ⇒ ⇒ 「台账说有、其实没有」不可能发生。
    """
    urls = _strict_client_urls()
    missing = [
        path for path in AUDITED_PROJECT_SCOPED_ENDPOINTS
        if not any(url.startswith(_normalise(path)) for url in urls)
    ]
    assert not missing, (
        f"台账里这些端点**没有** strict_client 断言：{missing}"
        " ⇒ ⇒ 默认 client 把守卫 mock 成永远 True ⇒ ⇒ 那类断言是 no-op"
        f"（现有 strict_client 测试函数：{_strict_client_test_count()} 个）"
    )


def test_the_audited_list_never_shrinks() -> None:
    """⚠️ **只增不减**：台账条目变少 ⇒ ⇒ 这里红（防止「悄悄删一条」）。"""
    assert len(AUDITED_PROJECT_SCOPED_ENDPOINTS) >= AUDITED_PROJECT_SCOPED_ENDPOINTS_MIN, (
        f"台账只剩 {len(AUDITED_PROJECT_SCOPED_ENDPOINTS)} 条，"
        f"下限是 {AUDITED_PROJECT_SCOPED_ENDPOINTS_MIN} 条 ⇒ ⇒ 有人把条目删了"
    )


def test_strict_client_coverage_keeps_up_with_the_audit() -> None:
    """⚠️ **数量版**（保留）：`strict_client` 的测试数 ≥ 台账条目数。

    ⇒ ⇒ 逐条那版（上面）是**主力**；这版防的是「台账加了条目、却把别处的
    ⇒ ⇒ 断言删了凑数」。
    """
    count = _strict_client_test_count()
    assert count >= len(AUDITED_PROJECT_SCOPED_ENDPOINTS), (
        f"用到 strict_client 的测试只有 {count} 个，"
        f"而已审的「带项目维度」端点有 {len(AUDITED_PROJECT_SCOPED_ENDPOINTS)} 个"
        " ⇒ ⇒ 审计推进了却没补 strict_client 断言"
    )


def test_the_number_of_strict_client_tests_never_shrinks() -> None:
    """⚠️ **断言数只增不减**（防止「一条条删断言」）。

    ⇒ ⇒ 逐条路径检查只看「这个端点**还有没有** `strict_client` 断言」
    ⇒ ⇒ ⇒ 同一个端点有 3 条断言时删掉 1 条 ⇒ ⇒ 它**看不出来**
    ⇒ ⇒ ⇒ 所以另有一条**数量下限** ⇒ ⇒ ⇒ 删一条 ⇒ ⇒ ⇒ 这里红。
    """
    count = _strict_client_test_count()
    assert count >= STRICT_CLIENT_TEST_MIN, (
        f"strict_client 测试只有 {count} 个，下限是 {STRICT_CLIENT_TEST_MIN} 个"
        " ⇒ ⇒ 有人删了守卫断言 ⇒ ⇒ 默认 client 把守卫 mock 成永远 True"
        " ⇒ ⇒ 那些断言是 no-op"
    )


# ---------------------------------------------------------------------------
# 「第三个 client」守卫（TODO-189 ③）
# ---------------------------------------------------------------------------

#: **已知**自建 ASGI client 的文件（历史分散点 · **只减不增**）。
#:
#: ⚠️ **为什么要有这条**：棘轮只数 `strict_client` ⇒ ⇒ 一个**自建**的
#: 「不 mock 守卫」的 client 写出来的用例 ⇒ ⇒ 对棘轮**隐形** ⇒ ⇒
#: 「已审面」的计数**偏小** ⇒ ⇒ 而且**没人知道**。
#:
#: ⇒ ⇒ 这份清单是**已知的分散点**⇒ ⇒ 新增一个 ⇒ ⇒ 这里红 ⇒ ⇒
#: 要么改用 `tests/conftest.py` 的 `client` / `strict_client` ⇒ ⇒
#: 要么**明确**加进这份清单（那是「有意识地再开一个」⇒ ⇒ 有人看见过）。
KNOWN_CUSTOM_CLIENT_FILES: frozenset[str] = frozenset(
    {
        "api/v1/test_ai_audit_middleware.py",
        "api/v1/test_deliverables_progress_aggregate.py",
        # ⚠️ **P10-C · T1a**：`/metrics` 挂在 **app 根路径**（Prometheus 抓
        # 服务根 ⇒ ⇒ ⇒ 挂进 `api_router` 会被 `/api/v1` 前缀带走 ⇒ ⇒ ⇒ 404）
        # ⇒ ⇒ ⇒ 而 conftest 的 `client` fixture 只挂 `api_router`
        # ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ **那个 app 里压根没有 `/metrics`** ⇒ ⇒ ⇒ 恒 404
        # ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ 只能自建（**测的是真实接线**：中间件 + 根路径挂载）
        "api/v1/test_metrics_endpoint.py",
        "api/v1/test_p9a_dlv_011_authorization.py",
        "api/v1/test_project_creation.py",
        "api/v1/test_record_edits_endpoint.py",
        "api/v1/test_workflow_progress_api.py",
        "core/test_outbound_ai_client.py",
        "e2e_flows/conftest.py",
        "test_dual_engine.py",
        "test_token_issuer_endpoints.py",
    }
)


def _files_building_an_asgi_client() -> set[str]:
    """哪些测试文件**自建**了 ASGI client（`ASGITransport`）。

    ⚠️ **判据 = `ASGITransport(`** ⇒ ⇒ 命中的就是「自己 new 一个 app + client」
    ⇒ ⇒ 正是「第三个 client」的形状。
    """
    found: set[str] = set()
    for path in TESTS_DIR.rglob("*.py"):
        rel = path.relative_to(TESTS_DIR).as_posix()
        if rel == "conftest.py":
            continue  # 根 conftest 是**唯一真相源**（client / strict_client）
        if rel == Path(__file__).relative_to(TESTS_DIR).as_posix():
            continue  # 本文件自己写着这个关键字 ⇒ ⇒ 别把自己算进去
        if "ASGITransport(" in path.read_text(encoding="utf-8", errors="ignore"):
            found.add(rel)
    return found


def test_no_new_file_may_build_its_own_client() -> None:
    """⚠️ **自建 client 的文件集合被冻结** ⇒ ⇒ 新增一个 ⇒ ⇒ 这里红。

    ⇒ ⇒ 「第三个 client」从此**必须有人看见**才能存在。
    """
    found = _files_building_an_asgi_client()
    new_files = found - KNOWN_CUSTOM_CLIENT_FILES
    assert not new_files, (
        f"这些文件**自建**了 ASGI client：{sorted(new_files)}"
        " ⇒ ⇒ 棘轮只数 strict_client ⇒ ⇒ 它们的守卫用例对棘轮隐形"
        " ⇒ ⇒ 请改用 tests/conftest.py 的 client / strict_client"
        "（确实需要自建 ⇒ ⇒ 请明确加进 KNOWN_CUSTOM_CLIENT_FILES）"
    )

