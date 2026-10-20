"""`CostEstResult` 的项目隔离 —— P9A-5 Task B（TODO-061）。

## 这条测试钉的是什么

2026-10-20 实测：`app/api/v1/cost_est.py` 的 **8 个端点全部没有项目鉴权**
（`grep check_project_access_or_404 app/api/v1/cost_est.py` → 0 命中），
而 `CostEstResult`（`app/models/calc.py:1193` `class CostEstResult(Base)`）
**连 `project_id` 列都没有** ⇒ 守卫连挂都挂不上。

后果比 bug-2039 那族更宽：

- **写面**：任何持 `DESIGNER` 的登录用户能改/删**别人项目**的造价结果。
- **读面**（本文件最在意的一条）：`GET /cost-est/results` 不传参时
  `list_cost_est_results_service` 走「不传 = 全量」⇒ **整表返回**，
  即**跨项目的数据泄漏**（信息本身，不只是可写性）。
- `equipment_id` 虽是 UNIQUE 且 `equipment_list.project_id` NOT NULL
  ⇒ JOIN 反查项目是可行的，但**读侧按项目过滤仍需 JOIN**，
  且通用守卫 `check_record_access_or_404` 读的是 `record.project_id`。

## 裁决：补 `cost_est_results.project_id` 列（不是 JOIN）

依据三处一致：ADR-0050 `:403`/`:477` + `TODOS.md` TODO-048
「归属：P9A（`cost_est_results` 补列时一并处理）」。
⚠️ **不补** `workspace_id` / `sign_status` / `updated_at` ——
该表的设计是「与设备 1:1、状态跟随设备」，补了就是另一套设计。

## 为什么每条都断言「数据没变」而不是只看状态码

bug-2039 的教训：旧顺序下响应**也是** 404，可**行已经改了**。
只断言状态码的守卫测试对着旧代码照样绿（假绿）。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select

from app.models.calc import CostEstResult
from app.models.equipment import EquipmentList
from app.services.user_project_service import UserProjectService

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _no_project_access(*_args: Any, **_kwargs: Any) -> bool:
    """模拟「该用户没有这个项目的授权」。"""
    return False


async def _make_equipment(db, *, project_id: uuid.UUID | None = None) -> EquipmentList:
    eq = EquipmentList(
        equipment_id=uuid.uuid4(),
        type_code="PUMP",
        equipment_name=f"E-{uuid.uuid4().hex[:8]}",
        tag_number=f"T-{uuid.uuid4().hex[:8]}",
        project_id=project_id or uuid.uuid4(),
        workspace_id=uuid.uuid4(),
    )
    db.add(eq)
    await db.commit()
    await db.refresh(eq)
    return eq


async def _make_cost_est(
    db, *, equipment: EquipmentList, **overrides: Any
) -> CostEstResult:
    """建一行 CostEstResult。

    ⚠️ `project_id` 是本 Task B 新增的列 —— 建行时**显式**给一个值，
    免得测试因为「忘了补列」而红得莫名其妙。
    """
    kwargs: dict[str, Any] = dict(
        equipment_id=equipment.equipment_id,
        estimated_cost=1000.0,
        currency="USD",
        cost_index_year=2019,
        created_at=datetime.now(UTC),
        record_hash="a1b2c3d4e5f60718",
        project_id=equipment.project_id,
    )
    kwargs.update(overrides)
    row = CostEstResult(**kwargs)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


def _create_body(equipment_id: uuid.UUID) -> dict[str, Any]:
    return {
        "equipment_id": str(equipment_id),
        "estimated_cost": 1000.0,
        "currency": "USD",
        "cost_index_year": 2019,
    }


def _six_tenths_body(equipment_id: uuid.UUID) -> dict[str, Any]:
    return {
        "equipment_id": str(equipment_id),
        "reference_cost": 10000.0,
        "reference_cepci": 550.0,
        "target_cepci": 600.0,
        "scaling_exponent": 0.6,
        "estimated_cost": 10909.09,
        "currency": "USD",
        "cost_index_year": 2019,
    }


def _cepci_body(equipment_id: uuid.UUID) -> dict[str, Any]:
    return {
        "equipment_id": str(equipment_id),
        "reference_cost": 10000.0,
        "reference_cepci": 550.0,
        "target_cepci": 600.0,
        "estimated_cost": 10909.09,
        "currency": "USD",
        "cost_index_year": 2019,
    }


def _correlation_body(equipment_id: uuid.UUID) -> dict[str, Any]:
    return {
        "equipment_id": str(equipment_id),
        "equipment_type": "PUMP",
        "scale_parameter": 25.0,
        "correlation_source": "API 650",
        "estimated_cost": 50000.0,
        "currency": "USD",
        "cost_index_year": 2019,
    }

# ---------------------------------------------------------------------------
# 写面：创建
# ---------------------------------------------------------------------------


async def test_create_without_project_access_is_404_and_creates_nothing(
    client, sample_user_token, db_session, monkeypatch
):
    """无权用户在**别人项目的设备**上建造价 ⇒ 404 且**一行都没建**。"""
    monkeypatch.setattr(
        UserProjectService, "check_user_project_access", _no_project_access
    )
    eq = await _make_equipment(db_session)

    r = await client.post(
        "/api/v1/cost-est/results",
        json=_create_body(eq.equipment_id),
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"
    rows = (await db_session.execute(select(CostEstResult))).scalars().all()
    assert not rows, f"无权用户仍建出了 {len(rows)} 行 cost_est"


@pytest.mark.parametrize(
    ("path", "body_fn"),
    [
        ("/api/v1/cost-est/six-tenths-rule/calculate", _six_tenths_body),
        ("/api/v1/cost-est/cepci-adjustment/calculate", _cepci_body),
        ("/api/v1/cost-est/cost-correlation/calculate", _correlation_body),
    ],
    ids=["six-tenths", "cepci", "correlation"],
)
async def test_calculate_without_project_access_is_404_and_creates_nothing(
    client, sample_user_token, db_session, monkeypatch, path, body_fn
):
    """3 个 calc 端点同理：它们同样按 `equipment_id` 落库。"""
    monkeypatch.setattr(
        UserProjectService, "check_user_project_access", _no_project_access
    )
    eq = await _make_equipment(db_session)

    r = await client.post(
        path, json=body_fn(eq.equipment_id), headers=_auth(sample_user_token)
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"
    rows = (await db_session.execute(select(CostEstResult))).scalars().all()
    assert not rows, f"无权用户仍通过 {path} 建出了 {len(rows)} 行"


# ---------------------------------------------------------------------------
# 写面：PATCH / DELETE
# ---------------------------------------------------------------------------


async def test_patch_without_project_access_is_404_and_does_not_write(
    client, sample_user_token, db_session, monkeypatch
):
    """PATCH：404 **且** `estimated_cost` 没变。

    ⚠️ 基线给**有效值** ⇒ 并发检查放行 ⇒ 请求真的走到保存那一步；
    否则 409 短路，本例又变成「什么都没测」。
    """
    monkeypatch.setattr(
        UserProjectService, "check_user_project_access", _no_project_access
    )
    eq = await _make_equipment(db_session)
    row = await _make_cost_est(db_session, equipment=eq)

    r = await client.patch(
        f"/api/v1/cost-est/results/{row.cost_est_id}",
        json={"estimated_cost": 99999.0, "expected_hash": row.record_hash},
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"
    await db_session.refresh(row)
    assert float(row.estimated_cost) == pytest.approx(1000.0), (
        "无权用户的 PATCH 改了 estimated_cost ⇒ 鉴权排在保存之后（bug-2039 同族）"
    )


async def test_delete_without_project_access_is_404_and_keeps_the_row(
    client, sample_user_token, db_session, monkeypatch
):
    """DELETE：404 **且**行还在（cost_est 是物理删除 ⇒ 行消失即删掉了）。"""
    monkeypatch.setattr(
        UserProjectService, "check_user_project_access", _no_project_access
    )
    eq = await _make_equipment(db_session)
    row = await _make_cost_est(db_session, equipment=eq)

    r = await client.delete(
        f"/api/v1/cost-est/results/{row.cost_est_id}",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"
    still_there = (
        await db_session.execute(
            select(CostEstResult).where(CostEstResult.cost_est_id == row.cost_est_id)
        )
    ).scalar_one_or_none()
    assert still_there is not None, "无权用户的 DELETE 把行删掉了"


# ---------------------------------------------------------------------------
# 读面：跨项目数据泄漏（比写面更宽的一条）
# ---------------------------------------------------------------------------


async def test_list_requires_a_project_id(client, sample_user_token):
    """不传 `project_id` ⇒ **422**（旧行为是**整表返回**）。

    ⚠️ 与其余 5 个结果模块一致：它们的 list 端点都是
    `project_id: Annotated[UUID, Query(...)]` **必填**。
    """
    r = await client.get(
        "/api/v1/cost-est/results", headers=_auth(sample_user_token)
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_list_without_project_access_is_404(
    client, sample_user_token, monkeypatch
):
    monkeypatch.setattr(
        UserProjectService, "check_user_project_access", _no_project_access
    )
    r = await client.get(
        f"/api/v1/cost-est/results?project_id={uuid.uuid4()}",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


async def test_list_only_returns_rows_of_the_requested_project(
    client, sample_user_token, db_session
):
    """授权路径：按 `project_id` 过滤 ⇒ 别的项目的行**不出现**。"""
    eq_a = await _make_equipment(db_session)
    eq_b = await _make_equipment(db_session)
    await _make_cost_est(db_session, equipment=eq_a)
    await _make_cost_est(db_session, equipment=eq_b)

    r = await client.get(
        f"/api/v1/cost-est/results?project_id={eq_a.project_id}",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    items = r.json()["items"]
    assert items, "授权用户看不到自己项目的行"
    assert {i["equipment_id"] for i in items} == {str(eq_a.equipment_id)}, (
        "列表混进了别的项目的行"
    )


async def test_get_without_project_access_is_404(
    client, sample_user_token, db_session, monkeypatch
):
    """详情端点同样要守卫（按 `result_id` 直取，最容易越权读）。"""
    monkeypatch.setattr(
        UserProjectService, "check_user_project_access", _no_project_access
    )
    eq = await _make_equipment(db_session)
    row = await _make_cost_est(db_session, equipment=eq)

    r = await client.get(
        f"/api/v1/cost-est/results/{row.cost_est_id}",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# 列本身：project_id 必须来自它的设备
# ---------------------------------------------------------------------------


async def test_created_row_takes_its_project_from_the_equipment(
    client, sample_user_token, db_session
):
    """新建行的 `project_id` = 该 `equipment_id` 所属项目的 project_id。

    ⚠️ 这是**冗余列**（设备本身已带 project_id）的唯一同步点 ——
    若哪天有人手写 `CostEstResult(...)` 忘了给 project_id，
    这条就是它的守卫。
    """
    eq = await _make_equipment(db_session)
    r = await client.post(
        "/api/v1/cost-est/results",
        json=_create_body(eq.equipment_id),
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 201, f"got {r.status_code}: {r.text}"
    row = (
        await db_session.execute(
            select(CostEstResult).where(
                CostEstResult.equipment_id == eq.equipment_id
            )
        )
    ).scalar_one()
    assert row.project_id == eq.project_id, (
        "cost_est.project_id 没有跟随 equipment.project_id ⇒ "
        "守卫会按一个错的 project 判定"
    )


async def test_cost_est_result_has_a_project_id_column():
    """列本身存在且 NOT NULL（否则守卫的 500 分支会一直触发）。"""
    col = CostEstResult.__table__.c.get("project_id")
    assert col is not None, "CostEstResult 没有 project_id 列（守卫无法工作）"
    assert not col.nullable, "project_id 必须 NOT NULL（无 project 的行不允许存在）"
