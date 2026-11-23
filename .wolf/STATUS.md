---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-23（第 40 轮：
> **P10-F · F4-PRE** —— 14 条遗留债**逐条裁决**完）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 40 轮 · P10-F · F4-PRE · 2026-11-23）

计划 `docs/superpowers/plans/2026-11-17-p10-batch-f-production-readiness.md`
的 **F4 前置批**（FP-T1~T5）⇒ ⇒ 提交见 `git log`（本轮）。

**FP-T1 逐条裁决**（主任务）⇒ ⇒ 14 条债**逐条落成三者之一**
⇒ ⇒ **本批修 8 条** · **转批 2 条** · **关闭 4 条**
⇒ ⇒ **无一条留在「未定」**（那正是这批债攒下来的原因）
⇒ ⇒ 逐条证据：`TODOS.md` 末尾「**F4-PRE 裁决表**」（唯一账本）。

**FP-T2 棘轮抬真** ⇒ ⇒ 台账本就是**清单**（不是计数）⇒ ⇒ 本批补两件事：
`report.py` 的 **4 条**项目作用域端点进台账 · 新增「**自建 client 的文件集合
冻结**」守卫（防第三个 client）。

**FP-T3 车道残留** ⇒ ⇒ ⚠️ **发现 TODO-164 其实没关**：`pg` 标记的用例
**平时也会被默认车道跑** ⇒ ⇒ 在**开发库**里建 schema + 跑 alembic 链（DDL 写！）
⇒ ⇒ 补**收集期**闸（`pg` 只在车道跑）⇒ ⇒ 依赖真 Redis 的用例按 fixture 名
**自动**标 `pg`（21 条）⇒ ⇒ **PG 车道 7 → 46 passed** ⇒ ⇒ 覆盖回来了。

**FP-T4 断言缺口** ⇒ ⇒ 173（`config.py` **11 条**端点逐条 403 + **AST 完整性
守卫**）· 181（`report.py` 4 条端点补 `strict_client` 断言 + 删掉**恒真**断言）
· 183（初值 `True` ⇒ ⇒ `False`）· 188（角色白名单提为**模块级常量**
`ALLOWED_ROLES` ⇒ ⇒ `/me` 用 `*ALLOWED_ROLES` ⇒ ⇒ **抄漏**不再可能）· 171 关闭。

**FP-T5 台账** ⇒ ⇒ `TODOS.md` 逐条标状态 + 计划末尾的清单表同步 + 两个新批号。

⚠️ **顺带修的三个真缺陷**（`bug-2194/2195/2196`）：批量提交端点角色名
**拼错**（`PROCESS_CONTROLLOR`）⇒ ⇒ 工艺室的人 403 · `/user-projects/me`
漏两个角色（**P10-H 的项目选择器对他们直接空**）· 默认车道摸开发库。

**转出去的两条**（都**有批号**了）：**P10-I** 守卫补洞批（TODO-187 改 404
文案）· **P10-J** 功能批（TODO-177 公司级模板可执行 · TODO-197 他人发布入口
· TODO-196 DMC CAS）⇒ ⇒ 两份计划已建。

---

## 🚀 Next quest

1. **P10-I**（新建 · `docs/superpowers/plans/2026-11-23-p10-i-report-review-publish.md`）
   ⇒ ⇒ **T1 · TODO-197**（**已裁决 2026-11-23**：选 ①「待我审核」队列 + 列表页发布按钮
   + 三个约束：只读视图 / 过滤条件与 `visible_clause` 分离 / 「拒绝」不做 ⇒ 转 TODO-197b）
   ⇒ ⇒ **T2 · TODO-187b**（**已裁决**：选 A「守卫加可选 `not_found_code/message`」
   + 两个约束：同端点同资源类型才逐字同形 / **守卫默认文案不得变**（要有测试钉子）
   ⇒ ⇒ 范围 **12 族** · 🟢 low）
   ⇒ ⇒ **T3 · TODO-197b**（登记 ⇒ P10-J）
   ⇒ ⇒ ⚠️ **不塞 P10-C**（那条批已满）⇒ ⇒ **优先级 197 > 187b**。
2. **P10-F · F4 主批**（`docs/superpowers/plans/2026-11-17-p10-batch-f-production-readiness.md`
   的 F4）⇒ ⇒ 前置是 **P10-C**（没有镜像 / 部署物 / 告警 ⇒ F4 开不了）
   ⇒ ⇒ **P10-C** 未做 ⇒ ⇒ F4 仍**开不了** ⇒ ⇒ 下一批该开 **P10-C**。
3. **推送**：本轮提交**待明确授权**。
4. **仍待人裁决**：**TODO-196**（10 个 DMC 组分的 CAS ⇒ **工艺室**确认）·
   **P10-J-T1** 的两个问题（公司级模板该不该可执行 / 无权时 404 还是 403）·
   **P10-I-T1** 的两个实现选择（队列端点形态 · 「忽略」存哪）。
5. **SPEC §7.5 的向导**里 PMS / BEDD 两步**仍是空占位** ⇒ ⇒ 另开。

---

## Context

- main。**不要建 worktree** · **不要 `git checkout <commit> --detach`**。**不得擅自 push**。
  `.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- ⚠️ **每轮开工先查残留**：`fuser -v pcs-backend/.tmp/lane.lock`（谁占着车道锁）·
  `pgrep -af "uvicorn app.main:app"`（真后端通道的后端）· `ss -ltnp | grep 5173`。
- ⚠️ **默认车道现在零连真 PG**（`pg` 用例只在车道跑）⇒ ⇒ 想跑它们**必须**走
  `bash scripts/pytest_pg.sh`（**唯一入口**）⇒ ⇒ 该车道要求 **redis 起着**
  （编辑锁 / 广播用例要真 Redis）。
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
- **标记只在**「收集期」**生效才叫车道隔离** ⇒ ⇒ `pg` 用例平时也会被默认
  车道跑 ⇒ ⇒ 闸门必须挂在 `pytest_collection_modifyitems` 上（不是运行时）。
