"""record_hash 不变式的**集合关系**契约（P9A-4 D0 · ADR-0048 §⑥）。

## 为什么是「集合关系」而不是「行为」测试

行为测试（`tests/services/test_record_hash_invariant.py`）只能覆盖**已登记的
那几张表**。若将来有人给第 7 张结果表加了 `PATCH /results/{id}` 端点，
行为测试不会红 —— 而那张表会**静默地没有并发保护**（D2 的 guard 对它永远
走「放行」分支）。

⇒ 本文件做两件事：
1. **发现**：扫 `app/api/v1/*.py` 里所有 `PATCH|PUT` 且路径含 `/results` 的
   端点 ⇒ 得到的模块集合必须与登记集合**完全相等**（多一个 ⇒ 红）。
2. **位置**：每个登记的 update service，其「改业务字段」函数里
   `compute_record_hash` 的调用必须**在 setattr 之后、在 commit 之前** ——
   早了算的是旧内容，晚了算的是已提交的内容（且没落库）。

⚠️ 本文件**不**检查「谁调用了这个 update service」—— 那是 D2 的接线
（6 个 API 端点），不在 D0 范围。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
API_DIR = BACKEND / "app" / "api" / "v1"
SERVICES = BACKEND / "app" / "services"

# 登记：有 PATCH /results/{id} 端点、且必须有 record_hash 并发令牌的结果表。
# 键 = API 模块名，值 = 承载 update 逻辑的 service 文件（相对 app/services/）。
REGISTERED: dict[str, str] = {
    "cool_tower": "cool_tower/cool_tower_persist_service.py",
    "filtration": "filtration/filtration_persist_service.py",
    "flare": "flare/flare_persist_service.py",
    "open_channel": "open_channel/open_channel_persist_service.py",
    "psychro": "psychro/psychro_persist_service.py",
    "cost_est": "cost_est/cost_est_persist_service.py",
}


def _result_patch_modules() -> set[str]:
    """扫出所有带 `PATCH|PUT ... /results` 路由的 API 模块。"""
    found: set[str] = set()
    for py in sorted(API_DIR.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                fn = dec.func
                method = None
                if isinstance(fn, ast.Attribute) and fn.attr in {"patch", "put"}:
                    method = fn.attr
                elif isinstance(fn, ast.Name) and fn.id in {"patch", "put"}:
                    method = fn.id
                if method is None:
                    continue
                for arg in dec.args:
                    path = arg.value if isinstance(arg, ast.Constant) else None
                    if isinstance(path, str) and "/results" in path:
                        found.add(py.stem)
    return found


def _update_function(tree: ast.Module, path: Path) -> ast.AsyncFunctionDef:
    """找出该 service 文件里「改业务字段」的 update 函数。

    判据：函数名以 `update_` 开头 **且** 体内有 `setattr(<record-like>, ...)`。
    """
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        if not node.name.startswith("update_"):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                if sub.func.id == "setattr":
                    hits.append(node)
                    break
    assert len(hits) == 1, (
        f"{path.name}: 期望恰好 1 个「改业务字段」的 update 函数，"
        f"实际 {len(hits)} 个（{[h.name for h in hits]}）"
    )
    return hits[0]


def _call_lineno(fn: ast.AST, name: str) -> list[int]:
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name) and target.id == name:
                out.append(node.lineno)
            elif (
                isinstance(target, ast.Attribute)
                and target.attr == name
                and isinstance(target.value, ast.Name)
                and target.value.id == "compute_record_hash"
            ):
                out.append(node.lineno)
    return out


def test_discovered_result_patch_endpoints_match_the_registry():
    """发现集合 == 登记集合。新增 PATCH /results 端点必须先登记（否则红）。"""
    assert _result_patch_modules() == set(REGISTERED), (
        "有 PATCH/PUT /results 端点但未登记到 record_hash 不变式："
        f"{_result_patch_modules() - set(REGISTERED)}；"
        f"登记了但端点没了：{set(REGISTERED) - _result_patch_modules()}"
    )


@pytest.mark.parametrize("module_name", sorted(REGISTERED))
def test_update_service_recomputes_hash_after_mutation_before_commit(module_name):
    """`compute_record_hash` 必须在 setattr 之后、commit 之前调用。"""
    rel = REGISTERED[module_name]
    path = SERVICES / rel
    assert path.exists(), f"登记的 service 文件不存在：{rel}"

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    fn = _update_function(tree, path)

    setattr_lines = _call_lineno(fn, "setattr")
    hash_lines = _call_lineno(fn, "compute_record_hash")
    commit_lines = [
        node.lineno
        for node in ast.walk(fn)
        if isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "commit"
    ]

    assert setattr_lines, f"{path.name}: 找不到 setattr 调用"
    assert hash_lines, (
        f"{path.name}:{fn.name} 改了业务字段却没重算 record_hash "
        "⇒ D2 的并发检测对该表是空操作"
    )
    assert commit_lines, f"{path.name}:{fn.name} 找不到 session.commit()"
    assert max(setattr_lines) < min(hash_lines), (
        f"{path.name}:{fn.name} 重算发生在改字段之前 ⇒ 算的是旧内容"
    )
    assert min(hash_lines) < min(commit_lines), (
        f"{path.name}:{fn.name} 重算发生在 commit 之后 ⇒ 新 hash 没落库"
    )
