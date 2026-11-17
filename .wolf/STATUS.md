---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-17（第 32 轮：
> **P10-B 评审修复批** —— ce-code-review 的 21 条发现按人裁决全部落地；
> **未 push**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 32 轮：P10-B · ce-code-review 评审修复批）

报告：`docs/ce-code-review/20261117-013829-7e9fbabe/report.md`（+ 末尾的人裁决节）
· 账簿 `.superpowers/sdd/2026-11-17-p10b-review-fixes/progress.md`
· commits `cebf48d` → `1e27216`（**未 push**）。

**裁决落地**（21 条发现里人裁的 12 条 + 随裁决连带修的）：
A1/#14（审计端点读 `content_hash` · #3/#4/#12 随之）· #2（迁移种子 +
lifespan ensure ⇒ #1 作废）· **#8**（库名白名单 `current_database()`）·
**#16**（闸门③ 不再接受「跑 1 条 skip 29 条」）· **#19**（隔离扩到**进程级
session factory**）· **#10**（RBAC 审计早退 → 按**真实连接**判车道上下文）·
**#5**（越权断言换「角色够、授权缺」身份 ⇒ 断 404 + code/message 模板）·
**#6**（矩阵断言改断种子那张）· **#7**（路由扫描改真断言 + 白名单外为空）·
**#18**（种子显式灌生产默认数据）· **#20/#21**（schema 一致性挪到发布前闸门
+ 断「与代码 head 对齐」）· **#23**（三个变量落到三层各自位置 + fail-fast）·
**#11**（5 份 `docs/solutions/` 回写）· **#25**（偏离登记同步到权威 V1.3.1）·
**#26**（请求侧 `case_type` 可省略）· **#15**（锁移项目内 + 默认路径互斥实测）。

**闸门**：默认车道全量 · PG 车道 7 · E2E 车道 31 · 真后端 Playwright 7 ·
mock 通道 23 · vitest 1054 · typecheck/lint clean · 两库 `p10_002 (head)` +
`alembic check` 干净 · 幂等 48 迁移 0 violations · 裸载荷 42 ≤ 71。

**新登记**：bug-2173~2180（8 条）· TODO-162（antd rowKey 弃用告警）·
TODO-163（compose 的 migrate/seed 未进锁 ⇒ 无外网无法验证）。

---

## 🚀 Next quest

1. **推送本轮**（12 个提交未 push；用户此前要求过「推送远端」⇒ 需明确授权）。
2. **P10-C/D/E/F** 仍未开工（部署可观测 / 压测 / 文档 / 生产就绪评审）。
3. **未落地的裁决项**（本批**未**处理，等下一批）：#9（`useFetch` 改走 axios）·
   #13（preview-streams 补 response_model）· #17（种子管级按契约改）·
   #22（public 守卫覆盖全部表 + 种子前基线）· #24（仪表盘 404 守卫条件）·
   #27（flock 守卫剥注释 + 校验 `-n`）。
4. **E2E 进 CI 延到 P10-F**（既有裁决「不新建流水线」⇒ D25）。

---

## Context

> ⚠️ **迁移 / PG 车道 / 裸载荷基线 / 发布前检查** ⇒ 见 `CLAUDE.md` ⇒ **不重复**。

- main。**不要建 worktree**（历史事故）· **不要 `git checkout <commit> --detach`**。
  **不得擅自 push**。`.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- 提交约定：conventional commits，**带** `Co-Authored-By: Claude Code` 行；长消息写文件后 `git commit -F`。
- ⚠️ **真后端通道现在有统一入口**（评审 #23）：后端 `bash pcs-backend/scripts/serve_e2e_backend.sh`
  （库 `pcs_pgtest` · 端口 **8001** · mock 登录开）⇒ 前端 `npm run e2e:real`
  ⇒ 三个变量由 `playwright.config.ts` 的 webServer.env **默认**给 ⇒ 不用手工 export。
- ⚠️ **`.env` 的 `DATABASE_URL` 指向开发库 `pcs`** ⇒ 跑真后端通道必须**显式覆盖**
  ⇒ 且 alembic 的 `settings` 是 pydantic **缓存实例** ⇒ **一库一个进程**
  ⇒ 已有现成脚本：`uv run python scripts/check_schema_parity.py`（逐库独立进程 + 与代码 head 比）。
- ⚠️ **antd 的 `role="option"` 是隐藏副本**（宽 0）⇒ Playwright 判「不可见」
  ⇒ 用 `.ant-select-item-option`；状态徽标上写的是**中文**（「已核验」）。
- ⚠️ **跑 pytest 前先清掉残留进程**（本机多次出现上几轮遗留的 pytest）⇒ 满负载 ⇒
  Playwright 的 `locator.click` **30s 超时假红**。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。
- ⚠️ **`.env` 的口令不要写命令行** ⇒ 用 `dotenv_values('.env')` 在**进程内**派生 URL。
- ⚠️ **本机无外网** ⇒ compose 的一次性服务（`seed` / `migrate`）**构建不了**
  ⇒ ⇒ compose 侧改动**无法验证** ⇒ 别盲改（TODO-163 就是这么留下的）。

---

## 教训（**已进 cerebrum / docs/solutions**，此处只留最新三条）

- **断言要断的分支必须先「到达」** ⇒ 身份不对 ⇒ 比较的是**另一个闸门**的码
  ⇒ ⇒ 用**变异测试**证明敏感（删掉被守卫的代码 ⇒ 断言必须红）（bug-2174）。
- **响应字段的可空性要从 DB 列推出来** ⇒ 窄声明 = 整个端点 500；请求侧要**对称**（bug-2167/2173）。
- **车道的驱动必须与生产同一个** ⇒ 否则「int 塞进 VARCHAR」这类缺陷**隐形**（bug-2166）。
⇒ 其余历史教训查 `.wolf/cerebrum.md` 的 Do-Not-Repeat（**先查顶部索引表，别通读**）
   与 `docs/solutions/`。
