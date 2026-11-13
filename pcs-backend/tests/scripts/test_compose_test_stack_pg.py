"""**执行级**的测试栈守卫（评审 #22 · 2026-11-12）。

## 为什么需要它

`tests/scripts/test_compose_test_profile.py` 只 **yaml.safe_load** 了
`docker-compose.yml` ⇒ 它断言的是「文件里**声明**了哪些字符串」⇒ 而

- `alembic upgrade head` 在 `pcs_pgtest` 上**真的**成功吗？
- `scripts/seed_e2e_data.py` 在**真 PG** 上**真的**能跑吗？
- seed **真的**幂等吗（跑两遍行数不涨）？

这三件事**从来没被执行过** ⇒ 那个守门是**空壳**（跟本批的架构守卫同病：
断言的形状与被守的东西无关）。

⇒ 本文件**真跑** `scripts/compose_test_stack.sh`（它自己 fail-closed）
⇒ 失败 ⇒ 用例红。

⚠️ **只在 PG 车道里跑**（`@pytest.mark.pg`）⇒ 平时被静默跳过
⇒ **必须**经 `scripts/pytest_pg.sh`（唯一入口）跑。

⚠️ **docker 不可用 ⇒ 跳过**（不是静默通过）：本用例需要能起容器
⇒ 没有 docker 的机器上它**没法**验证任何东西 ⇒ 明确说「没验」，
而不是假装验过（仓里的 PG 车道对「收集到 0 个 / 全 skip」是 fail-closed 的，
但本用例属于「环境不具备」⇒ 跳过并写明原因）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

#: 脚本在 `pcs-backend/scripts/` 下。
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "compose_test_stack.sh"


@pytest.mark.pg
def test_compose_test_stack_executes_migrate_and_seed() -> None:
    """真跑测试栈 ⇒ migrate + seed（两遍）+ 直查库验证 ⇒ 退出码 0。"""
    # ⚠️ **只在 PG 车道里跑** —— 本用例会**起容器**（migrate + seed 两遍）
    # ⇒ 默认 pytest 车道里跑它 = 每次全量测试都起一遍 compose ⇒ 不可接受。
    # ⇒ 判据 = **PG 车道自己导出的** `TEST_DATABASE_URL`（`scripts/pytest_pg.sh`
    # 导出，指向 `pcs_pgtest`）⇒ 默认车道没有这个变量 ⇒ 跳过。
    lane_url = os.environ.get("TEST_DATABASE_URL", "")
    if "pcs_pgtest" not in lane_url:
        pytest.skip(
            "不在 PG 车道里（无 TEST_DATABASE_URL）⇒ 须经 scripts/pytest_pg.sh 跑"
        )
    if shutil.which("docker") is None:
        pytest.skip("docker 不可用 ⇒ 本用例没法验证测试栈（不是「验过了」）")

    assert SCRIPT.exists(), f"脚本不存在：{SCRIPT}"

    # ⚠️ **超时给 1 小时**：脚本第一次跑要在容器里**装一遍依赖**
    # （`uv run --frozen` ⇒ ~600 MB 的包）⇒ 实测 15~40 分钟
    # （取决于网络）⇒ 1800 s 会在**正常**路径上误杀。
    # ⇒ 之后的每次跑都命中**持久卷**（依赖 + 下载缓存）⇒ 约 10 秒。
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=3600,
    )

    assert result.returncode == 0, (
        f"测试栈执行失败：\n{result.stdout}\n{result.stderr}"
    )
    assert "OK:" in result.stdout, result.stdout
