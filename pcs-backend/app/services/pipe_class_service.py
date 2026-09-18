"""PipeClassService — 管道等级 CRUD + 项目分配（Task 1.9.1 / P2-STD-001）。

规则（spec §3.2.5 验收）：已用等级不可删除（仅可作废）。
在用判定：project_pipe_classes 存在关联行 或 piping_results.material_class 引用。

SUP-002 PC-3（V1.4 §0.5/§2.1/§3.1）：增加 5 态 transition 流（submit/approve/publish/
obsolete），状态机驱动 ConfigAsset.status；pipe_classes.status 为 ConfigAsset.status
的镜像。CRUD 与 Excel 导入仍走旧 3 态契约（向后兼容 1.9 客户 + xfail 测试）。

SUP-002 PC-4（V1.4 §2.4）：项目级 fork + 快照绑定 + 有效值解析 + 5 态轻量状态机；
项目级 ProjectPipeClass 不挂 ConfigAsset（CATEGORY_5 公司级专属），仅以 5 态轻量
status 列走 ProjectPipeClassStateMachine；approve/reject 写 config_approvals.
project_class_id（PC-1 列）。fork_to_project / get_effective / submit/approve/
reject/publish/obsolete 是 PC-4 唯一入口；1.9 兼容层 assign_to_project 已删
（bug-051 收口，2026-09-08 P2 close）。
"""
from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PipingResult
from app.models.config_domain import (
    ConfigApproval,
    ConfigAsset,
    ConfigVersion,
    PipeClass,
    ProjectPipeClass,
)
from app.models.enums import AuditAction, ConfigTransition
from app.schemas.pipe_class import PipeClassCreate, PipeClassUpdate
from app.services.audit_service import AuditService
from app.services.config_state_machine import (
    ConfigStateMachine,
    InvalidTransitionError,
)
from app.services.exceptions import PcsError


class _ActorLike(Protocol):
    """最小 actor 协议 — ConfigStateMachine.record_approval 需要 .user_id/role."""

    user_id: Any
    role: str | None

_STATUS_OK = {"DRAFT", "ACTIVE", "OBSOLETE"}

IMPORT_HEADERS = [
    "class_id", "class_name", "material_standard", "corrosion_allowance",
    "design_pressure", "design_temperature", "dn_min", "dn_max",
    "sch_series(JSON)", "flange_class", "source", "version",
]


# ---------------------------------------------------------------------------
# SUP-002 PC-4 helper + 5 态状态机（项目级轻量；V1.4 §2.4/§五、#1）
# ---------------------------------------------------------------------------


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并：字典逐键合并，列表整体替换，标量直接覆写。"""
    result = dict(base)
    for key, val in (override or {}).items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(val, dict)
        ):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _build_snapshot(company_pc: PipeClass) -> dict:
    """从公司级 PipeClass 构造完整 snapshot_json（13 字段）。"""
    return {
        "class_name": company_pc.class_name,
        "material_standard": company_pc.material_standard,
        "base_material": company_pc.base_material,
        "corrosion_allowance": company_pc.corrosion_allowance,
        "design_pressure": company_pc.design_pressure,
        "design_temperature": company_pc.design_temperature,
        "dn_series_json": company_pc.dn_series_json,
        "sch_series_json": company_pc.sch_series_json,
        "flange_class": company_pc.flange_class,
        "fitting_type": company_pc.fitting_type,
        "allowable_stress_json": company_pc.allowable_stress_json,
        "branch_table_json": company_pc.branch_table_json,
        "version": company_pc.version,
    }


class ProjectPipeClassStateMachine:
    """项目级管道等级轻量状态机（不挂 ConfigAsset，V1.4 §五、#1 裁决）。

    5 态：DRAFT → PENDING → APPROVED → PUBLISHED → OBSOLETE；
    DRAFT/APPROVED 可 OBSOLETE 直接出局；PUBLISHED → OBSOLETE；OBSOLETE 终态。
    审批记录写入 config_approvals.project_class_id（PC-1 已加可空列）。
    """

    TRANSITIONS: dict[str, set[str]] = {
        "DRAFT": {"submit", "obsolete"},
        "PENDING": {"approve", "reject"},
        "APPROVED": {"publish", "obsolete"},
        "PUBLISHED": {"obsolete"},
        "OBSOLETE": set(),
    }
    ACTION_TO_STATUS: dict[str, str] = {
        "submit": "PENDING",
        "approve": "APPROVED",
        "reject": "DRAFT",
        "publish": "PUBLISHED",
        "obsolete": "OBSOLETE",
    }

    @classmethod
    def can_transition(cls, current_status: str, action: str) -> bool:
        return action in cls.TRANSITIONS.get(current_status, set())

    @classmethod
    def next_status(cls, action: str) -> str:
        return cls.ACTION_TO_STATUS[action]


class PipeClassService:
    @classmethod
    async def list_company(
        cls, session: AsyncSession, *, status: str | None = None, keyword: str | None = None
    ) -> list[PipeClass]:
        """列出公司管号等级（COMPANY_STD 来源，可选 status/keyword 过滤）。

        步骤：
        1. 固定过滤 source == 'COMPANY_STD'（项目派生 fork 不入此列表）
        2. 可选 status：按 status_pipclass 过滤（DRAFT/APPROVED/PUBLISHED/OBSOLETE）
        3. 可选 keyword：class_name ILIKE 模糊
        4. 排序：class_id 升序（前端下拉稳定）

        对应 list_project：项目内派生（source='PROJECT_DERIVED'）走 list_project。
        """
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
        """更新管号等级（状态流转校验 + 字段覆盖）。

        步骤：
        1. 取行（不存在 → PIPE_CLASS_NOT_FOUND 404，由 get() 抛）
        2. 状态流转校验：
           - DRAFT → ACTIVE：允许
           - 同状态写回：允许（幂等）
           - 任何状态 → OBSOLETE：单向允许（DRAFT/ACTIVE → OBSOLETE）
           - 其他组合（ACTIVE → DRAFT、PENDING → ACTIVE 等）→
             PIPE_CLASS_BAD_TRANSITION（409）
        3. 字段覆盖：payload.model_dump(exclude={"status"})
           → 逐字段 setattr 写入（code/description/spec/corrosive_allowance 等）
        4. 提交由本函数负责（session.commit()）

        注意：status 字段从 payload 中排除单独处理，避免 setattr 覆盖
        上面计算好的 new_status。
        """
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
        """删除管号等级（强引用检查，仅可作废不可删的场景显式拒绝）。

        步骤：
        1. 取行（不存在 → PIPE_CLASS_NOT_FOUND 404）
        2. SUP-002 PC-1 引用检查：
           - ProjectPipeClass.source_class_id 引用
           - PipingResult.material_class 引用
           任一命中 → PIPE_CLASS_IN_USE（409，提示走作废而非删除）
        3. 删 PipeClass 行（直接 __table__.delete，绕 ORM 避免级联）
        4. 提交由本函数负责（session.commit()）

        注意：被引用时仅可走 status=OBSOLETE 作废流（preserve 引用完整性）。
        """
        await cls.get(session, class_id)
        # SUP-002 PC-1：ProjectPipeClass 不再存 class_id FK，改存 source_class_id。
        assigned = (await session.execute(
            select(ProjectPipeClass.project_class_id).where(
                ProjectPipeClass.source_class_id == class_id,
            )
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
    async def list_project(
        cls, session: AsyncSession, project_id: uuid.UUID
    ) -> list[ProjectPipeClass]:
        """列出项目内派生管号等级（按 class_name 排序）。

        - 按 project_id 过滤，返回 ProjectPipeClass（PROJECT_DERIVED 来源）
        - 排序：class_name 升序（前端下拉稳定）
        - 不分页（项目内 fork 数量级小，O(10)）
        - 对应 list_company：公司级（COMPANY_STD）走 list_company
        """
        stmt = (
            select(ProjectPipeClass)
            .where(ProjectPipeClass.project_id == project_id)
            .order_by(ProjectPipeClass.class_name)
        )
        return list((await session.execute(stmt)).scalars())

    # ------------------------------------------------------------------
    # Excel 批量导入（Task 1.9.6 / P2-STD-001）
    # ------------------------------------------------------------------

    @classmethod
    def build_import_template(cls) -> bytes:
        """构建管号等级 Excel 导入模板（xlsx bytes）。

        步骤：
        1. 新建 openpyxl Workbook，第一张工作表 ws 重命名 'pipe_classes'
        2. 写入表头（IMPORT_HEADERS，含 class_id/cn_name/en_name/dn/inch/pip_class_id/...）
        3. BytesIO 缓冲 → wb.save 序列化为 xlsx 字节流
        4. 返回 bytes（前端用于 <a download> 下载）

        与 build_export_template 区别：本函数只写表头，无数据行；供用户
        手动填表导入。导出模板（export）通常按已存数据填行。
        """
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
        """从 Excel 批量导入管号等级（每行 = 一条 PipeClassCreate）。

        步骤：
        1. 读 Excel：优先 sheet "pipe_classes"，否则回退 active sheet
        2. 表头校验：必须匹配 IMPORT_HEADERS（否则 IMPORT_BAD_HEADER 422）
        3. 逐行解析为 PipeClassCreate，调 cls.create 落库
        4. 错误聚合：
           - PIPE_CLASS_DUP → 计入 skipped（不视为错误）
           - 其他 PcsError → 计入 errors（行号 + message）
           - ValueError/TypeError/IndexError/JSONDecodeError → 计入 errors

        返回 {imported, skipped, errors} 字典供前端展示。
        """
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

    # ------------------------------------------------------------------
    # SUP-002 PC-3：5 态 transition 流（公司级）
    # 状态机驱动 ConfigAsset（CATEGORY_5，asset_subtype=PIPE_CLASS）；pipe_classes.status
    # 是 ConfigAsset.status 的镜像列（cerebrum Do-Not-Repeat：双写必须同事务）。
    # ------------------------------------------------------------------

    @classmethod
    async def create_with_config_asset(
        cls,
        session: AsyncSession,
        *,
        payload: PipeClassCreate,
        actor: _ActorLike,
    ) -> PipeClass:
        """创建 PipeClass + ConfigAsset + ConfigVersion v1（同事务）。

        PC-3 唯一入口（替换 1.9 的 ``create``）：

        - PipeClass DRAFT（5 态起点）
        - ConfigAsset CATEGORY_5 + asset_subtype=PIPE_CLASS（DRAFT）
        - ConfigVersion v1（DRAFT，content_json 镜像 PipeClass 字段）
        - pipe_classes.asset_id 反向指 ConfigAsset
        - audit：CONFIG_ASSET_CREATED

        Excel 导入继续走 ``create``（3 态契约，1.9 兼容）。
        """
        if await session.get(PipeClass, payload.class_id):
            raise PcsError(
                f"管道等级 {payload.class_id} 已存在",
                code="PIPE_CLASS_DUP", status=409,
            )
        pc = PipeClass(**payload.model_dump(), status="DRAFT")
        session.add(pc)
        await session.flush()

        version_code = pc.version or "v1"
        asset = ConfigAsset(
            category="CATEGORY_5",
            asset_subtype="PIPE_CLASS",
            name=payload.class_name,
            current_version=version_code,
            status="DRAFT",
            content_json={
                "class_id": pc.class_id,
                "class_name": pc.class_name,
                "material_standard": pc.material_standard,
                "design_pressure": pc.design_pressure,
                "design_temperature": pc.design_temperature,
                "dn_series_json": pc.dn_series_json,
                "sch_series_json": pc.sch_series_json,
                "flange_class": pc.flange_class,
            },
        )
        session.add(asset)
        await session.flush()

        version = ConfigVersion(
            asset_id=asset.asset_id,
            version_code=version_code,
            content_json=asset.content_json,
            status="DRAFT",
        )
        session.add(version)
        await session.flush()

        pc.asset_id = asset.asset_id
        await session.flush()

        await AuditService(session).write(
            action=AuditAction.CONFIG_ASSET_CREATED,
            resource_type="CONFIG",
            resource_id=str(asset.asset_id),
            user_id=getattr(actor, "user_id", None),
            detail={
                "class_id": pc.class_id,
                "asset_subtype": "PIPE_CLASS",
                "version_code": version_code,
            },
        )
        await session.commit()
        return pc

    @classmethod
    async def _resolve_asset_and_version(
        cls, session: AsyncSession, pc: PipeClass
    ) -> tuple[ConfigAsset, ConfigVersion]:
        """取 pc.asset_id 对应 ConfigAsset 与最新 ConfigVersion（按 created_at desc）。"""
        if not pc.asset_id:
            raise PcsError(
                f"等级 {pc.class_id} 未挂 ConfigAsset（PC-3 漏建）",
                code="PIPE_CLASS_NO_ASSET", status=409,
            )
        asset = await session.get(ConfigAsset, pc.asset_id)
        if asset is None:
            raise PcsError(
                f"ConfigAsset {pc.asset_id} 不存在",
                code="PIPE_CLASS_NO_ASSET", status=409,
            )
        version = (
            await session.execute(
                select(ConfigVersion)
                .where(ConfigVersion.asset_id == asset.asset_id)
                .order_by(ConfigVersion.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if version is None:
            raise PcsError(
                f"ConfigAsset {asset.asset_id} 缺 ConfigVersion（PC-3 漏建）",
                code="PIPE_CLASS_NO_VERSION", status=409,
            )
        return asset, version

    @classmethod
    async def _mirror_status(
        cls,
        session: AsyncSession,
        pc: PipeClass,
        asset: ConfigAsset,
    ) -> None:
        """pipe_classes.status = asset.status（同步 commit）。"""
        pc.status = asset.status
        await session.commit()

    @classmethod
    async def submit(
        cls, session: AsyncSession, class_id: str, *, actor: _ActorLike
    ) -> PipeClass:
        """DRAFT → PENDING。ConfigStateMachine.transition 转移 + 镜像同步。"""
        pc = await cls.get(session, class_id)
        asset, version = await cls._resolve_asset_and_version(session, pc)
        sm = ConfigStateMachine(session)
        try:
            await sm.transition(
                asset, version, action=ConfigTransition.SUBMIT, actor=actor,
            )
        except InvalidTransitionError as e:
            raise PcsError(str(e), code="PIPE_CLASS_BAD_TRANSITION", status=409) from e
        await cls._mirror_status(session, pc, asset)
        return pc

    @classmethod
    async def approve(
        cls,
        session: AsyncSession,
        class_id: str,
        *,
        actor: _ActorLike,
        role: str | None = None,
    ) -> PipeClass:
        """PENDING → APPROVED。CATEGORY_5 单层签：reviewer 一次性 APPROVED。"""
        pc = await cls.get(session, class_id)
        asset, version = await cls._resolve_asset_and_version(session, pc)
        sm = ConfigStateMachine(session)
        approver_role = role or getattr(actor, "role", None) or "REVIEWER"
        try:
            await sm.record_approval(
                asset,
                version,
                approver_id=getattr(actor, "user_id", None),
                role=approver_role,
                decision="APPROVED",
                actor=actor,
            )
        except Exception as e:  # noqa: BLE001
            raise PcsError(str(e), code="PIPE_CLASS_BAD_TRANSITION", status=409) from e
        await cls._mirror_status(session, pc, asset)
        return pc

    @classmethod
    async def publish(
        cls, session: AsyncSession, class_id: str, *, actor: _ActorLike
    ) -> PipeClass:
        """APPROVED → PUBLISHED。"""
        pc = await cls.get(session, class_id)
        asset, version = await cls._resolve_asset_and_version(session, pc)
        sm = ConfigStateMachine(session)
        try:
            await sm.transition(
                asset, version, action=ConfigTransition.PUBLISH, actor=actor,
            )
        except InvalidTransitionError as e:
            raise PcsError(str(e), code="PIPE_CLASS_BAD_TRANSITION", status=409) from e
        await cls._mirror_status(session, pc, asset)
        return pc

    @classmethod
    async def obsolete(
        cls, session: AsyncSession, class_id: str, *, actor: _ActorLike
    ) -> PipeClass:
        """→ OBSOLETE（DRAFT / APPROVED / PUBLISHED 都可经 OBSOLETE 直接出局）。"""
        pc = await cls.get(session, class_id)
        asset, version = await cls._resolve_asset_and_version(session, pc)
        sm = ConfigStateMachine(session)
        try:
            await sm.transition(
                asset, version, action=ConfigTransition.OBSOLETE, actor=actor,
            )
        except InvalidTransitionError as e:
            raise PcsError(str(e), code="PIPE_CLASS_BAD_TRANSITION", status=409) from e
        await cls._mirror_status(session, pc, asset)
        return pc

    # ------------------------------------------------------------------
    # SUP-002 PC-4：项目级 fork + 快照 + 有效值解析 + 5 态轻量状态机
    # ProjectPipeClass 不挂 ConfigAsset（CATEGORY_5 公司级专属），仅 5 态 status
    # 列；审批记录写 config_approvals.project_class_id。
    # ------------------------------------------------------------------

    @classmethod
    async def fork_to_project(
        cls, session: AsyncSession, *,
        project_id: uuid.UUID, class_id: str, actor,
    ) -> ProjectPipeClass:
        """从公司级等级 fork 到项目级。已存在则返回现有行（idempotent）。"""
        company_pc = await session.get(PipeClass, class_id)
        if company_pc is None:
            raise PcsError(
                f"公司级等级 {class_id} 不存在",
                code="PIPE_CLASS_NOT_FOUND", status=404,
            )
        existing = (await session.execute(
            select(ProjectPipeClass).where(
                ProjectPipeClass.project_id == project_id,
                ProjectPipeClass.source_class_id == class_id,
            )
        )).scalar_one_or_none()
        if existing:
            return existing
        ppc = ProjectPipeClass(
            project_id=project_id,
            source_class_id=class_id,
            class_name=company_pc.class_name,
            override_json={},
            snapshot_json=_build_snapshot(company_pc),
            status="DRAFT",
        )
        session.add(ppc)
        await session.commit()
        return ppc

    @classmethod
    async def create_project_class(
        cls, session: AsyncSession, *,
        project_id: uuid.UUID, class_name: str, data: dict, actor,
    ) -> ProjectPipeClass:
        """项目全新创建等级（source_class_id=NULL, snapshot_json=NULL,
        override_json 含全部字段）。"""
        existing = (await session.execute(
            select(ProjectPipeClass).where(
                ProjectPipeClass.project_id == project_id,
                ProjectPipeClass.class_name == class_name,
            )
        )).scalar_one_or_none()
        if existing:
            raise PcsError(
                f"项目内已存在同名等级 {class_name}",
                code="PROJECT_PIPE_CLASS_DUP", status=409,
            )
        ppc = ProjectPipeClass(
            project_id=project_id,
            source_class_id=None,
            class_name=class_name,
            override_json=data,
            snapshot_json=None,
            status="DRAFT",
        )
        session.add(ppc)
        await session.commit()
        return ppc

    @classmethod
    async def update_project_override(
        cls, session: AsyncSession, *,
        project_class_id: uuid.UUID, override: dict, actor,
    ) -> ProjectPipeClass:
        """修改 override_json（仅 DRAFT/PENDING 状态可改，APPROVED/PUBLISHED/OBSOLETE 不可改）。"""
        ppc = await session.get(ProjectPipeClass, project_class_id)
        if ppc is None:
            raise PcsError(
                "项目级等级不存在",
                code="PROJECT_PIPE_CLASS_NOT_FOUND", status=404,
            )
        if ppc.status not in ("DRAFT", "PENDING"):
            raise PcsError(
                f"状态 {ppc.status} 下不可修改 override_json（仅 DRAFT/PENDING 可改）",
                code="PROJECT_PIPE_CLASS_IMMUTABLE", status=409,
            )
        ppc.override_json = override
        await session.commit()
        return ppc

    @classmethod
    async def get_effective(
        cls, session: AsyncSession, *,
        project_id: uuid.UUID, class_name: str,
    ) -> dict:
        """返回项目级有效值（snapshot_json ⊕ override_json 递归深合并）。

        全项目全新创建（source_class_id=NULL）时返回 override_json 本身。
        """
        ppc = (await session.execute(
            select(ProjectPipeClass).where(
                ProjectPipeClass.project_id == project_id,
                ProjectPipeClass.class_name == class_name,
            )
        )).scalar_one_or_none()
        if ppc is None:
            raise PcsError(
                f"项目级等级 {class_name} 不存在",
                code="PROJECT_PIPE_CLASS_NOT_FOUND", status=404,
            )
        if ppc.snapshot_json is None:
            return dict(ppc.override_json or {})
        return _deep_merge(ppc.snapshot_json, ppc.override_json)

    @classmethod
    async def submit_project_class(
        cls, session: AsyncSession, *, project_class_id: uuid.UUID, actor,
    ) -> ProjectPipeClass:
        return await cls._project_transition(
            session, project_class_id, "submit", actor,
        )

    @classmethod
    async def approve_project_class(
        cls, session: AsyncSession, *, project_class_id: uuid.UUID, actor, role: str = "REVIEWER",
    ) -> ProjectPipeClass:
        return await cls._project_transition(
            session, project_class_id, "approve", actor,
            role=role, record_approval=True,
        )

    @classmethod
    async def reject_project_class(
        cls, session: AsyncSession, *, project_class_id: uuid.UUID, actor, role: str = "REVIEWER",
    ) -> ProjectPipeClass:
        return await cls._project_transition(
            session, project_class_id, "reject", actor,
            role=role, record_approval=True,
        )

    @classmethod
    async def publish_project_class(
        cls, session: AsyncSession, *, project_class_id: uuid.UUID, actor,
    ) -> ProjectPipeClass:
        return await cls._project_transition(
            session, project_class_id, "publish", actor,
        )

    @classmethod
    async def obsolete_project_class(
        cls, session: AsyncSession, *, project_class_id: uuid.UUID, actor,
    ) -> ProjectPipeClass:
        return await cls._project_transition(
            session, project_class_id, "obsolete", actor,
        )

    @classmethod
    async def _project_transition(
        cls, session: AsyncSession, project_class_id: uuid.UUID, action: str, actor,
        *, role: str | None = None, record_approval: bool = False,
    ) -> ProjectPipeClass:
        ppc = await session.get(ProjectPipeClass, project_class_id)
        if ppc is None:
            raise PcsError(
                "项目级等级不存在",
                code="PROJECT_PIPE_CLASS_NOT_FOUND", status=404,
            )
        if not ProjectPipeClassStateMachine.can_transition(ppc.status, action):
            raise PcsError(
                f"{ppc.status} → {action} 不允许",
                code="PROJECT_PIPE_CLASS_BAD_TRANSITION", status=409,
            )
        new_status = ProjectPipeClassStateMachine.next_status(action)
        if record_approval:
            approval = ConfigApproval(
                version_id=None,
                project_class_id=ppc.project_class_id,
                approver_id=getattr(actor, "user_id", None),
                approver_role=role or "REVIEWER",
                decision="REJECTED" if action == "reject" else "APPROVED",
            )
            session.add(approval)
        ppc.status = new_status
        audit_action = {
            "obsolete": AuditAction.CONFIG_ASSET_OBSOLETED,
            "approve": AuditAction.CONFIG_ASSET_APPROVED,
            "reject": AuditAction.CONFIG_ASSET_REJECTED,
            "submit": AuditAction.CONFIG_ASSET_SUBMITTED,
            "publish": AuditAction.CONFIG_ASSET_PUBLISHED,
        }[action]
        await AuditService(session).write(
            action=audit_action,
            resource_type="PROJECT_PIPE_CLASS",
            resource_id=str(ppc.project_class_id),
            user_id=getattr(actor, "user_id", None),
            detail={"from": ppc.status, "to": new_status, "action": action},
        )
        await session.commit()
        return ppc
