---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-13（第 30 轮：
> **P10-A 整批评审（round 2 · 含 hermes 第三视角）的 23 条可执行发现全落地**
> + 批末闸门抓到 **bug-2162**；**未 push**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 30 轮：P10-A 整批评审修复）

来源：`docs/ce-code-review/20261112-181851-76e48fc4/report.md`（round 2 · 23 条可执行：
P1×6 · P2×14 · P3×3 · 裁决 **Ready with fixes**）· 账簿
`.superpowers/sdd/2026-11-12-p10a-review-fixes/progress.md` · 报告入库 `3e71d0d`。

**落地**：#1 #2 #3 #4 #6 #7 #8 #9 #10 #11 #12 #13 #14 #15 #16 #17 #18 #19 #20 #22 #23 #24 #29
（+ #21 的代码部分）⇒ **23 条全修**（TDD RED→GREEN，一组一个 commit，未 push）。

**批末闸门抓到的真红（bug-2162）**：全量后端测试红一条
（`test_ws_notifications.py::test_ws_accepts_a_valid_token` ⇒ asyncpg
「attached to a different loop」）⇒ 病因在**别的文件**：
`tests/conftest.py::_avoid_real_db_probe` 只 patch 了**定义处**
⇒ 消费者 `app/api/v1/health.py` 是 `from ... import` **按值导入** ⇒ 补丁够不着
⇒ **「单测不碰真库」的守卫一直是空壳** ⇒ 单测真连了开发库 ⇒ 那次探测创建
**模块级单例**的 async engine ⇒ 连接绑定在当时的 loop 上 ⇒ **下一个文件的下一个
loop** 拿到死连接 ⇒ 红。
⇒ 修法 = **同时 patch 消费者侧的绑定**（守卫不再是空壳）+ 加**回归钉子**
（打过 `/api/v1/health` 后 `_async_engine` 必须仍是 None）。
⇒ 解法已入库 `docs/solutions/testing-issues/guard-patched-definition-site-consumer-imported-by-value.md`。

**QA 门禁**：`npm run typecheck` / `lint` clean · 前端 **1054 passed**（116 files）·
`gate_08` **259 paths / 378 schemas** drift 一致 · 裸载荷 **71 未涨** ·
浏览器 **36 条路由全 200 · 0 console error · 0×404/500（6184 请求）**
⇒ 报告 `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-13-p10a-review-fixes.md`。

**刻意没动（报告划给 human / release）**：#25（cerebrum 超限 ⇒ 归档需**策展**，
最旧几条**仍活着**且被 `CLAUDE.md` 引用）· #26（改已发布请求形状）·
#27（根因在 `openapi-typescript` 对带 `default` 属性的取舍 ⇒ 影响**全部**类型）·
#28（今天不可达的 latent P3）⇒ 清单与理由见账簿与上份报告。

---

## ✅ Done（第 29 轮：P10-A —— 前置与测试左移 + AI 预留接口）

计划：`docs/superpowers/plans/2026-11-04-p10-batch-a-preflight-ai-reserve.md`（总纲
`2026-11-04-p10-master-plan.md`）· 账簿 `.superpowers/sdd/2026-11-04-p10-batch-a-preflight-ai-reserve/progress.md`

**段一**：compose 加 `seed` 一次性服务（test profile）· 幂等种子脚本（固定 UUID +
`--reset` 只删自己 + 必造 `UserProject` 授权行）· 真后端 E2E 通道（关 MSW +
Playwright `real-backend` + 代理目标可 env 覆盖 + mock-login 路径改写）。

**段二**：6 个 AI 键 · `internal_cidrs` + 启动时校验 · 递归脱敏 + 规范化哈希
（人名遮蔽默认关）· `ai_audit_log` 加 8 列 + 迁移 `p10_001`（partial 唯一索引；
时间列复用 `occurred_at`）· 501 专用信封 · `OutboundAIClient`（唯一出口）·
5 个 AI 端点（一律 501）· ARQ 审计任务（幂等）· 纯 ASGI 审计中间件
（认证失败也留痕 + body 重放）· `/api/v1/health/ai` · 架构守卫。

**真库才暴露的缺陷（已修）**：PG `ON CONFLICT (request_id)` 匹配不到 **partial** 唯一索引
⇒ 每次写 AI 审计都炸，而单测（SQLite）全绿 ⇒ 补 `index_where` + PG 车道新增用例
（`bug-2159`）。**SPEC 偏离登记 D1~D22 已回写**（该 SPEC 实际是 **V1.0** ⇒ D20）。

---

## 🚀 Next quest

1. **下一批 = P10-B（全流程 E2E）**：18 个场景 · SUP-007 五类路径 · 权限矩阵。
   ⚠️ 开工前先做 **TODO-149**（量一次种子数据规模 —— 本批的种子只够跑冒烟）。
   ⚠️ 权限矩阵要用 per-user 的**项目内角色** ⇒ 本批种子里是**统一 `DESIGNER`**
   （见 `scripts/seed_e2e_data.py::SEED_PROJECT_ROLE`）⇒ P10-B 要改这一处。
   ⚠️ 真后端通道现在**有数据级断言**（读种子项目 ⇒ 必须 200）⇒ 后端必须连
   **`pcs_pgtest`（宿主 5433）** ⇒ 别用 `.env` 的开发库（README 已写）。
2. **P10-C/D/E/F** 仍未开工（部署可观测 / 压测 / 文档 / 生产就绪评审）。
3. **本轮未 push**（用户未要求）。
4. **新增 TODO**：146（AI 可选依赖推迟 · D19）· 147（pgvector 维度）·
   148（内网 CIDR 清单待 IT）· 149（P10-B 前量种子规模）· 150（AI 端点权限模型待定）·
   **151**（FastAPI 422 信封对深层嵌套 JSON 自己 `RecursionError` · bug-2161）。

---

## Context

> ⚠️ **迁移 / PG 车道 / 裸载荷基线 / 发布前检查** ⇒ 见 `CLAUDE.md`（§测试前检查、§发布前检查）⇒ **不重复**。

- main。**不要建 worktree**（历史事故）· **不要 `git checkout <commit> --detach`**。
  **不得擅自 push**。`.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- 提交约定：conventional commits，**带** `Co-Authored-By: Claude Code` 行；长消息写文件后 `git commit -F`。
- ⚠️ **本机 8000 端口被别的服务占着**（root 起的另一个项目）⇒ PCS 后端起在 **8001**，
  前端代理用 `VITE_API_PROXY_TARGET=http://localhost:8001`。
- ⚠️ **mock 登录的真实路径是 `/auth/mock-login`**（不在 `/api/v1` 下 · ADR-0046）⇒
  前端 axios baseURL 是 `/api/v1` ⇒ **vite proxy 里有一层改写** ⇒ 改它时别忘了这条。
- ⚠️ **跑 pytest 前先清掉残留进程**：本机多次出现**上几轮遗留的 pytest**在跑
  ⇒ 满负载 ⇒ Playwright 的 `locator.click` **30s 超时假红**（实测两次假红）。
  ⇒ 跑 e2e 前 `pgrep -af pytest` 看一眼。
- ⚠️ **dev server 改动 `vite.config.ts` 后要重启**：`reuseExistingServer` 会复用
  旧 server ⇒ 用旧配置 ⇒ 症状是「登录页渲染不出来」。
- ⚠️ **ARQ 0.28 只对 `Retry` 异常重试**（其余当场判死）⇒ 「max_tries=5 ⇒ 重试必然
  发生」在本仓**不成立**。
- ⚠️ **`.wolf/cerebrum.md` 已 ≈24 590 token**（目标 ≤24 000）⇒ 清退窗口已到
  ⇒ 但**别机械搬最旧的**（#25：最旧的几条**仍活着**且被 `CLAUDE.md` 引用）。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。
- ⚠️ **本机 PyPI 下载不稳**（反复 `Recv failure: 连接被对方重置`）⇒ 容器里
  `uv run --frozen` 装依赖会卡住 ⇒ **别把「容器路径跑得通」当成理所当然**。

---

## 教训（**已进 cerebrum / docs/solutions**，此处只留最新两条）

- **单测跑 SQLite ⇒ 碰不到 PG 的方言分支** ⇒ PG 独有的失败形状要有 **PG 车道**用例。
- **纯 ASGI 中间件读 body ⇒ 必须重放** ⇒ 否则症状是 **422** 而不是本该报的 501。
⇒ 其余历史教训查 `.wolf/cerebrum.md` 的 Do-Not-Repeat（**先查顶部索引表，别通读**）
   与 `docs/solutions/`。
