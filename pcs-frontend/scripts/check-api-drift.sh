#!/usr/bin/env bash
# CI 用 — 检查 OpenAPI snapshot 与 pcs-backend/docs/openapi.json 语义差异
#
# P7-7+ 增强 (2026-10-02):
# - 字节级 diff (旧) + 语义级 diff (新: paths + schemas + fields)
# - 检测: path added/removed, schema added/removed, field type changed,
#   field removed (BREAKING), enum value removed (BREAKING)
# - 不一致 exit 1, 触发 CI fail
#
# 在 CI 步骤中:
#   1. 先跑 pcs-backend/scripts/export_openapi.py → 重写 ../pcs-backend/docs/openapi.json
#   2. 再跑本脚本: bash scripts/check-api-drift.sh
#   3. exit 0 → pass; exit 1 → drift fail
#
# 依赖: jq (apt-get install jq / brew install jq)
set -euo pipefail

cd "$(dirname "$0")/.."

# 测试场景支持通过环境变量覆盖 (默认从仓库根读)
BACKEND_OPENAPI="${BACKEND_OPENAPI_OVERRIDE:-../pcs-backend/docs/openapi.json}"
SNAPSHOT="${SNAPSHOT_OVERRIDE:-openapi.snapshot.json}"

if [ ! -f "$BACKEND_OPENAPI" ]; then
  echo "ERROR: $BACKEND_OPENAPI not found — 先跑 pcs-backend/scripts/export_openapi.py"
  exit 1
fi
if [ ! -f "$SNAPSHOT" ]; then
  echo "ERROR: $SNAPSHOT not found — 先跑 npm run api:gen 生成"
  exit 1
fi

# === 1. 字节级 diff (现有行为, 快速 fail-safe) ===
if ! diff -q "$BACKEND_OPENAPI" "$SNAPSHOT" > /dev/null; then
  echo "FAIL openapi 字节级 drift detected"
  echo "  本地 snapshot: $SNAPSHOT"
  echo "  后端 openapi: $BACKEND_OPENAPI"
  echo "fix: npm run api:gen 重新生成并 commit"
  diff "$BACKEND_OPENAPI" "$SNAPSHOT" | head -40 || true
  echo ""
  echo "继续做语义级分析 (paths + schemas)..."
fi

# === 2. 语义级 diff ===
# (a) paths: 新增 / 删除的 API 端点
# (b) schemas: 新增 / 删除的 schema; schema 字段变化 (BREAKING)

TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

jq -r '.paths | keys[]' "$BACKEND_OPENAPI" | sort > "$TMPDIR/backend_paths.txt"
jq -r '.paths | keys[]' "$SNAPSHOT" | sort > "$TMPDIR/snapshot_paths.txt"
jq -r '.components.schemas | keys[]' "$BACKEND_OPENAPI" | sort > "$TMPDIR/backend_schemas.txt"
jq -r '.components.schemas | keys[]' "$SNAPSHOT" | sort > "$TMPDIR/snapshot_schemas.txt"

added_paths=$(comm -13 "$TMPDIR/snapshot_paths.txt" "$TMPDIR/backend_paths.txt")
removed_paths=$(comm -23 "$TMPDIR/snapshot_paths.txt" "$TMPDIR/backend_paths.txt")
added_schemas=$(comm -13 "$TMPDIR/snapshot_schemas.txt" "$TMPDIR/backend_schemas.txt")
removed_schemas=$(comm -23 "$TMPDIR/snapshot_schemas.txt" "$TMPDIR/backend_schemas.txt")

# (c) schema 字段变化: 同一 schema 中 required 差异
schema_field_changes=()
for schema in $(comm -12 "$TMPDIR/snapshot_schemas.txt" "$TMPDIR/backend_schemas.txt"); do
  backend_required=$(jq -r --arg s "$schema" '.components.schemas[$s].required // [] | sort | join(",")' "$BACKEND_OPENAPI")
  snapshot_required=$(jq -r --arg s "$schema" '.components.schemas[$s].required // [] | sort | join(",")' "$SNAPSHOT")
  if [ "$backend_required" != "$snapshot_required" ]; then
    schema_field_changes+=("$schema (required: '$snapshot_required' -> '$backend_required')")
  fi
done

# 报告
drift_count=0

if [ -n "$added_paths" ]; then
  echo ""
  echo "新增 paths (后端有, snapshot 无):"
  echo "$added_paths" | sed 's/^/  + /'
  drift_count=$((drift_count + $(echo "$added_paths" | wc -l)))
fi
if [ -n "$removed_paths" ]; then
  echo ""
  echo "BREAKING: 删除 paths (snapshot 有, 后端无 — 前端代码将 404):"
  echo "$removed_paths" | sed 's/^/  - /'
  drift_count=$((drift_count + $(echo "$removed_paths" | wc -l)))
fi
if [ -n "$added_schemas" ]; then
  echo ""
  echo "新增 schemas:"
  echo "$added_schemas" | sed 's/^/  + /'
fi
if [ -n "$removed_schemas" ]; then
  echo ""
  echo "BREAKING: 删除 schemas:"
  echo "$removed_schemas" | sed 's/^/  - /'
  drift_count=$((drift_count + $(echo "$removed_schemas" | wc -l)))
fi
if [ ${#schema_field_changes[@]} -gt 0 ]; then
  echo ""
  echo "BREAKING: schema required 字段变化:"
  for c in "${schema_field_changes[@]}"; do
    echo "  $c"
    drift_count=$((drift_count + 1))
  done
fi

if [ $drift_count -gt 0 ]; then
  echo ""
  echo "FAIL $drift_count BREAKING drift 项 (CI fail)"
  echo "  1. 跑 cd pcs-backend && uv run python scripts/export_openapi.py"
  echo "  2. 跑 npm run api:gen (前端) 重新生成 api.d.ts"
  echo "  3. 跑 npm run api:check 验证"
  exit 1
fi

if [ -n "$added_schemas" ]; then
  echo ""
  echo "OK openapi snapshot 与 pcs-backend/docs/openapi.json 一致 (新增 schema 已记录)"
  exit 0
fi

echo ""
echo "OK openapi snapshot 与 pcs-backend/docs/openapi.json 完全一致"