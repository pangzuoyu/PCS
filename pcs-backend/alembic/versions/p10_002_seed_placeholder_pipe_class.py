"""p10_002：种「占位管级」`CS-STD`（P10-B 评审 #2 · P1 · A1 裁决后的人裁决）。

## 为什么

`piping_results.material_class` 是指向 `pipe_classes.class_id` 的**外键**
⇒ 链计算写死 `"CS-STD"` ⇒ 该行**必须真的存在** ⇒ 否则真库上插记录撞 FK ⇒
**端点 500**（P10-B 的 E2E-003 撞出来的）⇒ ⚠️ 单测走 SQLite（**不强制 FK**）
⇒ 单测照绿、真库每次都炸。

⇒ **人裁决（2026-11-17）**：**迁移种子 + lifespan 幂等 ensure**，
**删掉请求路径写入** ⇒ ⇒ 迁移是配置数据的 canonical 落点（先例：`p9_013`）。

## 形状

照 `PipeClassService.create`（`app/services/pipe_class_service.py`）的语义：
`dn_series_json={"min": int, "max": int}`（**int**）·
`sch_series_json={DN: Sch}`（**字符串**）· `source="COMPANY_STD"` · `status="DRAFT"`。

⚠️ **本文件与 `app/services/pipe_class_service.py::ensure_placeholder_pipe_class`
必须给出行**完全相同**的值**（后者是「迁移没跑 / 行被删」时的兜底）⇒
⇒ 两者的一致性由 **PG 车道**的用例守着。

## 幂等

`ON CONFLICT (class_id) DO NOTHING` ⇒ 重复跑不炸、也不覆盖已有行。
"""
from __future__ import annotations

from alembic import op

revision = "p10_002"
down_revision = "p10_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO pipe_classes (
            class_id, class_name, material_standard, base_material,
            corrosion_allowance, design_pressure, design_temperature,
            fluid_service, allowable_stress_json, dn_series_json, sch_series_json,
            flange_class, fitting_type, branch_table_json,
            source, version, status, created_at, updated_at
        ) VALUES (
            'CS-STD', '碳钢标准（链计算占位）', 'GB/T 150', '20#',
            1.5, 1.0, 60.0, NULL,
            '{"20#": 137.0}'::jsonb,
            '{"min": 15, "max": 600}'::jsonb,
            '{"15": "0.5", "600": "1.2"}'::jsonb,
            'PN16', NULL, NULL,
            'COMPANY_STD', '1', 'DRAFT', now(), now()
        )
        ON CONFLICT (class_id) DO NOTHING
        """
    )


def downgrade() -> None:
    # ⚠️ 只删**自己种的那一行** ⇒ 不碰别的配置行
    op.execute("DELETE FROM pipe_classes WHERE class_id = 'CS-STD'")
