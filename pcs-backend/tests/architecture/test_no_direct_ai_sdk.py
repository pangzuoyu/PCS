"""AI SDK 的**架构守卫**（P10-A · Task T14 · 评审 #7 修过）。

## 为什么需要

AI 端点现在一律 501 ⇒ AI 调用**只能**从
`app/core/outbound_ai_client.py` 出去（那里有：调用时二次校验内网 CIDR ·
脱敏 · 审计）。
⇒ 有人**绕过**它直连模型服务 ⇒ 少了三道防护（内网校验 / 脱敏 / 审计）。

⇒ 守卫把「唯一的出口」钉死。

## ⚠️ 规则**倒过来**了（评审 #7 · 2026-11-12）

旧规则是「**认出**已知的几种写法」：

- SDK 导入名单（openai / ollama / vllm / langchain …）
- `httpx.<method>(url)` 且 url 字面量里含**四个标记串**之一

⇒ **自然的绕过** `await httpx.post("http://llm.internal:8000/v1/chat/completions", json=...)`
**两个规则都不匹配** ⇒ 守卫照样绿 ⇒ 它守的东西**根本没被守**。

⇒ 新规则是「**除唯一出口外，禁止出现网络客户端**」：
`httpx` / `requests` / `aiohttp` / `urllib3` / `urllib.request` 一律不许在
`app/` 里被导入（`urllib.parse` 这种纯字符串工具**不受影响**）。
⇒ 将来若有**合法**的出站集成（比如调外部报表服务），
在 `ALLOWED_FILES` 里**显式**加一行并写明理由 —— 这是**棘轮**：
默认拒绝、显式放行。

## ⚠️ 守卫必须**被看见红过**（评审 #7 的另一半）

一个从来没红过的守卫，等于没有守卫 ⇒ 本文件带**负控**：
造几个**违例**文件喂给扫描器，断言它**确实**报出来
（扫描器自己的灵敏度是被测出来的，不是被假设的）。

## ⚠️ 静态扫描的局限（写在这里，别把它当万能护栏）

扫描的是**导入**与**调用形状** ⇒
「先在别处 import，再把函数对象传进来」这类**间接**用法扫不到
⇒ 约定：**AI 端点的 URL 必须直接写 `settings.ai_endpoint` 或字面量**。
"""
from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

#: 允许出现 AI SDK / 网络客户端的文件（**唯一出口**）。
#: ⚠️ 加行必须写理由 —— 这是**显式放行**，不是顺手一提。
ALLOWED_FILES: frozenset[str] = frozenset({"core/outbound_ai_client.py"})

#: 被禁止的 AI SDK 顶层包名。
FORBIDDEN_SDK_ROOTS = frozenset(
    {
        "openai",
        "ollama",
        "vllm",
        "langchain",
        "langchain_core",
        "langchain_community",
        "langgraph",
        "llama_index",
        "chromadb",
        "sentence_transformers",
        "transformers",
        "torch",
        "anthropic",
        "litellm",
    }
)

#: 被禁止的**网络客户端**顶层包名（评审 #7：规则倒过来）。
#: ⚠️ **不含 `urllib`** —— `urllib.parse` 是纯字符串工具（`ai_cidr` 在用）
#: ⇒ 只禁 `urllib.request`（见 `FORBIDDEN_NETWORK_MODULES`）。
FORBIDDEN_NETWORK_ROOTS = frozenset({"httpx", "requests", "aiohttp", "urllib3"})

#: 被禁止的**网络客户端**子模块（完整模块名）。
FORBIDDEN_NETWORK_MODULES = frozenset({"urllib.request", "http.client"})

#: 「这个调用在打 AI 端点」的特征串（**额外**信号，不是主规则）。
AI_ENDPOINT_MARKERS = ("ai_endpoint", "/api/v1/ai", "ai.intent", "ai/knowledge")


def _python_files() -> list[Path]:
    return sorted(p for p in APP_ROOT.rglob("*.py"))


def _rel(path: Path) -> str:
    return str(path.relative_to(APP_ROOT))


def _imported_roots(tree: ast.AST) -> set[str]:
    """所有 `import` / `from X import ...` 的**顶层包名**。"""
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


def _imported_modules(tree: ast.AST) -> set[str]:
    """所有被导入的**完整模块名**（`urllib.request` 这种子模块）。"""
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                modules.add(node.module)
    return modules


def _httpx_calls(tree: ast.AST) -> list[ast.Call]:
    """所有**看起来像 httpx 调用**的节点（含 `httpx.post` / `httpx.Client(...)`）。"""
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id == "httpx":
                calls.append(node)
        elif isinstance(func, ast.Name) and func.id in {"httpx"}:
            calls.append(node)
    return calls


def _mentions_ai_endpoint(node: ast.AST) -> bool:
    """这个表达式里有没有「AI 端点」的特征。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if any(marker in sub.value for marker in AI_ENDPOINT_MARKERS):
                return True
        if isinstance(sub, ast.Attribute) and sub.attr in {"ai_endpoint"}:
            return True
    return False


def scan_offenders(path: Path) -> list[str]:
    """扫**一个**文件，返回它违反的规则（空列表 = 干净）。

    ⚠️ 纯函数（只读、不依赖仓库状态）⇒ **负控**可以直接喂它造出来的文件。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []

    roots = _imported_roots(tree)
    sdk_hit = roots & FORBIDDEN_SDK_ROOTS
    if sdk_hit:
        offenders.append(f"AI SDK 导入：{sorted(sdk_hit)}")

    modules = _imported_modules(tree)
    net_hit = set(roots & FORBIDDEN_NETWORK_ROOTS) | (
        modules & FORBIDDEN_NETWORK_MODULES
    )
    if net_hit:
        offenders.append(f"网络客户端导入：{sorted(net_hit)}")

    # ⚠️ **额外**信号：httpx 调用的 URL 里出现 AI 特征串。
    for call in _httpx_calls(tree):
        candidates = list(call.args[:1])
        candidates += [kw.value for kw in call.keywords if kw.arg == "url"]
        for candidate in candidates:
            if _mentions_ai_endpoint(candidate):
                offenders.append(f"httpx 调 AI 端点（行 {call.lineno}）")
                break
    return offenders


def test_no_module_outside_outbound_client_uses_ai_sdks_or_network_clients() -> None:
    """除**唯一出口**外，`app/` 里不许出现 AI SDK / 网络客户端。

    ⚠️ 本批**还没装** AI SDK ⇒ 那半边现在**恒绿**（防将来）。
    ⚠️ 网络客户端那半边**今天就有牙**：绕过唯一出口直连模型服务
    ⇒ 少了「内网 CIDR 二次校验 / 脱敏 / 审计」三道防护。
    """
    offenders: list[str] = []
    for path in _python_files():
        rel = _rel(path)
        if rel in ALLOWED_FILES:
            continue
        for offender in scan_offenders(path):
            offenders.append(f"{rel}: {offender}")

    assert not offenders, (
        "AI 出口只允许在 "
        f"{sorted(ALLOWED_FILES)}（唯一出口）：{offenders}"
    )


def test_the_guard_detects_a_synthetic_ai_sdk_import(tmp_path: Path) -> None:
    """⚠️ **负控**（评审 #7）—— 扫描器必须**真的**抓得到 AI SDK 导入。"""
    offender = tmp_path / "offender.py"
    offender.write_text("import openai\n", encoding="utf-8")

    assert scan_offenders(offender), "扫描器没抓到 AI SDK 导入 ⇒ 守卫是空壳"


def test_the_guard_detects_the_natural_bypass(tmp_path: Path) -> None:
    """⚠️ **负控**（评审 #7）—— **自然的绕过**必须被抓到。

    `await httpx.post("http://llm.internal:8000/v1/chat/completions", json=...)`
    **不含**任何标记串 ⇒ 旧规则（查标记）**抓不到** ⇒ 旧守卫是空壳。
    """
    offender = tmp_path / "bypass.py"
    offender.write_text(
        "import httpx\n"
        "\n"
        "\n"
        "async def go():\n"
        '    return await httpx.post("http://llm.internal:8000/v1/chat/completions", json={})\n',
        encoding="utf-8",
    )

    assert scan_offenders(offender), "扫描器没抓到直连模型服务的绕过 ⇒ 守卫是空壳"


def test_the_guard_allows_the_sanctioned_exit() -> None:
    """**唯一出口**本身必须存在（守卫不能指向一个不存在的文件）。"""
    for rel in ALLOWED_FILES:
        assert (APP_ROOT / rel).exists(), f"唯一出口 {rel} 不存在"


def test_the_scanner_does_not_flag_plain_string_helpers(tmp_path: Path) -> None:
    """⚠️ **别误伤** —— `urllib.parse` 是纯字符串工具（`ai_cidr` 在用）。

    ⇒ 守卫禁的是 `urllib.request`（能发网络请求的那个），不是整个 `urllib`。
    """
    innocent = tmp_path / "innocent.py"
    innocent.write_text(
        "from urllib.parse import urlparse\n", encoding="utf-8"
    )

    assert scan_offenders(innocent) == []
