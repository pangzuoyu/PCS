# P10-K · SPEC §7.5 项目向导 —— 计划

> **来源**：`TODOS.md` · `TODO-195`（SPEC §7.5 按 SPEC 全做）· `TODO-203`（模板选择的数据源）
> **性质**：**前端为主** + **后端补端点 + 迁移** + **契约变更**
> **状态**：✅ **已批准**（2026-11-25 · 人裁「approve」）⇒ ⇒ ⇒ **可开工**（但与 P10-J-T1 **串行** ⇒ ⇒ ⇒ **排在 P10-J-T1 之后**）
> **2026-11-24/25 · plan-eng-review + hermes 第三方审查已审完**，全部待裁项已裁（见 §十 / §十一）⇒ ⇒ **计划已按裁决改写，待批准执行**

---

## 一、⚠️ 实测**推翻** TODO-203 的前提 ⇒ ⇒ ⇒ **三个选项全部作废**

| TODO-203 说的 | **实测** | 出处 |
|---|---|---|
| 「仓里**没有**「项目模板」实体」| ❌ **有** —— `project_templates` **表存在** | 迁移 `dd47298c9c38`（v3.1 全量 53 表）；`p2_sup_sprint_int1_project_template_integration.py` 加 `pipe_code_template_id` 列 + `project_template_pipe_classes` 关联表 |
| | ✅ `ProjectTemplate` **ORM 存在**（**9 列**：`template_id` / `name` / `industry` / `default_config_json` / `version` / `status`（默认 `"ACTIVE"`）/ **`asset_id`（FK `config_assets`）** / `checklist_json` / `pipe_code_template_id`）| `app/models/config_domain.py:194-224` |
| | ✅ `ProjectTemplateConfig` **schema 存在**（**7 段**：`record_approval` 记录审批 / `stream_approval` 物流审批 / `numbering` 编号 / `customer_approval` 业主审批 / `signature_matrix` 签署矩阵 / `version_sequence` 版本序列 / **`reversal_role` 逆审角色**）| `app/schemas/project_template.py:117-130` |
| | ✅ `ProjectTemplateService` **存在**（5 方法：`validate_config` / `load` / `get_default_pipe_class_ids` / `get_pipe_code_template_id` / `set_default_pipe_classes`）| `app/services/project_template_service.py` |
| | ⚠️ **零 API 端点** + **零*生产*调用方**（3 个测试文件在调它 ⇒ 「零调用方」不准确）| 实测 |
| | 🔴 **本批两库都是 0 行**（`pcs` / `pcs_test` 的 `project_templates` 与 PUBLISHED `config_assets` 都是 0）⇒ ⇒ ⇒ 「只列已发布」与「seed」都**没有可参照的现状** | 实测（2026-11-24）|

⇒ ⇒ ⇒ **原三选项**：①「新造模板概念」**不需要**（概念已存在）②「该步降级」**不必**③「拿最近用过的项目冒充模板」**不必**
⇒ ⇒ ⇒ **新选项 ④：用真模板** ⇒ ⇒ ⇒ 仍要补：**列表端点 + 应用端点 + 发布语义 + seed**（见 §三）

---

## 二、SPEC §7.5 四项 vs 现状（实测）

| SPEC §7.5 要求 | 现状 | 差距 |
|---|---|---|
| 项目创建向导 | `ProjectWizardPage` = **占位**：3 步（项目/PMS/BEDD）· 每步**只有一个「标记完成」复选框** · **不调任何端点** · 路由 `/wizard`（`App.tsx:158`，导航 `MainLayout.tsx:123` **普通组**）| **几乎全部** |
| **BEDD 编辑：分组 Tab** | ✅ `BeddPage` **已做**（**9** 个分组 Tab + SchemaForm + `PUT /projects/{id}/bedd` + 项目守卫 + 角色闸）| ✅ 已齐 ⇒ ⇒ ⇒ **本批不抽它**（见 §十·裁 11）|
| 表单：SchemaForm 驱动 | ✅ 已做 | — |
| **单位制切换**（**顶部**下拉 · 切换后所有数值**实时转换** · 提示「已按 1 bar = 100 kPa 转换」）| ❌ **完全没有** —— `unit_system` 只是 `ProjectCreate` 的必填**自由文本**（`str`，min 1 max 20）| **全部** |
| ⚠️ 「实时转换」的数据基础 | ⚠️ 字段单位**在标签里**（`"气压 (kPa)"`）⇒ ⇒ **没有机器可读单位** ⇒ ⇒ ⇒ **没法编程换算**<br>✅ 但 `UiSchemaField.unit` **已在契约里且已被前端消费**（**不是**「没被填」）| **要补一环** |

### ⚠️ 四处**必须先纠正**的前提（评审核实）

| # | 计划/SPEC 的说法 | 实测 |
|---|---|---|
| **C-1** | 「SPEC §7.5 列 **8** 组，与页面 9 组要核」 | ❌ **SPEC 列的就是 9 组**（`docs/PCS-UI-SPEC.md:1273-1281`）· 后端 9（`app/schemas/bedd.py:57-141`）· 前端 9（`BeddPage.tsx:28-38`）· 已有断言 9 ⇒ ⇒ **三方一致，「8 vs 9」是伪问题，写死 9** |
| **C-2** | 模板 7 段含「**设备类型码**」 | ❌ 第 7 段是 **`reversal_role`（逆审角色）**；「设备类型码」只活在 ORM 列**注释**里（`config_domain.py:211-214`，过期注释）⇒ ⇒ **基于它写的落库目标不存在** |
| **C-3** | `UiSchemaField.unit`「在契约里但没被填」 | ❌ **已填 5 个资源**（`ui_schema_service.py:128/135/142/188/272/281/290/348`）**且前端已在渲染**（`SchemaForm.tsx:225-233` 追加「/ kPa」）⇒ ⇒ W-1 给 BEDD 补 unit ⇒ **双重单位显示「气压 (kPa) / kPa」** ⇒ ⇒ **必须同步去标签里的单位** |
| **C-4** | 「7 段全落」⇒ ⇒ 两者都能填 | ❌ `SignatureMatrixBinding` 的 docstring 明写「**与 record_approval 互斥（用其一即可）**」（`app/schemas/project_template.py:86-87`）⇒ ⇒ ⇒ 两个都填 ⇒ ⇒ **422 拒绝**（见 §四·4.3）|

---

## 三、任务清单（评审 + hermes 改写后）

### 硬前置（不做则本批跑不起来）

| # | 内容 | 文件 | 状态 |
|---|---|---|---|
| **W-0** 🔴 | **seed 三样东西**（不是「至少 1 条模板」）：<br>① **2 条 `project_templates`**（`status='PUBLISHED'`）—— ⚠️ **「7 段全落」在单条模板上做不到**（`record_approval` ↔ `signature_matrix` **互斥**）⇒ ⇒ ⇒ **模板 A（签署矩阵型）**：`signature_matrix` ✔ + `record_approval` ✘ + 其余 5 段 ✔；**模板 B（审批深度型）**：`record_approval` ✔ + `signature_matrix` ✘ + 其余 5 段 ✔ ⇒ ⇒ ⇒ **7 段在集合层面全覆盖 + 互斥被遵守**<br>② 它们依赖的**命名 SignatureMatrix**（`signature_matrices` 行）+ **PipeCodeTemplate** + `project_template_pipe_classes` 关联行<br>③ **一个未被占用的 FORMAL 工作区**（⚠️ **今天 `pcs` 只有 1 个 FORMAL 工作区、已被唯一项目占用** ⇒ ⇒ 向导第 1 步的工作区下拉**恒空** ⇒ ⇒ ⇒ **没有它整个向导跑不起来**）<br>⚠️ e2e 还要**幂等**：跑一次就把 seed 的工作区吃掉 ⇒ ⇒ 第二次跑 409 `WORKSPACE_ALREADY_HAS_PROJECT` ⇒ ⇒ ⇒ 每次跑用**新的**工作区或重置 | `pcs-backend/scripts/seed_*.py` | ✅ |

### 单位制（存储恒为 SI）

| # | 内容 | 文件 | 状态 |
|---|---|---|---|
| **W-1** | `BEDD_FIELDS` 加**第五元组 `unit`**（机器可读）⇒ ⇒ ⚠️ **两处生产解包同步改**（`app/schemas/bedd.py:150` `for field_key, _label, _widget, kind in ...` · `app/services/ui_schema_service.py:56` `for i, (field_key, label, widget, _kind) in ...` ⇒ ⇒ **不加就 import 期崩**）⇒ ⇒ **把单位从标签里删掉**（避免 C-3 的双重显示）⇒ ⇒ ui-schema 填 `unit` + **`unit_display {factor, offset, display_unit}`** | `app/schemas/bedd.py` · `app/services/ui_schema_service.py` | ✅ |
| **W-1b** 🔴 | **契约类加字段**：`UiSchemaField`（`app/api/v1/meta.py:122`）**必须加 `unit_display`** ⇒ ⇒ 否则 `meta.py:234` 的 `UiSchemaField(**f)`（pydantic 默认 `extra='ignore'`）⇒ ⇒ ⇒ **静默丢弃** `unit_display` ⇒ ⇒ ⇒ **症状 = 字段永远标灰、无任何报错** | `app/api/v1/meta.py` | ✅ |
| **W-2** | `unit_system` **词表化**：`app/models/enums.py` 加 `class UnitSystem(str, Enum): SI / US` ⇒ ⇒ schemas 用它 ⇒ ⇒ `meta_service.get_enums()` 暴露一组（前端不手写）⇒ ⇒ **DB 加 `CheckConstraint` + 一条迁移**<br>✅ **存量取证已完成**（2026-11-24 · 两库各一进程）：`pcs` = **1** 行全 `'SI'` · `pcs_test` = **254** 行全 `'SI'` ⇒ ⇒ **两库今天加 CHECK 都安全** ⇒ ⇒ ⚠️ **别的环境仍须重跑** `SELECT DISTINCT unit_system FROM projects` | `app/models/enums.py` · `app/schemas/project.py` · `app/models/project.py` · `alembic/versions/*` · `app/services/meta_service.py` | ✅ |
| **W-2b** | `ProjectOut` **加 `unit_system`**（⚠️ 这一改同时动 `POST /projects` / `GET /projects/{id}` / `PATCH .../product-category` **三个端点的响应**）⇒ ⇒ **新增窄端点** `PATCH /projects/{id}/unit-system`（仿 `set_product_category` 的形状：SYSTEM_ADMIN + 项目守卫）⇒ ⇒ ⚠️ **不要抄 `product_category` 的 422 保护** —— 那个是因为产品类别有**冻结下游值**（`projects.py:341-357`），`unit_system` **没有** | `app/schemas/project.py` · `app/api/v1/projects.py` | ✅ |
| **W-4** | 前端：**单位制下拉**（页面顶部）⇒ ⇒ **默认取 `project.unit_system`**（需 `ProjectOut` 暴露）· 切换 = **页面临时覆盖**（不写项目）⇒ ⇒ **实时换算** + 提示（**按实际量纲生成**）⇒ ⇒ **不可换算的 10 个数值字段标灰 = 不换算、按原值显示**（**不是禁用**）⇒ ⇒ 标签里的单位**换成 `unit_display.display_unit`**（否则 US 模式下标签写 kPa、值是 14.5 psi）| 新组件 `src/pages/bedd/UnitSystemSwitch.tsx` + `BeddPage` | ✅ |
| **W-5** | 前端：**换算逻辑**（纯函数，最好测的文件）⇒ ⇒ **canonical 恒 SI** · 读路径 canonical→display · 写路径 display→canonical ⇒ ⇒ ⚠️ **form state 保持 canonical**，**只在控件边界换算** ⇒ ⇒ 否则每次保存时**未被编辑的字段也会在末位比特上漂移** ⇒ ⇒ 往返相对误差上界 **≤ 1e-9** ⇒ ⇒ ⚠️ 验收例子 **14.5 psi = 99.97 kPa**（不是 100！`14.5 × 6.894757293168 = 99.97`）⇒ ⇒ ⇒ 断言要带容差 | 新文件 `src/utils/units.ts` | ✅ |
| **W-19** | **缺因子的兵底**：后端加新单位却**忘了**填 `unit_display` ⇒ ⇒ 前端必须**明确**怎么办（标灰 + 「该字段无换算」· **不是**静默不换）⇒ ⇒ ⚠️ 「后端新增单位不可能不带因子」是**约定不是类型**（`ui_schema_service._FIELDS` 是手写 dict ⇒ `ui_schema_service.py:68`）⇒ ⇒ ⇒ 必须有这条兵底 + 对应测试 | `src/utils/units.ts` | ✅ |

### 项目状态（DRAFT/ACTIVE · 兑现 SPEC §12.4 V1.6 的旧承诺）

| # | 内容 | 文件 | 状态 |
|---|---|---|---|
| **W-2c** 🆕 | `Project.status` **词表化** = **`DRAFT` / `ACTIVE`**（2 值）⇒ ⇒ **DB 加 `CheckConstraint`**（与 `unit_system` 的 CHECK **同一条迁移**）⇒ ⇒ ⚠️ `projects.status` **今天全仓无人读** ⇒ ⇒ ⇒ **加这个态的行为影响几乎为零**<br>✅ **存量取证已完成**（2026-11-25 · 两库各一进程）：`pcs` 1 行 + `pcs_test` 254 行 ⇒ **distinct status 全是 `['ACTIVE']`** ⇒ ⇒ ⇒ **两库今天加 CHECK 都安全**<br>⇒ ⇒ ⇒ **兑现 SPEC §12.4 V1.6 早就承诺过的「项目两态 DRAFT/ACTIVE」**（模型里一直没落地）| `app/models/enums.py` · `app/models/project.py` · `alembic/versions/*` | ✅ |
| **W-2d** 🆕 | **激活端点** `PATCH /projects/{id}/status`（`DRAFT` → `ACTIVE`；SYSTEM_ADMIN + 项目守卫）⇒ ⇒ ⇒ **向导第 4 步「确认」调它** ⇒ ⇒ ⇒ **从项目页跳过去补完的用户** ⇒ ⇒ ⇒ 项目页（PMS）对 **DRAFT** 项目显示一个「**完成配置并激活**」入口（同一个端点）⇒ ⇒ ⇒ ⚠️ **DRAFT 不改变任何行为**（今天没有任何守卫读 `Project.status`）⇒ ⇒ ⇒ ⇒ 它纯粹是「**未完成向导**」的标签 | `app/api/v1/projects.py` · `src/pages/pms/PmsPage.tsx` | ✅ |

### 模板

| # | 内容 | 文件 | 状态 |
|---|---|---|---|
| **W-3** | 后端：`GET /project-templates` ⇒ ⇒ **SYSTEM_ADMIN 闸** · **只列 `status='PUBLISHED'`** · **响应必须是**命名模型 `ProjectTemplateSummary`（⚠️ **裸字段基线正好 71**（182 个 schema 里 111 已覆盖）⇒ ⇒ ⇒ **必须命名响应模型** ⇒ ⇒ ⇒ **不要照抄** `pipe_codes.py:131` 那个**没有 `response_model`** 的形状 ⇒ ⇒ **那会把棘轮推爆**）⇒ ⇒ 响应**不含 `default_config_json`** ⇒ ⇒ + `ProjectTemplateService.list_templates()`（⚠️ `get_default_pipe_class_ids`（`service.py:52-61`）**每模板一次查询** ⇒ ⇒ **N+1** ⇒ ⇒ 要批量）⇒ ⇒ 滚 openapi + `src/types/api.d.ts` + **snapshot** | `app/api/v1/project_templates.py`（新）· `app/services/project_template_service.py` | ✅ |
| **W-3b** | **「已发布」的定义**（本批新建）：`ProjectTemplate.status` 词表化 = **`DRAFT` / `PUBLISHED` / `OBSOLETE`**（3 值，⚠️ **不是** config 资产那套 5 态 —— `PipeClass.status` 的 DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE 在 `config_domain.py:262-264`，`config_assets.asset_subtype` 也**没有** `PROJECT_TEMPLATE` 取值 ⇒ ⇒ ⇒ **本批模板不挂 `config_assets`** ⇒ ⇒ `asset_id` 留空）⇒ ⇒ **谁写 `PUBLISHED`**：本批只有 **seed** 写 ⇒ ⇒ ⇒ **没有发布端点**（另开 · **TODO-206**）⇒ ⇒ ⇒ 端点只列 `PUBLISHED` | `app/models/config_domain.py` · `app/schemas/project_template.py` | ✅ |
| **W-3c** | **模板落库**（7 段，按「有消费者的进真家、无消费者的升列」分工）：<br>· `signature_matrix` → `project_signature_matrix_bindings`（`app/models/deliverable.py:190-197`，有 (project_id, module) 唯一约束）✔ **唯一干净落点**<br>· `record_approval` → **改绑** ⚠️ **只许替换「自动绑的默认」** ⇒ ⇒ **`ensure_default_record_matrix` 明写「不覆盖：人工改过的绑定不被夺走」**（`app/services/signature_matrix_service.py:751-758`）⇒ ⇒ ⇒ 条件化替换<br>· `pipe_code_template_id` → 项目管号配置 **fork**（现成路径 `pipe_codes.py:364` `fork_to_project`，带 `source_template_id` 溯源）<br>· `checklist_json` → 输入清单<br>· `numbering` → 与管号子系统**语义重叠** ⇒ 对齐而非另建<br>· 🆕 `stream_approval.max_depth`（int）· `customer_approval.proxy_allowed`（bool）· `customer_approval.attachment_required`（bool）· `version_sequence.skip_alpha_versions`（bool）· `version_sequence.allowed_purposes`（list）· `reversal_role.reversal_approver_role`（str）⇒ ⇒ ⇒ **物理形状 = `projects` 表 + 6 个具体列**（**2026-11-25 裁**）⇒ ⇒ ⇒ **不建 4 张表**（免 JOIN、免外键）⇒ ⇒ ⇒ **不建 JSONB blob**（6 个都是标量 ⇒ 列更好查）⇒ ⇒ ⇒ ⚠️ 这 4 段**今天没有任何消费者**（只出现在 `app/schemas/project_template.py`）⇒ ⇒ ⇒ 写了没人读<br>· 🆕 `applied_template_json`（**1 列 JSONB provenance**）⇒ ⇒ 记「哪个模板 / 哪一版 / 什么时候应用的」⇒ ⇒ **不承载配置**（配置在上面那些落点）⇒ ⇒ ⇒ 兼作「未来重放/审计」的依据 | `app/models/project.py` · `app/models/deliverable.py` · `app/services/project_template_service.py` · `alembic/versions/*` | ✅ |
| **W-3d** | **应用模板的端点**（**本批核心写路径** · 2026-11-24 人裁）：**新端点** `POST /projects/{id}/apply-template`（body: `template_id`）⇒ ⇒ 服务层**同一事务**：① 校验模板已发布 ② `signature_matrix` 改绑 ③ `record_approval` 改绑（**只替自动绑的**）④ `pipe_code_template_id` fork ⑤ `checklist_json` ⑥ 4 段 typed 列 ⑦ `applied_template_json` provenance ⇒ ⇒ **失败整事务回滚** ⇒ ⇒ **幂等**（重试安全）⇒ ⇒ ⚠️ **`record_approval` 与 `signature_matrix` 都填 ⇒ ⇒ 422**（C-4 互斥）<br>⚠️ 顺带修 `ProjectTemplateService` docstring 里那个**不存在**的 `create_from_template`（`service.py:19`）| `app/api/v1/projects.py` 或新文件 `app/api/v1/project_templates.py` · `app/services/project_template_service.py` | ✅ |
| **W-3e** | ⚠️ **`POST /projects` 已有约束必须尊重**：**只收 SYSTEM_ADMIN**（`projects.py:120`）· **只收 FORMAL 工作区**（`:126-138`）· **一个工作区只能挂一个项目**（`:143-158` 409）· 建完**回填 `workspaces.project_id`**（`:198` ⇒ 工作区被占用）⇒ ⇒ ⇒ 向导的工作区下拉**必须过滤掉已挂项目的工作区**（`WorkspaceOut.project_id` 有值 ⇒ `listWorkspaces` 不过滤 ⇒ 前端要过滤）| `src/api/projects.ts` · `src/components/ProjectCreateForm.tsx` | ✅ |

### 向导

| # | 内容 | 文件 | 状态 |
|---|---|---|---|
| **W-6** | 前端：向导**重做 4 步**（**建项目 → 项目人员 → 选模板 → 确认**）⇒ ⇒ ①`POST /projects`（**`status='DRAFT'`**）②`POST /user-projects/grant` ③`POST /projects/{id}/apply-template` ④`PATCH /projects/{id}/status`（**→ ACTIVE**）+ 摘要 + 「**去项目录 BEDD**」⇒ ⇒ ⚠️ **深链到现有 `BeddPage`**（`projectScope` store 设当前项目 → 跳 `/bedd`）⇒ ⇒ ⇒ **不抽 `BeddForm`**（2026-11-25 人裁）⇒ ⇒ ⇒ **不动已工作的 `BeddPage`**<br>⚠️ **`/wizard` 挪进 admin 组**（2026-11-25 人裁）⇒ ⇒ ⇒ `MainLayout.tsx:123` ⇒ ⇒ ⇒ 非 SYSTEM_ADMIN **根本看不到入口** ⇒ ⇒ ⇒ 不会出现「进去才发现没权限」<br>⚠️ **中间态**（第 2/3 步失败）⇒ ⇒ ⇒ **保留已建项目**（**不拆**）⇒ ⇒ ⇒ 留在向导里 + 明确告知「项目已创建（编号 X），但第 N 步未完成」+ 两个出口：「**去项目页继续**」/「**留在本页重试**」⇒ ⇒ ⇒ ⚠️ **向导不可重入**（已建的项目不再走向导）⇒ ⇒ ⇒ **不引入任何删除能力** | `src/pages/wizard/ProjectWizardPage.tsx` · `src/pages/routeWrappers.tsx` · `src/layouts/MainLayout.tsx` | ✅ |
| **W-6c** | **抽 `ProjectCreateForm`**（8 必填 + 工作区下拉 + 错误处理 + `unit_system` Select）⇒ ⇒ `ProjectAdminPage` 与向导**共用** ⇒ ⇒ 不复制第二份 | 新文件 `src/components/ProjectCreateForm.tsx` · `src/pages/admin/ProjectAdminPage.tsx` | ✅ |
| **W-16** | 🔴 **建完项目后 `projectScope` store 要刷新**：`ensureLoaded` 是**每会话一次**（`useProjectScope.ts:45-48`）⇒ ⇒ ⇒ **刚建的项目不会出现在顶栏选择器** ⇒ ⇒ ⇒ 「去项目」需要一个**明确的目标**（`selectProject(newId)` + 跳 `/bedd`）⇒ ⇒ ⇒ 且 `grant_project_access` 给了创建者授权 ⇒ ⇒ 但 store 的候选列表**没重新拉** | `src/store/projectScope.ts` · `src/pages/wizard/ProjectWizardPage.tsx` | ✅ |

### SPEC + 测试 + 基础设施

| # | 内容 | 文件 | 状态 |
|---|---|---|---|
| **W-7** | SPEC **§7.5 改 4 步**（顺序改为 建项目 → 项目人员 → 选模板 → 确认，「BEDD 录入」改为确认步的「去项目录 BEDD」入口）+ 补**单位制换算口径**（canonical 恒 SI · **8 个可换字段** · 不可换算字段=标灰不换算 · 提示文案按量纲生成）+ 补**§7.10.6「项目模板」的对应关系登记**（⚠️ 实为 **12 项**（不是 10）：输入清单模板 / 默认单位制 / 默认模块 / 默认管道等级 / BEDD 默认结构 / 版本序列配置 / 签署矩阵绑定 / 记录批准深度 / 物流校对深度 / 编号模板 / 客户代录配置 / 撤销批准角色）⇒ ⇒ **9 项有对应、3 项没有**（默认单位制 / 默认模块 / BEDD 默认结构）⇒ ⇒ ⇒ 那 3 项都是「**模板给新项目预填**」⇒ ⇒ 要补就得让**模板选择前置于建项目** ⇒ ⇒ ⇒ 与「项目先建」顺序**冲突** ⇒ ⇒ ⇒ **本批登记关系、不补实现**）+ **§12.4 修订登记**（含 **§3.2 与 §7.5 的矛盾**：`:216` 说「单位制只读、在 PMS 改」vs `:1284` 说「顶部下拉实时转换」⇒ 调和为「下拉默认取项目值、切页面临时覆盖；改项目默认去 PMS」+ **项目两态 DRAFT/ACTIVE**）+ **SPEC 文件头版本号同步**（当前 V2.19；⚠️ **P10-J 先落地会先占一个版本号** ⇒ ⇒ 本批的版本号要在 P10-J 之后重算）| `docs/PCS-UI-SPEC.md` | ✅ |
| **W-8** | 断言（后端：端点闸 + 词表 + `unit`/`unit_display` 填充 + 7 段落库 + DRAFT/ACTIVE 转换 + 迁移；前端：向导 4 步 + 换算 util + 下拉 + 漂移守卫）| `tests/` · `pcs-frontend/tests/` | ✅ |
| **W-10** 🔴 | **前端漂移守卫会自我失效**：`pcs-frontend/tests/mocks/bedd_ui_schema_drift.test.ts:44` 的正则**只匹配 4 元组** ⇒ ⇒ W-1 加第 5 元素后 `backendFieldPaths()` 返回空 ⇒ ⇒ 连它自己的「别让守卫悄悄失效」断言都会红 ⇒ ⇒ **必须同批改正则（容忍第 5 元素）+ 让守卫顺便比对 `unit`** | `pcs-frontend/tests/mocks/bedd_ui_schema_drift.test.ts` | ✅ |
| **W-11** | 前端 mock seed 是后端真相的**第 2 份镜像**（`pcs-frontend/src/mocks/seed/pms.ts:130-186`）⇒ ⇒ **同步补 `unit` + 去掉标签里的单位** ⇒ ⇒ ⚠️ **还要加一条「标签里不再含单位」的回归测试**（否则 C-3 的双重显示会悄悄回来）| `pcs-frontend/src/mocks/seed/pms.ts` | ✅ |
| **W-13** | msw **零 `http.put` handler** ⇒ ⇒ `PUT /projects/{id}/bedd` 在 mock/dev 通道是未处理路径 ⇒ ⇒ 补 `PUT /projects/:id/bedd` + `GET /project-templates` handler（⚠️ `POST /api/v1/projects` 的 mock 在 `src/mocks/signFlow.ts:88`）⇒ ⇒ ⇒ `handlers.test.ts` 的 **ajv 形状校验**要加新端点 | `pcs-frontend/src/mocks/handlers.ts` · `pcs-frontend/tests/mocks/handlers.test.ts` | ✅ |
| **W-18** | ⚠️ **mock 与真实枚举要对齐**：`signFlow.ts:88` 的 `POST /projects` mock 必须开始**拒非 SI/US** **与拒非 DRAFT/ACTIVE** ⇒ ⇒ 否则 dev 与 prod 漂移（前端下拉只给 SI/US，但 mock 接受任意值）| `pcs-frontend/src/mocks/signFlow.ts` | ✅ |
| **W-14** | e2e：`/wizard` **不在** `e2e/real_backend_route_sweep.spec.ts` 的 ROUTES 里 ⇒ ⇒ 补进去（SYSTEM_ADMIN 登录有现成的：`loginViaUi(realPage,'dan')`，`real_backend_route_sweep.spec.ts:162`）⇒ ⇒ ⚠️ 专用 `project_wizard.spec.ts` **需要幂等设计**（每次跑消耗一个 FORMAL 工作区）⇒ ⇒ ⇒ ⇒ **不做**（⇒ ⇒ 降级为「ROUTES 扫达 + vitest 覆盖流程」）| `pcs-frontend/e2e/` | ✅ |
| **W-15** | `pcs-frontend/tests/pages/wizard/ProjectWizardPage.test.tsx` 的 **14 条断言全部绑死在占位页 props 契约**（`initialSteps` / `initialProjectName` / `onStepDone` / `onFinish`）⇒ ⇒ W-6 是**整文件重写**（⚠️ 但因为**不嵌 BeddForm** ⇒ ⇒ 断言量比原计划**少很多**）| 同左 | ✅ |
| **W-17** | ⚠️ **审计决定**（本批要**明确回答**，哪怕答案是「不写」）：模板应用 / 矩阵改绑 = **改变「谁该签」**的治理动作 ⇒ ⇒ 而 `signature_matrix_service.py` 里**零 audit** ⇒ ⇒ ⇒ 本批：**模板应用写一条审计**（`resource_type=project` / `action=PROJECT_TEMPLATE_APPLIED` / 快照带 template_id + version + 7 段摘要）⇒ ⇒ ⇒ 矩阵改绑另记（现有绑定路径没审计）| `app/services/audit_service.py` | ✅ |
| **W-20** | ℹ️ **psychro 词表的同义关系要落进代码注释**：`app/schemas/psychro.py:499,524-525` 的 `units: Literal["METRIC","IMPERIAL"]`（docstring：「METRIC 公制 SI / IMPERIAL 英制」）⇒ ⇒ ⇒ **与本批 `SI`/`US` 是同一个轴、只是拼写不同** ⇒ ⇒ ⇒ 本批**不动 psychro**（其 docstring 明写「**不影响算法，仅标注**」）⇒ ⇒ ⇒ ⇒ 但 **`UnitSystem` 的 docstring 必须点名它**（⚠️ **否则下一个人会把两套合并**）⇒ ⇒ ⇒ 且在 SPEC §12.4 登记这层关系 | `app/models/enums.py` · `docs/PCS-UI-SPEC.md` | ✅ |

---

## 四、口径（**已逐条裁完**，见 §十）

### 4.1 向导 4 步（2026-11-25 人裁：深链 BeddPage ⇒ 不嵌 BEDD 录入）

| 步 | 内容 | 端点 |
|---|---|---|
| 1 | **建项目**（基本信息 + 工作区 + `unit_system`）⇒ ⇒ **`status='DRAFT'`** | `POST /projects` |
| 2 | **项目人员**（加授权 + `role_in_project`）| `POST /user-projects/grant` |
| 3 | **选模板**（**必选** ⇒ 不选不能继续）| `GET /project-templates` + **`POST /projects/{id}/apply-template`** |
| 4 | **确认** ⇒ ⇒ **`status` → `ACTIVE`** + 摘要 + 「**去项目录 BEDD**」⇒ ⇒ 设 `projectScope` + 跳 `/bedd` | `PATCH /projects/{id}/status` |

⚠️ **BEDD 必须在项目建完后存**（2026-11-24 人裁）⇒ ⇒ 第 4 步在第 1 步之后，天然满足 ⇒ ⇒ **不存在「暂存 BEDD」问题**。

⚠️ **`/wizard` 在 admin 组**（2026-11-25 人裁）⇒ ⇒ ⇒ 与 `/admin/projects` 同口径。

⚠️ ⚠️ **弃单残留的成因要写对**（本计划上一版写错了，已改）：**早期建项目是本批的「选择」，它就是碎屑的成因**（不是「建项目本身的固有后果」）—— 若改成「第 4 步才建」，碎屑是 0 ⇒ ⇒ ⇒ **但那与「项目先建、其余是项目下的动作」的模型冲突** ⇒ ⇒ ⇒ 本批用 **DRAFT 态**收口（见 4.4）⇒ ⇒ ⇒ **不提供删除/清理功能**（→ **TODO-204**）。

### 4.2 中间态口径（第 2/3 步失败）

| 情形 | 处置 |
|---|---|
| 第 2 步 `grant` 失败 | **保留已建项目**（`status` 留 `DRAFT`）⇒ ⇒ 留在向导 + 告知「项目已创建（编号 X），但『项目人员』未完成」+ 两个出口：「**去项目页加人员**」/「**留在本页重试**」⇒ ⇒ ⇒ **不引入删除能力** |
| 第 3 步 `apply-template` 失败 | 同上（事务回滚 ⇒ 项目未被模板配置，但项目本身还在）⇒ ⇒ 「去项目页配置模板」/「留在本页重试」 |
| 用户点了「去项目页」 | ⇒ ⇒ 项目**留在 `DRAFT`** ⇒ ⇒ **项目页（PMS）对 DRAFT 项目显示「完成配置并激活」入口**（`PATCH /projects/{id}/status`）⇒ ⇒ ⇒ ⚠️ **DRAFT 不改变任何行为**（今天没有任何守卫读 `Project.status`）⇒ ⇒ ⇒ 它纯粹是「**未完成向导**」的标签 ⇒ ⇒ ⇒ 也让弃单项目**可被识别、可被清理**（运维只需 `status='DRAFT'` 一句）|
| 向导**不可重入** | 已建的项目不再走向导（`/wizard` 是「**新建**项目向导」）⇒ ⇒ ⇒ 续做走项目页 |

### 4.3 单位制口径

| 项 | 口径 |
|---|---|
| **存储** | **恒为 canonical（SI）** —— 换算是**双向视图变换**：读 `canonical→display`，写 `display→canonical` |
| **换算位置** | ⚠️ **form state 保持 canonical**，**只在控件边界换算** ⇒ ⇒ 否则每次保存时未被编辑的字段也会在末位比特上漂移 |
| **项目级 `unit_system`** | 该项目的**默认显示单位制**（SI / US）· **不是**存储单位 |
| **页面下拉** | 默认取 `project.unit_system`；切换 = **页面临时覆盖**（不写项目）|
| **改项目默认** | 去 PMS ⇒ `PATCH /projects/{id}/unit-system` |
| **可换字段（8）** | 气压 kPa→psi · 背压 kPa→psi · 气温 ℃→℉（**偏移 ×9/5+32**）· 风速 m/s→ft/s · 海拔 m→ft · 降雨/雪/蒸发 mm/a→in/a |
| **不可换（10，标灰）** | 噪声 dB×2（**对数刻度**）· 湿度 % · 雷暴/雾 d/a×2 · 日照 h/a · 太阳辐射 W/m² · kW/m² · 加速度 g · 设计寿命 a ⇒ ⇒ **标灰 = 不换算、按原值显示**（**不是禁用**）|
| **无单位（35）** | 蒸汽/水/空气/… 等介质与类别字段 ⇒ **本来就没有数可换** |
| **提示文案** | **按实际量纲生成**（如「已按 1 psi = 6.895 kPa、1 ℉ = … 转换」）⇒ ⚠️ **不再用 SPEC 原文那句固定的「1 bar = 100 kPa」**（US 是 psi 不是 bar）|
| **往返精度** | 相对误差上界 **≤ 1e-9** ⇒ ⚠️ **验收例子：`14.5 psi = 99.97 kPa`（不是 100）** ⇒ 断言要带容差 |
| **标签单位** | 标签里的单位**删掉**（避免双重显示）· 渲染时用 **`unit_display.display_unit`**（US 模式下标签不能还写 kPa）|
| **换算因子归属** | **后端拥有**，随 ui-schema 下发（`UiSchemaField.unit_display = {factor, offset, display_unit}`）⇒ ⇒ 前端**没有换算表** ⇒ ⇒ ⚠️ 但这是**约定不是类型** ⇒ ⇒ ⇒ **必须有「后端漏填因子」的兵底**（W-19）|

### 4.4 项目状态口径（DRAFT/ACTIVE）

| 项 | 口径 |
|---|---|
| **取值** | `DRAFT` / `ACTIVE`（**2 值**，无 CHECK ⇒ ⇒ 本批加 CHECK）|
| **默认值** | `ACTIVE`（`POST /projects` 不传时）⇒ ⇒ ⇒ **向导第 1 步显式传 `DRAFT`** |
| **语义** | `DRAFT` = 「**由向导建了但没走完**」⇒ ⇒ ⇒ **不改变任何行为**（今天没有任何守卫读 `Project.status`）⇒ ⇒ ⇒ 它是**标签**，不是状态机 |
| **转换** | 只 `DRAFT → ACTIVE`（单向；**没有**「DRAFT → 取消/删除」）|
| **谁转** | 向导第 4 步「确认」⇒ ⇒ ⇒ 或从项目页跳过去补完的用户 ⇒ ⇒ ⇒ **项目页（PMS）对 DRAFT 项目给「完成配置并激活」入口** |
| **兑现的旧承诺** | SPEC §12.4 V1.6 早就承诺的「项目两态 DRAFT/ACTIVE」⇒ ⇒ ⇒ 模型里一直没落地 ⇒ ⇒ ⇒ 本批补上 |

### 4.5 模板口径

| 项 | 口径 |
|---|---|
| **谁能看** | **SYSTEM_ADMIN only** · 只列 `status='PUBLISHED'` · 响应**命名模型** `ProjectTemplateSummary`（**不含 `default_config_json`**）|
| **是否必选** | **必选** ⇒ ⇒ ⇒ **seed 是硬前置**（W-0）|
| **生效范围** | **7 段全落**（W-3c）⇒ ⇒ 2 段进真绑定 + 1 段走 fork + 1 段对齐 + 4 段 typed 列 + 1 列 provenance |
| **互斥** | `record_approval` 与 `signature_matrix` **同时填 ⇒ ⇒ 422**（C-4）⇒ ⇒ ⇒ ⇒ **一条模板填不满 7 段** ⇒ ⇒ ⇒ ⇒ **seed 种 2 条**（模板 A signature_matrix 型 / 模板 B record_approval 型）⇒ ⇒ ⇒ ⇒ 7 段在**集合层面**全覆盖 |
| **改绑前提** | `record_approval` **只许替换「自动绑的默认」**，**不夺人工绑定**（`ensure_default_record_matrix` 的既有不变量）|
| **端点归属** | `project_templates` 是**配置层**实体 ⇒ ⇒ 新文件 `app/api/v1/project_templates.py` |

---

## 五、预判的坑（评审 + hermes 改写后）

| # | 坑 | 对策 |
|---|---|---|
| 1 | ⚠️ **单位在标签里** ⇒ ⇒ 换算只能改字符串 | W-1 加 `unit` 字段 **+ 从标签里删单位** + **两处 4 元组解包同步改** |
| 2 | 🔴 **「换算只改显示、不改已存的值」是自相矛盾的** | 改为「**存储恒为 canonical（SI）**；切换只改显示；**提交前换回 canonical**」⇒ ⇒ 原验收条件「存回去的是原值」**作废** ⇒ ⇒ 新验收：「US 下提交 14.5 psi ⇒ **落库 ≈ 99.97 kPa**（带容差）」|
| 3 | 🔴 **`UiSchemaField` 不加 `unit_display` ⇒ 静默丢弃** | W-1b ⇒ ⇒ 且**加一条测试断言该字段真的到达客户端** |
| 4 | 🔴 **向导第 3 步没有「把模板应用到项目」的入口** ⇒ ⇒ 本批核心写路径**完全没被指定** | W-3d 新端点 `POST /projects/{id}/apply-template`（同事务 · 幂等）|
| 5 | 🔴 **「已发布」没有定义** ⇒ ⇒ 过滤条件与 seed 都没语义 | W-3b：`status` 词表化（DRAFT/PUBLISHED/OBSOLETE）· 本批只有 seed 写 PUBLISHED |
| 6 | 🔴 **向导 happy path 在当前环境跑不起来**（唯一 FORMAL 工作区已被占用 ⇒ 工作区下拉恒空） | W-0 加「一个未占用的 FORMAL 工作区」· e2e 幂等 |
| 7 | 🔴 **`record_approval` ↔ `signature_matrix` 互斥** ⇒ ⇒ 「7 段全落」在单条模板上做不到 | C-4 ⇒ **422**（同填）⇒ ⇒ **seed 种 2 条**（4.5）|
| 8 | 🔴 **`ensure_default_record_matrix` 明写「不覆盖人工绑定」** | W-3c 的改绑**条件化**为「只替自动绑的默认」|
| 9 | 🔴 **新端点用裸 object 会把 payload 棘轮推爆**（基线正好 71 裸字段） | W-3 必须用**命名响应模型** ⇒ ⇒ ⇒ **不要照抄** `pipe_codes.py:131` 那个无 `response_model` 的形状 |
| 10 | 🔴 **W-1 会打死前端漂移守卫**（正则只匹配 4 元组）⇒ ⇒ 守卫当天变成「什么都测不到」 | W-10 同批改正则 + 让守卫顺便比对 `unit` |
| 11 | 🔴 **无 seed ⇒ 模板列表恒空 ⇒ 向导卡死** | W-0 硬前置 |
| 12 | 🔴 **`POST /projects` 只收 SYSTEM_ADMIN + FORMAL + 一工作区一项目** ⇒ ⇒ 向导第 1 步对非管理员必 403 | ✅ **已裁**：`/wizard` **挪进 admin 组**（W-6）⇒ ⇒ ⇒ 非管理员**根本看不到入口**⇒ ⇒ ⇒ **TODO-205 由此关闭** |
| 13 | ⚠️ **模板 `record_approval` 与 `POST /projects` 已绑的默认 RECORD 矩阵冲突** | W-3c 明确是**条件化改绑**，不是新建 |
| 14 | ⚠️ **4 段模板配置今天没有消费者** | 人裁：升 **typed 列**（`projects` 表 + 6 个标量列）⇒ ⇒ **写入但无人读** ⇒ ⇒ ⇒ 「谁该签」类的段才是真消费者 |
| 15 | ⚠️ **`projectScope` store 每会话只拉一次** ⇒ ⇒ 建完项目顶栏看不到它 | W-16 刷新 + 定义「去项目」目标 |
| 16 | ⚠️ **`ProjectCreateForm` 的「已自动绑定记录级签署矩阵」提示在第 3 步改绑后变假** | W-6c 抽组件时把该提示改成**按项目实际绑定状态**渲染 |
| 17 | ⚠️ **`ProjectTemplateService` docstring 引用不存在的 `create_from_template`** | W-3d 顺手改（同批 · 不单开任务）|
| 18 | ⚠️ **`ProjectWizardPage` docstring 引用不存在的「SPEC §7.5.3」** | W-6 重写该文件时顺手改（同批 · 不单开任务）|
| 19 | ⚠️ **改 `unit_system` 为枚举 ⇒ 既有数据若不是 SI/US ⇒ 读出来就炸** | ✅ **两库已取证**：全 `'SI'` ⇒ ⇒ 但**别的环境仍须先跑** `SELECT DISTINCT` |
| 20 | ⚠️ **改 `unit_system` 为枚举 ⇒ mock 不跟着改 ⇒ dev 与 prod 漂移** | W-18 |
| 21 | ⚠️ **SPEC §7.5 说「所有数值实时转换」但只有 8 个字段能换** ⇒ ⇒ §12.4 必须**明确切这个口子** | W-7 |
| 22 | ⚠️ **换算往返 ⇒ 未编辑字段在末位比特上漂移** | W-5：form state 保持 canonical，只在控件边界换算 |
| 23 | ⚠️ **中间态失败 ⇒ 已建项目/已占工作区变垃圾** | 4.2：保留项目 + 明确提示 + 去项目页继续 · **不引入删除** · DRAFT 态让它可识别 |
| 24 | ⚠️ **DRAFT 项目如果被守卫读 ⇒ 行为变** | ✅ `projects.status` **今天全仓无人读** ⇒ ⇒ ⇒ **零行为影响** ⇒ ⇒ ⇒ 但**加 CHECK 约束**（防止别的环境塞进第三种值）|
| 25 | ⚠️ **psychro 的 `METRIC/IMPERIAL` 与 `SI/US` 同义不同拼** ⇒ ⇒ 下一个人会把两套合并 | W-20：`UnitSystem` 的 docstring 点名 + §12.4 登记 |

---

## 六、验收

- [ ] `GET /api/v1/project-templates` 在契约里（**三份**都更新）· **SYSTEM_ADMIN 闸** · 只列 `PUBLISHED` · **命名响应模型**（裸字段基线**仍 ≤ 71**）· 响应**不含** `default_config_json` · **无 N+1**
- [ ] **seed 落地**：**2 条**已发布模板（**A：signature_matrix 型** / **B：record_approval 型**）· 各自的 SignatureMatrix / PipeCodeTemplate / 关联行 · **一个未占用的 FORMAL 工作区** ⇒ 端点返回**非空** 且 向导第 1 步的工作区下拉**非空**
- [ ] `POST /api/v1/projects/{id}/apply-template` 存在 · **同一事务**（7 段中任一段失败 ⇒ 全回滚）· **幂等** · `record_approval` 与 `signature_matrix` 都填 ⇒ ⇒ **422**
- [ ] `record_approval` 改绑**只替换自动绑的默认** ⇒ ⇒ 人工改过的绑定**不被夺走**（断言：先人工改绑定 → 再应用模板 → 绑定不变）
- [ ] 向导 **4 步**每一步都有实际内容 · 第 4 步「去项目录 BEDD」⇒ ⇒ 设 `projectScope` + 跳 `/bedd` ⇒ ⇒ **顶栏当前项目随之切换**
- [ ] **`/wizard` 在 admin 组** ⇒ ⇒ 非 SYSTEM_ADMIN 的导航里**看不到**它
- [ ] 向导第 1 步建的项目 **`status='DRAFT'`** · 第 4 步「确认」⇒ ⇒ **转 `ACTIVE`** · 项目页对 **DRAFT** 项目有「完成配置并激活」入口
- [ ] 第 2/3 步失败 ⇒ ⇒ **项目保留**（`DRAFT`）+ 明确文案「项目已创建（编号 X），但第 N 步未完成」+ 两个出口（去项目页 / 留在本页重试）⇒ ⇒ ⇒ **没有引入任何删除调用**
- [ ] 单位制下拉在页面顶部 · 默认取 `project.unit_system` · 切换后**8 个字段真的换算** · 提示文案**按量纲生成** · 不可换算字段**标灰但仍可录入**（按原值显示）
- [ ] 标签**不含单位**且**只显示一次**（无双单位）· US 模式下标签显示 `psi` 而不是 `kPa`
- [ ] 换算是**双向**的：US 下提交 14.5 psi ⇒ **落库 ≈ 99.97 kPa**（**带容差**）⇒ ⇒ 往返相对误差 **≤ 1e-9**
- [ ] **未编辑的字段**在一次保存后**末位比特不变**（canonical 保持在 state）
- [ ] 后端漏填 `unit_display` 的字段 ⇒ ⇒ 前端**标灰 + 提示**（不是静默不换）
- [ ] `ProjectOut` 有 `unit_system` + `PATCH /projects/{id}/unit-system` 可用（**403 非 admin / 404 无权 / 200 + 回显**）
- [ ] `unit_system` 与 `status` 的 DB `CHECK` 存在 ⇒ ⇒ **两库各跑一次** `alembic check`（**独立进程**）+ 直查 `alembic_version` 与约束存在性
- [ ] `GET /api/v1/meta/enums` 含 `UnitSystem` 组 ⇒ ⇒ 前端从它取词表（**不手写**）
- [ ] 前端漂移守卫**仍有效**（解析到 >30 个字段路径）
- [ ] 「标签里不再含单位」的**回归测试**在（否则 C-3 会悄悄回来）
- [ ] `handlers.test.ts` 的 ajv 形状覆盖含新端点 · `signFlow.ts` 的 `POST /projects` 拒绝非 SI/US 与非 DRAFT/ACTIVE
- [ ] SPEC §7.5 改 4 步 + 换算口径 + **§7.10.6 的 12 项对应关系登记（3 项未补 + 为什么）** + §12.4 修订登记（项目两态 + psychro 同义关系）+ 文件头版本号同步（⚠️ 在 P10-J 之后重算）
- [ ] 后端 / 前端 / PG 三车道绿 · 浏览器回归

---

## 七、失败模式（production）

| 失败模式 | 有测试？ | 有错误处理？ | 用户看得见？ |
|---|---|---|---|
| **换算往返精度塌陷 ⇒ 存储值被悄悄改** | ⬜ **要加**（相对误差上界 + 属性测试）| ⬜ **要加** | ❌ **静默** ⇒ 🔴 **critical gap** |
| **未编辑字段末位比特漂移**（每次保存都改一点）| ⬜ **要加** | ⬜ **要加**（canonical 保持在 state）| ❌ **静默** ⇒ 🔴 **critical gap** |
| 模板 7 段中 3 段写成功、4 段失败 | ⬜ **要加** | ⬜ **要加**（同一事务）| ✅ 回滚 ⇒ 明确失败 |
| 后端加新单位但漏填 `unit_display` | ⬜ **要加**（兵底测试）| ✅（W-19 标灰 + 提示）| ✅ |
| `unit_system` / `status` 存量不合规 ⇒ CHECK 迁移炸 | ✅ **已取证**（两库全合规）· 别的环境要重跑 | ⬜ **要加**（清晰报错 + 修复路径）| ✅ 迁移报错 |
| 模板 `default_config_json` 泄漏给无权用户 | ⬜ **要加** | ✅（summary 不含它）| — |
| 向导弃单 ⇒ 留 **DRAFT** 项目 + 占用 FORMAL 工作区 | ✅ | ⬜ | ⚠️ 用户看得见（项目页会显示「完成配置并激活」）⇒ ⇒ ⇒ **可识别、可清理**（运维按 `status='DRAFT'` 一句）⇒ ⇒ ⇒ **不再需要单独的清理脚本**（→ **TODO-204 降级**）|
| 第 2 步 grant 失败 | ⬜ **要加** | ✅（4.2：保留项目 + 明确提示 + 去项目页继续）| ✅ |
| 第 3 步模板应用失败 | ⬜ **要加** | ✅（事务回滚 + 明确失败 + 去项目页继续）| ✅ |
| 浏览器中途刷新 ⇒ 重新走第 1 步 ⇒ `project_no` 409 | ✅ | ⬜ **要加**（提示「该编号已存在」）| ✅ |
| 「去项目页继续」后项目**永远停在 DRAFT**（用户忘了激活）| ⬜ **要加** | ✅（项目页有激活入口）| ✅（项目页显示「完成配置并激活」）|

---

## 八、什么已经存在（不要重造）

| 子问题 | 已有 | 复用方式 |
|---|---|---|
| BEDD 分组 Tab | **已完成**（后端 `BEDD_FIELDS` + ui-schema + `BeddPage` + 9 Tab 单测 + 漂移守卫）| ⚠️ **本批不抽它**（深链）⇒ ⇒ 只在 `BeddPage` 加单位制下拉 |
| 字段单位 | ui-schema 的 `unit` **已存在且已被前端渲染**（5 个资源已填）| 只给 BEDD 补填 + **去标签单位** + 契约类加 `unit_display` |
| 建项目表单 | **已完成**（`ProjectAdminPage.tsx:126-210`：8 必填 + 工作区下拉 + 错误处理 + 「已自动绑定记录级签署矩阵」提示 + `unit_system` 输入框）| 抽 `ProjectCreateForm`，两处共用 |
| 项目人员授权 | **已完成**（`POST /user-projects/grant`，SYSTEM_ADMIN，带 `role_in_project`）| 向导第 2 步直接用 |
| 模板→管号 | **已完成**（`pipe_codes.py:364` `fork_to_project`，带 `source_template_id` 溯源）| `pipe_code_template_id` 段照抄 fork 语义 |
| 签署矩阵绑定 | **已完成**（`project_signature_matrix_bindings`，`app/models/deliverable.py:190-197`）| `signature_matrix` 段的落点 |
| 默认 RECORD 矩阵 | **已完成**（`signature_matrix_service.py:751` `ensure_default_record_matrix`，**不覆盖人工绑定**）| `record_approval` 段改绑的**前提** |
| 公司级只读资源的读面 | **有**：report styles —— 公司级**只给 SYSTEM_ADMIN**（`report.py:355-364`）；⚠️ **更近的先例**是 `GET /pipe-code-templates`（`pipe_codes.py:147`）⇒ **DESIGNER/PROCESS_CONTROLLER 也可读** ⇒ ⇒ ⇒ 两个先例**要么都引要么都不引** | 本批只 SYSTEM_ADMIN（唯一调用方是向导，而向导第 1 步已要 SYSTEM_ADMIN）|
| 枚举词表单一真相源 | **有**：`app/models/enums.py`（str Enum）+ `meta_service.get_enums()` 19 组 | `UnitSystem` / `ProjectStatus` 走这条路（照抄 `ProductCategory` 的「枚举默认 + CHECK」形状，`models/project.py:84-97`）|
| 换算因子归后端 | **有先例**：`config_energy_conversion_factors` / `pcs_toe_conversion_factors` | 因子随 ui-schema 下发 |
| 审计 | **有**：`AuditService` + `AuditAction` | W-17 决定模板应用要不要写审计 |
| **项目两态 DRAFT/ACTIVE** | ⚠️ **SPEC §12.4 V1.6 早就承诺**，但**模型里一直没落地**（`projects.status` 是**只写不读**的装饰列）| W-2c/W-2d **兑现旧承诺**（不是新概念）|

---

## 九、人裁记录（2026-11-24/25 · plan-eng-review + hermes 逐条裁完）

| # | 待裁项 | 裁决 |
|---|---|---|
| 1 | 批次切分 | **一批做完**（不拆 3 批）|
| 2 | 模板 7 段落几段 | **全 7 段落** ⇒ ⇒ 2 段进真绑定 + 1 段走 fork + 4 段**typed 列** + 1 列 provenance |
| 3 | 换算语义 | **存储恒为 SI（canonical）**，切换只改显示；**双向变换**；**form state 保持 canonical，只在控件边界换算**；往返误差 ≤ 1e-9 |
| 4 | 向导步骤表 | **4 步**：建项目 → 项目人员 → 选模板 → 确认（**深链现有 `BeddPage`**，**不抽 `BeddForm`**）⇒ ⇒ **SPEC §7.5 改 4 步 + 登 §12.4** |
| 5 | `unit_system` 词表与强制 | **SI / US**，走 `app/models/enums.py` + `get_enums()` + **DB CHECK + 迁移**；✅ **存量已取证**（两库全 `SI`）|
| 6 | 换算范围 | **8 个字段** · 其余 10 个数值字段**标灰 = 不换算、按原值显示**（不是禁用）· 35 个非数值字段无数可换 · 提示文案**按量纲生成** |
| 7 | 换算表归属 | **后端拥有**，随 ui-schema 下发（`unit_display {factor, offset, display_unit}`）⇒ ⇒ **前端无换算表** ⇒ ⇒ ⇒ 但**要有「后端漏填」的兵底**（W-19）|
| 8 | 单位制层级 | **混合**：下拉默认取 `project.unit_system` · 切换 = 页面临时覆盖 · 改项目默认去 PMS（+1 窄 PATCH 端点 + `ProjectOut` 暴露 `unit_system`）|
| 9 | 谁能看模板 | **SYSTEM_ADMIN only** · 只列 `PUBLISHED` · **命名响应模型** · 响应只给 summary |
| 10 | 模板是否必选 | **必选** ⇒ ⇒ ⇒ **seed 是硬前置**（W-0）|
| 11 | 向导第 4 步形态 | **深链现有 `BeddPage`** ⇒ ⇒ **不抽 `BeddForm`** ⇒ ⇒ SPEC 的「BEDD 录入」改成确认步的「去项目录 BEDD」入口 |
| 12 | 应用模板的入口 | **新端点** `POST /projects/{id}/apply-template`（同事务 · 幂等）⇒ ⇒ **不动** `POST /projects` 的语义 |
| 13 | 🆕 **seed 的模板范围**（互斥 ⇒ 单条填不满 7 段）| **种 2 条**：模板 A（`signature_matrix` 型）/ 模板 B（`record_approval` 型）⇒ ⇒ 7 段**集合层面**全覆盖 + 互斥遵守 |
| 14 | 🆕 **向导的角色门** | **`/wizard` 挪进 admin 组**（与 `/admin/projects` 同口径）⇒ ⇒ 非 SYSTEM_ADMIN 看不到入口 ⇒ ⇒ **TODO-205 关闭** |
| 15 | 🆕 **中间态处置**（第 2/3 步失败）| **保留已建项目**（不拆 · 不引入删除能力）+ 留在向导 + 明确告知「项目已创建（编号 X），但第 N 步未完成」+ 两个出口（去项目页继续 / 留在本页重试）⇒ ⇒ **向导不可重入** |
| 16 | 🆕 **弃单残留** | **给项目加 DRAFT 态**：第 1 步落 `DRAFT` · 第 4 步转 `ACTIVE` ⇒ ⇒ 弃单 = **可识别的 DRAFT 项目** ⇒ ⇒ **兑现 SPEC §12.4 V1.6 的旧承诺** ⇒ ⇒ ⇒ `projects.status` 今天无人读 ⇒ ⇒ ⇒ 行为影响几乎为零 ⇒ ⇒ ⇒ **TODO-204 降级**（不再需要清理脚本，只需按 `status='DRAFT'` 识别）|

---

## 十、评审与 hermes 改掉的**实质内容**

| # | 评审发现 | 处置 |
|---|---|---|
| 1 | 🔴 **向导第 3 步没有「把模板应用到项目」的入口** ⇒ ⇒ 本批**核心写路径完全没被指定**（`create_from_template` 只是个不存在的 docstring）| **W-3d** 新端点 |
| 2 | 🔴 **「只列已发布」没有定义**（`status` 默认 `"ACTIVE"`、无发布端点、无写者、两库 0 行）| **W-3b** 词表化 3 值 |
| 3 | 🔴 **`record_approval` 与 `signature_matrix` 互斥**（schema docstring 明写）| C-4 ⇒ **422** + **seed 种 2 条**（裁 13）|
| 4 | 🔴 **`ensure_default_record_matrix` 明写「不覆盖人工绑定」** ⇒ ⇒ W-3b 的「替换」违反既有不变量 | W-3c 改绑**条件化** |
| 5 | 🔴 **向导 happy path 在当前环境跑不起来**（唯一 FORMAL 工作区已被占用 ⇒ 工作区下拉恒空）⇒ ⇒ 且 e2e 跑一次就吃掉 seed 工作区 ⇒ ⇒ 第二次 409 | **W-0** 加备用工作区 · e2e 幂等 · W-14 降级为「不做专用 spec」|
| 6 | ⚠️ **5 元组打破两处生产解包**（`bedd.py:150` · `ui_schema_service.py:56`）⇒ ⇒ import 期崩 | W-1 明列 |
| 7 | ⚠️ **`UiSchemaField(**f)` 静默丢弃 `unit_display`**（pydantic `extra='ignore'`）⇒ ⇒ 症状 = 永远标灰、无报错 | **W-1b** |
| 8 | ⚠️ **验收例子算错**：`14.5 psi × 6.89476 = 99.97 kPa`（不是 100）| §四·4.3 + §六 加容差 |
| 9 | ⚠️ **US 模式下标签仍写 canonical 单位**（`SchemaForm.tsx:225-233` 渲染 `/ {f.unit}`）| W-4 用 `unit_display.display_unit` |
| 10 | ⚠️ **「标灰」语义歧义**（灰 = 禁用 ⇒ 用户填不了湿度）| 裁 6：**灰 = 不换算、按原值显示** |
| 11 | ⚠️ **写路径若对全部字段换算 ⇒ 未编辑字段末位比特漂移** | W-5：canonical 保持在 state |
| 12 | ⚠️ **「后端新增单位不可能不带因子」是约定不是类型**（`_FIELDS` 是手写 dict）| **W-19** 兵底 + 测试 |
| 13 | ⚠️ **裸字段棘轮正好 71** ⇒ ⇒ 新端点**必须命名响应模型** ⇒ ⇒ **照抄 `pipe_codes.py:131`（无 `response_model`）会推爆棘轮** | W-3 |
| 14 | ⚠️ **`projectScope` store 每会话只拉一次** ⇒ ⇒ 建完项目顶栏看不到它 | **W-16** |
| 15 | ⚠️ **模板应用 / 矩阵改绑零审计**（改变「谁该签」的治理动作）| **W-17** 本批写一条审计 |
| 16 | ⚠️ **mock 的 `POST /projects` 不强制枚举** ⇒ ⇒ dev 与 prod 漂移 | **W-18** |
| 17 | ⚠️ **「弃单残留是建项目本身的固有后果」这句逻辑是错的**（改成第 4 步建则碎屑为 0 ⇒ ⇒ 早期建项目**就是**碎屑的成因）| §四·4.1 已改写 + **DRAFT 态收口**（裁 16）|
| 18 | ⚠️ **seed 范围被低估**：一条全 7 段模板要**命名 SignatureMatrix + PipeCodeTemplate + `project_template_pipe_classes` 行** ⇒ ⇒ 且**互斥让「一条填满」不可能** ⇒ ⇒ ⇒ ⇒ **2 条** | W-0 已展开（裁 13）|
| 19 | ⚠️ **`ProjectCreateForm` 的「已自动绑定记录级签署矩阵」提示在第 3 步后变假** | 坑 16 |
| 20 | ⚠️ **`unit_system` 没有冻结下游值**（不像 `product_category` 有 `projects.py:341-357` 的锁）⇒ ⇒ ⇒ **新 PATCH 不要抄 422 保护** | W-2b |
| 21 | ⚠️ **SPEC §7.10.6 实为 12 项**（不是 10）· 其中 9 项有对应、**3 项没有**（默认单位制 / 默认模块 / BEDD 默认结构）⇒ ⇒ 那 3 项要补就得**模板选择前置** ⇒ ⇒ 与「项目先建」**冲突** ⇒ ⇒ ⇒ **登记关系、不补实现** | W-7 |
| 22 | ⚠️ **psychro 的 `METRIC/IMPERIAL` 与 `SI/US` 同义不同拼** | **W-20**（docstring 点名 + §12.4 登记）|

---

## 十一、未解决（**已全部收口**）

| 原未决项 | 结论 |
|---|---|
| 1. **seed 的内容与范围**（互斥 ⇒ 一条填不满 7 段）| ✅ **种 2 条模板**（裁 13）· A（signature_matrix 型）/ B（record_approval 型）· `asset_id` 本批**留空**（`config_assets.asset_subtype` 无 `PROJECT_TEMPLATE` 取值）|
| 2. **4 段的物理形状**（4 张表 vs 4 组列）| ✅ **`projects` 表 + 6 个具体列**（`max_depth` int · `proxy_allowed` bool · `attachment_required` bool · `skip_alpha_versions` bool · `allowed_purposes` list · `reversal_approver_role` str）⇒ ⇒ 免 JOIN、免外键、迁移就是 `ADD COLUMN` ×6 ⇒ ⇒ **不建 JSONB blob**（6 个都是标量）|
| 3. **向导的角色门** | ✅ **`/wizard` 挪进 admin 组**（裁 14）⇒ ⇒ **TODO-205 关闭** |
| 4. **弃单清理** | ✅ **给项目加 DRAFT 态**（裁 16）⇒ ⇒ 弃单 = 可识别的 DRAFT 项目 ⇒ ⇒ **不需要清理脚本**（运维按 `status='DRAFT'` 一句）⇒ ⇒ **TODO-204 降级** |
| 5. **中间态处置** | ✅ **保留已建项目 + 留在向导 + 明确提示 + 两个出口**（裁 15）⇒ ⇒ **不引入删除能力** |
| 6. **与 P10-J-T1 的耦合** | ✅ **串行** ⇒ ⇒ ⚠️ **P10-J 先落地会先占一个 SPEC 版本号** ⇒ ⇒ 本批的版本号要重算 |
| 7. **SPEC §7.10.6 的 12 项** | ✅ **登记对应关系，不补实现**（3 项没有的都要「模板选择前置」⇒ 与顺序冲突）⇒ ⇒ 登记进 §12.4 |
| 8. **psychro 的 `METRIC/IMPERIAL`** | ✅ **本批不动**（其 docstring 明写「不影响算法，仅标注」）⇒ ⇒ **W-20** 在 `UnitSystem` docstring 点名 + §12.4 登记 |
| 9. **模板发布的运营流程** | ✅ **本批边界 = 只有 seed 写 `PUBLISHED`**（无发布端点、无审批、无版本序列）⇒ ⇒ ⇒ **另开**（**TODO-206**）|

⇒ ⇒ ⇒ **没有一条留在「未定」** ⇒ ⇒ ⇒ 本批**只差「批准」**这一个闸门。

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 20 | ISSUES_OPEN | 23 issues（主审）· 2 critical gap |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE VOICE:** hermes（**GLM-5.2** · zai）· 计划文本 + 仓库只读 · 跨模型对抗 · **5 条 P1 + 5 条 P2**，其中 **3 条 P1 是主审漏掉的**
- **CROSS-MODEL:** 13 处张力已由人裁收敛 —— ① 向导第 4 步 ⇒ ⇒ **深链**（不抽 `BeddForm`）② 4 段载体 ⇒ ⇒ **typed 列**（否决 hermes 的 provenance-only）③ 应用模板入口 ⇒ ⇒ **新端点** ④ 标灰语义 ⇒ ⇒ **不换算按原值显示** ⑤ seed ⇒ ⇒ **种 2 条** ⑥ 角色门 ⇒ ⇒ **挪 admin 组** ⑦ 中间态 ⇒ ⇒ **保留 + 提示** ⑧ 弃单 ⇒ ⇒ **DRAFT 态** ⑨ 「已发布」定义 ⑩ 互斥 ⇒ ⇒ 422 ⑪ 改绑条件化 ⑫ 备用工作区 seed ⑬ 审计决定<br>⇒ ⇒ ⇒ **hermes 的「范围过大（三个批穿一件）」判断未采纳**（人裁「一批做完」）⇒ ⇒ ⇒ **但采纳了它指出的每一处缺口**
- **UNRESOLVED:** 0（§十一 全部收口）
- **VERDICT:** eng review 有未决项 ⇒ ⇒ **eng review required**（本计划**未获批**）

⚠️ **本次评审改了计划的 22 处实质内容**（§十）：**加了 11 个原计划没有的任务**（W-0 扩成三样 + 2 条模板 · W-1b 契约类加字段 · W-2c 项目状态枚举 · W-2d 激活端点 · W-3b 发布语义 · W-3c 落库分工 · **W-3d 应用模板端点** · W-5 换算 · W-16 store 刷新 · W-17 审计 · W-18 mock 枚举 · W-19 缺因子兵底 · W-20 psychro 点名）· 纠正 4 个错前提（SPEC 9 组 · 第 7 段 `reversal_role` · `unit` 已填且已渲染 · 7 段互斥）· **向导从 5 步改 4 步且深链 BeddPage**（不抽组件）· **加项目 DRAFT 态**（兑现 SPEC §12.4 V1.6 的旧承诺）· 换算语义重写 + 验收例子改对（99.97 不是 100）· 补「什么已存在」13 条。
---

## 十二、落地记录（2026-11-25）

| 任务 | 落地位置 | 备注 |
|---|---|---|
| **W-0** | `pcs-backend/scripts/seed_project_templates.py`（**幂等**）· 前端 mock `ws-formal-004` | 种 **2 条**已发布模板（签署矩阵型 / 审批深度型）+ 命名签署矩阵 + 管号模板 + 默认等级关联 + **一个未占用的 FORMAL 工作区** |
| **W-1 / W-1b** | `app/schemas/bedd.py`（**5 元组**）· `app/services/ui_schema_service.py` · `app/api/v1/meta.py`（`UnitDisplay`）· **新** `app/services/unit_conversion.py` | ⚠️ **两处生产解包同步改**（不加就 import 期崩）· ⚠️ **单位从标签里删掉**（防双单位）|
| **W-2 / W-2c** | `app/models/enums.py`（`UnitSystem` / `ProjectStatus`）· `app/models/project.py`（**两条 CHECK**）· `alembic/versions/p10_006_project_wizard_fields.py` | ⚠️ **加 CHECK 前两库各取证**（全 `SI` / 全 `ACTIVE` ⇒ 安全）|
| **W-2b / W-2d** | `app/schemas/project.py` · `app/api/v1/projects.py`（两个 PATCH）· `ProjectOut` 加两字段 | ⚠️ **不抄** `product_category` 的 422 保护（那是因为冻结下游值）|
| **W-3 / W-3b** | **新** `app/api/v1/project_templates.py` · `app/models/config_domain.py`（`ProjectTemplateStatus` + CHECK）| ⚠️ **命名响应模型**（裸字段基线**已顶满 71**）· 只列 `PUBLISHED` · **无 N+1** |
| **W-3c / W-3d** | `app/services/project_template_service.py`（`apply_to_project` + 4 个分步实现）· `projects` 表 **7 列** | ⚠️ **同一事务**（任一段失败 ⇒ 全回滚）· **幂等** · ⚠️ **`record_approval` 只替自动绑的默认**（**不夺人工绑定**）|
| **W-3e** | `src/components/ProjectCreateForm.tsx` | 工作区下拉**过滤掉已挂项目的工作区** |
| **W-4 / W-5 / W-19** | **新** `src/pages/bedd/UnitSystemSwitch.tsx` · **新** `src/utils/units.ts` · `src/components/common/SchemaForm.tsx` | ⚠️ **换算只在控件边界**（`getValueProps` / `normalize`）⇒ form state 恒 canonical |
| **W-6 / W-6c / W-16** | `src/pages/wizard/ProjectWizardPage.tsx`（**整文件重写**）· `src/components/ProjectCreateForm.tsx`（**新**）· `src/store/projectScope.ts`（`refresh()`）· `src/layouts/MainLayout.tsx` | ⚠️ `/wizard` **挪进 admin 组** · ⚠️ 中间态**保留项目 + 两个出口** |
| **W-7 / W-20** | `docs/PCS-UI-SPEC.md` **§7.5**（改 4 步 + 换算口径）· **§7.10.6**（12 项对应关系）· **§12.4 V2.21**（文件头 V2.20 ⇒ **V2.21**）· `app/models/enums.py`（`UnitSystem` docstring 点名 psychro）| |
| **W-8 / W-10 / W-11 / W-13 / W-18** | 后端 12 + PG 1 · 前端 9 + 9 + 2 + 1 · `tests/mocks/bedd_ui_schema_drift.test.ts` · `src/mocks/seed/pms.ts` · `src/mocks/handlers.ts` · `src/mocks/signFlow.ts` · `src/mocks/seed/projects.ts` · `src/mocks/seed/workspaces.ts` | |
| **W-14 / W-15** | `e2e/real_backend_route_sweep.spec.ts`（`/wizard` 进 ROUTES）· `tests/pages/wizard/ProjectWizardPage.test.tsx`（**整文件重写**）| |
| **W-17** | `AuditAction.PROJECT_TEMPLATE_APPLIED` + 端点写一条审计 | |

**车道**（2026-11-25 实测）：后端默认 **6184 passed**（+12）· PG **48 passed**（+1）·
前端 typecheck / lint clean · 前端 **1146 passed**（+7）· `alembic check` 两库各一进程 exit 0 ·
裸载荷棘轮 **71 未涨** · 浏览器回归（向导 4 步全通 + BEDD 单位制换算 8/10/35）⇒ ⇒ ⇒ **CRITICAL/HIGH 0 条**。

⇒ ⇒ ⇒ **QA 报告**：`.gstack/qa-reports/qa-report-pcs-frontend-2026-11-25-p10k.md`
