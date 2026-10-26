P9 工作流与权限开发规格说明书（修订版）
文件标识：PCS-REQ-2026-002-SPEC-P9
当前版本：V2.15（V2.14 + TODO-082 落地登记，2026-10-27；V2.8 + TODO-078 落地登记，2026-10-26；V2.7 + TODO-077 落地登记，2026-10-26；V2.6 + TODO-084 全部落地登记，2026-10-26；V2.5 + TODO-086 落地登记，2026-10-26；V2.4 + P9A-DLV-011 收尾两处裁决登记，2026-10-26；V2.3 + P9A-DLV-011 评审修复批登记，2026-10-26；V2.2 + P9A-DLV-011 落地登记，2026-10-26；V2.2 + P9A-DLV-007 / TODO-057 落地登记，2026-10-26；V2.0 + P9A Z 收口验收登记，2026-10-21；V1.3 → V2.0 结构性重排，2026-10-07）
修订依据：架构审查结论（2026-10-07）+ TODOS.md 实证核销（2026-10-06/07）
修订性质：破坏性重排——V1.3 的"前端集成阶段"定位作废，改为 P9-Prep → P9A（后端）→ P9B（前端）三段式

修订摘要（V1.3 → V2.0）
#	变更	原因
R1	P9 拆为 P9-Prep / P9A / P9B 三段	V1.3 假设"后端已由 P1 交付"，实测 Deliverable/SignatureMatrix 无 service、无 API、无路由（2026-10-08 更新：Deliverable **读面**已由 P8 前置补上，SignatureMatrix 仍空）
R2	新增 P9-Prep 前置阶段（清 P7 欠账 + 4 份 ADR）	bug-144 未修、utility_* CHECK 缺 ORM 声明、身份模型迁移无 ADR。**2026-10-08 更新：PP-1~PP-4 已全部完成**（见 §2.2.1 状态列），P9-Prep 剩余量见 §2.3
R3	新增 P9A 后端交付物子系统规格	V1.3 §1.2 "不包含后端"作废
R4	新增 ADR 前置项 4 份	用户身份模型迁移 / workflow_progress 观测层 / 编辑锁 / 通知数据模型
R5	数据模型补 3 张表	notifications、todos、workflow_progress（P0 清单中均无）
R6	P9-ADM-001 补 token_version 条目	V1.3 "停用"只写四个字，未规定已签发令牌处理
R7	MFA（P9-OPEN-001）升级为硬阻塞	V1.3 悬空，但签署/代录两条核心链路依赖它
R8	工作量重估：5.5–7.5 人周 → P9A 8–12 + P9B 3–4 人周	V1.3 只算前端，漏掉整个交付物后端
R9	周期重估：3 周 → 约 10 周（Prep 2 + A 4–6 + B 3–4）	同上
R10	依赖修正：P1, P7 → P7 收口 + P9-Prep ADR	P1 交付物后端实际未交付
第一部分：引言（修订）
1.1 目的
本文档定义 P9 阶段（工作流与权限）的完整需求规格，分三段交付：

P9-Prep：前置清账与架构决策，不动业务代码

P9A：后端交付物子系统 + 用户身份改造 + 横切观测层

P9B：前端签署交互 + 变更影响展示 + ADMIN 界面

1.2 文档范围（修订）
包含：

P9-Prep：P7 欠账清理、4 份 ADR、P1 端点可用性核实

P9A：DeliverableService、SignatureMatrixService、workflow_progress 写入层、users 表启用 + AD 同步、token_version、二次认证中间件、编辑锁后端、通知/待办后端

P9B：V1.3 原有的签署流程前端、变更影响前端、ADMIN 前端、并发控制前端

不包含（修订，删除 V1.3 的错误表述）：

~~后端状态机引擎（P1已交付）~~ ← 删除。P1 仅交付状态机骨架，交付物 service 层需 P9A 建设

~~后端变更影响分析引擎（P1已交付）~~ ← 改为：P1 检测层已交付，确认分流 API 待 P9-Prep 核实后决定归属

CONFIG 审批流前端（P2 已交付）

AI 功能实现（P10 仅预留接口）

1.3 术语补充（新增）
术语	定义
P9-Prep	P9 前置阶段：清账 + ADR + 端点核实，不写业务代码
P9A	P9 后端阶段：交付物子系统 + 身份改造 + 观测层
P9B	P9 前端阶段：签署交互 + ADMIN 界面
token_version	users 表列，JWT refresh 校验用，停用用户时递增使在手令牌失效
身份模型迁移	user_id 从 uuid5(username) 派生 → users 表持久化主键
第二部分：P9-Prep（全新增，2 周）
2.1 目标
在 P9A 动工前，把 P7 遗留的阻塞项清掉、把 P9A 的架构决策定死、把 P1 的实际交付面核实清楚。本阶段不写业务代码（除清账迁移外）。

2.2 任务分解
2.2.1 P7 欠账清理（阻塞级）
项	内容	证据
PP-1 ✅	bug-144：user_projects 四个外键缺失（user_id / project_id / granted_by / revoked_by），成因 p7_open_010:40-43 裸 sa.ForeignKey 位置参数被 alembic 静默丢弃。需新迁移补 FK，补前先清孤儿行	TODOS.md "397 条真实构成"
PP-2 ✅	*utility_ CHECK 缺 ORM 声明**：utility_energy_summary(8) / utility_heat_exchange(6) / utility_fuel_gas(5) / util_results(4) / utility_power_items(4)。补 __table_args__，零迁移成本。补前逐条核对 CHECK 表达式与 DB 一致	TODOS.md "剩余 43 条"
PP-3 ✅	ondelete 裁决：fk_utility_energy_summary_workspace_id_workspaces DB=CASCADE / ORM=RESTRICT，两侧声明不一致。需业务裁决（删除项目是否连带删能耗汇总）	TODOS.md 同上
PP-4 ✅	uq_user_projects_user_project 补 ORM 声明：DB 有、ORM 无，换库/建 SQLite 单测时唯一约束丢失	TODOS.md 同上
PP-5 ❌	alembic check 闸门自动化：把"改完迁移必须跑 alembic check"从 CLAUDE.md 一段文字变成 git hook / 脚本，提交迁移文件时自动跑并阻断。注意退出码是 255 不是 1	TODOS.md "缺一个 ORM↔迁移静态检查"
验收（**2026-10-08 已达成，实际优于预期**）：`uv run alembic check` 报「No new upgrade operations detected」，exit 0 —— 不是原定的 ≤5，是 **0**。

实际处置与原计划的差异，都是原计划没预见到的：

- **PP-1 / bug-144**：新迁移 `p7_s5_007`（drop(if_exists) + create，幂等）。同批还修了 bug-143（`user_projects.created_by` 继承列从未迁移）。
- **PP-2**：原估 23 条 CHECK，实际补了 **28** 条 CHECK + **9** 条 UNIQUE（共 37 条声明）。补声明后立刻撞出一条 fixture 写 `operating_hours_per_year=10000.0`（一年最多 8760/8784 小时）—— **这 39 条不是噪声，是测试库与真库之间的护栏缺失**。
- **PP-2 附带**：为让一条 PG 专有 CHECK（`interval '1 second'` 类型字面量）能在 SQLite 建表，`tests/conftest.py` 加了按约束名的 SQLite 替身，并新增测试证明 PG 原式与 SQLite 替身在同一张 6 条判定表上裁决完全一致。
- **PP-3**：用户裁决 CASCADE，ORM 已改（`fd0e8b9`）。
- **PP-2/4 附带**：另发现 `projects` 整表零外键 —— ORM 声明了 `use_alter=True` 但那条延迟迁移从未落地（bug-146，新迁移 `p7_s5_008` 补建）。**`use_alter=True` 不会自己生成迁移。**
- **`compound_api521_thresholds` 名字是被 `NAMING_CONVENTION` 展开错的**（bug-147），改显式命名。

2.2.2 四份 ADR（阻塞级）
ADR	标题	必须回答的问题
ADR-A	用户身份模型迁移：uuid5(username) → users 表持久化	① ID 等价性：历史 uuid5 与新 DB 主键如何共存/迁移？② 是否回填历史 uuid5 为 users 行？③ 登录路径变更（现在不查 users，未来为判停用要查）④ token_version 引入时机 ⑤ 停用即刻作废 access/refresh token 的实现
　　✅ 已裁决：`docs/adr/0046-user-identity-model-migration.md`（accepted 2026-10-19）。① DB 主键唯一权威，uuid5 降级为存量 JWT 解析；② 不批量回填，惰性建行；③ 登录与 mock 共用 `_issue_tokens()`；④ 只给 refresh 写 `tv`；⑤ 停用时 `token_version += 1`，refresh 比对
ADR-B	workflow_progress 观测层	① 写入点清单（哪些状态变更要写）② 同步写 vs 异步写（500ms 延迟要求倾向同步）③ 与 P1 状态机事务的边界 ④ 与计算模块事务的关系
　　✅ 已裁决：`docs/adr/0047-workflow-progress-observation-layer.md`（accepted 2026-10-19）。① 3 个写入点（签署推进/退回、变更单创建与自动关闭、代录批准）；② **同步写，与业务状态同事务**；③ **调用方写、不在 state_machine 埋点**（实测 `transition()` 只 flush，commit 在 `records.py:215`）；④ 与计算模块事务无关
ADR-C	编辑锁	① 存储：DB SELECT FOR UPDATE vs Redis ② 自动续期机制（前端心跳频率 + 后端续期接口）③ 超时清理（30 分钟）④ 与状态机事务的关系 ⑤ Redis 不可用时的降级
　　✅ 已裁决：`docs/adr/0048-edit-lock-storage.md`（accepted 2026-10-19）。① Redis；② 心跳 60s / TTL 30min；③ Redis TTL 自动清理；④ 与状态机解耦，**不得**把持锁当写入前置条件；⑤ **两层锁**（Redis 体验层 + DB record_hash 正确性层），显式声明了与 user-stated learning `ekris-redis-lock-degradation` 的关系与可证伪条件
ADR-D	通知与待办数据模型	① notifications 表 vs 实时计算 ② todos 表 vs 实时计算 ③ 若实时计算，≤500ms 加载指标靠什么索引支撑 ④ 通知保留 30 天清理任务归属（ARQ？但 TODO-016 显示 ARQ 失败路径覆盖为零）
　　✅ 已裁决：`docs/adr/0049-notification-and-todo-data-model.md`（accepted 2026-10-19）。① **通知建表**；② **待办实时计算**（从 `SignatureMatrix.steps_json` 重算，不建表）；③ 部分索引 `ix_notifications_recipient_unread (recipient_id, read_at) WHERE read_at IS NULL` 必须进迁移；④ ARQ 清理任务 + 失败注入测试（TODO-016）+ 纳入既有「入队 ⊆ 已注册」断言
验收：4 份 ADR 状态为 accepted，且被 P9A/P9B SPEC 引用。

2.2.3 P1 端点可用性核实（阻塞级）
逐端点 grep 确认，产出《P1 实际交付面清单》：

P9 前端需调用的端点	核实命令	归属
POST /records/{module}/{id}/submit-approval	grep -rn "submit-approval" app/api/	存在→P1；不存在→P9A
POST /records/{module}/{id}/approval-step	同上	
POST /records/{module}/{id}/abandon-change	同上	
POST /records/{module}/{id}/request-reversal	同上	
POST /records/{module}/{id}/reversal-decision	同上	
POST /records/{module}/{id}/obsolete	同上	
POST /records/{module}/{id}/comments	同上	
GET /deliverables/{id}/actions	grep -rn "deliverables" app/services/ app/api/	已知不存在 → P9A
POST /deliverables/{id}/issue	同上	已知不存在 → P9A
POST /deliverables/{id}/sign-step	同上	已知不存在 → P9A
POST /deliverables/{id}/customer-approval/proxy	同上	已知不存在 → P9A
POST /change-impact/{module}/{id}/confirm	grep -rn "change-impact" app/api/	待核实→P1 或 P9A
POST /change-impact/{module}/{id}/manual-adjust	同上	待核实

✅ 已完成（2026-10-19）。产出 `docs/PCS-NOTE-P9-Prep-P1端点交付面清单-2026-10-19.md`。

⚠️ 上表的核实命令**全部有缺陷**，照抄会得到假结论，修正见清单 §0/§1：
① `app/api/` 在 `pcs-backend/` 下，在仓库根跑是「目录不存在」，不是「搜过了没有」；
② `for r in app.routes` 在本仓 FastAPI 版本上枚举不到任何 API 路由
（`include_router` 包成 `_IncludedRouter` 不展开），须改用 `app.openapi()["paths"]`。

结论：上表 11 个端点**确认不存在** ⇒ 归 P9A；
`POST /change-impact/{module}/{id}/confirm` **不存在**，实际存在的是
`POST /change-impact/{record_type}/{record_id}/confirm-recalc`
（`app/api/v1/change_impact.py:27`），它**不含** P9A-CIA-001 的哈希判定分流。
⇒ **P9A-CIA-001 / CIA-002 均归 P9A**。
验收：清单完成，每条明确归属；凡归 P9A 的写入 P9A SPEC。

2.2.4 MFA 决议（阻塞级）
P9-OPEN-001 从"待确认"升级为硬阻塞。二选一：

路径 A：确认公司 MFA 方案（TOTP / 短信 / 硬件令牌），写入 SPEC

路径 B：Fallback——AD 密码二次输入 + 强制审计（SIGN_2FA_FALLBACK），MFA 后续替换

验收：P9-OPEN-001 状态改为"已确认"或"已 Fallback"，且 SPEC §3.2.1 通过/退回操作、§3.2.1（5b）代录批准两条链路有明确实现依据。

✅ 已完成（2026-10-19）：**路径 B —— AD 密码二次输入 + `SIGN_2FA_FALLBACK` 强制审计**，
见 `docs/PCS-NOTE-P9-Prep-MFA决议-2026-10-19.md`。
连带裁决：mock 会话豁免二次认证（**限于登录层**，`verify_secondary_auth()` 本身不得豁免）；
P9-OPEN-002 本版不设邮件服务器、预留 `NotificationChannel` 接口；P9-OPEN-004 每日凌晨；
P9-OPEN-006 WebSocket + 降级轮询（降级状态必须可观测，不得直接停推）。

2.3 P9-Prep 交付物（**2026-10-19 状态**）

| 交付物 | 状态 | 落点 |
|---|---|---|
| bug-144 迁移 + 应用 | ✅ | `p7_s5_007`（另修 bug-143） |
| CHECK / UNIQUE ORM 声明补齐 | ✅ | bug-147，28 CHECK + 9 UNIQUE |
| ondelete 裁决决议 | ✅ | CASCADE，`fd0e8b9` |
| uq_user_projects_user_project ORM 声明 | ✅ | bug-147 |
| `projects` 零外键修复 | ✅（计划外） | bug-146，`p7_s5_008` |
| alembic check 闸门脚本 / git hook | ✅ | `pcs-backend/scripts/gate_alembic_check.py` + `.githooks/pre-commit` 第二触发段，见 `.githooks/README.md` |
| ADR-A / B / C / D（4 份，accepted） | ✅ | ADR-0046 / 0047 / 0048 / 0049。⚠️ 编号**不是** 0042~0045 —— ADR-0041 正文预留了 0042（解冻机制），故从 0046 起 |
| 《P1 实际交付面清单》 | ✅ | `docs/PCS-NOTE-P9-Prep-P1端点交付面清单-2026-10-19.md`。结论：SPEC 点名的 12 个端点里 11 个确认不存在，`confirm` 不存在（存在的是不含哈希判定分流的 `confirm-recalc`）⇒ 交付物写面全归 P9A |
| MFA 决议 | ✅ | `docs/PCS-NOTE-P9-Prep-MFA决议-2026-10-19.md`。路径 B（AD 密码二次输入 + `SIGN_2FA_FALLBACK`）。连带关闭 P9-OPEN-002（无邮件，预留 NotificationChannel）/ 004（每日凌晨）/ 006（WebSocket + 降级轮询） |

**PP-5 注（2026-10-19 已落地）**：闸门 = `pcs-backend/scripts/gate_alembic_check.py`，经 `scripts/run_gate.run_capture()` 观测退出码，只判 `rc == 0` / `rc != 0`，**不比较 255 或 1**。四个分支：无漂移放行 / DB revision 落后则阻断并提示 `upgrade head`（「守门没跑」不等于「通过」）/ DB 不可达则放行 + 告警（避免训练出 `--no-verify`）/ 其余非 0 阻断。

⚠️ **已知盲区（无法自动化）**：闸门只对 `DATABASE_URL` 指向的那个库成立（开发库 `pcs`）。`pcs_test` 的漂移不在视野内 —— **「hook 绿」不得被读成「两库都干净」**，要声称两库都干净必须单独跑一次。另注：`alembic check` 比对的是 ORM ↔ **活库**，不读迁移源码 —— 加一条未 apply 的迁移不会被检出。

沿用既有裁决：不做静态列覆盖检查器（「狼来了」）；不用 pre-commit 框架（与「CI/CD 不做」冲突），走 `.githooks/` + `core.hooksPath`。

周期：**原估 2 周（1 人），剩余量按 4 项未完成项重估约 1.5 周**（ADR 4 份最重）。
阻塞下游：P9A 全部

第三部分：P9A 后端（全新增，4–6 周）
3.1 目标
交付 P9B 所依赖的全部后端能力：交付物子系统、用户身份改造、横切观测层。

3.2 任务分解
3.2.1 交付物子系统（核心）
编号	内容	依据
P9A-DLV-001	DeliverableService：create / issue / sign-step / customer-approval-proxy 四方法	P9 SPEC §3.1.2 端点清单
P9A-DLV-002	Rev 生成器：版本序列配置驱动 + 序列内校验	P1 计划 1.2
P9A-DLV-003	doc_no 编号引擎：段解析 + scope 原子序号分配	P1 计划 1.2
P9A-DLV-004	交付物快照绑定：仅 CHECKED 可绑定、record_hash 固化、AFFECTED 判定	P1 计划 1.2
P9A-DLV-005	变更单：deliverable_type=CHANGE_NOTICE 创建/签署/自动关闭绑定记录	P1 计划 1.2
P9A-DLV-006	变更前快照服务：进入 STALE/CHANGE_PENDING 时保存、放弃/撤销时恢复	P1 计划 1.2
P9A-DLV-007	SignatureMatrixService：steps_json 消费方，矩阵步骤推进、角色判定、动态列数	SUP-005　**✅ 2026-10-26 落地**（P9A-DLV-007 + TODO-057 同批，commit `da299fb` / `3b7e99b`）。⚠️ **实现偏离**：①「矩阵步骤推进、角色判定」**早在 P9A B2 就已落地**（`DeliverableService.sign_step`），本项真正补的是**「矩阵从哪来」**——`signature_matrices` 原本恒 0 行且全仓无创建方 ⇒ 变更单（`matrix_id` NOT NULL + FK）建不出来；②「动态列数」是前端行为（`SignatureMatrix.tsx` 按 `steps.length` 出列）；③本项**不含**把 `sign_step` 的角色判定抽进新服务（会动已验收的签署路径）。落地内容：`SignatureMatrixService.parse_steps`（`steps_json` 的**唯一**解析口）+ `ensure_change_notice_matrix`（惰性建内置模板 `CHANGE_NOTICE_3_LEVEL` + 项目绑定）
P9A-DLV-008	代录客户批准后端：凭证附件存储（PDF/JPG/PNG/EML ≤20MB）+ 二次认证 + 审计 CUSTOMER_APPROVAL_PROXIED	ADR-0007
P9A-DLV-009	bug-145：ChangeNoticeService.create_change_notice 写死 matrix_id=None，但 Deliverable.matrix_id NOT NULL 带 FK → 真库必 500。**2026-10-08 已部分处置**：函数改为显式 `raise NotImplementedError`（不再留「接个 API 路由就 500」的哑雷），5 个 happy-path 测试改为断言拒绝 + 无副作用 + 不写审计。**✅ 2026-10-26 已真正修复**（随 P9A-DLV-007 落地，commit `3b7e99b`）：`create_change_notice` 落地并绑定矩阵；**那 5 个假 DB 用例已改成真库用例**（假 DB 结构上看不见 DB 层的 NOT NULL / 唯一约束 —— 这正是「测试根本不碰数据库」这条根因）。✅ **HTTP 入口已补**（2026-10-26 P9A-DLV-011 落地，TODO-068 闭环）：`POST /records/{module}/{id}/initiate-change` / `/apply-change` / `/change-notice` ⇒ 不再是「service 层可达、界面无发起点」。
P9A-DLV-011	**变更单闭环的 HTTP 面 + 签署矩阵管理面**：①`POST /records/{module}/{id}/initiate-change`（CHECKED → CHANGE_PENDING，自动写 BEFORE_CHANGE 快照）、`/apply-change`（→ CHANGED）、`/change-notice`（建变更单，FORMAL 工作区门禁）、`/change-notice/cancel`（作废该记录当前开着的变更单）；②变更单建单即带版本行（ISSUED_FOR_CHANGE）⇒ 3 级矩阵走既有 `sign-step` ⇒ **矩阵真的生效**；③`sign_step` 最后一步置 APPROVED ⇒ **自动**把绑定记录 CHANGED → CHECKED + 写 `change_resolved_by`（ADR-0008「系统自动」）+ CHANGE_NOTICE 观测 COMPLETED；④签署矩阵管理面 6 端点（模板 = SYSTEM_ADMIN / 绑定 = 项目负责人侧）+ `steps_json` 写入时严格校验。	**✅ 2026-10-26 落地**（计划 `docs/PCS-PLAN-P9A-DLV-011-变更单闭环与签署矩阵管理面.md`，commit `9a4f66b`~`b18cbbc`）。⚠️ **实现偏离**：①变更单与记录的关联走 `deliverable_record_bindings`（ADR-0008 明写用它替代原 `change_notice_record_bindings`），不靠解析 `scope_value` 字符串；②`doc_no` 用完整 32 位 hex（可读编号另批，TODO-073）；③矩阵绑定的权限按**三层**判：全局角色 ∈ {DESIGNER, PROCESS_CONTROLLER, SYSTEM_ADMIN} **且** 有项目授权 **且** 项目内角色 = **项目负责人**（`role_in_project=PROJECT_LEAD`）—— **用户 2026-10-26 裁决「只有项目负责人能绑」**；`PROJECT_LEAD` 是**新增**的项目内角色（依据 `spec/校审层级可配置化增补规格说明书.md` §2.1.2「项目负责人（新增）」），⚠️ 词表无序 ⇒ 不声称「≥ DESIGNER」；④「一条记录一张变更单」是**实现推导**的业务约束（TODO-069）—— **2026-10-26 按 TODO-078 调整**：一张变更单可关**多条**记录，但一条记录**同一时刻**只能出现在**一张未关闭**（DRAFT / PENDING）的变更单里（已 APPROVED / 已作废都**不挡**新单）；⑤**新增作废端点** `POST /records/{module}/{id}/change-notice/cancel`（TODO-080，理由必填）—— 作废的是**单据**（`sign_status = OBSOLETE`），记录**保持 CHANGED**（顺手关成 CHECKED = **绕过 3 级校审**）；⑥**快照真的装数据**（TODO-087）：`data_snapshot_json` 此前**恒为 `{}`** ⇒ 撤销/放弃**只回状态不回数据**；现在快照装着记录的业务数据（UUID / 日期 / 枚举**打标签**），撤销/放弃 ⇒ 数据**与 `record_hash`** 都回到变更前	ADR-0002 · ADR-0008 · TODO-068~072 · TODO-077~080 · TODO-087
P9A-DLV-010	**新端点响应 schema 零裸字段**（硬约束，阻塞 P9B）。每个新端点的响应模型必须显式
	声明结构；不得用 `response: object` 或裸 `dict` 敷衍。交付证据 = 覆盖率闸裸字段数不上涨
	（基线 71 保持不变）	P9B 4.2 前端纪律
	⚠️ 与 P9A-DLV-0XX 的区别：0XX 是**修既有 71 个**，本项是**新增的不许欠**。两者都做，P9A
	才不会一边修旧账一边欠新账
P9A-DLV-0XX	API 载荷结构债：全 OpenAPI 的 object/array 字段中有 71 个是裸类型（无 properties/items），覆盖率 87/158 = 55.1%。前端对这些只能继续手写类型 —— 即 TODO-039/041 想消灭的东西。已加覆盖率闸 `scripts/check_openapi_payload_coverage.py`（只拦倒退）。与 P9-Prep 引用的 §3.4 约束① 是同一笔债的两个观测面。**权威值在代码的 `BASELINE_BARE_FIELDS`，本文档不硬写 schema/字段总数**（它们随新增端点自然变化，抄进文档必漂）	TODOS.md TODO-039/041
　　⚠️ 复核推翻了原记录两点：①「无任何测试」是错的（`tests/services/` 下有 5 个，但用假 DB，结构上观察不到 DB 层约束）；②`ChangeNoticeService` **无任何 API 路由调用**、真库 0 行，是未接线的死路径而非线上 500	TODOS.md
验收：P9B 所需全部端点可用；alembic check 无新增漂移；bug-145 有回归测试。

**⚠️ 硬约束（2026-10-08 用户裁决，阻塞 P9B）**：P9A 交付的**每一个**新端点，
其响应 schema **不得含裸 `object` / `array`**（即声明了 object/array 却没有
`properties` / `items`）。

理由：P9B 的纪律是「前端 type 从 `./api` 生成，禁止手写」。而 `pcs-frontend` 的
类型由 openapi-typescript 从 OpenAPI 生成，对裸字段只能生成 `object` / `any[]`。
**P9A 若沿用现有习惯，这批端点会直接产出 unknown，纪律在 P9 内部第一天就废掉** —
不是偿还 TODO-039/041 的债，是把债复制进 P9。

执行方式：`pcs-backend/scripts/check_openapi_payload_coverage.py`。该闸在裸字段数
上涨时 exit 1，天然满足「新端点贡献 0 个裸字段」。P9A 收口时基线应仍为 **71**
（不是下调到 0 —— 71 是既有欠账，属 P9-Prep/§3.4 范围，见 P9A-DLV-0XX）。

3.2.2 用户身份改造（高风险）
编号	内容	依据
P9A-USR-001	users 表启用：AD 同步创建系统用户记录	ADR-A + P9-ADM-001
P9A-USR-002	AD 同步服务：手动触发 + 定时任务（每日凌晨）；用户基本信息（姓名/邮箱/部门）+ AD 安全组	P9 SPEC §3.2.3
P9A-USR-003	角色映射：AD 安全组 → 系统角色（5 角色），支持手动覆盖 + 日志	P9 SPEC §3.2.3
P9A-USR-004	离职处理：AD 删除后标记停用 + token_version 递增使在手令牌即刻失效	新增条目（V1.3 缺口）
P9A-USR-005	登录路径变更：登录时查 users 表判 status；停用用户拒绝登录	ADR-0046
　　⚠️ ADR-0046 §③ 增加两项 SPEC 原条目没有的工作，**不写进排期会掉**：
　　(a) 把签发逻辑抽成单一 `_issue_tokens()`，并让 `/auth/mock-login`（`mock_auth.py:53-68`，
　　　现无 user_id claim / 无 tv / 不查 users / 不写审计）**共用**；否则 ADR-0046 的
　　　①②⑤ 三条断言对 mock 流量全部失效。
　　(b) 导出 `user_projects.user_id` / `audit_logs.created_by` 中**无对应 users 行**的
　　　uuid5 存量孤儿清单。**清单交用户裁决，实施者不得自行决定补行还是保留** ——
　　　补行 = 授权恢复，保留 = 授权静默失效（用户只看到 404，不会看到原因），
　　　方向相反，不是技术优劣问题。P9A 只出清单 + 补行 SQL 模板 + 影响面（孤儿数 /
　　　每个孤儿名下 user_projects 行数 / 建议处置）。**不删 users 行**（FK CASCADE，删即删授权）。
　　(c) ⚠️ **`/auth/mock-login` 不得写 `users` 表**（ADR-0046 §③b）。共用 `_issue_tokens()`
　　　**不等于**共用「惰性建行」—— mock 的 username（alice/bob/carol/dan）与真实 AD
　　　可能同名，uuid5 也以 username 为键 ⇒ 落进同一行。而 `app/core/acl.py:13` 明写
　　　ORM `User.roles` 是 ACL 的权威输入，写入 mock 派生角色 = 让测试数据参与授权判定。
　　　mock 走「临时签发、不持久化」，`tv` claim 写哨兵 `0`；真实 users 行出现后
　　　（token_version 从 1 起）mock 存量令牌自动失效。
　　(d) 🔧 **带归属的待办 —— `users.roles` 的列注释（`project.py:153`）写着 `SYSADMIN`，
　　　是 2026-10-04 收敛的遗漏**（现行值 `SYSTEM_ADMIN`，见 `_guard.py:37`）。
　　　**P9A-USR-001 实施惰性建行时必须同时修正该注释**，否则实施者第一眼看到的是这条
　　　过时注释而非权威词表，写出的值 ACL 不认 —— 即 P8 刚消灭过的 bug-180~191 那类
　　　词表漂移，等于治理倒退。**不在 P9-Prep 修**（超出 ADR 范围，且会让「注释何时变的」
　　　指向错误的 commit）。落库前另需对 `roles` 取值做契约枚举校验（同 `StrictColumns`）。
　　(e) 🔒 **`token_version = 0` 是保留值，真实用户永不为 0。** §③b 的 mock 令牌用
　　　`tv = 0` 哨兵；若 AD 同步把 `server_default` 或建行逻辑改成 0，机制会**静默反向** ——
　　　mock 令牌与真实用户 tv 全等，变成任何 mock 令牌都能刷新任何真实用户的会话。
　　　⇒ `users.token_version` **应有 CHECK 约束 `>= 1`**（P9A 迁移时加）。
　　(f) ⚠️ **不得用内存黑名单缩短吊销窗口**（论证见 P9A-USR-007 📌 段，两处只写一处）。
P9A-USR-006	历史 user_id 兼容：uuid5 派生 ID 与 DB 主键的等价性处理	ADR-A
P9A-ADM-001	`GET /admin/users` —— 用户列表（演示 disable 前后状态）	ADR-0046 §③（惰性建行）
P9A-ADM-002	`PUT /admin/users/{id}/disable` —— 停用用户，同事务 `token_version += 1`	ADR-0046 §⑤
　　⚠️ **这两条不是可选项**：P9A-USR-004 的验收标准是「停用用户 refresh 立即 401」，
　　而**触发停用的入口必须存在** —— 不建 disable 端点，ADR-0046 §⑤ 整段落不了地。
　　**前置依赖**：演示需要 `users` 表有行，而行来自 `P9A-USR-001` 惰性建行与
　　`P9A-USR-002` AD 同步 ⇒ **最小 AD 同步已在本节范围内**，不是可选附带。
　　🚫 **范围界定**：完整用户/授权管理后台（角色编辑、授权增删、批量操作）**单列**，
　　不塞 P9A。审计查询端点**已有**（`audit.py`：`/audit-logs`、`/equipment-deletion-audit`、
　　`/config-audit`），不算新增。
P9A-USR-007	token_version 机制：users 表加列；create_token 写 claim；refresh 端点校验（access token 保持无状态，吊销粒度 = access TTL 30 分钟）	TODO-002 修正后处方
　　📌 **已知边界，P9A 计划必须原文引用（ADR-0046 §已知边界，不得表述为「已解决」）**：
　　停用后**在手 access token 仍可用至多 30 分钟**（无状态，不查库）。这是本项明确接受的
　　吊销粒度，**不是缺陷**。若业务要求秒级失效，唯一出路是把 access token 改为**有状态**
　　（每次校验查库）—— 属独立裁决。
　　🚫 **不接受「加个内存黑名单」** —— 与 ADR-0048 §⑤ 是同一个 concept：把必须跨进程
　　共享的状态放进单进程内存（参见 TODO-047：`advisory_lock` 用进程内 `hash()` 做锁键，
　　多 worker 下静默失效、失败无声）。内存名单不共享、重启即丢 —— 只是换一个更安静的坑。
验收：AD 同步端到端跑通；停用用户 refresh 立即 401；历史数据外键不断裂。

3.2.3 横切观测层
编号	内容	依据
P9A-OBS-001	workflow_progress 表：8 字段 + 5 态枚举（PENDING/IN_PROGRESS/COMPLETED/SKIPPED/FAILED）	SUP-008 V1.1 §2.6
　　⚠️ **依据栏的引用是错的（2026-10-20 勘误）**：SUP-008 §2.6 实为「2.6 新模块：反应器计算」，
　　§3.2.6 是「新增 reactor_results 表」—— **8 字段的定义在 SUP-008 里根本不存在**。
　　而 SUP-008 §8.5 另有一个**同名**的 `workflow_progress`（14 字段的「项目作业流程
　　进度百分比表」，Excel Sheet 2 导入用），与本条的签署步骤观测表**领域不同**。
　　⇒ 本条取的是观测表；§8.5 那张未落地，将来要建须另起表名。见 `TODOS.md` TODO-052。
　　⚠️ **实现偏离（2026-10-20，P9A-2 B0 落地）**：实际表为 **10 业务字段** +
　　`progress_id` 主键 + TimestampMixin 三列。多出 2 列是被 P9A 自己的需求强制的：
　　`workflow_type`（读 API 的 URL 段 + 三个写入点的区分依据）与 `project_id`
　　（`workflow_id` 多态、无法 join 回项目，而读 API 要按项目鉴权）。
　　另有 2 处改名：`step_no`→`step_order`、`step_name`→`step_role`
　　（与 `SignatureMatrix.steps_json` 的键逐字一致）。**本行的「8 字段」保留为原始设计，
　　不是要回改的实现目标**；偏差见 `TODOS.md` TODO-053。
P9A-OBS-002	写入层：签署 / 变更单 / 代录批准状态变更时**同步写**，且写入点必须在 **service 层**	ADR-0047
	　　⚠️ **不得写在 `app/api/v1/*` 路由处理函数里**（ADR-0047 §① 🔒）。实测依据：
	　　`StateMachineService.transition()` 今天有 4 条入口，其中 `cia_engine.py:85`
	　　（`cia_mark_stale` 事件处理者）由 **`app/workers/cia_tasks.py` 的 ARQ cron**
	　	（1 分钟增量 / 5 分钟全量 CIA 扫描）驱动，**完全不经过 API 层**。
	　　⇒ 写在 API 层会让**所有 cron 驱动的状态变更在观测层里系统性隐形**，
	　　且不报错、不告警 —— 观测层看起来是通的，只是漏掉了最需要观测的部分。
P9A-OBS-003	读 API：供前端甘特图/进度条/超时告警消费	SUP-008 §8.3.5
P9A-OBS-004	500ms 延迟验证：流程状态变更到持久化 ≤ 500ms	P9-OPEN-007 验收标准
	　　📌 通知的同步/异步**不由本节裁决**（ADR-0049 §① 明确未锁，本版无邮件服务器）。
	　　若 P9A 最终把**通知发送**也做成异步，会出现「workflow_progress 已写 COMPLETED
	　　但通知尚未入队/发送」的窗口 —— **这是已知行为不是错误**，但排障时不得反过来
	　　当成观测层不可信。已确定属 ARQ 范围的只有**通知 30 天清理任务**（P9A-NOT-004）。
验收：workflow_progress 在三条工作流上均有写入；延迟达标。

3.2.4 通知 / 待办后端
编号	内容	依据
P9A-NOT-001	**notifications 建表**（按 ADR-0049 §①）	新增（P0 清单无）
	　　📌 **通道抽象的最小接口已定**（ADR-0049 §①，勿自创签名）：
	　　`async def deliver(self, payload: NotificationPayload) -> DeliveryResult`
	　　- 入参是 **frozen dataclass DTO，不是 ORM**，**不传 `recipient: User`**
	　	（收件人已在 `payload.recipient_id`；传 ORM 会让通道耦合会话，将来接邮件多一个失败面）
	　　- **只有一个方法**，不预定义 `can_deliver` / `on_failure` / 批量接口 ——
			预先猜测下一版需求就是空壳的另一种写法
	　　- `DeliveryResult(delivered: bool, reason: str | None)`：**本版恒 `delivered=True`**。
			字段存在是为了让将来的邮件通道有地方报告 SMTP 拒收；没有它，接邮件的人第一反应
			就是在 service 里加 `try/except` —— 那正是 ADR-0049 §① 禁止的「临时 if」
	　　- 🚫 **不写 `EmailChannel` 空壳**；🚫 **不得 `if 走邮件: ...`**
	　　⚠️ **`InAppChannel.deliver()` 只写 `notifications` 行，不推 WebSocket**（通道不该知道
	　　WebSocket 存在）。**但推送的接线义务在本版** —— P9-OPEN-006 已把 WebSocket 定为
	　　通知的**关键路径**，而 WebSocket 是服务端推送，服务端不推就没有它。
	　　⇒ 写侧在 `deliver()` 成功后须通知进程内 broadcaster 向该 `recipient_id` 的连接推送。
	　　**「登录时轮询能看到」只是降级路径，不等于推送已实现。**
	　　P9A 验收：① `deliver()` 写入 notifications 行；② WebSocket 在连接建立时可用。
	　　**不要求**「离线用户在断线期间收到推送」—— 那是产品上线门禁，不占 P9A 验收。
P9A-NOT-002	**按 ADR-0049 走实时计算，不建表** —— 从 `SignatureMatrix.steps_json` 当前步骤
		的 `sign_role` × 当前用户角色重算	新增（P0 清单无）
		⚠️ 待办查询需先按「当前用户有权的 project」缩小集合；`deliverables` 现有索引里
		没有按用户/角色的索引，P9A 需确认 `user_projects` 侧有可用索引，否则 500ms 达不到
P9A-NOT-003	GET /todos / GET /notifications / PUT /notifications/{id}/read	P9 SPEC §3.1.2
P9A-NOT-004	通知保留 30 天清理：ARQ 任务 + 失败路径覆盖（补 TODO-016 缺口）	P9 SPEC §3.2.1（7）
P9A-NOT-005	通知实时推送：`WS /ws/notifications` + **Redis pub/sub 跨进程广播**	ADR-0049 §⑤、P9-OPEN-006
	　　⚠️ **必须跨进程**：进程内 broadcaster 在多 worker 下会让连接到 A 的用户收不到 B
	　　产生的通知，**且不报错** —— 与 TODO-047 同形状（dev 单进程会掩盖它）。
	　　禁止用「文档限制单进程部署」替代跨进程正确性。
	　　四条硬约束：① **pub/sub 不持久化**，断线期间的消息由 `notifications` 表兜底，
	　　重连走 `GET /notifications?after=<last_seen>`；**不得**把「WS 推送成功」当作
	　　「通知已送达」；② 降级须可观测（见 P9A-NOT-006）+ 前端切轮询；
	　　③ **订阅端独立连接**（订阅会阻塞，不能与 ARQ 的 BLPOP 共用）；
	　　④ channel 按 `recipient_id` 分（`ws:notify:{user_id}`）；连接数 >5000 再考虑分片。
P9A-NOT-006	**`/health` 响应扩展 `realtime` / `realtime_reason` 字段**（**不是**新增健康端点）	ADR-0049 §⑥
	　　`realtime`: ok / degraded；`realtime_reason`: redis_unavailable / redis_timeout /
	　　pubsub_error / null。**三条硬约束**：
	　　① 检测**不得阻塞 `/health` 主路径** —— 读 broadcaster 维护的状态标志，零额外探测
	　		（`/health` 现在已同步 `check_database_async()` 且无显式超时，不能再叠第二个依赖）；
	　　② **状态码语义不变**，degraded 时仍 200；`realtime` 仅供观测，**不得用于 liveness/readiness 判定**
				（否则 Redis 挂了会触发服务重启循环）；
	　　③ `realtime_reason` **必须是枚举**，不是自由字符串。
	　　📌 语义：`realtime` 检测的是 **pub/sub 可达性**，不是 Redis 整体健康 ——当前等价，但只承诺「WS 推送能力」。
P9A-NOT-005	待办生成器：签署任务 / 退回通知 / 变更报警 / 系统公告 四类型	P9 SPEC §3.2.1（7）
验收：待办列表 ≤500ms；通知列表 ≤500ms；清理任务有失败注入测试。

3.2.5 编辑锁后端
编号	内容	依据
P9A-LCK-001	锁存储（按 ADR-C：DB 或 Redis）	ADR-C
P9A-LCK-002	acquire / release / status 三端点	P9 SPEC §3.1.2
P9A-LCK-003	自动续期：前端心跳 + 后端续期接口	P9 SPEC §2.5
P9A-LCK-004	超时清理：30 分钟过期	P9 SPEC §2.5
P9A-LCK-005	降级策略：Redis 不可用时（若选 Redis）	ADR-0048
　　⚠️ ADR-0048 §⑥/§⑦ 增加四项 SPEC 原条目里没有的工作，**不写进排期会掉**：
　　(a) 编辑保存路径的 `expected_hash` / `expected_updated_at` 比对 —— `records.py` 现无 PUT/PATCH，该路径 P9A 全新建
　　(b) `RECORD_EDIT_CONFLICT` 409 响应 schema（受 P9A-DLV-010 零裸字段约束，`basis` 三值）
　　(c) `RECORD_EDIT_OVERWROTE_STALE_BASELINE` 审计 action 枚举
　　(d) **兜底令牌按表而异**：29 张 `*_result(s)` 表中 19 张有 `record_hash`（零迁移），
　　　但 `sim_*`(8) / `util_results` / `cost_est_results` 无 `record_hash`，`two_phase_results` 无 `updated_at`
　　　🔻 **已裁决收窄为 1 张**（ADR-0048 §⑥ 收窄表）：这 11 张里只有 `cost_est_results`
　　　**真的需要补** —— 它是唯一「可编辑（PATCH /results/{id}，**无 sign_status 门禁**）
　　　∧ 无任何并发令牌」的表。`util_results` / `sim_*`(8) / `two_phase_results`
　　　**无手动编辑端点**，不需要兜底。
　　　**不引入 `row_version`**（会在 record_hash 之外叠第二套令牌，实施者每次都要
　　　判断用哪个 ⇒ bug-180~191 词表分叉的同构问题）。补 `cost_est_results.record_hash`
　　　是**补兜底**不是补漏 —— `RECORD_TYPE_REGISTRY` 与「必须有 hash 列」无代码关系
　　	（finalize 靠鸭子类型，从不查注册表）。
　　　⚠️ 触发条件：若 P9B 新增 SIM 结果编辑入口 ⇒ 结论失效，回 ADR-0048 修订
　　⚠️ **ADR-0048 §⑤「拦住并发的是 DB」只对这 19 张成立。** Redis 降级后另外 11 张
　　　**没有 DB 兜底**，每次编辑保存都落 `no_baseline`。⇒ P9B 的降级横幅**不能**是
　　　全局一句话：对这 11 张表的记录须额外提示「**本次编辑无冲突检测**」。
　　　用户必须在无保护状态下知道自己在无保护状态下编辑。
　　✅ **已裁决：每次编辑保存写一条 `audit_logs`**（action = `RECORD_EDITED`），
　　　`changed_by` / `changed_at` 从本次编辑对应的那条取。理由：字段级 diff 要求
　　　`detail_json` 有 schema（零裸字段约束），而实测**编辑保存路径今天不写任何 diff**
　　	（`change_diff_json` 只在计算收口 / CIA 写），`record_hash` 是哈希无法事后 diff
　　　⇒ 主路径上非写不可；一次 audit 同时给「谁」+「改了哪」。
　　　三条约束：① 只取本次编辑对应的那条，**不得**用最近一条 audit 泛匹配凑
　　	（会把冲突归因给错误的人）；② **不得**用 `updated_at` 冒充 `changed_at`；
　　	③ `detail_json` 字段级摘要**必须有显式 schema**。
　　　⚠️ **随之产生的新欠账**：`audit_logs` 保留期未裁决（P9-OPEN-003 只定导出格式），
　　　而写侧增速现取决于编辑频率 ⇒ P9A 须一并提保留期方案。
验收：并发编辑场景下锁正确；过期自动释放；与状态机事务无死锁。

3.2.6 变更影响确认分流（若 P1 未交付）
✅ 已核实（2026-10-19，见 `docs/PCS-NOTE-P9-Prep-P1端点交付面清单-2026-10-19.md`）：
`POST /change-impact/.../confirm` **不存在**；实际存在的 `confirm-recalc`
**不含**哈希判定分流 ⇒ **本节两项均归 P9A**：

编号	内容
P9A-CIA-001	哈希判定分流：结果不变 → STALE_RESOLVED_NO_CHANGE（免凭证）；结果变化 → CHANGE_PENDING
P9A-CIA-002	manual-adjust 端点
3.3 P9A 交付物
交付物子系统全套 service + API + 迁移

users 表启用 + AD 同步 + token_version

workflow_progress 写入层 + 读 API

notifications / todos 表 + API + 清理任务

编辑锁后端

（条件）CIA confirm 分流

OpenAPI 契约冻结（供 P9B 生成前端 type）

周期：4–6 周（1–2 人）
阻塞下游：P9B 全部

第四部分：P9B 前端（原 P9 修订，3–4 周）
本节大部分沿用 V1.3 §3.2.1–§3.2.5，修订处已标注。核心修订：所有对"后端已交付"的假设改为"消费 P9A 冻结的 OpenAPI"。

4.1 关键修订
V1.3 表述	V2.0 修订
§1.2 "依赖 P1 后端状态机、变更影响引擎、版本管理 API 已可用"	删除。改为"依赖 P9A 交付并冻结的 OpenAPI"
§2.6 "依赖 P1：后端状态机、变更影响分析引擎、版本管理 API 已可用"	重写为"依赖 P9A 全部交付物 + OpenAPI 冻结"
§3.2.1（1）"前端根据当前状态和用户角色，调用 GET /records/{id}/actions"	保持，但明确该端点归属（P1 或 P9A，按 P9-Prep 核实结果）
全文对 /deliverables/* 端点的调用	保持，明确归属 P9A
§3.2.1（5b）代录客户批准	保持，依赖 P9A-DLV-008
§3.2.2 变更影响前端"确认并重新计算"	保持，依赖 P9A-CIA-001（已核实归 P9A，见 §2.2.3）
4.2 前端开发纪律（新增）
强制约束（吸取 TODO-039/041 逾期教训）：

前端 type 从 ./api 生成，禁止手写 mock type。7 个 mock type 文件（pipeClass/flash/pipe/pump/pipeNet/pms/common）改 import 自 ./api，这是 TODO-039 的要求，P9B 开工前必须先清完。

MSW handlers 按 OpenAPI 重写，禁止按前端 mock types 写（TODO-041）。

P9B 开工前提 = P9A OpenAPI 契约冻结。契约未冻结不允许前端动工，避免对着 mock 绿、上线 404。

**契约冻结的验收包含一条硬指标：P9A 新增端点的响应 schema 零裸字段**（P9A-DLV-010）。
只「冻结」不够 —— 冻结一份满是 `object` 的契约等于把 unknown 合法化。开工前用
`scripts/check_openapi_payload_coverage.py` 确认裸字段数仍为 71（未因 P9A 上涨）。

⚠️ 本节「7 个 mock type 文件改 import 自 ./api」的前提，本会话已查明**不成立**：
28/31 个导出 interface 在 OpenAPI 里无对应 schema，且前后端字段名不同、单位不同
（`p_mpa` ↔ `P_Pa`）。P9B 开工前须按 TODOS.md 的重定范围重新评估，不要照原文执行。

4.3 任务分解
沿用 V1.3 §3.2.1–§3.2.5，工作量不变：

模块	工作量
签署流程前端（操作栏、批注、状态时间线、待办、通知中心）	2–2.5 人周
变更影响分析前端（高亮、对比、确认）	1–1.5 人周
ADMIN 用户管理前端	1–1.5 人周
ADMIN 审计日志前端	0.5–1 人周
ADMIN 系统参数前端	0.5 人周
并发控制前端	0.5 人周
新增：workflow_progress 甘特图/进度条组件	0.5 人周
新增：物流手动创建向导 + 校对 UI（V1.2 ADR-0019/0022）	1–1.5 人周
合计	7.5–10 人周
注：V1.3 §4.4 的 5.5–7.5 人周未含 workflow_progress 组件与物流手动创建向导，V2.0 补入。

4.4 P9B 交付物
签署流程前端全套

变更影响前端

ADMIN 前端全套

并发控制前端

workflow_progress 可视化组件

物流手动创建向导 + 校对 UI

周期：3–4 周（1–2 人）
依赖：P9A OpenAPI 冻结 + TODO-039/041 清完

第五部分：修订后的数据模型需求（全新增）
5.1 P9 涉及的表
表	来源	状态
users	P0 清单有，但真库 0 行、无代码写入	P9A 启用
audit_logs	P0 已交付	复用；P9 补签署/变更/代录 action 枚举
system_settings	P0 已交付	复用
data_lineage	P1 已交付	复用
workspaces	P1 已交付	复用
notifications	P0 清单无	P9A 新建
todos	P0 清单无	**不建表**，按 ADR-0049 实时计算
workflow_progress	P0 清单无	P9A 新建
deliverables / deliverable_versions / ...（P1 5 张表）	P1 ORM 骨架存在，无 service	P9A 补 service
5.2 迁移纪律
新表迁移必含 created_by / created_at（timezone+server_default）/ updated_at（nullable）——TimestampMixin 三列纪律

所有 drop_table 在 downgrade() 且带 if_exists guard

迁移写完后跑 alembic check，退出码 255 视为漂移

第六部分：修订后的工作量与周期
6.1 工作量对比
阶段	V1.3 估算	V2.0 估算	差异原因
P9-Prep	无	2 人周	全新增：P7 欠账 + 4 ADR + 端点核实 + MFA
P9A	无	8–12 人周	全新增：交付物子系统 + 身份改造 + 观测层 + 通知 + 编辑锁
P9B	5.5–7.5 人周	7.5–10 人周	+workflow_progress 组件 +物流向导
合计	5.5–7.5	17.5–24 人周	V1.3 漏算整个后端
6.2 周期对比
阶段	V1.3	V2.0
P9-Prep	—	2 周
P9A	—	4–6 周
P9B	3 周	3–4 周
合计	3 周（第 23–25 周）	9–12 周（第 23–35 周）
6.3 压缩路径（若资源允许）
2 人并行：P9A 可压至 3–4 周（交付物子系统与身份改造可拆两人）

P9B 与 P9A 后半段可部分重叠（仅限非依赖端点）

极限压缩：P9-Prep 2 + P9A 3 + P9B 3 = 8 周（需 2 人满投入）

第七部分：修订后的依赖与里程碑
7.1 依赖图（修订）
text
P7 收口
  └─► P9-Prep（清账 + ADR + 核实）
        └─► P9A（后端）
              └─► P9B（前端）
                    └─► P10
关键变更：

P9 依赖从 P1, P7 改为 P7 收口 + P9-Prep

P1 不再作为 P9 的前置——P1 未交付的交付物后端由 P9A 承担

7.2 里程碑验收（修订）
里程碑	V1.3 验收标准	V2.0 验收标准
P9-Prep 完成	（无）	bug-144 修复；alembic check ≤5；4 份 ADR accepted；《P1 实际交付面清单》完成；MFA 决议
P9A 完成	（无）	交付物全套端点可用；AD 同步端到端跑通；停用用户 refresh 立即 401；workflow_progress 三工作流写入 + 500ms 达标；待办/通知 ≤500ms；编辑锁并发正确；OpenAPI 冻结
P9B 完成	签署流程完整走通、变更影响分析正确触发	同左，加：前端 type 全部 from './api'；MSW handlers 按 OpenAPI；workflow_progress 甘特图可用；物流手动创建向导可用
P9 整体完成	（原标准）	P9-Prep + P9A + P9B 三段验收全过

### 7.2.1 P9A 验收状态（2026-10-21 Z 收口实测）

⚠️ **本表是「实测状态」，不是「验收标准」** —— 标准在 §7.2 原表（不改）。
状态取值只有三档：**通过** / **代码就绪，待运维账号** / **部分（记明缺哪一项）**。
⚠️ **不得**把「代码就绪」记成「通过」（与 TODO-045「本地有、部署无」同族）；
⚠️ **不得**把「部分」记成「已写入」，也**不得**记成「不适用」。

| §7.2 验收标准 | 状态 | 证据 |
|---|---|---|
| 交付物全套端点可用 | **通过** | OpenAPI 冻结件含 deliverables 6 端点（issue / sign-step / customer-approval/proxy / versions / snapshot / actions）+ records 9 端点；测试见 `tests/api/v1/test_deliverable_sign_step.py` 等。**2026-10-26 追加**：变更单闭环 3 端点（initiate-change / apply-change / change-notice）+ 签署矩阵管理面 6 端点（`tests/api/v1/test_change_notice_api.py` / `test_signature_matrix_api.py`）。**2026-10-26 再追加**：变更单**作废**端点（`POST /records/{module}/{record_id}/change-notice/cancel`，理由必填）⇒ 变更单闭环共 **4** 端点|
| AD 同步端到端跑通 | **代码就绪，待运维账号** | `POST /admin/users/sync` 已发布；服务账号（`LDAP_BIND_DN` / `LDAP_BIND_PASSWORD` / `LDAP_USER_FILTER` / `LDAP_USER_ATTRS`）到位前端点返 503、每日 cron 记一条 WARN 后 no-op ⇒ **端到端验收不可演示，不得标「通过」** |
| 停用用户 refresh 立即 401 | **通过** | `tests/api/v1/test_admin_users.py::test_disabled_user_refresh_returns_401`（含登录建行 → 可见 → 停用 → refresh 401 的完整验收链） |
| workflow_progress 三工作流写入 | **通过（3/3）** | SIGN ✅ / CUSTOMER_APPROVAL_PROXY ✅ / **CHANGE_NOTICE ✅（2026-10-26 落地）** —— `change_notice_service.create_change_notice` 不再 `raise NotImplementedError`：建单写 **PENDING**（写入点 2a）、**签完最后一步**（`sign_step` 置 APPROVED）写 **COMPLETED**（写入点 2b，即 `close_on_approved`），`workflow_id` = **变更单自己的 deliverable_id**（不是版本 id）。守卫：`tests/services/test_change_notice_observation.py`（4 例，含「观测写失败 ⇒ 建单整体回滚」的同事务断言）。⚠️ 口径：**CHANGE_NOTICE 工作流只写 1 行**（`step_order=1`）—— 变更单的签署步骤已由 SIGN 工作流观测，再写一份就是同一事实的两个来源。✅ **HTTP 入口已补**（2026-10-26 P9A-DLV-011 落地，TODO-068 闭环）：`POST /records/{module}/{id}/initiate-change` / `/apply-change` / `/change-notice` ⇒ 「用户可达」达成（SPEC §7.2 的验收标准是**写入**，非「界面可发起」） |
| workflow_progress ≤500ms | **通过** | `tests/services/test_workflow_progress_acceptance.py::test_observed_p99_under_500ms` —— 三类工作流**逐类**实测 p99（**2026-10-21 修了参数化**：原实现把 `WorkflowType.SIGN` 写死在写入与查询两处 ⇒ 三个用例其实只跑了一类） |
| 待办 ≤500ms | **通过** | `tests/api/v1/test_todos.py::test_todo_sql_and_parse_both_within_budget`（300 个待签交付物，分段计时） |
| 通知 ≤500ms | **通过（本轮才补上的验收）** | `tests/api/v1/test_notification_list_budget.py`（表内 2800 行 / 目标收件人 800 条 / 未读 300；含 `?after=` 断线补齐路径）。⚠️ **收口前全仓无任何通知性能断言** —— 标准写了、代码实现了，但没人证明达标 |
| 编辑锁并发正确 | **通过** | `tests/api/v1/test_edit_lock_api.py`（锁三端点 + 降级放行）+ `tests/api/v1/test_edit_acl_order.py`（bug-2039 鉴权顺序） |
| OpenAPI 冻结 | **通过** | baseline 滚动至 `p9_008` 终态（**2026-10-26 P9A-DLV-011 后**：239→**246 path（+7）** / 334→**346 schema（+12）** / 0 删除；`p9_007` 时为 +60/+105）。**2026-10-26 再更新**（TODO-080 + TODO-087 批）：**247 path** / **348 schema**（+1 path = 变更单作废端点；+1 schema = `ChangeNoticeCancelResponse`；+1 schema = `ChangeActionRequest`；**0 删除**）⇒ `openapi.json` / baseline / 前端 snapshot + `api.d.ts` 已重新生成并滚 baseline；裸字段仍 **71**（基线未降 —— 71 是既有欠账，不是本轮成果） |

**收口时的门禁实测（2026-10-21）**

| 门禁 | 结果 |
|---|---|
| `alembic check`（开发库 `pcs`） | exit 0，无漂移；`current` = `p9_008` = `heads`（**先核对 revision 真的变了**，再信 check 的结论） |
| `alembic check`（`pcs_test`） | 同上，exit 0（**每个库各跑一次** —— 只在一个库上 exit 0 推不出另一个库也干净） |
| `check_openapi_payload_coverage.py` | exit 0，裸字段 **71**（未升未降） |
| `gate_08_openapi_contract.sh --check-baseline` | exit 0（冻结后） |
| 后端 `pytest -q` | **5155 passed / 77 skipped / 0 failed**（P9A-4 D lane 收口时 5102，本轮 +53） |
| 前端 `typecheck` / `lint` / `test` | exit 0 / exit 0 / **716 passed** |

**本轮（P9A Z 收口）补的三件事** —— 都不是「优化」，是**验收标准缺证据**：

1. **通知 ≤500ms 的自动化验收**（§7.2 写着，代码实现了，**没人证明**）。
   ⇒ 新增 `tests/api/v1/test_notification_list_budget.py`（列表 + 未读计数 + `?after=` 补齐）。
   ⚠️ 造到 **2800 行**再测 —— 小表下测不出真实性能，500ms 是假达标（同 `test_todos.py` 头注）。
2. **一个装饰性的参数化** —— `test_observed_p99_under_500ms` 的
   `@parametrize("workflow_type", [SIGN, CHANGE_NOTICE, CUSTOMER_APPROVAL_PROXY])`
   下面，`_write_then_read` 把 `WorkflowType.SIGN` **写死在写入与查询两处**
   ⇒ 三个用例**测的都是 SIGN**，而用例名与 docstring 都说「三类工作流逐类」。
   ⇒ 已修（`workflow_type` 传进写入与查询）。**注释与代码字面冲突，是 bug 的气味。**
3. **SPEC 欠账补写** —— ADR-0047 §后果 与 ADR-0049 §⑥ 承诺要写进 UI-SPEC 的
   `P9A-OBS-001~004` / `P9A-NOT-001~006` 十条**至今 0 命中**
   ⇒ 已写进 `docs/PCS-UI-SPEC.md` **V2.1**（§6.22 TodoPanel / §6.23 RealtimeStatus /
   §6.24 WorkflowProgressPanel + §6.20 扩写）。

**仍未闭环（不占 P9A 验收，但必须跟着走）**

- **P9A-DLV-007**：✅ **已于 2026-10-26 落地**（`SignatureMatrixService` +
  `create_change_notice` + 两个观测写入点）⇒ workflow_progress 三工作流
  **3/3**（TODO-057 已闭环）。⚠️ 遗留（2026-10-26 更新）：变更单**无 HTTP 入口**
  ⇒ **已闭环**（TODO-068，P9A-DLV-011）；矩阵**无管理面** ⇒ **已闭环**
  （TODO-070，同批）⇒ 本条仅剩：「一条记录一张变更单」的业务约束待 SPEC 确认
  （TODO-069）。
- **ADR-0050 P1~P6**：签署职责与任务参与（`users.token_version` 之外的整条签署门禁
  线）**用户 2026-10-20 裁决「先不做」** ⇒ 不实施；再开工按 P1~P6（P1 纯增量）。
- **P9B（前端）**：本轮**未做**。`docs/PCS-UI-SPEC.md` §6.21 / §6.7.1 的前端
  兑现（编辑锁 UI / 409 弹窗 / CIA 确认）与本轮补写的 §6.22~§6.24 都归
  `docs/PCS-PLAN-P9B-1-结果记录页与编辑锁.md`。
  ⚠️ 收口前实测发现**前端 `NotificationCenter` 组件的 props 与契约已漂移**
  （自造 `category` / `summary` / `issued_at` / `unread`，而契约是
  `kind` / `title` / `body` / `created_at` / `read_at`）⇒ 归 P9B-1 处理。

第八部分：待确定问题（修订）
编号	问题	V1.3 状态	V2.0 状态	归属
P9-OPEN-001	MFA 实现方式	已裁决（路径 B，2026-10-19）：AD 密码二次输入 + `SIGN_2FA_FALLBACK` 强制审计；mock 会话豁免（限登录层）	硬阻塞 → `docs/PCS-NOTE-P9-Prep-MFA决议-2026-10-19.md`	~~P9-Prep~~ 已关闭
P9-OPEN-002	通知邮件服务器	已裁决（2026-10-19）：**本版不设邮件服务器**，仅站内信；预留 `NotificationChannel` 抽象，**不写 EmailChannel 空壳**	ADR-0049 §①	~~P9-Prep~~ 已关闭
P9-OPEN-003	审计日志导出格式	已确认	保持	P9B
P9-OPEN-004	用户同步定时频率	已裁决（每日凌晨，2026-10-19）	沿用 SPEC 倾向，无新增依据	~~P9-Prep~~ 已关闭
P9-OPEN-005	批注 @提及	已确认（不支持）	保持	—
P9-OPEN-006	通知 WebSocket vs 轮询	已裁决（WebSocket + 降级轮询，2026-10-19）；邮件移除后实时推送为通知唯一及时性来源 ⇒ **关键路径**，降级状态必须可观测	ADR-0049 §后果	~~P9-Prep~~ 已关闭
P9-OPEN-007	workflow_progress	已裁决：ADR-0047 accepted（2026-10-19），同步写 + 同事务 + 调用方写	升级为 P9A-OBS-001~004	P9A（ADR 侧已关闭）
P9-OPEN-008	用户身份模型迁移	已裁决：ADR-0046 accepted（2026-10-19）	ADR-A → `docs/adr/0046-user-identity-model-migration.md`	~~P9-Prep~~ 已关闭
P9-OPEN-009	编辑锁存储方案	已裁决：ADR-0048 accepted（2026-10-19），Redis + 30min TTL + DB record_hash 兜底	ADR-C → `docs/adr/0048-edit-lock-storage.md`	~~P9-Prep~~ 已关闭
P9-OPEN-010	通知/待办表 vs 实时计算	已裁决：ADR-0049 accepted（2026-10-19），通知建表 / 待办实时计算	ADR-D → `docs/adr/0049-notification-and-todo-data-model.md`	~~P9-Prep~~ 已关闭
P9-OPEN-011	fk_utility_energy_summary ondelete CASCADE vs RESTRICT	（无）	**已裁决：CASCADE**（`fd0e8b9`）	~~P9-Prep~~ 已关闭
第九部分：修订后对开发计划文档的同步要求
目标文件：`spec/工艺专用综合计算软件需求规格说明书 Web版开发计划.md`
（⚠️ 不在 `docs/` 下 —— 2026-10-19 实测。写 `docs/Web版开发计划.md` 会找不到文件）

✅ **已于 2026-10-19 全部同步完成**：

P9 章节：

周期：第 23–25 周 → 第 23–35 周（P9-Prep 23–24 / P9A 25–30 / P9B 31–35）

核心产出：签署流程、变更影响分析、ADMIN → P9-Prep（清账+ADR）、P9A（后端交付物+身份+观测层）、P9B（前端交互）

依赖：P1, P7 → P7 收口 + P9-Prep ADR

模块依赖图：P8 → P9 之间的箭头改为 P8 → P9-Prep → P9A → P9B → P10

里程碑验收标准表：P9 行拆为 P9-Prep / P9A / P9B 三行

未解决问题章节：新增「P9 后端交付物子系统实际未由 P1 交付」说明
　　✅ 已写入 Web开发计划 §P9 的「目标」段，注明 P1 只交付状态机骨架 + deliverables 读面，
　　9 个 records 工作流端点 / 4 个 deliverables 写端点 / CIA 哈希判定分流均不存在，
　　并指向 `docs/PCS-NOTE-P9-Prep-P1端点交付面清单-2026-10-19.md`

版本历史（追加）
版本	日期	修改内容	编制人
V1.0	2026-08-27	初始版本	联合项目组
V1.1	2026-08-28	SUP-004/005/006/007 两层签署	联合项目组
V1.2	2026-08-29	ADR-0019/0022 物流手动创建	联合项目组
V1.3	2026-09-03	SUP-008 V1.1 workflow_progress	联合项目组
V2.0	2026-10-07	架构审查后结构性重排：拆 P9-Prep/P9A/P9B；新增后端交付物子系统规格；补 4 份 ADR 前置；补 notifications/todos/workflow_progress 三表；补 token_version 条目；MFA 升级硬阻塞；工作量 5.5–7.5 → 17.5–24 人周；周期 3 周 → 9–12 周；依赖 P1,P7 → P7 收口 + P9-Prep	架构审查
V2.1	2026-10-21	P9A Z 收口（**纯追加，不改任何绑定正文**）：①新增 **§7.2.1 P9A 验收状态**（实测状态表 + 门禁实测 + 「本轮补的三件事」+「仍未闭环」）—— ⚠️ §7.2 原表**不改**：验收标准是绑定权威，改它要重走 §7.2 验收；状态表的取值只有「通过 / 代码就绪待运维账号 / 部分（记明缺哪一项）」三档，**不得**把「代码就绪」记成「通过」、**不得**把「部分」记成「已写入」或「不适用」；②**TODO-053 偏离的处置在此登记**：§3.2.3 `P9A-OBS-001` 的「8 字段」**保留原文不改**（它是原始设计，不是实现目标），实际 10 业务列 + 2 处改名以**行下注记 + ADR-0047 §后果**双重登记；③补记 ADR-0047 §后果 / ADR-0049 §⑥ 承诺的 `P9A-OBS-001~004` / `P9A-NOT-001~006` 十条前端条款已写进 `docs/PCS-UI-SPEC.md` **V2.1**（§6.22 / §6.23 / §6.24 + §6.20 扩写）；④OpenAPI baseline 滚动至 `p9_007` 终态（+60 path / +105 schema / 0 删除），裸字段仍 71	Claude Code
V2.2	2026-10-26	P9A-DLV-007 + TODO-057 落地（**纯追加 + 状态更新，不改绑定正文**）：①§3.2.1 `P9A-DLV-007` 行补落地登记与**实现偏离**（矩阵步骤推进/角色判定早于 B2 落地，本项真正补的是「矩阵从哪来」+ 解析收敛；不含抽 `sign_step` 的角色判定）；②`P9A-DLV-009`（bug-145）标记**真正修复**（假 DB 用例已改真库）；③§7.2.1「workflow_progress 三工作流写入」由 **部分（2/3）** 改为 **通过（3/3）**，并写明口径「CHANGE_NOTICE 工作流只写 1 行」与遗留「无 HTTP 入口」；④「仍未闭环」段同步更新 —— ⚠️ §7.2 原表**不改**（验收标准是绑定权威）	PCS
V2.3	2026-10-26	P9A-DLV-011 落地（**纯追加 + 状态更新，不改绑定正文**）：①§3.2.1 新增 `P9A-DLV-011` 行（变更单闭环 HTTP 面 + 签署矩阵管理面）并写明 4 条**实现偏离**（binding 关联 / doc_no / 权限分层口径 / 一记录一单待确认）；②§7.2.1「交付物全套端点可用」补 2026-10-26 追加的 9 个端点证据；③`TODOS.md` TODO-068~072 **闭环**，新增 TODO-073~080（编号可读性 / 矩阵名唯一 / `change_resolved_by` 语义 / 工作区门禁 / apply-change 不校验 hash / 多记录变更 / 矩阵管理前端 / 评审 3 条 deferred minor）	PCS
V2.4	2026-10-26	P9A-DLV-011 **评审修复批**（**纯追加 + 状态更新，不改绑定正文**）：①§3.2.1 `P9A-DLV-011` 行的实现偏离③补「项目内角色不能是 VIEWER」（评审 I-5：「有项目授权」≠「有权决定谁该签」）；②§7.2.1「OpenAPI 冻结」行与「alembic check」行的计数/revision 更新到实测值（`p9_008` / 246 path / 346 schema）；③§7.2.1「workflow_progress 三工作流写入」行的遗留「无 HTTP 入口（TODO-068）」已闭环 ⇒ 同步更新	PCS
V2.5	2026-10-26	P9A-DLV-011 **收尾两处裁决**（**纯追加 + 状态更新，不改绑定正文**）：①**矩阵绑定权限**按用户裁决「**只有项目负责人能绑**」落成三层判定（全局角色 + 项目授权 + 项目内角色 `PROJECT_LEAD`）—— 新增 `PROJECT_LEAD` 项目内角色（无 DB CHECK 约束 ⇒ **不需要迁移**）；②**ADR-0002 与 ADR-0008 在「变更单驳回」上的矛盾**经裁决消解：**ADR-0008 管辖**（驳回的是「单据」，记录**保持 CHANGED**），ADR-0002 那半句被取代；「重改」的落地路径 = **撤销 → 重来**（request-reversal → approve-reversal 恢复快照 → CHECKED → 再 initiate-change），已由 `tests/api/v1/test_change_notice_api.py::test_rejected_notice_can_be_reworked_via_reversal` 钉住	PCS
V2.6	2026-10-26	**TODO-086 落地**（**纯追加 + 状态更新，不改绑定正文**）：①变更单的**绑定哈希**在**重新 `apply-change`** 时刷新 —— `ChangeNoticeService.refresh_open_bindings` 把该记录名下**未关闭**（`sign_status != APPROVED`）的变更单绑定刷成 `record_hash` = 记录当前哈希、`old_record_hash_before_change` = **本次** BEFORE_CHANGE 快照哈希（与建单同一口径）⇒ 关闭凭证说的**就是**被关的那条数据；⚠️ **只刷未关闭的**（已 APPROVED 的绑定描述的是那一轮 ⇒ 改它 = 篡改历史）；②新增 `AuditAction.CHANGE_NOTICE_BINDING_REFRESHED`（`String(50)` 列 ⇒ 零迁移）；③**顺带登记 TODO-087**：撤销批准**不恢复**记录数据与哈希（`RecordChangeSnapshot.data_snapshot_json` **恒为 `{}`** ⇒ 恢复循环空转 ⇒「撤销」只回状态不回数据），有 xfail 用例钉着	PCS
V2.7	2026-10-26	**TODO-084 全部落地**（**纯追加 + 状态更新，不改绑定正文**）：①变更单响应的 `sign_status` 改为读**交付物行里的真值**（此前端点**硬编码** `PENDING` ⇒ 建单没真推进时会骗用户「在签署中」而 sign-step 409）；②`create_change_notice` 在 **service 层**自查 `project_id` 与记录所属项目一致（否则 422 `CHANGE_NOTICE_PROJECT_MISMATCH` 且**一行都不写** —— service 是对外入口，不能只信端点传参）；③矩阵**全部非法**时待办不再**静默消失** ⇒ `todo_service` 记一条 **error** 日志（此前「这个交付物没人能签」完全不可见 ⇒ 矩阵配错了没人发现）；④变更动作（`initiate-change` / `apply-change` / `abandon-change`）的入参由 `ObsoleteRequest` 改为**专用** `ChangeActionRequest`（字段与约束**完全相同** ⇒ **纯改名**，请求体形状/校验/行为零变化）—— 此前契约里「发起变更」的入参类型名叫 `ObsoleteRequest`（那是「弃用」的请求体）⇒ 读契约的人会把「发起变更」误读成「弃用」；⑤契约影响：OpenAPI **346 → 347 schemas**（+1）、paths 不变（246）⇒ `openapi.json` / baseline / 前端 snapshot + `api.d.ts` 已重新生成并滚 baseline，裸字段仍 **71**	PCS
V2.8	2026-10-26	**TODO-077 落地**（**纯追加 + 状态更新，不改绑定正文**）：①**业务裁决** —— `apply-change`（CHANGE_PENDING → CHANGED）**要求记录真的改过**：记录的 `record_hash` 与发起变更时的 BEFORE_CHANGE 快照哈希相同 ⇒ **409 `CHANGE_NO_MODIFICATION`**（**推翻**计划 R-11 当初「不要求 hash 变化」的取舍）。理由：ADR-0002 的 CHANGE_PENDING =「**获准修改**、正在改+重校核」⇒「提交变更完成」= 有变更完成了；确实无需修改的正确动作是「**放弃变更**」；不拦 ⇒ 一条**没有实质变更**的记录被关掉而变更单里写着「管径修正」⇒ 凭证说的不是事实。②守卫是**状态机层**的业务前置（与角色/状态校验同层 ⇒ 任何调用方都躲不掉），**迁移前**判定 ⇒ 被拒时一行都没写。③⚠️ 两种「无从判断」放行：记录没有 `record_hash` 列 / 哈希为空串（物流 streams 恒为 ""）。④**已知代价**：「重新校核后确认无需修改」现在被 409 挡住（可改用「放弃变更」）—— 有意为之	PCS
V2.9	2026-10-26	**TODO-078 落地（多记录变更）**（**纯追加 + 状态更新，不改绑定正文**）：①建单请求体加 **`record_ids: list[uuid] | None`** = 本次变更影响的**全部**记录（**必须包含**路径里的 `{record_id}`，否则 422 `CHANGE_NOTICE_RECORD_SET_INVALID`；不给 = 只有路径那条 ⇒ **向后兼容**）—— 工程实践里一次管径修正常影响十几条记录；②`deliverable_record_bindings` **每条记录一行** ⇒ `close_on_approved` **批量**关（逐条校验「还在不在 CHANGED / 模型认不认识 / 记录还在不在」；任一条不合格 ⇒ **整批失败**、一条都不关 ⇒ 不做「半关半不关」）；③⚠️ **重复绑定判重改按 `binding`**（不再按 `scope_value`）—— 多记录变更单的 scope 只标识**主记录** ⇒ 次要记录在 scope 里查不到；且「未关闭」= 交付物**不是** `APPROVED`（已关过记录的那张不挡新单）⇒ 「一条记录同时只在**一张未关闭**的变更单里」；④返回值**向后兼容**（单记录时逐字不变）+ 新增 `closed_records`	PCS
V2.10	2026-10-26	**TODO-080 + TODO-087 落地**（**纯追加 + 状态更新，不改绑定正文**）：—— 两项**同一个 commit**（TODO-086 的返工用例只有快照真的装了数据才**确定性**通过 ⇒ 拆开 ⇒ 历史里留下一个 flaky commit）。**①TODO-080 第 1 条（取消路径）** —— 新端点 `POST /records/{module}/{record_id}/change-notice/cancel`（理由必填）⇒ 变更单 `sign_status = OBSOLETE`（交付物 4 态里**已有**这一态 ⇒ **不需要迁移**）+ 审计 `CHANGE_NOTICE_CANCELLED` + 观测 FAILED；⚠️ **记录不动**（保持 CHANGED）—— 作废的是「单据」不是「校核结论」⇒ 顺手关成 CHECKED = **绕过 3 级校审**；⇒ 判重口径改为「**开着** = DRAFT / PENDING」（已 APPROVED / 已 OBSOLETE 都**不挡**新单）；⚠️ `doc_no` 与 `scope_value` 改为按**变更单自己的 uuid** 派生（原先按记录派生 ⇒ 同一记录的第二张单撞唯一约束 ⇒ 500）。**②TODO-080 第 2 条（真覆盖）** —— **删除**已弃用的 `approve_change_notice`（它**绕过矩阵**且**连记录都不关**）+ 死代码 `_apply_record_resolution`；⚠️ 审批通过的通知逻辑原先只在该方法里 ⇒ **真实路径从不通知任何人** ⇒ 随删除**迁到** `close_on_approved`（通知行**同一事务**写，推送由 `sign_step` 在 commit **之后**做）；真库用例搬到 `tests/services/test_change_notice_close_real_db.py`（4 例）。**③TODO-080 第 3 条（两个 `PcsError` 变体）** —— service 变体**继承** core 变体 ⇒ `except core.PcsError` **两个都捕得到**；⚠️ `app/core/errors.py` 对 service 变体的 import 改成**惰性**（否则 core → services → core 成环 ⇒ 启动即 ImportError）；⚠️ 子类的 `code`/`status` **必须**取 `type(self).code`（写死 ⇒ 124 个既有用例的子类退化成 `PCS_ERROR`）。**④TODO-087（撤销/放弃**真的**恢复数据）** —— `RecordChangeSnapshot.data_snapshot_json` 此前**恒为 `{}`** ⇒ 撤销/放弃**只回状态不回数据**；⇒ 新模块 `app/services/record_snapshot_codec.py`：快照**装着**记录的业务数据（JSONB 装不下的 UUID / datetime / date / Decimal / Enum **打标签**），恢复时按标签**还原成真类型**；⚠️ **不**快照主键 / 归属 / 审计 / 状态机流程列（恢复它们会与当前状态打架），**但快照 `record_hash`**（它是「变更前的数据指纹」）；⚠️ 顺带修 `ReversalApprovalService._load_active_snapshot` 的 **PK 取法**（`getattr(record, "record_id", None)` ⇒ **只有部分表叫 `record_id`** ⇒ 别的表上**恒为 None** ⇒ 快照永远查不到 ⇒ 撤销**什么都不恢复**）。**⑤契约影响**：OpenAPI **246 → 247 path**（+1 = 作废端点）、**347 → 348 schema**（+1 = `ChangeNoticeCancelResponse`）⇒ `openapi.json` / baseline / 前端 snapshot + `api.d.ts` 已重新生成并滚 baseline，裸字段仍 **71**	PCS
V2.11	2026-10-27	**TODO-073 落地（变更单编号走模板）**（**纯追加 + 状态更新，不改绑定正文**）：①变更单的 `doc_no` 此前是 `CN-{32 位 uuid hex}` ⇒ 只保证**唯一**、**不可读**（用户报单号时谁都对不上）⇒ 改走**编号模板**：内置「变更单编号模板」（**幂等** + `template_name` 唯一约束兜底并发），段 = `{项目号}-{文档类型}-{序号}` ⇒ 编号渲染成 `P-1A2B3C4D-CHANGE_NOTICE-1`。②⚠️ 取号必须**在建行之前**（`uq_deliverables_doc_no` 全局唯一 ⇒ 「先建行、编号后补」⇒ 同事务第二张单撞空串约束 ⇒ 500）⇒ 为此把渲染从 `_allocate_doc_no`（吃交付物行）抽成 `DeliverableService.render_doc_no`（不依赖已存在的行），`_allocate_doc_no` 转调它（行为不变）。③变更单交付物行 ⇒ `doc_no_mode="TEMPLATE"` + `numbering_template_id` ⇒ 之后**再签发版本**时按模板**重新取号**（与其它交付物同一条路）。④**迁移 `p9_009`**：`numbering_templates.template_name` 加**全局唯一**约束 —— 不唯一 ⇒ 并发下两份同名模板 ⇒ **两条独立号段** ⇒ 同一项目里出现两个同号的变更单 ⇒ 凭证认不出是哪一张。⑤⚠️ **顺带登记 TODO-088**：在**隔离 schema** 上从零跑迁移会**漏建** 6 条约束（`p8_001`/`p8_008`/`p9_009` 的幂等检查**只按名字**查 `pg_constraint` ⇒ **不分 schema** ⇒ 别的 schema 里有同名列就跳过）⇒ 那个 schema 上的 `alembic check` 会报 6 条**假漂移**（真·全新数据库不受影响）	PCS
V2.12	2026-10-27	**TODO-074 落地（签署矩阵同名唯一）**（**纯追加 + 状态更新，不改绑定正文**）：①`signature_matrices` 此前**同名同状态**可以存在多份 ⇒ 内置矩阵按 `(matrix_name, status='ACTIVE')` **找第一份** ⇒ 并发下两个项目可能绑到不同的一份 ⇒ 「谁该签这一步」两个答案。②**应用层**：建矩阵 / 改名时**同名 + 同状态**已存在 ⇒ **409 `SIGNATURE_MATRIX_NAME_CONFLICT`**（不是 500）。③**DB 约束**（并发兜底）：**迁移 `p9_010`** ⇒ `uq_signature_matrices_name_status` = **(matrix_name, status)** 唯一。④⚠️ **为什么不是「名字全局唯一」**：一份**已作废**的同名模板不该永久堵住重建（否则历史绑定里的旧名字全是死链）⇒ 应用层与 DB 约束**同口径**。⑤两库 `pcs` / `pcs_test` 各跑一次 `alembic check` ⇒ **exit 0**（`current` 均为 `p9_010` = head）；全新隔离 schema 从零 `alembic upgrade head` ⇒ 通过（⚠️ 该 schema 上另有 6 条**假漂移** —— 见 TODO-088）	PCS
V2.13	2026-10-27	**TODO-075 落地（`change_resolved_by` 只由关记录那步写）**（**纯追加 + 状态更新，不改绑定正文**）：①`change_resolved_at` / `change_resolved_by` 记的是「**谁关闭了这次变更**」（ADR-0002「可追溯的关闭凭证（谁、为什么、凭什么关闭）」）⇒ 写它们的是**关记录那步**（变更单 APPROVED ⇒ `close_on_approved`），**不是**「校核完成」那步。②此前 9 态状态机的 `APPLY_CHANGE` **也写**这两个字段 ⇒ 变更单**还没批准**就已经有「关闭人」（= 校核人）⇒ 中间态语义**错位**（最终值会被覆盖，但对账中间态是错的）⇒ **已去掉**。③⚠️ **连带影响**：记录在 CHANGED（= 等关闭凭证）阶段，这两个字段是**空的** ⇒ 「变更已关闭」的查询在凭证批准前查不到 —— 这是**正确**的（那时变更确实还没关闭）。④测试：既有 `test_stream_transition.py` 的断言前提已变 ⇒ 改成断言它们**仍是空的**；新增流程级用例（APPLY_CHANGE 后为空 → 签完最后一步才写）	PCS
V2.14	2026-10-27	**TODO-076 落地（工作区门禁覆盖 UI-SPEC §5.3 全部四类操作）**（**纯追加 + 状态更新，不改绑定正文**）：①工作区门禁此前只挂在「创建变更单」一个端点 ⇒ UI-SPEC §5.3 清单里的其余三类（**提交批准 / 创建交付物 / 签署**）在 API 层**没有**守卫 ⇒ 「后端 403 为兜底」（UI-SPEC 自己写的）落空 ⇒ **绕过前端就能做**。⇒ 门禁挂到全部四类：`submit-approval` / `approval-step`（提交批准）· `issue`（创建交付物）· `change-notice`（创建变更单，原有）· `sign-step` / `customer-approval/proxy`（签署）⇒ 非 FORMAL 一律 **403 `WORKSPACE_TYPE_NOT_ALLOWED`**。②**两条放行（fail-open）分支显式化**：本守卫在「项目不存在 / 没挂工作区」与「工作区行不存在」时**放行**（**有意**：历史项目没挂工作区 ⇒ 不是个人草稿区 ⇒ 不因缺元数据挡掉正常操作）⇒ 现在**各有**一条测试钉住。③⚠️ 顺带修：`_guard.py` 原先抛 **core 变体** `PcsError` ⇒ `except service.PcsError`（仓里的多数写法）**捕不到** ⇒ 改成抛 **service 变体**（子类 ⇒ 两种 `except` 都捕得到）；⚠️ 同类残留登记 **TODO-089**（~20 个模块仍抛 core 变体 ⇒ 55 处 `except` 是潜在漏网）	PCS
V2.15	2026-10-27	**TODO-082 落地（两道「已对外生效」的门换成真实可判定的条件）**（**纯追加 + 状态更新，不改绑定正文**）：①`records.locked_by_deliverable` **全仓只被读、从不被写 True** ⇒ 两道门（①作废前必须先建 RECORD_CANCELLATION 变更单 ②已对外生效只能走 CHANGE_REVERSAL）**永远不触发** ⇒ 任何记录都能被直接弃用 / 直接撤销 ⇒ 「作废、撤销都要有凭证」这条业务约束**事实上不存在**。②**业务裁决（用户 2026-10-27）**：判据换成**真实可判定**的条件 —— 记录有没有被一张 **APPROVED** 的交付物绑定（`deliverable_record_bindings` ⋈ `deliverable_versions` ⋈ `deliverables`）⇒ 新增 `DeliverableService.is_record_effectively_published`。③⚠️ 判「APPROVED」而不是「有绑定」：一张**还没签完**的变更单也绑了记录 ⇒ 用「有绑定」当门禁 ⇒ 用户在变更单还没批准时就被挡住 ⇒ 流程走不动。④⚠️ `bound_obsolete_via_deliverable` 改判「**这张**交付物绑了这条记录」—— 判「已批准」会把那条路径永远堵死（它由 APPROVED 流程调用，那时单子还没批完）。⑤**已知代价**（裁决时已告知）：变更单**批准**后该记录即「已对外生效」⇒ 之后**普通撤销**会被拒 ⇒ 只能走 **CHANGE_REVERSAL** 反向变更单。⑥⚠️ **遗留 TODO-090**：`locked_by_deliverable` 列现在既无写入方也不是门禁（读端仍原样上报 ⇒ 恒为 False）⇒ 要么在发布时写它（审计标记），要么删列（16 张表 + 字典）	PCS
