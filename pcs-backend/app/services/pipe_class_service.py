"""PipeClassService — 管道等级 CRUD + 项目分配（Task 1.9.1 / P2-STD-001）。

规则（spec §3.2.5 验收）：已用等级不可删除（仅可作废）。
在用判定：project_pipe_classes 存在关联行 或 piping_results.material_class 引用。
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PipingResult
from app.models.config_domain import PipeClass, ProjectPipeClass
from app.schemas.pipe_class import PipeClassCreate, PipeClassUpdate
from app.services.exceptions import PcsError

_STATUS_OK = {"DRAFT", "ACTIVE", "OBSOLETE"}

IMPORT_HEADERS = [
    "class_id", "class_name", "material_standard", "corrosion_allowance",
    "design_pressure", "design_temperature", "dn_min", "dn_max",
    "sch_series(JSON)", "flange_class", "source", "version",
]


class PipeClassService:
    @classmethod
    async def list_company(
        cls, session: AsyncSession, *, status: str | None = None, keyword: str | None = None
    ) -> list[PipeClass]:
        stmt = select(PipeClass).where(PipeClass.source == "COMPANY_STD")
        if status:
            stmt = stmt.where(PipeClass.status == status)
        if keyword:
            stmt = stmt.where(PipeClass.class_name.ilike(f"%{keyword}%"))
        stmt = stmt.order_by(PipeClass.class_id)
        return list((await session.execute(stmt)).scalars())

    @classmethod
    async def get(cls, session: AsyncSession, class_id: str) -> PipeClass:
        pc = await session.get(PipeClass, class_id)
        if not pc:
            raise PcsError(f"管道等级 {class_id} 不存在", code="PIPE_CLASS_NOT_FOUND", status=404)
        return pc

    @classmethod
    async def create(cls, session: AsyncSession, *, payload: PipeClassCreate) -> PipeClass:
        if await session.get(PipeClass, payload.class_id):
            raise PcsError(f"管道等级 {payload.class_id} 已存在", code="PIPE_CLASS_DUP", status=409)
        pc = PipeClass(**payload.model_dump(), status="DRAFT")
        session.add(pc)
        await session.commit()
        return pc

    @classmethod
    async def update(
        cls, session: AsyncSession, class_id: str, *, payload: PipeClassUpdate
    ) -> PipeClass:
        pc = await cls.get(session, class_id)
        if payload.status == "OBSOLETE" and pc.status != "OBSOLETE":
            new_status = "OBSOLETE"  # 作废：单向，允许 DRAFT/ACTIVE → OBSOLETE
        elif payload.status == pc.status or (pc.status == "DRAFT" and payload.status == "ACTIVE"):
            new_status = payload.status
        else:
            raise PcsError(
                f"非法状态流转 {pc.status}→{payload.status}（OBSOLETE 单向）",
                code="PIPE_CLASS_BAD_TRANSITION", status=409,
            )
        data = payload.model_dump(exclude={"status"})
        for k, v in data.items():
            setattr(pc, k, v)
        pc.status = new_status
        await session.commit()
        return pc

    @classmethod
    async def delete(cls, session: AsyncSession, class_id: str) -> None:
        await cls.get(session, class_id)
        assigned = (await session.execute(
            select(ProjectPipeClass.class_id).where(ProjectPipeClass.class_id == class_id)
        )).first()
        lined = (await session.execute(
            select(PipingResult.pipe_id).where(PipingResult.material_class == class_id).limit(1)
        )).first()
        if assigned or lined:
            raise PcsError(
                f"等级 {class_id} 已被项目/管道行引用，不可删除（仅可作废）",
                code="PIPE_CLASS_IN_USE", status=409,
            )
        await session.execute(
            PipeClass.__table__.delete().where(PipeClass.class_id == class_id)
        )
        await session.commit()

    @classmethod
    async def assign_to_project(
        cls, session: AsyncSession, project_id: uuid.UUID, class_id: str,
        *, enabled: bool = True, override: dict | None = None,
    ) -> ProjectPipeClass:
        await cls.get(session, class_id)
        row = await session.get(ProjectPipeClass, {"project_id": project_id, "class_id": class_id})
        if row:
            row.enabled = enabled
            row.custom_override_json = override
        else:
            row = ProjectPipeClass(
                project_id=project_id, class_id=class_id,
                enabled=enabled, custom_override_json=override,
            )
            session.add(row)
        await session.commit()
        return row

    @classmethod
    async def list_project(
        cls, session: AsyncSession, project_id: uuid.UUID
    ) -> list[ProjectPipeClass]:
        stmt = (
            select(ProjectPipeClass)
            .where(ProjectPipeClass.project_id == project_id)
            .order_by(ProjectPipeClass.class_id)
        )
        return list((await session.execute(stmt)).scalars())

    # ------------------------------------------------------------------
    # Excel 批量导入（Task 1.9.6 / P2-STD-001）
    # ------------------------------------------------------------------

    @classmethod
    def build_import_template(cls) -> bytes:
        import io

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "pipe_classes"
        ws.append(IMPORT_HEADERS)
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    @classmethod
    async def import_from_excel(cls, session, fileobj) -> dict:
        import json

        from openpyxl import load_workbook

        wb = load_workbook(fileobj, read_only=True, data_only=True)
        ws = wb["pipe_classes"] if "pipe_classes" in wb.sheetnames else wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows or [str(c) for c in rows[0]] != IMPORT_HEADERS:
            raise PcsError("表头不符（须用 /pipe-classes/import-template 模板）",
                           code="IMPORT_BAD_HEADER", status=422)
        imported = skipped = 0
        errors: list[str] = []
        for i, row in enumerate(rows[1:], start=2):
            if not row or not row[0]:
                continue
            try:
                sch = json.loads(row[8]) if row[8] else {}
                payload = PipeClassCreate(
                    class_id=str(row[0]), class_name=str(row[1]), material_standard=str(row[2]),
                    corrosion_allowance=float(row[3]), design_pressure=float(row[4]),
                    design_temperature=float(row[5]),
                    dn_series_json={"min": int(row[6]), "max": int(row[7])},
                    sch_series_json={str(k): str(v) for k, v in sch.items()},
                    flange_class=str(row[9]), source=str(row[10]), version=str(row[11]),
                )
                await cls.create(session, payload=payload)
                imported += 1
            except PcsError as e:
                if e.code == "PIPE_CLASS_DUP":
                    skipped += 1
                else:
                    errors.append(f"行{i}: {e}")
            except (ValueError, TypeError, IndexError, json.JSONDecodeError) as e:
                errors.append(f"行{i}: 解析失败 {e}")
        return {"imported": imported, "skipped": skipped, "errors": errors}
