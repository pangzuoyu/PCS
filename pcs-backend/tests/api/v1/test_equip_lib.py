import uuid

"""equip-lib 沉淀 + 检索测试（Task 1.9.5 / P2-EQL-001，CATEGORY_6 复用审批链）。"""

_SETTLE = {
    "equipment_name": "原料进料泵",
    "equipment_type": "PUMP",
    "standard_drawing_no": "AB-1234",
    "applicable_conditions": {
        "pressure_mpa": "0.5~2.5", "temperature_c": "-20~150", "medium": "蜡油",
    },
    "material": "ZG230-450",
    "weight_kg": 850.0,
    "key_dimensions": {"head_m": 120, "flow_m3h": 45, "rpm": 2950},
    "original_tag": "121-P-101A",
    "commissioning_date": "2015-06-30",
    "source_equipment_id": "00000000-0000-0000-0000-000000000001",
    "source_project_id": "00000000-0000-0000-0000-000000000002",
}


async def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


async def test_settle_creates_category6_draft(client, sample_pc_token):
    r = await client.post(
        "/api/v1/equip-lib/settle", json=_SETTLE, headers=await _h(sample_pc_token)
    )
    assert r.status_code == 201
    body = r.json()
    assert body["category"] == "CATEGORY_6" and body["status"] == "DRAFT"


async def test_settle_validation_missing_material(client, sample_pc_token):
    bad = {k: v for k, v in _SETTLE.items() if k != "material"}
    r = await client.post(
        "/api/v1/equip-lib/settle", json=bad, headers=await _h(sample_pc_token)
    )
    assert r.status_code == 422  # 材质必填（P7 §3.2.3(4) 标准化要求）


async def test_search_returns_only_published(client, sample_pc_token, db, make_asset):
    # 一条 PUBLISHED + 一条 DRAFT
    from app.models.enums import ConfigStatus
    pub = await make_asset(
        status=ConfigStatus.PUBLISHED.value, category="CATEGORY_6", name="循环水泵 X"
    )
    draft = await make_asset(
        status=ConfigStatus.DRAFT.value, category="CATEGORY_6", name="循环水泵 Y"
    )
    r = await client.get(
        "/api/v1/equip-lib/search", params={"keyword": "循环水泵"},
        headers=await _h(sample_pc_token),
    )
    assert r.status_code == 200
    ids = [a["asset_id"] for a in r.json()]
    assert str(pub.asset_id) in ids and str(draft.asset_id) not in ids


async def test_settle_truncates_name_to_column_limit(client, sample_pc_token):
    """name = equipment_name(≤200) + " []" + tag(≤50) 可达 253 > ConfigAsset.name(200) → 截断。"""
    payload = {**_SETTLE, "equipment_name": "泵" * 200, "original_tag": "T" * 50}
    r = await client.post(
        "/api/v1/equip-lib/settle", json=payload, headers=await _h(sample_pc_token)
    )
    assert r.status_code == 201
    assert len(r.json()["name"]) <= 200


async def test_search_limit_lower_bound(client, sample_pc_token):
    r = await client.get(
        "/api/v1/equip-lib/search", params={"limit": -1}, headers=await _h(sample_pc_token)
    )
    assert r.status_code == 422  # limit ge=1


async def test_full_settle_lifecycle_publishes(client, sample_pc_token, db):
    """沉淀申请 → CONFIG 审批链 submit/approve/publish → 入库生效。"""
    r = await client.post(
        "/api/v1/equip-lib/settle", json=_SETTLE, headers=await _h(sample_pc_token)
    )
    asset_id = r.json()["asset_id"]
    h = await _h(sample_pc_token)
    await client.post(f"/api/v1/config/assets/{asset_id}/submit", headers=h)
    await client.post(f"/api/v1/config/assets/{asset_id}/approve", headers=h)
    r = await client.post(f"/api/v1/config/assets/{asset_id}/publish", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "PUBLISHED"
    r = await client.get(
        "/api/v1/equip-lib/search", params={"keyword": "原料进料泵"}, headers=h,
    )
    assert [a["asset_id"] for a in r.json()] == [asset_id]  # 沉淀记录与源项目解耦（仅存快照）


# ---------------------------------------------------------------------------
# 设备代号采集（地基 A）
#
# 相似度匹配以 type_code 为主键，但 settle 此前**根本不采集**它 ——
# 沉淀出的设备库条目没有可比对的设备代号，相似度无从谈起。
# type_code 优先从源设备（equipment_list）取，源是权威；无源时才用入参。
# ---------------------------------------------------------------------------


async def _make_source_equipment(db, type_code: str) -> str:
    """造一条 equipment_list，返回其 equipment_id 字符串。"""
    import uuid

    from app.models.equipment import EquipmentList

    eq = EquipmentList(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        tag_number=f"P-{uuid.uuid4().hex[:6]}",
        equipment_name="源泵",
        type_code=type_code,
    )
    db.add(eq)
    await db.commit()
    await db.refresh(eq)
    return str(eq.equipment_id)


async def test_settle_collects_type_code_from_source_equipment(
    client, sample_pc_token, db
):
    """有源设备时，type_code 取自 equipment_list（源是权威）。"""
    eq_id = await _make_source_equipment(db, "PUMP-CENTRIFUGAL-01")
    body = {**_SETTLE, "source_equipment_id": eq_id}
    r = await client.post(
        "/api/v1/equip-lib/settle", json=body, headers=await _h(sample_pc_token)
    )
    assert r.status_code == 201, r.text
    # content_json 经 ConfigVersion 快照落库；直接从响应取不到 content_json，
    # 故回查 asset
    from sqlalchemy import select

    from app.models.config_domain import ConfigAsset

    asset = (
        await db.execute(
            select(ConfigAsset).where(ConfigAsset.asset_id == uuid.UUID(r.json()["asset_id"]))
        )
    ).scalar_one()
    info = asset.content_json["standard_info"]
    assert info.get("type_code") == "PUMP-CENTRIFUGAL-01", asset.content_json


async def test_settle_uses_payload_type_code_when_no_source(
    client, sample_pc_token, db
):
    """无源设备时用入参 type_code（允许脱离项目直接沉淀标准件）。"""
    body = {
        k: v for k, v in _SETTLE.items()
        if k not in ("source_equipment_id", "source_project_id")
    }
    body["type_code"] = "PUMP-INLINE-02"
    r = await client.post(
        "/api/v1/equip-lib/settle", json=body, headers=await _h(sample_pc_token)
    )
    assert r.status_code == 201, r.text
    from sqlalchemy import select

    from app.models.config_domain import ConfigAsset

    asset = (
        await db.execute(
            select(ConfigAsset).where(ConfigAsset.asset_id == uuid.UUID(r.json()["asset_id"]))
        )
    ).scalar_one()
    assert asset.content_json["standard_info"].get("type_code") == "PUMP-INLINE-02"


async def test_settle_source_type_code_wins_over_payload(
    client, sample_pc_token, db
):
    """源设备与入参都给了 type_code → 源的赢（避免两边打架后型号错配）。"""
    eq_id = await _make_source_equipment(db, "PUMP-FROM-SOURCE")
    body = {**_SETTLE, "source_equipment_id": eq_id, "type_code": "PUMP-FROM-CLIENT"}
    r = await client.post(
        "/api/v1/equip-lib/settle", json=body, headers=await _h(sample_pc_token)
    )
    assert r.status_code == 201, r.text
    from sqlalchemy import select

    from app.models.config_domain import ConfigAsset

    asset = (
        await db.execute(
            select(ConfigAsset).where(ConfigAsset.asset_id == uuid.UUID(r.json()["asset_id"]))
        )
    ).scalar_one()
    assert asset.content_json["standard_info"]["type_code"] == "PUMP-FROM-SOURCE"


async def test_config_asset_rejects_unknown_category(db):
    """category 越界必须被拒 —— 否则拼错成 CATEGORY_07 会静默写入一条
    永远检索不到的孤儿记录（设备库上尤其致命：沉淀了却查不出来）。"""
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.models.config_domain import ConfigAsset

    db.add(ConfigAsset(
        category="CATEGORY_07", name="拼错的设备库条目",
        current_version="v1", status="DRAFT",
    ))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
