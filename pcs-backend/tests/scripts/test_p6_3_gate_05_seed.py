"""P6-3 G-05：filtration_media_library seed 脚本测试。

按 P6 计划 §Task 29 硬性前置 gate G-05：

- 验证 ``scripts/p6_3_gate_05_filtration_media_library_seed.py``：
  - ``--dry-run`` 输出含 5 行合成数据；
  - 真库 upsert 走通（受 ``_ONLY_PCS_TEST`` 守卫约束）；
  - 重复 ``(medium_type, grade)`` 触发 unique 冲突；
  - upsert 不覆盖 ``confirmed_by`` / ``confirmed_at``（mirror G-03
    行为）。

测试模式参照 ``tests/services/test_cepci_seed.py`` 与
``tests/scripts/test_p6_3_gate_04_seed.py``，通过 ``pytest.mark.skipif``
限定 ``database_url`` 指向 pcs_test 库 — 防止误触 pcs 开发库。

注意：

- 本文件路径放在 ``tests/scripts/`` 目录（brief 约定）。
- 每个用例前先 delete 全表，避免上一次 upsert 残留导致断言漂移。
"""
from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

# 允许直接 ``python -m pytest`` 或 ``uv run pytest`` 调用 seed 脚本子进程。
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import (  # noqa: E402
    dispose_engines_async,
    get_async_session_factory,
)
from app.models.config import FiltrationMediaLibrary  # noqa: E402
from scripts.p6_3_gate_05_filtration_media_library_seed import (  # noqa: E402
    SYNTHETIC_FILTER_MEDIA,
)

# 安全守卫：仅 pcs_test 库允许跑（防误触 pcs 开发库；与
# tests/models/test_alembic_roundtrip.py:_ONLY_PCS_TEST 同源约束）。
_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason=(
        "seed 测试仅允许 pcs_test 库（防误触 pcs 开发库）；"
        "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test"
    ),
)


@pytest_asyncio.fixture(autouse=True)
async def _reset_async_engine() -> AsyncIterator[None]:
    """每个用例 reset 全局 async engine（绑定当前 event loop）。"""
    await dispose_engines_async()
    yield
    await dispose_engines_async()


@pytest_asyncio.fixture
async def clean_filtration_media_table() -> AsyncIterator[None]:
    """每次用例前清空 filtration_media_library（保证测试可重复，幂等）。"""
    factory = get_async_session_factory()
    async with factory() as session:
        await session.execute(delete(FiltrationMediaLibrary))
        await session.commit()
    yield


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_filtration_media_dry_run_print(
    clean_filtration_media_table: None,
) -> None:
    """执行 ``--dry-run`` 子进程 + 验证输出含 5 行 + 未连接 DB。

    ``brief`` 要求 ≥5 行；脚本预期 5 行（SAND / ANTHRACITE / CARBON /
    RUTH_FILTER_CLOTH / ERGUN_PACKING）；同时校验 ``source`` 字段全部
    为 ``SYNTHETIC_TEST_DATA``（合成标记）。
    """
    import subprocess

    script_path = _BACKEND_ROOT / "scripts" / "p6_3_gate_05_filtration_media_library_seed.py"
    result = subprocess.run(
        [sys.executable, str(script_path), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"seed 脚本 --dry-run 失败：\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "[DRY-RUN]" in result.stdout
    assert "未连接数据库，未写入任何行。" in result.stdout
    # 5 行合成数据输出
    for row in SYNTHETIC_FILTER_MEDIA:
        assert row["medium_type"] in result.stdout
        assert row["grade"] in result.stdout
        assert row["source"] in result.stdout

    # DB 内仍然为空（--dry-run 不连接 DB）
    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(select(FiltrationMediaLibrary))
        ).scalars().all()
    assert len(rows) == 0


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_filtration_media_upsert_unique_constraint(
    clean_filtration_media_table: None,
) -> None:
    """执行 seed 脚本子进程 + 验证 ``filtration_media_library`` 载入 ≥5 行 + 二次 upsert 不报错。

    upsert 语义：按 ``(medium_type, grade)`` 唯一索引 ``ON CONFLICT DO UPDATE``；
    二次执行应幂等（同一唯一键命中 → 更新），不抛 unique 冲突。
    """
    import subprocess

    script_path = _BACKEND_ROOT / "scripts" / "p6_3_gate_05_filtration_media_library_seed.py"

    # 第一次 upsert
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"seed 脚本首次 upsert 失败：\nstdout={result.stdout}\nstderr={result.stderr}"
    )

    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(
                select(FiltrationMediaLibrary).order_by(
                    FiltrationMediaLibrary.medium_type, FiltrationMediaLibrary.grade,
                )
            )
        ).scalars().all()

    # brief 要求 ≥5 行；脚本预期 5 行
    assert len(rows) >= 5
    assert len(rows) == len(SYNTHETIC_FILTER_MEDIA), (
        f"期望载入 {len(SYNTHETIC_FILTER_MEDIA)} 行，实际 {len(rows)} 行"
    )
    # 合成标记全部命中 brief
    assert all(row.source == "SYNTHETIC_TEST_DATA" for row in rows)
    # (medium_type, grade) 与合成数据一致
    assert {(row.medium_type, row.grade) for row in rows} == {
        (r["medium_type"], r["grade"]) for r in SYNTHETIC_FILTER_MEDIA
    }
    # nominal_rating_um 与合成数据一致（浮点等值用 1e-6 容差）
    actual_by_key = {
        (row.medium_type, row.grade): row for row in rows
    }
    for r in SYNTHETIC_FILTER_MEDIA:
        actual = actual_by_key[(r["medium_type"], r["grade"])]
        if r["nominal_rating_um"] is None:
            assert actual.nominal_rating_um is None
        else:
            assert abs(actual.nominal_rating_um - r["nominal_rating_um"]) < 1e-6

    # 第二次 upsert：应幂等（同一 (medium_type, grade) → 更新）
    result2 = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result2.returncode == 0, (
        f"seed 脚本二次 upsert 失败：\nstdout={result2.stdout}\nstderr={result2.stderr}"
    )

    async with factory() as session:
        rows2 = (
            await session.execute(select(FiltrationMediaLibrary))
        ).scalars().all()
    # 行数不变（ON CONFLICT DO UPDATE）
    assert len(rows2) == len(SYNTHETIC_FILTER_MEDIA)


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_filtration_media_confirmed_fields_not_overwritten(
    clean_filtration_media_table: None,
) -> None:
    """验证 upsert 不覆盖 ``confirmed_by`` / ``confirmed_at``（mirror G-03）。

    流程：

    1. seed 脚本首次 upsert（合成数据，全部 confirmed 字段为 NULL）；
    2. 人工（测试代码模拟）UPDATE 第一行 ``confirmed_by`` +
       ``confirmed_at`` 为工艺室签字值；
    3. seed 脚本二次 upsert（同一 ``(medium_type, grade)`` → ON
       CONFLICT DO UPDATE）；
    4. 断言第一行 ``confirmed_by`` / ``confirmed_at`` 仍为签字值（**未
       被 upsert 清空**）。
    """
    import subprocess
    from datetime import UTC, datetime

    script_path = _BACKEND_ROOT / "scripts" / "p6_3_gate_05_filtration_media_library_seed.py"

    # 1. 首次 upsert
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"seed 脚本首次 upsert 失败：\nstdout={result.stdout}\nstderr={result.stderr}"
    )

    factory = get_async_session_factory()
    signed_at = datetime(2026, 2, 10, 14, 30, 0, tzinfo=UTC)
    signed_by = "工艺工程师_李四"

    # 2. 模拟工艺室签字
    async with factory() as session:
        target = (
            await session.execute(
                select(FiltrationMediaLibrary).where(
                    FiltrationMediaLibrary.medium_type == "SAND",
                    FiltrationMediaLibrary.grade == "#20-30",
                )
            )
        ).scalars().one()
        target.confirmed_by = signed_by
        target.confirmed_at = signed_at
        await session.commit()
        target_media_id = target.media_id

    # 3. 二次 upsert
    result2 = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result2.returncode == 0, (
        f"seed 脚本二次 upsert 失败：\nstdout={result2.stdout}\nstderr={result2.stderr}"
    )

    # 4. 断言 confirmed_by / confirmed_at 未被覆盖
    async with factory() as session:
        after = (
            await session.execute(
                select(FiltrationMediaLibrary)
                .where(FiltrationMediaLibrary.media_id == target_media_id)
            )
        ).scalars().one()
    assert after.confirmed_by == signed_by, (
        f"confirmed_by 被覆盖：actual={after.confirmed_by} expected={signed_by}"
    )
    assert after.confirmed_at == signed_at, (
        f"confirmed_at 被覆盖：actual={after.confirmed_at} expected={signed_at}"
    )