"""ORM↔DB 元数据 drift 守卫（bug-101/bug-102 防回归）。

背景（2026-09-26 收口）：

- bug-101：ORM ``RecordMixin`` 在 20 张记录表映射 P4-0-1 审计三件套，
  历史迁移只落 15 表 → 5 张旧表真 PG INSERT 必炸（sqlite 测试掩盖）。
- bug-102：修 bug-101 时手写表名清单又漏 ``sep_equip_results`` 等 3 表。

教训：drift 清单必须从 ORM metadata **程序化生成**。本测试把该对比
固化为守卫：对齐后的 pcs_test 真库逐表逐列对比 ORM ``Base.metadata``，
任何"ORM 映射了而库里没有"的表/列直接失败，附带完整差异清单。

方向约定：只查 ORM → DB（缺表/缺列 = drift）。DB 独有对象不查
（``alembic_version`` 由 alembic 管理；server 端触发器/约束等非 ORM
职责）。

跑前需（CLAUDE.md 测试前检查）：
    DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test \\
        uv run alembic upgrade head
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine

import app.models  # noqa: F401  # 触发全部 ORM 注册
from app.core.config import get_settings
from app.db.base import Base

# 安全守卫：仅当 database_url 指向 pcs_test 才执行（与 roundtrip 测试同模式）
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason="drift 守卫需已对齐的 pcs_test 真库；"
           "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test",
)


@_ONLY_PCS_TEST
def test_orm_columns_exist_in_db() -> None:
    """ORM 映射的每张表每一列都必须存在于 pcs_test 真库（零 drift）。"""
    url = get_settings().database_url
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            db_tables = {
                row[0]
                for row in conn.exec_driver_sql(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            }

            drifts: list[str] = []
            for name, table in sorted(Base.metadata.tables.items()):
                if name not in db_tables:
                    drifts.append(f"表缺: {name}（ORM 已映射，库中不存在）")
                    continue
                db_cols = {
                    row[0]
                    for row in conn.exec_driver_sql(
                        "SELECT column_name FROM information_schema.columns "
                        f"WHERE table_name = '{name}'"
                    )
                }
                missing = sorted(set(table.columns.keys()) - db_cols)
                if missing:
                    drifts.append(f"{name} 缺列: {missing}")
    finally:
        engine.dispose()

    assert not drifts, (
        "ORM↔DB drift 检出（bug-101/bug-102 模式回归）：\n  "
        + "\n  ".join(drifts)
        + "\n修复方式：新增 alembic 矫正迁移补列（沿 p6_5_005/006 先例），"
        "勿手改 ORM。"
    )
