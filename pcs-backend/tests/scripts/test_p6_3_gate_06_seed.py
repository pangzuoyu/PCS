"""P6-3 G-06：flare_radiation_limits seed 脚本测试。

按 P6 计划 §Task 29 硬性前置 gate G-06：

- 验证 ``scripts/p6_3_gate_06_flare_radiation_limits_seed.py``：
  - ``--dry-run`` 输出含 3 行（API 521 §7.4.2.3 BEDD 三档真实限值）；
  - 真库 upsert 走通（受 ``_ONLY_PCS_TEST`` 守卫约束）；
  - 重复 ``limit_type`` 触发 unique 冲突；
  - upsert 不覆盖 ``confirmed_by`` / ``confirmed_at``（mirror G-03
    行为）。

G-06 与 G-04/05 不同：3 行默认数据来自 **API 521 真实公开限值**（非合
成），``source`` 直接填 ``'API521_§7.4.2.3'``；测试仍覆盖 ``confirmed``
字段保护（即使默认数据是真实的，工艺室签字字段也由人工流程维护）。

测试模式参照 ``tests/services/test_cepci_seed.py`` 与
``tests/scripts/test_p6_3_gate_04_seed.py``。
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
from app.models.config import FlareRadiationLimits  # noqa: E402
from scripts.p6_3_gate_06_flare_radiation_limits_seed import (  # noqa: E402
    SYNTHETIC_RADIATION_LIMITS,
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
async def clean_flare_radiation_limits_table() -> AsyncIterator[None]:
    """每次用例前清空 flare_radiation_limits（保证测试可重复，幂等）。"""
    factory = get_async_session_factory()
    async with factory() as session:
        await session.execute(delete(FlareRadiationLimits))
        await session.commit()
    yield


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_flare_radiation_limits_dry_run_print(
    clean_flare_radiation_limits_table: None,
) -> None:
    """执行 ``--dry-run`` 子进程 + 验证输出含 3 行（API 521 BEDD 三档）+ 未连接 DB。

    ``brief`` 要求 3 行；脚本预期 3 行（PROPERTY_LINE / PERSONNEL /
    EMERGENCY）；同时校验 ``source`` 字段全部为 ``API521_§7.4.2.3``（真
    实限值标记，非合成）。
    """
    import subprocess

    script_path = _BACKEND_ROOT / "scripts" / "p6_3_gate_06_flare_radiation_limits_seed.py"
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
    # 3 行真实限值输出
    for row in SYNTHETIC_RADIATION_LIMITS:
        assert row["limit_type"] in result.stdout
        assert row["source"] in result.stdout
    # 数值输出（浮点等值检查 4.73 / 6.31 / 12.6 都出现）
    assert "4.73" in result.stdout
    assert "6.31" in result.stdout
    assert "12.6" in result.stdout

    # DB 内仍然为空（--dry-run 不连接 DB）
    factory = get_async_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(select(FlareRadiationLimits))
        ).scalars().all()
    assert len(rows) == 0


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_flare_radiation_limits_upsert_unique_constraint(
    clean_flare_radiation_limits_table: None,
) -> None:
    """执行 seed 脚本子进程 + 验证 ``flare_radiation_limits`` 载入 3 行 + 二次 upsert 不报错。

    upsert 语义：按 ``limit_type`` 唯一索引 ``ON CONFLICT DO UPDATE``；
    二次执行应幂等（同一唯一键命中 → 更新），不抛 unique 冲突。
    """
    import subprocess

    script_path = _BACKEND_ROOT / "scripts" / "p6_3_gate_06_flare_radiation_limits_seed.py"

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
                select(FlareRadiationLimits).order_by(FlareRadiationLimits.limit_type)
            )
        ).scalars().all()

    # brief 要求 3 行；脚本预期 3 行（API 521 BEDD 三档）
    assert len(rows) == 3, (
        f"期望载入 3 行，实际 {len(rows)} 行"
    )
    # source 全部为 API 521 真实标记
    assert all(row.source == "API521_§7.4.2.3" for row in rows)
    # limit_type 与 BEDD 三档一致
    assert {row.limit_type for row in rows} == {
        "PROPERTY_LINE", "PERSONNEL", "EMERGENCY",
    }
    # q_kw_m2_limit 与 API 521 §7.4.2.3 一致（浮点等值用 1e-6 容差）
    actual_by_type = {row.limit_type: row for row in rows}
    assert abs(actual_by_type["PROPERTY_LINE"].q_kw_m2_limit - 4.73) < 1e-6
    assert abs(actual_by_type["PERSONNEL"].q_kw_m2_limit - 6.31) < 1e-6
    assert abs(actual_by_type["EMERGENCY"].q_kw_m2_limit - 12.6) < 1e-6

    # 第二次 upsert：应幂等（同一 limit_type → 更新）
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
            await session.execute(select(FlareRadiationLimits))
        ).scalars().all()
    # 行数不变（ON CONFLICT DO UPDATE）
    assert len(rows2) == 3


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_flare_radiation_limits_confirmed_fields_not_overwritten(
    clean_flare_radiation_limits_table: None,
) -> None:
    """验证 upsert 不覆盖 ``confirmed_by`` / ``confirmed_at``（mirror G-03）。

    流程：

    1. seed 脚本首次 upsert（API 521 真实值，全部 confirmed 字段为 NULL）；
    2. 人工（测试代码模拟）UPDATE ``PROPERTY_LINE`` 行 ``confirmed_by``
       + ``confirmed_at`` 为工艺室签字值；
    3. seed 脚本二次 upsert（同一 ``limit_type`` → ON CONFLICT DO
       UPDATE）；
    4. 断言 ``PROPERTY_LINE`` 行 ``confirmed_by`` / ``confirmed_at``
       仍为签字值（**未被 upsert 清空**）。
    """
    import subprocess
    from datetime import UTC, datetime

    script_path = _BACKEND_ROOT / "scripts" / "p6_3_gate_06_flare_radiation_limits_seed.py"

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
    signed_at = datetime(2026, 3, 5, 11, 0, 0, tzinfo=UTC)
    signed_by = "工艺工程师_王五"

    # 2. 模拟工艺室签字
    async with factory() as session:
        target = (
            await session.execute(
                select(FlareRadiationLimits).where(
                    FlareRadiationLimits.limit_type == "PROPERTY_LINE",
                )
            )
        ).scalars().one()
        target.confirmed_by = signed_by
        target.confirmed_at = signed_at
        await session.commit()
        target_limit_id = target.limit_id

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
                select(FlareRadiationLimits)
                .where(FlareRadiationLimits.limit_id == target_limit_id)
            )
        ).scalars().one()
    assert after.confirmed_by == signed_by, (
        f"confirmed_by 被覆盖：actual={after.confirmed_by} expected={signed_by}"
    )
    assert after.confirmed_at == signed_at, (
        f"confirmed_at 被覆盖：actual={after.confirmed_at} expected={signed_at}"
    )