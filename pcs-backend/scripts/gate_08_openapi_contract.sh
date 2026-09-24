#!/usr/bin/env bash
# A-08 G-08 OpenAPI 契约自动化门禁脚本
#
# CI 不做（单人开发裁决，.wolf/STATUS.md §锁定用户裁决）；本地一键 + git hook
# 替代 CI 门禁。每批末 Task 16/28 必跑 + pre-commit 自动跑。
#
# 三阶段必跑（无 --check-baseline）：
#   1. regen pcs-backend/docs/openapi.json（后端 export）
#   2. regen pcs-frontend/openapi.snapshot.json + src/types/api.d.ts（前端 gen）
#   3. check-api-drift.sh（后端 vs 前端 一致性）
#
# 第四阶段（--check-baseline；批末/合并前）：
#   4. diff pcs-backend/docs/openapi-baseline.json vs openapi.json（baseline 一致）
#
# 用法：
#   bash scripts/gate_08_openapi_contract.sh           # 阶段 1-3（dev 常规）
#   bash scripts/gate_08_openapi_contract.sh --check-baseline  # 阶段 1-4（批末）
#
# exit 0 → 通过；exit 1 → 漂移 fail（commit/push 阻断）
set -euo pipefail

# 仓库根（脚本可从任意目录调用）
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

CHECK_BASELINE=0
if [ "${1:-}" = "--check-baseline" ]; then
    CHECK_BASELINE=1
fi

echo "=========================================="
echo "[A-08] G-08 OpenAPI 契约门禁"
echo "=========================================="

# 阶段 1：regen backend openapi.json
echo ""
echo "[1/3] regen pcs-backend/docs/openapi.json"
echo "----------------------------------------"
if ! (cd pcs-backend && uv run python scripts/export_openapi.py); then
    echo "FAIL pcs-backend/scripts/export_openapi.py 失败"
    exit 1
fi

# 阶段 2：regen frontend snapshot + api.d.ts
echo ""
echo "[2/3] regen pcs-frontend/openapi.snapshot.json + src/types/api.d.ts"
echo "----------------------------------------"
if ! bash pcs-frontend/scripts/gen-api-types.sh; then
    echo "FAIL pcs-frontend/scripts/gen-api-types.sh 失败"
    exit 1
fi

# 阶段 3：drift check（backend vs frontend）
echo ""
echo "[3/3] drift check (backend openapi.json vs frontend openapi.snapshot.json)"
echo "----------------------------------------"
if ! bash pcs-frontend/scripts/check-api-drift.sh; then
    echo "FAIL 前后端 OpenAPI 契约漂移"
    exit 1
fi

# 阶段 4（可选）：baseline diff
if [ "$CHECK_BASELINE" = "1" ]; then
    echo ""
    echo "[4/4] baseline diff (pcs-backend/docs/openapi-baseline.json vs openapi.json)"
    echo "----------------------------------------"
    if [ ! -f pcs-backend/docs/openapi-baseline.json ]; then
        echo "FAIL pcs-backend/docs/openapi-baseline.json 不存在；请确认基线锁定"
        exit 1
    fi
    if diff -q pcs-backend/docs/openapi-baseline.json pcs-backend/docs/openapi.json > /dev/null; then
        echo "OK baseline 与当前一致（无漂移）"
    else
        echo "FAIL baseline drift detected"
        echo "  基线：pcs-backend/docs/openapi-baseline.json"
        echo "  当前：pcs-backend/docs/openapi.json"
        echo "fix：批末 Task 16/28 滚动更新 baseline + commit"
        diff pcs-backend/docs/openapi-baseline.json pcs-backend/docs/openapi.json | head -60 || true
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "[A-08] ✅ G-08 OpenAPI 契约门禁通过"
echo "=========================================="
exit 0