"""PSV 多标准配置 ORM（P5-0-5 Task 24a，SUP-P5-PSV-001 §3.1 + ADR-0028 V1.1）。

按 SUP-P5-PSV-001 §3.1 + ADR-0028 V1.1 决策 10a/11 + DICT V3.3 §4：

**ProjectCalculationStandardProfile** 表：
- 项目级 PSV/VESSEL/HEAT/PIPE/PUMP/SEPARATOR 标准配置
- 字段：id (UUID PK) / project_id (UUID FK projects) / discipline / profile_code /
  standard_refs_json / approval_json / is_default / migrated_default /
  effective_from / effective_to / approved_by / created_at / updated_at
- 3 CHECK 约束：discipline_enum / profile_code_enum / custom_requires_approval
- 1 EXCLUDE USING gist 约束（project_id, discipline, tstzrange 区间相交 +
  WHERE is_default=TRUE AND migrated_default=FALSE），依赖 btree_gist 扩展
- effective_from 未来时间校验下沉到 API 层 Pydantic（跨方言安全 + 时钟漂移容许）
- 2 部分索引：current_default + migrated_default

**Discipline / ProfileCode enum**：
- DisciplineEnum: PSV / VESSEL / HEAT / PIPE / PUMP / SEPARATOR（与 DB CHECK 对齐）
- StandardProfileCodeEnum: API / GB / CUSTOM（与 DB CHECK 对齐）

**业务语义（SUP §3.1 约束语义）**：
- is_default + migrated_default = FALSE：正式当前默认
- is_default + migrated_default = TRUE：迁移占位（不作为正式默认，需 pending_review）
- effective_to NULL：当前生效；非 NULL：已失效
- CUSTOM profile 必填 approval_json（G3 门禁 DB 层兜底）
- P5 不支持预排程 profile（effective_from ≤ created_at + 1s）

**REGISTRY 9 类（Q4 约束）**：ProjectCalculationStandardProfile 加入 RECORD_TYPE_REGISTRY，
P5-0-5 checkpoint 断言 `len == 9`（P5-0-1a 后 8 + 本 Task 1 = 9）。
"""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DisciplineEnum(str, enum.Enum):
    """项目级标准配置 discipline（SUP §3.1 discipline_enum_chk）。

    PSV / VESSEL / HEAT / PIPE / PUMP / SEPARATOR — 6 种计算 discipline。
    """

    PSV = "PSV"
    VESSEL = "VESSEL"
    HEAT = "HEAT"
    PIPE = "PIPE"
    PUMP = "PUMP"
    SEPARATOR = "SEPARATOR"


class StandardProfileCodeEnum(str, enum.Enum):
    """项目级标准配置 profile_code（SUP §3.1 profile_code_enum_chk）。

    API / GB / CUSTOM — 3 种标准族。
    """

    API = "API"
    GB = "GB"
    CUSTOM = "CUSTOM"


class ProjectCalculationStandardProfile(Base):
    """项目级计算标准配置（SUP-P5-PSV-001 §3.1）。

    同一 (project_id, discipline) 在任意时刻至多一个 is_default = TRUE
    （EXCLUDE USING gist + WHERE is_default=TRUE AND migrated_default=FALSE）。

    P5 阶段限制：
    - effective_from 必须 ≤ created_at + 1s（即时生效）
    - CUSTOM profile 必填 approval_json
    - migrated_default = TRUE 是迁移占位（不作为正式默认）
    """

    __tablename__ = "project_calculation_standard_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.project_id"),
        nullable=False,
        comment="项目 ID（UUID FK projects）",
    )
    discipline: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="PSV / VESSEL / HEAT / PIPE / PUMP / SEPARATOR",
    )
    profile_code: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="API / GB / CUSTOM",
    )
    standard_refs_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="各子标准、版本、条款映射（{fire_case, relief_area, orifice, ...}）",
    )
    approval_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="CUSTOM 时必填：审批人+依据",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
        comment="是否当前默认 profile",
    )
    migrated_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
        comment="迁移占位标志：与 psv_results/relief_results 同名同语义",
    )
    effective_from: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        comment="生效起始时间",
    )
    effective_to: Mapped[object | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="NULL 表示当前生效；非 NULL 表示已失效",
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
        comment="审批人（CUSTOM profile 必填）",
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    __table_args__ = (
        # discipline CHECK（与 DB CHECK 对齐）
        CheckConstraint(
            "discipline IN ('PSV', 'VESSEL', 'HEAT', 'PIPE', 'PUMP', 'SEPARATOR')",
            name="discipline_enum_chk",
        ),
        # profile_code CHECK
        CheckConstraint(
            "profile_code IN ('API', 'GB', 'CUSTOM')",
            name="profile_code_enum_chk",
        ),
        # CUSTOM profile 必填 approval_json（G3 门禁 DB 层兜底）
        CheckConstraint(
            "(profile_code = 'CUSTOM' AND approval_json IS NOT NULL) OR "
            "(profile_code <> 'CUSTOM')",
            name="custom_requires_approval_chk",
        ),
        # effective_from 未来时间校验下沉到 API 层 Pydantic
        # （跨方言安全 + 容许时钟漂移）
        # current_default 部分索引（排除 migrated_default + 已失效）
        Index(
            "idx_pcs_project_discipline_default",
            "project_id",
            "discipline",
            postgresql_where=text(
                "is_default = TRUE AND migrated_default = FALSE AND effective_to IS NULL"
            ),
        ),
        # migrated_default 部分索引（供 §11.4 复核队列查询）
        Index(
            "idx_pcs_profile_migrated_default",
            "project_id",
            "discipline",
            postgresql_where=text("migrated_default = TRUE"),
        ),
        # EXCLUDE USING gist：同一 (project_id, discipline) 至多一个 is_default=TRUE
        # 完整 SQL 字符串由 alembic migration 创建（Dialect 限制，ORM 不直接支持 EXCLUDE）
        {"comment": "EXCLUDE USING gist constraint project_standard_default_unique alembic 创建"},
    )
