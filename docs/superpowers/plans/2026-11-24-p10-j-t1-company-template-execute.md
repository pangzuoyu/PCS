# P10-J-T1 · 公司级模板「执行时选项目」 —— 计划

> **来源**：`TODOS.md` · `TODO-177`（P10-J · T1）
> **人裁**：2026-11-23（见 `2026-11-23-p10-j-feature-backlog.md` §P10-J-T1）
> **性质**：**新功能**（**滚 OpenAPI 契约**）

---

## 一、人裁（2026-11-23 · 同意建议）

| 问 | 裁决 |
|---|---|
| ① 公司级模板该不该可执行 | **「公司级模板＝模板，执行时**必须**选项目」** ⇒ ⇒ 做成 **UI 流程** |
| ② 指定的项目若无权 | **404**（与「不存在」同形 · 技术决定）|

**SPEC 条款草案**（随本批登记）：

> **执行**：公司级模板（`project_id IS NULL`）**执行时必须选项目**；
> **执行的 scope = 定义自带项目 ∧ 请求指定项目**（不一致 ⇒ ⇒ **以定义自带项目为准**）；
> 项目级模板**忽略**请求里的项目。

---

## 二、现状（**为什么公司级模板永远跑不通**）

| 位置 | 现状 | 后果 |
|---|---|---|
| `builder_service.py:179` | `scope = project_id or row.project_id` | **请求优先** ⇒ ⇒ 定义绑 B、执行取 A 的数据 ⇒ ⇒ **静默语义事故** |
| `report_builder.py:591`（入队） | `project_id=str(row.project_id or "")` | 公司级 ⇒ ⇒ **恒空串** |
| `report_builder_tasks.py:79` | `pid = uuid.UUID(project_id) if project_id else None` | ⇒ ⇒ `report_files.project_id` 落 **NULL**（产出文件无归属）|
| `builder_service.py:180` | `scope is None` ⇒ ⇒ **400** | ⇒ ⇒ **公司级模板永远 400**，且发生在 **worker 里** ⇒ ⇒ 用户看到「202 已提交 → 执行失败」|

⚠️ **契约缺口**：`ReportExecuteRequest` **没有** `project_id` 字段
⇒ ⇒ **没有任何入口能传项目 id** ⇒ ⇒ 「执行时选项目」这条路**今天物理上不存在**。

---

## 三、任务清单

| # | 内容 | 文件 | 状态 |
|---|---|---|---|
| **T1-1** | 契约：`ReportExecuteRequest` **加 `project_id`** ⇒ ⇒ 滚 openapi + `api.d.ts` + snapshot | `app/api/v1/report_builder.py` | ⬜ |
| **T1-2** | service **scope 顺序倒置**：`scope = row.project_id or project_id` ⇒ ⇒ 仍 `None` ⇒ ⇒ 400 `REPORT_PROJECT_SCOPE_REQUIRED` | `app/services/report/builder_service.py` | ⬜ |
| **T1-3** | 端点：**先解析 scope** ⇒ ⇒ `require_project_access_or_404`（**服务层那份** ⇒ `code="PROJECT_NOT_FOUND"`）⇒ ⇒ 无权 ⇒ ⇒ **404** | `app/api/v1/report_builder.py` | ⬜ |
| **T1-4** | **入队与快照传「解析后的 scope」**（不是 `row.project_id`）⇒ ⇒ 产出文件有项目归属 | 端点 + `report_builder_tasks.py` | ⬜ |
| **T1-5** | 前端：执行页 —— 选中**公司级**定义时给「**选项目**」入口（`useProjectScope`）⇒ ⇒ 项目级**不出现** | `src/pages/report/ReportExecutePage.tsx` | ⬜ |
| **T1-6** | **SPEC §7.18 补条款** + §12.4 修订登记 + 断言（默认车道 + **PG 车道**）| `docs/PCS-UI-SPEC.md` · `tests/` | ⬜ |

---

## 四、口径

| 场景 | scope | 结果 |
|---|---|---|
| 项目级定义 + 请求**不带**项目 | 定义自带项目 | ✅ |
| 项目级定义 + 请求**带**别的项目 | **定义自带项目**（请求被忽略）| ✅ |
| 公司级模板 + 请求带**有权**的项目 | 请求指定的项目 | ✅ 跑通 |
| 公司级模板 + 请求带**无权**的项目 | —— | **404** `PROJECT_NOT_FOUND` |
| 公司级模板 + 请求**不带**项目 | —— | **400** `REPORT_PROJECT_SCOPE_REQUIRED` |

---

## 五、预判的坑

| # | 坑 | 对策 |
|---|---|---|
| 1 | ⚠️ **scope 顺序倒置被当「风格」省掉** | 现状就是 `project_id or row.project_id`（**请求优先**）⇒ ⇒ 定义叫 B、出来的是 A 的数据 ⇒ ⇒ ⇒ 倒置是**规范依据**（SPEC 条款明写），不是实现细节 |
| 2 | ⚠️ **入队仍传 `row.project_id`** ⇒ ⇒ 产出文件 `project_id` 落 NULL | 入队与快照都传**解析后的 scope** |
| 3 | ⚠️ **404 用了 API 层那份**（`HTTPException` ⇒ `code="HTTP_404"`）⇒ ⇒ **code 不同仍可枚举** | 只用**服务层**那份（`code="PROJECT_NOT_FOUND"`）⇒ ⇒ ⇒ 403 只留给「角色闸」|
| 4 | ⚠️ **项目级定义被请求覆盖** | 服务层 `scope = row.project_id or project_id`（**定义优先**）|
| 5 | ⚠️ **公司级语义（`project_id IS NULL`）在 SQLite 单测里不可验**（`postgresql_nulls_not_distinct=True` ⇒ SQLite 退化成普通 UNIQUE ⇒ ⇒ NULL 互不相等）| 「公司级模板」的新用例 ⇒ ⇒ **必须走 PG 车道**（`scripts/pytest_pg.sh`）⇒ ⇒ ⇒ 默认车道绿灯**对这一族没有证明力** |

---

## 六、验收

- [ ] 契约里 `ReportExecuteRequest` 有 `project_id`
- [ ] 「公司级模板 + 有权的项目」⇒ ⇒ 跑通（用例）
- [ ] 「公司级模板 + 无权的项目」⇒ ⇒ **404**（用例）
- [ ] 「项目级模板 + 请求带别的项目」⇒ ⇒ **仍是定义自带项目**（用例）
- [ ] 前端「执行报表」有「选项目」入口（**仅公司级模板出现**）
- [ ] PG 车道 exit 0（公司级那族用例真跑过）

---

## 七、未解决

- **执行页的「选项目」默认取哪儿**：顶栏 `useProjectScope().projectId` 作默认值？⇒ ⇒ 倾向 **是**（同一真相源）
- **公司级模板是否需要「执行前确认项目」二次确认弹窗** ⇒ ⇒ 倾向 **不要**（选了就能跑）
- ⚠️ **P10-J-T2 的「被退回」与本批无耦合** ⇒ ⇒ 可并行但**不并行改同一处契约**
