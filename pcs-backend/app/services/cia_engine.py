"""CIA 变更影响分析引擎（Sprint 3）。

职责：
- 扫描 records 表：当前 record_hash 与 data_lineage 最新 hash 比对
- 不匹配 → 标记 STALE（仅 CHECKED/CHANGED 状态）
- 链式传播：上游 STALE → 下游 STALE
- 设备联动（ADR-0025）：来源 record STALE → 关联 equipment STALE

实现约束：MVP 阶段只扫描 PipingResult 表；FLASH 通过血统矩阵判定，不在 CIA 扫描范围。
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PipingResult
from app.models.config_domain import ConfigAsset, ConfigVersion
from app.models.enums import (
    ActualDataStatus,
    AuditAction,
    RecordSignStatus9,
    StateTransition,
)
from app.models.equipment import EquipmentList
from app.models.system import DataLineage
from app.services.audit_service import AuditService
from app.services.lineage import LineageTracker, _compute_hash
from app.services.state_machine import StateMachineService

# MVP 阶段纳入 CIA 扫描的 record 类型
CIA_TRACKED_TYPES: tuple[str, ...] = ("PipingResult",)

# data_lineage.record_type → ORM 模型 映射表（反向传播路由）
# 未登记的 record_type 静默跳过，避免某模块删表后遗留 lineage 行导致传播中断
REGISTRY: dict[str, type] = {
    "config_asset": ConfigAsset,
    "config_version": ConfigVersion,
    "equipment_list": EquipmentList,
}

# 系统占位 actor UUID（CIA/SYSADMIN 触发的转移无 actor；填占位 UUID）
SYSADMIN_ACTOR = uuid.UUID("00000000-0000-0000-0000-000000000000")


class CIAEngine:
    MAX_DEPTH = 8

    def __init__(self, session: AsyncSession):
        self.session = session
        self.tracker = LineageTracker(session)
        self.fsm = StateMachineService(session)

    async def scan_stale(self, *, project_id: uuid.UUID | None = None) -> int:
        """扫描 + 标记 STALE；返回影响行数。"""
        stale_count = 0
        for cls in (PipingResult,):
            stale_count += await self._scan_one_class(cls, project_id=project_id)
        await self.session.flush()
        return stale_count

    async def _scan_one_class(
        self,
        cls: type[PipingResult],
        *,
        project_id: uuid.UUID | None,
    ) -> int:
        """扫描一个 record 表：current hash vs latest lineage hash。"""
        rows: Sequence[PipingResult] = (
            (
                await self.session.execute(
                    select(cls).where(
                        cls.sign_status.in_(
                            [RecordSignStatus9.CHECKED, RecordSignStatus9.CHANGED]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        marked = 0
        for r in rows:
            if project_id is not None and getattr(r, "project_id", None) != project_id:
                continue
            current_hash = _compute_hash(r)
            latest = await self.tracker.latest(
                record_type=cls.__name__,
                record_id=_pk(r),
            )
            if latest is None:
                continue
            latest_diff = latest.change_diff_json or {}
            baseline = latest_diff.get("hash") if isinstance(latest_diff, dict) else None
            if baseline is None or baseline == current_hash:
                continue
            # 哈希不匹配：尝试 MARK_STALE
            try:
                await self.fsm.transition(
                    record=r,
                    transition=StateTransition.MARK_STALE,
                    actor_user_id=SYSADMIN_ACTOR,
                    actor_role="SYSADMIN",
                    reason=f"CIA: hash mismatch ({cls.__name__})",
                )
            except Exception:
                # 状态机拒绝（不在合法转移集合）— 跳过
                continue
            # 落一条 CIA 血缘
            await self.tracker.track(
                record=r,
                source="CIA",
                change_summary="hash mismatch → STALE",
                change_diff={"old": baseline, "new": current_hash},
                actor_user_id=SYSADMIN_ACTOR,
            )
            marked += 1
        return marked

    async def propagate(self, *, record_type: str, record_id: uuid.UUID) -> int:
        """链式传播：record → 下游 lineage → 标 STALE。

        下游通过 data_lineage.parent_lineage_id 关联（同一 line）。
        """
        # 找出本 record 触发的所有 lineage 节点（按时间正向）
        lineages: Sequence[DataLineage] = (
            (
                await self.session.execute(
                    select(DataLineage).where(
                        DataLineage.record_type == record_type,
                        DataLineage.record_id == record_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not lineages:
            return 0
        # 按 lineage_id 取下游
        affected = 0
        seen: set[uuid.UUID] = set()
        for ln in lineages:
            downstream = await self.tracker.downstream(lineage_id=ln.lineage_id)
            for d in downstream:
                if d.lineage_id in seen:
                    continue
                seen.add(d.lineage_id)
                rec = await self._load_record(d.record_type, d.record_id)
                if rec is None:
                    continue
                try:
                    await self.fsm.transition(
                        record=rec,
                        transition=StateTransition.MARK_STALE,
                        actor_user_id=SYSADMIN_ACTOR,
                        actor_role="SYSADMIN",
                        reason=f"propagation from {record_type}:{record_id}",
                    )
                except Exception:
                    continue
                affected += 1
        await self.session.flush()
        return affected

    async def propagate_to_equipment(
        self,
        *,
        record_type: str,
        record_id: uuid.UUID,
        scan_attempts: int = 0,
    ) -> int:
        """ADR-0025：来源 STALE → 关联 equipment STALE。

        scan_attempts >= 3：actual_data_status=NEED_RECALC + 写 audit（CIA_NOTIFIED/SCAN_FAILED）
        scan_attempts <  3：状态机 MARK_STALE

        MVP 简化：EquipmentList.source_module='PIPING' AND source_record_id == pipe_id。
        """
        if record_type != "PipingResult":
            return 0
        rec = (
            await self.session.execute(
                select(PipingResult).where(PipingResult.pipe_id == record_id)
            )
        ).scalar_one_or_none()
        if rec is None:
            return 0
        matches: Sequence[EquipmentList] = (
            (
                await self.session.execute(
                    select(EquipmentList).where(
                        EquipmentList.source_module == "PIPING",
                        EquipmentList.source_record_id == rec.pipe_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        marked = 0
        audit = AuditService(self.session)
        for eq in matches:
            try:
                if scan_attempts >= 3:
                    eq.actual_data_status = ActualDataStatus.NEED_RECALC.value
                    await audit.write(
                        action=AuditAction.CIA_NOTIFIED,
                        resource_type="equipment_list",
                        resource_id=eq.equipment_id,
                        user_id=None,
                        detail={
                            "reason": "SCAN_FAILED",
                            "source_record_type": record_type,
                            "source_record_id": str(record_id),
                            "scan_attempts": scan_attempts,
                        },
                    )
                else:
                    await self.fsm.transition(
                        record=eq,
                        transition=StateTransition.MARK_STALE,
                        actor_user_id=SYSADMIN_ACTOR,
                        actor_role="SYSADMIN",
                        reason=f"ADR-0025: source pipe {rec.line_no} STALE",
                    )
                marked += 1
            except Exception:
                continue
        await self.session.flush()
        return marked

    async def _load_record(self, record_type: str, record_id: uuid.UUID):
        """按 record_type 名查 record。MVP：仅 PipingResult。"""
        if record_type == "PipingResult":
            return (
                await self.session.execute(
                    select(PipingResult).where(PipingResult.pipe_id == record_id)
                )
            ).scalar_one_or_none()
        return None

    async def propagate_from_source(
        self, source_type: str, source_id: uuid.UUID
    ) -> int:
        """反向传播：以 (source_type, source_id) 为起点，沿 data_lineage 反向传播
        （按 source_ref_type/source_ref_id 查询），把所有下游 record 标 STALE。

        返回被标 STALE 的下游 record 数（含递归产生的）。
        """
        marked = 0
        visited: set[tuple[str, uuid.UUID]] = set()
        async for _ in self._iter_propagate(source_type, source_id, depth=0, visited=visited):
            marked += 1
        await self.session.flush()
        return marked

    async def _iter_propagate(
        self,
        source_type: str,
        source_id: uuid.UUID,
        *,
        depth: int,
        visited: set[tuple[str, uuid.UUID]],
    ):
        """递归助手：generator 形式 — yield 每个被标 STALE 的 record。

        MAX_DEPTH=8 截断（深度 8 进入即返回，不再访问其下游）；
        visited set 防环 + 防重复访问。
        """
        if depth >= self.MAX_DEPTH:
            return
        key = (source_type, source_id)
        if key in visited:
            return
        visited.add(key)
        rows: Sequence[DataLineage] = (
            (
                await self.session.execute(
                    select(DataLineage).where(
                        DataLineage.source_ref_type == source_type,
                        DataLineage.source_ref_id == source_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for lineage in rows:
            record = await self._get_record(lineage.record_type, lineage.record_id)
            if record is None:
                continue
            current = getattr(record, "sign_status", None)
            if current is None:
                # 无 sign_status 字段的 model：不标，但仍递归其下游
                async for _ in self._iter_propagate(
                    lineage.record_type,
                    lineage.record_id,
                    depth=depth + 1,
                    visited=visited,
                ):
                    yield _
                continue
            if current != RecordSignStatus9.STALE:
                record.sign_status = RecordSignStatus9.STALE
                yield record
            async for nested in self._iter_propagate(
                lineage.record_type,
                lineage.record_id,
                depth=depth + 1,
                visited=visited,
            ):
                yield nested

    async def _get_record(self, record_type: str, record_id: uuid.UUID):
        """按 record_type 路由到对应 ORM 模型；未登记返回 None（静默跳过）。

        已删除的 record → session.get 返回 None，传播静默跳过。
        """
        model = REGISTRY.get(record_type)
        if model is None:
            return None
        return await self.session.get(model, record_id)


def _pk(record) -> uuid.UUID:
    from sqlalchemy import inspect as _inspect

    mapper = _inspect(record.__class__)
    if mapper is None:
        raise TypeError(f"cannot inspect mapper for {record.__class__.__name__}")
    val = getattr(record, mapper.primary_key[0].name)
    if not isinstance(val, uuid.UUID):
        raise TypeError(f"record PK must be UUID, got {type(val).__name__}")
    return val


async def mark_stale_then_propagate(
    session: AsyncSession,
    *,
    record_type: str,
    record_id: uuid.UUID,
) -> dict[str, int]:
    """CIA 高层动作：mark + propagate + equipment 联动。

    返回各阶段影响行数。
    """
    engine = CIAEngine(session)
    propagated = await engine.propagate(
        record_type=record_type, record_id=record_id
    )
    equipment = await engine.propagate_to_equipment(
        record_type=record_type, record_id=record_id
    )
    return {"propagated": propagated, "equipment": equipment}


__all__ = [
    "CIAEngine",
    "CIA_TRACKED_TYPES",
    "mark_stale_then_propagate",
]


# 暴露给测试用
_ = Iterable  # 防止 unused warning