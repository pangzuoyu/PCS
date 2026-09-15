"""P4-TASK0 CI 三方比对基础（骨架）。

PRO/II / HYSYS / 手工算例的 baseline JSON + hash 校验机制。
本批仅建数据契约 + 校验机制，不实际跑三方软件（需商业 license）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

BASELINE_DIR = Path(__file__).resolve().parent
BASELINE_JSON = BASELINE_DIR / "baseline_cases.json"


def _load_baseline() -> dict:
    return json.loads(BASELINE_JSON.read_text(encoding="utf-8"))


def _hash_payload(payload: dict) -> str:
    """与 calc_lineage 一致：sha256 截断 16 hex。"""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def test_baseline_json_exists() -> None:
    """骨架数据契约文件存在。"""
    assert BASELINE_JSON.is_file(), f"missing {BASELINE_JSON}"


def test_baseline_has_three_vendors() -> None:
    """baseline 含 PRO/II / HYSYS / MANUAL 三个对照源。"""
    data = _load_baseline()
    vendors = {c.get("vendor") for c in data["cases"]}
    assert {"PROII", "HYSYS", "MANUAL"} <= vendors


def test_baseline_each_case_has_hash_and_fingerprint() -> None:
    """每个 case 必须有 case_id + fingerprint + expected_hash 字段。"""
    data = _load_baseline()
    for c in data["cases"]:
        assert "case_id" in c and "vendor" in c
        assert "fingerprint" in c and "expected_hash" in c
        assert len(c["expected_hash"]) == 16


def test_verify_baseline_returns_ok() -> None:
    """verify_baseline：对当前 JSON 重算 hash 应一致。"""
    data = _load_baseline()
    for c in data["cases"]:
        h = _hash_payload(c["fingerprint"])
        assert h == c["expected_hash"], (
            f"{c['case_id']} fingerprint hash drift: "
            f"expected {c['expected_hash']} got {h}"
        )


def test_missing_baseline_raises(tmp_path: Path) -> None:
    """baseline 文件缺失时 verify_baseline 应 raise FileNotFoundError。"""
    from app.services.ci_baseline import verify_baseline

    with pytest.raises(FileNotFoundError):
        verify_baseline(tmp_path / "nope.json")


def test_load_baseline_helper() -> None:
    """helper：load_baseline 返回契约 dict。"""
    from app.services.ci_baseline import load_baseline

    data = load_baseline(BASELINE_JSON)
    assert data["schema_version"] == "1.0"
    assert isinstance(data["cases"], list)
