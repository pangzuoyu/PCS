"""AI SDK 的**架构守卫**（P10-A · Task T14）。

## 为什么需要

AI 端点现在一律 501 ⇒ AI 调用**只能**从
`app/core/outbound_ai_client.py` 出去（那里有：调用时二次校验内网 CIDR ·
脱敏 · 审计）。
⇒ 有人**绕过**它直连模型服务 ⇒ 少了三道防护（内网校验 / 脱敏 / 审计）。

⇒ 守卫把「唯一的出口」钉死。

## ⚠️ 静态扫描的局限（写在这里，别把它当万能护栏）

本守卫扫的是 **URL 字面量 / 属性名** ⇒ `httpx.post(url_var, ...)`（url 是
局部变量）**扫不到** ⇒ 将来若有人用变量调 AI 端点，守卫**抓不到**。
⇒ 约定：**AI 端点的 URL 必须直接写 `settings.ai_endpoint` 或字面量**，
否则绕过守卫。
"""
from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

#: 允许出现 AI SDK 的文件（**唯一出口**）。
ALLOWED_FILE = "core/outbound_ai_client.py"

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

#: 「这个调用在打 AI 端点」的特征串（URL 字面量 / 属性名）。
AI_ENDPOINT_MARKERS = ("ai_endpoint", "/api/v1/ai", "ai.intent", "ai/knowledge")


def _python_files() -> list[Path]:
    return sorted(p for p in APP_ROOT.rglob("*.py"))


def _rel(path: Path) -> str:
    return str(path.relative_to(APP_ROOT))


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


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


def test_no_module_outside_outbound_client_imports_ai_sdks() -> None:
    """openai / ollama / vllm / langchain **只**允许出现在
    `app/core/outbound_ai_client.py`。

    ⚠️ 本批**还没装**这些包 ⇒ 全仓零命中 ⇒ 本条现在**恒绿**。
    ⇒ 它是**防将来**的棘轮：真装上之后，有人绕过唯一出口直连 ⇒ 这里红。
    """
    offenders: list[str] = []
    for path in _python_files():
        rel = _rel(path)
        if rel == ALLOWED_FILE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        hit = _imported_roots(tree) & FORBIDDEN_SDK_ROOTS
        if hit:
            offenders.append(f"{rel}: {sorted(hit)}")

    assert not offenders, (
        "AI SDK 只允许出现在 app/core/outbound_ai_client.py（唯一出口）："
        f"{offenders}"
    )


def test_only_outbound_client_calls_httpx_with_an_ai_endpoint() -> None:
    """⚠️ **httpx 允许被多处用**（不是禁 httpx）⇒ 守卫的是「httpx 调 **AI 端点**」
    ⇒ 只允许 `app/core/outbound_ai_client.py`。

    ⚠️ **静态扫描的局限**：本守卫扫 URL 字面量 / 属性名 ⇒
    `httpx.post(url_var, ...)` 扫不到 ⇒ 约定 AI 端点的 URL 必须直接写
    `settings.ai_endpoint` 或字面量。
    """
    offenders: list[str] = []
    for path in _python_files():
        rel = _rel(path)
        if rel == ALLOWED_FILE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in _httpx_calls(tree):
            if not call.args:
                continue
            if _mentions_ai_endpoint(call.args[0]):
                offenders.append(f"{rel}:{call.lineno}")

    assert not offenders, (
        "用 httpx 打 AI 端点只允许在 app/core/outbound_ai_client.py："
        f"{offenders}"
    )


def test_the_allowed_file_is_the_only_ai_exit() -> None:
    """**唯一出口**本身必须存在（守卫不能指向一个不存在的文件）。"""
    assert (APP_ROOT / ALLOWED_FILE).exists(), f"唯一出口 {ALLOWED_FILE} 不存在"
