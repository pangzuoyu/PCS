"""P4-TASK0 CI 三方比对基础 helper。

三方对照用例集（PRO/II / HYSYS / 手工算例）— 数据契约 + hash 校验。
不实际跑三方软件（需商业 license），仅建数据契约 + 校验机制。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_HASH_PREFIX = 16


def _hash_payload(payload: dict[str, Any]) -> str:
    """fingerprint sha256 截断 16 hex（与 calc_lineage 一致）。"""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:_HASH_PREFIX]


def load_baseline(path: Path) -> dict[str, Any]:
    """读三方对照用例 JSON 契约。"""
    return json.loads(path.read_text(encoding="utf-8"))


def verify_baseline(path: Path) -> dict[str, Any]:
    """校验 baseline JSON：每个 case 的 fingerprint 重算 hash == expected_hash。

    Raises:
        FileNotFoundError: baseline 文件缺失
        ValueError: 任一 case hash 漂移
    """
    if not path.is_file():
        raise FileNotFoundError(f"baseline not found: {path}")
    data = load_baseline(path)
    drift: list[str] = []
    for c in data.get("cases", []):
        h = _hash_payload(c["fingerprint"])
        if h != c["expected_hash"]:
            drift.append(f"{c['case_id']}: expected {c['expected_hash']} got {h}")
    if drift:
        raise ValueError("baseline hash drift:\n" + "\n".join(drift))
    return data


__all__ = ["load_baseline", "verify_baseline"]
