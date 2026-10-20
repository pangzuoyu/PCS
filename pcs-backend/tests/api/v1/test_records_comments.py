"""记录批注测试（P9A B4c）。

⚠️ **本轮新增一张表** `record_comments`：计划只列了 B0 一个迁移，
但 `comments` 端点要落库而全仓 `grep "class Comment"` 零命中 ——
不建表就只能返回「假批注」（响应成功但刷新就没了），
那比没有这个端点更坏：用户以为意见记下来了。

## 批注是给人看的，不是给状态机看的

ADR-0047 §① 明写「不写『打开页面』『查看』等读行为」—— 批注**不是**工作流进度，
所以本端点**不写** `workflow_progress`。ADR-0047 §后果 那句「3 个写入点若超出
这个数，说明有第四类工作流被漏登记」在这里正是要防的事。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PipingResult
from app.models.enums import RecordSignStatus9

pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth(sample_user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {sample_user_token}"}


async def _make_record(
    client, auth, db_session: AsyncSession, project_id, workspace, *, line_no="P-4001"
) -> PipingResult:
    resp = await client.post(
        "/api/v1/records/piping",
        headers=auth,
        params={"workspace_id": str(workspace.workspace_id)},
        json={"project_id": str(project_id), "line_no": line_no},
    )
    assert resp.status_code == 200, resp.text
    rec = await db_session.get(PipingResult, uuid.UUID(resp.json()["pipe_id"]))
    rec.sign_status = RecordSignStatus9.CHECKED
    await db_session.commit()
    await db_session.refresh(rec)
    return rec


def _url(rec, suffix: str = "") -> str:
    return f"/api/v1/records/PipingResult/{rec.pipe_id}/comments{suffix}"


async def _post(client, auth, rec, body: str = "这里的数据要再核对一遍"):
    return await client.post(_url(rec), headers=auth, json={"body": body})


class TestWriteComment:
    async def test_comment_is_stored_with_author(
        self, client, auth, db_session, project_id, workspace
    ):
        from app.models.record_comment import RecordComment

        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await _post(client, auth, rec)

        assert resp.status_code == 200, resp.text
        rows = (await db_session.execute(select(RecordComment))).scalars().all()
        assert len(rows) == 1
        assert rows[0].body == "这里的数据要再核对一遍"
        assert rows[0].record_type == "PipingResult"
        assert rows[0].record_id == rec.pipe_id
        assert rows[0].author_id is not None

    async def test_reject_empty_body(self, client, auth, db_session, project_id, workspace):
        """空批注 ⇒ 422。

        空行会进列表并占位，而列表是要给别人看的意见 ——
        一屏空行等于这一屏没内容，却让人以为「有人回过」。
        """
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await _post(client, auth, rec, body="")

        assert resp.status_code == 422, resp.text

    async def test_reject_whitespace_only_body(
        self, client, auth, db_session, project_id, workspace
    ):
        """纯空白也要拒 —— `min_length=1` 不管 `"   "`。"""
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await _post(client, auth, rec, body="   \n\t ")

        assert resp.status_code == 422, resp.text

    async def test_oversized_body_is_rejected(
        self, client, auth, db_session, project_id, workspace
    ):
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await _post(client, auth, rec, body="x" * 5001)

        assert resp.status_code == 422, resp.text

    async def test_comment_on_unknown_record_is_404_with_code(self, client, auth):
        """404 必须带 code —— 只断言 404 会在端点不存在时就绿。"""
        resp = await client.post(
            f"/api/v1/records/PipingResult/{uuid.uuid4()}/comments",
            headers=auth, json={"body": "x"},
        )

        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "RECORD_NOT_FOUND"


class TestListComments:
    async def test_comments_are_paginated(
        self, client, auth, db_session, project_id, workspace
    ):
        rec = await _make_record(client, auth, db_session, project_id, workspace)
        for i in range(5):
            assert (await _post(client, auth, rec, body=f"第 {i} 条")).status_code == 200

        page1 = await client.get(_url(rec), headers=auth, params={"limit": 2})
        page2 = await client.get(
            _url(rec), headers=auth, params={"limit": 2, "offset": 2}
        )

        assert page1.status_code == 200, page1.text
        assert page1.json()["total"] == 5
        assert len(page1.json()["items"]) == 2
        assert len(page2.json()["items"]) == 2

    async def test_comments_are_scoped_to_the_record(
        self, client, auth, db_session, project_id, workspace
    ):
        """A 记录的批注不得出现在 B 记录的列表里。

        批注是**针对某条记录**的意见；串了会让人对着错误的记录做修改。
        """
        a = await _make_record(client, auth, db_session, project_id, workspace, line_no="P-4001")
        b = await _make_record(client, auth, db_session, project_id, workspace, line_no="P-4002")
        await _post(client, auth, a, body="A 的批注")

        resp = await client.get(_url(b), headers=auth)

        assert resp.json()["items"] == []

    async def test_comments_are_ordered_oldest_first(
        self, client, auth, db_session, project_id, workspace
    ):
        """顺序稳定 —— `created_at` 是秒级粒度，必须有 tiebreaker。

        同批写入的批注在 SQLite 上时间戳必然相同；只按 created_at 排序时
        并列行的返回顺序不确定 ⇒ 翻页会漏批注或重复。
        """
        rec = await _make_record(client, auth, db_session, project_id, workspace)
        for i in range(4):
            await _post(client, auth, rec, body=f"第 {i} 条")

        first = await client.get(_url(rec), headers=auth, params={"limit": 2})
        second = await client.get(
            _url(rec), headers=auth, params={"limit": 2, "offset": 2}
        )

        ids_first = [c["comment_id"] for c in first.json()["items"]]
        ids_second = [c["comment_id"] for c in second.json()["items"]]
        assert not set(ids_first) & set(ids_second), "两页出现重复批注"
        assert ids_first + ids_second == [
            c["comment_id"]
            for c in (await client.get(_url(rec), headers=auth)).json()["items"]
        ]

    async def test_empty_record_returns_empty_list(
        self, client, auth, db_session, project_id, workspace
    ):
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await client.get(_url(rec), headers=auth)

        assert resp.status_code == 200, resp.text
        assert resp.json() == {"items": [], "total": 0}


class TestCommentsAreNotObservation:
    async def test_comment_does_not_write_workflow_progress(
        self, client, auth, db_session, project_id, workspace
    ):
        """批注**不写** workflow_progress（ADR-0047 §①）。

        观测层记的是流程进度；把「有人留言」也算成工作流活动，
        会让甘特图上的活动看起来比实际多 —— 而观测层一旦不可信就没人再信它。
        """
        from app.models.workflow_progress import WorkflowProgress

        rec = await _make_record(client, auth, db_session, project_id, workspace)
        await _post(client, auth, rec)

        rows = (await db_session.execute(select(WorkflowProgress))).scalars().all()
        assert rows == []


class TestSchemaContract:
    def test_record_type_column_fits_every_registry_key(self):
        """列宽必须装得下**注册表里最长的键**。

        ⚠️ 原宽度 30 装不下 `ProjectCalculationStandardProfile`（33 字符）——
        给这类记录留言会在**入库那一刻**炸，且炸的是 500 而不是 422。
        这条断言在 `p9_003` 写下时就会红：它是纯元数据检查，不依赖任何数据。
        """
        import app.models  # noqa: F401
        import app.models.record_comment  # noqa: F401
        from app.db.base import Base
        from app.services.calc_lineage import RECORD_TYPE_REGISTRY

        longest = max(RECORD_TYPE_REGISTRY, key=len)
        width = Base.metadata.tables["record_comments"].columns["record_type"].type.length
        assert width >= len(longest), (
            f"record_comments.record_type 是 VARCHAR({width})，"
            f"装不下注册表里最长的键 {longest!r}（{len(longest)} 字符）"
        )


class TestResponseContract:
    async def test_comment_response_has_no_bare_fields(
        self, client, auth, db_session, project_id, workspace
    ):
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await _post(client, auth, rec)

        assert set(resp.json()) == {
            "comment_id", "record_type", "record_id", "body", "author_id", "created_at",
        }

    async def test_no_bare_dict_responses_in_new_router(self):
        from app.api.v1 import records_actions

        offenders = [
            r.path
            for r in records_actions.router.routes
            if getattr(r, "response_model", None) in (dict, list[dict])
        ]
        assert not offenders, f"新 router 出现裸 dict 响应：{offenders}"
