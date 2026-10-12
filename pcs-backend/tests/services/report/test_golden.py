"""10 类报表的 Golden 基线 —— 输出**稳定性**的回归闸。

## 为什么不直接比二进制

PDF 字节**每次都不同**（reportlab 随机 `/ID`，`CreationDate` 随时钟变 ——
bug-155 已实证）。所以 Golden 比的是**归一化文本**（`pypdf` 抽文本），
不是字节。这不是权宜之计，是这类文件格式的固有约束。

## 这条测试防的是什么

不是「输出内容没变」这种温和回归，而是**渲染器被改坏却没人发现**：
字段被悄悄删掉、NULL 变空串、假设标记消失、页码不再变。任何一项都会让
归一化文本不同 → 红。

## ⚠️ Golden 的维护陷阱

新增/修改报表字段后 Golden **必然**不一致 —— 那是**预期的**，不是 bug。
此时跑 `--update-golden` 重新生成，然后**逐条看 diff** 确认变化是你要的。
不看 diff 就重新生成，等于把回归固化成基线。

因此另有一条 `test_golden_contains_real_seed_values`：防「全是占位符」的
假基线 —— 一份「表头 + 空行」的 PDF 也合法、也能生成，若基线是这样，
它对任何回归都免疫。
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.services.report.collector import REPORT_TYPES
from app.services.report.report_service import generate
from app.services.report.style import ReportStyle
from tests.fixtures.report.seed import make_report_seed

GOLDEN_DIR = (Path(__file__).resolve().parents[3] / "tests" / "fixtures"
              / "golden" / "report")


def normalize_pdf(data: bytes) -> str:
    """PDF → 归一化文本。

    只抽文本层：时间戳与文档 ID **不进**文本层，而字形/分页/换行都进 ——
    正好是「人眼看到的」的等价物。
    """
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)


async def _render(db, project_id, report_type) -> str:
    ids = await make_report_seed(db, project_id, report_type)
    out = await generate(report_type=report_type, project_id=project_id,
                         record_ids=ids, output_format="pdf",
                         style=ReportStyle(), ctx={}, db=db)
    from app.services.report import paths

    return normalize_pdf(paths.resolve_path(out.file_path).read_bytes())


@pytest.mark.parametrize("report_type", sorted(REPORT_TYPES))
@pytest.mark.asyncio
async def test_golden_text_stable(db, project_id, report_type, request):
    got = await _render(db, project_id, report_type)
    assert got.strip(), f"{report_type} 生成的内容是空的"

    target = GOLDEN_DIR / f"{report_type}.txt"
    if request.config.getoption("--update-golden"):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(got)
        return

    assert target.exists(), (
        f"缺 Golden 基线 {target.name}。首次生成：\n"
        f"  pytest tests/services/report/test_golden.py --update-golden\n"
        f"（基线文件入库后才有人在改动时看到差异）")
    assert got == target.read_text(), (
        f"{report_type} Golden 不一致。\n"
        f"若这是**预期的**改动（新增/修改字段），跑 --update-golden 并逐条看 diff；"
        f"若不是，说明渲染器被改坏了。")


@pytest.mark.asyncio
async def test_golden_contains_real_seed_values(db, project_id):
    """防「全是占位符」的假基线。

    「表头 + 空行」的 PDF 也是合法输出、也能生成 —— 若基线是这样，
    它对任何回归都免疫。而这种基线**看起来完全正常**，是典型的假绿。
    """
    # ⚠️ 断言的必须是**这一类报表真有的**值。第一版写了「天然气」——
    # 那是 PUMP/STREAMS 的字段，EQUIPMENT_LIST 里根本没有，于是这条
    # 「防空壳基线」的守卫自己报了个假警。
    text = await _render(db, project_id, "EQUIPMENT_LIST")
    for marker in ("PUMP-101", "离心泵", "ACME", "CP-50"):
        assert marker in text, (
            f"输出里没有种子的真实值 {marker} —— 基线是空壳，对回归免疫。"
            f"实得前 200 字：{text[:200]}")


@pytest.mark.asyncio
async def test_seed_covers_all_report_types(db, project_id):
    """每种报表都要能造出种子 —— 造不出说明该类的字段闸是空的。"""
    for report_type in sorted(REPORT_TYPES):
        ids = await make_report_seed(db, project_id, report_type)
        assert ids, f"{report_type} 没有种子记录"