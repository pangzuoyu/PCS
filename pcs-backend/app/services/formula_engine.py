"""FormulaEngine — 公式解析与版本指纹。

Task 2.3 设计要点：
- 解析路径：Python ast.parse(mode="eval") + AST 白名单 -> compile -> 闭包持 code object，
  运行时 eval 在受限命名空间（{"__builtins__": {}}）下求值。
- 安全边界：白名单 + FORBIDDEN_NODES/NAMES；ast.Attribute.attr 也必须经禁止子串检查
  （否则 "".__class__ 等可绕过 ast.Name 检查）。
- 版本指纹（D33）：SHA-256(payload) hex[:16]，payload 为 expression.strip() + \\x1f +
  JSON(sort_keys=True, ensure_ascii=False)。
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import math
from collections.abc import Callable
from typing import Any

from app.services.exceptions import PreconditionViolation, PcsError


class FormulaSecurityError(PcsError):
    """公式包含禁止的 AST 节点或名称时抛出。code=FORMULA_SECURITY, status=422."""

    code = "FORMULA_SECURITY"
    status = 422


class FormulaEngine:
    ALLOWED_FUNCS = {"sqrt", "log", "exp", "sin", "cos", "tan", "pow", "abs", "min", "max"}
    ALLOWED_NAMES = {"math"} | ALLOWED_FUNCS
    FORBIDDEN_NODES = (
        ast.Import,
        ast.ImportFrom,
        ast.Global,
        ast.Nonlocal,
        ast.Lambda,
        ast.FunctionDef,
        ast.ClassDef,
        ast.Try,
        ast.With,
        ast.AsyncFor,
        ast.AsyncWith,
    )
    FORBIDDEN_NAMES = {"__", "open", "eval", "exec", "compile", "globals", "locals", "vars"}

    @classmethod
    def _build_namespace(cls) -> dict[str, Any]:
        """构建公式可用命名空间。

        math.* 函数按白名单注入。`min`/`max` 在 `math` 模块下不存在
        （属 builtins），需显式补齐，否则 ALLOWED_FUNCS 形同虚设。
        """
        ns: dict[str, Any] = {
            name: getattr(math, name) for name in cls.ALLOWED_FUNCS if hasattr(math, name)
        }
        ns.setdefault("min", builtins.min)
        ns.setdefault("max", builtins.max)
        ns["math"] = math
        return ns

    @classmethod
    def parse(cls, expression: str, parameters: dict[str, float]) -> Callable[[dict], float]:
        tree = ast.parse(expression, mode="eval")
        cls._validate_ast(tree)
        namespace = cls._build_namespace()
        namespace.update(parameters)
        code = compile(tree, "<formula>", "eval")

        def evaluator(p: dict[str, float]) -> float:
            merged = {**namespace, **p}
            return float(eval(code, {"__builtins__": {}}, merged))  # noqa: S307 — 已通过 AST 白名单

        return evaluator

    @classmethod
    def _validate_ast(cls, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if isinstance(node, cls.FORBIDDEN_NODES):
                raise FormulaSecurityError(f"禁止节点: {type(node).__name__}")
            if isinstance(node, ast.Name) and any(f in node.id for f in cls.FORBIDDEN_NAMES):
                raise FormulaSecurityError(f"禁止名称: {node.id}")
            # 防御性：ast.Attribute 的 attr 字段也必须经禁止子串检查，
            # 否则 `().__class__.__bases__[0].__subclasses__()` 这类攻击
            # 可绕过 Name 检查（因 `__class__` 不是 Name 而是 Attribute.attr）。
            if isinstance(node, ast.Attribute) and any(
                f in node.attr for f in cls.FORBIDDEN_NAMES
            ):
                raise FormulaSecurityError(f"禁止属性: {node.attr}")

    @staticmethod
    def compute_version_hash(expression: str, parameters: dict | None = None) -> str:
        """公式版本指纹（SHA-256 截前 16 位，D33 决议）。

        Payload 格式：`f"{expression.strip()}\\x1f{params_repr}"`，
        其中 params_repr 是 `json.dumps(parameters, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"))`。

        调用方：ConfigVersion 创建时自动调用填充 formula_version 列。
        """
        params_repr = json.dumps(
            parameters or {},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        payload = f"{expression.strip()}\x1f{params_repr}".encode()
        return hashlib.sha256(payload).hexdigest()[:16]

    @classmethod
    def run_unit_tests(
        cls, expression: str, parameters: dict, unit_tests: list[dict]
    ) -> tuple[int, int]:
        """返回 (passed, total)。PUBLISH 端点断言 passed == total。"""
        fn = cls.parse(expression, parameters)
        passed = 0
        for tc in unit_tests:
            try:
                result = fn(tc["params"])
                if abs(result - tc["expected"]) <= tc.get("tolerance", 0.01):
                    passed += 1
            except Exception:
                pass
        return passed, len(unit_tests)

    @classmethod
    def evaluate_preconditions(
        cls,
        preconditions: list[dict],
        context: dict,
        *,
        phase: str = "pre",
        trace_table: dict[str, str | None] | None = None,
    ) -> list[str]:
        """评估 preconditions 数组，返回违规 ID 列表。

        phase="pre"：input.*/params.* 可用；result.* 不应存在
        phase="post"：result.* 可用；input.*/params.* 只读

        变量白名单：input.* / params.* / result.* ；
        context.* 引用一律 REJECT（V1.6 §2.3 表达力边界）。

        trace_table：params.* → CoefficientTable 溯源映射；
                     缺键或 None 值 → REJECT。
        """
        violations: list[str] = []
        for pc in preconditions:
            target = pc.get("target", "")
            if not target.startswith(("input.", "params.", "result.")):
                raise PreconditionViolation(
                    f"precondition target 必须是 input.*/params.*/result.*；得到 {target!r}",
                    details={"id": pc.get("id"), "target": target},
                )

            parts = target.split(".", 1)
            namespace, path = parts[0], parts[1]

            if namespace == "context":
                raise PreconditionViolation(
                    f"禁止引用 context.*（V1.6 §2.3 边界）；precondition id={pc.get('id')!r}",
                    details={"id": pc.get("id"), "target": target},
                )

            if phase == "pre" and namespace == "result":
                raise PreconditionViolation(
                    f"pre 阶段禁止引用 result.*；precondition id={pc.get('id')!r}",
                    details={"id": pc.get("id"), "target": target},
                )

            # 解析嵌套值
            value = context.get(namespace, {})
            for segment in path.split("."):
                if not isinstance(value, dict) or segment not in value:
                    raise PreconditionViolation(
                        f"target 路径解析失败：{target!r}",
                        details={"id": pc.get("id"), "target": target, "missing": segment},
                    )
                value = value[segment]

            # 溯源校验
            if namespace == "params" and trace_table is not None:
                if trace_table.get(path) is None:
                    raise PreconditionViolation(
                        f"params.{path} 未溯源到 CoefficientTables",
                        details={"id": pc.get("id"), "target": target, "param": path},
                    )

            # 评估 expression（复用 AST 白名单）
            try:
                tree = ast.parse(pc["expression"], mode="eval")
                cls._validate_ast(tree)
                code = compile(tree, "<precondition>", "eval")
                namespace_ns = cls._build_namespace()
                namespace_ns["value"] = value
                # 绑定叶节点名称供 expression 引用（如 "T > 0" 中 T）
                leaf_name = path.rsplit(".", 1)[-1]
                namespace_ns[leaf_name] = value
                result = eval(code, {"__builtins__": {}}, namespace_ns)  # noqa: S307
                if not result:
                    violations.append(pc.get("id", target))
            except FormulaSecurityError as e:
                raise PreconditionViolation(
                    f"precondition expression 含禁止 AST 节点：{e}",
                    details={"id": pc.get("id"), "target": target},
                ) from e

        if violations:
            raise PreconditionViolation(
                f"preconditions 违规：{violations}",
                details={"violations": violations},
            )
        return violations
