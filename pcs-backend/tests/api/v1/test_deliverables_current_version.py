"""交付物「当前版本 id」（P9B-1 Task T0）。

## 为什么需要这个字段

P9B-1 的交付物进度页要按「签署工作流」拉进度，而签署工作流的 `workflow_id`
在 `SIGN` 语义下是**版本 ID**（SPEC §6.24）—— 不是 Rev 文本、也不是
`deliverable_id` ⇒ 后端必须把「当前 Rev 对应的那条版本行」显式交出来。

⚠️ **Rev 是自由文本**（`current_rev` 是非空 `str`，取值域"A/B/0/1/AS-BUILT/X"）
⇒ 前端**不能**靠猜「当前 Rev 是哪个版本」⇒ 这就是本文件存在的理由。

## 两条防线

1. `current_version_id` 必须指向 **`rev == current_rev`** 的那条版本行 ——
   这是「防止未来有人改了 current_rev 的算法但忘了 current_version_id」的唯一防线。
2. **没有版本行** ⇒ `current_version_id is None`。
   ⚠️ 判据是「**没有版本行**」，不是「current_rev 为 null」——
   `current_rev` 是**非空 str**（ORM `Mapped[str]` + schema 必填），永不为 null。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable import (
    Deliverable,
    DeliverableVersion,
    SignatureMatrix,
)
from app.models.enums import DeliverableSignStatus
from app.services.deliverable_service import DeliverableService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth(sample_user_token: str) -> dict[str, str]:
    """读端点需登录 —— 不带 Authorization 头时 current_actor 直接 401。"""
    return {"Authorization": f"Bearer {sample_user_token}"}


async def _make_matrix(db: AsyncSession) -> SignatureMatrix:
    """建一条签署矩阵。

    `Deliverable.matrix_id` 是 **NOT NULL 且带 FK** 到 signature_matrices。
    """
    row = SignatureMatrix(
        matrix_name="测试矩阵",
        module="*",
        doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        steps_json=[{"role": "DESIGNER"}],
        status="ACTIVE",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _make_deliverable(
    db: AsyncSession,
    project_id: uuid.UUID,
    matrix_id: uuid.UUID | None = None,
    **overrides,
) -> Deliverable:
    """建一条交付物（最小必填集）。"""
    if matrix_id is None:
        matrix_id = (await _make_matrix(db)).matrix_id
    payload = {
        "matrix_id": matrix_id,
        "project_id": project_id,
        "deliverable_type": "CALCULATION_BOOK",
        "scope_type": "PROJECT_ALL",
        "scope_value": overrides.pop("scope_value", None) or str(uuid.uuid4())[:8],
        "doc_no": "CB-001",
        "doc_no_mode": "MANUAL",
        "title": "泵计算书",
        "current_rev": "0",
        "version_purpose": "ISSUED_FOR_CONSTRUCTION",
        "sign_status": DeliverableSignStatus.DRAFT,
    }
    payload.update(overrides)
    row = Deliverable(**payload)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _make_version(
    db: AsyncSession, deliverable_id: uuid.UUID, rev: str
) -> DeliverableVersion:
    """建一条交付物版本行（`record_snapshot_json` / `signature_summary_json` NOT NULL）。"""
    row = DeliverableVersion(
        deliverable_id=deliverable_id,
        rev=rev,
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        description=f"Rev {rev}",
        record_snapshot_json={},
        signature_summary_json={},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


class TestCurrentVersionId:
    async def test_current_version_id_points_at_current_rev(
        self, db_session: AsyncSession, project_id: uuid.UUID
    ):
        """current_version_id 必须是 current_rev 对应的那个 version 的 id。"""
        d = await _make_deliverable(db_session, project_id, current_rev="A")
        v_a = await _make_version(db_session, d.deliverable_id, "A")
        await _make_version(db_session, d.deliverable_id, "B")

        ids = await DeliverableService.current_version_ids(
            db_session, deliverables=[d]
        )
        assert ids[d.deliverable_id] == v_a.version_id

        got = await db_session.get(
            DeliverableVersion, ids[d.deliverable_id]
        )
        assert got is not None
        assert got.rev == d.current_rev

    async def test_current_version_id_is_none_when_no_version(
        self, db_session: AsyncSession, project_id: uuid.UUID
    ):
        """没有版本行的交付物 ⇒ current_version_id 为 None。

        ⚠️ 判据是「没有版本行」，不是「current_rev 为 null」——
        current_rev 是非空 str（ORM `Mapped[str]` + schema 必填），永不为 null。
        """
        d = await _make_deliverable(db_session, project_id)

        ids = await DeliverableService.current_version_ids(
            db_session, deliverables=[d]
        )
        assert ids.get(d.deliverable_id) is None

    async def test_current_version_id_is_none_when_no_rev_matches(
        self, db_session: AsyncSession, project_id: uuid.UUID
    ):
        """有版本行但**没有一条**的 rev == current_rev ⇒ None（不猜「最近的那个」）。"""
        d = await _make_deliverable(db_session, project_id, current_rev="C")
        await _make_version(db_session, d.deliverable_id, "A")
        await _make_version(db_session, d.deliverable_id, "B")

        ids = await DeliverableService.current_version_ids(
            db_session, deliverables=[d]
        )
        assert ids.get(d.deliverable_id) is None

    async def test_current_version_id_follows_current_rev(
        self, db_session: AsyncSession, project_id: uuid.UUID
    ):
        """current_rev 推进到 B ⇒ current_version_id 跟着变（不是钉死在首个版本）。"""
        d = await _make_deliverable(db_session, project_id, current_rev="A")
        v_a = await _make_version(db_session, d.deliverable_id, "A")
        v_b = await _make_version(db_session, d.deliverable_id, "B")

        d.current_rev = "B"
        await db_session.commit()

        ids = await DeliverableService.current_version_ids(
            db_session, deliverables=[d]
        )
        assert ids[d.deliverable_id] == v_b.version_id
        assert ids[d.deliverable_id] != v_a.version_id


class TestCurrentVersionIdOverHttp:
    async def test_list_endpoint_carries_current_version_id(
        self, client, auth, db_session: AsyncSession, project_id: uuid.UUID
    ):
        """列表端点必须带上 current_version_id —— 进度页只拉列表，不逐条查详情。"""
        d = await _make_deliverable(db_session, project_id, current_rev="A")
        v = await _make_version(db_session, d.deliverable_id, "A")

        resp = await client.get(
            "/api/v1/deliverables",
            headers=auth,
            params={"project_id": str(project_id)},
        )
        assert resp.status_code == 200, resp.text
        item = resp.json()["items"][0]
        assert item["current_version_id"] == str(v.version_id)

    async def test_detail_endpoint_carries_current_version_id(
        self, client, auth, db_session: AsyncSession, project_id: uuid.UUID
    ):
        d = await _make_deliverable(db_session, project_id, current_rev="A")
        v = await _make_version(db_session, d.deliverable_id, "A")

        resp = await client.get(
            f"/api/v1/deliverables/{d.deliverable_id}", headers=auth
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["current_version_id"] == str(v.version_id)

    async def test_detail_endpoint_current_version_id_is_null_without_version(
        self, client, auth, db_session: AsyncSession, project_id: uuid.UUID
    ):
        """没有版本行 ⇒ 字段为 null（**不是**省略、不是报错）。"""
        d = await _make_deliverable(db_session, project_id)

        resp = await client.get(
            f"/api/v1/deliverables/{d.deliverable_id}", headers=auth
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["current_version_id"] is None

    async def test_list_endpoint_is_not_n_plus_one(
        self, client, auth, db_engine, db_session: AsyncSession, project_id: uuid.UUID
    ):
        """100 个交付物 ⇒ SQL 查询数 ≤ 3（交付物 + 版本 + 计数）。

        ⚠️ 这是「禁 N+1」的**验收**：序列化时逐行查版本会让查询数随行数线性增长。
        """
        matrix = await _make_matrix(db_session)
        for i in range(100):
            d = await _make_deliverable(
                db_session,
                project_id,
                matrix_id=matrix.matrix_id,
                doc_no=f"CB-{i:03d}",
                current_rev="A",
            )
            await _make_version(db_session, d.deliverable_id, "A")

        statements: list[str] = []

        def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
            statements.append(statement)

        event.listen(db_engine.sync_engine, "before_cursor_execute", _record)
        try:
            resp = await client.get(
                "/api/v1/deliverables",
                headers=auth,
                params={"project_id": str(project_id), "limit": 100},
            )
            assert resp.status_code == 200, resp.text
            assert len(resp.json()["items"]) == 100
        finally:
            event.remove(db_engine.sync_engine, "before_cursor_execute", _record)

        selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
        version_queries = [s for s in selects if "deliverable_versions" in s]
        assert len(version_queries) == 1, (
            f"deliverable_versions 被查 {len(version_queries)} 次 ⇒ N+1"
        )
        assert len(selects) <= 3, (
            f"查询数 {len(selects)} > 3 ⇒ N+1：\n" + "\n".join(selects)
        )
