"""ReportService tests (Task 5.1 + 5.2 / P2 Sprint 3)。

Task 5.1 与 brief 偏差（F2 防御性修复）：

- 不用 ``by_key[(category, count)]`` 元组索引（脆；同 category 不同 count 会
  互相覆盖）。改为 ``by_key = {r.category: r for r in result}``，按 category
  索引后断言每个字段的具体数值。

Task 5.2 与 brief 偏差（F1 / F3 / F6 防御性修复）：

- ORM 替代 raw ``text(...)``（F1 — 跨 DB 兼容，与 Task 5.1 一致）
- top-level async 函数替代 ``class TestDocNoUsage``（F3 — pytest-asyncio 风格）
- ``r.total == 50`` 直接断言替代 ``by_template[tid] == 50`` 间接索引（F6 —
  反直觉，更清晰）
"""

from __future__ import annotations

from app.services.report_service import ConfigAssetReport, ReportService


async def test_empty_db_returns_empty_list(db):
    svc = ReportService(db)
    result = await svc.config_asset_status()
    assert result == []


async def test_aggregates_by_category_and_status(db, sample_assets_and_versions):
    svc = ReportService(db)
    result = await svc.config_asset_status()
    by_key = {r.category: r for r in result}

    # CATEGORY_2: 3 assets × 1 PUBLISHED version each → 3 published, 其它 0
    cat2 = by_key["CATEGORY_2"]
    assert cat2.published == 3
    assert cat2.draft == 0
    assert cat2.pending == 0
    assert cat2.approved == 0
    assert cat2.obsolete == 0

    # CATEGORY_3: 1 asset × 5 versions × 5 statuses → 每个状态各 1
    cat3 = by_key["CATEGORY_3"]
    assert cat3.draft == 1
    assert cat3.pending == 1
    assert cat3.approved == 1
    assert cat3.published == 1
    assert cat3.obsolete == 1


async def test_handles_all_status_values(db, sample_assets_and_versions):
    svc = ReportService(db)
    result = await svc.config_asset_status()

    # 2 个 category 都进结果集
    assert {r.category for r in result} == {"CATEGORY_2", "CATEGORY_3"}

    # 每个 report 都是 ConfigAssetReport 实例，且 5 个 count 字段都是 int
    for r in result:
        assert isinstance(r, ConfigAssetReport)
        for f in ("draft", "pending", "approved", "published", "obsolete"):
            assert isinstance(getattr(r, f), int)


# ---------------------------------------------------------------------------
# Task 5.2 — doc_no_sequence_usage
# ---------------------------------------------------------------------------


async def test_doc_no_sequence_usage_empty_db_returns_empty_list(db):
    svc = ReportService(db)
    result = await svc.doc_no_sequence_usage()
    assert result == []


async def test_doc_no_sequence_usage_sums_per_template(db, sample_doc_no_sequences):
    svc = ReportService(db)
    result = await svc.doc_no_sequence_usage()

    by_template_id = {r.template_id: r for r in result}

    # Template-A (current_value=50) + Template-B (current_value=30)
    seq_a, seq_b = sample_doc_no_sequences
    assert by_template_id[seq_a.template_id].total == 50
    assert by_template_id[seq_b.template_id].total == 30
    assert by_template_id[seq_a.template_id].template_name == "Template-A"
    assert by_template_id[seq_b.template_id].template_name == "Template-B"

    # 按 template_name 字母序：Template-A 在 Template-B 之前
    assert [r.template_name for r in result] == ["Template-A", "Template-B"]


async def test_doc_no_sequence_usage_skips_zero_counters(
    db, sample_template_with_zero_counter
):
    svc = ReportService(db)
    result = await svc.doc_no_sequence_usage()

    # 零计数模板不应出现在结果里
    template_ids = [r.template_id for r in result]
    assert sample_template_with_zero_counter.template_id not in template_ids
    assert result == []
