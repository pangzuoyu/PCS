"""P3.x SIM-25：GET /imports/excel/template 模板下载端点测试。

端点契约：
- 路径：GET /api/v1/projects/{project_id}/imports/excel/template
- 响应：application/vnd.openpyxformats-officedocument.spreadsheetml.sheet
- 文件名：pcs_stream_import_template.xlsx
- 3 个 sheet：
  1. 物流列表（按 spec 附录 A 列名）
  2. 组分组成
  3. 别名表（Group / Alias / Standard）
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN / VIEWER（只读模板）
"""
from __future__ import annotations

import uuid
from io import BytesIO

import pytest
import pytest_asyncio
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Workspace


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
def viewer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-viewer", role="VIEWER")
    return {"Authorization": f"Bearer {token}"}


def _parse_template(content: bytes) -> dict[str, list[list]]:
    """打开下载的 .xlsx，把每个 sheet 的所有行收成 list[list]。"""
    wb = load_workbook(filename=BytesIO(content), data_only=True, read_only=True)
    sheets: dict[str, list[list]] = {}
    for name in wb.sheetnames:
        ws = wb[name]
        rows: list[list] = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))
        sheets[name] = rows
    wb.close()
    return sheets


# ---------------------------------------------------------------------------
# 端点契约
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_excel_template_200_designer(
    client, make_project, designer_headers
):
    proj = await make_project()
    r = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports/excel/template",
        headers=designer_headers,
    )
    assert r.status_code == 200, r.text
    ct = r.headers["content-type"]
    assert "spreadsheetml" in ct
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert "pcs_stream_import_template.xlsx" in cd


@pytest.mark.asyncio
async def test_get_excel_template_viewer_can_read(
    client, make_project, viewer_headers
):
    """模板只读，VIEWER 也应能下。"""
    proj = await make_project()
    r = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports/excel/template",
        headers=viewer_headers,
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_get_excel_template_missing_bearer_401(client, make_project):
    proj = await make_project()
    r = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports/excel/template",
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_excel_template_unknown_project_404(client, designer_headers):
    r = await client.get(
        f"/api/v1/projects/{uuid.uuid4()}/imports/excel/template",
        headers=designer_headers,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 内容契约
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_excel_template_has_three_sheets(
    client, make_project, designer_headers
):
    proj = await make_project()
    r = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports/excel/template",
        headers=designer_headers,
    )
    assert r.status_code == 200
    sheets = _parse_template(r.content)
    assert "物流列表" in sheets
    assert "组分组成" in sheets
    assert "别名表" in sheets


@pytest.mark.asyncio
async def test_get_excel_template_sheet1_headers(
    client, make_project, designer_headers
):
    """物流列表 sheet 至少包含 7 列名（按 spec 附录 A）。"""
    proj = await make_project()
    r = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports/excel/template",
        headers=designer_headers,
    )
    sheets = _parse_template(r.content)
    header_row = sheets["物流列表"][0]
    # 中文/英文兼容：列名至少包含一个常见的关键字段
    joined = " | ".join(str(c) for c in header_row if c)
    for needle in ["Stream", "Temperature", "Pressure", "Phase"]:
        assert needle in joined, f"缺关键列 {needle}：{header_row}"


@pytest.mark.asyncio
async def test_get_excel_template_alias_sheet_has_at_least_17(
    client, make_project, designer_headers
):
    """别名表至少 17 条（PRO/II 已知 LIBID→CAS）。"""
    proj = await make_project()
    r = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports/excel/template",
        headers=designer_headers,
    )
    sheets = _parse_template(r.content)
    rows = sheets["别名表"]
    # 去掉表头
    data_rows = [r for r in rows if any(c not in (None, "") for c in r)]
    assert len(data_rows) >= 1 + 17, (
        f"别名表条数不足 17：实有 {len(data_rows) - 1}"
    )


@pytest.mark.asyncio
async def test_get_excel_template_alias_includes_h2o_and_ch4(
    client, make_project, designer_headers
):
    proj = await make_project()
    r = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports/excel/template",
        headers=designer_headers,
    )
    sheets = _parse_template(r.content)
    rows = sheets["别名表"]
    flat = " ".join(
        str(c) for row in rows for c in row if c is not None
    )
    assert "H2O" in flat
    assert "C1" in flat  # PRO/II LIBID
    assert "METHANE" in flat