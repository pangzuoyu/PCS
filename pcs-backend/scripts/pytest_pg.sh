#!/usr/bin/env bash
# 唯一的 PG 车道入口（TODO-099 · 委员会 2026-11-02 裁决 4）。
#
# ⚠️ **不得**在 README/CLAUDE.md 里教「也可以直接 DATABASE_URL=... pytest」——
#    那会重新引入「多条路径做同一件事」的分叉。
#
# 三条 fail-closed 约束（缺一条就等于没做）：
#   ① PG 实例没起 ⇒ FAIL（不是 skip）
#   ② 收集到 0 个 PG 测试 ⇒ FAIL（「收集到 0 个」不是「通过」）
#   ③ 测试被全 skip ⇒ FAIL（PG 起了但没真跑，与没起无法区分）
#
# ⚠️ `pg` marker 的用例平时被 `pytest.skip` 静默跳过 ⇒ 只有走这个脚本才会真跑。
#
# 用法：`bash scripts/pytest_pg.sh`（默认等价于 `pytest -m pg`，但多三道 fail-closed 闸）
set -euo pipefail

cd "$(dirname "$0")/.."

PG_PYTEST_MARK="${PG_PYTEST_MARK:-pg}"
PG_DB_NAME="${PG_DB_NAME:-pcs_pgtest}"
PG_PORT="${PG_PORT:-5433}"

# compose 文件在**仓库根**（不是 pcs-backend/）⇒ 必须显式 -f，
# 否则 `docker compose` 在 pcs-backend/ 下报「no configuration file」。
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.yml"

# ⚠️ **不传 `-p` 时** compose 自己从 compose 文件所在目录推导项目名
#    （= 仓库目录名的小写形式）⇒ 脚本查的与用户 `docker compose --profile pg up -d`
#    起的是**同一个**项目 ⇒ 仓库换个目录名克隆也不会「实例起着却报没起」。
#    需要显式指定时才设 PG_COMPOSE_PROJECT。
if [ -n "${PG_COMPOSE_PROJECT:-}" ]; then
  COMPOSE_PROJECT_ARGS=(-p "$PG_COMPOSE_PROJECT")
else
  COMPOSE_PROJECT_ARGS=()
fi

# ① PG 实例必须起着
# ⚠️ `-p` 可选但**语义必需**：设了它，「PG 没起」这条断言才能被单独触发
#    （守卫测不到它声称的东西）。
if ! docker compose -f "$COMPOSE_FILE" "${COMPOSE_PROJECT_ARGS[@]}" --profile pg ps --status running \
     | grep -q "postgres-pgtest"; then
  echo "FAIL: PG 测试实例未起 ⇒ docker compose --profile pg up -d" >&2
  exit 1
fi

# ⓛ 车道互斥锁（**不是** fail-closed 闸门，是并发保护）
#
# ⚠️ **PG 车道与 E2E 车道共用同一个库**（`pcs_pgtest`）⇒ 各自建隔离 schema
#    ⇒ 并发跑 ⇒ DDL 互相等锁 ⇒ 表现是「**偶发卡住**」而不是报错
#    ⇒ 排查成本极高 ⇒ 「别同时跑」必须是**机制**，不能只是一句叮嘱。
#
# ⚠️ **锁放在这个共享脚本里**（不是各自的薄封装里）⇒
#    ① 一次加锁 ⇒ 两条车道都生效（E2E 车道 exec 进这里 ⇒ 一样被锁）
#    ② 薄封装**不会**自己再抢一次 ⇒ 不会自己锁死自己。
#
# ⚠️ **锁文件在项目内**（不是 `/tmp`）—— P10-B 评审 #15 的第 ② 步：
#    `/tmp` 会被**清理**（tmpfs / 重启）⇒ ⇒ 锁文件的 inode 换新 ⇒ ⇒
#    ⇒ 正在跑的车道的锁**对新来的车道不可见** ⇒ ⇒ 互斥**静默失效**
#    ⇒ ⇒ 放项目内（`.tmp/` 不被清理 ⇒ inode 稳定）。
#    ⚠️ **绝对路径**（`$BACKEND_DIR`）⇒ ⇒ 从任何目录调脚本都锁**同一个**文件。
#    ⚠️ 守门测试用 `PCS_PGTEST_LANE_LOCK` **覆盖**它（见
#    `tests/scripts/test_pytest_pg_gate.py`）⇒ ⇒ 与真车道互不干扰。
BACKEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCK_FILE="${PCS_PGTEST_LANE_LOCK:-${BACKEND_DIR}/.tmp/lane.lock}"
mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "FAIL: 另一条车道（PG 车道 / E2E 车道）正在跑 ⇒ 同一个库不能并发建 schema" >&2
  exit 1
fi

# 口令**只在环境变量里**（不上命令行 —— 会被权限分类器拦，且进 shell 历史）
PG_USER="${POSTGRES_USER:-pcs}"
PG_PASS="${POSTGRES_PASSWORD:-pcs_dev}"
export DATABASE_URL="postgresql+psycopg://${PG_USER}:${PG_PASS}@localhost:${PG_PORT}/${PG_DB_NAME}"
export TEST_DATABASE_URL="$DATABASE_URL"

# ② 收集到的 PG 测试数必须 > 0
# ⚠️ pytest 的 `-q --collect-only` 摘要是「N/M tests collected (K deselected)」
#    —— 第一个数才是**选中**的（N），第二个是总数（M）⇒ 取第一个。
collected="$(uv run pytest -m "$PG_PYTEST_MARK" --collect-only -q 2>/dev/null \
  | grep -oE '[0-9]+(/[0-9]+)? tests? collected' | head -1 \
  | cut -d/ -f1 | grep -oE '[0-9]+' | head -1 || true)"
if [ "${collected:-0}" -eq 0 ]; then
  echo "FAIL: 收集到 0 个 PG 测试（标记缺失 / 全部 skip）" >&2
  exit 1
fi

# ③ 正式执行；输出里必须有「至少 1 passed」，且**不能有 skip**
out="$(uv run pytest -m "$PG_PYTEST_MARK" -q 2>&1)" || { echo "$out"; exit 1; }
echo "$out"
if ! echo "$out" | grep -qE '[1-9][0-9]* passed'; then
  echo "FAIL: PG 车道没有实际执行任何测试（全部 skip？）" >&2
  exit 1
fi
# ⚠️ **部分 skip 也算假绿**（P10-B 评审 #16 · P1）——
# 原先只要求「≥1 passed」⇒ ⇒「30 条里跑 1 条、29 条被 skip」也是绿的
# ⇒ ⇒ 车道绿灯**不携带信息**（验证机制的失败模式就是假绿）。
# ⇒ ⇒ 只看**摘要行**（`tail -1`）⇒ 免得用例输出里的 "skipped" 字样误伤。
# ⚠️ **deselected 不算 skip**（那是 marker 过滤掉的，不是 skip）。
summary="$(echo "$out" | tail -1)"
if echo "$summary" | grep -qE '[0-9]+ skipped'; then
  echo "FAIL: PG 车道有测试被 skip ⇒ fail-closed（skip 的用例不算「跑过」）: $summary" >&2
  exit 1
fi
