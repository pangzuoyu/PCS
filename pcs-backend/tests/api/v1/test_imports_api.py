"""P3.2 SIM-10 + P3.x SIM-14：PRO/II + Excel 导入 stateful preview/commit API 测试。

stateful（D-4 闭环）：
- preview 阶段：解析 + 持久化到 sim_imports，返回 {import_id, preview}
- commit 阶段：通过 import_id 读取 sim_imports，落库 + 更新 status=COMMITTED

端到端验证 4 端点：
- POST /projects/{id}/imports/proii/preview  (multipart .inp+.out)
- POST /projects/{id}/imports/proii/commit   (JSON {import_id: UUID})
- POST /projects/{id}/imports/excel/preview  (multipart .xlsx)
- POST /projects/{id}/imports/excel/commit   (JSON {import_id: UUID})

错误码：
- 401 missing bearer / 403 role forbidden
- 404 SIM_STREAM_NOT_FOUND（commit 时 project 不存在——同 stream CRUD）
- 404 SIM_IMPORT_NOT_FOUND（commit 时 import_id 不存在）
- 410 SIM_IMPORT_EXPIRED（import_id 超过 24h 过期）
- 422 SIM_IMPORT_PARSE_ERROR（parser 抛 ValueError）
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Workspace

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "proii"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
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
        await db.commit()
        return proj

    return _make


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def no_role_headers() -> dict[str, str]:
    token = create_access_token(subject="test-norole", role="VIEWER")
    return {"Authorization": f"Bearer {token}"}


def _proii_pair(sample: str) -> tuple[Path, Path]:
    d = FIXTURES / sample
    return d / f"{sample}.inp", d / f"{sample}.out"


def _build_xlsx(
    path: Path, *, sheet1: list, sheet2: list, sheet1_name: str = "物流列表"
) -> None:
    wb = Workbook()
    ws1 = wb.active
    ws1.title = sheet1_name
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


@pytest.mark.asyncio
async def test_preview_proii_200(client, make_project, designer_headers):
    proj = await make_project()
    inp, out = _proii_pair("sample1_34comp")
    with inp.open("rb") as f_inp, out.open("rb") as f_out:
        r = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/proii/preview",
            files={"file_inp": ("sample1.inp", f_inp, "text/plain"),
                   "file_out": ("sample1.out", f_out, "text/plain")},
            headers=designer_headers,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "import_id" in body
    preview = body["preview"]
    assert preview["convergence_status"] in ("CONVERGED", "WARNINGS", "NOT_CONVERGED")
    assert len(preview["preview_streams"]) >= 1
    assert "conflict_report" in preview


@pytest.mark.asyncio
async def test_preview_proii_unreliable_marked(client, make_project, designer_headers):
    proj = await make_project()
    inp, out = _proii_pair("sample2_unconverged")
    with inp.open("rb") as f_inp, out.open("rb") as f_out:
        r = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/proii/preview",
            files={"file_inp": ("sample2.inp", f_inp, "text/plain"),
                   "file_out": ("sample2.out", f_out, "text/plain")},
            headers=designer_headers,
        )
    assert r.status_code == 200
    body = r.json()
    preview = body["preview"]
    assert preview["convergence_status"] == "NOT_CONVERGED"
    assert any(e["is_unreliable"] for e in preview["preview_streams"])


@pytest.mark.asyncio
async def test_preview_proii_401_no_bearer(client, make_project):
    proj = await make_project()
    inp, out = _proii_pair("sample1_34comp")
    with inp.open("rb") as f_inp, out.open("rb") as f_out:
        r = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/proii/preview",
            files={"file_inp": ("a.inp", f_inp, "text/plain"),
                   "file_out": ("a.out", f_out, "text/plain")},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_preview_proii_403_role_forbidden(client, make_project, no_role_headers):
    proj = await make_project()
    inp, out = _proii_pair("sample1_34comp")
    with inp.open("rb") as f_inp, out.open("rb") as f_out:
        r = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/proii/preview",
            files={"file_inp": ("a.inp", f_inp, "text/plain"),
                   "file_out": ("a.out", f_out, "text/plain")},
            headers=no_role_headers,
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_preview_proii_404_project_not_found(client, designer_headers):
    inp, out = _proii_pair("sample1_34comp")
    with inp.open("rb") as f_inp, out.open("rb") as f_out:
        r = await client.post(
            f"/api/v1/projects/{uuid.uuid4()}/imports/proii/preview",
            files={"file_inp": ("a.inp", f_inp, "text/plain"),
                   "file_out": ("a.out", f_out, "text/plain")},
            headers=designer_headers,
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_preview_proii_invalid_banner_422(client, make_project, designer_headers, tmp_path):
    """.out 缺 banner → parser 抛 ValueError → 422 SIM_IMPORT_PARSE_ERROR。"""
    proj = await make_project()
    inp = tmp_path / "bad.inp"
    inp.write_text("STREAM DATA\n")
    out = tmp_path / "bad.out"
    out.write_text("NO BANNER HERE\n")
    with inp.open("rb") as f_inp, out.open("rb") as f_out:
        r = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/proii/preview",
            files={"file_inp": ("bad.inp", f_inp, "text/plain"),
                   "file_out": ("bad.out", f_out, "text/plain")},
            headers=designer_headers,
        )
    assert r.status_code == 422
    assert r.json()["code"] == "SIM_IMPORT_PARSE_ERROR"


# ===========================================================================
# PRO/II commit
# ===========================================================================


@pytest.mark.asyncio
async def test_commit_proii_201(client, make_project, designer_headers):
    proj = await make_project()
    inp, out = _proii_pair("sample1_34comp")
    with inp.open("rb") as f_inp, out.open("rb") as f_out:
        r1 = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/proii/preview",
            files={"file_inp": ("a.inp", f_inp, "text/plain"),
                   "file_out": ("a.out", f_out, "text/plain")},
            headers=designer_headers,
        )
    assert r1.status_code == 200
    body1 = r1.json()
    import_id = body1["import_id"]
    preview_streams = body1["preview"]["preview_streams"]
    r2 = await client.post(
        f"/api/v1/projects/{proj.project_id}/imports/proii/commit",
        json={"import_id": import_id},
        headers=designer_headers,
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["committed_count"] == len(preview_streams)
    assert body["skipped_count"] == 0
    assert len(body["stream_ids"]) == body["committed_count"]


@pytest.mark.asyncio
async def test_commit_proii_duplicate_skipped(client, make_project, designer_headers):
    """commit 两次 → 第二次 409 SIM_IMPORT_INVALID_STATE（state 已 = COMMITTED）。"""
    proj = await make_project()
    inp, out = _proii_pair("sample1_34comp")
    with inp.open("rb") as f_inp, out.open("rb") as f_out:
        r1 = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/proii/preview",
            files={"file_inp": ("a.inp", f_inp, "text/plain"),
                   "file_out": ("a.out", f_out, "text/plain")},
            headers=designer_headers,
        )
    import_id = r1.json()["import_id"]
    # 第一次 commit 成功
    r1c = await client.post(
        f"/api/v1/projects/{proj.project_id}/imports/proii/commit",
        json={"import_id": import_id},
        headers=designer_headers,
    )
    assert r1c.status_code == 200
    # 第二次 commit → 409 SIM_IMPORT_INVALID_STATE（state 已 COMMITTED）
    r2 = await client.post(
        f"/api/v1/projects/{proj.project_id}/imports/proii/commit",
        json={"import_id": import_id},
        headers=designer_headers,
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == "SIM_IMPORT_INVALID_STATE"


# ===========================================================================
# Excel preview / commit
# ===========================================================================


@pytest.mark.asyncio
async def test_preview_excel_200(client, make_project, designer_headers, tmp_path):
    proj = await make_project()
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
    with p.open("rb") as f:
        r = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/excel/preview",
            files={"file_xlsx": ("sample.xlsx", f,
                                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=designer_headers,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    preview = body["preview"]
    assert len(preview["preview_streams"]) == 1
    assert preview["preview_streams"][0]["composition_json"] == {"WATER": 1.0}  # H2O → WATER 别名


@pytest.mark.asyncio
async def test_commit_excel_201(client, make_project, designer_headers, tmp_path):
    proj = await make_project()
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
    with p.open("rb") as f:
        r1 = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/excel/preview",
            files={"file_xlsx": ("sample.xlsx", f,
                                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=designer_headers,
        )
    import_id = r1.json()["import_id"]
    r2 = await client.post(
        f"/api/v1/projects/{proj.project_id}/imports/excel/commit",
        json={"import_id": import_id},
        headers=designer_headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["committed_count"] == 1


@pytest.mark.asyncio
async def test_preview_excel_422_missing_sheet(client, make_project, designer_headers, tmp_path):
    """Excel 缺 Sheet 2 → 422 SIM_IMPORT_PARSE_ERROR。"""
    proj = await make_project()
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "物流列表"
    ws1.append(["Stream Name", "Temp (°C)", "Pressure (kPa)", "Phase",
                "Total Mass Flow (kg/h)", "Total Molar Flow (kmol/h)", "Description"])
    ws1.append(["S-101", 80.0, 200.0, "L", 1000.0, 50.0, "test"])
    p = tmp_path / "incomplete.xlsx"
    wb.save(p)
    with p.open("rb") as f:
        r = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/excel/preview",
            files={"file_xlsx": ("x.xlsx", f,
                                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=designer_headers,
        )
    assert r.status_code == 422
    assert r.json()["code"] == "SIM_IMPORT_PARSE_ERROR"


@pytest.mark.asyncio
async def test_preview_excel_401_no_bearer(client, make_project, tmp_path):
    proj = await make_project()
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
    with p.open("rb") as f:
        r = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/excel/preview",
            files={"file_xlsx": ("x.xlsx", f, "application/vnd.ms-excel")},
        )
    assert r.status_code == 401


# ===========================================================================
# P3.x SIM-14：stateful preview 专项测试
# ===========================================================================


@pytest.mark.asyncio
async def test_commit_proii_404_import_not_found(client, make_project, designer_headers):
    """commit 传不存在的 import_id → 404 SIM_IMPORT_NOT_FOUND。"""
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/imports/proii/commit",
        json={"import_id": str(uuid.uuid4())},
        headers=designer_headers,
    )
    assert r.status_code == 404
    assert r.json()["code"] == "SIM_IMPORT_NOT_FOUND"


@pytest.mark.asyncio
async def test_stateful_preview_persists_to_sim_imports(
    client, make_project, designer_headers, db
):
    """stateful preview 必须把解析结果写入 sim_imports（status=PREVIEW，D-4 闭环核心）。"""
    from app.models.sim_import import SimImport, SimImportStatus

    proj = await make_project()
    inp, out = _proii_pair("sample1_34comp")
    with inp.open("rb") as f_inp, out.open("rb") as f_out:
        r = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/proii/preview",
            files={"file_inp": ("sample1.inp", f_inp, "text/plain"),
                   "file_out": ("sample1.out", f_out, "text/plain")},
            headers=designer_headers,
        )
    assert r.status_code == 200
    body = r.json()
    import_id = uuid.UUID(body["import_id"])

    # 直接查 DB 验证 sim_imports 行已写入
    from sqlalchemy import select

    stmt = select(SimImport).where(SimImport.import_id == import_id)
    sim_import = (await db.execute(stmt)).scalar_one()
    assert sim_import.status == SimImportStatus.PREVIEW
    assert sim_import.project_id == proj.project_id
    assert sim_import.source_file_name == "sample1.inp"
    assert sim_import.expires_at > sim_import.created_at
    assert len(sim_import.preview_streams_json) >= 1


@pytest.mark.asyncio
async def test_stateful_commit_marks_status_committed(
    client, make_project, designer_headers, db
):
    """commit 后 sim_imports.status 必须更新为 COMMITTED + committed_at + committed_by。"""
    from app.models.sim_import import SimImport, SimImportStatus

    proj = await make_project()
    inp, out = _proii_pair("sample1_34comp")
    with inp.open("rb") as f_inp, out.open("rb") as f_out:
        r1 = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/proii/preview",
            files={"file_inp": ("sample1.inp", f_inp, "text/plain"),
                   "file_out": ("sample1.out", f_out, "text/plain")},
            headers=designer_headers,
        )
    import_id = uuid.UUID(r1.json()["import_id"])
    r2 = await client.post(
        f"/api/v1/projects/{proj.project_id}/imports/proii/commit",
        json={"import_id": str(import_id)},
        headers=designer_headers,
    )
    assert r2.status_code == 200

    # 验证 DB 状态更新
    from sqlalchemy import select

    stmt = select(SimImport).where(SimImport.import_id == import_id)
    sim_import = (await db.execute(stmt)).scalar_one()
    assert sim_import.status == SimImportStatus.COMMITTED
    assert sim_import.committed_at is not None
    assert sim_import.committed_by is not None


@pytest.mark.asyncio
async def test_p4_4_commit_writes_sim_tower_results(
    client, make_project, designer_headers, db
):
    """P4 #4 parser 入库链路：commit 阶段把 COLUMN SUMMARY 写入 sim_tower_results。

    sample1_34comp 含 COLUMN SUMMARY 段 → 至少 1 行 sim_tower_results。
    """
    from sqlalchemy import select

    from app.models.sim_tower import SimTowerResult

    proj = await make_project()
    inp, out = _proii_pair("sample1_34comp")
    with inp.open("rb") as f_inp, out.open("rb") as f_out:
        r1 = await client.post(
            f"/api/v1/projects/{proj.project_id}/imports/proii/preview",
            files={"file_inp": ("sample1.inp", f_inp, "text/plain"),
                   "file_out": ("sample1.out", f_out, "text/plain")},
            headers=designer_headers,
        )
    import_id = uuid.UUID(r1.json()["import_id"])
    # preview 阶段 preview_towers 至少 1 条
    assert len(r1.json()["preview"].get("preview_towers", [])) >= 1, r1.text
    r2 = await client.post(
        f"/api/v1/projects/{proj.project_id}/imports/proii/commit",
        json={"import_id": str(import_id)},
        headers=designer_headers,
    )
    assert r2.status_code == 200, r2.text
    assert len(r2.json().get("tower_ids", [])) >= 1, r2.text

    # DB 校验
    stmt = select(SimTowerResult).where(SimTowerResult.import_id == import_id)
    towers = (await db.execute(stmt)).scalars().all()
    assert len(towers) >= 1
    assert towers[0].tower_type == "COLUMN"
    assert towers[0].tower_uid is not None
    assert towers[0].num_stages is not None
