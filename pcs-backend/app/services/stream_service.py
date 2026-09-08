"""P3.2 SIM-4 + SIM-8：StreamService 物流 / 状态点 CRUD（spec V1.6 §3.2.3）。

整合 P3.2 SIM-1 ORM + SIM-3 物性补全 + SIM-7 三级冲突 + SIM-9 状态点冲突：

Stream CRUD（SIM-4）：
- create / list / get / update / delete
- create 与 update 走 SIM-3 物性补全 + SIM-7 冲突检测
- BLOCK 冲突 → 拒绝保存（PcsError 422, code=SIM_STREAM_BLOCKED）
- WARN 冲突 → 保存 + 返回 conflicts.warnings
- INFO 冲突 → 保存 + 返回 conflicts.infos
- unique (project_id, stream_name) 约束 → 422 (SIM_STREAM_DUPLICATE_NAME)

StatePoint CRUD（SIM-8，新增）：
- create_state_point / list_state_points / get_state_point / update_state_point / delete_state_point
- 走 SIM-9 状态点冲突检测（SIM-SV01~SV05）
- BLOCK 冲突 → 拒绝保存（PcsError 422, code=SIM_STATEPOINT_BLOCKED）
- 状态点按所属 stream_name 关联；父流删除时 FK 联动删除

API 入口（SIM-6 / SIM-8）：POST/GET/PATCH/DELETE /streams 与 /state-points。
下游：SIM-10 导入预览 commit 时复用 create() 路径。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Stream, StreamStatePoint
from app.schemas.stream import (
    StreamCreate,
    StreamStatePointCreate,
    StreamStatePointUpdate,
    StreamUpdate,
)
from app.services.conflict_resolver import ConflictReport, ConflictResolver
from app.services.exceptions import PcsError
from app.services.property_completion import ParsedStatePoint, ParsedStream

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


def _to_parsed_state_point(
    payload: dict[str, Any],
    *,
    stream_name: str,
    state_point_id: str | None = None,
) -> ParsedStatePoint:
    """StreamStatePointCreate/Update dict → ParsedStatePoint（SI 单位）。

    - temp °C → K
    - press kPa → Pa
    - composition_json → composition dict
    """
    composition = payload.get("composition_json") or {}
    return ParsedStatePoint(
        state_point_id=state_point_id or payload.get("state_point_id", ""),
        stream_name=stream_name,
        state_label=payload.get("state_label", ""),
        case_type=payload.get("case_type", "NORMAL"),
        temperature_k=(
            (payload["temp"] + _C_TO_K_OFFSET) if payload.get("temp") is not None else None
        ),
        pressure_pa=(
            payload["press"] * _KPA_TO_PA if payload.get("press") is not None else None
        ),
        phase=payload.get("phase"),
        vapor_fraction=payload.get("vapor_fraction"),
        mass_flow_kg_h=payload.get("mass_flow"),
        composition=composition or None,
        vapor_composition=payload.get("vapor_composition_json") or None,
        liquid_composition=payload.get("liquid_composition_json") or None,
        source_type=payload.get("source_type"),
    )


class StreamService:
    """物流 + 状态点 CRUD 服务。

    Stream / StreamStatePoint ID 类型 UUID；project_id + stream_name 联合唯一。
    StatePoint 通过 stream_id FK 关联 Stream。
    """

    # =====================================================================
    # Stream CRUD（SIM-4）
    # =====================================================================

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

    # =====================================================================
    # StatePoint CRUD（SIM-8）
    # =====================================================================

    @staticmethod
    async def create_state_point(
        db: AsyncSession,
        stream_id: uuid.UUID,
        payload: StreamStatePointCreate,
        *,
        actor: uuid.UUID,
    ) -> tuple[StreamStatePoint, ConflictReport]:
        """创建状态点：SIM-9 冲突检测，BLOCK 拒绝。

        Args:
            db: async session
            stream_id: 所属物流 ID（FK）
            payload: StreamStatePointCreate（state_label/case_type/temp/press/...）
            actor: 操作用户 UUID（保留字段）

        Returns:
            (saved_state_point, ConflictReport)

        Raises:
            PcsError(404, SIM_STREAM_NOT_FOUND): 父流不存在
            PcsError(422, SIM_STATEPOINT_BLOCKED): BLOCK 冲突（SIM-SV01~SV05）
        """
        stream = await StreamService.get(db, stream_id)
        data = payload.model_dump(exclude={"stream_id"})
        parsed = _to_parsed_state_point(
            data, stream_name=stream.stream_name
        )
        report = ConflictResolver().resolve_state_points(
            [parsed], parent_streams=[stream.stream_name], block_on_error=False
        )
        if report.has_blocks:
            first = report.blocks[0]
            raise PcsError(
                f"状态点 {payload.state_label} 触发 BLOCK 冲突 "
                f"[{first.code}]: {first.message}",
                code="SIM_STATEPOINT_BLOCKED",
                status=422,
            )
        sp = StreamStatePoint(stream_id=stream_id, **data)
        db.add(sp)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            # bug-062 闭环：DB UniqueConstraint(stream_id, case_type, state_label)
            # 拦截跨批次 duplicate。PG 含约束名；SQLite 仅列名 → 双匹配。
            err_str = str(e.orig)
            if (
                "uq_stream_state_points_label" in err_str
                or (
                    "UNIQUE constraint failed" in err_str
                    and "state_label" in err_str
                )
            ):
                raise PcsError(
                    f"状态点 (state_label='{payload.state_label}', "
                    f"case_type='{payload.case_type}') 已存在",
                    code="SIM_STATEPOINT_BLOCKED",
                    status=422,
                ) from e
            raise
        await db.refresh(sp)
        return sp, report

    @staticmethod
    async def list_state_points(
        db: AsyncSession, stream_id: uuid.UUID
    ) -> list[StreamStatePoint]:
        """某物流下状态点列表（按 case_type 排序，NORMAL → MIN → MAX → ALTERNATE）。"""
        # 父流存在性校验（返回 404 而不是空列表）
        await StreamService.get(db, stream_id)
        stmt = (
            select(StreamStatePoint)
            .where(StreamStatePoint.stream_id == stream_id)
            .order_by(StreamStatePoint.case_type, StreamStatePoint.state_label)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_state_point(
        db: AsyncSession, state_point_id: uuid.UUID
    ) -> StreamStatePoint:
        """单条状态点查询。"""
        sp = await db.get(StreamStatePoint, state_point_id)
        if sp is None:
            raise PcsError(
                f"StreamStatePoint {state_point_id} 不存在",
                code="SIM_STATEPOINT_NOT_FOUND",
                status=404,
            )
        return sp

    @staticmethod
    async def update_state_point(
        db: AsyncSession,
        state_point_id: uuid.UUID,
        payload: StreamStatePointUpdate,
        *,
        actor: uuid.UUID,
    ) -> tuple[StreamStatePoint, ConflictReport]:
        """更新状态点（部分字段）。BLOCK 拒绝；其他冲突保留。"""
        sp = await StreamService.get_state_point(db, state_point_id)
        data = payload.model_dump(exclude_none=True)
        merged = {**StreamService._state_point_to_dict(sp), **data}
        stream = await StreamService.get(db, sp.stream_id)
        parsed = _to_parsed_state_point(
            merged,
            stream_name=stream.stream_name,
            state_point_id=str(sp.state_point_id),
        )
        report = ConflictResolver().resolve_state_points(
            [parsed], parent_streams=[stream.stream_name], block_on_error=False
        )
        if report.has_blocks:
            first = report.blocks[0]
            raise PcsError(
                f"状态点 {sp.state_label} 触发 BLOCK 冲突 "
                f"[{first.code}]: {first.message}",
                code="SIM_STATEPOINT_BLOCKED",
                status=422,
            )
        for k, v in data.items():
            setattr(sp, k, v)
        await db.commit()
        await db.refresh(sp)
        return sp, report

    @staticmethod
    async def delete_state_point(
        db: AsyncSession, state_point_id: uuid.UUID, *, actor: uuid.UUID
    ) -> None:
        """删除状态点。"""
        sp = await StreamService.get_state_point(db, state_point_id)
        await db.delete(sp)
        await db.commit()

    @staticmethod
    def _state_point_to_dict(sp: StreamStatePoint) -> dict[str, Any]:
        """ORM StreamStatePoint → 业务字段 dict。"""
        skip = {"state_point_id", "stream_id", "record_hash", "created_at"}
        out: dict[str, Any] = {}
        for col in StreamStatePoint.__table__.columns:
            if col.name in skip:
                continue
            out[col.name] = getattr(sp, col.name)
        return out


__all__ = ["StreamService"]
