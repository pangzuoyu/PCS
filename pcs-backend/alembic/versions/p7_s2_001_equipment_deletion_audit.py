"""equipment_deletion_audit 表 (F-P2-009 fix / P3 登记项).

设备 (equipment_list) 删除时, utility_power_items / utility_fuel_gas /
utility_heat_exchange 3 表的 equipment_id FK 因 ondelete=SET NULL 静默解耦,
无 audit log. 本表记录删除前快照, 用于:
1. 数据溯源: 谁删的 / 何时删的 / 影响哪些 utility_* 记录
2. 合规审计: 满足 R1 §3 数据完整性要求
3. 风险告警: orphan utility_* 记录监控

设计要点 (P7 Sprint 2 落地, 与 Sprint 1 audit_logs 共存):
- 不合并到 audit_logs (后者只记认证/安全, 关注 user_id/action/resource)
- equipment_deletion_audit 关注数据完整性 (业务字段 + orphan 列表)
- JSONB orphan_records 存被 SET NULL 的 utility_* record_id 列表
- 加 (project_id, equipment_id) 复合索引 + occurred_at 倒序索引
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "p7_s2_001"
down_revision: str | None = "p7_open_014"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "equipment_deletion_audit",
        sa.Column("audit_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "equipment_id", UUID(as_uuid=True), nullable=False,
            comment="被删除设备 ID (FK 已无, 存快照)",
        ),
        sa.Column(
            "project_id", UUID(as_uuid=True), nullable=False,
            comment="项目 ID (删时快照)",
        ),
        sa.Column(
            "workspace_id", UUID(as_uuid=True), nullable=False,
            comment="workspace ID",
        ),
        sa.Column(
            "equipment_tag", sa.String(64), nullable=False,
            comment="设备位号快照 (删时)",
        ),
        sa.Column(
            "deleted_by", UUID(as_uuid=True), nullable=False,
            comment="删除操作者 user_id",
        ),
        sa.Column(
            "orphan_records", JSONB(astext_type=sa.Text()), nullable=False,
            comment=(
                "被 SET NULL 的 utility_* 记录: "
                "{power_items: [...], fuel_gas: [...], heat_exchange: [...]}"
            ),
        ),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "reason", sa.String(500), nullable=True,
            comment="删除原因 (可选, 用户备注)",
        ),
    )
    # 复合索引: 按项目查某设备的删除历史
    op.create_index(
        "ix_equipment_deletion_audit_project_equipment",
        "equipment_deletion_audit",
        ["project_id", "equipment_id"],
    )
    # 时间倒序索引: 审计报表 / 倒序翻页
    op.create_index(
        "ix_equipment_deletion_audit_occurred_at_desc",
        "equipment_deletion_audit",
        [sa.text("occurred_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_equipment_deletion_audit_occurred_at_desc",
        table_name="equipment_deletion_audit",
    )
    op.drop_index(
        "ix_equipment_deletion_audit_project_equipment",
        table_name="equipment_deletion_audit",
    )
    op.drop_table("equipment_deletion_audit")
