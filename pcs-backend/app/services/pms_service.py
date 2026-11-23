"""PMS 管道材料规格的数据访问（P10-H · T2 · TODO-195）。

⚠️ **签署**：本模块**不碰** `sign_status` —— 那是**通用记录工作流**的
（`/records/{module}/{record_id}/submit-approval` 等）⇒ ⇒ 本模块只负责
「建 / 改 / 列」，状态迁移一律走工作流 ⇒ ⇒ **不会**出现两处真相源。
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RecordSignStatus9
from app.models.pms import PmsItem
from app.models.project import Project
from app.schemas.pms import PmsItemCreate, PmsItemUpdate
from app.services.calc_lineage import compute_record_hash
from app.services.exceptions import PcsError

#: 列表默认只**排除作废**（其余全列）。
#:
#: ⚠️ **为什么不照抄结果模块的 (DRAFT, CHECKED) 白名单**：那两条是「**可编辑**」
#: 的状态 ⇒ ⇒ 结果模块列表只列可改的行是对的；但 PMS 是**材料规格台账**
#: ⇒ ⇒ 只列 DRAFT/CHECKED ⇒ ⇒ **送审中的、已核验的条目全都看不见**
#: ⇒ ⇒ 用户提交完就「消失」了 ⇒ ⇒ 那是台账页最不能接受的行为。
#:
#: ⇒ ⇒ 只排掉 `OBSOLETE`（作废的行不该占台账）⇒ ⇒ 其余 8 态全列。
DEFAULT_STATUSES: tuple[RecordSignStatus9, ...] = (
    RecordSignStatus9.DRAFT,
    RecordSignStatus9.IN_APPROVAL,
    RecordSignStatus9.CHECKED,
    RecordSignStatus9.CHECK_REJECTED,
    RecordSignStatus9.STALE,
    RecordSignStatus9.CHANGE_PENDING,
    RecordSignStatus9.CHANGED,
    RecordSignStatus9.REVERSAL_PENDING,
)


async def list_pms_items(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    sign_status_filter: tuple[RecordSignStatus9, ...] = DEFAULT_STATUSES,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[PmsItem]:
    """列出项目下的 PMS 条目（按创建时间倒序）。"""
    stmt = select(PmsItem).where(PmsItem.project_id == project_id)
    if sign_status_filter:
        stmt = stmt.where(PmsItem.sign_status.in_(sign_status_filter))
    stmt = stmt.order_by(PmsItem.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_pms_item(
    session: AsyncSession, *, item_id: uuid.UUID
) -> PmsItem | None:
    """按 id 取一条（不判权限 —— 权限由路由层判）。"""
    result = await session.execute(
        select(PmsItem).where(PmsItem.item_id == item_id)
    )
    return result.scalar_one_or_none()


def _is_pms_no_unique_violation(exc: IntegrityError) -> bool:
    """这条 `IntegrityError` 是不是 `pms_no` 的**唯一约束**冲突？

    ⚠️ **只**对唯一约束说 True —— 别的约束违约（NOT NULL / FK / CHECK）
    必须让调用方重新抛出（⇒ 500 + 服务端留详情）⇒ ⇒ 否则用户会被
    「编号已存在」这条**假提示**引到错误的方向（TODO-102 同形）。

    判据：PG 的 `exc.orig.diag.constraint_name` == `uq_pms_items_project_pms_no`；
    SQLite（单测）没有 `diag` ⇒ 匹配 `UNIQUE` + `pms_no`。
    """
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None)
    if constraint_name:
        return constraint_name == "uq_pms_items_project_pms_no"
    message = str(orig)
    return "UNIQUE" in message.upper() and "pms_no" in message


async def create_pms_item(
    session: AsyncSession,
    *,
    project: Project,
    payload: PmsItemCreate,
    created_by: uuid.UUID | None,
) -> PmsItem:
    """新建一条 PMS 条目（**DRAFT** ⇒ ⇒ 要送审走通用工作流）。"""
    if project.workspace_id is None:
        # ⚠️ **不猜**：工作区是签署矩阵 / 交付物绑定的键 ⇒ ⇒ 没有就是没有
        # ⇒ ⇒ fail-loud（否则条目会挂在一个没有归属的项目上）。
        raise PcsError(
            code="PROJECT_WITHOUT_WORKSPACE",
            status=422,
            message=f"项目 {project.project_id} 没有绑定工作区 ⇒ ⇒ 无法建立 PMS 条目",
        )
    item = PmsItem(
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        pms_no=payload.pms_no,
        description=payload.description,
        pms_class=payload.pms_class,
        hazard_level=payload.hazard_level,
        sign_status=RecordSignStatus9.DRAFT,
        created_by=created_by,
    )
    session.add(item)
    try:
        await session.flush()
        # ⚠️ **flush 之后才算哈希**（默认值此刻才落进 state.dict）
        item.record_hash = compute_record_hash(item)
        await session.flush()
    except IntegrityError as exc:
        if not _is_pms_no_unique_violation(exc):
            raise
        await session.rollback()
        raise PcsError(
            code="PMS_NO_CONFLICT",
            status=409,
            message=(
                f"PMS 编号 {payload.pms_no} 在本项目已存在（项目内唯一），请换一个"
            ),
        ) from exc
    return item


async def update_pms_item(
    session: AsyncSession,
    *,
    item: PmsItem,
    payload: PmsItemUpdate,
) -> PmsItem:
    """改一条 PMS 条目（**只有 DRAFT 能改**）。

    ⚠️ 锁定态（CHECKED / IN_APPROVAL / …）拒绝改 ⇒ ⇒ 评审中数据不漂。
    """
    if item.sign_status != RecordSignStatus9.DRAFT:
        raise PcsError(
            code="PMS_ITEM_NOT_EDITABLE",
            status=409,
            message=(
                f"PMS 条目 {item.item_id} 当前状态 {item.sign_status} 不可修改"
                "（只有 DRAFT 可改；已送审的请走变更单）"
            ),
        )
    item.pms_no = payload.pms_no
    item.description = payload.description
    item.pms_class = payload.pms_class
    item.hazard_level = payload.hazard_level
    await session.flush()
    item.record_hash = compute_record_hash(item)
    await session.flush()
    return item
