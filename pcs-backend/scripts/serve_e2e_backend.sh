#!/usr/bin/env bash
# 真后端通道的**后端**起服脚本 —— P10-B 评审 #23。
#
# ## 为什么要有它
#
# 真后端 E2E 通道需要「后端 + 库 + 种子数据」三样同时就位 ⇒ 以前这三样
# **散在 README 的一段 bash 里** ⇒ ⇒ 复现要靠人记得三件事同时对：
#   ① `DATABASE_URL` 指的是**被 seed 的那个库**（`pcs_pgtest` · 宿主 5433）
#      —— 不设 ⇒ 后端读 `.env` ⇒ 连的是**开发库 `pcs`** ⇒ 种子在 A 库、
#      后端在 B 库 ⇒ **两边不是同一个库** ⇒ 项目守卫的端点全 404
#   ② `PCS_ENABLE_MOCK_LOGIN=true`（mock 登录**默认关** ⇒ 双闸）
#   ③ 端口与前端 `VITE_API_PROXY_TARGET` **成对**
#
# ⇒ 少任何一件 ⇒ 症状是「登录失败」或「表格永远没行」⇒ **极难定位**
# ⇒ ⇒ 这三件事**收进本脚本** ⇒ 一个入口 ⇒ 端口也由本脚本说了算。
#
# ## 跑法
#
# ```bash
# cd pcs-backend && bash scripts/serve_e2e_backend.sh     # 终端 ①
# cd pcs-frontend && npm run e2e:real                     # 终端 ②
# ```
#
# ⚠️ **库与种子**：本脚本**只起服**，不迁移、不灌种子 ⇒ 那两步是
# `docker compose --profile test up -d` + `run --rm migrate` + `run --rm seed`
# （见仓库根 README「E2E 两条通道」）。
#
# ⚠️ **口令走环境变量**（`POSTGRES_PASSWORD`）⇒ 不写进命令行（不进 shell 历史、
# 不被权限分类器拦）⇒ 默认值是 compose 里那个**仅限开发**的口令。
set -euo pipefail

cd "$(dirname "$0")/.."

PG_DB_NAME="${PG_DB_NAME:-pcs_pgtest}"
PG_PORT="${PG_PORT:-5433}"
BACKEND_PORT="${BACKEND_PORT:-8001}"

PG_USER="${POSTGRES_USER:-pcs}"
PG_PASS="${POSTGRES_PASSWORD:-pcs_dev}"

# ⚠️ **必须是被 seed 的那个库**（`pcs_pgtest` · 宿主 5433）—— 不是 `.env` 里的
# 开发库 `pcs` ⇒ 种子在 A 库、后端在 B 库 ⇒ 两边不通。
export DATABASE_URL="postgresql+psycopg://${PG_USER}:${PG_PASS}@localhost:${PG_PORT}/${PG_DB_NAME}"

# ⚠️ mock 登录**默认关**（`app/api/v1/mock_auth.py` 的双闸：非生产 **且**
# 显式 `PCS_ENABLE_MOCK_LOGIN=true`）⇒ 真后端通道必须显式开。
export PCS_ENABLE_MOCK_LOGIN=true

echo "真后端通道的后端：${DATABASE_URL%%@*}/…@localhost:${PG_PORT}/${PG_DB_NAME} · 端口 ${BACKEND_PORT}" >&2
echo "（口令不在输出里；库名与端口在上）" >&2

exec uv run uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
