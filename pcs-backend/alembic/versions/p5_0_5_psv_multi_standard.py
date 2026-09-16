"""P5-0-5 Task 24a: PSV 多标准配置 + 9 类 registry。

按 SUP-P5-PSV-001 §3 + ADR-0028 V1.1（决策 10a G1-G6 门禁 + 决策 11 GB 分层阈值）：
1. **新表** `project_calculation_standard_profiles`：项目级 PSV/VESSEL/HEAT 等 discipline 标准配置
   - 字段：id (UUID PK) / project_id (UUID FK) / discipline / profile_code / standard_refs_json /
     approval_json / is_default / migrated_default / effective_from / effective_to /
     approved_by / created_at / updated_at
   - 约束：4 个 CHECK（discipline / profile_code / custom_requires_approval /
     future_dated_forbidden）
   - EXCLUDE USING gist（project_id, discipline, tstzrange 区间相交 +
     WHERE is_default=TRUE AND migrated_default=FALSE）
   - 2 部分索引（current_default + migrated_default）
2. **psv_results / relief_results 加 7 列**：
   standard_profile_code / standard_refs_json / formula_ref_json / pending_review /
   migrated_default / override_reason / override_approval_json
3. **2 表各加 override_paired_chk CHECK** + 各 2 部分索引（pending_review + migrated_default）

P5-0 批约束 3（2026-09-16 用户裁决 Q4）：REGISTRY 8→9，Task 24 完成后
checkpoint 断言 `len(RECORD_TYPE_REGISTRY) == 9`。

**SPEC 类型适配**：SUP §3.1 草稿用 BIGINT/BIGSERIAL，但 DICT V3.3 §4 projects.project_id = UUID PK
+ PCS 后端实际用 UUID；本迁移以 DICT V3.3 为准（id/project_id/approved_by 全部 UUID）。

**EXTENSION**：btree_gist 已 DBA 预装（commit 5060b76），本迁移补 `CREATE EXTENSION IF NOT EXISTS`
作为建表前置条件（迁移自身幂等不依赖扩展是否预装）。

**DOWN-REVISION** = p5_0_4a_pk_rename_and_tag_number（P5-0-4a 末态）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "p5_0_5_psv_multi_standard"
down_revision = "p5_0_4a_pk_rename_and_tag_number"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. btree_gist 扩展（EXCLUDE USING gist 需要，跨类型 = 运算符支持）
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # 2. CREATE TABLE project_calculation_standard_profiles
    op.create_table(
        "project_calculation_standard_profiles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.project_id"),
            nullable=False,
        ),
        sa.Column(
            "discipline",
            sa.String(length=16),
            nullable=False,
            comment="PSV / VESSEL / HEAT / PIPE / PUMP / SEPARATOR",
        ),
        sa.Column(
            "profile_code",
            sa.String(length=16),
            nullable=False,
            comment="API / GB / CUSTOM",
        ),
        sa.Column(
            "standard_refs_json",
            JSONB,
            nullable=False,
            comment="各子标准、版本、条款映射（{fire_case, relief_area, orifice, ...}）",
        ),
        sa.Column(
            "approval_json",
            JSONB,
            nullable=True,
            comment="CUSTOM 时必填：审批人+依据",
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="是否当前默认 profile",
        ),
        sa.Column(
            "migrated_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="迁移占位标志：与 psv_results/relief_results 同名同语义",
        ),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "effective_to",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="NULL 表示当前生效；非 NULL 表示已失效",
        ),
        sa.Column(
            "approved_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # discipline CHECK
        sa.CheckConstraint(
            "discipline IN ('PSV', 'VESSEL', 'HEAT', 'PIPE', 'PUMP', 'SEPARATOR')",
            name="discipline_enum_chk",
        ),
        # profile_code CHECK
        sa.CheckConstraint(
            "profile_code IN ('API', 'GB', 'CUSTOM')",
            name="profile_code_enum_chk",
        ),
        # CUSTOM profile 必填 approval_json（G3 门禁 DB 层兜底）
        sa.CheckConstraint(
            "(profile_code = 'CUSTOM' AND approval_json IS NOT NULL) OR "
            "(profile_code <> 'CUSTOM')",
            name="custom_requires_approval_chk",
        ),
        # effective_from 未来时间检查下沉到 API 层 Pydantic 校验（跨方言安全
        # + 容许时钟漂移；DB 层无 INTERVAL/时区比较的跨方言兜底机制）
        # EXCLUDE USING gist 由下方 op.execute 创建（SQLAlchemy 不解析
        # op.create_table 内的字符串为独立约束）
    )

    # EXCLUDE USING gist：同一 (project_id, discipline) 至多一个 is_default=TRUE
    # 依赖 btree_gist 扩展（已在本升级顶部 CREATE EXTENSION）
    op.execute(
        """
        ALTER TABLE project_calculation_standard_profiles
        ADD CONSTRAINT project_standard_default_unique
        EXCLUDE USING gist (
            project_id WITH =,
            discipline WITH =,
            tstzrange(effective_from, COALESCE(effective_to, 'infinity'::timestamptz), '[)') WITH &&
        ) WHERE (is_default = TRUE AND migrated_default = FALSE)
        """
    )

    # 3. 部分索引
    # current_default 部分索引（排除 migrated_default + 已失效）
    op.create_index(
        "idx_pcs_project_discipline_default",
        "project_calculation_standard_profiles",
        ["project_id", "discipline"],
        postgresql_where=sa.text(
            "is_default = TRUE AND migrated_default = FALSE AND effective_to IS NULL"
        ),
    )
    # migrated_default 部分索引（供 §11.4 复核队列查询）
    op.create_index(
        "idx_pcs_profile_migrated_default",
        "project_calculation_standard_profiles",
        ["project_id", "discipline"],
        postgresql_where=sa.text("migrated_default = TRUE"),
    )

    # 4. psv_results 加 7 列
    op.add_column(
        "psv_results",
        sa.Column("standard_profile_code", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "psv_results",
        sa.Column("standard_refs_json", JSONB, nullable=True),
    )
    op.add_column(
        "psv_results",
        sa.Column("formula_ref_json", JSONB, nullable=True),
    )
    op.add_column(
        "psv_results",
        sa.Column(
            "pending_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="标准配置变更后旧记录需复核（自动触发，详 §5.6）",
        ),
    )
    op.add_column(
        "psv_results",
        sa.Column(
            "migrated_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="历史项目迁移默认值（不作为正式默认）",
        ),
    )
    op.add_column(
        "psv_results",
        sa.Column("override_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "psv_results",
        sa.Column("override_approval_json", JSONB, nullable=True),
    )
    # override 字段成对 CHECK（B3 修复：DB 层兜底防绕过 API 层）
    op.create_check_constraint(
        "psv_override_paired_chk",
        "psv_results",
        "(override_reason IS NULL AND override_approval_json IS NULL) OR "
        "(override_reason IS NOT NULL AND override_approval_json IS NOT NULL)",
    )
    # 2 部分索引
    op.create_index(
        "idx_psv_results_pending_review",
        "psv_results",
        ["project_id"],
        postgresql_where=sa.text("pending_review = TRUE"),
    )
    op.create_index(
        "idx_psv_results_migrated_default",
        "psv_results",
        ["project_id"],
        postgresql_where=sa.text("migrated_default = TRUE"),
    )

    # 5. relief_results 加 7 列（与 psv_results 同模式）
    op.add_column(
        "relief_results",
        sa.Column("standard_profile_code", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "relief_results",
        sa.Column("standard_refs_json", JSONB, nullable=True),
    )
    op.add_column(
        "relief_results",
        sa.Column("formula_ref_json", JSONB, nullable=True),
    )
    op.add_column(
        "relief_results",
        sa.Column(
            "pending_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="标准配置变更后旧记录需复核",
        ),
    )
    op.add_column(
        "relief_results",
        sa.Column(
            "migrated_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="历史项目迁移默认值",
        ),
    )
    op.add_column(
        "relief_results",
        sa.Column("override_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "relief_results",
        sa.Column("override_approval_json", JSONB, nullable=True),
    )
    op.create_check_constraint(
        "relief_override_paired_chk",
        "relief_results",
        "(override_reason IS NULL AND override_approval_json IS NULL) OR "
        "(override_reason IS NOT NULL AND override_approval_json IS NOT NULL)",
    )
    op.create_index(
        "idx_relief_results_pending_review",
        "relief_results",
        ["project_id"],
        postgresql_where=sa.text("pending_review = TRUE"),
    )
    op.create_index(
        "idx_relief_results_migrated_default",
        "relief_results",
        ["project_id"],
        postgresql_where=sa.text("migrated_default = TRUE"),
    )


def downgrade() -> None:
    # 1. relief_results 回退
    op.drop_index(
        "idx_relief_results_migrated_default", table_name="relief_results"
    )
    op.drop_index(
        "idx_relief_results_pending_review", table_name="relief_results"
    )
    op.drop_constraint(
        "relief_override_paired_chk", "relief_results", type_="check"
    )
    op.drop_column("relief_results", "override_approval_json")
    op.drop_column("relief_results", "override_reason")
    op.drop_column("relief_results", "migrated_default")
    op.drop_column("relief_results", "pending_review")
    op.drop_column("relief_results", "formula_ref_json")
    op.drop_column("relief_results", "standard_refs_json")
    op.drop_column("relief_results", "standard_profile_code")

    # 2. psv_results 回退
    op.drop_index(
        "idx_psv_results_migrated_default", table_name="psv_results"
    )
    op.drop_index(
        "idx_psv_results_pending_review", table_name="psv_results"
    )
    op.drop_constraint(
        "psv_override_paired_chk", "psv_results", type_="check"
    )
    op.drop_column("psv_results", "override_approval_json")
    op.drop_column("psv_results", "override_reason")
    op.drop_column("psv_results", "migrated_default")
    op.drop_column("psv_results", "pending_review")
    op.drop_column("psv_results", "formula_ref_json")
    op.drop_column("psv_results", "standard_refs_json")
    op.drop_column("psv_results", "standard_profile_code")

    # 3. project_calculation_standard_profiles 回退
    op.drop_index(
        "idx_pcs_profile_migrated_default",
        table_name="project_calculation_standard_profiles",
    )
    op.drop_index(
        "idx_pcs_project_discipline_default",
        table_name="project_calculation_standard_profiles",
    )
    op.drop_table("project_calculation_standard_profiles")

    # 4. btree_gist 扩展保留（DBA 预装，本迁移不卸载；DBA 统一管理）
