"""G-07 psychro_results schema drift 守护。

背景（2026-11-15 P6-9-PICKUP-3 T2 收口）：

- ``psychro_results`` 表 PK 列名 = ``psychro_id``（DICT V3.3；P5-0-4a 矫正迁移
  ``psychro_calc_id`` → ``psychro_id``），ORM 字段一致。
- 历史教训：pcs_test 库矫正迁移只部分落地，``psychro_results`` 表 PK 列名仍
  为 ``psychro_calc_id`` → ORM INSERT 抛 UndefinedColumnError，3 个
  G-07 persist 集成测试（``test_save_psychro_result_g07_real_pcs_test`` /
  ``test_save_saturation_w_calc_g07_real_pcs_test`` /
  ``test_save_saturation_w_with_other_fields_preserves_nulls``）全挂。

本测试固化为 CI 守护：

- **ORM 端**：``PsychroResult.__table__`` 必含 ``psychro_id`` PK（与 DICT V3.3
  对齐），且不含遗留 ``psychro_calc_id``。
- **DB 端（pcs_test）**：``information_schema.columns`` 中
  ``psychro_results.psychro_id`` 必须存在；任一缺失即 G-07 漂移回归。

ORM↔DB 全库 drift 由 ``tests/models/test_orm_db_drift.py`` 覆盖；
本测试为 psychro 单一表的快速定向守卫（避免整库扫描）。

修复路径（重现漂移时）：

1. ``cd pcs-backend && DATABASE_URL=...pcs_test uv run alembic upgrade head``
   （矫正迁移从历史断点续推；若 pcs_test alembic_version 表 ``version_num``
   列宽不足 64，先 ``ALTER TABLE alembic_version ALTER COLUMN version_num
   TYPE VARCHAR(64)``）。
2. 重跑本测试 + G-07 三件套验证。

不要做的事：

- 不要回退 ORM 字段名到 ``psychro_calc_id``（违反 DICT V3.3，
  ``test_p5_0_4a_pk_rename`` 架构守卫会失败）。
- 不要新增 ``psychro_calc_id`` 别名列（DB 唯一名 = ``psychro_id``）。

跑前：与 G-07 三件套同源约束，仅 pcs_test 库运行。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.models.calc import PsychroResult

# 安全守卫：仅当 database_url 指向 pcs_test 才执行（与 G-07 三件套同源约束）
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason=(
        "G-07 psychro schema drift 守护仅允许 pcs_test 库；"
        "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test"
    ),
)


@_ONLY_PCS_TEST
def test_psychro_result_orm_has_psychro_id_pk() -> None:
    """ORM 端：PsychroResult.__table__ 必须含 psychro_id PK，不含 psychro_calc_id。

    DICT V3.3 §4.1 字典约定：TaggedRecordMixin 表 PK 命名 = ``*_id``
    （不带 ``_calc`` 后缀）；P5-0-4a 矫正迁移方向锁定，禁止回退。
    """
    cols = frozenset(PsychroResult.__table__.columns.keys())
    assert "psychro_id" in cols, (
        "PsychroResult ORM 必须含 psychro_id PK（DICT V3.3；"
        "P5-0-4a 矫正迁移方向）"
    )
    assert "psychro_calc_id" not in cols, (
        "PsychroResult ORM 不应含 psychro_calc_id（P5-0-4a 已 rename 移除；"
        "如回退，违反 DICT V3.3 字典约定）"
    )


@_ONLY_PCS_TEST
def test_psychro_results_table_has_psychro_id_column_in_pcs_test() -> None:
    """DB 端：pcs_test.psychro_results 表必须有 psychro_id 列（无 _calc 后缀）。

    失败即 G-07 漂移：矫正迁移未完全落地到 pcs_test 库，需按模块 docstring
    修复路径 1 重对齐。
    """
    url = get_settings().database_url
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            db_cols = {
                row[0]
                for row in conn.exec_driver_sql(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'psychro_results'"
                )
            }
    finally:
        engine.dispose()

    assert "psychro_id" in db_cols, (
        "pcs_test.psychro_results 缺 psychro_id 列（G-07 漂移）；"
        "修复路径：DATABASE_URL=...pcs_test uv run alembic upgrade head "
        "（沿 P5-0-4a 矫正迁移方向 psychro_calc_id→psychro_id）。"
        "如 alembic_version.version_num 列宽不足 64，先 ALTER COLUMN TYPE VARCHAR(64)。"
    )
    assert "psychro_calc_id" not in db_cols, (
        "pcs_test.psychro_results 仍含 psychro_calc_id 列（G-07 漂移未清）；"
        "P5-0-4a 矫正迁移未完全落地，需重跑 upgrade head。"
    )
