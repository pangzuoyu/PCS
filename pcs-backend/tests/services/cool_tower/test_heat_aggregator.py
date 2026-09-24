"""P6-2 Task 25 COOL_TOWER heat_aggregator 测试（§3.2.4.5）。

按 SPEC §3.2.4.5：从 ``heat_results`` 表按 project_id +
exchanger_categories 汇总 duty → H kW。

设计要点：
- 单元测试用 Mock session 隔离（避免外部 DB 耦合）；覆盖两类别 /
  过滤 AIR_COOL / sign_status filter / 空项目 / formula_ref /
  InputError isinstance PcsError。
- G-07 真库测试走 aggregate_heat_duty 真 session（pcs_test；守卫同
  tests/services/flare/test_relief_aggregator._ONLY_PCS_TEST）。
- **Do-Not-Repeat**：HeatResult（继承 TaggedRecordMixin）:
  exchanger_category String(30) + duty Float（ADR-0027 V1.0 双轨
  扩展）；fixture pattern = 直接 ORM 构造（G-07 路径走真 DB）。
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
from app.services.cool_tower import (  # noqa: E402
    HeatAggregatorInput,
    HeatAggregatorInputError,
    aggregate_heat_duty,
)
from app.services.exceptions import PcsError  # noqa: E402

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
# Helpers（Mock session + 构造 GROUP BY 结果）
# ============================================================================


def _mock_session_groupby(
    rows: list[tuple[Any, Any, Any]] | None = None,
) -> MagicMock:
    """构造 mock session，``await session.execute(...)`` 返回 rows 列表。

    heat_aggregator 走 SQL GROUP BY → 返回 list[(exchanger_category,
    sum_duty, cnt)] 三元组；不走 scalars（避免 enum select 限制）。
    """
    session = MagicMock()
    execute_result = MagicMock()
    execute_result.all.return_value = rows or []
    # session.execute 必须 awaitable → AsyncMock
    session.execute = AsyncMock(return_value=execute_result)
    return session


def _build_session_with_categories(
    categories: list[tuple[str, float]],
    sign_status: RecordSignStatus9 = RecordSignStatus9.DRAFT,
) -> MagicMock:
    """构造 mock session，模拟 GROUP BY 输出（每个 category 一行 sum）。"""
    rows: list[tuple[Any, Any, Any]] = [
        (cat, duty, 1) for cat, duty in categories
    ]
    return _mock_session_groupby(rows=rows)


# ============================================================================
# 1. basic_two_categories — 2 HeatResult (SHELL_TUBE + PLATE) → 求和
# ============================================================================


@pytest.mark.asyncio
async def test_heat_aggregator_basic_two_categories() -> None:
    """SHELL_TUBE 1000 + PLATE 500 → h_aggregate_kw = 1500.0。"""
    session = _build_session_with_categories(
        [("SHELL_TUBE", 1000.0), ("PLATE", 500.0)]
    )
    r = await aggregate_heat_duty(
        HeatAggregatorInput(
            session=session,
            project_id=uuid.uuid4(),
        )
    )
    assert r.h_aggregate_kw == pytest.approx(1500.0)
    assert r.heat_record_count == 2
    assert r.per_exchanger_category == {
        "SHELL_TUBE": pytest.approx(1000.0),
        "PLATE": pytest.approx(500.0),
    }
    assert r.formula_ref == "API_521_§3.2.4.5"


# ============================================================================
# 2. excludes_air_cool — 过滤列表不含 AIR_COOL
# ============================================================================


@pytest.mark.asyncio
async def test_heat_aggregator_excludes_air_cool() -> None:
    """exchanger_categories_filter 默认 ('SHELL_TUBE', 'PLATE') →
    AIR_COOL 被过滤（不出现在结果）。

    本测试通过 mock session 模拟只命中 SHELL_TUBE（air_cool 行在 SQL 层
    被过滤掉）— 验证 service 层不假定 AIR_COOL 会出现在结果中。
    """
    session = _build_session_with_categories([("SHELL_TUBE", 800.0)])
    r = await aggregate_heat_duty(
        HeatAggregatorInput(
            session=session,
            project_id=uuid.uuid4(),
            exchanger_categories_filter=("SHELL_TUBE", "PLATE"),
        )
    )
    assert r.h_aggregate_kw == pytest.approx(800.0)
    assert "AIR_COOL" not in r.per_exchanger_category


# ============================================================================
# 3. sign_status_filter — 仅 DRAFT/CHECKED 计入；OBSOLETE 被过滤
# ============================================================================


@pytest.mark.asyncio
async def test_heat_aggregator_sign_status_filter() -> None:
    """默认 sign_status_filter=(DRAFT, CHECKED)；OBSOLETE 在 SQL 层被过滤。

    验证：通过 mock session 模拟只命中 DRAFT（OBSOLETE 被过滤掉），
    service 层不假定 OBSOLETE 会出现在结果中。
    """
    session = _build_session_with_categories([("SHELL_TUBE", 750.0)])
    r = await aggregate_heat_duty(
        HeatAggregatorInput(
            session=session,
            project_id=uuid.uuid4(),
            sign_status_filter=(RecordSignStatus9.DRAFT,),
        )
    )
    assert r.h_aggregate_kw == pytest.approx(750.0)
    # sign_status_filter 透传
    assert r.per_exchanger_category == {"SHELL_TUBE": pytest.approx(750.0)}


# ============================================================================
# 4. empty_project — project_id 无 HeatResult → 0 / 0 / {}
# ============================================================================


@pytest.mark.asyncio
async def test_heat_aggregator_empty_project() -> None:
    """空项目 → h_aggregate_kw=0 / heat_record_count=0 / per_exchanger_category={}。"""
    session = _mock_session_groupby(rows=[])
    r = await aggregate_heat_duty(
        HeatAggregatorInput(
            session=session,
            project_id=uuid.uuid4(),
        )
    )
    assert r.h_aggregate_kw == 0.0
    assert r.heat_record_count == 0
    assert r.per_exchanger_category == {}


# ============================================================================
# 5. formula_ref — 恒等 "API_521_§3.2.4.5"
# ============================================================================


@pytest.mark.asyncio
async def test_heat_aggregator_formula_ref() -> None:
    """formula_ref 恒等 "API_521_§3.2.4.5"（§3.2.4.5 章节号精确匹配）。"""
    session = _mock_session_groupby(rows=[])
    r = await aggregate_heat_duty(
        HeatAggregatorInput(
            session=session,
            project_id=uuid.uuid4(),
        )
    )
    assert r.formula_ref == "API_521_§3.2.4.5"


# ============================================================================
# 6. InputError — isinstance PcsError + 非法 filter 校验
# ============================================================================


@pytest.mark.asyncio
async def test_heat_aggregator_input_error_is_pcs_error() -> None:
    """AirCool in filter → HeatAggregatorInputError 且 isinstance PcsError。"""
    session = _mock_session_groupby(rows=[])
    with pytest.raises(HeatAggregatorInputError) as exc_info:
        await aggregate_heat_duty(
            HeatAggregatorInput(
                session=session,
                project_id=uuid.uuid4(),
                exchanger_categories_filter=("AIR_COOL",),
            )
        )
    assert "AIR_COOL" in str(exc_info.value)
    assert isinstance(exc_info.value, PcsError)
    assert exc_info.value.code == "HEAT_AGGREGATOR_INPUT_ERROR"
    assert exc_info.value.status == 422


# ============================================================================
# G-07 真库测试：3 HeatResult（1 SHELL_TUBE + 1 PLATE + 1 AIR_COOL）
# → h_aggregate_kw = sum(2 water_cooled)，AIR_COOL 被过滤
# ============================================================================


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_heat_aggregator_g07_real_pcs_test() -> None:
    """G-07：真 pcs_test 库 + aggregate_heat_duty 端到端。

    构造：

    - 1 个 workspace + 1 个 project（FK 必填）
    - 直接 ORM 插 3 条 HeatResult（1 SHELL_TUBE + 1 PLATE + 1 AIR_COOL）
    - aggregate_heat_duty → 期望 h_aggregate_kw = sum(2 water_cooled)，
      AIR_COOL 被 SQL 层过滤

    期望：

    - 命中行数 = 2（AIR_COOL 被排除）
    - h_aggregate_kw = duty_SHELL_TUBE + duty_PLATE
    - per_exchanger_category = {"SHELL_TUBE": ..., "PLATE": ...}
    """
    from sqlalchemy import delete

    from app.db.session import get_async_session_factory
    from app.models.calc import HeatResult
    from app.models.enums import WorkspaceType
    from app.models.project import Project, Workspace

    await dispose_engines_async()

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    duty_shell = 1000.0
    duty_plate = 500.0
    duty_air = 800.0  # 应被过滤

    factory = get_async_session_factory()
    async with factory() as session:
        # 1. 清表（本测试项目 ID 唯一）
        await session.execute(
            delete(HeatResult).where(HeatResult.project_id == project_id)
        )
        # 2. 建 workspace + project（FK 必填）
        workspace = Workspace(
            workspace_id=workspace_id,
            workspace_type=WorkspaceType.FORMAL.value,
            name="heat-aggregator-test-workspace",
        )
        project = Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"HEAT-AGG-{uuid.uuid4().hex[:8]}",
            project_name="HEAT AGG G-07 Test",
            owner_company="test",
            location="test",
            project_type="test",
            design_phase="BASIC",
            unit_system="SI",
        )
        session.add_all([workspace, project])
        await session.commit()

    # 3. 插 3 条 HeatResult（直接 ORM 构造；不依赖 service — 测试独立）
    async with factory() as session:
        hr1 = HeatResult(
            project_id=project_id,
            tag_number=f"HEAT-{uuid.uuid4().hex[:6]}",
            exchanger_category="SHELL_TUBE",
            duty=duty_shell,
            design_conditions_json={},
            input_json={},
            output_json={},
            sign_status=RecordSignStatus9.DRAFT,
        )
        hr2 = HeatResult(
            project_id=project_id,
            tag_number=f"HEAT-{uuid.uuid4().hex[:6]}",
            exchanger_category="PLATE",
            duty=duty_plate,
            design_conditions_json={},
            input_json={},
            output_json={},
            sign_status=RecordSignStatus9.DRAFT,
        )
        hr3 = HeatResult(
            project_id=project_id,
            tag_number=f"HEAT-{uuid.uuid4().hex[:6]}",
            exchanger_category="AIR_COOL",
            duty=duty_air,
            design_conditions_json={},
            input_json={},
            output_json={},
            sign_status=RecordSignStatus9.DRAFT,
        )
        session.add_all([hr1, hr2, hr3])
        await session.commit()

    # 4. aggregate_heat_duty（独立 session 读）
    async with factory() as session:
        result = await aggregate_heat_duty(
            HeatAggregatorInput(
                session=session,
                project_id=project_id,
                exchanger_categories_filter=("SHELL_TUBE", "PLATE"),
                sign_status_filter=(RecordSignStatus9.DRAFT,),
            )
        )

    # 5. 验证：AIR_COOL 被过滤；h_aggregate_kw = sum(2 water_cooled)
    expected_total = duty_shell + duty_plate
    assert result.h_aggregate_kw == pytest.approx(expected_total)
    assert result.heat_record_count == 2
    assert result.per_exchanger_category == {
        "SHELL_TUBE": pytest.approx(duty_shell),
        "PLATE": pytest.approx(duty_plate),
    }
    assert "AIR_COOL" not in result.per_exchanger_category

    # 6. 清表（GA 收尾）
    async with factory() as session:
        await session.execute(
            delete(HeatResult).where(HeatResult.project_id == project_id)
        )
        await session.commit()