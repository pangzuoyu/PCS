"""P6-6A-6 (Ruling 5 closure, v4) FULL 甘醇脱水系统 API 集成测试。

POST /api/v1/psychro/glycol-dehydration/calculate 端到端契约测试
（端点 → 真 service 层；client / sample_user_token 来自 tests/conftest.py）：

- 11 cases 涵盖：
  - 2 happy path（TEG / TEG + acid gas → acid_gas_corrected=True）
  - 1 DEG 拒绝（v5.1 Ruling 5：FULL system 仅 TEG）
  - 1 M-3 闭环：缺 T/P 时 dewpoint=None + dewpoint_unavailable_reason 填值
  - 7 个 validation 422（Pydantic Field bounds + service 拒绝）
  - 1 ACL：DESIGNER 通过 / VIEWER 拒绝
  - 1 negative flow（Pydantic Field gt=0 拒绝）

设计要点：
- ACL：DESIGNER 通过；缺 auth / VIEWER 拒绝（401/403）
- 不依赖 pcs_test 库（in-memory SQLite；不走 DB）
- DEG / 缺 T/P / 越界 flooding_c_sb 等边界：service 抛 GlycolDehydrationError
  → _to_http → 422 envelope；端点契约层验证
"""
from __future__ import annotations

from typing import Any

import pytest

from app.core.security import create_access_token

# ============================================================================
# 共用 helper：构造合法 baseline body（TEG 8 块塔盘 + 3 gpm 循环量）
# ============================================================================


def _baseline_body(**overrides: Any) -> dict[str, Any]:
    """构造合法 TEG 接触塔 body（GPSA §20.4 reference）。

    baseline:
    - Q_gas = 10 MMscfd（典型 small/mid-size 接触塔）
    - inlet = 15 lb/MMscf；outlet = 0.1 lb/MMscf → η ≈ 99.3%
    - tray_count = 8（GPSA §20.4 typical）
    - circulation = 3 gpm（GPSA 经验 3 gpm/MMscf）
    - T/P 不传 → dewpoint_unavailable_reason 填值
    """
    body: dict[str, Any] = {
        "gas_flow_mmscfd": 10.0,
        "inlet_water_content_lb_per_mmscf": 15.0,
        "outlet_water_content_lb_per_mmscf": 0.1,
        "contactor_tray_count": 8,
        "glycol_circulation_rate_gpm": 3.0,
        "glycol_type": "TEG",
    }
    body.update(overrides)
    return body


def _viewer_token() -> str:
    """VIEWER 角色 token（DESIGNER 拒绝；验证 ACL）。"""
    return create_access_token(subject="test-viewer", role="VIEWER")


# ============================================================================
# 1. POST /psychro/glycol-dehydration/calculate — 200 happy path
# ============================================================================


async def test_happy_path_tegs_full_system_200(
    client, sample_user_token
) -> None:
    """TEG baseline (8 塔盘 + 3 gpm) → 200 + 完整 GlycolDehydrationResponse。

    期望（GPSA §20.4 Eq.20-4）：
    - dehydration_efficiency ≈ 0.9933
    - n_tray_minimum = 4（GPSA §20.4 Eq.20-4：ln(150)/ln(4.5) ≈ 3.33 → ceil = 4）
    - is_tray_count_ok = True（8 ≥ 4）
    - teg_loss_gpd = 5.0（GPSA 经验 0.5 × 10）
    - imperial_conversion = None（默认 SI）
    - dewpoint_unavailable_reason 非空（缺 T/P）
    - acid_gas_corrected = False（默认无 acid gas）
    - glycol_type = "TEG"回显
    """
    body = _baseline_body()
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()

    # 既有 7 字段
    assert data["dehydration_efficiency"] == pytest.approx(0.99333, abs=1e-3)
    assert data["n_tray_minimum"] == 4
    assert data["is_tray_count_ok"] is True
    assert data["teg_loss_gpd"] == pytest.approx(5.0, abs=1e-6)
    assert data["contactor_diameter_in"] > 0
    assert data["imperial_conversion"] is None
    assert isinstance(data["formula_ref"], dict)
    assert data["glycol_type"] == "TEG"

    # OUT_OF_SCOPE 字段（v4 含 acid_gas_corrected + dewpoint_unavailable_reason）
    assert data["water_dewpoint_f"] is None
    assert data["dewpoint_unavailable_reason"] is not None
    assert "temperature_f" in data["dewpoint_unavailable_reason"].lower()
    assert data["acid_gas_corrected"] is False
    # FULL system 必填字段（brief schema 标 float 非 Optional）
    assert data["column_diameter_full_in"] > 0
    assert data["column_height_ft"] > 0
    assert data["number_of_transfer_units"] > 0
    assert data["mass_h2o_removed_lb_s"] > 0
    assert data["reboiler_duty_btu_hr"] > 0
    assert data["column_csa_ft2"] > 0
    # 默认 lean_glycol_concentration = 0.99 回显
    assert data["lean_glycol_concentration"] == pytest.approx(0.99, abs=1e-6)


async def test_happy_path_tegs_with_acid_gas_200_acid_gas_corrected_true(
    client, sample_user_token
) -> None:
    """TEG + acid gas（CO2=10%, H2S=5%）→ 200 + acid_gas_corrected=True。

    v4 新增（H-1）：co2_mol_pct 或 h2s_mol_pct > 0 → acid_gas_corrected=True。
    Behr dewpoint 计算触发 acid gas 校正（线性 placeholder；P6-6B 接管真
    Wichert-Aziz）。
    """
    body = _baseline_body(
        # 高 outlet=12 + 高 P=2500 psia 让 dewpoint > 60°F 避免 T<60°F
        # extrapolation 触发 dewpoint_unavailable_reason 填值
        outlet_water_content_lb_per_mmscf=12.0,
        temperature_f=120.0,
        pressure_psia=2500.0,
        co2_mol_pct=10.0,
        h2s_mol_pct=5.0,
    )
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()

    # v4 关键断言：acid_gas_corrected = True
    assert data["acid_gas_corrected"] is True
    # dewpoint 在 T/P 提供时应有值
    assert data["water_dewpoint_f"] is not None
    # dewpoint_unavailable_reason 应为 None（T/P 都给 + dewpoint > 60°F）
    assert data["dewpoint_unavailable_reason"] is None
    # 既有脱水效率不受 acid gas 影响（acid gas 仅影响 dewpoint）
    assert data["dehydration_efficiency"] == pytest.approx(
        1.0 - 12.0 / 15.0, abs=1e-3
    )
    # formula_ref 含 acid gas_correction 标注
    assert "acid_gas_correction" in data["formula_ref"]


async def test_deg_raises_422(client, sample_user_token) -> None:
    """DEG → 422（v5.1 Ruling 5：FULL system 仅 TEG）。

    GlycolDehydrationError → _to_http → 422 envelope。
    """
    body = _baseline_body(glycol_type="DEG")
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"
    # envelope 验证（具体 code 字段由 CorePcsError 提供；不强制字段名）
    body_json = r.json()
    assert "GLYCOL_DEHYDRATION_INPUT_ERROR" in r.text or any(
        "DEG" in str(v) or "FULL" in str(v)
        for v in (body_json.values() if isinstance(body_json, dict) else [])
    )


async def test_missing_t_p_dewpoint_none_with_reason(
    client, sample_user_token
) -> None:
    """缺 T/P → dewpoint=None + dewpoint_unavailable_reason 填值（M-3 闭环）。

    既不抛错（service 友好降级），也不静默吞掉（reason 明确告知）。
    """
    body = _baseline_body()  # 不带 temperature_f / pressure_psia
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()

    # M-3 闭环断言：dewpoint_unavailable_reason 填值 + dewpoint 字段 None
    assert data["water_dewpoint_f"] is None
    assert data["adjusted_dewpoint_f"] is None
    assert data["dewpoint_unavailable_reason"] is not None
    # reason 文案应提及 temperature_f 或 pressure_psia
    assert (
        "temperature_f" in data["dewpoint_unavailable_reason"]
        or "pressure_psia" in data["dewpoint_unavailable_reason"]
    )


# ============================================================================
# 2. validation 422（service 层 PcsError → 422 envelope）
# ============================================================================


async def test_lean_glycol_out_of_range_422(client, sample_user_token) -> None:
    """lean_glycol_concentration = 0.80（< 0.95）→ 422（Pydantic Field ge=0.95）。"""
    body = _baseline_body(lean_glycol_concentration=0.80)
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_flooding_c_sb_out_of_range_422(
    client, sample_user_token
) -> None:
    """flooding_c_sb = 0.10（< 0.30）→ 422（Pydantic Field ge=0.30；v3 新增）。"""
    body = _baseline_body(flooding_c_sb=0.10)
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_relative_volatility_out_of_range_422(
    client, sample_user_token
) -> None:
    """relative_volatility = 100（> 50.0）→ 422（Pydantic Field le=50.0；v3 新增）。

    alpha 上限 = 50.0（v3 修订；原 4.5~50.0 不允许扩到 100）。
    """
    body = _baseline_body(relative_volatility=100.0)
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_co2_mol_pct_out_of_range_422(
    client, sample_user_token
) -> None:
    """co2_mol_pct = 150（> 100）→ 422（Pydantic Field le=100；v4 新增 H-1）。"""
    body = _baseline_body(co2_mol_pct=150.0)
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_h2s_mol_pct_out_of_range_422(
    client, sample_user_token
) -> None:
    """h2s_mol_pct = -1（< 0）→ 422（Pydantic Field ge=0；v4 新增 H-1）。"""
    body = _baseline_body(h2s_mol_pct=-1.0)
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


# ============================================================================
# 3. ACL — DESIGNER / PROCESS_CONTROLLER 通过；VIEWER / unauthenticated 拒绝
# ============================================================================


async def test_acl_designer_only(client) -> None:
    """ACL：DESIGNER → 200；VIEWER → 403；缺 auth → 401/403。

    三态验证：
    - sample_user_token（DESIGNER）→ 200
    - VIEWER token → 403（require_roles 拒绝）
    - 无 Authorization header → 401/403（mock_auth 拒绝）
    """
    body = _baseline_body()

    # DESIGNER → 200
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": "Bearer " + _baseline_actor_token()},
    )
    assert r.status_code == 200, f"DESIGNER got {r.status_code}: {r.text}"

    # VIEWER → 403
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": f"Bearer {_viewer_token()}"},
    )
    assert r.status_code == 403, f"VIEWER got {r.status_code}: {r.text}"

    # 缺 auth → 401/403
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
    )
    assert r.status_code in (401, 403), (
        f"unauthenticated got {r.status_code}: {r.text}"
    )


def _baseline_actor_token() -> str:
    """DESIGNER 角色 token（ACL happy path）。"""
    return create_access_token(subject="test-acl-designer", role="DESIGNER")


# ============================================================================
# 4. Pydantic schema 校验（Field 边界）
# ============================================================================


async def test_pydantic_validation_negative_flow(
    client, sample_user_token
) -> None:
    """gas_flow_mmscfd = -1 → 422（Pydantic Field gt=0；先于 service 触发）。

    验证 Pydantic schema 层而非 service 层的拒绝路径。
    """
    body = _baseline_body(gas_flow_mmscfd=-1.0)
    r = await client.post(
        "/api/v1/psychro/glycol-dehydration/calculate",
        json=body,
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"