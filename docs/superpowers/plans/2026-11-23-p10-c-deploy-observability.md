# P10-C 主体 · 部署与可观测性 · 计划

> 2026-11-23 建。**F4 的前置**（没镜像 / 部署物 / 告警 ⇒ F4 开不了）。
> 范围 = 主纲 P10-C（SPEC §10.4）· **前端收口子批已做**（2026-11-18/19）⇒ 不重复。
> 不做：P10-D 压测 · P10-E 文档 · P10-F 评审。

## 预检（2026-11-23 **实测** · 非沿用旧结论）

| 项 | 现状 | 结论 |
|---|---|---|
| Docker | ✅ 29.4.3 · `postgres:18-alpine` 本地已有 | 可做 |
| 网络 | ✅ deb 200 · ghcr 401(正常) · **pypi ✘** · **阿里云 pip 镜像 200** | ⇒ ⇒ 容器内 `uv sync` **必须**指镜像源 |
| `/health`（liveness+DB）· `/health/ai` | ✅ P10-A 已有 | 状态页的**数据源已有** |
| exporters | ❌ **零依赖**（无 prometheus / otel / structlog） | 要新引入 |
| 监控栈 | ❌ compose 里没有 | 选型待裁 |
| 状态页 | ❌ 前端无路由 | 要做 |
| 测试报告页 | ❌ 无 | 要做 |
| 备份演练 | ❌ 无脚本 | 要做 |
| 部署前置清单（TODO-131） | ⚠️ seed 脚本已有 · **无清单** | 要做 |
| TODO-137 遗留账号迁移 | ❌ **无迁移脚本** | 要做 |
| TODO-163 容器侧车道锁 | ❌ 容器无 flock · 锁目录**只读**挂载 | 可做（前提已具备）|

⚠️ **旧结论「本机无外网 ⇒ 镜像构建不了」已过时**（TODO-163 里的那行）⇒ ⇒ **实测有网**。

## 批次切分

| 批 | 内容 | 需人裁 |
|---|---|---|
| **T0** | 容器侧车道锁（TODO-163）· 部署前置清单（TODO-131/137）| **否** |
| **T1** | exporters · 监控栈+告警 · 状态页 · 备份演练 | **是**（①②③④）|

---

## T0 · 无裁决 · 可直接开工

- [ ] **T0-1 · `pcs-backend/Dockerfile`**（生产镜像）
      ⇒ 装 `util-linux`（**`flock`** · TODO-163 要用）· `fonts-noto-cjk`（PDF 渲染）
      ⇒ 非 root 运行 · `uv` + `--frozen` ⇒ ⇒ **镜像即部署物**
- [ ] **T0-2 · compose 侧接线**
      ⇒ `migrate` / `seed` 改用该镜像 · **锁目录可写挂载**（`.tmp`）
      ⇒ ⇒ 容器内 `flock` **同一把锁、同一路径口径**（`pcs-backend/.tmp/lane.lock`）
      ⇒ ⇒ 抢不到 ⇒ **非零退出**（与宿主侧 `pytest_pg.sh` / `compose_test_stack.sh` 同纪律）
      ⇒ ⇒ ⚠️ 开发仍走**挂载**（不改日常路径）⇒ ⇒ 两套并存，**生产 profile** 用镜像
- [ ] **T0-3 · 守卫**
      ⇒ 静态：compose 里 `migrate`/`seed` 确实带 `flock` + 可写挂载
      ⇒ 动态：**跑着的车道** + `docker compose run --rm migrate` ⇒ ⇒ **必须被拒**
- [ ] **T0-4 · TODO-137 迁移脚本** `scripts/migrate_legacy_user_ids.py`
      ⇒ ⚠️ **必须调** `app/services/token_issuer.py::derive_user_id`（**不另抄一份**）
      ⇒ ⇒ 三步顺序（让出 username → 建派生行 → 转移 `user_projects`）⇒ ⇒ **幂等**
      ⇒ ⇒ 干跑模式（`--dry-run`）先出清单再动手
- [ ] **T0-5 · 部署前置清单** `docs/deploy-prerequisites.md`
      ⇒ 每环境：seed 授权行（TODO-131）· 遗留账号迁移（TODO-137）·
      `alembic check` **两库各一进程**（pcs / pcs_test）· 遗留账号行数 = 0
      ⇒ ⇒ 挂进 `CLAUDE.md` 的「发布前检查」

---

## T1 · **需人裁**（4 问）

| # | 问 | 选项 | 我的建议 |
|---|---|---|---|
| ① | **镜像策略** | **A** 保持 uv 官方镜像 + 源码挂载 / **B** 加生产镜像（开发仍挂载）| **B** —— A 没有**部署物**（F4 过不去）· 且 TODO-163 的 flock 本来就要自定义镜像 |
| ② | **监控栈** | **A** Prometheus + Grafana（**不做 ELK**）/ **B** A + Loki / **C** 完整 ELK | **A** —— C 的三套栈对单人项目过重 · 日志改 JSON 行输出交给宿主系统 |
| ③ | **状态页** | **A** 后端聚合端点 + 前端 `/status` 页 / **B** 只做端点 | **A** —— 「状态页」本身就是 P10-C 的交付项 |
| ④ | **备份演练** | **A** 可验证脚本（`pg_dump` → 恢复 → 断言）/ **B** 只写 Runbook | **A** —— B 不可验证 ⇒ ⇒ 等于没做 |

### T1 · 待裁后细项（骨架）

- [ ] **exporters** —— `prometheus-client` + `GET /metrics`
      ⇒ ⚠️ **无鉴权** ⇒ ⇒ 只在容器内网暴露（不映射到宿主端口）
      ⇒ 指标（5~8 个）：请求延迟直方图 · 在飞请求数 · ARQ 队列深度 ·
      DB 连接池 · 状态机转移失败数 · 待签署数
- [ ] **监控栈 + 告警** —— compose 加 `prometheus` + `grafana`
      ⇒ ⇒ 4 条告警规则（5xx 率 · P95 延迟 · 队列积压 · 状态机失败率）
      ⇒ ⇒ 告警**出口**（邮件 / webhook）**待裁**（第 5 问）
- [ ] **状态页** —— `GET /status`（DB / Redis / LDAP / worker 心跳 / 队列深度）
      ⇒ ⇒ 前端 `/status` 页（**只读** · **不含敏感值**）
- [ ] **备份演练** —— `scripts/backup_restore_drill.sh`
      ⇒ ⇒ `pg_dump` → 恢复到**临时库** → `alembic check` + 抽样行数比对
      ⇒ ⇒ **脚本自带断言**（失败即非零退出）⇒ ⇒ 演练记录进 `docs/`
- [ ] **测试报告页** —— **形态待裁**（页面形态 + 数据来源）

---

## 验收

| 车道 | 判据 |
|---|---|
| 默认车道 | `uv run pytest -q` 全绿（**≥ 上批 baseline**）|
| PG 车道 | `bash scripts/pytest_pg.sh` exit 0（**唯一入口**）|
| 前端 | `npm run typecheck` + `npm run lint` + `npm run test` 全绿 |
| 容器 | `docker compose run --rm migrate` 与跑着的车道**并发** ⇒ ⇒ **必须被拒** |
| 备份 | 演练脚本 exit 0 ⇒ ⇒ 恢复库能过 `alembic check` |

## 未解决

- **①②③④ 待人裁**（T1 的前提）· **告警出口**待裁（第 5 问）· **测试报告页形态**待裁
- P10-J-T2「拒绝」动作（4 问）· TODO-196 工艺室签字 · SPEC §7.5 向导 PMS/BEDD 占位 —— **均不在本批**
