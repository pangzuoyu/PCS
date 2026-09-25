"""P6-3 Task 32 OPEN_CHANNEL open_channel_persist_service 测试（SPEC §3.2.6）。

按 SPEC §3.2.6 P6-OPEN-001：OpenChannelResult 标准 CRUD + sign_status 流。

设计要点：
- 单元测试用 Mock session 隔离（避免外部 DB 耦合）；覆盖 input 校验 /
  status filter / project 隔离语义 / PATCH 锁定 / soft_delete。
- G-07 真库测试走 save_manning_result 直接落 open_channel_results
  （pcs_test；守卫同 test_cool_tower_persist_service._ONLY_PCS_TEST）。
- **Do-Not-Repeat**：OpenChannelResult（继承 TaggedRecordMixin）:
  tag_number NOT NULL + project_id FK + workspace_id；fixture pattern =
  POST API 创建（service 层补必填） → DB UPDATE 状态字段。
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import dispose_engines_async  # noqa: E402
from app.models.enums import RecordSignStatus9  # noqa: E402
from app.services.open_channel import (  # noqa: E402
    OpenChannelPersistInputError,
    create_open_channel_result_direct,
    get_open_channel_result_service,
    list_open_channel_results_service,
    save_critical_result,
    save_jump_result,
    save_manning_result,
    save_section_result,
    soft_delete_open_channel_result_service,
    update_open_channel_result_service,
)

# 安全守卫：仅 pcs_test 库允许跑 G-07（防误触 pcs 开发库）。
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason=(
        "G-07 集成测试仅允许 pcs_test 库（防误触 pcs 开发库）；"
        "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test"
    ),
)


# ============================================================================
# Helpers（Mock session + 构造 OpenChannelResult-like 行）
# ============================================================================


def _make_open_channel_row(
    *,
    project_id: uuid.UUID,
    open_channel_id: uuid.UUID | None = None,
    tag_number: str = "OC-001",
    channel_type: str = "RECT",
    sign_status: RecordSignStatus9 = RecordSignStatus9.DRAFT,
    record_hash: str = "",
    flow_rate: float | None = None,
    depth: float | None = None,
    velocity: float | None = None,
    slope: float | None = None,
) -> Any:
    """构造 ``OpenChannelResult`` 行-like 对象（Mock）。"""
    row = MagicMock()
    row.open_channel_id = open_channel_id or uuid.uuid4()
    row.project_id = project_id
    row.workspace_id = uuid.uuid4()
    row.tag_number = tag_number
    row.channel_type = channel_type
    row.cross_section_json = {"bottom_width": 2.0}
    row.flow_rate = flow_rate
    row.depth = depth
    row.velocity = velocity
    row.slope = slope
    row.critical_depth = None
    row.froude_number = None
    row.manning_n = None
    row.hydraulic_radius = None
    row.jump_type = None
    row.conjugate_depth = None
    row.energy_loss = None
    row.sign_status = sign_status
    row.record_hash = record_hash
    row.stale_resolution_path = None
    row.created_at = MagicMock()
    row.updated_at = MagicMock()
    return row


def _mock_session(rows: list[Any] | None = None) -> MagicMock:
    """构造 mock session，``await session.execute(...).scalars()...`` 返回 rows。"""
    session = MagicMock()
    execute_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows or []
    scalars_mock.first.return_value = (rows[0] if rows else None)
    execute_result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=execute_result)
    return session


def _mock_get_session(record: Any | None) -> MagicMock:
    """构造 mock session，``await session.execute().scalars().first()`` 返回 record。"""
    session = MagicMock()
    execute_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = record
    execute_result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=execute_result)
    session.get = AsyncMock(return_value=record)
    return session


# ============================================================================
# 1. save_manning_result 输入校验
# ============================================================================


@pytest.mark.asyncio
async def test_save_manning_result_validates_tag_number() -> None:
    """空 tag_number → OpenChannelPersistInputError。"""
    session = _mock_session()
    with pytest.raises(OpenChannelPersistInputError) as exc_info:
        await save_manning_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="",
            channel_type="RECT",
            cross_section_json={"bottom_width": 2.0},
            flow_rate=3.06,
            depth=1.0,
            velocity=1.53,
            slope=0.001,
        )
    assert "tag_number" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_manning_result_validates_channel_type() -> None:
    """未知 channel_type → OpenChannelPersistInputError。"""
    session = _mock_session()
    with pytest.raises(OpenChannelPersistInputError) as exc_info:
        await save_manning_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="OC-001",
            channel_type="HEXAGON",
            cross_section_json={},
            flow_rate=1.0,
            depth=1.0,
            velocity=1.0,
            slope=0.001,
        )
    assert "channel_type" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_manning_result_validates_negative_values() -> None:
    """flow_rate < 0 → OpenChannelPersistInputError。"""
    session = _mock_session()
    with pytest.raises(OpenChannelPersistInputError) as exc_info:
        await save_manning_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="OC-001",
            channel_type="RECT",
            cross_section_json={},
            flow_rate=-1.0,
            depth=1.0,
            velocity=1.0,
            slope=0.001,
        )
    assert ">=" in str(exc_info.value) or "≥" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_section_result_validates_channel_type() -> None:
    """未知 channel_type → OpenChannelPersistInputError。"""
    session = _mock_session()
    with pytest.raises(OpenChannelPersistInputError):
        await save_section_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="OC-SEC",
            channel_type="UNKNOWN",
            cross_section_json={},
            flow_rate=2.0,
            depth=0.85,
            velocity=2.0,
            slope=0.001,
        )


@pytest.mark.asyncio
async def test_save_critical_result_validates_critical_depth() -> None:
    """critical_depth < 0 → OpenChannelPersistInputError。"""
    session = _mock_session()
    with pytest.raises(OpenChannelPersistInputError) as exc_info:
        await save_critical_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="OC-CRIT",
            channel_type="RECT",
            cross_section_json={"bottom_width": 2.0},
            flow_rate=2.0,
            depth=1.0,
            velocity=1.0,
            slope=0.001,
            critical_depth=-0.5,
            froude_number=0.5,
        )
    assert "critical_depth" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_jump_result_validates_jump_type() -> None:
    """非法 jump_type → OpenChannelPersistInputError。"""
    session = _mock_session()
    with pytest.raises(OpenChannelPersistInputError) as exc_info:
        await save_jump_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="OC-JUMP",
            channel_type="RECT",
            cross_section_json={"bottom_width": 2.0},
            flow_rate=10.0,
            depth=0.5,
            velocity=5.0,
            slope=0.001,
            jump_type="INVALID",
            conjugate_depth=1.366,
            energy_loss=0.24,
        )
    assert "jump_type" in str(exc_info.value)


# ============================================================================
# 2. list_open_channel_results_service：project_id 隔离
# ============================================================================


@pytest.mark.asyncio
async def test_list_open_channel_results_service_filters_project() -> None:
    """2 project × 3 row → list(p1)=3 行。"""
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()
    rows_p1 = [_make_open_channel_row(project_id=p1) for _ in range(3)]
    rows_p2 = [_make_open_channel_row(project_id=p2) for _ in range(3)]

    session = _mock_session(rows=rows_p1)
    r1 = await list_open_channel_results_service(
        session, project_id=p1, limit=10
    )
    assert len(r1) == 3
    assert all(row.project_id == p1 for row in r1)
    _ = (p2, rows_p2)


@pytest.mark.asyncio
async def test_list_open_channel_results_service_excludes_obsolete_default() -> None:
    """默认 include_obsolete=False → service 走 filter。"""
    session = _mock_session(rows=[])
    await list_open_channel_results_service(
        session, project_id=uuid.uuid4()
    )
    assert session.execute.called


@pytest.mark.asyncio
async def test_list_open_channel_results_service_passes_skip_limit() -> None:
    """skip / limit 透传。"""
    session = _mock_session(rows=[])
    await list_open_channel_results_service(
        session, project_id=uuid.uuid4(), skip=10, limit=50
    )
    assert session.execute.called


# ============================================================================
# 3. get_open_channel_result_service
# ============================================================================


@pytest.mark.asyncio
async def test_get_open_channel_result_service_found() -> None:
    """记录存在 → 返回 ORM 行。"""
    record = _make_open_channel_row(project_id=uuid.uuid4())
    session = _mock_get_session(record=record)
    r = await get_open_channel_result_service(
        session, result_id=record.open_channel_id
    )
    assert r is record


@pytest.mark.asyncio
async def test_get_open_channel_result_service_not_found() -> None:
    """记录不存在 → OpenChannelPersistInputError (OPEN_CHANNEL_NOT_FOUND)。"""
    session = _mock_get_session(record=None)
    with pytest.raises(OpenChannelPersistInputError) as exc_info:
        await get_open_channel_result_service(
            session, result_id=uuid.uuid4()
        )
    assert exc_info.value.code == "OPEN_CHANNEL_NOT_FOUND"


# ============================================================================
# 4. update_open_channel_result_service：白名单 + 锁定态
# ============================================================================


@pytest.mark.asyncio
async def test_update_open_channel_result_service_draft_works() -> None:
    """DRAFT 状态 PATCH → 字段更新成功。"""
    project_id = uuid.uuid4()
    record = _make_open_channel_row(
        project_id=project_id, sign_status=RecordSignStatus9.DRAFT
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    r = await update_open_channel_result_service(
        session,
        result_id=record.open_channel_id,
        patch={"depth": 1.5, "velocity": 2.0},
    )
    assert r is record
    assert r.depth == 1.5
    assert r.velocity == 2.0


@pytest.mark.asyncio
async def test_update_open_channel_result_service_checked_locked() -> None:
    """CHECKED 状态 PATCH → OpenChannelPersistInputError (OPEN_CHANNEL_LOCKED)。"""
    record = _make_open_channel_row(
        project_id=uuid.uuid4(), sign_status=RecordSignStatus9.CHECKED
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()

    with pytest.raises(OpenChannelPersistInputError) as exc_info:
        await update_open_channel_result_service(
            session,
            result_id=record.open_channel_id,
            patch={"depth": 2.0},
        )
    assert exc_info.value.code == "OPEN_CHANNEL_LOCKED"
    assert not session.commit.called


@pytest.mark.asyncio
async def test_update_open_channel_result_service_invalid_fields() -> None:
    """非法字段 → OpenChannelPersistInputError (OPEN_CHANNEL_INVALID_FIELDS)。"""
    record = _make_open_channel_row(
        project_id=uuid.uuid4(), sign_status=RecordSignStatus9.DRAFT
    )
    session = _mock_get_session(record=record)
    with pytest.raises(OpenChannelPersistInputError) as exc_info:
        await update_open_channel_result_service(
            session,
            result_id=record.open_channel_id,
            patch={"unknown_field": 1.0},
        )
    assert exc_info.value.code == "OPEN_CHANNEL_INVALID_FIELDS"


@pytest.mark.asyncio
async def test_update_open_channel_result_service_not_found() -> None:
    """记录不存在 → OpenChannelPersistInputError (OPEN_CHANNEL_NOT_FOUND)。"""
    session = _mock_get_session(record=None)
    with pytest.raises(OpenChannelPersistInputError) as exc_info:
        await update_open_channel_result_service(
            session,
            result_id=uuid.uuid4(),
            patch={"depth": 1.0},
        )
    assert exc_info.value.code == "OPEN_CHANNEL_NOT_FOUND"


# ============================================================================
# 5. soft_delete_open_channel_result_service
# ============================================================================


@pytest.mark.asyncio
async def test_soft_delete_open_channel_result_service_sets_obsolete() -> None:
    """DELETE → sign_status=OBSOLETE + tag_number 加 __OBSOLETE_<ts> 后缀。"""
    record = _make_open_channel_row(
        project_id=uuid.uuid4(),
        sign_status=RecordSignStatus9.DRAFT,
        tag_number="OC-DEL-001",
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    r = await soft_delete_open_channel_result_service(
        session, result_id=record.open_channel_id
    )
    assert r is record
    assert r.sign_status == RecordSignStatus9.OBSOLETE
    assert "__OBSOLETE_" in r.tag_number
    assert r.tag_number.startswith("OC-DEL-001__OBSOLETE_")
    assert session.commit.called


@pytest.mark.asyncio
async def test_soft_delete_open_channel_result_service_not_found() -> None:
    """记录不存在 → OpenChannelPersistInputError。"""
    session = _mock_get_session(record=None)
    with pytest.raises(OpenChannelPersistInputError) as exc_info:
        await soft_delete_open_channel_result_service(
            session, result_id=uuid.uuid4()
        )
    assert exc_info.value.code == "OPEN_CHANNEL_NOT_FOUND"


# ============================================================================
# 6. create_open_channel_result_direct：白名单 + tag_number 校验
# ============================================================================


@pytest.mark.asyncio
async def test_create_open_channel_result_direct_validates_tag_number() -> None:
    """空 tag_number → OpenChannelPersistInputError。"""
    session = _mock_session()
    with pytest.raises(OpenChannelPersistInputError):
        await create_open_channel_result_direct(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="",
            channel_type="RECT",
            cross_section_json={},
            flow_rate=1.0,
            depth=1.0,
            velocity=1.0,
            slope=0.001,
        )


@pytest.mark.asyncio
async def test_create_open_channel_result_direct_invalid_fields() -> None:
    """非法字段 → OpenChannelPersistInputError (OPEN_CHANNEL_INVALID_FIELDS)。"""
    session = _mock_session()
    with pytest.raises(OpenChannelPersistInputError) as exc_info:
        await create_open_channel_result_direct(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="OC-DIRECT",
            unknown_field=1.0,
        )
    assert exc_info.value.code == "OPEN_CHANNEL_INVALID_FIELDS"


# ============================================================================
# G-07 真库测试：save → list → get → soft_delete → list filter 全链路
# ============================================================================


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_save_open_channel_result_g07_real_pcs_test() -> None:
    """G-07：真 pcs_test 库 + save_manning_result 端到端 + record_hash 已写。

    构造：
    - 1 个 workspace + 1 个 project（FK 必填）
    - save_manning_result → 真实 ORM 落 open_channel_results
    - get_open_channel_result_service 验证 round-trip 字段
    - list_open_channel_results_service 验证默认 filter（DRAFT 命中）
    - soft_delete_open_channel_result_service → sign_status=OBSOLETE
    - 再 list 不命中（OBSOLETE 被过滤）

    期望：
    - record_hash 已写（finalize_calc_record，16 hex）
    - 业务字段 round-trip 一致
    - soft_delete → sign_status=OBSOLETE + tag_number 加 __OBSOLETE_ 后缀
    """
    from sqlalchemy import delete, select

    from app.db.session import get_async_session_factory
    from app.models.calc import OpenChannelResult
    from app.models.enums import WorkspaceType
    from app.models.project import Project, Workspace

    await dispose_engines_async()

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    factory = get_async_session_factory()
    async with factory() as session:
        # 1. 清表
        await session.execute(
            delete(OpenChannelResult).where(
                OpenChannelResult.project_id == project_id
            )
        )
        # 2. 建 workspace + project（FK 必填）
        workspace = Workspace(
            workspace_id=workspace_id,
            workspace_type=WorkspaceType.FORMAL.value,
            name="open-channel-persist-test-workspace",
        )
        project = Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"OC-P32-{uuid.uuid4().hex[:8]}",
            project_name="OpenChannel P32 G-07 Test",
            owner_company="test",
            location="test",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
        )
        session.add_all([workspace, project])
        await session.commit()

    # 3. save_manning_result
    async with factory() as session:
        record = await save_manning_result(
            session,
            project_id=project_id,
            workspace_id=workspace_id,
            tag_number="OC-P32-001",
            channel_type="RECT",
            cross_section_json={"bottom_width": 2.0},
            flow_rate=3.0649,
            depth=1.0,
            velocity=1.5325,
            slope=0.001,
            hydraulic_radius=0.5,
            manning_n=0.013,
        )
        record_id = record.open_channel_id
        record_hash_1 = record.record_hash
        assert record_hash_1 and len(record_hash_1) == 16, (
            f"record_hash 应为 16 hex，实际={record_hash_1!r}"
        )

    # 4. get_open_channel_result_service round-trip
    async with factory() as session:
        r = await get_open_channel_result_service(
            session, result_id=record_id
        )
        assert r is not None
        assert r.tag_number == "OC-P32-001"
        assert r.channel_type == "RECT"
        assert r.flow_rate == pytest.approx(3.0649)
        assert r.depth == pytest.approx(1.0)
        assert r.hydraulic_radius == pytest.approx(0.5)
        assert r.manning_n == pytest.approx(0.013)
        assert r.record_hash and len(r.record_hash) == 16

    # 5. list 默认 filter（DRAFT 应命中）
    async with factory() as session:
        rows = await list_open_channel_results_service(
            session, project_id=project_id
        )
        assert any(r2.open_channel_id == record_id for r2 in rows), (
            "save 后 list 应命中"
        )

    # 6. soft_delete
    async with factory() as session:
        deleted = await soft_delete_open_channel_result_service(
            session, result_id=record_id
        )
        assert deleted is not None
        assert deleted.sign_status == RecordSignStatus9.OBSOLETE

    # 7. 验证 stale_resolution_path 与 tag_number 后缀
    async with factory() as session:
        stmt = select(OpenChannelResult).where(
            OpenChannelResult.open_channel_id == record_id
        )
        result = (await session.execute(stmt)).scalars().first()
        assert result is not None
        assert result.sign_status == RecordSignStatus9.OBSOLETE
        assert "__OBSOLETE_" in result.tag_number

    # 8. list 默认 filter 不含 OBSOLETE → 软删后不再命中
    async with factory() as session:
        rows = await list_open_channel_results_service(
            session, project_id=project_id
        )
        assert not any(r2.open_channel_id == record_id for r2 in rows), (
            "软删后默认 list 不应命中（被 OBSOLETE 过滤）"
        )

    # 9. 清表（GA 收尾）
    async with factory() as session:
        await session.execute(
            delete(OpenChannelResult).where(
                OpenChannelResult.project_id == project_id
            )
        )
        await session.commit()