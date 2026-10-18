#!/usr/bin/env bash
# CI 用 — 检查 OpenAPI snapshot 与 pcs-backend/docs/openapi.json 语义差异
#
# P7-7+ 增强 (2026-10-02):
# - 字节级 diff (旧) + 语义级 diff (新: paths + schemas + fields)
# - 检测: path added/removed, schema added/removed, required 变化,
#   field removed (BREAKING), field type changed (BREAKING),
#   enum value removed (BREAKING)
# - 不一致 exit 1, 触发 CI fail
#
# ⚠️ **本 docstring 曾声称三项从未实现的检查**（2026-10-19 修）：
#   「field type changed / field removed / enum value removed」写在头部，
#   实现却只比了 `required` 数组 —— 改字段名、改类型、删 enum 值全部放行。
#   代价有实例：bug-180 里 `pipe_class_id` → `class_id` 的**整组改名**、
#   `schedule: string` → `sch_series_json: {...}` 的**改类型**，都过了这道闸。
#
# 教训：**守门自己的 docstring 也要被验**。写着「检测 X」不等于检测了 X。
# 本脚本的 `tests/scripts/check-api-drift.test.sh` 现在逐条钉住头部声称的每一项。
#
# 在 CI 步骤中:
#   1. 先跑 pcs-backend/scripts/export_openapi.py → 重写 ../pcs-backend/docs/openapi.json
#   2. 再跑本脚本: bash scripts/check-api-drift.sh
#   3. exit 0 → pass; exit 1 → drift fail
#
# 依赖: jq (apt-get install jq / brew install jq)
set -euo pipefail

# ⚠️ **必须在任何 coreutils 之前**统一 locale（2026-10-19）。
#
# zh_CN.UTF-8 下 `sort` 与 `comm` 的排序规则不一致：`sort` 按 zh 排序产出的文件，
# `comm` 判定为「not in sorted order」并往 stderr 喷三条警告 —— **结果仍是对的**，
# 但那三条警告混在报告里，看起来像分析失败。
#
# 本脚本靠 `sort | comm` 做集合差；集合差不需要排序结果，只需要同样的顺序假设。
# 统一成 C locale 让这个假设在**任何机器的任意 locale**下都成立。
export LC_ALL=C

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

# (c) schema 级 + 字段级变化 —— **一次 `jq -s` 出全部结果**（2026-10-19）。
#
# ⚠️ 三处 jq 语法坑（都让这段**静默失效**，不是报错）：
#   1. `EXP as $x | ...` **不收集成数组** —— 它是「对 EXP 的每个输出各绑定一次」。
#      写 `($obj | keys[]) as $names | $names[]` 时 `$names` 是**字符串**，
#      `$names[]` 于是变成「迭代一个字符串」→ `Cannot iterate over string`。
#      要收集得显式 `[ ... ]`。本段干脆不收集。
#   2. `as $x` 后面必须跟 `|`，所以 `... as $x , (branch)` 是语法错。
#      分支列表要作为最后那条管道的**右操作数**：`... as $x | (b1), (b2)`。
#   3. `|` 后面直接接 `,`（`A | B | C , D | E`）同样语法错。
#
# 此前是 `for schema in $(comm -12 ...)` 里每 schema 起 2 次 jq
# （291 个 schema = 582 次进程启动，实测 9.8s，占整脚本 10s 的 98%）。
# 改 `-s` 把两份文档当数组一次读入后比较：更快，也少一层 shell 拼装。
#
# 输出格式统一为 `分类<TAB>说明`，报告侧按 TAB 前缀分组。
schema_changes=$(jq -s -r '  def typesig:
      if   has("$ref") then "ref:" + (."$ref" | split("/") | last)
      elif has("type") and (.type | type) == "array"
        then "array[" + ([.type[] | tostring] | join("|")) + "]"
      elif has("type") then (.type | tostring)
      elif has("anyOf") then "anyOf(" + ([.anyOf[] | typesig] | join("|")) + ")"
      elif has("oneOf") then "oneOf(" + ([.oneOf[] | typesig] | join("|")) + ")"
      elif has("allOf") then "allOf(" + ([.allOf[] | typesig] | join("|")) + ")"
      elif has("items") then "items(" + (.items | typesig) + ")"
      else "?" end;
  def reqsig:  ((.required // []) | map(tostring) | sort | join(","));
  def enumsig: if has("enum") then ([.enum[] | tostring] | sort | join(",")) else "" end;

  .[0] as $snap
  | .[1] as $back
  | $snap.components.schemas
  | keys[] as $name
  | select($back.components.schemas | has($name))
  | ($snap.components.schemas[$name] // {}) as $S
  | ($back.components.schemas[$name] // {}) as $B
  | ($S.properties // {}) as $sp
  | ($B.properties // {}) as $bp
  | ( ($S | reqsig) as $r1 | ($B | reqsig) as $r2
      | select($r1 != $r2) | "\($name)\trequired \($r1) -> \($r2)" )
  , ( $sp | keys[] as $f | select(($bp | has($f)) | not)
      | "\($name).\($f)\t字段删除（后端已移除该字段）" )
  , ( $sp | keys[] as $f | select($bp | has($f))
      | ($sp[$f] | typesig) as $t1 | ($bp[$f] | typesig) as $t2
      | select($t1 != $t2) | "\($name).\($f)\t类型 \($t1) -> \($t2)" )
  , ( $sp | keys[] as $f | select($bp | has($f))
      | ($sp[$f] | enumsig) as $e1 | ($bp[$f] | enumsig) as $e2
      | select($e1 != "" and $e2 != "")
      | (($e1 | split(",")) - ($e2 | split(","))) as $gone
      | select(($gone | length) > 0) | "\($name).\($f)\tenum 值删除 \($gone | join(","))" )
' "$SNAPSHOT" "$BACKEND_OPENAPI")

req_changes=$(printf '%s\n' "$schema_changes" | grep $'\trequired ' || true)
del_changes=$(printf '%s\n' "$schema_changes" | grep $'\t字段删除' || true)
type_changes=$(printf '%s\n' "$schema_changes" | grep $'\t类型 ' || true)
enum_changes=$(printf '%s\n' "$schema_changes" | grep $'\tenum 值删除' || true)

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
_report() {
  local title="$1" lines="$2" marker="$3"
  [ -n "$lines" ] || return 0
  echo ""
  echo "BREAKING: $title"
  printf '%s\n' "$lines" | sed "s/\t/ $marker /" | sed 's/^/  /'
  drift_count=$((drift_count + $(printf '%s\n' "$lines" | wc -l)))
}
_report "schema required 字段变化:"        "$req_changes"  '='
_report "字段删除（前端在读已不存在的字段）:" "$del_changes"  '-'
_report "字段类型变化:"                    "$type_changes" '~'
_report "enum 值删除:"                     "$enum_changes" '!'

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