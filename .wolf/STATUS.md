---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-23（第 41 轮：
> **CAS 号核完** —— 3 条错号已修 + 离线棘轮已立）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

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

1. **P10-I**（`docs/superpowers/plans/2026-11-23-p10-i-report-review-publish.md`）
   ⇒ ⇒ **T1 · TODO-197 已裁决**（选 ①「待我审核」队列 + 只读视图 + 过滤与
   `visible_clause` 分离 + 「拒绝」转 TODO-197b）· **T2 · TODO-187b 已裁决**
   （选 A 守卫加可选 `not_found_code/message` + 两个约束 · 12 族 · 🟢 low）
   ⇒ ⇒ ⚖️ **hermes 意见已落盘**
   （`docs/ce-code-review/20261123-hermes-p10i-p10j/hermes-adjudication.md`）
   ⇒ ⇒ ⚠️ **不塞 P10-C**（那条批已满）⇒ ⇒ **优先级 197 > 187b**。
2. **P10-F · F4 主批** ⇒ ⇒ 前置是 **P10-C**（没镜像/部署物/告警 ⇒ F4 开不了）
   ⇒ ⇒ **P10-C 未做 ⇒ F4 开不了 ⇒ P10-I 之后开 P10-C**。
3. **推送**：✅ 已推（`origin/main..HEAD` = 0）。**18:00 起做 P10-I**。
4. **仍待人裁决**：**P10-J-T2「拒绝」动作**（4 问：状态模型 / 谁可见 / 能不能再编辑 /
   要不要通知）⇒ ⇒ **P10-J 未排期** · **TODO-196**：只剩**工艺室签字**（已核完）·
   **SPEC §7.5 向导**的 PMS / BEDD 两步**仍是空占位** ⇒ ⇒ 另开。
5. ⚖️ **2026-11-23 第二轮人裁已落**：P10-I 的 6 条（`CREATOR_ONLY` 不列 +
   `publish()` 补判 · 按钮只在队列页 · SPEC 随批登记 · 忽略用 `localStorage`
   · 公司级模板留 P10-J · scope 顺序确认）⇒ ⇒ **P10-I · T1 无待裁项**。

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
