"""Excel 批量导入测试（Task 1.9.6 / P2-STD-001 验收「Excel导入正常」）。"""
import io
from pathlib import Path

from openpyxl import Workbook

from app.services.pipe_class_service import PipeClassService

_HEADERS = [
    "class_id", "class_name", "material_standard", "corrosion_allowance",
    "design_pressure", "design_temperature", "dn_min", "dn_max",
    "sch_series(JSON)", "flange_class", "source", "version",
]
_ROW = ["A1", "等级A1", "GB/T 8163", 1.5, 2.5, 200, 15, 350,
        '{"15": "40", "350": "STD"}', "PN25", "COMPANY_STD", "PC-V1.0"]


def _xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "pipe_classes"
    ws.append(_HEADERS)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_create(class_id: str):
    from app.schemas.pipe_class import PipeClassCreate
    return PipeClassCreate(
        class_id=class_id, class_name=f"等级{class_id}", material_standard="GB/T 8163",
        corrosion_allowance=1.5, design_pressure=2.5, design_temperature=200.0,
        dn_series_json={"min": 15, "max": 350},
        sch_series_json={"15": "40", "350": "STD"},
        flange_class="PN25", source="COMPANY_STD", version="PC-V1.0",
    )


async def test_import_two_rows_one_dup(db):
    await PipeClassService.create(db, payload=_make_create("A1"))  # 预存 A1 → 导入行 A1 冲突跳过
    row_a2 = ["A2", "等级A2"] + _ROW[2:]
    result = await PipeClassService.import_from_excel(
        db, io.BytesIO(_xlsx([_ROW, row_a2])))
    assert result["imported"] == 1 and result["skipped"] == 1
    assert await PipeClassService.get(db, "A2")


async def test_import_bad_json_reports_error(db):
    bad = [_ROW[:8] + ["not-json"] + _ROW[9:]]
    result = await PipeClassService.import_from_excel(db, io.BytesIO(_xlsx(bad)))
    assert result["imported"] == 0 and len(result["errors"]) == 1


async def test_template_download(client, sample_pc_token):
    r = await client.get("/api/v1/pipe-classes/import-template",
                         headers={"Authorization": f"Bearer {sample_pc_token}"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd")
    assert len(r.content) > 500  # 有效 xlsx


SEEDS = Path(__file__).parents[2] / "app" / "seeds"


async def test_import_bep_seed(db):
    """P2-OPEN-001：BEP 4.3 Rev0 真实数据全量导入（6 等级，A2F sch 为空 JSON）。"""
    result = await PipeClassService.import_from_excel(
        db, (SEEDS / "pipe_classes_bep_rev0.xlsx").open("rb"))
    assert result["imported"] == 6 and result["skipped"] == 0 and result["errors"] == []
    pc = await PipeClassService.get(db, "G1E")
    assert pc.design_pressure == 10.0 and pc.flange_class == "1500Lb/RJ"


async def test_import_kaimen_seed(db):
    """P2-OPEN-001 第二数据源：Kaimen SPC-0004-C1 54 等级（PROJECT source）。"""
    result = await PipeClassService.import_from_excel(
        db, (SEEDS / "pipe_classes_kaimen_20048a.xlsx").open("rb"))
    assert result["imported"] == 54 and result["errors"] == []
    pc = await PipeClassService.get(db, "150C10F01RF")
    assert pc.source == "PROJECT" and pc.corrosion_allowance == 1.5
    assert pc.sch_series_json["15"] == "SCH 80"
    jacket = await PipeClassService.get(db, "40BA90G12E")  # 夹套芯管
    assert jacket.design_temperature == 350.0 and jacket.design_pressure == 1.6


async def test_import_ppg_seed(db):
    """P2-OPEN-001 第三数据源：PPG MRQ-0001 11 等级（U1-U8/P1-P3）。"""
    result = await PipeClassService.import_from_excel(
        db, (SEEDS / "pipe_classes_ppg.xlsx").open("rb"))
    assert result["imported"] == 11 and result["errors"] == []
    u4 = await PipeClassService.get(db, "U4")  # 冷却水到大口径
    assert u4.dn_series_json == {"min": 15, "max": 900}
    assert u4.sch_series_json["900"] == "STD" and u4.sch_series_json["15"] == "XS"
    u5 = await PipeClassService.get(db, "U5")  # 热油 390°C
    assert u5.design_temperature == 390.0 and u5.corrosion_allowance == 1.6
