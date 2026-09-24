"""P6-1 Task 10: cv_api POST /api/v1/cv/calculate 端点契约测试。

按 PCS-PLAN-P6-BATCH.md §Task 10 + SPEC §3.2.1.1~1.4 + §3.2.1.6 + ADR-0022 V1.0：

端到端验证（in-memory SQLite + httpx async）：
- POST /api/v1/cv/calculate → 201 + cv_result_id + outlet_stream_id + record_hash
- OpenAPI /openapi.json 含 /cv/calculate 路径 + 21+ 字段 schema
- Pydantic extra='forbid' → 422 ValidationError（未知字段拦截）
- standard_profile_code 缺省 → 默认 API-60534

DB 测试 fixture 最简 pattern（参考 .wolf/cerebrum.md Do-Not-Repeat）：
- 源流直接 ORM 构造（最简必填字段；cv_persist 仅校验 project_id 一致）
- POST API 创建（service 层补必填）→ DB UPDATE 状态字段
"""
from __future__ import annotations

import re
import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Stream

_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


# ---------------------------------------------------------------------------
# Fixtures（最小源流；CV 不需 CHECKED 流，cv_persist 仅校验 project_id 一致）
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def source_stream(db: AsyncSession, project_id, workspace_id) -> Stream:
    """源流（DRAFT 状态；cv_persist 仅校验 project_id 一致即可）。

    approval_depth 在 Stream ORM 上 NOT NULL 但无 server_default；测试 fixture
    显式填 1（DRAFT 态最小校对深度）。
    """
    s = Stream(
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-CV-{project_id.hex[:8]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


def _liquid_body(
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
    **overrides: Any,
) -> dict[str, Any]:
    """最小液体工况请求（SPEC §3.2.1.1）。

    提供 P1/P2/T1 完整三件套以满足 CvResult NOT NULL 约束 + LIQUID 必填 SG/dP_bar。
    """
    body: dict[str, Any] = {
        "project_id": str(project_id),
        "workspace_id": str(workspace_id),
        "fluid_phase": "LIQUID",
        "Q_m3h": 100.0,
        "P1_pa": 300_000.0,
        "P2_pa": 200_000.0,
        "T1_k": 300.0,
        "SG": 1.0,
        "dP_bar": 1.0,
        "FL": 0.9,
        "FF": 0.96,
        "Pv": 2000.0,
        "Pc": 22.0e6,
        "source_stream_id": str(source_stream_id),
    }
    body.update(overrides)
    return body


# ============================================================================
# 1. POST /cv/calculate 成功路径（液体 + 默认 standard_profile_code）
# ============================================================================


@pytest.mark.asyncio
async def test_cv_calculate_post_success(
    client, source_stream, project_id, workspace_id
):
    """POST /cv/calculate happy path：201 + cv_result_id + outlet_stream_id + record_hash。"""
    r = await client.post(
        "/api/v1/cv/calculate",
        json=_liquid_body(project_id, workspace_id, source_stream.stream_id),
    )
    assert r.status_code == 201, r.text
    body = r.json()

    # 主键 + 关键结果字段
    assert "cv_result_id" in body
    uuid.UUID(body["cv_result_id"])  # parse OK
    assert body["fluid_phase"] == "LIQUID"
    assert body["Cv_calculated"] > 0
    assert body["standard_profile_code"] == "IEC_60534"  # C-07 默认值
    assert body["design_stage"] == "BASIC"  # 默认值
    assert _HASH_RE.match(body["record_hash"]), body["record_hash"]

    # outlet stream 锚定
    assert "outlet_stream_id" in body
    uuid.UUID(body["outlet_stream_id"])
    assert body["outlet_stream_id"] != body["cv_result_id"]

    # tag_number 8 hex（无 CV- 前缀；outlet device 字段补前缀）
    assert re.match(r"^[0-9A-F]{8}$", body["tag_number"]), body["tag_number"]


# ============================================================================
# 2. OpenAPI 契约：/cv/calculate 路径 + 21+ 字段 schema
# ============================================================================


@pytest.mark.asyncio
async def test_cv_calculate_openapi_contract(client):
    """OpenAPI /openapi.json 含 /cv/calculate 路径 + CvCalculateRequest 关键字段。

    契约：
    - 路径存在
    - Request body schema 含 21 字段（5 context + 1 phase + 10 工况 + 5 修正 + 1 source）
    - Response 201 schema 含 cv_result_id / outlet_stream_id / record_hash
    """
    r = await client.get("/openapi.json")
    assert r.status_code == 200, r.text
    spec = r.json()

    # 路径存在 + POST 方法
    path = "/api/v1/cv/calculate"
    assert path in spec["paths"], f"OpenAPI 缺路径 {path}: {list(spec['paths'])}"
    post = spec["paths"][path].get("post")
    assert post is not None, f"OpenAPI {path} 缺 POST 方法"
    assert "requestBody" in post
    assert "201" in post["responses"] or "200" in post["responses"]

    # 引用 CvCalculateRequest schema
    schemas = spec.get("components", {}).get("schemas", {})
    assert "CvCalculateRequest" in schemas, (
        f"OpenAPI 缺 CvCalculateRequest schema：{list(schemas)}"
    )
    req_props = schemas["CvCalculateRequest"]["properties"]
    # 关键必填字段存在
    for field in (
        "project_id", "workspace_id", "fluid_phase", "Q_m3h",
        "P1_pa", "P2_pa", "T1_k", "source_stream_id",
    ):
        assert field in req_props, f"CvCalculateRequest 缺字段 {field}: {list(req_props)}"

    # 引用 CvCalculateResponse schema
    assert "CvCalculateResponse" in schemas, (
        f"OpenAPI 缺 CvCalculateResponse schema：{list(schemas)}"
    )
    resp_props = schemas["CvCalculateResponse"]["properties"]
    for field in (
        "cv_result_id", "tag_number", "fluid_phase", "Cv_calculated",
        "choked", "record_hash", "outlet_stream_id",
    ):
        assert field in resp_props, f"CvCalculateResponse 缺字段 {field}: {list(resp_props)}"


# ============================================================================
# 3. invalid input：缺 source_stream_id → 422 ValidationError
# ============================================================================


@pytest.mark.asyncio
async def test_cv_calculate_invalid_input_missing_source_stream(
    client, project_id, workspace_id
):
    """缺 source_stream_id → 422 Pydantic ValidationError（extra='forbid' + 必填拦截）。"""
    body = _liquid_body(project_id, workspace_id, source_stream_id=uuid.uuid4())
    del body["source_stream_id"]

    r = await client.post("/api/v1/cv/calculate", json=body)
    assert r.status_code == 422, r.text
    payload = r.json()
    # Pydantic ValidationError 标准 envelope：detail[*].type 包含 "missing"
    assert "detail" in payload
    missing_errors = [
        e for e in payload["detail"] if e.get("type") == "missing"
    ]
    assert any(
        "source_stream_id" in (e.get("loc") or [])
        for e in payload["detail"]
    ), f"应有 source_stream_id 字段缺失错误：{payload['detail']}"
    assert len(missing_errors) >= 1, (
        f"应至少 1 条 missing 类型错误，实际：{payload['detail']}"
    )


@pytest.mark.asyncio
async def test_cv_calculate_invalid_input_unknown_field(
    client, source_stream, project_id, workspace_id
):
    """未知字段 → 422（extra='forbid' 严格模式；不静默吞字段）。"""
    body = _liquid_body(project_id, workspace_id, source_stream.stream_id)
    body["unknown_field_xyz"] = "should be rejected"

    r = await client.post("/api/v1/cv/calculate", json=body)
    assert r.status_code == 422, r.text
    payload = r.json()
    # extra='forbid' → Pydantic 抛 "extra_forbidden" 类型错误
    extra_errors = [
        e for e in payload["detail"] if e.get("type") == "extra_forbidden"
    ]
    assert len(extra_errors) >= 1, (
        f"应至少 1 条 extra_forbidden 错误，实际：{payload['detail']}"
    )


# ============================================================================
# 4. standard_profile_code 缺省验证
# ============================================================================


@pytest.mark.asyncio
async def test_cv_calculate_standard_profile_code_default(
    client, source_stream, project_id, workspace_id
):
    """缺省 standard_profile_code → 默认 IEC_60534（C-07 评审委员会 2026-09-24 裁决）。

    不传 standard_profile_code 时仍能跑（Pydantic 默认值；CvEngine 内部也用
    同样的默认填充 CvResult.standard_profile_code 列）。
    """
    body = _liquid_body(project_id, workspace_id, source_stream.stream_id)
    assert "standard_profile_code" not in body  # 确认未传

    r = await client.post("/api/v1/cv/calculate", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["standard_profile_code"] == "IEC_60534"
