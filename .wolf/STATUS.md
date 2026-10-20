---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-20（P9A-4 D0 落地）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 8 轮（本会话）：P9A-4「编辑锁与 CIA」lane **全 lane 完成**（D0→D3）

commit `b4470e0`→`bbb4a37`（4 笔）。计划 `docs/PCS-PLAN-P9A-4-编辑锁与CIA.md`，
绑定 ADR-0048。

| task | 产出 |
|---|---|
| D0 | `p9_006`：`cost_est_results.record_hash`（String(64) NOT NULL）+ 回填做进迁移 + **「编辑后重算 hash」不变式**（原先 6 条路径都不重算 ⇒ D2 的 guard 会是空操作） |
| D1 | Redis 编辑锁三端点（acquire/renew/release）+ 降级放行 + SPEC §6.21 P9A-LCK-001~005 |
| D2 | 409 契约（共享 guard）+ 编辑审计 + 自检 cron + SPEC P9A-LCK-006 |
| D3 | CIA 哈希判定分流 `confirm` + 人工判定 `manual-adjust` + SPEC §6.7.1 |

**基线**：后端 **5096 passed / 77 skipped / 0 failed**（D 之前 5005，+91）；
前端 704 passed（未变，前端还没接 §6.21）；两端 typecheck + lint clean；
裸字段仍 **71**；两库均在 `p9_006`（head），`alembic check` 均 exit 0。

**计划被实测否决的四处**（均已写回 ADR-0048 / SPEC）：
① 列宽 `String(64)` 不是 `String(16)`（16 是**值**长不是列宽）；
② `NOT NULL` 不是 nullable（空串是唯一哨兵，阶梯按 `== ""` 写）；
③ 迁移号 `p9_006`（计划写的 `p9_004` 已被占）；
④ 409 用仓库统一错误信封（ADR §⑦ 的顶层三字段作废 ⇒ 冲突对象进 `detail.conflict`）。

### D0 明细（迁移基座）

commit `b4470e0`。计划 `docs/PCS-PLAN-P9A-4-编辑锁与CIA.md`，绑定 ADR-0048 §⑥。

- `p9_006` 迁移：`cost_est_results.record_hash` **String(64) NOT NULL default ''**
  + **回填做进迁移**（不留「记得手工跑脚本」的后门）。
- **不变式**：6 个 update service 改业务字段后**重算 hash**（原先一律不重算 ⇒
  ADR-0048 §⑥ 的阶梯永远走「放行」⇒ D2 的 guard 会是空操作）。
- `calc_lineage`：`apply_record_hash` / `backfill_record_hash` / `finalize` 显式
  校验（缺列抛明确错，不再靠注释挡）。
- 守卫：列形状 8 + 不变式/回填 14 + 集合关系契约 7。

**基线**：后端 **5033 passed / 77 skipped / 0 failed**（上批 5005）；改动文件
ruff clean；两库均 `p9_006`（head），`alembic check` 均 exit 0 且守门真跑了；
真库回填实测过（pcs_test seed 1 行 → 迁移 → 拿到 16 hex，与现算值一致）。

**计划的三处被实测否决**（已写回 ADR-0048 §⑥）：① 列宽 `String(64)` 不是
`String(16)`（16 是**值**长不是列宽，全库 25 张同形）；② `NOT NULL` 不是
nullable（空串是唯一哨兵，阶梯按 `== ""` 写）；③ 迁移号 `p9_006`
（计划写的 `p9_004` 已被占）。

### 第 7 轮：P9A-3「通知待办」lane（C0→C4）落地 + 终审修复

commit `397bd52`→`a996577`。C0 `notifications` 表（`p9_005`）/ C1 通知抽象 /
C1b 触发接线 / C2 Redis+WS / C3 ARQ 清理 / C4 待办实时计算（不建表）；
终审修 F-1~F-9（bug-2030~2034）。基线 5005 passed / 77 skipped；
用户两条裁决（写侧同步 / 触发源最小集合）已回写 ADR-0049。

---

## 🚀 Next quest

1. **前端接 §6.21 / §6.7.1**（P9B 的活，D lane 只做了后端 + SPEC）——
   编辑锁 UI（取锁 / 60s 心跳 / 他人持锁只读化 / 降级横幅）、409 弹窗
   （按 basis 三值分流文案）、PATCH **回传 expected_hash**、ChangeImpactPanel
   的「确认」动作。⚠️ **后端契约已就位（SPEC V1.9）但前端一行都还没写** ——
   在前端接之前，那 6 个 PATCH 端点对前端是**不可用**的（不带基线 ⇒ 409）。
2. **TODO-060**：`record_type` 三处三套词表（`/change-impact` 类名、
   `/results`+`/locks` 表名、`record_comments` 列类名）⇒ 建议随前端接
   §6.21 时一并归一（转换路径存在：`__tablename__` ↔ `RECORD_TYPE_REGISTRY`）。
3. **Z 收口**（OpenAPI 冻结 + 全量回归）—— D lane 已完成，可开。
4. **ADR-0050 暂缓**（`docs/adr/0050-…md`，proposed）—— ⚠️ 用户 2026-10-20
   裁决「先不做」⇒ 不实施；再开工按 P1~P6（P1 纯增量）。
5. **P9A-1 遗留项**（未变）：access token 不带 `tv`；AD 同步需运维服务账号
   ⇒ P9A-USR-002/003 只算**代码就绪**，不得标「通过」。

---

## Context

- main，工作区干净。**不要建 worktree**（历史事故）。
- 两库均在 `p9_006`（head），`alembic check` 均 exit 0。改迁移的纪律见 CLAUDE.md
  （退出码 **255**；先 `current` vs `heads`；**每库各跑一次**；闸门在 DB 落后时
  会 exit 0 但**根本没跑** —— 2026-10-20 又撞了一次）。
  `pcs_test` 的跑法：URL 从 `.env` 派生（`DATABASE_URL` 改库名），
  **不要把口令写在命令行**（会被权限分类器拦）。
- **本机需要真 Redis 才能跑 C2/D1 的跨进程测试**：`docker compose up redis`。
  没起 Redis 时那批测试会 **skip**（不是绿）—— 看输出别误读。
- 契约产物由 G-08 钩子在 commit **之后**重生成，而 `git add` 在钩子之前
  ⇒ 偶尔漏提交，commit 后要 `git add -A && git commit --amend --no-edit` 补。
- 无 CI/CD（单人开发裁决，勿再建议）。本地 gate 走 `.githooks/`。
- 提交约定：conventional commits，**无 attribution 行**（本仓全局禁用）。
- ⚠️ commit message 里用 `!` `（）` 会被 shell 吃掉 —— 长消息写文件后
  `git commit -F <file>`。

---

## 教训（本会话新增）

- **「共用一个 helper」不等于「同一个口径」**。P9A C lane 曾把收件人解析与待办解析
  共用一个 helper，结果**方向相反**（一个解析「全体用户里谁有这角色」、一个解析
  「我有没有这角色」）⇒ 通知越权 + 待办缺项。共用 helper 只防了「抄两份」，
  没防「同一份用出两个意思」。⇒ 判定函数必须是**同一层**的。ADR-0050 §⑤。
- **注释与代码字面冲突，是 bug 的气味**。终审第一个 finding 就是
  「注释写着『本行自身不再 commit』、代码却 commit 了」。
  注释写下的意图比注释本身更值得当断言用。
- **守卫测试要能对旧代码变红**。对着旧代码也绿的断言不是守卫 ——
  「notify 不自己提交」对着旧代码也绿（旧的 commit 在调用方），
  真正的守卫必须落在**调用方**的提交次数上，且场景要让通知**真的发出去**。
- **计划的前提可能是错的，且「已实现」不等于「被用上」**。计划写「部分索引是 500ms
  指标的全部支撑」，真库 EXPLAIN 证明**不成立**。⇒ 「建了索引」≠「被用上了」；
  空表上的 EXPLAIN 更是什么都证明不了。
- **同一概念的多份清单会漂移，且漂移是静默的**。全仓三份角色词表实测差集：
  `VIEWER` 只在两份里、`DATA_ADMIN` 只在一份里（**发不出 token**），交集只剩 4 值，
  且**没有任何契约测试互相对齐**。⇒ 词表要有单一来源 + 对齐测试。
- **判据应当是「系统实际执行的那条路径」**，不是我以为的语义（我曾把自己发现的
  越权泄漏判成「不是 bug」）。
- **（D0）选一个字段当「并发令牌」之前，先查它有没有维护者**。ADR-0048 选
  `record_hash` 当正确性层，但 6 条编辑路径**一条都不重算** ⇒ 阶梯永远走
  「放行」⇒ 保护是**空操作**。⇒ 「有这一列」≠「这一列会变」。
- **（D0）计划给的列形状要用全库实测否决**。计划写 `String(16)`（那是**值**的
  长度）而全库 25 张同名列都是 `String(64)`；计划写 nullable 而全库都是 NOT NULL
  （空串是唯一哨兵，阶梯按 `== ""` 写）。⇒ 列形状看**全库分布**。
- **（D0）Mock 行撑不住依赖 ORM 状态的逻辑**。`compute_record_hash` 读
  `state.dict` ⇒ 6 个既有单测的 MagicMock 行必须改成**真 ORM 实例**。
  这不是「为了让测试过」，是 Mock 本来就测不出这条不变式。
- **（D0）哨兵值不是 None**。`LoaderCallableStatus.NO_VALUE` 会让「取不到值」
  变成「拿到一个怪东西」⇒ 待 flush 对象的哈希计算直接 TypeError。
- **（D1/D2）补了表上的列 ≠ 补了响应里的字段**。D0 给 cost_est 补了
  `record_hash` 列，**响应 schema 忘了补** ⇒ 前端拿不到基线 ⇒ D2 的契约对
  该表**不可用**（bug-2037）。⇒ 补列时把**读路径**一起列出来。
- **（D2）ADR 写的响应体形状要和仓库的错误信封核对**。ADR-0048 §⑦ 写的是
  顶层三字段，而本仓全部 4xx/5xx 走 `{code, message, detail, trace_id}`
  ⇒ 照字面实现 ⇒ 前端要解析两套信封（bug-2038）。
- **（D2）契约变了，既有测试必须跟着变**。6 个 PATCH 端点现在**必须**带
  `expected_hash` ⇒ 既有测试不带基线就拿 409。⚠️ 这是**故意**的：
  「保护不存在」不能是默认值。
- **（D3）同一 URL 空间不许出现两套词表**。`/change-impact` 用类名、
  `/results`+`/locks` 用表名、`record_comments` 列又用类名 ⇒ 三处三套
  （TODO-060）。跨 URL 空间的两套词表是**欠账**，不是「各管一段」。
- **（D2）性能断言的失败要先复跑再当回归**。D2 那次全量里 todo 的 500ms
  预算挂了（1264ms），单独复跑 198ms ⇒ 满负载下的抖动，不是回归。
