"""批次「提交校对」的地基能力（P9B-3b · T1）。

本文件先只放四件**可复用**的小能力（后续 T2 的批次 service 全部依赖它们）：

1. `composition_mole_fraction_total` —— 组成合计口径（**单一来源**）；
2. `get_setting_value` —— 读系统参数（批次上限从这儿取）；
3. `AuditAction.STREAM_BATCH_SUBMITTED` —— 批次审计动作；
4. `build_stream_for_update_stmt` / `select_stream_for_update` —— **唯一**的
   加锁读入口（单条提交与批量提交共用；`populate_existing=True` 是 C-1 的修复点）。

⚠️ 为什么组成口径要抽到 service：批次端点与单条端点**必须同一口径** ⇒
口径写在 router 里时，service 层只能反向 import 路由模块（分层倒挂）⇒ 抽。
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction, StreamSignStatus
from app.models.project import Stream
from app.services.stream_service import composition_mole_fraction_total
from app.services.system_setting_service import get_setting_value

pytestmark = pytest.mark.asyncio

#: 批次测试用的**固定**操作人。
#:
#: ⚠️ P9B-4 紧急批次 T4：批次 service 现在**逐条**做项目守卫 ⇒ 操作人没有
#: 授权行 ⇒ 每条都会被判成「不存在」⇒ 下面那些用例就全在测「全失败」而不是
#: 它们各自要测的东西了 ⇒ 用**固定**操作人 + `batch_project` 里给它授权。
#: （是**补授权行**，不是放宽守卫。）
BATCH_ACTOR_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "batch-actor")


def _stream(**kw) -> Stream:
    """构造一个**不落库**的 Stream（只测组成口径，不碰 DB）。"""
    return Stream(
        stream_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        stream_name="S-1",
        sign_status=StreamSignStatus.DRAFT,
        **kw,
    )


async def test_composition_total_none_means_no_composition():
    """`composition_json = None` ⇒ **跳过**（纯物质，无组成）。"""
    assert composition_mole_fraction_total(_stream(composition_json=None)) is None


async def test_composition_total_empty_object_is_zero():
    """`composition_json = {}` ⇒ 合计 0.0（⇒ 落在范围外 ⇒ **拒绝**，与「未填写」同义）。"""
    assert composition_mole_fraction_total(_stream(composition_json={})) == 0.0


async def test_composition_total_sums_fractions():
    """有内容 ⇒ 合计 = 各组分之和（值域 0~1 的小数，**不是**百分数）。"""
    total = composition_mole_fraction_total(
        _stream(composition_json={"7732-18-5": 0.6, "7440-23-5": 0.387})
    )
    assert total == pytest.approx(0.987)


async def test_get_setting_value_returns_stored_value(db_session: AsyncSession):
    """键存在 ⇒ 返回它的值。"""
    from app.services.system_setting_service import seed_defaults

    await seed_defaults(db_session)
    await db_session.commit()

    assert await get_setting_value(db_session, "stream.batch_submit_limit", default=7) == 100


async def test_get_setting_value_falls_back_to_default(db_session: AsyncSession):
    """键**不存在** ⇒ 返回 `default`（不抛异常 ⇒ 上限读不到时批次仍能跑）。"""
    assert await get_setting_value(db_session, "no.such.key", default=42) == 42


async def test_batch_audit_action_exists():
    """批次审计动作必须**存在**于枚举里（否则写审计时退化成裸字符串 ⇒ 审计页筛不出来）。"""
    assert AuditAction.STREAM_BATCH_SUBMITTED.value == "STREAM_BATCH_SUBMITTED"


# ---------------------------------------------------------------------------
# T2：批次 service 本身（D1~D6）
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def batch_project(db_session: AsyncSession, grant_project):
    """一个项目 + 一个工作区（批次里的物流都挂在它下面）。

    ⚠️ 同时给 `BATCH_ACTOR_ID` 授一行项目权限 —— 批次 service **逐条**做项目
    守卫（P9B-4 T4）⇒ 没授权 ⇒ 每条都判成「不存在」⇒ 用例全测不到它们要测
    的东西。
    """
    from app.models.project import Project, Workspace

    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db_session.add(ws)
    await db_session.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="批量测试",
        owner_company="测试业主",
        location="测试地点",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db_session.add(proj)
    await db_session.commit()
    await grant_project(BATCH_ACTOR_ID, proj.project_id, username="batch-actor")
    return proj


async def _make_draft(db: AsyncSession, proj, name: str, composition=None) -> Stream:
    """建一条 DRAFT 物流（绕过 API：service 层只关心状态与组成）。"""
    stream = Stream(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        stream_name=name,
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        source="MANUAL",
        phase="LIQUID",
        temp=80.0,
        press=200.0,
        mass_flow=1000.0,
        composition_json=composition if composition is not None else {"7732-18-5": 1.0},
        sign_status=StreamSignStatus.DRAFT,
        # ⚠️ `approval_depth` 是 Stream 上**唯一没有默认值**的 NOT NULL 列
        #   （cerebrum Do-Not-Repeat：写 DB fixture 前必查 NOT NULL 列）
        #   ⇒ 取值与 `StreamService.create` 一致（1 步校对）。
        approval_depth=1,
    )
    db.add(stream)
    await db.commit()
    await db.refresh(stream)
    return stream


async def test_batch_deduplicates_stream_ids(db_session, batch_project):
    """⚠️ Review Focus #1：同一批里重复的 id **只处理一次**，`total` 是去重后的条数。"""
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    result = await submit_batch(
        db_session,
        [s.stream_id, s.stream_id, s.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    assert result.total == 1
    assert len(result.succeeded) == 1
    assert len(result.failed) == 0


async def test_batch_success_moves_status_and_reports_transition(
    db_session, batch_project
):
    """正常路径：DRAFT → IN_APPROVAL，响应里 from/to 都给。"""
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    assert result.total == 1
    assert len(result.succeeded) == 1
    item = result.succeeded[0]
    assert item.stream_id == s.stream_id
    assert item.from_status == "DRAFT"
    assert item.to_status == "IN_APPROVAL"
    assert item.note is None

    await db_session.refresh(s)
    assert s.sign_status.value == "IN_APPROVAL"


async def test_batch_partial_success_does_not_roll_back_the_good_ones(
    db_session, batch_project
):
    """⚠️ Review Focus #4（D2 的全部意义）：一条失败**不回滚**成功的那些。

    失败样本：组成合计 98.7%（门禁拒）⇒ 状态不变；成功样本：正常转移。
    """
    from sqlalchemy import update

    from app.services.stream_batch_service import submit_batch

    good = await _make_draft(db_session, batch_project, "GOOD")
    bad = await _make_draft(db_session, batch_project, "BAD")
    await db_session.execute(
        update(Stream)
        .where(Stream.stream_id == bad.stream_id)
        .values(composition_json={"7732-18-5": 0.6, "7440-23-5": 0.387})
    )
    await db_session.commit()

    result = await submit_batch(
        db_session,
        [good.stream_id, bad.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    assert [i.stream_id for i in result.succeeded] == [good.stream_id]
    assert [i.stream_id for i in result.failed] == [bad.stream_id]
    assert result.failed[0].reason == "SIM_STREAM_COMPOSITION_OUT_OF_RANGE"

    await db_session.refresh(good)
    await db_session.refresh(bad)
    assert good.sign_status.value == "IN_APPROVAL", "成功的被失败的那条回滚了"
    assert bad.sign_status.value == "DRAFT", "失败的这条状态变了"


async def test_batch_already_in_approval_is_idempotent_success(db_session, batch_project):
    """⚠️ Review Focus #2（D5）：已 `IN_APPROVAL` ⇒ 记**成功** + `note`，且**不重复转移**。"""
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    s.sign_status = StreamSignStatus.IN_APPROVAL
    await db_session.commit()

    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    assert len(result.failed) == 0
    item = result.succeeded[0]
    assert item.note == "already_in_approval"
    assert item.from_status == "IN_APPROVAL"
    assert item.to_status == "IN_APPROVAL"


async def test_batch_reports_missing_stream_as_failed_item(db_session, batch_project):
    """不存在的 id ⇒ **该条**失败（`SIM_STREAM_NOT_FOUND`），整批**不**报错。"""
    from app.services.stream_batch_service import submit_batch

    result = await submit_batch(
        db_session,
        [uuid.uuid4()],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    assert result.total == 1
    assert len(result.succeeded) == 0
    assert result.failed[0].reason == "SIM_STREAM_NOT_FOUND"


async def test_batch_rejects_stream_in_non_submittable_status(db_session, batch_project):
    """已 `CHECKED`（不可再提交）⇒ 该条失败 `SIM_STREAM_INVALID_TRANSITION`。"""
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    s.sign_status = StreamSignStatus.CHECKED
    await db_session.commit()

    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    assert len(result.succeeded) == 0
    assert result.failed[0].reason == "SIM_STREAM_INVALID_TRANSITION"


async def test_batch_limit_exceeded_raises(db_session, batch_project):
    """D4：超过上限 ⇒ 整批拒（422 `SIM_STREAM_BATCH_LIMIT_EXCEEDED`），**不**部分执行。"""
    from app.core.errors import PcsError
    from app.services.stream_batch_service import submit_batch

    ids = [uuid.uuid4() for _ in range(3)]
    with pytest.raises(PcsError) as exc:
        await submit_batch(
            db_session,
            ids,
            actor_user_id=BATCH_ACTOR_ID,
            actor_role="DESIGNER",
            limit=2,
        )
    assert exc.value.code == "SIM_STREAM_BATCH_LIMIT_EXCEEDED"
    assert exc.value.status == 422


async def test_batch_limit_is_configurable(db_session, batch_project):
    """D4 的上限**取自系统参数**（`stream.batch_submit_limit`），不是写死的 100。"""
    from app.services.system_setting_service import get_setting_value, seed_defaults, update_batch

    await seed_defaults(db_session)
    await db_session.commit()
    await update_batch(
        db_session,
        {"stream.batch_submit_limit": 1},
        actor_user_id=BATCH_ACTOR_ID,
    )
    await db_session.commit()
    assert await get_setting_value(db_session, "stream.batch_submit_limit") == 1

    s = await _make_draft(db_session, batch_project, "S-1")
    s2 = await _make_draft(db_session, batch_project, "S-2")

    from app.core.errors import PcsError
    from app.services.stream_batch_service import submit_batch

    with pytest.raises(PcsError) as exc:
        await submit_batch(
            db_session,
            [s.stream_id, s2.stream_id],
            actor_user_id=BATCH_ACTOR_ID,
            actor_role="DESIGNER",
        )
    assert exc.value.code == "SIM_STREAM_BATCH_LIMIT_EXCEEDED"


async def test_dry_run_changes_nothing_and_writes_no_audit(db_session, batch_project):
    """⚠️ Review Focus #3（D6）：预演 ⇒ 状态不变、**审计表零新增**（连批次那条也没有）。"""
    from sqlalchemy import func, select

    from app.models.system import AuditLog
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    before = (
        await db_session.execute(select(func.count()).select_from(AuditLog))
    ).scalar_one()

    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
        dry_run=True,
    )

    assert result.dry_run is True
    assert len(result.succeeded) == 1
    assert result.succeeded[0].to_status == "IN_APPROVAL"

    await db_session.refresh(s)
    assert s.sign_status.value == "DRAFT", "预演改了状态"

    after = (
        await db_session.execute(select(func.count()).select_from(AuditLog))
    ).scalar_one()
    assert after == before, "预演写了审计"


async def test_dry_run_still_reports_failures(db_session, batch_project):
    """预演也要**报出失败项**（否则「预演」等于「说没事」）。"""
    from sqlalchemy import update

    from app.services.stream_batch_service import submit_batch

    bad = await _make_draft(db_session, batch_project, "BAD")
    await db_session.execute(
        update(Stream)
        .where(Stream.stream_id == bad.stream_id)
        .values(composition_json={"7732-18-5": 0.6, "7440-23-5": 0.387})
    )
    await db_session.commit()

    result = await submit_batch(
        db_session,
        [bad.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
        dry_run=True,
    )

    assert len(result.failed) == 1
    assert result.failed[0].reason == "SIM_STREAM_COMPOSITION_OUT_OF_RANGE"


# ---------------------------------------------------------------------------
# T2 补充：union 契约的三个断言（委员会 2026-11-03 · D5 裁决「必须加的三个测试」）
# ---------------------------------------------------------------------------


async def test_succeeded_item_requires_from_status():
    """成功项的 `from_status` **必填** —— 缺字段要抛 ValidationError。

    ⚠️ 这是「去掉中间类型」相对「保留 `_Outcome`」的核心优势之一：
    `_Outcome` 能构造出 `ok=True, from_status=None` 的非法状态（静态类型挡不住），
    union 的两个契约类型**每个字段都必填** ⇒ 非法状态构造不出来。
    """
    from pydantic import ValidationError

    from app.schemas.stream_batch import BatchSucceededItem

    with pytest.raises(ValidationError):
        BatchSucceededItem(
            status="succeeded",
            stream_id=uuid.uuid4(),
            to_status="IN_APPROVAL",
            note=None,
            # from_status 缺失
        )


async def test_batch_response_splits_by_status(db_session, batch_project):
    """成功的进 `succeeded`、失败的进 `failed`，**无交叉**（靠 `status` 判别）。"""
    from sqlalchemy import update

    from app.services.stream_batch_service import submit_batch

    good = await _make_draft(db_session, batch_project, "GOOD")
    bad = await _make_draft(db_session, batch_project, "BAD")
    await db_session.execute(
        update(Stream)
        .where(Stream.stream_id == bad.stream_id)
        .values(composition_json={"7732-18-5": 0.6, "7440-23-5": 0.387})
    )
    await db_session.commit()

    result = await submit_batch(
        db_session,
        [good.stream_id, bad.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    assert len(result.succeeded) == 1
    assert len(result.failed) == 1
    # ⚠️ **无交叉**：两张清单里的 `status` 必须各自纯粹
    assert all(item.status == "succeeded" for item in result.succeeded)
    assert all(item.status == "failed" for item in result.failed)
    assert result.succeeded[0].stream_id == good.stream_id
    assert result.failed[0].stream_id == bad.stream_id


async def test_submit_one_returns_contract_types():
    """⚠️ **结构性断言**：`_submit_one` 的返回类型**必须**是契约里的两个类型。

    这条不测行为、测**类型关系** ⇒ 保证「有人把 `_submit_one` 改成返回
    `_Outcome`（或别的中间类型）」时立刻变红 ⇒ 契约与实现**不会分叉**
    （字段定义只有一处）。
    """
    import inspect

    from app.services import stream_batch_service

    sig = inspect.signature(stream_batch_service._submit_one)
    return_type = str(sig.return_annotation)
    assert "BatchSucceededItem" in return_type, return_type
    assert "BatchFailedItem" in return_type, return_type


# ---------------------------------------------------------------------------
# T2 补充：三条「计划里写了分支但没写测试」的缺口（2026-11-03 eng review）
# ---------------------------------------------------------------------------


async def test_unexpected_error_becomes_failed_item_and_batch_continues(
    db_session, batch_project, monkeypatch
):
    """⚠️ 非预期异常 ⇒ 变成 `INTERNAL_ERROR` 的失败项，**且批次继续**。

    这是委员会 D5 刚加的兜底路径（`_submit_one` 的 `except Exception`）⇒
    必须有测试钉住两件事：① 不抛异常；② **后面的条目照常处理**。
    """
    from app.services import stream_batch_service

    good = await _make_draft(db_session, batch_project, "GOOD")
    boom = await _make_draft(db_session, batch_project, "BOOM")

    original = stream_batch_service.StreamService.transition

    async def exploding(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        stream_batch_service.StreamService, "transition", staticmethod(exploding)
    )

    result = await stream_batch_service.submit_batch(
        db_session,
        [boom.stream_id, good.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    # 两条都失败，但**没有异常冒泡**
    assert len(result.failed) == 2
    assert all(item.reason == "INTERNAL_ERROR" for item in result.failed)
    # ⚠️ 失败项**不泄露内部细节**
    assert all("boom" not in (item.detail or "") for item in result.failed)
    monkeypatch.setattr(
        stream_batch_service.StreamService, "transition", original
    )


async def test_single_item_role_forbidden_becomes_failed_item(db_session, batch_project):
    """⚠️ 单条**角色无权** ⇒ 该条失败 `SIM_STREAM_ROLE_FORBIDDEN`（批次继续）。

    ⚠️ HTTP 上走不到这条（端点 ACL 已经把 VIEWER 挡在外面）⇒
    但**服务层是公开 API** ⇒ 逐条的角色校验必须有测试。
    """
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="VIEWER",  # 不在 TRANSITION_ROLES[SUBMIT_FOR_CHECK] 里
    )

    assert len(result.succeeded) == 0
    assert result.failed[0].reason == "SIM_STREAM_ROLE_FORBIDDEN"


async def test_batch_audit_write_failure_still_returns_results(
    db_session, batch_project, monkeypatch
):
    """⚠️ **批次审计写失败** ⇒ 已提交的条目**不回滚**、仍返 207、响应带 `warning`。

    （委员会 2026-11-03 · D7 裁决的「遗漏项」：批次审计是**最后**单独写的，
    写失败**绝不能**把已提交的成果回滚掉 —— 那是 D2「部分成功」的成果。）
    """
    from app.services import stream_batch_service

    s = await _make_draft(db_session, batch_project, "S-1")

    class _BoomAudit:
        """只让**批次模块**用的 AuditService 抛错（状态机自己的审计不受影响）。"""

        def __init__(self, _db):
            pass

        async def write(self, **_kwargs):
            raise RuntimeError("audit down")

    monkeypatch.setattr(stream_batch_service, "AuditService", _BoomAudit)

    result = await stream_batch_service.submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    # ⚠️ 条目**已经提交**（状态真的变了）⇒ 不能因为批次审计失败而回滚
    await db_session.refresh(s)
    assert s.sign_status.value == "IN_APPROVAL", "批次审计失败把已提交的结果回滚了"
    # ⚠️ 但响应必须**如实**说「批次记录没写成」
    assert result.warning is not None
    assert "批次记录写入失败" in result.warning
    assert len(result.succeeded) == 1


async def test_failed_item_does_not_leak_its_partial_write_into_the_next_item(
    db_session, batch_project, monkeypatch
):
    """⚠️⚠️ **一条失败 ⇒ 它的部分写入绝不能被下一条的 commit 带走**。

    ## 缺陷形状

    `StreamService.transition` 的**成功路径**在 `state_machine.transition` 里
    **先 flush**（状态已写进 DB 的当前事务）**再 commit**。
    ⇒ 若 flush 之后、commit 之前抛**非预期**异常（最现实的：**审计写失败**）：

    1. 那一条的 `sign_status = IN_APPROVAL` **已经 flush 进事务**（未 commit）；
    2. 异常冒泡到 `_submit_one` 的 `except Exception` ⇒ 变成 `INTERNAL_ERROR`
       失败项 ⇒ **但没人回滚那个事务** ⇒ session 仍带着那条的脏写；
    3. **下一条**处理成功 ⇒ 它的 `transition` 调 `db.commit()`
       ⇒ ⚠️⚠️ **把上一条失败项的脏写一起提交了**。

    ⇒ 后果：**响应说这条失败，DB 里它却是 IN_APPROVAL** ⇒
    用户的界面上「失败」的那条，下次刷新就变成「审批中」⇒
    状态与响应**互相矛盾**，且没有任何审计（审计正是失败的原因）。

    ## 为什么这条断言是真的

    「下一条 commit 会带走上一条的脏写」⇒ 只有在**下一条也成功**时才会发生
    ⇒ 所以断言要**两条**、且第二条必须成功（用一条 GOOD 兜底）。
    """
    from app.services import state_machine
    from app.services.stream_batch_service import submit_batch

    bad = await _make_draft(db_session, batch_project, "BAD")
    good = await _make_draft(db_session, batch_project, "GOOD")

    # ⚠️ 让**状态机的审计写**在 flush 之后抛非预期异常 —— 这是 SUBMIT_FOR_CHECK
    #    **唯一现实存在**的 flush 后失败点（快照/恢复快照只对 INITIATE_CHANGE /
    #    REQUEST_REVERSAL 等转移触发）。
    # ⚠️ **先把 id 存下来**（失败项的实体在回滚后已过期 ⇒ 读属性会 lazy-load）。
    bad_id = bad.stream_id
    good_id = good.stream_id

    orig = state_machine.StateMachineService._write_audit

    async def boom_for_bad_only(self, *, resource_id, **kwargs):
        if resource_id == bad_id:
            raise RuntimeError("audit write failed after flush")
        return await orig(self, resource_id=resource_id, **kwargs)

    monkeypatch.setattr(
        state_machine.StateMachineService, "_write_audit", boom_for_bad_only
    )

    result = await submit_batch(
        db_session,
        [bad_id, good_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    # 失败的那条：响应里是失败项
    assert [i.stream_id for i in result.failed] == [bad_id]
    assert result.failed[0].reason == "INTERNAL_ERROR"

    # ⚠️⚠️ **关键**：失败的那条在 DB 里**必须仍是 DRAFT**
    #    （若被下一条的 commit 带走 ⇒ 它会是 IN_APPROVAL ⇒ 状态与响应矛盾）
    # ⚠️ 直接查**列**（不查实体）—— 同上，实体已过期。
    from sqlalchemy import select as sa_select

    bad_status = (
        await db_session.execute(
            sa_select(Stream.sign_status).where(Stream.stream_id == bad_id)
        )
    ).scalar_one()
    assert str(getattr(bad_status, "value", bad_status)) == "DRAFT", (
        f"失败项的状态变成了 {bad_status} ⇒ "
        "它的部分写入被下一条的 commit 一起提交了"
    )

    # 成功的那条不受影响（批次语义：一条失败不回滚其它条）
    good_status = (
        await db_session.execute(
            sa_select(Stream.sign_status).where(Stream.stream_id == good_id)
        )
    ).scalar_one()
    assert str(getattr(good_status, "value", good_status)) == "IN_APPROVAL"


async def test_precheck_lock_is_released_on_the_early_return_paths(
    db_session, batch_project
):
    """⚠️⚠️ **预检的行锁在「提前返回」路径上必须释放**（否则锁会**累积**）。

    ## 缺陷形状（整支分支评审的 Important #1）

    预检用 `select_stream_for_update` 取了 **`SELECT ... FOR UPDATE`**
    ⇒ 拿到的**行锁只在 COMMIT/ROLLBACK 时释放**（PG 语义）。
    而两条「提前返回」路径**直接 return，既不 commit 也不 rollback**：

    - **幂等命中**（已 `IN_APPROVAL`）；
    - **组成门禁拒**（`SIM_STREAM_COMPOSITION_OUT_OF_RANGE`）。

    ⇒ 那条的行锁**一直持有**，直到**后面某一条**的 `db.commit()` 顺带释放它
    ⇒ 期间**同时持有多把行锁** ⇒ 与模块 docstring 里那句
    「逐条 commit **天然只持一把锁 ⇒ 没有死锁面**」**矛盾**（假不变量）。

    ⇒ 真实后果：两个并发批次、**重叠的物流、顺序相反**、且都撞上提前返回
    ⇒ 经典的 A 持 1 等 2 / B 持 2 等 1 ⇒ 死锁环（PG 靠 `deadlock_timeout`
    中止一方 ⇒ 那一项对用户显示成 `INTERNAL_ERROR`）。

    ## 断言怎么写才有意义

    ⚠️ SQLite 把 `FOR UPDATE` 编译成空串 ⇒ **单测里测不到锁本身**。
    ⇒ 这里测**可观测的等价物**：**提前返回后事务必须已经结束**
    （`db.in_transaction()` 为 False）⇒ 事务结束 ⇒ 锁必已释放。
    （真锁在 PG 车道验证；这条守住「别让提前返回把事务开着」这个机制。）
    """
    from app.services import stream_batch_service

    # 幂等命中那条（已 IN_APPROVAL ⇒ 提前返回）
    hit = await _make_draft(db_session, batch_project, "HIT")
    hit.sign_status = StreamSignStatus.IN_APPROVAL
    await db_session.commit()
    hit_id = hit.stream_id

    await stream_batch_service._submit_one_inner(
        db_session,
        hit_id,
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
        dry_run=False,
    )

    assert not db_session.in_transaction(), (
        "幂等命中提前返回后事务仍然开着 ⇒ 那条的行锁仍然被持有 ⇒ "
        "锁会跨条目累积（与 docstring 断言的「只持一把锁」矛盾）"
    )


async def test_db_level_failure_does_not_poison_the_rest_of_the_batch(
    db_session, batch_project, monkeypatch
):
    """⚠️ **DB 级失败**（flush 失败）⇒ session 被污染 ⇒ **后续条目仍要能处理**。

    ## 为什么这条独立于上一条

    上一条是「**Python 级**异常」（审计写的 `RuntimeError`）⇒ session 没被污染。
    这条是「**DB 级**失败」（flush 真的失败）⇒ SQLAlchemy 把 session 标记成
    「需要 rollback」⇒ **之后任何 DB 操作都抛 `PendingRollbackError`**
    ⇒ 若不先 `rollback()`，**后面每一条都会失败** ⇒ 一条坏数据毁掉整批。

    ⇒ 断言：坏的那条失败 + **好的那条成功**（= 批次没有整体垮掉）。
    """
    from app.services import stream_batch_service
    from app.services.stream_batch_service import submit_batch

    bad = await _make_draft(db_session, batch_project, "BAD")
    good = await _make_draft(db_session, batch_project, "GOOD")
    bad_id = bad.stream_id
    good_id = good.stream_id

    # 让**批次自己的**审计写真的 flush 一行会失败的（`action` 是 NOT NULL）
    # ⇒ 真的把 session 弄成「需要 rollback」的状态。
    from app.models.system import AuditLog

    orig_write = stream_batch_service.AuditService.write

    async def boom_for_bad_only(self, **kwargs):
        if kwargs.get("resource_id") == bad_id:
            self.session.add(AuditLog(user_id=None, action=None, resource_type="Y"))
            await self.session.flush()  # ← 这里真的失败
        return await orig_write(self, **kwargs)

    monkeypatch.setattr(stream_batch_service.AuditService, "write", boom_for_bad_only)

    result = await submit_batch(
        db_session,
        [bad_id, good_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    # 坏的那条失败
    assert [i.stream_id for i in result.failed] == [bad_id]
    assert result.failed[0].reason == "INTERNAL_ERROR"

    # ⚠️⚠️ **关键**：好的那条**必须成功**（⇒ session 被回滚救回来了）
    assert [i.stream_id for i in result.succeeded] == [good_id]

    from sqlalchemy import select as sa_select

    bad_status = (
        await db_session.execute(
            sa_select(Stream.sign_status).where(Stream.stream_id == bad_id)
        )
    ).scalar_one()
    assert str(getattr(bad_status, "value", bad_status)) == "DRAFT"

    good_status = (
        await db_session.execute(
            sa_select(Stream.sign_status).where(Stream.stream_id == good_id)
        )
    ).scalar_one()
    assert str(getattr(good_status, "value", good_status)) == "IN_APPROVAL"


async def test_guard_db_failure_does_not_poison_the_rest_of_the_batch(
    db_session, batch_project, monkeypatch
):
    """⚠️ **项目守卫那条 DB 查询失败** ⇒ 后面每一条**仍要能处理**。

    ## 为什么单独一条（ce-code-review P1 #3 · bug-2148）

    项目守卫是**新增**的 DB 查询。它挂在**加锁读之后**、且兜底**不回滚**时：
    它一抛错 ⇒ 异常冒到 `_submit_one` 的兜底 ⇒ 只返回 INTERNAL_ERROR 而
    **没人回滚** ⇒ 事务被 abort ⇒ **后面每一条都失败**（D2「单条失败不影响
    其他」被打破）+ 行锁被持有。

    ⚠️ **必须造真的 DB 级失败**（不是 Python 异常）：Python 异常不会让事务
    进入「需要 rollback」状态 ⇒ 后面那条照样能跑 ⇒ 这条测试会**假绿**
    （变异实测：抛 `RuntimeError` 时旧代码也绿；查一张不存在的表也一样）。
    ⇒ 用**真的 flush 失败**（同 `test_db_level_failure_does_not_poison_the_rest_of_the_batch`
    的做法：插一行 `action=None` 撞 NOT NULL）⇒ session 被标记成
    「需要 rollback」⇒ 后面任何 DB 操作都抛 `PendingRollbackError`。
    """
    from app.models.system import AuditLog

    from app.services import stream_batch_service
    from app.services.stream_batch_service import submit_batch

    bad = await _make_draft(db_session, batch_project, "GUARD-BAD")
    good = await _make_draft(db_session, batch_project, "GUARD-GOOD")
    bad_id = bad.stream_id
    good_id = good.stream_id

    calls = {"n": 0}
    original = stream_batch_service.has_project_access

    async def boom_on_first_call(session, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            # ⚠️ **真的** DB 级失败 ⇒ 事务被 abort（session 需要 rollback）
            session.add(AuditLog(user_id=None, action=None, resource_type="Y"))
            await session.flush()  # ← 这里真的失败（action 是 NOT NULL）
        return await original(session, **kwargs)

    monkeypatch.setattr(stream_batch_service, "has_project_access", boom_on_first_call)

    result = await submit_batch(
        db_session,
        [bad_id, good_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    assert [i.stream_id for i in result.failed] == [bad_id]
    assert result.failed[0].reason == "INTERNAL_ERROR"
    # ⚠️⚠️ **关键**：好的那条**必须成功**（⇒ 事务被回滚救回来了）
    assert [i.stream_id for i in result.succeeded] == [good_id]


async def test_project_guard_rejection_happens_before_the_row_lock(
    db_session, batch_project, monkeypatch
):
    """⚠️ 跨项目条目 ⇒ **不能**对别人项目的行加过锁才拒绝。

    ## 为什么（ce-code-review P2 #9）

    守卫若在 `SELECT ... FOR UPDATE` **之后**才拒绝 ⇒ 只拥有项目 A 权限的
    调用方能短暂 `FOR UPDATE` 锁住**项目 B** 的物流行 ⇒ 阻塞 B 的写者
    （锁序侧信道）。

    ⇒ 断言：跨项目条目**根本没走到加锁读**（守卫先于加锁）。

    另外顺带钉住「守卫拒绝后事务已结束」（行锁不留着 ⇒ 锁不跨条目累积，
    与 bug-2135 的修复同族）。
    """
    from app.models.project import Project, Workspace
    from app.services import stream_batch_service
    from app.services.stream_batch_service import submit_batch

    # 另一个项目：**不给** BATCH_ACTOR_ID 授权 ⇒ 守卫必然拒绝
    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db_session.add(ws)
    await db_session.flush()
    other = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="未授权项目",
        owner_company="测试业主",
        location="测试地点",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db_session.add(other)
    await db_session.commit()
    foreign = await _make_draft(db_session, other, "FOREIGN")

    # spy 批次模块的**加锁读**（与 `test_batch_submit_uses_the_locked_select`
    # 同款接线：必须 spy 批次模块的引用，spy 服务层那个会被内部调用满足）
    seen: list[uuid.UUID] = []
    original_lock = stream_batch_service.select_stream_for_update

    async def spy(db, stream_id):
        seen.append(stream_id)
        return await original_lock(db, stream_id)

    monkeypatch.setattr(stream_batch_service, "select_stream_for_update", spy)

    result = await submit_batch(
        db_session,
        [foreign.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    # 跨项目 ⇒ 按「不存在」处理（逐字同形 ⇒ 不可枚举）
    assert [i.stream_id for i in result.failed] == [foreign.stream_id]
    assert result.failed[0].reason == "SIM_STREAM_NOT_FOUND"
    assert result.failed[0].detail == f"物流 {foreign.stream_id} 不存在"

    # ⚠️⚠️ **关键**：守卫拒绝前**不能**对别人的行加过锁
    assert seen == [], (
        f"跨项目条目竟然先加了行锁才拒绝：{seen} ⇒ 只拥有别项目权限的调用方"
        "能锁住别人项目的行（锁序侧信道）"
    )

    assert not db_session.in_transaction(), (
        "守卫拒绝后事务仍然开着 ⇒ 那条的行锁仍然被持有 ⇒ "
        "锁会跨条目累积（与 docstring 断言的「只持一把锁」矛盾）"
    )


async def test_commit_failure_itself_becomes_a_failed_item(
    db_session, batch_project, monkeypatch
):
    """⚠️ **`db.commit()` 本身失败** ⇒ 该条失败 + **状态没变** + 后续条目照常。

    ## 为什么这条与前两条并列

    转移的三个失败时点各有一种后果，**都要**有断言钉住：

    | 失败时点 | 数据状态 | 应报 |
    |---|---|---|
    | flush 之后、commit 之前（审计写失败） | 未提交 | **失败** |
    | commit 失败 | 未提交 | **失败** |
    | commit 成功、refresh 挂掉 | **已提交** | **成功** |

    ⚠️ 前两条已有；**commit 失败**这条原先**没有** ⇒ 裸奔。
    """
    from app.services import stream_service
    from app.services.stream_batch_service import submit_batch

    bad = await _make_draft(db_session, batch_project, "BAD")
    good = await _make_draft(db_session, batch_project, "GOOD")
    bad_id = bad.stream_id
    good_id = good.stream_id

    # 让 `transition` 的 **commit** 失败（DB 抖动 / 磁盘满 / 约束冲突）
    orig = stream_service.StreamService.transition

    async def boom_on_commit(db, stream_id, **kwargs):
        # 先让原 transition 跑完（它自己 commit）—— 不行，那已经成功了。
        # ⇒ 改成：跑原 transition 的**逻辑**但拦掉 commit。
        #   最简单的做法：在原 transition 之前注入一个「commit 必炸」的 session。
        class _BoomCommit:
            def __init__(self, real):
                self._real = real

            def __getattr__(self, name):
                return getattr(self._real, name)

            async def commit(self):
                raise RuntimeError("commit failed")

            async def rollback(self):
                return await self._real.rollback()

        boom_db = _BoomCommit(db)
        # ⚠️ 原 transition 内部会 `db.refresh(result)` ⇒ 我们的替身要透传
        return await orig(boom_db, stream_id, **kwargs)

    monkeypatch.setattr(
        stream_service.StreamService, "transition", staticmethod(boom_on_commit)
    )

    result = await submit_batch(
        db_session,
        [bad_id, good_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    # 两条都失败（commit 对**每一条**都失败）
    assert len(result.succeeded) == 0
    assert len(result.failed) == 2
    assert all(item.reason == "INTERNAL_ERROR" for item in result.failed)

    from sqlalchemy import select as sa_select

    for sid in (bad_id, good_id):
        status = (
            await db_session.execute(
                sa_select(Stream.sign_status).where(Stream.stream_id == sid)
            )
        ).scalar_one()
        assert str(getattr(status, "value", status)) == "DRAFT", (
            f"commit 失败的那条状态变成了 {status} ⇒ 状态变了"
        )


async def test_item_whose_commit_succeeded_is_reported_as_success(
    db_session, batch_project, monkeypatch
):
    """⚠️ **提交已经成功**、只是后续步骤失败 ⇒ 必须报**成功**（不是失败）。

    ## 为什么这条与上一条是一对

    `StreamService.transition` 的顺序是 **flush → commit → refresh** ⇒
    若失败发生在 **commit 之后**（`db.refresh` 挂掉：连接被掐 / 行被并发删），
    数据**已经落库** ⇒ 报「失败」是**假的** ⇒
    用户看到「失败 1」但那条其实已经在审批中 ⇒ 与响应矛盾。

    ⇒ 失败后必须**读回真实状态**：是 `IN_APPROVAL` ⇒ 老实报**成功**。
    """
    from app.services import stream_service
    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")
    s_id = s.stream_id

    # 让 `transition` 在 **commit 之后**失败：`db.refresh` 抛错。
    # ⚠️ `transition` 是 **staticmethod** ⇒ 签名里没有 self。
    orig = stream_service.StreamService.transition

    async def boom_after_commit(db, stream_id, **kwargs):
        result = await orig(db, stream_id, **kwargs)
        # ⚠️ 原 transition 已经 commit（数据已落库）⇒ 现在抛错
        raise RuntimeError("refresh failed after commit")

    monkeypatch.setattr(
        stream_service.StreamService, "transition", staticmethod(boom_after_commit)
    )

    result = await submit_batch(
        db_session,
        [s_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    # ⚠️ 数据已提交 ⇒ 必须报**成功**（报失败 = 状态与响应矛盾）
    assert [i.stream_id for i in result.succeeded] == [s_id]
    assert not result.failed

    from sqlalchemy import select as sa_select

    status = (
        await db_session.execute(
            sa_select(Stream.sign_status).where(Stream.stream_id == s_id)
        )
    ).scalar_one()
    assert str(getattr(status, "value", status)) == "IN_APPROVAL"


async def test_batch_limit_treats_boolean_as_garbage(db_session, batch_project):
    """⚠️ **布尔值不是数字** ⇒ 上限回落默认值（不是 1）。

    ## 缺陷形状

    `_batch_limit` 用 `int(raw)` 解析系统参数 ⇒ `int(True) == 1`
    （bool 是 int 的子类）⇒ 管理员若把这个参数存成布尔 `true`，
    批次上限会**静默变成 1** ⇒ 用户批量提交 2 条就被 422 拒
    ⇒ 而参数页上显示的是「true」⇒ 用户完全看不懂为什么被拒。

    ⇒ 修法：`int(raw)` 之前先排除 bool（`isinstance(raw, bool)`）。
    ⚠️ **不能靠 `int()` 抛异常来兜** —— `int(True)` **不抛** ⇒ 兜不住。
    """
    from app.services.system_setting_service import seed_defaults, update_batch
    from app.services.stream_batch_service import submit_batch

    await seed_defaults(db_session)
    await db_session.commit()

    s = await _make_draft(db_session, batch_project, "S-1")
    s2 = await _make_draft(db_session, batch_project, "S-2")

    # ⚠️ 存成布尔 `true`（JSONB 允许）⇒ 上限**不该**变成 1
    await update_batch(
        db_session, {"stream.batch_submit_limit": True}, actor_user_id=BATCH_ACTOR_ID
    )
    await db_session.commit()

    # ⇒ 两条应当**都成功**（上限回落成 100 ⇒ 2 条远不到上限）
    result = await submit_batch(
        db_session,
        [s.stream_id, s2.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )
    assert len(result.succeeded) == 2, (
        f"上限被布尔值静默变成 1 ⇒ 两条里只成功 {len(result.succeeded)} 条"
    )


async def test_batch_limit_falls_back_when_value_is_garbage(db_session, batch_project):
    """⚠️ 上限的**值不是整数** / **小于 1** ⇒ 回落默认值（不崩、不放行无上限）。"""
    from app.services.system_setting_service import seed_defaults, update_batch

    await seed_defaults(db_session)
    await db_session.commit()

    from app.services.stream_batch_service import submit_batch

    s = await _make_draft(db_session, batch_project, "S-1")

    # ① 值不是整数 ⇒ 回落 100（这条能过 ⇒ 上限**没有**变成「无上限」）
    await update_batch(
        db_session, {"stream.batch_submit_limit": "abc"}, actor_user_id=BATCH_ACTOR_ID
    )
    await db_session.commit()
    result = await submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )
    assert len(result.succeeded) == 1, "上限读成垃圾值时不该整批失败"

    # ② limit < 1 ⇒ 兜底成 1（不是 0 ⇒ 那样任何批次都会被拒）
    await update_batch(
        db_session, {"stream.batch_submit_limit": 0}, actor_user_id=BATCH_ACTOR_ID
    )
    await db_session.commit()
    from app.core.errors import PcsError

    # ⚠️ **必须两条不同的物流** —— 同一个 id 传两次会被**去重**（D5）⇒
    #   去重后只剩 1 条 ⇒ 永远超不过上限 ⇒ 断言不可能成立。
    s2 = await _make_draft(db_session, batch_project, "S-2")
    with pytest.raises(PcsError) as exc:
        await submit_batch(
            db_session,
            [s.stream_id, s2.stream_id],
            actor_user_id=BATCH_ACTOR_ID,
            actor_role="DESIGNER",
        )
    assert exc.value.code == "SIM_STREAM_BATCH_LIMIT_EXCEEDED"


# ---------------------------------------------------------------------------
# T4：行锁（方言级 + 接线）
# ---------------------------------------------------------------------------


async def test_locked_select_emits_for_update_on_postgres():
    """方言级断言：加锁那条 SELECT 在 **PG 方言**下真的带 `FOR UPDATE`。

    ## 为什么是方言级而不是「真跑 PG 并发」

    - in-memory SQLite 把 `with_for_update()` **编译成空串**（压根没有锁），
      且 StaticPool 共享连接 ⇒ 真并发在本仓单测 fixture 上**不可表达**；
    - 真 PG 双连接并发 ⇒ `scripts/pytest_pg.sh` 车道（见同目录的
      `test_stream_batch_concurrency_pg.py`）。

    ⇒ 这里钉**机制**（SQL 形状），下面两条钉「接线」与「C-1 的修复点」。
    """
    from sqlalchemy.dialects import postgresql

    from app.services.stream_service import build_stream_for_update_stmt

    stmt = build_stream_for_update_stmt(uuid.uuid4())
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql, sql


async def test_locked_select_sets_populate_existing(
    db_session, batch_project, monkeypatch
):
    """⚠️ **C-1 的修复点必须有断言钉住**（委员会 2026-11-03 · D4 裁决）。

    **为什么这条比「抽 helper」本身更重要**：SQLite 把 `FOR UPDATE` 编译掉
    ⇒ 删掉 `populate_existing=True` 后测试**仍然绿**（行为看着正常）⇒
    回归会以另一种形式回来（并发时两个提交都基于旧状态通过 ⇒ 行锁形同虚设）。

    ⇒ 这里断言**生产路径实际执行的那条语句**带 `populate_existing=True`
    （spy 抓的是 `build_stream_for_update_stmt` 的返回值 ⇒ 抓的是真语句，
    不是测试自己重抄的一份）。
    """
    from app.services import stream_service

    seen: list[Any] = []
    original = stream_service.build_stream_for_update_stmt

    def spy(stream_id):
        stmt = original(stream_id)
        seen.append(stmt)
        return stmt

    monkeypatch.setattr(stream_service, "build_stream_for_update_stmt", spy)

    s = await _make_draft(db_session, batch_project, "S-1")
    await stream_service.select_stream_for_update(db_session, s.stream_id)

    assert seen, "根本没走加锁读"
    for stmt in seen:
        assert stmt.get_execution_options().get("populate_existing") is True, (
            "加锁读**没有** populate_existing ⇒ C-1 的修复被删了 ⇒ "
            "并发时两个提交都会基于旧状态通过（行锁形同虚设）"
        )


async def test_batch_submit_uses_the_locked_select(
    db_session, batch_project, monkeypatch
):
    """接线断言：**批次自己的预检**走的是**加锁读**（不是随便一条 SELECT）。

    ⚠️ **必须 spy 批次模块的引用**（`stream_batch_service.select_stream_for_update`），
    **不能** spy `stream_service.build_stream_for_update_stmt` ——
    后者会被 `StreamService.transition` 的**内部**调用满足 ⇒
    批次的预检即使绕开加锁读，这条断言**照样绿**（变异实测抓到的假闸门）。
    ⇒ spy 批次模块 ⇒ 预检一旦不调它 ⇒ 计数为 0 ⇒ **必红**。
    """
    from app.services import stream_batch_service

    seen: list[uuid.UUID] = []
    original = stream_batch_service.select_stream_for_update

    async def spy(db, stream_id):
        seen.append(stream_id)
        return await original(db, stream_id)

    monkeypatch.setattr(stream_batch_service, "select_stream_for_update", spy)

    s = await _make_draft(db_session, batch_project, "S-1")
    await stream_batch_service.submit_batch(
        db_session,
        [s.stream_id],
        actor_user_id=BATCH_ACTOR_ID,
        actor_role="DESIGNER",
    )

    assert seen == [s.stream_id], f"批次的预检没走加锁读：{seen}"
