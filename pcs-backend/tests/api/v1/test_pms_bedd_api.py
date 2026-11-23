"""PMS / BEDD 端点（P10-H · T2 · TODO-195）。

## 为什么要有这个文件

前端 `/pms` · `/bedd` 两页此前**没有数据源** ⇒ ⇒ 只能占位
（TODO-159 / TODO-195）⇒ ⇒ 人裁（2026-11-23）：

- **PMS** = 项目级「管道材料规格」表 + **9 态签署**（继承 `RecordMixin`
  ⇒ ⇒ 走**通用记录工作流**，不另造签署框架）；
- **BEDD** = `projects.bedd_json` 存 **SPEC §7.5 的 9 个分组**
  （⇒ ⇒ 补上那条**从未存在**的写入路径）。

## 本文件钉的规则

### PMS

1. 匿名 ⇒ **401**。
2. 无项目授权 ⇒ **404**（与「不存在」同形 ⇒ ⇒ 枚举不出项目）。
3. 建出来是 **DRAFT** + 有 `record_hash`（⇒ ⇒ 能走变更单 / 送审）。
4. `pms_no` **项目内**唯一 ⇒ ⇒ 重复 ⇒ **409**（不是 500）。
5. **只有 DRAFT 能改** ⇒ ⇒ 锁定态 ⇒ **409**。
6. 别的项目的条目 ⇒ **404**。
7. 送审走**通用工作流**（`/records/PmsItem/{id}/submit-approval`）
   ⇒ ⇒ 状态变 `IN_APPROVAL` ⇒ ⇒ **签署流是真的**。

### BEDD

8. 读不到 ⇒ **空文档**（不是 404）⇒ ⇒ 页面有东西可渲染。
9. 写 ⇒ ⇒ **整份替换** ⇒ ⇒ 往返一致。
10. **未知分组 / 未知字段 ⇒ 422**（结构由白名单保证 ⇒ ⇒ 不静默丢字段）。

## 全部用 `strict_client`

默认 `client` 把项目守卫 mock 成永远 True ⇒ ⇒ 「越权被拒」是**空断言**
⇒ ⇒ 守卫测试**必须**用 `strict_client`（真守卫）。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio


def _tok(user_id: uuid.UUID, role: str = "DESIGNER") -> dict[str, str]:
    token = create_access_token(
        subject=str(user_id), role=role, extra={"user_id": str(user_id)}
    )
    return {"Authorization": f"Bearer {token}"}


async def _mk_project(db_session, owner_id: uuid.UUID) -> tuple[object, uuid.UUID]:
    """工作区 + 项目（**生产形状**：工作区先建、项目后建）。"""
    from app.models.project import Project, Workspace

    ws = Workspace(
        workspace_id=uuid.uuid4(),
        workspace_type="FORMAL",
        owner_id=owner_id,
        name="pms-bedd-test",
        status="ACTIVE",
    )
    db_session.add(ws)
    await db_session.commit()

    pid = uuid.uuid4()
    db_session.add(
        Project(
            project_id=pid,
            project_no=f"P-{pid.hex[:6]}",
            project_name="pms-bedd-test",
            owner_company="t",
            location="t",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
            status="ACTIVE",
            workspace_id=ws.workspace_id,
        )
    )
    await db_session.commit()
    return ws, pid


# ---------------------------------------------------------------------------
# PMS
# ---------------------------------------------------------------------------


async def test_pms_list_requires_authentication(strict_client, db_session):
    """⚠️ **匿名不得读 PMS**（项目数据 ⇒ ⇒ 匿名可读 = 越权）。"""
    _ws, pid = await _mk_project(db_session, uuid.uuid4())
    r = await strict_client.get(f"/api/v1/projects/{pid}/pms")
    assert r.status_code == 401, r.text


async def test_pms_list_without_grant_is_404(strict_client, db_session):
    """⚠️ **无权 ⇒ ⇒ 404**（与「不存在」同形）。"""
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    r = await strict_client.get(f"/api/v1/projects/{pid}/pms", headers=_tok(me))
    assert r.status_code == 404, r.text


async def test_pms_create_is_draft_and_has_hash(strict_client, db_session, grant_project):
    """建出来 ⇒ ⇒ **DRAFT** + 有 `record_hash`（⇒ ⇒ 走工作流的前提）。"""
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    r = await strict_client.post(
        f"/api/v1/projects/{pid}/pms",
        json={
            "pms_no": "PMS-CS-001",
            "description": "碳钢管道一般工况",
            "pms_class": "CS-A",
            "hazard_level": "LOW",
        },
        headers=_tok(me),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["sign_status"] == "DRAFT"
    assert body["record_hash"]
    assert body["hazard_level"] == "LOW"
    assert body["project_id"] == str(pid)


async def test_pms_list_returns_the_items(strict_client, db_session, grant_project):
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    await strict_client.post(
        f"/api/v1/projects/{pid}/pms",
        json={"pms_no": "PMS-SS-002", "hazard_level": "MEDIUM"},
        headers=_tok(me),
    )
    r = await strict_client.get(f"/api/v1/projects/{pid}/pms", headers=_tok(me))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["pms_no"] == "PMS-SS-002"


async def test_pms_duplicate_pms_no_is_409(strict_client, db_session, grant_project):
    """⚠️ **编号项目内唯一** ⇒ ⇒ 重复 ⇒ **409**（不是 500）。"""
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    payload = {"pms_no": "PMS-DUP-001", "hazard_level": "LOW"}
    r1 = await strict_client.post(
        f"/api/v1/projects/{pid}/pms", json=payload, headers=_tok(me)
    )
    assert r1.status_code == 201, r1.text
    r2 = await strict_client.post(
        f"/api/v1/projects/{pid}/pms", json=payload, headers=_tok(me)
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "PMS_NO_CONFLICT"


async def test_pms_invalid_hazard_level_is_422(strict_client, db_session, grant_project):
    """⚠️ **危险等级三值**（LOW / MEDIUM / HIGH）⇒ ⇒ 别的值 ⇒ **422**。"""
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    r = await strict_client.post(
        f"/api/v1/projects/{pid}/pms",
        json={"pms_no": "PMS-X", "hazard_level": "EXTREME"},
        headers=_tok(me),
    )
    assert r.status_code == 422, r.text


async def test_pms_update_draft_ok_and_locked_state_409(
    strict_client, db_session, grant_project
):
    """⚠️ **只有 DRAFT 能改** ⇒ ⇒ 送审后 ⇒ **409**。"""
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    created = (
        await strict_client.post(
            f"/api/v1/projects/{pid}/pms",
            json={"pms_no": "PMS-UPD-001", "description": "旧描述"},
            headers=_tok(me),
        )
    ).json()

    r = await strict_client.patch(
        f"/api/v1/projects/{pid}/pms/{created['item_id']}",
        json={"pms_no": "PMS-UPD-001", "description": "新描述"},
        headers=_tok(me),
    )
    assert r.status_code == 200, r.text
    assert r.json()["description"] == "新描述"

    # ⇒ ⇒ 手工把状态推到 IN_APPROVAL（模拟已送审）⇒ ⇒ 再改 ⇒ ⇒ 409
    from app.models.pms import PmsItem

    item = await db_session.get(PmsItem, uuid.UUID(created["item_id"]))
    item.sign_status = "IN_APPROVAL"
    await db_session.commit()

    r2 = await strict_client.patch(
        f"/api/v1/projects/{pid}/pms/{created['item_id']}",
        json={"pms_no": "PMS-UPD-001", "description": "送审后再改"},
        headers=_tok(me),
    )
    assert r2.status_code == 409, r2.text


async def test_pms_list_shows_submitted_items(strict_client, db_session, grant_project):
    """⚠️ **送审中的条目也必须在列表里**（台账页 ⇒ 提交完不能「消失」）。"""
    from app.models.pms import PmsItem

    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    created = (
        await strict_client.post(
            f"/api/v1/projects/{pid}/pms",
            json={"pms_no": "PMS-INAP-001"},
            headers=_tok(me),
        )
    ).json()
    item = await db_session.get(PmsItem, uuid.UUID(created["item_id"]))
    item.sign_status = "IN_APPROVAL"
    await db_session.commit()

    r = await strict_client.get(f"/api/v1/projects/{pid}/pms", headers=_tok(me))
    assert r.status_code == 200, r.text
    assert [i["pms_no"] for i in r.json()["items"]] == ["PMS-INAP-001"]


async def test_pms_list_excludes_obsolete(strict_client, db_session, grant_project):
    """⚠️ **作废的行不进台账**（其余 8 态都进）。"""
    from app.models.pms import PmsItem

    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    created = (
        await strict_client.post(
            f"/api/v1/projects/{pid}/pms",
            json={"pms_no": "PMS-OBS-001"},
            headers=_tok(me),
        )
    ).json()
    item = await db_session.get(PmsItem, uuid.UUID(created["item_id"]))
    item.sign_status = "OBSOLETE"
    await db_session.commit()

    r = await strict_client.get(f"/api/v1/projects/{pid}/pms", headers=_tok(me))
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []


async def test_pms_other_projects_item_is_404(strict_client, db_session, grant_project):
    """⚠️ **别的项目的条目 ⇒ ⇒ 404**（不泄漏存在性）。"""
    me = uuid.uuid4()
    other = uuid.uuid4()
    _ws_a, pid_a = await _mk_project(db_session, me)
    _ws_b, pid_b = await _mk_project(db_session, other)
    await grant_project(me, pid_a)
    await grant_project(other, pid_b)
    created = (
        await strict_client.post(
            f"/api/v1/projects/{pid_b}/pms",
            json={"pms_no": "PMS-OTHER-001"},
            headers=_tok(other),
        )
    ).json()
    r = await strict_client.get(
        f"/api/v1/projects/{pid_a}/pms/{created['item_id']}", headers=_tok(me)
    )
    assert r.status_code == 404, r.text


async def test_pms_submit_approval_goes_through_generic_workflow(
    strict_client, db_session, grant_project
):
    """⚠️ **签署流是真的** ⇒ ⇒ 送审走**通用记录工作流** ⇒ ⇒ 状态变 IN_APPROVAL。

    ⇒ ⇒ 这条断言证明「PMS 走的是仓内既有的 9 态工作流」⇒ ⇒ 不是自造一套。
    """
    from app.services.signature_matrix_service import SignatureMatrixService

    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    # 项目要有 RECORD 签署矩阵 ⇒ ⇒ 送审才有批准链
    await SignatureMatrixService.ensure_default_record_matrix(
        db_session, project_id=pid
    )
    await db_session.commit()

    created = (
        await strict_client.post(
            f"/api/v1/projects/{pid}/pms",
            json={"pms_no": "PMS-SIGN-001"},
            headers=_tok(me),
        )
    ).json()

    r = await strict_client.post(
        f"/api/v1/records/PmsItem/{created['item_id']}/submit-approval",
        json={"reason": "提交审核"},
        headers=_tok(me),
    )
    assert r.status_code == 200, r.text
    assert r.json()["to_status"] == "IN_APPROVAL"
    # ⇒ ⇒ 行上的状态也真的是 IN_APPROVAL（不是响应编的常量）
    from app.models.pms import PmsItem

    row = await db_session.get(PmsItem, uuid.UUID(created["item_id"]))
    await db_session.refresh(row)
    assert row.sign_status == "IN_APPROVAL"


# ---------------------------------------------------------------------------
# BEDD
# ---------------------------------------------------------------------------


async def test_bedd_read_requires_authentication(strict_client, db_session):
    _ws, pid = await _mk_project(db_session, uuid.uuid4())
    r = await strict_client.get(f"/api/v1/projects/{pid}/bedd")
    assert r.status_code == 401, r.text


async def test_bedd_read_without_grant_is_404(strict_client, db_session):
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    r = await strict_client.get(f"/api/v1/projects/{pid}/bedd", headers=_tok(me))
    assert r.status_code == 404, r.text


async def test_bedd_empty_document_when_never_written(strict_client, db_session, grant_project):
    """⚠️ **没写过 ⇒ ⇒ 空文档**（不是 404）⇒ ⇒ 页面有东西可渲染。"""
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    r = await strict_client.get(f"/api/v1/projects/{pid}/bedd", headers=_tok(me))
    assert r.status_code == 200, r.text
    # ⚠️ **9 个分组都是 null**（不是 404）⇒ ⇒ 页面有东西可渲染
    document = r.json()["document"]
    assert set(document) == {
        "meteorology", "hydrology_geology", "seismic", "utilities",
        "emission_limits", "design_criteria", "safety_fire", "flare",
        "interface_conditions",
    }
    assert all(v is None for v in document.values())


async def test_bedd_write_then_read_round_trip(strict_client, db_session, grant_project):
    """⚠️ **写入路径存在**（此前 `bedd_json` **没有任何写入路径**）⇒ ⇒ 往返一致。"""
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    payload = {
        "meteorology": {"temperature": 25.5, "altitude": 10},
        "flare": {"back_pressure": 101.3},
    }
    r = await strict_client.put(
        f"/api/v1/projects/{pid}/bedd", json=payload, headers=_tok(me)
    )
    assert r.status_code == 200, r.text
    assert r.json()["document"]["meteorology"]["temperature"] == 25.5
    assert r.json()["document"]["flare"]["back_pressure"] == 101.3

    r2 = await strict_client.get(f"/api/v1/projects/{pid}/bedd", headers=_tok(me))
    assert r2.status_code == 200, r2.text
    assert r2.json()["document"]["meteorology"]["temperature"] == 25.5
    assert r2.json()["document"]["meteorology"]["altitude"] == 10
    assert r2.json()["document"]["flare"]["back_pressure"] == 101.3


async def test_bedd_unknown_group_is_422(strict_client, db_session, grant_project):
    """⚠️ **未知分组 ⇒ ⇒ 422**（结构由白名单保证 ⇒ ⇒ 不静默丢字段）。"""
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    r = await strict_client.put(
        f"/api/v1/projects/{pid}/bedd",
        json={"not_a_group": {"x": 1}},
        headers=_tok(me),
    )
    assert r.status_code == 422, r.text


async def test_bedd_unknown_field_is_422(strict_client, db_session, grant_project):
    """⚠️ **分组里的未知字段 ⇒ ⇒ 422**。"""
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    r = await strict_client.put(
        f"/api/v1/projects/{pid}/bedd",
        json={"meteorology": {"not_a_field": 1}},
        headers=_tok(me),
    )
    assert r.status_code == 422, r.text


async def test_bedd_write_by_process_controller(strict_client, db_session, grant_project):
    """⚠️ **工艺角色要能写**（公用工程 / 排放限值那几组是工艺填的）。"""
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    r = await strict_client.put(
        f"/api/v1/projects/{pid}/bedd",
        json={"utilities": {"steam": "自产"}},
        headers=_tok(me, role="PROCESS_CONTROLLER"),
    )
    assert r.status_code == 200, r.text


async def test_bedd_write_requires_write_role(strict_client, db_session, grant_project):
    """⚠️ **审核角色不写数据源** ⇒ ⇒ REVIEWER 写 ⇒ ⇒ 403。"""
    me = uuid.uuid4()
    _ws, pid = await _mk_project(db_session, me)
    await grant_project(me, pid)
    r = await strict_client.put(
        f"/api/v1/projects/{pid}/bedd",
        json={"meteorology": {"temperature": 1}},
        headers=_tok(me, role="REVIEWER"),
    )
    assert r.status_code == 403, r.text
