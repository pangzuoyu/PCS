"""`config.py` **每一条**角色闸都要有 403 断言（TODO-173）。

## 为什么有本文件

TODO-173（P10-F · F3-T3a 审计）：`app/api/v1/config.py` 里有 **11 个**端点
带 `require_roles(...)` 闸门 ⇒ ⇒ 但**没有一条**「角色不够 ⇒ ⇒ 403」的断言
⇒ ⇒ ⇒ 「闸门在代码里」这件事**没有任何东西守着** ⇒ ⇒
把 `require_roles` 删掉，整份测试**照样全绿**。

⚠️ 与 TODO-181 同族，但更狠：TODO-181 的守卫是**项目授权**
（`check_user_project_access`）⇒ ⇒ 默认 `client` 把它 mock 成永远 True
⇒ ⇒ 断言写了也是 no-op；**这里**的角色闸走的是 `current_actor` 解析出来的
**角色字符串** ⇒ ⇒ **不受那个 mock 影响** ⇒ ⇒ ⇒ 断言是**真的**。

⇒ ⇒ 本文件两件事：
① **逐条**用「角色不够」的角色打一遍 ⇒ ⇒ 必须 403；
② **完整性**：从 `config.py` 的 **AST** 里推出「哪些端点带角色闸」
   ⇒ ⇒ 与本文件的清单**逐条比对** ⇒ ⇒ **新增一个带闸门的端点却忘了写断言**
   ⇒ ⇒ 本文件立刻红。
"""
from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest

from app.api.v1.config import ALLOWED_ROLES
from app.core.security import create_access_token

#: (method, path, 允许的角色, 请求体) —— 路径里的 `{asset_id}` 用随机 id 填。
#:
#: ⚠️ **为什么可以随便填 asset_id**：`require_roles` 是每个端点的**第一句**
#: ⇒ ⇒ 角色不够时**根本走不到**取资产的逻辑 ⇒ ⇒ 不需要准备资产行。
_CASES: list[tuple[str, str, tuple[str, ...], dict | None]] = [
    ("GET", "/api/v1/config/assets", ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN"), None),
    ("POST", "/api/v1/config/assets", ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN"),
     {"category": "CATEGORY_2", "name": "角色闸用例"}),
    ("POST", "/api/v1/config/assets/{asset_id}/versions",
     ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN"),
     {"content_json": {"expression": "a + b"}}),
    ("POST", "/api/v1/config/assets/{asset_id}/fork",
     ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN"), {}),
    ("POST", "/api/v1/config/assets/{asset_id}/submit",
     ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN"), None),
    ("POST", "/api/v1/config/assets/{asset_id}/approve",
     ("PROCESS_CONTROLLER", "SYSTEM_ADMIN"), None),
    ("POST", "/api/v1/config/assets/{asset_id}/publish",
     ("PROCESS_CONTROLLER", "SYSTEM_ADMIN"), None),
    ("POST", "/api/v1/config/assets/{asset_id}/obsolete",
     ("PROCESS_CONTROLLER", "SYSTEM_ADMIN"), None),
    ("GET", "/api/v1/config/assets/status-report",
     ("DESIGNER", "PROCESS_CONTROLLOR", "SYSTEM_ADMIN"), None),
    ("GET", "/api/v1/config/assets/status-report/export",
     ("DESIGNER", "PROCESS_CONTROLLOR", "SYSTEM_ADMIN"), None),
    ("GET", "/api/v1/config/assets/{asset_id}/diff",
     ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN"), None),
]


def _headers(role: str) -> dict[str, str]:
    token = create_access_token(subject=f"u-{role.lower()}", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("method", "path", "allowed", "body"),
    _CASES,
    ids=[f"{m} {p}" for m, p, _a, _b in _CASES],
)
async def test_role_gate_rejects_a_forbidden_role(client, method, path, allowed, body):
    """⚠️ **角色不够 ⇒ ⇒ 403**（每个带闸门的端点各一条）。"""
    forbidden = sorted(set(ALLOWED_ROLES) - set(allowed))
    assert forbidden, f"{path} 的允许角色已覆盖全白名单 ⇒ ⇒ 这条闸门形同虚设"

    concrete = path.format(asset_id=uuid.uuid4())
    kwargs: dict = {"headers": _headers(forbidden[0])}
    if body is not None:
        kwargs["json"] = body
    if path.endswith("/diff"):
        kwargs["params"] = {"v1": str(uuid.uuid4()), "v2": str(uuid.uuid4())}

    r = await getattr(client, method.lower())(concrete, **kwargs)
    assert r.status_code == 403, (
        f"{method} {path} 对角色 {forbidden[0]} 返回了 {r.status_code}"
        f"（应 403）⇒ ⇒ 角色闸没生效"
    )


# ---------------------------------------------------------------------------
# 完整性：闸门清单与 `config.py` 的 **AST** 逐条比对
# ---------------------------------------------------------------------------


def _gated_endpoints_in_source() -> set[tuple[str, str]]:
    """从 `config.py` 的 AST 推出「哪些端点带角色闸」。

    ⚠️ **为什么用 AST 而不是手抄**：手抄的清单**必然**会漏
    ⇒ ⇒ 漏一个 ⇒ ⇒ 新端点没有 403 断言 ⇒ ⇒ 而没人发现。
    """
    src = Path(__file__).resolve().parents[3] / "app" / "api" / "v1" / "config.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    found: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        route: tuple[str, str] | None = None
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            if not isinstance(dec.func.value, ast.Name) or dec.func.value.id != "router":
                continue
            method = dec.func.attr.upper()
            if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            if not dec.args or not isinstance(dec.args[0], ast.Constant):
                continue
            route = (method, f"/api/v1/config{dec.args[0].value}")
        if route is None:
            continue
        has_gate = any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "require_roles"
            for child in ast.walk(node)
        )
        if has_gate:
            found.add(route)
    return found


def test_every_gated_config_endpoint_has_a_403_assertion():
    """⚠️ **`config.py` 里每一条角色闸都有对应用例**（新增端点忘了写 ⇒ ⇒ 红）。"""
    in_source = _gated_endpoints_in_source()
    covered = {(m, p) for m, p, _a, _b in _CASES}
    missing = in_source - covered
    assert not missing, (
        f"这些端点带角色闸但**没有** 403 断言：{sorted(missing)}"
        f"⇒ ⇒ 请在 test_config_role_gates.py::_CASES 里补一条"
    )
    # 反向：清单里不该有源码里已不存在的端点（否则断言会指向空气）
    stale = covered - in_source
    assert not stale, f"清单里有源码里已不存在的端点（端点改名/删除？）：{sorted(stale)}"
