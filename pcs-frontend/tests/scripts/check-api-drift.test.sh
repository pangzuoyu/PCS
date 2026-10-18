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
# ---------------------------------------------------------------------------
# 5-7. docstring 声称但**从未实现**的三项（2026-10-19）
#
# 脚本头部写着「检测: path added/removed, schema added/removed,
# field type changed, field removed (BREAKING), enum value removed (BREAKING)」，
# 而实现只比了 `required` 数组。改字段名、改类型、删 enum 值 —— 三种都照过。
#
# 危害有具体证据：bug-180 里 `pipe_class_id` → `class_id` 这种
# **整组改名**、以及 `schedule: string` → `sch_series_json: {...}`
# 这种**改类型**，都被放过了。（那个 bug 靠 mock 遮着才活到今天。）
# ---------------------------------------------------------------------------

# 基准 fixture：一个 schema，三个字段（a 字符串 / b 整数 / e 三值 enum）。
# ⚠️ `jq -n` 不能省 —— 不给输入文件时 jq 读 stdin，写出的 fixture 是空文件，
# 于是后面每一条用例都变成「两个空文件比较」，看起来像脚本失灵。
DEMO_JSON='{"paths":{},"components":{"schemas":{"Demo":{"type":"object",
"required":["a"],"properties":{"a":{"type":"string"},"b":{"type":"integer"},
"e":{"type":"string","enum":["X","Y","Z"]}}}}},"info":{"title":"t","version":"1"}}'

mk_fixtures() {
  printf '%s\n' "$DEMO_JSON" | jq -S . > "$TMPDIR/base"
}

# 5. 字段**删除**（属性没了，但 required 未变）→ BREAKING
#
# ⚠️ 方向：删在**后端**那一侧（`BACKEND_OPENAPI_OVERRIDE`）。
# 删在 snapshot 侧是「后端加了字段」，那只是 snapshot 该重新生成，不是 breaking。
# 第一版删错了侧，于是 exit 0 —— 看起来像脚本没实现检测。
mk_fixtures
jq 'del(.components.schemas.Demo.properties.b)' "$TMPDIR/base" > "$TMPDIR/b1.json"
if run_with_overrides "$TMPDIR/base" "$TMPDIR/b1.json" > /tmp/drift_test_5.log 2>&1; then
  echo "FAIL test 5: 字段删除未被检出（docstring 声称 field removed 检测）"
  cat /tmp/drift_test_5.log
  exit 1
fi
grep -q "字段删除" /tmp/drift_test_5.log || {
  echo "FAIL test 5: 报告里没有「字段删除」段落"
  cat /tmp/drift_test_5.log; exit 1; }
echo "PASS test 5: 字段删除 → exit 1 + BREAKING 报告"

# 6. 字段**类型**变化 → BREAKING
mk_fixtures
jq '.components.schemas.Demo.properties.a.type = "integer"' "$TMPDIR/base" > "$TMPDIR/s2.json"
if run_with_overrides "$TMPDIR/s2.json" "$TMPDIR/base" > /tmp/drift_test_6.log 2>&1; then
  echo "FAIL test 6: 字段类型变化未被检出"
  cat /tmp/drift_test_6.log
  exit 1
fi
grep -q "字段类型变化" /tmp/drift_test_6.log || {
  echo "FAIL test 6: 报告里没有「字段类型变化」段落"
  cat /tmp/drift_test_6.log; exit 1; }
echo "PASS test 6: 字段类型变化 → exit 1 + BREAKING 报告"

# 7. enum **值删除** → BREAKING（同样删在后端侧）
mk_fixtures
jq '.components.schemas.Demo.properties.e.enum = ["X","Y"]' "$TMPDIR/base" > "$TMPDIR/b3.json"
if run_with_overrides "$TMPDIR/base" "$TMPDIR/b3.json" > /tmp/drift_test_7.log 2>&1; then
  echo "FAIL test 7: enum 值删除未被检出"
  cat /tmp/drift_test_7.log
  exit 1
fi
grep -q "enum 值删除" /tmp/drift_test_7.log || {
  echo "FAIL test 7: 报告里没有「enum 值删除」段落"
  cat /tmp/drift_test_7.log; exit 1; }
echo "PASS test 7: enum 值删除 → exit 1 + BREAKING 报告"

# 8. 后端**新增**字段（非 breaking）→ 仍应 exit 0，别把新增误报成 BREAKING。
#
# ⚠️ 方向：字段加在**后端**侧。snapshot 有而后端没有 = 「前端还在读一个
# 后端已删的字段」，那**确实**是 BREAKING（见 test 5/9）——
# 第一版把字段加在了 snapshot 侧，于是正确地报了 BREAKING，
# 测试却以为脚本误报。**同一条规则，第三次把方向搞反。**
mk_fixtures
jq '.components.schemas.Demo.properties.c = {type:"string"}' "$TMPDIR/base" > "$TMPDIR/b4.json"
if ! run_with_overrides "$TMPDIR/base" "$TMPDIR/b4.json" > /tmp/drift_test_8.log 2>&1; then
  echo "FAIL test 8: 新增字段被误报成 BREAKING"
  cat /tmp/drift_test_8.log
  exit 1
fi
echo "PASS test 8: 新增字段 → exit 0（非 breaking）"

# 9. 整组改名（bug-180 的形状）→ 必须被「字段删除」抓住
mk_fixtures
jq '.components.schemas.Demo.properties.a = {type:"string", deprecated:true}
    | .components.schemas.Demo.properties.z = .components.schemas.Demo.properties.a
    | del(.components.schemas.Demo.properties.a)' "$TMPDIR/base" > "$TMPDIR/b5.json"
if run_with_overrides "$TMPDIR/base" "$TMPDIR/b5.json" > /tmp/drift_test_9.log 2>&1; then
  echo "FAIL test 9: 字段改名未被检出（bug-180 的真实形状）"
  cat /tmp/drift_test_9.log
  exit 1
fi
grep -q "Demo.a" /tmp/drift_test_9.log || {
  echo "FAIL test 9: 报告里没点名被删的字段"
  cat /tmp/drift_test_9.log; exit 1; }
echo "PASS test 9: 字段改名 → 作为「字段删除」报出"
