"""P3.2 SIM-10：PRO/II + Excel 导入预览与落库服务（spec V1.6 §3.2 + §5.5）。

按 plan V1.0 落地（用户 2026-09-08 裁决）：
- preview 走 parser + ConflictResolver（不落库）
- commit 走 StreamService.create（复用 SIM-4 集成 SIM-3+SIM-7 链路）
- convergence_status: CONVERGED/WARNINGS 全量；NOT_CONVERGED/ABORTED → 标记
  unreliable=True 并 commit 仍尝试
- 临时文件：multipart 上传写入 NamedTemporaryFile，preview/commit 后清理

收敛分层（用户 2026-09-08 锁定）：
- CONVERGED / WARNINGS / NOT_SOLVED：全量入库，warnings 列在 import_warnings
- NOT_CONVERGED / ABORTED：unreliable=True 标记入库（用户需查看）
"""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.conflict_resolver import ConflictLevel, ConflictResolver
from app.services.excel_parser import parse_excel_file
from app.services.exceptions import PcsError
from app.services.proii_parser import (
    ConvergenceStatus,
    parse_proii_files,
)
from app.services.property_completion import ParsedStream
from app.services.stream_service import StreamService

# CONVERGED / WARNINGS / NOT_SOLVED 全量入库
_RELIABLE_STATUSES = frozenset(
    {
        ConvergenceStatus.CONVERGED,
        ConvergenceStatus.WARNINGS,
        ConvergenceStatus.NOT_SOLVED,
    }
)


def _phase_norm(p: str | None) -> str | None:
    """PRO/II 相态字母 → schema 完整词。

    V → VAPOR / L → LIQUID / M → None（避免 SIM-V01 BLOCK：
    PRO/II parser 当前不提取 vapor/liquid 组成，MIXED 会触发 BLOCK；
    留 None 让用户手工补；is_mixed_phase 字段保留 MIXED 事实） / S → SOLID
    """
    if not p:
        return None
    p = p.strip().upper()
    if p in ("V", "VAPOR"):
        return "VAPOR"
    if p in ("L", "LIQUID"):
        return "LIQUID"
    if p in ("M", "MIXED"):
        # 留 None 而非 MIXED，避免 SIM-V01 BLOCK（MIXED 必填两相组成）
        return None
    if p in ("S", "SOLID"):
        return "SOLID"
    return p


def _is_mixed_phase_raw(p: str | None) -> bool:
    """PRO/II 原始相态是否为 MIXED（汽液混相）。

    仅在调用前对 parser 输出的 phase（M/MIXED/VAPOR/LIQUID/SOLID）生效。
    后续 _phase_norm 会把 MIXED 映射成 None，但 is_mixed_phase 持久化标记
    不变——P4 composition 抽取时按此字段精准筛选。
    """
    if not p:
        return False
    return p.strip().upper() in ("M", "MIXED")


def _k_to_c(t: float | None) -> float | None:
    return None if t is None else t - 273.15


def _pa_to_kpa(p: float | None) -> float | None:
    return None if p is None else p / 1000.0


def _proii_lite_to_parsed(s: Any) -> ParsedStream:
    """_ParsedStreamLite → ParsedStream（物性补全 + 冲突检测需要 .cas 等）。

    PRO/II parser 当前不提取 composition（SIM-10 MVP 仅 T/P/flow/phase 落库）；
    .cas 留 None（SIM-3 转译为 MISSING_CAS → INFO 冲突）。
    MIXED 相检测由 caller 在调用前完成，结果通过 mixed_set 传至 preview。
    """
    return ParsedStream(
        tag=s.tag,
        cas=None,
        temperature_k=s.temperature_k,
        pressure_pa=s.pressure_pa,
        phase=_phase_norm(s.phase),
        mass_flow_kg_h=s.mass_flow_kg_h,
        zero_flow=s.zero_flow,
    )


def _proii_preview_entry(
    s: ParsedStream,
    *,
    banner_version: str,
    unreliable_set: set[str],
    mixed_set: set[str],
    warnings: list[str],
) -> dict[str, Any]:
    """ParsedStream → preview_streams 条目（dict 形态，便于 commit round-trip）。"""
    return {
        "stream_name": s.tag,
        "case_type": "NORMAL",  # PRO/II 默认设计工况
        "data_mode": "CHEMICAL",
        "source_type": "SIM_IMPORT",
        "phase": s.phase,
        "temp": _k_to_c(s.temperature_k),
        "press": _pa_to_kpa(s.pressure_pa),
        "mass_flow": s.mass_flow_kg_h,
        "composition_json": None,
        "import_source_version": f"V{banner_version}",
        "import_original_row": None,
        "is_unreliable": s.tag in unreliable_set,
        "is_mixed_phase": s.tag in mixed_set,
    }


def _excel_preview_entry(s: ParsedStream) -> dict[str, Any]:
    """ParsedStream（Excel）→ preview_streams 条目。

    Excel 走 sheet 顺序，无 source_version；composition 已按名称规整（SIM-10
    commit 阶段才转 CAS）。is_unreliable 显式 False（Excel 无收敛概念）。
    is_mixed_phase 显式 False（Excel sheet phase 列显式 L/V/S，无 MIXED）。
    """
    return {
        "stream_name": s.tag,
        "case_type": "NORMAL",
        "data_mode": "CHEMICAL",
        "source_type": "SIM_IMPORT",
        "phase": _phase_norm(s.phase),  # L/V → LIQUID/VAPOR
        "temp": _k_to_c(s.temperature_k),
        "press": _pa_to_kpa(s.pressure_pa),
        "mass_flow": s.mass_flow_kg_h,
        "composition_json": s.composition,
        "import_source_version": None,
        "import_original_row": None,
        "is_unreliable": False,
        "is_mixed_phase": False,
    }


def _serialize_report(report: Any) -> dict[str, Any]:
    """ConflictReport → dict（JSON 可序列化）。"""

    def _conflict_to_dict(c: Any) -> dict[str, Any]:
        return {
            "level": c.level.value if isinstance(c.level, ConflictLevel) else str(c.level),
            "code": c.code,
            "message": c.message,
            "stream_name": c.stream_name,
            "unit_id": c.unit_id,
            "field": c.field,
        }

    return {
        "blocks": [_conflict_to_dict(c) for c in report.blocks],
        "warnings": [_conflict_to_dict(c) for c in report.warnings],
        "infos": [_conflict_to_dict(c) for c in report.infos],
        "stats": report.stats,
    }


class ImportService:
    """PRO/II + Excel 导入预览与落库（无状态：classmethod 直调）。"""

    # =========================================================================
    # PRO/II
    # =========================================================================

    @classmethod
    def preview_proii(
        cls, inp_path: Path | str, out_path: Path | str
    ) -> dict[str, Any]:
        """PRO/II .inp+.out 解析 → 冲突检测 → 预览 dict。

        返回 dict 而非 StreamImportPreview 是为了 commit 阶段 round-trip 友好
        （含 `unreliable` 标记等扩展字段，不进 Pydantic schema）。
        """
        result = parse_proii_files(inp_path, out_path)
        unreliable_set = set(result.unreliable_streams)
        # SIM-10.2：捕获 MIXED 原始相态（在 _phase_norm 置 None 之前）
        mixed_set = {
            tag
            for tag, lite in result.streams.items()
            if _is_mixed_phase_raw(lite.phase)
        }
        # zero_flow 流也标记（保留流名，不阻塞保存）
        warnings: list[str] = list(result.warnings)
        # 物性补全 + 冲突检测（复用 SIM-4 链路）
        parsed = [_proii_lite_to_parsed(s) for s in result.streams.values()]
        report = ConflictResolver().resolve_batch(parsed, block_on_error=False)
        preview_streams = [
            _proii_preview_entry(
                p,
                banner_version=result.banner_version,
                unreliable_set=unreliable_set,
                mixed_set=mixed_set,
                warnings=warnings,
            )
            for p in parsed
        ]
        # 收敛分层：NOT_CONVERGED/ABORTED → 顶层 warn
        convergence_warn = ""
        if result.convergence_status in (
            ConvergenceStatus.NOT_CONVERGED,
            ConvergenceStatus.ABORTED,
        ):
            convergence_warn = (
                f"PRO/II 收敛状态 {result.convergence_status.value}，"
                f"unreliable 流将入库但需人工复核"
            )
            warnings.append(convergence_warn)
        return {
            "convergence_status": result.convergence_status.value,
            "unreliable_stream_names": sorted(unreliable_set),
            "warnings": warnings,
            "preview_streams": preview_streams,
            "conflict_report": _serialize_report(report),
        }

    @classmethod
    async def commit_proii(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        workspace_id: uuid.UUID,
        preview_streams: list[dict[str, Any]],
        actor: uuid.UUID,
    ) -> dict[str, Any]:
        """PRO/II 预览条目落库。

        - BLOCK 冲突（已在 preview 中识别）→ 跳过该流（preview 阶段已拦）
        - duplicate_name → 跳过（不影响其他流）
        - 成功 → StreamService.create 写入
        - unreliable 流：依旧落库，但 StreamResponse.phase 标 *UNRELIABLE* 不在
          schema 内，preview 已告知用户。本期实现：unreliable 流正常入库，
          response.unreliable_count 仅计数。
        """
        committed: list[uuid.UUID] = []
        skipped = 0
        unreliable_count = 0
        warnings: list[str] = []
        for entry in preview_streams:
            if entry.get("is_unreliable"):
                unreliable_count += 1
            stream_name = entry["stream_name"]
            try:
                stream, _report = await StreamService.create(
                    db,
                    _entry_to_stream_create(
                        entry,
                        project_id=project_id,
                        workspace_id=workspace_id,
                    ),
                    actor=actor,
                )
                committed.append(stream.stream_id)
            except PcsError as e:
                if e.code in {"SIM_STREAM_BLOCKED", "SIM_STREAM_DUPLICATE_NAME"}:
                    skipped += 1
                    warnings.append(f"{stream_name}: {str(e)}")
                else:
                    raise
        return {
            "committed_count": len(committed),
            "unreliable_count": unreliable_count,
            "skipped_count": skipped,
            "stream_ids": committed,
            "warnings": warnings,
        }

    # =========================================================================
    # Excel
    # =========================================================================

    @classmethod
    def preview_excel(cls, path: Path | str) -> dict[str, Any]:
        """Excel 双 Sheet 解析 → 冲突检测 → 预览 dict。"""
        result = parse_excel_file(path)
        # 物性补全 + 冲突检测
        report = ConflictResolver().resolve_batch(
            result.streams, block_on_error=False
        )
        preview_streams = [_excel_preview_entry(s) for s in result.streams]
        warnings: list[str] = list(result.warnings)
        if result.errors:
            warnings.extend([f"parser: {e}" for e in result.errors])
        return {
            "convergence_status": "N/A",  # Excel 无收敛概念
            "unreliable_stream_names": [],
            "warnings": warnings,
            "preview_streams": preview_streams,
            "conflict_report": _serialize_report(report),
        }

    @classmethod
    async def commit_excel(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        workspace_id: uuid.UUID,
        preview_streams: list[dict[str, Any]],
        actor: uuid.UUID,
    ) -> dict[str, Any]:
        """Excel 预览条目落库。逻辑与 commit_proii 同。"""
        committed: list[uuid.UUID] = []
        skipped = 0
        unreliable_count = 0
        warnings: list[str] = []
        for entry in preview_streams:
            if entry.get("is_unreliable"):
                unreliable_count += 1
            stream_name = entry["stream_name"]
            try:
                stream, _report = await StreamService.create(
                    db,
                    _entry_to_stream_create(
                        entry,
                        project_id=project_id,
                        workspace_id=workspace_id,
                    ),
                    actor=actor,
                )
                committed.append(stream.stream_id)
            except PcsError as e:
                if e.code in {"SIM_STREAM_BLOCKED", "SIM_STREAM_DUPLICATE_NAME"}:
                    skipped += 1
                    warnings.append(f"{stream_name}: {str(e)}")
                else:
                    raise
        return {
            "committed_count": len(committed),
            "unreliable_count": unreliable_count,
            "skipped_count": skipped,
            "stream_ids": committed,
            "warnings": warnings,
        }


def _entry_to_stream_create(
    entry: dict[str, Any],
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> Any:
    """preview_streams entry → StreamCreate（Pydantic 校验入口）。

    preview_streams 当前所有字段都是 schema-valid（is_unreliable 已纳入
    StreamBase），无需过滤。如未来加 preview 私有字段（已转换不可逆的中间
    数据），在此处排除。
    """
    from app.schemas.stream import StreamCreate  # 延迟 import 避免循环

    return StreamCreate(project_id=project_id, workspace_id=workspace_id, **entry)


# ---------------------------------------------------------------------------
# 临时文件 helper
# ---------------------------------------------------------------------------


def write_temp_upload(content: bytes, suffix: str) -> Path:
    """上传字节流 → 临时文件（close 后路径仍可用，caller 负责 unlink）。

    NamedTemporaryFile(delete=False) 便于跨阶段共享路径（preview 解析 + commit
    时二次访问）。返回 Path，caller 需在 finally 中 Path.unlink(missing_ok=True)。
    """
    f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    f.write(content)
    f.close()
    return Path(f.name)


__all__ = [
    "ImportService",
    "write_temp_upload",
]