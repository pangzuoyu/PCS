"""ReportService tests (Task 5.1 / P2 Sprint 3)。

与 brief 偏差（F2 防御性修复）：

- 不用 ``by_key[(category, count)]`` 元组索引（脆；同 category 不同 count 会
  互相覆盖）。改为 ``by_key = {r.category: r for r in result}``，按 category
  索引后断言每个字段的具体数值。
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
