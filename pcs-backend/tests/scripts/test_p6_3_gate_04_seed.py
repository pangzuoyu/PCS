"""P6-3 G-04：cooling_tower_curves seed 脚本测试。

按 P6 计划 §Task 29 硬性前置 gate G-04：

- 验证 ``scripts/p6_3_gate_04_cooling_tower_curves_seed.py``：
  - ``--dry-run`` 输出含 4 行合成数据；
  - 真库 upsert 走通（受 ``_ONLY_PCS_TEST`` 守卫约束）；
  - 重复 ``(tower_model, source)`` 触发 unique 冲突；
  - upsert 不覆盖 ``confirmed_by`` / ``confirmed_at``（mirror G-03
    ``CepciIndexSeries`` 行为）。

测试模式参照 ``tests/services/test_cepci_seed.py``（真库 async
session + 唯一字段 upsert），通过 ``pytest.mark.skipif`` 限定
``database_url`` 指向 pcs_test 库 — 防止误触 pcs 开发库。

注意：

- 本文件路径放在 ``tests/scripts/`` 目录（brief 约定），与 ``tests/services/``
  互不耦合；纯 ORM 直测 seed 脚本语义。
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
from app.models.config import CoolingTowerCurves  # noqa: E402
from scripts.p6_3_gate_04_cooling_tower_curves_seed import (  # noqa: E402
    SYNTHETIC_CTI_CURVES,
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
    """每个用例 reset 全局 async engine（绑定当前 event loop）。

    ``get_async_session_factory()`` 是模块级单例，跨 event loop 复用会触发
    ``Event loop is closed``。每次用例前 dispose 一次即可。
    """
    await dispose_engines_async()
    yield
    await dispose_engines_async()


@pytest_asyncio.fixture
async def clean_cooling_tower_curves_table() -> AsyncIterator[None]:
    """每次用例前清空 cooling_tower_curves（保证测试可重复，幂等）。"""
    factory = get_async_session_factory()
    async with factory() as session:
        await session.execute(delete(CoolingTowerCurves))
        await session.commit()
    yield


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_cooling_tower_curves_dry_run_print(
    clean_cooling_tower_curves_table: None,
) -> None:
    """执行 ``--dry-run`` 子进程 + 验证输出含 4 行 + 未连接 DB。

    ``brief`` 要求 ≥4 行；脚本预期 4 行；同时校验 ``source`` 字段全部为
    ``SYNTHETIC_TEST_DATA``（合成标记）。
    """
    import subprocess

    script_path = _BACKEND_ROOT / "scripts" / "p6_3_gate_04_cooling_tower_curves_seed.py"
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
    # 4 行合成数据输出（行标题 + 4 数据行）
    for row in SYNTHETIC_CTI_CURVES:
        assert row["tower_model"] in result.stdout
        assert row["source"] in result.stdout

    # DB 内仍然为空（--dry-run 不连接 DB）
    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(select(CoolingTowerCurves))
        ).scalars().all()
    assert len(rows) == 0


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_cooling_tower_curves_upsert_unique_constraint(
    clean_cooling_tower_curves_table: None,
) -> None:
    """执行 seed 脚本子进程 + 验证 ``cooling_tower_curves`` 载入 ≥4 行 + 二次 upsert 不报错。

    upsert 语义：按 ``(tower_model, source)`` 唯一索引 ``ON CONFLICT DO UPDATE``；
    二次执行应幂等（同一唯一键命中 → 更新），不抛 unique 冲突。
    """
    import subprocess

    script_path = _BACKEND_ROOT / "scripts" / "p6_3_gate_04_cooling_tower_curves_seed.py"

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
                select(CoolingTowerCurves).order_by(CoolingTowerCurves.tower_model)
            )
        ).scalars().all()

    # brief 要求 ≥4 行；脚本预期 4 行
    assert len(rows) >= 4
    assert len(rows) == len(SYNTHETIC_CTI_CURVES), (
        f"期望载入 {len(SYNTHETIC_CTI_CURVES)} 行，实际 {len(rows)} 行"
    )
    # 合成标记全部命中 brief
    assert all(row.source == "SYNTHETIC_TEST_DATA" for row in rows)
    # tower_model 与合成数据一致
    assert {row.tower_model for row in rows} == {
        r["tower_model"] for r in SYNTHETIC_CTI_CURVES
    }
    # c_coefficient / m_exponent 与合成数据一致（浮点等值用 1e-6 容差）
    actual_by_model = {row.tower_model: row for row in rows}
    for r in SYNTHETIC_CTI_CURVES:
        actual = actual_by_model[r["tower_model"]]
        assert abs(actual.c_coefficient - r["c_coefficient"]) < 1e-6
        assert abs(actual.m_exponent - r["m_exponent"]) < 1e-6

    # 第二次 upsert：应幂等（同一 (tower_model, source) → 更新）
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
            await session.execute(select(CoolingTowerCurves))
        ).scalars().all()
    # 行数不变（ON CONFLICT DO UPDATE）
    assert len(rows2) == len(SYNTHETIC_CTI_CURVES)


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_cooling_tower_curves_confirmed_fields_not_overwritten(
    clean_cooling_tower_curves_table: None,
) -> None:
    """验证 upsert 不覆盖 ``confirmed_by`` / ``confirmed_at``（mirror G-03）。

    流程：

    1. seed 脚本首次 upsert（合成数据，全部 confirmed 字段为 NULL）；
    2. 人工（测试代码模拟）UPDATE 第一行 ``confirmed_by`` +
       ``confirmed_at`` 为工艺室签字值；
    3. seed 脚本二次 upsert（同一 ``(tower_model, source)`` → ON
       CONFLICT DO UPDATE）；
    4. 断言第一行 ``confirmed_by`` / ``confirmed_at`` 仍为签字值（**未
       被 upsert 清空**）。
    """
    import subprocess
    from datetime import UTC, datetime

    script_path = _BACKEND_ROOT / "scripts" / "p6_3_gate_04_cooling_tower_curves_seed.py"

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
    signed_at = datetime(2026, 1, 15, 9, 0, 0, tzinfo=UTC)
    signed_by = "工艺工程师_张三"

    # 2. 模拟工艺室签字
    async with factory() as session:
        target = (
            await session.execute(
                select(CoolingTowerCurves)
                .where(CoolingTowerCurves.tower_model == "MARLEY-MD-STD")
            )
        ).scalars().one()
        target.confirmed_by = signed_by
        target.confirmed_at = signed_at
        await session.commit()
        target_curve_id = target.curve_id

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
                select(CoolingTowerCurves)
                .where(CoolingTowerCurves.curve_id == target_curve_id)
            )
        ).scalars().one()
    assert after.confirmed_by == signed_by, (
        f"confirmed_by 被覆盖：actual={after.confirmed_by} expected={signed_by}"
    )
    assert after.confirmed_at == signed_at, (
        f"confirmed_at 被覆盖：actual={after.confirmed_at} expected={signed_at}"
    )