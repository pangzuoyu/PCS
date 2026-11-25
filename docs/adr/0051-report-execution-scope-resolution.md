# ADR-0051：报表执行的项目作用域解析 —— 公司级模板「执行时选项目」

- Status: **accepted**（2026-11-25 · 人裁「approve」· 计划
  `docs/superpowers/plans/2026-11-24-p10-j-t1-company-template-execute.md`）
- Date: 2026-11-25
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/api/v1/report_builder.py`、`app/services/report/builder_service.py`、
  `app/services/report/definition_service.py`、`app/services/report/datasource_registry.py`、
  `app/services/user_project_service.py`、`app/models/report.py`、
  `app/workers/report_builder_tasks.py`
- Informed: 前端执行面板（`src/pages/report/ReportExecutePage.tsx`）、部署与运维
- Supersedes: —
- Superseded by: —
- Related: SPEC §7.18.2（本次同步登记）、§12.4 `V2.20`、
  `TODOS.md` TODO-177（公司级模板执行）、TODO-174（跨项目读 · P10-F）、
  ADR-0046（用户身份模型迁移）
- 状态说明：本 ADR 的「实测」断言于 2026-11-25 在本仓代码与**开发库 `pcs`**
  上复核过；复核命令见文末「附录 A」。

---

## 背景

`report_definitions.project_id` **可空** ⇒ ⇒ **`NULL` = 公司级模板**
⇒ ⇒ ⇒ 公司级模板**不绑定任何项目** ⇒ ⇒ ⇒ 它对谁可见、能导出什么数据，
此前**没有定义**。

执行链路上有**五个位置**各自读 `row.project_id`，它们合起来产生了三个
不可接受的后果。

### ① 公司级模板**永远跑不通** —— 且失败发生在 worker 里

`app/services/report/builder_service.py:179-185`（改前）：

```python
scope = project_id or row.project_id
if scope is None:
    raise PcsError(... code="REPORT_PROJECT_SCOPE_REQUIRED", status=400)
```

而 `POST /report-builder/definitions/{def_id}/execute` 的 body
（`ReportExecuteRequest`）**没有 `project_id` 字段** ⇒ ⇒ ⇒ 请求端**没有任何
办法**指定项目 ⇒ ⇒ ⇒ 公司级模板 ⇒ ⇒ **scope 恒为 `None`** ⇒ ⇒ ⇒ 恒 400。

⇒ ⇒ ⇒ 且这个 400 发生在 **ARQ worker 里** ⇒ ⇒ ⇒ 用户看到的是
「202 已提交 → 轮询 → 执行失败」⇒ ⇒ ⇒ 真正的原因（没选项目）在提交那一刻
**根本不可达**。

### ② 公司级模板的产出**没有归属**

`app/api/v1/report_builder.py:572`（快照）与 `:591`（入队）都是
`str(row.project_id or "")` ⇒ ⇒ ⇒ 公司级 ⇒ ⇒ **恒空串** ⇒ ⇒ ⇒
`app/workers/report_builder_tasks.py:79` 的
`pid = uuid.UUID(project_id) if project_id else None` ⇒ ⇒ ⇒
`report_files.project_id` 落 **NULL** ⇒ ⇒ ⇒ **产出文件不属于任何项目**
⇒ ⇒ ⇒ 事后没人能说清这份报表是哪个项目的。

### ③ 「不带项目过滤」是**静默的全库扫描**

`builder_service.py` 把项目过滤拼进用户可编辑的 `FilterConditions` 组里
（`:227-235`）⇒ ⇒ ⇒ 项目过滤是**越权边界**，不是「用户条件的一部分」
⇒ ⇒ ⇒ 一旦解析不到项目就放行 ⇒ ⇒ ⇒ 执行**不带任何项目条件**
⇒ ⇒ ⇒ 报表 200、行数正常、列也齐 ⇒ ⇒ ⇒ **只是混了别的项目的数据**
⇒ ⇒ ⇒ 这比报错严重得多 —— **报错会让人停下，串数据不会**。

⇒ ⇒ ⇒ 所以「解析不到项目」必须**拒绝执行**，不能「那就不筛吧」。

### ④ 合同缺口：请求体**没有** `project_id`

`ReportExecuteRequest`（`app/api/v1/report_builder.py:419`）**没有**
`project_id` ⇒ ⇒ ⇒ 「执行时选项目」这条路**今天物理上不存在**
⇒ ⇒ ⇒ 这是**契约**问题，不是 UI 问题。

---

## 决策

### D1 · scope 在**端点**一处解析（service 不改）

**执行的 scope = 定义自带项目 ∨（公司级 ⇒ 请求指定的项目）**。

规则**只落在端点一处**（`app/api/v1/report_builder.py`）⇒ ⇒ ⇒
`builder_service.execute_definition()` 里那句
`project_id or row.project_id` **原样不动**。

理由：

- MISMATCH 400 在**端点**拦 ⇒ ⇒ ⇒ worker 收到的**永远是已解析且一致**的
  scope ⇒ ⇒ ⇒ service 里那个顺序在**每条可达路径上都是死代码**
  ⇒ ⇒ ⇒ 一条不变量两种机制 = 未来的漂移种子；
- 既有测试**没有一条**会传冲突的 `project_id`（该字段此前不存在）
  ⇒ ⇒ ⇒ 改 service 等于没测、还动了别人依赖的行为；
- service 是**纯执行引擎**（`execute_definition()` 不知道自己被谁调用）
  ⇒ ⇒ ⇒ 把它挪到端点，engine 那一层**职责更干净**。

### D2 · 判定顺序（**不得重排既有行为**）

| # | 判定 | 结果 |
|---|---|---|
| 1 | 定义不可见 | **404** `REPORT_DEFINITION_NOT_FOUND` |
| 2 | `row.project_id is not None` ⇒ 对**定义自带项目**做授权判定 | **404** `PROJECT_NOT_FOUND` |
| 3 | `row.status != "PUBLISHED"` | **409** `REPORT_DEFINITION_STATE` |
| 4 | **MISMATCH**：请求项目 ≠ 定义自带项目 | **400** `REPORT_PROJECT_SCOPE_MISMATCH` |
| 5 | **SCOPE**：解析出的 scope 仍为 `None` | **400** `REPORT_PROJECT_SCOPE_REQUIRED` |
| 6 | 公司级 + 请求带了项目 ⇒ 对**该项目**做授权判定 | **404** `PROJECT_NOT_FOUND` |

⚠ **1→2→3 必须在 4→5→6 之前**：今天「项目级 + 授权被撤 + 定义未发布」返回
**404**（第 2 步）⇒ ⇒ ⇒ 若把 409 提到前面就变成 409 ⇒ ⇒ ⇒ **一次未被声明的
行为变更**。

⚠ **第 6 步放最后**：公司级定义今天**根本不做**授权判定（`:526` 的 `if`
会跳过）⇒ ⇒ ⇒ 新增它**不重排**任何既有行为。

### D3 · 「谁能对哪个项目执行公司级模板」= **对该项目有访问权**

公司级模板**对所有登录用户可见**（`visible_clause`：`PUBLISHED` ∧
`ALL_USERS` ∧ `project_id IS NULL`）⇒ ⇒ ⇒ 「看得见」≠「能执行」⇒ ⇒ ⇒
**看得见的是模板，授权判的是数据**。

⇒ ⇒ ⇒ 执行公司级模板时，**必须**对**解析出的 scope 项目**做
`require_project_access_or_404` ⇒ ⇒ ⇒ 无权 ⇒ ⇒ **404**（与「不存在」
**逐字同形** ⇒ ⇒ ⇒ 项目 id 枚举不出来）。

⇒ ⇒ ⇒ **SYSTEM_ADMIN 不豁免这条**：admin 靠 `require_project_access_or_404`
内部的**全局 bypass**放行（`app/services/user_project_service.py`）⇒ ⇒ ⇒
规则**一条**，不按角色分叉。

⇒ ⇒ ⇒ **候选列表**按角色分，是因为**候选来源**不同（admin 通常**没有授权行**
⇒ ⇒ ⇒ 只用授权行 ⇒ ⇒ ⇒ admin 的列表会是空的）⇒ ⇒ ⇒ **不是**因为判定口径
不同。

### D4 · 无权 ⇒ **404** 而不是 403

与技术决定一致（见 §一 人裁 ②）：**无权与不存在同形** ⇒ ⇒ ⇒ 不泄露项目
存在性 ⇒ ⇒ ⇒ 沿用**服务层**那份守卫（`code="PROJECT_NOT_FOUND"`）⇒ ⇒ ⇒
**不换**端点层那份（`app/api/v1/_guard.py`）—— 那会动 21+ 端点的错误信封。

### D5 · 不一致 ⇒ **400 拒绝**，不静默忽略

请求带了项目、而定义自带另一个项目 ⇒ ⇒ ⇒ **400**
`REPORT_PROJECT_SCOPE_MISMATCH` ⇒ ⇒ ⇒ 不「以定义自带项目为准」⇒ ⇒ ⇒
**显式 > 隐式**（静默忽略 = 用户以为跑的是 A、其实跑的是 B）。

### D6 · 「主数据源没有项目列」在**建定义时**拒

`DATALINEAGE` / `SUPPLIERS` / `CONFIG_ASSETS` 这 3 个源**没有 `project_id`
列** ⇒ ⇒ ⇒ 选了项目也**无法按项目隔离** ⇒ ⇒ ⇒ 那是「批量生产永远跑不
了的死路」⇒ ⇒ ⇒ 在**源头**拦住：建/改定义时，公司级 + 主源是那 3 个 ⇒ ⇒
**400** `REPORT_DATASOURCE_NOT_PROJECT_SCOPED`。

⚠ **执行侧用**同一个错误码（不是 `REPORT_PROJECT_SCOPE_REQUIRED`）⇒ ⇒ ⇒
因为「没选项目」和「选了也没用」是**两件事**⇒ ⇒ ⇒ 用户必须能区分 ⇒ ⇒ ⇒
（实测：`pcs` 库里 8 条公司级定义，主源全是 `HEAT_RESULTS`/`EQUIP_LIST`
⇒ ⇒ ⇒ **都有 `project_id` 列** ⇒ ⇒ ⇒ 零存量、零迁移、零清理。）

### D7 · 契约是**增量**：`ReportExecuteRequest` 加**可选** `project_id`

⚠ 它是「**这次执行的目标项目**」⇒ ⇒ ⇒ **不是**「重新挂载定义」
⇒ ⇒ ⇒ 定义本身的归属**不变** ⇒ ⇒ ⇒ 一份公司级模板仍可对多个项目执行
⇒ ⇒ ⇒ 但**每次执行**产出的文件与日志**记着**那个项目（快照与入队都传
**解析后的 scope** ⇒ ⇒ ⇒ `report_files.project_id` 不再落 NULL）。

---

## 被否决的替代方案

| 方案 | 为什么否决 |
|---|---|
| **默认用顶栏当前项目** | 人裁「**必选、无默认**」⇒ ⇒ ⇒ 少一层「以为跑的是 A 其实是 B」的推断 ⇒ ⇒ ⇒ 且强制用户**看一眼**这次跑的是哪个项目 |
| **默认用定义可见范围内的第一个项目** | 同上 ⇒ ⇒ ⇒ 且「第一个」是**任意的** ⇒ ⇒ ⇒ 不可预期 |
| **二次确认弹窗** | 人裁「**不要**」⇒ ⇒ ⇒ 项目在选择器里**看得见** ⇒ ⇒ ⇒ 多一步操作换不到额外保证 |
| **无权 ⇒ 403** | 403 **区别于** 404 ⇒ ⇒ ⇒ 泄露「项目存在但你没权」⇒ ⇒ ⇒ 项目 id 枚举 ⇒ ⇒ ⇒ 沿用仓库既有口径（**逐字同形**）|
| **不一致 ⇒ 以定义自带项目为准** | 静默忽略 ⇒ ⇒ ⇒ 用户以为跑的是 A、其实跑的是 B ⇒ ⇒ ⇒ 与本 ADR 要消灭的正是同一类事故 |
| **在 service 里解析 scope** | 一条不变量两种机制 ⇒ ⇒ ⇒ 漂移种子（见 D1）|
| **改用端点层守卫（`_guard.py`）** | 会动 21+ 端点的错误信封 ⇒ ⇒ ⇒ 属另一批 |
| **公司级模板改成「项目级模板 + 复制一份」** | 模板会**倍增** ⇒ ⇒ ⇒ 且改模板要改 N 份 ⇒ ⇒ ⇒ 与「模板」这个概念的初衷相反 |

---

## 后果

**正面**

- 公司级模板**第一次真的能跑**（2026-11-25 实测：带项目执行 ⇒ 202 ⇒
  `report_files.project_id` = 所选项目）；
- 「没选项目」从 **worker 里的 400** 提前到 **端点的 400** ⇒ ⇒ ⇒ 不再留一行
  永远 `QUEUED` 的执行日志等 15 分钟回收器；
- 产出文件**有归属** ⇒ ⇒ ⇒ 事后可追溯；
- 定义下拉标出作用域 ⇒ ⇒ ⇒ 用户在**选中之前**就知道要不要多选一个项目。

**代价 / 欠账**

- **契约破坏性变更**（新增可选字段）⇒ ⇒ ⇒ 前端类型必须重生成
  （`npm run api:gen`）⇒ ⇒ ⇒ ⚠️ **CI 拦不住「新增可选字段」** ⇒ ⇒ ⇒
  必须手工验 `npm run api:check`；
- 前端多一条**候选来源**（`GET /user-projects/me` ∪ `GET /workspaces`）
  ⇒ ⇒ ⇒ 普通用户与 admin 各走一条腿；
- `DATALINEAGE` / `SUPPLIERS` / `CONFIG_ASSETS` 这 3 个源**不能做公司级模板**
  ⇒ ⇒ ⇒ 若将来有「用这 3 个源做公司级模板」的需求 ⇒ ⇒ ⇒ 需要的是**给它
  加项目列**（那是一次迁移）⇒ ⇒ ⇒ 不是本 ADR 要解决的事。

---

## 附录 A · 复核命令（2026-11-25）

```bash
# ① 公司级定义的存量（主源是否有 project_id 列）
#    ⇒ pcs 库 8 条，主源全是 HEAT_RESULTS / EQUIP_LIST ⇒ 都有项目列 ⇒ 零存量
# ② 「有没有项目列」不能看注册表的 fields ⇒ 那是**导入时**算的
#    ⇒ 导入顺序一变就全错 ⇒ 改用 ORM 直查（datasource_registry
#    .source_supports_project_scope() 就是这么写的）
# ③ 约束真的在吗（PG 车道）：直连 ORM 插两条同名公司级定义
#    ⇒ 走 API 建会先被应用层 409 ⇒ ⇒ ⇒ 那是**假证据**
```

---

## 相关文件

- 端点：`pcs-backend/app/api/v1/report_builder.py`
- 执行引擎：`pcs-backend/app/services/report/builder_service.py`
- 定义服务：`pcs-backend/app/services/report/definition_service.py`
- 数据源注册表：`pcs-backend/app/services/report/datasource_registry.py`
- 授权守卫：`pcs-backend/app/services/user_project_service.py`
- 前端：`pcs-frontend/src/pages/report/ReportExecutePage.tsx`、
  `pcs-frontend/src/api/projects.ts`
- 规格：`docs/PCS-UI-SPEC.md` §7.18.2 · §12.4 `V2.20`
- 计划：`docs/superpowers/plans/2026-11-24-p10-j-t1-company-template-execute.md`
