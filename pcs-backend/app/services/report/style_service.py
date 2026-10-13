"""c6：样式写入 —— 版本化 + 回滚 + 两档权限（用户 2026-10-13 裁决）。

## 裁决原文要点

**两档权限，按破坏面分**：

| 作用域 | 谁能改 | 破坏面 |
|---|---|---|
| `project_id=NULL`（公司标准）| 仅 `SYSTEM_ADMIN` | 波及所有项目的所有报表 |
| `project_id=X`（项目级）| 有该项目访问权即可 | 限于单项目 |

**不加审批流。** CONFIG CATEGORY_4 模板管理有审批流，是因为模板文件
渲染错会生成错误的**正式文档**（数据正确性问题）；样式是展示层，
改错只是难看。用流程冗余去防一个不存在的数据风险。

**版本 + 回滚**：每次改动**新增一行**（version+1），旧行保留。
回滚 = 把旧 version 重新置为 ACTIVE，**不删数据**。
用户原话：「审批防的是『改错』，回滚解决的是『改错之后怎么办』。
前者依赖人的判断，后者是机制。」

**初始样式不落库**：作为 `ReportStyle()` 的代码默认值。用户提供的初始样式
放进 `resolve()` 的 defaults 层，语义正好。落库会引入「代码 vs 数据」的
同步问题（升级时用代码的还是库里的？），不落库就不存在这个问题。
**第一次改样式时才落库**，且只落改动部分 —— `resolve()` 的
`exclude_unset` 正是为此存在。

## 权限在每次写入上重判

不是「创建时判一次就放行」。否则管理员建一条公司标准后，
普通用户凭 `style_id` 就能改它 —— 修「查看权限」时不重判写入权限
是最常见的 ACL 漏洞。
"""
from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportStyleRow
from app.services.report.definition_service import DEFAULT_VERSION, bump_patch

#: 刻意**只有两个状态**。没有 PENDING / APPROVED —— 裁决明说「不要审批流」。
#: `tests/services/report/test_style_service.py::test_statuses_are_exactly_...`
#: 钉住这个集合，将来有人加审批状态会先红。
STYLE_STATUSES = frozenset({"ACTIVE", "SUPERSEDED"})


class _ActorLike(Protocol):
    user_id: uuid.UUID
    username: str
    role: str

    @property
    def roles(self) -> list[str]: ...


class StylePermissionError(Exception):
    """样式写入被拒。

    `status_code` 决定回什么：
    - **403**：公司标准被非 ADMIN 改 —— 调用方**知道**这个作用域是什么，
      403 不泄漏任何东西。
    - **404**：项目级且无权访问 —— 沿用 `_guard.check_project_access_or_404`
      的既有语义（不泄漏项目存在性）。这里不重新发明一套。
    """

    def __init__(self, message: str, *, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class StyleService:
    """`report_styles` 的写入侧。

    读侧（list/get）刻意留在 `app/api/v1/report.py` —— 它是纯查询，
    没有版本与权限语义，而写侧这些语义不能散进端点里各写一遍
    （写两遍就等于没有）。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # --- 读 ------------------------------------------------------------------

    async def get(self, *, style_id: uuid.UUID) -> ReportStyleRow | None:
        return (await self.db.execute(
            select(ReportStyleRow).where(ReportStyleRow.style_id == style_id)
        )).scalar_one_or_none()

    async def active_for(self, *, report_type: str,
                         project_id: uuid.UUID | None) -> list[ReportStyleRow]:
        """该作用域下 **ACTIVE** 的样式行（公司级 + 项目级各至多一行）。

        返回**有序**列表：`[by_type, project]` —— 调用方按这个顺序喂给
        `resolve()`，顺序即优先级。这里**不能**改成按 `created_at` 排 ——
        那是「哪条新哪条就赢」，会让公司标准被项目样式以外的因素盖掉。
        """
        stmt = select(ReportStyleRow).where(
            ReportStyleRow.report_type == report_type,
            ReportStyleRow.status == "ACTIVE",
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        by_type = [r for r in rows if r.project_id is None]
        by_project = [r for r in rows if r.project_id == project_id]
        return (by_type + by_project)[:2]

    # --- 写 ------------------------------------------------------------------

    async def create(self, *, report_type: str, project_id: uuid.UUID | None,
                     patch: dict[str, Any], actor: _ActorLike) -> ReportStyleRow:
        """建一条 ACTIVE 样式（version `0.1.0`）。

        已有 ACTIVE 时不静默并存 —— 报冲突。两条 ACTIVE 的后果不是
        「多显示一条」：生成时取哪条不确定，同一份报表两次生成可能
        长得不一样，而内容哈希把 style 算进去了，于是同一份数据算出
        两个哈希，缓存语义失效。改已有样式请走 `revise()`。
        """
        await self._authorize(actor, project_id=project_id)
        if await self._current(report_type, project_id) is not None:
            raise StyleConflict(
                f"{report_type} 在该作用域已有 ACTIVE 样式，请改用修订（revise）。")

        row = ReportStyleRow(
            report_type=report_type, project_id=project_id,
            style_json=patch, version=DEFAULT_VERSION, status="ACTIVE",
            created_by=actor.user_id,
        )
        self.db.add(row)
        await self.db.flush()
        await self._audit(actor, row, event="created")
        return row

    async def revise(self, *, style_id: uuid.UUID, patch: dict[str, Any],
                     actor: _ActorLike) -> ReportStyleRow:
        """改样式 = **新增一行**（version+1），原行转 SUPERSEDED。

        不在原行上改 `style_json`：`report_files.style_version` 冻结版本号
        就是为了可复现（ADR-P8-001「样式配置的存储」），原地改等于让
        那个字段说谎 —— 事后无法回答「上周那份报表当时长什么样」。
        """
        row = await self._require(style_id)
        await self._authorize(actor, project_id=row.project_id)

        current = await self._current(row.report_type, row.project_id)

        nxt = ReportStyleRow(
            report_type=row.report_type, project_id=row.project_id,
            style_json=patch, version=bump_patch(row.version), status="ACTIVE",
            created_by=actor.user_id,
        )
        self.db.add(nxt)
        if current is not None:
            current.status = "SUPERSEDED"
        await self.db.flush()
        await self._audit(actor, nxt, event="revised", previous_version=row.version)
        return nxt

    async def activate(self, *, style_id: uuid.UUID,
                       actor: _ActorLike) -> ReportStyleRow:
        """回滚：把某一历史版本重新置为 ACTIVE。

        **不删任何行** —— 删了「上周那份报表当时用的什么样式」
        就再也答不上来。已是 ACTIVE 时幂等成功（用户在列表里连点两下
        很正常，报错会让人以为出了故障）。
        """
        row = await self._require(style_id)
        await self._authorize(actor, project_id=row.project_id)

        current = await self._current(row.report_type, row.project_id)
        if current is not None and current.style_id == row.style_id:
            return row                      # 幂等
        if current is not None:
            current.status = "SUPERSEDED"
        row.status = "ACTIVE"
        await self.db.flush()
        await self._audit(actor, row, event="activated",
                          previous_version=current.version if current else None)
        return row

    # --- 内部 ----------------------------------------------------------------

    async def _require(self, style_id: uuid.UUID) -> ReportStyleRow:
        row = await self.get(style_id=style_id)
        if row is None:
            raise StylePermissionError(f"Style not found: {style_id}",
                                       status_code=404)
        return row

    async def _current(self, report_type: str,
                       project_id: uuid.UUID | None) -> ReportStyleRow | None:
        return (await self.db.execute(
            select(ReportStyleRow).where(
                ReportStyleRow.report_type == report_type,
                ReportStyleRow.project_id.is_(project_id)
                if project_id is None else ReportStyleRow.project_id == project_id,
                ReportStyleRow.status == "ACTIVE",
            ).limit(1)
        )).scalar_one_or_none()

    async def _authorize(self, actor: _ActorLike, *,
                         project_id: uuid.UUID | None) -> None:
        """两档权限，见模块 docstring。

        ⚠️ 每次写入都调，不是创建时判一次。
        """
        roles = list(actor.roles)
        if project_id is None:
            if "SYSTEM_ADMIN" not in roles:
                raise StylePermissionError(
                    "公司标准样式仅 SYSTEM_ADMIN 可改。", status_code=403)
            return
        if "SYSTEM_ADMIN" in roles:
            return                          # 与 _guard 既有 bypass 一致
        # ⚠️ 这里**不** import `app.api.v1._guard.check_project_access_or_404`
        # —— services 不许 import api（`tests/architecture/test_imports.py` 钉着）。
        # 那个 helper 只是 `UserProjectService.check_user_project_access`
        # 加一层 HTTPException 包装；服务层要的是判断本身。
        from app.services.user_project_service import UserProjectService

        ok = await UserProjectService.check_user_project_access(
            self.db, user_id=actor.user_id, project_id=project_id)
        if not ok:
            # 404 而非 403：不向无权者泄漏项目存在性（与 _guard 同一语义）
            raise StylePermissionError(
                f"Project not found: {project_id}", status_code=404)

    async def _audit(self, actor: _ActorLike, row: ReportStyleRow, *,
                     event: str, previous_version: str | None = None) -> None:
        """**只有公司标准强制写审计**。

        项目级改动破坏面小，写不写都行 —— 全写会让审计表被日常
        改字号淹掉，真正的公司标准改动反而淹没在里面。
        """
        if row.project_id is not None:
            return
        from app.models.enums import AuditAction
        from app.services.audit_service import AuditService

        await AuditService(self.db).write(
            action=AuditAction.REPORT_STYLE_CHANGED,
            resource_type="report_style",
            resource_id=row.style_id,
            user_id=actor.user_id,
            detail={"event": event, "report_type": row.report_type,
                    "version": row.version, "scope": "COMPANY",
                    "previous_version": previous_version},
        )


async def build_style(db: AsyncSession, *, report_type: str,
                      project_id: uuid.UUID | None,
                      level: str | None = None,
                      exchanger_type: str | None = None) -> Any:
    """**四层合并的生产入口** —— 生成路径只该调这一个函数。

    层序（ADR-P8-001 用户 2026-10-08 裁决）：
    `defaults → 报表类型 → 项目 → 运行时`

    ⚠️ **明细级预设是 defaults 层，不是某一上层**。这看起来反直觉，
    实则是「DETAIL 必须横向」唯一能落地的接法：`orientation` 在
    `locked_fields` 里，`resolve()` 拒绝**任何层**改它。
    预设放上层 → 横向要求被锁字段挡掉（实测拿到 portrait）；
    预设放 defaults → 横向落地，且仍锁得住（谁也改不了）。
    见 `tests/services/report/test_style_wiring.py` 里那条测试的注释。

    返回类型用 `Any` 是为了不在此文件 import `ReportStyle` —— 那会让
    `style_service` → `style` 的依赖看起来是循环（实际上 style.py
    不 import 本模块）。真要收紧就改成 TYPE_CHECKING 导入。
    """
    from app.services.report.style import ReportStyle, heat_detail_styles, resolve

    defaults = (heat_detail_styles(level, exchanger_type)
                if level else ReportStyle())
    layers = await StyleService(db).active_for(report_type=report_type,
                                                project_id=project_id)
    by_type = next((r for r in layers if r.project_id is None), None)
    project = next((r for r in layers if r.project_id is not None), None)
    return resolve(
        defaults=defaults,
        by_type=ReportStyle.model_validate(by_type.style_json) if by_type else None,
        project=ReportStyle.model_validate(project.style_json) if project else None,
    )


class StyleConflict(Exception):
    """该作用域已有 ACTIVE 样式 —— 要改请走 `revise()`。"""
