"""编辑端点的**鉴权顺序**守卫 —— P9A-4 D2 修的既有越权洞。

## 这条测试钉的是什么

2026-10-20 实测（bug-2039）：`filtration` / `flare` / `psychro` 三个 PATCH
端点的顺序是

```
require_roles → 保存 → check_project_access_or_404
```

⇒ **先写后鉴权**。而 service 取记录时**不带 project_id**
（`get_filtration_result_service(session, result_id=...)`）⇒ 那一步**没有任何
项目隔离** ⇒ 一个有 DESIGNER 角色的登录用户可以改到**别人项目**的记录；
鉴权只把**响应**变成 404 —— **行已经改了**。

⇒ 修法：**先鉴权，再保存**（预取记录拿 project_id → 鉴权 → 才写）。

⚠️ 顺带修掉 D2 引入的**身份泄漏**：409 响应带**持锁人身份**
（`holder.user_id` + `holder.acquired_at`）⇒ 若它在鉴权之前，无权者就能问出
「谁在改这条记录」⇒ 顺序必须鉴权在前。

## 为什么测试要自己把守卫打成 False

`tests/conftest.py` 的 `client` fixture 把
`UserProjectService.check_user_project_access` **mock 成恒 True**
（BLOCKER-3 集成测试的既定做法）⇒ 本文件把它改回 False，模拟
「该用户**没有**这个项目的授权」⇒ 于是端点必须 404 且**不改数据**。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.models.calc import (
    CoolingTowerResult,
    FiltrationResult,
    FlareSystemResult,
    PsychroResult,
)
from app.services.user_project_service import UserProjectService

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _no_project_access(*_args: Any, **_kwargs: Any) -> bool:
    """模拟「该用户没有这个项目的授权」。"""
    return False


#: 记录已知的 hash —— 有了它，「并发基线检查」才会**放行**，
#: 测试才能走到「保存」那一步 ⇒ 断言「数据没被改」才真的在盯着保存。
KNOWN_HASH = "a1b2c3d4e5f60718"

#: 每张表用来观察「有没有被改掉」的业务字段 + 改后的值。
PROBE = {
    "filtration_results": ("area", 1.0, 99.0),
    "flare_system_results": ("total_relief_load_kg_h", None, 123.0),
    "psychro_results": ("humidity_ratio_kg_kg", None, 0.05),
}


def _make_row(model: type) -> Any:
    common = dict(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        tag_number=f"T-{uuid.uuid4().hex[:8]}",
        record_hash=KNOWN_HASH,
    )
    if model is FiltrationResult:
        return FiltrationResult(
            filter_id=uuid.uuid4(),
            filter_type="RUTH_CONST_PRESSURE",
            area=1.0,
            cycle_time=1.0,
            pressure_drop=1e5,
            **common,
        )
    if model is CoolingTowerResult:
        return CoolingTowerResult(
            cooling_tower_id=uuid.uuid4(),
            calc_type="MERKEL",
            **common,
        )
    if model is FlareSystemResult:
        return FlareSystemResult(
            flare_id=uuid.uuid4(),
            calc_type="RELIEF",
            **common,
        )
    return PsychroResult(
        psychro_id=uuid.uuid4(),
        calc_type="HUMIDITY_RATIO",
        **common,
    )


# ⚠️ 路径前缀**必须**与 router 的 prefix 一致（`/filtration` `/flare` `/psychro`
# —— 路由是 `/results/{id}`，不是 `/{模块}-results/{id}`）。
# ⚠️ 写错 ⇒ 请求 404（路由不存在）⇒ 断言照样绿 ⇒ **假守卫**。
#   本文件第一版就踩了这个坑（2026-10-20 自查发现）。
CASES = [
    (FiltrationResult, "filtration", "filter_id", "filtration_results"),
    (FlareSystemResult, "flare", "flare_id", "flare_system_results"),
    (PsychroResult, "psychro", "psychro_id", "psychro_results"),
]


@pytest.mark.parametrize(
    ("model", "path_seg", "pk_attr", "table"),
    CASES,
    ids=[c[0].__name__ for c in CASES],
)
async def test_patch_without_project_access_is_404_and_does_not_write(
    client, sample_user_token, db_session, monkeypatch, model, path_seg, pk_attr, table
):
    """无权用户 PATCH ⇒ **404 且数据没变**（鉴权在保存之前）。"""
    monkeypatch.setattr(
        UserProjectService, "check_user_project_access", _no_project_access
    )
    row = _make_row(model)
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    pk = getattr(row, pk_attr)
    field, before_value, new_value = PROBE[table]

    r = await client.patch(
        f"/api/v1/{path_seg}/results/{pk}",
        # ⚠️ 基线**有效** ⇒ 并发检查放行 ⇒ 请求真的走到「保存」那一步
        #   （否则 409 短路，测不到「有没有被写」）
        json={field: new_value, "expected_hash": KNOWN_HASH},
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"
    # ⚠️ 关键：响应是 404 **不够** —— 旧顺序下响应也是 404，但**行已经改了**
    await db_session.refresh(row)
    assert getattr(row, field) == before_value, (
        f"无权用户的 PATCH 改了 {table}.{field} ⇒ 鉴权在保存之后（bug-2039）"
    )


@pytest.mark.parametrize(
    ("model", "path_seg", "pk_attr", "table"),
    [(FiltrationResult, "filtration", "filter_id", "filtration_results"),
     (CoolingTowerResult, "cool_tower", "cooling_tower_id", "cooling_tower_results")],
    ids=["filtration", "cool_tower"],
)
async def test_delete_without_project_access_is_404_and_does_not_write(
    client, sample_user_token, db_session, monkeypatch, model, path_seg, pk_attr, table
):
    """同族：DELETE 也必须**先鉴权再写**。

    ⚠️ filtration 的 DELETE 原先是「写完再鉴权」；cool_tower 的 DELETE
    **根本没有鉴权**（service 传 project_id=None ⇒ 也没有任何隔离）。
    """
    monkeypatch.setattr(
        UserProjectService, "check_user_project_access", _no_project_access
    )
    row = _make_row(model)
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    pk = getattr(row, pk_attr)

    r = await client.delete(
        f"/api/v1/{path_seg}/results/{pk}",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"
    await db_session.refresh(row)
    assert row.sign_status.value != "OBSOLETE", (
        f"无权用户的 DELETE 软删了 {table} 的记录（bug-2039）"
    )


async def test_conflict_detail_is_not_leaked_to_unauthorized_callers(
    client, sample_user_token, db_session, monkeypatch
):
    """409 的持锁人身份**不得**泄给无权者 ⇒ 无权者拿到的是 404，不是 409。"""
    monkeypatch.setattr(
        UserProjectService, "check_user_project_access", _no_project_access
    )
    row = _make_row(PsychroResult)
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    r = await client.patch(
        f"/api/v1/psychro/results/{row.psychro_id}",
        json={"expected_hash": "0000000000000000"},
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"
    assert "holder" not in r.text, "409 的持锁人身份泄给了无权者"
