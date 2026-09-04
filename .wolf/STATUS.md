---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — PCS

> Single source of truth for resuming work. Read this FIRST when starting a session.
> Last updated: 2026-09-04

---

## ✅ Done

- **P2 Sprint 1.8 + 1.10 计划全部完成（2026-09-03~04，SDD 8 任务 + 终审 + 修复波，commits 35a1614..1dc6a43）**：
  - s1.8：formula preconditions（PcsError/PreconditionViolation）+ FormulaSecurityError 继承 + CATEGORY_3 六系数表 seed + default_config_json Pydantic 验证
  - s1.10：折标煤系数组 + DETAIL 模板入库（template_version_seq 自动续号）+ HTRI schema 表 + ADR-0029 + DICT V3.6（`spec/PCS-DICT-ALL-003 V3.6.md`）
  - 修复波：jinja2 入锁、services.PcsError handler（422/404 信封）、toe 表 timestamptz 矫正迁移、hygiene
- **git 历史自持修复（R19）**：P0/P1 运行面整面落库（async session/依赖/7 迁移/P1 服务层/schemas），干净 worktree 实证 258 passed
- **ORM↔DB 收敛（R17/R18）**：D13 全部声明恢复 + doc_no_sequences project_id + 三列 UQ（迁移 p2_s110_doc_no_project_id）
- 质量门：`pytest` 258 passed（lock-synced venv 复验）/ `ruff` 触达文件 0 错 / alembic 单 head `p2_s110_fix_toe_timestamptz`
- 早期：领域建模 ADR-0001~0025 + SUP-007 + P0/P1-MVP（状态机/血缘/CIA/工作区）——详见 git log 与 TODOS.md 完成节

---

## 🚀 Next quest

**Goal:** P2 Sprint 1.9（配置层收尾）——PipeClass service + 5 端点、Riazi-Daubert/虚拟组分切割、equip-lib 沉淀 service（来源：本计划"不在范围内"排除表 #4/#6/equip-lib）

### 待用户裁决
1. **ADR-0029 仍「起草中」**——读 `docs/adr/0029-toe-conversion-and-detail-htri-templates.md`，接受则改「已接受」
2. **preconditions 未接发布门禁（TODO-031）**——终审裁延至 Sprint 1.12，可推翻要求现在接线（~10 行）
3. 仓库级未跟踪面：docs/adr/0001~0028、spec/ 大部分字典、CLAUDE.md/CONTEXT.md/.wolf/.claude、前端 3 脏文件（P0 auth 流）、debug_tmp.py（可删）——是否入库由用户定

### 注意
- pcs_test 库下次 schema 敏感运行前先 `alembic upgrade head`（矫正迁移只应用了 pcs）
- 新表迁移必须含 TimestampMixin 三列（created_by/created_at timestamptz/updated_at nullable）——见 .wolf/cerebrum Do-Not-Repeat

---

## Context

- 分支 main（单人直提惯例）；后端 uv+FastAPI+PG16，前端 Vite+React+antd
- TODOS.md 已入库（含新增 TODO-031/032）；SDD 工作区已删，git 史为正式记录
- 账本裁决全文随工作区删除，关键裁决浓缩于本文件与 cerebrum.md
