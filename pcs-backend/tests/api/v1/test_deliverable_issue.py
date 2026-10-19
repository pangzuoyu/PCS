"""交付物 issue 端点测试（P9A B1 / SPEC P9A-DLV-001·002·003）。

**为什么 issue 值得单独测**：只有 issue 产出的 `deliverable_versions` 行才能进入
sign-step 流程（B2）。没有它，`sign_status` 永远停在 DRAFT，签署矩阵无从消费。

**doc_no 为什么要单独一节**（P9A-DLV-003）：编号必须走
`NumberingService.next_value` 的 `SELECT ... FOR UPDATE` 行锁，自己
`max(doc_no)+1` 在并发下必然撞号。SQLite 没有 FOR UPDATE 语义，
所以并发正确性另有一条真 PG 的 [→E2E]（本文件末尾标注），
**这里的断言只验渲染规则，不验并发** —— 用 SQLite 验并发会给假绿。

覆盖用内存 SQLite（conftest 从 ORM metadata 建表），不覆盖迁移（CLAUDE.md 漂移盲区）。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import NumberingTemplate
from app.models.deliverable import (
    Deliverable,
    DeliverableVersion,
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.enums import DeliverableSignStatus

pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth(sample_user_token: str) -> dict[str, str]:
    """issue 需登录（current_actor 无 header 直接 401）。DESIGNER 是签发方角色。"""
    return {"Authorization": f"Bearer {sample_user_token}"}


@pytest.fixture
def reviewer_auth(sample_user_token: str) -> dict[str, str]:
    """REVIEWER 是**审**方 —— 审方不该能签发（那是作者的活）。"""
    from app.core.security import create_access_token

    return {
        "Authorization": f"Bearer {create_access_token(subject='rev-user', role='REVIEWER')}"
    }


async def _make_matrix(db: AsyncSession) -> SignatureMatrix:
    """建签署矩阵。`Deliverable.matrix_id` NOT NULL + FK（bug-145）。"""
    row = SignatureMatrix(
        matrix_name="测试矩阵",
        module="*",
        doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        steps_json=[
            {"step_order": 1, "sign_role": "DESIGNER", "required": True},
            {"step_order": 2, "sign_role": "REVIEWER", "required": True},
        ],
        status="ACTIVE",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _make_binding(
    db: AsyncSession, project_id: uuid.UUID, matrix_id: uuid.UUID
) -> ProjectSignatureMatrixBinding:
    """把矩阵绑到项目。

    缺这一行 = 项目没绑矩阵 ⇒ issue 必须拒（409），而不是拿一个没绑定的矩阵去签发。
    """
    row = ProjectSignatureMatrixBinding(
        project_id=project_id, module="RECORD", matrix_id=matrix_id
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _make_template(
    db: AsyncSession, segments: list, separator: str = "-"
) -> NumberingTemplate:
    row = NumberingTemplate(
        template_name="测试编号模板",
        description="DELIVERABLE",
        segments_json=segments,
        separator=separator,
        status="ACTIVE",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _make_deliverable(
    db: AsyncSession, project_id: uuid.UUID, *, bind: bool = True, **overrides
) -> Deliverable:
    """建一条交付物（最小必填集）+ 绑矩阵。issue 的前置就绪态。

    `bind=False` 建出「项目没绑矩阵」的状态，供 409 用例用。
    """
    matrix = overrides.pop("matrix", None) or await _make_matrix(db)
    if bind:
        await _make_binding(db, project_id, matrix.matrix_id)
    payload = {
        "matrix_id": matrix.matrix_id,
        "project_id": project_id,
        "deliverable_type": "CALCULATION_BOOK",
        "scope_type": "PROJECT_ALL",
        # UNIQUE(project_id, deliverable_type, scope_type, scope_value) ⇒ 必须逐条不同
        "scope_value": str(uuid.uuid4())[:8],
        "doc_no": "CB-DRAFT",
        "doc_no_mode": "MANUAL",
        "title": "泵计算书",
        "current_rev": "0",
        "version_purpose": "INTERNAL_REVIEW",
        "sign_status": DeliverableSignStatus.DRAFT,
    }
    payload.update(overrides)
    row = Deliverable(**payload)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _issue(client, auth, deliverable_id, **body):
    payload = {"version_purpose": "ISSUED_FOR_CONSTRUCTION", **body}
    return await client.post(
        f"/api/v1/deliverables/{deliverable_id}/issue", headers=auth, json=payload
    )


class TestIssueCreatesVersion:
    async def test_creates_first_version_with_rev_one(self, client, auth, db_session, project_id):
        """首个版本 rev 从 1 起（0 是草稿位，不是版本号）。"""
        d = await _make_deliverable(db_session, project_id)

        resp = await _issue(client, auth, d.deliverable_id)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["rev"] == "1"
        assert body["version_purpose"] == "ISSUED_FOR_CONSTRUCTION"
        assert body["deliverable_id"] == str(d.deliverable_id)
        assert body["version_id"]

        version = (
            await db_session.execute(
                select(DeliverableVersion).where(
                    DeliverableVersion.deliverable_id == d.deliverable_id
                )
            )
        ).scalar_one()
        assert version.rev == "1"

    async def test_advances_deliverable_to_pending(self, client, auth, db_session, project_id):
        """签发 = 提交送审 ⇒ sign_status DRAFT → PENDING，current_rev 跟着走。"""
        d = await _make_deliverable(db_session, project_id)

        await _issue(client, auth, d.deliverable_id)

        await db_session.refresh(d)
        assert d.sign_status == DeliverableSignStatus.PENDING
        assert d.current_rev == "1"
        assert d.version_purpose == "ISSUED_FOR_CONSTRUCTION"

    async def test_second_purpose_gets_rev_two(self, client, auth, db_session, project_id):
        """不同版本目的是不同版本 ⇒ rev 递增，不是覆盖。"""
        d = await _make_deliverable(db_session, project_id)

        first = await _issue(client, auth, d.deliverable_id)
        second = await _issue(
            client, auth, d.deliverable_id, version_purpose="INTERNAL_REVIEW"
        )

        assert first.json()["rev"] == "1"
        assert second.json()["rev"] == "2"
        versions = (
            await db_session.execute(
                select(DeliverableVersion).where(
                    DeliverableVersion.deliverable_id == d.deliverable_id
                )
            )
        ).scalars().all()
        assert {v.rev for v in versions} == {"1", "2"}

    async def test_signature_summary_carries_matrix_steps(
        self, client, auth, db_session, project_id
    ):
        """签署汇总要带上矩阵步骤 —— 否则 B2 的 sign-step 无从知道有几个步骤。"""
        d = await _make_deliverable(db_session, project_id)

        await _issue(client, auth, d.deliverable_id)

        version = (
            await db_session.execute(
                select(DeliverableVersion).where(
                    DeliverableVersion.deliverable_id == d.deliverable_id
                )
            )
        ).scalar_one()
        assert len(version.signature_summary_json["steps"]) == 2
        assert version.signature_summary_json["steps"][0]["sign_role"] == "DESIGNER"


class TestIssueValidation:
    async def test_rejects_invalid_version_purpose(self, client, auth, db_session, project_id):
        """13 值词表外的值必须 422。

        不能「先收下再说」—— 非法版本目的会进到签署矩阵里，
        而矩阵按 version_purpose 选步骤，猜错就是静默签错文件。
        """
        d = await _make_deliverable(db_session, project_id)

        resp = await _issue(
            client, auth, d.deliverable_id, version_purpose="NOT_A_REAL_PURPOSE"
        )

        assert resp.status_code == 422, resp.text

    async def test_rejects_unbound_matrix(self, client, auth, db_session, project_id):
        """项目没绑矩阵 ⇒ 409，不是 500，也不是默默拿矩阵_id 硬签。"""
        d = await _make_deliverable(db_session, project_id, bind=False)

        resp = await _issue(client, auth, d.deliverable_id)

        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "DELIVERABLE_MATRIX_UNBOUND"

    async def test_is_idempotent_on_second_call(self, client, auth, db_session, project_id):
        """重复签发同一版本目的 ⇒ 409，不静默产生第 2 个版本。

        静默产生第 2 个版本的后果：签署矩阵的步骤序号对不上，
        用户看到「已签发」却没有任何一版进入签署。
        """
        d = await _make_deliverable(db_session, project_id)

        assert (await _issue(client, auth, d.deliverable_id)).status_code == 200
        second = await _issue(client, auth, d.deliverable_id)

        assert second.status_code == 409, second.text
        assert second.json()["code"] == "DELIVERABLE_ALREADY_ISSUED"
        count = (
            await db_session.execute(
                select(DeliverableVersion).where(
                    DeliverableVersion.deliverable_id == d.deliverable_id
                )
            )
        ).scalars().all()
        assert len(count) == 1

    async def test_unknown_deliverable_is_404(self, client, auth):
        """404 且 code 是 DELIVERABLE_NOT_FOUND。

        ⚠️ 只断言 404 会**在端点还不存在时就绿**（FastAPI 对未注册路径也返 404）
        —— 那是个假绿，会把「端点没接上」伪装成「错误处理正确」。故断言 code。
        """
        resp = await _issue(client, auth, uuid.uuid4())
        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "DELIVERABLE_NOT_FOUND"

    async def test_reviewer_cannot_issue(self, client, reviewer_auth, db_session, project_id):
        """审方不能签发 —— 签发是作者的活，否则自己审自己批。"""
        d = await _make_deliverable(db_session, project_id)

        resp = await _issue(client, reviewer_auth, d.deliverable_id)

        assert resp.status_code == 403, resp.text


class TestIssueDocNo:
    async def test_keeps_manual_doc_no(self, client, auth, db_session, project_id):
        """`doc_no_mode=MANUAL` 且未绑模板 ⇒ 原样保留创建时的 doc_no。

        覆盖既有编号不是 issue 的职责；issue 覆盖它会让用户手工编的号凭空消失。
        """
        d = await _make_deliverable(db_session, project_id, doc_no="CB-2026-001")

        resp = await _issue(client, auth, d.deliverable_id)

        assert resp.json()["doc_no"] == "CB-2026-001"

    async def test_renders_doc_no_from_template_segments(
        self, client, auth, db_session, project_id
    ):
        """绑了模板 ⇒ 按 `segments_json` 逐段渲染。

        格式取自 P2 计划设计 §3.5：`["project_no","-","doc_type","-","seq"]`
        （`segments_json` = 分段定义，字面量段原样拼接）。
        """
        template = await _make_template(
            db_session, ["project_no", "-", "doc_type", "-", "seq"]
        )
        d = await _make_deliverable(
            db_session,
            project_id,
            numbering_template_id=template.template_id,
            doc_no_mode="WORLEY_STD",
        )

        resp = await _issue(client, auth, d.deliverable_id)

        doc_no = resp.json()["doc_no"]
        assert doc_no.endswith("-CALCULATION_BOOK-1"), doc_no
        assert doc_no.startswith(str(project_id)) or "-" in doc_no
        assert doc_no != "CB-DRAFT", "模板编号必须覆盖草稿占位号"

    async def test_sequence_increments_per_issue(self, client, auth, db_session, project_id):
        """同一模板 + 同一 scope 的两次签发 ⇒ 序号 1、2，不撞号。"""
        template = await _make_template(db_session, ["seq"])
        # doc_no 必须逐条不同：UNIQUE(project_id, doc_no)，占位号撞了会先在草稿阶段
        # IntegrityError —— 还没走到取号逻辑就先炸，看不出是取号还是约束。
        d1 = await _make_deliverable(
            db_session, project_id, numbering_template_id=template.template_id,
            doc_no_mode="WORLEY_STD", doc_no="DRAFT-1",
        )
        d2 = await _make_deliverable(
            db_session, project_id, numbering_template_id=template.template_id,
            doc_no_mode="WORLEY_STD", doc_no="DRAFT-2",
        )

        first = (await _issue(client, auth, d1.deliverable_id)).json()["doc_no"]
        second = (await _issue(client, auth, d2.deliverable_id)).json()["doc_no"]

        assert (first, second) == ("1", "2"), (first, second)

    async def test_unknown_token_is_rejected_not_literal(
        self, client, auth, db_session, project_id
    ):
        """模板里出现未登记的段名 ⇒ 报错，不能当字面量原样输出。

        静默输出的后果：`["projct_no","-","seq"]`（拼错）会渲染成
        `projct_no-1` —— 看着像编号，用起来撞号且没人知道为什么。
        """
        template = await _make_template(db_session, ["projct_no", "-", "seq"])
        d = await _make_deliverable(
            db_session, project_id, numbering_template_id=template.template_id,
            doc_no_mode="WORLEY_STD",
        )

        resp = await _issue(client, auth, d.deliverable_id)

        assert resp.status_code == 400, resp.text
        assert resp.json()["code"] == "NUMBERING_TEMPLATE_UNKNOWN_TOKEN"


class TestIssueResponseContract:
    async def test_response_model_has_no_bare_fields(self, client, auth, db_session, project_id):
        """P9A-DLV-010 零裸字段：响应模型显式声明，且不泄出内部列。"""
        d = await _make_deliverable(db_session, project_id)

        resp = await _issue(client, auth, d.deliverable_id)

        assert set(resp.json()) == {
            "deliverable_id",
            "version_id",
            "rev",
            "doc_no",
            "version_purpose",
            "sign_status",
            "issued_at",
        }

    async def test_writes_created_by_from_current_user(
        self, client, db_session, project_id
    ):
        """零裸字段的另一半：`created_by` 取当前登录人，不是固定值也不是空。"""
        from app.core.security import create_access_token

        actor_id = uuid.uuid4()
        token = create_access_token(
            subject="issuer", role="DESIGNER", extra={"user_id": str(actor_id)}
        )
        d = await _make_deliverable(db_session, project_id)

        resp = await _issue(
            client, {"Authorization": f"Bearer {token}"}, d.deliverable_id
        )

        assert resp.status_code == 200, resp.text
        version = (
            await db_session.execute(
                select(DeliverableVersion).where(
                    DeliverableVersion.deliverable_id == d.deliverable_id
                )
            )
        ).scalar_one()
        assert version.created_by == actor_id


# [→E2E] test_doc_no_unique_under_concurrent_issue —— 10 并发签发同一
# (project, template, scope)，断言 10 个 doc_no 互不相同。
# **必须真 PG**：`SELECT ... FOR UPDATE` 在 SQLite 上是空操作，
# 用内存 SQLite 跑并发会给「不撞号」的假绿，而撞号的后果是两份交付物同号。
