#!/usr/bin/env bash
# 从 pcs-backend/docs/openapi.json 生成 pcs-frontend/src/types/api.d.ts
# 不启后端服务，不依赖 localhost
#
#  用：
#    bash scripts/gen-api-types.sh                       # 默认读 ../pcs-backend/docs/openapi.json
#    bash scripts/gen-api-types.sh /path/to/openapi.json  # 自定义路径
set -euo pipefail

cd "$(dirname "$0")/.."

INPUT="${1:-../pcs-backend/docs/openapi.json}"
SNAPSHOT="openapi.snapshot.json"
OUTPUT="src/types/api.d.ts"

if [ ! -f "$INPUT" ]; then
  echo "ERROR: $INPUT not found"
  echo "先跑 pcs-backend/scripts/export_openapi.py 生成该文件"
  exit 1
fi

# 复制成 snapshot（仓库内提交）+ 生成 .d.ts
cp "$INPUT" "$SNAPSHOT"
npx openapi-typescript "$SNAPSHOT" -o "$OUTPUT"

echo "OK gen-api-types: $SNAPSHOT → $OUTPUT"
ls -la "$SNAPSHOT" "$OUTPUT"