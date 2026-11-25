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

**8 条待裁项逐条裁完** ⇒ 落盘 `TODOS.md` ⇒ **P10-C 全部细项落地**（「测试报告页」裁为**不建**）⇒ P10-C 收批。

**「打回」**（人裁四问全定：退回 DRAFT + 被退回标记 · 沿用现状可见性 · 能改 · 要通知）：
⚠️ **不是新状态** ⇒ **9 态机一个字不改** ⇒ 「**待审**（DRAFT 且没被打回）vs **待改**（DRAFT 且被打回）」
是**两个态** ⇒ 队列只装前者 ⇒ 打完回**离开队列** ⇒ 创建人改稿（`update()` **清标记**）⇒ 自动回来
· 三列（`rejected_at`/`rejected_by`/`reject_reason`）+ 迁移 `p10_005`（**两库各一次**独立进程 +
`alembic check` exit 0 + 直查库）· 端点 `POST /definitions/{def_id}/reject`（**照抄 `publish()` 的判定
顺序**：禁自审 403 · 项目授权 404 **逐字同形** · `CREATOR_ONLY` 403 · 状态 409；**被打回 ⇒ 不能直接
发布**）· 通知**复用 `STEP_RETURNED`**（`NotificationKind` 四值裁决清单不动）· 前端：队列页「打回」+
原因弹窗（空原因**禁用**）· 列表页「**被退回**」badge · **SPEC §7.18.1**（V2.19）· 断言 **后端 13 ·
前端 5**（棘轮：端点 13→**14** · `STRICT_CLIENT_TEST_MIN` 172→**184**）

⚠️ **实施中七个坑**（QA 报告 §4）⇒ 最险一条：**`_as_dict()` 是手写的字段清单** ⇒ ORM 加了列而它没加
⇒ 响应**静默少一个字段** ⇒ 前端判据永远为假 ⇒ **badge 永远不亮**。

## ✅ Done（第 45 轮 · **P10-C · T1**（exporters · 状态页 · 监控栈 · 备份演练）· 2026-11-24）

人裁五问全 **A**。`GET /metrics`（**挂 app 根路径**，挂进 `api_router` 会变 `/api/v1/metrics` ⇒ 404）
· `GET /api/v1/status`（**恒 200** · 不复用 `/health` ⇒ liveness 叠阻塞依赖 ⇒ 重启循环 · **要登录**）
· `deploy/prometheus/**` + `deploy/grafana/**`（5 条告警）· `scripts/backup_restore_drill.py`。
车道：默认 **6152** · PG **46** · 前端 **1129**。
⚠️ **四个「假零/泄露」陷阱**（bug-2201/2202）：① **没人喂的 gauge = 假零** ⇒ 「待签署数」删掉
② 队列深度只在 `/status` 里 `.set()` ⇒ 没人开页面就永远 0 ⇒ 告警永不触发 ⇒ 改 **collector**
（scrape 时现读 · 端点改 `def`）③ collector 读不到 Redis ⇒ **不产出序列**（不是报 0）⇒ 加 `absent()`
④ `/status` 原本**匿名可读** ⇒ 运维内部信息 = 一张内部拓扑图 ⇒ 加 `current_user`

## ✅ Done（第 44 轮 · **P10-C · T0**（容器侧车道锁 + 部署前置清单）· 2026-11-24）

**容器侧也抢同一把车道锁** ⇒ ⇒ **TODO-163 闭**（`Dockerfile` 带 `flock` + `scripts/compose_lane_lock.sh`
同 inode ⇒ 宿主/容器互斥）· **TODO-137 闭**（`scripts/migrate_legacy_user_ids.py` · 幂等 ·
引用列**从 ORM metadata 推导** ⇒ 实测 9 列）· `docs/deploy-prerequisites.md`。
⚠️ 四个环境坑：容器内网到镜像源被限速（⇒ `--network=host`）· Debian slim 自带 `flock`
· 锁文件权限（docker 建的是 root ⇒ chmod）· 装 wheel 盖住挂载源码（⇒ `PYTHONPATH=/app`）

## ✅ Done（第 43 轮 · **P10-I · T2**（TODO-187b）· 2026-11-23）

**404 文案逐字同形** —— 守卫加 `not_found_code` / `not_found_message` ⇒ 「不存在」与「无权」逐字同形
⇒ 存在性不可枚举；⚠️ 默认文案一个字没改（124 处零影响）。AST 实扫 = **47 端点**（计划写 12 族）
⇒ 扫描单位改成「抛 404 的函数」。断言 = AST 完整性守卫 + 端到端 2 族 + 约束钉子（变异自证 3/3）。

（第 42 轮 P10-I·T1「待我审核」队列 · 第 41 轮 CAS 号核完 · 第 40 轮 P10-F·F4-PRE ⇒ ⇒ 查 `git log`）

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
4. ✅ **两份计划已批准**（2026-11-25 · 人裁「approve」）⇒ ⇒ ⇒ **下一批 = P10-J-T1（先做）**
   · **P10-J-T1**（公司级模板执行时选项目 · **滚 OpenAPI 契约**）
     ⇒ ⇒ 计划 `docs/superpowers/plans/2026-11-24-p10-j-t1-company-template-execute.md`
     ⇒ ⇒ 人裁：选项目**必选无默认** · 不要二次确认 · **项目级+别的项目 ⇒ 400 拒不一致**
     ⇒ ⇒ **默认车道 + 1 条 PG 用例**（那条**直连 ORM 插入**，否则是假证据）
   · **P10-K**（SPEC §7.5 向导 · **后做**，串行）
     ⇒ ⇒ 计划 `docs/superpowers/plans/2026-11-24-p10-k-spec75-project-wizard.md`
     ⇒ ⇒ 「项目模板」实体**已存在** ⇒ **7 段全落** ⇒ 待裁项**全部收口**
   ⇒ ⇒ ⚠️ 两批都改契约+前端类型 ⇒ ⇒ **串行** ⇒ ⚠️ P10-K 会先占一个 SPEC 版本号
5. **推送**：本轮提交**已授权 ⇒ 已推**

---

## Context

- main。**不要建 worktree** · **不要 `git checkout <commit> --detach`**。**不得擅自 push**。
  `.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- ⚠️ **每轮开工先查残留**：`fuser -v pcs-backend/.tmp/lane.lock` ·
  `pgrep -af "uvicorn app.main:app"` · `ss -ltnp | grep 5173`。
- ⚠️ **默认车道零连真 PG** ⇒ ⇒ 跑 `pg` 用例**必须**走 `bash scripts/pytest_pg.sh`（**唯一入口**
  · 需 **redis 起着**）。
- ⚠️ **`.env` 口令不要写命令行** ⇒ 用 `dotenv_values('.env')` **进程内**派生 URL
  ⇒ ⇒ **一库一个进程**（alembic settings 是 pydantic 缓存实例）。
- ⚠️ **本机环境三件套**（2026-11-24 实测）：宿主 **8000 端口被占**（Prometheus 抓不到 ⇒ 换端口/
  改 target）· **docker.io 不可达**（镜像源是运营侧决定 ⇒ 仓库里**不写死**第三方镜像）·
  **pypi.org/simple 不可达**但 **files.pythonhosted.org 可达**（⇒ 依赖下载不受影响 ⇒
  `uv lock` 跑不动 ⇒ **手工补 lock 条目**；**别**用镜像源重锁 ⇒ 会改写全仓依赖 URL）。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。

---

## 教训（**已进 cerebrum / docs/solutions / buglog**，此处只留最新）

- **「已覆盖」要能复核** ⇒ 判据 = **这条断言用的是 `strict_client`**（默认 `client` 把守卫
  mock 成永远 True ⇒ 那些断言是 **no-op**）。
- **标记只在「收集期」生效才叫车道隔离** ⇒ 闸门挂在 `pytest_collection_modifyitems`（不是运行时）。
- ⚠️ **指标「定义了」≠「有值」** ⇒ 无标签 gauge **创建即报 0** ⇒ 假零比没有更坏 ⇒ 每个 gauge
  必须有**真实的喂点**；事件驱动的量（队列深度）用 **collector**；「测不到」要**不产出序列**。
- ⚠️ **慢测试的闸门会被「负载 +1」打翻** ⇒ 别当回归 ⇒ 放宽到**有界**值（与 2026-10-21
  5s→20s 同族）⇒ 但**要在提交信息里写明**。
