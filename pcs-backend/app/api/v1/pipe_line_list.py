"""管道一览表（**项目作用域**）—— P10-C · T2（TODO-159）。

## 为什么补这个端点

前端「管道一览表」页（`/pipe/line-list`）此前调 `GET /projects/{id}/pipe-line-list`
⇒ ⇒ **契约里根本没有这个端点** ⇒ ⇒ 真后端下 **404**
（mock 通道有 MSW handler ⇒ 一路绿灯 ⇒ **只有真后端通道抓得到**）⇒ ⇒ TODO-159。

⚠️ **数据源是 `piping_results`（管道记录的**唯一真相源**）** ⇒ ⇒ 一览表的每一列
都来自**同一张表** ⇒ ⇒ 不再是「前端编的一份形状」。

## 授权

- **要登录**（`current_actor`）
- **要对该项目有访问权**（`check_project_access_or_404`）⇒ ⇒ 无权 ⇒ **404**
  （与「不存在」**同形** ⇒ ⇒ 枚举不出项目 id）

⚠️ **SYSTEM_ADMIN 全局 bypass**（与仓内其它项目守卫同口径）。

## 路径的来历

前端本来就在调 `GET /projects/{id}/pipe-line-list` ⇒ ⇒ 沿用这个路径 ⇒
⇒ **前端零改动**（只需要把占位 project id 换成**真** id）。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor
from app.db.session import get_db
from app.models.calc import PipingResult
from app.schemas.pipe_line_list import PipeLineListRow

router = APIRouter(prefix="/projects", tags=["pipe-line-list"])


def _to_row(record: PipingResult) -> PipeLineListRow:
    """ORM 行 → 响应行（列名逐条对应 SPEC §7.11.2）。"""
    return PipeLineListRow(
        seq=record.seq_no,
        pipe_no=record.line_no,
        size=record.line_size,
        material=record.material_class,
        fluid_code=record.fluid_code,
        fluid_name=record.fluid_name,
        phase=record.fluid_phase,
        fluid_class=record.fluid_category,
        toxicity=record.toxic_class,
        pipe_class=record.pipe_grade,
        insulation_code=record.insulation_code,
        insulation_thickness=record.insulation_thickness,
        paint_code=record.paint_code,
        tracing_type=record.tracing_type,
        holding_temp=record.holding_temp,
        pid_ref=record.source_pid,
        start_point=record.line_from,
        end_point=record.line_to,
        norm_oper_press=record.norm_oper_press,
        max_oper_press=record.max_oper_press,
        norm_oper_temp=record.norm_oper_temp,
        max_oper_temp=record.max_oper_temp,
        alt_norm_oper_press=record.alt_norm_oper_press,
        alt_max_oper_press=record.alt_max_oper_press,
        alt_norm_oper_temp=record.alt_norm_oper_temp,
        alt_max_oper_temp=record.alt_max_oper_temp,
        design_pressure_mpa=record.design_press,
        design_vacuum=record.design_vacuum,
        design_temperature_c=record.design_temp,
        design_min_temperature_c=record.design_min_temp,
        piping_category=record.piping_category,
        pressure_test_medium=record.pressure_test_medium,
        pressure_test_press=record.pressure_test_press,
        ndt_method=record.ndt_method,
        ndt_ratio=record.ndt_ratio,
        ndt_tech_level=record.ndt_tech_level,
        leak_test_medium=record.leak_test_medium,
        leak_test_press=record.leak_test_press,
        check_class=record.check_class,
        cleaning_method=record.cleaning_method,
        stress_analysis_level=record.stress_analysis_level,
        remark=record.remark,
        sign_status=(
            record.sign_status.value
            if hasattr(record.sign_status, "value")
            else str(record.sign_status)
        ),
        updated_by=str(record.created_by) if record.created_by else None,
        updated_at=record.updated_at,
    )


@router.get("/{project_id}/pipe-line-list", response_model=list[PipeLineListRow])
async def list_pipe_line_list(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[PipeLineListRow]:
    """列出某项目的管道一览表（分页：默认 limit=200 / offset=0）。

    - **项目隔离**：只返回 `project_id` 下的 `PipingResult`
    - **排序**：`seq_no` asc（序号）
    - 列清单 = SPEC §7.11.2「管道一览表列（完整）」
    """
    await check_project_access_or_404(
        session,
        user_id=user.user_id,
        project_id=project_id,
        actor_roles=list(user.roles),
    )
    rows = (
        await session.execute(
            select(PipingResult)
            .where(PipingResult.project_id == project_id)
            .order_by(PipingResult.seq_no)
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [_to_row(r) for r in rows]
