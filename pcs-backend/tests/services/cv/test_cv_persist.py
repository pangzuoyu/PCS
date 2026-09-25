"""P6-1 Task 9: cv_persist 落库 + outlet stream（ADR-0022）测试。

按 SPEC §3.2.1.6 + §3.2.1.7 + ADR-0022 V1.0：
- 调 CvEngine.calculate → 21 键 payload
- 落 cv_results（含 v3_1 stub + record_hash 16 hex）
- 创建 outlet stream（DEVICE_CALCULATED, FRICTION_PRESSURE_DROP, device=CV-{tag}）

DB 测试 fixture 最简 pattern（参考 .wolf/cerebrum.md Do-Not-Repeat）：
- 直接用 conftest 的 db fixture（in-memory SQLite async session）
- 源流直接 ORM 构造（最简必填字段；outlet_stream 仅校验 project_id 一致）
- service 层补必填字段 → DB commit
"""
from __future__ import annotations

import re
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.calc import CvResult
from app.models.project import Stream
from app.services.cv.cv_persist import CvService

# record_hash 16 hex 校验（与 calc_lineage._HASH_PREFIX = 16 对齐）
_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_db(db):
    """P6-1 Task 9 test_db fixture：复用 conftest 的 db 别名（AsyncSession）。

    引用 .wolf/cerebrum.md「最简 pattern」：直接用现有 db fixture，不另造重复。
    """
    return db


@pytest_asyncio.fixture
async def source_stream(db, project_id, workspace_id) -> Stream:
    """源流（DRAFT 状态；outlet_stream 仅校验 project_id 一致即可）。

    approval_depth 在 Stream ORM 上 NOT NULL 但无 server_default；测试 fixture
    显式填 1（DRAFT 态最小校对深度）。StreamService.create() 业务路径会自动填，
    本 fixture 直接 ORM 构造仅供 outlet_stream project_id 校验用。
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


def _base_request(project_id: uuid.UUID, workspace_id: uuid.UUID) -> dict:
    """最小液体工况请求（SPEC §3.2.1.1）。

    提供 P1/P2/T1 完整三件套以满足 CvResult NOT NULL 约束。
    """
    return {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "fluid_phase": "LIQUID",
        "Q_m3h": 100.0,
        "SG": 1.0,
        "dP_bar": 1.0,
        "FL": 0.9,
        "FF": 0.96,
        "Pv": 2000.0,
        "Pc": 22.0e6,
        "P1_pa": 3.0e5,
        "P2_pa": 2.0e5,
        "T1_k": 300.0,
    }


# ---------------------------------------------------------------------------
# 1. 默认落库
# ---------------------------------------------------------------------------


async def test_persist_calculate_default(
    test_db, source_stream, project_id, workspace_id
):
    """默认落库：CvService.persist_calculate 返回 CvResult 实例，DB 已持久化。"""
    req = _base_request(project_id, workspace_id)
    cv_result = await CvService.persist_calculate(
        test_db, source_stream_id=source_stream.stream_id, request=req,
    )

    assert isinstance(cv_result, CvResult)
    assert cv_result.cv_id is not None
    # tag_number 是 8 hex（不预设 CV- 前缀；device 字段补前缀）
    assert re.match(r"^[0-9A-F]{8}$", cv_result.tag_number), (
        f"tag_number 应为 8 hex，实际 {cv_result.tag_number!r}"
    )
    # SPEC §3.2.1.6 关键字段
    assert cv_result.fluid_phase == "LIQUID"
    assert cv_result.standard_profile_code == "IEC_60534"
    assert cv_result.choked is False
    # DB 持久化校验（重新查一次）
    stmt = select(CvResult).where(CvResult.cv_id == cv_result.cv_id)
    refreshed = (await test_db.execute(stmt)).scalar_one()
    assert refreshed.cv_id == cv_result.cv_id


# ---------------------------------------------------------------------------
# 2. record_hash 含 standard_profile_code
# ---------------------------------------------------------------------------


async def test_record_hash_includes_standard_profile_code(
    test_db, source_stream, project_id, workspace_id
):
    """record_hash 是 16 hex 字符串，含 standard_profile_code 字段。"""
    from app.services.calc_lineage import compute_record_hash

    req = _base_request(project_id, workspace_id)
    cv_result = await CvService.persist_calculate(
        test_db, source_stream_id=source_stream.stream_id, request=req,
    )

    # 1. 16 hex 格式
    assert cv_result.record_hash != "", "record_hash 应非空"
    assert _HASH_RE.match(cv_result.record_hash), (
        f"record_hash 应为 16 hex，实际 {cv_result.record_hash!r}"
    )

    # 2. 改 standard_profile_code 后 hash 必须变化（说明 hash 含该字段）
    original_hash = cv_result.record_hash
    cv_result.standard_profile_code = "GB-12241"
    await test_db.flush()
    new_hash = compute_record_hash(cv_result)
    assert new_hash != original_hash, (
        f"改 standard_profile_code 后 hash 应变化，实际仍为 {original_hash}"
    )


# ---------------------------------------------------------------------------
# 3. outlet stream 创建（DEVICE_CALCULATED + FRICTION_PRESSURE_DROP）
# ---------------------------------------------------------------------------


async def test_create_outlet_stream_called(
    test_db, source_stream, project_id, workspace_id
):
    """outlet stream 链创建：source_type=DEVICE_CALCULATED, change_type=FRICTION_PRESSURE_DROP。"""
    from app.models.enums import StreamSignStatus

    req = _base_request(project_id, workspace_id)
    await CvService.persist_calculate(
        test_db, source_stream_id=source_stream.stream_id, request=req,
    )

    # 查 outlet stream（upstream_stream_id == source.stream_id）
    stmt = select(Stream).where(Stream.upstream_stream_id == source_stream.stream_id)
    outlet = (await test_db.execute(stmt)).scalar_one_or_none()
    assert outlet is not None, "应自动创建 outlet stream"
    assert outlet.source_type == "DEVICE_CALCULATED", (
        f"source_type 应为 DEVICE_CALCULATED，实际 {outlet.source_type}"
    )
    assert outlet.sign_status == StreamSignStatus.DRAFT, (
        f"sign_status 应为 DRAFT，实际 {outlet.sign_status}"
    )
    # properties 含 ADR-0022 关键字段
    props = outlet.stream_properties_json or {}
    assert props.get("change_type") == "FRICTION_PRESSURE_DROP", (
        f"change_type 应为 FRICTION_PRESSURE_DROP，实际 {props.get('change_type')}"
    )
    assert "device" in props, "outlet properties 应含 device 字段"


# ---------------------------------------------------------------------------
# 4. 多工况批：独立 cv_id + outlet 链
# ---------------------------------------------------------------------------


async def test_multi_scenario_batch(
    test_db, source_stream, project_id, workspace_id
):
    """多工况批：连续调用 5 次 persist_calculate，独立 cv_id + outlet stream。"""
    cv_ids: list[uuid.UUID] = []
    for i in range(5):
        req = _base_request(project_id, workspace_id)
        req["Q_m3h"] = 80.0 + i * 10.0  # 80 / 90 / 100 / 110 / 120
        cv_result = await CvService.persist_calculate(
            test_db, source_stream_id=source_stream.stream_id, request=req,
        )
        cv_ids.append(cv_result.cv_id)

    # 5 个独立 cv_id
    assert len(set(cv_ids)) == 5, f"5 次调用应产出 5 个独立 cv_id，实际 {cv_ids}"

    # 5 条 outlet stream
    stmt = select(Stream).where(Stream.upstream_stream_id == source_stream.stream_id)
    result = await test_db.execute(stmt)
    outlets = list(result.scalars().all())
    assert len(outlets) == 5, f"应自动创建 5 条 outlet stream，实际 {len(outlets)}"

    # 每条 outlet 的 cv_id 应能反查到对应 CvResult
    for outlet in outlets:
        props = outlet.stream_properties_json or {}
        assert props.get("Cv_calculated") is not None


# ---------------------------------------------------------------------------
# 5. device 命名格式：CV-{tag_number}
# ---------------------------------------------------------------------------


async def test_device_naming_format(
    test_db, source_stream, project_id, workspace_id
):
    """device 命名格式：CV-{tag_number}（outlet properties.device）。"""
    req = _base_request(project_id, workspace_id)
    cv_result = await CvService.persist_calculate(
        test_db, source_stream_id=source_stream.stream_id, request=req,
    )

    expected_device = f"CV-{cv_result.tag_number}"
    stmt = select(Stream).where(Stream.upstream_stream_id == source_stream.stream_id)
    outlet = (await test_db.execute(stmt)).scalar_one_or_none()
    assert outlet is not None
    props = outlet.stream_properties_json or {}
    assert props.get("device") == expected_device, (
        f"device 应为 {expected_device!r}，实际 {props.get('device')!r}"
    )