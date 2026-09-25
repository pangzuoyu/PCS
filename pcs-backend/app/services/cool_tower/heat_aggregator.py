"""COOL_TOWER HEAT 汇总（§3.2.4.5）。

按 SPEC §3.2.4.5 P6-CT-001：从已落库的 ``heat_results`` 表（继承
``TaggedRecordMixin``，ADR-0027 V1.0 双轨扩展）按 ``project_id`` + 水冷
``exchanger_category`` 汇总 ``duty`` → ``H_aggregate_kw``。

设计要点：

- 过滤 ``exchanger_category NOT IN ('AIR_COOL')`` — 仅水冷设备
  （SHELL_TUBE + PLATE）计入（空冷已 P5-2-x 单独空冷塔计算）。
- 默认 ``sign_status_filter = (DRAFT, CHECKED)`` — 排除 OBSOLETE 等
  门禁态污染聚合（与 SUP-007 §3.1 9 态门禁对齐）。
- SQL 参数化：用 ``sqlalchemy.select()`` + ``session.execute()`` + ``.in_()``
  拼接（防 SQL 注入 + 跨 dialect 兼容）。
- ``aggregate_heat_duty`` 接收 async ``AsyncSession``（与 P6-2 Task 23
  ``flare_persist_service`` 同源约定）。
- 不写 DB（仅 SELECT；落库由 Task 25 ``cool_tower_persist_service``
  统一处理）。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import HeatResult
from app.models.enums import RecordSignStatus9
from app.services.exceptions import PcsError


@dataclass(frozen=True)
class HeatAggregatorInput:
    """HEAT 汇总输入（§3.2.4.5）。

    字段：
    - session: async SQLAlchemy session（DB 读取）。
    - project_id: 项目 ID（必填；isolation key）。
    - exchanger_categories_filter: 过滤的 exchanger_category 列表
      （默认 ('SHELL_TUBE', 'PLATE')；排除 'AIR_COOL'）。
    - sign_status_filter: sign_status 白名单（默认 DRAFT/CHECKED，
      避免 OBSOLETE 污染聚合）。
    """

    session: AsyncSession
    project_id: uuid.UUID
    exchanger_categories_filter: tuple[str, ...] = ("SHELL_TUBE", "PLATE")
    sign_status_filter: tuple[RecordSignStatus9, ...] = field(
        default=(RecordSignStatus9.DRAFT, RecordSignStatus9.CHECKED)
    )


@dataclass(frozen=True)
class HeatAggregatorResult:
    """HEAT 汇总结果（§3.2.4.5）。

    字段：
    - h_aggregate_kw: 总 kW（各 exchanger_category 求和）。
    - heat_record_count: 命中的 HeatResult 行数。
    - per_exchanger_category: 按类别细分 {"SHELL_TUBE": 1234.5, "PLATE": 56.7}。
    - formula_ref: 公式溯源标记 "API_521_§3.2.4.5"。
    """

    h_aggregate_kw: float  # 总 kW
    heat_record_count: int  # 命中行数
    per_exchanger_category: dict[str, float]  # 各类别细分
    formula_ref: str = "API_521_§3.2.4.5"


class HeatAggregatorInputError(PcsError):
    """heat_aggregator 输入不合法（422）。

    触发场景：project_id 为空 / exchanger_categories_filter 包含
    AIR_COOL（违反「水冷设备 only」约束）。
    """

    code = "HEAT_AGGREGATOR_INPUT_ERROR"
    status = 422


async def aggregate_heat_duty(inp: HeatAggregatorInput) -> HeatAggregatorResult:
    """按 project_id + exchanger_categories 汇总 duty（kW，§3.2.4.5）。

    SQL（参数化，避免 SQL 注入）：

        SELECT exchanger_category, SUM(duty), COUNT(*)
        FROM heat_results
        WHERE project_id = :project_id
          AND exchanger_category IN :categories
          AND sign_status IN :statuses
        GROUP BY exchanger_category

    Args:
        inp: HeatAggregatorInput（已冻结 dataclass；含 session）。

    Returns:
        HeatAggregatorResult（含 h_aggregate_kw / heat_record_count /
        per_exchanger_category / formula_ref）。

    Raises:
        HeatAggregatorInputError: project_id 为空 / 过滤列表含 AIR_COOL。
    """
    if not inp.project_id:
        raise HeatAggregatorInputError("project_id 不能为空")
    # 防御：过滤列表排除 AIR_COOL（水冷设备 only）
    if "AIR_COOL" in inp.exchanger_categories_filter:
        raise HeatAggregatorInputError(
            "exchanger_categories_filter 不应包含 'AIR_COOL'（仅水冷计入）"
        )
    if not inp.exchanger_categories_filter:
        raise HeatAggregatorInputError("exchanger_categories_filter 不能为空")

    # GROUP BY 聚合（SQL 层做 SUM；避免 ORM 拉所有行 Python 端聚合）
    stmt = (
        select(
            HeatResult.exchanger_category,
            func.sum(HeatResult.duty).label("sum_duty"),
            func.count().label("cnt"),
        )
        .where(
            HeatResult.project_id == inp.project_id,
            HeatResult.exchanger_category.in_(inp.exchanger_categories_filter),
            HeatResult.sign_status.in_(inp.sign_status_filter),
        )
        .group_by(HeatResult.exchanger_category)
    )
    rows = (await inp.session.execute(stmt)).all()

    per_category: dict[str, float] = {}
    total_count = 0
    h_total = 0.0
    for category, sum_duty, cnt in rows:
        # category 是 String(30) 列 — 强制 str 化（防止 enum/None 干扰）
        cat_str = str(category)
        # sum_duty 可能为 None（无 duty 数据）→ 0.0
        s = float(sum_duty) if sum_duty is not None else 0.0
        c = int(cnt) if cnt is not None else 0
        per_category[cat_str] = s
        h_total += s
        total_count += c

    return HeatAggregatorResult(
        h_aggregate_kw=h_total,
        heat_record_count=total_count,
        per_exchanger_category=per_category,
    )


__all__ = [
    "HeatAggregatorInput",
    "HeatAggregatorResult",
    "HeatAggregatorInputError",
    "aggregate_heat_duty",
]