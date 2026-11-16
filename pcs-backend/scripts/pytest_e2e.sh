#!/usr/bin/env bash
# E2E 车道（隔离 schema · 真 PG）的唯一入口 —— P10-B。
#
# ## 定位
#
# 本脚本 = **薄封装**（复用 `scripts/pytest_pg.sh` 的三道 fail-closed 闸门）。
# ⚠️ **不复制**那三道闸门 —— 复制 = 两份真相源 ⇒ 以后改闸门只改了一边
# ⇒ 两条车道的行为悄悄分叉。
#
# ## 只做三件事
#
# ① `export PG_PYTEST_MARK=e2e` —— `pytest_pg.sh` 的 marker **已经参数化**
#    ⇒ E2E 用例靠这个 marker 被选中（闸门②「收集到 0 个 ⇒ FAIL」因此有效）
# ② `export PCS_E2E_LANE=1` —— **默认车道的 skip 闸门靠它放行**
#    ⇒ 没有它，`uv run pytest` 会把 E2E 场景**跑到开发库 `pcs` 上**
# ③ `exec bash scripts/pytest_pg.sh` —— 库 / 端口 / 三道闸门**全归它管**
#
# ## ⚠️ 不要在这里导 `DATABASE_URL` / `TEST_DATABASE_URL`
#
# `scripts/pytest_pg.sh:50-51` **无条件**覆写这两个变量 ⇒ 这里再导一次是
# **死代码** ⇒ 留着会让人以为「改薄封装就能换库」⇒ 改了没效果 ⇒ 排查半天。
#
# ## ⚠️ 车道互斥
#
# 两条车道共用同一个库 ⇒ 并发跑会 DDL 等锁 ⇒ 表现是「偶发卡住」。
# ⇒ 加锁放在**共享的** `pytest_pg.sh` 里（一次加锁 ⇒ 两条车道都生效，
# 且本脚本 exec 进它 ⇒ 不会自己锁死自己）。
set -euo pipefail

cd "$(dirname "$0")/.."

export PG_PYTEST_MARK=e2e
export PCS_E2E_LANE=1

exec bash scripts/pytest_pg.sh
