# OpenWolf

This project uses OpenWolf for context management. The always-on rules live in `.claude/rules/openwolf.md`; the hooks handle bookkeeping (anatomy index, memory log, read tracking) automatically.

For the full operating protocol (session handoff, memory discipline, bug logging), load the `openwolf` skill, or read `.wolf/OPENWOLF.md`. Regenerate the session handoff with `/handoff`.

# 知识库

- `docs/solutions/` — 已记录的问题解法（缺陷、最佳实践、工作流模式），按 `problem_type`
  分目录，带 YAML frontmatter（`module` / `tags` / `problem_type` / `severity`）。
  在已记录领域做实现或排障时相关；新增解法后回写一份，别只留在提交信息里。
- `CONCEPTS.md` — 共享领域词汇（实体、具名流程、状态概念）。熟悉代码库或讨论领域概念时的
  起点。它是词汇表，不是规格书。

# 测试前检查

- **单元测试（pytest）**：免前置。`tests/conftest.py` 用 `sqlite+aiosqlite:///:memory:`
  + `SA_Base.metadata.create_all` 建表 —— 从 ORM metadata 建，**不读 Postgres，不读
  迁移产物**。`.env` 的 `DATABASE_URL` 指向 `pcs`；无 `.env.test`。
- ⚠️ **`pcs_test` 库存在**（与 `pcs` 同机同实例，`pcs` 用户可连）。它**不是**单测用的 ——
  单测跑内存 SQLite。2026-10-07 实测它曾长期停在 `p7_s4_001`（落后 3 个 revision、
  多一张已被 p7_s5_001 删除的 `equipment_lib`），已补 `alembic upgrade head` 对齐到
  `p7_s5_007`。**改迁移后若要验证「迁移在另一个库上也成立」，显式指定它**：
  ⚠️ **只能靠 `DATABASE_URL` 环境变量**（口令**不要**写在命令行，会被权限分类器拦）。
  推荐**单进程内**做，口令既不落盘也不进命令行：

  ```python
  import os, re
  from dotenv import dotenv_values
  from alembic import command
  from alembic.config import Config

  url = dotenv_values('.env')['DATABASE_URL']
  os.environ['DATABASE_URL'] = re.sub(r'/pcs(\?|$)', r'/pcs_test\1', url)  # 进程内设
  cfg = Config('alembic.ini')
  command.upgrade(cfg, 'head')
  command.current(cfg)
  command.check(cfg)          # exit 255 = 真有漂移；0 = 一致（且要确认它真跑了）
  ```

  ⚠️⚠️ **不要用 `Config.set_main_option('sqlalchemy.url', ...)`** ——
  `alembic/env.py:18` 会 `config.set_main_option("sqlalchemy.url",
  settings.database_url)` **覆盖**你设的值 ⇒ 所有命令照旧跑在**开发库**上。
  2026-10-20 实测踩过：`pcs_test` 当时停在 `p9_006`，而这条路径下 `current`
  打出 `p9_007 (head)`、`check` 打出 `No new upgrade operations detected`
  ⇒ **exit 0 却根本没在 `pcs_test` 上跑**（与下面读法 ③ 同一形状）。
  ⇒ 换库后**先 `current` 确认 revision 真的变了**，再信 `check` 的结论。
  第二个库停在旧 revision 是产生困惑漂移结果的常见来源。
- ⚠️⚠️ **验多个库 ⇒ 一库一个进程**（2026-11-01 实测打脸，见 `.wolf/cerebrum.md`）：
  alembic 的 `settings` 是 **pydantic 缓存实例**（`alembic/env.py:18`）⇒ **同一进程内
  第二次改 `os.environ['DATABASE_URL']` 不生效** ⇒ 第二遍连的仍是第一个库。而
  `upgrade` 是幂等的 ⇒ 两遍都打印同一个 `(head)`，**输出无法区分** ⇒ 上一轮 QA 报告
  据此写下「pcs / pcs_test 两库都已到 head 且 check exit 0」—— 那是**假证据**
  （`pcs_test` 实际还停在旧 revision，是评审员直查库才发现的）。
  ⇒ 上面的「进程内派生 URL」配方只适用于**单个**库；要验多个库 ⇒
  **每库起独立进程**，且**必须直查库的 `alembic_version` + 目标列存在性**，
  不能只信命令输出。
- **Postgres 版本**：**18**。开发库是 apt 集群 `18-main`（5432，实测 18.6）；
  `docker-compose.yml` 与 CI 已于 2026-10-07 对齐到 18，CI 首次以 18 跑即全绿。
  历史：16 是 2026-09-16 为 `btree_gist` 有意装的旧集群（`docs/adr/signatures/dba-btree-gist-install-request.md`），
  后被 18 抢占端口 —— **16 → 18 那次数据迁移在仓库里无记录**。
- **⚠️ 漂移盲区**：迁移改了 schema 而 ORM 未跟随时，**单测照绿、真库会炸**。缺表会红（可见），
  漂移会绿（不可见）—— 后者没有自动化能抓。改任何 `alembic/versions/*` 时必须**手动核对
  ORM 列同步**（历史上 `config_energy_conversion_factors` 4 个 R1 分类列从未迁移，
  bug-137；见 `.wolf/cerebrum.md`）。
- **人工守门动作**：`uv run alembic check`（检测 ORM vs 迁移漂移）。四条读法，缺一条就会误判：
  1. **先确认它跑了**。DB revision 落后 code head 时它直接拒绝（"Target database is not up to
     date"）——那是**检查失败**，不是通过。先 `uv run alembic current` 对比 `uv run alembic heads`。
     2026-10-07 的 bug-143/144 藏了很久，直接原因就是有个已提交未应用的迁移把守门整个堵住了：
     **守门没报，是因为它根本没跑。**
  2. **退出码是 255，不是 1**。按 `== 1` 写的封装会把真实检出当通过。
     （`scripts/check_migration_idempotency.py` 才用 1 —— 两个工具别混。）
  3. **⚠️ 它只在「当前连接的那个库」上成立。** 命令比的是 ORM ↔ 你连上的
     schema，**不是** ORM ↔ 迁移应该造出的 schema。任何跨库漂移（`pcs` 有、
     `pcs_test` 没有的约束/列/索引）根本不在它的视野里。
     2026-10-07 记的「43 条 → 0，exit 0」**只在开发库 `pcs` 上为真**：
     那次是照着开发库补 ORM 声明，而开发库里那些约束本来就存在。
     2026-10-14 把 `pcs_test` 对齐到 head 后，同一条命令在它上面是
     **exit 255 + 1 条真实漂移**（`future_dated_forbidden_chk`）。
     ⇒ **要声称「迁移在别处也成立」，必须在每个库上各跑一次。**
     否则对着 `pcs` 看到 exit 0 就以为两个库都干净，是本仓最容易复现的假绿。
  4. **"无输出"不等于"一致"**。反过来也一样：`remove_constraint` 的字面意思
     （「DB 多余、ORM 要删」）与正确处置**恰好相反** —— 实测那 39 条全是
     「DB 有安全网、ORM 漏声明」，照字面删会把 DB 保护删掉。
     **`exit 0` 现在是真实状态**（2026-10-07 起 43 条全清，仅限开发库，见第 3 条），所以
     exit 255 一律是真缺陷，不需要再对「已裁决残留」做豁免。
     ⚠️ ORM 里写 `ForeignKey(..., use_alter=True)` **不会自己生成迁移** ——
     那条延迟迁移得有人手写，否则 DB 上压根没这个约束（`projects` 曾整表零外键，
     bug-146）。

## 物流面项目守卫（部署前置 · 2026-11-09 起）

物流的 **20 个端点/路径**已补上**项目级访问守卫** ⇒ **任何没有 `UserProject`
授权行的用户访问物流端点都被拒**（与「不存在」**逐字同形** ⇒ 枚举不出 UUID）。

⚠️ **形状按端点族分两种**（2026-11-10 修订 · ce-code-review 报告的 residual risk）：
- **单对象端点**（`GET/PATCH/DELETE /streams/{id}`、状态点、属性、六个状态转移端点、
  血缘三端点）⇒ **404**，与「不存在」**逐字同形**；
- **批量端点**（`POST /streams/batch-submit`）⇒ **207**，跨项目条目以
  **失败项**（`reason=SIM_STREAM_NOT_FOUND`）表达 ⇒ 与「真不存在」的失败项
  **逐字同形**（枚举向量同样被守住，只是**整体状态码**不是 404）。

⇒ **每个环境上线前**跑一次（幂等）：

```bash
cd pcs-backend
uv run python scripts/seed_user_project_access.py --username <用户名> --project <项目 UUID>
```

⚠️ **mock 登录不落 `users` 表**（ADR-0046 §③b）⇒ seed 脚本会**建行**（`roles=[]`）
⇒ dev 环境的 alice / bob / carol / dan **必须**靠它拿到授权 ⇒ 否则 dev 前端
**全站 404**（连 `/sim/streams` 列表页都空）。
⇒ `POST /projects` 会**自动授权创建者**（无需手动 seed 自己建的项目）。


## 发布前检查（必做）

- [ ] `alembic check` 在两库（pcs / pcs_test）各 exit 0 —— ⚠️ 必须**独立进程**跑，
      见 cerebrum「alembic settings 缓存」；且**直查库**确认 revision 与目标列
- [ ] `scripts/pytest_pg.sh` exit 0 —— 覆盖 `tests/alembic/` 的引擎级用例与并发类用例
- [ ] `check_openapi_payload_coverage.py` RC 0（裸字段 ≤ 基线）
- [ ] `check_migration_idempotency.py` RC 0
- [ ] 前后端全量测试绿
- [ ] 部署前确认**没有**遗留账号行：`SELECT count(*) FROM users WHERE user_id <> uuid5_derived(username)` = 0
      ⇒ > 0 ⇒ 先按 TODO-137 迁移（授权转到派生 id），否则 legacy 用户**处处 404**
      （`ensure_user_row` 只认派生 id ⇒ 建行撞唯一约束 ⇒ 显式 409 `USER_ID_CONFLICT`）

⚠️ 第 1 条验「迁移与 ORM 一致」，第 2 条验「迁移在**真实 PG** 上跑得通 + 并发语义正确」
⇒ 两者**不互相替代** ⇒ 「只跑 alembic check」不算发布前检查通过。

⚠️ PG 车道（`scripts/pytest_pg.sh`）是**唯一**入口：`pg` marker 的用例平时被
`pytest.skip` 静默跳过 ⇒ 绿灯**证明不了**它们跑过 ⇒ **不得**在别处教
「也可以直接 `DATABASE_URL=... pytest`」。

# 前端 UI 规范

前端所有 UI 以 `docs/PCS-UI-SPEC.md`（V1.0 冻结）为唯一编码依据。字段/枚举/权限/错误码以 OpenAPI + meta API 为准；与 SPEC 冲突时以 OpenAPI 为准并登记 SPEC 修订。

# Per-Batch QA Gate（每批落地强制浏览器回归）

原流程只写在全局 `~/.claude/CLAUDE.md`，**新克隆 / 换机器即失效**，
实际靠人脑维持 —— 2026-10-02 之后三批（Sprint 3 / Sprint 4 / Sprint 5 前置）
落地时都没跑过 QA 报告。此处入库，使闸门随仓库分发。

## 何时跑

每批 sprint 的**最后一个 commit 落地后**，开下一批之前。

## 流程

1. **定位批末 commit**：`git log --oneline -20 | grep '<本批前缀>' | head -1`
2. **回归**（先 `npm run dev` 起 vite，端口 5173）：
   - `npm run typecheck` clean（= `tsc --noEmit`）
   - `npm run lint` clean（自带 `--max-warnings 0` 与 `.` 范围，**别用裸 `npx eslint src/` 替代**）
   - `npm run test` ≥ 上批 baseline（= `vitest run`）
   - 浏览器：login 200 + dashboard 渲染 + 各 Page 路由可达
   - 控制台：无 antd / React / TypeScript error
   - 网络：核心 mock 端点（mock-login、meta 5 端点）无 404
3. **报告**：`.gstack/qa-reports/qa-report-pcs-frontend-YYYY-MM-DD-<batch>.md`
4. **CRITICAL / HIGH 必修完**才能开下一批；MEDIUM / LOW 登记到 `TODOS.md` 延后

## 注意事项

- **`.gstack/` 已在 `.gitignore` 中，报告只落本地不进仓库** ——
  这是设计取舍（截图体积大），但代价是**报告无法随仓库分发给同事或后续会话**。
  关键结论应同步进 `TODOS.md` 或提交信息，别只留在报告里。
- **不要用 `git checkout <commit> --detach`**。历史上为「测批末精确状态」用过，
  但 agent 会话里切换 HEAD 有把会话卡死的风险（本项目已发生过 worktree 被删
  导致隔离守卫援引不存在路径、会话永久无法 Edit/Bash 的事故，见 `.wolf/STATUS.md`）。
  正常流程下 main 就是批末，直接在 main 上跑即可。
- 工具：`~/.claude/skills/gstack/browse/dist/browse`（Linux 下需 `CI=1`）。
  `Skill gstack-qa` 需在 `~/.claude/settings.json` 设为 `"on"` —— 2026-10-07 实测已开。

## 现有报告

- `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-12-p9b4-review-fixes.md`（最新 · P9B-4 评审修复批 · 批末 HEAD `4032617`）
- `.gstack/qa-reports/qa-report-pcs-frontend-2026-11-04-p9b4.md`（P9B-4 体验批 · ⚠️ 批末 HEAD 早于真实批末两个提交 ⇒ 已被上一份取代）
- `.gstack/qa-reports/qa-report-pcs-frontend-per-batch-2026-09-16.md`
- `.gstack/qa-reports/qa-report-pcs-frontend-2026-10-02-sprint2-batch.md`
