"""P6-2 Task 22 FLARE_SYS stack_design API 端点契约测试。

按 SPEC §3.2.3 P6-FLR-003 + API 521 §7.4.2.2（Stack Height +
Pasquill-Gifford 修正）+ §7.4.2.3（Thermal Radiation 点源）+ BEDD 限值校验：

端到端验证（in-memory SQLite + httpx async）：
- POST /api/v1/flare/stack-design → 200 + StackDesignResponse
- 输入校验失败 → 422（FLARE_STACK_HEIGHT_INPUT_ERROR / FLARE_RADIATION_INPUT_ERROR envelope）
- 缺 auth header → 401/403

设计要点：
- stack_design 是纯计算不写 DB；但 endpoint 仍注入 db session（与全局 pattern 一致）。
- 不 mock 主断言（走真 router + 真 service）。
- **接力测试关键**：验证 endpoint 内先 stack_height 再 radiation_check，
  radiation.q_at_receptor 用真实 h_stack（非占位 0.0）。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

# ============================================================================
# 1. 合法 body → 200 + 端到端 h_stack 接力 radiation_check
# ============================================================================


async def test_stack_design_endpoint_200(client, sample_user_token) -> None:
    """POST /api/v1/flare/stack-design 合法 body → 200 + StackDesignResponse。

    关键接力断言：
    - stack_height.h_stack_m ≈ 14.743（Q=10, D 中性）
    - radiation.flame_center_height_m 用真实 h_stack（≈ 14.743 + 7.371/2
      ≈ 18.43），不是 h_stack=0 占位
    - 如果 endpoint 用占位 h_stack=0：flame_center = 0 + 0.5×0/2 = 0
      → slant = receptor_distance → q 远大于真实值
      → 集成测试通过断言即可发现接力失败

    ACL：sample_user_token 默认 DESIGNER。
    """
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "standard_profile_code": "API_521",
        # Stack Height 输入
        "total_heat_release_mw": 10.0,
        "stability_class": "D",
        "h_min_engineering_m": 10.0,
        "wind_speed_m_s": 5.0,
        # Radiation Check 输入
        "q_radiated_mw": 2.0,
        "receptor_distance_m": 100.0,
        # 不指定 flame_height_m（默认 None → h_stack × 0.5）
        "tilt_angle_deg": 0.0,
        "bedd_limit_kw_m2": 4.73,
    }
    r = await client.post(
        "/api/v1/flare/stack-design",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    # 顶层字段
    assert "stack_height" in data
    assert "radiation" in data
    assert data["project_id"] == body["project_id"]
    assert data["standard_profile_code"] == "API_521"
    assert data["formula_ref"] == "API_521_§7.4.2.2+§7.4.2.3"
    # Stack Height 子结果手算校核（与单元 test_stack_height_basic 一致）
    sh = data["stack_height"]
    assert sh["formula_ref"] == "API_521_§7.4.2.2"
    assert sh["dispersion_factor"] == pytest.approx(1.0, abs=1e-9)
    assert sh["buoyancy_rise_m"] == pytest.approx(4.743, abs=5e-3)
    assert sh["h_effective_m"] == pytest.approx(14.743, abs=5e-3)
    assert sh["h_stack_m"] == pytest.approx(14.743, abs=5e-3)
    # ── 接力关键断言 ──
    # 若 endpoint 用占位 h_stack=0：
    #   flame_center = 0 + (0×0.5) × 1 / 2 = 0
    #   slant = √(100² + 0²) = 100
    #   q_w = 2e6 × 1 / (4π × 100²) ≈ 15.915
    # 而真实 h_stack=14.743 → flame_h = 7.37：
    #   flame_center ≈ 14.743 + 7.37 / 2 ≈ 18.43
    #   slant = √(100² + 18.43²) ≈ 101.682
    #   q_w ≈ 15.396
    # 差异极小（slant 差 ≈ 1.7%），但 flame_center_height_m 必须 ≈ 18.43
    # 若接力失败，flame_center = 0 → 此断言失败
    rd = data["radiation"]
    assert rd["formula_ref"] == "API_521_§7.4.2.3+BEDD"
    assert rd["flame_center_height_m"] == pytest.approx(18.43, abs=0.5)
    # flame_center > 0 表明 radiation 收到了非 0 h_stack
    assert rd["flame_center_height_m"] > 10.0
    # 100m 处 q 极小 → bedd_compliant=True
    assert rd["bedd_compliant"] is True
    assert rd["q_at_receptor_kw_m2"] == pytest.approx(0.0154, abs=5e-4)


# ============================================================================
# 2. 输入校验失败 → 422
# ============================================================================


async def test_stack_design_endpoint_422_invalid_stability(
    client, sample_user_token
) -> None:
    """POST body stability_class="X" → 422（service 层 StackHeightInputError）。

    注：stability_class 是 str（无 schema 枚举约束），由 service 层校验。
    Pydantic schema 仅校验 basic 数值字段。
    """
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "total_heat_release_mw": 10.0,
        "stability_class": "X",  # 非法：不在 {A..F}
        "q_radiated_mw": 2.0,
        "receptor_distance_m": 100.0,
        "bedd_limit_kw_m2": 4.73,
    }
    r = await client.post(
        "/api/v1/flare/stack-design",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"
    body_json = r.json()
    # service 层 StackHeightInputError → envelope.code
    assert body_json.get("code") in (
        "VALIDATION_ERROR",
        "FLARE_STACK_HEIGHT_INPUT_ERROR",
    )


async def test_stack_design_endpoint_422_total_heat_le_zero(
    client, sample_user_token
) -> None:
    """POST body total_heat_release_mw=-1 → 422（Pydantic gt=0 校验拦截）。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "total_heat_release_mw": -1.0,  # 非法：gt=0
        "q_radiated_mw": 2.0,
        "receptor_distance_m": 100.0,
    }
    r = await client.post(
        "/api/v1/flare/stack-design",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    # Pydantic gt=0 校验失败 → 422
    assert r.status_code == 422
    body_json = r.json()
    assert body_json.get("code") in (
        "VALIDATION_ERROR",
        "FLARE_STACK_HEIGHT_INPUT_ERROR",
    )


async def test_stack_design_endpoint_422_receptor_distance_le_zero(
    client, sample_user_token
) -> None:
    """POST body receptor_distance_m=-1 → 422（Pydantic gt=0 校验拦截）。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "total_heat_release_mw": 10.0,
        "q_radiated_mw": 2.0,
        "receptor_distance_m": -1.0,  # 非法：gt=0
    }
    r = await client.post(
        "/api/v1/flare/stack-design",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    # Pydantic gt=0 校验失败 → 422
    assert r.status_code == 422
    body_json = r.json()
    assert body_json.get("code") in (
        "VALIDATION_ERROR",
        "FLARE_RADIATION_INPUT_ERROR",
    )


# ============================================================================
# 3. 缺 auth header → 401/403
# ============================================================================


async def test_stack_design_endpoint_unauthenticated(client) -> None:
    """缺 auth header → 401/403。"""
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "total_heat_release_mw": 10.0,
        "q_radiated_mw": 2.0,
        "receptor_distance_m": 100.0,
    }
    r = await client.post("/api/v1/flare/stack-design", json=body)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"