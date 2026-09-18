"""P6-0 G-01 fluids.open_channel API dir() 前置核验脚本（P6-OPEN-001 关闭）。

依据：ADR-0030 决策 5（dir() 前置核验）+ P6 SPEC §3.2.6 OPEN_CHANNEL + P6-OPEN-001 待确定问题。

用法：
  cd pcs-backend && uv run python scripts/p6_0_gate_01_open_channel_dir.py [报告路径]
默认报告路径：docs/p6-gate-reports/gate-01-open-channel-api.json（相对仓库根）。

输出：JSON 同时写 stdout 与指定路径文件。
  status="passed" — REQUIRED 5 函数全部 dir() 命中；
  status="degraded" — 存在 missing；按 ADR-0030 决策 7 启用自研兜底。
"""
# ruff: noqa — 一次性 gate 核验脚本（单点收敛），非 app 代码
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = [
    "Manning",
    "Manning_flow",
    "critical_depth",
    "V_Manning",
    "hydraulic_radius",
]

# P6 SPEC §3.2.6 写明 `fluids.open_channel`；fluids==1.3.1 实际不暴露该子模块，
# 最近等价路径为 `fluids.open_flow`。本脚本按 SPEC 顺序核验，未命中再回退到实际模块，
# 在 `open_channel_submodule` 字段如实记录最终命中的子模块路径。
CANDIDATE_SUBMODULES = ("fluids.open_channel", "fluids.open_flow")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_report_path(arg: str) -> Path:
    if arg:
        return Path(arg)
    # 仓库根 = scripts/ 的上级目录的上级目录
    repo_root = Path(__file__).resolve().parent.parent.parent
    return repo_root / "docs" / "p6-gate-reports" / "gate-01-open-channel-api.json"


def main() -> int:
    report_path = _resolve_report_path(sys.argv[1] if len(sys.argv) > 1 else "")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. fluids 库版本 + open_channel 子模块 dir() 核验
    note_parts: list[str] = []
    required_found: list[str] = []
    required_missing: list[str] = list(REQUIRED)
    submodule_hit: str | None = None
    fluids_version: str | None = None

    try:
        fluids = importlib.import_module("fluids")
        fluids_version = getattr(fluids, "__version__", "unknown")
    except Exception as exc:  # fluids 未安装 / import 失败
        note_parts.append(f"fluids import 失败：{exc}")
        report = {
            "gate": "G-01",
            "status": "degraded",
            "checked_at": _now_iso(),
            "required": REQUIRED,
            "required_found": [],
            "required_missing": list(REQUIRED),
            "fluids_version": None,
            "open_channel_submodule": None,
            "note": "；".join(note_parts + ["触发 P6-OPEN-001 自研兜底（ADR-0030 决策 7）"]),
        }
        _emit(report, report_path)
        return 1

    for candidate in CANDIDATE_SUBMODULES:
        try:
            sub = importlib.import_module(candidate)
        except ModuleNotFoundError as exc:
            note_parts.append(f"{candidate} 不可导入：{exc}")
            continue
        names = dir(sub)
        submodule_hit = candidate
        required_found = [n for n in REQUIRED if n in names]
        required_missing = [n for n in REQUIRED if n not in names]
        note_parts.append(f"命中 {candidate}（共 {len(names)} 个导出符号）")
        break
    else:
        note_parts.append(
            f"所有候选子模块均不可导入：{CANDIDATE_SUBMODULES}；触发 P6-OPEN-001 自研兜底"
        )

    status = "passed" if not required_missing else "degraded"
    if status == "degraded":
        note_parts.append(
            "触发 P6-OPEN-001：缺失函数按 ADR-0030 决策 7 自研兜底 "
            "（几何 + Manning 公式 + 临界水深 Froude 数判定 + 水跃共轭水深）"
        )

    report = {
        "gate": "G-01",
        "status": status,
        "checked_at": _now_iso(),
        "required": REQUIRED,
        "required_found": required_found,
        "required_missing": required_missing,
        "fluids_version": fluids_version,
        "open_channel_submodule": submodule_hit,
        "note": "；".join(note_parts),
    }
    _emit(report, report_path)
    return 0 if status == "passed" else 1


def _emit(report: dict, report_path: Path) -> None:
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    report_path.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())