---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-18（第 36 轮：
> **P10-F 批 3 的前两个审计子批（F3-T2a + F3-T2b）** —— 守卫覆盖审计
> + **T2b 查出 1 CRITICAL（匿名可读任意项目的管路记录）+ 1 HIGH（跨项目写入）**；
> **未 push**）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 36 轮：P10-F · **F3-T2a + F3-T2b**（审计子批 · 只出结论））

**F3-T2a**（`config.py` 11 + `report_builder.py` 9 = 20 端点）
⇒ ⇒ 结论在工作区 `…/audit-f3-t2a.md` ⇒ ⇒ **推翻了范围裁决的两个前提**：
`config.py` 的资源是**公司级**（`ConfigAsset` 无 `project_id`）⇒ ⇒ 「跨项目越权」
**语义不成立** ⇒ ⇒ **越权缺口 0**（只缺断言）· `report_builder.project_id` 是
**死字段**（可见性只看 `created_by`）⇒ ⇒ 真缺口是口径不一致（TODO-170 · 已裁决落地）
⇒ ⇒ 同批**修掉了 TODO-174**（报表执行跨项目读 · `c7da7b6`）+ TODO-170 选项 ③（`bc881fa`）
⇒ ⇒ 默认车道 **5855 passed**。

**F3-T2b**（`report.py` 10 + `records.py` 6 = 16 端点）⇒ 结论 `…/audit-f3-t2b.md`
⇒ **本批唯一的 CRITICAL**：**TODO-179 🔴** 匿名可读任意项目的管路记录与快照（三个 GET
既不要求登录也不做项目授权）· TODO-180 🟠 写面授权判 payload 的 `project_id`、行落进
workspace 的 workspace · TODO-181 🟠 项目守卫**零断言** · TODO-182 🟡 状态机守卫在
`ws.project_id IS NULL` 时整段跳过 · TODO-183 🟡 断言恒真 · TODO-184 🟢
`GET /report/styles` 的 `project_id` 是死参数 · TODO-185 🟢 详情端点零测试
⇒ bug-2187/2188 ⇒ 棘轮 `AUDITED_PROJECT_SCOPED_ENDPOINTS` 仍是 2（实际审计面 ≈12）。

**F3-T3a**（`psychro.results` 5 + `workspaces` 4 + `user_projects` 4 + `admin_users` 3 = 16）
⇒ 结论 `…/audit-f3-t3a.md` ⇒ 抽查 6 个变异，只有 `admin_users` 与 `workspaces.archive` 的
角色闸有断言 ⇒ **TODO-186 🔴** workspaces 三端点不要求登录（匿名枚举全部 workspace ·
匿名 GET **写库**（touch）· 匿名 POST 任意 owner_id + 审计行伪造 · bug-2189）
⇒ **TODO-187 🟡** 两种 404 文案不同 ⇒ 存在性可枚举（跨 21+ 端点族）·
**TODO-188 🟡** `GET /user-projects/me` 角色清单缺 3 个角色 ⇒ 合法用户 403（潜伏）。

**F3-T3b**（`audit` 3 + `system_settings` 2 + `meta` 6 = 11）⇒ 结论 `…/audit-f3-t3b.md`
⇒ **零越权缺口**（4 个变异全变红）⇒ ⚠️ 但查出**审计工具自己的两个分类错误**
（bug-2190 · `b275e73`）：`current_user` 漏判 ⇒ meta 的 6 端点被误判成「无守卫」（假阴性）·
`require_formal_project_workspace` 被算成「授权闸」（假阳性：只判类型、从不查
`user_projects`、且 fail-open）⇒ 守卫状态机三态 → **四态** ⇒ 守卫测试 8 → 11
⇒ 在审范围内各模块结论不变 ⇒ 新登记 **TODO-189**（两个「不 mock 守卫」的 client ⇒
棘轮看不见其中一个）。

**F3-T4 + F3-T5**（复核 + 结论文档）⇒ 三条越权债（TODO-132 禁用用户 · TODO-133
workspace 归属 · TODO-135 mock 旁路）**逐条做变异 ⇒ 三条全红** ⇒ 「已闭环」是真的
⇒ ⚠️ 两条自我修正：**变异必须跑「该缺陷对应的断言文件」**（第一次只跑 `current_user`
那个文件 ⇒ 没红 ⇒ 差点误判）+ **变异必须真的改变行为**（第一次写的字段不在那里 ⇒ 空转）。
⇒ 结论文档进仓库 `docs/solutions/security-issues/guard-coverage-audit-logistics-adjacent-modules.md`
（63 行逐端点表 · 19 处变异记录 · 18 条 TODO 缺口 · 排除理由 · 测试基础设施缺口）。


**F3 审计总计（4 子批 + 复核）**：63 端点逐个答 4 问 ⇒ ⇒ **已覆盖 44** ·
**已覆盖但断言缺口 9** · **已知限制 4** · **真缺口 6**
（**2 critical**：TODO-179 records 匿名可读任意项目管路记录 ·
TODO-186 workspaces 三端点无认证 ⇒ ⇒ **两条是一条链**）
⇒ ⇒ ⚠️ **审计批只出结论、不改产品代码** ⇒ ⇒ 两个 critical **要另开修复批**。

**批 4（F3 修复批）—— 两个 critical 同一条链一次关掉**（commit `a2b9889`）
⇒ ⇒ **口径**（人裁决 TODO-169）：**有项目 ⇒ 项目授权 · 无项目（PERSONAL）
⇒ ⇒ owner 本人** ⇒ ⇒ 「登录」是**下限**不是授权 ⇒ ⇒ **无权 ⇒ ⇒ 404**。
⇒ ⇒ ① 新增 service 层真相源 `workspace_service.py::require_workspace_access_or_404`
⇒ ⇒ ② `records.py` 三个 GET 加 `current_actor` + 工作区授权（此前**不带 token
也 200**）⇒ ⇒ ③ **授权对象统一成「工作区」**（⇒ ⇒ 跨项目写断掉 · payload 与
工作区项目不一致 ⇒ ⇒ **400**）⇒ ⇒ ④ `workspaces.py` 三个端点加认证 + 授权
（⇒ ⇒ `owner_id` 必须是令牌里的那个人 ⇒ ⇒ **审计行不再记在别人名下** ·
⇒ ⇒ `GET /{id}` 的 **touch 写副作用只在授权通过后**）
⇒ ⇒ ⑤ 「不存在」与「无权」抛**同一个**异常 ⇒ ⇒ **逐字同形**
⇒ ⇒ 测试：新增 `tests/api/v1/test_workspace_access_guard.py`（17 例 · 全
`strict_client`）⇒ ⇒ 改 `test_workspace.py` + `test_records.py`（此前**不带
token** ⇒ ⇒ 把「匿名可读可建」钉成了正常行为）
⇒ ⇒ TODO-179/180/182/185/186 **已修**（bug-2187/2188/2189 fix_commit `a2b9889`）。

**批 4 闸门（全绿）**：默认后端车道 **5877 passed**（EXIT=0）· E2E 车道 **40** ·
PG 车道 **7** · Playwright 真后端通道 **9/9**（新后端 8002）· 前端 typecheck
clean · lint clean · vitest **1069/1069**（⚠️ 第一次跑有 1 条红 = 与后端车道抢
CPU 的已知 flake ⇒ ⇒ 第二次全绿）⇒ ⇒ 契约快照随之更新（commit `0cb89e4`）。

**批 5 —— 两条人裁决落地**（commit `09c9282` · bug-2191）
⇒ ⇒ **TODO-172 publish 的职责分离**（三条）：① **禁自审**（`created_by == actor`
⇒ ⇒ **403**）② **审核者要对定义的项目有授权**（无授权 ⇒ ⇒ **404**，与
「不存在」**逐字同形**）③ **允许公司级审核者**（`project_id IS NULL` ⇒ ⇒ 不做
项目判定 ⇒ ⇒ 否则公司级模板永远没人能审）⇒ ⇒ 判定在 **service 层**（端点漏调
也绕不过 ⇒ ⇒ 这正是 TODO-178 的根因）⇒ ⇒ 新增 5 例（全 `strict_client`，
含两条**正面路径**）⇒ ⇒ **TODO-178 已修**。
⇒ ⇒ **TODO-175**：「只有系统管理员可以替别人建项目」⇒ ⇒ `POST /projects`
本来就只允许 SYSTEM_ADMIN ⇒ ⇒ 现状即满足；⇒ ⇒ 「**工作区 owner 自动获得
授权**」⇒ ⇒ 落 `PROJECT_LEAD` ⇒ ⇒ 否则他永远看不见这个项目。
⇒ ⇒ ⚠️ **裁决未覆盖**：`obsolete`（作废）**不查 `created_by`** ⇒ ⇒ 登记
**TODO-190**（产品语义 · 低优先）。

---

## ✅ Done（第 35 轮：P10-F · F1 + F2 + F3-T1 + 整支评审修复批 · 详情查 `git log`）

计划 `docs/superpowers/plans/2026-11-17-p10-batch-f-production-readiness.md` ·
账簿 `.superpowers/sdd/2026-11-17-p10-batch-f-production-readiness/progress.md` ·
commits `f26bdcb` → `df79685`（**未 push**）。
**F1**（4 条：`useFetch` 失败态+401 共用真相源 · `preview-streams` 补 `response_model`
· 种子管级按契约造 · 守门测试断 `flock -n`）· **F2**（5 条：public 守卫快照全表 ·
仪表盘守卫条件 · compose migrate/seed 进同一把锁 · rowKey 棘轮扩到函数形式 ·
默认车道不再碰开发库/真 Redis）· **F3-T1**（范围提案+初判）· **整支评审修复批**
（C1 `useFetch` path 变化不重置状态 · I1/I2 autouse 越界 ⇒ 隔离只作用默认车道 ·
I3/I4 车道锁与探针残留 · I5/I6 TODO-169 裁决 + TODO-167 清单订正）。
**闸门**：前端 typecheck/lint clean · vitest 1069/1069 · 后端默认车道绿。
**新登记**：bug-2183/2184/2185 · TODO-162/163/165/167/168；**TODO-166/169 已裁决关闭**。

---

## 🚀 Next quest

1. **P10-C 子批「前端收口」**（**人裁决 2026-11-18**）⇒ ⇒ 四条
   （**TODO-156** PRO/II 解析补组成 · ⚠️ 后端项 · 搭车 · **TODO-157** 设备台账页
   缺失 · ⚠️ 待人裁 ①补页/②只走API · **TODO-159** 三个页面调了不存在的端点 ·
   **TODO-160** 物性/应力/毒性三页首屏 422）
   ⇒ ⇒ **不依赖 P10-C 的部署物 ⇒ ⇒ 现在就能开**（与 P10-C 主体并行）
   ⇒ ⇒ 计划：`docs/superpowers/plans/2026-11-18-p10-c-frontend-closure.md`
   ⇒ ⇒ 台账：主计划 §二 已加一行 · `TODOS.md` 四条归属已改。
2. **P10-F 批 3（F3）—— 全部完成（4 个审计子批 + 复核 + 结论文档）**
   ⇒ ⇒ **下一批 = F4**（安全扫描 / 依赖漏洞 / 镜像扫描 / 回滚演练）
   ⇒ ⇒ ⚠️ **F4 的前置是 P10-C**（部署与可观测性）⇒ ⇒ 计划写明「P10-C 未落地
   ⇒ ⇒ ⇒ 没有可扫的镜像、没有部署物、没有告警」⇒ ⇒ ⇒ **F4 现在开不了**
   ⇒ ⇒ ⇒ ⇒ ⇒ **要么先开 P10-C，要么把 F4 缩到「不依赖镜像」的部分**
   （`bandit -r app/` + `uv audit` + `npm audit --production` ⇒ ⇒ **这三样
   不需要镜像** ⇒ ⇒ ⇒ ⇒ 可以先做）
3. ⚠️ **ce-code-review 出的修复项**（2026-11-18 · 评审 P10-F 整批 · **10/10 评审员全回**）
   ⇒ ⇒ **已修（bug-2192 · P0）**：工作区守卫拿 `workspaces.project_id`（**生产路径从来不写**
   ⇒ ⇒ FORMAL 被当成 PERSONAL ⇒ ⇒ 成员 404 + 写入恒 400）⇒ ⇒ 真相源改成
   **反查 `projects.workspace_id`** + `POST /projects` 回填 + 迁移 `p10_003` + 歧义 409
   ⇒ ⇒ **71 条既有测试由红转绿**（夹具在造生产不存在的形状）⇒ ⇒ 变异自证 8 条红。
   ⇒ ⇒ **已修**：OpenAPI 契约门禁 **exit 1 → 0**（批 4 的 baseline 没重滚）。
   ⇒ ⇒ **待修（下一批「守卫补洞批」）**：
   ① `records.py` 三个写端点：**FORMAL 类型闸（403）在工作区授权守卫（404）之前**
   ⇒ ⇒ **存在性可枚举**（adversarial + security 独立命中）
   ② `projects.py` 的 owner 自动授权**会造 `ws-owner-<uuid>` 的假用户名 users 行**
   ⇒ ⇒ 破坏「`user_id` = `uuid5(username)`」派生不变式（adversarial + project-standards 独立命中）
   ③ `DefinitionService.update` 改 `project_id` **不查项目授权**（POST 查了 · PUT 没查）
   ④ `obsolete` **绕开**刚定的可见性规则（publish 严 · obsolete 不严）
   ⑤ `POST /workspaces` 收**任意 `project_id`** ⇒ 无项目授权
   ⑥ `shared_with` 的 `CREATOR_ONLY` 在项目级定义上被**静默忽略**（字段与实现不符）
   ⑦ 前端「保存并发布」**只有创建人自己能点 ⇒ 永远 403**（+ MSW mock 返回 200 ⇒ 骗人）
   ⑧ `PipingStatusPanel` 裸 axios ⇒ 新的鉴权端点它打不开（无 token）
   ⑨ 棘轮 `AUDITED_PROJECT_SCOPED_ENDPOINTS = 2`（实际 17+）⇒ **永不触发**
   ⑩ `export PCS_TEST_LANE=1` 无守卫（删掉即静默回退）· `user_id=None` 时报表执行授权 **fail-open**
   ⑪ 审计脚本 `AUTHZ_GUARDS` 漏两个新守卫 ⇒ ⇒ 把新守卫判成「无守卫」⇒ ⇒ 假阴性
   ⇒ ⇒ 完整评审报告见 `/tmp/compound-engineering-1000/ce-code-review/20261118-151907-0f87af49/`。
4. **推送本轮**（P10-B 12 个 + P10-F 18 个 + 本轮 1 个未 push ⇒ 需明确授权）。
5. **待人裁决**：**TODO-190**（`obsolete` 不查 `created_by` · 产品语义）·
   **TODO-191**（前端「保存并发布」对创建人自己无提示）· **TODO-157** 的 ①/② ·
   ⚠️ **F3 审计出的债已进计划**（人裁决 2026-11-18）⇒ ⇒ 计划文件末尾加了
   **「F3/F4 遗留清单」**（14 条 · 带「谁做/何时做」）⇒ ⇒ **谁做/何时做未定的
   那部分归「新批 F4-PRE（F4 前置批）」**（5 个任务：逐条裁决 · 棘轮抬真 ·
   车道残留 · 断言缺口 · 台账入账）⇒ ⇒ **不依赖 P10-C ⇒ 现在就能开**
   ⇒ ⇒ F4 开工时台账不许有「未定」的行。
6. **P10-C / D / E** 未开工 ⇒ ⇒ F4（依赖漏洞/镜像扫描/回滚演练）与 F5（告警/备份/
   Go-No-Go）前置不满足 ⇒ ⇒ F6 收口要等 F4/F5。
7. **待人裁决**：**TODO-172**（publish 的**职责分离**未定义 · 产品语义 · 附带
   **TODO-178**「自审自批这条意图没被守住」）· **TODO-175**（`POST /projects`
   能不能替别人建项目 · 产品语义）· 其余（TODO-166/169/170/174）**已裁决落地**：
   `projects.py` 的 `POST /projects`（自动授权创建者 = 授权写入的唯一入口）
   **不在**裁决的 B 档清单里 ⇒ ⇒ 要不要并入？
   另：TODO-166 / TODO-169 已裁决关闭。

---

## Context

> ⚠️ **迁移 / PG 车道 / 裸载荷基线 / 发布前检查** ⇒ 见 `CLAUDE.md` ⇒ **不重复**。

- main。**不要建 worktree**（历史事故）· **不要 `git checkout <commit> --detach`**。
  **不得擅自 push**。`.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- 提交约定：conventional commits，**带** `Co-Authored-By: Claude Code` 行；长消息写文件后 `git commit -F`。
- ⚠️ **真后端通道统一入口**：后端 `bash pcs-backend/scripts/serve_e2e_backend.sh`
  （库 `pcs_pgtest` · 端口 **8001**）⇒ 前端 `npm run e2e:real`。
  ⇒ ⚠️ **本机有个 11-17 起的老后端还在跑（端口 8001）** ⇒ ⇒ 它是**改动前**起的
  ⇒ ⇒ **不占车道锁** ⇒ ⇒ 要验「后端与车道互斥」得**重启**它。
  ⇒ ⚠️ `pg_isready -p 5433` **不带 `-h`** 会说「no response」⇒ 要 `-h localhost`。
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

- **「autouse」是全局的** ⇒ ⇒ 任何「为了 X 场景」的 fixture 都要**判作用域**
  ⇒ ⇒ 否则它会盖掉别的车道的隔离 ⇒ ⇒ **假绿**（P10-F · 整支评审 I1/I2）。
- **闸门车道要跑在**稳定**的树上** ⇒ ⇒ 在车道跑的时候改产品代码
  ⇒ ⇒ 车道会抓到你的**中间态**（本轮 lane3 抓到我自己改到一半的 SyntaxError）
  ⇒ ⇒ ⇒ 那不是回归 ⇒ ⇒ ⇒ 结论：**改代码与跑车道不要重叠**。
- **「覆盖损失」必须能被复核** ⇒ ⇒ 「已登记 TODO」≠「TODO 可执行」⇒ ⇒ 登记时
  要看一眼：**按那条 TODO 写，能不能真的把用例跑起来**（同 I1/I2）。
- **状态不会因为「依赖变了」而自动重置** ⇒ ⇒ React Router **复用组件实例**
  ⇒ ⇒ `useState` 留着上一页的值 ⇒ ⇒ 换 id 也会停在上一条的错误上（bug-2183）。
⇒ 其余历史教训查 `.wolf/cerebrum.md` 的 Do-Not-Repeat（**先查顶部索引表，别通读**）
   与 `docs/solutions/`。
