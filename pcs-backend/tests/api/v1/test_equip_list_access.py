"""**设备台账的项目授权**（P10-C · T3 · 2026-11-19）。

## 为什么要有这个文件

`GET /api/v1/equipment-list` 此前**只有角色闸**（`require_roles`）
⇒ ⇒ 任何 DESIGNER / PROCESS_CONTROLLER 都能列**全部项目**的设备台账
⇒ ⇒ **跨项目读**（与 TODO-179 / TODO-186 同族：物流面与工作区面都栽过这一条）。

⇒ ⇒ 现在（本批补）：

| 请求 | 行为 |
|---|---|
| 传了 `project_id` | 该项目必须对我**有授权** ⇒ 否则 **404**（与「不存在」同形 ⇒ 枚举不出项目） |
| **没传** | 只返回**我有授权的项目**的设备（`user_projects` 有效行）⇒ SYSTEM_ADMIN 全局 bypass |

## 为什么用 `strict_client`

默认 `client` 把项目守卫 mock 成永远 True ⇒ ⇒ 在它上面「越权被拒」是**空断言**
⇒ ⇒ 本文件**全部**用 `strict_client`（真守卫）。
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


async def _mk_project_with_equipment(
    db_session, label: str
) -> tuple[uuid.UUID, str, uuid.UUID]:
    """建一个项目 + 一台设备（**生产形状**：工作区 → 项目 → type_code → 设备）。

    ⇒ ⇒ 返回 `(project_id, tag_number, equipment_id)`。
    """
    from app.models.equipment import EquipmentList, EquipmentTypeCode
    from app.models.project import Project, Workspace

    ws_id = uuid.uuid4()
    pid = uuid.uuid4()
    db_session.add(
        Workspace(
            workspace_id=ws_id,
            workspace_type="FORMAL",
            owner_id=uuid.uuid4(),
            name="equip-access-test",
            status="ACTIVE",
        )
    )
    db_session.add(
        Project(
            project_id=pid,
            project_no=f"P-{label}-{pid.hex[:6]}",
            project_name=label,
            owner_company="t",
            location="t",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
            status="ACTIVE",
            workspace_id=ws_id,
        )
    )
    db_session.add(
        EquipmentTypeCode(
            project_id=pid,
            type_code="PUMP",
            equipment_description="泵",
            category="ROTATING",
        )
    )
    await db_session.commit()

    tag = f"TAG-{label}-{pid.hex[:4]}"
    equipment_id = uuid.uuid4()
    db_session.add(
        EquipmentList(
            equipment_id=equipment_id,
            equipment_type_project_id=pid,
            type_code="PUMP",
            equipment_name=f"{label} 泵",
            tag_number=tag,
            project_id=pid,
            workspace_id=ws_id,
            equipment_status="A",
            approval_depth=1,
        )
    )
    await db_session.commit()
    return pid, tag, equipment_id


# ---------------------------------------------------------------------------


async def test_equipment_list_without_any_grant_sees_nothing(strict_client, db_session):
    """⚠️ **一条授权都没有 ⇒ ⇒ 看不到任何设备**（此前 = 看得到全部）。"""
    me = uuid.uuid4()
    _pid, tag, _eid = await _mk_project_with_equipment(db_session, "OTHER")

    r = await strict_client.get("/api/v1/equipment-list", headers=_tok(me))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 0
    assert not any(item["tag_number"] == tag for item in body["items"])


async def test_equipment_list_only_shows_authorized_projects(
    strict_client, db_session, grant_project
):
    """⚠️ **只看得到我有授权的项目**的设备（别人的看不到）。"""
    me = uuid.uuid4()
    other = uuid.uuid4()
    pid_mine, tag_mine, _eid = await _mk_project_with_equipment(db_session, "MINE")
    _pid_other, tag_other, _eid = await _mk_project_with_equipment(db_session, "OTHER")
    await grant_project(me, pid_mine)
    await grant_project(other, _pid_other)

    r = await strict_client.get("/api/v1/equipment-list", headers=_tok(me))
    assert r.status_code == 200, r.text
    body = r.json()
    tags = [item["tag_number"] for item in body["items"]]
    assert tag_mine in tags
    assert tag_other not in tags


async def test_equipment_list_of_an_unauthorized_project_is_404(
    strict_client, db_session, grant_project
):
    """⚠️ **传别人的 project_id ⇒ ⇒ 404**（与「不存在」同形 ⇒ 枚举不出项目）。"""
    me = uuid.uuid4()
    other = uuid.uuid4()
    pid_other, _tag, _eid = await _mk_project_with_equipment(db_session, "OTHER")
    pid_mine, _tag2, mine_eid = await _mk_project_with_equipment(db_session, "MINE")
    await grant_project(me, pid_mine)

    r = await strict_client.get(
        f"/api/v1/equipment-list?project_id={pid_other}", headers=_tok(me)
    )
    assert r.status_code == 404, r.text


async def test_equipment_list_with_grant_and_project_filter_is_200(
    strict_client, db_session, grant_project
):
    """⚠️ **有授权 + 传自己的 project_id ⇒ ⇒ 200 且看得到那一台**。"""
    me = uuid.uuid4()
    pid, tag, _eid = await _mk_project_with_equipment(db_session, "MINE")
    await grant_project(me, pid)

    r = await strict_client.get(
        f"/api/v1/equipment-list?project_id={pid}", headers=_tok(me)
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["tag_number"] == tag


async def test_equipment_list_system_admin_sees_everything(strict_client, db_session):
    """⚠️ **SYSTEM_ADMIN 全局 bypass**（与仓内其它项目守卫同口径）。"""
    admin = uuid.uuid4()
    _pid, tag, _eid = await _mk_project_with_equipment(db_session, "ANY")

    r = await strict_client.get("/api/v1/equipment-list", headers=_tok(admin, "SYSTEM_ADMIN"))
    assert r.status_code == 200, r.text
    tags = [item["tag_number"] for item in r.json()["items"]]
    assert tag in tags


async def test_equipment_list_requires_authentication(strict_client, db_session):
    """⚠️ **匿名不得读设备台账**。"""
    r = await strict_client.get("/api/v1/equipment-list")
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# ⚠️ **sync（写面）**：写入落在「源记录的项目」上（2026-11-19 · P10-C · T3）
# ---------------------------------------------------------------------------


async def _mk_checked_pump(db_session, project_id, workspace_id, tag="P-1001"):
    """造一条 **CHECKED** 的泵结果（= sync 的源记录）。"""
    from app.models.calc import PumpResult
    from app.models.enums import RecordSignStatus9

    pump = PumpResult(
        pump_id=uuid.uuid4(),
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number=tag,
        sign_status=RecordSignStatus9.CHECKED,
        approval_depth=2,
        basic_info_json={},
        fluid_properties_json={},
        flow_rates_json={},
        suction_calculation_json={},
        discharge_calculation_json={},
        differential_pressure_json={},
        design_pressure_json={},
        power_consumption_json={},
    )
    db_session.add(pump)
    await db_session.commit()
    return pump


async def test_sync_of_another_projects_source_record_is_404(
    strict_client, db_session, grant_project
):
    """⚠️⚠️ **跨项目写**：无权 ⇒ ⇒ 同步别人的源记录 ⇒ ⇒ **404**（不写）。

    ⇒ ⇒ 写入落在**源记录的 `project_id`** 上（`sync_from_source` 用的是它）
    ⇒ ⇒ 此前**只**查了 equipment 行的项目 ⇒ ⇒ 写进**别的项目**。

    ⚠️⚠️ **夹具的形状很重要**（本条用例第一版写错了 ⇒ ⇒ 断言**恒真**）：
    - `equipment_id` ⇒ ⇒ 必须是**我有权**的那个项目里的设备
      ⇒ ⇒ 否则 `check_record_access_or_404(existing)` **自己**就 404 了
      ⇒ ⇒ ⇒ 断言会在**守卫之前**成立 ⇒ ⇒ 删掉新守卫也照样绿（**不敏感**）。
    - `source_record_id` ⇒ ⇒ 必须是**别人项目**里的 CHECKED 源记录
      ⇒ ⇒ 删掉新守卫 ⇒ ⇒ sync 照常执行 ⇒ ⇒ **断言变红**（这才是敏感）。
    """
    me = uuid.uuid4()
    other = uuid.uuid4()
    pid_other, _tag, _eid = await _mk_project_with_equipment(db_session, "OTHER")
    pid_mine, _tag2, mine_equipment_id = await _mk_project_with_equipment(
        db_session, "MINE"
    )
    await grant_project(me, pid_mine)
    # ⇒ ⇒ 源记录在**别人**的项目里 ⇒ ⇒ 写入会落到那个项目
    pump = await _mk_checked_pump(db_session, pid_other, uuid.uuid4())

    r = await strict_client.post(
        f"/api/v1/equipment-list/{mine_equipment_id}/sync",
        json={
            "source_module": "PUMP",
            "source_service": "pump_service",
            "source_record_id": str(pump.pump_id),
        },
        headers=_tok(me),
    )
    # ⇒ ⇒ 「equipment 不存在」也是 404 ⇒ ⇒ 两种情形**同形**（不泄露存在性）
    assert r.status_code == 404, r.text

    # ⇒ ⇒ **没写进别人项目**（源记录那台泵**不该**变成设备行）
    from app.models.equipment import EquipmentList
    from sqlalchemy import select

    rows = (
        await db_session.execute(
            select(EquipmentList).where(EquipmentList.tag_number == "P-1001")
        )
    ).scalars().all()
    assert not rows, "无权的源记录**不应**被同步成设备行"


async def test_bulk_sync_skips_records_of_unauthorized_projects(
    strict_client, db_session, grant_project
):
    """⚠️⚠️ **bulk-sync 也要逐条预检** ⇒ 无权 ⇒ ⇒ 标 `failed` 且**不写**。

    ⇒ ⇒ 此前 bulk-sync **完全没有项目守卫** ⇒ ⇒ 批量同步别人的源记录
    ⇒ ⇒ 在别人项目里写出设备行。
    """
    me = uuid.uuid4()
    other = uuid.uuid4()
    pid_other, _tag, _eid = await _mk_project_with_equipment(db_session, "OTHER")
    pid_mine, _tag2, mine_eid = await _mk_project_with_equipment(db_session, "MINE")
    await grant_project(me, pid_mine)
    pump_other = await _mk_checked_pump(db_session, pid_other, uuid.uuid4(), tag="P-OTHER")
    pump_mine = await _mk_checked_pump(db_session, pid_mine, uuid.uuid4(), tag="P-MINE")

    r = await strict_client.post(
        "/api/v1/equipment-list/bulk-sync",
        json={
            "entries": [
                {
                    "source_module": "PUMP",
                    "source_service": "pump_service",
                    "source_record_id": str(pump_other.pump_id),
                },
                {
                    "source_module": "PUMP",
                    "source_service": "pump_service",
                    "source_record_id": str(pump_mine.pump_id),
                },
            ]
        },
        headers=_tok(me),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # ⇒ ⇒ 我有权的那条同步成功
    assert len(body["succeeded"]) == 1
    assert body["succeeded"][0]["item"]["tag_number"] == "P-MINE"
    # ⇒ ⇒ 别人的那条进 failed（**没写**）
    assert len(body["failed"]) == 1
    assert body["failed"][0]["error_code"] == "PROJECT_ACCESS_DENIED"

    # ⇒ ⇒ **库里不能有别人项目的那条设备**
    from app.models.equipment import EquipmentList
    from sqlalchemy import select

    rows = (
        await db_session.execute(
            select(EquipmentList).where(EquipmentList.tag_number == "P-OTHER")
        )
    ).scalars().all()
    assert not rows, "无权的源记录**不应**被同步成设备行"
