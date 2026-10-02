#!/usr/bin/env bash
# F-P3-002 fix: pre-commit hook for alembic migration idempotency.
# 检查 op.create_index / op.drop_table 等是否带 if_not_exists / if_exists.
#
# 用法:
#   scripts/check_migration_idempotency.sh          # CI 用, exit 1 on fail
#   或加 .git/hooks/pre-commit:
#     bash pcs-backend/scripts/check_migration_idempotency.sh

set -e
cd "$(dirname "$0")/.."
exec uv run python scripts/check_migration_idempotency.py
