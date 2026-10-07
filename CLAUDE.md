# OpenWolf

This project uses OpenWolf for context management. The always-on rules live in `.claude/rules/openwolf.md`; the hooks handle bookkeeping (anatomy index, memory log, read tracking) automatically.

For the full operating protocol (session handoff, memory discipline, bug logging), load the `openwolf` skill, or read `.wolf/OPENWOLF.md`. Regenerate the session handoff with `/handoff`.

# 测试前检查

- **单元测试（pytest）**：免前置。`tests/conftest.py` 用 `sqlite+aiosqlite:///:memory:`
  + `SA_Base.metadata.create_all` 建表 —— 从 ORM metadata 建，**不读 Postgres，不读
  迁移产物**。`.env` 的 `DATABASE_URL` 指向 `pcs`；当前无 `pcs_test`、无 `.env.test`。
- **Postgres 集成测试（若将来新增）**：须先 `cd pcs-backend && uv run alembic upgrade head`
  对齐。当前套件无此类测试。
- **⚠️ 漂移盲区**：迁移改了 schema 而 ORM 未跟随时，**单测照绿、真库会炸**。缺表会红（可见），
  漂移会绿（不可见）—— 后者没有自动化能抓。改任何 `alembic/versions/*` 时必须**手动核对
  ORM 列同步**（历史上 `config_energy_conversion_factors` 4 个 R1 分类列从未迁移，
  bug-137；见 `.wolf/cerebrum.md`）。人工守门动作：`uv run alembic check`
  （alembic 1.9+ 检测 ORM vs 迁移漂移），无输出即一致。

# 前端 UI 规范

前端所有 UI 以 `docs/PCS-UI-SPEC.md`（V1.0 冻结）为唯一编码依据。字段/枚举/权限/错误码以 OpenAPI + meta API 为准；与 SPEC 冲突时以 OpenAPI 为准并登记 SPEC 修订。

# Per-Batch QA Gate（每批落地强制浏览器回归）

原流程只写在全局 `~/.claude/CLAUDE.md`，**新克隆 / 换机器即失效**，
实际靠人脑维持 —— 2026-10-02 之后三批（Sprint 3 / Sprint 4 / Sprint 5 前置）
落地时都没跑过 QA 报告。此处入库，使闸门随仓库分发。

## 何时跑

每批 sprint 的**最后一个 commit 落地后**，开下一批之前。

## 流程

1. **定位批末 commit**：`git log --oneline -20 | grep '<本批前缀>' | head -1`
2. **回归**（先 `npm run dev` 起 vite，端口 5173）：
   - `npm run typecheck` clean（= `tsc --noEmit`）
   - `npm run lint` clean（自带 `--max-warnings 0` 与 `.` 范围，**别用裸 `npx eslint src/` 替代**）
   - `npm run test` ≥ 上批 baseline（= `vitest run`）
   - 浏览器：login 200 + dashboard 渲染 + 各 Page 路由可达
   - 控制台：无 antd / React / TypeScript error
   - 网络：核心 mock 端点（mock-login、meta 5 端点）无 404
3. **报告**：`.gstack/qa-reports/qa-report-pcs-frontend-YYYY-MM-DD-<batch>.md`
4. **CRITICAL / HIGH 必修完**才能开下一批；MEDIUM / LOW 登记到 `TODOS.md` 延后

## 注意事项

- **`.gstack/` 已在 `.gitignore` 中，报告只落本地不进仓库** ——
  这是设计取舍（截图体积大），但代价是**报告无法随仓库分发给同事或后续会话**。
  关键结论应同步进 `TODOS.md` 或提交信息，别只留在报告里。
- **不要用 `git checkout <commit> --detach`**。历史上为「测批末精确状态」用过，
  但 agent 会话里切换 HEAD 有把会话卡死的风险（本项目已发生过 worktree 被删
  导致隔离守卫援引不存在路径、会话永久无法 Edit/Bash 的事故，见 `.wolf/STATUS.md`）。
  正常流程下 main 就是批末，直接在 main 上跑即可。
- 工具：`~/.claude/skills/gstack/browse/dist/browse`（Linux 下需 `CI=1`）。
  `Skill gstack-qa` 需在 `~/.claude/settings.json` 设为 `"on"` —— 2026-10-07 实测已开。

## 现有报告

- `.gstack/qa-reports/qa-report-pcs-frontend-per-batch-2026-09-16.md`
- `.gstack/qa-reports/qa-report-pcs-frontend-2026-10-02-sprint2-batch.md`（最新）
