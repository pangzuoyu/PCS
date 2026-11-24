---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-24（第 45 轮：
> **P10-C · T1 落地** —— exporters + 状态页 + 监控栈 + 备份演练 · QA 全绿）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 46 轮 · **P10-J · T2**（「打回」动作 · TODO-197b）· 2026-11-24）

**8 条待裁项逐条裁完**（用户要求「逐一让我裁定」）⇒ ⇒ ⇒ 落盘在 `TODOS.md`
⇒ ⇒ ⇒ **P10-C 全部细项落地**（「测试报告页」裁为**不建**）⇒ ⇒ ⇒ P10-C 收批。

**「打回」**（人裁四问全定：退回 DRAFT + 被退回标记 · 沿用现状可见性 · 能改 · 要通知）：

- ⚠️ **不是新状态** ⇒ ⇒ ⇒ **9 态机一个字不改** ⇒ ⇒ ⇒ 「**待审**（DRAFT 且没被打回）
  vs **待改**（DRAFT 且被打回）是两个态 ⇒ ⇒ ⇒ 队列只装前者 ⇒ ⇒ ⇒ 打完回**离开队列**
  ⇒ ⇒ ⇒ 创建人改稿（`update()` **清标记**）⇒ ⇒ ⇒ 它自动回来
- 三列（`rejected_at` / `rejected_by` / `reject_reason`）⇒ ⇒ ⇒ 迁移 `p10_005`
  ⇒ ⇒ ⇒ **两库各一次**（独立进程）+ `alembic check` exit 0 + 直查库确认
- 端点 `POST /definitions/{def_id}/reject`（**照抄 `publish()` 的判定顺序**）
  ⇒ ⇒ ⇒ 禁自审 403 · 项目授权 404（**逐字同形**）· `CREATOR_ONLY` 403 · 状态 409
  ⇒ ⇒ ⇒ **被打回 ⇒ 不能直接发布**（409）⇒ ⇒ ⇒ 否则「刚打回的那一版」被原样发出去
- 通知**复用 `STEP_RETURNED`**（「退回」）⇒ ⇒ ⇒ `NotificationKind` 的**四值裁决清单不动**
- 前端：队列页「打回」+ 原因弹窗（空原因**禁用**）· 列表页「**被退回**」badge + 原因
- **SPEC §7.18.1**（V2.19）· 断言 **后端 13 · 前端 5**
  ⇒ ⇒ ⇒ 棘轮：端点进台账（13 → **14**）· `STRICT_CLIENT_TEST_MIN` 172 → **184**

⚠️ **实施中撞到的七个坑**（详见 QA 报告 §4）⇒ ⇒ 最险的一条：
**`_as_dict()` 是手写的字段清单** ⇒ ⇒ ⇒ ORM 加了列而它没加 ⇒ ⇒ ⇒
响应**静默少一个字段** ⇒ ⇒ ⇒ 前端判据永远为假 ⇒ ⇒ ⇒ **badge 永远不亮**。

## ✅ Done（第 45 轮 · **P10-C · T1**（exporters · 状态页 · 监控栈 · 备份演练）· 2026-11-24）

人裁 2026-11-24 五问全 **A**（镜像 / 监控栈 / 状态页 / 备份演练 / 告警出口只落 Prometheus）。

- **exporters**：`app/core/metrics.py` + `app/api/v1/metrics.py` ⇒ ⇒ `GET /metrics`
  ⇒ ⇒ **挂 app 根路径**（挂进 `api_router` ⇒ ⇒ 路径成 `/api/v1/metrics` ⇒ ⇒ 404）
  ⇒ ⇒ **不进 OpenAPI** ⇒ ⇒ 契约零变化；标签用**路由模板** ⇒ ⇒ 基数有上界
- **状态页**：`GET /api/v1/status`（**恒 200** · 五组件）+ 前端 `/status` 页
  ⇒ ⇒ **不复用 `/health`**（liveness probe ⇒ ⇒ 叠阻塞依赖 ⇒ ⇒ 重启循环）
  ⇒ ⇒ **要登录** ⇒ ⇒ **不含敏感值**（URL 凭据打码）⇒ ⇒ **SPEC §7.22**（V2.18）
- **监控栈**：`deploy/prometheus/{prometheus,rules}.yml` + `deploy/grafana/provisioning/**`
  ⇒ ⇒ **5 条告警**（5xx 率 · P95 · 队列积压 · **队列测不到** · 状态机失败）
- **备份演练**：`scripts/backup_restore_drill.py` ⇒ ⇒ dump → 恢复临时库 → **断言**
  （revision 一致 · 5 表行数一致 · `alembic check` exit 0）⇒ ⇒ 失败即非零退出
- **车道**：默认 **6152 passed**（基线 6137 ⇒ +15）· PG **46** · 前端 **1129**（基线 1125 ⇒ +4）
  · 容器 `docker build` exit 0 · 宿主持锁 ⇒ ⇒ `docker compose run --rm migrate` exit 1
- ⚠️ **三个「假零」陷阱**（本批实测修掉 ⇒ ⇒ 详见 `.wolf/buglog.json` bug-2201/2202）：
  ① **没人喂的 gauge = 假零**（创建即报 0）⇒ ⇒ 「待签署数」**删掉**（TODO-200）
  ② 队列深度若只在 `/status` 里 `.set()` ⇒ ⇒ **没人开页面就永远 0** ⇒ ⇒ 告警永不触发
  ⇒ ⇒ 改成 **collector**（scrape 时现读）⇒ ⇒ 端点改 **`def`**（阻塞读不进事件循环）
  ③ collector 读不到 Redis ⇒ ⇒ **不产出序列**（不是报 0）⇒ ⇒ 另加 `absent()` 告警
  ④ **`/status` 原本匿名可读** ⇒ ⇒ 运维内部信息 = 一张内部拓扑图 ⇒ ⇒ 加 `current_user`

## ✅ Done（第 44 轮 · **P10-C · T0**（容器侧车道锁 + 部署前置清单）· 2026-11-24）

**容器侧也抢同一把车道锁** ⇒ ⇒ **TODO-163 闭**（原先「直接 `docker compose run --rm seed`」
能绕过宿主锁 ⇒ ⇒ 与跑着的车道并发建 schema ⇒ ⇒ 「偶发卡住」）。
`Dockerfile`（生产镜像 · 带 `flock`）· `scripts/compose_lane_lock.sh`（同 inode ⇒ ⇒ 宿主/容器互斥）
· **TODO-137 闭**（`scripts/migrate_legacy_user_ids.py` · 幂等 · **迁完不留遗留行** ·
引用列**从 ORM metadata 推导** ⇒ ⇒ 实测 9 列）· `docs/deploy-prerequisites.md`。
⚠️ **四个环境坑**：容器内网到镜像源被限速（⇒ `--network=host`）· Debian slim 自带 `flock`
· 锁文件权限（docker 建的目录是 root ⇒ ⇒ chmod）· 装 wheel 盖住挂载源码（⇒ `PYTHONPATH=/app`）。

## ✅ Done（第 43 轮 · **P10-I · T2**（TODO-187b）· 2026-11-23）

**404 文案逐字同形** —— 守卫加 `not_found_code` / `not_found_message` ⇒ ⇒ 端点把自己那条传进去
⇒ ⇒ 「不存在」与「无权」**逐字同形** ⇒ ⇒ 存在性不可枚举。⚠️ 默认文案一个字没改（124 处零影响）。
AST 实扫 = **47 端点**（计划写 12 族）⇒ ⇒ 另有 4 处 own-404 在 helper 里 ⇒ ⇒ 扫描单位改成
「抛 404 的函数」。断言 = AST 完整性守卫 + 端到端 2 族 + 约束钉子（**变异自证 3/3 全红**）。

（第 42 轮 P10-I · T1「待我审核」队列 · 第 41 轮 CAS 号核完 · 第 40 轮 P10-F · F4-PRE ⇒ ⇒ 查 `git log`）

---

## 🚀 Next quest

1. ✅ **P10-C 全部细项落地**（exporters · 监控栈 · 状态页 · 备份演练 · 「测试报告页」
   ⇒ ⇒ **不建**）⇒ ⇒ **P10-C 收批**
2. ✅ **2026-11-24 · 8 条待裁项逐条裁完**（见 `TODOS.md`「逐条裁决落盘」）
   ⇒ ⇒ ⇒ **TODO-196 已签字**（`docs/adr/signatures/dmc-component-cas-signoff.md`）⇒ ⇒ 关闭
   ⇒ ⇒ ⇒ **TODO-200 / 201 / 202 / 153 关闭**
3. ✅ **P10-J-T2「打回」已落地**（第 46 轮）⇒ ⇒ **不动契约 / 不动 9 态机**
   ⇒ ⇒ ⇒ 提交 `90fd4a56`（feat）+ `c9e4643e`（buglog 两条 2203/2204）
   ⇒ ⇒ ⇒ 车道：默认 **6166 passed**（上批 6153 ⇒ +13）· PG **46 passed** · 前端 **1134**
4. ⏸ **下一批 = 待批准**（2026-11-24 用户裁决：**新计划须经批准才能执行**）
   · **P10-J-T1**（公司级模板执行时选项目 ⇒ ⇒ **要滚 OpenAPI 契约**）
     ⇒ ⇒ ⇒ 计划：`docs/superpowers/plans/2026-11-24-p10-j-t1-company-template-execute.md`
     ⇒ ⇒ ⇒ 人裁已补：「选项目」**必选、无默认** · **不要**二次确认弹窗
   · **P10-K**（SPEC §7.5 项目向导）⇒ ⇒ ⇒ 计划：
     `docs/superpowers/plans/2026-11-24-p10-k-spec75-project-wizard.md`
     ⇒ ⇒ ⇒ ⚠️ **实测推翻 TODO-203 的前提** ⇒ ⇒ ⇒ 「项目模板」实体**已存在**
     ⇒ ⇒ ⇒ **零迁移** ⇒ ⇒ ⇒ 但留 **6 条待裁 + 1 处结构性未决**
   ⇒ ⇒ ⇒ ⚠️ 两批**都改契约 + 前端类型** ⇒ ⇒ ⇒ ⇒ ⇒ **串行**（别并行）
5. **推送**：本轮提交**已授权 ⇒ 已推**

---

## Context

- main。**不要建 worktree** · **不要 `git checkout <commit> --detach`**。**不得擅自 push**。
  `.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- ⚠️ **每轮开工先查残留**：`fuser -v pcs-backend/.tmp/lane.lock` ·
  `pgrep -af "uvicorn app.main:app"` · `ss -ltnp | grep 5173`。
- ⚠️ **默认车道零连真 PG**（`pg` 用例只在车道跑）⇒ ⇒ 要跑它们**必须**走
  `bash scripts/pytest_pg.sh`（**唯一入口**）⇒ ⇒ 该车道要求 **redis 起着**。
- ⚠️ **`.env` 的口令不要写命令行** ⇒ 用 `dotenv_values('.env')` 在**进程内**派生 URL
  ⇒ ⇒ **一库一个进程**（alembic 的 settings 是 pydantic 缓存实例）。
- ⚠️ **本机环境三件套**（2026-11-24 实测）：**宿主 8000 端口被别的服务占着**
  （Prometheus 抓不到 ⇒ ⇒ 换端口或改 target）· **docker.io 不可达**（镜像源是**运营侧决定**
  ⇒ ⇒ 仓库里**不写死**第三方镜像）· **pypi.org/simple 不可达**但
  **files.pythonhosted.org 可达**（⇒ ⇒ 依赖**下载**不受影响 ⇒ ⇒ `uv lock` 跑不动 ⇒ ⇒
  手工补 lock 条目；**别**用镜像源重锁 ⇒ ⇒ 会改写**全仓**依赖 URL）。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。

---

## 教训（**已进 cerebrum / docs/solutions / buglog**，此处只留最新）

- **「已覆盖」要能复核** ⇒ ⇒ 判据 = **这条断言用的是 `strict_client`** ⇒ ⇒
  默认 `client` 把守卫 mock 成永远 True ⇒ ⇒ 那些断言是 **no-op**。
- **标记只在**「收集期」**生效才叫车道隔离** ⇒ ⇒ 闸门必须挂在
  `pytest_collection_modifyitems` 上（不是运行时）。
- ⚠️ **指标「定义了」≠「有值」** ⇒ ⇒ 无标签 gauge **创建即报 0** ⇒ ⇒ 假零比没有更坏
  ⇒ ⇒ 每个 gauge 必须有**真实的喂点**；事件驱动的量（队列深度）要用 **collector**
  ⇒ ⇒ 「测不到」要**不产出序列**，而不是报 0。
- ⚠️ **慢测试的闸门会被「负载 +1」打翻** ⇒ ⇒ 别把它当回归 ⇒ ⇒ 放宽到**有界**的值
  （与 2026-10-21 全局 5s→20s 同族处置）⇒ ⇒ 但**要在提交信息里写明**。
