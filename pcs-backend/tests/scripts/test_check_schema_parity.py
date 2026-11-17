"""`scripts/check_schema_parity.py` 的测试 —— 它唯一的产出是「一个退出码」。

## ⚠️ 为什么这里**不碰开发库**

这条闸门断的是**两个开发库**（`pcs` / `pcs_test`）⇒ ⇒ 它**不能**在
**默认车道**（单测）里真跑 ⇒ ⇒ 否则「单测车道绝不碰真库」这条纪律就破了
（CLAUDE.md「测试前检查」）。

⇒ ⇒ 本文件只测**逻辑**（探针被**注入**）⇒ ⇒ 真跑由**发布前检查**负责
（`uv run python scripts/check_schema_parity.py`）。

## ⚠️ 断的是「**与代码 head 对齐**」，不是「两库彼此相同」（评审 #21）

两库**都落后**时它们「彼此相同」⇒ ⇒ 只比彼此 ⇒ **两库都落后也绿** ⇒
⇒ 本闸门断的是**每个库 == 代码 head**。
"""
from __future__ import annotations

from scripts.check_schema_parity import Probe, main

#: 假的 URL（**不解析、不连接** ⇒ 默认车道不碰任何库）。
FAKE_URLS = [
    ("pcs", "postgresql+psycopg://u:p@localhost:5432/pcs"),
    ("pcs_test", "postgresql+psycopg://u:p@localhost:5432/pcs_test"),
]


def _probe_factory(revisions: dict[str, Probe]):
    def _probe(url: str) -> Probe:
        for name, fake_url in FAKE_URLS:
            if fake_url == url:
                return revisions[name]
        raise AssertionError(f"意料之外的 URL：{url}")

    return _probe


def test_all_databases_at_the_code_head_exits_zero(monkeypatch):
    """每个库都 == 代码 head 且 `alembic check` 干净 ⇒ exit 0。"""
    monkeypatch.setattr(
        "scripts.check_schema_parity.code_head", lambda: "p10_002"
    )
    probe = _probe_factory(
        {
            "pcs": Probe(revision="p10_002", drift_rc=0),
            "pcs_test": Probe(revision="p10_002", drift_rc=0),
        }
    )
    assert main(urls=FAKE_URLS, probe=probe) == 0


def test_a_database_behind_the_code_head_fails(monkeypatch):
    """⚠️ **落后代码 head** ⇒ 红（这正是 #21：两库都落后时「彼此一致」不算过）。"""
    monkeypatch.setattr(
        "scripts.check_schema_parity.code_head", lambda: "p10_002"
    )
    probe = _probe_factory(
        {
            "pcs": Probe(revision="p10_002", drift_rc=0),
            # ⚠️ 两库**都**落后 ⇒ 彼此一致 ⇒ 但都 ≠ 代码 head ⇒ 必须红
            "pcs_test": Probe(revision="p9_006", drift_rc=0),
        }
    )
    assert main(urls=FAKE_URLS, probe=probe) == 1


def test_a_drifted_database_fails(monkeypatch):
    """`alembic check` 非 0 ⇒ 红（ORM ↔ 迁移漂移）。"""
    monkeypatch.setattr(
        "scripts.check_schema_parity.code_head", lambda: "p10_002"
    )
    probe = _probe_factory(
        {
            "pcs": Probe(revision="p10_002", drift_rc=0),
            "pcs_test": Probe(revision="p10_002", drift_rc=255, drift_output="drift!"),
        }
    )
    assert main(urls=FAKE_URLS, probe=probe) == 1


def test_an_unreachable_database_fails_closed(monkeypatch):
    """⚠️ **查不到** ⇒ 当作**不通过**（fail-closed）⇒ 不是「跳过」。"""

    def _boom(url: str) -> Probe:
        raise RuntimeError("连不上")

    monkeypatch.setattr(
        "scripts.check_schema_parity.code_head", lambda: "p10_002"
    )
    assert main(urls=FAKE_URLS, probe=_boom) == 1
