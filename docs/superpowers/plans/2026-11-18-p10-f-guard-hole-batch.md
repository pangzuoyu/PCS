# P10-F「守卫补洞批」：ce-code-review 出的 3 条 P1 + 8 条 P2 · 2026-11-18

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `ce-code-review` 审 P10-F 整批得出的 **3 条 P1 + 8 条 P2** 修掉 ⇒ ⇒ 台账：`TODOS.md` **TODO-192**（逐条登记）。

**来源**：10 个评审员全部返回 ⇒ ⇒ 51 条原始发现 ⇒ ⇒ 合并去重 ⇒ ⇒
**1 条 P0 已修**（bug-2192 · commit `4b374b0`）⇒ ⇒ 本批处理余下的。

⚠️ **本批的判据**：**每条修复都要有「变异自证」** —— 把守卫/判定改回去 ⇒ ⇒
对应断言**必须变红** ⇒ ⇒ 否则不算修完（仓里反复吃过的亏：「断言在、但不敏感于缺陷」）。

**Tech Stack:** FastAPI · SQLAlchemy 2.x async · alembic · pytest（asyncio_mode=auto）· React 18 + antd 5

**关联**：`docs/superpowers/plans/2026-11-17-p10-batch-f-production-readiness.md`（F3/F4 遗留清单）·
`docs/solutions/security-issues/workspace-access-guard-project-or-owner.md`（工作区守卫口径）·
评审产物 `/tmp/compound-engineering-1000/ce-code-review/20261118-151907-0f87af49/report.md`

---

## 任务清单

### G1 · TODO-192 #1 —— `records.py` 三个写端点：**授权在前，类型闸在后** 🔴 P1

现状：`workspace: Workspace = Depends(require_formal_workspace)`（**依赖** ⇒ ⇒ 在函数体
**之前**执行）⇒ ⇒ 无权者先吃 **403 `WORKSPACE_TYPE_NOT_ALLOWED`** ⇒ ⇒
**403 与 404 可区分** ⇒ ⇒ **存在性可枚举**（adversarial + security 独立命中）。

⇒ ⇒ 修法：把「取工作区」与「类型判定」**拆开** ⇒ ⇒ 函数体里**先**授权
（`require_workspace_access_or_404` ⇒ ⇒ 无权 ⇒ ⇒ **404**）**再**判类型
（`WorkspaceTypeNotAllowedError` ⇒ ⇒ **403**）。

- [ ] 三个写端点（`create_piping` · `transition_piping` · `obsolete_piping`）改成
      `workspace: Workspace = Depends(get_workspace)` + 函数体里先授权后判类型
- [ ] 断言：**无权访问别人的 PERSONAL 工作区 ⇒ ⇒ 404**（不是 403）⇒ ⇒ 且与
      「不存在」的 `code` **逐字相同**
- [ ] 断言：**有权的 PERSONAL 工作区 ⇒ ⇒ 403**（类型不允许）⇒ ⇒ 两种情形**可区分**
      ⇒ ⇒ 且这个区分**不泄露存在性**（无权的 PERSONAL 与不存在的 PERSONAL 同形）
- [ ] **变异自证**：把授权调用挪回类型闸之后 ⇒ ⇒ 上面那条 404 断言**必须变红**

### G2 · TODO-192 #2 —— `DefinitionService.update` 补项目授权 🔴 P1

现状：`create()` 查 `require_project_access_or_404`，**`update()` 没查**
⇒ ⇒ 创建人可把定义改挂到**自己没有授权的项目**（5 位评审员独立命中）。

- [ ] `update()` 加 `actor_roles: Sequence[str] | None = None`
- [ ] `project_id` 非空 ⇒ ⇒ **赋值前**调 `require_project_access_or_404`
      （无授权 ⇒ ⇒ **404**，与「不存在」同形）
- [ ] 端点 `report_builder.py::update_definition` 传 `actor_roles=list(actor.roles)`
- [ ] 断言：把定义 `PUT` 到**无授权项目** ⇒ ⇒ **404**（当前是 200）
- [ ] ⚠️ **口径待人裁**：`project_id` 从有项目改成**公司级**（`None`）算不算
      「放宽作用域」？⇒ ⇒ 本批**先只挡「改挂到无授权项目」**⇒ ⇒ 那条另登记
- [ ] **变异自证**：删掉新增的授权调用 ⇒ ⇒ 断言**必须变红**

### G3 · TODO-192 #3 —— `projects.py` 的 owner 自动授权不再造假用户名 🔴 P1

现状：`ensure_user_row(db, user_id=workspace.owner_id, username=f"ws-owner-{workspace.owner_id}")`
⇒ ⇒ 建出一行**`user_id` ≠ `uuid5(username)`** 的 `users` 行 ⇒ ⇒ 破坏派生不变式
⇒ ⇒ owner 之后走真实登录 ⇒ ⇒ `USER_ID_CONFLICT`（409）⇒ ⇒ **owner 进不去自己的项目**。

⇒ ⇒ 修法：**先查**那个 owner 有没有 `users` 行 ⇒ ⇒ 有 ⇒ ⇒ 用**那一行的 username**；
⇒ ⇒ 没有 ⇒ ⇒ **不建行**、**不自动授权**（跳过 ⇒ ⇒ 授权留给
`scripts/seed_user_project_access.py` 那条**有据可查**的路径）⇒ ⇒ 且**明确记一笔**。

- [ ] `owner` 分支改成「查 `users` 行 ⇒ ⇒ 命中 ⇒ ⇒ 用它的 username；未命中 ⇒ ⇒ 跳过授权 + 记审计/日志」
- [ ] 断言：本端点**不创建**任何 `username` 以 `ws-owner-` 开头的 `users` 行
- [ ] 断言：owner 之后走 `issue_tokens(persist_user=True)` ⇒ ⇒ **成功**（不再 409）
- [ ] **变异自证**：把「不建假行」那段删掉 ⇒ ⇒ 断言**必须变红**

### G4 · TODO-192 #4~#7 —— 服务层与守卫的四处对称性 🟠 P2

- [ ] **#4 `obsolete()`**：`publish()` 有身份判定（禁自审 + 项目授权）⇒ ⇒ `obsolete()`
      **一样没有** ⇒ ⇒ 给它同款参数（`actor_user_id` · `actor_roles`）⇒ ⇒ 无权 ⇒ ⇒
      **404**（与「不存在」同形）⇒ ⇒ ⚠️ 「作废算不算审」**是产品语义**（TODO-190）⇒ ⇒
      本批**先按「算」实现**（与 publish 对称）⇒ ⇒ 若人裁「不算」⇒ ⇒ 改回一行
- [ ] **#5 `shared_with`**：项目级分支现在**不看** `shared_with` ⇒ ⇒ `CREATOR_ONLY`
      发布后对全体项目成员可见 ⇒ ⇒ ⚠️ **口径待人裁**（是「项目级一律共享」还是
      「CREATOR_ONLY 仍有效」）⇒ ⇒ **本批先把口径写进代码与文档**（消除「字段与实现不符」）
      ⇒ ⇒ 具体语义等人裁
- [ ] **#6 审计脚本**：`AUTHZ_GUARDS` 补 `require_project_access_or_404` ·
      `require_workspace_access_or_404` ⇒ ⇒ + 一条断言（只挂新守卫的端点 ⇒ ⇒ 判成 `authz`）
- [ ] **#7 `builder_service.py`**：`if scope is not None and user_id is not None:`
      ⇒ ⇒ `user_id is None` 时**整段跳过授权**（fail-open）⇒ ⇒ 改成
      **`user_id` 缺失 ⇒ ⇒ 拒绝执行**（fail-closed）⇒ ⇒ 更新那些传 `user_id=None` 的既有测试

### G5 · TODO-192 #8~#11 —— 口径与棘轮 🟠 P2

- [ ] **#8 `POST /workspaces`**：客户端自填 `project_id` ⇒ ⇒ ⚠️ **授权面影响已被 P0 修
      消除**（守卫不再信任那一列）⇒ ⇒ 只剩「展示字段被污染」⇒ ⇒ 改为**拒绝**带
      `project_id` 的创建请求（400）或**忽略**它 ⇒ ⇒ 需人裁
- [ ] **#9 三种错误码**：API 层 `HTTP_404` / service 层 `PROJECT_NOT_FOUND` /
      `REPORT_DEFINITION_NOT_FOUND` ⇒ ⇒ 「无权 ≡ 不存在」只在**同层内**成立 ⇒ ⇒
      **本批不动**（统一要动 21+ 端点的错误信封）⇒ ⇒ 登记为独立批
- [ ] **#10 admin bypass 口径**：`visible_clause`（SQL 侧）与
      `require_project_access_or_404`（service 侧）对 SYSTEM_ADMIN **不一致** ⇒ ⇒
      统一成一个口径
- [ ] **#11 棘轮**：`AUDITED_PROJECT_SCOPED_ENDPOINTS = 2`（实际 17+）⇒ ⇒ 改成
      **已审端点清单**（不是计数）⇒ ⇒ 让棘轮真能咬（与 **F4-PRE 的 FP-T2** 同一件事
      ⇒ ⇒ **同一处改，别做两遍**）

### G6 · P3（18 条 · 低优先 · 登记不修）

前端 axios 通道（`PipingStatusPanel` 裸 axios · Authorization 头抄到第三份）·
MSW mock 未实现新 403 / publish 403 ⇒ ⇒ **mock 通道继续骗人** ·
前端「保存并发布」永远 403（产品语义 · TODO-191）· `export PCS_TEST_LANE=1` 无守卫 ·
PG 车道只判 running 不判 healthy · PG 车道 pytest 无 timeout 且吞输出 ·
`pool.aclose()` 掩盖 503 · `psql_scalar` 吞退出码 · 真后端脚本对未迁移库开跑 ·
`cleanup_expired` 逐行 DELETE · `workspaces.owner_id` 无索引 · ARQ payload 混版窗口 ·
解法文档 frontmatter 缺 `tags` · 车道判定两个谓词

⇒ ⇒ **P3 不进本批的代码** ⇒ ⇒ 逐条登记进 `TODOS.md` 或本计划末尾的清单。

### G7 · 闸门

- [ ] 默认后端车道（`uv run pytest`）exit 0
- [ ] E2E 车道 + PG 车道 exit 0
- [ ] 前端 typecheck / lint clean · vitest ≥ baseline
- [ ] 契约：`export_openapi.py` ⇒ ⇒ `openapi.json` / `openapi-baseline.json` /
      前端 `openapi.snapshot.json` / `api.d.ts` **四者一致** ⇒ ⇒
      `gate_08_openapi_contract.sh --check-baseline` **exit 0**
- [ ] `TODOS.md` TODO-192 逐条标状态（修 / 转批 / 关闭+理由）

---

## 未解决的问题

1. **#5 `shared_with` 的产品语义**：项目级定义到底「一律共享」还是「`CREATOR_ONLY` 仍有效」？
   ⇒ ⇒ **等人裁**（本批只消除「字段与实现不符」，不替人定语义）。
2. **#8 `POST /workspaces` 的 `project_id`**：拒绝 / 忽略 ⇒ ⇒ **等人裁**。
3. **#9 错误信封统一**：要动 21+ 端点 ⇒ ⇒ **独立批**（不在本批）。
4. **G2 的「改成公司级」**：算不算放宽作用域？⇒ ⇒ **等人裁**（本批只挡「改挂到无授权项目」）。
