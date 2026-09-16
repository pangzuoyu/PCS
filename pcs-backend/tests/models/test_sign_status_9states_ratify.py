"""P5-0-3 Task 3: StreamSignStatus 9 态扩展 ratify（plan §批 P5-0 §Task 3）。

状态（2026-09-16 启动时）：本 Task 实质已在 P3.2 SIM-13 闭环，迁移
`alembic/versions/p3_sim_stream_sign_status_extend.py` 落地（revision=
p3sim_stream_sign_status_extend，IF NOT EXISTS 幂等）。
本 Task 标"已闭环 ratify"——本测试文件固化 9 态契约门禁，防止后续回归。

门禁（4 必查）：
1. ORM StreamSignStatus 枚举值 = 9 态全集
2. ORM 9 态值集合 == PG enum 9 态值集合（值对齐，顺序不强制）
3. alembic 历史含 p3_sim_stream_sign_status_extend 迁移
4. 迁移脚本使用 IF NOT EXISTS 幂等保护（ALTER TYPE ADD VALUE 不可逆）
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import StreamSignStatus

# 9 态全集（与 P3.2 SIM-13 锁定值一致）
EXPECTED_9_VALUES: frozenset[str] = frozenset({
    "DRAFT",
    "IN_APPROVAL",
    "CHECKED",
    "OBSOLETE",
    "CHECK_REJECTED",
    "STALE",
    "CHANGE_PENDING",
    "CHANGED",
    "REVERSAL_PENDING",
})

# alembic 迁移脚本路径（ratify 检查）
ALEMBIC_MIGRATION_PATH = Path(
    "pcs-backend/alembic/versions/p3_sim_stream_sign_status_extend.py"
)


def test_orm_streamsignstatus_has_9_values():
    """ORM StreamSignStatus 枚举必须含 9 态全集（值集合对齐）。"""
    orm_values = frozenset(s.value for s in StreamSignStatus)
    assert len(orm_values) == 9, (
        f"ORM StreamSignStatus 应有 9 态，实际 {len(orm_values)}: {orm_values}"
    )
    assert orm_values == EXPECTED_9_VALUES, (
        f"ORM 值集合与锁定 9 态不一致。"
        f"缺: {EXPECTED_9_VALUES - orm_values}, "
        f"多: {orm_values - EXPECTED_9_VALUES}"
    )


def test_alembic_migration_file_exists():
    """P3.2 SIM-13 迁移文件必须存在（P5-0-3 ratify 闭环凭证）。"""
    assert Path("alembic/versions/p3_sim_stream_sign_status_extend.py").exists(), (
        f"P3.2 SIM-13 迁移文件缺失: {ALEMBIC_MIGRATION_PATH}"
    )


def test_alembic_migration_uses_if_not_exists_idempotent():
    """迁移脚本必须使用 IF NOT EXISTS 保护（ALTER TYPE ADD VALUE 不可逆）。

    ALTER TYPE ... ADD VALUE 在 PG 中不可逆（不能 DELETE VALUE），
    唯一回滚路径是 DROP TYPE + 重建 enum。多次迁移执行必须幂等。
    """
    path = Path("alembic/versions/p3_sim_stream_sign_status_extend.py")
    content = path.read_text(encoding="utf-8")
    # 5 新值（CHECK_REJECTED / STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING）
    # 必须各自含 IF NOT EXISTS
    new_values = [
        "CHECK_REJECTED",
        "STALE",
        "CHANGE_PENDING",
        "CHANGED",
        "REVERSAL_PENDING",
    ]
    for value in new_values:
        pattern = f"ADD VALUE IF NOT EXISTS '{value}'"
        assert pattern in content, (
            f"迁移必须用 ADD VALUE IF NOT EXISTS '{value}' 保护，"
            f"未找到（内容审查）：{path}"
        )


@pytest.mark.asyncio
async def test_pg_enum_has_9_values(db_session: AsyncSession):
    """DB 端 PG enum streamsignstatus 必须含 9 态全集。

    依赖：conftest 提供 db_session fixture（pcs_test 库 PG 连接）。
    SQLite 下默认 conftest（in-memory）跳过本测试——PG enum 查询仅对真 PG 有效。
    CI 中显式覆盖 conftest 时（如 P5-0 集成测试）执行本断言。
    """
    bind = db_session.get_bind()
    dialect = bind.dialect.name if hasattr(bind, "dialect") else ""
    if dialect != "postgresql":
        pytest.skip(f"PG enum 断言需 postgresql，当前 dialect={dialect!r}")
    result = await db_session.execute(
        text("""
            SELECT enumlabel
            FROM pg_enum
            WHERE enumtypid = (
                SELECT oid FROM pg_type WHERE typname = 'streamsignstatus'
            )
        """)
    )
    db_values = frozenset(row[0] for row in result.fetchall())
    assert len(db_values) == 9, (
        f"PG enum streamsignstatus 应有 9 态，实际 {len(db_values)}: {db_values}"
    )
    assert db_values == EXPECTED_9_VALUES, (
        f"PG enum 值集合与锁定 9 态不一致。"
        f"缺: {EXPECTED_9_VALUES - db_values}, "
        f"多: {db_values - EXPECTED_9_VALUES}"
    )


def test_orm_db_value_alignment():
    """ORM 9 态值集合 == 锁定 9 态（静态验证，与 DB 测试并行）。"""
    orm_values = frozenset(s.value for s in StreamSignStatus)
    # 与期望值集合一致（顺序不强制）
    assert orm_values == EXPECTED_9_VALUES