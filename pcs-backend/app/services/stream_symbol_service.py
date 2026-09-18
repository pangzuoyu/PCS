"""StreamSymbolService — 公司级 CRUD + 项目级 fork（SUP-002 §7/§8）。

V1.4 §四、#5 修正：fork_to_project(symbol_id=None) → 复制全部公司级符号；
symbol_id 指定时只 fork 该符号。Returns list[ProjectStreamSymbol]。

SIM-37（2026-09-11）：项目级符号审批走轻量状态列 + 5 态机
（ProjectStreamSymbolStateMachine），不挂 ConfigAsset/ConfigApproval
（cerebrum Do-Not-Repeat：避免 config_assets 爆炸）。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import ConfigAsset, ConfigVersion
from app.models.enums import AuditAction, ConfigTransition
from app.models.stream_symbol import ProjectStreamSymbol, StreamSymbol
from app.services.audit_service import AuditService
from app.services.config_state_machine import ConfigStateMachine, InvalidTransitionError
from app.services.exceptions import PcsError


class ProjectStreamSymbolStateMachine:
    """项目级符号轻量 5 态机（不挂 ConfigAsset/ConfigApproval，V1.4 §五、#1）。

    与 ProjectPipeClassStateMachine 同模式：
    DRAFT → PENDING → APPROVED → PUBLISHED → OBSOLETE；
    DRAFT/APPROVED/PUBLISHED 可经 OBSOLETE 直接出局；OBSOLETE 终态。

    ConfigApproval 行不写（cerebrum Do-Not-Repeat：仅 PipeClass 写
    ConfigApproval.project_class_id；其他项目级三域只审计）。
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


class StreamSymbolService:
    # ---------- 公司级 ----------
    @classmethod
    async def list_company(
        cls, db: AsyncSession, *, status: str | None = None
    ) -> list[StreamSymbol]:
        stmt = select(StreamSymbol)
        if status:
            stmt = stmt.where(StreamSymbol.status == status)
        stmt = stmt.order_by(StreamSymbol.symbol)
        return list((await db.execute(stmt)).scalars())

    @classmethod
    async def get(cls, db: AsyncSession, symbol_id: uuid.UUID) -> StreamSymbol:
        ss = await db.get(StreamSymbol, symbol_id)
        if not ss:
            raise PcsError(
                f"符号 {symbol_id} 不存在",
                code="STREAM_SYMBOL_NOT_FOUND",
                status=404,
            )
        return ss

    @classmethod
    async def create_company(
        cls,
        db: AsyncSession,
        *,
        data: dict[str, Any],
        actor: Any,
    ) -> StreamSymbol:
        """创建公司级流股符号（unique symbol）。

        步骤：
        1. 按 symbol 唯一约束查重，命中 → STREAM_SYMBOL_DUP（409）
        2. 挂载 ConfigAsset（CATEGORY_5 / STREAM_SYMBOL，V1.4 §0.5
           SYM-OPEN-01 + INT-OPEN-01，资产化追踪）
        3. 插入 StreamSymbol 行（DRAFT 状态）
        4. 写 Audit（created_by 来自 actor.user_id）

        返回新建的 StreamSymbol（commit 由调用方负责）。
        """
        existing = (
            await db.execute(
                select(StreamSymbol).where(StreamSymbol.symbol == data["symbol"])
            )
        ).scalar_one_or_none()
        if existing:
            raise PcsError(
                f"符号 {data['symbol']} 已存在",
                code="STREAM_SYMBOL_DUP",
                status=409,
            )
        # ConfigAsset 挂载（V1.4 §0.5/SYM-OPEN-01 + INT-OPEN-01）
        asset = ConfigAsset(
            category="CATEGORY_5",
            asset_subtype="STREAM_SYMBOL",
            name=data["symbol"],
            current_version=str(data.get("version", "1")),
            status="DRAFT",
            created_by=getattr(actor, "user_id", None),
        )
        db.add(asset)
        await db.flush()
        ss = StreamSymbol(
            symbol=data["symbol"],
            name=data["name"],
            category=data.get("category"),
            asset_id=asset.asset_id,
            status="DRAFT",
            version=str(data.get("version", "1")),
            created_by=getattr(actor, "user_id", None),
        )
        db.add(ss)
        await AuditService(db).write(
            action=AuditAction.CONFIG_ASSET_CREATED,
            resource_type="CONFIG",
            resource_id=str(asset.asset_id),
            user_id=getattr(actor, "user_id", None),
            detail={"symbol": ss.symbol, "asset_subtype": "STREAM_SYMBOL"},
        )
        await db.commit()
        return ss

    @classmethod
    async def update_company(
        cls,
        db: AsyncSession,
        symbol_id: uuid.UUID,
        *,
        data: dict[str, Any],
        actor: Any,
    ) -> StreamSymbol:
        ss = await cls.get(db, symbol_id)
        for k, v in data.items():
            setattr(ss, k, v)
        await db.commit()
        return ss

    @classmethod
    async def delete_company(
        cls,
        db: AsyncSession,
        symbol_id: uuid.UUID,
        *,
        actor: Any,
    ) -> None:
        """删除公司级流股符号（cascade asset + 引用检查）。

        - 取行（不存在 → STREAM_SYMBOL_NOT_FOUND 404）
        - SYM-V06 引用检查：ProjectStreamSymbol.source_symbol_id 引用
          → STREAM_SYMBOL_IN_USE（409）
        - 级联删 ConfigAsset（若存在 asset_id；CASCADE 清理 ConfigVersion）
        - 删 StreamSymbol 行
        - 提交由本函数负责（db.commit()）
        """
        ss = await cls.get(db, symbol_id)
        # SYM-V06：被项目级 fork 引用则不可删
        ref = (
            await db.execute(
                select(ProjectStreamSymbol.project_symbol_id)
                .where(ProjectStreamSymbol.source_symbol_id == symbol_id)
                .limit(1)
            )
        ).first()
        if ref:
            raise PcsError(
                f"符号 {ss.symbol} 已被项目 fork，不可删除",
                code="STREAM_SYMBOL_IN_USE",
                status=409,
            )
        if ss.asset_id:
            asset = await db.get(ConfigAsset, ss.asset_id)
            if asset:
                await db.delete(asset)
        await db.delete(ss)
        await db.commit()

    @classmethod
    async def submit(cls, db: AsyncSession, symbol_id: uuid.UUID, *, actor: Any) -> StreamSymbol:
        return await cls._transition(db, symbol_id, ConfigTransition.SUBMIT, actor)

    @classmethod
    async def approve(cls, db: AsyncSession, symbol_id: uuid.UUID, *, actor: Any) -> StreamSymbol:
        return await cls._transition(db, symbol_id, ConfigTransition.APPROVE, actor)

    @classmethod
    async def publish(cls, db: AsyncSession, symbol_id: uuid.UUID, *, actor: Any) -> StreamSymbol:
        return await cls._transition(db, symbol_id, ConfigTransition.PUBLISH, actor)

    @classmethod
    async def obsolete(cls, db: AsyncSession, symbol_id: uuid.UUID, *, actor: Any) -> StreamSymbol:
        return await cls._transition(db, symbol_id, ConfigTransition.OBSOLETE, actor)

    @classmethod
    async def _transition(
        cls,
        db: AsyncSession,
        symbol_id: uuid.UUID,
        action: ConfigTransition,
        actor: Any,
    ) -> StreamSymbol:
        ss = await cls.get(db, symbol_id)
        if not ss.asset_id:
            raise PcsError(
                f"符号 {ss.symbol} 未挂 ConfigAsset",
                code="STREAM_SYMBOL_NO_ASSET",
                status=409,
            )
        asset = await db.get(ConfigAsset, ss.asset_id)
        version = (
            await db.execute(
                select(ConfigVersion)
                .where(ConfigVersion.asset_id == asset.asset_id)
                .order_by(ConfigVersion.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if version is None:
            # 没有 version 行 → 现造一个 stub（PC-3 模式）
            version = ConfigVersion(
                asset_id=asset.asset_id,
                version_code=ss.version,
                content_json={"symbol": ss.symbol, "name": ss.name},
                status="DRAFT",
            )
            db.add(version)
            await db.flush()
        sm = ConfigStateMachine(db)
        try:
            await sm.transition(asset, version, action=action, actor=actor)
        except InvalidTransitionError as e:
            raise PcsError(
                str(e), code="STREAM_SYMBOL_BAD_TRANSITION", status=409
            ) from e
        ss.status = asset.status
        await db.commit()
        return ss

    # ---------- 项目级 ----------
    @classmethod
    async def fork_to_project(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        symbol_id: uuid.UUID | None = None,
        actor: Any,
    ) -> list[ProjectStreamSymbol]:
        """V1.4 §四、#5：symbol_id=None 时复制全部公司级符号表；指定时只 fork 单个。"""
        if symbol_id is None:
            company = await cls.list_company(db, status="PUBLISHED")
        else:
            company = [await cls.get(db, symbol_id)]
        results: list[ProjectStreamSymbol] = []
        for ss in company:
            existing = (
                await db.execute(
                    select(ProjectStreamSymbol).where(
                        ProjectStreamSymbol.project_id == project_id,
                        ProjectStreamSymbol.source_symbol_id == ss.symbol_id,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                results.append(existing)
                continue
            pss = ProjectStreamSymbol(
                project_id=project_id,
                source_symbol_id=ss.symbol_id,
                symbol=ss.symbol,
                name=ss.name,
                category=ss.category,
                is_active=ss.is_active,
                snapshot_json={
                    "symbol": ss.symbol,
                    "name": ss.name,
                    "category": ss.category,
                    "version": ss.version,
                },
                override_json={},
                status="DRAFT",
                created_by=getattr(actor, "user_id", None),
            )
            db.add(pss)
            results.append(pss)
        await db.commit()
        return results

    @classmethod
    async def add_project_symbol(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        symbol: str,
        name: str,
        category: str | None,
        actor: Any,
    ) -> ProjectStreamSymbol:
        """在项目作用域新增流股符号（unique by project_id + symbol）。

        - 查重：按 (project_id, symbol) 复合唯一约束，命中 → PROJECT_STREAM_SYMBOL_DUP（409）
        - 新增：ProjectStreamSymbol 行（DRAFT，source_symbol_id=None 表示项目自创）
        - override_json 默认 {}（项目级覆盖由后续 update_project_symbol 写入）
        - 写入由本函数负责（db.commit()）

        与 `create_company` 区别：本函数不挂 ConfigAsset（项目级符号非 CATEGORY_5）。
        """
        existing = (
            await db.execute(
                select(ProjectStreamSymbol).where(
                    ProjectStreamSymbol.project_id == project_id,
                    ProjectStreamSymbol.symbol == symbol,
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise PcsError(
                f"项目内已存在符号 {symbol}",
                code="PROJECT_STREAM_SYMBOL_DUP",
                status=409,
            )
        pss = ProjectStreamSymbol(
            project_id=project_id,
            source_symbol_id=None,
            symbol=symbol,
            name=name,
            category=category,
            snapshot_json=None,
            override_json={},
            status="DRAFT",
            created_by=getattr(actor, "user_id", None),
        )
        db.add(pss)
        await db.commit()
        return pss

    @classmethod
    async def update_project_symbol(
        cls,
        db: AsyncSession,
        *,
        project_symbol_id: uuid.UUID,
        data: dict[str, Any],
        actor: Any,
    ) -> ProjectStreamSymbol:
        """更新项目内流股符号（局部字段覆盖 + override_json 合并）。

        - 查行（不存在 → PROJECT_STREAM_SYMBOL_NOT_FOUND 404）
        - override_json 合并：现有 + data["override"]（增量更新，不全替换）
        - 可选字段更新：name / category / is_active（按 in 检查，存在才覆盖）
        - 提交由本函数负责（db.commit()）

        actor 参数当前未使用（保留签名兼容后续审计接入）。
        """
        pss = await db.get(ProjectStreamSymbol, project_symbol_id)
        if pss is None:
            raise PcsError(
                f"项目符号 {project_symbol_id} 不存在",
                code="PROJECT_STREAM_SYMBOL_NOT_FOUND",
                status=404,
            )
        # override_json 合并
        override = dict(pss.override_json or {})
        override.update(data.get("override", {}))
        pss.override_json = override
        if "name" in data:
            pss.name = data["name"]
        if "category" in data:
            pss.category = data["category"]
        if "is_active" in data:
            pss.is_active = data["is_active"]
        await db.commit()
        return pss

    @classmethod
    async def delete_project_symbol(
        cls,
        db: AsyncSession,
        *,
        project_symbol_id: uuid.UUID,
        actor: Any,
    ) -> None:
        """删除项目作用域的流股符号（硬删除，无引用检查）。

        步骤：
        1. 查行（不存在 → PROJECT_STREAM_SYMBOL_NOT_FOUND 404）
        2. 直接 ORM delete（无引用检查、无审计、无快照；项目内符号为
           派生数据，前端编辑可自由重做）
        3. 提交由本函数负责（db.commit()）

        与 `delete_company` 区别：
        - delete_company 检查 ProjectStreamSymbol.source_symbol_id 引用
          （SYM-V06）→ STREAM_SYMBOL_IN_USE 拒绝
        - delete_project_symbol 不检查（项目内派生数据可任意重建）

        actor 参数当前未使用（保留签名兼容后续审计接入）。
        """
        pss = await db.get(ProjectStreamSymbol, project_symbol_id)
        if pss is None:
            raise PcsError(
                f"项目符号 {project_symbol_id} 不存在",
                code="PROJECT_STREAM_SYMBOL_NOT_FOUND",
                status=404,
            )
        await db.delete(pss)
        await db.commit()

    @classmethod
    async def list_project(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        include_company: bool = True,
    ) -> list[dict]:
        """列出项目作用域的流股符号（可选择叠加公司级 PUBLISHED）。

        合并规则：
        1. 先列项目内 ProjectStreamSymbol 行（override_json 优先，缺字段回退到表字段）
           - status 取行 status，is_active 取行 is_active
        2. include_company=True 时再列公司级 PUBLISHED 符号，去重后追加
           - status 标记为 INHERITED（语义：继承自公司级，未在项目内覆写）

        返回 dict 列表（前端无需关心项目/公司来源区分）。
        """
        out: list[dict] = []
        rows = (
            await db.execute(
                select(ProjectStreamSymbol).where(
                    ProjectStreamSymbol.project_id == project_id
                )
            )
        ).scalars()
        for pss in rows:
            sym: dict[str, Any] = dict(pss.override_json or {}) if pss.override_json else {}
            sym.setdefault("symbol", pss.symbol)
            sym.setdefault("name", pss.name)
            sym["status"] = pss.status
            sym["is_active"] = pss.is_active
            out.append(sym)
        if include_company:
            company = await cls.list_company(db, status="PUBLISHED")
            existing = {r["symbol"] for r in out}
            for ss in company:
                if ss.symbol not in existing:
                    out.append(
                        {
                            "symbol": ss.symbol,
                            "name": ss.name,
                            "category": ss.category,
                            "status": "INHERITED",
                            "is_active": ss.is_active,
                        }
                    )
        return out

    # ====================================================================
    # SIM-37 项目级符号 5 态审批（轻量状态列 + 审计；不写 ConfigApproval）
    # ====================================================================

    @classmethod
    async def submit_project_symbol(
        cls, db: AsyncSession, *, project_symbol_id: uuid.UUID, actor: Any,
    ) -> ProjectStreamSymbol:
        """DRAFT → PENDING。"""
        return await cls._project_transition(
            db, project_symbol_id, "submit", actor,
        )

    @classmethod
    async def approve_project_symbol(
        cls, db: AsyncSession, *, project_symbol_id: uuid.UUID, actor: Any,
        role: str = "REVIEWER",
    ) -> ProjectStreamSymbol:
        """PENDING → APPROVED。"""
        return await cls._project_transition(
            db, project_symbol_id, "approve", actor,
            role=role, record_approval=True,
        )

    @classmethod
    async def reject_project_symbol(
        cls, db: AsyncSession, *, project_symbol_id: uuid.UUID, actor: Any,
        role: str = "REVIEWER",
    ) -> ProjectStreamSymbol:
        """PENDING → DRAFT。"""
        return await cls._project_transition(
            db, project_symbol_id, "reject", actor,
            role=role, record_approval=True,
        )

    @classmethod
    async def publish_project_symbol(
        cls, db: AsyncSession, *, project_symbol_id: uuid.UUID, actor: Any,
    ) -> ProjectStreamSymbol:
        """APPROVED → PUBLISHED。"""
        return await cls._project_transition(
            db, project_symbol_id, "publish", actor,
        )

    @classmethod
    async def obsolete_project_symbol(
        cls, db: AsyncSession, *, project_symbol_id: uuid.UUID, actor: Any,
    ) -> ProjectStreamSymbol:
        """→ OBSOLETE（DRAFT/APPROVED/PUBLISHED 都可）。"""
        return await cls._project_transition(
            db, project_symbol_id, "obsolete", actor,
        )

    @classmethod
    async def _project_transition(
        cls,
        db: AsyncSession,
        project_symbol_id: uuid.UUID,
        action: str,
        actor: Any,
        *,
        role: str | None = None,
        record_approval: bool = False,  # noqa: ARG003 — 预留；不写 ConfigApproval
    ) -> ProjectStreamSymbol:
        """项目级符号状态转移公共实现（SIM-37 轻量 5 态机）。

        仅审计落库（cerebrum 政策：ProjectStreamSymbol 不写 ConfigApproval，
        避免 config_approvals 表膨胀；PipeClass 项目级特殊保留 ConfigApproval
        是 V1.4 §五、#1 历史决议）。
        """
        pss = await db.get(ProjectStreamSymbol, project_symbol_id)
        if pss is None:
            raise PcsError(
                f"项目符号 {project_symbol_id} 不存在",
                code="PROJECT_STREAM_SYMBOL_NOT_FOUND",
                status=404,
            )
        if not ProjectStreamSymbolStateMachine.can_transition(pss.status, action):
            raise PcsError(
                f"项目符号 {pss.symbol} 状态 {pss.status} 不允许 {action}",
                code="PROJECT_STREAM_SYMBOL_BAD_TRANSITION",
                status=409,
            )
        new_status = ProjectStreamSymbolStateMachine.next_status(action)
        old_status = pss.status
        pss.status = new_status
        audit_action_map = {
            "submit": AuditAction.CONFIG_ASSET_SUBMITTED,
            "approve": AuditAction.CONFIG_ASSET_APPROVED,
            "reject": AuditAction.CONFIG_ASSET_REJECTED,
            "publish": AuditAction.CONFIG_ASSET_PUBLISHED,
            "obsolete": AuditAction.CONFIG_ASSET_OBSOLETED,
        }
        await AuditService(db).write(
            action=audit_action_map[action],
            resource_type="PROJECT_STREAM_SYMBOL",
            resource_id=str(pss.project_symbol_id),
            user_id=getattr(actor, "user_id", None),
            detail={
                "from": old_status,
                "to": new_status,
                "action": action,
                "project_id": str(pss.project_id),
            },
        )
        await db.commit()
        return pss