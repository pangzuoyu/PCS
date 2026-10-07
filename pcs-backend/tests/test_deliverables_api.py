"""交付物读端点测试（P1-7+ D 模块 / P8 前置）。

覆盖 list / detail / versions / snapshot 四个读端点。写端点（create / issue /
customer-approval-proxy）服务 P9 签署流程，尚未实现。

**这些测试为什么有价值**：交付物表族此前**完全没有 HTTP 入口**，而 P8 REPORT
依赖从它读数据。测试用内存 SQLite（conftest 从 ORM metadata 建表），所以覆盖的是
「路由 + schema + service 查询」这条链，不覆盖迁移（见 CLAUDE.md 漂移盲区）。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable import (
    Deliverable,
    DeliverableRecordBinding,
    DeliverableVersion,
    SignatureMatrix,
)
from app.models.enums import DeliverableSignStatus

pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth(sample_user_token: str) -> dict[str, str]:
    """读端点需登录 —— conftest 的 client 不带任何 header 时 current_actor 直接 401.

    用 DESIGNER 角色（读面允许的最简角色）。
    """
    return {"Authorization": f"Bearer {sample_user_token}"}


async def _make_matrix(db: AsyncSession) -> SignatureMatrix:
    """建一条签署矩阵。

    `Deliverable.matrix_id` 是 **NOT NULL 且带 FK** 到 signature_matrices
    （app/models/deliverable.py:83-85）。不是可空字段 —— 见 bug-145。
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
    db: AsyncSession, project_id: uuid.UUID, matrix_id: uuid.UUID | None = None, **overrides
) -> Deliverable:
    """建一条交付物（最小必填集）。"""
    if matrix_id is None:
        matrix_id = (await _make_matrix(db)).matrix_id
    payload = {
        "matrix_id": matrix_id,
        "project_id": project_id,
        "deliverable_type": "CALCULATION_BOOK",
        "scope_type": "PROJECT_ALL",
        # scope_value 必须逐条不同：deliverables 上有
        # UNIQUE(project_id, deliverable_type, scope_type, scope_value)
        # —— 同类型同范围只允许一个交付物。不显式传时用计数器兜底。
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


class TestListDeliverables:
    async def test_empty_project_returns_empty_list(self, client, auth, project_id):
        resp = await client.get(
            "/api/v1/deliverables",
            headers=auth,
            params={"project_id": str(project_id)},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"items": [], "total": 0}

    async def test_lists_and_counts(self, client, auth, db_session, project_id):
        await _make_deliverable(db_session, project_id, doc_no="CB-001")
        await _make_deliverable(db_session, project_id, doc_no="CB-002")

        resp = await client.get(
            "/api/v1/deliverables",
            headers=auth,
            params={"project_id": str(project_id)},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    async def test_filters_by_deliverable_type(
        self, client, auth, db_session, project_id
    ):
        """报表生成中心按类型分组，故类型过滤必须真的生效。"""
        await _make_deliverable(db_session, project_id, doc_no="CB-001")
        await _make_deliverable(
            db_session,
            project_id,
            doc_no="CN-001",
            deliverable_type="CHANGE_NOTICE",
        )

        resp = await client.get(
            "/api/v1/deliverables",
            headers=auth,
            params={"project_id": str(project_id), "deliverable_type": "CHANGE_NOTICE"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["deliverable_type"] == "CHANGE_NOTICE"

    async def test_filters_by_sign_status(self, client, auth, db_session, project_id):
        await _make_deliverable(db_session, project_id, doc_no="CB-001")
        await _make_deliverable(
            db_session,
            project_id,
            doc_no="CB-002",
            sign_status=DeliverableSignStatus.PENDING,
        )
        resp = await client.get(
            "/api/v1/deliverables",
            headers=auth,
            params={"project_id": str(project_id), "sign_status": "PENDING"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["doc_no"] == "CB-002"

    async def test_total_is_not_capped_by_limit(
        self, client, auth, db_session, project_id
    ):
        """total 必须反映真实总数，不能是 len(items) —— 前端分页要靠它。"""
        for i in range(3):
            await _make_deliverable(db_session, project_id, doc_no=f"CB-{i:03d}")
        resp = await client.get(
            "/api/v1/deliverables",
            headers=auth,
            params={"project_id": str(project_id), "limit": 1},
        )
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 1

    async def test_other_project_not_leaked(
        self, client, auth, db_session, project_id, owner_id
    ):
        """按 project_id 过滤 —— A 项目看不到 B 项目的交付物。"""
        await _make_deliverable(db_session, project_id, doc_no="CB-MINE")
        other = uuid.uuid4()
        await _make_deliverable(db_session, other, doc_no="CB-OTHER")

        resp = await client.get(
            "/api/v1/deliverables",
            headers=auth,
            params={"project_id": str(project_id)},
        )
        doc_nos = {i["doc_no"] for i in resp.json()["items"]}
        assert doc_nos == {"CB-MINE"}


class TestGetDeliverable:
    async def test_returns_detail(self, client, auth, db_session, project_id):
        row = await _make_deliverable(db_session, project_id)
        resp = await client.get(f"/api/v1/deliverables/{row.deliverable_id}", headers=auth)
        assert resp.status_code == 200, resp.text
        assert resp.json()["doc_no"] == "CB-001"

    async def test_unknown_id_returns_404(self, client, auth):
        resp = await client.get(f"/api/v1/deliverables/{uuid.uuid4()}", headers=auth)
        assert resp.status_code == 404


class TestListVersions:
    async def test_versions_order_is_stable_across_calls(
        self, client, auth, db_session, project_id
    ):
        """Rev 顺序必须**稳定**，而非断言「谁在前」。

        `created_at` 是 `server_default=func.now()`，SQLite 的 CURRENT_TIMESTAMP
        只有秒级粒度 —— 同批写入的行时间戳必然相同，只按 created_at 排序时
        并列行顺序由存储引擎决定。这正是服务层加 version_id tiebreaker 的原因，
        测试锁的是「多次调用结果一致」，因为「哪个 Rev 排前面」在秒级精度下
        本就没有正确答案。
        """
        d = await _make_deliverable(db_session, project_id)
        for rev in ("0", "A", "B"):
            db_session.add(
                DeliverableVersion(
                    deliverable_id=d.deliverable_id,
                    rev=rev,
                    version_purpose="ISSUED_FOR_CONSTRUCTION",
                    description=f"版本 {rev}",
                    record_snapshot_json={},
                    signature_summary_json={},
                )
            )
        await db_session.commit()

        seen = []
        for _ in range(3):
            resp = await client.get(
                f"/api/v1/deliverables/{d.deliverable_id}/versions", headers=auth
            )
            assert resp.status_code == 200, resp.text
            seen.append([v["rev"] for v in resp.json()])
        assert len(seen[0]) == 3
        assert seen[0] == seen[1] == seen[2], seen

    async def test_list_order_is_stable_across_calls(
        self, client, auth, db_session, project_id
    ):
        """交付物列表同样要稳定顺序。

        三行的 created_at 在秒级精度下必然相同，排序靠 doc_no 兜底。
        （doc_no 与 (project,type,scope_type,scope_value) 都是项目内唯一，
        所以这两列合起来已是全序；deliverable_id 只是防御性兜底。）
        """
        for doc_no in ("CB-001", "CB-002", "CB-003"):
            await _make_deliverable(db_session, project_id, doc_no=doc_no)
        seen = []
        for _ in range(3):
            resp = await client.get(
                "/api/v1/deliverables",
                headers=auth,
                params={"project_id": str(project_id)},
            )
            seen.append([i["deliverable_id"] for i in resp.json()["items"]])
        assert seen[0] == seen[1] == seen[2], seen

    async def test_version_response_omits_heavy_json(
        self, client, auth, db_session, project_id
    ):
        """大 JSONB 不进列表响应 —— 那是 snapshot 端点的职责。"""
        d = await _make_deliverable(db_session, project_id)
        db_session.add(
            DeliverableVersion(
                deliverable_id=d.deliverable_id,
                rev="0",
                version_purpose="ISSUED_FOR_CONSTRUCTION",
                description="v0",
                record_snapshot_json={"records": list(range(100))},
                signature_summary_json={"steps": ["a", "b"]},
            )
        )
        await db_session.commit()

        resp = await client.get(f"/api/v1/deliverables/{d.deliverable_id}/versions", headers=auth)
        item = resp.json()[0]
        assert "record_snapshot_json" not in item
        assert "signature_summary_json" not in item
        assert "pdf_file_path" not in item

    async def test_unknown_deliverable_returns_404(self, client, auth):
        resp = await client.get(f"/api/v1/deliverables/{uuid.uuid4()}/versions", headers=auth)
        assert resp.status_code == 404


class TestSnapshot:
    async def test_returns_version_with_bindings(
        self, client, auth, db_session, project_id
    ):
        d = await _make_deliverable(db_session, project_id)
        v = DeliverableVersion(
            deliverable_id=d.deliverable_id,
            rev="0",
            version_purpose="ISSUED_FOR_CONSTRUCTION",
            description="v0",
            record_snapshot_json={"count": 2},
            signature_summary_json={"steps": ["design"]},
        )
        db_session.add(v)
        await db_session.flush()
        db_session.add(
            DeliverableRecordBinding(
                deliverable_version_id=v.version_id,
                record_type="PUMP",
                record_id=uuid.uuid4(),
                record_hash="a" * 64,
            )
        )
        db_session.add(
            DeliverableRecordBinding(
                deliverable_version_id=v.version_id,
                record_type="PUMP",
                record_id=uuid.uuid4(),
                record_hash="b" * 64,
                old_record_hash_before_change="c" * 64,
            )
        )
        await db_session.commit()

        resp = await client.get(
            f"/api/v1/deliverables/{d.deliverable_id}/versions/0/snapshot",
            headers=auth,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["rev"] == "0"
        assert body["doc_no"] == "CB-001"
        assert body["record_snapshot_json"] == {"count": 2}
        assert body["signature_summary_json"] == {"steps": ["design"]}
        assert len(body["bindings"]) == 2
        assert {b["record_hash"] for b in body["bindings"]} == {"a" * 64, "b" * 64}

    async def test_bindings_are_deterministically_ordered(
        self, client, auth, db_session, project_id
    ):
        """绑定顺序必须稳定 —— 报表按顺序渲染，不能依赖 DB 返回顺序。"""
        d = await _make_deliverable(db_session, project_id)
        v = DeliverableVersion(
            deliverable_id=d.deliverable_id,
            rev="0",
            version_purpose="ISSUED_FOR_CONSTRUCTION",
            description="v0",
            record_snapshot_json={},
            signature_summary_json={},
        )
        db_session.add(v)
        await db_session.flush()
        ids = []
        for _ in range(4):
            rid = uuid.uuid4()
            ids.append(rid)
            db_session.add(
                DeliverableRecordBinding(
                    deliverable_version_id=v.version_id,
                    record_type="PUMP",
                    record_id=rid,
                    record_hash="h",
                )
            )
        await db_session.commit()

        seen = []
        for _ in range(3):
            resp = await client.get(
                f"/api/v1/deliverables/{d.deliverable_id}/versions/0/snapshot",
                headers=auth,
            )
            seen.append([b["record_id"] for b in resp.json()["bindings"]])
        assert seen[0] == seen[1] == seen[2]
        assert seen[0] == [str(i) for i in sorted(ids)]

    async def test_unknown_rev_returns_404(self, client, auth, db_session, project_id):
        """交付物存在但 Rev 不存在 → 404，不能静默返回空快照。"""
        d = await _make_deliverable(db_session, project_id)
        resp = await client.get(
            f"/api/v1/deliverables/{d.deliverable_id}/versions/ZZ/snapshot",
            headers=auth,
        )
        assert resp.status_code == 404


class TestContract:
    async def test_write_endpoints_absent(self, client, auth):
        """三个写端点尚未实现（P9 范围）—— 显式锁住，避免误以为已可用。"""
        assert (await client.post("/api/v1/deliverables", headers=auth, json={})).status_code == 405

    async def test_endpoints_present_in_openapi(self):
        """确认四个读端点确实进了 OpenAPI 契约（API 漂移闸依赖它）。"""
        from app.main import create_app

        paths = create_app().openapi()["paths"]
        for p in (
            "/api/v1/deliverables",
            "/api/v1/deliverables/{deliverable_id}",
            "/api/v1/deliverables/{deliverable_id}/versions",
            "/api/v1/deliverables/{deliverable_id}/versions/{rev}/snapshot",
        ):
            assert p in paths, p