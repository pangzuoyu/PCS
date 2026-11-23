#!/bin/sh
# 一次性写者（compose 的 `migrate` / `seed`）的**容器侧**车道锁。
#
# ## 为什么容器也要抢这把锁（TODO-163）
#
# `scripts/pytest_pg.sh`（PG 车道）与 `scripts/compose_test_stack.sh`（测试栈）
# 都在**宿主侧**抢 `pcs-backend/.tmp/lane.lock` ⇒ ⇒ 同一个库不能并发建 schema。
# ⇒ ⇒ 但**直接** `docker compose run --rm seed` **绕过**宿主脚本
# ⇒ ⇒ ⇒ 那就能与跑着的车道**并发** ⇒ ⇒ DDL 互相等锁
# ⇒ ⇒ ⇒ 表现是「**偶发卡住**」（不是报错 ⇒ 极难定位）。
#
# ⇒ ⇒ 本脚本让**容器自己**也抢**同一把锁**（同一路径、同一 inode
# ⇒ ⇒ bind mount 进去 ⇒ ⇒ 宿主与容器**互斥**）⇒ ⇒ ⇒ 洞闭上。
#
# ## ⚠️ `PCS_LANE_LOCK_HELD=1` = 宿主已持锁 ⇒ ⇒ 容器**不再抢**
#
# `compose_test_stack.sh` 自己持锁 ⇒ ⇒ 若容器再抢 ⇒ ⇒ **同锁自锁**
# ⇒ ⇒ ⇒ 必死（`flock -n` 立刻失败）⇒ ⇒ ⇒ 宿主调容器时显式放行。
# ⇒ ⇒ ⇒ 这个开关**只能**由宿主脚本设 ⇒ ⇒ ⇒ 手动设它 = 主动绕过锁
# （与「直接 docker compose run」是同一个洞 ⇒ ⇒ ⇒ 属运维动作 ⇒ ⇒ 文档写明）。
#
# 用法（compose 里）：
#     command: ["sh", "/app/scripts/compose_lane_lock.sh", "alembic", "upgrade", "head"]
set -eu

#: 锁路径（容器内）⇒ ⇒ 必须与宿主 `${BACKEND_DIR}/.tmp/lane.lock` **同一个文件**
#: ⇒ ⇒ 靠 `./pcs-backend/.tmp` 的**可写**挂载 ⇒ ⇒ 同一个 inode ⇒ ⇒ 互斥成立。
LOCK_FILE="${PCS_LANE_LOCK:-/app/.tmp/lane.lock}"

if [ "${PCS_LANE_LOCK_HELD:-0}" = "1" ]; then
  # ⚠️ 宿主已持锁 ⇒ ⇒ 直接跑（**不**再抢 ⇒ ⇒ 否则同锁自锁）
  exec "$@"
fi

mkdir -p "$(dirname "$LOCK_FILE")"

# `-E 99`：抢不到锁 ⇒ ⇒ 退出码 **99**（与「命令自己失败」区分开）
set +e
flock -n -E 99 "$LOCK_FILE" "$@"
rc=$?
set -e

if [ "$rc" -eq 99 ]; then
  echo "FAIL: 另一条车道（PG 车道 / E2E 车道 / 测试栈）正在跑" >&2
  echo "      ⇒ 同一个库不能并发建 schema（锁：$LOCK_FILE）" >&2
  exit 1
fi

exit "$rc"
