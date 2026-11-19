---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-19（第 37 轮：
> **P10-C 子批「前端收口」** —— T1/T2/T3/T4 + T5 闸门**全绿** · **未 push**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 37 轮 · P10-C 子批「前端收口」· T1 + T2 + T3 + T4 + T5 闸门全绿）

计划 `docs/superpowers/plans/2026-11-18-p10-c-frontend-closure.md`
⇒ ⇒ **T1（TODO-160 · 三页首屏 422）** commit `ba312b9`
⇒ ⇒ **T2（TODO-159 · 三个页面调不存在的端点）** commit `75cece5`
⇒ ⇒ **T3（TODO-157 · 设备台账页）+ T4（TODO-156 · PRO/II 补组成）** 落地中。

**T1**：契约里三个端点的必填参数（`keyword` / `material`+`temp_c` / `cas`）⇒ ⇒
三页改「**填条件才查**」（300ms 防抖 ⇒ **首屏零请求**）
⇒ ⇒ 顺带纠正两处形状错（`allowable-stress` / `safety` 返的是**单个对象**）
⇒ ⇒ **MSW mock 同步收紧**（缺参数 ⇒ 422 ⇒ 不再比真后端宽容）
⇒ ⇒ 变异自证 6 条断言转红。

**T2**：查契约 ⇒ **三个端点都不存在** ⇒ ⇒ 分两种处置：
`/pipe/line-list` **补端点** `GET /projects/{project_id}/pipe-line-list`
（数据源 = `piping_results` · 列 = **SPEC §7.11.2 的 43 列**）
· `/pms` `/bedd` **明确占位**（后端**确实没有**那两个实体 ⇒ 不编）
⇒ ⇒ 新增 `useProjectScope`（从 `GET /workspaces` 解析**真** project id）
⇒ ⇒ `PipeLineListRow` 改成**契约类型**（作废 4 个**后端没有**的列）
⇒ ⇒ 真后端扫描的**白名单现在是空的**。

**T3（人裁决① 补一页设备台账）**：新页 `/equipment-list`（菜单独立成组）⇒ ⇒
列 = **契约字段**（SPEC §7.13 的「包号 / 单元 / 计算状态」契约里没有 ⇒ 不编）
⇒ ⇒ ⚠️ **顺带补上两个跨项目洞**：`GET /equipment-list` 此前**只有角色闸**
（跨项目读）· sync 写入落在**源记录的 `project_id`** 上（跨项目写）
⇒ ⇒ 8 例新测试（`strict_client`）+ **变异自证**（删授权 ⇒ 3 例红）

**T4（人裁决「我补 CAS 号并标注待确认」）**：`.inp` 的 `COMPOSITION(M|W)` ⇒ ⇒
`{CAS: 摩尔分率}`（和 = 1.0）⇒ ⇒ 送审的组成门禁（100±0.5%）能过
⇒ ⇒ 新增 `component_cas.py` + `proii_composition.py` + fixture `sample6_composition`
⇒ ⇒ 8 例新测试（含**真的过一遍送审门禁**的断言）
⇒ ⇒ ⚠️ **10 个 DMC 组分的 CAS 待工艺室确认** ⇒ ⇒ **TODO-196**

**顺带修掉三个洞**：① mock 漂移棘轮**看不见 `:param` 写法的端点**（躲了三年 ⇒
归一化后多出 14 条欠账 ⇒ **TODO-193**）② `DeepKeys` 被**数组字段**污染
（闸失效 + `StrictColumns` 不可赋值）③ **`GET /equipment-list` 没有项目守卫**
（跨项目读 ⇒ T3 修）。

**闸门（批末实跑 · 全绿）**：前端 typecheck clean · lint clean ·
vitest **1091/1091**（121 文件）· 后端默认车道 **5923 passed / EXIT=0** ·
契约门禁 G-08 RC 0（基线已滚动）· 迁移幂等 0 违反（49 个迁移）·
**真后端通道 9/9 passed**（`BAD_RESPONSES=[]` · `CONSOLE_ERRORS=[]` · 46 条路由全可达）。

---

## 🚀 Next quest

1. **P10-F · F4**（安全扫描 / 依赖漏洞 / 镜像扫描 / 回滚演练）
   ⇒ ⇒ ⚠️ **前置是 P10-C**（部署物）⇒ ⇒ **F4-PRE**（不依赖镜像的那部分
   `bandit` + `uv audit` + `npm audit`）**现在就能开**
2. **推送本轮**（P10-B 12 个 + P10-F 18 个 + 本轮 3 个未 push ⇒ 需明确授权）
3. **待人裁决**：**TODO-190**（`obsolete` 不查 `created_by`）·
   **TODO-191**（前端「保存并发布」对创建人自己无提示）·
   **TODO-195**（PMS / BEDD 两页**存废**：① 删页并归到向导 ② 补后端实体
   ③ 保留占位）· **TODO-192 #5 / #8 / #10**（`shared_with` · `POST /workspaces`
   的 `project_id` · admin bypass 口径）· **TODO-193**（14 条 mock 欠账）·
   **TODO-194**（项目选择器）· **TODO-196**（10 个 DMC 组分的 CAS）

---

## Context

> ⚠️ **迁移 / PG 车道 / 裸载荷基线 / 发布前检查** ⇒ 见 `CLAUDE.md` ⇒ **不重复**。

- main。**不要建 worktree** · **不要 `git checkout <commit> --detach`**。
  **不得擅自 push**。`.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- 提交约定：conventional commits，**带** `Co-Authored-By: Claude Code` 行；长消息写文件后 `git commit -F`。
- ⚠️ **真后端通道统一入口**：后端 `bash pcs-backend/scripts/serve_e2e_backend.sh`
  （库 `pcs_pgtest` · 端口 **8001**）⇒ 前端 `npm run e2e:real`。
  ⇒ ⇒ 它**整个生命周期**都占**车道锁** ⇒ ⇒ 跑它之前**先跑完** PG / E2E 车道。
- ⚠️ **`.env` 的 `DATABASE_URL` 指向开发库 `pcs`** ⇒ 跑真后端通道必须**显式覆盖**
  ⇒ alembic 的 `settings` 是 pydantic **缓存实例** ⇒ **一库一个进程**。
- ⚠️ **跑 pytest 前先清掉残留进程** ⇒ 满负载 ⇒ 前端 `locator.click` **30s 超时假红**
  （本轮实测：`result_page.test.tsx` 在车道跑时红、单独跑绿 ⇒ **已知 flake**）。
- ⚠️ **本轮踩到**：**上一轮遗留的后台 pytest 车道**没退出 ⇒ **两条车道并发**
  ⇒ ⇒ CPU 抢占 ⇒ 车道慢 + 一条疑似假红 ⇒ ⇒ **每轮开工先 `pgrep -af pytest` 看一眼**。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。
- ⚠️ **`.env` 的口令不要写命令行** ⇒ 用 `dotenv_values('.env')` 在**进程内**派生 URL。

---

## 教训（**已进 cerebrum / docs/solutions**，此处只留最新三条）

- **「替身比被测物更宽容」**（本轮第三次撞上）⇒ ⇒ **mock 必须和契约一样严**
  （缺参数 ⇒ 422 · 命中不到 ⇒ 404）⇒ ⇒ 否则前端漏参数在 mock 通道里**看不出来**。
- **变异必须跑「该缺陷对应的断言文件」** ⇒ ⇒ 断言分散在两个文件时 ⇒ ⇒ **两个都跑**
  （本轮：丢「M/W 基准」的变异在换算层测试里**全绿** ⇒ ⇒ 在解析器测试里才红）。
- **写面授权要判「行实际落到哪儿」** ⇒ ⇒ 单条 sync 查的是 equipment 行的项目
  ⇒ ⇒ 但写入落在**源记录的 `project_id`** 上 ⇒ ⇒ **判错了对象**（⇒ ⇒ 与
  TODO-180「判 A 落进 B」同形）⇒ ⇒ 守卫要判**落库那一维**。
