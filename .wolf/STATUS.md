---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-26（P9A-DLV-011 **整批评审修复批**收口）。
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

### 第 13 轮续四：**TODO-084 全部落地**（用户「进行 TODO-084」）

评审的 **5 条 deferred minor** 一次做完（每条一个测试 + 一次改动）：
1. 变更单响应的 `sign_status` **不再硬编码** —— service 读交付物**行里的真值**
   并返回，端点用它。
2. `create_change_notice` 在 **service 层**自查 `project_id` 与记录所属项目一致
   ⇒ 422 `CHANGE_NOTICE_PROJECT_MISMATCH` 且**一行都不写**。
3. 矩阵**全部非法**时待办不再**静默消失** ⇒ `todo_service` 记 **error** 日志。
4. （上一轮已裁决）ADR-0002 vs ADR-0008 的驳回矛盾。
5. 变更动作入参由 `ObsoleteRequest` 改为**专用** `ChangeActionRequest`
   （字段/约束**完全相同** ⇒ **纯改名**，行为零变化）⇒ 契约里「发起变更」不再
   长得像「弃用」。
⚠️ 契约影响：OpenAPI **346 → 347 schemas**（+1），paths 246 不变 ⇒ baseline +
前端 `api.d.ts` 已重新生成；裸字段仍 **71**。

### 第 13 轮续三：**TODO-086 落地**（用户「TODO-086 进行」）

- **绑定哈希刷新**：`ChangeNoticeService.refresh_open_bindings` —— 在**重新
  `apply-change`**（记录再次变 CHANGED 的唯一入口）时，把该记录名下**未关闭**
  （deliverable `sign_status != APPROVED`）的变更单绑定刷成「记录当前哈希」+
  「**本次** BEFORE_CHANGE 快照哈希」（与建单同一口径 ⇒ 复用 `_pre_change_hash`）
  ⇒ 与状态迁移**同一事务**。⚠️ **只刷未关闭的**（已 APPROVED 的绑定是**历史
  凭证** ⇒ 改它 = 篡改历史）。
- 新增 `AuditAction.CHANGE_NOTICE_BINDING_REFRESHED`（`String(50)` ⇒ 零迁移）。
- **顺带发现**：`RecordChangeSnapshot.data_snapshot_json` **恒为 `{}`** ⇒ 撤销
  批准的「恢复快照」**空转** ⇒ **撤销只回状态不回数据** ⇒ 登记 **TODO-087**
  + bug-2070（有 xfail 用例钉着）；并**二次更正** ADR-0002 修订记录里我上批写早
  的那句「恢复快照 ⇒ 回到变更前的数据」。
- SPEC **V2.6** · TODO-086 闭环 · buglog bug-2070 / bug-2071。

### 第 13 轮续二：**P9A-DLV-011 收尾批**（用户「解决未解决的问题」）

- **矩阵绑定权限**（用户裁决「**只有项目负责人能绑**」）⇒ 三层判定：全局角色 +
  项目授权 + 项目内角色 = **新增的 `PROJECT_LEAD`**（依据校审层级 SPEC §2.1.2
  「项目负责人（新增）」；`role_in_project` **无 DB CHECK 约束 ⇒ 不需要迁移**）。
  ⚠️ 这是全仓**唯一**按项目内角色鉴权的守卫（例外已写进 docstring）。
- **ADR-0002 vs ADR-0008 的「变更单驳回」矛盾** ⇒ 裁决 **ADR-0008 管辖**
  （单据回 DRAFT、**记录保持 CHANGED**）；「重改」路径 = **撤销 → 重来**
  （request-reversal → approve-reversal 恢复快照 → CHECKED ⇒ 再 initiate-change）
  ⇒ 已由 `test_rejected_notice_can_be_reworked_via_reversal` 端到端钉住；
  两份 ADR 各加**修订记录**。
- **前端两个缺口闭环**（TODO-079 + TODO-083）：矩阵管理页
  `/deliverables/signature-matrices` + 结果记录行上的变更动作（**按状态只给一个
  按钮**：变更申请 / 提交变更完成 / 创建变更单）。
- 顺带**更正 UI-SPEC §6.3 的错误登记**（本批第一次写错了按钮归属）。
- 新登记 **TODO-085**（矩阵修改的申请+双审未实现）· **TODO-086**（重走后绑定
  哈希漂移）。

### 第 13 轮续：**P9A-DLV-011 整批评审**（`3f68722`）—— 3 CRITICAL + 8 IMPORTANT 全修

- **C-1** `PUT /signature-matrices/{id}` 每次真实修改都 500（`updated_at` 是服务端
  表达式 ⇒ 懒加载 ⇒ `MissingGreenlet`）⇒ 补 `db.refresh`。
- **C-2** 驳回一次后 `issue` 永久 500（`MultipleResultsFound`）⇒ 探针改
  `.first()` + `limit(1)`。
- **C-3** TODO-068 闭环文案过度声称（守卫在 `cda6e40`，评审范围外）⇒ 更文案 +
  登记 `locked_by_deliverable` 死闸门（**TODO-082**）。
- **I-1** `_ensure_binding` 的 SAVEPOINT **无效**（`add` 在外 ⇒ 事务被打断）
  ⇒ `add` 移进 savepoint + 恢复分支**只读不写**（消掉 lost update）。
- **I-2** `bind_to_project` 并发 ⇒ 500 + 不校验 ACTIVE/模块 ⇒ SAVEPOINT + 两道 422。
- **I-4** `sign_step` 读**活矩阵** ⇒ 改小模板把在飞版本**永久卡死** ⇒ 新增
  `_steps_for_version`（**版本快照优先**）。
- **I-5** 绑定权限比用户裁决宽（**VIEWER 也能绑**）⇒ 新增
  `require_active_project_member`（项目内角色不是 VIEWER 才放行；不用「≥
  DESIGNER」——`role_in_project` 词表是**平行职责不是等级**）⇒ 计划 R-8 口径修订。
- **I-6** 5 个新端点没有 404 授权测试 ⇒ 新增
  `test_p9a_dlv_011_authorization.py`（6 例，**不套** ACL bypass mock）。
- **I-7** `require_formal_workspace` 与 `app/api/deps.py` **同名撞车**（一个
  fail-closed 一个 fail-open）⇒ 改名 `require_formal_project_workspace`。
- **I-3 / I-8** 补登记 + 补两条「响亮失败」分支的测试。

修复批后：后端 **5242 passed / 0 failed**；两库 `alembic check` 各 exit 0；
裸字段仍 71；G-08 门禁 exit 0。SPEC **V2.4** + README 计数（`p9_008` /
246 path / 346 schema）+ TODO-069/076 更新 + 新增 **TODO-082**（死闸门）/
**TODO-083**（变更单前端入口没 TODO）· buglog 新增 bug-2060~2065。

### 上一轮：**P9A-DLV-007 + TODO-057**（签署矩阵的取得 + 变更单观测写入点）—— 已完成

见 `docs/PCS-PLAN-P9A-DLV-007-…`；SPEC V2.2（workflow_progress 三工作流 2/3 → **3/3**）。

---

## 🚀 Next quest

1. **P9B-2**：签署流程前端（操作栏 / 批注 / 状态时间线）+ ADMIN 前端（用户管理 /
   审计日志）+ **两个后端前置**（**TODO-065** 聚合端点 `GET /deliverables/{id}/progress`、
   **TODO-066** 按项目守卫的编辑审计读端点）。
   ⚠️ 计划 `docs/PCS-PLAN-P9B-2-签署流程与ADMIN前端.md` **尚未过 `/plan-eng-review`**。
2. **P9B-3**：系统参数前端 + 物流手动创建向导 + 校对 UI。
3. **本批遗留**（TODO-073~078 · 080 · 082 · 084 · 085 · 086）：变更单编号改走编号
   模板 · 矩阵名唯一约束 · `change_resolved_by` 语义（状态机与 ADR-0002 冲突）·
   工作区门禁只覆盖本批端点（+ 两条 fail-open 分支）· `apply-change` 不校验 hash ·
   多记录变更 · **`locked_by_deliverable` 死闸门**（TODO-082）· **矩阵修改的申请 +
   双审**（TODO-085）· **重走后绑定哈希漂移**（TODO-086）· 4 条 minor（TODO-084）。
   ⇒ TODO-079 / TODO-083 / TODO-084（5 条 minor）/ TODO-086 **已闭环**；
   新增 **TODO-087**（撤销**不恢复**数据 —— 快照恒空）。
   ⇒ 仍开着：TODO-077（apply-change 不校验 hash）· TODO-078（变更单取消路径）·
   TODO-085（矩阵修改的申请 + 双审）· TODO-087（快照恒空）· TODO-080（3 条旧 minor）·
   约束 · `change_resolved_by` 语义（状态机与 ADR-0002 冲突）· 工作区门禁只覆盖本批
   端点（+ 两条 fail-open 分支）· `apply-change` 不校验 hash · 多记录变更 ·
   **矩阵管理前端**（TODO-079）+ **变更单前端入口**（TODO-083）·
   **`locked_by_deliverable` 死闸门**（TODO-082）· 评审 deferred minor。
   ⚠️ 另有 **5 条 minor** 未修 ⇒ 已登记 **TODO-084**（M-3 硬编码 sign_status /
   M-4 service 不校验 project_id / M-5 todo_service 缺日志 /
   M-7 **ADR-0002 vs ADR-0008 驳回矛盾** / M-8 复用 `ObsoleteRequest`）。
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
  ⇒ 要测 404 必须用 `_guard_client`（独立 client，不套那个 mock）。
- ⚠️ **in-memory SQLite 的 StaticPool 让 `db` 与独立 client 共用同一条连接**
  ⇒ 独立 client 退出时的 rollback 会把 `db` 这边**未提交**的 INSERT 一起回滚
  ⇒ 造完 fixture 必须先 `await db.commit()`，否则 `db.refresh` 报
  「Could not refresh instance」。

---

## 教训（本会话新增 3 条，已进 cerebrum）

- **要签署的东西必须有版本行**：绑了矩阵 ≠ 矩阵生效（没有版本行 ⇒ 进不了签署 ⇒
  审批只能绕过矩阵 ⇒ 矩阵成装饰品且没人发现）。
- **关联走表，不走字符串**：多态关联（对象 ↔ 对象）要专门的关联表；字符串只能当
  scope / 展示用，两者并存时用**守卫测试**钉住一致。
- **唯一约束会揭穿依赖非法状态的测试**：加约束后测试红了，先看它依赖了什么状态，
  别急着改产品代码（红的症状常常指向别处）。
- **SAVEPOINT 必须包住 `db.add()`**：`Session.begin_nested()` 在发出 SAVEPOINT
  **之前**会先 flush pending ⇒ savepoint 外的 INSERT 撞约束时 PostgreSQL 会
  **中止整个事务** ⇒ 「只回滚这一段」的意图落空。
- **「有等级」的词表要先确认它真有等级**：`role_in_project`（DESIGNER/CHECKER/
  REVIEWER/APPROVER/VIEWER）是**平行职责** ⇒「≥ DESIGNER」无定义 ⇒ 只能取唯一
  真实的等级语义「只读 vs 参与」。
