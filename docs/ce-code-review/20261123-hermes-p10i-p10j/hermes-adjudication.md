# 第三方裁决意见（hermes / learnings 人格）—— 三条**人未裁决**的项

> **范围**：**P10-I-T1** 的两个实现选择（队列端点形态 · 「忽略」存储）
> ＋ **P10-J-T1 · TODO-177** 的两个子问题（公司级模板该不该可执行 · 执行时无权 ⇒ 404 还是 403）
> **裁决者**：hermes（ce-code-review 的 `learnings` 人格）⇒ ⇒ **第三方意见**，非人裁决
> **日期**：2026-11-23
> **取证基准**：`main` @ `8abfdf5f`（**裁决当时**的代码）
> ⚠️ **hermes 只有 Read/Grep 能力** ⇒ ⇒ 全部结论是**读码**结论 ⇒ ⇒ 凡需运行时的点一律标注「需运行时验证」并给命令。
> ⚠️ **本文件不自动应用**：任何一条落地前，先按 `docs/superpowers/plans/2026-11-23-p10-i-report-review-publish.md`
> 与 `docs/superpowers/plans/2026-11-23-p10-j-feature-backlog.md` 的任务重核「事实基础」。
>
> ⚠️ **已由人裁完、本文件不重复裁决的两条**：
> **TODO-197**（2026-11-23 · 选 ①「待我审核」队列 + 三个约束）· **TODO-187**（2026-11-23 · 选 A + 两个约束）。

---

## 0. 送审的三条（原文口径）

### 项 1 · 队列端点形态

- **A**：新建端点 `GET /api/v1/report-builder/definitions/pending-review`
- **B**：复用 `GET /api/v1/report-builder/definitions` + 过滤参数（`status=DRAFT` & `exclude_creator=true`）
- 背景：队列**只读**（只看元数据 · **进不去编辑器** ⇒ `update()` 对非创建人 **404** 保持不变）；
  队列口径**与 `visible_clause` 分离**（公司级 ⇒ `REVIEWER+`；项目级 ⇒ `REVIEWER+` ∧ 我有项目授权；
  无授权 ⇒ 不可见；`created_by == 我` ⇒ 不可见）。

### 项 2 · 「忽略」动作的存储

- **A**：前端 localStorage（不增表）
- **B**：后端新表 + 幂等标记端点
- 背景：本批队列只做**「发布 / 忽略」**（「拒绝」本批不做 ⇒ 登记 TODO-197b）。

### 项 3 · TODO-177（公司级模板 `project_id IS NULL` 恒 400）

- **3.1** 公司级模板**该不该**可执行？（还是「只做模板 · 执行时必须选项目」⇒ ⇒ 那要改契约 + 做 UI 流程）
- **3.2** 执行时指定的**项目**若用户无权 ⇒ ⇒ **404** 还是 **403**？
- 背景：要可执行 ⇒ ⇒ **必须改契约**（`ReportExecuteRequest` 加 `project_id` ⇒ 滚 baseline + 前端类型）；
  `publish()` 对公司级模板**不做**项目判定（任何审核角色可审 · 既有裁决）。

---

## 1. 送审前**已核实**的事实（供 hermes 读码对照）

| # | 事实 | 出处 |
|---|---|---|
| F1 | `GET /definitions` 的 `status` 是**收窄**（加在 `visible_clause` **之后**）⇒ ⇒ `status=DRAFT` 只返回**我自己**的草稿 | `app/services/report/definition_service.py:326-348` |
| F2 | `visible_clause`：**DRAFT 只有创建人可见**（`SYSTEM_ADMIN` 全局 bypass，含别人的草稿）| `app/services/report/definition_service.py:181-222` |
| F3 | 现有列表响应 `ReportDefinitionOut` **含 `definition_json: ReportDefinitionBody`** ⇒ ⇒ 列表**今天就把整个定义正文发到前端** | `app/schemas/report_builder.py:176-190` |
| F4 | `publish()`：① `created_by == actor` ⇒ **403** ② 项目无授权 ⇒ **404**（与「不存在」同码同形）③ 状态须为 DRAFT | `app/services/report/definition_service.py:422-477` |
| F5 | `update()`：**非创建人 ⇒ 404** ⇒ ⇒ **连 SYSTEM_ADMIN 都打不开**别人的草稿编辑器 | `app/services/report/definition_service.py:350-376` |
| F6 | 执行路径**已经**有 scope 项目授权闸：`require_project_access_or_404` ⇒ ⇒ **404**（不是 403）；`user_id is None` ⇒ **fail-closed 拒绝** | `app/services/report/builder_service.py:179-206` |
| F7 | 公司级模板 ⇒ `scope = project_id or row.project_id` ⇒ `None` ⇒ **400 `REPORT_PROJECT_SCOPE_REQUIRED`** | `app/services/report/builder_service.py:179-186` |
| F8 | 前端 `src/` **零** `localStorage` 使用；`store/auth.ts:27` **明确**写「token 只存内存 · 防 XSS / 第三方脚本读取 localStorage」 | `pcs-frontend/src/store/auth.ts:27` |
| F9 | 本仓「per-user · per-item 状态」的既有形状 = **服务端**：`notifications.read_at` + `POST /notifications/{id}/read`（**幂等**）| `app/models/notification.py` · `app/api/v1/notifications.py:62-71` |
| F10 | 前端菜单里报表定义只有一项：`{ key: '/report/definitions', label: '报表定义' }` | `pcs-frontend/src/layouts/MainLayout.tsx:82` |
| F11 | SPEC §7.18 对报表定义只有一句「列表 + 版本 + 共享范围」⇒ ⇒ 新页面**要登记 SPEC 修订** | `docs/PCS-UI-SPEC.md:2176` |
| F12 | ⚠️ **SPEC §6.22（V2.1 · 2026-10-21）锁死了「**待办不落库**」**：「待办实时计算 —— 待办不落库，真值是『签署矩阵当前步骤 × 当前用户角色』」** ⇒ ⇒ 「待我审核」队列若算**待办** ⇒ ⇒ 「队列成员不落库」是 SPEC 级的 ⇒ ⇒ 但「**用户自己的忽略集**」是 per-user 状态 ⇒ ⇒ 与 §6.20 的 `read_at`（**服务端**）同形 ⇒ ⇒ ⚠️ **这一条对项 2 的两边都有张力** ⇒ ⇒ 需要分清「**队列成员**」与「**用户的忽略集**」 | `docs/PCS-UI-SPEC.md:2511`（§6.22 条款 · V2.1 修订记录）|
| F13 | ⚠️ **SPEC §6.22 的**响应形状**是项 1 的直接先例**：`{items: TodoResponse[], total: number}`，单条**只带** `deliverable_id` / `version_id` / `project_id` / `step_order` / `step_role` / `title` ⇒ ⇒ **不带内容正文** ⇒ ⇒ 「待我审核」队列的 item 若照此办理 ⇒ ⇒ **不返 `definition_json`**（= 半成品正文）⇒ ⇒ 且「**越权过滤在服务端完成**」⇒ ⇒ 队列的可见性判断必须在**服务端**（与约束 2 一致）⇒ ⇒ 空态文案也有先例：「**待办为空 ≠ 没有待办**」 | `docs/PCS-UI-SPEC.md:1088-1110`（§6.22 条款正文）|

---

## 2. 送审人的**初判**（供与 hermes 意见对照 · 不是裁决）

| 项 | 初判 | 依据（已核实的代码事实）|
|---|---|---|
| **1** | **A（新端点）** + **独立 schema**（**不带** `definition_json`）| F1：`status=DRAFT` 走 `visible_clause` ⇒ ⇒ 只返回**我自己**的草稿 ⇒ ⇒ **B 根本达不到目的**（除非改 `visible_clause` ⇒ ⇒ 违反约束 2）⇒ ⇒ 「B」实为「A 换个名字」；F3：现有列表响应**带整个 `definition_json`** ⇒ ⇒ 队列**不能**复用 `ReportDefinitionOut` ⇒ ⇒ 必须**另立 schema**（只带 `def_id` · `name` · `category` · `description` · `project_id`(+项目名) · `created_by` · `created_at` · `status`）|
| **2** | **B（后端表 + 幂等标记端点）** —— 与 `notifications.read_at` **同型** | F9：本仓「per-user · per-item 状态」的既有形状就是**服务端**（`read_at` + 幂等端点）；F8：`src/` **零** localStorage，且 `auth.ts` **明确**反对（防 XSS）⇒ ⇒ A 会**开一个新先例**；⚠️ 另注意：**待办是实时计算的**（`compute_todos`）⇒ ⇒ 仓里**没有**待办表 ⇒ ⇒ 「忽略」无处搭载 ⇒ ⇒ 只能是「独立小表」或「客户端」 |
| **3.1** | **该可执行**（执行时选项目）| F7：恒 400 的根因是**契约缺字段**（不是产品禁止）⇒ ⇒ 且 `publish()` 对公司级模板**不做**项目判定 ⇒ ⇒ 公司级模板本就是产品概念 ⇒ ⇒ 补 `project_id` 字段是**最小**改法 |
| **3.2** | **404**（与「不存在」同形）| F6：执行路径**已经**是 `require_project_access_or_404` ⇒ ⇒ **现在就是 404** ⇒ ⇒ 只要新增字段时**别改成 403** ⇒ ⇒ 且与仓规矩「无权 ≡ 不存在 ⇒ 逐字同形」一致 |

⚠️ **3.1 本质是产品决定**（公司级模板该不该被执行）⇒ ⇒ hermes 若给不出知识库依据
⇒ ⇒ 应当**明说「需人裁」**，只给技术侧约束与后果。

---

## 3. hermes 的第三方意见

### 3.1 · Learnings 搜索结果（≤5 条）

⚠️ 本仓**无** `docs/solutions/patterns/critical-patterns.md`（persona 的 Critical Patterns 节**省略**）。

| # | 学习 | 出处 | 对本次的作用 |
|---|---|---|---|
| L1 | **守卫覆盖审计**（security_issue / critical）| `docs/solutions/security-issues/guard-coverage-audit-logistics-adjacent-modules.md` | 判据「未授权返回什么 = 404(同形)✓ / 403(角色闸)⚠️ / **403(项目守卫)=缺口** / 200=缺口」(:46)⇒ ⇒ 定 **项 3.2**；「断项目授权的断言**必须**用 `strict_client`」(:253-258)⇒ ⇒ 项 1 的断言要求；publish「API 层权限对 · 产品流程在 UI 上走不完 · **API 层覆盖 ≠ 产品流程覆盖**」(:247)⇒ ⇒ 项 1 的立论；公司级模板不可执行 = **已知限制不是漏洞**(:295-296)⇒ ⇒ 项 3.1 的定性 |
| L2 | **角色白名单手抄第二份**（high）| `docs/solutions/security-issues/role-vocabulary-must-have-one-source.md` | 「抄第二份 = 下一个合法用户 403」·「**拼错**比漏写更贵 ⇒ 须有**唯一真相源**」⇒ ⇒ 项 1 的 **A-3** |
| L3 | **dialect 约束在 SQLite 上看不见**（high）| `docs/solutions/database-issues/dialect-options-invisible-on-sqlite.md` | `project_id IS NULL`（公司级作用域）语义**单测不可验**⇒ ⇒ 项 3 必须走 **PG 车道**；「一次声明意图 + 每 dialect 变体写全 + 每真库证明」 |
| L4 | **窄声明是约束还是遗漏**（high）| `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md` | 「**看它被消费的地方，不要看它的形状**」·「fixture 只能用契约类型构造」⇒ ⇒ 项 1 的字段裁剪与新 schema |
| L5 | **手写 create_table 静默丢继承列 / FK**（high）| `docs/solutions/database-issues/alembic-create-table-silently-drops-schema-elements.md` | 读 mixin + 约束名从 NAMING_CONVENTION 推导 +「**测试库是 ORM 的渲染 ⇒ 绿灯对真库无证明力**」⇒ ⇒ 项 2 选项 B 的成本清单 |

旁支：`docs/solutions/testing-issues/assertion-must-be-sensitive-to-named-defect.md`（断言须敏于它命名的分支）。

---

### 3.2 · 项 1 · 队列端点形态 ⇒ **选 A（新建端点）** + 4 条要求

**A-1 · 过滤落 service 层** ⇒ ⇒ 既有模式「判定在 service ⇒ 端点漏调也绕不过」(`report_builder.py:248-251`)

**A-2 · 两份 EXISTS 抽共享 helper，勿复制**（`definition_service.py:230-238`）

**A-3 · 角色闸引唯一真相源** ⇒ ⇒ 现状**已 2 份**（`report_builder.py:236` `PUBLISH_ROLES` + `definition_service.py:65` `OBSOLETE_ROLES`）⇒ ⇒ 队列会是**第 3 份** ⇒ ⇒ 层规则「service 不 import api」(`definition_service.py:62-64`)⇒ ⇒ 落 `app/core/acl.py`

**A-4 · SYSTEM_ADMIN 也排除自己的草稿** ⇒ ⇒ `visible_clause` 给 admin 恒真（含别人的草稿，`:240-241`），而 `publish()` 自审 **403**(`:454-458`)⇒ ⇒ 否则队列出现「**点了必失败**」的按钮

**判据**：**B 在契约层做不到** —— `ReportDefinitionOut.definition_json` **必填**（openapi `required` 实测）⇒ ⇒ 约束 1 要求队列**不带半成品** ⇒ ⇒ 复用要么**泄正文**、要么让 `GET /definitions` 变**条件响应**（前端类型 + OpenAPI 都变糊）；且「只读」**已结构性成立**（`update()` → `get()` → `visible_clause` ⇒ 非创建人 404，`definition_service.py:314-323,372-376`）⇒ ⇒ 队列**只能自足**；B 还要给「已审计 + 棘轮盯住」的端点加两参（`tests/conftest.py:340`），而 `DefinitionService.list(project_id=)` **已是死参**（`:328` · 端点从不传）。

**建议字段**（新具名 schema `ReportDefinitionReviewItem`）：
`def_id` / `name` / `created_by` / `project_id`（可空 = 公司级）/ `created_at` / `updated_at` / `description` / `category`
⇒ ⇒ **不带** `definition_json`（约束 1）· **不带** `version`（改草稿不动版本号 ⇒ 恒值）· **不带** `status`（恒 DRAFT）· 不带 `output_format` / `max_rows`。

⚠️ **风险（需人裁）**：`publish()` **不判 `shared_with`**（`:454-478` 只判自审 / 项目授权 / 状态）⇒ ⇒ `CREATOR_ONLY` 草稿**谁都能发**，发布后**仅创建人可见** ⇒ ⇒ **队列一上 UI 就给它开了口子**，而约束 2 的过滤表**漏了这一维**。

**其它要求**：队列须进 `AUDITED_PROJECT_SCOPED_ENDPOINTS`（`tests/conftest.py:333`）并**同批**抬棘轮（`:357`）；四条过滤规则的断言**全用 `strict_client`** 且**成对**断（有授权 ⇒ 出现 / 无授权 ⇒ 不出现），否则是**假绿**。

---

### 3.3 · 项 2 · 「忽略」存储 ⇒ **选 A（前端本地）** + 2 条约束

- ⚠️ **键必须是 `(def_id, updated_at)`** —— `version` **不行**：改草稿不动版本号（`definition_service.py:402-404`）⇒ ⇒ 只按 `def_id` 忽略 ⇒ ⇒ 会把创建人**改过的**草稿**永久静默隐藏**；`updated_at` 是 `onupdate=func.now()`（`app/models/mixins.py:41-43`）⇒ ⇒ 一改就**重新出现**
- **介质需人知情**：前端**零** `localStorage` 且有成文反对理由（`pcs-frontend/src/store/auth.ts:26-27`「防 XSS / 第三方脚本读取 localStorage」）⇒ ⇒ hermes 倾向 **`sessionStorage`**（刷新仍在 · 关标签即失 · 不建新模式）

**判据**：忽略语义**不是**状态 / 授权 / 审计 ⇒ ⇒ 后端表代价失衡；先例 `notifications.read_at`（`app/models/notification.py:109-111`）服务的是「已读」（**有用户可见后果**），忽略**没有** ⇒ ⇒ 不需要那套。

**风险**：换设备会忘（但 `publish()` 对已发布返 **409**（`definition_service.py:474-475`）⇒ ⇒ 重复发布幂等由后端兜住 ✅）；无「取消忽略」入口 ⇒ ⇒ 建议加「显示已忽略」开关；键名**带版本前缀**。

**翻成 B 的判据**：跨设备 / 需留痕 / 实际变成「**指派**」/ **TODO-197b 落地时**（那批本就要动数据模型 ⇒ ⇒ 建议把「忽略」的持久化**一并推给它**，一次做对）。

---

### 3.4 · 项 3.1 · 公司级模板该不该可执行 ⇒ **是产品决定，需人裁**

⇒ ⇒ 但技术侧只剩**一个**选项：**不存在「无项目地执行」** —— `execute_definition` 的 `scope is None` ⇒ 恒 400
（`builder_service.py:179-185`；注释：「**不能默认全库查询** —— 那会把别的项目的数据一起导出去」；
测试 docstring `tests/api/v1/test_report_builder.py:790-795`：「放行的后果不是『数据多一点』，而是**全库所有项目的数据**被导进一份报表交给任何一个能打开执行面板的人」）
⇒ ⇒ 计划里的「① 可执行 vs ② 只做模板、执行时必须选项目」**其实是同一件事**
⇒ ⇒ **真问句是「要不要把『执行时选项目』做成 UI 流程」**。

**三条技术约束（落地时必须满足）**：

- **a** **前端地基已在**（P10-H · TODO-194：`src/hooks/useProjectScope.ts` + `src/store/projectScope.ts`）⇒ ⇒ 但执行页**完全不认项目**（`src/pages/report/ReportExecutePage.tsx` 全文无 `project_id`）⇒ ⇒ 要接
- **b** ⚠️ **必须把 scope 顺序倒过来：`scope = row.project_id or body.project_id`**（现状 `project_id or row.project_id`，`builder_service.py:179`）—— 一旦 `ReportExecuteRequest` 有 `project_id`，前端**总是**发当前选中项目 ⇒ ⇒ **绑在项目 B 的定义会被拿项目 A 的数据执行** ⇒ ⇒ 不是越权（A 有权），而是「定义名叫 B、出来的是 A 的数据」的**静默语义事故**
- **c** ⚠️ **入队必须传「解析后的 scope」**（现状传 `str(row.project_id or "")`（`report_builder.py:463`）；worker `pid = uuid.UUID(project_id) if project_id else None`（`app/workers/report_builder_tasks.py:79`））⇒ ⇒ 否则公司级模板一执行，`report_files.project_id` 落 NULL ⇒ ⇒ **产出文件无项目归属**

**另**：**SPEC V1.0 无此条款**（`docs/PCS-UI-SPEC.md:2168-2176` 只有「报表定义管理：列表 + 版本 + 共享范围」；`:1506/:1539/:1541` 的「公司级」讲的是报表**样式**不是报表**定义**）⇒ ⇒ 冻结版 ⇒ ⇒ **须登记 SPEC 修订**（P10-J 自己的未解项 #2 已提）。

**技术倾向（仍是产品决定）**：选「公司级模板＝模板，执行时选项目」—— 让公司级模板**真正可用**（现在只能写不能用）· **3.1-b** 的顺序修正使**项目级定义行为完全不变**（纯增量）· 前端地基已在。**但请人明确裁**，并同时决定 SPEC 条款怎么写。

---

### 3.5 · 项 3.2 · 指定项目无权 ⇒ **404**（**技术决定，非产品决定**）

1. 守卫契约明写：「无权访问 `project_id` ⇒ ⇒ **404**（与『不存在』同形）…… ⇒ ⇒ **403 不行** ⇒ ⇒ 403 会泄露『这个项目存在』」—— `app/services/user_project_service.py:352-376`
2. 审计判据把「403（项目守卫）」归类为**缺口** —— audit `:46`
3. 端点对**定义自带**的项目已走 404（`report_builder.py:398-402`）⇒ ⇒ 指定项目必须**同口径**
4. 与 TODO-187b 约束 1 **不冲突**（跨资源类型可不同：「报表定义不存在」vs「项目不存在」）

**实现钉子**：404 须走 **service 层**那份（`code="PROJECT_NOT_FOUND"`）⇒ ⇒ **不能**用 api 层 `_guard.check_project_access_or_404`（抛 `HTTPException` ⇒ `code="HTTP_404"`）⇒ ⇒ 否则 **code 不同仍可枚举**（与 TODO-187b 的落地要点同一条）。
⇒ ⇒ **403 的合法位置只剩「角色闸」**（角色不够 ⇒ 403 对；项目无权 ⇒ 404 对）。

---

### 3.6 · 与已裁决条目的冲突检查

**TODO-197**（选 ① + 三个约束）

- 约束 1（只读）✅ **无冲突**，且被代码事实**加强**：只读是**现状**（`update()` → `get()` → `visible_clause` ⇒ 非创建人 404，`definition_service.py:314-323,372-376`）⇒ ⇒ 本批**只需加一个列表端点**，无需任何新写闸
- 约束 2（口径与 `visible_clause` 分离）✅ 无冲突（A 即其实现）—— ⚠️ 但**该表漏了一维**：`shared_with`（见项 1 风险）
- 约束 3（「拒绝」本批不做 ⇒ TODO-197b）✅ 无冲突，且建议把「忽略」的持久化**一并推给 TODO-197b**
- ⚠️ **人裁原话「列表页发布按钮」与「队列页」有措辞出入**：审核者在**列表页**看不到别人的草稿（可见性只给本人 + 已发布）⇒ ⇒ 按钮必须长在**队列页**；两处都有 ⇒ ⇒ 列表页那处对审核者是**死按钮** ⇒ ⇒ **措辞需人明确**
- ⚠️ **P10-I 计划的「跨文档」清单漏了 SPEC 修订登记**（新增队列页 = SPEC 变更）

**TODO-187**（选 A + 两个约束）

- 约束 1 ✅（跨资源类型可不同）· 约束 2 ✅（本批**不动**守卫默认值 ⇒ ⇒ 124 处 project 级零回归**自动满足**）
- ⚠️ 项 3.2 的 404 code 必须与「项目不存在」**同形** ⇒ ⇒ 复用 **service 层**那份
- **T2 与项 3 正交**（T2 改的是 12 族端点**自己**抛的「X not found」，不含项目守卫这一族）⇒ ⇒ 无顺序依赖

---

### 3.7 · hermes 列出的**待人裁清单**（6 条）

| # | 待裁 | 归属 |
|---|---|---|
| ① | 队列要不要列 `shared_with == CREATOR_ONLY` 的草稿（`publish()` **不判** `shared_with` ⇒ ⇒ 会发出**只有创建人可见**的模板）| P10-I · T1 |
| ② | 「发布」按钮放**队列页**还是两处 | P10-I · T1 |
| ③ | 「待我审核」页的 **SPEC 修订登记** | P10-I · T1 |
| ④ | 「忽略」用 `localStorage` 还是 `sessionStorage` | P10-I · T1 |
| ⑤ | 公司级模板执行**是否进 P10-J** + SPEC 条款怎么写 | P10-J · T1 |
| ⑥ | ⚠️ **scope 顺序倒置（`row.project_id or body.project_id`）必须写进 TODO-177 落地清单** —— 它不是「要不要」的问题，是「**实现时必须做**」，否则会被当风格省掉 | P10-J · T1 |

---

### 3.8 · hermes 的工具说明（值得单独记）

⚠️ 本机 **Grep/Glob 不可用**（ToolSearch 0 命中）⇒ ⇒ 它**实测 Bash 可用且未挂起**（本次约 **20 次只读命令**）
⇒ ⇒ 「**子代理 Bash 会挂起**」这条记忆在**本机**可能已**过期** ⇒ ⇒ 值得单独验一次。
