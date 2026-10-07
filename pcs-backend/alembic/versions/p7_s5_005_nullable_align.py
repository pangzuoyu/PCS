"""p7_s5_005: 对齐 23 列的可空性 —— 消除 `alembic check` 的 modify_nullable 漂移.

发现路径: 2026-10-07 索引漂移核销后 `alembic check` 露出的 23 条 modify_nullable。
**两个方向都有，不是单边的 ORM 落后**，故分两组处理。

## 组 A：16 列 —— 收紧 DB（ORM 是对的）

DB 允许 NULL，ORM 声明 NOT NULL。逐个查过写入路径，**ORM 的意图成立**：

- `cost_correlations.created_at` / `pipe_e_modulus.updated_at` —— 时间戳列，
  且前者 ORM 侧还带 `now()` 默认。created_at 为 NULL 本身就是洞。
- `cv_results.{Cv_calculated, fluid_phase, P1_pa, P2_pa, T1_k, valve_type}`
  —— 计算列，服务层以必填位置参数 / `payload[...]` 下标传入
  （缺键会 KeyError 而非静默 NULL）。
- `restriction_results.{beta_ratio, C_discharge, delta_P_pa, device_type,
  D_pipe_m, d_solved_m}` —— 同上，`restriction_persist.py:92,164-166`
  用 `payload["..."]` 直取。
- `project_pipe_classes.{class_name, override_json}` ——
  `pipe_class_service.py:596,626,597,627` 两个构造点均显式赋值。

## 组 B：7 列 —— 放松 DB（DB 侧的异类，ORM 跟随全库多数派）

DB 是 NOT NULL，ORM 是 nullable。查全库分布后判定 **DB 才是异类**：

- `updated_at`：全库 **67 张 nullable vs 7 张 NOT NULL**
- `hash_changed`：全库 **18 张 nullable vs 3 张 NOT NULL**

这 7 张来自 Sprint 2 `SUP-002`（pipe_codes 批）与 `RecordMixin` 早期建表，
与 `TimestampMixin.updated_at`（`Mapped[datetime | None]`，docstring 只说
"onupdate 自动更新"，未提 NOT NULL）的意图不符。改 DB 而非改 mixin ——
改 mixin 会波及另外 85 张表。

⚠️ 这 7 列**都带 server_default**（`now()` / `false`），所以 DROP NOT NULL
只是放开约束，**默认值仍在**，取值照旧由 DB 填。

## 前置核查

pcs 库相关 8 张表**全部 0 行**（cost_correlations / cv_results /
filtration_results / open_channel_results / pipe_code_templates /
pipe_e_modulus / project_pipe_classes / project_pipe_code_configs /
project_stream_symbols / project_template_pipe_classes /
restriction_results / stream_symbols），
故组 A 的 SET NOT NULL 无 NULL 数据阻挡。若某环境已有 NULL 值，
PG 会报错并回滚（事务性 DDL），届时需先清理。

Revision ID: p7_s5_005
Revises: p7_s5_004
Create Date: 2026-10-07
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s5_005"
down_revision = "p7_s5_004"
branch_labels = None
depends_on = None

# 组 A：收紧（ORM 声明 NOT NULL，DB 允许 NULL）—— ORM 意图已逐个查证
_SET_NOT_NULL: tuple[tuple[str, str], ...] = (
    ("cost_correlations", "created_at"),
    ("cv_results", "Cv_calculated"),
    ("cv_results", "fluid_phase"),
    ("cv_results", "P1_pa"),
    ("cv_results", "P2_pa"),
    ("cv_results", "T1_k"),
    ("cv_results", "valve_type"),
    ("pipe_e_modulus", "updated_at"),
    ("project_pipe_classes", "class_name"),
    ("project_pipe_classes", "override_json"),
    ("restriction_results", "beta_ratio"),
    ("restriction_results", "C_discharge"),
    ("restriction_results", "delta_P_pa"),
    ("restriction_results", "device_type"),
    ("restriction_results", "D_pipe_m"),
    ("restriction_results", "d_solved_m"),
)

# 组 B：放松（DB 是异类，回归全库多数派）—— 全部保留 server_default
_DROP_NOT_NULL: tuple[tuple[str, str], ...] = (
    ("filtration_results", "hash_changed"),
    ("open_channel_results", "hash_changed"),
    ("pipe_code_templates", "updated_at"),
    ("project_pipe_code_configs", "updated_at"),
    ("project_stream_symbols", "updated_at"),
    ("project_template_pipe_classes", "updated_at"),
    ("stream_symbols", "updated_at"),
)


def upgrade() -> None:
    """组 A 收紧 16 列，组 B 放松 7 列.

    用 `ALTER COLUMN ... SET/DROP NOT NULL` 而非 op.alter_column：
    PG 对已是目标状态的列重复执行不报错，故天然幂等。
    """
    for table, column in _SET_NOT_NULL:
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET NOT NULL')
    for table, column in _DROP_NOT_NULL:
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP NOT NULL')


def downgrade() -> None:
    """反向还原（两组的 server_default 均不受影响）."""
    for table, column in reversed(_DROP_NOT_NULL):
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET NOT NULL')
    for table, column in reversed(_SET_NOT_NULL):
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP NOT NULL')
