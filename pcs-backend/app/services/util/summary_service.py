"""S1-5 R3: util_results → 13 类聚合 + 折标煤计算。

Per plan brief Step 4: summary_service（求和 + 折标系数 CONFIG）。

业务：
- 13 类公用工程消耗量从 ``UtilResults.consumption_json`` 读出（flat map）
- 折标煤（toe_total）按 13→6 fuel_type 映射 + ToeConversionService.query_by_fuel_year
- 非能源 7 类不参与 toe_total 但进入 by_category 计数
- ``jsonb_deprecated`` 标记默认 False（Sprint 1 JSONB 权威）

R5: 最小范围；本服务仅做 read-only 聚合，不写库（persist_service 转 S1-5b）。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.util import UtilResults
from app.services.toe_conversion_service import ToeConversionService
from app.services.util.category_map import (
    TOE_FUEL_TYPE_BY_CATEGORY,
    UtilityCategory,
    utility_categories,
)


async def summarize(
    util_result: UtilResults,
    *,
    db: AsyncSession,
    year: int = 2026,
) -> dict:
    """UTIL V1.3 基线聚合：13 类 + 折标煤。

    Args:
        util_result: UtilResults 实例（持久化或 detached 都可；仅读 consumption_json）
        db: AsyncSession（用于 ToeConversionService 查询折标系数）
        year: 折标煤查询年份（默认 2026，与 ToeConversionService seed 一致）

    Returns:
        dict with keys:
          - by_category: dict[str, float] 13 类消耗量
          - toe_total: float 折标油当量总和（仅 6 类能源：ELECTRICITY + STEAM×4 + FUEL_GAS）
          - standard_coal_total: float 标煤总和（同 toe_total 计算）

    Raises:
        ValueError: consumption_json 含非 13 类键（schema 违反）
    """
    consumption = util_result.consumption_json or {}
    expected_keys = {c.value for c in utility_categories()}
    extra_keys = set(consumption.keys()) - expected_keys
    if extra_keys:
        # M8 fix: wording "未知键" 替代 "含非 13 类键" — 缺 key 合法（默认 0），
        # 仅 reject 未识别的 key
        raise ValueError(
            f"consumption_json 含未知键: {sorted(extra_keys)}; "
            f"valid: {sorted(expected_keys)}"
        )

    by_category: dict[str, float] = {}
    for cat in utility_categories():
        v = consumption.get(cat.value, 0.0)
        try:
            by_category[cat.value] = float(v) if v is not None else 0.0
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"consumption_json[{cat.value!r}] 非数值: {v!r}"
            ) from e

    toe_total = 0.0
    standard_coal_total = 0.0
    for cat_value, qty in by_category.items():
        fuel_type = TOE_FUEL_TYPE_BY_CATEGORY.get(cat_value)
        if fuel_type is None:
            continue  # 非能源类 / TOTAL 占位
        toe_row = await ToeConversionService.query_by_fuel_year(
            db, fuel_type=fuel_type, year=year
        )
        toe_total += qty * float(toe_row.toe_conversion_factor)
        standard_coal_total += qty * float(toe_row.standard_coal_factor)

    return {
        "by_category": by_category,
        "toe_total": toe_total,
        "standard_coal_total": standard_coal_total,
        "jsonb_deprecated": util_result.jsonb_deprecated,
        "year": year,
    }
