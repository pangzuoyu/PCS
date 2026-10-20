"""通知链路的**架构不变量**（ADR-0049 §①）。

⚠️ 本文件里的测试断言的是「某样东西**不**存在」—— 它们在实现之前就绿
（被守护的对象压根不存在，AST 扫描必然空）。**它们的价值在未来，不在现在**：
防止下一版接邮件时把 ADR-0049 §① 的决定悄悄推翻。

⇒ 与「行为测试」分开归档，是为了看测试报告的人能一眼分清哪些是
green-on-day-zero 的绊线、哪些是真的在验证行为。

## 为什么用 AST 不用全仓 grep（2026-10-19 委员会建议 4）

字符串 grep 测的是「文本里没有这个词」，而**文档与注释里提到它是正常的**
（ADR-0049 就写了「不写 `EmailChannel`」）。grep 会误报，长期会被人加
`# noqa` 绕过 —— 那就等于把守卫关掉了。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from app.services.notifications.channel import NotificationChannel

_APP = pathlib.Path(__file__).resolve().parents[2] / "app"


def test_protocol_has_exactly_one_method():
    """预定义 `can_deliver` / `on_failure` / 批量接口 = 预先猜测下一版的需求
    = 重蹈空壳覆辙（ADR §① 约束 2）。"""
    public = {
        n
        for n in vars(NotificationChannel)
        if not n.startswith("_") and n not in {"__doc__"}
    }
    # runtime_checkable 协议会带 __protocol_attrs__ 之类的内部属性
    public = {n for n in public if not n.startswith("__")}
    assert public == {"deliver"}, f"协议上多出方法：{public - {'deliver'}}"


def test_no_email_channel_class_in_repo():
    """不存在 `EmailChannel` 类定义或导入（ADR-0049 §①：不写空壳）。

    ⚠️ **用 AST 不用全仓 grep**（2026-10-19 委员会建议 4）：字符串 grep 测的是
    「文本里没有这个词」，而**文档与注释里提到它是正常的**（本 ADR 就写了
    「不写 `EmailChannel`」）。grep 会误报，长期会被人加 `# noqa` 绕过 ——
    那就等于把守卫关掉了。
    """
    for py in _APP.rglob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "EmailChannel":
                pytest.fail(f"EmailChannel 空壳出现在 {py}:{node.lineno}")
            if isinstance(node, (ast.ImportFrom, ast.Import)):
                for alias in node.names:
                    if getattr(alias, "name", "") == "EmailChannel":
                        pytest.fail(f"EmailChannel 被导入于 {py}:{node.lineno}")


def test_no_channel_type_branch_in_service():
    """service 层不得出现 `if channel_type == ...` 之类的按通道分支
    —— 那是 ADR §① 明令禁止的「临时 if」。"""
    for py in (_APP / "services" / "notifications").rglob("*.py"):
        src = py.read_text()
        assert "channel_type ==" not in src, f"{py} 出现按通道类型的分支"
        assert "走邮件" not in src, f"{py} 出现按通道类型的分支"
