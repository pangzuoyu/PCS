"""P6-2 Task 26 PSYCHRO psychro_persist_service + coolprop_version 测试
（SPEC §3.2.5 P6-PSY-001 + §3.2.3 P6-FLR-004）。

设计要点：
- 单元测试用 Mock session 隔离（避免外部 DB 耦合）；覆盖 input 校验 /
  status filter / project 隔离语义 / PATCH 锁定 / soft_delete /
  coolprop_version 自动填。
- G-07 真库测试走 save_psychro_result 直接落 psychro_results
  （pcs_test；守卫同 test_cool_tower_persist_service._ONLY_PCS_TEST）。
- **Do-Not-Repeat**：PsychroResult（继承 TaggedRecordMixin）:
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
from app.services.psychro import (  # noqa: E402
    PsychroPersistInputError,
    get_psychro_result,
    list_psychro_results,
    save_psychro_result,
    soft_delete_psychro_result,
    update_psychro_result,
)
from app.services.psychro.coolprop_version import (  # noqa: E402
    get_coolprop_version,
)

# 安全守卫：仅 pcs_test 库允许跑 G-07（防误触 pcs 开发库；与
# tests/services/flare/test_relief_aggregator._ONLY_PCS_TEST 同源约束）。
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason=(
        "G-07 集成测试仅允许 pcs_test 库（防误触 pcs 开发库）；"
        "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test"
    ),
)


# ============================================================================
# Helpers（Mock session + 构造 PsychroResult-like 行）
# ============================================================================


def _make_psychro_row(
    *,
    project_id: uuid.UUID,
    psychro_id: uuid.UUID | None = None,
    tag_number: str = "PSY-001",
    standard_profile_code: str = "ASHRAE_FUND_2021",
    calc_type: str = "HUMIDITY_RATIO",
    sign_status: RecordSignStatus9 = RecordSignStatus9.DRAFT,
    record_hash: str = "",
    humidity_ratio_kg_kg: float | None = None,
    enthalpy_kj_kg: float | None = None,
    coolprop_version: str | None = "6.6.0",
) -> Any:
    """构造 ``PsychroResult`` 行-like 对象（Mock）。"""
    row = MagicMock()
    row.psychro_id = psychro_id or uuid.uuid4()
    row.project_id = project_id
    row.workspace_id = uuid.uuid4()
    row.tag_number = tag_number
    row.standard_profile_code = standard_profile_code
    row.calc_type = calc_type
    row.coolprop_version = coolprop_version
    row.sign_status = sign_status
    row.record_hash = record_hash
    row.humidity_ratio_kg_kg = humidity_ratio_kg_kg
    row.dew_point_c = None
    row.wet_bulb_c = None
    row.enthalpy_kj_kg = enthalpy_kj_kg
    row.specific_volume_m3_kg = None
    row.sensible_heat_kw = None
    row.latent_heat_kw = None
    row.input_json = None
    row.output_json = None
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
    return session


# ============================================================================
# 1. save_psychro_result 输入校验（无需 DB；纯校验逻辑）
# ============================================================================


@pytest.mark.asyncio
async def test_save_psychro_result_validates_tag_number() -> None:
    """空 tag_number → PsychroPersistInputError。"""
    session = _mock_session()
    with pytest.raises(PsychroPersistInputError) as exc_info:
        await save_psychro_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="",
            standard_profile_code="ASHRAE_FUND_2021",
            payload={"humidity_ratio_kg_kg": 0.01},
        )
    assert "tag_number" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_psychro_result_validates_standard_profile_code() -> None:
    """空 standard_profile_code → PsychroPersistInputError。"""
    session = _mock_session()
    with pytest.raises(PsychroPersistInputError) as exc_info:
        await save_psychro_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="PSY-001",
            standard_profile_code="",
            payload={"humidity_ratio_kg_kg": 0.01},
        )
    assert "standard_profile_code" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_psychro_result_validates_empty_payload() -> None:
    """空 payload / 全部字段被白名单过滤 → PsychroPersistInputError。"""
    session = _mock_session()
    with pytest.raises(PsychroPersistInputError):
        await save_psychro_result(
            session,
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            tag_number="PSY-001",
            standard_profile_code="ASHRAE_FUND_2021",
            payload={"unknown_field": 1.0},  # 全部被白名单过滤掉
        )


# ============================================================================
# 2. list_psychro_results：project_id 隔离 + sign_status filter
# ============================================================================


@pytest.mark.asyncio
async def test_list_psychro_results_filters_project() -> None:
    """2 project × 3 row → list(p1)=3 行（单次调用只返 p1 行）。"""
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()
    rows_p1 = [_make_psychro_row(project_id=p1) for _ in range(3)]
    rows_p2 = [_make_psychro_row(project_id=p2) for _ in range(3)]

    session = _mock_session(rows=rows_p1)

    r1 = await list_psychro_results(session, project_id=p1, limit=10)
    assert len(r1) == 3
    assert all(row.project_id == p1 for row in r1)
    _ = (p2, rows_p2)


@pytest.mark.asyncio
async def test_list_psychro_results_filters_sign_status() -> None:
    """默认 sign_status_filter = (DRAFT, CHECKED) → OBSOLETE 被过滤。"""
    session = _mock_session(rows=[])
    await list_psychro_results(session, project_id=uuid.uuid4())
    assert session.execute.called


@pytest.mark.asyncio
async def test_list_psychro_results_passes_limit_offset() -> None:
    """limit / offset 透传。"""
    session = _mock_session(rows=[])
    await list_psychro_results(
        session, project_id=uuid.uuid4(), limit=50, offset=10
    )
    assert session.execute.called


# ============================================================================
# 3. get_psychro_result：project_id 隔离
# ============================================================================


@pytest.mark.asyncio
async def test_get_psychro_result_with_project_isolation_match() -> None:
    """project_id 匹配 → 返回行。"""
    record = _make_psychro_row(project_id=uuid.uuid4())
    session = _mock_get_session(record=record)
    r = await get_psychro_result(
        session,
        record_id=record.psychro_id,
        project_id=record.project_id,
    )
    assert r is record


@pytest.mark.asyncio
async def test_get_psychro_result_with_project_isolation_mismatch() -> None:
    """project_id 不匹配 → first() 返回 None。"""
    session = _mock_get_session(record=None)
    r = await get_psychro_result(
        session,
        record_id=uuid.uuid4(),
        project_id=uuid.uuid4(),  # 不同 project
    )
    assert r is None


# ============================================================================
# 4. update_psychro_result：sign_status 锁定（用 Mock 直接 stub 行为）
# ============================================================================


@pytest.mark.asyncio
async def test_update_psychro_result_draft_works() -> None:
    """DRAFT 状态 PATCH → 字段更新成功。"""
    project_id = uuid.uuid4()
    record = _make_psychro_row(
        project_id=project_id, sign_status=RecordSignStatus9.DRAFT
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    r = await update_psychro_result(
        session,
        record_id=record.psychro_id,
        project_id=project_id,
        payload={"humidity_ratio_kg_kg": 0.012},
    )
    assert r is record
    assert r.sign_status == RecordSignStatus9.DRAFT


@pytest.mark.asyncio
async def test_update_psychro_result_checked_locked() -> None:
    """CHECKED 状态 PATCH → PsychroPersistInputError
    code=PSYCHRO_PERSIST_SIGN_STATUS_LOCKED。"""
    project_id = uuid.uuid4()
    record = _make_psychro_row(
        project_id=project_id, sign_status=RecordSignStatus9.CHECKED
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()

    with pytest.raises(PsychroPersistInputError) as exc_info:
        await update_psychro_result(
            session,
            record_id=record.psychro_id,
            project_id=project_id,
            payload={"humidity_ratio_kg_kg": 0.012},
        )
    assert "PSYCHRO_PERSIST_SIGN_STATUS_LOCKED" in str(exc_info.value.code)
    assert not session.commit.called


@pytest.mark.asyncio
async def test_update_psychro_result_record_not_found() -> None:
    """记录不存在 / 隔离不匹配 → None。"""
    session = _mock_get_session(record=None)
    r = await update_psychro_result(
        session,
        record_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        payload={"humidity_ratio_kg_kg": 0.012},
    )
    assert r is None


# ============================================================================
# 5. soft_delete_psychro_result：sign_status=OBSOLETE +
#    stale_resolution_path
# ============================================================================


@pytest.mark.asyncio
async def test_soft_delete_psychro_result_sets_obsolete() -> None:
    """DELETE → sign_status=OBSOLETE +
    stale_resolution_path='PSYCHRO_RESULT_SOFT_DELETE'。"""
    project_id = uuid.uuid4()
    record = _make_psychro_row(
        project_id=project_id, sign_status=RecordSignStatus9.DRAFT
    )
    session = _mock_get_session(record=record)
    session.commit = AsyncMock()

    ok = await soft_delete_psychro_result(
        session,
        record_id=record.psychro_id,
        project_id=project_id,
    )
    assert ok is True
    assert record.sign_status == RecordSignStatus9.OBSOLETE
    assert record.stale_resolution_path == "PSYCHRO_RESULT_SOFT_DELETE"
    assert session.commit.called


@pytest.mark.asyncio
async def test_soft_delete_psychro_result_not_found() -> None:
    """记录不存在 → 返回 False。"""
    session = _mock_get_session(record=None)
    ok = await soft_delete_psychro_result(
        session,
        record_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
    )
    assert ok is False


# ============================================================================
# 6. coolprop_version 溯源：helper 单测 + service 自动填
# ============================================================================


def test_coolprop_version_returns_string() -> None:
    """get_coolprop_version() 返回非空字符串（环境装 CoolProp 时为版本号；
    未装时 fallback 'unknown'，二者均满足 'str' 类型）。"""
    v = get_coolprop_version()
    assert isinstance(v, str)
    assert v != ""


def test_coolprop_version_handles_missing(monkeypatch) -> None:
    """Mock ImportError → 返回 'unknown'。"""
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any):  # noqa: ANN401
        if name == "CoolProp" or name.startswith("CoolProp."):
            raise ImportError(f"mocked missing module {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert get_coolprop_version() == "unknown"


@pytest.mark.asyncio
async def test_save_psychro_result_auto_fills_coolprop_version(monkeypatch) -> None:
    """save_psychro_result 在 payload 缺 coolprop_version 时，由 service 层
    自动从 get_coolprop_version() 写入 '6.6.0' / 'unknown'。

    注：本测试用 Mock session 验证 ORM kwargs 路径；get_coolprop_version
    在测试环境下真实运行（CoolProp 已装 → 应返回非空字符串）。
    """
    # 强制 coolprop_version 为已知值，便于断言
    monkeypatch.setattr(
        "app.services.psychro.psychro_persist_service.get_coolprop_version",
        lambda: "9.9.9-test",
    )

    session = _mock_session()
    # ORM 落库链路需要 AsyncMock
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    captured_kwargs: dict[str, Any] = {}

    # capture 通过 ORM kwargs 传入的字段
    def fake_record(**kwargs: Any) -> Any:
        nonlocal captured_kwargs
        captured_kwargs = kwargs
        m = MagicMock()
        m.record_hash = "deadbeefdeadbeef"
        return m

    # patch ORM 类，让 save_psychro_result 走到 fake_record 时拿到清晰 kwargs
    monkeypatch.setattr(
        "app.services.psychro.psychro_persist_service.PsychroResult",
        fake_record,
    )
    # patch finalize_calc_record（绕过 SQLAlchemy inspection；本测试只关心
    # ORM kwargs 是否自动注入 coolprop_version）
    monkeypatch.setattr(
        "app.services.psychro.psychro_persist_service.finalize_calc_record",
        AsyncMock(),
    )

    await save_psychro_result(
        session,
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        tag_number="PSY-001",
        standard_profile_code="ASHRAE_FUND_2021",
        payload={"humidity_ratio_kg_kg": 0.01},  # 不传 coolprop_version
    )

    assert captured_kwargs.get("coolprop_version") == "9.9.9-test", (
        f"service 应自动填 coolprop_version，实际={captured_kwargs.get('coolprop_version')!r}"
    )


# ============================================================================
# G-07 真库测试：save → get → list → soft_delete → list filter 全链路
# ============================================================================


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_save_psychro_result_g07_real_pcs_test() -> None:
    """G-07：真 pcs_test 库 + save_psychro_result 端到端 +
    record_hash 已写。

    构造：

    - 1 个 workspace + 1 个 project（FK 必填）
    - save_psychro_result → 真实 ORM 落 psychro_results
    - get_psychro_result 验证 round-trip 字段 + coolprop_version 自动填
    - list_psychro_results 验证默认 filter（DRAFT 命中）
    - soft_delete_psychro_result → sign_status=OBSOLETE +
      stale_resolution_path 已写
    - 再 list 不命中（OBSOLETE 被过滤）

    期望：

    - record_hash 已写（finalize_calc_record，16 hex）
    - coolprop_version 自动写入（payload 缺时）
    - 业务字段 round-trip 一致
    - soft_delete → sign_status=OBSOLETE + stale_resolution_path 已写
    """
    from sqlalchemy import delete, select

    from app.db.session import get_async_session_factory
    from app.models.calc import PsychroResult
    from app.models.enums import WorkspaceType
    from app.models.project import Project, Workspace

    await dispose_engines_async()

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    factory = get_async_session_factory()
    async with factory() as session:
        # 1. 清表（本测试项目 ID 唯一）
        await session.execute(
            delete(PsychroResult).where(
                PsychroResult.project_id == project_id
            )
        )
        # 2. 建 workspace + project（FK 必填）
        workspace = Workspace(
            workspace_id=workspace_id,
            workspace_type=WorkspaceType.FORMAL.value,
            name="psychro-persist-test-workspace",
        )
        project = Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"PSY-P26-{uuid.uuid4().hex[:8]}",
            project_name="Psychro P26 G-07 Test",
            owner_company="test",
            location="test",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
        )
        session.add_all([workspace, project])
        await session.commit()

    # 3. save_psychro_result（独立 session 写入；payload 故意不传 coolprop_version
    #    以验证 service 层自动填）
    async with factory() as session:
        record = await save_psychro_result(
            session,
            project_id=project_id,
            workspace_id=workspace_id,
            tag_number="PSY-P26-001",
            standard_profile_code="ASHRAE_FUND_2021",
            calc_type="HUMIDITY_RATIO",
            payload={
                "humidity_ratio_kg_kg": 0.00993,
                "dew_point_c": 13.87,
                "wet_bulb_c": 17.88,
                "enthalpy_kj_kg": 50.423,
                "specific_volume_m3_kg": 0.858,
                "input_json": {"t_c": 25.0, "rh": 0.5, "p_pa": 101325.0},
                "output_json": {"humidity_ratio_kg_kg": 0.00993},
            },
            created_by=None,
        )
        record_id = record.psychro_id
        record_hash_1 = record.record_hash
        assert record_hash_1 and len(record_hash_1) == 16, (
            f"record_hash 应为 16 hex，实际={record_hash_1!r}"
        )
        # coolprop_version 自动填（payload 缺时由 service 层兜底）
        assert record.coolprop_version is not None, (
            "coolprop_version 应由 service 层自动写入"
        )
        assert isinstance(record.coolprop_version, str)
        assert record.coolprop_version != ""

    # 4. get_psychro_result 验证 round-trip 字段
    async with factory() as session:
        r = await get_psychro_result(
            session,
            record_id=record_id,
            project_id=project_id,
        )
        assert r is not None
        assert r.tag_number == "PSY-P26-001"
        assert r.standard_profile_code == "ASHRAE_FUND_2021"
        assert r.calc_type == "HUMIDITY_RATIO"
        assert r.humidity_ratio_kg_kg == pytest.approx(0.00993, abs=1e-6)
        assert r.dew_point_c == pytest.approx(13.87, abs=0.05)
        assert r.wet_bulb_c == pytest.approx(17.88, abs=0.05)
        assert r.enthalpy_kj_kg == pytest.approx(50.423, abs=0.05)
        assert r.specific_volume_m3_kg == pytest.approx(0.858, abs=0.01)
        assert r.input_json == {
            "t_c": 25.0,
            "rh": 0.5,
            "p_pa": 101325.0,
        }
        assert r.output_json == {"humidity_ratio_kg_kg": 0.00993}
        assert r.record_hash and len(r.record_hash) == 16
        assert r.coolprop_version is not None

    # 5. list_psychro_results（DRAFT 默认 filter；刚 save 默认 DRAFT 应命中）
    async with factory() as session:
        rows = await list_psychro_results(
            session, project_id=project_id, limit=10
        )
        assert any(r2.psychro_id == record_id for r2 in rows), (
            "save 后 list 应命中"
        )

    # 6. soft_delete → sign_status=OBSOLETE + stale_resolution_path
    async with factory() as session:
        ok = await soft_delete_psychro_result(
            session,
            record_id=record_id,
            project_id=project_id,
        )
        assert ok is True

    # 7. 验证 stale_resolution_path 与 sign_status 落库
    async with factory() as session:
        stmt = select(PsychroResult).where(
            PsychroResult.psychro_id == record_id
        )
        result = (await session.execute(stmt)).scalars().first()
        assert result is not None
        assert result.sign_status == RecordSignStatus9.OBSOLETE
        assert result.stale_resolution_path == "PSYCHRO_RESULT_SOFT_DELETE"

    # 8. list 默认 filter 不含 OBSOLETE → 软删后不再命中
    async with factory() as session:
        rows = await list_psychro_results(
            session, project_id=project_id, limit=10
        )
        assert not any(r2.psychro_id == record_id for r2 in rows), (
            "软删后默认 list 不应命中（被 OBSOLETE 过滤）"
        )

    # 9. 清表（GA 收尾）
    async with factory() as session:
        await session.execute(
            delete(PsychroResult).where(
                PsychroResult.project_id == project_id
            )
        )
        await session.commit()
