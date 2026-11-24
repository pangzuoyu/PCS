# P10-J-T2 · 「拒绝 / 打回」动作 —— 计划

> **来源**：`TODOS.md` · `TODO-197b`（P10-I · T1 留下的「审核者没有打回的路」）
> **人裁**：2026-11-24 · 四问全定（见下）
> **性质**：**新功能**（但**不动 9 态机** · **不加新状态**）

---

## 一、人裁（2026-11-24）

| 问 | 裁决 |
|---|---|
| ① 状态模型 | **退回 DRAFT + 「被退回」标记** ⇒ ⇒ **不新增 `REJECTED` 态** ⇒ ⇒ 9 态机一个字不改 |
| ② 谁可见 | **沿用现状 `visible_clause`**（创建人 ✓ · SYSTEM_ADMIN ✓ · 其余 ✘）⇒ ⇒ 可见性规则**不改** |
| ③ 能不能再编辑 | **能**（创建人改完再交审）|
| ④ 要不要通知创建人 | **要**（复用现有通知系统）|

---

## 二、形态（**一个标记 + 一次闭环**）

```
审核者：队列里看到草稿 ⇒ ⇒ 「打回」+ 填原因
                    ↓
        rejected_at / rejected_by / reject_reason 被置位
        （状态**不变** —— 仍是 DRAFT）
                    ↓
队列：**rejected_at IS NULL** 才在队列里 ⇒ ⇒ 被打回 ⇒ ⇒ **离开队列**
                    ↓
创建人：自己的列表里看到「被退回」+ 原因 ⇒ ⇒ 改稿
                    ↓
        update() ⇒ ⇒ **清掉三个标记** ⇒ ⇒ ⇒ 重新进队列
```

⇒ ⇒ ⇒ **「待审」（DRAFT 且没被打回）与「待改」（DRAFT 且被打回）是两个态**
⇒ ⇒ ⇒ 队列只装前者 ⇒ ⇒ ⇒ **不需要新状态**。

---

## 三、任务清单

| # | 内容 | 文件 | 状态 |
|---|---|---|---|
| **T2-1** | **3 个列** + 迁移（`p10_005`）⇒ ⇒ **ORM 与迁移逐列核对** | `app/models/report.py` · `alembic/versions/p10_005_*.py` | ✅ 两库各一次（独立进程）+ `check` exit 0 + 直查库 + 幂等自检 0 violations |
| **T2-2** | service `reject()` + `update()` **清标记** + `pending_review()` **排除被打回的** + `publish()` **拒绝**被打回的 | `app/services/report/definition_service.py` | ✅ |
| **T2-3** | 端点 `POST /definitions/{def_id}/reject` + **通知**（`notify` → commit → `publish`）| `app/api/v1/report_builder.py` | ✅ kind 复用 `STEP_RETURNED` |
| **T2-4** | 契约：`ReportDefinitionOut` **加 3 字段** ⇒ ⇒ 滚 openapi + `api.d.ts` + MSW | `app/schemas/report_builder.py` · `pcs-frontend/src/types/api.d.ts` | ✅ 纯增量 · `api:check` 一致 |
| **T2-5** | 前端：队列页「**打回**」+ 原因 Modal；定义列表「**被退回**」badge + 原因 | `pcs-frontend/src/pages/report/*` | ✅ |
| **T2-6** | **SPEC §7.18.1** 补条款 + §12.4 **V2.19** + 断言 | `docs/PCS-UI-SPEC.md` · `tests/` | ✅ 后端 13 · 前端 5 · 棘轮台账 +1 / MIN 172→184 |

---

## 四、口径（**照抄 `publish()` 的判定顺序**）

| # | 判定 | 错误码 | 状态码 |
|---|---|---|---|
| 1 | 定义不存在 | `REPORT_DEFINITION_NOT_FOUND` | 404 |
| 2 | **禁自审**（创建人自己不能打回自己的）| `REPORT_DEFINITION_SELF_REVIEW_FORBIDDEN` | 403 |
| 3 | 项目级 ⇒ 打回者要**对该项目有授权** | `REPORT_DEFINITION_NOT_FOUND`（**逐字同形**）| 404 |
| 4 | `CREATOR_ONLY` ⇒ 不能由他人打回 | `REPORT_DEFINITION_NOT_SHAREABLE` | 403 |
| 5 | 不是 `DRAFT` ⇒ 不能打回 | `REPORT_DEFINITION_STATE` / `..._OBSOLETE` | 409 |
| 6 | **已经打过回** ⇒ 不静默覆盖 | `REPORT_DEFINITION_ALREADY_REJECTED` | 409 |

⚠️ **角色闸**（`REVIEWER` / `APPROVER` / `SYSTEM_ADMIN`）在**端点层**（与 `publish` 同款）
⇒ ⇒ ⇒ 职责分离（禁自审 / 项目授权）在 **service 层** ⇒ ⇒ ⇒ 端点漏调也绕不过。

⚠️ **通知 kind 复用 `STEP_RETURNED`**（「退回」）⇒ ⇒ ⇒
**不新增 kind** ⇒ ⇒ ⇒ `NotificationKind` 的 **4 值裁决清单不动**（不必回 ADR-0049）。

⚠️ **不写 `audit_logs`** ⇒ ⇒ ⇒ 定义生命周期（create/update/publish/obsolete）**本来就不写**
⇒ ⇒ ⇒ **三个列 + 通知行**就是这次动作的痕迹 ⇒ ⇒ ⇒ 不动 `AuditAction` 的锁定清单。

---

## 五、验收

| 项 | 判据 |
|---|---|
| 默认车道 | `uv run pytest -q` 全绿（≥ 上批 baseline）|
| PG 车道 | `bash scripts/pytest_pg.sh` exit 0 |
| 前端 | `npm run typecheck` + `lint` + `test` 全绿 · `api:check` 一致 |
| 契约 | `openapi.json` **纯增量**（+ 3 字段 + 1 端点）|
| 断言 | service 层 6 条 + 端点层（`strict_client`）4 条 + 前端 3 条 |

---

## 六、预判的坑

| # | 坑 | 对策 |
|---|---|---|
| 1 | ⚠️ **改迁移 ⇒ ⇒ ORM 漂移**（单测照绿 · 真库会炸）| 逐列核对 + 两库各跑一次 `alembic check` |
| 2 | ⚠️ **打完回它还在队列里**（仍是 DRAFT）| 队列口径加 `rejected_at IS NULL` ⇒ ⇒ ⇒ **队列与可见性两套口径不许混** |
| 3 | ⚠️ **通知在 commit 前推** ⇒ ⇒ phantom notification | `notify` → `commit` → `publish`（ADR-0049 §① 的形状）|
| 4 | ⚠️ 打完回**标记永不消失** ⇒ ⇒ 创建人改完还显示「被退回」| `update()` 里**清三个标记** |
| 5 | ⚠️ **契约加字段 ⇒ ⇒ 前端类型要重生成** | `export_openapi.py` + `npm run api:gen` + `api:check` |

---

## 七、未解决

- **「被退回」的定义在创建人列表里怎么显示**：badge + Tooltip 原因 ⇒ ⇒ 形态随实现定
- **审核者能否看到「这条之前被打回过」** ⇒ ⇒ 本批**不给**（队列只装「待审」）
- ⚠️ **P10-J-T1（公司级模板执行时选项目）** ⇒ ⇒ 要滚契约 ⇒ ⇒ **另批**
