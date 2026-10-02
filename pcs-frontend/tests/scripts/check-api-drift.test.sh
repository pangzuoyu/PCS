#!/usr/bin/env bash
# check-api-drift.sh 单元测试
#
# 验证:
# 1. snapshot == backend openapi → exit 0
# 2. snapshot 缺 path → exit 1 + 报告
# 3. backend 加 path → exit 1 + 报告 (missing snapshot)
# 4. schema required 变化 → exit 1 + BREAKING 报告

set -euo pipefail

cd "$(dirname "$0")/../.."

SCRIPT="scripts/check-api-drift.sh"

# helper: 用 SNAPSHOT_OVERRIDE / BACKEND_OPENAPI_OVERRIDE env var 注入临时文件
run_with_overrides() {
  local snapshot="$1"
  local backend="$2"
  SNAPSHOT_OVERRIDE="$snapshot" BACKEND_OPENAPI_OVERRIDE="$backend" \
    bash "$SCRIPT"
}

# 1. 同 snapshot → 0
if run_with_overrides openapi.snapshot.json ../pcs-backend/docs/openapi.json > /tmp/drift_test_1.log 2>&1; then
  echo "PASS test 1: identical files → exit 0"
else
  echo "FAIL test 1: identical files should exit 0"
  cat /tmp/drift_test_1.log
  exit 1
fi

# 2. snapshot 缺 path → 1 + BREAKING 报告
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

cp openapi.snapshot.json "$TMPDIR/snapshot.json"
cp ../pcs-backend/docs/openapi.json "$TMPDIR/backend.json"

# snapshot 删 1 个 path (即 snapshot 缺 path, backend 有)
jq 'del(.paths["/api/v1/health"])' "$TMPDIR/snapshot.json" > "$TMPDIR/snapshot2.json"
mv "$TMPDIR/snapshot2.json" "$TMPDIR/snapshot.json"

# 跑脚本, 期望 exit 1 + 新增 paths 报告 (snapshot 缺 path = backend 新增, 需重新 snapshot)
if run_with_overrides "$TMPDIR/snapshot.json" "$TMPDIR/backend.json" > /tmp/drift_test_2.log 2>&1; then
  echo "FAIL test 2: missing path should exit 1"
  cat /tmp/drift_test_2.log
  exit 1
fi
if grep -q "新增 paths" /tmp/drift_test_2.log && \
   grep -q "/api/v1/health" /tmp/drift_test_2.log; then
  echo "PASS test 2: snapshot missing path detected"
else
  echo "FAIL test 2: output missing expected report"
  cat /tmp/drift_test_2.log
  exit 1
fi

# 3. backend 加新 path, snapshot 没 → 1 + 报告
cp openapi.snapshot.json "$TMPDIR/snapshot.json"
cp ../pcs-backend/docs/openapi.json "$TMPDIR/backend.json"

# backend 加 1 个 path
jq '.paths["/api/v1/test-only"] = {"get": {"responses": {"200": {"description": "OK"}}}}' \
  "$TMPDIR/backend.json" > "$TMPDIR/backend2.json"
mv "$TMPDIR/backend2.json" "$TMPDIR/backend.json"

if run_with_overrides "$TMPDIR/snapshot.json" "$TMPDIR/backend.json" > /tmp/drift_test_3.log 2>&1; then
  echo "FAIL test 3: added backend path should exit 1"
  cat /tmp/drift_test_3.log
  exit 1
fi
if grep -q "新增 paths" /tmp/drift_test_3.log && \
   grep -q "/api/v1/test-only" /tmp/drift_test_3.log; then
  echo "PASS test 3: added path detected"
else
  echo "FAIL test 3: output missing expected report"
  cat /tmp/drift_test_3.log
  exit 1
fi

# 4. schema required 变化 → 1 + BREAKING 报告
cp openapi.snapshot.json "$TMPDIR/snapshot.json"
cp ../pcs-backend/docs/openapi.json "$TMPDIR/backend.json"

# backend 加 required field to MockLoginResponse
jq '.components.schemas.MockLoginResponse.required += ["user_id"]' \
  "$TMPDIR/backend.json" > "$TMPDIR/backend2.json"
mv "$TMPDIR/backend2.json" "$TMPDIR/backend.json"

if run_with_overrides "$TMPDIR/snapshot.json" "$TMPDIR/backend.json" > /tmp/drift_test_4.log 2>&1; then
  echo "FAIL test 4: schema required change should exit 1"
  cat /tmp/drift_test_4.log
  exit 1
fi
if grep -q "schema required 字段变化" /tmp/drift_test_4.log && \
   grep -q "MockLoginResponse" /tmp/drift_test_4.log; then
  echo "PASS test 4: schema required change detected as BREAKING"
else
  echo "FAIL test 4: output missing expected report"
  cat /tmp/drift_test_4.log
  exit 1
fi

echo "All 4 drift detection tests passed"