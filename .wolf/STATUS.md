---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-19（第 5 轮）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ 本会话完成

### 第 1~2 轮（前序会话）：P8 契约词表治理 + 类型闸

12 个同族缺陷 bug-180~191（词表不在类型里 → 客户端猜 → 猜错 → 生产静默错）已闭环；
两道编译期闸（`StrictColumns<T>`、词表契约类型 + 双向断言）已补。
明细见 `.wolf/buglog.json` + commit `c9d937f`→`5b1174c`。
（该轮 handoff 另存 `/tmp/pcs-handoff-2026-10-19-P8词表治理(bug180-191).md`。）

### 第 3 轮（本会话）：P9-Prep 实施计划（编写 + 两轮审查 + 4 项裁决）

产出 **1 份计划**：`docs/PCS-PLAN-P9-PREP.md`（1662 行 / 9 task）。
提交：`60b0d35`（计划）→ `a2744f0`（cerebrum）→ `39e162f`（审查修正 + 裁决）。

**范围裁决**：SPEC（V2.0）覆盖 P9-Prep/P9A/P9B 三段共 17.5–24 人周。
只写 P9-Prep —— 后者 4 份 ADR 未定（编辑锁存 DB 还是 Redis、通知建表还是实时算），
此时写代码级步骤等于写 fiction。**P9A 计划待 ADR 落盘后另写 `docs/PCS-PLAN-P9A.md`。**

**两轮审查**（`/plan-eng-review` + 专家委员会），共 6 个 issue：
- ADR-0044 §⑤ 原写「Redis 挂 → 无锁放行」⇒ 静默覆盖 user-stated learning
  `ekris-redis-lock-degradation`，且 Redis 挂掉会静默丢用户编辑
  ⇒ 改**两层锁**（Redis 体验层 + `record_hash` 兜底层），§⑥ 粒度、§⑦ 409 契约
- ADR-0042 §③ 停用门只挂 `/auth/login` ⇒ `/mock-login` 是独立签发路径，
  无 `tv` claim、不查 users、不写审计 ⇒ 两者共用 `_issue_tokens()`
- 闸门复用**已存在**的 `scripts/run_gate.py`（cerebrum TODO-050 已立法），
  不新建 `_alembic_gate.py` —— 原提案的前提（两个 alembic 闸门）经核实是错的：
  `check_migration_idempotency.py` 是静态解析迁移文件，从不跑 alembic
- ADR-0044 §⑥「唯一收口」经核实**不成立**：`finalize_calc_record` 不是
  `record_hash` 唯一写入点，实测 6 条旁路；`updated_at` 带 `onupdate=func.now()`，
  空 hash 是 pump/pipe/pipe_net 的**常态**路径

**4 项裁决（用户）**：MFA 路径 B（AD 密码二次输入 + `SIGN_2FA_FALLBACK`）｜
mock 会话豁免二次认证（安全依据：生产不挂 mock 路由）｜
本版不设邮件服务器，预留 `NotificationChannel` 接口｜
P9-OPEN-004 每日凌晨 / P9-OPEN-006 WebSocket+降级轮询。

委员会建议 3（TODO-047 改 TODO-045）**驳回** —— TODO-045/046 已被占用，
它们是 `##` 级标题，`grep "^### TODO-"` 会漏一半。根因已进 cerebrum。

### 第 4 轮（本会话）：执行 P9-Prep 计划（9 个 task 全部完成）

`docs/PCS-PLAN-P9-PREP.md` inline 执行完毕。产出：
**闸门** `pcs-backend/scripts/gate_alembic_check.py`（接 `.githooks/pre-commit` 第二段）｜
**ADR-0046~0049**（用户身份 / 观测层 / 编辑锁 / 通知待办）｜**2 份 note**（P1 端点清单、MFA 决议）｜
SPEC §2.2.2/§2.2.3/§2.2.4/§2.3/§3.2.2/§3.2.4/§3.2.5/§8/§9 全面回写｜
Web 开发计划 P9 拆三段｜TODO-047 登记。

**ADR 编号不是 0042~0045** —— ADR-0041 正文预留了「0042 = 解冻机制」「0043+ = 后续接口扩展」，
本轮从 **0046** 起。两份文档占同一个号就是第二个真相源。

执行中发现并修正了计划/SPEC 的 6 处事实错误（详见 commit 说明与
`.superpowers/sdd/PCS-PLAN-P9-PREP/progress.md` 的 `Ruling:` 行），其中三处是**会让人验错东西**的：
① `alembic check` 比对 ORM ↔ **活库**，不读迁移源码 —— 按原计划往 `alembic/versions/`
放探针会得到假绿；② `for r in app.routes` 在本仓 FastAPI 版本上枚举不到任何 API 路由
（`_IncludedRouter` 不展开）—— 计划的「唯一可信来源」会产出空清单；
③ `record_hash` **不是**覆盖全部结果表 —— 29 张里只有 19 张有。

### 第 5 轮（本会话后半）：P9A 实施计划（编写 + 两轮审查）

产出 **`docs/PCS-PLAN-P9A.md` 总纲 + 4 份 lane**（1-身份 / 2-交付物写面 / 3-通知待办 / 4-编辑锁与CIA）。
经 `/plan-eng-review` + 决策委员会**两轮**，共 16 条 issue 全部处置，`UNRESOLVED: 0`。
明细见计划末尾 `## GSTACK REVIEW REPORT`。

**开工前勘察推翻了 SPEC 的一个关键假设**：P9A 不是「从零建 34 件事」——
实测 **8 张交付物 ORM 表 + 4 个 service（约 1900 行，各带约 450 行测试）已存在，
但无任何 API 出口** ⇒ P9A 主要是接线，真正新建只有 2 表 + 2 列 + 约 16 端点。

四条 lane **各自带自己的迁移**，可并行（卡不到同一个 alembic head 上）。
唯一强制顺序：**D2 编辑保存路径在 B 之后**。

---

## ✅ 基线

后端 **4643 passed / 77 skipped / 0 failed**（P9-Prep 落地后实测，+14 = PP-5 闸门的
10 个用例 + `run_capture` 的 4 个），前端 **704 passed / 0 failed**。
两端 lint/typecheck clean。`check-api-drift.sh` → OK / exit 0。

---

## 🚀 Next quest



1. **执行 `docs/PCS-PLAN-P9A-1-身份.md`（A1→A3）** —— 计划已写好并审完两轮，**无前置，是整条线起点**。
   ⚠️ **B4 有阻塞式 Step 0**：`change_notice_service.approve_change_notice` 是否等同
   SPEC 的 `abandon-change` 必须先读实现判定（approve 与 abandon 是相反动作，
   接错 = 数据语义错误），**结论写进 commit，无结论不开工**。
   B/C/D 三条 lane 可与 A 并行；D2 必须在 B 之后。


2. **两件多日工程，别当小任务排**：
   - **TODO-026**：9 张结果表里 8 张仍是 `input_json`/`output_json` 简化容器，
     照 `CoolingTowerResult` 的 14 子结构铺开 ≈ **100+ 个子结构** + 迁移 + 契约 + 测试；
   - **TODO-032**：条目写 4 个文件，**实测 29 个**用真 PG（`get_async_session_factory`）。


3. **P9A 计划里的未决项**（详见总纲 §尚未解决）：
   ① 周期估算可能偏低 —— SPEC 给 4~6 周，但 WebSocket / ARQ 失败注入 / 编辑锁
   不在原估算里；② `GET /deliverables/{id}/actions` 的数据源未定；
   ③ `audit_logs` 保留期未裁决（裁决 2 让写入量取决于编辑频率）。


4. **P9-Prep 顺带登记的**：
   - **TODO-047**（已登记，**已移出 P9A**）：`acquire_record_lock` 全仓**唯一调用方**是
     `workspaces.py:129`（workspace 归档），P9A 的 6 个文件 **0 处引用** ⇒ 与 P9A 无交集，
     是 P7/P8 缺陷。（委员会原判「P9A 会加剧它」经实测前提有误。）
   - **ADR-0048 §⑥ 覆盖缺口**：29 张 `*_result(s)` 表里 **19 张**有 `record_hash`，
     `sim_*`(8) / `util_results` / `cost_est_results` **没有**，`two_phase_results`
     有 hash 但**无 `updated_at`** ⇒ 这 **11 张**要做编辑并发保护**需要新列**（其中 9 张两者都没有）。补哪列未裁决。
   - **ADR-0046 三项决策委员会裁决**（2026-10-19）：① **`/auth/mock-login` 不得写
     `users` 表** —— 共用 `_issue_tokens()` ≠ 共用惰性建行；mock 的 alice 与真实 AD
     alice 同名会落进同一行，而 `acl.py:13` 明写 `User.roles` 是 ACL 权威输入。
     mock 走临时签发不持久化，`tv` 写哨兵 0；② **孤儿清单交用户裁决**，实施者只出
     清单 + SQL 模板（补行=授权恢复 / 保留=授权静默失效，方向相反）；
     ③ 编号 0043~0045 **是空的**，跳号因 ADR-0041 把 0043+ 划进兜底桶。
     ⚠️ 另三条硬约束（委员会复审追加，同属 ADR-0046）：
     **① 带归属的待办** —— `project.py:153` 的 `User.roles` 列注释写 `SYSADMIN`，
     是 2026-10-04 收敛的遗漏（现行 `SYSTEM_ADMIN`）。它**挡在惰性建行的写入路径上**，
     实施者第一眼看到的是它。**P9A-USR-001 实施时必须同时修**，
     顺带对 `roles` 取值做契约枚举校验。**不在 P9-Prep 修**（会让「注释何时变的」
     指向错误 commit）。
     **② `token_version = 0` 是保留值** —— mock 令牌用 `tv=0` 哨兵；若 AD 同步把
     `server_default` 改成 0，机制**静默反向**：mock 令牌与真实用户 tv 全等，
     等于任何 mock 令牌都能刷新任何真实用户的会话。⇒ P9A 迁移加 `CHECK >= 1`。
     **③ 不用内存黑名单缩短吊销窗口** —— 与 ADR-0048 §⑤ 同 concept（跨进程共享状态
     塞进单进程内存），参见 TODO-047。要缩短就走有状态 token。
   - **ADR-0049 §① 通知写侧同步/异步未锁**：本版无邮件，原「异步以免阻塞外部投递」理由已失效。

✅ **TODO-028 已于 2026-10-08 核实关闭**（此前 STATUS 里的挂靠是陈旧引用）。

---

## Context

- main，工作区除 `.wolf/*`（钩子维护）外干净。**不要建 worktree**（历史事故）。
- **两库均在 `p8_011`（head）**，`alembic check` 均 exit 0。`pcs_test` 是行为验证库。
  （此前 STATUS 写的 `p8_010` 是陈旧值。）
- 改迁移的纪律：`alembic check` 退出码 **255**；先 `current` vs `heads`；
  **每个库各跑一次**；行为验证上真库。
- 契约产物（`openapi.json` / `openapi.snapshot.json` / `api.d.ts`）由 G-08 钩子在
  **commit 之后**重生成，而 `git add` 在钩子之前 ⇒ 偶尔漏提交，
  手工 `git status` 看一眼。发现不同步时**不要** `git checkout --` 丢弃。
- 无 CI/CD（单人开发裁决，勿再建议）。本地 gate 走 `.githooks/`（`core.hooksPath`
  已设），**不是** pre-commit 框架。
- **提交约定**：本轮 3 个 commit 落在 main（仓库历史线性，且 CLAUDE.md 的 QA 闸门
  按「main 就是批末」描述）。

---

## 教训（本会话新增）

- **ADR 不得静默覆盖 user-stated learning**。要与既有裁决冲突，ADR 必须**显式引用**
  并给出**可证伪的作废条件**（「若改判为 (b)，本条作废」）。
  冲突不必然是错 —— 但**不写**就是错。
- **裁决要连落地约束一起写**，不只写结论。MFA 路径 B 记四条：审计 action
  **不得**复用 `SIGN_2FA_OK`（否则审计读成「已上真 MFA」）；路径 B 是过渡态；
  mock 豁免范围限定**登录层**、函数本身不豁免；邮件预留**不写空壳实现**也不写临时 `if`。
- **「唯一收口」是断言不是事实**，写进 ADR 前要 grep 验证。
  本次核实发现 6 条旁路 ⇒ 结论虽不变，论证（与实施者的预期）必须改。
- **引用编号前先验证编号存在**；断言一批编号空闲时先确认查询没漏级别
  （`TODOS.md` 混用 `##`/`###` 两种标题级别）。
- **评审意见要先核实再接受**。本次 6 条里 1 条基于误读（TODO-045 已被占用），
  1 条基于我的误读（以为有两个 alembic 闸门）。**驳回也要带证据。**
- **注释防不住已进过记录的 bug**（`alembic check` 的 255 已进 CLAUDE.md）⇒
  该由代码约束（共享函数 + 单测），不是每次改动补一句提醒。
- **「验证手段」本身也会是错的，且错得很安静**。本轮三处：
  ① `alembic check` 不读迁移源码 —— 按「加一条迁移造漂移」验收会拿到**假绿**；
  ② `app.routes` 不展开 `_IncludedRouter` —— 枚举路由会拿到**空清单**；
  ③ SPEC §2.2.3 的 `grep app/api/` 在仓库根是**命令没跑成功**，不是「搜过了没有」。
  ⇒ 写验收步骤时先问「这条命令真的能看到我想看的东西吗」，并**实跑一次看输出**，
  别照抄形状像对的命令。
- **计划里的「唯一收口 / 全部覆盖」是断言不是事实**，且实测常比断言小。
  本轮三处断言各错一半：record_hash 21 张（实 18/29）、唯一写入点（实 6 条旁路）、
  11 张表有 `updated_at`（实 4 张）。写 ADR 前逐条 grep 验证。
- **文档里不要硬写会自然变化的数字**。`259 schema / 141 字段` 抄在 SPEC 与脚本
  docstring 两处，**两份都漂了**（实为 296/158）。权威值应在代码里，文档指向它。
- **`.superpowers/` 未被 gitignore**，而计划里多个 Step 是 `git add -A` ⇒
  执行脚手架会被提交。开工前先确认工作区已 ignore。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
