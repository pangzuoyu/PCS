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
from app.services.calc_lineage import RECORD_TYPE_REGISTRY

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


async def _bind_to_approved_deliverable(
    db_session: AsyncSession, rec: PipingResult, project_id
) -> None:
    """把记录绑到一张**已批准**的交付物上（= 「已对外生效」）。

    ⚠️ TODO-082：「已对外生效」的判据**不是** `record.locked_by_deliverable`
    （那列**全仓只被读、从不被写 True** ⇒ 门永远不触发）⇒ 真实条件 = 记录被
    一张 **APPROVED** 的交付物绑定。
    """
    from app.models.deliverable import (
        Deliverable,
        DeliverableRecordBinding,
        DeliverableVersion,
        SignatureMatrix,
    )
    from app.models.enums import DeliverableSignStatus

    matrix = SignatureMatrix(
        matrix_name=f"矩阵-{uuid.uuid4().hex[:8]}",
        module="RECORD",
        doc_type="CHANGE_NOTICE",
        version_purpose="ISSUED_FOR_CHANGE",
        steps_json=[{"step_order": 1, "sign_role": "APPROVER"}],
        status="ACTIVE",
    )
    db_session.add(matrix)
    await db_session.flush()
    deliverable = Deliverable(
        matrix_id=matrix.matrix_id,
        project_id=project_id,
        deliverable_type="CHANGE_NOTICE",
        scope_type="CUSTOM",
        scope_value=f"CHANGE_NOTICE:PipingResult:{rec.pipe_id}:{uuid.uuid4().hex[:8]}",
        doc_no=f"CN-{uuid.uuid4().hex.upper()}",
        doc_no_mode="MANUAL",
        title="变更单",
        current_rev="0",
        version_purpose="ISSUED_FOR_CHANGE",
        sign_status=DeliverableSignStatus.APPROVED,
    )
    db_session.add(deliverable)
    await db_session.flush()
    version = DeliverableVersion(
        deliverable_id=deliverable.deliverable_id,
        rev="1",
        version_purpose="ISSUED_FOR_CHANGE",
        description="变更单版本",
        record_snapshot_json={},
        signature_summary_json={},
    )
    db_session.add(version)
    await db_session.flush()
    db_session.add(
        DeliverableRecordBinding(
            deliverable_version_id=version.version_id,
            record_type="PipingResult",
            record_id=rec.pipe_id,
            record_hash=rec.record_hash or "",
        )
    )
    await db_session.commit()


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
        """已对外生效的记录弃用 ⇒ 409（`BoundObsoleteError`），**不是 500**。

        已对外生效的记录必须走 RECORD_CANCELLATION 变更单（ADR-0002）
        —— ⚠️ 判据 = 被一张 **APPROVED** 的交付物绑定（TODO-082）。
        若这里变成 500，前端只知道「出错了」，用户会以为系统坏了而重试；
        而正确处置是「去开变更单」。
        """
        rec = await _make_record(client, auth, db_session, project_id, workspace)
        # ⚠️ 「已对外生效」= 被一张 **APPROVED** 的交付物绑定（TODO-082）
        await _bind_to_approved_deliverable(db_session, rec, project_id)

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

    async def test_registry_splits_into_supported_and_unsupported(self):
        """注册表的键分两类，端点必须**显式区分**而不是一律放行。

        ⚠️ 这条测试**曾经写反**：原断言是「每个键都能解析」。
        那正是 CRITICAL finding 的根源 —— `RECORD_TYPE_REGISTRY` 里混着
        几张列不齐的表（`CostEstResult` / `TwoPhaseResult` 没有 `project_id`，
        `ProjectCalculationStandardProfile` 没有 `sign_status`），
        「都能解析」等于把它们放进会抛 500 的路径。

        现在断言：具备 `RecordMixin` 全列的键解析得到模型；
        其余的必须抛 422 `RECORD_MODULE_UNSUPPORTED`。
        """
        from app.api.v1.records_actions import resolve_record_model
        from app.core.errors import PcsError
        from app.models.mixins import RecordMixin
        from app.services.calc_lineage import RECORD_TYPE_REGISTRY

        supported, unsupported = [], []
        for key, model in RECORD_TYPE_REGISTRY.items():
            columns = set(model.__table__.columns.keys())
            if set(RecordMixin.__annotations__) <= columns and "project_id" in columns:
                supported.append(key)
                assert resolve_record_model(key) is model, key
            else:
                unsupported.append(key)
                with pytest.raises(PcsError) as exc:
                    resolve_record_model(key)
                assert exc.value.code == "RECORD_MODULE_UNSUPPORTED", key

        # 两边都不能为空 —— 空集合说明分类逻辑写死了而不是真在判列
        assert supported, "没有任何注册表键被判为可用"
        assert unsupported, "没有任何注册表键被判为不可用（分类可能写死了）"


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


class TestRegistryModuleColumnCoverage:
    """注册表里**每一个** key 打遍写路径，都不得 500。

    为什么要有这条：`{module}` 直接取 `RECORD_TYPE_REGISTRY` 的键，而该注册表
    里混着几张**列不齐**的表 —— `CostEstResult` / `TwoPhaseResult` 没有
    `project_id`，`ProjectCalculationStandardProfile` 没有 `sign_status`。
    解析成功但加载失败 ⇒ 守卫抛 500「Record missing project_id (guard
    misconfigured)」—— 把开发者字符串端给用户，且不告诉他「这种记录不支持
    这套流程」这个真正该说的话。

    逐端点测只会覆盖已写测试的那几个模块；这条覆盖**将来**注册表里出现的
    每一个 key —— 那才是 500 的实际来源。
    """

    _ACTIONS = (
        ("obsolete", {"reason": "x"}),
        ("request-reversal", {"reason": "x"}),
        ("reversal-decision", {"decision": "APPROVE"}),
        ("submit-approval", {"approval_role": "CHECKER"}),
        ("approval-step", {"decision": "PASS"}),
        ("abandon-change", {"reason": "x"}),
    )

    @pytest.mark.parametrize("module", sorted(RECORD_TYPE_REGISTRY))
    async def test_write_paths_never_500(self, client, auth, approver_auth, module):
        # 角色闸先于模块解析：撤销裁决要 APPROVER、批步骤要 CHECKER/APPROVER，
        # 用错角色的 token 会先 403，断言集就得放宽到 403 ——
        # 而 403 对本测试（防 500）没有信息量。
        from app.core.security import create_access_token

        checker = {
            "Authorization": f"Bearer {create_access_token(subject='chk', role='CHECKER')}"
        }
        headers_for = {"reversal-decision": approver_auth, "approval-step": checker}
        for action, body in self._ACTIONS:
            resp = await client.post(
                f"/api/v1/records/{module}/{uuid.uuid4()}/{action}",
                headers=headers_for.get(action, auth), json=body,
            )
            assert resp.status_code != 500, (
                f"{module}/{action} 返回 500 —— 模块解析成功但加载失败"
            )
            assert resp.status_code in (404, 422), (
                f"{module}/{action} 期望 404（列齐但无此记录）或 422（列不齐），"
                f"实得 {resp.status_code} {resp.text}"
            )

    @pytest.mark.parametrize("module", sorted(RECORD_TYPE_REGISTRY))
    async def test_comment_paths_never_500(self, client, auth, module):
        """批注只需要 `project_id`，但同样不得 500。"""
        for method, path in (
            ("post", f"/api/v1/records/{module}/{uuid.uuid4()}/comments"),
            ("get", f"/api/v1/records/{module}/{uuid.uuid4()}/comments"),
        ):
            resp = await (
                client.post(path, headers=auth, json={"body": "x"})
                if method == "post"
                else client.get(path, headers=auth)
            )
            assert resp.status_code != 500, f"{module}/comments {method} 返回 500"

    async def test_unsupported_module_names_the_missing_columns(self, client, auth):
        """422 必须说清**缺哪些列** —— 只说「不支持」等于让用户猜。"""
        resp = await client.post(
            f"/api/v1/records/CostEstResult/{uuid.uuid4()}/obsolete",
            headers=auth, json={"reason": "x"},
        )

        assert resp.status_code == 422, resp.text
        body = resp.json()
        assert body["code"] == "RECORD_MODULE_UNSUPPORTED"
        assert "project_id" in body["message"]

    async def test_module_missing_sign_status_is_rejected_on_approval(
        self, client, auth
    ):
        """`submit-approval` 需要 `sign_status`/`approval_*`；缺则 422。

        这类模型有 `project_id` 所以能过守卫，不加列检查就会在下一步
        `AttributeError` ⇒ 500。
        """
        resp = await client.post(
            f"/api/v1/records/ProjectCalculationStandardProfile/"
            f"{uuid.uuid4()}/submit-approval",
            headers=auth, json={"approval_role": "CHECKER"},
        )

        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "RECORD_MODULE_UNSUPPORTED"
