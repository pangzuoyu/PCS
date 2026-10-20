"""编辑冲突 guard：**能力声明 + 阶梯判定 + 编辑审计**（ADR-0048 §⑥ §⑦）。

P9A-4 的分工：
- **D1**：静态声明（能力表 / 已接线表）。
- **D2（本文件当前内容）**：阶梯判定（`check_conflict`）+ 编辑审计
  （`record_edit_audit`）+ 自检扫描（`scan_missing_record_hash`）。

## 为什么用显式映射，不用 ORM 反射

ADR-0048 §⑥ 记的教训：`cost_est_results` 曾经「登记在
`RECORD_TYPE_REGISTRY` 里、却没有 `record_hash` 列」——
反射把「ORM 有列」当成「表有能力」，而两者可能不一致。

⇒ **能力必须显式声明**。漏登记要抛 `UnregisteredTableError`
（`check_conflict` 不得静默走 `no_baseline` —— 那等于给没保护的东西
发「无冲突」通行证）。

## 键 = `RECORD_TYPE_REGISTRY` 的键（**不是**表名、**不是**类名）

2026-10-20（P9A-5 Task A / TODO-060）。本表原先用**表名**当键，与
`/change-impact`、`/records/{module}` 的注册表键分叉 ⇒ 同一个 UI 要同时持
两套标识，且两套**都不报错**：

- `/locks` 无校验 ⇒ 前端传类名会 **200**，锁写进 `lock:edit:CostEstResult:{id}`，
  与 `lock:edit:cost_est_results:{id}` **互不可见** ⇒ 两个人用不同拼写可以
  同时编辑同一条记录 ⇒ 锁形同虚设。
- `has_conflict_detection("CostEstResult")` 返回 False ⇒ 降级横幅会**错误地**
  追加「；本次编辑无冲突检测」，而该表其实**有**冲突检测。

⚠️ **为什么不是「类名」**：`RECORD_TYPE_REGISTRY` 的 21 个键里**有 5 个 ≠ 类名**
（`cv_result` / `restriction_result` / `flare_system_result` /
`cooling_tower_result` / `psychro_result`）⇒ 「类名」本身不是一套词表。
⚠️ **为什么不用表名反查**：表名是复数（`cost_est_results`）、注册表键是单数
（`CostEstResult`）⇒ 反查**对 21 个全部失败**（TODO-060 原写「双向可换」，
实测为假）。

⇒ 本表的 `model` **从注册表取**（不再是手写的第二份模型清单）；
契约测试（`tests/api/v1/test_record_type_vocabulary.py`）钉住
`cap.model is RECORD_TYPE_REGISTRY[key]`。

## 两张表的区别（别混）

| 常量 | 含义 | 变更时机 |
|---|---|---|
| `TABLE_CAPABILITIES` | 该表**有**哪些并发令牌（能力）+ ORM 模型 | 加列 / 改 schema 时 |
| `GUARDED_TABLES` | 该表的保存路径**已接上** DB 层冲突检测（接线） | 接线时 |

「有能力」≠「已接线」。降级横幅按 `GUARDED_TABLES` 说话（§⑤ 的横幅是给
用户的**事实陈述**，不是能力表）。D2 的契约测试断言两张表**逐项相等**。
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction
from app.schemas.edit_conflict import ConflictDetail, EditAuditDetail
from app.services.audit_service import AuditService
from app.services.calc_lineage import RECORD_TYPE_REGISTRY

logger = logging.getLogger(__name__)


class UnregisteredTableError(LookupError):
    """表没有登记并发令牌能力。

    抛出而不是降级：`check_conflict` 对未登记的表**静默走 no_baseline**
    等于给没保护的东西发「无冲突」通行证（ADR-0048 §⑥）。
    """


@dataclass(frozen=True)
class TableCapability:
    """一张可编辑表的并发令牌能力（ADR-0048 §⑥）。

    ⚠️ `pk_attr` 必须在声明里 —— **反射猜不出主键叫什么**（6 张表有 6 个不同
    的主键名：`cooling_tower_id` / `filter_id` / `flare_id` / `open_channel_id` /
    `psychro_id` / `cost_est_id`）。
    ⚠️ `model` **必须写成 `RECORD_TYPE_REGISTRY[key]`**（不是手写类名）——
    否则「表 → 模型」就是同一概念的第二份清单（会漂移），正是本文件
    docstring 反对的那件事。
    """

    model: type
    pk_attr: str
    has_record_hash: bool
    has_updated_at: bool


#: 全部有手动编辑端点的结果表（实测：`grep -rn '@router\.\(patch\|put\)' app/api/v1/*.py`）。
#: ⚠️ **只登记有编辑路径的表** —— 其余表保护的是一个不存在的并发。
#: ⚠️ 键 = `RECORD_TYPE_REGISTRY` 的键（P9A-5 Task A，TODO-060）。
TABLE_CAPABILITIES: dict[str, TableCapability] = {
    "cooling_tower_result": TableCapability(
        model=RECORD_TYPE_REGISTRY["cooling_tower_result"],
        pk_attr="cooling_tower_id",
        has_record_hash=True,
        has_updated_at=True,
    ),
    "FiltrationResult": TableCapability(
        model=RECORD_TYPE_REGISTRY["FiltrationResult"],
        pk_attr="filter_id",
        has_record_hash=True,
        has_updated_at=True,
    ),
    "flare_system_result": TableCapability(
        model=RECORD_TYPE_REGISTRY["flare_system_result"],
        pk_attr="flare_id",
        has_record_hash=True,
        has_updated_at=True,
    ),
    "OpenChannelResult": TableCapability(
        model=RECORD_TYPE_REGISTRY["OpenChannelResult"],
        pk_attr="open_channel_id",
        has_record_hash=True,
        has_updated_at=True,
    ),
    "psychro_result": TableCapability(
        model=RECORD_TYPE_REGISTRY["psychro_result"],
        pk_attr="psychro_id",
        has_record_hash=True,
        has_updated_at=True,
    ),
    # CostEstResult：P9A-4 D0 刚补上 record_hash，但**没有 updated_at**
    # ⇒ 退化阶梯对它只有**一档**（record_hash），没有第二档兜底。
    "CostEstResult": TableCapability(
        model=RECORD_TYPE_REGISTRY["CostEstResult"],
        pk_attr="cost_est_id",
        has_record_hash=True,
        has_updated_at=False,
    ),
}

#: 保存路径**已接上** DB 层冲突检测的表。
#:
#: ⚠️ 「已接上」= D2 的 guard **真的接在该表的保存路径上**，不是「该表有
#: record_hash 列」。降级横幅按这张表说话：不在表里 ⇒ 用户在无冲突检测
#: 的状态下编辑 ⇒ 横幅必须写「本次编辑无冲突检测」（ADR-0048 §⑤）。
GUARDED_TABLES: frozenset[str] = frozenset(TABLE_CAPABILITIES)


@dataclass(frozen=True)
class ConflictCheckResult:
    """`check_conflict` 的结果（ADR-0048 §⑥ 决策 2）。

    ⚠️ **不返回 None、不抛异常**：
    - 返回 None ⇒ 每个调用点都要自己发明「怎么把冲突传出去」，然后漂移；
    - 抛异常 ⇒ 每个调用点都要 try/except。
    ⇒ 统一返回本对象；`conflict` 为 None 表示放行。

    `overwrote_stale_baseline`：本次保存**未经 hash 级比对**就放行了
    （行上的 hash 是空的 ⇒ 只能靠 updated_at 或根本没得比）⇒ 可能覆盖了
    别人的改动 ⇒ 按 ADR-0048 §⑦ 另写一条
    `RECORD_EDIT_OVERWROTE_STALE_BASELINE` 审计。
    """

    conflict: ConflictDetail | None
    overwrote_stale_baseline: bool = False


def capability_of(record_type: str) -> TableCapability:
    """查表能力。**未登记 ⇒ 抛 `UnregisteredTableError`**（不得静默降级）。

    ⚠️ `record_type` 是 `RECORD_TYPE_REGISTRY` 的**键**（`CostEstResult`），
    **不是**表名（`cost_est_results`）—— 见模块 docstring「键」一节。
    """
    try:
        return TABLE_CAPABILITIES[record_type]
    except KeyError as e:
        raise UnregisteredTableError(
            f"记录类型 {record_type!r} 未登记并发令牌能力 —— "
            "登记前不得给它做冲突判定；键必须是 RECORD_TYPE_REGISTRY 的键"
            "（如 CostEstResult），不是表名（ADR-0048 §⑥ · TODO-060）"
        ) from e


def has_conflict_detection(record_type: str) -> bool:
    """该表的保存路径**是否已接上**冲突检测（降级横幅用）。"""
    return record_type in GUARDED_TABLES


def _as_utc(value: datetime | None) -> datetime | None:
    """时间统一到 UTC（客户端可能送 naive 或带别的时区）。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def check_conflict(
    session: AsyncSession,
    *,
    record_type: str,
    record_id: uuid.UUID,
    expected_hash: str | None,
    expected_updated_at: datetime | None,
) -> ConflictCheckResult:
    """判定本次编辑是否与他人冲突（ADR-0048 §⑥ 的退化阶梯）。

    **纯检查，无副作用**：不改数据、不写审计（约束 1）。

    阶梯：

    ```
    当前 record_hash != ""  → 比 hash：不等 ⇒ 409 (basis=record_hash)
    当前 record_hash == ""  → 比 updated_at：不等 ⇒ 409 (basis=updated_at)
                            → 没有 updated_at / 客户端没给基线 ⇒ 409 (basis=no_baseline)
    ```

    ⚠️ **客户端没给基线 ⇒ 409（no_baseline）**：服务端无法判定并发，
    放行等于「保护可以不存在」（这正是 D0 修掉的那个假绿形状）。
    """
    cap = capability_of(record_type)  # 未登记 ⇒ UnregisteredTableError
    model = cap.model
    pk = getattr(model, cap.pk_attr)
    row = (
        await session.execute(select(model).where(pk == record_id))
    ).scalar_one_or_none()
    if row is None:
        # 记录不存在 ⇒ 交给业务层 404（这里不编造冲突）
        return ConflictCheckResult(conflict=None, overwrote_stale_baseline=False)

    current_hash = (getattr(row, "record_hash", "") or "").strip()
    current_updated_at = _as_utc(getattr(row, "updated_at", None))

    async def _conflict(basis: str, message: str) -> ConflictCheckResult:
        changed_by, changed_at = await _last_editor(session, record_type, record_id)
        return ConflictCheckResult(
            conflict=ConflictDetail(
                record_type=record_type,
                record_id=str(record_id),
                your_expected_hash=expected_hash,
                current_hash=current_hash or None,
                changed_by=changed_by,
                changed_at=changed_at,
                basis=basis,  # type: ignore[arg-type]
            ),
            overwrote_stale_baseline=False,
        )

    if current_hash:
        # 第一档：hash 比对（最强，能检出「内容变了但行没动」）
        if expected_hash is None:
            return await _conflict("no_baseline", "客户端未提供基线，无法判定并发")
        if current_hash != expected_hash:
            return await _conflict("record_hash", "该记录已被他人修改，请刷新后重新编辑")
        return ConflictCheckResult(conflict=None, overwrote_stale_baseline=False)

    # 第二档：hash 为空（从未计算过）⇒ 退到 updated_at
    if cap.has_updated_at and current_updated_at is not None:
        if expected_updated_at is None:
            return await _conflict("no_baseline", "客户端未提供基线，无法判定并发")
        if current_updated_at != _as_utc(expected_updated_at):
            return await _conflict("updated_at", "该记录已被他人修改，请刷新后重新编辑")
        # 放行，但**未经 hash 级比对** ⇒ 记一条「覆盖了陈旧基线」审计
        return ConflictCheckResult(conflict=None, overwrote_stale_baseline=True)

    return await _conflict("no_baseline", "该记录没有可用的并发基线，无法判定并发")


async def _last_editor(
    session: AsyncSession, record_type: str, record_id: uuid.UUID
) -> tuple[str | None, datetime | None]:
    """上一次编辑者（user_id / 时间），取自**编辑审计**。

    ⚠️ 只认 `action = RECORD_EDITED` 的审计行，**不得**用「该记录最近一条
    审计」泛匹配去凑（ADR-0048 §⑦ 强制）。
    ⚠️ **不得**用 `updated_at` 冒充 `changed_at`（那是精确性伪装）。
    """
    from app.models.system import AuditLog

    row = (
        await session.execute(
            select(AuditLog)
            .where(
                AuditLog.action == AuditAction.RECORD_EDITED.value,
                AuditLog.resource_type == record_type,
                AuditLog.resource_id == str(record_id),
            )
            .order_by(AuditLog.occurred_at.desc(), AuditLog.audit_id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return None, None
    return (str(row.user_id) if row.user_id else None), row.occurred_at


async def record_edit_audit(
    session: AsyncSession,
    *,
    record_type: str,
    record_id: uuid.UUID,
    user_id: uuid.UUID,
    changed_fields: list[str],
    overwrote_stale_baseline: bool = False,
) -> None:
    """写编辑审计（ADR-0048 §⑦）。

    ⚠️ **纯写审计**：不判定冲突（判定在 `check_conflict`），也不改业务数据。
    ⚠️ `changed_fields` 是**字段名列表**，不是完整值（一次大改版几十 KB）。
    ⚠️ 本函数**不 commit** —— 事务边界由调用方控制。
    """
    detail = EditAuditDetail(
        changed_fields=list(changed_fields),
        overwrote_stale_baseline=overwrote_stale_baseline,
    )
    audit = AuditService(session)
    await audit.write(
        action=AuditAction.RECORD_EDITED,
        resource_type=record_type,
        resource_id=str(record_id),
        user_id=user_id,
        detail=detail.model_dump(mode="json"),
    )
    if overwrote_stale_baseline:
        # ADR-0048 §⑦：覆盖了无法校验的基线 ⇒ 另写一条，事后能看见
        # 「谁在锁失效期间覆盖了别人」
        await audit.write(
            action=AuditAction.RECORD_EDIT_OVERWROTE_STALE_BASELINE,
            resource_type=record_type,
            resource_id=str(record_id),
            user_id=user_id,
            detail=detail.model_dump(mode="json"),
        )


async def scan_missing_record_hash(session: AsyncSession) -> dict[str, int]:
    """自检：扫出「record_hash 为空」的行（ADR-0048 §⑥ 的残留风险自检）。

    「提交了但没 finalize」的行会**永久**停在 `hash=""` ⇒ 落 no_baseline
    ⇒ 那一行没有并发保护。这是「计算结果已落库但哈希从未生成」的可靠信号。

    返回 {注册表键: 行数}（全为 0 才是健康）。
    """
    out: dict[str, int] = {}
    for record_type, cap in TABLE_CAPABILITIES.items():
        if not cap.has_record_hash:
            continue
        model = cap.model
        n = (
            await session.execute(
                select(model).where(model.__table__.c.record_hash == "")
            )
        ).scalars().all()
        count = len(n)
        out[record_type] = count
        if count:
            logger.error(
                "自检：%s 有 %d 行 record_hash 为空（提交了但没 finalize？）",
                record_type,
                count,
            )
    return out


__all__ = [
    "GUARDED_TABLES",
    "TABLE_CAPABILITIES",
    "ConflictCheckResult",
    "TableCapability",
    "UnregisteredTableError",
    "capability_of",
    "check_conflict",
    "has_conflict_detection",
    "record_edit_audit",
    "scan_missing_record_hash",
]
