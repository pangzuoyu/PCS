#!/usr/bin/env bash
# CI 用 — 检查 OpenAPI snapshot 是否与 pcs-backend/docs/openapi.json 一致
# 不一致 exit 1，触发 CI fail
#
# 在 CI 步骤中：
#  1. 先跑 pcs-backend/scripts/export_openapi.py → 重写 ../pcs-backend/docs/openapi.json
#  2. 再跑本脚本：bash scripts/check-api-drift.sh
#  3. exit 0 → pass；exit 1 → drift fail
set -euo pipefail

cd "$(dirname "$0")/.."

BACKEND_OPENAPI="../pcs-backend/docs/openapi.json"
SNAPSHOT="openapi.snapshot.json"

if [ ! -f "$BACKEND_OPENAPI" ]; then
  echo "ERROR: $BACKEND_OPENAPI not found — 先跑 pcs-backend/scripts/export_openapi.py"
  exit 1
fi
if [ ! -f "$SNAPSHOT" ]; then
  echo "ERROR: $SNAPSHOT not found — 先跑 npm run api:gen 生成"
  exit 1
fi

if diff -q "$BACKEND_OPENAPI" "$SNAPSHOT" > /dev/null; then
  echo "OK openapi snapshot 与 pcs-backend/docs/openapi.json 一致"
  exit 0
else
  echo "FAIL openapi drift detected"
  echo "  本地：$SNAPSHOT"
  echo "  后端：$BACKEND_OPENAPI"
  echo "fix：npm run api:gen 重新生成并 commit"
  diff "$BACKEND_OPENAPI" "$SNAPSHOT" | head -40 || true
  exit 1
fi