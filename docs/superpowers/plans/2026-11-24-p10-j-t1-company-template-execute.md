# P10-J-T1 · 公司级模板「执行时选项目」 —— 计划

> **来源**：`TODOS.md` · `TODO-177`（P10-J · T1）
> **人裁**：2026-11-23（见 `2026-11-23-p10-j-feature-backlog.md` §P10-J-T1）· 2026-11-24 补充（见 §七）· **2026-11-24 plan-eng-review + hermes 第三方审查增补（见 §八）**
> **性质**：**新功能**（**滚 OpenAPI 契约**）
> **状态**：✅ **已批准**（2026-11-25 · 人裁「approve」）⇒ ⇒ ⇒ **可开工** · 本批为**下一批的第一件事**（与 P10-K **串行**）
> **落地**：✅ **已落地**（2026-11-25 · 见 §十「落地记录」）⇒ ⇒ ⇒ **T1-1 / T1-3 / T1-4 / T1-5 / T1-6 / T1-7 / T1-8 全部完成**（**T1-2 已删**）

---

## 一、人裁（2026-11-23 · 同意建议）

| 问 | 裁决 |
|---|---|
| ① 公司级模板该不该可执行 | **「公司级模板＝模板，执行时**必须**选项目」** ⇒ ⇒ 做成 **UI 流程** |
| ② 指定的项目若无权 | **404**（与「不存在」同形 · 技术决定）|

**SPEC 条款草案**（随本批登记）：

> **执行**：公司级模板（`project_id IS NULL`）**执行时必须选项目**；
> **执行的 scope = 定义自带项目 ∨（公司级 ⇒ 请求指定的项目）**；
> **两者都给了且不一致 ⇒ ⇒ 400 拒绝**（不静默忽略）。

---

## 二、现状（**为什么公司级模板永远跑不通**）

| 位置 | 现状 | 后果 |
|---|---|---|
| `app/api/v1/report_builder.py:526-530` | `if row.project_id is not None:` ⇒ 才做项目授权判定 | 公司级 ⇒ ⇒ **跳过授权判定**（此时还没有项目可判） |
| `app/api/v1/report_builder.py:572`（**快照**） | `project_id=str(row.project_id or "")` | 公司级 ⇒ ⇒ **恒空串** |
| `app/api/v1/report_builder.py:591`（入队） | `project_id=str(row.project_id or "")` | 同上 |
| `app/workers/report_builder_tasks.py:79` | `pid = uuid.UUID(project_id) if project_id else None` | ⇒ ⇒ `report_files.project_id` 落 **NULL**（产出文件无归属）|
| `app/services/report/builder_service.py:180` | `scope is None` ⇒ ⇒ **400** `REPORT_PROJECT_SCOPE_REQUIRED` | ⇒ ⇒ **公司级模板永远 400**，且发生在 **worker 里** ⇒ ⇒ 用户看到「202 已提交 → 执行失败」|

⚠ **契约缺口**：`ReportExecuteRequest`（`app/api/v1/report_builder.py:419`）**没有** `project_id` 字段
⇒ ⇒ **没有任何入口能传项目 id** ⇒ ⇒ 「执行时选项目」这条路**今天物理上不存在**。

---

## 三、任务清单

| # | 内容 | 文件 | 状态 |
|---|---|---|---|
| **T1-1** | 契约：`ReportExecuteRequest` **加 `project_id`** ⇒ ⇒ 滚 openapi（`pcs-backend/docs/openapi.json`）· **`pcs-frontend/src/types/api.d.ts`**（**不是** `src/api/api.d.ts`）· **`pcs-frontend/openapi.snapshot.json`** ⇒ ⇒ ⚠️ **CI 拦不住「新增可选字段」⇒ ⇒ 必须手工跑 `npm run api:gen` 并提交那两份**（见 §八·修正 6）| `app/api/v1/report_builder.py` | ✅ |
| **T1-3** | 端点：**解析 scope + 三道新判定**（顺序见 §四·判定顺序，**不重排既有行为**）⇒ ⇒ ① **MISMATCH 400**（请求项目 ≠ 定义自带项目）② **SCOPE_REQUIRED 400**（公司级 + 未指定项目）③ 对**解析出的 scope** 做授权判定 ⇒ ⇒ 无权 ⇒ ⇒ **404** `PROJECT_NOT_FOUND` | `app/api/v1/report_builder.py` | ✅ |
| **T1-4** | **入队与快照传「解析后的 scope」**（`:591` 入队 + **`:572` 快照** 两处）⇒ ⇒ 产出文件有项目归属 | `app/api/v1/report_builder.py` | ✅ |
| **T1-7** 🆕 | **建定义时拒「公司级 + 主数据源无 `project_id` 列」** ⇒ ⇒ `DATALINEAGE` / `SUPPLIERS` / `CONFIG_ASSETS` 这 3 个源**没有项目列** ⇒ ⇒ 选了项目也**无法按项目隔离** ⇒ ⇒ 若不在源头拦住，编辑器默认 `projectId: null` ⇒ ⇒ **批量生产永远跑不了的死路**（见 §八·修正 12）<br>✅ **零存量**（两库实测：`pcs` 8 条公司级定义主源全有项目列 · `pcs_test` 0 条定义）⇒ ⇒ ⇒ **零迁移、零清理**；执行侧**另外**给一个**可区分**的错误码（不再复用 `REPORT_PROJECT_SCOPE_REQUIRED`）⇒ ⇒ ⇒ 让别处环境里的旧定义跑起来时**说实话** | `app/services/report/definition_service.py` · `app/services/report/datasource_registry.py` | ✅ |
| **T1-5** | 前端：执行页 —— 选中**公司级**定义（`def.project_id === null`，**生成类型里已有该字段**：`src/types/api.d.ts:16811`）时给「**选项目**」入口 ⇒ ⇒ **必选、无默认**（人裁 2026-11-24）⇒ ⇒ ⇒ 未选 ⇒ ⇒ **执行按钮禁用** ⇒ ⇒ 项目级**不出现**<br>⚠️ **四条实现约束**（见 §八·修正 7~9）：① 候选源**按角色分**（普通用户 = 自己的授权行 · SYSTEM_ADMIN = 工作区并集）② **不用** `useProjectScope().projects` 那个并集（**含你无权执行的项目**）③ **不能**用 `selectProject`（会改**全局顶栏**项目）④ Select 的 label **要标出作用域**（今天公司级与项目级在界面上**长得一模一样**）| `src/pages/report/ReportExecutePage.tsx` | ✅ |
| **T1-6** | **SPEC §7.18 补条款（§7.18.2）** + §12.4 修订登记 + 断言（后端默认车道 + **PG 车道 1 条直连 ORM** · 前端 vitest）| `docs/PCS-UI-SPEC.md` · `tests/` · `pcs-frontend/tests/` | ✅ |
| **T1-8** 🆕 | **ADR**：scope 解析裁决（定义自带项目优先 + 不一致 400）+ 「**谁能对哪个项目执行公司级模板**」的权限口径 | `docs/adr/` | ✅ |

### T1-2（**已删**）

原 T1-2 = service 层 `scope = project_id or row.project_id` ⇒ ⇒ **倒置为** `row.project_id or project_id`。
⇒ ⇒ ⇒ **2026-11-24 人裁：删掉，不改 service。**
理由（已核实）：MISMATCH 400 在**端点**拦 ⇒ ⇒ worker 收到的永远是**已解析且一致**的 scope ⇒ ⇒ service 里那个顺序在**每条可达路径上都是死代码** ⇒ ⇒ ⇒ 一条不变量两种机制 = 未来的漂移种子；且**现有测试没有一条会传冲突的 `project_id`**（该字段还不存在）⇒ ⇒ 改了等于没测、还动了别人依赖的行为。
⇒ ⇒ ⇒ **规则落在端点一处**（§四·判定顺序）· service 的 `project_id or row.project_id` **原样不动**。

---

## 四、口径

| 场景 | scope | 结果 |
|---|---|---|
| 项目级定义 + 请求**不带**项目 | 定义自带项目 | ✅ |
| 项目级定义 + 请求**带**别的项目 | —— | **400** `REPORT_PROJECT_SCOPE_MISMATCH` |
| 公司级模板 + 请求带**有权**的项目 | 请求指定的项目 | ✅ 跑通 |
| 公司级模板 + 请求带**无权**的项目 | —— | **404** `PROJECT_NOT_FOUND` |
| 公司级模板 + 请求**不带**项目 | —— | **400** `REPORT_PROJECT_SCOPE_REQUIRED` |
| 公司级模板 + 主源是 `DATALINEAGE`/`SUPPLIERS`/`CONFIG_ASSETS` | —— | **建定义时就拒**（T1-7）· 已存在的旧定义执行时仍会 400 |

### 判定顺序（**必须照抄这个顺序** ⇒ ⇒ 不重排既有行为）

| # | 判定 | 结果 | 位置 |
|---|---|---|---|
| 1 | `svc.get(def_id, …)` ⇒ 定义不可见 | **404** `REPORT_DEFINITION_NOT_FOUND` | 既有 `:516` |
| 2 | `row.project_id is not None` ⇒ 授权判定（**定义自带项目**）| **404** `PROJECT_NOT_FOUND` | 既有 `:526-530` |
| 3 | `row.status != "PUBLISHED"` | **409** `REPORT_DEFINITION_STATE` | 既有 `:532-538` |
| 4 | **MISMATCH**：请求项目 ≠ 定义自带项目 | **400** `REPORT_PROJECT_SCOPE_MISMATCH` | 新增 |
| 5 | **SCOPE**：解析出的 scope 为 `None` | **400** `REPORT_PROJECT_SCOPE_REQUIRED` | 新增 |
| 6 | 公司级 + 请求带了项目 ⇒ 对**该项目**做授权判定 | **404** `PROJECT_NOT_FOUND` | 新增 |

⚠ **为什么 1→2→3 必须在 4→5→6 之前**：今天「项目级 + 授权被撤 + 定义未发布」返回 **404**（第 2 步）⇒ ⇒ 若把 409 提到前面，就变成 409 ⇒ ⇒ **一次未被声明的行为变更**。
⚠ **为什么第 6 步放最后**：公司级定义今天**根本不做**授权判定（`:526` 的 `if` 会跳过）⇒ ⇒ ⇒ 新增它**不重排**任何既有行为。

---

## 五、预判的坑

| # | 坑 | 对策 |
|---|---|---|
| 1 | ⚠️ **scope 解析散落在端点与 service** | **规则只在端点一处**（§四）· service 不改（T1-2 已删）|
| 2 | ⚠️ **入队与快照仍传 `row.project_id`** ⇒ ⇒ 产出文件 `project_id` 落 NULL | 入队（`:591`）**与快照**（`:572`）都传**解析后的 scope** |
| 3 | ⚠️ **scope 解析失败抛在哪** | **端点抛 400**（第 4/5 步，**落日志/入队之前**）⇒ ⇒ 否则留一行永远 QUEUED 的执行日志等 15 分钟回收器 |
| 4 | ⚠️ **请求带的 project 与定义自带的不符** | **400 拒绝**（`REPORT_PROJECT_SCOPE_MISMATCH`）⇒ ⇒ 不静默忽略（显式 > 隐式）|
| 5 | ⚠️ **主源没有项目列的模板**（3 个源）⇒ ⇒ 选了项目也跑不了，且**与「没选项目」同码** | **T1-7 建定义时拒**（源头堵）· 执行侧另给**可区分的错误码**（见 §八·修正 12）|
| 6 | 🔴 **CI 不拦「新增可选字段」** ⇒ ⇒ 加了 `project_id` 而没滚 `api.d.ts` ⇒ ⇒ CI 照绿 ⇒ ⇒ 直到前端真用它才 `tsc` 红 | §八·修正 6 ⇒ ⇒ T1-1 写死 `npm run api:gen` + 两份都提交 + 手工 `api:check` |
| 7 | 🔴 **`useProjectScope().projects` 含你无权执行的项目**（workspaces 腿按所有权而非授权过滤）⇒ ⇒ 用户选了才吃 404 | §八·修正 7 ⇒ ⇒ 候选源**按角色分**（普通 = 授权行 · admin = 工作区并集）|
| 8 | 🔴 **`useProjectScope` 是全局 zustand store** ⇒ ⇒ 复用 `selectProject` 会**改全局顶栏项目** | §八·修正 8 ⇒ ⇒ 局部 state，只读列表不调 `selectProject` |
| 9 | 🔴 **公司级与项目级定义在界面上长得一模一样** ⇒ ⇒ 用户不知道为什么要多选一个项目 | §八·修正 9 ⇒ ⇒ Select label 标作用域 |
| 10 | 🔴 **`/user-projects/me` 不返项目名** ⇒ ⇒ 下拉里只有裸 UUID | §八·修正 11 ⇒ ⇒ 名称来源要**单独定**（补一次 `GET /projects/{id}` 批量，或加一个带名字的端点）|

---

## 六、验收

- [ ] 契约里 `ReportExecuteRequest` 有 `project_id`（`pcs-backend/docs/openapi.json` + `pcs-frontend/openapi.snapshot.json` + `pcs-frontend/src/types/api.d.ts` **三份**都更新）
- [ ] 「公司级模板 + 有权的项目」⇒ ⇒ 跑通（用例）· 且 **`report_files.project_id` == 所选项目**（**产出归属** —— 计划 §二 的真正落点，今天零断言）
- [ ] 「公司级模板 + 无权的项目」⇒ ⇒ **404** `PROJECT_NOT_FOUND`（用例）
- [ ] 「公司级模板 + 不带项目」⇒ ⇒ **400** `REPORT_PROJECT_SCOPE_REQUIRED`，且**没有**留下执行日志行（用例）
- [ ] 「项目级模板 + 请求带别的项目」⇒ ⇒ **400** `REPORT_PROJECT_SCOPE_MISMATCH`（用例）
- [ ] 「项目级模板 + 不带项目」⇒ ⇒ **仍是定义自带项目**（用例）
- [ ] 「公司级 + 主源是那 3 个无项目列的源」⇒ ⇒ **建定义被拒**（用例）
- [ ] 前端「执行报表」有「选项目」入口（**仅公司级模板出现**）· 未选时执行按钮禁用
- [ ] 前端 Select 的 label **标出作用域**（公司级 / 项目级）⇒ ⇒ 用户在选中**之前**就知道要不要多选项目
- [ ] 前端候选源**按角色分**：普通用户只看到**有权执行**的项目 · **SYSTEM_ADMIN 看到非空列表**
- [ ] 前端用**局部 state** 存本次选择，**不动**全局顶栏项目
- [ ] 前端按 `code` 分流（`REPORT_PROJECT_SCOPE_MISMATCH` / `PROJECT_NOT_FOUND` / `REPORT_DEFINITION_NOT_FOUND` 三者各给一句）⇒ ⇒ **不要**再显示「回收器判定为僵死」
- [ ] `npm run api:gen` 跑过 · `openapi.snapshot.json` **与** `src/types/api.d.ts` **两份**都提交（⚠️ CI 不拦「新增可选字段」⇒ ⇒ 手工验 `npm run api:check`）
- [ ] 新错误码在 `GET /api/v1/meta/error-codes` 里**能查到**（⇒ ⇒ 证明 raise 点用的是**字面量形式**）
- [ ] **默认车道绿**（公司级那族在 SQLite 车道可证）· 断言里**查 `code`**（今天的既有 404 断言**都不查 code**）
- [ ] **HTTP 层**的 400 `REPORT_PROJECT_SCOPE_REQUIRED` 用例（今天**没有** ⇒ 因为端点从不抛它）· **且断言执行日志表没留下行**
- [ ] `PROJECT_NOT_FOUND` 有断言（今天**全仓零测试**）
- [ ] **PG 车道 1 条绿**：**直连 ORM 插入**（绕过 `_reject_duplicate`）造两条同名公司级定义 ⇒ ⇒ **真的打到 UniqueConstraint** ⇒ ⇒ **约束被删了它就红**（⚠️ 走 API 建会先被应用层 409 ⇒ ⇒ 那是**假证据**）
- [ ] ADR 已写（scope 解析裁决 + 执行公司级模板的权限口径）

---

## 七、人裁补充（2026-11-24 · 逐条裁完）

| 问 | 裁决 |
|---|---|
| 执行页「选项目」**默认取哪儿** | **必选、无默认** ⇒ ⇒ ⇒ 用户**必须亲手选**一个项目才让执行（不取顶栏 `useProjectScope().projectId` 作默认）⇒ ⇒ ⇒ 理由：**少一层「以为跑的是 A 其实是 B」的推断** ⇒ ⇒ ⇒ 且「无默认」⇒ ⇒ ⇒ 强制用户**看一眼**这次跑的是哪个项目 |
| 公司级模板要不要**二次确认弹窗** | **不要**（选了就能跑）⇒ ⇒ ⇒ 多一步操作换不到额外保证（项目已在选择器里**看得见**）|

⇒ ⇒ ⇒ ⚠️ **「必选、无默认」与 SPEC 条款草案要同口径** ⇒ ⇒ ⇒
W-6 的 SPEC 条款必须写明「**必须选一个项目**」⇒ ⇒ ⇒ **不许**写成「默认当前项目」。

⇒ ⇒ ⇒ ⚠️ **评审后修订**：§一 的 SPEC 条款草案已按 §四 更新（**不一致 ⇒ ⇒ 400 拒绝**，不再是「以定义自带项目为准 + 静默忽略」）。

---

## 八、plan-eng-review + hermes 第三方审查增补（2026-11-24 · 已核实）

### 修正 1 · 坑 #3「404 用了 API 层那份」—— **前提是错的**

**实测**：`app/api/v1/report_builder.py:47` ⇒ `from app.services.user_project_service import require_project_access_or_404`；`:527` **已经在用服务层那份** ⇒ ⇒ 端点现在抛的就是 `code="PROJECT_NOT_FOUND"`（`user_project_service.py:392-396`）⇒ ⇒ **不存在「code 不同仍可枚举」的问题**。

⇒ ⇒ ⇒ **T1-3 的真正工作**不是「换守卫」，而是**把已有检查从 `row.project_id` 扩到「解析后的 scope」**。

⇒ ⇒ ⇒ ⚠️ **别照原计划去改守卫归属**：服务层 docstring（`user_project_service.py:378-384`）明写「**端点层用 API 那份**… 端点层改用本份 ⇒ ⇒ 形状一致 ⇒ ⇒ **但会动 21+ 端点的错误信封 ⇒ ⇒ 属另一批**」⇒ ⇒ ⇒ 本批**不动**守卫归属。

⇒ ⇒ ⇒ ℹ️ 供参：`app/api/v1/_guard.py:24` 的 `check_project_access_or_404` 有 `not_found_code` / `not_found_message` 参数（2026-11-23 · TODO-187b 加的），用途是让「同一个端点、同一种资源类型」的两种 404 **逐字同形** ⇒ ⇒ ⇒ 本端点**不需要**用它（两种 404 分属不同资源：定义 vs 项目）。

### 修正 2 · 坑 #5 的 PG 车道硬门槛 —— **结论过严，但补的那条用例本身是假证据**

- **原结论过严**：差异只在 `UniqueConstraint("project_id", "name", postgresql_nulls_not_distinct=True)`（`app/models/report.py:210-217`）⇒ ⇒ 只有**造两条同名公司级定义**才分叉；本功能只要**一条唯一名**的 ⇒ ⇒ **默认车道可证**。
- 🔴 **但补的那条用例是假证据**（hermes 查出来）：`_reject_duplicate`（`definition_service.py:867-877`）是**应用层** SELECT，**先**抛 409 `REPORT_DEFINITION_DUPLICATE` ⇒ ⇒ ⇒ **走 API 建两条同名定义永远碰不到 UniqueConstraint** ⇒ ⇒ 约束被删了那条测试照样绿。
- ⇒ ⇒ ⇒ **改法**：PG 那条**直连 ORM 插入**（绕过服务层）⇒ ⇒ 真打到约束。范式见 `tests/api/v1/test_stream_batch_concurrency_pg.py`（CREATE SCHEMA + `options=-csearch_path=` + `alembic upgrade head` + 测完 `DROP SCHEMA CASCADE`）。

### 修正 3 · 路径与文件名的三处出入

| 计划原文 | 实际 |
|---|---|
| `report_builder_tasks.py:79` | `app/workers/report_builder_tasks.py:79` |
| `api.d.ts` | `pcs-frontend/src/types/api.d.ts` |
| 「滚 openapi + api.d.ts + snapshot」 | 还需 `pcs-backend/docs/openapi.json`（**三份**都滚）|

### 修正 4 · 「什么已经存在」（不要重造）

| 已有 | 位置 | 本批怎么用 |
|---|---|---|
| 端点已有的早失败授权判定 | `report_builder.py:526-530` | **扩到解析后的 scope**，不新建 |
| 服务层的 scope 授权判定（worker 侧）| `builder_service.py:199-206` | **保持不动**（fail-closed：执行者身份未知 ⇒ 400 `REPORT_EXECUTOR_UNKNOWN`）|
| 定义可见性（公司级 PUBLISHED+ALL_USERS ⇒ 全员可见）| `definition_service.py:239,285` | ⇒ ⇒ **公司级定义普通用户本来就看得见** ⇒ ⇒ T1-5 的下拉确实会被触发 |
| `ReportDefinitionOut.project_id` | `schemas/report_builder.py:178` / `src/types/api.d.ts:16811` | ⇒ ⇒ **前端能判「公司级」** ⇒ ⇒ **不需要额外契约改动** |
| `POST /report/generate` 的 `project_id` in body | `app/api/v1/report.py:138` | ⇒ ⇒ **「body 传 project_id」有现成先例**，契约改法不是首创 |
| `ReportExecutePage` 已有「执行 + 轮询 + 下载」全套时序 | `src/pages/report/ReportExecutePage.tsx` | 只**加**项目下拉，不重写 |

### 修正 5 · 前端测试与 mock 的现状（**有一处要纠正**）

- 现有：`pcs-frontend/tests/pages/report/ReportExecutePage.test.tsx`（5 例 · 全是轮询/FAILED）· `ReportExecutePageDefinitionRace.test.tsx`（2 例 · 定义拉取竞态）
- ⚠️ **纠正**：原写「`src/mocks/handlers.ts` 零 report-builder handler ⇒ 要补」—— **不准确**：dev 模式的 MSW **已经注册**了 `reportBuilderHandlers`（`src/mocks/browser.ts:29`）⇒ ⇒ ⇒ **要补的不是 handler，而是单测通道的 `api` mock 接线**（现有测试直接 mock `api` 模块：`ReportExecutePage.test.tsx:29`）⇒ ⇒ ⇒ T1-5 的前端测试照这个范式写。
- e2e：`pcs-frontend/e2e/` 下 **无** report-builder spec ⇒ ⇒ 本批可不加 e2e（e2e 不进批末闸门）

### 修正 6 · ⚠️ **CI 拦不住「新增可选字段」** —— T1-1 必须手工滚

**实测**：后端**没有** pytest 快照 OpenAPI；闸门是 shell 的 `pcs-frontend/scripts/check-api-drift.sh`（比 `pcs-backend/docs/openapi.json` 与 `pcs-frontend/openapi.snapshot.json` 两份 JSON）+ CI `.github/workflows/check-api-drift.yml:67`
⇒ ⇒ ⇒ drift 脚本**只标** 路径增删 / schema 增删 / required 变化 / **字段移除** / 类型变化 / enum 变化（`scripts/check-api-drift.sh:105-181`）⇒ ⇒ **新增一个可选字段（`project_id`）它不报**（byte-diff 打了 FAIL 但不计入 drift_count）
⇒ ⇒ ⇒ 且它**从不校验 `src/types/api.d.ts` 是否同步** ⇒ ⇒ ⇒ **stale 的 `api.d.ts` 不会被 CI 抓到**，只有真正用到该字段时 `tsc --noEmit` 才红

⇒ ⇒ ⇒ **T1-1 的落地步骤必须是**：`npm run api:gen` → 提交 `pcs-frontend/openapi.snapshot.json` **与** `pcs-frontend/src/types/api.d.ts` **两份** ⇒ ⇒ ⇒ 并**手工验一次** `npm run api:check`。

### 修正 7 · 🔴 `useProjectScope().projects` **不是按授权过滤的** ⇒ ⇒ 不能直接当候选源

**实测**（`pcs-frontend/src/store/projectScope.ts:82-116` `fetchCandidateIds()`）：候选 = `GET /user-projects/me`（**自己的非撤销授权行**）**∪** `GET /workspaces`（SYSTEM_ADMIN ⇒ 全部；其他角色 ⇒ `?owner_id=me` ⇒ **按所有权，不是按授权**）
⇒ ⇒ ⇒ **授权被撤销的项目、或只是经由工作区触达的项目，仍会出现在 `projects` 里** ⇒ ⇒ ⇒ 此时 `GET /projects/{id}` 会 404（`projects.py:288` 用 API 层守卫）⇒ ⇒ ⇒ 名字退化成 `id.slice(0,8)`
⇒ ⇒ ⇒ ⇒ **用户能在「选项目」下拉里选到一个自己无权执行的项目 ⇒ ⇒ ⇒ 点了才吃 404**

⇒ ⇒ ⇒ **改法（2026-11-24 人裁）**：**按角色分源** ——
- **普通用户** ⇒ `GET /user-projects/me`（只含自己的有效授权行）
- **SYSTEM_ADMIN** ⇒ `GET /workspaces`（admin 看到全部工作区 ⇒ 全部项目）⇒ ⇒ **否则 admin 的下拉是空的**（admin 靠全局 bypass、通常**没有**授权行 ⇒ ⇒ 按钮永远禁用 ⇒ ⇒ 而 admin 恰恰是创建公司级模板的人）

### 修正 8 · 🔴 `useProjectScope` 是**全局 zustand store** ⇒ ⇒ 不能拿它的 `selectProject`

**实测**：`store/projectScope.ts:134` 是**全局单例**，`currentProjectId` = **顶栏**当前项目（`useProjectScope.ts:37-50`）
⇒ ⇒ ⇒ 若在执行页复用 `selectProject(...)` ⇒ ⇒ ⇒ **会把顶栏的当前项目一起改掉** ⇒ ⇒ ⇒ 用户在执行页选个项目，回到别的页发现项目被换了

⇒ ⇒ ⇒ **改法**：执行页用**局部 state** 存「这次执行选的项目」；只**读**候选列表，**不调** `selectProject`。

### 修正 9 · 🔴 今天公司级定义与项目级定义**在界面上长得一模一样**

**实测**：`ReportExecutePage.tsx:257-258` 的 Select label 只有 `${d.name}（${d.version}）`；`grep -c project ReportExecutePage.tsx` = **0**（今天**完全没有**项目选择器）
⇒ ⇒ ⇒ 用户选中一条公司级模板时，**界面没有任何提示说明它需要再选项目** ⇒ ⇒ ⇒ 突然冒出一个下拉会让人莫名其妙

⇒ ⇒ ⇒ **改法**：Select 的 label **标出作用域**（如「XX（v1）· 公司级」/「· 项目级」）⇒ ⇒ 让「为什么要多选一个项目」在选中**之前**就看得见。

### 修正 10 · 前端**不按 error code 分流** ⇒ ⇒ 且今天的失败文案对这个场景是**错的**

**实测**：`ReportExecutePage.tsx:173-176` 的 catch → `errorMessage(err)`（`api/reportBuilder.ts:207-213`：先 `data.message` → 再 `data.code` → 再 `err.message`）⇒ ⇒ ⇒ **整页不按 `code` 分支**（可仿 `src/pages/report/ReportReviewQueuePage.tsx:65-83` 的 `hintFor(code)`）

⇒ ⇒ ⇒ ⚠️ **两个后果**：
- ① 今天那个 400 发生在 **worker** ⇒ ⇒ ⇒ 前端**永远看不到 400** ⇒ ⇒ ⇒ 只见 202 → 轮询 FAILED ⇒ ⇒ ⇒ 显示通用文案「可能是执行器中断后被回收器判定为僵死」⇒ ⇒ ⇒ **对「公司级模板没选项目」这个场景是错误解释** ⇒ ⇒ ⇒ **T1-3 把 400 提前到端点，正是为了让用户拿到真因**
- ② 同端点现在有**两个不同的 404 code**：`REPORT_DEFINITION_NOT_FOUND`（`svc.get` 的可见性判定）与 `PROJECT_NOT_FOUND`（项目守卫）⇒ ⇒ ⇒ 前端若要分流，必须**两个都分**。

### 修正 11 · 下拉的**名字来源**与**空候选态**

**实测**：`GET /user-projects/me` 返回 `UserProjectResponse`（`user_projects.py:49-59`）⇒ ⇒ **不返项目名** ⇒ ⇒ ⇒ 而 `useProjectScope` 的取名逻辑（`projectScope.ts:119-132` `fetchNames`，逐个 `GET /projects/{id}`）是**模块私有**的
⇒ ⇒ ⇒ ⇒ **T1-5 必须自己解决名字来源**（N 次 `GET /projects/{id}`，N 小可接受；或加一个带名字的端点）⇒ ⇒ 否则下拉里只有裸 UUID。

⇒ ⇒ ⇒ ⚠️ **空候选态**：一个**零授权**的用户打开下拉 ⇒ ⇒ 列表空 + 执行按钮永远禁用 + **没有任何解释** ⇒ ⇒ ⇒ 必须给一句可读提示（「你当前没有可执行的项目，请联系管理员授权」）。

### 修正 12 · 🔴 **3 个数据源没有 `project_id` 列** ⇒ ⇒ 「公司级模板」的最自然形态**永远跑不了**

**实测**（`app/services/report/datasource_registry.py` `_add_project_columns()`：把**表上有 `project_id` 列**的源登记进来；13 个源里恰好 3 个**没有**）：

| 数据源 | `project_id` 列 | 语义 |
|---|---|---|
| `DATALINEAGE` | ❌ | 血缘（公司级）|
| `SUPPLIERS` | ❌ | 供应商目录（公司级）|
| `CONFIG_ASSETS` | ❌ | 配置资产（公司级）|

⇒ ⇒ ⇒ `builder_service._project_field()`（`:314-328`）对它们抛 **`400 REPORT_PROJECT_SCOPE_REQUIRED`** ⇒ ⇒ ⇒ **与「你没选项目」是同一个错误码** ⇒ ⇒ ⇒ 文案是假的
⇒ ⇒ ⇒ 而且这发生在 **worker 里**（202 之后）⇒ ⇒ ⇒ 被 ARQ **重试 3 次**（`report_builder_tasks.py:133-134` · `worker.py:48`）⇒ ⇒ ⇒ 最终 FAILED ⇒ ⇒ ⇒ **这批要消灭的「202 → 神秘失败」UX 原封不动地回来了**
⇒ ⇒ ⇒ 且**创建定义时没有任何东西拦**（`validate_definition_json`（`definition_service.py:128-165`）只查注册表成员资格）
⇒ ⇒ ⇒ 且编辑器默认 `projectId: null`（`ReportDefinitionEditorPage.tsx:470-472`）⇒ ⇒ ⇒ **默认路径就在批量生产死路**

⇒ ⇒ ⇒ **改法（2026-11-24 人裁）**：**建定义时拒**（T1-7）—— 公司级定义 + 主数据源是那 3 个 ⇒ ⇒ **创建就拒**（新错误码）。
⇒ ⇒ ⇒ 执行侧**另外**给一个**可区分**的错误码（不再复用 `REPORT_PROJECT_SCOPE_REQUIRED`）⇒ ⇒ ⇒ 让已存在的旧定义跑起来时**说实话**。

### 修正 13 · ⚠️ 一个**秒级窗口**的权限陈旧（记一笔，不改设计）

**实测**：`roles` 随队列载荷走（`report_builder.py:595`）⇒ ⇒ worker 在 `builder_service.py:204` 用**载荷里的 roles** 判 SYSTEM_ADMIN bypass
⇒ ⇒ ⇒ ⇒ **入队后、跑之前**被降权的 SYSTEM_ADMIN 仍会被 bypass（秒级窗口 · 一份报表的越权读）
⇒ ⇒ ⇒ 不改设计（端点已先判过），但**登记**在案。

### 修正 14 · 「什么已经存在」的**反面**：本批**不需要**的东西

- ❌ **不需要迁移**（不改表结构）· ❌ **不需要 seed**（不新增数据）· ❌ **不需要审计行改造**（现有 `REPORT_EXECUTED/FAILED` 行的快照已带解析后的 scope）
- ❌ **不需要**改 `visible_clause`（公司级定义的可见性本来就对）
- ❌ **不需要**给 list / duplicate / update / publish 路径加「定义优先」规则 ⇒ ⇒ **那些路径上不存在「请求项目 vs 定义项目」的冲突**：create/update 的 `project_id` **本来就来自 body**（`definition_service.py:310-314,484-488`）；publish/reject/obsolete 只读 `row.project_id`（`:574,:685`）；list 的 service 级 `project_id` 参数**端点根本没暴露**（`report_builder.py:148-177` 只有 `status`）

---

## 九、未解决（**已全部收口**）

| 原未决项 | 结论 |
|---|---|
| ⚠️ **已存在的「公司级 + 3 个无项目列的源」的旧定义** ⇒ ⇒ 清理 / 迁移 / 放任？ | ✅ **已查实：零存量**（2026-11-25 · 两库各一进程）：`pcs` 8 条公司级定义，主源全是 `HEAT_RESULTS`/`EQUIP_LIST`（**都有 `project_id` 列**）⇒ ⇒ **死路定义 = 0 条**；`pcs_test` **0 条定义** ⇒ ⇒ ⇒ **零迁移**、零清理 ⇒ ⇒ T1-7 只拦新建 + 执行侧给**可区分**的错误码（让已存在的旧定义跑起来时说实话）⇒ ⇒ **本项关闭**（⚠️ 别的环境若还有 ⇒ ⇒ 执行侧那个错误码就是它们的出路）|
| ⚠️ **P10-J-T2 的「被退回」与本批无耦合** | ✅ **确认无耦合** ⇒ ⇒ 可并行，但**不并行改同一处契约** |
| ⚠️ **与 P10-K（§7.5 向导）耦合** | ✅ **串行**（两批都改契约 + 前端类型）⇒ ⇒ ⇒ **P10-K 先落地会先占一个 SPEC 版本号** ⇒ ⇒ ⇒ 本批的 SPEC 版本号在 P10-K 之后重算 |
| ⚠️ **PLAN MODE 未启** | ⚠️ **状态项**：本计划**尚未获批执行**（2026-11-24 用户裁决：新计划须经批准才能执行）⇒ ⇒ **不是缺陷，是闸门** |

---

## 十、落地记录（2026-11-25）

| 任务 | 落地位置 | 备注 |
|---|---|---|
| **T1-1** | `app/api/v1/report_builder.py`（`ReportExecuteRequest.project_id`）· `pcs-backend/docs/openapi.json` · `pcs-frontend/openapi.snapshot.json` · `pcs-frontend/src/types/api.d.ts` | ⚠️ **三份契约都提交了**（CI 拦不住「新增可选字段」⇒ ⇒ 手工 `npm run api:check` 验过）|
| **T1-3** | `app/api/v1/report_builder.py`（**判定顺序照抄 §四**）| ⚠️ **service 的 `project_id or row.project_id` 原样不动**（T1-2 已删 ⇒ 规则只在端点一处）|
| **T1-4** | 快照 `:572` + 入队 `:591` ⇒ ⇒ 都传**解析后的 scope** ⇒ ⇒ `report_files.project_id` 不再落 NULL | |
| **T1-5** | `src/pages/report/ReportExecutePage.tsx` · `src/api/projects.ts`（`executableProjects(isAdmin)`）| ⚠️ 候选源**按角色分**；**不动**全局顶栏；Select label 标作用域；未选 ⇒ 执行按钮禁用 |
| **T1-6** | `docs/PCS-UI-SPEC.md` **§7.18.2** + §12.4 **V2.20**（文件头 V2.19 ⇒ V2.20）· 后端 6 条新用例 · 前端 5 条新用例 · **PG 车道 1 条**（`tests/api/v1/test_report_definition_scope_uniqueness_pg.py` · **直连 ORM**）| |
| **T1-7** | `definition_service._assert_primary_source_project_scopable()`（create + update 都调）· `datasource_registry.source_supports_project_scope()`（**ORM 直查** ⇒ 不受导入顺序影响）· `builder_service._project_field()` 改抛**可区分**的码 | |
| **T1-8** | `docs/adr/0051-report-execution-scope-resolution.md`（+ `docs/adr/README.md` 索引）| |

**车道**（2026-11-25 实测）：

| 车道 | 结果 |
|---|---|
| 后端默认（`uv run pytest`）| **6172 passed** / 164 skipped（上批 6166 ⇒ **+6**）· RC=0 |
| 后端 PG（`bash scripts/pytest_pg.sh`）| **47 passed**（上批 46 ⇒ **+1**）· RC=0 |
| 前端 `npm run typecheck` | clean |
| 前端 `npm run lint` | clean（`--max-warnings 0` + `.` 范围）|
| 前端 `npm run test` | **129 files / 1139 tests passed**（上批 1134 ⇒ **+5**）|
| `alembic check`（**pcs / pcs_test 各一进程**）| 两库都 `p10_005 (head)` + `No new upgrade operations detected` · RC=0 |
| 浏览器（gstack browse · CI=1）| 登录 200 → 仪表盘 → 报表定义 → **执行页：公司级模板出现「选项目」下拉 · 未选时执行按钮禁用 · 选了项目解禁 · 定义下拉 label 标「公司级」** · 执行 POST 202 · 控制台无 error · 无 404 |

⚠️ **本批改了 SPEC 版本号**（V2.19 ⇒ **V2.20**）⇒ ⇒ ⇒ 与 §九 那条「P10-K 先落地会先占一个版本号」的预判**相反**（本批先落地）⇒ ⇒ ⇒ **P10-K 的 SPEC 版本号从 V2.21 起算**。

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 20 | ISSUES_OPEN | 8 issues（本次）· 4 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE VOICE:** hermes（GLM-5.2 · zai）· 计划文本 + 仓库只读 · 跨模型对抗 · **5 条 blocking（3 条推翻了主审的判断）+ 1 条纠正了主审的错误结论**
- **CROSS-MODEL:** 5 处张力全部已由人裁收敛 —— ① 3 个无项目列的数据源 ⇒ **建定义时拒** ② T1-2 倒置 ⇒ **删掉** ③ 候选源 ⇒ **按角色分** ④ PG 那条用例 ⇒ **改成直连 ORM** ⑤ **主审自己错了**：MSW handler 那条（`browser.ts:29` 已注册）⇒ **已纠正**
- **UNRESOLVED:** 4（§九）
- **VERDICT:** eng review 有未决项 ⇒ ⇒ **eng review required**（本计划**未获批**）

⚠️ **本次评审改了计划的 8 处实质内容**：坑 #3 前提错误（端点已在用服务层守卫）· 坑 #5 的 PG 硬门槛降为默认车道 + **改成直连 ORM 的 1 条** · 口径表加 `400 REPORT_PROJECT_SCOPE_MISMATCH` · **删掉 T1-2**（规则收到端点一处）· **加 T1-7**（建定义时拒 3 个无项目列的源）· **加 T1-8**（ADR）· 补「判定顺序」（不重排既有行为）· 补「CI 不拦新增可选字段」这条 CI 盲区 + 候选源按角色分 + 名字来源 + 空候选态。