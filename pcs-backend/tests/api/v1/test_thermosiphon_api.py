"""P5-0-1b T1 热虹吸循环安装高度 API 集成测试。

端到端验证（httpx async client）：
- POST /api/v1/thermosiphon/calculate happy path → 200 + 完整响应结构
- ACL：VIEWER 角色被拒（403）
- 未知字段被拒（extra='forbid' → 422）
- 无解输入（ΣP12 >= 驱动梯度）→ 422 THERMOSIPHON_INPUT_ERROR envelope
- 响应携带 formula_ref 4 段（标准 / 版本 / 条款 / 来源，含 XLS 溯源）

端点是纯计算（不落库）——安装高度是安装尺寸核算，不产生物流变化。
"""
from __future__ import annotations

from typing import Any

import pytest

from app.core.security import create_access_token


@pytest.fixture
def designer_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(subject='t-designer', role='DESIGNER')}"
    }


@pytest.fixture
def viewer_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(subject='t-viewer', role='VIEWER')}"
    }


def _body(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "circulation_type": "HORIZONTAL",
        "shell_diameter_m": 1.6,
        "drum_diameter_m": 2.4,
        "drum_liquid_level_m": 1.2,
        "drum_liquid_density_kg_m3": 865.0,
        "shell_avg_density_kg_m3": 500.0,
        "drum_temperature_c": 215.0,
        "inlet_pressure_drop_const_m": 1.1073228721942285,
        "inlet_pressure_drop_coeff": 0.01137,
        "outlet_pressure_drop_const_m": 0.85,
        "outlet_pressure_drop_coeff": 0.015,
        "shell_pressure_drop_const_m": 0.30,
        "shell_pressure_drop_coeff": 0.010,
        "safety_factor": 1.5,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_thermosiphon_calculate_happy_path(client, designer_headers):
    """happy path：200 + Hx/Hxo/推动力比/校核 + formula_ref 4 段。"""
    r = await client.post(
        "/api/v1/thermosiphon/calculate", json=_body(), headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["installation_height_calc_m"] > 0
    assert body["installation_height_final_m"] > body["installation_height_calc_m"]
    assert body["check_result"] == "PASS"
    assert body["circulation_drive_ratio"] > 1.0
    # formula_ref 4 段（service 层承载，不入 DDL）
    assert body["formula_ref_standard"] == "GPSA"
    assert body["formula_ref_version"] == "20.4"
    assert "132汽包安装高度计算" in body["formula_ref_source"]


@pytest.mark.asyncio
async def test_thermosiphon_calculate_acl_denies_viewer(client, viewer_headers):
    """ACL：VIEWER 无 DESIGNER 角色 → 403。"""
    r = await client.post(
        "/api/v1/thermosiphon/calculate", json=_body(), headers=viewer_headers
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_thermosiphon_calculate_rejects_unknown_field(client, designer_headers):
    """extra='forbid'：未知字段 → 422。"""
    r = await client.post(
        "/api/v1/thermosiphon/calculate",
        json=_body(not_a_real_field=1.0),
        headers=designer_headers,
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_thermosiphon_calculate_no_solution_422(client, designer_headers):
    """ΣP12 >= 驱动梯度 → 422 THERMOSIPHON_INPUT_ERROR envelope。"""
    r = await client.post(
        "/api/v1/thermosiphon/calculate",
        json=_body(inlet_pressure_drop_coeff=0.5),
        headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "THERMOSIPHON_INPUT_ERROR"
