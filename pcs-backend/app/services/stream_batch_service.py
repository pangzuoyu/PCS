"""批量「提交校对」（P9B-3b · 委员会裁决 5 的 D1~D6）。

## 契约要点

- **D1** 后端端点：一次请求 N 条（前端**不**循环 —— 部分失败无法重试）。
- **D2** 部分成功：一条失败**不回滚**其它条。
- **D3** 审计 N+1：每条**真正转移**的物流 1 条 `RECORD_TRANSITION`（状态机写）
  + 批次 1 条 `STREAM_BATCH_SUBMITTED`（本模块写）。
- **D4** 上限取 `system_settings.stream.batch_submit_limit`（默认 100）。
- **D5** 幂等：批次内按 `stream_id` 去重；**已 `IN_APPROVAL`** 记成功
  （`note="already_in_approval"`）⇒ 重复提交**不报错**、也**不重复写审计**。
- **D6** `dry_run=true` ⇒ 不改状态、**不写任何审计**（含批次那条），
  只返回每条的预判结果。

## ⚠️ 为什么**逐条 commit**（而不是整批一个事务）

`StreamService.transition` 在非法转移 / 越权时 `await db.rollback()` ——
**rollback 掉的是「当前事务」** ⇒ 若整批共用一个事务，**一条失败会把前面已经
成功的那些全回滚掉**（与 D2 相反）⇒ 故每条自成事务：一条失败只回滚它自己。

⚠️ **「用 SAVEPOINT 隔离每条」这条路走不通**（2026-11-03 · D7 **实测**）：
在 `begin_nested()` 内调用 **session 级** `await db.rollback()` ⇒
**整个外层事务被关掉**（实测：后续 insert 报 `Can't operate on closed
transaction`，连 savepoint 之外的那行也没落库）⇒
**实测比文档措辞可靠**：只有 `begin_nested()` 返回的 `SessionTransaction`
句柄的 `rollback()` 才只回滚到 savepoint ⇒ 而 `transition` 内部调的是
session 级 `db.rollback()` ⇒ 救不了 ⇒ **逐条 commit 是唯一可行解**。

⚠️ **「整批一个事务」被排除的根本理由不是死锁，而是与 D2 冲突**：
D2 已裁决「部分成功」（50 条里 8 条失败不该回滚 42 条）⇒
「全成或全不成」是 D2 的反面。（死锁是可排序修复的次要问题，且逐条 commit
天然只持一把锁 ⇒ 没有死锁面。）

⚠️ **性能代价（实测本机 PG：18.6 · `synchronous_commit=on` · `fsync=on` ·
`wal_sync_method=fdatasync`）**：100 条 = 100 次 COMMIT ⇒ 每次一次 WAL fsync
≈ 0.5~2ms ⇒ 合计 **≈ 50~200ms** ⇒ **用户感知上不可区分**（< 200ms），
但吞吐量上确实有差 ⇒ 这是**刻意接受**的代价（换来：不持多把锁 + 与单条端点
**走同一条状态机路径**）。

⚠️ **实现形态（已核实，勿画蛇添足）**：`StreamService.transition` 内部
**自己** `db.commit()`（成功路径，第 477 行）+ `db.refresh()`，错误路径
`db.rollback()`（第 463/470 行）⇒ ⇒ **批次 service 不要用
`async with db.begin():` 包每条**（transition 已经提交了，再 commit 会撞
「closed transaction」）⇒ **直接调 transition，让它自己提交**就是「逐条 commit」
的正确实现 ⇒ 批次 service 在条目之间**不需要**额外的 commit / rollback。

## ⚠️ 为什么加锁读用 `populate_existing=True`

同 P9B-3 评审 C-1：加锁读的**目的**就是读「锁住的那一行」⇒ 若 session 里
已有同 PK 的实体（identity map），SQLAlchemy **默认不覆盖**它的已加载属性
⇒ 读到的是**过期**状态 ⇒ 并发时两个提交都基于同一个旧状态通过 ⇒ 行锁形同虚设。
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.enums import AuditAction, StateTransition, StreamSignStatus
from app.models.project import Stream
from app.schemas.stream_batch import (
    BatchFailedItem,
    BatchSucceededItem,
    StreamBatchSubmitResponse,
)
from app.services.audit_service import AuditService
from app.services.stream_service import (
    StreamService,
    composition_mole_fraction_total,
    select_stream_for_update,
)
from app.services.system_setting_service import get_setting_value

logger = logging.getLogger(__name__)

#: 批次上限的配置键（值在 `system_settings` 表里，管理员可改）。
BATCH_LIMIT_SETTING_KEY = "stream.batch_submit_limit"

#: 配置读不到时的兜底上限（与 `DEFAULT_SETTINGS` 的 seed 值一致）。
DEFAULT_BATCH_LIMIT = 100

#: 组成合计的容差（≡ SPEC §7.7.2「100±0.5%」）。
COMPOSITION_TOLERANCE = 0.005

#: 幂等命中时的 `note`。
NOTE_ALREADY_IN_APPROVAL = "already_in_approval"


async def _batch_limit(db: AsyncSession) -> int:
    """批次上限（`system_settings.stream.batch_submit_limit`，默认 100）。"""
    raw = await get_setting_value(
        db, BATCH_LIMIT_SETTING_KEY, default=DEFAULT_BATCH_LIMIT
    )
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        limit = DEFAULT_BATCH_LIMIT
    return max(limit, 1)


async def _submit_one(
    db: AsyncSession,
    stream_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    actor_role: str,
    dry_run: bool,
) -> BatchSucceededItem | BatchFailedItem:
    """处理一条 ⇒ 返回**成功或失败**（**绝不抛异常**）。

    ⚠️ **绝不抛异常**是批次语义（D2 部分成功）的一部分：任何一条出错都必须
    变成 `BatchFailedItem`，**不能**让异常冒泡中断整个批次（委员会
    2026-11-03 · D5 裁决的「附加」条款）。

    ⚠️ 返回类型是 **union**（不是「带 ok 开关的 `_Outcome`」）：
    - 成功项只有成功的字段（`from_status` / `to_status` / `note`）；
    - 失败项只有失败的字段（`reason` / `detail`）；
    - `status` 是**判别字段** ⇒ 调用方与前端都靠它分流。

    ⚠️ 契约类型与内部计算是**同一件事**（批次结果就只是「成功 / 失败」）⇒
    直接返回契约类型，**不再有中间类型**（字段定义只有一处 ⇒ 不会分叉）。
    ⚠️ 这确实是**新引入的返回类型耦合**（`StreamService.transition` 返回的是
    ORM 实体 `Stream`）⇒ 理由是「批次结果的语义就是 schema 的语义」，
    **不是**「延续惯例」。
    """
    try:
        return await _submit_one_inner(
            db,
            stream_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            dry_run=dry_run,
        )
    except PcsError as e:
        return BatchFailedItem(
            status="failed",
            stream_id=stream_id,
            reason=getattr(e, "code", "SIM_STREAM_UNKNOWN"),
            detail=str(e),
        )
    except Exception:  # noqa: BLE001 —— 兜底：非预期异常也**不中断批次**
        # ⚠️ 这不是「打补丁」，是批次语义的要求：单条失败不应中断批次。
        logger.exception("批量提交校对：条目 %s 处理失败", stream_id)
        return BatchFailedItem(
            status="failed",
            stream_id=stream_id,
            reason="INTERNAL_ERROR",
            detail="服务端内部错误，请联系管理员",
        )


async def _read_sign_status(db: AsyncSession, stream_id: uuid.UUID) -> str | None:
    """读回一条物流**当前**的 `sign_status`（**只读这一列**）。

    ⚠️ 为什么需要它：转移失败后必须判断「**这条到底提交了没有**」——
    `StreamService.transition` 的顺序是 flush → commit → refresh ⇒
    flush 之后失败 ⇒ 数据还**没**提交（回滚即可）；
    commit 之后失败（refresh 挂掉）⇒ 数据**已经**提交 ⇒ 报「失败」是错的。

    ⚠️ 只 SELECT 一列 ⇒ 不加载整行 ⇒ 不会把实体塞进 identity map
    （也不会覆盖调用方已经持有的实体）。
    """
    value = (
        await db.execute(
            select(Stream.sign_status).where(Stream.stream_id == stream_id)
        )
    ).scalar_one_or_none()
    if value is None:
        return None
    return str(getattr(value, "value", value))


async def _submit_one_inner(
    db: AsyncSession,
    stream_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    actor_role: str,
    dry_run: bool,
) -> BatchSucceededItem | BatchFailedItem:
    """处理一条的**业务逻辑**（异常由 `_submit_one` 统一兜住）。"""
    if dry_run:
        # ⚠️ 预演**不加锁**（不改任何东西 ⇒ 不该占着别人的行锁）。
        stream = (
            await db.execute(
                select(Stream).where(Stream.stream_id == stream_id)
            )
        ).scalar_one_or_none()
    else:
        # ⚠️ 加锁读走**唯一入口**（T1 抽出的 `select_stream_for_update`）——
        #    它带 `populate_existing=True`（C-1 的修复点）⇒ 并发时读到的是
        #    **锁住的那一行**，不是 identity map 里的旧副本。
        stream = await select_stream_for_update(db, stream_id)

    if stream is None:
        return BatchFailedItem(
            status="failed",
            stream_id=stream_id,
            reason="SIM_STREAM_NOT_FOUND",
            detail=f"物流 {stream_id} 不存在",
        )

    from_status = str(
        stream.sign_status.value
        if hasattr(stream.sign_status, "value")
        else stream.sign_status
    )

    # D5 幂等：已 IN_APPROVAL ⇒ 记成功，**不重复转移、不重复写审计**。
    if from_status == StreamSignStatus.IN_APPROVAL.value:
        return BatchSucceededItem(
            status="succeeded",
            stream_id=stream_id,
            from_status=from_status,
            to_status=from_status,
            note=NOTE_ALREADY_IN_APPROVAL,
        )

    # 组成合计门禁（与单条端点**同一口径**）。
    total = composition_mole_fraction_total(stream)
    if total is not None and abs(total - 1.0) > COMPOSITION_TOLERANCE:
        return BatchFailedItem(
            status="failed",
            stream_id=stream_id,
            reason="SIM_STREAM_COMPOSITION_OUT_OF_RANGE",
            detail=(
                f"物流 {stream_id} 的组成摩尔分率合计 {total * 100:.2f}%，"
                "不在 100±0.5% 内 ⇒ 不能提交校对"
            ),
        )

    if dry_run:
        # D6：预演 ⇒ 只给结论，不改状态、不写审计。
        return BatchSucceededItem(
            status="succeeded",
            stream_id=stream_id,
            from_status=from_status,
            to_status=StreamSignStatus.IN_APPROVAL.value,
        )

    # 真正的转移：行锁 + 角色校验 + 单条审计 + **提交**（逐条独立事务）。
    # ⚠️⚠️ **失败必须回滚这条的部分写入**（否则会被下一条的 commit 带走）。
    try:
        await StreamService.transition(
            db,
            stream_id,
            transition=StateTransition.SUBMIT_FOR_CHECK,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
    except Exception:
        # `transition` 的内部顺序是 **flush（状态已写进当前事务）→ commit** ⇒
        # 若在 flush 之后、commit 之前失败（最现实的：**审计写失败**），
        # 那条的状态**已经 flush 进事务但还没 commit** ⇒
        # ⚠️ **不回滚 ⇒ 下一条处理成功时它的 `db.commit()` 会把这条的脏写
        # 一起提交掉** ⇒ 响应说这条失败、DB 里它却是 IN_APPROVAL ⇒
        # **状态与响应互相矛盾**（且审计正是失败的原因 ⇒ 没有审计）。
        #
        # ⇒ 这里回滚**这条**的事务（每条自成事务 ⇒ 回滚只影响这条，
        #    已提交的前面那些**不受影响** ⇒ D2「部分成功」仍成立）。
        await db.rollback()
        # ⚠️ 回滚之后**必须读回真实状态**：commit 可能**已经成功**了
        #    （`transition` 里 commit 之后还有一次 `db.refresh` ⇒ 它失败时
        #    数据**已落库**）⇒ 那时报「失败」同样是错的 ⇒ 读回 IN_APPROVAL
        #    ⇒ 老实报**成功**。
        #    判据是可靠的：走到这里说明 `from_status != IN_APPROVAL`
        #    （幂等命中在上面就返回了）⇒ 「现在是 IN_APPROVAL」只可能是
        #    **这次转移真的提交了**。
        actual = await _read_sign_status(db, stream_id)
        if actual == StreamSignStatus.IN_APPROVAL.value:
            return BatchSucceededItem(
                status="succeeded",
                stream_id=stream_id,
                from_status=from_status,
                to_status=StreamSignStatus.IN_APPROVAL.value,
            )
        raise

    return BatchSucceededItem(
        status="succeeded",
        stream_id=stream_id,
        from_status=from_status,
        to_status=StreamSignStatus.IN_APPROVAL.value,
    )


async def _write_batch_audit(
    db: AsyncSession,
    *,
    batch_id: uuid.UUID,
    total: int,
    succeeded: list[BatchSucceededItem],
    failed: list[BatchFailedItem],
    actor_user_id: uuid.UUID,
    actor_role: str,
) -> None:
    """写批次审计（D7 的**最后一个**事务；预演不写）。

    ## ⚠️ 审计记录的形状（**给审计页的用户看的**）

    - `action = STREAM_BATCH_SUBMITTED`
    - `resource_type = "STREAM_BATCH"` ← **本批新增的资源类型**
    - `resource_id = str(batch_id)` ← **必须**等于响应里的 `batch_id`
      ⇒ 用户拿到 `batch_id` ⇒ 管理员就能在审计页查到这一批
      （**由测试 `test_batch_audit_resource_id_equals_response_batch_id` 钉住**）
    - `detail_json = {batch_id, total, succeeded_ids, failed_ids, dry_run,
      requester_user_id, requester_role, succeeded[], failed[]}`

    ## ⚠️ 怎么在审计页查到它（本批的审计页现状）

    审计页（`/audit`）的 `resource_type` 过滤是**自由文本输入框**（**不是下拉**
    —— `AuditLogPage.tsx:395`）⇒ 查批次审计的步骤：
    1. 打开 `/audit`；
    2. `resource_type` 输入 `STREAM_BATCH`；
    3. 知道批次 id 的话，`resource_id` 再输入那个 `batch_id`（uuid）；
    4. `action` 过滤可不填（会显示所有批次审计）。

    ⚠️ **不要在审计页加「STREAM_BATCH 下拉项」** —— 那是审计页的**通用**改进
    （`resource_type` 的下拉需要一个**权威词表来源**，而那个来源目前**不存在**
    ⇒ 不是「枚举词表麻烦」，是「未设计的通用功能」）⇒ **不是本批的事**。
    批次自己的义务是「**文档化自己的输出格式**」。

    ## ⚠️ 写失败**不能**回滚已提交的结果

    调用方兜住异常（记 ERROR 日志 + 回滚**这次**写入 + 在响应里带 `warning`）
    ⇒ 已提交的 stream 是 D2「部分成功」的成果，回滚它们违背 D2。
    """
    await AuditService(db).write(
        action=AuditAction.STREAM_BATCH_SUBMITTED,
        resource_type="STREAM_BATCH",
        resource_id=str(batch_id),
        user_id=actor_user_id,
        detail={
            # ⚠️ **审计完整性**（委员会 2026-11-03 · D3 约束 2）：本端点
            #    **没有项目守卫**（与既有单条端点同口径，见 T6 登记的
            #    TODO-118）⇒ 审计是**唯一**的事后追溯手段 ⇒ 这一行必须
            #    一次说清「谁 · 哪一批 · 动了哪些 · 每条什么结果」。
            "batch_id": str(batch_id),
            "total": total,
            "dry_run": False,
            "requester_user_id": str(actor_user_id),
            "requester_role": actor_role,
            # ⚠️ 两个 id 数组 = 「这一批动了哪些」的**可 grep** 形态
            #    （完整条目里也带 stream_id，但审计排查时按 id 数组找更快）
            "succeeded_ids": [str(item.stream_id) for item in succeeded],
            "failed_ids": [str(item.stream_id) for item in failed],
            # 完整条目（带 from/to/note 与 reason/detail ⇒ **失败原因不丢**）
            "succeeded": [item.model_dump(mode="json") for item in succeeded],
            "failed": [item.model_dump(mode="json") for item in failed],
        },
    )
    await db.commit()


async def submit_batch(
    db: AsyncSession,
    stream_ids: list[uuid.UUID],
    *,
    actor_user_id: uuid.UUID,
    actor_role: str,
    dry_run: bool = False,
    limit: int | None = None,
) -> StreamBatchSubmitResponse:
    """批量提交校对（D1~D6）。

    Args:
        db: async session
        stream_ids: 待提交的物流 id（**去重后**处理；保留请求顺序）
        actor_user_id: 操作用户（写审计）
        actor_role: 操作用户角色（状态机按 `TRANSITION_ROLES` 校验）
        dry_run: 只校验，不改状态、不写审计（D6）
        limit: **覆盖**批次上限（默认 `None` ⇒ 读系统参数 `stream.batch_submit_limit`）

    Returns:
        207 的批次结果（成功清单 + 失败清单）。

    Raises:
        PcsError: 422 —— 超过批次上限（整批拒，**不**部分执行）。
    """
    effective_limit = limit if limit is not None else await _batch_limit(db)

    # D5 去重（保留请求顺序 ⇒ 响应顺序可预期）。
    unique_ids = list(dict.fromkeys(stream_ids))

    if len(unique_ids) > effective_limit:
        raise PcsError(
            code="SIM_STREAM_BATCH_LIMIT_EXCEEDED",
            message=(
                f"批量提交 {len(unique_ids)} 条，超过上限 {effective_limit} 条"
                f"（系统参数 {BATCH_LIMIT_SETTING_KEY}）"
            ),
            status=422,
            detail={
                "limit": effective_limit,
                "requested": len(unique_ids),
                "setting_key": BATCH_LIMIT_SETTING_KEY,
            },
        )

    batch_id = uuid.uuid4()
    outcomes: list[BatchSucceededItem | BatchFailedItem] = []

    for stream_id in unique_ids:
        outcomes.append(
            await _submit_one(
                db,
                stream_id,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                dry_run=dry_run,
            )
        )

    # 分流：靠 **status 判别字段**（不用 isinstance —— JSON 序列化后
    # isinstance 的信息会丢，而 `status` 会留在契约里 ⇒ 前端也能靠它分流）。
    succeeded = [o for o in outcomes if o.status == "succeeded"]
    failed = [o for o in outcomes if o.status == "failed"]

    # D3 批次审计（D6：预演**不写**）。
    # ⚠️ **批次审计的写入时机**（委员会 2026-11-03 · D7 裁决的「遗漏项」）：
    #   - 每条 stream 的审计（`RECORD_TRANSITION`）在**每条自己的事务**里
    #     （随那条一起 commit / rollback）；
    #   - 批次的那一条（`STREAM_BATCH_SUBMITTED`）在**最后单独一次**事务里写；
    #   - ⚠️ **批次审计写失败 ⇒ 绝不能回滚已提交的 stream**（那是 D2「部分成功」
    #     的成果）⇒ 记 ERROR 日志 + 回滚**这次**审计写入 ⇒ **仍然返回 207**
    #     ⇒ 响应里带 `warning` ⇒ 前端提示「已提交 N 条，但批次记录写入失败」。
    warning: str | None = None
    if not dry_run:
        try:
            await _write_batch_audit(
                db,
                batch_id=batch_id,
                total=len(unique_ids),
                succeeded=succeeded,
                failed=failed,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            )
        except Exception:  # noqa: BLE001 —— 审计写失败**不能**毁掉已提交的结果
            logger.exception("批量提交校对：批次审计写入失败（batch_id=%s）", batch_id)
            await db.rollback()  # 只回滚**这次**审计写入
            warning = (
                f"已提交 {len(succeeded)} 条，但批次记录写入失败，请联系管理员"
                f"（batch_id={batch_id}）"
            )

    return StreamBatchSubmitResponse(
        batch_id=batch_id,
        total=len(unique_ids),
        succeeded=succeeded,
        failed=failed,
        dry_run=dry_run,
        warning=warning,
    )
