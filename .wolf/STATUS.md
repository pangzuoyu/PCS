---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-23（第 42 轮：
> **P10-I · T1 落地** —— 「待我审核」队列 + `publish()` 补洞 · QA 全绿）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 43 轮 · **P10-I · T2**（TODO-187b）· 2026-11-23）

**404 文案逐字同形** —— 守卫（`_guard.py`）加两个可选参数
`not_found_code` / `not_found_message` ⇒ ⇒ 端点把**自己那条**传进去
⇒ ⇒ 「不存在」与「无权」**逐字同形** ⇒ ⇒ **存在性不可枚举**。

⚠️ **默认文案一个字没改**（`"Project not found: {project_id}"` ⇒ ⇒ **124 处零影响**
⇒ ⇒ 有测试钉子）。
⚠️ **实测范围比计划大**：计划写「12 族」⇒ ⇒ **AST 实扫 = 47 个端点**
⇒ ⇒ 另有两处 own-404 在 **helper** 里（`supplier.py::_load_equipment` ·
`records_actions.py::load_record` ⇒ ⇒ 后者被**所有记录写面端点**共用）。
⚠️ **守卫在前 ⇒ ⇒ 自己的 404 不可达 ⇒ ⇒ 无向量** ⇒ ⇒ 不纳入（AST 守卫带顺序判据）。

**断言** = ① **AST 完整性守卫**（扫全 api 层 47 端点逐条比对「自己抛的那条」
与「传给守卫的那条」的 **AST 结构** ⇒ ⇒ 漏传/抄错一个字即红）
② **端到端** 2 族（真发请求 ⇒ ⇒ 同一无权用户探「存在」与「不存在」
⇒ ⇒ `(code, message)` 逐字相同 ⇒ ⇒ 用 `strict_client`）
③ **约束 2 钉子** ⇒ ⇒ **变异自证 3/3 全红**。

⇒ ⇒ **收批时又抓三个坑**：① 两个既有测试断的是旧文案 ⇒ ⇒ 改断资源自己那条
② ⚠️ **URL 字面量写在模块级常量** ⇒ ⇒ 棘轮只扫**测试函数体** ⇒ ⇒ **台账假绿**
⇒ ⇒ 字面量搬进函数体 ③ 两个向量在 **helper** 里 ⇒ ⇒ 端点级 AST 扫看不见
⇒ ⇒ 扫描单位改成「抛 404 的函数」。
⇒ ⇒ **棘轮**：`AUDITED_PROJECT_SCOPED_ENDPOINTS` +2（psychro / filtration 详情）
⇒ ⇒ `…_MIN` 11 → **13** · `STRICT_CLIENT_TEST_MIN` 171 → **172**（参数化算 1 个）。

⇒ ⇒ 前端**零改动**：它早已按 `SIM_STREAM_NOT_FOUND` / `HEAT_NOT_FOUND` /
`RECORD_NOT_FOUND` 分流 ⇒ ⇒ 对齐后端反而**与前端既有口径一致**。
⇒ ⇒ 解法回写 `docs/solutions/security-issues/two-404-messages-leak-existence.md`。

## ✅ Done（第 42 轮 · **P10-I · T1** · 2026-11-23）

**「待我审核」队列**（TODO-197 · 人裁方案 ①）落地 ⇒ ⇒ **后端 + 前端 + SPEC**：

- **端点** `GET /api/v1/report-builder/definitions/pending-review`
  ⇒ ⇒ **声明在 `/definitions/{def_id}` 之前**（否则被 `{def_id}` 抢走 ⇒ 422）
- **口径与 `visible_clause` 分离**（人裁约束 2）⇒ ⇒ **不**复用它
  （它对 SYSTEM_ADMIN 全局 bypass ⇒ ⇒ admin 会看到别人的 `CREATOR_ONLY` 草稿）
- **过滤落 service 层** + 角色闸**同处**（端点漏调也绕不过）⇒ ⇒ 端点**不**调
  `require_roles`（同一条件只留**一个**错误码）
- **`publish()` 补判 `shared_with`** ⇒ ⇒ 403 `REPORT_DEFINITION_NOT_SHAREABLE`
  ⇒ ⇒ 位置在**项目授权 404 之后**（404 先赢 ⇒ 不泄露半成品存在性）
- **A-3** `PUBLISH_ROLES` / `OBSOLETE_ROLES` 两份重复 ⇒ ⇒ 收进 **`app/core/acl.py`**
  （core = api 与 service 都能 import 的那一层）
- **前端**「待我审核」页 + `/report/review` + 菜单 · 「发布」**只在队列页**
  · 「忽略」`localStorage`（键含 `updated_at` + 版本前缀 + 「显示已忽略」开关）
- **SPEC** §7.18.1 已登记 + §12.4 **V2.17**（文件头 V2.6 的漂移一并校正）
- **断言** 10 条 `strict_client`（成对断）⇒ ⇒ **5/5 变异自证**全红
  ⇒ ⇒ 队列进台账 + `STRICT_CLIENT_TEST_MIN` 120 → **171**
- ⚠️ **后果**：`CREATOR_ONLY` 的定义**永远停在 DRAFT**（人裁 ① 的直接后果，已写进 SPEC）

**QA 全绿**：后端 6079 · PG 46 · 前端 1125 · 浏览器（队列渲染 / 名称**不是链接** /
发布 / 忽略 / 无 console error / 无 404）⇒ ⇒ 报告
`.gstack/qa-reports/qa-report-pcs-frontend-2026-11-23-p10i-t1.md`

**顺带修了 `scripts/slim_todos.py` 的 6 个缺陷**（最重：**第二次跑会抹掉已归档的 98 条**
⇒ ⇒ 已回滚救回）⇒ ⇒ 现在**两次跑逐字节一致**（幂等）。

## ✅ Done（第 41 轮 · **CAS 号核完** · 2026-11-23）

**触发**：人问「TODO-196 的 CAS 号**可以网络查询呀？**」⇒ ⇒ **能**（公开登记号）
⇒ ⇒ 10 条 DMC 组分逐条核 ⇒ ⇒ **查出 3 条错的**（bug-2197）：

| 组分 | 错号 | 错在哪 | 正号 |
|---|---|---|---|
| `ISO_BUTANE` | `106-98-3` | **CAS 校验位就不对** | `75-28-5` |
| `DIPROPYLENE_GLYCOL` | `25265-29-4` | **CAS 校验位就不对** | `25265-71-8` |
| `TRIPROPYLENE_GLYCOL` | `2463-75-4` | 校验位**过**，但没有源指向三丙二醇 | `24800-44-0` |

⇒ ⇒ **影响分级**（比原 TODO 说得准）：错号**取不到 MW** ⇒ ⇒ 组成**静默作废**
⇒ ⇒ 那些流**闪蒸算不了**（**安全的失败**）⇒ ⇒ 只有「真号指向别的物质」才算出**错**结果。

**自动化**：`tests/services/test_component_cas.py` —— **离线棘轮** 95 条断言
（42 × 〔**校验位关** + `chemicals` **存在关**〕+ 11 条**分子量钉死**）
⇒ ⇒ **变异自证**：塞回错号 ⇒ ⇒ **8 条红**；
`scripts/verify_component_cas.py` —— 联网那半（**PubChem 双向**）
⇒ ⇒ ⚠️ **CAS Common Chemistry 现要 API key（401）** ⇒ ⇒ **别把 401 当「查不到」**
⇒ ⇒ ⚠️ **三丙二醇 PubChem 无独立记录** ⇒ ⇒ 用 OECD SIDS / CAMEO 交叉确认。
解法落盘 `docs/solutions/domain-data/cas-numbers-must-be-verified-not-recalled.md`
⇒ ⇒ **TODO-196 从「等工艺室」变成「已核 + 只剩签字」**。

## ✅ Done（第 40 轮 · P10-F · F4-PRE · 2026-11-23）

**FP-T1 逐条裁决**（主任务）⇒ ⇒ 14 条债**逐条落成三者之一** ⇒ ⇒ **修 8 · 转 2 · 关 4**
⇒ ⇒ **无一条留「未定」** ⇒ ⇒ 逐条证据 = `TODOS.md` 末尾「**F4-PRE 裁决表**」。
**FP-T2** 棘轮抬真（台账本=清单）· **FP-T3** ⚠️ **发现 TODO-164 没关**
（`pg` 用例平时也跑 ⇒ ⇒ 摸开发库 ⇒ ⇒ 补**收集期**闸 + 按 fixture 名自动标 pg
⇒ ⇒ **PG 车道 7 → 46 passed**）· **FP-T4** 173/181/183/188 断言缺口补齐
（角色白名单提为**模块级常量** `ALLOWED_ROLES`）· **FP-T5** 台账同步
⇒ ⇒ 顺带修 3 个真缺陷（bug-2194/2195/2196：角色名**拼错** · `/me` 漏两角色 ·
默认车道摸开发库）。**转出去的两条有批号**：P10-I · P10-J（计划已建）。

---

## 🚀 Next quest

1. **P10-C 主体**（**部署与可观测性**：exporters · 监控栈 · 状态页 · 备份演练）
   ⇒ ⇒ **F4 的前置**（没镜像 / 部署物 / 告警 ⇒ F4 开不了）
   ⇒ ⇒ ⚠️ **P10-C 的「前端收口」子批已做**（2026-11-18/19）⇒ ⇒ 剩下的就是这主体
   ⇒ ⇒ ⇒ 它需要**形态裁决**（镜像怎么打 · 监控栈选型 · 备份演练怎么做）⇒ ⇒ 需人裁
2. **推送**：本轮提交**待明确授权**
3. **仍待人裁决**：**P10-J-T2「拒绝」动作**（4 问：状态模型 / 谁可见 / 能不能再编辑 /
   要不要通知）⇒ ⇒ **P10-J 未排期** · **TODO-196**：只剩**工艺室签字**（已核完）·
   **SPEC §7.5 向导**的 PMS / BEDD 两步**仍是空占位** ⇒ ⇒ 另开。
4. ✅ **P10-I 已整批完成**（T1 队列 + T2 404 同形；T3「拒绝」登记在 P10-J）。

---

## Context

- main。**不要建 worktree** · **不要 `git checkout <commit> --detach`**。**不得擅自 push**。
  `.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- ⚠️ **每轮开工先查残留**：`fuser -v pcs-backend/.tmp/lane.lock` ·
  `pgrep -af "uvicorn app.main:app"` · `ss -ltnp | grep 5173`。
- ⚠️ **默认车道零连真 PG**（`pg` 用例只在车道跑）⇒ ⇒ 要跑它们**必须**走
  `bash scripts/pytest_pg.sh`（**唯一入口**）⇒ ⇒ 该车道要求 **redis 起着**。
- ⚠️ **真后端通道**：后端 `bash pcs-backend/scripts/serve_e2e_backend.sh`（库
  `pcs_pgtest` · 端口 8001）⇒ 前端 `npm run e2e:real`；**mock 登录端点是
  `/auth/mock-login`（不在 `/api/v1` 下）**。
- ⚠️ **`.env` 的口令不要写命令行** ⇒ 用 `dotenv_values('.env')` 在**进程内**派生 URL
  ⇒ ⇒ **一库一个进程**（alembic 的 settings 是 pydantic 缓存实例）。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。

---

## 教训（**已进 cerebrum / docs/solutions**，此处只留最新两条）

- **「已覆盖」要能复核** ⇒ ⇒ 判据 = **这条断言用的是 `strict_client`** ⇒ ⇒
  默认 `client` 把守卫 mock 成永远 True ⇒ ⇒ 那些断言是 **no-op**。
- **标记只在**「收集期」**生效才叫车道隔离** ⇒ ⇒ 闸门必须挂在
  `pytest_collection_modifyitems` 上（不是运行时）。
