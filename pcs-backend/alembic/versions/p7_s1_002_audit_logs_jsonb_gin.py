"""audit_logs.detail_json 加 JSONB GIN 索引（P7-Sprint 1 T0 / D8 裁决 9A）。

优化 detail_json 字段查询（如 WHERE detail_json @> '{stale_resolution_path: ...}'
或按 changed_fields 列表查询）；支持 STALE_RESOLVED 三字段（R-03 T0 落地）的
高频 audit_logs 查询。

索引选项：
- jsonb_path_ops：仅支持 @> containment 操作符；索引体积 ~30% 更小；查询更快
- 默认 GIN：支持所有 jsonb 操作符；索引体积较大

本批选 jsonb_path_ops 因 audit_logs 主流查询是 containment
（按 detail_json 内具体字段值查），与 R-03 T0 三字段写入路径契合。
Sprint 4 monthly partition 后此索引会随 partition 自动继承。
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p7_s1_002"
# 当前 head 是 p7_s1_005（util_results）；本 D8 gap 补在 T0 落地后立即执行，
# 但 filename 沿用 plan V2.2 指定的 p7_s1_002_audit_logs_jsonb_gin.py
# M3 fix: filename p7_s1_002 编号 < p7_s1_005 chain 顺序（p7_s1_002 在 p7_s1_005 之后落）；
# 此处故意保留 plan V2.2 指定文件名，避免 alembic rename 风险。Future plan revision
# 应统一编号规则。
down_revision: str | None = "p7_s1_005"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # F-P0-005 修复：CONCURRENTLY 不能在 alembic transaction 内跑；
    # 必须先 COMMIT 退出当前事务，再 CONCURRENTLY 建索引，最后再开新事务。
    # See: https://alembic.sqlalchemy.org/en/latest/cookbook.html#create-index-concurrently
    op.execute("COMMIT")
    op.create_index(
        "ix_audit_logs_detail_json_gin",
        "audit_logs",
        ["detail_json"],
        postgresql_using="gin",
        postgresql_ops={"detail_json": "jsonb_path_ops"},
        postgresql_concurrently=True,
    )


def downgrade() -> None:
    # 与 upgrade 对称：CONCURRENTLY drop 也需 COMMIT 退出事务
    op.execute("COMMIT")
    op.drop_index(
        "ix_audit_logs_detail_json_gin",
        table_name="audit_logs",
        postgresql_concurrently=True,
    )
