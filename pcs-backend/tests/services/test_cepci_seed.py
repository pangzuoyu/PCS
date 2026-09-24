"""G-03 CEPCI seed 测试（P6-2 Task 17，硬性前置 gate）。

测试目的：

- 验证 ``scripts/p6_2_gate_03_cepci_seed.py`` 在真实 pcs_test 库上跑通：
  upsert 后 ``cepci_index_series`` 表内 ≥1 行；
- 验证 alembic 迁移 ``p6_2_gate_03_cepci_seed`` 升级成功（前置条件，
  由 conftest fixture 在模块级 ``alembic upgrade head`` 保证）。

测试模式参照 ``tests/seeds/test_category3_seeds.py``（真库 async
session 工厂 + 唯一字段 upsert），通过 ``pytest.mark.skipif`` 限定
``database_url`` 指向 pcs_test 库 — 防止误触 pcs 开发库。

注意：

- 本文件路径放在 ``tests/services/`` 目录（brief 约定），但实际不依赖
  任何 service 层，纯 ORM 直测 seed 脚本语义。
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
from app.models.config import CepciIndexSeries  # noqa: E402
from scripts.p6_2_gate_03_cepci_seed import SYNTHETIC_CEPCI  # noqa: E402

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
async def clean_cepci_table() -> AsyncIterator[None]:
    """每次用例前清空 cepci_index_series（保证测试可重复，幂等）。

    seed 脚本本身是 upsert，但测试断言「行数 == 合成数据长度」需从 0 起
    算；脚本二次跑只会 do-update 行数不变，故 delete 更直观。
    """
    factory = get_async_session_factory()
    async with factory() as session:
        await session.execute(delete(CepciIndexSeries))
        await session.commit()
    yield


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_cepci_series_loaded(clean_cepci_table) -> None:
    """执行 seed 脚本子进程 + 验证 ``cepci_index_series`` 载入 ≥1 行。

    ``brief`` 要求 ≥1 行；脚本预期 7 行（2018~2024）；同时校验 source
    字段全部为 ``SYNTHETIC_TEST_DATA``（合成标记）与 brief 一致。

    用 ``subprocess.run`` 调用脚本而非直接调函数，避免 seed 脚本的
    main() 内 ``get_settings().database_url`` 与测试进程的 settings
    缓存不一致（lru_cache 单例在跨进程下互不影响）。
    """
    import subprocess

    script_path = _BACKEND_ROOT / "scripts" / "p6_2_gate_03_cepci_seed.py"
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"seed 脚本执行失败：\nstdout={result.stdout}\nstderr={result.stderr}"
    )

    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(select(CepciIndexSeries).order_by(CepciIndexSeries.year))
        ).scalars().all()

    # brief 要求 ≥1 行；脚本预期 7 行 — 两者都断言，确保意图对齐。
    assert len(rows) >= 1, "CEPCI seed 至少应载入 1 行"
    assert len(rows) == len(SYNTHETIC_CEPCI), (
        f"期望载入 {len(SYNTHETIC_CEPCI)} 行，实际 {len(rows)} 行"
    )
    # 合成标记全部命中 brief
    assert all(row.source == "SYNTHETIC_TEST_DATA" for row in rows)
    # 年份与合成数据一致
    assert {row.year for row in rows} == {r["year"] for r in SYNTHETIC_CEPCI}
    # cepci_value 与合成数据一致（浮点等值用 1e-6 容差）
    actual_values = {row.year: row.cepci_value for row in rows}
    expected_values = {r["year"]: r["cepci_value"] for r in SYNTHETIC_CEPCI}
    for year, expected in expected_values.items():
        assert abs(actual_values[year] - expected) < 1e-6, (
            f"year={year} cepci_value 不匹配："
            f"actual={actual_values[year]} expected={expected}"
        )
