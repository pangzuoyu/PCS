"""P4-0-2 SUP-008 表扩展迁移验证测试。

验证 pcs_test 库已运行 ``p4_sup008_result_fields``：

- piping_results +11 列（line_description / pipe_type / max_flow_factor /
  selected_diameter / liquid_velocity_max / gas_velocity_max /
  pressure_drop_per_100m / selected_pipe_size / recommended_pipe_size /
  check_result / velocity_range_reference）
- pump_results +5 列（selected_pump_model / selected_motor_model /
  selected_motor_power / pump_operation + design_stage(BASIC default)）
- psv_results / vessel_results +design_stage（BASIC default）
- two_phase_results 新表（13 列：PK + input/output JSONB + 业务字段 + 时间戳）
- 6 个 PG enum（pipe_type / check_result / pump_operation / design_stage /
  flow_pattern / two_phase_check）

跑前需（CLAUDE.md 测试前检查）：
    DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test \\
        uv run alembic upgrade head
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import dispose_engines_async, get_async_session_factory

# 列名 → (data_type, character_maximum_length)
_PIPING_COLS = {
    "line_description": ("character varying", 200),
    "max_flow_factor": ("double precision", None),
    "selected_diameter": ("double precision", None),
    "liquid_velocity_max": ("double precision", None),
    "gas_velocity_max": ("double precision", None),
    "pressure_drop_per_100m": ("double precision", None),
    "selected_pipe_size": ("character varying", 20),
    "recommended_pipe_size": ("character varying", 20),
    "velocity_range_reference": ("character varying", 100),
    # 2 个 enum（PG 渲染为 USER-DEFINED 类型，长度 None）
    "pipe_type": ("USER-DEFINED", None),
    "check_result": ("USER-DEFINED", None),
}

# 列名 → (data_type, character_maximum_length)
_PUMP_NEW_COLS = {
    "selected_pump_model": ("character varying", 100),
    "selected_motor_model": ("character varying", 100),
    "selected_motor_power": ("double precision", None),
    # 2 个 enum
    "pump_operation": ("USER-DEFINED", None),
    "design_stage": ("USER-DEFINED", None),
}

# two_phase_results 13 字段（含 PK + JSONB + 业务 + 时间戳）
# 注：Bx / By 是 PG 大小写敏感列（双字符全大写未自动小写）
_TWO_PHASE_COLS = {
    "two_phase_id": ("uuid", None),
    "input_json": ("jsonb", None),
    "output_json": ("jsonb", None),
    "Bx": ("double precision", None),
    "By": ("double precision", None),
    "flow_pattern": ("USER-DEFINED", None),
    "two_phase_check": ("USER-DEFINED", None),
    "liquid_velocity": ("double precision", None),
    "gas_velocity": ("double precision", None),
    "pressure_gradient": ("double precision", None),
    "void_fraction": ("double precision", None),
    "calc_method": ("character varying", 50),
    "created_at": ("timestamp with time zone", None),
}

# 6 个 enum：类型名 → 期望值集合（顺序严格）
_ENUM_VALUES = {
    "pipe_type_enum": (
        "PUMP_SUCTION",
        "PUMP_DISCHARGE",
        "SELF_FLOW",
        "HEATING_STEAM",
        "TWO_PHASE",
    ),
    "check_result_enum": ("PASS", "FAIL", "WARNING"),
    "pump_operation_enum": ("NORMAL", "STANDBY", "OFF"),
    "design_stage_enum": ("BASIC", "DETAIL"),
    "flow_pattern_enum": (
        "ANNULAR",
        "MIST",
        "BUBBLE",
        "SLUG",
        "STRATIFIED",
        "WAVE",
    ),
    "two_phase_check_enum": ("PASS", "WARNING", "FAIL"),
}

# 安全守卫：仅当 database_url 指向 pcs_test 才执行（仿 test_calc_audit_fields）
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason="迁移验证仅允许 pcs_test 库；"
           "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test",
)


@pytest_asyncio.fixture(autouse=True)
async def _reset_async_engine() -> AsyncIterator[None]:
    """每次用例 reset 全局 async engine（绑定当前 event loop）。"""
    await dispose_engines_async()
    yield
    await dispose_engines_async()


async def _fetch_column_rows(table: str, cols: tuple[str, ...]) -> list[dict]:
    factory = get_async_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                """
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_name = :t
                  AND column_name = ANY(:cols)
                """
            ),
            {"t": table, "cols": list(cols)},
        )
        return [dict(r) for r in result.mappings().all()]


# === piping_results 11 列 ===

@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_piping_eleven_columns_exist() -> None:
    """piping_results 11 新列均存在且可空。"""
    rows = await _fetch_column_rows("piping_results", tuple(_PIPING_COLS))
    got = {r["column_name"]: r["is_nullable"] for r in rows}
    assert got == {c: "YES" for c in _PIPING_COLS}, f"piping_results: {got}"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_piping_column_types() -> None:
    """piping_results 11 新列类型断言。"""
    rows = await _fetch_column_rows("piping_results", tuple(_PIPING_COLS))
    got = {
        r["column_name"]: (r["data_type"], r["character_maximum_length"])
        for r in rows
    }
    assert got == _PIPING_COLS, f"piping_results: {got}"


# === pump_results 5 列 ===

@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_pump_five_columns_exist() -> None:
    """pump_results 5 新列：4 列 nullable + design_stage NOT NULL default BASIC。"""
    rows = await _fetch_column_rows("pump_results", tuple(_PUMP_NEW_COLS))
    got = {r["column_name"]: r["is_nullable"] for r in rows}
    # design_stage NOT NULL；其余可空
    expected_nullable = dict.fromkeys(_PUMP_NEW_COLS, "YES")
    expected_nullable["design_stage"] = "NO"
    assert got == expected_nullable, f"pump_results: {got}"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_pump_column_types() -> None:
    """pump_results 5 新列类型断言。"""
    rows = await _fetch_column_rows("pump_results", tuple(_PUMP_NEW_COLS))
    got = {
        r["column_name"]: (r["data_type"], r["character_maximum_length"])
        for r in rows
    }
    assert got == _PUMP_NEW_COLS, f"pump_results: {got}"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_pump_design_stage_server_default_basic() -> None:
    """pump_results.design_stage server_default = 'BASIC'::design_stage_enum。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT column_default
                    FROM information_schema.columns
                    WHERE table_name = 'pump_results'
                      AND column_name = 'design_stage'
                    """
                )
            )
        ).mappings().one()
    default = (row["column_default"] or "").lower()
    assert "basic" in default, f"pump_results.design_stage default={default!r}"


# === psv_results / vessel_results design_stage ===

@_ONLY_PCS_TEST
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "table", ["psv_results", "vessel_results", "column_sizing_results"]
)
async def test_design_stage_column_exists_not_null(table: str) -> None:
    """psv_results / vessel_results / column_sizing_results 设计阶段列存在 + NOT NULL。

    SUP-008 §8.4 OPEN-009 VESSEL/PSV/COLUMN 三表必须 design_stage NOT NULL；
    column_sizing_results 由 P5-OPEN-005（V1.3）落地，前两表由 P4-0-2 落地。
    """
    rows = await _fetch_column_rows(table, ("design_stage",))
    assert rows and rows[0]["is_nullable"] == "NO", f"{table}: {rows}"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "table", ["psv_results", "vessel_results", "column_sizing_results"]
)
async def test_design_stage_server_default_basic(table: str) -> None:
    """psv_results / vessel_results / column_sizing_results 设计阶段 server_default = 'BASIC'。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT column_default
                    FROM information_schema.columns
                    WHERE table_name = :t
                      AND column_name = 'design_stage'
                    """
                ),
                {"t": table},
            )
        ).mappings().one()
    default = (row["column_default"] or "").lower()
    assert "basic" in default, f"{table}.design_stage default={default!r}"


# === two_phase_results 新表 ===

@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_two_phase_results_table_exists() -> None:
    """two_phase_results 表在 information_schema.tables 中存在。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_name = 'two_phase_results'
                      AND table_schema = 'public'
                    """
                )
            )
        ).mappings().one_or_none()
    assert row is not None, "two_phase_results 表不存在"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_two_phase_results_thirteen_columns() -> None:
    """two_phase_results 13 字段存在性 + 类型断言。"""
    rows = await _fetch_column_rows("two_phase_results", tuple(_TWO_PHASE_COLS))
    got = {
        r["column_name"]: (r["data_type"], r["character_maximum_length"])
        for r in rows
    }
    assert got == _TWO_PHASE_COLS, f"two_phase_results: {got}"


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_two_phase_results_pk_is_uuid() -> None:
    """two_phase_id 是 uuid 类型 PK。"""
    factory = get_async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_name = 'two_phase_results'
                      AND column_name = 'two_phase_id'
                    """
                )
            )
        ).mappings().one()
    assert row["data_type"] == "uuid", f"PK type={row['data_type']!r}"


# === 6 个 PG enum 值域 ===

@_ONLY_PCS_TEST
@pytest.mark.asyncio
@pytest.mark.parametrize("type_name,expected", list(_ENUM_VALUES.items()))
async def test_enum_values(type_name: str, expected: tuple[str, ...]) -> None:
    """6 个 enum 存在 + 值集合完全等于预期（顺序严格）。"""
    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT enumlabel
                    FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    WHERE t.typname = :name
                    ORDER BY e.enumsortorder
                    """
                ),
                {"name": type_name},
            )
        ).scalars().all()
    assert tuple(rows) == expected, (
        f"{type_name}: expected={expected!r}, got={tuple(rows)!r}"
    )


# === two_phase_results 落库 roundtrip（P4-2-4） ===

# 用于落库的 TwoPhaseInput 构造（golden horizontal_air_water）
_TWO_PHASE_INPUT_DICT: dict = {
    "liquid_mass_flow": 1.0,
    "gas_mass_flow": 0.05,
    "liquid_density": 1000.0,
    "gas_density": 1.2,
    "liquid_viscosity": 1.0e-3,
    "gas_viscosity": 1.8e-5,
    "surface_tension": 0.072,
    "pipe_diameter_m": 0.05,
    "pipe_roughness_m": 4.5e-5,
    "inclination_deg": 0.0,
    "L_m": 10.0,
    "P1_pa": 200000.0,
}


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_two_phase_results_persist_roundtrip_all_columns() -> None:
    """P4-2-4：calc → persist_two_phase_result → SELECT 验证 13 字段全部对齐。

    覆盖：input/output JSONB + Bx/By + flow_pattern/two_phase_check enum +
    liquid_velocity/gas_velocity/pressure_gradient/void_fraction + calc_method +
    created_at。
    """
    # 延迟导入：测试模块位于 pcs-backend，service 包结构稳定
    from app.services.pipe.two_phase_persist import persist_two_phase_result
    from app.services.pipe.two_phase_service import (
        TwoPhaseInput,
        calc_two_phase,
    )

    inp = TwoPhaseInput(**_TWO_PHASE_INPUT_DICT)
    res = calc_two_phase(inp)

    factory = get_async_session_factory()
    async with factory() as session:
        row = await persist_two_phase_result(session, inp, res)
        await session.commit()
        pk = row.two_phase_id

    # SELECT 全部字段验证
    # 注：Bx / By 是 PG 大小写敏感列（双字符全大写未自动小写），必须双引号引用
    async with factory() as session:
        result = await session.execute(
            text(
                """
                SELECT two_phase_id, input_json, output_json, "Bx", "By",
                       flow_pattern, two_phase_check,
                       liquid_velocity, gas_velocity, pressure_gradient,
                       void_fraction, calc_method, created_at
                FROM two_phase_results
                WHERE two_phase_id = :pk
                """
            ),
            {"pk": str(pk)},
        )
        record = result.mappings().one()
    got = dict(record)

    # PK + created_at
    assert got["two_phase_id"] == pk
    assert got["created_at"] is not None

    # 数值字段
    assert got["Bx"] is not None and abs(float(got["Bx"]) - res.Bx) < 1e-9
    assert got["By"] is not None and abs(float(got["By"]) - res.By) < 1e-9
    assert abs(float(got["liquid_velocity"]) - res.liquid_velocity) < 1e-9
    assert abs(float(got["gas_velocity"]) - res.gas_velocity) < 1e-9
    assert abs(float(got["pressure_gradient"]) - res.pressure_gradient) < 1e-9
    assert abs(float(got["void_fraction"]) - res.void_fraction) < 1e-6

    # PG enum 字段（直接传字符串；读回也是字符串）
    assert got["flow_pattern"] == res.flow_pattern
    assert got["two_phase_check"] == res.two_phase_check

    # String 字段
    assert got["calc_method"] == res.calc_method

    # JSONB 透传
    assert got["input_json"]["pipe_diameter_m"] == inp.pipe_diameter_m
    assert got["input_json"]["liquid_mass_flow"] == inp.liquid_mass_flow
    assert got["output_json"]["Bx"] == res.Bx
    assert got["output_json"]["flow_pattern"] == res.flow_pattern


# === piping_results 落库 roundtrip（P4-2-5：链式管道） ===

_CHAIN_INPUT_DICT: dict = {
    "project_id": None,  # 由 case 注入
    "workspace_id": None,
    "source_stream_id": None,
    "tag_number": "P-CHAIN-RT-001",
    "inlet_pressure_pa": 200000.0,
    "inlet_temperature_K": 298.15,
    "parallel_branches": 1,
    "segments": [
        {
            "fluid_phase": "LIQUID",
            "mass_flow_kg_s": 1.0,
            "density_kg_m3": 1000.0,
            "viscosity_pa_s": 1.0e-3,
            "pipe_diameter_m": 0.05,
            "pipe_roughness_m": 4.6e-5,
            "length_m": 10.0,
        },
        {
            "fluid_phase": "LIQUID",
            "mass_flow_kg_s": 1.0,
            "density_kg_m3": 1000.0,
            "viscosity_pa_s": 1.0e-3,
            "pipe_diameter_m": 0.08,
            "pipe_roughness_m": 4.6e-5,
            "length_m": 5.0,
        },
    ],
}


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_piping_results_pipe_chain_roundtrip_all_columns() -> None:
    """P4-2-5：calc → persist_pipe_chain_result → SELECT 验证 SUP-008 11 列 +
    record_hash + cleaning_method JSONB 含链完整 input/output。

    覆盖：
    - line_description = "PIPE_CHAIN: 2seg dp=...Pa"
    - pressure_drop_per_100m = gradient × 100
    - selected_diameter = 首段 D (mm)
    - cleaning_method JSONB[0]._chain_calc = True 且含 input/output
    - record_hash 16 hex
    """
    import uuid

    from app.services.pipe.pipe_chain_persist import persist_pipe_chain_result
    from app.services.pipe.pipe_chain_service import (
        PipeChainInput,
        PipeSegmentInput,
        calc_chain,
    )

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()
    payload = dict(_CHAIN_INPUT_DICT)
    payload["project_id"] = project_id
    payload["workspace_id"] = workspace_id
    payload["source_stream_id"] = source_stream_id
    payload["segments"] = [PipeSegmentInput(**s) for s in payload["segments"]]
    inp = PipeChainInput(**payload)
    res = calc_chain(inp)

    # 最小 Project + Workspace + Stream 落库前置（与 test_pipe_chain 同模式）
    # FK 链：Workspace.project_id ↔ Project.workspace_id（Project 一侧
    # use_alter=True 破建表循环，但 INSERT 仍立即检查） +
    # piping_results.material_class → pipe_classes.class_id（persist 硬编码
    # 'CS-STD'）。
    # INSERT 顺序：Workspace（project_id NULL）→ Project（workspace_id 引用）
    # → Workspace.project_id 回填 → CS-STD PipeClass → Stream。
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.config_domain import PipeClass
    from app.models.enums import StreamSignStatus
    from app.models.project import Project, Stream, Workspace

    factory = get_async_session_factory()
    async with factory() as session:
        ws = Workspace(
            workspace_id=workspace_id,
            workspace_type="FORMAL",
            project_id=None,  # 先 NULL；Project 落库后回填（FK 可空）
            name="t",
        )
        session.add(ws)
        await session.flush()
        proj = Project(
            project_id=project_id,
            project_no=f"P-{project_id.hex[:8]}",
            project_name="t",
            owner_company="t",
            location="t",
            project_type="t",
            design_phase="BASIC",
            unit_system="SI",
            status="ACTIVE",
            workspace_id=ws.workspace_id,
        )
        session.add(proj)
        await session.flush()
        ws.project_id = project_id  # 回填 Workspace→Project FK（可空）
        await session.flush()

        # CS-STD PipeClass（persist_pipe_chain_result 硬编码
        # material_class='CS-STD'；pcs_test 默认空 → FK 违反）。
        # 幂等：ON CONFLICT (class_id) DO NOTHING（重复运行安全）。
        stmt = (
            pg_insert(PipeClass)
            .values(
                class_id="CS-STD",
                class_name="Carbon Steel Standard",
                material_standard="ASME B36.10",
                base_material="A106-B",
                corrosion_allowance=1.5,
                design_pressure=2.5,
                design_temperature=200.0,
                allowable_stress_json={},
                dn_series_json={"min": 15, "max": 600},
                sch_series_json=["STD", "40", "XS"],
                flange_class="PN25",
                source="COMPANY_STD",
                version="v1",
                status="PUBLISHED",
            )
            .on_conflict_do_nothing(index_elements=["class_id"])
        )
        await session.execute(stmt)
        await session.flush()

        stream = Stream(
            stream_id=source_stream_id,
            project_id=project_id,
            workspace_id=workspace_id,
            stream_name=f"S-{source_stream_id.hex[:8]}",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            sign_status=StreamSignStatus.CHECKED,
            approval_depth=1,
            press=200000.0,
            temp=298.15,
            composition_json={"C1": 1.0},
        )
        session.add(stream)
        await session.flush()

        row, outlet = await persist_pipe_chain_result(session, inp, res)
        await session.commit()
        pk = row.pipe_id
        row_hash = row.record_hash
        outlet_source_type = outlet.source_type
        outlet_upstream = outlet.upstream_equipment_type

    # SELECT 11 SUP-008 列 + line_no + cleaning_method
    async with factory() as session:
        result = await session.execute(
            text(
                """
                SELECT pipe_id, line_no, line_description, pressure_drop_per_100m,
                       selected_diameter, cleaning_method, record_hash, check_result
                FROM piping_results
                WHERE pipe_id = :pk
                """
            ),
            {"pk": str(pk)},
        )
        record = result.mappings().one()
    got = dict(record)

    # line_no = tag_number
    assert got["line_no"] == "P-CHAIN-RT-001"
    # line_description 链摘要
    assert "PIPE_CHAIN" in got["line_description"]
    # pressure_drop_per_100m = gradient × 100（与计算结果一致）
    expected_dp100 = res.pressure_gradient_kpa_m * 100.0
    assert abs(float(got["pressure_drop_per_100m"]) - expected_dp100) < 1e-6
    # selected_diameter = 首段 D (mm) = 0.05 × 1000 = 50.0
    assert abs(float(got["selected_diameter"]) - 50.0) < 1e-6
    # cleaning_method JSONB 含完整 chain input/output
    cm = got["cleaning_method"]
    assert isinstance(cm, list) and len(cm) == 1
    chain_data = cm[0]
    assert chain_data["_chain_calc"] is True
    assert chain_data["_tag_number"] == "P-CHAIN-RT-001"
    assert "input" in chain_data and "output" in chain_data
    # input 内 UUID 已转 str（_json_safe 兼容 SQLite/PG JSONB）
    assert chain_data["input"]["tag_number"] == "P-CHAIN-RT-001"
    assert chain_data["input"]["inlet_pressure_pa"] == 200000.0
    # output 含 P4-2-5 新字段
    assert "flow_regimes" in chain_data["output"]
    assert chain_data["output"]["confidence"] in ("HIGH", "MEDIUM", "LOW")
    # record_hash 16 hex
    assert len(row_hash) == 16
    # outlet_stream P4-1-3 helper 复用契约
    assert outlet_source_type == "PIPE_CALCULATED"
    assert outlet_upstream == "PIPE"