#!/usr/bin/env python
"""**守卫覆盖审计**的端点枚举（P10-F · F3）。

## 为什么要有这个脚本

F3-T1 的范围提案说「端点清单可复跑」⇒ ⇒ **可复跑**就得有个脚本 ⇒ ⇒
否则「313 个端点」这个数**谁也验不了**（裁决 2026-11-18 · 建议改 #8）。

⇒ ⇒ 而且它输出的**不只是清单**，还有**守卫三态**（见下）⇒ ⇒
F3-T2/T3 的「4 问表」的第 ② 问（该 id 是否按当前用户/项目做授权判定）
**可以从这个输出里直接取初判** ⇒ ⇒ 免得每个端点都靠人眼重扫一遍。

## ⚠️ **守卫四态**（2026-11-18 裁决 · 修的是初判口径 · **F3-T3b 又修了一次**）

| 态 | 判据（端点体 / 签名里出现的调用） | 含义 | 后续 |
|---|---|---|---|
| `authz` | `check_project_access_or_404` · `check_project_access` | 判「**这个 id 是不是你的**」 | 候选「已覆盖」⇒ F3-T2 核**断言行** |
| `role_only` | `require_roles`（角色闸）· `current_actor`（只认证）· `current_user`（只认证） | 只判「你是什么角色 / 你是谁」⇒ **不判项目归属** | ⚠️ **优先审** —— ce review #5 的形状 |
| `type_only` | `require_formal_workspace` · `require_formal_project_workspace` | 判「**这个工作区是不是 FORMAL**」⇒ ⇒ **既不判项目归属、也不判身份** | ⚠️ **不是授权闸**（见下） |
| `none` | 四个都没出现 | 端点里看不到任何守卫调用 | 候选缺口（**守卫可能在 service 层** ⇒ 不等于真缺口） |

⚠️ **为什么不能合成一档**（裁决前的失真）：

- `current_actor` / `current_user` 是「**拿到当前用户**」，**不是**「判断授权」；
- `require_roles` 是**角色闸**，**不是**项目级授权。

把它们算成「有守卫」⇒ ⇒ **假阴性**：一个端点调了 `current_actor` 但没
`check_project_access` ⇒ ⇒ 被判「有守卫」⇒ ⇒ **不进候选缺口**
⇒ ⇒ **真缺口被漏掉** ⇒ ⇒ 漏掉的缺口**不会**进入后续审计
⇒ ⇒ 比假阳性危险。

⚠️ ⚠️ **F3-T3b 实测踩到的两个分类错误**（⇒ ⇒ 都有守卫测试钉着）：

1. **`current_user` 不在「只认证」那一档** ⇒ ⇒ `meta.py` 的 6 个端点
   （**全部**用 `Depends(current_user)`）被误判成 `none`
   ⇒ ⇒ 审计者会以为它们「匿名可读」⇒ ⇒ **结论整个是错的**
   ⇒ ⇒ ⇒ `current_user` 无 Bearer 头 ⇒ ⇒ **401** ⇒ ⇒ 它与 `current_actor` 同档。
2. **`require_formal_project_workspace` 被算成「项目授权闸」** ⇒ ⇒ **假阳性**
   ⇒ ⇒ 它只判「工作区是不是 FORMAL」⇒ ⇒ **一次也没查 `user_projects`**
   ⇒ ⇒ 而且它是 **fail-open** 的（项目没挂工作区 ⇒ ⇒ 直接放行）
   ⇒ ⇒ ⇒ 算成 `authz` ⇒ ⇒ 端点表说「已覆盖」⇒ ⇒ **结论是错的**
   ⇒ ⇒ ⇒ 它自己单独一档（`type_only`）。

⚠️ **教训**：**分类表本身也要被审** ⇒ ⇒ 否则「工具给的初判」会把
**工具的错**带进**审计的结论**⇒ ⇒ ⇒ 工具的每个分类都要有守卫测试。

## 用法

```bash
# 人读的表（端点 · 三态 · 参数）
uv run python scripts/audit_list_endpoints.py --module config

# 机器读（给后续脚本用）
uv run python scripts/audit_list_endpoints.py --json > /tmp/endpoints.json

# 只要模块与端点数
uv run python scripts/audit_list_endpoints.py --counts
```

⚠️ **口径**：只扫 `app/api/v1/*.py` 里的 **`APIRouter` 装饰的函数**
⇒ ⇒ `app/main.py` 里直接挂的端点（若将来有）**不在其中**。
⚠️ **「守卫不在端点体里」≠「没守卫」** —— 守卫可能在 service 层
⇒ ⇒ 本脚本的输出**只是初判**，不是审计结论。
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

#: 后端目录（本文件在 `pcs-backend/scripts/` ⇒ ⇒ 父目录就是）。
BACKEND = Path(__file__).resolve().parents[1]
#: 被扫的端点目录。
API_DIR = BACKEND / "app" / "api" / "v1"

#: **项目级授权闸** —— 判「这个 id 是不是你的」。
#:
#: ⚠️ **这里不能放 `require_formal_project_workspace`**（F3-T3b 实测踩过）：
#: 它只判「项目所在的工作区是不是 FORMAL」⇒ ⇒ **一次也没查 `user_projects`**
#: ⇒ ⇒ 而且 **fail-open**（项目没挂工作区 ⇒ ⇒ 直接放行）
#: ⇒ ⇒ 算成授权闸 ⇒ ⇒ 端点表说「已覆盖」⇒ ⇒ **结论是错的**。
AUTHZ_GUARDS = frozenset(
    {
        "check_project_access_or_404",
        "check_project_access",
        # ⚠️ **2026-11-18 · ce-code-review（TODO-192 #6）**：**service 层**那两份
        # ⇒ ⇒ 也是「项目/工作区授权闸」⇒ ⇒ 此前**没登记** ⇒ ⇒ ⇒ 端点表把
        # ⇒ ⇒ 「只调了 service 层守卫」的端点判成「无守卫」⇒ ⇒ **假阴性**。
        "require_project_access_or_404",
        "require_workspace_access_or_404",
    }
)
#: **角色闸** —— 判「你是什么角色」⇒ **不判项目归属**。
ROLE_GUARDS = frozenset({"require_roles"})
#: **只认证** —— 判「你是谁」⇒ **不判任何归属**。
#:
#: ⚠️ **`current_user` 也在这一档**（F3-T3b 实测踩过）：`app/api/v1/auth.py`
#: 里的它无 Bearer 头 ⇒ ⇒ **401** ⇒ ⇒ 与 `current_actor` 同档
#: ⇒ ⇒ 不认它 ⇒ ⇒ `meta.py` 的 6 个端点被误判成「无任何守卫」。
WHOAMI_GUARDS = frozenset({"current_actor", "current_user"})
#: **工作区类型闸** —— 判「这个工作区是不是 FORMAL」⇒ ⇒ **既不判身份、也不判归属**。
TYPE_GUARDS = frozenset(
    {
        "require_formal_workspace",
        "require_formal_project_workspace",
        # ⚠️ **2026-11-18**：`require_formal_workspace_type`（从依赖里拆出来的
        # ⇒ ⇒ **同一份**类型闸实现 ⇒ ⇒ 要跟依赖版**同档**。
        "require_formal_workspace_type",
    }
)

#: HTTP 方法（FastAPI 路由装饰器名）。
METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


def _call_tail(node: ast.AST) -> str | None:
    """取调用**被调用者**的末段名（`svc.check_project_access` ⇒ `check_project_access`）。"""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _router_prefix(tree: ast.Module) -> str:
    """模块级 `router = APIRouter(prefix=...)` 的前缀（没有就是空串）。

    ⚠️ **两个坑**（都实测踩过 ⇒ ⇒ 都有守卫钉着）：

    ① **`Assign` 与 `AnnAssign` 都要认** —— 带类型标注的写法
    （`router: APIRouter = APIRouter(prefix="/x")`）会让前缀**整段漏掉**；
    ② **判的是「赋值目标叫 router」**，不是「调用者是 router」⇒ ⇒
    `APIRouter(...)` 的调用者是**类名** ⇒ ⇒ 判错 ⇒ ⇒ 前缀照样漏。
    ⇒ ⇒ 后果一样：端点表里的路径**对不上真实路径** ⇒ ⇒ 审计时按表找端点会**找错**。
    """
    for node in tree.body:
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if not isinstance(value, ast.Call):
            continue
        func = value.func
        # ⚠️ `APIRouter(...)` 可以写成 **Name**（`from fastapi import APIRouter`）
        # 也可以写成 **Attribute**（`fastapi.APIRouter(...)`）⇒ ⇒ 两种都要认
        # ⇒ ⇒ 只认一种 ⇒ ⇒ 前缀静默漏掉（实测踩过）。
        is_api_router = (
            isinstance(func, ast.Name) and func.id == "APIRouter"
        ) or (isinstance(func, ast.Attribute) and func.attr == "APIRouter")
        if not is_api_router:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "router" for t in targets):
            continue
        for kw in value.keywords:
            if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                return str(kw.value.value)
    return ""


def _decorator_route(func: ast.FunctionDef) -> tuple[str, str] | None:
    """返回 `(method, path)`；不是路由装饰器则 `None`。"""
    for dec in func.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        target = dec.func
        if not (
            isinstance(target, ast.Attribute)
            and target.attr in METHODS
            and isinstance(target.value, ast.Name)
            and target.value.id == "router"
        ):
            continue
        path = ""
        if dec.args and isinstance(dec.args[0], ast.Constant):
            path = str(dec.args[0].value)
        for kw in dec.keywords:
            if kw.arg == "path" and isinstance(kw.value, ast.Constant):
                path = str(kw.value.value)
        return target.attr.upper(), path
    return None


def _path_params(path: str) -> list[str]:
    """路径里的 `{param}` 占位符。"""
    return [
        seg[1:-1]
        for seg in path.split("/")
        if seg.startswith("{") and seg.endswith("}")
    ]


def _signature_params(func: ast.FunctionDef) -> list[str]:
    """端点的**参数名**（路径参数 + 查询参数 + body）。"""
    args = func.args
    names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
    return names


def _alias_guards(tree: ast.Module) -> dict[str, set[str]]:
    """模块级**类型别名** ⇒ ⇒ 它内含的守卫名。

    ⚠️ 为什么需要：`report.py` 等模块把依赖注入写成**别名**
    （`ActorDep = Annotated[_Actor, Depends(current_actor)]`）
    ⇒ ⇒ 端点签名里只有 `actor: ActorDep` ⇒ ⇒ **字面量 `current_actor`
    一个都看不到** ⇒ ⇒ 只扫名字 ⇒ ⇒ 会把它判成「**无任何调用**」
    ⇒ ⇒ **假阴性**（端点其实**有**认证）。
    """
    out: dict[str, set[str]] = {}
    interesting = AUTHZ_GUARDS | ROLE_GUARDS | WHOAMI_GUARDS | TYPE_GUARDS
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = {n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)}
        hits = names & interesting
        if not hits:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                out[target.id] = hits
    return out


def _guard_calls(func: ast.FunctionDef, aliases: dict[str, set[str]] | None = None) -> list[str]:
    """端点体 + 签名默认值里出现的**守卫**调用名（去重、保序）。

    ⚠️ **只留四类守卫**（授权闸 / 角色闸 / 只认证 / 类型闸）⇒ ⇒ 其余调用名
    （`select` / `commit` / `model_validate` …）不进表 ⇒ ⇒ 表读得懂。
    ⚠️ **签名里的 `Depends(current_actor)` 也要算** ⇒ ⇒ 多数端点是用
    依赖注入拿当前用户的 ⇒ ⇒ 只扫函数体 ⇒ ⇒ 会误判成「无任何调用」。
    ⚠️ **别名（`ActorDep`）也要解开** ⇒ ⇒ 否则「有认证」会被判成「没有」。
    """
    # ⚠️⚠️ **2026-11-18 · ce-code-review（TODO-192 #6）**：**类型闸也要收**
    # ⇒ ⇒ 此前 `interesting` **不含** `TYPE_GUARDS` ⇒ ⇒ 函数体里的类型闸
    # ⇒ ⇒ **一个都收不到** ⇒ ⇒ ⇒ `type_only` 这一档**不可达**
    # ⇒ ⇒ ⇒ 「三态 → 四态」那次修复（bug-2190）**没做完** ⇒ ⇒ 四态里有一态是空的。
    interesting = AUTHZ_GUARDS | ROLE_GUARDS | WHOAMI_GUARDS | TYPE_GUARDS
    aliases = aliases or {}
    found: list[str] = []

    def _add(name: str | None) -> None:
        if name in interesting and name not in found:
            found.append(name)

    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            _add(_call_tail(node))
        elif isinstance(node, ast.Name):
            # ⚠️ **裸名字引用也要算** —— `Depends(current_actor)` 的**外层**
            # 调用名是 `Depends` ⇒ ⇒ 只看调用尾名 ⇒ ⇒ `current_actor` 被漏
            # ⇒ ⇒ 端点被误判成「无任何调用」⇒ ⇒ **假阳性**。
            _add(node.id)
            # ⚠️ **别名解包** —— `actor: ActorDep` ⇒ ⇒ 别名里藏着守卫。
            for hit in aliases.get(node.id, ()):  # type: ignore[arg-type]
                _add(hit)
    return found


def classify(guards: list[str]) -> str:
    """守卫**四态**（见文件头）。"""
    if AUTHZ_GUARDS & set(guards):
        return "authz"
    if ROLE_GUARDS & set(guards) or WHOAMI_GUARDS & set(guards):
        return "role_only"
    if TYPE_GUARDS & set(guards):
        return "type_only"
    return "none"


def _rel(path: Path) -> str:
    """相对后端目录的路径（**不在后端目录内**就原样返回 ⇒ 别让相对化炸掉）。"""
    try:
        return str(path.relative_to(BACKEND))
    except ValueError:
        return str(path)


def _module_local_funcs(tree: ast.Module) -> set[str]:
    """模块里定义的**本地函数/异步函数**名（不含端点自己）。"""
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _local_calls(func: ast.FunctionDef, locals_: set[str]) -> list[str]:
    """端点体里调用的**本地函数**（⇒ ⇒ 守卫可能藏在里面）。

    ⚠️ 为什么要有这一列：`report.py` 的
    `GET /report/{id}/download` 调的是**本地封装** `_guard_project(...)`
    ⇒ ⇒ 只看「已知守卫名」会把它判成「无任何调用」⇒ ⇒ **假阳性**
    ⇒ ⇒ 这一列告诉审计者「**去读这个本地函数**」。
    """
    found: list[str] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            tail = _call_tail(node)
            if tail in locals_ and tail not in found and tail != func.name:
                found.append(tail)
    return found


def enumerate_endpoints(api_dir: Path = API_DIR) -> list[dict[str, Any]]:
    """枚举全部端点（每个端点一条记录）。"""
    out: list[dict[str, Any]] = []
    for path in sorted(api_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prefix = _router_prefix(tree)
        locals_ = _module_local_funcs(tree)
        aliases = _alias_guards(tree)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            route = _decorator_route(node)
            if route is None:
                continue
            method, raw_path = route
            full_path = f"{prefix}{raw_path}"
            guards = _guard_calls(node, aliases)
            params = _signature_params(node)
            path_params = _path_params(full_path)
            out.append(
                {
                    "module": path.stem,
                    "file": _rel(path),
                    "method": method,
                    "path": full_path,
                    "func": node.name,
                    "line": node.lineno,
                    "path_params": path_params,
                    "params": params,
                    "guards": guards,
                    "state": classify(guards),
                    "local_calls": _local_calls(node, locals_),
                }
            )
    return out


def _counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """按模块统计：端点数 + 三态分布。"""
    out: dict[str, dict[str, int]] = {}
    for row in rows:
        mod = out.setdefault(
            row["module"],
            {"total": 0, "authz": 0, "role_only": 0, "type_only": 0, "none": 0},
        )
        mod["total"] += 1
        mod[row["state"]] += 1
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="守卫覆盖审计的端点枚举")
    parser.add_argument("--module", help="只看这一个模块")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--counts", action="store_true", help="只输出每模块的端点数与三态分布")
    args = parser.parse_args(argv)

    rows = enumerate_endpoints()
    if args.module:
        rows = [r for r in rows if r["module"] == args.module]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if args.counts:
        counts = _counts(rows)
        for mod in sorted(counts):
            c = counts[mod]
            print(
                f"{mod:28s} total={c['total']:3d}  authz={c['authz']:3d}  "
                f"role_only={c['role_only']:3d}  type_only={c['type_only']:3d}  "
                f"none={c['none']:3d}"
            )
        print(f"\n合计 {len(rows)} 个端点")
        return 0

    for row in rows:
        ids = ",".join(row["path_params"]) or "-"
        local = ",".join(row["local_calls"]) or "-"
        print(
            f"{row['module']:22s} {row['method']:6s} {row['path']:52s} "
            f"id={ids:16s} [{row['state']:9s}] guards={','.join(row['guards']) or '-':40s} "
            f"local={local}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
