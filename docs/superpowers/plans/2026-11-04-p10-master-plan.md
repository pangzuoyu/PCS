# P10 总纲：AI 预留 + 测试左移 + 部署可观测（批次划分与执行顺序）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 SPEC `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md` 的 8 个子批（10.0~10.7）**按「仓里实际缺什么」重排成 6 个可执行批次**，钉死顺序、依赖、验收口径与**对 SPEC 的偏离登记**。

**Architecture:** 总纲只定**批次边界与顺序**，不写实现细节。每一批另起一份细计划（bite-sized task）。本轮已把**第一批（P10-A：前置 + AI 预留）**写成可执行细计划 ⇒ `docs/superpowers/plans/2026-11-04-p10-batch-a-preflight-ai-reserve.md`。
**批次数仍 6**（不因前置遗留债项新起批次）⇒ 那些债项**归口到既有批次** ⇒ 见「〇、前置批次遗留债项归口」。

**Tech Stack:** FastAPI · SQLAlchemy 2.x async · Pydantic v2 · alembic · ARQ + Redis · pytest · Playwright（前端 E2E）· React 19 + antd 5

**Spec:** `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md`（V1.3.1 · 2026-10-27 · 冻结候选）

---

## Global Constraints

- **分支 `main`，不要建 worktree**（历史事故）。
- **conventional commits，不带 attribution 行**；长消息写文件后 `git commit -F <file>`。
- ⚠️ **口令不要写在命令行**（会被权限分类器拦）—— 只在环境变量 / 进程内派生。
- ⚠️ **不要用 `git checkout <commit> --detach`**。
- **改 `alembic/versions/*` ⇒ 必须手动核对 ORM 列同步**（本仓漂移盲区：单测照绿、真库会炸）。
- 契约改动 ⇒ 批末滚 OpenAPI baseline + 跑 G-08 `--check-baseline`；**裸载荷数不得上涨**。
- 前端类型**契约派生** ⇒ 后端加字段后必须重跑类型生成 + 同步 MSW mock（seed 走 ajv 校验 ⇒ 漏字段即红）。
- ⚠️ **本仓 CI 已有**：`.github/workflows/check-api-drift.yml`（在**全新 PG** 上跑 `alembic upgrade head` + API drift 闸门）⇒ **不要新建流水线**（与「单人开发 · CI/CD 不做」的裁决一致）。本批 CI 相关的**唯一**动作是「让现有闸门覆盖新代码」。
- ⚠️ **PG 版本 18**（仓里 `postgres:18-alpine`，CI 同）—— SPEC 部署架构图写的 **16 已过时**。
- ⚠️ **每批落地后必须跑 gstack-qa 浏览器回归**（流程见 `CLAUDE.md`），报告落 `.gstack/qa-reports/`（gitignored）。

---

## Review Focus

以下五类情形**没有现成测试**，但最可能咬到真实用户/运维；每条都在对应批次里落成测试。

1. **AI 路由的审计必须在「认证失败」时也留下记录**（`user_id=None`）—— 否则攻击者用无效 token 探测 AI 端点时**不留痕** ⇒ 审计表对探测行为完全失明。（P10-A）
2. **中间件读完 body 后，下游 Pydantic 仍要能收到 body** —— 纯 ASGI 中间件若吞了 body，AI 路由会报 422 而不是 501 ⇒ **症状与「参数错」无法区分**。（P10-A）
3. **AI 审计写库必须幂等**（同一 `request_id` 重试不产生第二行）—— ARQ 的 `max_tries` 重试若不幂等 ⇒ 一次请求留下 N 条审计 ⇒ 审计表被灌水。（P10-A）
4. **种子数据脚本必须可重复执行**（幂等）—— E2E 每次跑之前都要重置 ⇒ 脚本不幂等 ⇒ 第二次跑要么撞唯一约束、要么留下脏数据让断言飘。（P10-B）
5. **E2E 的页面导航必须走 SPA 菜单点击** —— 本仓 zustand auth store 是**内存态** ⇒ `page.goto` / `reload` 会清 session ⇒ 弹回 `/login` ⇒ 表格永远没有行。（P10-B）

---

## 〇、前置批次遗留债项归口（P9B-4 紧急批次收口 · 2026-11-10）

> **开工前先看这一节** —— P10 之前刚收完的 P9B-4 紧急批次留下 6 条债项 + 2 条相邻债
> ⇒ **它们不在 P10 的功能范围里，但决定 P10 能不能开工**。
> **批次数不变（仍 6 批）** ⇒ 债项**归口到既有批次**，**不新起 P10-G**。

### 〇-1 P9B-4 紧急批次的收口状态

| 项 | 内容 |
|---|---|
| 范围 | `3a929b6..cbc701b`（物流面 20 个端点的项目级访问守卫 + `GET /streams/{id}/review-log`） |
| ce-code-review | 判 **Ready with fixes**；8 项 actionable **已全部修完** ⇒ 报告与收口在 `docs/ce-code-review/20261109-181644-6f6ddca3/` |
| ⚠️ 修完 ≠ 修全 | 报告的 5 条 residual risk **升格成 TODO**（下表 6 条）⇒ 其中 3 条是「**上批修复不完整**」⇒ **P1**，不是「pre-existing 历史债」 |

### 〇-2 P9B-4 **体验批**的状态（**必须先说清**）

| 项 | 状态 |
|---|---|
| 计划 | `docs/superpowers/plans/2026-11-04-p9b-4-ux-batch.md`（2026-11-10 修订 · 新增 **Task T0 前置补课**） |
| 落地 | ✅ **已闭环**（2026-11-11）—— `a5f62c6..3e362ea`（**14 个 commit**：T0-A~T0-F + T1 + T2 + T3 账簿 + 评审修复）⇒ 已推 origin/main |
| 交付 | 停用**立即生效**（actor 层判 `users.status`）· **工作区归属**（`create_stream` 一律用项目的工作区）· 血缘**按源引用查**（注册表**派生** · 键=类名 · 未知类型 fail-closed · 同形合成 root · 具名 schema）· 真实登录**覆盖**写 `users.roles` · mock 登录**双闸**（`PCS_ENABLE_MOCK_LOGIN`，默认关）· 「**只重试失败项**」· 「**引用 📎×N**」 |
| 整支评审 | **Critical 0 · Important 3 全闭合**（roles 覆盖 / 血缘下游有界 / 共享标签表）+ Minor #1~#7 已修或已登记 ⇒ **Ready to merge** |
| 闸门 | 后端 5626 passed / PG 车道 5 · 前端 1046 · 裸载荷 71 · G-08 四阶段 RC=0 · 浏览器 QA **0C-0H-0M** |
| 与 P10 的关系 | ✅ **已完成** ⇒ P10-B 的 E2E 可以直接吃**真实**守卫行为（不再需要「兜底」语义） |
| ⚠️ 硬顺序 | ✅ **已满足** —— P9B-4 先于 P10-B 落地 ⇒ **P10-B 的血缘场景不再需要兜底**（TODO-136 已闭合） |

⚠️ **不重复施工**：TODO-132/133/134/135/136 **已排进 P9B-4 的 T0-B~T0-F**
⇒ P10 侧**不另起一批重做**；下表「P10 侧兜底」列是**P9B-4 若未先落地时的备选**。

### 〇-3 归口表

| # | 债项 | 严重度 | 首选承接 | P10 侧兜底 | 为什么这么归 |
|---|---|---|---|---|---|
| **TODO-132** | 守卫**不看 `users.status`** ⇒ 已禁用用户持**已发出的 token** 仍能访问 20+ 物流端点 | 🔴 | ✅ **已闭环**（`9d10767` · T0-B · actor 层判 ⇒ 停用**立即生效**） | — | 改的是守卫**判定语义** ⇒ 拖到 P10 才改 ⇒ 这期间每一次物流面改动都带着这个洞 ⇒ **已先落地** |
| **TODO-133** | `create_stream` **不校验 `workspace_id` 属于 URL 的项目** ⇒ 可把物流挂到别人的工作区 | 🔴 | ✅ **已闭环**（`5338eed` · T0-C · 一律用 `project.workspace_id`） | — | 同上（**跨项目写入**）；上批守卫补的是 URL 那一维，工作区那一维一直空着 ⇒ **已先落地** |
| **TODO-135** | mock 登录签发**任意 role claim** ⇒ 完整鉴权旁路，只靠 `settings.is_production` 一道闸 | 🔴 | ✅ **已闭环**（`ebd6819` · T0-F · **双闸** + 顺手救回一条**一直空转**的部署断言） | — | 与「上线前不许有旁路」是同一件事 ⇒ **已先落地**（⚠️ 副作用见下「mock 登录默认关」） |
| **TODO-136** | 血缘守卫的 `record_type` 注册表：键口径混用（类名/表名）+ 漏登记 **fail-open** | 🟡 | ✅ **已闭环**（`a1c3da1` · T0-D · 派生 + 键=类名 + **fail-closed** + 33 例） | — | ⚠️ **不是拼写问题**（实测：物流只作**源引用**、`data_lineage` 0 行）⇒ **已先落地** ⇒ **不再阻塞 P10-B** |
| **TODO-134** | seed 建出来的用户 `roles=[]` ⇒ 通知选人永远选不到他 | 🟡 | ✅ **已闭环**（`69b2327` · T0-E · 真实登录**覆盖**写 roles） | — | 写手册要写「谁会收到通知」⇒ **口径已定**（= 当前真实身份）⇒ P10-E 照此写 |
| **（P9B-4 T0-B 遗留）** | **运维手册须写「停用用户**立即生效**」** —— 停用后其**在手 access token 下一次请求即 401**（此前「停用后 token 仍可用至多 30 分钟」已**不成立**，见 ADR-0046 §⑤） | 🟡 | 代码 + ADR-0046 + UI-SPEC **已落**（`9d10767` 同 commit） | ⚠️ **P10-E 的手册清单项**（10.5 管理员手册 + 10.6 Runbook）**仍未写** | ⚠️ **运维手册尚不存在**（P10-E 未开工）⇒ 无处可写 ⇒ 登记在此，**P10-E 出手册时必须含这条**（否则运维仍按「30 分钟窗口」理解停用） |
| **TODO-137** | 遗留账号（`user_id` ≠ 派生值）的授权迁移 | 🟡 | **不进 P9B-4**（一次性运维动作） | **P10-C / P10-F 的部署清单项** | 迁移步骤已在 `TODOS.md` + `CLAUDE.md` §发布前检查 ⇒ **上线前必查**（P9B-4 已把它写进发布前检查清单） |
| **TODO-129** | 物流面**之外**的模块（`config.py` / `report_builder.py` / `psychro.py`…）守卫覆盖**未审** | 🟡 | 独立技术债 | **P10-F 的审阅范围**（与 TODO-136 成对） | 「守卫面扩大」正是 P10 的主题 ⇒ 审计放收口批；**没结论就不能说守卫补齐**（⚠️ TODO-136 已闭合 ⇒ 这条**不再成对**，单独成立） |
| **TODO-104**（索引部分） | review-log 查询用 `->>` ⇒ 表上 GIN 索引（`jsonb_path_ops`）**用不上** | 🟡 | 独立技术债 | **P10-D 的压测范围** | 性能债由**压测数据**驱动 ⇒ 不预先优化 |

#### 〇-3b **P9B-4 体验批新增的遗留**（2026-11-11 · 评审带出来的）

| # | 债项 | 严重度 | 首选承接 | 为什么这么归 |
|---|---|---|---|---|
| **TODO-143** | **两处缺索引**（`streams.upstream_stream_id` + `data_lineage(source_ref_type, source_ref_id)` ⇒ 列表聚合与血缘 Tab 都是**顺序扫描**）+ `reference_count` **未按项目隔离**（跨项目下游会计进本项目计数） | 🟡 | **P10-D**（索引债由**压测数据**驱动 ⇒ 同 TODO-104 的处理方式）+ `reference_count` 的口径**待裁决** | ⚠️ 三条都**要改 `alembic/versions/*`** ⇒ 独立批（批次数仍 6）⇒ 归口到已有批 |
| **TODO-138** | `TwoPhaseResult` **没有 `project_id`** ⇒ 无法登记血缘守卫 ⇒ fail-closed 下**永久 404** | 🟡 | **不排期**（只留触发条件） | 补列的成本（迁移 + 回填 + 检查所有写入点）**大于**收益（血缘需求**未验证**）⇒ 「不提供」比「提供了但永远 404」更清晰 |
| **TODO-140** | **设备引用（JSONB 数组）是否计入 📎×N** | 🟡 | **待裁决**（下一批） | 要**逐设备类型**定口径 + 性能方案（表达式索引？物化列？）⇒ 不是一行改动 |
| **TODO-141** | **全量测试迁移到 `strict_client`**（守卫测试的唯一入口） | 🟡 | **P10-B**（E2E 批次顺手把新写的守卫用例迁过去） | 默认 `client` fixture 把守卫 mock 成永远 True ⇒ 「端点缺守卫」**测不出来** ⇒ 越早迁移越早不漏 |
| **TODO-142** | 前端 review-log 的 `rowKey` 可能撞（同一事务两行） | ⚪ | **不排期**（低优先级） | 只影响极端情况下的渲染 ⇒ 不影响数据正确性 |
| **（副作用）** | **mock 登录**现在**默认关**（`PCS_ENABLE_MOCK_LOGIN`）⇒ **存量开发机 / E2E 起栈必须显式开** | 🟡 | **P10-A 的 T1/T3**（起栈命令 + Playwright `webServer` 都要带这一行） | ⚠️ 不开 ⇒ mock 登录 **403 `MOCK_DISABLED`** ⇒ **P10-A 的真后端 E2E 通道会红** ⇒ 见 P10-A 计划的「前置状态更新」 |

### 〇-4 对批次与估算的影响

| 批次 | 变化 | 估算 |
|---|---|---|
| **P10-A** | ⚠️ **起栈/E2E 要显式开 `PCS_ENABLE_MOCK_LOGIN=true`**（P9B-4 的副作用）⇒ 起栈命令 + Playwright `webServer` 各加一行 | 不变 |
| **P10-B** | 血缘 E2E 场景 ⇒ **TODO-136 已落地** ⇒ **兜底取消** | 2.1~3.2 → **2~3 人周** |
| **P10-C** | 部署前置清单：seed 授权行（TODO-131）+ 遗留账号迁移（TODO-137） | 不变 |
| **P10-D** | 压测范围 +「review-log 查询的 P95 ⇒ 决定是否加表达式索引」（TODO-104）+ **两处缺索引**（TODO-143 ⇒ 列表聚合 / 血缘 Tab 都是顺序扫描）⇒ 压测**多两个观测点** | 1~1.5 → **1.2~1.8 人周** |
| **P10-F** | 验收扩面（见 §六）：**① 三条越权债（✅ 已由 P9B-4 闭合 ⇒ 只做**复核**）② 物流面外守卫覆盖审计（TODO-129）③ 原 8 项收口** | 1.5~2.5 → **0.8~1.4 人周** |
| 跨批 | 守卫判定语义改动 ⇒ 物流面 20+ 端点的守卫测试与浏览器回归要重跑 | **已由 P9B-4 跑过** ⇒ 余量归零 |

⇒ **P10 总估算：10.5~16 → ≈8.4~12.2 人周**
（分项：2.5~3.5 + 2~3 + 1.5~2 + 1.2~1.8 + 1.5~2.5 + 0.8~1.4）

✅ **P9B-4 体验批已于 2026-11-11 落地** ⇒ 上面这组数字**就是实际估算**（不再是「若」）
⇒ **P10 便宜了 ≈2 人周** ⇒ 这就是它排 P10-B 之前的硬顺序的收益（已兑现）。

---

## 一、SPEC 的 10.0~10.7 与「仓里实际缺什么」的对照

> **这是本总纲的核心** —— SPEC 的子批划分假设「从零开始」，而仓里已经有相当一部分 ⇒ **照抄 SPEC 会做重复劳动，也会漏掉真正缺的东西**。

| SPEC 子批 | 内容 | 仓里现状（2026-11-04 实测） | 判定 |
|---|---|---|---|
| **10.0** 前置与测试左移 | CI 迁移校验 · docker-compose.test · 种子数据 · E2E 框架 | **CI 已有**（`check-api-drift.yml` 在全新 PG 跑 alembic）· **compose 已有**（postgres 18 / postgres-pgtest / redis / worker / **openldap + openldap-seed** = mock AD）· **Playwright 已有**（`pcs-frontend/e2e/`，2 个 spec）· **缺**：种子数据、compose 的「测试组」、E2E 公共 fixture | ⚠️ **一半已有** ⇒ 只补缺的 |
| **10.1** AI 预留接口 | 路由 501 · 两张表 · 递归脱敏 · OutboundAIClient · CIDR · 审计中间件 · /health/ai · 前端占位 | **几乎 0%**：无 `app/api/v1/ai/`、无 `ai_sanitizer.py`、无 `outbound_ai_client.py`、无 AI 中间件、无 `/health/ai`；`ai_audit_log` / `document_chunks` **表已存在但字段完全不同** | 🔴 **全量新做 + 两张表加列** |
| **10.2** 全流程 E2E | 18 场景 · SUP-007 五类路径 · 权限矩阵 · PR/nightly | Playwright 已装；**场景 0/18** | 🔴 大头 |
| **10.3** 性能压测 | k6 · P95/P99 · 错误率 · Redis · **PgBouncer 容量** · 报告 | **无 k6**；**无 PgBouncer**（compose 里应用**直连** PG）⇒ SPEC 部署图里的 PgBouncer 是**尚不存在的一层** | ⚠️ **需裁决**（见下） |
| **10.4** 部署与可观测性 | 完整 compose · exporters · Prometheus/Grafana/ELK · 状态页 · 测试报告页 · 备份演练 | compose 有基础；**无 exporters / 无监控栈 / 无状态页** | ⚠️ 新做 |
| **10.5** 用户文档 | 用户手册 · 管理员手册 · FAQ · 培训材料 | 部分 ADR 已有；**手册 / FAQ 无** | ⚠️ 新做 |
| **10.6** 知识转移 | 架构 · 依赖图 · ADR · Runbook · interrogate gate | ADR 有 40+；**Runbook 无** | ⚠️ 部分已有 |
| **10.7** 生产就绪评审 | 安全 · 漏洞 · 镜像 · 回滚 · 数据迁移 · 告警 · 备份 · Go/No-Go | — | ⚠️ 收口批 |

**SPEC 估算 7.5~12.5 人周**（4.5 节）；按仓里实际状态**重估为 10.5~16 人周**（分项加总：2.5~3.5 + 2.1~3.2 + 1.5~2 + 1~1.5 + 1.5~2.5 + 1.5~2.5 + 0.4~0.8）。
⚠️ 原口径是 9~13.5 ⇒ **+1.5~2.5** 来自「〇、前置批次遗留债项归口」（P9B-4 收口后带进来的守卫面债项）⇒ 构成：P10-F 扩面 +1~1.5 · P10-B 兜底 +0.1~0.2 · 跨批回归余量 +0.4~0.8 ⇒ 见〇-4。

⚠️ **与 SPEC 估的差在哪**：SPEC 的 7.5~12.5 假设「从零搭 CI / compose / E2E 框架」⇒ 那三项仓里已有 ⇒ 本该**更少**；但 10.1 因「给既有表加列 + 迁移 + 中间件 + 审计链路」比 SPEC 估的 0.5~1 人周**多约 1.5 人周**，10.3 因「PgBouncer 那一层仓里根本不存在」也**不在 SPEC 的估算里**；再叠上〇节的守卫面遗留债 ⇒ 落在 10.5~16。

---

## 二、批次划分与执行顺序

| 批 | 名称 | 对应 SPEC | 内容 | 估算 |
|---|---|---|---|---|
| **P10-A** | 前置与 AI 预留 | 10.0 + 10.1 | compose 测试组 · 种子数据 · E2E fixture（⚠️ **起栈要显式 `PCS_ENABLE_MOCK_LOGIN=true`**）· AI 路由/表/脱敏/客户端/CIDR/中间件/审计/健康端点/前端占位 | **2.5~3.5 人周** |
| **P10-B** | 全流程 E2E | 10.2 | 18 个场景 · SUP-007 五类路径 · 权限矩阵（⚠️ 血缘场景依赖 TODO-136 已落地 ⇒ 兜底 +0.1~0.2） | **2.1~3.2 人周** |
| **P10-C** | 部署与可观测性 | 10.4 | exporters · Prometheus/Grafana/ELK · 状态页 · 测试报告页 · 备份演练 · **部署前置清单**（seed 授权行 TODO-131 / 遗留账号迁移 TODO-137） | **1.5~2 人周** |
| **P10-D** | 性能压测 | 10.3 | k6 脚本 · P95/P99 · 错误率 · Redis 容量 · **review-log 查询的 P95 ⇒ 决定是否加表达式索引**（TODO-104）· ⚠️ **+两处缺索引的观测点**（TODO-143：`streams.upstream_stream_id` 聚合 + `data_lineage(source_ref_*)` 血缘查询 ⇒ 两者现在都是**顺序扫描**） | **1.2~1.8 人周**（⚠️ 不含 PgBouncer 引入） |
| **P10-E** | 用户文档 + 知识转移 | 10.5 + 10.6 | 手册 · FAQ · Runbook · ADR 补齐 · interrogate gate（顺手核对「通知选人」口径 · TODO-134） | **1.5~2.5 人周** |
| **P10-F** | 生产就绪评审 | 10.7 + **遗留债** | **① 三条越权债**（TODO-132 / 133 / 135）—— ✅ **已由 P9B-4 闭合** ⇒ 本批只做**复核**（不重做）· **② 物流面外守卫覆盖审计**（TODO-129）· **③ 安全 · 漏洞 · 镜像 · 回滚 · 迁移 · 告警 · 备份 · Go/No-Go** · 部署前置清单（TODO-131/137） | **0.8~1.4 人周**（原 1.5~2.5） |

**关键路径**（SPEC 4.2 的关键路径图仍然成立）：

```
P10-A ──→ P10-B ──→ P10-F
   └────────────→ P10-C / P10-D / P10-E（可并行）
```

**P10-F 的 P1 前置**：三条越权债（TODO-132/133/135）**默认由 P9B-4 体验批的 T0-B/T0-C/T0-F 满足** ⇒
**P9B-4 必须先于 P10-B 落地**（否则 E2E 按错的守卫语义写断言）；
**若不走 P9B-4** ⇒ 三条债**改由 P10-F 承接**（P10-F 估 1.5~2.5 已含它）⇒ P10-B 仍先于 P10-F。

**串行要求**：P10-B~F **不得**插入 P10-A 的 task 之间（共用 `pcs-frontend/e2e/` 与 `docker-compose.yml`）。

---

## 三、对 SPEC 的偏离登记（**必须回写 SPEC**）

> 这些不是「实现细节差异」，是**与 SPEC 字面不符**的地方 ⇒ 必须在 SPEC 上留痕（否则下一个读 SPEC 的人会以为 spec 说的就是代码里的样子）。

| # | SPEC 原文 | 仓里实际 | 裁决（2026-11-04 用户） | 回写位置 |
|---|---|---|---|---|
| **D1** | 部署架构图：`PostgreSQL 16 (主从复制)` | 仓里 **PG 18**（compose + CI 同步于 2026-10-07） | **以 18 为准** ⇒ 改 SPEC 的架构图 | SPEC §4.3 |
| **D2** | 10.0(3)：`docker-compose.test`（PG+pgvector / Redis / mock AD / backend / worker / frontend） | 现有 `docker-compose.yml` **已含** postgres / postgres-pgtest / redis / worker / **openldap+seed**（= mock AD） | **不新建文件** ⇒ 用现有 compose + **profile** 起测试组 ⇒ **改写 SPEC 的验收项措辞** | SPEC §3.2.0(3)(5) |
| **D3** | 10.1(2)：「P10 只执行 `CREATE EXTENSION IF NOT EXISTS vector`」 | `postgres:18-alpine` **不带 vector 扩展**；且 `document_chunks.embedding_vector` 是 **JSONB**（不是 vector）⇒ 扩展建了**无处可用** | **本批不建**，登记 TODO（待 P10-OPEN-002 裁决维度后一并做）⇒ compose/CI **不换镜像** | SPEC §3.2.1(2) |
| **D4** | 10.1(2)：`ai_audit_log` 表（9 个字段，`request_id` 唯一） | 仓里 `ai_audit_log` **已存在**（SUP-006 强制，字段完全不同） | **给既有表加列**（nullable）⇒ SUP-006 字段不动 ⇒ `request_id` 唯一索引用 **partial**（`WHERE request_id IS NOT NULL`）⇒ 既有行不冲突 | SPEC §3.2.1(2) + §4.1.4 |
| **D5** | 10.0(2)：CI 跑 `alembic upgrade head` 覆盖 `pcs` 与 `pcs_test` | 现有 CI 在**全新 PG** 上跑 alembic（更强的形态：验证迁移在**没建过任何表的库**上也能跑） | **已满足** ⇒ 不新建流水线；只在 SPEC 上把措辞改成「全新库 + 幂等闸门」 | SPEC §3.2.0(2) |
| **D6** | 10.1(2)：`document_chunks` 表（`document_id` / `content` / `source`） | 仓里 `document_chunks` **已存在**（`source_type` / `source_id` / `project_id` / `chunk_text` / `embedding_vector JSONB` / `token_count`） | **本批不动这张表** ⇒ 它不参与 P10 的 AI 预留路径 ⇒ 记 TODO（P10-OPEN-002 一并处理） | SPEC §3.2.1(2) |
| **D7** | 10.1(1)：`Depends(current_user)` | 仓里是 `current_actor`（返回 `_Actor`：`user_id` / `username` / `role`） | 用 `current_actor` | SPEC §3.2.1(1) |
| **D8** | 10.1(4)：中间件生成 `request_id` | 仓里 `add_trace_id` 中间件已生成 `request.state.trace_id`（`uuid4().hex`，**32 位无连字符**） | AI 审计的 `request_id` **另生成** `uuid4()` 标准 UUID 串 ⇒ 与 `trace_id` **并存但不同**（trace_id 走日志、request_id 走 AI 审计）⇒ 须在代码里写明「两者不是一回事」 | SPEC §3.2.1(4) |
| **D10** | 10.1(3)：「CI 使用 **import-linter** + 自定义架构测试」 | 仓里已有 `tests/architecture/` 的**自定义扫描**做法 ⇒ 本批**只加自定义守卫**，**不引入 import-linter**（多一个依赖、多一套配置） | SPEC §3.2.1(3) |
| **D11** | 10.1(5)：「`INTERNAL_CIDRS` … Settings 解析为 `list[str]`」 | 本批 env 侧保留**原始串** ⇒ 解析在 `ai_cidr.parse_cidrs`（**单一解析点**，且能报清晰错误） | SPEC §3.2.1(5) |
| **D12** | 4.1.2：请求体用 **`topK`** | 后端 schema 用 `top_k` + **alias `topK`**（`populate_by_name=True`）⇒ **契约里的字段名仍是 `topK`** ⇒ 与 SPEC 逐字一致 | SPEC §4.1.2 |
| **D13** | 10.1(9)：env 有 `AI_ENABLED` / `AI_TIMEOUT` | 本批把开关/参数**全部放 `system_settings`**（前端参数页可改）⇒ env 侧**不设** AI 开关 ⇒ **单一真相源 = system_settings** ⇒ 避免「两个开关 + AND 语义 + admin 改了却没生效」 | SPEC §3.2.1(9) |
| **D14** | 10.1(3)：`OutboundAIClient.__init__(endpoint, timeout)` | 本批加 **`cidrs`** 构造参数（调用时二次校验需要它）⇒ 构造签名多一个 | SPEC §3.2.1(3) |
| **D15** | 10.1(8)：`[project.optional-dependencies] ai = [langchain, ollama, vllm]` | 本批**照做**（加进 `pyproject.toml`）⇒ 默认 `uv sync` **不装** optional ⇒ 架构守卫的「全仓零命中」仍成立 | SPEC §3.2.1(8) |
| **D16** | 4.1.4：审计字段含 **`timestamp`** | 仓里 `ai_audit_log` **已有** `occurred_at`（16 列之一）⇒ 本批**复用它**当请求时间，**不新增第二个时间列**（两个时间列语义重叠 ⇒ 以后没人知道该读哪个） | SPEC §4.1.4 |
| **D9** | 10.1(2)：`system_settings` 保存 6 个 AI 键 | 仓里 `system_settings` 已有 7 个键（`DEFAULT_SETTINGS`），且**前端参数页显示全部键** | 追加 6 个 AI 键（`ai_enabled=false` / `ai_model_version=null` / `ai_endpoint=null` / `ai_timeout=30` / `ai_max_tokens=4096` / `ai_temperature=0.1`）⇒ 前端**自动可见**（无需改前端） | SPEC §3.2.1(9) |

---

## 四、需要用户裁决的开放问题（**P10-A 开工前必须定**）

| # | 问题 | 现状 | 建议 | 归属 |
|---|---|---|---|---|
| **Q1** | **PgBouncer 引入与否** | SPEC 部署图有 PgBouncer（transaction 池 / `max_prepared_statements=200`），但仓里应用**直连** PG | **P10-D 不引入**（引入要改所有服务的 `DATABASE_URL` + 会话级特性约束 + 迁移幂等脚本会踩 ⇒ 是个独立批次）⇒ SPEC 里把 PgBouncer 降级为「后续」 | 用户裁决 |
| **Q2** | **内网 CIDR 清单**（P10-OPEN-010） | 待 IT 提供 | 本批的 CIDR 校验**只做机制**（可配置、非法即启动报错）⇒ 用回环地址做测试 ⇒ **清单本身不影响本批开工** | 待 IT，不阻塞 |
| **Q3** | **SMTP 服务器**（P10-OPEN-003） | 待 IT | 与本批无关（通知模块）⇒ 不阻塞 | 待 IT |
| **Q4** | **GPU 资源**（P10-OPEN-001） | 待确认 | P10 是「预留」⇒ **不需要 GPU** ⇒ 不阻塞 | 待确认 |
| **Q5** | **开发计划升 V1.4**（P10-OPEN-008） | 待发布 | 本总纲 = V1.4 的 P10 部分 ⇒ **P10-A 收口（T15 Step 7）** 更新 `docs/PCS-PLAN-*.md` | P10-A 收口 |
| **Q6** | ~~**P9B-4 体验批先开还是与 P10-A 并行**~~ | ✅ **已裁决并已执行**（2026-11-11）：P9B-4 **独立跑完**（`a5f62c6..3e362ea`）⇒ 三条越权债闭合 ⇒ **P10 总估省 ≈2 人周** | 已闭 |
| **Q7** | **`reference_count` 是否按项目隔离**（TODO-143 的第三条） | ✅ **已裁决并已落地**（2026-11-11）：**① 只算同项目** —— `StreamService.reference_counts(db, ids, *, project_id)`（`project_id` **必填关键字参数** ⇒ 忘传编译期就红）⇒ 两条聚合各带一个 `project_id` 谓词 ⇒ **零迁移**（两列本来就存在）⇒ ⚠️ **今天的数值一个都没变**（`create_outlet_stream` / `flash_persist` 都强制同项目 ⇒ 跨项目引用造不出来）⇒ **前瞻性保护**（DB 层**允许**跨项目 ⇒ 过滤必须落在查询上） | ✅ 已闭 |
| **Q8** | **设备引用（JSONB 数组）是否计入 📎×N**（TODO-140） | ✅ **已裁决**（2026-11-11）：**① 维持不计** —— 四条障碍（装的是 **PRO/II tag 字符串**非 UUID · 设备表**无 `project_id`** · JSONB 展开**全表扫** · 「进料/出料/塔侧线/计算器序列」**口径未定义**）⇒ 维持现状，SPEC §7.7.1 已写明（V2.15） | ✅ 已闭（**触发式重开**：真有人问「这条物流被哪些设备用了」⇒ 做成**详情页反查**，不做列表页计数） |

---

## 五、第一批（P10-A）的交付清单

**明细见** `docs/superpowers/plans/2026-11-04-p10-batch-a-preflight-ai-reserve.md`。

| 段 | 内容 | 状态 |
|---|---|---|
| **10.0 前置与测试左移** | compose 测试组（profile，不新建文件）· 种子数据脚本（幂等）· E2E 公共 fixture（登录 + SPA 导航 + 数据重置） | 📋 计划已写 |
| **10.1 AI 预留接口** | AI 开关与 Settings · CIDR 校验 · 递归脱敏 · `ai_audit_log` 加列 + 迁移 · OutboundAIClient + `AINotImplementedError` · AI 路由骨架（501）· 纯 ASGI 审计中间件 · ARQ 审计任务（幂等）· `/health/ai` · 前端顶栏占位 · 架构守卫（禁直接 import AI SDK） | 📋 计划已写 |

---

## 六、验收（总纲层）

| 门 | 判据 |
|---|---|
| 批次顺序 | P10-A 全批 commit 落地后，才开 P10-B；P10-C/D/E 可在 P10-B 期间并行 |
| **遗留债（历史债）** | **P10-F 开工前**：三条越权债（TODO-132 禁用用户 / TODO-133 workspace 归属 / TODO-135 mock 旁路）✅ **已由 P9B-4 闭合**（`9d10767` / `5338eed` / `ebd6819`）⇒ P10-F 只做**复核**（不重做）；血缘守卫的注册完整性（TODO-136）✅ 已闭合 + 33 例钉住；**物流面外模块的守卫覆盖审计有结论**（TODO-129：缺口逐条登记 TODO，不留「未审即没问题」）<br>⚠️ **P9B-4 带出来的新债**：TODO-143（两处缺索引 + `reference_count` 项目隔离）⇒ 索引归 **P10-D**（压测驱动）+ 口径归 **Q7 裁决** |
| 偏离登记 | **D1~D16** 全部回写进 SPEC（`spec/PCS-SPEC-P10 V1.3.1 ….md`）⇒ 每个偏离都有裁决与理由 |
| 契约 | 每批批末：G-08 `--check-baseline` 4/4 · 裸载荷不涨 · 前后端类型同步 |
| 迁移 | 每批改了 `alembic/versions/*` ⇒ **两库各跑一次独立进程**的 `alembic check` + 直查 `alembic_version`（⚠️ 同进程第二次改 `DATABASE_URL` 不生效 —— pydantic 缓存） |
| 浏览器 | 每批批末 gstack-qa 回归：0 error / 0×404 / 核心路由可达 |
| **部署前置** | 每个环境上线前跑一次 `scripts/seed_user_project_access.py`（TODO-131）⇒ 若库里有 `user_id ≠ 派生值` 的遗留行 ⇒ **先按 TODO-137 迁移**，否则 legacy 用户处处 404 |
| **性能** | 压测报告给出 **review-log 查询的 P95** ⇒ 据此决定是否加 `detail_json->>'transition'` 表达式索引（TODO-104 索引部分）⇒ 不预先优化 |
| 账簿 | 每批结束写 `.wolf/STATUS.md` + `TODOS.md` + `.wolf/buglog.json` |

---

## 尚未解决的问题（开工前需裁决或登记）

| # | 问题 | 现状 | 归属 |
|---|---|---|---|
| 1 | **PgBouncer 引入与否**（Q1） | SPEC 部署图有、仓里没有 ⇒ 引入是独立批次 | 用户裁决 · P10-D 开工前 |
| 2 | **P10-OPEN-002 pgvector 维度** | 未定 ⇒ 本批不建扩展（D3） | P10-A 收口登记 TODO |
| 3 | **P10-OPEN-010 内网 CIDR 清单** | 待 IT ⇒ 只影响真实启用，不影响机制实现 | 不阻塞 |
| 4 | **P10-OPEN-003 SMTP** / **001 GPU** | 待 IT / 待确认 ⇒ 与 AI 预留无关 | 不阻塞 |
| 5 | **P10-OPEN-013 中6/中7 复审条目闭环** | 文档治理 ⇒ 需对照《复审结论：V1.2 ….》原文逐条补记或书面作废 | P10-E（文档批） |
| 6 | **18 个 E2E 场景的种子数据规模** | 未知 ⇒ P10-B 开工前先量一次 | P10-B 开工前 |
| 7 | **AI 端点的前端占位形态** | UI-SPEC §顶栏写「打开 AI 助手抽屉（P10 预留，先禁用并提示）」⇒ 本批做**禁用按钮 + tooltip**；抽屉不做 | 已定（P10-A） |
| 8 | ~~**P9B-4 体验批 vs P10-A 的先后**~~ | ✅ **已闭合并执行**（2026-11-11 · `a5f62c6..3e362ea`）⇒ P10 估省 ≈2 人周 | 已闭 |
| 8b | ~~**`reference_count` 是否按项目隔离**（Q7 / TODO-143-3）~~ | ✅ **已闭合并落地**（2026-11-11 · 裁决 ① 只算同项目）⇒ `reference_counts` 的 `project_id` 改**必填关键字参数** + 两条聚合各带 `project_id` 谓词 ⇒ **零迁移**、**前端零改动** | 已闭 |
| 8c | **两处缺索引**（TODO-143：① `streams.upstream_stream_id` ② `data_lineage(source_ref_type, source_ref_id)`） | 列表聚合与血缘 Tab 现在都是**顺序扫描** ⇒ 要改 `alembic/versions/*` | **P10-D**（压测驱动 ⇒ 同 TODO-104） |
| 8d | ~~**设备引用是否计入 📎×N**（Q8 / TODO-140）~~ | ✅ **已闭**（2026-11-11 · 裁决 ① 维持不计）⇒ SPEC §7.7.1 已写明四条障碍 + **触发式重开**条件 | 已闭（触发式重开） |
| 8e | **全量测试迁 `strict_client`**（TODO-141） | 默认 `client` 把守卫 mock 成永远 True ⇒ 守卫缺陷**测不出来** | **P10-B**（顺手迁新写的用例） |
| 8f | **mock 登录默认关** ⇒ **存量开发机 / E2E 起栈要显式 `PCS_ENABLE_MOCK_LOGIN=true`** | 不开 ⇒ **403 `MOCK_DISABLED`** | **P10-A 的 T1/T3**（起栈命令 + Playwright `webServer`） |
| 8g | **`TwoPhaseResult` 无 `project_id`**（TODO-138）⇒ 血缘永久 404 | 裁决：**不补列**（只留触发条件） | 不排期 |
| 9 | ~~TODO-136 的键口径 + `root` 语义~~ | ✅ **已裁决**（2026-11-10 两轮委员会）：键口径 = **写入方的类名**；`streams` 是「按源引用查」的入口键；**合成 root**（与 `_serialize` 的 10 字段同形）+ 注册完整性三步（快照 ✅已做 ⇒ 21 类型 / 20 可登记 / 1 个 `TwoPhaseResult` 不补列） | 已闭合并落进 P9B-4 T0-D |
| 10 | **TODO-129 审计范围有多大** | 物流面外的候选：`config.py` 12 端点 / `report_builder.py` 9 / `psychro.py` 13 … ⇒ 审计本身可能产生一串新债 | P10-F（与 TODO-136 成对；缺 strict_client 则测不出 ⇒ TODO-128 一并考虑） |
