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

<!-- HERMES-OUTPUT -->
