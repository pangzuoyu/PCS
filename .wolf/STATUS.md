---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-12（第 29 轮：**P10-A 批落地**
> —— 前置与测试左移 + AI 预留接口；**未 push**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 29 轮：P10-A —— 前置与测试左移 + AI 预留接口）

计划：`docs/superpowers/plans/2026-11-04-p10-batch-a-preflight-ai-reserve.md`
（总纲 `2026-11-04-p10-master-plan.md`）· 账簿 `.superpowers/sdd/2026-11-04-p10-batch-a-preflight-ai-reserve/progress.md`

**段一（10.0 前置与测试左移）**：compose 加 `seed` 一次性服务（test profile，不新建文件）
· 幂等种子脚本（固定 UUID + `--reset` 只删自己 + **必造 `UserProject` 授权行**）
· **真后端 E2E 通道**（`VITE_ENABLE_MOCK=false` 关 MSW + Playwright `real-backend` 项目
+ `gotoViaMenu` SPA 导航 helper + 代理目标可 env 覆盖 + **mock-login 路径改写**）。

**段二（10.1 AI 预留）**：6 个 AI 键（`ai_enabled` 等）· `internal_cidrs` + 启动时校验
· 递归脱敏 + 规范化哈希（人名遮蔽**默认关**）· `ai_audit_log` 加 **8** 列 + 迁移 `p10_001`
（**partial** 唯一索引；时间列**复用 `occurred_at`**）· `AINotImplementedError` + 501 专用信封
· `OutboundAIClient`（唯一出口）· **5 个** AI 端点（一律 501）· ARQ 审计任务（**幂等**）
· 纯 ASGI 审计中间件（**认证失败也留痕** + body 重放）· `/api/v1/health/ai` ·
顶栏 AI 占位（**禁用** + 提示）· 架构守卫（AI SDK 只能从唯一出口出去）。

**实测**：后端 **5751 passed**（基线 5662 ⇒ +89）· PG 车道 **6 passed**（+1）·
前端 **116 files / 1054 tests**（+1）· Playwright mock 通道 **24 passed** ·
真后端通道 **1 passed** · 裸载荷 **71 未涨** · G-08 4/4 · 两库 `p10_001 (head)` +
`alembic check` exit 0 · **浏览器回归 0C-0H-0M**（报告
`.gstack/qa-reports/qa-report-pcs-frontend-2026-11-12-p10a.md`）。

**真库才暴露的缺陷（已修）**：PG `ON CONFLICT (request_id)` 匹配不到 **partial** 唯一索引
⇒ **每次写 AI 审计都炸**，而单测（SQLite）全绿 ⇒ `index_where` 补齐 + **PG 车道新增用例**
（`bug-2159` · fix_commit `5b608a1`）。

**SPEC 偏离登记 D1~D22 已回写**（`spec/P10 AI预留与测试部署开发规格说明书.md` 第五部分）
⇒ ⚠️ 该 SPEC 实际是 **V1.0**（计划引用的「V1.3.1」**在仓库里不存在** ⇒ D20）。

---

## 🚀 Next quest

1. **下一批 = P10-B（全流程 E2E）**：18 个场景 · SUP-007 五类路径 · 权限矩阵。
   ⚠️ 开工前先做 **TODO-149**（量一次种子数据规模 —— 本批的种子只够跑冒烟）。
   ⚠️ 权限矩阵要用 per-user 的**项目内角色** ⇒ 本批种子里是**统一 `DESIGNER`**
   （见 `scripts/seed_e2e_data.py::SEED_PROJECT_ROLE`）⇒ P10-B 要改这一处。
2. **P10-C/D/E/F** 仍未开工（部署可观测 / 压测 / 文档 / 生产就绪评审）。
3. **本轮未 push**（用户未要求）。
4. **新增 TODO**：146（AI 可选依赖推迟 · D19）· 147（pgvector 维度）·
   148（内网 CIDR 清单待 IT）· 149（P10-B 前量种子规模）· 150（AI 端点权限模型待定）。

---

## Context

> ⚠️ **迁移 / PG 车道 / 裸载荷基线 / 发布前检查** ⇒ 见 `CLAUDE.md`（§测试前检查、§发布前检查）⇒ **不重复**。

- main。**不要建 worktree**（历史事故）· **不要 `git checkout <commit> --detach`**。
  **不得擅自 push**。`.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- 提交约定：conventional commits，**带** `Co-Authored-By: Claude Code` 行；长消息写文件后 `git commit -F`。
- ⚠️ **本机 8000 端口被别的服务占着**（root 起的另一个项目）⇒ PCS 后端起在 **8001**，
  前端代理用 `VITE_API_PROXY_TARGET=http://localhost:8001`；真后端 E2E 用
  `VITE_ENABLE_MOCK=false VITE_API_PROXY_TARGET=… npx playwright test --project=real-backend`。
- ⚠️ **mock 登录的真实路径是 `/auth/mock-login`**（不在 `/api/v1` 下 · ADR-0046）⇒
  前端 axios baseURL 是 `/api/v1` ⇒ **vite proxy 里有一层改写** ⇒ 改它时别忘了这条。
- ⚠️ **跑 pytest 前先清掉残留进程**：本机多次出现**上几轮遗留的 pytest**在跑
  ⇒ 满负载 ⇒ Playwright 的 `locator.click` **30s 超时假红**（本轮实测两次假红）。
  ⇒ 跑 e2e 前 `pgrep -af pytest` 看一眼。
- ⚠️ **dev server 改动 `vite.config.ts` 后要重启**：`reuseExistingServer` 会复用
  旧 server ⇒ 用旧配置 ⇒ 症状是「登录页渲染不出来」。
- ⚠️ **ARQ 0.28 只对 `Retry` 异常重试**（其余当场判死）⇒ 「max_tries=5 ⇒ 重试必然
  发生」在本仓**不成立**。
- ⚠️ **`.wolf/cerebrum.md` 已 ≈24 230 token**（目标 ≤24 000）⇒ **下次清退窗口已到**。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。

---

## 教训（**已进 cerebrum**，此处只留最新两条）

- **单测跑 SQLite ⇒ 碰不到 PG 的方言分支** ⇒ PG 独有的失败形状要有 **PG 车道**用例。
- **纯 ASGI 中间件读 body ⇒ 必须重放** ⇒ 否则症状是 **422** 而不是本该报的 501。
⇒ 其余历史教训查 `.wolf/cerebrum.md` 的 Do-Not-Repeat（**先查顶部索引表，别通读**）。
