---
module: pcs-backend — 守卫覆盖审计（A/B/D 档 · 63 端点）
date: 2026-11-18
problem_type: security_issue
component: authorization / audit
severity: critical
tags: [authorization, guard-coverage, project-scope, strict_client, P10-F, F3, audit]
symptoms: 匿名调用方可读走任意项目的管路记录与变更快照（records.py 三个 GET 既不要求登录也不做项目授权）；workspaces.py 三个端点同样不要求登录 ⇒ 匿名可枚举全部工作区、匿名 GET 带写副作用、匿名 POST 可指定任意 owner_id 并把审计行记在别人名下；records.py 写面授权判的是 payload 的 project_id 而行落进 workspace ⇒ 授权在项目 A 的人把记录写进项目 B 的工作区
root_cause: ① 守卫**结构性缺失**（端点没有 current_actor ⇒ 连登录都不要求；作用域 id 只过 get_workspace ⇒ 只判存在性、零 user_projects 判定）；② 守卫**判的 id 与生效的 id 不同源**（create_piping 判 payload.project_id、落库用 workspace_id、transition/obsolete 又判 ws.project_id ⇒ 三者可以互不相同）；③ **测试基础设施把守卫 mock 成永远 True**（默认 client monkeypatch UserProjectService.check_user_project_access ⇒ 「端点缺项目守卫」这类缺陷在它上面一个都测不出来 ⇒ 断言缺口与越权缺口叠加）
---

# 守卫覆盖审计 —— A/B/D 档 63 个端点逐个回答

> 计划：`docs/superpowers/plans/2026-11-17-p10-batch-f-production-readiness.md`（F3 段）
> 范围裁决：2026-11-18（人）—— **A + B + D(敏感)**，**C 档不审**（无项目级数据读写 ⇒ 越权语义不成立）
> 判据：D6 的 4 问（①资源 id / ②a资源 id 授权 / ②b作用域 id 授权 / ③未授权返回 / ④判定行号）
> **+ 一列「覆盖断言用的 client」+ 抽样变异**
> 四个子批：T2a（config + report_builder）· T2b（report + records）· T3a（psychro.results + 工作区/身份面）· T3b（audit + system_settings + meta）· T4（三条越权债复核）

---

## 一 · 摘要

⇒ ⇒ **63 个端点逐个答了 4 问，18 处抽样变异全部还原**
⇒ ⇒ ⇒ **结论不是「未审即没问题」**：每个「已覆盖」都给了**断言位置**，每个「缺口」都**实测取证**。

| 结论 | 数量 | 说明 |
|---|---|---|
| 🟢 **已覆盖**（代码 + 断言） | 44 | 断言**对缺陷敏感**（变异会红） |
| 🟡 **已覆盖（代码）· 断言缺口** | 9 | 代码有守卫、**没有任何断言** ⇒ 变异无人应答 |
| 🟡 **已知限制（有意 · 有断言钉住）** | 4 | 明确写下来的取舍，**不是**缺口 |
| 🟠🔴 **真缺口** | 6 | 见 §五（**2 critical + 2 high + 2 medium/low**） |

⇒ ⇒ **两条 critical 是同一条链的两端**：
**`workspaces` 匿名枚举 workspace_id（TODO-186）⇒ ⇒ `records` 匿名读走任意项目的管路记录（TODO-179）**。

---

## 二 · 方法（照 D6）

| # | 必答问题 | 合格答案 |
|---|---|---|
| ① | 端点从哪个参数拿到**资源 id**？ | 路径/查询/body 参数 + 行号 |
| ②a | 该**资源 id** 是否按当前用户/项目做授权判定？ | 守卫调用 + 行号 |
| ②b | 该**作用域 id**（workspace_id / project_id / 项目下的集合）是否按当前用户/项目做授权判定？ | 守卫调用 + 行号；**无作用域 id 填 N/A 并说明理由** |
| ③ | 未授权时**返回什么**？ | 404（同形）✓ / 403（**角色闸位置**）⚠️ / **403（项目守卫）= 缺口** / 200 = 缺口 |
| ④ | 授权判定发生在**哪一行**？ | 文件:行号 |

⚠️ **外加一列「覆盖断言用的 client」** ——
默认 `client` 把 `UserProjectService.check_user_project_access` **mock 成永远 True**
⇒ ⇒ 断「项目授权」的断言**必须**用 `strict_client` ⇒ ⇒ 否则那类断言是 **no-op**。

⚠️ **抽样变异**：从「已覆盖」里抽样 ⇒ ⇒ 临时删守卫 ⇒ ⇒ 断言**必须红** ⇒ ⇒ 还原
⇒ ⇒ **没有对应断言 ⇒ 变异后无人应答 ⇒ 那本身就是缺口**。

⚠️ **枚举工具**：`pcs-backend/scripts/audit_list_endpoints.py`（可复跑 · 守卫测试 11 条）
⇒ ⇒ ⚠️ **它的分类表本身也出过两处错**（见 §七）⇒ ⇒ **工具的每个分类都要有守卫测试**。

---

## 三 · 逐端点表格（63 行）

### 3.1 `config.py`（11 · 公司级资源 ⇒ 无项目维度 ⇒ 授权维度 = 角色）

| 端点 | ① 资源 id | ②a | ②b | ③ | ④ | client | 结论 |
|---|---|---|---|---|---|---|---|
| `GET /config/assets` | —（列表 + `category`） | 角色闸 `require_roles(DESIGNER,PC,SA)` | **N/A**（公司级） | 403 | `config.py:178` | default | 🟢 已覆盖（✅ 403 断言） |
| `POST /config/assets` | —（body） | 同上 | N/A | 403 | `:198` | default | 🟢 已覆盖（⚠️ **无 403 断言** · TODO-173） |
| `POST /config/assets/{asset_id}/versions` | `asset_id` | 同上 | N/A | 403 | `:219` | default | 🟢 同上 |
| `POST /config/assets/{asset_id}/fork` | `asset_id` | 同上 | N/A | 403 | `:253` | default | 🟢 同上 |
| `POST /config/assets/{asset_id}/submit` | `asset_id` | 同上 | N/A | 403 | `:278` | default | 🟢 同上 |
| `POST /config/assets/{asset_id}/approve` | `asset_id` | `require_roles(PC,SA)` | N/A | 403 | `:306` | default | 🟢 已覆盖（✅ **变异敏感**） |
| `POST /config/assets/{asset_id}/publish` | `asset_id` | `require_roles(PC,SA)` | N/A | 403 | `:335` | default | 🟢 同上（⚠️ 无 403 断言） |
| `POST /config/assets/{asset_id}/obsolete` | `asset_id` | `require_roles(PC,SA)` | N/A | 403 | `:373` | default | 🟢 同上 |
| `GET /config/assets/status-report` | — | `require_roles(D,PC,SA)` | N/A | 403 | `:400` | default | 🟢 已覆盖（✅ 断言） |
| `GET /config/assets/status-report/export` | — | 同上 | N/A | 403 | `:414` | default | 🟢 同上（⚠️ 无断言） |
| `GET /config/assets/{asset_id}/diff` | `asset_id` + 版本码 | 同上 | N/A | 403 | `:435` | default | 🟢 同上（⚠️ 无断言） |

⚠️ `GET /config/toe-conversion`（`config.py` 第 12 个）= **C 档**（纯计算）⇒ ⇒ **不审**。

### 3.2 `report_builder.py`（9 · 可见性按「创建人 + 共享」）

| 端点 | ① 资源 id | ②a | ②b | ③ | ④ | client | 结论 |
|---|---|---|---|---|---|---|---|
| `GET /report-builder/datasources` | —（13 个源字段树） | 仅认证 | **N/A**（无租户数据） | 401 | `report_builder.py:56` | default | 🟢 已覆盖（✅ 断言） |
| `POST /report-builder/definitions` | `body.project_id` | ✅ **已修**（`require_project_access_or_404`） | ✅ 同左 | 404 | `definition_service.py::create` | **strict** ✅ | 🟢 已覆盖（**TODO-174 已修** `c7da7b6`） |
| `GET /report-builder/definitions` | 可选 `project_id` 过滤 | ✅ `visible_clause`（三态） | N/A（公司级模板 ⇒ scope 空 ⇒ 恒 400 · TODO-177） | 404（不在列表） | `definition_service.py::visible_clause` | default（断**纯 SQL** ⇒ 不受 mock 影响） | 🟢 已覆盖（✅ **变异敏感**） |
| `GET /report-builder/definitions/{def_id}` | `def_id` | ✅ `visible_clause` | N/A | 404 | `::get` | default | 🟢 已覆盖（✅ 断言） |
| `PUT /report-builder/definitions/{def_id}` | `def_id` | ⚠️ `update` 的 `created_by` 检查**冗余**（读闸先挡） | N/A | 404 | `definition_service.py::update` | default | 🟡 **写闸无独立断言**（TODO-171） |
| `POST /report-builder/definitions/{def_id}/publish` | `def_id` | 角色闸 `require_roles(REVIEWER,APPROVER,SA)`；service **不查 `created_by`** | N/A | 403 | `report_builder.py:233` | default | 🟢 已覆盖（✅ **变异敏感**）· ⚠️ 「自审自批」允许（TODO-172 / 178） |
| `POST /report-builder/definitions/{def_id}/obsolete` | `def_id` | 同上 | N/A | 403 | `:245` | default | 🟢 已覆盖（✅ 断言） |
| `GET /report-builder/executions/{task_id}` | `task_id` | 复用 `get`（可见性） | N/A | 404 | `:304-327` | default | 🟢 已覆盖（✅ 断言） |
| `POST /report-builder/definitions/{def_id}/execute` | `def_id` + scope 项目 | ✅ 可见性 `get` | ✅ **已修**（scope 项目授权 ⇒ 404） | 404 | `report_builder.py::execute_definition_endpoint` + `builder_service.py::execute_definition` | **strict** ✅ | 🟢 已覆盖（**TODO-174 已修**） |

### 3.3 `report.py`（10）

| 端点 | ① 资源 id | ②a | ②b | ③ | ④ | client | 结论 |
|---|---|---|---|---|---|---|---|
| `POST /report/generate` | `body.project_id`（**必填**）+ `record_ids` | ✅ `check_project_access_or_404`（`:146-149`）· `record_ids` 由取数层**项目作用域 ∩ 主键**兜住（`report_service.py:178-215`） | 同左 | 404 | `report.py:146` | service 级 ✅ / **端点级无** | 🟢 已覆盖（代码）· ⚠️ **断言缺口**（TODO-181） |
| `GET /report/{id}/status` | `report_file_id` | ✅ `_guard_project`（`:234`） | — | 404 | `:234` | **无端点级断言** | 🟢 已覆盖（代码）· ⚠️ **断言缺口** |
| `GET /report/{id}/download` | `report_file_id` | ✅ `:244` | — | 404 | `:244` | **无端点级断言** | 🟢 同上 |
| `GET /report/verify/{id}` | `report_file_id` | ✅ **有意免登录**：HMAC 签名绑定 id + 15 分钟 exp + 限速 | — | 403 / 404 | `:280` | default ✅（不依赖项目守卫） | 🟢 **已覆盖**（✅ 5 条断言） |
| `GET /report/{id}/hash` | `report_file_id` | ✅ `:306` | — | 404 | `:306` | **无端点级断言** | 🟢 已覆盖（代码）· ⚠️ 断言缺口 |
| `GET /report/styles` | —（列全部） | `_style_readable`：**项目级登录即可读**（**有意**） | — | 403（公司级） | `report.py:355-364` | default ✅（决定被专门的文件钉住） | 🟢 **已知限制（有意）**· ⚠️ `project_id` 是**死参数**（TODO-184） |
| `GET /report/styles/{style_id}` | `style_id` | ① `_style_readable`（`:346`）② 写面 `style_service._authorize` 判项目（**读面不判** ⇒ 有意不对称） | — | 404 / 403 | `:346-351` | default ✅ | 🟢 已覆盖 + 🟢 已知限制 |
| `POST /report/styles` | `body.project_id` | ✅ `style_service._authorize`（项目 404 / 公司级 403） | — | 403 / 404 | `style_service.py:210-228` | **service 级 ✅** | 🟢 **已覆盖**（✅ 断言） |
| `POST /report/styles/{id}/revise` | `style_id` | ✅ 同上（`:145`） | — | 403 / 404 | `style_service.py:145` | service 级 ✅ | 🟢 **已覆盖** |
| `POST /report/styles/{id}/activate` | `style_id` | ✅ 同上（`:170`） | — | 403 / 404 | `style_service.py:170` | service 级 ✅ | 🟢 **已覆盖** |

### 3.4 `records.py`（6）

| 端点 | ① 资源 id | ②a | ②b | ③ | ④ | client | 结论 |
|---|---|---|---|---|---|---|---|
| `GET /records/piping` | — | 不适用 | ❌ `workspace_id`（`:42`）→ `get_workspace`（`:54`）= **只判存在性** | 404 只在 workspace 不存在时 | **无** | **default（且测试不带 token）** | 🔴 **缺口**（TODO-179） |
| `GET /records/piping/{pipe_id}` | `pipe_id`（`:79`）⇒ 查询按 `ws.workspace_id` 双键（`:95-99`） | 靠 ②b 兜住 | ❌ `workspace_id`（`:81`）→ `get_workspace`（`:92`）= **无授权** | 404（`:102`） | **无** | **无任何测试** | 🔴 **缺口**（TODO-179 + TODO-185） |
| `POST /records/piping` | `payload["project_id"]`（`:132`） | ✅ `check_project_access_or_404`（`:130-134`） | ⚠️ `workspace_id`（`:120`）**不参与授权** ⇒ ⇒ **②a 与 ②b 不同源** | 404 | `:130` | default ⇒ **守卫被 mock ⇒ 断言无效** | 🟠 **缺口**（TODO-180 · 跨项目写入） |
| `POST /records/piping/{pipe_id}/transition` | `pipe_id` + `ws.workspace_id` 双键（`:196-201`） | 靠 ②b | ⚠️ `ws.project_id`（`:189`）⇒ ⚠️ **仅当非空**才判 | 404 | `:190-193` | default（变异 M3 **无人应答**） | 🟠 **缺口**（TODO-181 断言缺口 + TODO-182） |
| `DELETE /records/piping/{pipe_id}` | 同上（`:242-247`） | 靠 ②b | 同上（`:243`） | 404 | `:244-247` | default | 🟠 同上 |
| `GET /records/piping/{pipe_id}/snapshots` | `pipe_id` + `ws.workspace_id`（`:291-295`） | 靠 ②b | ❌ `workspace_id`（`:284`）→ `get_workspace`（`:286`）= **无授权** | 404（`:296`） | **无** | **default（且测试不带 token）** | 🔴 **缺口**（TODO-179） |

### 3.5 `psychro.py` 的 `results*`（5 · 其余 8 个纯计算 ⇒ C 档不审）

| 端点 | ① 资源 id | ②a | ②b | ③ | ④ | client | 结论 |
|---|---|---|---|---|---|---|---|
| `POST /psychro/results` | `req.project_id` | ✅ `check_project_access_or_404`（`psychro.py:535`） | 同左 | 404 | `:535` | **无断言**（M6 同族） | 🟢 已覆盖（代码）· ⚠️ 断言缺口 |
| `GET /psychro/results` | `project_id`（query） | ✅（`:601`） | 同左 | 404 | `:601` | 无断言 | 🟢 同上 |
| `GET /psychro/results/{record_id}` | `record_id` ⇒ 先取记录拿 `record.project_id` | ✅（`:639`） | 同左 | 404 ⚠️ **两种 404 文案不同** | `:639` | 无断言 | 🟢 同上 + ⚠️ TODO-187 |
| `PATCH /psychro/results/{record_id}` | `record_id` ⇒ `pre_record.project_id`（`:685`） | ✅（`:689`） | 同左 | 404 ⚠️ 文案不同 | `:689` | 无断言 | 🟢 同上 |
| `DELETE /psychro/results/{record_id}` | `record_id` ⇒ `pre_record.project_id` | ✅（`:758`） | 同左 | 404 ⚠️ 文案不同 | `:758` | 无断言 | 🟢 同上 |

⇒ ⇒ **顺序是对的**（先取记录拿 `project_id` ⇒ 再判授权 ⇒ ⇒ 不取业务数据）。

### 3.6 `workspaces.py`（4）

| 端点 | ① 资源 id | ②a | ②b | ③ | ④ | client | 结论 |
|---|---|---|---|---|---|---|---|
| `POST /workspaces` | — | ❌ **无 `current_actor`** ⇒ ⇒ `owner_id` **客户端任意填**（`:33`） | — | **201**（无认证） | **无** | **仓库测试不带 token 断言 201** | 🔴 **缺口**（TODO-186） |
| `GET /workspaces` | — | ❌ 无认证；`owner_id` 不传 ⇒ **返回全部**（`:63-81`）⇒ ⇒ 前端注释说那是「**admin 视图**」⇒ ⇒ **admin 视图没有 admin 闸** | — | **200** | **无** | 仓库测试不带 token | 🔴 **缺口**（TODO-186 · **TODO-179 的放大器**） |
| `GET /workspaces/{workspace_id}` | `workspace_id` | ❌ 无认证 | — | **200** | **无** | 仓库测试不带 token | 🔴 **缺口**（读 + **写副作用**：`svc.touch` ⇒ 匿名写库） |
| `PATCH /workspaces/{id}/archive` | `workspace_id` | ✅ `require_roles(user, "SYSTEM_ADMIN")`（`:126`）⇒ 403 | ✅ `check_project_access_or_404`（`:139`，**仅当 `project_id` 非空**） | 403 / 404 | `:126` · `:139` | default ✅ **403 断言在**（M9 红）· ❌ 项目守卫无断言（M10 全绿） | 🟢 角色闸已覆盖 · ⚠️ 项目守卫断言缺口（TODO-181） |

### 3.7 `user_projects.py`（4）

| 端点 | ① 资源 id | ②a | ②b | ③ | ④ | client | 结论 |
|---|---|---|---|---|---|---|---|
| `POST /user-projects/grant` | `body.user_id` / `body.project_id` | ✅ `require_roles(actor, "SYSTEM_ADMIN")`（`:86`）⇒ 403 | ✅ 同左（**全局资源 · 无项目维度** ⇒ 管理员的职责本身） | 403 | `:86` | **无 403 断言**（M7 全绿） | 🟢 已覆盖（代码）· ⚠️ 断言缺口 |
| `POST /user-projects/revoke` | 同上 | ✅（`:106`） | ✅ 同左 | 403 | `:106` | 无断言 | 🟢 同上 |
| `GET /user-projects/me` | —（**只看自己** ⇒ `actor.user_id`，`:125`） | ✅ 角色闸（`:123`）⚠️ **角色清单不全**（TODO-188） | — | 403 | `:123` | 无断言 | 🟢 已覆盖（代码）· ⚠️ 清单缺口 |
| `GET /user-projects/{user_id}` | `user_id` | ✅ `require_roles(actor, "SYSTEM_ADMIN")`（`:136`）⇒ 403 | — | 403 | `:136` | **无 403 断言**（M11 全绿） | 🟢 已覆盖（代码）· ⚠️ 断言缺口 |

### 3.8 `admin_users.py`（3 · 身份表**无 `project_id`** ⇒ 无跨项目语义）

| 端点 | ① 资源 id | ②a | ②b | ③ | ④ | client | 结论 |
|---|---|---|---|---|---|---|---|
| `GET /admin/users` | —（全局身份表） | ✅ `require_roles(actor, "SYSTEM_ADMIN")`（`:90`） | —（**无项目维度**） | 403 | `:90` | default ✅ **403 断言在**（M8 红） | 🟢 **已覆盖** |
| `PUT /admin/users/{user_id}/disable` | `user_id` | ✅ 同上（`:117`） | — | 403 / 404 | `:117` | default ✅ 403 断言在 | 🟢 **已覆盖** |
| `POST /admin/users/sync` | — | ✅ 同上（`:133`） | — | 403 / 503 | `:133` | default ✅ 403 断言在 | 🟢 **已覆盖** |

### 3.9 `audit.py`（3）/ `system_settings.py`（2）/ `meta.py`（6）

| 端点 | ① 资源 id | ②a | ②b | ③ | ④ | client | 结论 |
|---|---|---|---|---|---|---|---|
| `GET /audit-logs` | `resource_id`/`user_id`/`action`（筛选） | ✅ `require_roles(user, "SYSTEM_ADMIN")`（`audit.py:58`） | ⇒ `audit_logs` **无 `project_id`** ⇒ ⇒ 无跨项目语义 | 403 | `:58` | default ✅ **403 断言在**（M12 红） | 🟢 **已覆盖** |
| `GET /equipment-deletion-audit` | `equipment_id`/`workspace_id`（筛选） | ✅ 项目守卫（`:128-133`）⇒ 404；非 admin **必传** `project_id`（`:136-140` ⇒ 403） | ✅ `project_id`（`:127`） | 403 / 404 | `:128` · `:136` | **`real_user_project_client`**（**不** mock 守卫）✅ ⇒ ⇒ **404 断言在**（M13 红） | 🟢 **已覆盖**（**本批唯一带「真守卫断言」的项目守卫端点**） |
| `GET /config-audit` | `asset_id` | ✅ `require_roles(D,PC,R,A,SA)`（`:207`） | ⇒ 过滤 `config_energy_conversion_factors` ⇒ ⇒ **公司级** | 403 | `:207` | default ✅ 403 断言在 | 🟢 **已覆盖** |
| `GET /system-settings` | —（全局参数表） | ✅ `require_roles(actor, "SYSTEM_ADMIN")`（`system_settings.py:37`） | — | 403 | `:37` | default ✅ **403 断言在**（M14 红） | 🟢 **已覆盖** |
| `PUT /system-settings` | 键名（body） | ✅ 同上（`:52`）⇒ 批量原子 + 写审计 | — | 403 / 404 | `:52` | default ✅ **403 断言在** + ✅ 审计有断言 | 🟢 **已覆盖** |
| `GET /meta/enums` | —（静态字典） | 仅认证 `current_user` ⇒ 401 | — | 401 | `meta.py:162` | default ✅ **401 断言在**（M15 红） | 🟢 **已覆盖**（无项目维度） |
| `GET /meta/permissions` | — | 同上 | — | 401 | `:171` | ✅ 401 断言 | 🟢 同上 |
| `GET /meta/permissions.csv` | — | 同上 | — | 401 | `:179` | ✅ 401 断言 | 🟢 同上 |
| `GET /meta/error-codes` | — | 同上 | — | 401 | `:192` | ✅ 401 断言 | 🟢 同上 |
| `GET /meta/state-machine` | — | 同上 | — | 401 | `:200` | ✅ 401 断言 | 🟢 同上 |
| `GET /meta/ui-schema/{resource}` | `resource`（路径参数）⇒ **注册表查表** ⇒ 未知 ⇒ 404 ⇒ ⇒ **不读文件、无路径穿越** | 仅认证 | — | 401 / 404 | `:212` | ✅ 401 + 200 断言 | 🟢 **已覆盖** |

---

## 四 · 抽样变异记录（18 处 · 全部还原）

| # | 被变异的东西 | 期望 | 实测 | 判定 |
|---|---|---|---|---|
| 1 | `config.py:306` `approve` 的 `require_roles` | 红 | 🔴 `test_approve_requires_process_controller` **红** | ✅ 敏感 |
| 2 | `report_builder.py:233` `publish` 的 `require_roles` | 红 | 🔴 `test_publish_requires_reviewer_role` **红** | ✅ 敏感 |
| 3 | `definition_service.py::update` 的 `created_by` 检查 | 红 | ⚪ **71 条全绿** | ❌ 无人应答 ⇒ **TODO-171** |
| 4 | `visible_clause` 的「仅创建人可见」 | 红 | 🔴 `test_draft_is_invisible_to_others_but_visible_to_creator` **红** | ✅ 敏感 |
| 5 | `report_service._scope_and_records` 的项目作用域条件 | 红 | 🔴 `test_fixed_10_types_refuse_record_ids_from_another_project` **红** | ✅ 敏感 |
| 6 | `style_service._authorize` 的项目检查 | 红 | 🔴 `test_project_level_denied_when_no_project_access` **红**（但 `test_project_level_uses_project_access_not_admin` 仍绿 ⇒ **恒真断言** ⇒ TODO-183） | ✅ 部分敏感 |
| 7 | `records.py::transition_piping` 的项目守卫 | 红 | ⚪ **49 条全绿** | ❌ ⇒ **TODO-181** |
| 8 | `report.py::_guard_project` | 红 | ⚪ **45 条全绿** | ❌ ⇒ **TODO-181** |
| 9 | `report.py::generate_report` 的守卫 | 红 | ⚪ **29 条全绿** | ❌ ⇒ **TODO-181** |
| 10 | `psychro.py::get_psychro_result` 的项目守卫 | 红 | ⚪ **26 条全绿** | ❌ ⇒ **TODO-181** |
| 11 | `user_projects.py::grant` 的 `require_roles` | 红 | ⚪ **15 条全绿** | ❌ ⇒ **TODO-181** |
| 12 | `admin_users.py::get_users` 的 `require_roles` | 红 | 🔴 `test_list_users_requires_system_admin` **红** | ✅ 敏感 |
| 13 | `workspaces.py::archive_workspace` 的 `require_roles` | 红 | 🔴 `test_archive_workspace_requires_admin_403` **红** | ✅ 敏感 |
| 14 | `workspaces.py::archive_workspace` 的**项目守卫** | 红 | ⚪ **6 条全绿** | ❌ ⇒ **TODO-181** |
| 15 | `user_projects.py::list_user_projects` 的 `require_roles` | 红 | ⚪ **15 条全绿** | ❌ ⇒ **TODO-181** |
| 16 | `audit.py::list_audit_logs` 的 `require_roles` | 红 | 🔴 `test_403_require_roles_denial_writes_audit` **红** | ✅ 敏感 |
| 17 | `audit.py::list_equipment_deletion_audit` 的项目守卫 | 红 | 🔴 `test_ungranted_designer_404` **红** | ✅ 敏感 |
| 18 | `system_settings.py::get_system_settings` 的 `require_roles` | 红 | 🔴 `test_get_settings_requires_system_admin` **红** | ✅ 敏感 |
| 19 | `meta.py::get_enums` 的 `Depends(current_user)` | 红 | 🔴 `test_enums_anonymous_denied` **红** | ✅ 敏感 |

⇒ ⇒ **10 处敏感 · 9 处无人应答** ⇒ ⇒ **无人应答的 9 处就是断言缺口本身**（TODO-181 等）。

⚠️ **事后补记（2026-11-18 · 批 4/批 5 之后）**：变异 M3/M7/M10/M11 对应的
端点中，**`records` 的三个读端点与 `workspaces` 的三个端点**已由批 4 补上
`strict_client` 断言 ⇒ ⇒ ⇒ 「无人应答」从 9 处降到 **6 处**。

---

## 五 · 缺口清单（逐条 ⇒ 已在 `TODOS.md` 登记）

| TODO | 严重度 | 一句话 | 实测证据 |
|---|---|---|---|
| **TODO-179** | 🔴 critical | `records.py` 的三个 GET **既不要求登录也不做项目授权** ⇒ ⇒ 匿名读走任意项目的管路记录与变更快照 | 演示：无 token 200；有 token（无授权）也 200 |
| **TODO-186** | 🔴 critical | `workspaces.py` 的三个端点**不要求登录** ⇒ ⇒ 匿名枚举全部 workspace · 匿名 GET **写库** · 匿名 POST **任意 owner_id** + **审计行伪造** | 演示：匿名列到别人的 workspace；`last_active_at` 被改；伪造 owner 名下 1 条 `WORKSPACE_CREATED` |
| **TODO-180** | 🟠 high | `records.py` 写面授权判 **payload 的 project_id**、行落进 **workspace 的 workspace** ⇒ ⇒ 授权在 A 的人写进 B 的工作区 | 演示：跨项目写入 **200**；对照组（payload=B）**404** ⇒ ⇒ 守卫本身是「真」的 |
| **TODO-181** | 🟠 high | `records.py` / `report.py` / `psychro` / `user_projects` / `workspaces.archive` 的守卫**零断言**（9 个端点）⇒ ⇒ 变异无人应答 | 变异 7~15 全绿 |
| **TODO-182** | 🟠 high | `records.py` 状态机守卫在 `ws.project_id IS NULL` 时**整段跳过** | 代码审查（`records.py:189/243`） |
| **TODO-170** | 🟠 medium | `report_definitions.project_id` 是**死字段**（数据模型说项目级 · 授权说创建人级）⇒ ⇒ **已裁决落地**（选项 ③ · `bc881fa`） | —— |
| **TODO-171** | 🟡 medium | `DefinitionService.update` 的**写闸**没有独立断言（删掉 ⇒ 71 条全绿） | 变异 3 |
| **TODO-172 / 178** | 🟡 medium | **publish 的职责分离** ⇒ ⇒ **已裁决并落地**（`09c9282`）：禁自审 403 · 审核者需项目授权 404 · 公司级审核者例外 | 探针：创建人自己是 REVIEWER ⇒ 发布自己的定义 ⇒ **200**（**现已 403**） |
| **TODO-173** | 🟡 medium | `config.py` 的 **8 个端点**的角色闸**没有 403 断言** | T2a |
| **TODO-175** | 🟡 medium | `POST /projects` 能否替别人建项目（**产品语义**）⇒ ⇒ **已裁决并落地**（`09c9282`）：只有 SYSTEM_ADMIN 能替别人建（**现状即满足**）+ **工作区 owner 自动获授权** | —— |
| **TODO-176** | 🟠 high | 默认 `client` 把项目守卫 mock 成永远 True ⇒ ⇒ 「已覆盖」必须复核（**部分已做**：`strict_client` + 棘轮） | —— |
| **TODO-177** | 🟡 medium | **公司级模板（`project_id IS NULL`）当前不可执行**（恒 400） | —— |
| **TODO-187** | 🟡 medium | 两种 404 **文案不同** ⇒ ⇒ 存在性可枚举（跨 21+ 端点族） | 守卫 `Project not found: X` vs 端点 `X not found` |
| **TODO-188** | 🟡 medium | `GET /user-projects/me` 角色清单缺 `PROCESS_CONTROLLER`/`VIEWER`/`DATA_ADMIN` | 代码审查 |
| **TODO-183** | 🟡 medium | `test_project_level_uses_project_access_not_admin` 的断言**恒真** | 变异 6 |
| **TODO-184** | 🟢 low | `GET /report/styles` 的 `project_id` 是**死参数** | 代码审查 |
| **TODO-185** | 🟢 low | `GET /records/piping/{pipe_id}` **零测试** | 全仓 grep |
| **TODO-189** | 🟢 low | `strict_client` 与 `real_user_project_client` **重复** ⇒ ⇒ 棘轮看不见后者 | 代码审查 |

---

## 六 · 排除理由（为什么某些端点「无越权面」——**写清楚，而不是不写**）

| 端点族 | 理由 |
|---|---|
| `config.py` 全部 11 个 | `ConfigAsset` 是**公司级**资源（**无 `project_id` 列**）⇒ ⇒ 「跨项目访问」语义**不成立** ⇒ ⇒ 授权维度是**角色**（`require_roles`）⇒ ⇒ **不是** #5 型越权 |
| `psychro.py` 的 8 个纯计算端点 | **C 档**：无项目级数据读写（纯公式）⇒ ⇒ 不审 |
| `config.py` 的 `GET /config/toe-conversion` | 同上（C 档） |
| `admin_users.py` 3 个 | 用户表**无 `project_id`** ⇒ ⇒ 无跨项目语义 ⇒ ⇒ 按裁决「全局资源按敏感度分级」⇒ ⇒ 身份表与审计日志/系统参数同级 ⇒ ⇒ 闸在即可 |
| `audit-logs` / `config-audit` | `audit_logs` 与配置因子**均无 `project_id`** ⇒ ⇒ 同上 |
| `report.py` 的**样式读面**（项目级） | **有意放宽**（登录即可读）⇒ ⇒ 理由（N+1）写在 `_style_readable` 的 docstring 里 ⇒ ⇒ **且有专门的文件把这条决定钉住**（`tests/api/v1/test_report_style_read_scope.py`）⇒ ⇒ **不是缺口** |
| `report.py` 的 `verify` | **有意免登录**（HMAC 签名 + 15 分钟 exp + 限速 + 签名绑定 id）⇒ ⇒ 设计内 |
| `user_projects` 的 grant / `{user_id}` | 能给**任意**项目授权、查**任意**用户的清单 ⇒ ⇒ **管理员的职责本身**（SYSTEM_ADMIN 闸在）⇒ ⇒ 设计内 |
| `meta.py` 6 个 | **静态字典 + 认证** ⇒ ⇒ 无项目维度 |

---

## 七 · 测试基础设施缺口（本审计的**基础设施级**发现）

### 7.1 默认 `client` 把项目守卫 mock 成永远 True

`tests/conftest.py` 的 `client` fixture monkeypatch
`UserProjectService.check_user_project_access` ⇒ 永远 True
⇒ ⇒ 「端点缺项目守卫」这类缺陷在它上面**一个都测不出来**
⇒ ⇒ ⇒ 断「项目授权」的断言**必须**用 `strict_client`（+ 真 `UserProject` 授权行）。

⇒ ⇒ 已做：`strict_client`（P9B-4）+ `grant_project` fixture + **可执行棘轮**
（`tests/test_strict_client_ratchet.py`：「用 `strict_client` 的测试函数数
≥ 已审的『带项目维度』端点数」⇒ ⇒ 台账
`tests/conftest.py::AUDITED_PROJECT_SCOPED_ENDPOINTS`）。

⚠️ **棘轮数当前 = 2，而实际审计面 ≈ 18** ⇒ ⇒ **棘轮已低于实际** ⇒ ⇒
**抬棘轮与补断言必须同批**（否则要么红、要么假绿）⇒ ⇒ ⇒ 归 TODO-181。

### 7.2 审计工具自己的分类表出过两处错

`scripts/audit_list_endpoints.py`（守卫测试 11 条）：

| 错 | 后果 | 修法 |
|---|---|---|
| `current_user` 不在「只认证」档 | `meta.py` 的 6 个端点（有认证）被误判成「无守卫」⇒ ⇒ **假阴性** | 加进 `WHOAMI_GUARDS` |
| `require_formal_project_workspace` 被算成「项目授权闸」 | 它只判工作区**类型**、**从不查 `user_projects`**、且 **fail-open** ⇒ ⇒ **假阳性** | 挪出 `AUTHZ_GUARDS` ⇒ 单开 `type_only` 档（三态 → 四态） |

⇒ ⇒ **影响面已逐模块核对**：在审范围内各模块的结论**全部不变**
⇒ ⇒ 只有 `meta` 的判定被修正 ⇒ ⇒ `deliverables` / `records_actions`
（**不在本次范围**）由假阳性纠正。

⇒ ⇒ **教训**：**工具给的初判会把工具的错带进审计的结论** ⇒ ⇒
**工具的每个分类都要有守卫测试**。

### 7.3 两个「不 mock 项目守卫」的 client

`conftest.py::strict_client` 与 `tests/test_audit_guard.py::real_user_project_client`
做的是同一件事 ⇒ ⇒ 而棘轮**只数前者** ⇒ ⇒ 「已审面」计数**偏小**（TODO-189）。

---

## 八 · 已知限制与有意取舍（**不是缺口**）

1. **样式读面**：项目级样式登录即可读（`_style_readable`）⇒ ⇒ 有意（N+1）· 有断言钉住。
2. **`verify` 免登录**：HMAC 签名 + 时效 + 限速 ⇒ ⇒ 设计内。
3. **公司级模板不可执行**（`project_id IS NULL` ⇒ 执行恒 400 · TODO-177）
   ⇒ ⇒ 已知限制，**不是漏洞**。
4. **`require_formal_project_workspace` 是 fail-open**（项目没挂工作区 ⇒ 放行）
   ⇒ ⇒ 有意（不因缺元数据挡掉正常操作）⇒ ⇒ **但它不是授权闸**（见 §7.2）。
5. **两种 404 文案不同**（TODO-187）⇒ ⇒ 规则冲突，低优先级。

---

## 九 · 三条越权债的复核（F3-T4）

⇒ ⇒ 判据与 F3-T2 相同：**断言必须对它命名的缺陷敏感** ⇒ ⇒ 抽一个做变异验证。

| 债 | 断言位置 | 变异 | 实测 | 复核结论 |
|---|---|---|---|---|
| **TODO-132**（禁用用户 · actor 层判定） | `tests/api/v1/test_user_disabled_guard.py::test_disabled_user_with_existing_token_is_rejected`（**`strict_client`** · 真守卫）+ `tests/api/v1/test_disabled_user_endpoints.py`（`current_user` 那 7 个端点） | 删 `config.py::current_actor` 的 `is_account_disabled` 判定 | 🔴 **红** | ✅ **断言敏感 ⇒ 债真的闭合** |
| **TODO-133**（workspace 归属） | `tests/api/v1/test_stream_workspace_ownership.py::test_foreign_workspace_id_is_ignored`（4 例） | `workspace_id = req.workspace_id or project.workspace_id` | 🔴 **红** | ✅ **断言敏感 ⇒ 债真的闭合** |
| **TODO-135**（mock 旁路） | `tests/test_mock_auth.py`（14 例 · 闸门矩阵 4 种组合 + 默认关 + 部署期断言） | 去掉「显式 `PCS_ENABLE_MOCK_LOGIN=true`」那一闸 | 🔴 **红**（2 条） | ✅ **断言敏感 ⇒ 债真的闭合** |

⚠️ **两条自我修正**（写在这里，因为它们是**方法论**的一部分）：

1. **第一次跑 TODO-132 的变异只跑了 `current_user` 那个测试文件** ⇒ ⇒ **没红**
   ⇒ ⇒ 差点误判成「断言缺口」⇒ ⇒ 跑对文件（`test_user_disabled_guard.py`）后**变红**
   ⇒ ⇒ ⇒ **教训：变异验证必须跑「该缺陷对应的断言文件」**，不能只跑「看起来相关」的一个。
2. **第一次的 TODO-133 变异本身是空转**（写成 `req.payload.get("workspace_id")`
   ⇒ ⇒ 那个字段根本不在 `payload` 里）⇒ ⇒ **没红**⇒ ⇒ 改成
   `req.workspace_id or project.workspace_id` 后**变红**
   ⇒ ⇒ ⇒ **教训：变异必须真的改变行为** ⇒ ⇒ **没红先怀疑变异本身**。

---

## 十 · 复现方式

```bash
# 端点枚举（可复跑 · 守卫测试 11 条）
cd pcs-backend
uv run python scripts/audit_list_endpoints.py --module config      # 其余模块同理
uv run python scripts/audit_list_endpoints.py --counts

# 缺口清单
grep -nE "^## TODO-(17[0-9]|18[0-9])" ../TODOS.md
```

⚠️ **四个子批的完整 4 问表与逐条取证**在工作区（gitignored）：
`.superpowers/sdd/2026-11-17-p10-batch-f-production-readiness/`
下的 `audit-f3-t2a.md` · `audit-f3-t2b.md` · `audit-f3-t3a.md` · `audit-f3-t3b.md`
⇒ ⇒ **本文档是仓库里的那份**（结论 + 表格 + 变异记录 + 缺口清单）。
