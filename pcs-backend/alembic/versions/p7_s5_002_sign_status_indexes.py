"""p7_s5_002: 补 4 张表的 sign_status 索引（历史迁移遗漏，非有意设计）.

发现路径（2026-10-06 索引漂移核销）: `alembic check` 报 4 条 add_index，逐个对拍 DB 后确认
**DB 真的缺这 4 个索引**，不是命名/表示差异:

| 表 | ORM 声明 | DB | 判定 |
|---|---|---|---|
| column_sizing | ix_column_sizing_sign_status | 无 | 缺 |
| mixer_results | ix_mixer_results_sign_status | 无 | 缺 |
| relief_results | ix_relief_results_sign_status | 无 | 缺 |
| thermosiphon_circulation_results | ix_thermosiphon_circulation_results_sign_status | 无 | 缺 |

判据是「全库 21 张表声明 sign_status 索引，DB 里已有 18 个，唯独这 4 张没有」
（`ix_<table>_sign_status` 命名在全库高度一致），故属**迁移遗漏**而非产品口径分歧 ——
本迁移按既有惯例补齐，不改 ORM。

为什么 sign_status 要索引: 状态机查询与 CIA 传播都按 sign_status 过滤
（如「捞出所有待校核记录」「按 sign_status 统计」），缺索引即全表扫。

Revision ID: p7_s5_002
Revises: p7_s5_001
Create Date: 2026-10-06
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s5_002"
down_revision = "p7_s5_001"
branch_labels = None
depends_on = None

# (索引名, 表名) —— 索引名严格遵循全库既有的 ix_<table>_sign_status 惯例.
_INDEXES = (
    ("ix_column_sizing_sign_status", "column_sizing"),
    ("ix_mixer_results_sign_status", "mixer_results"),
    ("ix_relief_results_sign_status", "relief_results"),
    ("ix_thermosiphon_circulation_results_sign_status",
     "thermosiphon_circulation_results"),
)


def upgrade() -> None:
    """补建 4 个 sign_status 索引（幂等: 已存在则跳过）."""
    for index_name, table in _INDEXES:
        op.create_index(
            index_name, table, ["sign_status"],
            if_not_exists=True,
        )


def downgrade() -> None:
    """删除 4 个 sign_status 索引（幂等）."""
    for index_name, table in reversed(_INDEXES):
        op.drop_index(index_name, table_name=table, if_exists=True)
