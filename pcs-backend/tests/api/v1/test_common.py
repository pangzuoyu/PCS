"""COMMON 物性/许用应力/介质安全 API 测试（P3.3 / spec §3.2.3）。

数据来源：vendor chemicals1.5.2 + 内置 ASME B31.3 / 安全 dict（spec §3.2.3 不要求持久化）。
ACL：读（DESIGNER + PROCESS_CONTROLLER + SYSTEM_ADMIN），无写操作。
"""
from __future__ import annotations

import math

import pytest


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ---------------------------------------------------------------------------
# 材料物性查询（chemicals1.5.2）
# ---------------------------------------------------------------------------


async def test_material_search_by_name(client, sample_user_token):
    """按名称 'water' 搜，返回至少 1 条（CAS/MW/formula/source）。"""
    r = await client.get(
        "/api/v1/common/materials/search",
        params={"keyword": "water"},
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, r.text
    items = r.json()
    assert isinstance(items, list) and len(items) >= 1
    item = items[0]
    assert set(item.keys()) >= {"cas", "name", "formula", "mw", "source"}
    assert item["source"] == "CHEMICALS_LIBRARY"


async def test_material_search_by_cas(client, sample_user_token):
    """按 CAS '7732-18-5' 精确搜，命中 water。"""
    r = await client.get(
        "/api/v1/common/materials/search",
        params={"keyword": "7732-18-5"},
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, r.text
    items = r.json()
    assert any(i["cas"] == "7732-18-5" for i in items), items


async def test_material_search_no_keyword_422(client, sample_user_token):
    """缺 keyword 必返 422。"""
    r = await client.get(
        "/api/v1/common/materials/search",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 422


async def test_material_get_by_cas_returns_properties(client, sample_user_token):
    """查 water 完整物性：含 MW/Tc/Pc/Tb/Tm/formula + source=EXPERIMENTAL。"""
    r = await client.get(
        "/api/v1/common/materials/7732-18-5",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cas"] == "7732-18-5"
    assert body["mw"] == pytest.approx(18.0153, rel=1e-3)
    assert body["tc_k"] == pytest.approx(647.096, rel=1e-3)
    assert body["pc_pa"] == pytest.approx(22_064_000.0, rel=1e-3)
    assert body["source"] in {"EXPERIMENTAL", "IAPWS-IF97"}


async def test_material_get_unknown_cas_404(client, sample_user_token):
    r = await client.get(
        "/api/v1/common/materials/0000-00-0",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 许用应力（ASME B31.3 Table A-1 内置 + 线性插值）
# ---------------------------------------------------------------------------


async def test_allowable_stress_carbon_steel_250c(client, sample_user_token):
    """碳钢 A106 Gr.B 在 250°C（节点间）的许用应力：内插 200/300°C。"""
    r = await client.get(
        "/api/v1/common/allowable-stress",
        params={"material": "A106-GrB", "temp_c": 250},
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["material"] == "A106-GrB"
    assert body["temp_c"] == 250
    assert body["interpolated"] is True
    # 200°C → 113.8, 300°C → 96.5 → 250 插值 = 105.15
    assert math.isclose(body["stress_mpa"], 105.15, abs_tol=0.1)


async def test_allowable_stress_exact_table_point(client, sample_user_token):
    """刚好命中表节点温度 → 返回该节点精确值（不插值）。"""
    r = await client.get(
        "/api/v1/common/allowable-stress",
        params={"material": "A106-GrB", "temp_c": 200},
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["interpolated"] is False
    # 200°C 节点精确值 = 113.8
    assert math.isclose(body["stress_mpa"], 113.8, abs_tol=0.1)


async def test_allowable_stress_oob_temp_422(client, sample_user_token):
    """温度超出材料表 → 422。"""
    r = await client.get(
        "/api/v1/common/allowable-stress",
        params={"material": "A106-GrB", "temp_c": 2000},
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 422


async def test_allowable_stress_unknown_material_404(client, sample_user_token):
    r = await client.get(
        "/api/v1/common/allowable-stress",
        params={"material": "UNKNOWN-XYZ", "temp_c": 100},
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 介质安全（毒性 + 爆炸极限）
# ---------------------------------------------------------------------------


async def test_safety_known_medium_methane(client, sample_user_token):
    """甲烷 CAS 74-82-8：极低毒 + 爆炸极限 5~15 vol%。"""
    r = await client.get(
        "/api/v1/common/safety",
        params={"cas": "74-82-8"},
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cas"] == "74-82-8"
    assert body["toxicity_class"] in {"LOW", "NONE"}  # 甲烷基本无毒
    assert 4 < body["lel_vol_pct"] < 6
    assert 14 < body["uel_vol_pct"] < 16


async def test_safety_unknown_cas_404(client, sample_user_token):
    r = await client.get(
        "/api/v1/common/safety",
        params={"cas": "0000-00-0"},
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# ACL：仅 DESIGNER/PC/SA 可读，匿名 401
# ---------------------------------------------------------------------------


async def test_common_anonymous_denied(client):
    r = await client.get(
        "/api/v1/common/materials/search",
        params={"keyword": "water"},
    )
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# service 单测（不依赖 API 路由）
# ---------------------------------------------------------------------------


def test_common_service_search_returns_list():
    """service 直测：search 返回 list，不依赖路由。"""
    from app.services.common_service import CommonService

    items = CommonService.search_material("water")
    assert isinstance(items, list)
    assert len(items) >= 1


def test_common_service_allowable_stress_interp():
    from app.services.common_service import CommonService

    # 250°C 在 200 / 300 之间 → 插值
    result = CommonService.allowable_stress("A106-GrB", 250)
    assert "stress_mpa" in result
    assert result["interpolated"] is True