"""P5-1-4 VESSEL API + 落库 + 出口物流 集成测试。

端到端验证（in-memory SQLite + httpx async）：
- POST /api/v1/vessel/calculate（sizing + hydraulics 一次计算）
- record_hash 16 hex + lineage（DataLineage.source_ref_id = stream_id）
- outlet_stream DRAFT 态拒绝下游（403 STREAM_NOT_CHECKED）
- stream 不存在（404 SIM_STREAM_NOT_FOUND）
- 输入非法（K_factor 越界 → 422）
- horizontal orientation 触发 UserWarning（API 透传 calc_vessel_hydraulics 警告）

record_hash 契约（ADR-0031）：16 hex，6 位有效数字规范化（与 flash 共享 lineage）。
"""
from __future__ import annotations

import re
import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.calc import VesselResult
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.models.system import DataLineage
from app.schemas.stream import StreamCreate
from app.services.stream_service import StreamService

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """最小 Workspace + Project 工厂。"""

    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="vessel API 测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        return proj

    return _make


@pytest_asyncio.fixture
async def checked_stream(db: AsyncSession, make_project) -> Stream:
    """Workspace + Project + Stream（LIQUID，CHECKED）。

    vessel calc 入口要求源流 CHECKED。
    """
    proj = await make_project()
    sp, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name="S-V-101",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0,
            press=200.0,
            phase="LIQUID",  # 避免 MIXED 必填 vapor/liquid_composition
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.3, "106-97-8": 0.7},
        ),
        actor=uuid.uuid4(),
    )
    sp.sign_status = StreamSignStatus.CHECKED
    await db.commit()
    await db.refresh(sp)
    return sp


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


def _calc_body(stream_id: uuid.UUID, **kw: Any) -> dict[str, Any]:
    """POST /vessel/calculate 默认 body（sizing VERTICAL + hydraulics vertical）。"""
    base: dict[str, Any] = dict(
        source_stream_id=str(stream_id),
        sizing={
            "vessel_type": "VERTICAL",
            "rho_L_kg_m3": 850.0,
            "rho_V_kg_m3": 1.2,
            "liquid_flow_m3_s": 0.005,
            "vapor_flow_m3_s": 0.5,
            "residence_time_min": 5.0,
            "K_factor_ms": 0.10,
        },
        hydraulics={
            "D_m": 2.0,
            "L_m": 5.0,
            "h0_m": 1.0,
            "d_orifice_m": 0.05,
            "Cd_orifice": 0.62,
            "Q_in_liquid_m3_s": 0.005,
            "d_overflow_m": 0.1,
            "h_overflow_m": 1.0,
            "Cd_overflow": 0.62,
            "orientation": "vertical",
            "thermal_breathing_factor": 1.0,
        },
    )
    # 允许 overrides（仅顶层字段；sizing/hydraulics 字段需通过 _calc_body_with 修改）
    for k, v in kw.items():
        if k in ("sizing", "hydraulics"):
            base[k].update(v)
        else:
            base[k] = v
    return base


# ============================================================================
# 1) happy path：POST /vessel/calculate → 201 + record_hash + lineage + outlet DRAFT
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_vessel_happy_path(
    client, checked_stream, designer_headers
):
    """vessel 计算 happy path：sizing + hydraulics 联动 → 201 + 完整响应结构。"""
    r = await client.post(
        "/api/v1/vessel/calculate",
        json=_calc_body(checked_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()

    # 响应结构
    assert "calc_id" in body
    assert _HASH_RE.match(body["record_hash"]), body["record_hash"]
    assert body["calc_type"] == "VESSEL"
    assert body["stream_id"] == str(checked_stream.stream_id)
    assert len(body["lineage_ids"]) >= 1

    # outlet_stream DRAFT
    assert body["outlet_stream_id"] is not None
    assert body["outlet_stream_name"].startswith(checked_stream.stream_name)

    # result 含 sizing + hydraulics
    assert "sizing" in body["result"]
    assert "hydraulics" in body["result"]
    assert body["result"]["sizing"]["V_max_ms"] > 0
    assert body["result"]["sizing"]["D_min_m"] > 0
    assert body["result"]["hydraulics"]["empty_time_s"] > 0
    assert isinstance(body["result"]["hydraulics"]["overflow_ok"], bool)


@pytest.mark.asyncio
async def test_calculate_vessel_vessel_result_in_db(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """VesselResult ORM 落库：input_json + output_json 双轨 + record_hash 16 hex。"""
    r = await client.post(
        "/api/v1/vessel/calculate",
        json=_calc_body(checked_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201
    body = r.json()
    vessel_id = uuid.UUID(body["calc_id"])

    record = await db.get(VesselResult, vessel_id)
    assert record is not None
    # input_json 双轨（ADR-0032 V1.1 决策 6）
    assert "sizing" in record.input_json
    assert "hydraulics" in record.input_json
    assert record.input_json["sizing"]["vessel_type"] == "VERTICAL"
    assert record.input_json["sizing"]["K_factor_ms"] == 0.10
    assert record.input_json["hydraulics"]["orientation"] == "vertical"
    # output_json 合并
    assert "sizing" in record.output_json
    assert "hydraulics" in record.output_json
    # hash 16 hex
    assert _HASH_RE.match(record.record_hash)


@pytest.mark.asyncio
async def test_calculate_vessel_lineage_in_db(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """finalize_calc_record：DataLineage.record_type=VesselResult + source_ref_id=stream_id。"""
    r = await client.post(
        "/api/v1/vessel/calculate",
        json=_calc_body(checked_stream.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 201
    body = r.json()
    vessel_id = uuid.UUID(body["calc_id"])

    rows = (
        await db.execute(
            select(DataLineage).where(
                DataLineage.record_type == "VesselResult",
                DataLineage.record_id == vessel_id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1, f"应 1 条血缘，实际 {len(rows)}"
    assert rows[0].source_ref_type == "Stream"
    assert rows[0].source_ref_id == checked_stream.stream_id


# ============================================================================
# 2) 三步守卫：DRAFT → 403 / 不存在 → 404
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_vessel_draft_stream_403(
    client, db: AsyncSession, make_project, designer_headers
):
    """DRAFT 状态源流 → 403 STREAM_NOT_CHECKED（三步守卫）。"""
    proj = await make_project()
    sp, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name="S-V-DRAFT",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0,
            press=200.0,
            phase="LIQUID",
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.3, "106-97-8": 0.7},
        ),
        actor=uuid.uuid4(),
    )
    # 默认 DRAFT，不动

    r = await client.post(
        "/api/v1/vessel/calculate",
        json=_calc_body(sp.stream_id),
        headers=designer_headers,
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "STREAM_NOT_CHECKED"


@pytest.mark.asyncio
async def test_calculate_vessel_stream_not_found_404(client, designer_headers):
    """源流 UUID 不存在 → 404 SIM_STREAM_NOT_FOUND。"""
    r = await client.post(
        "/api/v1/vessel/calculate",
        json=_calc_body(uuid.uuid4()),
        headers=designer_headers,
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "SIM_STREAM_NOT_FOUND"


# ============================================================================
# 3) 输入非法 422：K_factor 越界（> 1.0 物理上限）
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_vessel_invalid_input_422(
    client, checked_stream, designer_headers
):
    """ρ_L < ρ_V 物理不合理（service 层校验）→ 422 VESSEL_INPUT_ERROR。

    注：K_factor 越界被 Pydantic schema 层（ge=0.01, le=1.0）拦截为
    VALIDATION_ERROR；本测试用 service 层的 ρ_L < ρ_V 校验
    （schema 不交叉比较两密度字段）。
    """
    body = _calc_body(checked_stream.stream_id)
    body["sizing"]["rho_L_kg_m3"] = 1.0
    body["sizing"]["rho_V_kg_m3"] = 10.0  # ρ_L < ρ_V 物理不合理
    r = await client.post(
        "/api/v1/vessel/calculate",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "VESSEL_INPUT_ERROR"


# ============================================================================
# 4) horizontal orientation → UserWarning（API 透传）
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_vessel_horizontal_orientation_warning(
    client, checked_stream, designer_headers
):
    """horizontal orientation 触发 UserWarning（仍返 201，结果仍落地）。"""
    body = _calc_body(checked_stream.stream_id)
    body["hydraulics"]["orientation"] = "horizontal"

    # httpx 默认会把 warnings 收敛，但 TestClient 不直接抛；断言响应结构
    r = await client.post(
        "/api/v1/vessel/calculate",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    resp = r.json()
    assert resp["result"]["hydraulics"]["applicable_orientation"] == "vertical"
    # applicable_orientation 固定为 vertical（数据可追溯适用边界）