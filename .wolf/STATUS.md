---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-23（第 42 轮：
> **P10-I · T1 落地** —— 「待我审核」队列 + `publish()` 补洞 · QA 全绿）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

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

1. **P10-I · T2 · TODO-187b**（12 族端点的 404 文案**逐字同形** · 选 A
   「守卫加可选 `not_found_code/message`」· 🟢 low）⇒ ⇒ **已裁决 · 待实施**
   ⇒ ⇒ 两个约束：同端点同资源类型才逐字同形 · **守卫默认文案
   `"Project not found: {project_id}"` 不得变**（124 处依赖 ⇒ ⇒ 要测试钉子）
   ⇒ ⇒ 计划 `docs/superpowers/plans/2026-11-23-p10-i-report-review-publish.md` §T2
2. **P10-F · F4 主批** ⇒ ⇒ 前置是 **P10-C**（没镜像/部署物/告警 ⇒ F4 开不了）
   ⇒ ⇒ **P10-C 未做 ⇒ F4 开不了 ⇒ T2 之后开 P10-C**
3. **推送**：本批提交**待明确授权**
4. **仍待人裁决**：**P10-J-T2「拒绝」动作**（4 问：状态模型 / 谁可见 / 能不能再编辑 /
   要不要通知）⇒ ⇒ **P10-J 未排期** · **TODO-196**：只剩**工艺室签字**（已核完）·
   **SPEC §7.5 向导**的 PMS / BEDD 两步**仍是空占位** ⇒ ⇒ 另开。
5. ⚠️ **P10-C 里有「SPEC §7.5 向导」的 PMS / BEDD 空占位** ⇒ ⇒ 另开一条。

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
