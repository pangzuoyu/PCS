"""`scripts/pytest_e2e.sh` 的形状守卫（P10-B · T1）。

## 为什么这个文件存在

E2E 车道是**薄封装**（复用 `scripts/pytest_pg.sh` 的三道 fail-closed 闸门）——
「薄」这件事本身没有强制力 ⇒ 哪天有人把闸门复制一份过去，
就会变成**两份真相源** ⇒ 改了闸门只改了一边 ⇒ 车道行为悄悄分叉。

⇒ 本文件把「薄」钉死：

- 脚本**必须**存在且可执行
- 脚本 body 里**不得**出现 `uv run pytest`（⇒ 闸门只有一份）
- 脚本**必须**委派给 `pytest_pg.sh` 且把 marker 设成 `e2e`
- 脚本**不得**导 `DATABASE_URL` / `TEST_DATABASE_URL`
  （`pytest_pg.sh:50-51` 无条件覆写 ⇒ 薄封装里导是**死代码**
  ⇒ 留着会让人以为「改薄封装就能换库」⇒ 改了没效果 ⇒ 排查半天）
- 脚本**必须**用 `flock` 串行（两条车道共用同一个库 ⇒ 并发 DDL 等锁
  ⇒ 表现是「偶发卡住」而不是报错 ⇒ 机制化挡住）

⚠️ 本文件**不**执行 E2E 车道（那要真 PG + 隔离 schema）⇒ 它是**静态**守卫
⇒ 在默认车道也跑 ⇒ 改了脚本忘了重跑车道时，这里仍然红。
"""
from __future__ import annotations

import os
from pathlib import Path

from tests.scripts.lane_script_body import lane_script_body

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pytest_e2e.sh"
PG_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pytest_pg.sh"


def _body() -> str:
    """脚本的**可执行部分**（去掉注释）。

    ⚠️ **一处真相源**（P10-F · 评审 #27）：剥注释的口径在
    `tests/scripts/lane_script_body.py` ⇒ ⇒ 本文件与 `test_pytest_pg_gate.py`
    共用同一份 ⇒ ⇒ 同一个文件里**不再**有两套口径。
    """
    return lane_script_body(SCRIPT)


def test_script_exists_and_is_executable():
    assert SCRIPT.exists(), "E2E 车道入口脚本不存在"
    assert os.access(SCRIPT, os.X_OK), "脚本不可执行"


def test_e2e_script_does_not_duplicate_the_fail_closed_gates():
    """⚠️ **不复制闸门** —— 薄封装的 body 里**不得**出现 `uv run pytest`。

    ⇒ 闸门逻辑只有一份（`scripts/pytest_pg.sh`）⇒ 以后改一处两边生效。
    """
    body = _body()
    assert "uv run pytest" not in body, (
        "薄封装里出现了 `uv run pytest` ⇒ 闸门被复制了一份 ⇒ 两份真相源会漂移"
    )


def test_e2e_script_delegates_to_the_pg_lane_script():
    """薄封装确实 exec 到 `pytest_pg.sh` 且把 marker 设成 `e2e` + 放行车道闸门。"""
    body = _body()
    assert "pytest_pg.sh" in body, "薄封装没有委派给 PG 车道脚本"
    assert "exec" in body, "薄封装没有用 exec 委派 ⇒ 多一层子进程 ⇒ 退出码会丢"
    assert "PG_PYTEST_MARK" in body, "薄封装没有设 PG_PYTEST_MARK"
    assert "e2e" in body, "薄封装没有把 marker 设成 e2e"
    assert "PCS_E2E_LANE" in body, (
        "薄封装没有导出 PCS_E2E_LANE ⇒ 默认车道的 skip 闸门会把这批用例全跳过"
    )


def test_e2e_script_does_not_export_database_url():
    """⚠️ 薄封装里导 `DATABASE_URL` / `TEST_DATABASE_URL` 是**死代码**
    （`scripts/pytest_pg.sh:50-51` 无条件覆写这两个变量）⇒ 必须不导。
    """
    body = _body()
    assert "DATABASE_URL" not in body, (
        "薄封装里出现了 DATABASE_URL ⇒ 它会被 pytest_pg.sh 无条件覆写 ⇒ 死代码"
    )


def test_lane_scripts_serialize_with_flock():
    """⚠️ 两条车道共用同一个库 ⇒ 并发跑会 DDL 等锁 ⇒ **偶发卡住**。

    ⇒ 「别同时跑」必须是**机制**（`flock -n` ⇒ 抢不到就非零退出），
    不能只是一句叮嘱。

    ⚠️ **锁在共享的 `pytest_pg.sh` 里**（不是薄封装里）⇒
    ① 一次加锁 ⇒ 两条车道都生效 ② 薄封装 exec 进它 ⇒ 不会自己锁死自己
    ⇒ 所以这里断的是 **`pytest_pg.sh`** 的 body。

    ⚠️ **断「可执行部分」**（P10-F · 评审 #27）⇒ ⇒ 注释里写一句 `flock`
    不足以让守卫通过 ⇒ ⇒ 与 `test_pytest_pg_gate.py` 同一份口径。
    """
    pg_body = lane_script_body(PG_SCRIPT)
    assert "flock -n" in pg_body, (
        "共享的 pytest_pg.sh 没有用**非阻塞** flock（-n）⇒ 两条车道并发时会排队卡住"
    )
    assert "exec 9>" in pg_body, (
        "共享的 pytest_pg.sh 没有锁住 fd 9 ⇒ 锁的生命周期只覆盖一条命令"
    )
    assert "pytest_pg.sh" in _body(), "薄封装没有委派 ⇒ 拿不到共享的那把锁"
