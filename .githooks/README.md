# .githooks/ — 本地 Git Hooks 集合

PCS 仓库本地 Git Hooks 目录。**不入 git 索引**（通过 `git config core.hooksPath` 在本地激活），是 CI/CD 不做（用户裁决）的工程自动化替代方案。

## 当前 Hooks

### `pre-commit` — A-08 G-08 OpenAPI 契约门禁

**触发条件**：`pcs-backend/app/api/v1/` 或 `pcs-backend/app/schemas/` 或 `pcs-frontend/src/types/` 文件改动时自动跑 G-08 OpenAPI 契约门禁。

**门禁内容**（详见 [`pcs-backend/scripts/gate_08_openapi_contract.sh`](../pcs-backend/scripts/gate_08_openapi_contract.sh)）：
1. regen `pcs-backend/docs/openapi.json`
2. regen `pcs-frontend/openapi.snapshot.json` + `src/types/api.d.ts`
3. check-api-drift（后端 vs 前端 一致性）

**失败时**：commit 阻断（exit 1）。

**跳过方式**：`git commit --no-verify`（紧急情况，需登记到 backlog）。

## 启用方式（仓库根执行一次）

```bash
git config core.hooksPath .githooks
```

启用后所有 commit 默认自动跑 hook。

## 验证启用

```bash
git config core.hooksPath  # 输出 .githooks
ls -la .githooks/pre-commit  # 应该是可执行文件
```

## 设计原则

1. **CI 不做替代**：用户裁决单人开发不上 CI，本地 hook 作为替代
2. **最小触发面**：每段各自窄触发 —— A-08 仅 OpenAPI/schemas 改动，PP-5 仅迁移文件改动（性能 + 范围聚焦）
3. **可跳过**：紧急情况 `--no-verify`（透明 + 登记）
4. **可读输出**：失败信息含 fix 步骤，不阻塞排查

## 关联文档

- P6 计划 G-08 定义：`docs/superpowers/plans/2026-09-19-p6-batch.md` §8 数据前置 gate
- A-08 实施：`docs/superpowers/plans/2026-09-19-p6-batch.md` §A.08（DevOps 类）
- 用户裁决："CI/CD 不做（单人开发裁决）"——.wolf/STATUS.md §锁定用户裁决

## 维护

新增 hook 在本目录创建 `pre-commit` / `commit-msg` / `pre-push` 等标准 git hook 命名。README 同步追加章节。

## `pre-commit` 第二段 — P9-Prep PP-5 alembic 漂移闸门

**触发条件**：暂存区含 `pcs-backend/alembic/versions/` 改动。

**门禁内容**（`pcs-backend/scripts/gate_alembic_check.py`）：

1. 经 `scripts/run_gate.py` 的 `run_capture()` 跑 `uv run alembic check`（cwd = `pcs-backend/`）
2. 退出码判定一律「非 0 即失败」—— **不比较 255 或 1**。255 这个码进过 `CLAUDE.md`
3. DB revision 落后 code head → 闸门未真正运行，阻断并提示先 `upgrade head`
4. DB 不可达 → 放行 + 醒目告警（避免训练出 `--no-verify`）

**为什么经 run_gate**：本仓闸门共用一个退出码观测层（cerebrum TODO-050）。
另写一套 `RC=$?` 就是造第二个真相源。

**`alembic check` 检的是什么**：ORM metadata ↔ **活库当前 schema**。
它**不读迁移源码** —— 加一条未 apply 的迁移不会被检出（DB 与 ORM 都没那列 ⇒ 一致 ⇒ 通过）。

**已知盲区**：本闸只对 `DATABASE_URL` 指向的那个库成立（开发库 `pcs`）。
`pcs_test` 的漂移不在视野内 —— 要声称两库都干净，必须在 `pcs_test` 上单独跑一次：

```bash
cd pcs-backend
# 口令取本地 .env（已 gitignore），此处不重复写；
# 开发库连接串见 pcs-backend/.env.example 或 README.md §快速开始。
DATABASE_URL="postgresql+psycopg://<user>:<password>@localhost:5432/pcs_test" \
  uv run python scripts/gate_alembic_check.py
```

**绕过**：`git commit --no-verify`，需登记到 backlog。