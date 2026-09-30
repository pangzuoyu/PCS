"""S1-5 R1: UtilResults ORM (util_results 单表) + jsonb_deprecated marker。

Per SPEC V1.4 §4.4 + plan brief Step 3：13 类公用工程枚举（consumption_json
JSONB 存 per-category quantity）+ jsonb_deprecated bool（默认 False；Sprint 1
JSONB 权威，Sprint 2 起置 True 当 5 表迁移完成后）。

Sprint 2 Task S2-1~6 会在此文件 append 5 张独立表（utility_power_items /
utility_fuel_gas / utility_heat_exchange / utility_energy_summary /
catalyst_loading）；本任务仅落 V1.3 基线 + 折标煤计算路径。
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class UtilResults(TimestampMixin, Base):
    """UTIL V1.3 基线表（util_results，per SPEC V1.4 §4.4 + plan brief）。

    业务：
    - ``consumption_json`` 存 13 类公用工程消耗量（flat {category: float_quantity}）
    - ``jsonb_deprecated`` 默认 False（Sprint 1 JSONB 权威）；Sprint 2 起置 True
      当 5 表 (utility_power_items / utility_fuel_gas / utility_heat_exchange /
      utility_energy_summary / catalyst_loading) 全部迁移完成且数据回填后
    - 13 类公用工程清单 + 单位见 ``app/services/util/category_map.py``
    - 折标煤通过 ``ToeConversionService`` 查询 + 13→6 fuel_type 映射计算
    """

    __tablename__ = "util_results"
    __table_args__ = (
        Index("ix_util_results_project", "project_id"),
    )

    util_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id"), index=True
    )

    # 业务日期（折标煤按年查询需要）
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 13 类消耗量（JSONB；SQLite 测试时 conftest 映射 JSON）
    consumption_json: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        comment="13 类公用工程 flat {category: float_quantity} map (per SPEC V1.4 §4.4)",
    )

    # Sprint 1 JSONB 权威；Sprint 2 起置 True 当 5 表迁移完成
    jsonb_deprecated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Sprint 1 False JSONB 权威；Sprint 2 起 True 表示已迁移 5 表",
    )

    # 元信息
    source: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="数据来源描述（GB 2589 / 项目实际 / 设计值）",
    )
