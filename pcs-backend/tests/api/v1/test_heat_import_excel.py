"""`POST /heat/import-htri` 接受 HTRI 的 **Excel 版**报表。

用户 2026-10-13 澄清：`A-101.xls` 就是 HTRI 文件的 Excel 版。所以端点
不能只收 `.txt` —— 现场工程师手上的就是 Excel。

## 为什么要单独钉这一层

`parse_htri_excel` 若只做成一个模块而没有端点，用户触达不到：模块测试
全绿、导入功能实际不可用。所以本文件走**完整 HTTP 路径**。

## 分派规则

按**上传文件名后缀**决定用哪个 parser，不用文件内容嗅探 ——
嗅探失败时的默认分支是「按老的走」，而老 parser 对 Excel 会抛
「首行无法判别版本」，错误信息指向版本而不是「这是 Excel 请换个入口」。
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parents[3].parent / "sample"
XACE = SAMPLE / "A-101.xls"


@pytest.fixture
def auth_designer():
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(subject='d1', role='DESIGNER')}"}


def _form(**over):
    base = {
        "project_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "equipment_no": "E-901",
        "tag_number": "E-901",
        "exchanger_category": "AIR_COOL",
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_import_accepts_an_excel_report(client, auth_designer, db_session):
    """真实 Xace 报表走完整 HTTP 路径 → 201，且**新字段真的落库**。

    ⚠️ 「端点返回 201」不等于「字段落库了」—— 中间隔着
    `map_htri_to_heat_input` 的字段映射，漏一个 key 就是 201 + 空列。
    """
    if not XACE.exists():
        pytest.skip("A-101.xls 不在 sample/")
    from sqlalchemy import select

    from app.models.calc import HeatResult

    r = await client.post(
        "/api/v1/heat/import-htri",
        headers=auth_designer,
        files={"file": ("A-101.xls", XACE.read_bytes(),
                        "application/vnd.ms-excel")},
        data=_form(),
    )
    assert r.status_code == 201, r.text

    rows = (await db_session.execute(select(HeatResult))).scalars().all()
    assert rows, "导入后库里一条 HeatResult 都没有"
    row = rows[-1]
    # 用户 2026-12-12 裁决要进规格书的字段
    assert row.duty == pytest.approx(0.3103e6, rel=1e-3), "热负荷"
    assert row.skin_temp_min == pytest.approx(39.60), "壁温 min"
    assert row.skin_temp_max == pytest.approx(93.42), "壁温 max"
    assert row.tube_rows == 4, "管排数（别取成管程数 2）"
    assert row.tube_passes == 2
    assert row.extended_area_m2 == pytest.approx(580.567)
    assert row.shell_params["vapor_wt_frac_out"] == pytest.approx(0.117)
    # 主表剩余 4 条缺口
    assert row.bare_area_m2 == pytest.approx(24.908)
    assert row.heat_transfer_safety_factor == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_excel_import_error_says_excel_not_version(client, auth_designer, tmp_path):
    """传一个不是 HTRI 报表的 xlsx → 错误信息要说「不是报表」，
    **不是**「首行无法判别版本」。

    后者会把用户指向版本问题，而真实原因是「这个文件不是 HTRI 报表」。
    """
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.append(["随便", "什么"])
    p = tmp_path / "junk.xlsx"
    wb.save(p)

    r = await client.post(
        "/api/v1/heat/import-htri",
        headers=auth_designer,
        files={"file": ("junk.xlsx", p.read_bytes(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data=_form(),
    )
    assert r.status_code == 422, r.text
    body = r.json()
    msg = body.get("message", "")
    assert "报表" in msg or "HTRI" in msg, f"错误信息没指向「不是 HTRI 报表」：{msg}"
    assert "版本" not in msg, f"错误信息误指向版本判别：{msg}"


@pytest.mark.asyncio
async def test_text_path_error_is_not_masked_by_a_scoping_bug(client, auth_designer):
    """⚠️ `.txt` 路径抛错时，错误必须**原样**到达用户。

    加 Excel 分支时踩过：`HtriExcelParseError` 被 import 在
    `if is_excel:` 里面，走 `.txt` 路径时它是**未绑定的局部名**，而
    `except (A, B)` 里的 B 在**异常发生那一刻**求值 →
    `UnboundLocalError` 把原始的 `HtriParseError` 顶掉，
    用户看到的是一个完全无关的错误，且**掩盖了真实原因**。
    """
    r = await client.post(
        "/api/v1/heat/import-htri",
        headers=auth_designer,
        files={"file": ("corrupted.txt", b"not an HTRI report",
                        "text/plain")},
        data=_form(),
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "HEAT_INPUT_ERROR", body
    assert "UnboundLocalError" not in body["message"], \
        f"原始错误被作用域 bug 顶掉了：{body['message']}"
