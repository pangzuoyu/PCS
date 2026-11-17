---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-18（第 34 轮：
> **P10-F 批 1+2（F1+F2 · 9 个任务）** —— 生产就绪评审的 8 条技术债 + 1 条
> 评审期间新发现全部落地；**未 push**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 34 轮：P10-F · F1 + F2 两批）

计划：`docs/superpowers/plans/2026-11-17-p10-batch-f-production-readiness.md`
· 账簿 `.superpowers/sdd/2026-11-17-p10-batch-f-production-readiness/progress.md`
· QA 报告 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-17-p10f-f1.md`
+ `…-2026-11-18-p10f-f2.md`（**gitignored** ⇒ 结论已同步进本文 + `TODOS.md`）
· commits `f26bdcb` → `16ebcb6`（**未 push**）。

**F1（4 条）**：#9 `useFetch` 失败态 + 401 与 axios **共用真相源**（`handleSessionOver`）
· #13 `preview-streams` 补 `response_model`（**契约滚了 4 份**）· #17 种子管级按
契约造 **+ 订正老行** · #27 守门测试统一断「可执行部分」+ 断 `flock -n`。

**F2（4+1 条）**：#22 public 守卫快照**全部表** + `max(xmin)` + 补 `_sync_engine`
+ **session 级基线** · #24 仪表盘守卫条件改成「**拿到了真 project_id**」+ 种子的
PERSONAL 工作区 · #15① compose 的 migrate/seed **进同一把锁** · TODO-162 rowKey
棘轮扩到函数形式（**白名单现在空了**）· **F2-T5 默认车道不再碰开发库/真 Redis**。

**额外修掉两条上一批遗留红**：① `test_ui_schema_drift`（#26 让 `case_type` 可省略
⇒ uiSchema 未同步）② `test_meta`（它与漂移守卫**互相打架** ⇒ 改的是它）。

**闸门**：默认车道 **5835 passed / 138 skipped**（9m25s · EXIT=0）· PG 7 ·
E2E 39 · 真后端 Playwright **9** · mock 通道 23 · vitest **1067** · typecheck/lint
clean · G-08 baseline 过 · 裸载荷 42。

**新登记**：bug-2181 · bug-2182 · TODO-162（已关）· TODO-163（部分关闭）·
TODO-165（真 Redis 用例迁车道）· TODO-166（公司管级列表要不要出现种子行 · **产品**）·
TODO-167（占位常量被当真 id）· TODO-168（漂移守卫仍连开发库 · 只读）。

---

## 🚀 Next quest

1. **P10-F 批 3（F3 · 5 任务）**：**只有 T1 能开**（范围提案 + 初判 ⇒ 交人裁决）⇒ ⇒
   T2/T3 等人批了范围再开（主计划 Q10）。
2. **推送本轮**（P10-B 12 个 + 本轮 10 个提交未 push ⇒ 需明确授权）。
3. **P10-C / D / E** 未开工 ⇒ ⇒ F4（依赖漏洞/镜像扫描/回滚演练）与 F5（告警/备份/
   Go-No-Go）前置不满足 ⇒ ⇒ F6 收口要等 F4/F5。
4. **待人裁决**：#17 的 `source` 副作用（TODO-166）· #24 的 FORMAL 回填 · F3 范围。

---

## Context

> ⚠️ **迁移 / PG 车道 / 裸载荷基线 / 发布前检查** ⇒ 见 `CLAUDE.md` ⇒ **不重复**。

- main。**不要建 worktree**（历史事故）· **不要 `git checkout <commit> --detach`**。
  **不得擅自 push**。`.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- 提交约定：conventional commits，**带** `Co-Authored-By: Claude Code` 行；长消息写文件后 `git commit -F`。
- ⚠️ **计划里的 Task 标签带批次前缀**（F1-T1）⇒ 内置 `task-brief` 只认纯数字 ⇒
  本轮自建 `.superpowers/sdd/<plan>/brief.sh`（等价抽取）⇒ 下一批沿用。
- ⚠️ **真后端通道统一入口**：后端 `bash pcs-backend/scripts/serve_e2e_backend.sh`
  （库 `pcs_pgtest` · 端口 **8001**）⇒ 前端 `npm run e2e:real`。
  ⇒ ⚠️ `pcs-postgres-pgtest-1` 容器**在跑**（宿主 5433）⇒ `pg_isready -p 5433`
  **不带 `-h`** 会说「no response」⇒ 要 `-h localhost`。
  ⇒ ⚠️ **public schema 的种子要重灌**（compose 的 `seed` 一次性服务本机拉不动镜像）
  ⇒ ⇒ 进程内调 `scripts/seed_e2e_flows.py::_main`（口令从**仓库的 compose 文件**
  读 ⇒ **不在命令行**）。
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

- **「存在就不动」的写法 ⇒ 改了工厂函数也修不了老行** ⇒ ⇒ 订正必须**显式**做
  （幂等：只在形状真的不对时才写）（F1-T3 · F2-T2 都踩了）。
- **守卫要断「可执行部分」，不是原文** ⇒ 注释里写一句 `flock` 就足以让守卫绿
  ⇒ ⇒ 一处真相源 + 剥注释按 shell 的**词边界**规则（F1-T4）。
- **antd 的 `rowKey` 弃用告警判据是 `rowKey.length > 1`** ⇒ ⇒ **参数名**改成
  `i` 也一样告警 ⇒ ⇒ 断**参数个数**才够（F2-T4）。
⇒ 其余历史教训查 `.wolf/cerebrum.md` 的 Do-Not-Repeat（**先查顶部索引表，别通读**）
   与 `docs/solutions/`。
