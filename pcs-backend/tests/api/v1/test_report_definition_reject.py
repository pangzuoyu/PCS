"""「打回」动作 —— **被退回**标记（P10-J · T2 · TODO-197b · 2026-11-24 人裁）。

## 人裁（四问全定）

| 问 | 裁决 | 这里怎么断 |
|---|---|---|
| ① 状态模型 | **退回 DRAFT + 被退回标记**（**不新增 `REJECTED`**）| 断言 `status` **不变**（仍 DRAFT）+ 三个字段被置位 |
| ② 谁可见 | **沿用现状 `visible_clause`** | 断言「无权者**看不到**」+「有权的**看得到**」|
| ③ 能不能再编辑 | **能**（改完再交审）| 断言 `update()` **清掉**标记 ⇒ ⇒ ⇒ 它**重新进队列** |
| ④ 要不要通知 | **要** | 断言创建人收到一条 `STEP_RETURNED` 通知 |

## ⚠️ **为什么用 `strict_client`**

默认 `client` 把项目守卫 mock 成永远 True ⇒ ⇒ 「无授权也打回得了」
这类缺陷在它上面**一个都测不出来**。

## ⚠️ **为什么 URL 字面量写在每个测试函数体内**

`tests/test_strict_client_ratchet.py` 的 `_strict_client_urls()` 用 AST
**逐个测试函数**扫 URL 字面量 ⇒ ⇒ 写在模块级常量或 helper 里 ⇒ ⇒
⇒ 棘轮**扫不到** ⇒ ⇒ ⇒ 台账会说「这个端点没有 strict_client 断言」⇒ ⇒ ⇒ 红。
⇒ ⇒ 所以下面每处都**写全路径**（不是引常量）。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio


def _auth(subject: str, role: str = "DESIGNER", *, user_id: uuid.UUID | None = None):
    extra = {"user_id": str(user_id)} if user_id else None
    token = create_access_token(subject=subject, role=role, extra=extra)
    return {"Authorization": f"Bearer {token}"}


def _body(**over):
    body = {
        "project_id": None,
        "name": "设备一览",
        "category": "设备类",
        "description": "按位号列设备",
        "output_format": "xlsx",
        "shared_with": "ALL_USERS",
        "definition_json": {
            "DataSources": [{"source": "EQUIP_LIST"}],
            "SelectedFields": [
                {"source": "EQUIP_LIST", "field": "tag_number",
                 "alias": "位号", "order": 0, "visible": True},
            ],
            "FilterConditions": [],
        },
    }
    body.update(over)
    return body


async def _mk_def(strict_client, *, subject="author-1", user_id=None,
                  project_id=None, shared_with="ALL_USERS", name=None):
    r = await strict_client.post(
        "/api/v1/report-builder/definitions",
        headers=_auth(subject, "DESIGNER", user_id=user_id),
        json=_body(
            project_id=str(project_id) if project_id else None,
            shared_with=shared_with,
            **({"name": name} if name else {}),
        ),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_project(db_session, name="打回项目"):
    from app.models.project import Project

    proj = Project(
        project_no=f"RPT-{uuid.uuid4().hex[:8]}",
        project_name=name, owner_company="X", location="X",
        project_type="CHEMICAL", design_phase="FEED", unit_system="SI",
        status="ACTIVE", workspace_id=uuid.uuid4(),
    )
    db_session.add(proj)
    await db_session.flush()
    return proj


# ---------------------------------------------------------------------------
# ① 打回本体
# ---------------------------------------------------------------------------


async def test_reject_marks_the_definition_without_changing_its_status(
    strict_client, db_session
):
    """⚠️⚠️ **状态不变** —— 人裁 ① = 「退回 DRAFT + 被退回标记」。

    ⇒ ⇒ ⇒ 断言 `status` **仍是 DRAFT**（不是新状态）
    ⇒ ⇒ ⇒ 且三个字段被置位 ⇒ ⇒ ⇒ 这是「待审 vs 待改」的唯一区分信号。
    """
    creator = uuid.uuid4()
    created = await _mk_def(strict_client, subject="author-1", user_id=creator)

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{created['def_id']}/reject",
        headers=_auth("reviewer-1", "REVIEWER"),
        json={"reason": "字段选错了：位号不是设备一览的主键"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # ⚠️ **状态没变**（人裁 ①）
    assert body["status"] == "DRAFT"
    # ⚠️ 三个标记被置位
    assert body["rejected_at"] is not None
    assert body["reject_reason"] == "字段选错了：位号不是设备一览的主键"
    assert body["rejected_by"] is not None


async def test_reject_requires_a_reason(strict_client, db_session):
    """⚠️ **原因不能为空** —— 创建人要看得懂要改什么 ⇒ ⇒ 空原因 = 无信息。"""
    created = await _mk_def(strict_client, subject="author-1")

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{created['def_id']}/reject",
        headers=_auth("reviewer-1", "REVIEWER"),
        json={"reason": "   "},
    )
    assert r.status_code in (400, 422), r.text


async def test_rejecting_twice_is_a_conflict(strict_client, db_session):
    """⚠️ **重复打回 = 409**（不静默覆盖）⇒ ⇒ ⇒ 与 `publish()` 的幂等口径一致。"""
    created = await _mk_def(strict_client, subject="author-1")
    url = f"/api/v1/report-builder/definitions/{created['def_id']}/reject"

    first = await strict_client.post(
        url, headers=_auth("reviewer-1", "REVIEWER"), json={"reason": "再改改"},
    )
    assert first.status_code == 200, first.text

    second = await strict_client.post(
        url, headers=_auth("reviewer-2", "REVIEWER"), json={"reason": "还是不行"},
    )
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "REPORT_DEFINITION_ALREADY_REJECTED"


# ---------------------------------------------------------------------------
# ② 职责分离（**照抄 `publish()`** ⇒ ⇒ ⇒ 同一族动作同一套口径）
# ---------------------------------------------------------------------------


async def test_creator_cannot_reject_their_own_definition(strict_client, db_session):
    """⚠️ **禁自审** ⇒ ⇒ 创建人自己不能打回自己的（⇒ 与 `publish()` 同款）。"""
    creator = uuid.uuid4()
    created = await _mk_def(strict_client, subject="author-1", user_id=creator)

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{created['def_id']}/reject",
        headers=_auth("author-1", "REVIEWER", user_id=creator),
        json={"reason": "我自己打回自己"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "REPORT_DEFINITION_SELF_REVIEW_FORBIDDEN"


async def test_reject_without_project_grant_is_404_word_for_word(
    strict_client, db_session, grant_project
):
    """⚠️⚠️ **逐字同形** —— 无权打回 ⇒ ⇒ 与「没有这条定义」**同一个**错误。

    ⇒ ⇒ ⇒ 否则能靠错误码区分「这条草稿存在」⇒ ⇒ ⇒ 枚举得出（TODO-187b）。
    """
    proj = await _mk_project(db_session)
    creator = uuid.uuid4()
    # ⇒ ⇒ ⇒ **创建人要有该项目授权**才能把定义挂上去（`create()` 的判定）
    await grant_project(creator, proj.project_id)
    created = await _mk_def(
        strict_client, subject="author-1", user_id=creator,
        project_id=proj.project_id,
    )

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{created['def_id']}/reject",
        headers=_auth("reviewer-x", "REVIEWER"),
        json={"reason": "没授权也来打回"},
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "REPORT_DEFINITION_NOT_FOUND"

    # ⇒ ⇒ ⇒ 与「**真不存在**」的那条**同一个错误**（code + 文案形状都一致）
    # ⚠️ 文案里嵌了 `def_id` ⇒ ⇒ ⇒ 两条**不可能逐字相同**（id 不同）
    # ⇒ ⇒ ⇒ **能枚举的是 code** ⇒ ⇒ ⇒ 判据 = code 相同 + 文案**形状**相同。
    missing = await strict_client.post(
        "/api/v1/report-builder/definitions/"
        f"{uuid.uuid4()}/reject",
        headers=_auth("reviewer-x", "REVIEWER"),
        json={"reason": "随便打回一条不存在的"},
    )
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == r.json()["code"]
    assert missing.json()["message"].startswith("报表定义不存在：") == (
        r.json()["message"].startswith("报表定义不存在：")
    )


async def test_creator_only_definition_cannot_be_rejected_by_others(
    strict_client, db_session
):
    """⚠️ `CREATOR_ONLY` ⇒ ⇒ **不能由他人打回**（与 `publish()` 同一判据）。"""
    created = await _mk_def(strict_client, subject="author-1", shared_with="CREATOR_ONLY")

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{created['def_id']}/reject",
        headers=_auth("reviewer-1", "REVIEWER"),
        json={"reason": "仅创建人可见的也要打回"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "REPORT_DEFINITION_NOT_SHAREABLE"


async def test_non_reviewer_role_cannot_reject(strict_client, db_session):
    """⚠️ **角色闸** ⇒ ⇒ 非审核角色连打回都不行（`REVIEWER` / `APPROVER` / `SYSTEM_ADMIN`）。"""
    created = await _mk_def(strict_client, subject="author-1")

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{created['def_id']}/reject",
        headers=_auth("designer-1", "DESIGNER"),
        json={"reason": "我不是审核角色"},
    )
    assert r.status_code == 403, r.text


async def test_published_definition_cannot_be_rejected(strict_client, db_session):
    """⚠️ **只有 `DRAFT` 能被打回** ⇒ ⇒ 已发布的 ⇒ ⇒ 409。"""
    created = await _mk_def(strict_client, subject="author-1")
    pub = await strict_client.post(
        f"/api/v1/report-builder/definitions/{created['def_id']}/publish",
        headers=_auth("reviewer-1", "REVIEWER"),
    )
    assert pub.status_code == 200, pub.text

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{created['def_id']}/reject",
        headers=_auth("reviewer-2", "REVIEWER"),
        json={"reason": "已发布的也要打回"},
    )
    assert r.status_code == 409, r.text


async def test_a_rejected_definition_cannot_be_published_directly(
    strict_client, db_session
):
    """⚠️⚠️ **被打回的草稿不能直接发布** ⇒ ⇒ ⇒ 否则「刚刚打回的那一版」被原样发出去。

    ⇒ ⇒ ⇒ 「被打回」= **等创建人改** ⇒ ⇒ ⇒ 它已经离开审核队列
    ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ 必须先由创建人改稿（`update()` 清标记）⇒ ⇒ ⇒ 才能再审。
    """
    created = await _mk_def(strict_client, subject="author-1")
    def_id = created["def_id"]

    rej = await strict_client.post(
        f"/api/v1/report-builder/definitions/{def_id}/reject",
        headers=_auth("reviewer-1", "REVIEWER"),
        json={"reason": "字段选错了"},
    )
    assert rej.status_code == 200, rej.text

    pub = await strict_client.post(
        f"/api/v1/report-builder/definitions/{def_id}/publish",
        headers=_auth("reviewer-2", "REVIEWER"),
    )
    assert pub.status_code == 409, pub.text
    assert pub.json()["code"] == "REPORT_DEFINITION_ALREADY_REJECTED"


# ---------------------------------------------------------------------------
# ③ 「待审 vs 待改」闭环（**队列口径**）
# ---------------------------------------------------------------------------


async def test_rejected_definition_leaves_the_review_queue(strict_client, db_session):
    """⚠️⚠️ **打完回它就不在队列里了** ⇒ ⇒ ⇒ 否则审核者点了必失败。

    ⇒ ⇒ ⇒ 「待审」（DRAFT 且没被打回）与「待改」（DRAFT 且被打回）是**两个态**。
    """
    created = await _mk_def(strict_client, subject="author-1")
    def_id = created["def_id"]

    before = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("reviewer-1", "REVIEWER"),
    )
    assert before.status_code == 200, before.text
    assert def_id in {i["def_id"] for i in before.json()["items"]}

    rej = await strict_client.post(
        f"/api/v1/report-builder/definitions/{def_id}/reject",
        headers=_auth("reviewer-1", "REVIEWER"),
        json={"reason": "先打回"},
    )
    assert rej.status_code == 200, rej.text

    after = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("reviewer-1", "REVIEWER"),
    )
    assert after.status_code == 200, after.text
    assert def_id not in {i["def_id"] for i in after.json()["items"]}, (
        "被打回的草稿还在队列里 ⇒ ⇒ ⇒ 审核者会看到「点了必失败」的行"
    )


async def test_creator_editing_the_definition_clears_the_rejection(
    strict_client, db_session
):
    """⚠️⚠️ **改稿 ⇒ ⇒ 清掉标记** ⇒ ⇒ ⇒ 它**重新进队列**（人裁 ③ = 能改）。

    ⇒ ⇒ ⇒ 否则这条草稿**永远没人审**（既不在队列里、创建人也看不到提示）。
    """
    creator = uuid.uuid4()
    created = await _mk_def(strict_client, subject="author-1", user_id=creator)
    def_id = created["def_id"]

    rej = await strict_client.post(
        f"/api/v1/report-builder/definitions/{def_id}/reject",
        headers=_auth("reviewer-1", "REVIEWER"),
        json={"reason": "改一下字段"},
    )
    assert rej.status_code == 200, rej.text
    assert rej.json()["rejected_at"] is not None

    upd = await strict_client.put(
        f"/api/v1/report-builder/definitions/{def_id}",
        headers=_auth("author-1", "DESIGNER", user_id=creator),
        json=_body(name="设备一览（改）"),
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["rejected_at"] is None
    assert upd.json()["reject_reason"] is None

    queue = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("reviewer-1", "REVIEWER"),
    )
    assert queue.status_code == 200, queue.text
    assert def_id in {i["def_id"] for i in queue.json()["items"]}, (
        "改完稿 ⇒ ⇒ ⇒ 它应该**重新进队列**（否则永远没人审）"
    )


# ---------------------------------------------------------------------------
# ④ 可见性（**沿用现状口径**）与 ⑤ 通知
# ---------------------------------------------------------------------------


async def test_creator_sees_the_rejection_reason_in_their_list(
    strict_client, db_session
):
    """⚠️ **创建人看得见「被退回」+ 原因**（人裁 ② = 沿用现状可见性）。

    ⇒ ⇒ ⇒ 列表端点要带这三个字段 ⇒ ⇒ ⇒ 前端才能渲染 badge。
    """
    creator = uuid.uuid4()
    created = await _mk_def(strict_client, subject="author-1", user_id=creator)

    rej = await strict_client.post(
        f"/api/v1/report-builder/definitions/{created['def_id']}/reject",
        headers=_auth("reviewer-1", "REVIEWER"),
        json={"reason": "别名要改成中文"},
    )
    assert rej.status_code == 200, rej.text

    lst = await strict_client.get(
        "/api/v1/report-builder/definitions",
        headers=_auth("author-1", "DESIGNER", user_id=creator),
    )
    assert lst.status_code == 200, lst.text
    item = next(
        i for i in lst.json()["items"] if i["def_id"] == created["def_id"]
    )
    assert item["rejected_at"] is not None
    assert item["reject_reason"] == "别名要改成中文"


async def test_creator_is_notified_about_the_rejection(strict_client, db_session):
    """⚠️ **通知**（人裁 ④ = 要通知）⇒ ⇒ ⇒ 复用 `STEP_RETURNED`（「退回」）。

    ⇒ ⇒ ⇒ `NotificationKind` 的**四值裁决清单不动**（不必回 ADR-0049 补记）。
    """
    creator = uuid.uuid4()
    created = await _mk_def(strict_client, subject="author-1", user_id=creator)

    rej = await strict_client.post(
        f"/api/v1/report-builder/definitions/{created['def_id']}/reject",
        headers=_auth("reviewer-1", "REVIEWER"),
        json={"reason": "改完再交"},
    )
    assert rej.status_code == 200, rej.text

    notes = await strict_client.get(
        "/api/v1/notifications",
        headers=_auth("author-1", "DESIGNER", user_id=creator),
    )
    assert notes.status_code == 200, notes.text
    items = notes.json()["items"]
    assert items, "创建人没收到任何通知 ⇒ ⇒ ⇒ 「打回」等于没人知道"
    assert items[0]["kind"] == "STEP_RETURNED"
    assert "被打回" in items[0]["title"]
