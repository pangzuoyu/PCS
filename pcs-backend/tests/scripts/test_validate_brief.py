"""OPEN-P6-6A-2: validate_brief.py 单元测试（CLI subprocess + 临时 brief 文件）。

测试三组核心场景：

1. **PASS path** — brief 含全部 expected-ids，无 foreign-ids
2. **MISSING path** — brief 缺 expected-id（复制粘贴遗漏 / 跨任务错配）
3. **FOREIGN path** — brief 包含 foreign-id（其他任务的 ID 误植）

每组用 ``tmp_path`` 写临时 plan + brief 副本，再子进程调
``scripts/validate_brief.py`` 验 exit code + stderr。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_VALIDATE_BRIEF = _BACKEND_ROOT / "scripts" / "validate_brief.py"


def _run_validator(
    plan: Path,
    brief: Path,
    task_n: int,
    expected_ids: list[str],
    foreign_ids: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable, str(_VALIDATE_BRIEF),
        "--plan", str(plan),
        "--task-n", str(task_n),
        "--brief", str(brief),
        "--expected-ids", *expected_ids,
    ]
    if foreign_ids:
        cmd.extend(["--foreign-ids", *foreign_ids])
    return subprocess.run(
        cmd, capture_output=True, text=True, check=False, timeout=10,
    )


def _write_files(tmp_path: Path, plan_body: str, brief_body: str):
    plan = tmp_path / "plan.md"
    brief = tmp_path / "brief.md"
    plan.write_text(plan_body, encoding="utf-8")
    brief.write_text(brief_body, encoding="utf-8")
    return plan, brief


_PLAN = """| # | ID | TYPE | TARGET | TOLERANCE |
|---|---|---|---|---|
| 9 | C-17 PR-019 | IMPLEMENTER | WS-CA-PR-019 | 经验 1% |
| 10 | C-18 PR-020 | IMPLEMENTER | WS-CA-PR-020 | 强公式 0.1% |
"""


def test_pass_when_brief_matches_expected_ids(tmp_path: Path):
    brief = (
        "# Task 9: C-17 saturation water content vs WS-CA-PR-019\n\n"
        "5 cases, working fluid defect (humid air vs natural gas).\n"
    )
    plan, brief_p = _write_files(tmp_path, _PLAN, brief)
    result = _run_validator(plan, brief_p, 9, ["C-17", "WS-CA-PR-019"])
    assert result.returncode == 0, (
        f"expected OK, got rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "OK:" in result.stdout


def test_fail_when_brief_missing_expected_id(tmp_path: Path):
    """复制粘贴遗漏：C-17 task 的 brief 缺 WS-CA-PR-019。"""
    brief = (
        "# Task 9: C-17 saturation water content\n\n"
        "5 cases (no XLS reference in body).\n"
    )
    plan, brief_p = _write_files(tmp_path, _PLAN, brief)
    result = _run_validator(plan, brief_p, 9, ["C-17", "WS-CA-PR-019"])
    assert result.returncode == 1, (
        f"expected FAIL, got rc={result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    assert "missing expected IDs" in result.stderr
    assert "WS-CA-PR-019" in result.stderr


def test_fail_when_brief_has_foreign_id(tmp_path: Path):
    """OPEN-P6-6A-2 原始症状：C-17 task 的 brief 误含 C-18 + WS-CA-PR-020。"""
    brief = (
        "# Task 9: C-17 saturation water content\n\n"
        "Cross-references WS-CA-PR-019 for sanity check.\n"
        "(see also C-18 hydrate vs WS-CA-PR-020)\n"
    )
    plan, brief_p = _write_files(tmp_path, _PLAN, brief)
    result = _run_validator(
        plan, brief_p, 9,
        expected_ids=["C-17", "WS-CA-PR-019"],
        foreign_ids=["C-18", "WS-CA-PR-020"],
    )
    assert result.returncode == 1, (
        f"expected FAIL on foreign IDs, got rc={result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    assert "foreign IDs" in result.stderr
    assert "C-18" in result.stderr
    assert "WS-CA-PR-020" in result.stderr


def test_fail_when_plan_file_missing(tmp_path: Path):
    plan = tmp_path / "no_such_plan.md"
    brief = tmp_path / "brief.md"
    brief.write_text("anything", encoding="utf-8")
    result = _run_validator(plan, brief, 9, ["C-17"])
    assert result.returncode == 2
    assert "plan file not found" in result.stderr


def test_fail_when_brief_file_missing(tmp_path: Path):
    plan = tmp_path / "plan.md"
    plan.write_text(_PLAN, encoding="utf-8")
    brief = tmp_path / "no_such_brief.md"
    result = _run_validator(plan, brief, 9, ["C-17"])
    assert result.returncode == 2
    assert "brief file not found" in result.stderr


@pytest.mark.parametrize(
    "expected_ids, foreign_ids",
    [
        (["C-17", "WS-CA-PR-019"], []),
        (["WS-CA-PR-019", "C-17"], ["C-18"]),  # 顺序无关
    ],
)
def test_id_order_invariant(
    tmp_path: Path, expected_ids, foreign_ids,
):
    brief = "# Task 9: C-17 saturation water content (WS-CA-PR-019)"
    plan, brief_p = _write_files(tmp_path, _PLAN, brief)
    result = _run_validator(
        plan, brief_p, 9, expected_ids, foreign_ids or None,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))