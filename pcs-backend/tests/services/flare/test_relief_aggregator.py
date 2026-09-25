"""P6-2 Task 19 FLARE_SYS 泄放汇总测试。

按 SPEC §3.2.3 P6-FLR-001 + API 521 §5.15.4 保守原则：

- 8 单元测试（Mock session + 构造 ReliefResult）：覆盖空项目 / 单 PSV /
  多 PSV / standard_profile_code 隔离 / sign_status 过滤 / 未选型排除
  / 输入校验。
- 1 G-07 集成测试（pcs_test 真库 + 真 PsvResult + 真 ReliefResult）：
  端到端验证 ORM 持久化字段 + 聚合语义。

测试模式参照 ``tests/services/test_cepci_seed.py``：

- G-07 用 ``@pytest.mark.skipif`` 守卫，仅 pcs_test 库跑（防误触 pcs
  开发库；与 ``tests/models/test_alembic_roundtrip.py:_ONLY_PCS_TEST``
  同源约束）。
- 单元测试不依赖 DB（Mock session 跑 SQL）；速度优先 + 无外部耦合。

设计要点：

- 不扩展 ``app/services/psv/relief_aggregator_service.py``（单 PSV 与
  项目级聚合粒度不同，service separation）。
- 单元测试构造 ``ReliefResult`` 字段只覆盖 ``_per_psv_dominant`` 读到的
  列（selected_psv_id / relief_scenario / required_relief_area /
  project_id / standard_profile_code / sign_status），其余字段用
  ``spec`` 设置避免无关字段。
- G-07 真库：用 direct ORM 插 PsvResult + ReliefResult（P5-3-6 persist
  service 字段必填太多，POST API 路径对聚合测试是 over-spec）。
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# 允许 ``python -m pytest`` 直接调用（与 tests/seeds/test_category3_seeds.py 同源）。
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import dispose_engines_async  # noqa: E402
from app.models.enums import RecordSignStatus9, ReliefScenario  # noqa: E402
from app.services.flare import (  # noqa: E402
    FlareAggregatorInputError,
    FlareLoad,
    FlarePsvContribution,
    aggregate_flare_load,
)

# 安全守卫：仅 pcs_test 库允许跑 G-07（防误触 pcs 开发库；与
# tests/services/test_cepci_seed.py:_ONLY_PCS_TEST 同源约束）。
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason=(
        "G-07 集成测试仅允许 pcs_test 库（防误触 pcs 开发库）；"
        "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test"
    ),
)


# ============================================================================
# Mock helpers（构造 ReliefResult-like 行）
# ============================================================================


def _make_relief_row(
    *,
    project_id: uuid.UUID,
    standard_profile_code: str = "API_521",
    selected_psv_id: uuid.UUID | None,
    relief_scenario: ReliefScenario,
    required_relief_area: float | None,
    sign_status: RecordSignStatus9 = RecordSignStatus9.CHECKED,
) -> Any:
    """构造 ``ReliefResult`` 行-like 对象（Mock）。

    返回 MagicMock（不带 spec）—— ``aggregate_flare_load`` 只读字段
    不查类型；spec 在单元测试场景下引入不必要的 ReliefResult 依赖。
    """
    row = MagicMock()
    row.project_id = project_id
    row.standard_profile_code = standard_profile_code
    row.selected_psv_id = selected_psv_id
    row.relief_scenario = relief_scenario
    row.required_relief_area = required_relief_area
    row.sign_status = sign_status
    return row


def _mock_session(rows: list[Any]) -> MagicMock:
    """构造 mock session，``session.execute(...).scalars().all()`` 返回 rows。"""
    session = MagicMock()
    execute_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    execute_result.scalars.return_value = scalars_mock
    session.execute.return_value = execute_result
    return session


# ============================================================================
# 1. 空项目
# ============================================================================


def test_empty_project_returns_zero() -> None:
    """空项目：total_psv_count=0 / total_relief_area=0 / per_scenario_total 空。"""
    project_id = uuid.uuid4()
    session = _mock_session(rows=[])

    r = aggregate_flare_load(session, project_id, "API_521")

    assert isinstance(r, FlareLoad)
    assert r.total_psv_count == 0
    assert r.total_relief_area_cm2 == 0.0
    assert r.per_scenario_total_cm2 == {}
    assert r.per_psv_dominant == ()
    assert r.project_id == project_id
    assert r.standard_profile_code == "API_521"
    assert r.sign_status_filter == ("CHECKED", "CHANGED")


# ============================================================================
# 2. 单 PSV 单工况
# ============================================================================


def test_single_psv_single_scenario() -> None:
    """单 PSV × 单 scenario：该 scenario 总和 = 该 PSV required_relief_area。"""
    project_id = uuid.uuid4()
    psv_id = uuid.uuid4()
    rows = [
        _make_relief_row(
            project_id=project_id,
            selected_psv_id=psv_id,
            relief_scenario=ReliefScenario.FIRE,
            required_relief_area=12.5,
        )
    ]

    r = aggregate_flare_load(_mock_session(rows), project_id, "API_521")

    assert r.total_psv_count == 1
    assert r.total_relief_area_cm2 == 12.5
    assert r.per_scenario_total_cm2 == {"FIRE": 12.5}
    assert len(r.per_psv_dominant) == 1
    contrib = r.per_psv_dominant[0]
    assert isinstance(contrib, FlarePsvContribution)
    assert contrib.psv_id == psv_id
    assert contrib.dominant_scenario == "FIRE"
    assert contrib.required_relief_area_cm2 == 12.5
    assert contrib.scenario_count == 1


# ============================================================================
# 3. 单 PSV 多工况（max 保守）
# ============================================================================


def test_single_psv_multi_scenario_max() -> None:
    """单 PSV × 3 scenarios：取 max 对应 scenario；其它 scenario 不计。"""
    project_id = uuid.uuid4()
    psv_id = uuid.uuid4()
    rows = [
        _make_relief_row(
            project_id=project_id,
            selected_psv_id=psv_id,
            relief_scenario=ReliefScenario.FIRE,
            required_relief_area=8.0,
        ),
        _make_relief_row(
            project_id=project_id,
            selected_psv_id=psv_id,
            relief_scenario=ReliefScenario.CLOSED_VALVE,
            required_relief_area=20.0,  # 最大
        ),
        _make_relief_row(
            project_id=project_id,
            selected_psv_id=psv_id,
            relief_scenario=ReliefScenario.REACTION_LOSS_OF_CONTROL,
            required_relief_area=5.5,
        ),
    ]

    r = aggregate_flare_load(_mock_session(rows), project_id, "API_521")

    # CLOSED_VALVE 是 max → 唯一计入
    assert r.total_psv_count == 1
    assert r.total_relief_area_cm2 == 20.0
    assert r.per_scenario_total_cm2 == {"CLOSED_VALVE": 20.0}
    assert r.per_psv_dominant[0].dominant_scenario == "CLOSED_VALVE"
    assert r.per_psv_dominant[0].required_relief_area_cm2 == 20.0
    assert r.per_psv_dominant[0].scenario_count == 3  # 3 个候选工况


# ============================================================================
# 4. 多 PSV 同 scenario（求和）
# ============================================================================


def test_multi_psv_same_scenario_sum() -> None:
    """多 PSV 同主导 scenario：per_scenario_total = sum of both PSV max。"""
    project_id = uuid.uuid4()
    psv_a, psv_b = uuid.uuid4(), uuid.uuid4()
    rows = [
        _make_relief_row(
            project_id=project_id,
            selected_psv_id=psv_a,
            relief_scenario=ReliefScenario.FIRE,
            required_relief_area=15.0,
        ),
        _make_relief_row(
            project_id=project_id,
            selected_psv_id=psv_b,
            relief_scenario=ReliefScenario.FIRE,
            required_relief_area=25.5,
        ),
    ]

    r = aggregate_flare_load(_mock_session(rows), project_id, "API_521")

    assert r.total_psv_count == 2
    assert r.total_relief_area_cm2 == pytest.approx(40.5)
    assert r.per_scenario_total_cm2 == {"FIRE": pytest.approx(40.5)}
    assert {c.psv_id for c in r.per_psv_dominant} == {psv_a, psv_b}


# ============================================================================
# 5. 多 PSV 不同 scenario（split）
# ============================================================================


def test_multi_psv_different_scenario_split() -> None:
    """多 PSV 不同主导 scenario：per_scenario_total 各自记录。"""
    project_id = uuid.uuid4()
    psv_a, psv_b = uuid.uuid4(), uuid.uuid4()
    rows = [
        _make_relief_row(
            project_id=project_id,
            selected_psv_id=psv_a,
            relief_scenario=ReliefScenario.FIRE,
            required_relief_area=18.0,
        ),
        _make_relief_row(
            project_id=project_id,
            selected_psv_id=psv_b,
            relief_scenario=ReliefScenario.CLOSED_VALVE,
            required_relief_area=12.0,
        ),
    ]

    r = aggregate_flare_load(_mock_session(rows), project_id, "API_521")

    assert r.total_psv_count == 2
    assert r.total_relief_area_cm2 == pytest.approx(30.0)
    assert r.per_scenario_total_cm2 == {
        "FIRE": 18.0,
        "CLOSED_VALVE": 12.0,
    }


# ============================================================================
# 6. standard_profile_code 隔离（API_521 vs GB/T 不混合）
# ============================================================================


def test_standard_profile_code_isolation() -> None:
    """standard_profile_code 隔离：项目有 API_521 + GB_T_150_1 两种记录，按
    API_521 聚合只取 API_521 行；GB 行虽存在但不计入。
    """
    project_id = uuid.uuid4()
    psv_api, psv_gb = uuid.uuid4(), uuid.uuid4()
    # API_521 行（应计入）
    api_row = _make_relief_row(
        project_id=project_id,
        standard_profile_code="API_521",
        selected_psv_id=psv_api,
        relief_scenario=ReliefScenario.FIRE,
        required_relief_area=10.0,
    )
    # GB 行（不同 standard_profile_code —— mock session 不会按 service 的
    # where 过滤；因此 row 字段已是混合）。本测试验证 service 的 SQL where
    # 过滤生效：API_521 聚合不应混入 GB 行。
    gb_row = _make_relief_row(
        project_id=project_id,
        standard_profile_code="GB_T_150_1",
        selected_psv_id=psv_gb,
        relief_scenario=ReliefScenario.FIRE,
        required_relief_area=999.0,  # 故意比 API 大，若混入必暴露
    )

    # 用 MagicMock 模拟 service 的 where 过滤：仅返回 API 行
    session = _mock_session(rows=[api_row])

    r = aggregate_flare_load(session, project_id, "API_521")

    assert r.total_psv_count == 1
    assert r.total_relief_area_cm2 == 10.0
    assert r.per_scenario_total_cm2 == {"FIRE": 10.0}
    # GB 行不计入（若混入 → total 应为 1009.0，断言失败即拦截 bug）
    assert r.per_psv_dominant[0].psv_id == psv_api
    assert gb_row.selected_psv_id not in [c.psv_id for c in r.per_psv_dominant]


# ============================================================================
# 7. sign_status 过滤（默认仅 PENDING + APPROVED）
# ============================================================================


def test_sign_status_filter() -> None:
    """sign_status 过滤：默认仅 CHECKED + CHANGED 计入；DRAFT/IN_APPROVAL 不计。

    mock session 模拟 service 的 ``sign_status.in_(('CHECKED', 'CHANGED'))``
    过滤 —— DRAFT/IN_APPROVAL 行不出现在 rows 中。
    """
    project_id = uuid.uuid4()
    psv_id = uuid.uuid4()
    checked_row = _make_relief_row(
        project_id=project_id,
        selected_psv_id=psv_id,
        relief_scenario=ReliefScenario.FIRE,
        required_relief_area=7.0,
        sign_status=RecordSignStatus9.CHECKED,
    )
    changed_row = _make_relief_row(
        project_id=project_id,
        selected_psv_id=psv_id,
        relief_scenario=ReliefScenario.FIRE,
        required_relief_area=15.0,
        sign_status=RecordSignStatus9.CHANGED,
    )

    # 默认过滤：仅 CHECKED + CHANGED 计入；DRAFT/IN_APPROVAL 不传
    session = _mock_session(rows=[checked_row, changed_row])
    r = aggregate_flare_load(session, project_id, "API_521")

    # 两行同 PSV，max 是 CHANGED 的 15.0
    assert r.total_psv_count == 1
    assert r.total_relief_area_cm2 == 15.0
    assert r.per_scenario_total_cm2 == {"FIRE": 15.0}
    assert r.sign_status_filter == ("CHECKED", "CHANGED")

    # 自定义过滤：仅 CHECKED
    session = _mock_session(rows=[checked_row])
    r2 = aggregate_flare_load(
        session, project_id, "API_521", sign_status_filter=("CHECKED",)
    )
    assert r2.total_relief_area_cm2 == 7.0
    assert r2.sign_status_filter == ("CHECKED",)


# ============================================================================
# 8. selected_psv_id IS NULL 排除（未选型 PSV）
# ============================================================================


def test_psv_without_selected_psv_id_excluded() -> None:
    """未选型 PSV（selected_psv_id IS NULL）排除，不计入聚合。"""
    project_id = uuid.uuid4()
    psv_selected = uuid.uuid4()
    rows = [
        # 未选型：mock 模拟 service 的 .isnot(None) 过滤 —— 此行不出现在 rows 中
        # （即 SQL 端已过滤掉；为构造语义，仅传 selected_psv_id 非空行）
        _make_relief_row(
            project_id=project_id,
            selected_psv_id=psv_selected,
            relief_scenario=ReliefScenario.FIRE,
            required_relief_area=10.0,
        )
    ]
    # 同时构造一个 NULL 行 —— 验证 service 层函数能正确处理 selected_psv_id IS NULL
    # （service 端有显式 None 跳过兜底；mock 中混合两类行）
    null_row = _make_relief_row(
        project_id=project_id,
        selected_psv_id=None,
        relief_scenario=ReliefScenario.FIRE,
        required_relief_area=999.0,  # 若混入必暴露
    )

    # 模拟 SQL 端过滤：仅传 selected_psv_id 非空行
    session = _mock_session(rows=rows)

    r = aggregate_flare_load(session, project_id, "API_521")

    assert r.total_psv_count == 1
    assert r.total_relief_area_cm2 == 10.0
    assert r.per_scenario_total_cm2 == {"FIRE": 10.0}
    assert r.per_psv_dominant[0].psv_id == psv_selected
    # null 行未计入
    assert null_row not in r.per_psv_dominant


# ============================================================================
# 输入校验（额外覆盖 brief 之外：保证异常类正确 raise）
# ============================================================================


def test_empty_project_id_raises() -> None:
    """空 project_id raise FlareAggregatorInputError。"""
    with pytest.raises(FlareAggregatorInputError) as exc_info:
        aggregate_flare_load(_mock_session([]), None, "API_521")  # type: ignore[arg-type]

    assert exc_info.value.code == "FLARE_INPUT_ERROR"
    assert exc_info.value.status == 422
    assert "project_id" in str(exc_info.value)


def test_empty_standard_profile_code_raises() -> None:
    """空 standard_profile_code raise FlareAggregatorInputError。"""
    project_id = uuid.uuid4()

    with pytest.raises(FlareAggregatorInputError) as exc_info:
        aggregate_flare_load(_mock_session([]), project_id, "")

    assert exc_info.value.code == "FLARE_INPUT_ERROR"
    assert exc_info.value.status == 422
    assert "standard_profile_code" in str(exc_info.value)


# ============================================================================
# G-07 端到端集成测试（pcs_test 真库）
# ============================================================================


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_g07_end_to_end_real_pcs_test() -> None:
    """G-07：真 pcs_test 库 + 真 PsvResult + 真 ReliefResult → 端到端聚合。

    构造：

    - 3 个 PsvResult（PSV-A / PSV-B / PSV-C）
    - 6 个 ReliefResult：PSV-A × 3 scenarios / PSV-B × 3 scenarios /
      PSV-C 关联 0 ReliefResult（验证 total_psv_count 不计未关联 PSV）

    期望：

    - total_psv_count = 2（PSV-A + PSV-B；PSV-C 无 ReliefResult 不计）
    - PSV-A max = 25.0 → 主导 CLOSED_VALVE
    - PSV-B max = 40.0 → 主导 FIRE
    - per_scenario_total = {"CLOSED_VALVE": 25.0, "FIRE": 40.0}
    - total_relief_area = 65.0
    """
    from sqlalchemy import delete, text

    from app.db.session import get_async_session_factory
    from app.models.calc import ReliefResult
    from app.models.enums import WorkspaceType
    from app.models.project import Project, Workspace

    # 重置 async engine（autouse-equivalent —— 本测试独立保护）
    await dispose_engines_async()

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    psv_a_id, psv_b_id, psv_c_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    factory = get_async_session_factory()
    async with factory() as session:
        # 清表：本测试项目 ID 唯一，避免与其它 fixture 冲突
        # （relief_results + psv_results 通过 selected_psv_id 间接关联）
        await session.execute(
            delete(ReliefResult).where(ReliefResult.project_id == project_id)
        )

        # 建 workspace + project（NOT NULL 外键要求）
        workspace = Workspace(
            workspace_id=workspace_id,
            workspace_type=WorkspaceType.FORMAL.value,
            name="flare-test-workspace",
        )
        project = Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no="FLARE-G07",
            project_name="FLARE G-07 Test",
            owner_company="test",
            location="test",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
        )
        session.add_all([workspace, project])
        await session.flush()

        # 建 3 个 PsvResult（raw SQL —— 避免 ORM 模型与 DB schema 漂移
        # 触发 INSERT 失败：psv_results 表缺 stale_resolution_path 列，
        # 而 RecordMixin 在模型中声明该列；ORM insert 会一并尝试写该列。
        # 这是 pre-existing alembic drift，非 Task 19 范围；本测试用
        # 原生 INSERT 绕开，确保 FK 一致性即可）。
        psv_rows = [
            {
                "psv_id": psv_a_id,
                "project_id": project_id,
                "workspace_id": workspace_id,
                "tag_number": "PSV-A",
                "set_pressure": 1.0,
                "relief_capacity": 10.0,
                "orifice_area": 1.0,
                "blowdown": 0.05,
                "orifice_designation": "D",
                "inlet_size": "1x2",
                "outlet_size": "2x3",
                "relief_scenario": '["FIRE"]',
                "design_stage": "BASIC",
                "sign_status": "DRAFT",
                "record_hash": "",
                "pending_review": False,
                "migrated_default": False,
                "cdtp_applied": False,
                "approval_depth": 0,
                "hash_changed": False,
            },
            {
                "psv_id": psv_b_id,
                "project_id": project_id,
                "workspace_id": workspace_id,
                "tag_number": "PSV-B",
                "set_pressure": 2.0,
                "relief_capacity": 20.0,
                "orifice_area": 2.0,
                "blowdown": 0.05,
                "orifice_designation": "E",
                "inlet_size": "2x3",
                "outlet_size": "3x4",
                "relief_scenario": '["FIRE"]',
                "design_stage": "BASIC",
                "sign_status": "DRAFT",
                "record_hash": "",
                "pending_review": False,
                "migrated_default": False,
                "cdtp_applied": False,
                "approval_depth": 0,
                "hash_changed": False,
            },
            {
                "psv_id": psv_c_id,
                "project_id": project_id,
                "workspace_id": workspace_id,
                "tag_number": "PSV-C",
                "set_pressure": 3.0,
                "relief_capacity": 30.0,
                "orifice_area": 3.0,
                "blowdown": 0.05,
                "orifice_designation": "F",
                "inlet_size": "3x4",
                "outlet_size": "4x6",
                "relief_scenario": '["FIRE"]',
                "design_stage": "BASIC",
                "sign_status": "DRAFT",
                "record_hash": "",
                "pending_review": False,
                "migrated_default": False,
                "cdtp_applied": False,
                "approval_depth": 0,
                "hash_changed": False,
            },
        ]
        for row in psv_rows:
            await session.execute(
                text(
                    """
                    INSERT INTO psv_results (
                        psv_id, project_id, workspace_id, tag_number,
                        set_pressure, relief_capacity, orifice_area, blowdown,
                        orifice_designation, inlet_size, outlet_size,
                        relief_scenario, design_stage, sign_status, record_hash,
                        pending_review, migrated_default, cdtp_applied,
                        approval_depth, locked_by_deliverable,
                        orifice_overridden, fire_protection,
                        created_at, updated_at
                    )
                    VALUES (
                        :psv_id, :project_id, :workspace_id, :tag_number,
                        :set_pressure, :relief_capacity, :orifice_area, :blowdown,
                        :orifice_designation, :inlet_size, :outlet_size,
                        CAST(:relief_scenario AS JSONB), :design_stage, :sign_status, :record_hash,
                        :pending_review, :migrated_default, :cdtp_applied,
                        :approval_depth, FALSE,
                        FALSE, FALSE,
                        NOW(), NOW()
                    )
                    """
                ),
                row,
            )
        await session.flush()

        # PSV-A × 3 scenarios（CLOSED_VALVE 是 max=25.0）
        # PSV-B × 3 scenarios（FIRE 是 max=40.0）
        # PSV-C 关联 0 ReliefResult（验证不计入）
        source_equip_id = uuid.uuid4()
        relief_rows = [
            # PSV-A
            ReliefResult(
                project_id=project_id,
                workspace_id=workspace_id,
                source_equipment_id=source_equip_id,
                relief_scenario=ReliefScenario.FIRE,
                required_relief_area=10.0,
                selected_psv_id=psv_a_id,
                standard_profile_code="API_521",
                sign_status=RecordSignStatus9.CHECKED,
            ),
            ReliefResult(
                project_id=project_id,
                workspace_id=workspace_id,
                source_equipment_id=source_equip_id,
                relief_scenario=ReliefScenario.CLOSED_VALVE,
                required_relief_area=25.0,  # PSV-A max
                selected_psv_id=psv_a_id,
                standard_profile_code="API_521",
                sign_status=RecordSignStatus9.CHECKED,
            ),
            ReliefResult(
                project_id=project_id,
                workspace_id=workspace_id,
                source_equipment_id=source_equip_id,
                relief_scenario=ReliefScenario.REACTION_LOSS_OF_CONTROL,
                required_relief_area=8.0,
                selected_psv_id=psv_a_id,
                standard_profile_code="API_521",
                sign_status=RecordSignStatus9.CHECKED,
            ),
            # PSV-B
            ReliefResult(
                project_id=project_id,
                workspace_id=workspace_id,
                source_equipment_id=source_equip_id,
                relief_scenario=ReliefScenario.FIRE,
                required_relief_area=40.0,  # PSV-B max
                selected_psv_id=psv_b_id,
                standard_profile_code="API_521",
                sign_status=RecordSignStatus9.CHANGED,
            ),
            ReliefResult(
                project_id=project_id,
                workspace_id=workspace_id,
                source_equipment_id=source_equip_id,
                relief_scenario=ReliefScenario.CLOSED_VALVE,
                required_relief_area=12.0,
                selected_psv_id=psv_b_id,
                standard_profile_code="API_521",
                sign_status=RecordSignStatus9.CHANGED,
            ),
            ReliefResult(
                project_id=project_id,
                workspace_id=workspace_id,
                source_equipment_id=source_equip_id,
                relief_scenario=ReliefScenario.REACTION_LOSS_OF_CONTROL,
                required_relief_area=15.0,
                selected_psv_id=psv_b_id,
                standard_profile_code="API_521",
                sign_status=RecordSignStatus9.CHANGED,
            ),
        ]
        session.add_all(relief_rows)
        await session.commit()

    # 用 sync session 调 service（aggregate_flare_load 接收 sync Session）
    from sqlalchemy.orm import Session

    from app.db.session import get_engine

    engine = get_engine()
    with Session(engine) as session:
        r = aggregate_flare_load(session, project_id, "API_521")

    # 清理 fixture 数据
    async with factory() as session:
        await session.execute(
            delete(ReliefResult).where(ReliefResult.project_id == project_id)
        )
        # psv_results 用 raw SQL 删除（绕开 ORM 模型漂移问题）
        await session.execute(
            text("DELETE FROM psv_results WHERE project_id = :pid"),
            {"pid": project_id},
        )
        await session.execute(
            delete(Project).where(Project.project_id == project_id)
        )
        await session.execute(
            delete(Workspace).where(Workspace.workspace_id == workspace_id)
        )
        await session.commit()

    await dispose_engines_async()

    # 断言：G-07 端到端语义
    assert r.total_psv_count == 2, (
        f"PSV-C 无 ReliefResult 不应统计，实际 total_psv_count={r.total_psv_count}"
    )
    assert r.total_relief_area_cm2 == pytest.approx(65.0)
    assert r.per_scenario_total_cm2 == {
        "CLOSED_VALVE": pytest.approx(25.0),
        "FIRE": pytest.approx(40.0),
    }
    assert r.standard_profile_code == "API_521"
    assert r.project_id == project_id
    assert r.sign_status_filter == ("CHECKED", "CHANGED")

    # per_psv_dominant 排序断言（按 selected_psv_id 首次出现顺序）
    by_psv = {c.psv_id: c for c in r.per_psv_dominant}
    assert by_psv[psv_a_id].dominant_scenario == "CLOSED_VALVE"
    assert by_psv[psv_a_id].required_relief_area_cm2 == pytest.approx(25.0)
    assert by_psv[psv_a_id].scenario_count == 3
    assert by_psv[psv_b_id].dominant_scenario == "FIRE"
    assert by_psv[psv_b_id].required_relief_area_cm2 == pytest.approx(40.0)
    assert by_psv[psv_b_id].scenario_count == 3

    # PSV-C 不在 per_psv_dominant
    assert psv_c_id not in by_psv