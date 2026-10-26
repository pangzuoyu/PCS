"""签署矩阵管理面端点测试（TODO-070 · P9A-DLV-011 T3）。

## 这组测试钉住的失败模式

| # | 失败模式 | 期望 |
|---|---|---|
| RF-1 | **模板是全局表** ⇒ 普通用户能改 ⇒ 别的项目在用的矩阵跟着变 | 建/改模板 = **SYSTEM_ADMIN** |
| RF-2 | 坏 `steps_json` **入库** ⇒ 签署少一道校核而没人知道 | 写入时**严格校验** ⇒ 422，且**不落库** |
| RF-3 | 绑定不看项目授权 ⇒ 把矩阵绑到**别人**的项目 | 绑定 = 角色 + **项目授权**（无权 404） |
| RF-4 | 同一项目同一模块**两行**绑定 ⇒「谁该签这一步」两个答案 | 换绑 = 改同一行（唯一约束兜底） |
| RF-5 | 响应含裸字段 ⇒ 前端只能拿 `object`（P9A-DLV-010） | 零裸字段（字段集合被钉死） |
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.deliverable import (
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.project import UserProject

pytestmark = pytest.mark.asyncio


def _token(*, role: str, subject: str = "matrix-user"):
    from app.core.security import create_access_token

    return {
        "Authorization": f"Bearer "
        f"{create_access_token(subject=subject, role=role)}"
    }


def _actor_id(subject: str = "matrix-user") -> uuid.UUID:
    """`current_actor` 的 user_id 推导规则（uuid5(DNS, sub)）。"""
    return uuid.uuid5(uuid.NAMESPACE_DNS, subject)


async def _grant(db, user_id: uuid.UUID, project_id: uuid.UUID, role: str = "DESIGNER"):
    db.add(UserProject(user_id=user_id, project_id=project_id, role_in_project=role))
    await db.flush()


_STEPS = [
    {"step_order": 1, "sign_role": "CHECKER"},
    {"step_order": 2, "sign_role": "APPROVER"},
]


def _payload(**over):
    body = {
        "matrix_name": "项目专用矩阵",
        "module": "RECORD",
        "doc_type": "CALCULATION_BOOK",
        "version_purpose": "ISSUED_FOR_CONSTRUCTION",
        "steps": _STEPS,
        "status": "ACTIVE",
    }
    body.update(over)
    return body


# ---------------------------------------------------------------------------
# 模板 CRUD
# ---------------------------------------------------------------------------


async def test_admin_can_create_matrix(client, db):
    """SYSTEM_ADMIN ⇒ 建矩阵成功。"""
    resp = await client.post(
        "/api/v1/signature-matrices",
        json=_payload(),
        headers=_token(role="SYSTEM_ADMIN"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["matrix_name"] == "项目专用矩阵"
    assert [s["step_order"] for s in body["steps"]] == [1, 2]
    rows = (await db.execute(select(SignatureMatrix))).scalars().all()
    assert len(rows) == 1


async def test_designer_cannot_create_matrix(client):
    """⚠️ RF-1：模板是**全局表** ⇒ 普通用户改它 ⇒ 别的项目跟着变 ⇒ 403。"""
    resp = await client.post(
        "/api/v1/signature-matrices",
        json=_payload(),
        headers=_token(role="DESIGNER"),
    )
    assert resp.status_code == 403, resp.text


async def test_create_with_bad_steps_rejected_and_not_stored(client, db):
    """⚠️ RF-2：坏步骤 ⇒ 422，且**一行都不入库**（不部分入库）。

    `step_order` 是**请求形状** ⇒ Pydantic 先挡（422 `VALIDATION_ERROR`）；
    形状对但**语义坏**的（重复序号 / 空步骤 / 非字符串角色）由 service 的
    `validate_steps` 挡（422 `SIGNATURE_MATRIX_INVALID`，见
    `tests/services/test_signature_matrix_service.py`）。
    """
    resp = await client.post(
        "/api/v1/signature-matrices",
        json=_payload(steps=[{"step_order": 1, "sign_role": "CHECKER"},
                            {"step_order": "x", "sign_role": "REVIEWER"}]),
        headers=_token(role="SYSTEM_ADMIN"),
    )
    assert resp.status_code == 422, resp.text
    rows = (await db.execute(select(SignatureMatrix))).scalars().all()
    assert rows == [], "校验没过 ⇒ 一行都不许落库"


async def test_duplicate_step_order_rejected(client):
    """两个同序号的步骤 ⇒「谁该签这一步」两个答案 ⇒ 422。"""
    resp = await client.post(
        "/api/v1/signature-matrices",
        json=_payload(steps=[{"step_order": 1, "sign_role": "CHECKER"},
                            {"step_order": 1, "sign_role": "REVIEWER"}]),
        headers=_token(role="SYSTEM_ADMIN"),
    )
    assert resp.status_code == 422, resp.text


async def test_list_and_get_matrix(client, db):
    """读面：列表 + 详情（不存在 ⇒ 404）。"""
    created = await client.post(
        "/api/v1/signature-matrices",
        json=_payload(),
        headers=_token(role="SYSTEM_ADMIN"),
    )
    matrix_id = created.json()["matrix_id"]

    listing = await client.get(
        "/api/v1/signature-matrices", headers=_token(role="DESIGNER")
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    detail = await client.get(
        f"/api/v1/signature-matrices/{matrix_id}", headers=_token(role="DESIGNER")
    )
    assert detail.status_code == 200
    assert detail.json()["matrix_id"] == matrix_id

    missing = await client.get(
        f"/api/v1/signature-matrices/{uuid.uuid4()}",
        headers=_token(role="DESIGNER"),
    )
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# 项目绑定
# ---------------------------------------------------------------------------


async def test_bind_requires_designer_side_role(client, db, project_id):
    """⚠️ RF-3（角色那一半）：REVIEWER 不能给项目绑矩阵 ⇒ 403。

    ⚠️ **项目授权那一半在本 fixture 下测不了**：`client` fixture 把
    `UserProjectService.check_user_project_access` mock 成恒 True
    （见 `tests/conftest.py` 的 client fixture 注释：「mock ⇒ True。
    测试不验证 ACL 行为」）⇒ 无权访问 ⇒ 404 由 `_guard` 自己的测试覆盖。
    """
    created = await client.post(
        "/api/v1/signature-matrices",
        json=_payload(),
        headers=_token(role="SYSTEM_ADMIN"),
    )
    matrix_id = created.json()["matrix_id"]

    resp = await client.post(
        f"/api/v1/projects/{project_id}/signature-matrices",
        json={"module": "RECORD", "matrix_id": matrix_id},
        headers=_token(role="REVIEWER"),
    )
    assert resp.status_code == 403, resp.text


async def test_bind_and_rebind_keep_one_row(client, db, project_id):
    """⚠️ RF-4：换绑 = **改同一行**（不是再建一行）。"""
    me = _actor_id()
    await _grant(db, me, project_id)
    m1 = await client.post(
        "/api/v1/signature-matrices",
        json=_payload(),
        headers=_token(role="SYSTEM_ADMIN"),
    )
    m2 = await client.post(
        "/api/v1/signature-matrices",
        json=_payload(matrix_name="另一个矩阵"),
        headers=_token(role="SYSTEM_ADMIN"),
    )

    first = await client.post(
        f"/api/v1/projects/{project_id}/signature-matrices",
        json={"module": "RECORD", "matrix_id": m1.json()["matrix_id"]},
        headers=_token(role="DESIGNER"),
    )
    assert first.status_code == 200, first.text
    assert first.json()["matrix_name"] == "项目专用矩阵"

    second = await client.post(
        f"/api/v1/projects/{project_id}/signature-matrices",
        json={"module": "RECORD", "matrix_id": m2.json()["matrix_id"]},
        headers=_token(role="DESIGNER"),
    )
    assert second.status_code == 200, second.text
    assert second.json()["matrix_name"] == "另一个矩阵"

    rows = (
        await db.execute(
            select(ProjectSignatureMatrixBinding).where(
                ProjectSignatureMatrixBinding.project_id == project_id
            )
        )
    ).scalars().all()
    assert len(rows) == 1, "同一项目同一模块只允许一行绑定"
    assert str(rows[0].matrix_id) == m2.json()["matrix_id"]


async def test_unbind(client, db, project_id):
    """解绑；本来就没绑 ⇒ `unbound=false`（**不是** 404）。"""
    me = _actor_id()
    await _grant(db, me, project_id)
    created = await client.post(
        "/api/v1/signature-matrices",
        json=_payload(),
        headers=_token(role="SYSTEM_ADMIN"),
    )
    await client.post(
        f"/api/v1/projects/{project_id}/signature-matrices",
        json={"module": "RECORD", "matrix_id": created.json()["matrix_id"]},
        headers=_token(role="DESIGNER"),
    )

    resp = await client.delete(
        f"/api/v1/projects/{project_id}/signature-matrices/RECORD",
        headers=_token(role="DESIGNER"),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["unbound"] is True

    again = await client.delete(
        f"/api/v1/projects/{project_id}/signature-matrices/RECORD",
        headers=_token(role="DESIGNER"),
    )
    assert again.status_code == 200
    assert again.json()["unbound"] is False


# ---------------------------------------------------------------------------
# 契约
# ---------------------------------------------------------------------------


async def test_response_has_no_bare_fields(client):
    """⚠️ RF-5：P9A-DLV-010 零裸字段 —— 字段集合被钉死。"""
    resp = await client.post(
        "/api/v1/signature-matrices",
        json=_payload(),
        headers=_token(role="SYSTEM_ADMIN"),
    )
    assert set(resp.json()) == {
        "matrix_id",
        "matrix_name",
        "module",
        "doc_type",
        "version_purpose",
        "status",
        "steps",
        "created_at",
        "updated_at",
    }
    assert set(resp.json()["steps"][0]) == {
        "step_order",
        "sign_role",
        "required",
        "can_self_check",
        "can_skip",
    }
