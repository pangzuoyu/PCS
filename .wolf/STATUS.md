---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-26（P9A-DLV-011 落地：变更单闭环 + 矩阵管理面）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 13 轮：**P9A-DLV-011**（变更单闭环 + 签署矩阵管理面）—— TODO-068~072 全闭环

用户 2026-10-26 裁决：**068 全闭环**（ADR-0008 忠实）· **070 分层权限** · **只做后端**。
计划 `docs/PCS-PLAN-P9A-DLV-011-变更单闭环与签署矩阵管理面.md`。commit
`9da0810` → `b18cbbc`（+ 收口）。

- **T1** 建单 = 交付物 + **版本行**（ISSUED_FOR_CHANGE）+ **记录 binding**
  （`deliverable_record_bindings`，ADR-0008 指定）⇒ 变更单**进得了签署流程**；
  `doc_no` 改完整 32 位 hex（原前 8 位会撞唯一约束 ⇒ 500）；`issue` 抽出
  **不 commit** 的 `create_version_row`（同事务）。
- **T2** 迁移 `p9_008`：`project_signature_matrix_bindings` 加
  `(project_id, module)` 唯一约束（**全新隔离 schema 验过** + 两库 check exit 0）+
  `_ensure_binding` 撞约束用 **SAVEPOINT** 重读。
- **T3** 矩阵管理面 6 端点（模板 = **SYSTEM_ADMIN** / 绑定 = DESIGNER·
  PROCESS_CONTROLLER·SYSTEM_ADMIN + 项目授权）+ `validate_steps` **写路径严格校验**。
- **T4** 变更单闭环 HTTP 面：`initiate-change` / `apply-change` / `change-notice`
  （FORMAL 工作区门禁）+ **自动关记录**（`sign_step` 最后一步 ⇒ 记录 CHANGED →
  CHECKED + `change_resolved_by` + 观测 COMPLETED）+ 驳回后可再签发。
- **评审修复批**（P9A-DLV-007 的 1 条 IMPORTANT）：`todo_service` 还有**第二份**
  `steps_json` 解析 ⇒ 收敛到唯一解析口（坏矩阵曾让待办端点 **500**）。

登记：SPEC **V2.3**（新增 `P9A-DLV-011` 行 + 4 条实现偏离）· `TODOS.md`
TODO-068~072 **闭环** + 新增 TODO-073~080 · buglog bug-2050/2053/2054 补记 +
新增 bug-2055~2059 · UI-SPEC §6.3 修订注记（变更申请按钮该挂 CHANGED）。

### 上一轮：**P9A-DLV-007 + TODO-057**（签署矩阵的取得 + 变更单观测写入点）—— 已完成

见 `docs/PCS-PLAN-P9A-DLV-007-…`；SPEC V2.2（workflow_progress 三工作流 2/3 → **3/3**）。

---

## 🚀 Next quest

1. **P9B-2**：签署流程前端（操作栏 / 批注 / 状态时间线）+ ADMIN 前端（用户管理 /
   审计日志）+ **两个后端前置**（**TODO-065** 聚合端点 `GET /deliverables/{id}/progress`、
   **TODO-066** 按项目守卫的编辑审计读端点）。
   ⚠️ 计划 `docs/PCS-PLAN-P9B-2-签署流程与ADMIN前端.md` **尚未过 `/plan-eng-review`**。
2. **P9B-3**：系统参数前端 + 物流手动创建向导 + 校对 UI。
3. **本批遗留**（TODO-073~080）：变更单编号改走编号模板 · 矩阵名唯一约束 ·
   `change_resolved_by` 语义（状态机与 ADR-0002 冲突）· 工作区门禁只覆盖本批端点 ·
   `apply-change` 不校验 hash · 多记录变更 · 矩阵管理前端 · 评审 3 条 deferred minor。
4. **ADR-0050**：用户 2026-10-20 裁决「先不做」⇒ 再开工按 P1~P6。
5. **P9A-1 遗留**（未变）：access token 不带 `tv`；AD 同步需运维服务账号。

---

## Context

- main，工作区干净。**不要建 worktree**（历史事故）。
- 两库均在 **`p9_008`**（head）· `alembic check` 两库各 exit 0。改迁移的纪律见
  CLAUDE.md（退出码 **255**；先 `current` vs `heads`；`pcs_test` 的跑法：URL 从
  `.env` 派生，**不要把口令写在命令行**）。
- ⚠️ **CI 现在是活的**（`.github/workflows/check-api-drift.yml`，全新 Postgres）
  ⇒ 改了迁移必须**在全新库上验**（本机无建库权限 ⇒ 用隔离 schema：
  `options=-csearch_path=<schema>`；⚠️ URL 里**不能有 `%`**（configparser 插值会炸），
  用 `options=-csearch_path=xxx`）。
- **Redis**：跨进程/锁的测试需要真 Redis —— `docker compose up -d redis`
  （没起时那批测试**红**而不是 skip）。
- 契约：批末要滚 `pcs-backend/docs/openapi-baseline.json`（+ 前端 snapshot / api.d.ts
  由 `gate_08_openapi_contract.sh` 重生成）⇒ 本批已滚（9 个新端点）。
- 提交约定：conventional commits，**无 attribution 行**；长消息写文件后
  `git commit -F <file>`（`!` `（）` 会被 shell 吃掉）。
- ⚠️ **API 测试的 `client` fixture 把 `check_user_project_access` mock 成恒 True**
  ⇒ **项目授权（404）在 API 测试里测不了** ⇒ 只能测角色那一半（403）。

---

## 教训（本会话新增 3 条，已进 cerebrum）

- **要签署的东西必须有版本行**：绑了矩阵 ≠ 矩阵生效（没有版本行 ⇒ 进不了签署 ⇒
  审批只能绕过矩阵 ⇒ 矩阵成装饰品且没人发现）。
- **关联走表，不走字符串**：多态关联（对象 ↔ 对象）要专门的关联表；字符串只能当
  scope / 展示用，两者并存时用**守卫测试**钉住一致。
- **唯一约束会揭穿依赖非法状态的测试**：加约束后测试红了，先看它依赖了什么状态，
  别急着改产品代码（红的症状常常指向别处）。
