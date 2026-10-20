"""P9A-5 Task B：cost_est_results 补 project_id（项目隔离键）。

## 为什么这张表要单独补

`class CostEstResult(Base)`（`app/models/calc.py:1193`）**不继承**任何 mixin
⇒ 没有 `project_id` / `workspace_id` / `sign_status`。
⇒ `app/api/v1/cost_est.py` 的 **8 个端点全部没有项目鉴权**
（实测 `grep check_project_access_or_404 app/api/v1/cost_est.py` → 0 命中），
且通用守卫 `check_record_access_or_404` 读的是 `record.project_id`
⇒ 守卫**连挂都挂不上**。

最宽的一条是**读面**：`GET /cost-est/results` 不传参时
`list_cost_est_results_service` 走「不传 = 全量」⇒ **整表返回**
⇒ 跨项目数据泄漏（信息本身，不只是可写性）。

## 为什么是补列而不是 JOIN `equipment_list.project_id`

`equipment_id` 是 `equipment_list` 的 PK 且在 cost_est 上 UNIQUE，
`equipment_list.project_id` NOT NULL ⇒ **JOIN 反查是可行的**。但：

1. 守卫 helper `check_record_access_or_404` 读 `record.project_id` ⇒ JOIN 要
   另写一条守卫路径（6 张表里 5 张走通用路径 ⇒ 多一条分叉）；
2. `GET /results` 的**项目过滤**也要 JOIN 才能做；
3. **三处既有裁决一致**要求补列：`ADR-0050:403` / `:477` +
   `TODOS.md` TODO-048「归属：P9A（`cost_est_results` 补列时一并处理）」。

## ⚠️ 冗余列的漂移风险与它的唯一同步点

补列意味着「行的 project」是**冗余**的（设备本身已带 project）。
漂移路径 = **设备被改到别的项目** ⇒ 实测**当前没有任何端点
UPDATE `equipment_list.project_id`** ⇒ 现实中不可达。
唯一的同步点是**创建路径从 equipment 复制**（见
`cost_est_persist_service._ensure_equipment_exists` 返回 project_id）
⇒ 由 `tests/api/v1/test_cost_est_project_isolation.py::
test_created_row_takes_its_project_from_the_equipment` 钉住。

## ⚠️ 为什么**不**补 workspace_id / sign_status / updated_at

该表的设计是「与设备 1:1、状态跟随设备」（模型 docstring +
`cost_est_persist_service.py:12` 的模块说明）⇒ 补这三列是**另一套设计**。
特别是 `updated_at`：补它会让 ADR-0048 §⑥ 的退化阶梯对它有**两档**，
而 `TABLE_CAPABILITIES` 现在显式登记 `has_updated_at=False`
（且 `tests/alembic/test_p9_006_cost_est_record_hash.py:90` 钉住
「cost_est_results 无 updated_at」）⇒ 保持一档。

## 回填为什么在迁移里做

与 `p9_006` 同理：本仓吃过「守门没跑却看着是绿的」亏 ⇒ 升级路径必须自带回填。
回填用 `UPDATE ... FROM equipment_list`（**纯 SQL**，不 import app 模型 ——
迁移里跑 ORM 查询要处理 alembic 事务/SAVEPOINT，而这里一条 SQL 就够）。

## Revision

`revision = p9_007`，`down_revision = p9_006`（当前 head）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p9_007"
down_revision = "p9_006"
branch_labels = None
depends_on = None

_CONSTRAINT = "fk_cost_est_results_project_id_projects"
_INDEX = "ix_cost_est_results_project_id"


def upgrade() -> None:
    """加列（先 nullable）→ 回填 → 改 NOT NULL → FK + 索引。

    ⚠️ 分四步而不是「加 NOT NULL 列 + server_default」：NOT NULL 列必须给
    default，而 default 造出来的 project_id 是**假值**（uuid 0 或类似）
    ⇒ 必须先 nullable 回填再收紧，否则会出现一批「有 project 但不是它的
    项目」的假归属。
    """
    op.add_column(
        "cost_est_results",
        sa.Column(
            "project_id",
            sa.Uuid(),
            nullable=True,
            comment="项目 ID（FK → projects.project_id；P9A-5 Task B 补，"
            "取自 equipment_list.project_id）",
        ),
    )
    # 回填：从 equipment 复制（同一条 UPDATE ... FROM，幂等）
    op.execute(
        """
        UPDATE cost_est_results AS c
        SET project_id = e.project_id
        FROM equipment_list AS e
        WHERE e.equipment_id = c.equipment_id
          AND c.project_id IS DISTINCT FROM e.project_id
        """
    )
    # ⚠️ 回填后仍可能有 project_id IS NULL（孤儿行：equipment 不存在的行）。
    # FK 本身会挡住这种行；这里显式失败而不是静默留 NULL —— 留 NULL 的行
    # 在守卫里会走到 500 分支（"Record missing project_id"），那是个
    # **运行期才暴露**的坏数据。
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM cost_est_results WHERE project_id IS NULL) THEN
                RAISE EXCEPTION
                    'cost_est_results 存在无法回填 project_id 的孤儿行'
                    '（其 equipment_id 在 equipment_list 里没有对应行）';
            END IF;
        END $$;
        """
    )
    op.alter_column("cost_est_results", "project_id", nullable=False)
    op.create_foreign_key(
        _CONSTRAINT,
        "cost_est_results",
        "projects",
        ["project_id"],
        ["project_id"],
    )
    op.create_index(_INDEX, "cost_est_results", ["project_id"], if_not_exists=True)


def downgrade() -> None:
    """删索引 + FK + 列。

    ⚠️ 数据丢失：回填出来的 project_id 无法恢复（可从 equipment_list 重算）。
    """
    op.drop_index(_INDEX, table_name="cost_est_results", if_exists=True)
    op.drop_constraint(_CONSTRAINT, "cost_est_results", type_="foreignkey")
    op.drop_column("cost_est_results", "project_id")
