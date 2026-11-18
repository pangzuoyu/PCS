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

**F3-T2b**（`report.py` 10 + `records.py` 6 = 16 端点）⇒ ⇒ 结论 `…/audit-f3-t2b.md`
⇒ ⇒ **本批唯一的 CRITICAL**：

| 编号 | 缺口 | 位置 |
|---|---|---|
| **TODO-179** 🔴 | **匿名可读任意项目的管路记录与快照**（三个 GET 既不要求登录也不做项目授权）⇒ ⇒ `GET /workspaces` 也不要求登录且可枚举全部 ⇒ ⇒ 攻击链闭合 | `records.py:40/78/270` |
| **TODO-180** 🟠 | 写面授权判 **payload 的 project_id**、行落进 **workspace 的 workspace** ⇒ ⇒ 授权在 A 的人写进 B 的工作区 | `records.py:130-137` |
| **TODO-181** 🟠 | `records.py`/`report.py` 的项目守卫**零断言**（变异 M3/M4/M5 **无人应答**） | 3 个变异 |
| **TODO-182** 🟡 | 状态机守卫在 `ws.project_id IS NULL` 时**整段跳过** | `records.py:189/243` |
| **TODO-183** 🟡 | `test_project_level_uses_project_access_not_admin` 的断言**恒真**（`granted` 起始 `True`） | `test_style_service.py:208` |
| **TODO-184** 🟢 | `GET /report/styles` 的 `project_id` 是**死参数** | `report.py:319` |
| **TODO-185** 🟢 | `GET /records/piping/{pipe_id}` **零测试** | `records.py:78` |

⇒ ⇒ bug-2187（critical）· bug-2188（high）⇒ ⇒ 演示取证文件**已移出仓库**
⇒ ⇒ 棘轮 `AUDITED_PROJECT_SCOPED_ENDPOINTS` 仍是 2（**已低于实际审计面 ≈12**
⇒ ⇒ 留给 TODO-181 的修复批同批抬）。

**F3-T3a**（`psychro.results` 5 + `workspaces` 4 + `user_projects` 4 +
`admin_users` 3 = 16 端点）⇒ ⇒ 结论 `…/audit-f3-t3a.md` ⇒ ⇒ 抽查 6 个变异
（M6~M11）⇒ ⇒ **只有 `admin_users` 与 `workspaces.archive` 的角色闸有断言**
⇒ ⇒ 其余 4 个变异**全绿**（⇒ ⇒ 断言缺口，累计 9 个端点）⇒ ⇒ 新登记：

| 编号 | 缺口 |
|---|---|
| **TODO-186** 🔴 | **`workspaces` 三个端点不要求登录** ⇒ ⇒ 匿名枚举**全部** workspace（admin 视图无 admin 闸）· 匿名 GET **写库**（touch）· 匿名 POST **任意 owner_id** + **审计行伪造**（bug-2189）⇒ ⇒ **它是 TODO-179 的放大器 ⇒ ⇒ 两条是一条链** |
| **TODO-187** 🟡 | 两种 404 **文案不同**（`Project not found: X` vs `PsychroResult not found`）⇒ ⇒ 存在性可枚举（跨 21+ 端点族） |
| **TODO-188** 🟡 | `GET /user-projects/me` 角色清单缺 `PROCESS_CONTROLLER`/`VIEWER`/`DATA_ADMIN` ⇒ ⇒ 合法用户 403（前端无消费者 ⇒ 潜伏） |

⇒ ⇒ `admin_users` 3 个端点 **🟢 已覆盖**（403 断言在 · M8 变红）。

**F3-T3b**（`audit` 3 + `system_settings` 2 + `meta` 6 = 11 端点）
⇒ ⇒ 结论 `…/audit-f3-t3b.md` ⇒ ⇒ **本子批零越权缺口**（4 个变异**全部变红**
⇒ ⇒ ⇒ 「已覆盖」**每个都有断言** ⇒ ⇒ 不是「未审即没问题」）
⇒ ⇒ ⚠️ **但查出了审计工具自己的两个分类错误**（bug-2190 · commit `b275e73`）：
`current_user` 漏判 ⇒ ⇒ `meta` 的 6 个端点被误判成「无守卫」（**假阴性**）·
`require_formal_project_workspace` 被算成「授权闸」（**假阳性** ⇒ 它只判工作区
**类型**、**从不查 `user_projects`**、且 **fail-open**）⇒ ⇒ 状态机三态 → **四态**
⇒ ⇒ 守卫测试 8 → **11**（含真模块回归）
⇒ ⇒ **在审范围内各模块的结论全部不变**（逐模块核对过）。
⇒ ⇒ 新登记 TODO-189（两个「不 mock 守卫」的 client ⇒ ⇒ 棘轮看不见其中一个）。

**F3-T4 + F3-T5**（复核 + 结论文档）⇒ ⇒ 三条越权债（TODO-132 禁用用户 ·
TODO-133 workspace 归属 · TODO-135 mock 旁路）**逐条做变异** ⇒ ⇒ **三条全红**
⇒ ⇒ ⇒ 「已闭环」是真的（不是「已登记就算」）⇒ ⇒ ⚠️ 两条自我修正：
**变异必须跑「该缺陷对应的断言文件」**（第一次只跑了 `current_user` 那个文件
⇒ ⇒ 没红 ⇒ ⇒ 差点误判）+ **变异必须真的改变行为**（第一次写成
`req.payload.get("workspace_id")` ⇒ ⇒ 字段不在那里 ⇒ ⇒ 空转 ⇒ ⇒ 没红）。
⇒ ⇒ 结论文档进仓库
`docs/solutions/security-issues/guard-coverage-audit-logistics-adjacent-modules.md`
⇒ ⇒ 63 行逐端点表 · **19 处变异记录** · 缺口清单（18 条 TODO）·
排除理由 · 测试基础设施缺口 · 已知限制。

**F3 审计总计（4 子批 + 复核）**：63 端点逐个答 4 问 ⇒ ⇒ **已覆盖 44** ·
**已覆盖但断言缺口 9** · **已知限制 4** · **真缺口 6**
（**2 critical**：TODO-179 records 匿名可读任意项目管路记录 ·
TODO-186 workspaces 三端点无认证 ⇒ ⇒ **两条是一条链**）
⇒ ⇒ ⚠️ **审计批只出结论、不改产品代码** ⇒ ⇒ 两个 critical **要另开修复批**。

---

## ✅ Done（第 35 轮：P10-F · F1 + F2 + F3-T1 + **整支评审修复批**）

计划：`docs/superpowers/plans/2026-11-17-p10-batch-f-production-readiness.md`
· 账簿 `.superpowers/sdd/2026-11-17-p10-batch-f-production-readiness/progress.md`
· 评审包 `review-2618f46..426887c.diff`（13 commit）
· commits `f26bdcb` → `df79685`（**未 push**）。

**F1（4 条）**：#9 `useFetch` 失败态 + 401 与 axios **共用真相源** · #13 `preview-streams`
补 `response_model`（**契约滚了 4 份**）· #17 种子管级按契约造 **+ 订正老行** ·
#27 守门测试统一断「可执行部分」+ 断 `flock -n`。

**F2（4+1 条）**：#22 public 守卫快照**全部表** + `max(xmin)` + 补 `_sync_engine`
+ **session 级基线** · #24 仪表盘守卫条件改成「**拿到了真 project_id**」+ 种子的
PERSONAL 工作区 · #15① compose 的 migrate/seed **进同一把锁** · TODO-162 rowKey
棘轮扩到函数形式（**白名单现在空了**）· **F2-T5 默认车道不再碰开发库/真 Redis**。

**F3-T1**：守卫覆盖审计的**范围提案 + 初判**（54 模块 · 313 端点 · 16 条候选缺口）
⇒ ⇒ **等范围批复**（主计划 Q10）⇒ ⇒ T2/T3 未开。

**整支评审的修复批**（独立评审员 · opus · 1 CRITICAL + 6 IMPORTANT + 7 MINOR）：

| # | 修了什么 | 提交 |
|---|---|---|
| **C1** | `useFetch` 在 **path 变化时不重置状态** ⇒ ⇒ 详情页停在上一次的失败提示 / 显示上一条的数据 ⇒ ⇒ effect 开头重置 | `5da8bd2` |
| M7 | 卸载后迟到的 401 **不清会话**（`cancelled` 判断提前） | `5da8bd2` |
| **I1/I2** | 隔离 fixture 是 **autouse** ⇒ ⇒ 它对 PG/E2E 车道**同样生效** ⇒ ⇒ PG 车道 `_sync_engine` 指向 SQLite（**假绿**）+ 20 条真 Redis 用例在**所有**车道都被跳过 ⇒ ⇒ 隔离**只作用于默认车道**（判据 = `PCS_TEST_LANE`） | `77a12ab` |
| **I3** | 真后端通道的**后端**也**写 public** ⇒ ⇒ 与 E2E 车道的守卫并发 ⇒ ⇒ 误红 ⇒ ⇒ 它也进**同一把车道锁** | `77a12ab` |
| **I4** | 上一次跑崩了留下的探针行 ⇒ ⇒ 把**下一次**跑带偏（假红）⇒ ⇒ 取基线**之前**先清残留 | `77a12ab` |
| I5/I6 | 补登记 **TODO-169**（产品裁决）· **TODO-167 的清单改成全仓实测**（12 文件 / 24 处，原写「4 处」） | `df79685` |
| M1/M2/M3/M5/M6 | 种子的 SCH 键改**裸 DN**（`"150"`）· reset **恢复** PERSONAL 工作区 · `max(xmin)` 的**漏报面**写进注释 · 回写 `docs/solutions/` · 换引擎前 `dispose` | `f1c57b3` / `df79685` |

**闸门**：前端 typecheck/lint clean · **vitest 1069/1069（118 文件）** · mock 通道 23 ·
真后端通道 9 · 后端默认车道 **绿**（见下）· PG 车道 · E2E 车道。

**新登记**：bug-2183（C1）· bug-2184（autouse 越界）· bug-2185（探针残留假红）·
TODO-162（已关）· TODO-163（部分）· TODO-165（计数订正 + 现在**可执行**）·
TODO-167（清单已订正）· TODO-168（漂移守卫仍连开发库 · 只读）·
**TODO-166 / TODO-169 已裁决关闭**（2026-11-18：166 = 接受现状 · 169 = FORMAL
必然有项目、无项目的就是 PERSONAL ⇒ 写进 `CONCEPTS.md`）。

---

## 🚀 Next quest

1. **P10-F 批 3（F3）—— 全部完成（4 个审计子批 + 复核 + 结论文档）**
   ⇒ ⇒ **下一批 = F4**（安全扫描 / 依赖漏洞 / 镜像扫描 / 回滚演练）
   ⇒ ⇒ ⚠️ **F4 的前置是 P10-C**（部署与可观测性）⇒ ⇒ 计划写明「P10-C 未落地
   ⇒ ⇒ ⇒ 没有可扫的镜像、没有部署物、没有告警」⇒ ⇒ ⇒ **F4 现在开不了**
   ⇒ ⇒ ⇒ ⇒ ⇒ **要么先开 P10-C，要么把 F4 缩到「不依赖镜像」的部分**
   （`bandit -r app/` + `uv audit` + `npm audit --production` ⇒ ⇒ **这三样
   不需要镜像** ⇒ ⇒ ⇒ ⇒ 可以先做）
2. **推送本轮**（P10-B 12 个 + 本轮 6 个提交未 push ⇒ 需明确授权）。
3. **待人裁决**：**TODO-172**（publish 的**职责分离**未定义 · 产品语义 · 附带
   **TODO-178**「自审自批这条意图没被守住」）· **TODO-175**（`POST /projects`
   能不能替别人建项目 · 产品语义）· 其余（TODO-166/169/170/174）**已裁决落地**。
4. ⚠️ **建议尽快开「修复批」**：TODO-179（🔴 匿名可读任意项目的管路记录）+
   TODO-186（🔴 workspaces 三端点无认证）⇒ ⇒ **两条是一条链**（前者要 workspace_id
   才能读，后者正好把 workspace_id 白送）⇒ ⇒ ⇒ **匿名可读走任意项目业务数据**。
3. **P10-C / D / E** 未开工 ⇒ ⇒ F4（依赖漏洞/镜像扫描/回滚演练）与 F5（告警/备份/
   Go-No-Go）前置不满足 ⇒ ⇒ F6 收口要等 F4/F5。
4. **待人裁决**：**TODO-172**（publish 的**职责分离**未定义 · 产品语义 · 附带
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
- **「覆盖损失」必须能被复核** ⇒ ⇒ 「已登记 TODO」≠「TODO 可执行」⇒ ⇒ 登记时
  要看一眼：**按那条 TODO 写，能不能真的把用例跑起来**（同 I1/I2）。
- **状态不会因为「依赖变了」而自动重置** ⇒ ⇒ React Router **复用组件实例**
  ⇒ ⇒ `useState` 留着上一页的值 ⇒ ⇒ 换 id 也会停在上一条的错误上（bug-2183）。
⇒ 其余历史教训查 `.wolf/cerebrum.md` 的 Do-Not-Repeat（**先查顶部索引表，别通读**）
   与 `docs/solutions/`。
