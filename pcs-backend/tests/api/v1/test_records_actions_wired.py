"""records 写端点 · 接线面测试（P9A B4a）。

本文件只测**端点层契约**，不重测三个既有 service 的业务逻辑 ——
它们各自有约 450 行测试（`tests/services/test_record_cancellation.py` /
`test_reversal_approval.py`）。重复测一遍只会得到「实现变了才红」的脆弱用例，
而端点真正会出错的地方是**接线**：模块解析、鉴权、错误码映射、裸字段。

## `{module}` 的取值

取自 `calc_lineage.RECORD_TYPE_REGISTRY` 的键（唯一真值源，不另起注册表）。
该注册表的键**大小写风格不统一**（`PipingResult` vs `cv_result`）——
`test_unknown_module_is_rejected` 钉住「注册表外的名字一律拒」，
风格不统一本身登记在 TODO 里。

## fixture 用 POST /api/v1/piping 建记录

按 cerebrum 的 DB fixture 纪律：**能用 API 建的别用 ORM kwarg 拼装** ——
PipingResult 的 NOT NULL 字段多且会变，ORM 拼装漏一个必填就是一条看不懂的
IntegrityError；POST 端点由 service 层兜底必填，且缺什么会立刻显出来。
建完再用 DB UPDATE 改状态字段（DRAFT → CHANGED 等无端点的迁移）。
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


@pytest.fixture
def approver_auth() -> dict[str, str]:
    """撤销裁决要 APPROVER（`state_machine.TRANSITION_ROLES[APPROVE_REVERSAL]`）。

    角色集取自状态机那张表而不是另发明 —— 三个被接线的 service 都不做角色校验
    （注释自陈「角色校验交给签名矩阵层」），端点层必须补，补的依据就用它。
    """
    from app.core.security import create_access_token

    return {
        "Authorization": f"Bearer {create_access_token(subject='app-user', role='APPROVER')}"
    }


async def _make_record(
    client, auth, db_session: AsyncSession, project_id, workspace, **status
) -> PipingResult:
    """经 POST /api/v1/piping 建一条 CHECKED 记录，再按需改状态。"""
    resp = await client.post(
        "/api/v1/records/piping",
        headers=auth,
        params={"workspace_id": str(workspace.workspace_id)},
        json={
            "project_id": str(project_id),
            "line_no": status.pop("line_no", "P-1001"),
        },
    )
    assert resp.status_code == 200, resp.text
    pipe_id = resp.json()["pipe_id"]

    rec = await db_session.get(PipingResult, uuid.UUID(pipe_id))
    for field, value in status.items():
        setattr(rec, field, value)
    await db_session.commit()
    await db_session.refresh(rec)
    return rec


def _url(rec: PipingResult, action: str) -> str:
    return f"/api/v1/records/PipingResult/{rec.pipe_id}/{action}"


class TestObsoleteEndpoint:
    async def test_obsolete_unbound_record_succeeds(
        self, client, auth, db_session, project_id, workspace
    ):
        """未绑定记录直接弃用（ADR-0009：未绑定免凭证 OBSOLETE）。"""
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await client.post(
            _url(rec, "obsolete"), headers=auth, json={"reason": "重复录入"}
        )

        assert resp.status_code == 200, resp.text
        await db_session.refresh(rec)
        assert rec.sign_status == RecordSignStatus9.OBSOLETE

    async def test_obsolete_endpoint_returns_409_when_bound_to_deliverable(
        self, client, auth, db_session, project_id, workspace
    ):
        """已绑定记录弃用 ⇒ 409（`BoundObsoleteError`），**不是 500**。

        已绑定记录必须走 RECORD_CANCELLATION 变更单（ADR-0002）。
        若这里变成 500，前端只知道「出错了」，用户会以为系统坏了而重试；
        而正确处置是「去开变更单」。
        """
        rec = await _make_record(
            client, auth, db_session, project_id, workspace,
            locked_by_deliverable=True,
        )

        resp = await client.post(
            _url(rec, "obsolete"), headers=auth, json={"reason": "重复录入"}
        )

        assert resp.status_code == 409, resp.text
        await db_session.refresh(rec)
        assert rec.sign_status != RecordSignStatus9.OBSOLETE, "被拒的弃用不得改状态"

    async def test_obsolete_requires_reason(self, client, auth, db_session, project_id, workspace):
        """弃用理由必填 —— 空理由的弃用事后无法追溯为什么作废。"""
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await client.post(_url(rec, "obsolete"), headers=auth, json={"reason": ""})

        assert resp.status_code == 422, resp.text


class TestReversalEndpoints:
    async def test_request_reversal_requires_changed_state(
        self, client, auth, db_session, project_id, workspace
    ):
        """撤销只对 CHANGED 发起（ADR-0002）—— CHECKED 记录撤不了。

        反过来也不成立：已生效的记录要走变更单而不是撤销。
        """
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await client.post(
            _url(rec, "request-reversal"), headers=auth, json={"reason": "数据错了"}
        )

        assert resp.status_code in (409, 422), resp.text

    async def test_request_reversal_moves_to_reversal_pending(
        self, client, auth, db_session, project_id, workspace
    ):
        rec = await _make_record(
            client, auth, db_session, project_id, workspace,
            sign_status=RecordSignStatus9.CHANGED,
        )

        resp = await client.post(
            _url(rec, "request-reversal"), headers=auth, json={"reason": "数据错了"}
        )

        assert resp.status_code == 200, resp.text
        await db_session.refresh(rec)
        assert rec.sign_status == RecordSignStatus9.REVERSAL_PENDING

    async def test_reversal_decision_approve_and_reject_both_reachable(
        self, client, auth, approver_auth, db_session, project_id, workspace
    ):
        """approve 与 reject 是**相反动作** —— 两个分支都要端到端跑通。

        只接通 approve 的半成品会让「拒绝撤销」永远 500，而用户看到的是
        「我按了拒绝，什么都没发生」—— 且记录卡在 REVERSAL_PENDING 谁也动不了。
        """
        approved = await _make_record(
            client, auth, db_session, project_id, workspace,
            line_no="P-2001", sign_status=RecordSignStatus9.CHANGED,
        )
        rejected = await _make_record(
            client, auth, db_session, project_id, workspace,
            line_no="P-2002", sign_status=RecordSignStatus9.CHANGED,
        )

        for rec in (approved, rejected):
            r = await client.post(
                _url(rec, "request-reversal"), headers=auth, json={"reason": "数据错了"}
            )
            assert r.status_code == 200, r.text

        approve_resp = await client.post(
            _url(approved, "reversal-decision"),
            headers=approver_auth, json={"decision": "APPROVE"},
        )
        reject_resp = await client.post(
            _url(rejected, "reversal-decision"),
            headers=approver_auth,
            json={"decision": "REJECT", "reason": "凭证已对外发出"},
        )

        assert approve_resp.status_code == 200, approve_resp.text
        assert reject_resp.status_code == 200, reject_resp.text

        await db_session.refresh(approved)
        await db_session.refresh(rejected)
        assert approved.sign_status == RecordSignStatus9.CHECKED, "批准撤销 → 回 CHECKED"
        assert rejected.sign_status == RecordSignStatus9.CHANGED, "拒绝撤销 → 维持 CHANGED"

    async def test_reversal_decision_requires_approver_role(
        self, client, auth, db_session, project_id, workspace
    ):
        """DESIGNER 撤不了自己的撤销 —— 撤销裁决要 APPROVER。

        三个被接线的 service 都不做角色校验，端点层补的这一道必须有测试，
        否则它就是一条没人验证过的规则：删掉它不会有任何用例变红。
        """
        rec = await _make_record(
            client, auth, db_session, project_id, workspace,
            sign_status=RecordSignStatus9.CHANGED,
        )
        await client.post(
            _url(rec, "request-reversal"), headers=auth, json={"reason": "数据错了"}
        )

        resp = await client.post(
            _url(rec, "reversal-decision"), headers=auth, json={"decision": "APPROVE"}
        )

        assert resp.status_code == 403, resp.text

    async def test_reversal_decision_rejects_unknown_decision(
        self, client, auth, approver_auth, db_session, project_id, workspace
    ):
        rec = await _make_record(
            client, auth, db_session, project_id, workspace,
            sign_status=RecordSignStatus9.CHANGED,
        )
        await client.post(
            _url(rec, "request-reversal"), headers=auth, json={"reason": "数据错了"}
        )

        resp = await client.post(
            _url(rec, "reversal-decision"),
            headers=approver_auth, json={"decision": "MAYBE"},
        )

        assert resp.status_code == 422, resp.text


class TestModuleResolution:
    async def test_unknown_module_is_rejected_with_code(
        self, client, auth, db_session, project_id, workspace
    ):
        """注册表外的模块名 ⇒ 422 + 明确 code。

        只断言 4xx 是不够的：未注册路径也会 404/422，会把「端点没接上」
        伪装成「模块解析正确」。同 ADR-0047 式的「写错层不报错」是同一类问题。
        """
        resp = await client.post(
            f"/api/v1/records/NoSuchModel/{uuid.uuid4()}/obsolete",
            headers=auth, json={"reason": "x"},
        )

        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "RECORD_MODULE_UNKNOWN"

    async def test_unknown_record_is_404_with_code(
        self, client, auth, project_id, workspace
    ):
        resp = await client.post(
            f"/api/v1/records/PipingResult/{uuid.uuid4()}/obsolete",
            headers=auth, json={"reason": "x"},
        )

        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "RECORD_NOT_FOUND"

    async def test_every_registry_module_resolves(self):
        """`RECORD_TYPE_REGISTRY` 的每个键都必须能被 `{module}` 解析。

        这条测试存在的意义：注册表与端点的 `{module}` 是同一份词表；
        若哪天有人往注册表加了一个没接进端点的键，这里会红。
        """
        from app.api.v1.records_actions import resolve_record_model
        from app.services.calc_lineage import RECORD_TYPE_REGISTRY

        for key in RECORD_TYPE_REGISTRY:
            assert resolve_record_model(key) is RECORD_TYPE_REGISTRY[key], key


class TestResponseContract:
    async def test_responses_declare_no_bare_fields(
        self, client, auth, db_session, project_id, workspace
    ):
        """P9A-DLV-010：新增端点零裸字段（`records.py` 既有 6 个裸 dict 不在范围内）。"""
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        resp = await client.post(
            _url(rec, "obsolete"), headers=auth, json={"reason": "重复录入"}
        )

        assert set(resp.json()) == {
            "record_type", "record_id", "from_status", "to_status",
        }

    async def test_no_bare_dict_responses_in_new_router(self):
        """结构性断言：新 router 里不得出现 `response_model=dict`。

        逐端点测「响应有没有裸字段」只能覆盖已写测试的那几个；
        这条覆盖**将来新增**的端点 —— 那才是裸字段增长的实际来源。
        """
        from app.api.v1 import records_actions

        offenders = [
            r.path
            for r in records_actions.router.routes
            if getattr(r, "response_model", None) in (dict, list[dict])
        ]
        assert not offenders, f"新 router 出现裸 dict 响应：{offenders}"

    async def test_obsolete_row_is_still_in_db(
        self, client, auth, db_session, project_id, workspace
    ):
        """弃用是状态迁移不是删除 —— 行还在，只是 sign_status 变了。

        删行会让「这行曾经存在过、什么时候被谁作废的」无从查证，
        而弃用理由是审计追溯的关键输入。
        """
        rec = await _make_record(client, auth, db_session, project_id, workspace)

        await client.post(_url(rec, "obsolete"), headers=auth, json={"reason": "重复录入"})

        rows = (
            await db_session.execute(
                select(PipingResult).where(PipingResult.pipe_id == rec.pipe_id)
            )
        ).scalars().all()
        assert len(rows) == 1
