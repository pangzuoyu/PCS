"""SPEC §3.3.1 性能指标 —— **绝对阈值断言**。

刻意不用 pytest-benchmark：它的相对阈值（±X%）在 CI 共享 runner 上会因负载
波动频繁误报，几次之后就会被 disable —— 这是 cerebrum 里「守门恒报噪声 =
狼来了」的另一个版本。要曲线就本地手动跑，这个文件只管守 SPEC 的三个数字。

## 测的是什么、不测什么

b7 已把生成改为 ARQ 异步，所以这里测的是**任务体本身**（取数 + 渲染），
**不含队列等待** —— 队列延迟是另一回事，混进来会让阈值失去意义。

⚠️ 阈值与硬件强相关（下面数字是 20 核机器实测）。CI runner 通常更慢，
所以三条断言都留了余量，但**不是为了「在 CI 上也能过」而放宽** —— 那会让
这个文件失去意义。真变慢了应该改实现或改 SPEC，不该改阈值。
"""
from __future__ import annotations

import time

import pytest

from app.services.report.report_service import generate
from app.services.report.style import ReportStyle
from tests.fixtures.report.seed import make_bulk_seed, make_report_seed

# SPEC §3.3.1
SIMPLE_LIMIT_S = 5.0
COMPLEX_LIMIT_S = 15.0
BUILDER_10K_LIMIT_S = 10.0


async def _gen(db, project_id, report_type, fmt="pdf", style=None):
    ids = await make_report_seed(db, project_id, report_type)
    t0 = time.perf_counter()
    await generate(report_type=report_type, project_id=project_id,
                   record_ids=ids, output_format=fmt,
                   style=style or ReportStyle(), ctx={}, db=db)
    return time.perf_counter() - t0


@pytest.mark.asyncio
async def test_simple_report_under_5s(db, project_id):
    """简单报表（数据表类，行数少）。"""
    el = await _gen(db, project_id, "PSV_DATA_TABLE")
    assert el < SIMPLE_LIMIT_S, f"简单报表 {el:.2f}s > {SIMPLE_LIMIT_S}s"


@pytest.mark.asyncio
async def test_complex_report_under_15s(db, project_id):
    """复杂报表（规格书类，多字段）。"""
    el = await _gen(db, project_id, "HEAT_SPEC")
    assert el < COMPLEX_LIMIT_S, f"复杂报表 {el:.2f}s > {COMPLEX_LIMIT_S}s"


@pytest.mark.asyncio
async def test_xlsx_10k_rows_under_10s(db, project_id):
    """1 万行执行 —— SPEC 预算。

    实测（20 核）：10k 行 XLSX ≈ 0.23s、**PDF ≈ 9.6 CPU-秒**（≈1ms/行，
    线性无超线性爆炸）。这里测 XLSX 因为它是 SPEC §3.3.1 里「1 万行」的
    那一档；PDF 的 10k 成本单独记在 ADR-P8-004，那里才是它该被看的地方
    （决定 worker 并发与「>5000 行建议改用 Excel」的产品提示）。
    """
    ids = await make_bulk_seed(db, project_id, "EQUIPMENT_LIST", 10000)

    t0 = time.perf_counter()
    out = await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                         record_ids=ids, output_format="xlsx",
                         style=ReportStyle(), ctx={}, db=db)
    el = time.perf_counter() - t0

    # ⚠️ **断言输出真的有一万行**，不只断输入造了多少条。
    # 只断耗时是不够的：变异「只造 2 行」时测试**照样全绿**（2 行 ~0.02s，
    # 远在 10s 之内）—— 时间阈值**分辨不出 2 行与 1 万行**。
    # 「测的确实是 1 万行」这个前提必须由**输出**钉住，
    # 否则改一次造数逻辑就悄悄变成测 2 行了。
    from openpyxl import load_workbook

    from app.services.report import paths

    ws = load_workbook(paths.resolve_path(out.file_path), read_only=True)["报表"]
    assert ws.max_row >= 10000, \
        f"输出只有 {ws.max_row} 行，不是 1 万行 —— 这条测试没在测 1 万行"

    assert el < BUILDER_10K_LIMIT_S, f"1 万行执行 {el:.2f}s > {BUILDER_10K_LIMIT_S}s"


@pytest.mark.asyncio
async def test_font_registration_is_cached_across_renders(db, project_id):
    """字体注册必须**进程内只做一次** —— 每次重新解析 10.6MB 的 TTF
    会让「简单报表」的耗时被字体加载吃掉（实测首次 ≈0.3s，后续 ≈0）。

    这不是性能断言而是**行为断言**：没有它，某天有人把缓存删掉做「小清理」，
    性能测试仍可能全绿（字体解析在预热后很快）。
    """
    from app.services.report import renderer_pdf

    await _gen(db, project_id, "PSV_DATA_TABLE")
    assert "Noto Sans CJK SC" in renderer_pdf._REGISTERED, \
        "首次渲染后字体应已注册并记入缓存"