"""守卫覆盖审计的端点枚举脚本（P10-F · F3）的守卫。

## 为什么要有这个测试

枚举脚本的输出**就是 F3-T2/T3 的初判表** ⇒ ⇒ 它错一个字段，
后面 56 个端点的审计就建在错的地基上 ⇒ ⇒ 必须钉住。

⚠️ **已抓到的真 bug**（写这个测试时发现）：`router = APIRouter(prefix=...)`
写成 **`AnnAssign`**（带类型标注）时 ⇒ ⇒ 前缀被漏掉 ⇒ ⇒ 路径少一段
⇒ ⇒ 端点表里的路径**对不上真实路径** ⇒ ⇒ 审计时按表找端点会**找错**。

⇒ ⇒ 所以这里的第一条断言就是「路径带前缀」。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit_list_endpoints import classify, enumerate_endpoints

#: 合成模块：四种守卫态各一个 + 一个带前缀的 router（**AnnAssign** 形式）。
SYNTHETIC = '''
from __future__ import annotations

from fastapi import APIRouter

router: APIRouter = APIRouter(prefix="/demo")


@router.get("/things/{thing_id}")
async def get_thing(thing_id: str):
    return {"id": thing_id}


@router.post("/things")
async def create_thing(user=Depends(current_actor)):
    require_roles(user, "DESIGNER")
    return {}


@router.get("/things/{thing_id}/ro")
async def get_thing_ro(thing_id: str):
    check_project_access_or_404(thing_id)
    return {}


@router.get("/open")
async def open_thing():
    return {}
'''


@pytest.fixture()
def api_dir(tmp_path: Path) -> Path:
    (tmp_path / "demo.py").write_text(SYNTHETIC, encoding="utf-8")
    return tmp_path


def test_paths_carry_the_router_prefix(api_dir: Path) -> None:
    """⚠️ **前缀必须带上** —— 少了它，端点表里的路径对不上真实路径。"""
    rows = enumerate_endpoints(api_dir)
    paths = {r["path"] for r in rows}
    assert "/demo/things/{thing_id}" in paths, f"前缀丢了：{sorted(paths)}"


def test_guard_state_has_three_states(api_dir: Path) -> None:
    """⚠️ **三态**（授权闸 / 角色闸·只认证 / 无任何调用）——不是「5 个调用任一出现」。"""
    by_func = {r["func"]: r for r in enumerate_endpoints(api_dir)}
    assert by_func["get_thing_ro"]["state"] == "authz", "项目授权闸必须认出来"
    assert by_func["create_thing"]["state"] == "role_only", "角色闸**不是**项目授权闸"
    assert by_func["get_thing"]["state"] == "none", "无任何守卫调用 ⇒ 必须是 none"
    assert by_func["open_thing"]["state"] == "none"


def test_role_gate_is_not_project_authorization() -> None:
    """⚠️ **角色闸 ≠ 项目授权闸**（ce review #5 的形状）⇒ ⇒ 分开判。"""
    assert classify(["require_roles"]) == "role_only"
    assert classify(["current_actor"]) == "role_only"
    assert classify(["check_project_access_or_404"]) == "authz"
    assert classify(["require_formal_project_workspace"]) == "authz"
    assert classify(["require_roles", "check_project_access"]) == "authz"
    assert classify([]) == "none"


def test_dependency_style_guards_are_seen(api_dir: Path) -> None:
    """⚠️ 守卫写成 **`Depends(...)`**（签名里）也要认出来。

    ⇒ ⇒ `current_actor` 多数端点是用 `Depends(current_actor)` 注入的
    ⇒ ⇒ 只扫函数体 ⇒ ⇒ 会把它判成「无任何调用」⇒ ⇒ **假阳性**。
    """
    by_func = {r["func"]: r for r in enumerate_endpoints(api_dir)}
    assert "current_actor" in by_func["create_thing"]["guards"]


def test_real_modules_have_the_endpoint_counts_the_plan_snapshotted() -> None:
    """⚠️ **逐模块计数**（计划的快照 vs 现在的源码）⇒ ⇒ 对不上要**说清**。

    ⚠️ 这不是「数字必须永远相等」的断言 ⇒ ⇒ 端点数会随功能增删变
    ⇒ ⇒ 断的是「**枚举能跑、且这些模块确实存在**」+ 端点数**落在合理区间**。
    """
    rows = enumerate_endpoints()
    by_module: dict[str, int] = {}
    for row in rows:
        by_module[row["module"]] = by_module.get(row["module"], 0) + 1
    for module, lo, hi in (
        ("config", 8, 16),
        ("report_builder", 6, 14),
        ("report", 6, 14),
        ("records", 4, 10),
        ("psychro", 10, 18),
        ("workspaces", 3, 8),
        ("user_projects", 3, 8),
        ("admin_users", 2, 6),
        ("audit", 2, 6),
        ("meta", 4, 10),
    ):
        assert module in by_module, f"模块 {module} 没被枚举到"
        assert lo <= by_module[module] <= hi, (
            f"{module} 的端点数 {by_module[module]} 不在 [{lo},{hi}] ⇒ ⇒ "
            "要么源码变了，要么枚举漏了 ⇒ ⇒ 开工前要重核"
        )


def test_local_wrapper_calls_are_reported(api_dir: Path) -> None:
    """⚠️ **本地封装**（守卫可能藏在里面）也要报出来。

    ⇒ ⇒ `report.py` 的 `GET /report/{id}/download` 调的是本地
    ⇒ ⇒ `_guard_project(...)` ⇒ ⇒ 只看「已知守卫名」会把它判成
    ⇒ ⇒ 「无任何调用」⇒ ⇒ **假阳性**。
    """
    src = SYNTHETIC + '''

def _guard_project(project_id: str) -> None:
    return None


@router.get("/guarded")
async def guarded(thing_id: str):
    _guard_project(thing_id)
    return {}
'''
    (api_dir / "demo2.py").write_text(src, encoding="utf-8")
    by_func = {r["func"]: r for r in enumerate_endpoints(api_dir)}
    assert "_guard_project" in by_func["guarded"]["local_calls"], (
        "本地封装没被报出来 ⇒ ⇒ 审计者会以为这个端点完全没有守卫"
    )


def test_type_alias_dependencies_are_unwrapped(api_dir: Path) -> None:
    """⚠️ **依赖注入的别名**（`ActorDep = Annotated[..., Depends(current_actor)]`）
    ⇒ ⇒ 端点签名里只有 `actor: ActorDep` ⇒ ⇒ 字面量 `current_actor` 一个都看不到
    ⇒ ⇒ 不解包 ⇒ ⇒ 把它判成「无任何调用」⇒ ⇒ **假阴性**（端点其实有认证）。
    """
    src = '''
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

router = APIRouter(prefix="/alias")


class _Actor:
    pass


ActorDep = Annotated[_Actor, Depends(current_actor)]


@router.get("/x")
async def get_x(actor: ActorDep):
    return {}
'''
    (api_dir / "demo3.py").write_text(src, encoding="utf-8")
    by_func = {r["func"]: r for r in enumerate_endpoints(api_dir)}
    assert "current_actor" in by_func["get_x"]["guards"], (
        "别名里的 `current_actor` 没解出来 ⇒ ⇒ 有认证的端点被判成「无任何调用」"
    )


def test_every_row_has_a_state_and_a_method() -> None:
    """每个端点都必须有**方法**与**三态**⇒ ⇒ 表里不许有空格。"""
    for row in enumerate_endpoints():
        assert row["method"] in {"GET", "POST", "PUT", "PATCH", "DELETE"}
        assert row["state"] in {"authz", "role_only", "none"}
