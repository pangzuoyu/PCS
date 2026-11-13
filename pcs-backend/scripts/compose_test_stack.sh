#!/usr/bin/env bash
# **真跑一遍**测试栈（migrate + seed）并**直查库**验证结果。
#
# ## 定位
#
# 本脚本 = **compose 路径**的执行器（README 里那条「怎么起测试栈」）。
# ⚠️ 它**不是** PG 车道的守卫 —— 车道里的执行级守卫是
# `tests/scripts/test_compose_test_stack_pg.py`，它跑的是**同样的两条命令**
# （`alembic upgrade head` / `scripts/seed_e2e_data.py`）但**在宿主 venv 里**
# ⇒ 秒级、不依赖网络 ⇒ 车道不会被「容器装依赖」拖死。
#
# ## 为什么需要这个脚本（评审 #22 · 2026-11-12）
#
# `tests/scripts/test_compose_test_profile.py` 只 **yaml.safe_load** 了
# compose 文件 ⇒ 它断言的是「文件里**声明**了哪些字符串」
# ⇒ 但「alembic upgrade 在 `pcs_pgtest` 上**真的**成功吗」
# 「seed 脚本在**真 PG** 上**真的**能跑吗」**从来没被执行过**
# ⇒ 那个守门是**空壳**（跟本批的架构守卫是同一类病）。
#
# ⇒ 本脚本**执行**四步并**直查库**：
#   ① `postgres-pgtest` 起起来（healthy）
#   ② `migrate`（`alembic upgrade head`）
#   ③ `seed`（幂等灌种子）—— **跑两遍** ⇒ 第二次的行数必须**不涨**
#   ④ 直查库：`alembic_version` 有值 + 种子表里有行
#
# ⚠️ **幂等**：本脚本可以重复执行 ⇒ 第二遍必须同样成功。
# ⚠️ **fail-closed**：任何一步失败 ⇒ 非零退出（不 skip、不吞）。
# ⚠️ 口令**只在环境变量里**（不上命令行 —— 会进 shell 历史）。
#
# ⚠️ **为什么要挂两个卷**（`/opt/venv` + `/opt/uvcache`）：
# `docker compose run` 每次都**新建容器** ⇒ 而 compose 里那两个目录
# **没挂卷** ⇒ 每次都要**重新装一遍依赖 + 重新下载一遍包**
# ⇒ 实测单次 ~13 分钟 ⇒ 本脚本要跑 3 次容器 ⇒ **40 分钟**。
# ⇒ 挂上命名卷 ⇒ 依赖与下载缓存**跨容器复用**
# ⇒ 第一次 ~13 分钟，之后每次 ~10 秒。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.yml"

PG_USER="${POSTGRES_USER:-pcs}"
PG_PASS="${POSTGRES_PASSWORD:-pcs_dev}"
PG_DB_NAME="${PG_DB_NAME:-pcs_pgtest}"

#: 依赖与下载缓存的**命名卷**（跨 `compose run` 复用 ⇒ 见文件头说明）。
VENV_VOL="${PCS_PGTEST_VENV_VOL:-pcs-pgtest-venv}"
CACHE_VOL="${PCS_PGTEST_CACHE_VOL:-pcs-pgtest-uvcache}"

if [ -n "${PG_COMPOSE_PROJECT:-}" ]; then
  COMPOSE_PROJECT_ARGS=(-p "$PG_COMPOSE_PROJECT")
else
  COMPOSE_PROJECT_ARGS=()
fi

dc() {
  docker compose -f "$COMPOSE_FILE" "${COMPOSE_PROJECT_ARGS[@]}" "$@"
}

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

run_svc() {
  # 跑一次性服务（migrate / seed）⇒ **带上持久卷**（依赖 + 下载缓存）。
  #
  # ⚠️ `--no-deps`：本脚本**自己**管顺序（① 起 PG → ② migrate → ③ seed）
  # ⇒ 若让 compose 照 `depends_on` 再起一遍 `migrate`（seed 声明依赖它）
  # ⇒ 每次多起一个容器、多等一轮 ⇒ 白白变慢（依赖关系的**声明**由
  # `tests/scripts/test_compose_test_profile.py` 在 yaml 层守着）。
  local svc="$1"
  shift
  dc --profile test run --rm --no-deps \
    -v "$VENV_VOL:/opt/venv" \
    -v "$CACHE_VOL:/opt/uvcache" \
    "$svc" "$@"
}

psql_scalar() {
  # 直查库（不走应用层）⇒ 查到的就是**库里真实的样子**。
  dc --profile test exec -T postgres-pgtest \
    psql -U "$PG_USER" -d "$PG_DB_NAME" -tAc "$1" | tr -d '[:space:]'
}

# ① PG 实例起来（healthy ⇒ compose 的 service_healthy 条件已满足）
dc --profile test up -d --wait postgres-pgtest \
  || fail "postgres-pgtest 起不来（docker compose --profile test up -d --wait postgres-pgtest）"

# ② 迁移
run_svc migrate || fail "migrate 失败（alembic upgrade head）"

# ③ 种子 —— 第一遍
run_svc seed || fail "seed 失败（第一遍）"

grants_before="$(psql_scalar 'SELECT count(*) FROM user_projects')"
streams_before="$(psql_scalar 'SELECT count(*) FROM streams')"

# ③ 种子 —— 第二遍（**幂等**的直接证据：行数不能涨）
run_svc seed || fail "seed 失败（第二遍 ⇒ 不幂等）"

grants_after="$(psql_scalar 'SELECT count(*) FROM user_projects')"
streams_after="$(psql_scalar 'SELECT count(*) FROM streams')"

[ "$grants_before" = "$grants_after" ] \
  || fail "user_projects 行数变了（$grants_before → $grants_after）⇒ seed 不幂等"
[ "$streams_before" = "$streams_after" ] \
  || fail "streams 行数变了（$streams_before → $streams_after）⇒ seed 不幂等"

# ④ 直查库
revision="$(psql_scalar 'SELECT version_num FROM alembic_version')"
[ -n "$revision" ] || fail "alembic_version 表是空的 ⇒ migrate 没落地"

for table in workspaces projects users user_projects streams; do
  count="$(psql_scalar "SELECT count(*) FROM $table")"
  [ "${count:-0}" -ge 1 ] || fail "表 $table 里没有种子行（count=$count）⇒ seed 没落地"
done

echo "OK: 测试栈真跑通过（alembic_version=$revision · user_projects=$grants_after · streams=$streams_after）"
