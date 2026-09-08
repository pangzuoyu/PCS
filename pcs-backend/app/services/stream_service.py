"""P3.2 SIM-4：StreamService 物流 CRUD（spec V1.6 §3.2.3）。

整合 P3.2 SIM-1 ORM + SIM-3 物性补全 + SIM-7 三级冲突检测：

- create / list / get / update / delete
- create 与 update 走 SIM-3 物性补全 + SIM-7 冲突检测
- BLOCK 冲突 → 拒绝保存（PcsError 422, code=SIM_STREAM_BLOCKED）
- WARN 冲突 → 保存 + 返回 conflicts.warnings
- INFO 冲突 → 保存 + 返回 conflicts.infos
- unique (project_id, stream_name) 约束 → 422 (SIM_STREAM_DUPLICATE_NAME)

API 入口（SIM-6 落 API）：POST/GET/PATCH/DELETE /projects/{id}/streams
下游：SIM-8 状态点 CRUD 合并本 service；SIM-10 导入预览 commit 时复用
  create() 路径。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Stream
from app.schemas.stream import StreamCreate, StreamUpdate
from app.services.conflict_resolver import ConflictReport, ConflictResolver
from app.services.exceptions import PcsError
from app.services.property_completion import ParsedStream

_C_TO_K_OFFSET = 273.15
_KPA_TO_PA = 1000.0


def _to_parsed_stream(payload: dict[str, Any], tag: str) -> ParsedStream:
    """StreamCreate/Update dict → ParsedStream（SI 单位 + 多 CAS 主导取首 CAS）。

    - temp °C → K（+273.15）
    - press kPa → Pa（×1000）
    - composition_json → composition dict（保留 CAS→frac 形式）
    - 多 CAS 时 .cas 取 composition 首个键（SIM-3 物性补全的近似主导组分）
    """
    composition = payload.get("composition_json") or {}
    cas = next(iter(composition), None) if composition else None
    return ParsedStream(
        tag=tag,
        cas=cas,
        temperature_k=(
            (payload["temp"] + _C_TO_K_OFFSET) if payload.get("temp") is not None else None
        ),
        pressure_pa=(
            payload["press"] * _KPA_TO_PA if payload.get("press") is not None else None
        ),
        phase=payload.get("phase"),
        mass_flow_kg_h=payload.get("mass_flow"),
        molar_flow_kmol_h=payload.get("molar_flow"),
        molecular_weight=payload.get("molecular_weight"),
        composition=composition or None,
        vapor_composition=payload.get("vapor_composition_json") or None,
        liquid_composition=payload.get("liquid_composition_json") or None,
    )


class StreamService:
    """物流 CRUD 服务。Stream ID 类型 UUID；project_id + stream_name 联合唯一。"""

    @staticmethod
    async def create(
        db: AsyncSession, payload: StreamCreate, *, actor: uuid.UUID
    ) -> tuple[Stream, ConflictReport]:
        """创建物流：SIM-3 物性补全 + SIM-7 冲突检测，BLOCK 拒绝。

        Returns:
            (saved_stream, ConflictReport)

        Raises:
            PcsError(422, SIM_STREAM_BLOCKED): 任意 BLOCK 冲突
            PcsError(422, SIM_STREAM_DUPLICATE_NAME): 同 (project, stream_name) 已存在
        """
        data = payload.model_dump(exclude={"project_id", "workspace_id"})
        # 物性补全 + 冲突检测
        parsed = _to_parsed_stream(data, tag=payload.stream_name)
        report = ConflictResolver().resolve_batch([parsed], block_on_error=False)
        if report.has_blocks:
            # 取首条 BLOCK 消息作为错误 message
            first = report.blocks[0]
            raise PcsError(
                f"物流 {payload.stream_name} 触发 BLOCK 冲突 [{first.code}]: {first.message}",
                code="SIM_STREAM_BLOCKED",
                status=422,
            )
        stream = Stream(
            project_id=payload.project_id,
            workspace_id=payload.workspace_id,
            approval_depth=1,  # spec V1.6 §3.2.1 默认 1 步校对
            **data,
        )
        db.add(stream)
        try:
            await db.flush()
        except IntegrityError as e:
            await db.rollback()
            # PG: "duplicate key value violates unique constraint 'uq_streams...'"
            # SQLite: "UNIQUE constraint failed: streams.project_id, streams.stream_name"
            err_str = str(e.orig)
            if (
                "uq_streams_project_stream_name" in err_str
                or ("UNIQUE constraint failed" in err_str and "stream_name" in err_str)
            ):
                raise PcsError(
                    f"同项目内已存在 stream_name={payload.stream_name}",
                    code="SIM_STREAM_DUPLICATE_NAME",
                    status=422,
                ) from e
            raise
        await db.commit()
        await db.refresh(stream)
        return stream, report

    @staticmethod
    async def list_by_project(
        db: AsyncSession,
        project_id: uuid.UUID,
        *,
        case_type: str | None = None,
    ) -> list[Stream]:
        """项目下物流列表（可选 case_type 过滤）。"""
        stmt = select(Stream).where(Stream.project_id == project_id)
        if case_type is not None:
            stmt = stmt.where(Stream.case_type == case_type)
        stmt = stmt.order_by(Stream.stream_name)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get(db: AsyncSession, stream_id: uuid.UUID) -> Stream:
        """单条物流查询。"""
        stream = await db.get(Stream, stream_id)
        if stream is None:
            raise PcsError(
                f"Stream {stream_id} 不存在",
                code="SIM_STREAM_NOT_FOUND",
                status=404,
            )
        return stream

    @staticmethod
    async def update(
        db: AsyncSession,
        stream_id: uuid.UUID,
        payload: StreamUpdate,
        *,
        actor: uuid.UUID,
    ) -> tuple[Stream, ConflictReport]:
        """更新物流（部分字段）。BLOCK 拒绝；其他冲突保留。"""
        stream = await StreamService.get(db, stream_id)
        data = payload.model_dump(exclude_none=True)
        # 合并后再做物性补全 + 冲突检测（用最新 effective 值）
        merged = {**StreamService._to_dict(stream), **data}
        parsed = _to_parsed_stream(merged, tag=merged.get("stream_name", stream.stream_name))
        report = ConflictResolver().resolve_batch([parsed], block_on_error=False)
        if report.has_blocks:
            first = report.blocks[0]
            raise PcsError(
                f"物流 {stream.stream_name} 触发 BLOCK 冲突 [{first.code}]: {first.message}",
                code="SIM_STREAM_BLOCKED",
                status=422,
            )
        for k, v in data.items():
            setattr(stream, k, v)
        await db.commit()
        await db.refresh(stream)
        return stream, report

    @staticmethod
    async def delete(db: AsyncSession, stream_id: uuid.UUID, *, actor: uuid.UUID) -> None:
        """删除物流（hard delete — Stream 无软删字段；状态点通过 FK 联动）。"""
        stream = await StreamService.get(db, stream_id)
        await db.delete(stream)
        await db.commit()

    @staticmethod
    def _to_dict(stream: Stream) -> dict[str, Any]:
        """ORM Stream → 业务字段 dict（排除审计 + ID）。"""
        skip = {
            "stream_id",
            "project_id",
            "workspace_id",
            "sign_status",
            "approval_step",
            "checked_by",
            "checked_at",
            "record_hash",
            "last_change_reason",
            "last_change_note",
            "last_changed_by",
            "last_changed_at",
            "created_at",
            "updated_at",
        }
        out: dict[str, Any] = {}
        for col in Stream.__table__.columns:
            if col.name in skip:
                continue
            out[col.name] = getattr(stream, col.name)
        return out


__all__ = ["StreamService"]
