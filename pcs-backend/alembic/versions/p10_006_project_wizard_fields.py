"""p10_006：项目向导的字段 —— 单位制词表 + 项目两态 + 模板落库的 7 列（P10-K）。

## 为什么

SPEC §7.5 的「项目向导」要求三件今天**做不到**的事：

1. **单位制切换** ⇒ ⇒ ⇒ `projects.unit_system` 今天只是**自由文本**
   （`str`，min 1 max 20）⇒ ⇒ ⇒ 谁都能塞 `"MKS"` / `"公制"` 进去
   ⇒ ⇒ ⇒ 前端没法拿它当词表用；
2. **项目两态（DRAFT / ACTIVE）** ⇒ ⇒ ⇒ SPEC §12.4 **V1.6 早就承诺过**
   （2026-10-20）⇒ ⇒ ⇒ 但模型里**一直没落地** ⇒ ⇒ ⇒ 本批补上
   ⇒ ⇒ ⇒ ⚠️ **`DRAFT` 不是状态机** —— 今天**没有任何守卫读 `Project.status`**
   ⇒ ⇒ ⇒ 加它**零行为影响** ⇒ ⇒ ⇒ 它只是「向导没走完」的**标签**；
3. **模板落库**（7 段）⇒ ⇒ ⇒ 4 段**今天没有任何消费者**（只出现在
   `app/schemas/project_template.py`）⇒ ⇒ ⇒ 2026-11-25 人裁：**升 6 个标量列**
   ⇒ ⇒ ⇒ **不建 4 张表**（免 JOIN、免外键）⇒ ⇒ ⇒ **不建 JSONB blob**
   （6 个都是标量 ⇒ ⇒ ⇒ 列更好查）⇒ ⇒ ⇒ 另加 1 列 **provenance**。

## 列形状（与 ORM `Project` 逐列一致）

| 列 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `stream_approval_max_depth` | `INTEGER` | ✔ | 物流校对深度 |
| `customer_approval_proxy_allowed` | `BOOLEAN` | ✔ | 客户代录是否允许 |
| `customer_approval_attachment_required` | `BOOLEAN` | ✔ | 客户批准是否必须附附件 |
| `version_sequence_skip_alpha_versions` | `BOOLEAN` | ✔ | 版本序列是否跳过字母版次 |
| `version_sequence_allowed_purposes` | `JSONB` | ✔ | 版本序列允许的用途列表 |
| `reversal_role_reversal_approver_role` | `VARCHAR(20)` | ✔ | 逆审角色 |
| `applied_template_json` | `JSONB` | ✔ | **provenance**（哪个模板/哪一版/何时应用）—— **不承载配置** |

## ⚠️ 两条 `CHECK` 约束

| 约束 | 内容 | 为什么 |
|---|---|---|
| `ck_projects_unit_system` | `unit_system IN ('SI','US')` | 词表在**代码**里（`UnitSystem`）⇒ ⇒ ⇒ CHECK 在**库里** ⇒ ⇒ ⇒ **两处都要有** ⇒ ⇒ ⇒ 只在代码里 ⇒ ⇒ ⇒ 写库的人（脚本 / 迁移）能塞进垃圾值 |
| `ck_projects_status` | `status IN ('DRAFT','ACTIVE')` | 同上 ⇒ ⇒ ⇒ **防止别的环境塞进第三种值** |

⚠️ **加 CHECK 前必须先取证**：既有行若不满足 ⇒ ⇒ ⇒ 加约束**直接失败**
⇒ ⇒ ⇒ 2026-11-25 实测（**两库各一进程**）：`pcs` 1 行 + `pcs_test` 254 行
⇒ ⇒ ⇒ `distinct unit_system` 全是 `['SI']` ⇒ ⇒ ⇒ `distinct status` 全是
`['ACTIVE']` ⇒ ⇒ ⇒ **两库今天加 CHECK 都安全** ⇒ ⇒ ⇒ ⚠️ **别的环境仍须先跑**
`SELECT DISTINCT unit_system, status FROM projects`。

## Revision

`revision = p10_006`，`down_revision = p10_005`（当前 head）。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "p10_006"
down_revision = "p10_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """加 7 列（全可空 ⇒ ⇒ 存量行不需要回填）+ 两条 CHECK。"""
    op.add_column(
        "projects",
        sa.Column("stream_approval_max_depth", sa.Integer(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("customer_approval_proxy_allowed", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("customer_approval_attachment_required", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("version_sequence_skip_alpha_versions", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("version_sequence_allowed_purposes", JSONB(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column(
            "reversal_role_reversal_approver_role", sa.String(length=20), nullable=True
        ),
    )
    op.add_column(
        "projects",
        sa.Column("applied_template_json", JSONB(), nullable=True),
    )
    # ⚠️ CHECK **后加** ⇒ ⇒ ⇒ 存量行已满足（取证见模块 docstring）⇒ ⇒ ⇒ 不会失败
    op.create_check_constraint(
        "ck_projects_unit_system",
        "projects",
        "unit_system IN ('SI', 'US')",
    )
    op.create_check_constraint(
        "ck_projects_status",
        "projects",
        "status IN ('DRAFT', 'ACTIVE')",
    )
    # ⚠️ **`project_templates.status` 的历史值 `ACTIVE` 不在新词表里**
    # ⇒ ⇒ ⇒ 先**映射**再**加 CHECK** ⇒ ⇒ ⇒ 映射成 `DRAFT`
    # ⇒ ⇒ ⇒（映射成 `PUBLISHED` 是**撒谎** —— 没人审核过它）
    # ⇒ ⇒ ⇒ ⇒ 旧模板因此**不进**「已发布」列表 ⇒ ⇒ ⇒ 需要时由运维改状态。
    op.execute(
        "UPDATE project_templates SET status = 'DRAFT' WHERE status = 'ACTIVE'"
    )
    op.create_check_constraint(
        "ck_project_templates_status",
        "project_templates",
        "status IN ('DRAFT', 'PUBLISHED', 'OBSOLETE')",
    )


def downgrade() -> None:
    """反向：先删 CHECK，再删列（**顺序也要一致**）。"""
    op.drop_constraint("ck_project_templates_status", "project_templates", type_="check")
    op.drop_constraint("ck_projects_status", "projects", type_="check")
    op.drop_constraint("ck_projects_unit_system", "projects", type_="check")
    op.drop_column("projects", "applied_template_json")
    op.drop_column("projects", "reversal_role_reversal_approver_role")
    op.drop_column("projects", "version_sequence_allowed_purposes")
    op.drop_column("projects", "version_sequence_skip_alpha_versions")
    op.drop_column("projects", "customer_approval_attachment_required")
    op.drop_column("projects", "customer_approval_proxy_allowed")
    op.drop_column("projects", "stream_approval_max_depth")
