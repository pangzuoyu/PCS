P9 工作流与权限开发规格说明书（修订版）
文件标识：PCS-REQ-2026-002-SPEC-P9
当前版本：V2.0（V1.3 → V2.0 结构性重排，2026-10-07）
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
ADR-B	workflow_progress 观测层	① 写入点清单（哪些状态变更要写）② 同步写 vs 异步写（500ms 延迟要求倾向同步）③ 与 P1 状态机事务的边界 ④ 与计算模块事务的关系
ADR-C	编辑锁	① 存储：DB SELECT FOR UPDATE vs Redis ② 自动续期机制（前端心跳频率 + 后端续期接口）③ 超时清理（30 分钟）④ 与状态机事务的关系 ⑤ Redis 不可用时的降级
ADR-D	通知与待办数据模型	① notifications 表 vs 实时计算 ② todos 表 vs 实时计算 ③ 若实时计算，≤500ms 加载指标靠什么索引支撑 ④ 通知保留 30 天清理任务归属（ARQ？但 TODO-016 显示 ARQ 失败路径覆盖为零）
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
验收：清单完成，每条明确归属；凡归 P9A 的写入 P9A SPEC。

2.2.4 MFA 决议（阻塞级）
P9-OPEN-001 从"待确认"升级为硬阻塞。二选一：

路径 A：确认公司 MFA 方案（TOTP / 短信 / 硬件令牌），写入 SPEC

路径 B：Fallback——AD 密码二次输入 + 强制审计（SIGN_2FA_FALLBACK），MFA 后续替换

验收：P9-OPEN-001 状态改为"已确认"或"已 Fallback"，且 SPEC §3.2.1 通过/退回操作、§3.2.1（5b）代录批准两条链路有明确实现依据。

2.3 P9-Prep 交付物（**2026-10-08 状态**）

| 交付物 | 状态 | 落点 |
|---|---|---|
| bug-144 迁移 + 应用 | ✅ | `p7_s5_007`（另修 bug-143） |
| CHECK / UNIQUE ORM 声明补齐 | ✅ | bug-147，28 CHECK + 9 UNIQUE |
| ondelete 裁决决议 | ✅ | CASCADE，`fd0e8b9` |
| uq_user_projects_user_project ORM 声明 | ✅ | bug-147 |
| `projects` 零外键修复 | ✅（计划外） | bug-146，`p7_s5_008` |
| alembic check 闸门脚本 / git hook | ❌ | 见下注 |
| ADR-A / B / C / D（4 份，accepted） | ❌ | 无 |
| 《P1 实际交付面清单》 | ❌ | 无 |
| MFA 决议 | ❌ | 无 |

**PP-5 注**：`alembic check` 现状为 exit 0（无漂移），但**闸门本身仍未自动化** —— `.pre-commit-config.yaml` 里没有 alembic 检查。TODOS.md 已裁决**不做**静态列覆盖检查器（一次性会报几百条没人能修的红，是「狼来了」）。可行的替代是把 `alembic check` （注意退出码 255）接进 pre-commit 的本地 hook，只在改动 `alembic/versions/*` 时触发。

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
P9A-DLV-007	SignatureMatrixService：steps_json 消费方，矩阵步骤推进、角色判定、动态列数	SUP-005（当前未落地）
P9A-DLV-008	代录客户批准后端：凭证附件存储（PDF/JPG/PNG/EML ≤20MB）+ 二次认证 + 审计 CUSTOMER_APPROVAL_PROXIED	ADR-0007
P9A-DLV-009	bug-145：ChangeNoticeService.create_change_notice 写死 matrix_id=None，但 Deliverable.matrix_id NOT NULL 带 FK → 真库必 500。**2026-10-08 已部分处置**：函数改为显式 `raise NotImplementedError`（不再留「接个 API 路由就 500」的哑雷），5 个 happy-path 测试改为断言拒绝 + 无副作用 + 不写审计。**功能本身仍待 P9A-DLV-007 的矩阵消费方**。
　　⚠️ 复核推翻了原记录两点：①「无任何测试」是错的（`tests/services/` 下有 5 个，但用假 DB，结构上观察不到 DB 层约束）；②`ChangeNoticeService` **无任何 API 路由调用**、真库 0 行，是未接线的死路径而非线上 500	TODOS.md
验收：P9B 所需全部端点可用；alembic check 无新增漂移；bug-145 有回归测试。

3.2.2 用户身份改造（高风险）
编号	内容	依据
P9A-USR-001	users 表启用：AD 同步创建系统用户记录	ADR-A + P9-ADM-001
P9A-USR-002	AD 同步服务：手动触发 + 定时任务（每日凌晨）；用户基本信息（姓名/邮箱/部门）+ AD 安全组	P9 SPEC §3.2.3
P9A-USR-003	角色映射：AD 安全组 → 系统角色（5 角色），支持手动覆盖 + 日志	P9 SPEC §3.2.3
P9A-USR-004	离职处理：AD 删除后标记停用 + token_version 递增使在手令牌即刻失效	新增条目（V1.3 缺口）
P9A-USR-005	登录路径变更：登录时查 users 表判 status；停用用户拒绝登录	ADR-A
P9A-USR-006	历史 user_id 兼容：uuid5 派生 ID 与 DB 主键的等价性处理	ADR-A
P9A-USR-007	token_version 机制：users 表加列；create_token 写 claim；refresh 端点校验（access token 保持无状态，吊销粒度 = access TTL 30 分钟）	TODO-002 修正后处方
验收：AD 同步端到端跑通；停用用户 refresh 立即 401；历史数据外键不断裂。

3.2.3 横切观测层
编号	内容	依据
P9A-OBS-001	workflow_progress 表：8 字段 + 5 态枚举（PENDING/IN_PROGRESS/COMPLETED/SKIPPED/FAILED）	SUP-008 V1.1 §2.6
P9A-OBS-002	写入层：签署 / 变更单 / 代录批准状态变更时同步写	ADR-B
P9A-OBS-003	读 API：供前端甘特图/进度条/超时告警消费	SUP-008 §8.3.5
P9A-OBS-004	500ms 延迟验证：流程状态变更到持久化 ≤ 500ms	P9-OPEN-007 验收标准
验收：workflow_progress 在三条工作流上均有写入；延迟达标。

3.2.4 通知 / 待办后端
编号	内容	依据
P9A-NOT-001	notifications 表（或实时计算方案，按 ADR-D）	新增（P0 清单无）
P9A-NOT-002	todos 表（或实时计算方案，按 ADR-D）	新增（P0 清单无）
P9A-NOT-003	GET /todos / GET /notifications / PUT /notifications/{id}/read	P9 SPEC §3.1.2
P9A-NOT-004	通知保留 30 天清理：ARQ 任务 + 失败路径覆盖（补 TODO-016 缺口）	P9 SPEC §3.2.1（7）
P9A-NOT-005	待办生成器：签署任务 / 退回通知 / 变更报警 / 系统公告 四类型	P9 SPEC §3.2.1（7）
验收：待办列表 ≤500ms；通知列表 ≤500ms；清理任务有失败注入测试。

3.2.5 编辑锁后端
编号	内容	依据
P9A-LCK-001	锁存储（按 ADR-C：DB 或 Redis）	ADR-C
P9A-LCK-002	acquire / release / status 三端点	P9 SPEC §3.1.2
P9A-LCK-003	自动续期：前端心跳 + 后端续期接口	P9 SPEC §2.5
P9A-LCK-004	超时清理：30 分钟过期	P9 SPEC §2.5
P9A-LCK-005	降级策略：Redis 不可用时（若选 Redis）	ADR-C
验收：并发编辑场景下锁正确；过期自动释放；与状态机事务无死锁。

3.2.6 变更影响确认分流（若 P1 未交付）
若 P9-Prep §2.2.3 核实 POST /change-impact/.../confirm 不存在，则归 P9A：

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
§3.2.2 变更影响前端"确认并重新计算"	保持，依赖 P9A-CIA-001（或 P1，按核实）
4.2 前端开发纪律（新增）
强制约束（吸取 TODO-039/041 逾期教训）：

前端 type 从 ./api 生成，禁止手写 mock type。7 个 mock type 文件（pipeClass/flash/pipe/pump/pipeNet/pms/common）改 import 自 ./api，这是 TODO-039 的要求，P9B 开工前必须先清完。

MSW handlers 按 OpenAPI 重写，禁止按前端 mock types 写（TODO-041）。

P9B 开工前提 = P9A OpenAPI 契约冻结。契约未冻结不允许前端动工，避免对着 mock 绿、上线 404。

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
todos	P0 清单无	P9A 新建（或实时计算，按 ADR-D）
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
第八部分：待确定问题（修订）
编号	问题	V1.3 状态	V2.0 状态	归属
P9-OPEN-001	MFA 实现方式	待确认	硬阻塞，P9-Prep 决议	P9-Prep
P9-OPEN-002	通知邮件服务器	待确认	P9-Prep 决议	P9-Prep
P9-OPEN-003	审计日志导出格式	已确认	保持	P9B
P9-OPEN-004	用户同步定时频率	待确认	P9-Prep 决议（建议每日凌晨）	P9-Prep
P9-OPEN-005	批注 @提及	已确认（不支持）	保持	—
P9-OPEN-006	通知 WebSocket vs 轮询	待确认	P9-Prep 决议（建议 WebSocket + 降级轮询）	P9-Prep
P9-OPEN-007	workflow_progress	待启动	升级为 P9A-OBS-001~004	P9A
P9-OPEN-008	用户身份模型迁移	（无）	ADR-A	P9-Prep
P9-OPEN-009	编辑锁存储方案	（无）	ADR-C	P9-Prep
P9-OPEN-010	通知/待办表 vs 实时计算	（无）	ADR-D	P9-Prep
P9-OPEN-011	fk_utility_energy_summary ondelete CASCADE vs RESTRICT	（无）	**已裁决：CASCADE**（`fd0e8b9`）	~~P9-Prep~~ 已关闭
第九部分：修订后对开发计划文档的同步要求
Web版开发计划.md 需同步修订：

P9 章节：

周期：第 23–25 周 → 第 23–35 周（P9-Prep 23–24 / P9A 25–30 / P9B 31–35）

核心产出：签署流程、变更影响分析、ADMIN → P9-Prep（清账+ADR）、P9A（后端交付物+身份+观测层）、P9B（前端交互）

依赖：P1, P7 → P7 收口 + P9-Prep ADR

模块依赖图：P8 → P9 之间的箭头改为 P8 → P9-Prep → P9A → P9B → P10

里程碑验收标准表：P9 行拆为 P9-Prep / P9A / P9B 三行

未解决问题章节：新增"P9 后端交付物子系统实际未由 P1 交付"说明

版本历史（追加）
版本	日期	修改内容	编制人
V1.0	2026-08-27	初始版本	联合项目组
V1.1	2026-08-28	SUP-004/005/006/007 两层签署	联合项目组
V1.2	2026-08-29	ADR-0019/0022 物流手动创建	联合项目组
V1.3	2026-09-03	SUP-008 V1.1 workflow_progress	联合项目组
V2.0	2026-10-07	架构审查后结构性重排：拆 P9-Prep/P9A/P9B；新增后端交付物子系统规格；补 4 份 ADR 前置；补 notifications/todos/workflow_progress 三表；补 token_version 条目；MFA 升级硬阻塞；工作量 5.5–7.5 → 17.5–24 人周；周期 3 周 → 9–12 周；依赖 P1,P7 → P7 收口 + P9-Prep	架构审查
