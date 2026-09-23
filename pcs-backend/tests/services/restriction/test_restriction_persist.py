"""P6-1 Task 13: restriction_persist 落库 + outlet stream（ADR-0022）测试。

按 SPEC §3.2.2.6 + ADR-0022 V1.0：
- 调 RestrictionEngine.calculate → 13 键 payload
- 落 restriction_results（含 v3_1 stub + record_hash 16 hex）
- 创建 outlet stream（RESTRICTION_CALCULATED, ISOENTHALPIC, device=RES-{tag}）

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

from app.models.calc import RestrictionResult
from app.models.project import Stream
from app.services.restriction.restriction_persist import RestrictionService

# record_hash 16 hex 校验（与 calc_lineage._HASH_PREFIX = 16 对齐）
_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_db(db):
    """P6-1 Task 13 test_db fixture：复用 conftest 的 db 别名（AsyncSession）。

    引用 .wolf/cerebrum.md「最简 pattern」：直接用现有 db fixture，不另造重复。
    """
    return db


@pytest_asyncio.fixture
async def source_stream(db, project_id, workspace_id) -> Stream:
    """源流（DRAFT 状态；outlet_stream 仅校验 project_id 一致即可）。

    approval_depth 在 Stream ORM 上 NOT NULL 但无 server_default；测试 fixture
    显式填 1（DRAFT 态最小校对深度）。
    """
    s = Stream(
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-RES-{project_id.hex[:8]}",
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
    """最小孔板工况请求（SPEC §3.2.2.1）。

    默认 ORIFICE；提供 D/d/Re_D/P1/dP/rho1 完整六件套以满足 RestrictionEngine
    输入校验 + RestrictionResult NOT NULL 约束。
    """
    return {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "device_type": "ORIFICE",
        "fluid_phase": "LIQUID",
        "D_pipe_m": 0.1,
        "d_solved_m": 0.05,
        "Re_D": 1.0e6,
        "P1_pa": 200_000.0,
        "dP_pa": 10_000.0,
        "rho1": 1000.0,
    }


# ---------------------------------------------------------------------------
# 1. 默认落库
# ---------------------------------------------------------------------------


async def test_persist_calculate_default(
    test_db, source_stream, project_id, workspace_id
):
    """默认落库：RestrictionService.persist_calculate 返回 RestrictionResult 实例，DB 已持久化。"""
    req = _base_request(project_id, workspace_id)
    restriction_result = await RestrictionService.persist_calculate(
        test_db, source_stream_id=source_stream.stream_id, request=req,
    )

    assert isinstance(restriction_result, RestrictionResult)
    assert restriction_result.orifice_id is not None
    # tag_number 是 8 hex（不预设 RES- 前缀；device 字段补前缀）
    assert re.match(r"^[0-9A-F]{8}$", restriction_result.tag_number), (
        f"tag_number 应为 8 hex，实际 {restriction_result.tag_number!r}"
    )
    # SPEC §3.2.2.6 关键字段
    assert restriction_result.device_type == "ORIFICE"
    assert restriction_result.choked is False
    assert restriction_result.design_stage.value == "BASIC"
    # DB 持久化校验（重新查一次）
    stmt = select(RestrictionResult).where(
        RestrictionResult.orifice_id == restriction_result.orifice_id
    )
    refreshed = (await test_db.execute(stmt)).scalar_one()
    assert refreshed.orifice_id == restriction_result.orifice_id


# ---------------------------------------------------------------------------
# 2. record_hash 含 standard_profile_code 影响
# ---------------------------------------------------------------------------


async def test_record_hash_includes_standard_profile_code(
    test_db, source_stream, project_id, workspace_id
):
    """record_hash 是 16 hex 字符串，改 device_type 后 hash 必须变化。

    注：RestrictionResult ORM 没有独立的 standard_profile_code 列（P6-1 Task 7
    schema 未含此列；标准代码走 input_json JSONB 容器）。验证通过 device_type
    字段变更触发 hash 漂移，间接证明 hash 含字段内容。
    """
    from app.services.calc_lineage import compute_record_hash

    req = _base_request(project_id, workspace_id)
    restriction_result = await RestrictionService.persist_calculate(
        test_db, source_stream_id=source_stream.stream_id, request=req,
    )

    # 1. 16 hex 格式
    assert restriction_result.record_hash != "", "record_hash 应非空"
    assert _HASH_RE.match(restriction_result.record_hash), (
        f"record_hash 应为 16 hex，实际 {restriction_result.record_hash!r}"
    )

    # 2. 改 device_type 后 hash 必须变化
    original_hash = restriction_result.record_hash
    restriction_result.device_type = "VENTURI"
    await test_db.flush()
    new_hash = compute_record_hash(restriction_result)
    assert new_hash != original_hash, (
        f"改 device_type 后 hash 应变化，实际仍为 {original_hash}"
    )


# ---------------------------------------------------------------------------
# 3. outlet stream 创建（RESTRICTION_CALCULATED + ISOENTHALPIC）
# ---------------------------------------------------------------------------


async def test_create_outlet_stream_isoenthalpic(
    test_db, source_stream, project_id, workspace_id
):
    """outlet stream 链创建：source_type=RESTRICTION_CALCULATED, change_type=ISOENTHALPIC。

    关键区别于 CV：control_valve 是 FRICTION_PRESSURE_DROP，限制装置是
    ISOENTHALPIC（等熵焓降；SPEC §3.2.2 line 192 + ADR-0022 V1.0）。
    """
    from app.models.enums import StreamSignStatus

    req = _base_request(project_id, workspace_id)
    await RestrictionService.persist_calculate(
        test_db, source_stream_id=source_stream.stream_id, request=req,
    )

    # 查 outlet stream（upstream_stream_id == source.stream_id）
    stmt = select(Stream).where(Stream.upstream_stream_id == source_stream.stream_id)
    outlet = (await test_db.execute(stmt)).scalar_one_or_none()
    assert outlet is not None, "应自动创建 outlet stream"
    assert outlet.source_type == "RESTRICTION_CALCULATED", (
        f"source_type 应为 RESTRICTION_CALCULATED，实际 {outlet.source_type}"
    )
    assert outlet.sign_status == StreamSignStatus.DRAFT, (
        f"sign_status 应为 DRAFT，实际 {outlet.sign_status}"
    )
    # properties 含 ADR-0022 关键字段（**关键：ISOENTHALPIC 区别 CV FRICTION**）
    props = outlet.stream_properties_json or {}
    assert props.get("change_type") == "ISOENTHALPIC", (
        f"change_type 应为 ISOENTHALPIC（区别 CV FRICTION_PRESSURE_DROP），"
        f"实际 {props.get('change_type')}"
    )
    assert "device" in props, "outlet properties 应含 device 字段"
    assert props.get("device_type") == "ORIFICE", (
        f"outlet device_type 应为 ORIFICE，实际 {props.get('device_type')}"
    )


# ---------------------------------------------------------------------------
# 4. 多工况批：独立 orifice_id + outlet 链
# ---------------------------------------------------------------------------


async def test_multi_scenario_batch(
    test_db, source_stream, project_id, workspace_id
):
    """多工况批：连续调用 5 次 persist_calculate，独立 orifice_id + outlet stream。"""
    orifice_ids: list[uuid.UUID] = []
    for i in range(5):
        req = _base_request(project_id, workspace_id)
        req["dP_pa"] = 5_000.0 + i * 5_000.0  # 5/10/15/20/25 kPa
        restriction_result = await RestrictionService.persist_calculate(
            test_db, source_stream_id=source_stream.stream_id, request=req,
        )
        orifice_ids.append(restriction_result.orifice_id)

    # 5 个独立 orifice_id
    assert len(set(orifice_ids)) == 5, (
        f"5 次调用应产出 5 个独立 orifice_id，实际 {orifice_ids}"
    )

    # 5 条 outlet stream
    stmt = select(Stream).where(Stream.upstream_stream_id == source_stream.stream_id)
    result = await test_db.execute(stmt)
    outlets = list(result.scalars().all())
    assert len(outlets) == 5, f"应自动创建 5 条 outlet stream，实际 {len(outlets)}"

    # 每条 outlet 的 device_type 应为 ORIFICE
    for outlet in outlets:
        props = outlet.stream_properties_json or {}
        assert props.get("device_type") == "ORIFICE"


# ---------------------------------------------------------------------------
# 5. device 命名格式：RES-{tag_number}
# ---------------------------------------------------------------------------


async def test_device_naming_format(
    test_db, source_stream, project_id, workspace_id
):
    """device 命名格式：RES-{tag_number}（outlet properties.device）。

    关键区别于 CV 的 CV-{tag_number} 前缀；RES = RESTRICTION 缩写。
    """
    req = _base_request(project_id, workspace_id)
    restriction_result = await RestrictionService.persist_calculate(
        test_db, source_stream_id=source_stream.stream_id, request=req,
    )

    expected_device = f"RES-{restriction_result.tag_number}"
    stmt = select(Stream).where(Stream.upstream_stream_id == source_stream.stream_id)
    outlet = (await test_db.execute(stmt)).scalar_one_or_none()
    assert outlet is not None
    props = outlet.stream_properties_json or {}
    assert props.get("device") == expected_device, (
        f"device 应为 {expected_device!r}，实际 {props.get('device')!r}"
    )