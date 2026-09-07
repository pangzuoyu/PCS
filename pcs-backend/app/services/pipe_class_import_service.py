"""SUP-002 PC-5：管道等级 Excel 双 Sheet + 验证引擎 + import_id 暂存。

V1.4 §0.6/§三、#6：
- Sheet1 12 列模板（V1.4 EXCEL-01 锁 1.9.6 表头）；可选 13 列 BaseMaterial
  （插在 MaterialStandard 之后）
- Sheet2 Sch系列 可选；按 (ClassID, DN) → Sch 列表 长表，覆盖 Sheet1 隐式 sch
- 校验走 PipeClassValidator.validate_company（PC-2 已锁 22 条规则）
- preview 写 pipe_class_import_previews 返 import_id；commit_import 按 import_id
  重放，二次同 import_id 拒绝（consumed_at 防重复消费）
- TTL 24h（service 层按 expires_at 过滤；过期返回 410）

本服务是 1.9 PipeClassService.import_from_excel 的 SUP-002 升级版，旧方法保留
（向后兼容 + xfail 测试用）。两方法并存。
"""
from __future__ import annotations

import io
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import openpyxl
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import PipeClass, PipeClassImportPreview
from app.services.exceptions import PcsError
from app.services.pipe_class_validator import (
    PipeClassValidator,
    Severity,
    ValidationResult,
)


class _ActorLike(Protocol):
    """最小 actor 协议 — 与 PipeClassService._ActorLike 对齐。"""

    user_id: Any
    role: str | None


# ---------- 表头常量（V1.4 EXCEL-01 锁 1.9.6 模板） ----------

SHEET1_HEADERS_12: list[str] = [
    "ClassID", "ClassName", "MaterialStandard", "DesignPressure", "DesignTemp",
    "CorrosionAllowance", "FlangeClass", "FittingType", "AllowableStressTable",
    "BranchTable", "Source", "Version",
]
# 13 列：BaseMaterial 插在 MaterialStandard 之后（PC-1 加的列，EXCEL-01 允许）
SHEET1_HEADERS_13: list[str] = SHEET1_HEADERS_12.copy()
SHEET1_HEADERS_13.insert(3, "BaseMaterial")

SHEET2_HEADERS: list[str] = ["ClassID", "DN", "Sch列表"]

PREVIEW_TTL_HOURS = 24


# ---------- DTO ----------

@dataclass
class ImportRow:
    """单行预览数据（已校验）。"""

    row_number: int
    class_id: str
    data: dict
    results: list[ValidationResult] = field(default_factory=list)


@dataclass
class ImportPreview:
    """预览聚合结果（DB 序列化为 parsed_json）。"""

    valid: list[ImportRow] = field(default_factory=list)
    errors: list[ValidationResult] = field(default_factory=list)
    warnings: list[ValidationResult] = field(default_factory=list)

    def has_errors(self) -> bool:
        return any(r.severity == Severity.ERROR for r in self.errors)


# ---------- Service ----------

class PipeClassImportService:
    """PC-5：双 Sheet + 验证引擎 + import_id 暂存。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- 模板（V1.4 EXCEL-01 锁 1.9.6 12 列） ----------

    @staticmethod
    def build_import_template() -> bytes:
        """生成 12 列 Excel 模板（与 V1.4 EXCEL-01 一致）。"""
        wb = Workbook()
        ws = wb.active
        ws.title = "等级列表"
        ws.append(SHEET1_HEADERS_12)
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # ---------- preview ----------

    async def preview(
        self,
        file_bytes: bytes,
        *,
        actor: _ActorLike | None = None,
    ) -> tuple[ImportPreview, uuid.UUID]:
        """解析 Excel → 逐行校验 → 暂存 → 返 (preview, import_id)。"""
        rows = self._parse_excel(file_bytes)
        preview = ImportPreview()
        for row in rows:
            results = PipeClassValidator.validate_company(row.data)
            row.results = list(results)
            errs = [r for r in results if r.severity == Severity.ERROR]
            warns = [r for r in results if r.severity == Severity.WARN]
            preview.errors.extend(errs)
            preview.warnings.extend(warns)
            if not errs:
                preview.valid.append(row)

        import_id = uuid.uuid4()
        now = datetime.now(UTC)
        actor_id = getattr(actor, "user_id", None) if actor else None
        rec = PipeClassImportPreview(
            import_id=import_id,
            actor_id=actor_id,
            file_bytes=file_bytes,
            parsed_json=self._serialize_preview(preview),
            error_count=len(preview.errors),
            warning_count=len(preview.warnings),
            expires_at=now + timedelta(hours=PREVIEW_TTL_HOURS),
        )
        self.db.add(rec)
        await self.db.commit()
        return preview, import_id

    # ---------- get_preview（按 import_id 取，不消费） ----------

    async def get_preview(self, import_id: uuid.UUID) -> ImportPreview:
        """按 import_id 取预览结果。已消费 409；已过期 410；不存在 404。"""
        rec = await self.db.get(PipeClassImportPreview, import_id)
        if rec is None:
            raise PcsError(
                f"导入预览 {import_id} 不存在",
                code="IMPORT_NOT_FOUND", status=404,
            )
        now = datetime.now(UTC)
        expires_at = rec.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < now:
            raise PcsError(
                f"导入预览 {import_id} 已过期",
                code="IMPORT_EXPIRED", status=410,
            )
        if rec.consumed_at is not None:
            raise PcsError(
                f"导入预览 {import_id} 已消费，不可重放",
                code="IMPORT_CONSUMED", status=409,
            )
        return self._deserialize_preview(rec.parsed_json)

    # ---------- commit_import ----------

    async def commit_import(
        self,
        import_id: uuid.UUID,
        *,
        actor: _ActorLike | None = None,
    ) -> int:
        """按 import_id 重放 preview 写入 PipeClass；任一行失败全量回滚。

        第二次同 import_id 拒绝（IMPORT_CONSUMED 409）。preview 含 ERROR 拒绝
        写入（IMPORT_HAS_ERRORS 422）。
        """
        preview = await self.get_preview(import_id)  # raises if expired/consumed
        if preview.has_errors():
            raise PcsError(
                "存在校验错误，不可导入",
                code="IMPORT_HAS_ERRORS", status=422,
            )

        inserted = 0
        try:
            for row in preview.valid:
                pc = self._build_pipe_class(row.data)
                self.db.add(pc)
                inserted += 1
            await self.db.flush()
        except Exception:
            await self.db.rollback()
            raise

        # 标记 consumed（独立小事务）
        rec = await self.db.get(PipeClassImportPreview, import_id)
        rec.consumed_at = datetime.now(UTC)
        await self.db.commit()
        return inserted

    # ---------- 序列化 ----------

    @staticmethod
    def _serialize_preview(preview: ImportPreview) -> dict:
        return {
            "valid": [
                {"row_number": r.row_number, "class_id": r.class_id, "data": r.data}
                for r in preview.valid
            ],
            "errors": [
                {"rule_id": r.rule_id, "severity": r.severity.value,
                 "message": r.message, "field": r.field}
                for r in preview.errors
            ],
            "warnings": [
                {"rule_id": r.rule_id, "severity": r.severity.value,
                 "message": r.message, "field": r.field}
                for r in preview.warnings
            ],
        }

    @staticmethod
    def _deserialize_preview(data: dict) -> ImportPreview:
        preview = ImportPreview()
        for v in data.get("valid", []):
            preview.valid.append(ImportRow(
                row_number=v["row_number"], class_id=v["class_id"], data=v["data"],
            ))
        for e in data.get("errors", []):
            preview.errors.append(ValidationResult(
                rule_id=e["rule_id"], severity=Severity(e["severity"]),
                message=e["message"], field=e.get("field"),
            ))
        for w in data.get("warnings", []):
            preview.warnings.append(ValidationResult(
                rule_id=w["rule_id"], severity=Severity(w["severity"]),
                message=w["message"], field=w.get("field"),
            ))
        return preview

    # ---------- ORM 构造 ----------

    @staticmethod
    def _build_pipe_class(payload: dict) -> PipeClass:
        """按解析后 data 构造 PipeClass ORM 行（DRAFT）。"""
        bm = payload.get("base_material") or payload.get("material_standard")
        return PipeClass(
            class_id=payload["class_id"],
            class_name=payload["class_name"],
            material_standard=payload["material_standard"],
            base_material=bm,
            corrosion_allowance=float(payload["corrosion_allowance"]),
            design_pressure=float(payload["design_pressure"]),
            design_temperature=float(payload["design_temperature"]),
            dn_series_json=payload.get("dn_series_json") or {},
            sch_series_json=payload.get("sch_series_json") or {},
            flange_class=payload["flange_class"],
            fitting_type=payload.get("fitting_type"),
            allowable_stress_json=payload.get("allowable_stress_json") or {},
            branch_table_json=payload.get("branch_table_json") or {},
            source=payload.get("source") or "COMPANY_STD",
            version=payload.get("version") or "1",
            status="DRAFT",
        )

    # ---------- Excel 解析 ----------

    def _parse_excel(self, file_bytes: bytes) -> list[ImportRow]:
        wb = openpyxl.load_workbook(
            io.BytesIO(file_bytes), read_only=True, data_only=True,
        )
        sheet1_name = "等级列表" if "等级列表" in wb.sheetnames else wb.sheetnames[0]
        ws1 = wb[sheet1_name]
        rows = list(ws1.iter_rows(values_only=True))
        if not rows:
            raise PcsError(
                "Sheet1 为空",
                code="IMPORT_BAD_HEADER", status=422,
            )
        header = [str(c) for c in rows[0]] if rows[0] else []
        if header == SHEET1_HEADERS_12:
            has_base_material = False
        elif header == SHEET1_HEADERS_13:
            has_base_material = True
        else:
            raise PcsError(
                f"表头不符（需 12 或 13 列），实际 {header}",
                code="IMPORT_BAD_HEADER", status=422,
            )

        # Sheet2（可选）— Sch系列 长表
        sch_by_class: dict[str, dict[str, list[str]]] = {}
        dns_by_class: dict[str, list[int]] = {}
        if "Sch系列" in wb.sheetnames:
            ws2 = wb["Sch系列"]
            for r in ws2.iter_rows(min_row=2, values_only=True):
                if not r or not r[0]:
                    continue
                cid = str(r[0])
                try:
                    dn = int(r[1])
                except (TypeError, ValueError):
                    continue
                raw = r[2]
                if raw is None or str(raw).strip() == "":
                    continue
                sch_vals = [v.strip() for v in str(raw).split(",") if v.strip()]
                sch_by_class.setdefault(cid, {})[f"DN{dn}"] = sch_vals
                dns_by_class.setdefault(cid, []).append(dn)

        out: list[ImportRow] = []
        for idx, r in enumerate(rows[1:], start=2):
            if not r or r[0] is None or str(r[0]).strip() == "":
                continue
            cid = str(r[0])
            data = self._build_row_data(
                cid, r, has_base_material, sch_by_class.get(cid, {}),
                dns_by_class.get(cid, []),
            )
            out.append(ImportRow(row_number=idx, class_id=cid, data=data))
        return out

    @staticmethod
    def _build_row_data(
        class_id: str,
        row: tuple,
        has_base_material: bool,
        sch_map: dict[str, list[str]],
        dns: list[int],
    ) -> dict:
        """单行原始 tuple → validator 友好的 data dict。"""
        if has_base_material:
            # [ClassID, ClassName, MaterialStandard, BaseMaterial, DesignPressure,
            #  DesignTemp, CorrosionAllowance, FlangeClass, FittingType,
            #  AllowableStressTable, BranchTable, Source, Version]
            class_name = str(row[1])
            material_standard = str(row[2])
            base_material = str(row[3]) if row[3] else material_standard
            design_pressure = float(row[4])
            design_temperature = float(row[5])
            corrosion_allowance = float(row[6])
            flange_class = str(row[7])
            fitting_type = str(row[8]) if row[8] else None
            allowable = str(row[9]) if row[9] else None
            branch = str(row[10]) if row[10] else None
            source = str(row[11]) if row[11] else "COMPANY_STD"
            version = str(row[12]) if row[12] else "1"
        else:
            # 12 列：BaseMaterial 缺省取 MaterialStandard
            class_name = str(row[1])
            material_standard = str(row[2])
            base_material = material_standard
            design_pressure = float(row[3])
            design_temperature = float(row[4])
            corrosion_allowance = float(row[5])
            flange_class = str(row[6])
            fitting_type = str(row[7]) if row[7] else None
            allowable = str(row[8]) if row[8] else None
            branch = str(row[9]) if row[9] else None
            source = str(row[10]) if row[10] else "COMPANY_STD"
            version = str(row[11]) if row[11] else "1"

        # 由 Sheet2 DNs 隐含 dn_series_json（min/max/series）
        if dns:
            dn_min, dn_max = min(dns), max(dns)
            dn_series = {"min": dn_min, "max": dn_max, "series": sorted(dns)}
        else:
            dn_series = {}

        return {
            "class_id": class_id,
            "class_name": class_name,
            "material_standard": material_standard,
            "base_material": base_material,
            "design_pressure": design_pressure,
            "design_temperature": design_temperature,
            "corrosion_allowance": corrosion_allowance,
            "dn_series_json": dn_series,
            "sch_series_json": dict(sch_map),
            "flange_class": flange_class,
            "fitting_type": fitting_type,
            "allowable_stress_json": {"table": allowable} if allowable else {},
            "branch_table_json": {"table": branch} if branch else {},
            "source": source,
            "version": version,
        }
