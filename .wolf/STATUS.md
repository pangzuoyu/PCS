---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-18（第 35 轮：
> **P10-F 批 1+2（F1+F2+F3-T1）+ 整支评审的修复批** —— 生产就绪评审落地
> + 独立评审员查出的 **1 CRITICAL + 6 IMPORTANT** 全部修完；**未 push**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 35 轮：P10-F · F1 + F2 + F3-T1 + **整支评审修复批**）

计划：`docs/superpowers/plans/2026-11-17-p10-batch-f-production-readiness.md`
· 账簿 `.superpowers/sdd/2026-11-17-p10-batch-f-production-readiness/progress.md`
· 评审包 `review-2618f46..426887c.diff`（13 commit）
· commits `f26bdcb` → `df79685`（**未 push**）。

**F1（4 条）**：#9 `useFetch` 失败态 + 401 与 axios **共用真相源** · #13 `preview-streams`
补 `response_model`（**契约滚了 4 份**）· #17 种子管级按契约造 **+ 订正老行** ·
#27 守门测试统一断「可执行部分」+ 断 `flock -n`。

**F2（4+1 条）**：#22 public 守卫快照**全部表** + `max(xmin)` + 补 `_sync_engine`
+ **session 级基线** · #24 仪表盘守卫条件改成「**拿到了真 project_id**」+ 种子的
PERSONAL 工作区 · #15① compose 的 migrate/seed **进同一把锁** · TODO-162 rowKey
棘轮扩到函数形式（**白名单现在空了**）· **F2-T5 默认车道不再碰开发库/真 Redis**。

**F3-T1**：守卫覆盖审计的**范围提案 + 初判**（54 模块 · 313 端点 · 16 条候选缺口）
⇒ ⇒ **等范围批复**（主计划 Q10）⇒ ⇒ T2/T3 未开。

**整支评审的修复批**（独立评审员 · opus · 1 CRITICAL + 6 IMPORTANT + 7 MINOR）：

| # | 修了什么 | 提交 |
|---|---|---|
| **C1** | `useFetch` 在 **path 变化时不重置状态** ⇒ ⇒ 详情页停在上一次的失败提示 / 显示上一条的数据 ⇒ ⇒ effect 开头重置 | `5da8bd2` |
| M7 | 卸载后迟到的 401 **不清会话**（`cancelled` 判断提前） | `5da8bd2` |
| **I1/I2** | 隔离 fixture 是 **autouse** ⇒ ⇒ 它对 PG/E2E 车道**同样生效** ⇒ ⇒ PG 车道 `_sync_engine` 指向 SQLite（**假绿**）+ 20 条真 Redis 用例在**所有**车道都被跳过 ⇒ ⇒ 隔离**只作用于默认车道**（判据 = `PCS_TEST_LANE`） | `77a12ab` |
| **I3** | 真后端通道的**后端**也**写 public** ⇒ ⇒ 与 E2E 车道的守卫并发 ⇒ ⇒ 误红 ⇒ ⇒ 它也进**同一把车道锁** | `77a12ab` |
| **I4** | 上一次跑崩了留下的探针行 ⇒ ⇒ 把**下一次**跑带偏（假红）⇒ ⇒ 取基线**之前**先清残留 | `77a12ab` |
| I5/I6 | 补登记 **TODO-169**（产品裁决）· **TODO-167 的清单改成全仓实测**（12 文件 / 24 处，原写「4 处」） | `df79685` |
| M1/M2/M3/M5/M6 | 种子的 SCH 键改**裸 DN**（`"150"`）· reset **恢复** PERSONAL 工作区 · `max(xmin)` 的**漏报面**写进注释 · 回写 `docs/solutions/` · 换引擎前 `dispose` | `f1c57b3` / `df79685` |

**闸门**：前端 typecheck/lint clean · **vitest 1069/1069（118 文件）** · mock 通道 23 ·
真后端通道 9 · 后端默认车道 **绿**（见下）· PG 车道 · E2E 车道。

**新登记**：bug-2183（C1）· bug-2184（autouse 越界）· bug-2185（探针残留假红）·
TODO-162（已关）· TODO-163（部分）· TODO-165（计数订正 + 现在**可执行**）·
TODO-167（清单已订正）· TODO-168（漂移守卫仍连开发库 · 只读）·
**TODO-166 / TODO-169 已裁决关闭**（2026-11-18：166 = 接受现状 · 169 = FORMAL
必然有项目、无项目的就是 PERSONAL ⇒ 写进 `CONCEPTS.md`）。

---

## 🚀 Next quest

1. **P10-F 批 3（F3）—— F3-T2a 完成 ⇒ 下一批 = F3-T2b**（`report.py` 10 + `records.py` 6）
   ⇒ ⇒ 范围**已由人裁决**（2026-11-18 · A+B+D(敏感)，C 不审 ≈ 63 端点）
   ⇒ ⇒ 提案在工作区 `…/proposals/guard-coverage-scope-proposal.md` ·
   T2a 结论在 `…/audit-f3-t2a.md`
   ⇒ ⇒ ⚠️ **T2a 推翻了裁决的两个前提** ⇒ ⇒ 要报告给人：
   **`config.py` 的资源是「公司级」**（`ConfigAsset` 无 `project_id`）⇒ ⇒
   「跨项目越权」语义**不成立** ⇒ ⇒ **越权缺口 0**（只缺断言）·
   **`report_builder` 的 `project_id` 是死字段**（可见性只看 `created_by`）
   ⇒ ⇒ 真缺口是**口径不一致**（TODO-170 · 产品裁决）
2. **推送本轮**（P10-B 12 个 + 本轮 8 个提交未 push ⇒ 需明确授权）。
3. **P10-C / D / E** 未开工 ⇒ ⇒ F4（依赖漏洞/镜像扫描/回滚演练）与 F5（告警/备份/
   Go-No-Go）前置不满足 ⇒ ⇒ F6 收口要等 F4/F5。
4. **待人裁决**：**TODO-170**（报告定义按不按项目隔离 · 两条路要人选）· 另 **1 个待确认项**（`POST /projects` ⇒ ⇒ **已核：只有 SYSTEM_ADMIN + 校验 FORMAL 工作区 + 授权给请求方自己 ⇒ ⇒ 越权面 ≈ 0 ⇒ ⇒ 不必并入 B 档** ⇒ ⇒ 等一句确认）：
   `projects.py` 的 `POST /projects`（自动授权创建者 = 授权写入的唯一入口）
   **不在**裁决的 B 档清单里 ⇒ ⇒ 要不要并入？
   另：TODO-166 / TODO-169 已裁决关闭。

---

## Context

> ⚠️ **迁移 / PG 车道 / 裸载荷基线 / 发布前检查** ⇒ 见 `CLAUDE.md` ⇒ **不重复**。

- main。**不要建 worktree**（历史事故）· **不要 `git checkout <commit> --detach`**。
  **不得擅自 push**。`.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- 提交约定：conventional commits，**带** `Co-Authored-By: Claude Code` 行；长消息写文件后 `git commit -F`。
- ⚠️ **真后端通道统一入口**：后端 `bash pcs-backend/scripts/serve_e2e_backend.sh`
  （库 `pcs_pgtest` · 端口 **8001**）⇒ 前端 `npm run e2e:real`。
  ⇒ ⚠️ **本机有个 11-17 起的老后端还在跑（端口 8001）** ⇒ ⇒ 它是**改动前**起的
  ⇒ ⇒ **不占车道锁** ⇒ ⇒ 要验「后端与车道互斥」得**重启**它。
  ⇒ ⚠️ `pg_isready -p 5433` **不带 `-h`** 会说「no response」⇒ 要 `-h localhost`。
- ⚠️ **`.env` 的 `DATABASE_URL` 指向开发库 `pcs`** ⇒ 跑真后端通道必须**显式覆盖**
  ⇒ alembic 的 `settings` 是 pydantic **缓存实例** ⇒ **一库一个进程**。
- ⚠️ **antd 的 `role="option"` 是隐藏副本**（宽 0）⇒ Playwright 判「不可见」
  ⇒ 用 `.ant-select-item-option`。
- ⚠️ **跑 pytest 前先清掉残留进程** ⇒ 满负载 ⇒ Playwright 的 `locator.click`
  **30s 超时假红**（本轮实测 mock 通道 19/18/23 三次 ⇒ 满负载时的已知 flake）。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。
- ⚠️ **`.env` 的口令不要写命令行** ⇒ 用 `dotenv_values('.env')` 在**进程内**派生 URL。

---

## 教训（**已进 cerebrum / docs/solutions**，此处只留最新三条）

- **「autouse」是全局的** ⇒ ⇒ 任何「为了 X 场景」的 fixture 都要**判作用域**
  ⇒ ⇒ 否则它会盖掉别的车道的隔离 ⇒ ⇒ **假绿**（P10-F · 整支评审 I1/I2）。
- **「覆盖损失」必须能被复核** ⇒ ⇒ 「已登记 TODO」≠「TODO 可执行」⇒ ⇒ 登记时
  要看一眼：**按那条 TODO 写，能不能真的把用例跑起来**（同 I1/I2）。
- **状态不会因为「依赖变了」而自动重置** ⇒ ⇒ React Router **复用组件实例**
  ⇒ ⇒ `useState` 留着上一页的值 ⇒ ⇒ 换 id 也会停在上一条的错误上（bug-2183）。
⇒ 其余历史教训查 `.wolf/cerebrum.md` 的 Do-Not-Repeat（**先查顶部索引表，别通读**）
   与 `docs/solutions/`。
