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
