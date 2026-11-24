# 部署前置清单（每个环境各跑一次 · P10-C · T0-5）

> 面向**运维动作**（不是开发步骤）。四条，**按顺序**做 ⇒ ⇒ 顺序错会白做。
> ⚠️ **口令不要写命令行** ⇒ ⇒ 下面所有脚本都从 `.env` 的 `DATABASE_URL` 读。

---

## ① 遗留账号迁移（TODO-137）

**为什么**：登录用的 id 是**派生值**（`uuid5(NAMESPACE_DNS, username)`）⇒ ⇒
若某个用户名被一条 **`user_id` ≠ 派生值**的遗留行占着 ⇒ ⇒ 登录时建行撞唯一约束
⇒ ⇒ 显式 409 `USER_ID_CONFLICT` ⇒ ⇒ ⇒ 那个用户**处处 404**。

```bash
cd pcs-backend
# 先干跑（只读）：把要迁的行列出来
uv run python scripts/migrate_legacy_user_ids.py --dry-run
# 真跑（幂等）
uv run python scripts/migrate_legacy_user_ids.py
```

**做完必须复核**（发布闸）：

```sql
SELECT count(*) FROM users WHERE user_id <> uuid5_derived(username);  -- 必须 = 0
```

⚠️ 脚本的判据用**应用层的** `derive_user_id`（`app/services/token_issuer.py`）
⇒ ⇒ 复核时**不要**另抄一份 uuid5 公式 ⇒ ⇒ 用脚本自己的输出：

```bash
uv run python scripts/migrate_legacy_user_ids.py --dry-run   # 输出「没有遗留账号」= 通过
```

⚠️ **迁移会删掉遗留行**（引用全部转走后删 ⇒ ⇒ 闸才绿）⇒ ⇒ ⇒ **先干跑**。

---

## ② seed 授权行（TODO-131）

**为什么**：物流面加了**项目级守卫** ⇒ ⇒ 任何没有 `UserProject` 授权行的用户
访问物流端点都 **404**（与「不存在」逐字同形 ⇒ ⇒ 枚举不出来，但**用不了**）。
⇒ ⇒ 每个环境都要给**实际使用者**授权：

```bash
cd pcs-backend
uv run python scripts/seed_user_project_access.py --username alice --project <项目 UUID>
```

- 该脚本**幂等**（同 `(user_id, project_id)` 重复跑覆盖角色）⇒ ⇒ 可重复执行。
- 用户**不在 `users` 表**时脚本会**建行**（`roles=[]`）⇒ ⇒ mock 登录的用户
  （alice / bob / carol / dan）也能拿到授权。
- ⚠️ 生产库的用户**必须先在 `users` 表里存在**（FK 约束）⇒ ⇒ 走真实登录路径即可。

---

## ③ 迁移与 ORM 一致（**两库各跑一次**）

```bash
cd pcs-backend
uv run alembic current     # 打印当前 revision
uv run alembic heads       # 打印 code 侧 head
uv run alembic check       # ORM ↔ 迁移 的漂移检查
```

⚠️ **四条读法，缺一条就会误判**：

1. **先确认它跑了** —— DB revision 落后 code head 时 `check` 直接拒绝
   （"Target database is not up to date"）⇒ ⇒ 那是**检查失败**，不是通过。
2. **退出码是 255**，不是 1。
3. **它只在「当前连接的那个库」上成立** ⇒ ⇒ `pcs` 与 `pcs_test` **各跑一次**。
4. **「无输出」不等于「一致」** ⇒ ⇒ ⇒ `exit 0` 才是。

⚠️⚠️ **一库一个进程**（alembic 的 `settings` 是 **pydantic 缓存实例**
⇒ ⇒ 同一进程内第二次改 `DATABASE_URL` **不生效**）⇒ ⇒ ⇒ 两库各起独立进程。

⚠️ 换库的方式**只能靠环境变量** ⇒ ⇒ 进程内派生（口令不落盘也不进命令行）：

```python
import os, re
from dotenv import dotenv_values
url = dotenv_values('.env')['DATABASE_URL']
os.environ['DATABASE_URL'] = re.sub(r'/pcs(\?|$)', r'/pcs_test\1', url)
```

⚠️ **不要**用 `Config.set_main_option('sqlalchemy.url', ...)` ⇒ ⇒
`alembic/env.py` 会用 `settings.database_url` **覆盖**你设的值
⇒ ⇒ ⇒ 所有命令照旧跑在**开发库**上（⇒ ⇒ exit 0 却根本没在目标库上跑）。

---

## ④ 无遗留账号行（发布闸）

```bash
cd pcs-backend
uv run python scripts/migrate_legacy_user_ids.py --dry-run   # ⇒ 「没有遗留账号」
```

⇒ ⇒ > 0 ⇒ ⇒ 先做 ①。

---

## 附 · 监控栈（P10-C · T1d）

```bash
docker compose -f docker-compose.yml up -d prometheus grafana
```

⇒ ⇒ 两个服务**都不映射宿主端口** ⇒ ⇒ ⇒ 只在 compose 内网可达
⇒ ⇒ ⇒ （`/metrics` 无鉴权 ⇒ ⇒ ⇒ 映射出去 = 把指标暴露给整个局域网）。

### ⚠️ 两个**环境事实**（2026-11-24 实测 · 不是配置问题）

| # | 事实 | 影响 | 处置 |
|---|---|---|---|
| 1 | ⚠️ **宿主 8000 端口被别的服务占着**（实测 `main:app` · 不是本仓）⇒ ⇒ Prometheus 抓 `host.docker.internal:8000` ⇒ ⇒ **404** | 抓取目标 down | **换端口**：后端跑在别的端口 ⇒ ⇒ 改 `deploy/prometheus/prometheus.yml` 的 target ⇒ ⇒ （或停掉占端口的服务）|
| 2 | ⚠️ **docker.io 本机不可达**（`registry-1.docker.io` IPv6 超时）⇒ ⇒ `prom/prometheus` · `grafana/grafana` 拉不动 | 监控栈起不来 | **镜像源是运营侧决定** ⇒ ⇒ ⇒ 仓库里**不写死**第三方镜像 ⇒ ⇒ ⇒ 需要时用 daemon 的 `registry-mirrors` 或 `docker tag` 改本地标签 |

⇒ ⇒ ⇒ 端到端已验：抓取目标 **up** · 抓到 `pcs_http_requests_total` · 标签是**路由模板** ✔
⇒ ⇒ ⇒ 告警规则 **5 条**（5xx 率 · P95 延迟 · 队列积压 · **队列测不到** · 状态机失败）
⇒ ⇒ ⇒ ⚠️ **前 4 条**在真 Prometheus 上验过（`/api/v1/rules` 可见 · `state=inactive`）
⇒ ⇒ ⇒ ⇒ 第 5 条（`absent()`）是本批新增 ⇒ ⇒ 镜像已不在本机 ⇒ ⇒ **未经 promtool 复核**
⇒ ⇒ ⇒ ⚠️ 「队列测不到」那条是因为队列深度是 **scrape 时现读 Redis** 的
⇒ ⇒ ⇒ ⇒ ⇒ 读不到 ⇒ ⇒ ⇒ **序列不产出**（不是报 0）⇒ ⇒ ⇒ ⇒ ⇒ 「测不到」与「真的是 0」可区分 ✔

## 附 · 车道互斥（同一时刻只有一条能建 schema）

`migrate` / `seed` / PG 车道 / E2E 车道**都写 `pcs_pgtest`** ⇒ ⇒ 必须互斥：

| 谁 | 怎么抢锁 |
|---|---|
| PG 车道 | `bash scripts/pytest_pg.sh`（**唯一入口**）|
| E2E 车道 | `bash scripts/pytest_e2e.sh` |
| 测试栈 | `bash scripts/compose_test_stack.sh` |
| **裸 `docker compose run --rm seed`** | ✅ **P10-C · T0-2 起也抢锁** ⇒ ⇒ 抢不到 ⇒ ⇒ 非零退出 |

⇒ ⇒ 锁文件：`pcs-backend/.tmp/lane.lock`（同一 inode ⇒ ⇒ 宿主与容器互斥）。

---

## 关联

- **TODO-131**（seed 授权行）· **TODO-137**（遗留账号迁移）· **TODO-163**（容器侧锁）
- 计划：`docs/superpowers/plans/2026-11-23-p10-c-deploy-observability.md`
- `CLAUDE.md` 的「发布前检查」是**本文的摘要版** ⇒ ⇒ 两处口径一致。
