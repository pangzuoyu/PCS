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

⚠️ **本测试不检查「每条已覆盖结论都有 strict_client 断言」** ⇒ ⇒ 那需要
审计结论表进仓库 ⇒ ⇒ 属 F3-T5 的产出 ⇒ ⇒ ⇒ 本棘轮只管**数量**
⇒ ⇒ 数量只增不减 ⇒ ⇒ ⇒ 审计推进时它会拦住「只审不补断言」。
"""
from __future__ import annotations

import ast
from pathlib import Path

from tests.conftest import AUDITED_PROJECT_SCOPED_ENDPOINTS

TESTS_DIR = Path(__file__).resolve().parent


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


def test_strict_client_coverage_keeps_up_with_the_audit() -> None:
    """⚠️ **棘轮**：`strict_client` 的测试数 ≥ 已审的「带项目维度」端点数。

    ⇒ ⇒ 审计推进 ⇒ ⇒ 必须补断言 ⇒ ⇒ 否则这里红。
    """
    count = _strict_client_test_count()
    assert count >= AUDITED_PROJECT_SCOPED_ENDPOINTS, (
        f"用到 strict_client 的测试只有 {count} 个，"
        f"而已审的「带项目维度」端点有 {AUDITED_PROJECT_SCOPED_ENDPOINTS} 个"
        " ⇒ ⇒ 审计推进了却没补 strict_client 断言"
        " ⇒ ⇒ 默认 client 把守卫 mock 成永远 True ⇒ ⇒ 那类断言是 no-op"
    )
