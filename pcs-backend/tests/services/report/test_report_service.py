"""生成编排契约 —— 二维码载荷 + 取数 + 渲染 + 内容哈希存储 + 审计。

四条要害（SPEC §六验收）：

1. **内容哈希复用** —— 同样的内容重复生成必须是**同一个** ReportFile 行、
   同一个磁盘文件（Review Focus #5、SPEC §2.5 文件不可变性）。
2. **失败也写审计** —— `REPORT_FAILED`。漏了这条测试就发现不了漏。
3. **磁盘失败报 PcsError** —— 不能把裸 `OSError` 抛到 API 层。
4. **假设数据声明页** —— SPEC §3.2.1(4)：存在 ASSUMED/NOT_STARTED 输入项
   → 自动加声明页，且**写进 `ReportFile.has_assumption_page`**。

⚠️ 第 1 条依赖二维码载荷**确定性**。载荷里若含 `datetime.now()`，
同一份内容两次生成的 PDF 字节不同 → 哈希不同 → 不复用。
`test_qr_payload_is_deterministic` 是这条链的根，单独钉住。
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import func, select

from app.models.report import ReportFile
from app.models.system import AuditLog
from app.services.exceptions import PcsError
from app.services.report.blocks import TableBlock
from app.services.report.qr import build_qr_payload
from app.services.report.report_service import generate
from app.services.report.style import ReportStyle

CTX = {"project_no": "PCS-2026-001", "doc_no": "D-001", "rev": "A"}

#: 签名的 `exp` 是**有意**随时间变的（防二维码被截图转发），所以「载荷确定性」
#: 这几条测试必须钉住 `now` 才能断言相等。确定性真正要求的是 **fragment** ——
#: 那部分是要画进 PDF 的凭据。另有专门一条断言两者之别。
FIXED_NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
QRID = uuid.UUID("11111111-2222-3333-4444-555555555555")
SIGKW = dict(report_file_id=QRID, secret="s", now=FIXED_NOW)


def test_qr_payload_is_deterministic():
    """**根断言**：同一组输入两次必须得到**完全相同**的载荷字符串。

    载荷里一旦有时间戳，内容哈希就每次不同，`test_same_content_twice_reuses_one_file`
    直接失效，而且失效得很隐蔽（哈希机制照常工作，只是永远命中不了）。
    """
    kw = dict(report_id="r-1", doc_no="D-001", rev="A", version_purpose="FOR_REVIEW",
              record_hashes=["h1", "h2"], verify_base_url="https://pcs.example", **SIGKW)
    assert build_qr_payload(**kw) == build_qr_payload(**kw)


def test_qr_payload_order_independent_on_record_hashes():
    """记录顺序不同不应改变摘要 —— 同批记录换个顺序还是同一份报表。"""
    a = build_qr_payload(report_id="r", doc_no="D", rev="A", version_purpose="P",
                         record_hashes=["h2", "h1"], verify_base_url="https://x", **SIGKW)
    b = build_qr_payload(report_id="r", doc_no="D", rev="A", version_purpose="P",
                         record_hashes=["h1", "h2"], verify_base_url="https://x", **SIGKW)
    assert a == b


def test_qr_payload_digest_changes_with_records():
    """记录变了摘要必须变 —— 这是「比对」能发现文件被动过的依据。"""
    a = build_qr_payload(report_id="r", doc_no="D", rev="A", version_purpose="P",
                         record_hashes=["h1"], verify_base_url="https://x", **SIGKW)
    b = build_qr_payload(report_id="r", doc_no="D", rev="A", version_purpose="P",
                         record_hashes=["h2"], verify_base_url="https://x", **SIGKW)
    assert a != b


def test_qr_payload_points_at_verify_endpoint():
    p = build_qr_payload(report_id="r-42", doc_no="D", rev="A", version_purpose="P",
                         record_hashes=[], verify_base_url="https://pcs.example/", **SIGKW)
    assert p.startswith("https://pcs.example/api/v1/report/verify/r-42")


@pytest.mark.asyncio
async def test_same_content_twice_reuses_one_file(db, project_id, tmp_path):
    """Review Focus #5：内容哈希命名 → 重复生成复用同文件。"""
    kw = dict(report_type="EQUIPMENT_LIST", project_id=project_id, record_ids=[],
              output_format="pdf", style=ReportStyle(), ctx=CTX, db=db)
    a = await generate(**kw)
    b = await generate(**kw)

    assert a.report_file_id == b.report_file_id, "同样内容两次生成应复用同一行"
    n = await db.scalar(select(func.count()).select_from(ReportFile.__table__))
    assert n == 1, f"应只有 1 行，实得 {n}"


@pytest.mark.asyncio
async def test_different_format_creates_separate_file(db, project_id):
    """格式不同 → 内容哈希不同 → 不同文件（PDF 不能复用 XLSX 的行）。"""
    a = await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                       record_ids=[], output_format="pdf",
                       style=ReportStyle(), ctx=CTX, db=db)
    b = await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                       record_ids=[], output_format="xlsx",
                       style=ReportStyle(), ctx=CTX, db=db)
    assert a.report_file_id != b.report_file_id
    assert a.content_hash != b.content_hash


@pytest.mark.asyncio
async def test_failure_writes_report_failed_audit(db, project_id, monkeypatch):
    """SPEC §六验收明写「失败也记录」。漏了这条测试就发现不了。"""
    from app.services.report import report_service

    def boom(*a, **k):          # 同步函数：渲染本来就是 CPU 密集的同步操作
        raise RuntimeError("渲染炸了")

    monkeypatch.setattr(report_service, "_render_sync", boom)
    with pytest.raises(RuntimeError):
        await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                       record_ids=[], output_format="pdf",
                       style=ReportStyle(), ctx=CTX, db=db)

    acts = (await db.execute(
        select(AuditLog).where(AuditLog.action == "REPORT_FAILED"))).scalars().all()
    assert acts, "失败路径必须写 REPORT_FAILED 审计"


@pytest.mark.asyncio
async def test_disk_failure_raises_pcserror_not_raw_oserror(db, project_id, monkeypatch):
    """磁盘满 / 权限不足 → 必须是 PcsError(REPORT_STORAGE_FAILED)，
    不能把裸 OSError 抛到 API 层变成 500 之外的奇怪响应。"""
    from app.services.report import report_service

    def boom(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(report_service, "_write_file", boom)
    with pytest.raises(PcsError) as e:
        await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                       record_ids=[], output_format="pdf",
                       style=ReportStyle(), ctx=CTX, db=db)
    assert e.value.code == "REPORT_STORAGE_FAILED"


@pytest.mark.asyncio
async def test_audit_failure_does_not_rollback_the_file(db, project_id, monkeypatch):
    """**审计失败不回滚文件记录** —— 文件已落盘，回滚 DB 只留下无记录的孤儿文件。

    孤儿文件比有记录更难排查（既没人知道它存在，也没人知道该删）。
    """
    from app.services.report import report_service

    real_write = report_service._write_file

    async def audit_boom(*a, **k):
        raise RuntimeError("审计库挂了")

    monkeypatch.setattr(report_service.AuditService, "write", audit_boom)
    out = await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                         record_ids=[], output_format="pdf",
                         style=ReportStyle(), ctx=CTX, db=db)
    assert out.report_file_id is not None, "审计失败不应回滚文件记录"
    assert real_write is report_service._write_file


@pytest.mark.asyncio
async def test_unsupported_output_format_rejected(db, project_id):
    """未知格式在**渲染前**就拒 —— 别渲染完再发现格式不认识，白烧 CPU。"""
    with pytest.raises(PcsError) as e:
        await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                       record_ids=[], output_format="pdf; DROP TABLE report_files",
                       style=ReportStyle(), ctx=CTX, db=db)
    assert e.value.code == "REPORT_FORMAT_UNSUPPORTED"


@pytest.mark.asyncio
async def test_xlsx_and_pdf_both_supported(db, project_id):
    for fmt in ("pdf", "xlsx", "docx"):
        out = await generate(report_type="EQUIPMENT_LIST", project_id=project_id,
                             record_ids=[], output_format=fmt,
                             style=ReportStyle(), ctx=CTX, db=db)
        assert out.file_format == fmt

# --- 内容指纹（不是字节哈希）------------------------------------------------


def test_rendered_pdf_is_never_byte_identical():
    """**前提事实**：reportlab 每次生成随机 `/ID`，同一秒内两次也不同。

    这条不是测我们的代码，是测**为什么不能**对渲染字节取哈希 —— 钉住这个
    前提，将来谁把 `_content_hash` 改回 `sha256(payload)` 时，
    `test_same_content_twice_reuses_one_file` 会立刻红并指回这里。
    """
    from app.services.report.renderer_pdf import render_pdf

    kw = dict(title="t", blocks=[TableBlock(headers=["a"], rows=[["b"]])],
              style=ReportStyle(), qr_payload=None, assumed_fields=[], context=CTX)
    assert render_pdf(**kw) != render_pdf(**kw), \
        "PDF 字节竟然相同了 —— 若 reportlab 改行为，重评内容指纹方案"


def test_content_hash_ignores_when_rendering_happened():
    """内容指纹只取决于内容，与渲染时刻无关。"""
    from app.services.report.report_service import _content_hash

    kw = dict(blocks=[TableBlock(headers=["a"], rows=[["b"]])], output_format="pdf")
    assert _content_hash(style=ReportStyle(), ctx=CTX, **kw) == \
        _content_hash(style=ReportStyle(), ctx=CTX, **kw)


def test_content_hash_changes_with_format_and_content():
    from app.services.report.report_service import _content_hash

    b1 = [TableBlock(headers=["a"], rows=[["b"]])]
    b2 = [TableBlock(headers=["a"], rows=[["c"]])]
    def h(**kw):
        return _content_hash(style=ReportStyle(), ctx=CTX, **kw)

    assert h(blocks=b1, output_format="pdf") != h(blocks=b1, output_format="xlsx")
    assert h(blocks=b1, output_format="pdf") != h(blocks=b2, output_format="pdf")


def test_content_hash_ignores_font_dir():
    """`font_dir` 是部署路径不是样式内容 —— 混进去会让两台机器算出两个哈希。"""
    from app.services.report.report_service import _content_hash

    blocks = [TableBlock(headers=["a"], rows=[["b"]])]
    assert _content_hash(blocks=blocks, style=ReportStyle(), ctx=CTX,
                         output_format="pdf") == \
        _content_hash(blocks=blocks, style=ReportStyle(font_dir="/some/other/dir"),
                      ctx=CTX, output_format="pdf")


@pytest.mark.asyncio
async def test_the_qr_drawn_into_the_pdf_verifies_against_the_stored_row(
        db, project_id, tmp_path, monkeypatch):
    """**端到端**：画进 PDF 的那个二维码，必须能用**落库那一行**的 id 验签通过。

    这是 #4 的全部要害。`qr_payload` 与 `report_file_id` 在两条独立的路径上
    产生 —— 一个在渲染前，一个在 upsert 时。若两边不同源，画进 PDF 的签名
    绑的是 A、登记的是 B，**每一张**报表的二维码扫码都 403，而生成过程
    全程无报错（PDF 里画一个字符串总是成功的）。

    评审建议的修法（把 `store_rendered` 重排成「先 upsert 再签名」）不采纳：
    它担心签名的时间戳污染 `_content_hash`，而 `_content_hash` 哈希的是
    Blocks + style + format + ctx，**qr_payload 根本不在里面**。
    这里用「渲染前自选 id」达到同样结果，且不动既有顺序。
    """
    from urllib.parse import parse_qs, urlsplit

    from app.api.v1.report import _check_sig
    from app.core.config import get_settings
    from app.services.report import report_service

    monkeypatch.setattr(get_settings(), "report_verify_secret", "e2e-secret",
                        raising=False)
    monkeypatch.setattr(get_settings(), "report_verify_base_url",
                        "https://pcs.example", raising=False)

    seen: dict = {}
    real = report_service._render_sync

    def spy(**kw):
        seen["qr"] = kw.get("qr_payload")
        return real(**kw)

    monkeypatch.setattr(report_service, "_render_sync", spy)

    row = await generate(
        report_type="EQUIPMENT_LIST", project_id=project_id, record_ids=[],
        output_format="pdf", style=ReportStyle(), ctx=CTX, db=db)

    assert seen.get("qr"), (
        "渲染时 qr_payload 是 None —— 二维码根本没画进 PDF，"
        "而流程全程无报错（这正是评审 P1 #4 描述的症状）")
    parts = urlsplit(seen["qr"])
    qs = {k: v[0] for k, v in parse_qs(parts.query).items()}
    _check_sig(row.report_file_id, qs["sig"], int(qs["exp"]))
