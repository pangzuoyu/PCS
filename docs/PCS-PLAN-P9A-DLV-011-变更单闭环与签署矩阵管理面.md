# P9A-DLV-011 实施计划：变更单闭环（HTTP 面）+ 签署矩阵管理面

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`
> ledger: `.superpowers/sdd/PCS-PLAN-P9A-DLV-011-变更单闭环与签署矩阵管理面/progress.md`

**Goal:** 闭环 **TODO-068~072**（用户 2026-10-26 裁决：068 全闭环 / 070 分层权限 / 只做后端）：
变更单从「service 层可达」变成「**用户可达且真能走完**」，签署矩阵从「只能惰性建内置模板」
变成「**可管理、可校验**」。

**Architecture:** 变更单走**既有交付物签署机制**（ADR-0008「一套交付物状态机」）——
建单即建版本（ISSUED_FOR_CHANGE）+ 绑记录 + 观测行，签署走 `POST /deliverables/{id}/sign-step`
（3 级矩阵 `CHANGE_NOTICE_3_LEVEL`），**最后一步签完自动关记录**（CHANGED → CHECKED）。
矩阵管理面是独立的一组 service + 端点（模板全局 / 绑定项目，分层权限）。

**Tech Stack:** FastAPI + SQLAlchemy 2.x async + pytest（内存 SQLite）。

**Spec:**
- `docs/adr/0008-change-notice-as-deliverable-subtype.md`（变更单 = 交付物子类型；APPROVED 后
  **系统自动** CHANGED → CHECKED；驳回回 DRAFT；默认 3 级矩阵；版本目的 ISSUED_FOR_CHANGE）
- `docs/adr/0002-changed-lifecycle-and-change-notice.md`（CHECKED → CHANGE_PENDING → CHANGED）
- `docs/adr/0047-workflow-progress-observation-layer.md` §①（唯一写入口）
- `docs/PCS-UI-SPEC.md` §5.3（工作区门禁：创建变更单限 FORMAL）§6.3（记录操作按钮组）
- `spec/PCS-REQ-2026-002-SPEC-P9 …` §3.2.1 / §7.2.1
- `TODOS.md` **TODO-068~072**

---

## Global Constraints

1. **观测写入只有一个入口**：`workflow_progress_writer.record_step`（ADR-0047 §① 🔒）。
2. **写入层在 service 层**（同上）⇒ 观测写不落 API 层。
3. **同一事务**：变更单的建单 / 版本 / 绑定 / 观测 / 审计**一次提交**。
   ⇒ `DeliverableService.issue` 现状是「自己 commit」⇒ 需抽出**不 commit** 的版本创建 helper。
4. **不改前端**（用户裁决：只做后端）⇒ 契约变更是允许的（新增端点），前端按契约接入。
5. **提交约定**：conventional commits，无 attribution 行；长消息写文件后 `git commit -F`。
6. ⚠️ **不建 worktree**（本仓历史事故）。
7. ⚠️ **本批改迁移**（TODO-071 唯一约束）⇒ 必须**全新库**验证 + 两库各跑一次 `alembic check`。

## Review Focus

| # | 失败模式 | 期望行为 | 归属 |
|---|---|---|---|
| RF-1 | **矩阵是装饰品** —— 变更单绑了 3 级矩阵，审批却绕过矩阵直接批准 | 签署只走 `sign-step`；矩阵角色/顺序生效 | T4 |
| RF-2 | **记录永远到不了 CHANGED** ⇒ 建单端点不可达 | 补 `initiate-change` / `apply-change` 两个端点 | T4 |
| RF-3 | **驳回后变更单卡死**（DRAFT ⇒ sign-step 409、issue 409 ⇒ 永远签不了） | 退回后允许再次签发新版本 | T4 |
| RF-4 | **自动关记录漏了/错了记录** | 记录由 binding 行反查（不是解析字符串）；关不到 ⇒ 响亮失败 | T4 |
| RF-5 | **矩阵绑定重复**（并发 ⇒ 同项目同模块两个绑定） | 唯一约束 + IntegrityError 兜底 | T2 |
| RF-6 | **坏 steps_json 进库** ⇒ 签署少一道校审 | 写入时**严格校验**（任一项非法 ⇒ 422，不部分跳过） | T3 |
| RF-7 | **越权管理矩阵**（普通用户改全局模板 ⇒ 影响别的项目） | 模板 = SYSTEM_ADMIN；绑定 = 项目内 DESIGNER+ | T3 |
| RF-8 | **两个真相源**（记录↔变更单的关联写两处且会漂） | binding 行为权威；scope_value 仅为 scope；守卫测试钉住两者一致 | T1 |

---

## 事实基础（2026-10-26 实测）

### 缺口 1：记录到不了 CHANGED

`ALLOWED_TRANSITIONS` 里有 `CHECKED --INITIATE_CHANGE--> CHANGE_PENDING` 与
`CHANGE_PENDING --APPLY_CHANGE--> CHANGED`，但 **`INITIATE_CHANGE` / `APPLY_CHANGE`
全仓没有任何 API 或 service 触发**（`grep` 只命中状态机表、快照逻辑、审计映射）。
⇒ `create_change_notice` 要求记录是 CHANGED ⇒ **记录永远到不了 CHANGED**
⇒ 建单端点即使写出来也不可达。

### 缺口 2：变更单没有版本 ⇒ 签不了

`create_change_notice` 建的是 `deliverables` 一行（`current_rev="0"`，**无版本行**）。
`sign_step` 要求 `version_id` ⇒ 变更单**无法进入签署流程**。
⇒ ADR-0008「一套交付物状态机、一套版本历史」对变更单**未兑现**。

### 缺口 3：审批绕过了矩阵

`ChangeNoticeService.approve_change_notice` 直接 `PENDING → APPROVED`（不查矩阵、不查角色）
⇒ 绑定的 `CHANGE_NOTICE_3_LEVEL` **纯装饰**。而 ADR-0008 明写「变更单 APPROVED 后
**系统自动**将绑定记录 CHANGED → CHECKED」——「自动」意味着触发点在**把状态推成 APPROVED 的地方**
（= `sign_step` 的最后一步），不是另一个手工端点。

### 缺口 4：记录↔变更单的关联只存在字符串里

`change_notice_details` 有 `source_record_type` 但**没有 `source_record_id`**；
关联只体现在 `deliverables.scope_value`（本仓上批自造的 `"CHANGE_NOTICE:{表名}:{id}"`）
⇒ 自动关记录只能解析字符串。

**ADR-0008 已指定正解**：「`deliverable_record_bindings` 增加
`old_record_hash_before_change` 字段承载新旧哈希对比（**替代原
`change_notice_record_bindings`**）」⇒ 关联走 `deliverable_record_bindings`
（其 `deliverable_version_id` FK ⇒ **变更单必须有版本行** ⇒ 与缺口 2 的修法一致）。

### 既有可复用的东西

- `sign_step`：顺序推进、角色判定、`can_self_check`、`can_skip`、RETURN ⇒ DRAFT、
  最后一步 SIGN ⇒ APPROVED —— **ADR-0008 的「被驳回则回 DRAFT」已天然满足**。
- `issue`：建版本 + 定 rev + 推进 DRAFT → PENDING + 审计（但**自己 commit**）。
- `StateMachineService.transition`：ACL（`TRANSITION_ROLES`）+ 非法转移 409 +
  INITIATE_CHANGE 自动写 BEFORE_CHANGE 快照 + APPLY_CHANGE 写 `change_resolved_*`。
- `deliverables` 列表/详情端点已支持 `deliverable_type=CHANGE_NOTICE` 过滤 ⇒ 读面够用。

### 数据现状（开发库 `pcs` 实测）

`project_signature_matrix_bindings` 0 行、`signature_matrices` 0 行、
`deliverables`（CHANGE_NOTICE）0 行、`change_notice_details` 0 行
⇒ 加唯一约束**不需要去重**。

---

## 裁决

| # | 裁决 | 理由 | 代价 |
|---|---|---|---|
| **R-1** | 变更单**签署只走 `sign-step`**；`approve_change_notice` **不再作为审批入口**（保留为内部「关记录」步骤） | ADR-0008「系统自动」+ 一套状态机 ⇒ 矩阵角色生效（RF-1） | 旧接口语义变化 ⇒ 旧测试改写；`approve_change_notice` 的「直接批准」路径被弃用（登记） |
| **R-2** | 记录↔变更单的关联写 **`deliverable_record_bindings`** 一行（version_id + record_type + record_id + record_hash + old_record_hash_before_change） | ADR-0008 明写用它替代 `change_notice_record_bindings`（RF-4） | binding 的 `deliverable_version_id` ⇒ 变更单必须有版本（与 R-3 同向） |
| **R-3** | 建单时**同时建版本行**（`version_purpose=ISSUED_FOR_CHANGE`，rev=1）+ 交付物 DRAFT → PENDING | 没有版本就进不了签署（缺口 2） | 建单事务多 2 行；`issue` 需抽出不 commit 的 helper（重构已验收路径） |
| **R-4** | 「自动关记录」的触发点 = `sign_step` 里**最后一步 SIGN 置 APPROVED 之后** | 「自动」= 状态推成 APPROVED 的那一刻（缺口 3） | `sign_step` 多一个类型守卫分支（只对 `deliverable_type='CHANGE_NOTICE'` 生效） |
| **R-5** | `issue` 的幂等判据从「有版本」放宽为「有**未退回**的版本」：交付物处于 DRAFT（退回过）⇒ 允许再签发新版本 | 否则驳回后变更单**永久卡死**（RF-3） | 普通交付物多一条可重签路径（此前 DRAFT 状态本来就能 issue，语义不变） |
| **R-6** | `doc_no` = `CN-{record_id.hex.upper()}`（**完整 32 位 hex**，不再取前 8 位） | 前 8 位 = 32 bit ⇒ 同项目 ~65k 张单即可能撞 `uq_deliverables_doc_no` ⇒ 500 | 编号可读性下降 ⇒ 登记「变更单编号改走编号模板」 |
| **R-7** | 「一条记录同时只有一张变更单」保留（409），判重依据 = `scope_value`（`uq_deliverables_scope` 已保证唯一）；binding 行与之**由守卫测试钉住一致** | 避免两份关联各写各的（RF-8） | scope_value 与 binding 仍有两处 ⇒ 用测试钉住 |
| **R-8** | 矩阵管理权限**分层**：模板（全局表）增删改 = **SYSTEM_ADMIN**；项目绑定 = 全局角色 ∈ {DESIGNER, PROCESS_CONTROLLOR, SYSTEM_ADMIN} **且** 有该项目授权 **且** 项目内角色 = **项目负责人**（`PROJECT_LEAD`） | 全局表若让项目角色可改 ⇒ 一个项目能改到别的项目在用的模板；**用户 2026-10-26 裁决「只有项目负责人能绑」** | ⚠️ `role_in_project` 词表是**平行职责不是等级** ⇒「DESIGNER 及以上」**无定义** ⇒ 引入 **`PROJECT_LEAD`**（项目负责人）这个**项目级**角色（依据 `spec/校审层级可配置化增补规格说明书.md` §2.1.2「项目负责人（新增）」）⇒ 该角色由 `user_projects` 授予；`role_in_project` 列**无 DB CHECK 约束** ⇒ 加这个角色**不需要迁移** |
| **R-9** | `steps_json` **写入时严格校验**（任一项非法 ⇒ 422，不部分跳过）；`parse_steps` 的「部分跳过」只留给**存量脏数据** | 「签署少一道校审」比报错更危险（RF-6） | 存量脏矩阵仍走部分跳过路径（要日志） |
| **R-10** | 变更单相关端点**只做后端**；工作区门禁（UI-SPEC §5.3 创建变更单限 FORMAL）**本批实现**（项目 → workspace → FORMAL，否则 403） | UI-SPEC 明写；且项目必有 workspace ⇒ 门禁可判定 | 只覆盖本批端点；全端点的工作区门禁仍缺 ⇒ 登记 |
| **R-11** | `apply-change`（CHANGE_PENDING → CHANGED）**不要求 hash 变化** | ADR-0002 只说「校核完成」；发明「必须改过」是加需求 | 可能出现「没改内容也关了变更」 ⇒ 登记 |

| **R-11′** | **推翻 R-11**：`apply-change` **要求记录真的改过** —— 哈希与发起变更时的 BEFORE_CHANGE 快照相同 ⇒ 409 `CHANGE_NO_MODIFICATION` | 2026-10-26 **业务裁决**（TODO-077）：R-11 当初的顾虑（「发明『必须改过』是加需求」）已被后续证据推翻 —— ①ADR-0002 的 CHANGE_PENDING = 「**获准修改**、正在改+重校核」⇒「提交变更完成」= 有变更完成了；②确实无需修改的正确动作是「**放弃变更**」（ABANDON_CHANGE → CHECKED），不是提交完成；③不拦 ⇒ 一条**没有实质变更**的记录被关掉，而变更单里写着「管径修正」⇒ 凭证说的不是事实（ADR-0002「防止无声修改」被架空） | ⚠️ 「重新校核后确认无需修改」的场景现在会被 409 挡住（可改用「放弃变更」）—— 这是**有意的**：那条路会留下「变更完成」的假凭证 |
---

## 文件结构

**新建**（5 个）：

| 文件 | 职责 |
|---|---|
| `pcs-backend/app/schemas/signature_matrix.py` | 矩阵 CRUD + 绑定的请求/响应模型 |
| `pcs-backend/app/api/v1/signature_matrices.py` | 矩阵管理端点（6 个） |
| `pcs-backend/tests/api/v1/test_signature_matrix_api.py` | 矩阵管理面守卫 |
| `pcs-backend/tests/api/v1/test_change_notice_api.py` | 变更单闭环端点守卫 |
| `pcs-backend/alembic/versions/p9_008_*.py` | 唯一约束迁移（TODO-071） |

**修改**（6 个）：

| 文件 | 改什么 |
|---|---|
| `pcs-backend/app/services/signature_matrix_service.py` | + CRUD + 绑定 + **严格校验**（R-9） |
| `pcs-backend/app/services/change_notice_service.py` | 建单加**版本 + binding**；`approve_change_notice` 改为内部「关记录」 |
| `pcs-backend/app/services/deliverable_service.py` | 抽不 commit 的版本 helper；`issue` 幂等放宽（R-5）；`sign_step` 末尾挂**自动关记录**（R-4） |
| `pcs-backend/app/models/deliverable.py` | `ProjectSignatureMatrixBinding` 加 `UniqueConstraint(project_id, module)` |
| `pcs-backend/app/api/v1/records_actions.py` | + `initiate-change` / `apply-change` / `change-notice` 三个端点 |
| `pcs-backend/app/api/v1/__init__.py` | 注册矩阵路由 |

---

## Task T1：建单 = 交付物 + 版本 + 记录绑定（TODO-069 · R-2/R-3/R-6/R-7）

**改**：`change_notice_service.py`、`deliverable_service.py`（抽 helper）

1. **RED**（`tests/services/test_change_notice_service.py` 增补）：
   - 建单 ⇒ 交付物有**版本行**（`version_purpose=ISSUED_FOR_CHANGE`、rev=1）且
     `sign_status=PENDING`、`current_rev="1"`；
   - 建单 ⇒ `deliverable_record_bindings` 有一行：`deliverable_version_id` = 那个版本、
     `record_type`/`record_id` 对得上、`record_hash` = 记录当前 hash、
     `old_record_hash_before_change` = INITIATE_CHANGE 时的快照 hash（无快照 ⇒ None）；
   - `doc_no` = `CN-{record_id.hex.upper()}`（全 32 位）；
   - 同记录第二张仍 409；**不同**记录两张都成；
   - scope_value 与 binding 的 `record_type:record_id` **一致**（RF-8 守卫）。
2. **实现**：
   - `DeliverableService.create_version_row(...)` —— **不 commit**，返回版本行
     （`issue` 改为调它 + 审计 + commit，行为不变）；
   - `create_change_notice` 调它 + 建 binding + 观测 + 审计 + **一次 commit**。
3. **GREEN** + 全量后端。

## Task T2：唯一约束迁移（TODO-071 · RF-5）

1. 迁移 `p9_008`：`project_signature_matrix_bindings` 加 `uq (project_id, module)`；
   ORM 同步声明（⇒ `alembic check` 不报漂移）。
2. **全新库验**（隔离 schema：`search_path` + `alembic upgrade head`）—— CI 会跑全新库。
3. 两库各跑一次 `alembic check`（退出码 255 才算检出）。
4. `ensure_change_notice_matrix` / `_ensure_binding` 捕获 IntegrityError ⇒ 重新读
   （并发安全，RF-5）+ 测试。

## Task T3：矩阵管理面 + 严格校验（TODO-070 + TODO-072 · R-8/R-9）

1. **service**：`create_matrix` / `update_matrix` / `list_matrices` / `get_matrix` /
   `bind_to_project` / `unbind_from_project` + `validate_steps`（严格，任一项非法 ⇒ 422）。
2. **API**（6 端点，分层权限 R-8）+ schemas（**零裸字段**，P9A-DLV-010 硬约束）。
3. **测试**：service + API 两层。

## Task T4：变更单闭环的 HTTP 面（TODO-068 · R-1/R-4/R-5/R-10/R-11）

1. `POST /records/{module}/{id}/initiate-change`（CHECKED → CHANGE_PENDING）
2. `POST /records/{module}/{id}/apply-change`（CHANGE_PENDING → CHANGED）
3. `POST /records/{module}/{id}/change-notice`（建单；FORMAL 工作区门禁）
4. **自动关记录**：`sign_step` 最后一步 SIGN ⇒ APPROVED ⇒ 记录 CHANGED → CHECKED +
   `change_resolved_by` + CHANGE_NOTICE 观测 COMPLETED + 审计（同一事务）
5. **驳回后再签发**（R-5）+ 测试

## Task T5：收口

- [ ] `uv run pytest -q` 全绿；`alembic check` 两库各一次（255 才算检出）
- [ ] 全新库 `alembic upgrade head` 验过
- [ ] `gate_08_openapi_contract.sh --check-baseline`（本批**新增端点** ⇒ baseline 要滚）
- [ ] `check_openapi_payload_coverage.py`（裸字段数不上涨，基线 71）
- [ ] `.wolf/buglog.json` / `TODOS.md`（068~072 闭环 + 新登记）/ `TODOS.md` SPEC 登记
- [ ] SPEC **V2.3**：§3.2.1 加 `P9A-DLV-011` 行；§7.2.1 状态更新；UI-SPEC §6.3 修订注记
- [ ] `.wolf/STATUS.md`

## 验收（全 lane）

- [ ] 记录 CHECKED →（initiate-change）→ CHANGE_PENDING →（apply-change）→ CHANGED
- [ ] CHANGED →（change-notice）→ 变更单（有版本 + 有 binding + 有观测 PENDING）
- [ ] 变更单 3 级矩阵**真的生效**：错角色 403、越步 409、顺序推进
- [ ] 最后一步 SIGN ⇒ 记录自动 CHANGED → CHECKED + `change_resolved_by` + 观测 COMPLETED
- [ ] 退回 ⇒ 变更单回 DRAFT + 记录保持 CHANGED + 可再次签发并签完
- [ ] 矩阵管理：模板 SYSTEM_ADMIN 才能改；项目绑定 DESIGNER+ 才能做；坏 steps_json 422
- [ ] 同项目同模块只有一个绑定（唯一约束）
- [ ] 后端全量绿；契约门禁过；裸字段不涨

## 尚未解决的问题（开工前需裁决或登记）

1. **变更单编号改走编号模板**（R-6 的代价）：`CN-{32位hex}` 只是唯一，不是可读编号。
2. **`change_resolved_by` 被写两次**：状态机 `APPLY_CHANGE` 就写了（校核完成时），
   ADR-0002 说它是「变更单关闭人」⇒ 最终值由关记录那步覆盖，但中间值语义不对 ⇒ 登记。
3. **工作区门禁只覆盖本批端点**：全端点的 FORMAL 门禁仍缺 ⇒ 登记。
4. **`apply-change` 不要求 hash 变化**（R-11）⇒ 可能「没改内容也关变更」⇒ 登记。
5. **矩阵管理面前端没有**（用户裁决只做后端）⇒ 前端页另批。
6. **变更单与记录的多对多**：现在一条变更单只绑一条记录（ADR-0002 的场景够用），
   但「一次变更影响多条记录」未支持 ⇒ 登记。

---

## 执行结果（2026-10-26 完成）

| 任务 | 状态 | commit |
|---|---|---|
| 评审修复批（P9A-DLV-007 的 1 IMPORTANT + 4 minor） | ✅ | `9da0810` |
| T1 建单 = 交付物 + 版本 + 记录 binding | ✅ | `9a4f66b` |
| T2 唯一约束迁移 | ✅ | `4724573` |
| T3 矩阵管理面 + 严格校验 | ✅ | `35a5bc8` |
| T4 变更单闭环 HTTP 面 | ✅ | `b18cbbc` |
| T5 收口 | ✅ | 本提交 |
| **整批评审修复批**（3 CRITICAL + 8 IMPORTANT） | ✅ | `3f68722` |

**与计划的偏差**（裁决见 ledger）：

1. **T2/T3 提前到 T4 之前**：计划原本 T2 在 T3 后 —— 实际「矩阵绑定端点依赖唯一
   约束兜底」⇒ 唯一约束必须先落。
2. **计划没写「记录到不了 CHANGED」这个缺口**的解法只到端点层 —— 实测发现
   `INITIATE_CHANGE` / `APPLY_CHANGE` **全仓无触发点** ⇒ 补两个端点（计划 R-11
   之外的额外发现，已登记 bug-2056）。
3. **评审抓到的 IMPORTANT 插在 T1 之前修**（`todo_service` 第二份解析）——
   它是「上批的验收项与代码不符」，先修再往下走。
4. **`issue` 抽出 `create_version_row`**（计划未提）：建单要「交付物 + 版本 +
   binding + 观测」同一事务，而 `issue` 现状**自己 commit** ⇒ 必须能只建行、
   不提交。

**验收结果**：

- 后端全量：**5226 passed / 77 skipped / 0 failed**（基线 5188，+38；含 9 个新端点的
  20 条 API 用例 + 26 条 service/schema/迁移用例）
  ⚠️ 首轮跑出过 1 个 `test_export_perf_budget`（导出耗时的 2 秒墙钟预算）—— 单独跑绿、
  重跑全绿 ⇒ **计时类 flake**（本仓此前已为同类 flake 放宽过全局超时），与本批无关。
- `alembic check`：`pcs` 与 `pcs_test` **各跑一次**均 exit 0（两库 `p9_008` head）
- **全新隔离 schema** 从零 `alembic upgrade head` 通过（CI 的 api-drift job 跑的
  就是全新 Postgres）
- `gate_08_openapi_contract.sh --check-baseline`：exit 0（baseline 已滚）
- `check_openapi_payload_coverage.py`：exit 0（裸字段仍 **71**，未上涨）

---

## 整批评审（2026-10-26）

评审范围 `9a4f66b`~`e93d3bb` ⇒ **3 CRITICAL + 8 IMPORTANT + 8 minor**。
CRITICAL + IMPORTANT 一次修完（`3f68722`），minor 进 ledger 延后。

| # | 级别 | 问题 | 处置 |
|---|---|---|---|
| C-1 | CRITICAL | `PUT /signature-matrices/{id}` 每次真实修改都 500（`updated_at` 服务端表达式 ⇒ 懒加载 ⇒ `MissingGreenlet`） | 补 `db.refresh` + 测试 |
| C-2 | CRITICAL | 驳回一次后 `issue` 永久 500（`MultipleResultsFound`） | 探针改 `.first()` + `limit(1)` |
| C-3 | CRITICAL | TODO-068 闭环文案过度声称（守卫在 `cda6e40`，评审范围外） | 更文案 + 登记 `locked_by_deliverable` 死闸门（TODO-082） |
| I-1 | IMPORTANT | `_ensure_binding` 的 SAVEPOINT 无效（`add` 在外） | `add` 移进 savepoint + 恢复分支只读 |
| I-2 | IMPORTANT | `bind_to_project` 并发 ⇒ 500；不校验 ACTIVE / 模块 | SAVEPOINT 恢复 + 两道 422 |
| I-3 | IMPORTANT | 「第二次变更 ⇒ 记录卡在 CHANGED」没登记 | 补进 TODO-069 |
| I-4 | IMPORTANT | `sign_step` 读活矩阵 ⇒ 改小模板把在飞版本卡死 | 新增 `_steps_for_version`（快照优先） |
| I-5 | IMPORTANT | 绑定权限比用户裁决宽（VIEWER 也能绑） | 新增 `require_active_project_member`；**R-8 口径随之修订** |
| I-6 | IMPORTANT | 5 个新端点没有 404 授权测试 | 新增 `test_p9a_dlv_011_authorization.py`（6 例，不套 ACL bypass mock） |
| I-7 | IMPORTANT | `require_formal_workspace` 与 deps 版撞名 | 改名 `require_formal_project_workspace` + 登记 fail-open 分支 |
| I-8 | IMPORTANT | 两条「响亮失败」分支零测试 | 补 2 例 |

修复批后验收：后端 **5242 passed / 77 skipped / 0 failed**（+16）；
两库 `alembic check` 各 exit 0；裸字段仍 71；G-08 门禁 exit 0。
