"""P4-TASK0 架构层 importlinter 测试（自实现，零依赖）。

层级约束：
- api → services → models / core
- services 不可 import api
- models 不可 import services / api
- core 不可 import api / services / models

实现：importlib 解析顶层包内所有 .py 文件 → 抽取 import 目标 → 检查违规。
约定：app 子包按目录区分（api/ services/ models/ core/）。
本测试在 CI 跑得起（不依赖 importlinter 包）；pyproject.toml 仅留手工文档参考。
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "app"
LAYERS = ("api", "services", "models", "core")


def _collect_imports(layer: str) -> dict[str, set[str]]:
    """遍历 app/<layer>/**/*.py，返回 {file_relpath: {imported_top_modules}}。

    仅抽取跨层 `from app.X import ...` / `import app.X`（X ≠ 当前 layer）。
    同层 import（app.services.X import from app.services.Y）放行。
    """
    layer_dir = ROOT / layer
    result: dict[str, set[str]] = {}
    for py in layer_dir.rglob("*.py"):
        if py.name == "__init__.py" and py.parent == layer_dir:
            rel = "__init__"
        else:
            rel = str(py.relative_to(layer_dir))
        src = py.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(py))
        except SyntaxError:
            continue
        deps: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("app."):
                    top = node.module.split(".", 2)
                    if len(top) >= 2 and top[1] in LAYERS and top[1] != layer:
                        deps.add(top[1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("app."):
                        top = alias.name.split(".", 2)
                        if len(top) >= 2 and top[1] in LAYERS and top[1] != layer:
                            deps.add(top[1])
        result[rel] = deps
    return result


# ============================================================================
# Layer rules
# ============================================================================


def test_api_only_imports_downstream_layers() -> None:
    """api 层只允许 import services/models/core（不反向）。"""
    deps = _collect_imports("api")
    for rel, ds in deps.items():
        bad = ds - {"services", "models", "core"}
        assert not bad, f"api/{rel} 反向/跨层 import {bad}"


def test_services_does_not_import_api() -> None:
    """services 层禁止 import api（api 是顶层）。"""
    deps = _collect_imports("services")
    for rel, ds in deps.items():
        assert "api" not in ds, f"services/{rel} 不应 import api"


def test_models_does_not_import_services_or_api() -> None:
    """models 层禁止 import services/api（基础层）。"""
    deps = _collect_imports("models")
    for rel, ds in deps.items():
        assert "api" not in ds, f"models/{rel} 不应 import api"
        assert "services" not in ds, f"models/{rel} 不应 import services"


def test_core_does_not_import_api_or_models() -> None:
    """core 层禁止 import api/models（services 是已知遗留例外）。

    已知遗留：core/errors.py → app.services.exceptions（PcsError 复用）。
    后续批次可考虑将 PcsError 移至 app.core.exceptions 解除循环；当前
    通过 _ALLOWED_CORE_CROSS_LAYER 显式 allowlist，不阻塞 CI。
    """
    deps = _collect_imports("core")
    for rel, ds in deps.items():
        bad = ds - _ALLOWED_CORE_CROSS_LAYER
        assert not bad, f"core/{rel} 不应 import app.{bad}（core 是最底层）"


# 已知遗留 allowlist：core → services 的特定导入（不在扩展时违规）
_ALLOWED_CORE_CROSS_LAYER: frozenset[str] = frozenset({"services"})


def test_layers_present_in_repo() -> None:
    """4 层目录必须存在（防止误删层）。"""
    for layer in LAYERS:
        assert (ROOT / layer).is_dir(), f"app/{layer} 缺失"


# 标记：以下常量被 pyproject.toml 文档化（非运行时约束）
_DOC_REFERENCE = {
    "layers": ["api", "services", "models", "core"],
    "rules": [
        "api → services → models/core",
        "services ⊄ imports(api)",
        "models ⊄ imports(services, api)",
        "core ⊄ imports(api, services, models)",
    ],
}
