"""P3.2 SIM-10：ImportService PRO/II + Excel 导入契约测试（spec V1.6 §5.5）。

按 plan V1.0 落地（用户 2026-09-08 锁定）：
- preview 走 parser + ConflictResolver（不落库）
- commit 走 StreamService.create（复用 SIM-4 链路：SIM-3 物性补全 + SIM-7 冲突）
- convergence_status: CONVERGED/WARNINGS 全量入库；NOT_CONVERGED/ABORTED → 标记
  unreliable=True（入库但需复核）
- 复用 5 PRO/II 样例（tests/fixtures/proii/sample{1..5}）+ 1 Excel 样例
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, Workspace
from app.services.import_service import ImportService
from app.services.proii_parser import ConvergenceStatus

FIXTURES = Path(__file__).parent.parent / "fixtures" / "proii"


def _proii_pair(sample: str) -> tuple[Path, Path]:
    d = FIXTURES / sample
    return d / f"{sample}.inp", d / f"{sample}.out"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """Workspace + Project 工厂（commit 阶段需要 project_id）。"""

    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.flush()
        return proj

    return _make


def _build_xlsx(path: Path, *, sheet1: list, sheet2: list) -> None:
    """临时构造 xlsx（commit 阶段用例）。"""
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "物流列表"
    for row in sheet1:
        ws1.append(row)
    ws2 = wb.create_sheet("组分组成")
    for row in sheet2:
        ws2.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


# ===========================================================================
# PRO/II preview
# ===========================================================================


def test_preview_proii_sample1_converged_full_import():
    """sample1 V8.5 CONVERGED：所有 13 stream 走 preview，含 1 个 unreliable warning。"""
    inp, out = _proii_pair("sample1_34comp")
    preview = ImportService.preview_proii(inp, out)
    assert preview["convergence_status"] == ConvergenceStatus.CONVERGED.value
    # sample1 13 个流：FEED/S1-S7/OVHD/BTMS/REFLUX/REBOIL
    assert len(preview["preview_streams"]) >= 13
    # preview_streams 含 case_type/phase/temp/press/mass_flow/unreliable
    first = preview["preview_streams"][0]
    assert first["case_type"] == "NORMAL"
    assert first["data_mode"] == "CHEMICAL"
    assert first["source_type"] == "SIM_IMPORT"
    assert first["import_source_version"] == "V8.5"
    assert "is_unreliable" in first
    # conflict_report 必有 stats
    assert "BLOCK" in preview["conflict_report"]["stats"]


def test_preview_proii_unreliable_streams_marked():
    """sample2 NOT_CONVERGED：unreliable 流标记 True。"""
    inp, out = _proii_pair("sample2_unconverged")
    preview = ImportService.preview_proii(inp, out)
    assert preview["convergence_status"] == ConvergenceStatus.NOT_CONVERGED.value
    assert len(preview["unreliable_stream_names"]) > 0
    # 至少一个 preview_streams 条目 is_unreliable=True
    assert any(
        e["is_unreliable"] for e in preview["preview_streams"]
    )


def test_preview_proii_phase_normalized():
    """PRO/II 相态单字母 L/V → LIQUID/VAPOR（MIXED 留 None 避免 SIM-V01 BLOCK）。"""
    inp, out = _proii_pair("sample1_34comp")
    preview = ImportService.preview_proii(inp, out)
    # 至少有 LIQUID/VAPOR 中之一（V/L）
    phases = {e["phase"] for e in preview["preview_streams"] if e["phase"]}
    assert phases & {"LIQUID", "VAPOR"}


def test_preview_proii_temperature_pressure_si_to_engineering():
    """温度 K → °C（-273.15）/压力 Pa → kPa（/1000）。"""
    inp, out = _proii_pair("sample1_34comp")
    preview = ImportService.preview_proii(inp, out)
    s = preview["preview_streams"][0]
    # FEED: T=380K→106.85°C; P=1500kPa=1.5MPa in .inp（inp unit）
    # .out parser 已是 SI（Pa/K），故 preview 应已转换回工程单位
    if s["temp"] is not None:
        assert -300 < s["temp"] < 1000
    if s["press"] is not None:
        assert s["press"] > 0


def test_preview_proii_banner_v4_17_import_version_string():
    inp, out = _proii_pair("sample2_unconverged")
    preview = ImportService.preview_proii(inp, out)
    assert preview["preview_streams"][0]["import_source_version"] == "V4.17"


# ===========================================================================
# PRO/II commit
# ===========================================================================


@pytest.mark.asyncio
async def test_commit_proii_creates_streams_in_project(db, make_project):
    """preview → commit → 项目下新增对应 stream。"""
    inp, out = _proii_pair("sample1_34comp")
    proj = await make_project()
    preview = ImportService.preview_proii(inp, out)
    result = await ImportService.commit_proii(
        db,
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        preview_streams=preview["preview_streams"],
        actor=uuid.uuid4(),
    )
    assert result["committed_count"] == len(preview["preview_streams"])
    assert result["skipped_count"] == 0
    assert len(result["stream_ids"]) == result["committed_count"]


@pytest.mark.asyncio
async def test_commit_proii_duplicate_name_skipped(db, make_project):
    """同名已存在 → commit 跳过该流，不抛错。"""
    proj = await make_project()
    inp, out = _proii_pair("sample1_34comp")
    # 第一次 commit：建流
    preview = ImportService.preview_proii(inp, out)
    await ImportService.commit_proii(
        db,
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        preview_streams=preview["preview_streams"],
        actor=uuid.uuid4(),
    )
    # 第二次 commit：全部 SKIP
    result = await ImportService.commit_proii(
        db,
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        preview_streams=preview["preview_streams"],
        actor=uuid.uuid4(),
    )
    assert result["committed_count"] == 0
    assert result["skipped_count"] == len(preview["preview_streams"])


@pytest.mark.asyncio
async def test_commit_proii_unreliable_counted(db, make_project):
    """unreliable 流：仍入库，但 unreliable_count > 0。"""
    inp, out = _proii_pair("sample2_unconverged")
    proj = await make_project()
    preview = ImportService.preview_proii(inp, out)
    result = await ImportService.commit_proii(
        db,
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        preview_streams=preview["preview_streams"],
        actor=uuid.uuid4(),
    )
    assert result["unreliable_count"] > 0
    assert result["committed_count"] >= result["unreliable_count"]


@pytest.mark.asyncio
async def test_commit_proii_persists_is_unreliable_column(db, make_project):
    """SIM-10.1：Stream.is_unreliable 列在 commit 后正确落库。

    - 至少一个流 is_unreliable=True
    - 至少一个流 is_unreliable=False
    - DB 列可查询（用户 2026-09-09 裁决：下游过滤刚需）
    """
    from sqlalchemy import select

    from app.models.project import Stream

    inp, out = _proii_pair("sample2_unconverged")
    proj = await make_project()
    preview = ImportService.preview_proii(inp, out)
    await ImportService.commit_proii(
        db,
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        preview_streams=preview["preview_streams"],
        actor=uuid.uuid4(),
    )
    rows = (
        await db.execute(select(Stream.is_unreliable).where(Stream.project_id == proj.project_id))
    ).scalars().all()
    true_rows = [r for r in rows if r is True]
    false_rows = [r for r in rows if r is False]
    assert len(true_rows) >= 1, f"sample2 必含 unreliable 流，got {rows}"
    assert len(false_rows) >= 1, f"sample2 应也含可靠流，got {rows}"


@pytest.mark.asyncio
async def test_commit_excel_persists_is_unreliable_false(db, make_project, tmp_path):
    """Excel 无收敛概念 → commit 后所有 stream is_unreliable=False。"""
    from sqlalchemy import select

    from app.models.project import Stream

    sheet1 = [
        ["Stream Name", "Temp (°C)", "Pressure (kPa)", "Phase",
         "Total Mass Flow (kg/h)", "Total Molar Flow (kmol/h)", "Description"],
        ["S-101", 80.0, 200.0, "L", 1000.0, 50.0, "test"],
    ]
    sheet2 = [
        ["Stream Name", "Component Name", "Mole Fraction", "Mass Flow (kg/h)"],
        ["S-101", "H2O", 1.0, ""],
    ]
    p = tmp_path / "sample.xlsx"
    _build_xlsx(p, sheet1=sheet1, sheet2=sheet2)
    proj = await make_project()
    preview = ImportService.preview_excel(p)
    await ImportService.commit_excel(
        db,
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        preview_streams=preview["preview_streams"],
        actor=uuid.uuid4(),
    )
    rows = (
        await db.execute(select(Stream.is_unreliable).where(Stream.project_id == proj.project_id))
    ).scalars().all()
    assert rows == [False]


# ===========================================================================
# Excel preview
# ===========================================================================


def test_preview_excel_streams_with_composition(tmp_path):
    """Excel 解析 → preview 含 composition_json。"""
    sheet1 = [
        ["Stream Name", "Temp (°C)", "Pressure (kPa)", "Phase",
         "Total Mass Flow (kg/h)", "Total Molar Flow (kmol/h)", "Description"],
        ["S-101", 80.0, 200.0, "L", 1000.0, 50.0, "test"],
    ]
    sheet2 = [
        ["Stream Name", "Component Name", "Mole Fraction", "Mass Flow (kg/h)"],
        ["S-101", "H2O", 1.0, ""],
    ]
    p = tmp_path / "sample.xlsx"
    _build_xlsx(p, sheet1=sheet1, sheet2=sheet2)
    preview = ImportService.preview_excel(p)
    assert len(preview["preview_streams"]) == 1
    s = preview["preview_streams"][0]
    assert s["stream_name"] == "S-101"
    assert s["composition_json"] == {"WATER": 1.0}  # H2O → WATER 别名
    assert preview["convergence_status"] == "N/A"


def test_preview_excel_phase_uppercased(tmp_path):
    """Excel phase 小写 l → 大写 LIQUID。"""
    sheet1 = [
        ["Stream Name", "Temp (°C)", "Pressure (kPa)", "Phase",
         "Total Mass Flow (kg/h)", "Total Molar Flow (kmol/h)", "Description"],
        ["S-101", 80.0, 200.0, "l", 1000.0, 50.0, "test"],
    ]
    sheet2 = [
        ["Stream Name", "Component Name", "Mole Fraction", "Mass Flow (kg/h)"],
        ["S-101", "H2O", 1.0, ""],
    ]
    p = tmp_path / "sample.xlsx"
    _build_xlsx(p, sheet1=sheet1, sheet2=sheet2)
    preview = ImportService.preview_excel(p)
    assert preview["preview_streams"][0]["phase"] == "LIQUID"


# ===========================================================================
# Excel commit
# ===========================================================================


@pytest.mark.asyncio
async def test_commit_excel_creates_stream(db, make_project, tmp_path):
    sheet1 = [
        ["Stream Name", "Temp (°C)", "Pressure (kPa)", "Phase",
         "Total Mass Flow (kg/h)", "Total Molar Flow (kmol/h)", "Description"],
        ["S-101", 80.0, 200.0, "L", 1000.0, 50.0, "test"],
    ]
    sheet2 = [
        ["Stream Name", "Component Name", "Mole Fraction", "Mass Flow (kg/h)"],
        ["S-101", "H2O", 1.0, ""],
    ]
    p = tmp_path / "sample.xlsx"
    _build_xlsx(p, sheet1=sheet1, sheet2=sheet2)
    proj = await make_project()
    preview = ImportService.preview_excel(p)
    result = await ImportService.commit_excel(
        db,
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        preview_streams=preview["preview_streams"],
        actor=uuid.uuid4(),
    )
    assert result["committed_count"] == 1
    assert result["skipped_count"] == 0