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
