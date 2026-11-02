# P9B-3 实施计划：本地 PG 车道 + 系统参数 + SIM 物流前端（SPEC §7.7 / §7.20）

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`
> （或 `superpowers:subagent-driven-development`）。
> ledger: `.superpowers/sdd/PCS-PLAN-P9B-3-系统参数与SIM物流前端/progress.md`
>
> ⚠️ **本计划已吸收 2026-11-02 委员会的 8 条裁决 + 5 条用户裁决 + 3 条 P1 +
> 5 条 P2 + 7 条前置核实**（见下各表）⇒ 开工前**不需要**再问同一批问题。
> **「尚未解决的问题」一节是唯一还需要裁决的**（其中 2 条已在本次复审关闭）。

**Goal:** 补上三块欠账 —— ①**本地 PG 车道**（TODO-099：PG 专属语义至今零自动化
覆盖）②**§7.20 系统参数页**（`system_settings` 表存在但零 API，前端零页面）
③**§7.7 SIM 物流前端**（列表工具栏/筛选/引用列、手动创建向导、详情页 7 个 Tab、
单条「提交校对」—— 三个页面目前都是极简占位）。

**Architecture:** 三个**互不依赖**的子系统，按「基础设施 → 契约 → 业务」顺序落地：
- **T0** 是**基础设施**（docker-compose `pg` profile 独立实例 + `pcs_pgtest` 库 +
  `scripts/pytest_pg.sh` 唯一入口）⇒ 它是 T3/T6/T8 里 PG 专属断言的**载体**；
- **T2**（SPEC V2.6）**先于**所有代码 —— CLAUDE.md 规定「前端唯一依据是 SPEC」，
  且「与 OpenAPI 冲突时以 OpenAPI 为准并**登记 SPEC 修订**」⇒ 契约先落；
- **T4**（系统参数后端）→ **T5**（系统参数前端）是**一条链**（端点 → 页面）；
  **T6/T7/T8**（物流列表 → 手动创建向导 → 详情页 Tab）是**另一条链**（列表页的
  「新建物流」跳向导，向导写完回列表，列表展开进详情）。

**Tech Stack:** React 19 + TypeScript + antd 5 + axios + zustand + vitest + MSW +
Playwright；后端 FastAPI + SQLAlchemy 2.x async + pytest + alembic。

**Spec:** 本文档即设计（委员会 2026-11-02 裁决 + 前置核实结论）⇒ 计划自证其依据。

### 任务执行顺序（委员会 2026-11-02 最终判定）

```text
T0    本地 PG 车道（fail-closed 三约束）
T1    债项三条（TODO-101 / 102 / 103）—— 103 拆两个 commit
T2    SPEC V2.6（✅/⏳/❌ 状态标记版）
T2.5  streams.source 列 + 迁移 p9_015 + 枚举（MANUAL / SIM_IMPORT / EXCEL / LAB）
T3    物流组成合计门禁（None 跳过 / {} 拒绝）
T4    系统参数后端（7 项 seed + 批量原子 PUT）
T5    系统参数前端
T6    物流列表页（工具栏 / 四项筛选 / 单条提交校对）
T7    物流手动创建向导（校验→写入→估算→提交）
T8    物流详情页 7 Tab（含校核记录，前端过滤 + TODO 登记）
T9    QA gate + 收口
```

⚠️ **T2.5 的位置不是任选的**：必须在 **T2 之后**（SPEC 先定义 source 枚举）
与 **T3 之前**（T6 的「来源」列/筛选与 T7 的向导都依赖它）。

---

## Global Constraints

| 约束 | 精确值 |
|---|---|
| 提交约定 | conventional commits，**无 attribution 行**；长消息写文件后 `git commit -F` |
| 分支 | 直提 `main`，**禁 worktree**（用户长期裁决 + 历史事故） |
| 每个 task 一 commit | 每批一收口报告 |
| 前端类型来源 | **契约派生**（`components['schemas'][...]`）；⚠️ 手写 union 是 bug-2040 那类漂移根因 |
| 后端错误 | 全仓唯一 `PcsError`（`app/core/errors.py`）；业务码大写蛇形 + HTTP 状态码 |
| 审计 | 状态变更写 `audit_logs`（`AuditService.write`）；动作名加进 `AuditAction` 枚举 |
| 口令 | **不上命令行**（会被权限分类器拦 + 进 shell 历史）⇒ 进程内派生 / 环境变量 |
| 验多库 | **每库一个独立进程**（alembic 的 `settings` 是 pydantic 缓存实例）⇒ 且**直查库**确认 |
| 行锁断言 | 方言级 SQL 断言（PG 方言编译出 `FOR UPDATE`）+ 接线断言；**不**依赖 SQLite |
| SPEC | 前端唯一编码依据；与 OpenAPI 冲突时以 OpenAPI 为准并**登记修订**（§12.4 加行） |
| 契约门禁 | 每批末 `bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline` |
| 发布前清单 | `CLAUDE.md` 的「发布前检查（必做）」四条（见 T0） |

## Review Focus

写实现前先读这五条 —— 每条对应一个**测试**，钉在拥有该代码的 task 里：

1. **批量保存系统参数时中途失败** ⇒ 期望**全不改**（不是改了一半）。
   → 钉在 **T4**（后端事务原子性测试）。
2. **后端返回 9 态之外的 `sign_status`** ⇒ 期望**降级显示**（`StateBadge` 的
   `unknownBadge`），不是 `TypeError` 整页崩（P9B-2F #14 的同形，新页面别重犯）。
   → 钉在 **T6**（列表）与 **T8**（详情）。
3. **物流组成合计 98.7%** ⇒ 期望送审**被拒**（422，具名错误码），不是放行。
   → 钉在 **T3**。
4. **PG 车道在 PG 没起 / 测试被全 skip 时** ⇒ 期望**非零退出**，不是「全绿」。
   → 钉在 **T0**。
5. **同一条 stream 被并发提交校对两次** ⇒ 期望**一胜一拒**（行锁），
   不是两次都成功（P9B-2 报告 #1 的同形）。→ 钉在 **P9B-3b**（本批只做单条，
   并发断言随批量端点一起做）。

---

## 委员会裁决（2026-11-02）

| # | 项 | 裁决 |
|---|---|---|
| 1 | §7.20 三页后端落法 | 选项 1（复用 `system_settings` + 新建 `prompt_templates`）—— ⚠️ **但见裁决 2**：AI 开关页与 Prompt 模板页**本批不做** ⇒ 实际只做**系统参数页** |
| 2 | AI 开关 + Prompt 模板 | **不做**（P10 前无下游消费者；未来签名未知 ⇒ 现在做要全部推翻）⇒ **必须同步修改 SPEC §7.21** |
| 3 | 角色分配（TODO-092） | **本批不做**（选项 3）⇒ 「AD 同步覆盖 roles」是**当前行为**，必须写进计划；角色来源权威性**升格独立 ADR**（不是计划里能拍的） |
| 4 | TODO-099 PG 车道 | **选项 1**（本地 PG 车道）+ 三条硬约束 + 一条复审触发（见 T0） |
| 5 | 校对批量 | D1~D6 六条决策全部采纳 ⇒ **单列 P9B-3b**（见文末移交节） |
| 6 | §7.20 系统参数 | **复用 `system_settings`**（表结构核实：主键 / JSONB / 0 行 / 无 `updated_by` 符合全仓口径）⇒ T4 |
| 7 | Prompt 模板 | 覆盖式 + 审计（无版本要求）—— ⚠️ **随裁决 2 不做**（P10） |
| 8 | 事实基础按**实测**写 | 状态名 `IN_APPROVAL` · 审计复用 `RECORD_TRANSITION` · 组成校验需新建 ⇒ 三处偏差已标注（见「与委员会 brief 的三处偏差」） |

## 用户裁决（2026-11-02）

| # | 项 | 裁决 | 落地 |
|---|---|---|---|
| 1a | `streams.source` 列 | **加**（迁移 `p9_015`） | **T2.5**（4 值：MANUAL / SIM_IMPORT / EXCEL / LAB） |
| 1b | PRO/II 归属 | `SIM_IMPORT`（**不单列**一值） | T2.5 的 docstring + SPEC §7.7.1 |
| 2 | T7 顺序 | 校验 → 写入 → 估算 → 提交；**估算失败可继续**（不阻塞） | T7 Step 3 的 7 步表 + 一条「估算失败仍可继续提交校对」的测试 |
| 3 | SPEC 写法 | **B：状态标记（✅/⏳/❌）**，不用「本批」 | T2 的 Step 2~5（§12.4 约定 + §7.7.1 / §7.20 / §7.21 改写） |
| 4 | T4 默认键清单 | **7 项**（含 `stream.batch_submit_limit` 预埋） | P1-1（`DEFAULT_SETTINGS` + `seed_defaults()`） |

## 计划审查意见落地（2026-11-02 委员会复审 · CLEARED TO START）

| # | 级别 | 意见 | 落地 |
|---|---|---|---|
| P1-1 | P1 | T4 缺「系统参数键初始化机制」（表 0 行 ⇒ 管理员看到空页面） | T4 Step 4b：`DEFAULT_SETTINGS` 7 项 + `seed_defaults()` + 启动钩子 + `test_seed_is_idempotent` |
| P1-2 | P1 | T0 的 `test_fails_when_zero_pg_tests_are_collected` **测的不是它想测的**（PG 一定没起 ⇒ 脚本第一步就退出 ⇒ 永远走不到「收集到 0 个」分支） | T0：假 `docker` shim 放 PATH 让 PG 检查通过 ⇒ 才测得到目标分支 |
| P1-3 | P1 | T2 让 SPEC 写「本批」「P9B-3b」⇒ 违反 SPEC 定位（需求规格书不该知道批次概念） | T2 Step 2~5：**✅/⏳/❌ 状态标记**（含 §12.4 约定） |
| P2-1 | P2 | 空 `composition_json` 的策略没区分 | T3：`None` 跳过 / `{}` 拒绝（422）/ 有内容校验 `\|sum−1\| ≤ 0.005` + SPEC §7.7.2 补一句 |
| P2-2 | P2 | T8 校核记录的前端过滤性能 | T8 Step 4b：保持前端过滤 + 登记 TODO-104（触发条件 / 方案 / 归属） |
| P2-3 | P2 | T4 的「只能改不能增」是**已知限制**，得写明 | T4 的 docstring + SPEC §7.20.1 同款措辞 |
| P2-4 | P2 | T1 的 TODO-103 diff 很大 | T1 拆**两个** commit（只加生成器 / 再跑生成器） |
| P2-5 | P2 | T9 的「三库」表述模糊 | T9 Step 5 改成「**两库 + 一条车道**」表（`pcs` / `pcs_test` / `pcs_pgtest` 各验什么） |

## 事实基础（2026-11-02 实测，非推断）

### 后端

| 面 | 现状 | 出处 |
|---|---|---|
| `streams` 写面 | `POST /streams`（创建）· `POST /streams/validate` · `PATCH/DELETE /streams/{id}` | `app/api/v1/streams.py:202,241,325,347` |
| `streams.source_type` | **已存在**：`VARCHAR(30)` NOT NULL + CHECK `ck_streams_source_type`，**13 值**（3 人工/导入 + 10 个 `*_CALCULATED` 设备计算出口流）⇒ 语义 = **产出方式**，**不是** SPEC §7.7.1 的「来源」 | `app/models/project.py:256,444` + `pcs_test` 直查库（202 行：MANUAL_ENTRY 101 / PIPE_NET_CALCULATED 68 / PIPE_CALCULATED 33） |
| `streams.source`（SPEC §7.7.1 的「来源」） | **不存在** ⇒ T2.5 新增（4 值：MANUAL / SIM_IMPORT / EXCEL / LAB） | 同上 |
| 物流状态机 | `POST /streams/{id}/submit`（**DRAFT → IN_APPROVAL**）· `approve` · `reject` · `initiate-change` · `pass-change` · `mark-stale` | `streams.py:518…604` |
| 物性 / 状态点 | `GET /streams/{id}/properties` · `POST .../estimate` · `GET /streams/{id}/state-points` | `streams.py:635,663,402` |
| 血缘 | `GET /lineage/{record_type}/{record_id}/upstream|downstream|graph` | `app/api/v1/lineage.py:28,59,92` |
| 审计读 | `GET /audit-logs` **已支持** `resource_type` / `resource_id` / `action` / `user_id` / 时间区间过滤 | `app/api/v1/audit.py:40-70` |
| `system_settings` | 表存在、**零 API**、**零行**；`setting_key` = **主键**（UNIQUE）· `setting_value_json` = **JSONB** · 无 `updated_by` · 无 CHECK | `app/models/system.py:140` + `dd47298c9c38…:293` |
| Prompt 模板 | **无表、无 API** | `grep -rniE "prompt_template"` = 0 命中 |
| AI 开关 | **无端点**；`ai_audit_log` 表存在（仅审计） | `app/models/system.py:185` |
| 角色分配 | `admin_users` 只有 list / disable / sync 三个端点 ⇒ TODO-092 确认 | `app/api/v1/admin_users.py:84,94,116` |

### 前端

| 面 | 现状 |
|---|---|
| `StreamListPage.tsx` | **140 行**：只有状态分页签 + 表格；**无**工具栏（导入/新建物流/提交校对/导出）· **无**筛选（工况/相态/状态/来源）· **无**引用列 |
| `StreamDetailPage.tsx` | **266 行**：只有「基础信息」Descriptions + 「组成」Table 两个 Card；**无 Tab**（SPEC 要 7 个） |
| `ImportWizardPage.tsx` | **105 行**：2 步（预览 / 确认）；SPEC §7.7.3 要 7 步（含「手工」分支 / Excel 列映射） |
| `src/api/stream.ts` | **1017B**：只有 `listByProject` + **手写** `StreamListItem`（5 字段）⇒ 契约脱钩 |
| ADMIN 页 | `UserAdminPage.tsx` ✓ · `ProjectAdminPage.tsx` ✓ · 系统参数 / 角色分配 / AI 开关 / Prompt 模板 ✗ |

### 七条前置核实的结论

| 核实 | 结论 |
|---|---|
| 1 `system_settings` 表结构 | **适合复用**：`setting_key` 是主键（UNIQUE ✓）· JSONB ✓ · 真库 0 行（无存量要迁）· 无 `updated_by` **不是缺口**（全仓口径是 `updated_at` + `audit_logs` 写审计，`config_assets` 同样没有 `updated_by`）⇒ **不需加列** |
| 2 AI 开关是否独立概念 | 是 key 前缀（方案 A）—— ⚠️ 但 SPEC §7.21 明写「**P10 前禁用**」⇒ **无消费者** ⇒ 裁决 2：**不做** |
| 3 Prompt 模板是否要版本 | SPEC **无**版本要求 ⇒ 覆盖式 + 审计 —— ⚠️ 随裁决 2 **不做** |
| 4 「复用」≠「零成本」 | 表存在 ≠ API 存在 ⇒ 仍需 **1 service + 1 router + 批量原子端点**（T4） |
| A `StreamSignStatus` 状态机 | **9 态**（与 `RecordSignStatus9` 字面对齐）：DRAFT / IN_APPROVAL / CHECKED / CHECK_REJECTED / STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE ⇒「提交校对」= `SUBMIT_FOR_CHECK` = **DRAFT → IN_APPROVAL** |
| B 单条提交端点是否存在 | **存在** ✓ `POST /streams/{id}/submit`（ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN；`reason=None`）⇒ 批量端点是「N 次单条语义的批量化」 |
| C 校核记录存哪 | **在 `audit_logs`**（动作 `RECORD_TRANSITION`，`resource_type='streams'`，与记录侧同构）⇒ `GET /audit-logs` 已能按 `resource_type` + `resource_id` 过滤 ⇒ **校核记录 Tab 不需要新后端端点** |

### ⚠️ 与委员会 brief 的三处偏差（计划按**实测**写，不是按 brief 写）

1. **状态名**：brief 假设 `DRAFT → PENDING`；实测是 **`DRAFT → IN_APPROVAL`**（9 态字面对齐记录侧）⇒ 幂等判定、审计 action 名、错误码文案全部按 `IN_APPROVAL` 写。
2. **审计动作**：brief 建议新动作 `STREAM_SUBMITTED_FOR_REVIEW`；实测 streams 的转移**复用** `RECORD_TRANSITION`（`state_machine.TRANSITION_AUDIT_ACTION`）⇒ **不新造动作**（新造会让「按动作查审计」分裂成两套）。只有**批次**那条是新动作 `STREAM_BATCH_SUBMITTED`（P9B-3b）。
3. **组成合计校验不存在**（`grep COMPOSITION` = 0 命中）⇒ brief 里的失败原因 `COMPOSITION_SUM_OUT_OF_RANGE` **需要新建**（T3），不是「复用既有的」。

---

## NOT in scope（本批明确不做）

| 不做 | 理由 | 归属 |
|---|---|---|
| **AI 开关页 + Prompt 模板页**（含后端表与 API） | P10 前无下游消费者；未来签名未知 ⇒ 现在做要全部推翻（裁决 2） | P10（随 AI 助手本体） |
| **角色分配页**（含 `PUT /admin/users/{id}/roles`） | 「手工优先」是 ADR 级改动；角色来源权威性**升格独立 ADR**（裁决 3） | 独立 ADR + 后续批次 |
| **批量「提交校对」** | 委员会裁决 5：六条契约决策量大 ⇒ 单列 | **P9B-3b**（文末移交节） |
| AI 助手本体（对话面板 / 知识检索 / 相似设备） | P10 | P10 |
| `prompt_templates` 表与迁移 | 随裁决 2 | P10 |
| 物流 Excel 列映射 / 模板库（§7.7.3 步骤 4） | 本批只做**手工**分支（T7） | P9B-4 |
| §7.7.2 的「物性」页内编辑 | `POST /streams/{id}/properties/estimate` 已有，只读展示 + 触发估算 | 后续 |

---

## 文件结构

**后端（新增）**

```
pcs-backend/app/schemas/system_settings.py      # T4：SystemSettingOut / SystemSettingBatchIn
pcs-backend/app/services/system_setting_service.py  # T4：批量原子写
pcs-backend/app/api/v1/system_settings.py       # T4：GET /system-settings · PUT /system-settings
pcs-backend/scripts/pytest_pg.sh                 # T0：PG 车道唯一入口（fail-closed）
pcs-backend/scripts/gen_compact_orm.py           # T1：compact ORM 表生成器（TODO-103）
pcs-backend/tests/api/v1/test_system_settings.py # T4
pcs-backend/tests/api/v1/test_stream_composition_sum.py  # T3
pcs-backend/tests/api/v1/test_stream_source.py          # T2.5：source 列 + 筛选
pcs-backend/alembic/versions/p9_015_stream_source.py     # T2.5：迁移
pcs-backend/tests/scripts/test_pytest_pg_gate.py # T0：脚本的 fail-closed 行为
pcs-backend/tests/alembic/test_p9_013_bind_default_record_matrix.py  # T0：docstring 再更正
pcs-backend/tests/alembic/test_p9_014_record_approval_chain_snapshot.py  # T0：docstring 再更正
```

**后端（修改）**

```
pcs-backend/app/models/enums.py                  # T4：AuditAction 加 SYSTEM_SETTINGS_UPDATED；T2.5：StreamSource 枚举
pcs-backend/app/models/project.py                # T2.5：Stream.source 列 + CHECK + 复合索引
pcs-backend/app/schemas/stream.py               # T2.5：StreamBase.source
pcs-backend/app/services/import_service.py       # T2.5：导入路径写 source
pcs-backend/app/services/outlet_stream.py        # T2.5：出口流继承上游 source
pcs-backend/app/api/v1/streams.py                # T3：submit 前加组成合计校验；T2.5：?source= 筛选
pcs-backend/app/api/v1/projects.py               # T1：IntegrityError 只在命中 project_no 时映射 409
pcs-backend/app/api/v1/__init__.py               # T4：挂 system_settings router
pcs-backend/app/main.py                          # T4：启动钩子调 seed_defaults（P1-1）
pcs-backend/pyproject.toml                       # T0：注册 pg marker
pcs-backend/docs/openapi.json                   # T4：契约重滚
```

**前端（新增）**

```
pcs-frontend/src/api/systemSettings.ts           # T5
pcs-frontend/src/pages/admin/SystemSettingsPage.tsx  # T5
pcs-frontend/src/pages/sim/StreamManualWizardPage.tsx  # T7
pcs-frontend/src/pages/sim/tabs/StreamBasicTab.tsx      # T8
pcs-frontend/src/pages/sim/tabs/StreamCompositionTab.tsx  # T8
pcs-frontend/src/pages/sim/tabs/StreamPropertiesTab.tsx  # T8
pcs-frontend/src/pages/sim/tabs/StreamStatePointsTab.tsx  # T8
pcs-frontend/src/pages/sim/tabs/StreamConnectionsTab.tsx  # T8
pcs-frontend/src/pages/sim/tabs/StreamLineageTab.tsx      # T8
pcs-frontend/src/pages/sim/tabs/StreamReviewLogTab.tsx    # T8
```

**前端（修改）**

```
pcs-frontend/src/api/stream.ts                   # T6/T7/T8：契约派生类型 + 新端点封装
pcs-frontend/src/pages/sim/StreamListPage.tsx    # T6：工具栏 / 筛选 / 引用列 / 行操作
pcs-frontend/src/pages/sim/StreamDetailPage.tsx  # T8：改成 7 Tab 宿主（拆子组件）
pcs-frontend/src/router/App.tsx（实为 src/App.tsx）  # T5：/admin/system-settings 路由 + 菜单
pcs-frontend/src/types/api.d.ts                 # T4：契约重滚（生成物，勿手改）
```

**文档**

```
docs/PCS-UI-SPEC.md        # T2：§12.4 加 V2.6 行 + §7.7/§7.20/§7.21 正文
TODOS.md                   # T2：TODO-092 升格 ADR 的登记 + TODO-100 的 scope 登记
CLAUDE.md                  # T0：发布前检查（必做）清单
docker-compose.yml         # T0：pg profile 独立实例
```

---

## Task T0：本地 PG 车道（TODO-099 · 裁决 4）

**Files:**
- Modify: `docker-compose.yml`（加 `postgres-pgtest` 服务 + `pgtestdata` 卷）
- Modify: `pcs-backend/pyproject.toml`（注册 `pg` marker）
- Create: `pcs-backend/scripts/pytest_pg.sh`
- Create: `pcs-backend/tests/scripts/test_pytest_pg_gate.py`
- Modify: `pcs-backend/tests/alembic/test_p9_013_bind_default_record_matrix.py`（docstring 再更正）
- Modify: `pcs-backend/tests/alembic/test_p9_014_record_approval_chain_snapshot.py`（同上 + 标 `pg`）
- Modify: `CLAUDE.md`（发布前检查清单）

**Interfaces:**
- Consumes: `tests/alembic/` 里现有的 PG 引擎级测试（p9_013 两条 + p9_014 两条）。
- Produces: **`scripts/pytest_pg.sh`** —— 全仓**唯一**的 PG 车道入口；
  `pg` pytest marker（`pytest -m pg` 只选 PG 专属用例）；CLAUDE.md 的发布前清单。

- [ ] **Step 1: 写脚本行为测试（先红）**

```python
# pcs-backend/tests/scripts/test_pytest_pg_gate.py
"""scripts/pytest_pg.sh 的 fail-closed 行为（T0 · TODO-099 · 裁决 4 约束 1）。

## 为什么这个文件存在

「一键脚本」如果没有**强制力**，等于没有 —— 没人跑就等于没做。
委员会的三条硬约束里第一条就是「**fail-closed**」：
PG 没起 ⇒ FAIL；收集到 0 个 PG 测试 ⇒ FAIL；测试被全 skip ⇒ FAIL。
⇒ 这三条必须**有测试**，否则「脚本写了但没人跑」与「脚本不存在」不可区分
（同 `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`）。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pytest_pg.sh"


def _run(env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env={**os.environ, **env_extra},
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_script_exists_and_is_executable():
    assert SCRIPT.exists(), "PG 车道入口脚本不存在"
    assert os.access(SCRIPT, os.X_OK), "脚本不可执行"


def test_fails_when_pg_instance_is_not_running():
    """PG 实例没起 ⇒ 非零退出 + 明确提示（不是「跳过」）。"""
    r = _run({"PG_COMPOSE_PROJECT": "pcs_pg_absent_project"})
    assert r.returncode != 0, "PG 没起却退出 0 ⇒ 假绿"
    assert "docker compose --profile pg up -d" in (r.stdout + r.stderr)


def test_fails_when_zero_pg_tests_are_collected(tmp_path):
    """收集到 0 个 PG 测试 ⇒ 非零退出（「收集到 0 个」不是「通过」）。

    ⚠️ **必须让 PG 检查通过**才能测到这条分支 —— 否则脚本在「PG 没起」那步就
    退出，这条测试实际测的是「PG 没起」而不是「收集到 0 个」
    （`guard-test-fooled-by-lying-comment` 同形：守卫测的不是它声称的东西）。

    ⇒ 用**假的 docker**（PATH 前置一个 shim，输出 `postgres-pgtest running`）
    让第 ① 步通过。
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text("#!/bin/sh\necho 'postgres-pgtest running'\nexit 0\n")
    fake_docker.chmod(0o755)

    r = _run({
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "PG_PYTEST_MARK": "no_such_marker_xyz",
    })
    assert r.returncode != 0
    assert "收集到 0 个 PG 测试" in (r.stdout + r.stderr)


def test_script_does_not_teach_a_second_entry_point():
    """⚠️ 唯一入口：脚本里不得出现「直接 DATABASE_URL=... pytest」的第二条路。"""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "pytest -m pg" in body
    # 不得在脚本里另起一条不经脚本的 pytest 调用路径（注释里说明允许）
    assert body.count("uv run pytest") == 2, (
        "脚本里应只有「收集计数」与「正式执行」两次 pytest 调用；"
        "多出来的说明有人加了第二条路径"
    )
```

- [ ] **Step 2: 跑测试确认红**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_pytest_pg_gate.py -v`
Expected: FAIL —— `scripts/pytest_pg.sh` 不存在。

- [ ] **Step 3: 加 `pg` marker**

在 `pcs-backend/pyproject.toml` 的 `markers = [...]` 里追加：

```toml
    "pg: PG 专属用例（需真 PostgreSQL）。只能经 scripts/pytest_pg.sh 跑 —— 平时被 skipif 静默跳过。",
```

⚠️ `addopts = "-m 'not visual'"` 会被命令行后出现的 `-m` 覆盖 ⇒ `pytest -m pg` 选得到。

- [ ] **Step 4: 给 PG 用例打标记**

`tests/alembic/test_p9_013_bind_default_record_matrix.py` 的
`test_p9_013_runs_on_fresh_postgres_schema` 与
`test_p9_013_p9_012_downgrade_upgrade_roundtrip`，
`tests/alembic/test_p9_014_record_approval_chain_snapshot.py` 的两条 PG 测试，
各加一行 `@pytest.mark.pg`。

- [ ] **Step 5: 写 `scripts/pytest_pg.sh`**

```bash
#!/usr/bin/env bash
# 唯一的 PG 车道入口（TODO-099 · 委员会 2026-11-02 裁决 4）。
#
# ⚠️ **不得**在 README/CLAUDE.md 里教「也可以直接 DATABASE_URL=... pytest」——
#    那会重新引入「多条路径做同一件事」的分叉。
#
# 三条 fail-closed 约束（缺一条就等于没做）：
#   ① PG 实例没起 ⇒ FAIL（不是 skip）
#   ② 收集到 0 个 PG 测试 ⇒ FAIL（「收集到 0 个」不是「通过」）
#   ③ 测试被全 skip ⇒ FAIL（PG 起了但没真跑，与没起无法区分）
set -euo pipefail

cd "$(dirname "$0")/.."

PG_COMPOSE_PROJECT="${PG_COMPOSE_PROJECT:-pcs}"
PG_PYTEST_MARK="${PG_PYTEST_MARK:-pg}"
PG_DB_NAME="${PG_DB_NAME:-pcs_pgtest}"
PG_PORT="${PG_PORT:-5433}"

# ① PG 实例必须起着
if ! docker compose --profile pg ps --status running \
     | grep -q "postgres-pgtest"; then
  echo "FAIL: PG 测试实例未起 ⇒ docker compose --profile pg up -d" >&2
  exit 1
fi

# 口令**只在环境变量里**（不上命令行 —— 会被权限分类器拦，且进 shell 历史）
PG_USER="${POSTGRES_USER:-pcs}"
PG_PASS="${POSTGRES_PASSWORD:-pcs_dev}"
export DATABASE_URL="postgresql+psycopg://${PG_USER}:${PG_PASS}@localhost:${PG_PORT}/${PG_DB_NAME}"
export TEST_DATABASE_URL="$DATABASE_URL"

# ② 收集到的 PG 测试数必须 > 0
collected="$(uv run pytest -m "$PG_PYTEST_MARK" --collect-only -q 2>/dev/null \
  | grep -oE '[0-9]+ tests? collected' | grep -oE '[0-9]+' | head -1 || true)"
if [ "${collected:-0}" -eq 0 ]; then
  echo "FAIL: 收集到 0 个 PG 测试（标记缺失 / 全部 skip）" >&2
  exit 1
fi

# ③ 正式执行；输出里必须有「至少 1 passed」
out="$(uv run pytest -m "$PG_PYTEST_MARK" -q 2>&1)" || { echo "$out"; exit 1; }
echo "$out"
if ! echo "$out" | grep -qE '[1-9][0-9]* passed'; then
  echo "FAIL: PG 车道没有实际执行任何测试（全部 skip？）" >&2
  exit 1
fi
```

`chmod +x pcs-backend/scripts/pytest_pg.sh`

- [ ] **Step 6: 加 docker-compose 的 `pg` profile（独立实例 + 独立库）**

```yaml
  postgres-pgtest:
    # ⚠️ **独立实例**（不是复用开发库那个 postgres）：PG 车道跑的是
    # 迁移 / 降级环 / 并发用例 ⇒ 绝不能污染开发数据（CLAUDE.md「漂移盲区」）。
    # 独立 database（pcs_pgtest）防「开发时 alembic upgrade head 误把
    # 测试数据升了」。裁决 4 修正 2 明确要求独立实例 + 独立 database。
    profiles: ["pg"]
    image: postgres:18-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-pcs}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-pcs_dev}
      POSTGRES_DB: pcs_pgtest
    ports: ["5433:5432"]
    volumes: [pgtestdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pcs -d pcs_pgtest"]
      interval: 5s
      timeout: 3s
      retries: 10
```

并在 `volumes:` 段加 `pgtestdata:`。

- [ ] **Step 7: 跑脚本测试确认绿**

Run: `cd pcs-backend && uv run pytest tests/scripts/test_pytest_pg_gate.py -v`
Expected: PASS（4 例）。

- [ ] **Step 8: 真跑一次 PG 车道**

```bash
cd /home/pangzy/code_project/PCS && docker compose --profile pg up -d
cd pcs-backend && bash scripts/pytest_pg.sh
```
Expected: 退出 0，输出含 `4 passed`（p9_013 两条 + p9_014 两条）。
⚠️ 若 PG 刚起还没 ready，先 `docker compose --profile pg ps` 确认 healthcheck 通过。

- [ ] **Step 9: 修两条 false delegation docstring（裁决 4 约束 2）**

`tests/alembic/test_p9_013_bind_default_record_matrix.py` 与
`tests/alembic/test_p9_014_record_approval_chain_snapshot.py` 里凡出现
「CI 的 api-drift job 承担同口径验证」/「CI 覆盖不到本文件」的句子，一律改成：

> 引擎级验证**必须**在发布前经 `scripts/pytest_pg.sh` 手动跑（唯一入口）。
> CI **不**跑 pytest —— `check-api-drift` job 只跑 `alembic upgrade head` 与
> OpenAPI 导出；见 `CLAUDE.md` §「发布前检查（必做）」。

- [ ] **Step 10: CLAUDE.md 加「发布前检查（必做）」清单**

在 `CLAUDE.md` 的「测试前检查」一节末尾追加：

```markdown
## 发布前检查（必做）

- [ ] `alembic check` 在两库（pcs / pcs_test）各 exit 0 —— ⚠️ 必须**独立进程**跑，
      见 cerebrum「alembic settings 缓存」；且**直查库**确认 revision 与目标列
- [ ] `scripts/pytest_pg.sh` exit 0 —— 覆盖 `tests/alembic/` 的引擎级用例与并发类用例
- [ ] `check_openapi_payload_coverage.py` RC 0（裸字段 ≤ 基线）
- [ ] `check_migration_idempotency.py` RC 0
- [ ] 前后端全量测试绿

⚠️ 第 1 条验「迁移与 ORM 一致」，第 2 条验「迁移在**真实 PG** 上跑得通 + 并发语义正确」
⇒ 两者**不互相替代** ⇒ 「只跑 alembic check」不算发布前检查通过。
```

- [ ] **Step 11: 登记复审触发（裁决 4）**

在 `TODOS.md` 的 TODO-099 条目里追加：

```markdown
⚠️ **复审触发（2026-11-02 委员会）**：若未来 **2–3 个发布周期内**出现至少一次
「PG-specific bug 因为没跑 `scripts/pytest_pg.sh` 而在发布后暴露」⇒
2026-08-29 的「CI/CD 流水线不做」裁决**必须被重新提出**（不是被绕过），
依据是「自己记得跑」这个前提被证伪 N 次。
```

- [ ] **Step 12: Commit**

```bash
git add docker-compose.yml pcs-backend/pyproject.toml pcs-backend/scripts/pytest_pg.sh \
        pcs-backend/tests/scripts/test_pytest_pg_gate.py \
        pcs-backend/tests/alembic/ CLAUDE.md TODOS.md
git commit -F <消息文件>
```
消息首行：`feat(P9B-3): 本地 PG 车道（TODO-099）—— 独立实例 + fail-closed 唯一入口`

---

## Task T1：债项三条（TODO-101 / 102 / 103）

**Files:**
- Modify: `pcs-frontend/src/components/common/StateBadge.tsx`
- Test: `pcs-frontend/tests/components/common/StateBadge.test.tsx`（新增）
- Modify: `pcs-backend/app/api/v1/projects.py`
- Test: `pcs-backend/tests/api/v1/test_projects_api.py`（既有文件，加用例）
- Create: `pcs-backend/scripts/gen_compact_orm.py`
- Modify: `pcs-backend/docs/schema_compact_orm.md`（生成物）

**Interfaces:**
- Consumes: `DeliverableSignStatus`（4 态，契约派生）；`projects.project_no` 唯一约束。
- Produces: `scripts/gen_compact_orm.py`（可重跑，把 compact ORM 表变成**派生**产物）。

- [ ] **Step 1: TODO-101 —— StateBadge 交付物强调集（先红）**

`StateBadge.tsx` 的 `MODULE_ACTIVATED.DELIVERABLE` 现在装的是**记录侧 9 态**
⇒ 交付物自己的 `PENDING` / `APPROVED` 不在集合里 ⇒ 渲染成 opacity 0.4
（看起来像「过期」）。改成交付物 4 态：

```ts
  DELIVERABLE: new Set<DeliverableSignStatus>([
    'DRAFT', 'PENDING', 'APPROVED', 'OBSOLETE',
  ]),
```

（`MODULE_ACTIVATED` 的类型是 `Record<StateBadgeModule, ReadonlySet<AnyKnownStatus>>`，
⇒ 需要把 `AnyKnownStatus` 扩成 `RecordSignStatus | DeliverableSignStatus`，
或把该表的类型放宽到 `ReadonlySet<string>`。）

测试（新增文件 `pcs-frontend/tests/components/common/StateBadge.test.tsx`）：

```tsx
it('交付物的 PENDING / APPROVED **不半透明**（TODO-101）', () => {
  const { container } = render(<StateBadge module="DELIVERABLE" status="PENDING" />);
  const badge = container.querySelector('[data-testid=state-badge]') as HTMLElement;
  expect(badge.style.opacity).toBe('1');   // 此前是 0.4
});
```

- [ ] **Step 2: 跑测试确认红 → 改实现 → 跑绿**

Run: `cd pcs-frontend && npx vitest run tests/components/common/StateBadge.test.tsx`
Expected: 先 FAIL（opacity 0.4）⇒ 改实现 ⇒ PASS。

- [ ] **Step 3: TODO-102 —— IntegrityError 只在命中 project_no 时映射 409（先红）**

`projects.py` 现在把**任何** `IntegrityError` 报成 409「项目编号已存在」⇒
NOT NULL / FK / CHECK 违约也会被说成「编号重复」⇒ 用户照提示换编号，换了还是错。

改成只在该约束命中时映射 409，其余重新抛出：

```python
    try:
        await db.flush()
    except IntegrityError as e:
        # ⚠️ **只有** `project_no` 唯一约束冲突才是 409（TODO-102）；
        #    其它约束违约（NOT NULL / FK / CHECK）重新抛 ⇒ 500 + 服务端留详情，
        #    不把「另一种错」说成「编号重复」。
        if "project_no" not in str(getattr(e, "orig", e)):
            raise
        await db.rollback()
        raise PcsError(
            code="PROJECT_NO_CONFLICT",
            message=f"项目编号 {payload.project_no} 已存在（全局唯一），请换一个",
            status=409,
        ) from e
```

测试（加到 `tests/api/v1/test_projects_api.py`）：构造一条**别的**约束违约
（例如 `project_name=None` 触发 NOT NULL）⇒ 期望 **500 / 未被映射成 409**。

- [ ] **Step 4: TODO-103 —— compact ORM 表改成派生**

新建 `pcs-backend/scripts/gen_compact_orm.py`：从 `SA_Base.metadata` 导出
`docs/schema_compact_orm.md`，格式沿用现有的 `列|类型!` 风格（`!` = NOT NULL，
`CHARPK` / `CHARFK` / `jsonb` / `dt` 等类型映射照现有文件）。

⚠️ 现有文件是 **2026-09-02 的 53 表快照**（ORM 现有 107 张）⇒ 生成器一次会
把它变成 **107 表** ⇒ diff 很大但**正确**（TODO-103 的目的就是让文件不再过期）。
生成器的头部必须写：

```markdown
> 生成时间：<ISO 日期> | 来源：app/models/*.py（**生成物，勿手改**）
> 重新生成：`cd pcs-backend && uv run python scripts/gen_compact_orm.py`
```

- [ ] **Step 5: 跑生成器 + 断言它包含新列**

```bash
cd pcs-backend && uv run python scripts/gen_compact_orm.py
grep -c "approval_chain_snapshot|jsonb" docs/schema_compact_orm.md   # 应为 20
```

- [ ] **Step 6: Commit（拆三个，P2-4）**

⚠️ TODO-103 的 diff 会很大（53 表快照 → 107 表派生）⇒ **拆两个 commit**，让
「实质改动」与「历史债清理」在历史里可分：

```bash
# ① 只加生成器，不跑（文件不变 ⇒ diff 小）
git add pcs-backend/scripts/gen_compact_orm.py
git commit -F <消息文件>
# 首行：feat(P9B-3): compact ORM 生成器（TODO-103 第一部分）—— 只加脚本，不跑

# ② 跑生成器，重新生成文件（diff 大）
git add pcs-backend/docs/schema_compact_orm.md
git commit -F <消息文件>
# 首行：chore(P9B-3): compact ORM 重新生成（TODO-103 第二部分，历史债清理）
# ⚠️ 消息里明确写「diff 大不是本批实质改动」
```

StateBadge / 409 收窄另外两个 commit：

```bash
git add pcs-frontend/src/components/common/StateBadge.tsx \
        pcs-frontend/tests/components/common/StateBadge.test.tsx
git commit -F <消息文件>   # fix(P9B-3): StateBadge 交付物词表用错 9 态（TODO-101）

git add pcs-backend/app/api/v1/projects.py pcs-backend/tests/api/v1/test_projects_api.py
git commit -F <消息文件>   # fix(P9B-3): 409 映射收窄到 project_no 唯一约束（TODO-102）
```

---

## Task T2：SPEC V2.6 修订 + TODO 登记

**Files:**
- Modify: `docs/PCS-UI-SPEC.md`（§7.7.1 / §7.7.2 / §7.7.3 / §7.20 / §7.21 / §12.4）
- Modify: `TODOS.md`

**Interfaces:**
- Consumes: 委员会裁决 2 / 3；P9B-2F 的 SPEC V2.5（`docs/PCS-UI-SPEC.md` §12.4 最后一行）。
- Produces: **前端实现的唯一依据**（CLAUDE.md）—— T4~T8 的字段与错误码口径全部落在这里。

- [ ] **Step 1: §7.20 增「7.20.1 系统参数」小节**

字段（后端 T4 按此实现）：

```text
系统参数（/admin/system-settings · SYSTEM_ADMIN）

- 键值表（后端 system_settings）：setting_key（≤100 字符，主键）/
  setting_value_json（JSONB）/ description / updated_at
- **批量保存**：一次 PUT 提交全部改动 ⇒ 事务内**全改或全不改**
  （硬约束：不做「每个键一个 PATCH」—— 那会让保存变成 N 个请求且中途失败留半改状态）
- 审计：每次写入一条 audit_logs（action=SYSTEM_SETTINGS_UPDATED，detail 含变更前后的键集合）
- 错误码：403 HTTP_403（无 SYSTEM_ADMIN）/ 404 SYSTEM_SETTING_NOT_FOUND（改不存在的键时）
```

- [ ] **Step 2: §12.4 写「状态标记约定」（P1-3：SPEC 不该知道批次概念）**

⚠️ **SPEC 是需求规格说明书，不该出现「本批」「P9B-3b」这类批次概念** ⇒ 改用
**状态标记**。在 §12.4 修订记录的说明处加：

```text
**状态标记约定**：
- ✅ 已实现且可用
- ⏳ 未实现，已排期（附归属：随 X 交付）
- ❌ 明确不做（附理由）
- （无标记）= 纯需求描述，未涉及实现状态
```

- [ ] **Step 3: §7.7.1 改写（P1-3：行操作 / 工具栏 / 来源枚举）**

```text
- 工具栏：导入 / 新建物流 / 导出 / 批量提交校对（⏳ 待 P9B-3b）
- 行操作：查看 / 校对（✅ 单条） / 变更
- 来源（source）：MANUAL（手动）/ SIM_IMPORT（模拟软件：PRO/II·HYSYS·Aspen）/
  EXCEL / LAB（预留）
```

⚠️ **PRO/II 归 `SIM_IMPORT`**，不单列一值（用户裁决 1b）⇒ `SIM_IMPORT` 的含义是
「模拟软件导出」，PRO/II / HYSYS / Aspen 都属它。

⚠️ **「来源」列的 4 值 = `streams.source`（T2.5 新增）**，与既有的
`streams.source_type`（13 值 · 产出方式）**不是同一列** ⇒ SPEC 只写前者。

- [ ] **Step 4: §7.20 改写（AI 开关 / Prompt 模板 用 ⏳）**

```text
⚠️ AI 开关（⏳ 未实现）：P10 随 AI 助手本体交付。
   理由：AI 助手 P10 前禁用（§7.21）⇒ 当前无下游消费者。

⚠️ Prompt 模板（⏳ 未实现）：P10 随 AI 助手本体交付。
   理由：同 AI 开关。
```

- [ ] **Step 5: §7.21 补状态表（P1-3）**

在 §7.21 末尾「P10 前禁用，Tooltip『AI 功能未启用』。」之后追加：

```text
⚠️ **AI 开关与 Prompt 模板的状态**：
   - 后端表/API：❌ 未实现（随 AI 助手本体）
   - 前端页：❌ 未实现（随 AI 助手本体）
   - 消费者：无（AI 助手本身未实现）

   待 P10 开工时，随 AI 助手一并对齐最终形态（参数化 / 版本 / A-B / 模型绑定待定）。
```

- [ ] **Step 6: §7.7.1 / §7.7.2 / §7.7.3 补齐口径**

- §7.7.1（Step 3 已改写工具栏 / 行操作 / 来源三块 ⇒ 这里只补**口径**）：
  筛选新增「工况 / 相态 / 状态 / 来源」四项（来源取值 = `source` 的 4 值）；
  ⚠️ 工具栏的「批量提交校对」标 ⏳ ⇒ **行操作的「校对」是 ✅ 单条**
  （`POST /streams/{id}/submit`），两者不矛盾；
  「引用 📎×N」的口径见「尚未解决的问题」第 1 条（本批先不渲染该列）。
- §7.7.2：7 个 Tab 的清单与「校核记录」的数据来源（`GET /audit-logs?resource_type=streams&resource_id=…`）。
- §7.7.3：明确「手工」分支 = **本批的手动创建向导**（T7）；Excel 列映射 / 模板库不在本批。

- [ ] **Step 7: §12.4 加 V2.6 行 + 文件头版本号升到 V2.6**

- [ ] **Step 8: TODOS.md 登记**

- TODO-092 追加：「**角色来源权威性升格独立 ADR**」（不是计划里能拍的）；并写明
  「**AD 同步覆盖 `users.roles` 是当前行为**」（本批不做 ⇒ 行为不变，但必须留档）；
- 新增一条 TODO 指向「角色分配 ADR」的立项（编号接 104）；
- ⚠️ **新增 3 条**（T2.5 落地时暴露的，见「尚未解决的问题」第 9/10/11 条）：
  ① `streams.source` 与 `streams.source_type` 长期是否合并（ADR 级）；
  ② Excel 导入行的 `source_type` 仍是 `SIM_IMPORT` ⇒ 是否扩该词表；
  ③ 10 个 `*_CALCULATED` 设备计算出口流在 `source` 的 4 值里无对应 ⇒
  是否加第 5 值 `CALCULATED`（本批规则：出口流继承上游的 `source`）；
- TODO-100 追加触发条件：「下一轮 ce-code-review 的 scope 须含
  `test_deliverable_issue.py` + deliveries / record_edits API 改动 + 该批 diff 其余部分」。

- [ ] **Step 9: Commit**

```bash
git add docs/PCS-UI-SPEC.md TODOS.md
git commit -F <消息文件>
```
首行：`docs(P9B-3): SPEC V2.6 —— §7.20.1 系统参数 + §7.7 物流三节口径 + AI/Prompt 移出 P9B-3`

---

## Task T2.5：`streams.source` 列 + 迁移 `p9_015`（用户裁决 1a）

**位置：** 必须在 **T2 之后**（SPEC 先定义 source 枚举）、**T3 之前**（T6/T7 依赖它）。

**Files:**
- Create: `pcs-backend/alembic/versions/p9_015_stream_source.py`
- Modify: `pcs-backend/app/models/enums.py`（新增 `StreamSource` 枚举，4 值）
- Modify: `pcs-backend/app/models/project.py`（`Stream.source` 列 + CHECK + 复合索引）
- Modify: `pcs-backend/app/schemas/stream.py`（`StreamBase.source` 契约字段）
- Modify: `pcs-backend/app/services/import_service.py`（PRO/II 写 `SIM_IMPORT` / Excel 写 `EXCEL`）
- Modify: `pcs-backend/app/services/outlet_stream.py`（出口流**继承上游**的 `source`）
- Modify: `pcs-backend/app/api/v1/streams.py`（列表端点支持 `?source=` 筛选）
- Test: `pcs-backend/tests/api/v1/test_stream_source.py`

**Interfaces:**
- Consumes: `streams.source_type`（**既有** 13 值 NOT NULL · `ck_streams_source_type`）·
  `StreamBase` · `StreamService.create` / `list_by_project`。
- Produces:
  - `StreamSource` 枚举（4 值：`MANUAL` / `SIM_IMPORT` / `EXCEL` / `LAB`）
  - `streams.source` 列（`VARCHAR(20)` NOT NULL DEFAULT `'MANUAL'` + CHECK
    `ck_streams_source_valid` + 复合索引 `ix_streams_project_source(project_id, source)`）
  - `GET /projects/{project_id}/streams?source=<值>` 筛选

### ⚠️ 与既有 `streams.source_type` 的关系（**先读，否则会把两列混为一谈**）

实测（2026-11-02，`pcs_test` 直查库）：`streams` **已经有** `source_type` 列 ——
`VARCHAR(30)` **NOT NULL** + CHECK `ck_streams_source_type`，**13 值**：
`SIM_IMPORT` / `MANUAL_ENTRY` / `LAB_REPORT` + 10 个 `*_CALCULATED`
（设备计算出口流）。本任务新增的 `source` 是**另一个轴**：

| 列 | 语义 | 取值 | 谁写 |
|---|---|---|---|
| `source`（**新**） | **录入通道**（这条物流怎么进系统的） | 4 值：MANUAL / SIM_IMPORT / EXCEL / LAB | 创建路径（向导 / 导入） |
| `source_type`（既有） | **产出方式**（这条物流的数据怎么算出来的） | 13 值：3 个人工/导入 + 10 个设备计算 | 导入路径 / 设备计算 |

⇒ 两列**正交**，不是同一概念的两种写法；但有 3 处**取值重叠且拼写不同**
（`SIM_IMPORT` 同名 / `MANUAL_ENTRY`↔`MANUAL` / `LAB_REPORT`↔`LAB`）⇒
**这正是「同一概念两份定义 ⇒ 漂移」的温床**（bug-187~191 / bug-2040 同族）⇒
本任务用三条规则钉死（见 Step 3b），并把「长期是否合并两列」登记为未解决问题。

⚠️ **另外两处实测事实**（委员会裁决 1a 的前提未覆盖）：

1. Excel 导入路径当前把 `source_type` 也写成 `SIM_IMPORT`
   （`import_service._excel_preview_entry`）⇒ 新列 `source` 在 Excel 行上写
   `EXCEL` ⇒ **同一行两列取值不同**是**有意的**（`source_type` 词表里没有
   `EXCEL`，本批不扩它）⇒ 登记为未解决问题（是否扩 `source_type` 词表）。
2. 10 个 `*_CALCULATED` 设备计算出口流在 4 值词表里**没有对应值** ⇒ 本批规则：
   **出口流继承其上游物流的 `source`**（`outlet_stream.persist` 有上游 ORM 对象
   ⇒ 直接抄）⇒ 登记为未解决问题（是否加第 5 值 `CALCULATED`）。

- [ ] **Step 1: 写失败测试**

```python
# pcs-backend/tests/api/v1/test_stream_source.py
"""`streams.source` 列（用户裁决 1a · P9B-3 · T2.5）。

## 这一列是什么

SPEC §7.7.1 的物流列表有「来源」列（SIM导入 / 手动 / Excel / 化验）⇒ 后端
得有一个**能筛能显示**的字段承载它。

## ⚠️ 它与既有的 `streams.source_type` **不是同一列**

| 列 | 语义 | 取值 |
|---|---|---|
| `source`（本列） | **录入通道**（怎么进系统的） | 4 值：MANUAL / SIM_IMPORT / EXCEL / LAB |
| `source_type`（既有） | **产出方式**（数据怎么算出来的） | 13 值：SIM_IMPORT / MANUAL_ENTRY / LAB_REPORT + 10 个 `*_CALCULATED` |

⚠️ 两者有 3 处取值重叠但拼写不同（SIM_IMPORT 同名 / MANUAL_ENTRY↔MANUAL /
LAB_REPORT↔LAB）⇒ **防漂移靠本文件末尾的一致性断言**，不是靠「大家记得填对」。

## 4 个取值

| 值 | 含义 | 谁写 |
|---|---|---|
| `MANUAL` | 手动创建向导 | T7 向导 |
| `SIM_IMPORT` | 模拟软件导出（**PRO/II / HYSYS / Aspen 都归它**，用户裁决 1b） | PRO/II 导入路径 |
| `EXCEL` | Excel 双 Sheet 导入 | Excel 导入路径 |
| `LAB` | 化验报告（**预留**，本批无写入路径） | — |
"""
```

断言**七条**（前五条 = 委员会指定）：

1. 创建物流**不传** `source` ⇒ 落库为 `MANUAL`（默认值）；
2. 传 `source='SIM_IMPORT'` ⇒ 落库正确；
3. ⚠️ 传 `source='INVALID'` ⇒ **422** ——
   ⚠️ 注意**是谁拒的**：API 路径上是 **Pydantic 枚举**先拒（`StreamSource`
   枚举 ⇒ `422`）；DB 的 CHECK 约束是**绕过 schema 的写入**（直连 SQL / 脚本）
   的兜底 ⇒ **两条都断言**：
   - API 路径：422（`StreamSource` 枚举）；
   - DB 路径：ORM 声明了 `CheckConstraint("source IN (...)",
     name="ck_streams_source_valid")` ⇒ 单测库（`create_all` 从 ORM metadata
     建表，**不是**迁移产物）里该 CHECK **存在** ⇒ 直写非法值 ⇒ `IntegrityError`。
     ⇒ 这条**不依赖 PG**，SQLite 也真跑（单测的 CHECK 从 ORM 来 ⇒ 存在）。
4. 列表响应带 `source` 字段；
5. `GET /projects/{id}/streams?source=MANUAL` ⇒ 只返回匹配的；
6. ⚠️ **一致性**：PRO/II 导入 ⇒ `source='SIM_IMPORT'` **且**
   `source_type='SIM_IMPORT'`；Excel 导入 ⇒ `source='EXCEL'` **且**
   `source_type='SIM_IMPORT'`（⚠️ **有意不同**，见 T2.5 开头的实测事实 1）；
7. ⚠️ **出口流继承**：`outlet_stream` 造的出口流 ⇒ `source` == 其上游物流的
   `source`（不是默认 `MANUAL`）。

- [ ] **Step 2: 跑测试确认红**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_stream_source.py -v`
Expected: FAIL（列不存在 / 端点不接受 `source` 筛选）。

- [ ] **Step 3: 加枚举 + ORM 列**

```python
# app/models/enums.py
class StreamSource(str, enum.Enum):
    """物流**录入通道** 4 态（`streams.source`，String(20)）。

    ⚠️ **与 `StreamSourceType`（13 值）不是一回事**：
    - 本枚举 = **怎么进系统的**（手动向导 / 模拟软件导出 / Excel 导入 / 化验报告）
    - `StreamSourceType` = **数据怎么算出来的**（3 人工/导入 + 10 个设备计算出口流）

    ⚠️ 两者有 3 处重叠且拼写不同（SIM_IMPORT 同名 / MANUAL_ENTRY↔MANUAL /
    LAB_REPORT↔LAB）⇒ **两列必须由同一处写入**（见
    `import_service` / `outlet_stream` 的映射），并有测试钉住配对关系。
    """

    MANUAL = "MANUAL"
    SIM_IMPORT = "SIM_IMPORT"   # 模拟软件导出（PRO/II · HYSYS · Aspen 都归它）
    EXCEL = "EXCEL"
    LAB = "LAB"                  # 化验报告（预留）
```

`Stream` 模型（`app/models/project.py`）：

```python
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MANUAL",
        server_default="MANUAL",
    )
```

⚠️ **不要用 `index=True`** —— 那会生成 `ix_streams_source`（单列），
与迁移里的复合索引 `ix_streams_project_source` **对不上** ⇒ `alembic check`
报漂移。复合索引必须显式声明在 `__table_args__`：

```python
        CheckConstraint(
            "source IN ('MANUAL','SIM_IMPORT','EXCEL','LAB')",
            name="ck_streams_source_valid",
        ),
        Index("ix_streams_project_source", "project_id", "source"),
```

⚠️ CHECK 约束的**名字与文本**必须与迁移**逐字一致** ⇒ 否则 `alembic check`
报漂移（CLAUDE.md「漂移盲区」）。

- [ ] **Step 3b: 钉死两列的写入规则（防漂移）**

| 写入路径 | `source` | `source_type` |
|---|---|---|
| 手动向导（T7） | `MANUAL` | `MANUAL_ENTRY`（既有必填字段，不动） |
| PRO/II 导入 | `SIM_IMPORT` | `SIM_IMPORT`（既有） |
| Excel 导入 | `EXCEL` | `SIM_IMPORT`（**既有行为，本批不改**） |
| 设备计算出口流 | **继承上游的 `source`** | `*_CALCULATED`（既有，不动） |
| 化验报告（本批无路径） | `LAB` | `LAB_REPORT` |

⇒ **两列在每个写入点成对赋值**（不是一个可选项）⇒ 测试断言 6/7 钉住。

- [ ] **Step 4: 写迁移 `p9_015`**

```python
"""给 `streams` 加 `source` 列（SPEC §7.7.1「来源」· P9B-3 · T2.5 · 用户裁决 1a）。

## 为什么

SPEC §7.7.1 的物流列表有「来源」列（SIM导入 / 手动 / Excel / 化验）——
后端此前**没有**承载它的字段（`data_mode` 是「数据模式」CHEMICAL/PETROLEUM/SOLID，
**不是**来源）⇒ 前端要么画一列假的，要么不画。

## ⚠️ 与既有 `streams.source_type` 的关系（别混）

- `source`（本列）= **录入通道**（怎么进系统的），4 值
- `source_type`（既有）= **产出方式**（数据怎么算出来的），13 值
  （3 人工/导入 + 10 个 `*_CALCULATED` 设备计算出口流）

两列正交；Excel 行上 `source='EXCEL'` 而 `source_type='SIM_IMPORT'` 是**有意的**
（`source_type` 词表里没有 EXCEL，本批不扩它）⇒ 已登记为未解决问题。

## 列形状（与 ORM `Stream.source` 一致）

`VARCHAR(20) / NOT NULL / DEFAULT 'MANUAL'`：存量行默认 MANUAL
（存量都是早期建的，无录入通道信息 ⇒ 默认「手动」是最诚实的近似）。

⚠️ 改迁移 ⇒ 必须验「迁移与 ORM 一致」（每库各一次，独立进程 + 直查库）。
"""

revision = "p9_015"
down_revision = "p9_014"
```

`upgrade()`：

```python
    op.add_column(
        "streams",
        sa.Column("source", sa.String(20), nullable=False, server_default="MANUAL"),
    )
    op.create_check_constraint(
        "ck_streams_source_valid", "streams",
        "source IN ('MANUAL','SIM_IMPORT','EXCEL','LAB')",
    )
    op.create_index("ix_streams_project_source", "streams", ["project_id", "source"])
```

`downgrade()`：三个反向操作（drop index → drop constraint → drop column）。

- [ ] **Step 5: schema + 写入路径 + 筛选**

- `app/schemas/stream.py`：`StreamBase.source: StreamSource = Field(default=StreamSource.MANUAL)`
  ⇒ 「不传 ⇒ MANUAL」由**契约层**兜住（不靠 service 默认值）；
  ⚠️ `StreamBase` 是 `StreamCreate` / `StreamResponse` 的共同基类 ⇒ 加在这里，
  响应自动带 `source`（测试 4）；`StreamUpdate` **不加** `source`
  （来源是录入通道，创建后不改 ⇒ 免掉一处可漂移的写入面）；
- `app/services/import_service.py`：`_proii_preview_entry` 加
  `"source": "SIM_IMPORT"`；`_excel_preview_entry` 加 `"source": "EXCEL"`
  （preview entry 直接喂 `StreamCreate(**entry)` ⇒ 契约层收下）；
- `app/services/outlet_stream.py`：出口流 `source=source.source`（继承上游）；
- `app/api/v1/streams.py`：`list_project_streams` 加
  `source: StreamSource | None = Query(None)` ⇒ `StreamService.list_by_project`
  加同名可选参数并 `.where(Stream.source == source)`。

⚠️ **顺带补齐另两个筛选**（计划自洽性 · 复审未覆盖）：T6 的断言是「工况 / 相态 /
状态 / 来源**四项**筛选都带 query 参数重新请求」，但后端列表端点**实测只支持
`case_type`**（`phase` / `sign_status` 无筛选参数）⇒ 前端发的 query 会被静默忽略
⇒ 断言必红。⇒ 本步一并加：
`phase: StreamPhase | None = Query(None)` 与
`sign_status: StreamSignStatus | None = Query(None)`
（`StreamService.list_by_project` 同步加可选参数 + `.where`）⇒ **三个都可选、
可组合**（AND 关系）。

⚠️ `sign_status` 走 `ix_streams_sign_status` 索引（既有）⇒ 无需新索引；
`phase` 无索引（本批量级下全表扫可接受 ⇒ 登记为潜在性能债，见未解决问题第 12 条）。

- [ ] **Step 6: 跑测试 + 迁移自检**

```bash
cd pcs-backend && uv run pytest tests/api/v1/test_stream_source.py -v
# ⚠️ 改了迁移 ⇒ 必须验「迁移与 ORM 一致」（每库各一次，独立进程 + 直查库）
```

⚠️ **ORM 与迁移的 CHECK 名字/文本、索引名必须逐字一致** ⇒ 否则 `alembic check`
报漂移（CLAUDE.md「漂移盲区」）。⚠️ `alembic check` 退出码是 **255** 不是 1。

- [ ] **Step 7: Commit**

```bash
git add pcs-backend/alembic/versions/p9_015_stream_source.py pcs-backend/app/models/enums.py \
        pcs-backend/app/models/project.py pcs-backend/app/schemas/stream.py \
        pcs-backend/app/services/import_service.py pcs-backend/app/services/outlet_stream.py \
        pcs-backend/app/api/v1/streams.py pcs-backend/tests/api/v1/test_stream_source.py
git commit -F <消息文件>
```
首行：`feat(P9B-3): streams.source 列（4 值录入通道 + 迁移 p9_015）`

---

## Task T3：物流组成合计校验（后端门禁）

**Files:**
- Modify: `pcs-backend/app/api/v1/streams.py`（submit 前校验）
- Modify: `pcs-backend/app/models/enums.py`（新错误码进 `PcsError` 的 code 字符串即可，无需枚举）
- Test: `pcs-backend/tests/api/v1/test_stream_composition_sum.py`（新建）

**Interfaces:**
- Consumes: `Stream.composition_json`（JSONB，NOT NULL）；SPEC §7.7.2「底部合计校验（100±0.5%）」。
- Produces: 错误码 `SIM_STREAM_COMPOSITION_OUT_OF_RANGE`（422）。

- [ ] **Step 1: 写失败测试**

```python
# pcs-backend/tests/api/v1/test_stream_composition_sum.py
"""物流组成合计校验（SPEC §7.7.2「底部合计校验（100±0.5%）」）。

## 为什么这是**新增**而不是复用

⚠️ 实测（2026-11-02）：全仓 `grep -rn "COMPOSITION"` = 0 命中 ⇒
「组成合计」这条校验**根本不存在** ⇒ 委员会 brief 里假设的失败原因
`COMPOSITION_SUM_OUT_OF_RANGE` 需要**新建**（不是复用既有的）。

## 为什么校验挂在**送审**上

物流的组成不合法却进了校对 ⇒ 校对人在 Tab「组成」里看到合计 98.7%
却已经被要求签字 ⇒ 门禁必须**前置**（SPEC §5.1「门禁前置」）⇒ 挂在
`POST /streams/{id}/submit`（DRAFT → IN_APPROVAL）之前。
"""
```

断言两条：
1. 组成摩尔分率合计 = 0.987 ⇒ submit ⇒ **422** `SIM_STREAM_COMPOSITION_OUT_OF_RANGE`，
   且 `sign_status` **不变**（仍 DRAFT）；
2. 合计 = 1.0 ⇒ submit ⇒ **200**（或至少不是该错误码）。

- [ ] **Step 2: 跑测试确认红**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_stream_composition_sum.py -v`
Expected: FAIL（现在放行）。

- [ ] **Step 3: 实现校验**

在 `streams.py` 的 `submit_stream` 里，进入 `_transition_endpoint` **之前**：

```python
    # ⚠️ 组成合计门禁（SPEC §7.7.2「100±0.5%」）—— 送审**前**校验，
    #    不合法不放进校对（门禁前置，SPEC §5.1）。
    total = _composition_mole_fraction_total(stream)
    if total is not None and abs(total - 100.0) > 0.5:
        raise PcsError(
            code="SIM_STREAM_COMPOSITION_OUT_OF_RANGE",
            message=(
                f"物流 {stream_id} 的组成摩尔分率合计 {total:.2f}%，"
                "不在 100±0.5% 内 ⇒ 不能提交校对"
            ),
            status=422,
        )
```

`_composition_mole_fraction_total` 的口径（**已按实测钉死**，不再是待裁决项）：

- `composition_json` 是 **`{CAS 号: 摩尔分率}` 字典**（`app/schemas/stream.py:331`
  「总组成 CAS→摩尔分率」；`flash_persist._extract_composition` 取 `comp[c]` 当
  `zs` 喂给闪蒸计算器 ⇒ **值域 0~1 的小数**，不是百分数）；
- 合计 = `sum(float(v) for v in composition_json.values())`；
- 判定 `abs(total - 1.0) > 0.005`（≡ SPEC §7.7.2 的「100±0.5%」）；
- 错误消息里**同时给百分比**：`合计 {total * 100:.2f}%`；
- ⚠️ **空 composition 的区分（P2-1）**：

| `composition_json` | 行为 | 理由 |
|---|---|---|
| `None` | **跳过校验** | 纯物质物流（无组成是合法场景） |
| `{}` | **拒绝**（422，同一错误码） | 未填写（用户忘了填）⇒ 空对象 ≠ 无组成 |
| 有内容 | 校验 `\|sum−1\| ≤ 0.005` | 正常 |

⇒ SPEC §7.7.2 补一句：「纯物质物流可以无组成（`composition_json = null`）；
空对象 `{}` 视为未填写，拒绝提交。」

- [ ] **Step 4: 跑测试确认绿 + 跑既有 streams 套件防回归**

Run: `cd pcs-backend && uv run pytest tests/api/v1/ -k stream -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add pcs-backend/app/api/v1/streams.py pcs-backend/tests/api/v1/test_stream_composition_sum.py
git commit -F <消息文件>
```
首行：`feat(P9B-3): 物流组成合计门禁（送审前置，100±0.5%）`

---

## Task T4：系统参数后端（service + router + 批量原子写）

**Files:**
- Create: `pcs-backend/app/schemas/system_settings.py`
- Create: `pcs-backend/app/services/system_setting_service.py`
- Create: `pcs-backend/app/api/v1/system_settings.py`
- Modify: `pcs-backend/app/models/enums.py`（`AuditAction` 加 `SYSTEM_SETTINGS_UPDATED`）
- Modify: `pcs-backend/app/api/v1/__init__.py`（挂 router）
- Modify: `pcs-backend/app/main.py`（**启动钩子**调 `seed_defaults` —— 实测位置
  `app/main.py:59`，与 `CoefficientService.seed_default_tables` 同处）
- Modify: `pcs-backend/docs/openapi.json`（契约重滚，生成物）
- Test: `pcs-backend/tests/api/v1/test_system_settings.py`

**Interfaces:**
- Consumes: `app.models.system.SystemSetting`（已存在）；`AuditService.write`。
- Produces:
  - `GET /api/v1/system-settings` ⇒ `list[SystemSettingOut]`
  - `PUT /api/v1/system-settings` ⇒ `SystemSettingBatchOut`
  - `SystemSettingOut = {setting_key: str, setting_value_json: Any, description: str | None, updated_at: datetime}`
  - `SystemSettingBatchIn = {settings: dict[str, Any]}`
  - `SystemSettingBatchOut = {updated: list[SystemSettingOut]}`
  - `seed_defaults(db)` —— **幂等**写入 7 项默认键（见 Step 4b）
  - 错误码：`HTTP_403`（非 SYSTEM_ADMIN）/ `SYSTEM_SETTING_NOT_FOUND`（404，改不存在的键）

- [ ] **Step 1: 写失败测试**

```python
# pcs-backend/tests/api/v1/test_system_settings.py
"""系统参数 CRUD（§7.20.1 · P9B-3 · T4）。

## 硬约束：批量 + **原子**

委员会 2026-11-02 裁决「硬约束 1」：系统参数页一次改多个参数 ⇒
**一次 PUT**（body 是 `{key: value}` 的 map）⇒ 事务内**要么全改、要么全不改**。
⚠️ 不做「每个键一个 PATCH」—— 那会让「保存」变成 N 个请求且中途失败留半改状态。
⇒ 本文件的核心断言就是**原子性**：一个键非法 ⇒ **一个键都不改**。
"""
```

断言三条：
1. `GET /system-settings`（SYSTEM_ADMIN）⇒ 200 + 列表；非 SYSTEM_ADMIN ⇒ 403。
2. `PUT` 两个键都合法 ⇒ 200 + 两个键都变了 + **一条** `SYSTEM_SETTINGS_UPDATED` 审计。
3. ⚠️ **原子性**：`PUT` 里塞一个**不存在的键** ⇒ 404 `SYSTEM_SETTING_NOT_FOUND`
   ⇒ 且**另一个合法键的值没变**（直查 DB 断言）。

- [ ] **Step 2: 跑测试确认红**（404 —— 端点不存在）

- [ ] **Step 3: 写 schema**

```python
# pcs-backend/app/schemas/system_settings.py
"""系统参数（§7.20.1）。

⚠️ `system_settings` 是**已存在的表**（`app/models/system.py`），此前**零 API**
⇒ 本文件是它的**第一个**对外形状 ⇒ 「表存在」≠「API 存在」（核实 4）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SystemSettingOut(BaseModel):
    """一条系统参数。"""

    model_config = ConfigDict(from_attributes=True)

    setting_key: str
    setting_value_json: Any
    description: str | None = None
    updated_at: datetime


class SystemSettingBatchIn(BaseModel):
    """批量保存的请求体 —— **一次 PUT 提交全部改动**（硬约束 1）。"""

    settings: dict[str, Any] = Field(description="setting_key → 新值；整批原子提交")


class SystemSettingBatchOut(BaseModel):
    """批量保存的结果。"""

    updated: list[SystemSettingOut]
```

- [ ] **Step 4b: 加 7 项默认键的幂等 seed（P1-1）**

⚠️ `system_settings` **真库 0 行** ⇒ 不 seed 的话管理员打开页面**一片空白**
（「没有参数可改」与「参数加载失败」看起来一样）⇒ 启动时幂等 seed：

```python
# app/services/system_setting_service.py
DEFAULT_SETTINGS: list[dict] = [
    {"key": "session.timeout_minutes",      "value": 30,    "description": "会话超时（分钟）"},
    {"key": "notification.retention_days",  "value": 30,    "description": "已读通知保留天数"},
    {"key": "edit_lock.ttl_minutes",        "value": 30,    "description": "编辑锁有效期（分钟）"},
    {"key": "edit_lock.renew_enabled",      "value": True,  "description": "编辑锁自动续期"},
    {"key": "record.self_check_allowed",    "value": False, "description": "是否允许设计兼任校核"},
    {"key": "equip_list.auto_sync_enabled", "value": True,  "description": "CHECKED 触发设备表同步"},
    {"key": "stream.batch_submit_limit",    "value": 100,   "description": "物流批量提交上限（P9B-3b 用）"},
]


async def seed_defaults(db: AsyncSession) -> None:
    """幂等：缺失则写入，存在则跳过（**不覆盖**管理员改过的值）。"""
```

⚠️ 第 7 项 `stream.batch_submit_limit` 在**本批无消费者**（批量提交在 P9B-3b）——
提前 seed 比 P9B-3b 再补省事（seed 幂等 ⇒ 多一个键零成本）⇒ 但 **T5 的页面上必须
能编辑它**（否则管理员看到「有配置但改不了」会困惑）。

调用位置：`app/main.py` 的启动钩子（与 `CoefficientService.seed_default_tables`
同位置）⇒ **只插缺失的键**，已存在的**不覆盖**。

测试（加到 `test_system_settings.py`）：

```python
async def test_seed_is_idempotent(db_session):
    """启动两次 ⇒ 不多写行、且**不覆盖**管理员改过的值。"""
    await seed_defaults(db_session)
    await db_session.commit()
    await db_session.execute(
        update(SystemSetting)
        .where(SystemSetting.setting_key == "session.timeout_minutes")
        .values(setting_value_json={"v": 999})
    )
    await db_session.commit()
    await seed_defaults(db_session)
    await db_session.commit()
    rows = (await db_session.execute(select(SystemSetting))).scalars().all()
    assert len(rows) == len(DEFAULT_SETTINGS), "重复 seed 写出了重复行"
    kept = next(r for r in rows if r.setting_key == "session.timeout_minutes")
    assert kept.setting_value_json == {"v": 999}, "seed 覆盖了管理员改过的值"
```

- [ ] **Step 4: 写 service（原子写）**

```python
# pcs-backend/app/services/system_setting_service.py
"""系统参数读写（§7.20.1 · T4）。

⚠️ **原子性**（委员会硬约束 1）：批量保存是**一次事务** ⇒ 任一键失败 ⇒
**全部不落** ⇒ 不留「半改」状态。实现上：先校验全部键存在，再一次性写。

⚠️ **已知限制（P2-3）**：系统参数**只能改已有键的值，不能新增键**。新增键需要
改代码（`DEFAULT_SETTINGS` 清单）+ 重启（或迁移）。理由：允许管理员新增键会导致
键名拼写错误污染表 —— **键的集合由开发者控制，值由管理员控制**。
（同一条限制写进 SPEC §7.20.1。）
"""
```

`list_all(db) -> list[SystemSetting]` 与
`update_batch(db, values: dict[str, Any], *, actor_user_id) -> list[SystemSetting]`：

- 先 `SELECT ... WHERE setting_key IN (...)` 取全部目标行；
- **缺任何一个键 ⇒ 抛 `PcsError(code="SYSTEM_SETTING_NOT_FOUND", status=404)`**
  （**在任何写入之前** ⇒ 天然原子）；
- 全部命中 ⇒ 逐个赋值 + **一次** `db.flush()` + **一次** `AuditService.write`
  （`action=AuditAction.SYSTEM_SETTINGS_UPDATED`，`detail={"keys": [...], "before": {...}}`）。

- [ ] **Step 5: 写 router**

```python
# pcs-backend/app/api/v1/system_settings.py
"""系统参数端点（§7.20.1）。

⚠️ **批量 + 原子**：`PUT /system-settings` 一次提交全部改动，事务内全改或全不改。
"""
```

- `GET ""` ⇒ `require_roles(user, "SYSTEM_ADMIN")` ⇒ `list_all`
- `PUT ""` ⇒ 同上 ⇒ `update_batch` ⇒ 提交 ⇒ 返回 `SystemSettingBatchOut`

⚠️ `AuditAction` 枚举**要加** `SYSTEM_SETTINGS_UPDATED = "SYSTEM_SETTINGS_UPDATED"`
（`app/models/enums.py`，与 `CONFIG_*` 一族同处）。

- [ ] **Step 6: 挂 router**（`app/api/v1/__init__.py`，与其它 router 同款）

- [ ] **Step 7: 跑测试确认绿 + 重滚契约**

```bash
cd pcs-backend && uv run pytest tests/api/v1/test_system_settings.py -v
cd /home/pangzy/code_project/PCS && bash pcs-backend/scripts/gate_08_openapi_contract.sh
```
Expected: 3 passed；契约重滚无漂移。

- [ ] **Step 8: Commit**

```bash
git add pcs-backend/app/schemas/system_settings.py pcs-backend/app/services/system_setting_service.py \
        pcs-backend/app/api/v1/system_settings.py pcs-backend/app/api/v1/__init__.py \
        pcs-backend/app/main.py pcs-backend/app/models/enums.py \
        pcs-backend/docs/openapi.json pcs-backend/tests/api/v1/test_system_settings.py
git commit -F <消息文件>
```
首行：`feat(P9B-3): 系统参数后端（批量原子 PUT + 审计）`

---

## Task T5：系统参数前端页

**Files:**
- Create: `pcs-frontend/src/api/systemSettings.ts`
- Create: `pcs-frontend/src/pages/admin/SystemSettingsPage.tsx`
- Modify: `pcs-frontend/src/App.tsx`（路由 + 菜单）
- Modify: `pcs-frontend/src/types/api.d.ts`（生成物）
- Test: `pcs-frontend/tests/pages/admin/systemSettings.test.tsx`

**Interfaces:**
- Consumes: T4 的 `GET/PUT /api/v1/system-settings`（契约类型
  `components['schemas']['SystemSettingOut']` / `SystemSettingBatchOut`）。
- Produces: 路由 `/admin/system-settings`；`systemSettingsApi.list()` / `.save(values)`。

- [ ] **Step 1: 写失败测试**（vitest + MSW）

```tsx
/**
 * 系统参数页（§7.20.1 · P9B-3 · T5）。
 *
 * ⚠️ **一次保存 = 一个 PUT**（硬约束 1）—— 测试要钉住「保存只发一个请求」，
 * 否则前端改成逐键 PATCH 时测试不会红，而那正是委员会禁止的形状。
 */
```

断言三条：
1. 页面渲染出参数行（键 + 值），值取自 mock；
2. ⚠️ 改两个参数后点「保存」⇒ **只发一个** `PUT /system-settings`，
   body 的 `settings` 含两个键；
3. PUT 失败（500）⇒ 页面显示错误，**不**显示「已保存」。

- [ ] **Step 2: 跑测试确认红**（页面不存在）

- [ ] **Step 3: 写 api 客户端**

```ts
// pcs-frontend/src/api/systemSettings.ts
/**
 * 系统参数客户端（§7.20.1 · P9B-3）。
 *
 * ⚠️ 类型**契约派生**（`components['schemas'][...]`）—— 不手写 union
 * （手写 = 与后端脱钩 = bug-2040 那类漂移根因）。
 *
 * ⚠️ `save()` **一次 PUT 提交全部改动**（委员会硬约束 1）—— 不做逐键 PATCH。
 */
import { api } from './client';
import type { components } from '../types/api';

export type SystemSettingOut = components['schemas']['SystemSettingOut'];
export type SystemSettingBatchOut = components['schemas']['SystemSettingBatchOut'];

export const systemSettingsApi = {
  list: (): Promise<SystemSettingOut[]> =>
    api.get<SystemSettingOut[]>('/system-settings').then((r) => r.data),

  save: (settings: Record<string, unknown>): Promise<SystemSettingBatchOut> =>
    api
      .put<SystemSettingBatchOut>('/system-settings', { settings })
      .then((r) => r.data),
};
```

- [ ] **Step 4: 写页面**

`src/pages/admin/SystemSettingsPage.tsx`：从 `systemSettingsApi.list()` 拉列表 ⇒
渲染成表单（每行一个键 + 一个 JSON 值输入）⇒ 「保存」按钮**一次**调
`systemSettingsApi.save(changed)` ⇒ 成功提示 / 失败提示。

⚠️ 值是 JSONB ⇒ 输入框给 **JSON 文本**，保存前 `JSON.parse` ⇒ 解析失败就**就地报错**
（不发请求）—— 解析失败不是后端的错。

- [ ] **Step 5: 挂路由 + 菜单**（`src/App.tsx`，与 `/admin/users` 同款）

⚠️ 菜单项仅 **SYSTEM_ADMIN** 可见（与 `/admin/users` / `/admin/projects` 同口径）。

- [ ] **Step 6: 跑测试 + typecheck + lint**

```bash
cd pcs-frontend && npx vitest run tests/pages/admin/systemSettings.test.tsx && npm run typecheck && npm run lint
```
Expected: PASS / clean / clean。

- [ ] **Step 7: Commit**

```bash
git add pcs-frontend/src/api/systemSettings.ts pcs-frontend/src/pages/admin/SystemSettingsPage.tsx \
        pcs-frontend/src/App.tsx pcs-frontend/src/types/api.d.ts \
        pcs-frontend/tests/pages/admin/systemSettings.test.tsx
git commit -F <消息文件>
```
首行：`feat(P9B-3): 系统参数页（一次保存 = 一个 PUT）`

---

## Task T6：SIM 物流列表页（工具栏 / 筛选 / 引用列 / 行操作）

**Files:**
- Modify: `pcs-frontend/src/api/stream.ts`（契约派生类型 + 端点封装）
- Modify: `pcs-frontend/src/pages/sim/StreamListPage.tsx`（重写）
- Test: `pcs-frontend/tests/pages/sim/streamList.test.tsx`（新建）

**Interfaces:**
- Consumes: `GET /api/v1/projects/{project_id}/streams`（既有）；`POST /streams/{id}/submit`（既有，T6 用它做**单条**提交校对）。
- Produces: `streamApi.list(projectId)`（**契约派生**类型）、`streamApi.submitForReview(id)`。

- [ ] **Step 1: 写失败测试**

断言四条：
1. 工具栏出现 **导入 / 新建物流 / 导出** 三个按钮（**没有**「批量提交校对」——
   批量在 P9B-3b，SPEC §7.7.1 的工具栏批量口径由 T2 登记）；
2. 筛选有 **工况 / 相态 / 状态 / 来源** 四项，且改了筛选会重新请求（带 query 参数），
   ⚠️ 其中「来源」带的参数是 `source=<4 值之一>`（T2.5 的后端筛选）；
3. 行操作有 **查看 / 校对 / 变更** 三个入口；
4. ⚠️ 点行「校对」⇒ 调 `POST /streams/{id}/submit` ⇒ 成功后该行状态徽章变
   `IN_APPROVAL`；失败（403）⇒ 显示错误**且状态不变**；
5. ⚠️ **未知 `sign_status`**（mock 返回 `"SOMETHING_NEW"`）⇒ 列表**照常渲染**
   （StateBadge 的未知态兜底），不是整页崩（Review Focus 第 2 条）。

- [ ] **Step 2: 跑测试确认红**

- [ ] **Step 3: api 客户端改成契约派生**

```ts
// pcs-frontend/src/api/stream.ts（重写）
/**
 * SIM 物流 API 客户端（P9B-3 · T6/T7/T8 扩展）。
 *
 * ⚠️ 类型**契约派生** —— 此前是手写的 `StreamListItem`（5 字段）⇒ 与契约脱钩
 * （backend `StreamListItem` 实际有几十个字段）⇒ 后端加字段前端静默丢。
 * ⇒ 本批改成 `components['schemas'][...]`，并新增 submit / properties /
 * state-points 三个端点封装。
 */
```

⚠️ **列表响应是否带 `reference_count`**（SPEC §7.7.1「引用 📎×N」）——
后端**当前不返回**该字段 ⇒ 见「尚未解决的问题」第 1 条。
⇒ **本批先不渲染引用列**，等口径定下再补（T2 已登记）。

⚠️ **`listByProject` 这个名字必须保留** —— `VesselComputePage.tsx:127` 在用它
（OPEN-4-1：没注入 streams 时走 `streamApi.listByProject` 自取）⇒ 改名会破坏
那个页面。本批只把它**返回类型**换成契约派生，**不动名字**。

✅ **「来源」列与「来源」筛选本批做** —— 数据源由 **T2.5** 提供
（`streams.source` 新列 · 4 值：MANUAL / SIM_IMPORT / EXCEL / LAB ·
后端支持 `?source=` 筛选）⇒ 前端**契约派生**该枚举，不手写 union。

⚠️ **只显示 `source`（4 值），不显示 `source_type`（13 值）** ——
后者是「产出方式」（含 10 个 `*_CALCULATED` 设备计算出口流），塞进一列会爆。
⚠️ 两列**正交但取值重叠**（`source_type` 已在既有契约里）⇒ 前端**只消费
`source`** ⇒ 列表列不出现 13 值的来源。

- [ ] **Step 4: 重写 StreamListPage**

列（SPEC §7.7.1）：物流号（等宽）· 名称 · 工况 · 相态 · 温度 · 压力 ·
质量流量 · 状态（StateBadge）· 来源 · 操作。
筛选：工况 / 相态 / 状态 / 来源（来源 = `source` 4 值枚举 ⇒ 用 Select；
取值来自**契约派生**的 `StreamSource`，不手写）。
工具栏：导入 / 新建物流 / 导出。

⚠️ 「新建物流」⇒ 跳 **T7** 的手动创建向导（路由 `/sim/streams/new`）。

- [ ] **Step 5: 跑测试 + typecheck + lint**

- [ ] **Step 6: Commit**

```bash
git add pcs-frontend/src/api/stream.ts pcs-frontend/src/pages/sim/StreamListPage.tsx \
        pcs-frontend/tests/pages/sim/streamList.test.tsx
git commit -F <消息文件>
```
首行：`feat(P9B-3): 物流列表页 —— 工具栏 / 四项筛选 / 单条提交校对`

---

## Task T7：物流手动创建向导

**Files:**
- Create: `pcs-frontend/src/pages/sim/StreamManualWizardPage.tsx`
- Modify: `pcs-frontend/src/App.tsx`（路由 `/sim/streams/new`）
- Modify: `pcs-frontend/src/api/stream.ts`（`create` / `validate` 封装）
- Test: `pcs-frontend/tests/pages/sim/streamManualWizard.test.tsx`（新建）

**Interfaces:**
- Consumes: `POST /api/v1/streams`（既有，`StreamCreate`）· `POST /streams/validate`（既有）。
- Produces: 路由 `/sim/streams/new`；向导写完跳回列表。

- [ ] **Step 1: 写失败测试**

断言四条：
1. 向导是 **多步**（不是一行表单）：基本信息 → 组成 → 物性 → 状态点 → 校验 → 写入 → 提交；
2. 「校验」步调 `POST /streams/validate` ⇒ 通过项绿 / 警告项黄 / 错误项红
   （SPEC §7.7.3「校验结果」）；
3. ⚠️ **校验有红项 ⇒ 「写入 DRAFT」按钮禁用**（阻断项必须处理，SPEC §7.7.3）；
4. 「写入 DRAFT」⇒ `POST /streams` ⇒ 成功 ⇒ 跳回列表；失败 ⇒ 显示错误；
5. ⚠️ **物性估算失败 ⇒ 提示 + 仍可继续提交校对**（用户裁决 2：估算不阻塞）。

- [ ] **Step 2: 跑测试确认红**

- [ ] **Step 3: 写向导页**

⚠️ **不**塞进 `ImportWizardPage`（那是**导入**专用，105 行；混进去会让它超 800 行
上限，且「导入」与「新建」是两种心智）⇒ 新建独立页 `StreamManualWizardPage.tsx`。

步骤与字段（SPEC §7.7.3 的「手工」分支裁剪版 —— 手工没有「上传文件」也没有
「Excel 列映射」）：

| 步 | 内容 | 后端 |
|---|---|---|
| 1 基本信息 | 物流号 / 名称 / 描述 / 相态 / 工况 / 项目 / 工作区（**来源不暴露**：固定 `MANUAL`，用户裁决 2） | `StreamCreate` 必填字段（`source` 省略 ⇒ 默认 `MANUAL`） |
| 2 组成 | 组分名 / 分子式 / 摩尔分率 / 质量分率 / 体积分率 + **底部合计校验（100±0.5%）** | `composition_json` |
| 3 状态点 | 标签 / 类型 / 温压 / 相态 / 汽化分率 | `state_points` |
| 4 校验 | 绿 / 黄 / 红 三色 | `POST /streams/validate` |
| 5 写入 DRAFT | 调 `POST /streams` ⇒ 得 `stream_id` | — |
| 6 物性估算 | 调 `POST /streams/{id}/properties/estimate` | ⚠️ **失败 ⇒ 提示 + 允许继续**（不阻塞） |
| 7 提交校对 | 调 `POST /streams/{id}/submit` ⇒ DRAFT → IN_APPROVAL | — |

⚠️ **顺序（用户裁决 2）**：校验 → 写入 → 估算 → 提交。估算排在写入之后（估算要
`stream_id`），且**失败不阻塞后续提交**（物性估算是增强，不是门禁）。
⇒ T7 加一条测试：「物性估算失败 ⇒ 提示 + 仍可继续提交校对」。

- [ ] **Step 4: 跑测试 + typecheck + lint**

- [ ] **Step 5: Commit**

```bash
git add pcs-frontend/src/pages/sim/StreamManualWizardPage.tsx pcs-frontend/src/App.tsx \
        pcs-frontend/src/api/stream.ts pcs-frontend/tests/pages/sim/streamManualWizard.test.tsx
git commit -F <消息文件>
```
首行：`feat(P9B-3): 物流手动创建向导（7 步 · 校验阻断 + 写入 DRAFT + 提交校对）`

---

## Task T8：物流详情页 7 Tab + 校核记录

**Files:**
- Modify: `pcs-frontend/src/pages/sim/StreamDetailPage.tsx`（改成 Tab 宿主）
- Create: `pcs-frontend/src/pages/sim/tabs/StreamBasicTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamCompositionTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamPropertiesTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamStatePointsTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamConnectionsTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamLineageTab.tsx`
- Create: `pcs-frontend/src/pages/sim/tabs/StreamReviewLogTab.tsx`
- Modify: `pcs-frontend/src/api/stream.ts`（properties / state-points / lineage / audit 封装）
- Test: `pcs-frontend/tests/pages/sim/streamDetailTabs.test.tsx`（新建）

**Interfaces:**
- Consumes（**全部已存在**，本 task 不需要新后端端点）：
  - `GET /streams/{id}/properties` · `GET /streams/{id}/state-points`
  - `GET /lineage/{record_type}/{record_id}/graph`（`record_type` = `streams`）
  - `GET /audit-logs?resource_type=streams&resource_id={id}&action=RECORD_TRANSITION`
- Produces: 7 个 Tab 组件（各 ≤ 150 行）。

- [ ] **Step 1: 写失败测试**

断言三条：
1. 7 个 Tab **都在**（label 逐个断言）：基本信息 / 组成 / 物性 / 状态点 / 设备连接 /
   血缘 / 校核记录；
2. ⚠️ **校核记录 Tab** 调 `GET /audit-logs` 且带 `resource_type=streams` +
   `resource_id=<id>` ⇒ 只显示**校对相关**的行（`detail.transition` ∈
   {SUBMIT_FOR_CHECK, PASS_CHECK, REJECT_CHECK}）⇒ 断言**其它 transition 不出现**；
3. **组成 Tab** 底部显示合计 + 超出 100±0.5% 时**标红**（T3 的门禁在前端也要看得见）。

- [ ] **Step 2: 跑测试确认红**

- [ ] **Step 3: 拆成 7 个子组件**

⚠️ `StreamDetailPage.tsx` 现有 266 行、两个 Card ⇒ 改成 **Tab 宿主**（只管
`Tabs` + 数据加载 + 状态），内容全部下沉到 `tabs/` 下 7 个文件 ⇒ 每个 ≤ 150 行
（`docs/TODOS.md` TODO-098 同类拆分口径）。

- [ ] **Step 4: 校核记录 Tab 的过滤逻辑**

```ts
// ⚠️ 审计行的 action 是 `RECORD_TRANSITION`（与记录侧**同构**，不新造动作）
// ⇒ 过滤靠 detail_json.transition，而不是新动作名。
const REVIEW_TRANSITIONS = ['SUBMIT_FOR_CHECK', 'PASS_CHECK', 'REJECT_CHECK'];
const rows = audit.rows.filter((r) => REVIEW_TRANSITIONS.includes(r.detail_json?.transition));
```

⚠️ `audit_logs.detail_json` 在 OpenAPI 里是 `object`（任意）⇒ 前端要**防御性**读
（`r.detail_json?.transition`），不能假设它存在。

- [ ] **Step 4b: 登记「校核记录后端过滤」技术债（P2-2）**

本批**保持前端过滤**（`GET /audit-logs?...&action=RECORD_TRANSITION` 返回该物流的
全部状态转移，前端按 `detail_json.transition` 筛出校对相关的三条）⇒ 在
`TODOS.md` 登记（编号接 104）：

```markdown
### TODO-104: 校核记录的后端过滤

**现状**：`GET /audit-logs?...&action=RECORD_TRANSITION` 返回该物流的全部状态转移，
前端按 `detail_json.transition` 过滤出校核相关的三条。

**为什么本批不做**：当前一个物流平均 5–10 次状态转移，前端过滤可接受。

**触发条件**：状态转移次数显著增长（如 > 50 次/物流），或校核记录 Tab 加载变慢。

**方案**：`audit_logs.detail_json` 加 GIN 索引，或表达式索引
`(detail_json->>'transition')`。

**归属**：P9B-4 或独立技术债。
```

- [ ] **Step 5: 跑测试 + typecheck + lint + 全量前端测试**

- [ ] **Step 6: Commit**

```bash
git add pcs-frontend/src/pages/sim/StreamDetailPage.tsx pcs-frontend/src/pages/sim/tabs/ \
        pcs-frontend/src/api/stream.ts pcs-frontend/tests/pages/sim/streamDetailTabs.test.tsx
git commit -F <消息文件>
```
首行：`feat(P9B-3): 物流详情页 7 Tab（含校核记录 · 读 audit_logs）`

---

## Task T9：QA gate + 收口

**Files:**
- Create: `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-XX-p9b3.md`（gitignored）
- Modify: `TODOS.md`（本批结项）
- Modify: `.wolf/STATUS.md`（下一 quest）

- [ ] **Step 1: 后端全量**（先起 Redis）

```bash
cd pcs-backend && docker compose up -d redis && uv run pytest -q
```
⚠️ **别信 `pytest | tail` 的退出码**（管道会吃掉）⇒ 看文本结果行。

- [ ] **Step 2: PG 车道**（T0 的唯一入口）

```bash
cd pcs-backend && bash scripts/pytest_pg.sh
```
Expected: 退出 0 且输出含 `N passed`（N ≥ 1）。

- [ ] **Step 3: 前端全量**

```bash
cd pcs-frontend && npm run typecheck && npm run lint && npm run test
```

- [ ] **Step 4: 契约门禁（批末）**

```bash
cd /home/pangzy/code_project/PCS
cp pcs-backend/docs/openapi.json pcs-backend/docs/openapi-baseline.json
bash pcs-backend/scripts/gate_08_openapi_contract.sh --check-baseline
```

- [ ] **Step 5: 两库 + 一条车道（P2-5：不是「三库」）**

| 目标 | 验什么 | 怎么验 |
|---|---|---|
| `pcs`（开发库） | 迁移与 ORM 一致 | `alembic check` exit 0 —— **独立进程** + 直查 `alembic_version` + 目标列 |
| `pcs_test`（测试库） | 同上 | 同上（**独立进程**） |
| `pcs_pgtest`（PG 车道） | 迁移在**真实 PG** 上跑得通 + 并发语义 | `scripts/pytest_pg.sh` exit 0 |

⚠️ 前两个**必须每库一个独立进程**（alembic 的 settings 是 pydantic 缓存实例）
⇒ 且**直查库**的 `alembic_version` 与目标列，不能只信命令输出。
⚠️ 第三个**不是**「第三库要 alembic check」⇒ 它由 **T0 的车道**覆盖（那个车道
才是 PG 专属语义的验证通道）。

- [ ] **Step 6: 浏览器 QA**

`npm run dev` ⇒ `~/.claude/skills/gstack/browse/dist/browse`（`CI=1`）：
login 200 → dashboard → 逐条走 T5/T6/T7/T8 的新页面 ⇒ 控制台 0 error ⇒ 网络 0×404。
⚠️ `goto` 会清 zustand ⇒ 路由可达性检查走 **SPA 菜单点击**。

- [ ] **Step 7: 写 QA 报告 + 结项**

报告路径 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-XX-p9b3.md`，**certified 范围
写真实 commit 区间**（评审 #3 的教训）。

- [ ] **Step 8: Commit**

---

## 验收（全批）

| 门 | 判据 |
|---|---|
| 后端全量 | `pytest -q` 0 failed（基线 5405 passed / 77 skipped / 1 xfailed ⇒ 本批净增） |
| **PG 车道** | `scripts/pytest_pg.sh` exit 0 且 `N passed`（N ≥ 1）—— **不是**「skip 也算过」 |
| 前端全量 | `npm run typecheck` / `npm run lint` / `npm run test` 全绿 |
| 契约门禁 | `gate_08_openapi_contract.sh --check-baseline` 四阶段全过 |
| 三库 | `pcs` / `pcs_test` 各 `p9_014` + `alembic check` exit 0（独立进程 + 直查库） |
| 浏览器 | 新页面全部可达；控制台 0 error；网络 0×404 |
| 债项 | TODO-101 / 102 / 103 关闭；TODO-099 关闭（PG 车道落地）；TODO-092 / 100 仍在（**本批不做**，已登记） |

---

## P9B-3b 移交（批量「提交校对」—— 本批**不做**）

委员会 2026-11-02 裁决 5：六条契约决策全部采纳，但**归属取决于 P9B-3 的总量**
⇒ P9B-3 本体 ≈ 11 天（≈ 2.2 周）⇒ 已接近 2 周 ⇒ **按委员会建议单列 P9B-3b**。

**P9B-3b 的任务书（本批只留接口与移交说明，实施另起计划）**

后端 `POST /streams/batch/submit`：

- 请求 `{stream_ids: [uuid], dry_run: false}`；响应 **207 Multi-Status**：
  `{batch_id, total, succeeded: [{stream_id, from_status, to_status}], failed: [{stream_id, reason, detail}]}`
- **D1** 后端端点（不是前端循环）—— 典型批量 30–50 条，前端循环部分失败无法重试
- **D2** 部分成功（**不做**全原子）—— 50 条里 8 条失败不该回滚 42 条
- **D3** 审计 **N+1** 条：N 条单条（动作沿用 **`RECORD_TRANSITION`** —— 见
  「与 brief 的偏差」第 2 条）+ 1 条批次（新动作 `STREAM_BATCH_SUBMITTED`）
- **D4** 上限 100 条，配置化（`system_settings` 的 `stream.batch_submit_limit`）
- **D5** 幂等：按 `stream_id` 去重；**已 `IN_APPROVAL`** 视为成功
  （`note: "already_in_approval"`；⚠️ 状态名见「与 brief 的偏差」第 1 条）
- **D6** `dry_run=true` ⇒ 不改状态、不写审计，只返回校验结果
- ⚠️ **失败原因 `SIM_STREAM_COMPOSITION_OUT_OF_RANGE`** 由 T3 提供（不是新造）
- ⚠️ **最关键的测试**：并发提交同一条 stream ⇒ 一胜一拒（行锁）——
  **与 P9B-2 报告 #1 同形** ⇒ 必须有方言级 SQL 断言 + 接线断言（PG 级并发靠
  `scripts/pytest_pg.sh` 车道）

12 条边界用例清单（委员会 brief 第五节）照抄进 P9B-3b 的计划。

---

## 尚未解决的问题（开工前需裁决或登记）

| # | 问题 | 现状 | 建议 | 归属 |
|---|---|---|---|---|
| 1 | SPEC §7.7.1「引用 📎×N」的 **N 是什么** | SPEC 只给了列名，未定义口径；后端列表响应**不返回**该字段 | N = 该物流被**下游引用**的条数（设备 + 物流，lineage downstream 口径）⇒ 需后端在列表响应里加 `reference_count`（**一次聚合，无 N+1**） | ✅ **本批已定**：**不渲染该列**（T2 在 SPEC 标 ⏳，T6 不画）⇒ 口径与聚合留待下一批 |
| 2 | 组成合计的**气/液两相口径** | 主组成 `composition_json` 的口径已按实测钉死（CAS→摩尔分率，0~1，判定 \|sum−1\| ≤ 0.005，见 T3） | **但**两相流的 `vapor_composition_json` / `liquid_composition_json` 是否**各自**也要合计校验？ | ✅ **本批已定：只校验主组成**（两相的两份是同一套组分的相态拆分，各自合计本就 ≈1 ⇒ 重复校验只会制造噪音）⇒ T3 按此实现 |
| 3 | 物流列表「来源」列 —— **后端没有这个字段** | ✅ **已裁决（用户裁决 1a）**：加 `streams.source` 列 + 迁移 `p9_015`，4 值枚举 MANUAL / SIM_IMPORT / EXCEL / LAB ⇒ **落地在 T2.5** | ⚠️ 落地时注意：既有 `streams.source_type`（13 值 · **产出方式**）与新列**正交**但取值重叠 ⇒ 防漂移规则 + 一致性断言见 T2.5 的 Step 3b | **已裁决**（T2.5） |
| 4 | 手动创建向导里「物性估算」与「写入 DRAFT」的**顺序** | ✅ **已裁决（用户裁决 2）**：校验 → 写入 → 估算 → 提交；**估算失败只提示、不阻塞**后续提交校对 | 落地在 T7（Step 3 的 7 步表 + 一条「估算失败仍可继续提交」的测试） | **已裁决**（T7） |
| 5 | 「提交校对」要不要**理由** | 既有单条端点 `reason=None` | 本批**沿用不要求理由**（与既有行为一致，不扩语义） | 已定（无需裁决） |
| 6 | 系统参数页显示**哪些键** | `system_settings` 是通用 KV，键由后端/运维写入 | 页面显示**全部键**（不做白名单）⇒ 白名单反而要求后端维护一份清单 | 已定（无需裁决） |
| 7 | 角色分配 ADR 的**编号与立项时机** | 裁决 3 要求升格独立 ADR | 建议下一批开工前先立 ADR（与 P9B-3 并行不冲突） | 下一批 |
| 8 | P9B-3b 的端点命名 | 委员会 brief 用 `POST /streams/batch/submit` | 与 FastAPI 现有前缀风格一致（`/streams/{id}/submit`）⇒ `POST /streams/batch/submit` 可用，但 `batch` 会与 `{stream_id}` 抢路由 ⇒ **建议** `/streams/batch-submit` | P9B-3b 开工前裁决 |
| 9 | `streams.source`（新 · 4 值）与 `streams.source_type`（既有 · 13 值）**长期是否合并** | 实测两列**语义正交**（录入通道 vs 产出方式）但**取值重叠 3 处**（SIM_IMPORT 同名 / MANUAL_ENTRY↔MANUAL / LAB_REPORT↔LAB）⇒ 本批用「同一写入点成对赋值 + 一致性断言」防漂移（T2.5 Step 3b） | 长期看：要么把 `source_type` 的 3 个人工值收窄进 `source`（破坏既有契约，不划算），要么在 ADR 层写明「两列正交」并永久保留 | T2.5 落地后随 ADR 一并登记 |
| 10 | Excel 导入行的 `source_type` 仍是 `SIM_IMPORT`（实测 `import_service._excel_preview_entry`） | Excel 双 Sheet 导入在 `source_type` 上与 PRO/II **同值** ⇒ 既有契约里分不出两者 | 本批：新增的 `source` 列写 `EXCEL`（两列取值不同是**有意的**）⇒ 前端按 `source` 区分 ⇒ **既有 `source_type` 保持不动**（改它要动既有枚举与契约） | 下一批或独立 ADR（是否扩 `source_type` 词表） |
| 11 | 10 个 `*_CALCULATED` 设备计算出口流在 `source` 的 4 值里**无对应值** | 实测 `pcs_test` 202 行里 101 行是 `PIPE_CALCULATED`/`PIPE_NET_CALCULATED`（出口流） | 本批规则：出口流**继承其上游物流的 `source`**（不造第 5 值、不撒谎）⇒ 测试断言 7 钉住 | 下一批（是否加 `CALCULATED` 第 5 值） |
| 12 | `streams.phase` 无索引 | 列表新增「相态」筛选后按 `phase` 过滤要全表扫（`sign_status` 有 `ix_streams_sign_status`，`project_id` 有 `ix_streams_project_id`，`phase` **没有**） | 本批量级（单项目物流数 ≪ 1000）可接受 ⇒ 先不加索引；触发条件：某项目物流数 > 1000 且列表明显变慢 | 下一批（按需加 `ix_streams_phase`） |

---

## GSTACK REVIEW REPORT

> 计划成型后跑 `gstack review`（或 `/plan-eng-review`）做一次外部复核；复核结论以
> **追加节**形式写回本文档（不改写正文 —— 计划是时点快照，改写它会让「当时说了什么」
> 不可追溯）。
