# ADR-0047：workflow_progress 观测层 —— 写入点、同步性与事务边界

- Status: **accepted**
- Date: 2026-10-19
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/services/state_machine.py`、`app/core/commit_or_rollback.py`、`app/api/v1/records.py`
- Informed: P9A 实施者、P9B 甘特图组件
- Supersedes: —
- Superseded by: —
- Related: SPEC §3.2.3 P9A-OBS-001~004、P9-OPEN-007、ADR-0041 §编号预留（故取 0047）
- 引用勘误（2026-10-20，决策委员会）：本 ADR 原在 Related 里写「SUP-008 V1.1 §2.6」
  作为 8 字段定义的出处 —— **该引用是错的**：SUP-008 §2.6 实为「2.6 新模块：反应器计算」，
  §3.2.6 是「新增 reactor_results 表」，**8 字段的定义在 SUP-008 里根本不存在**。
  真正的出处是 SPEC §3.2.3 P9A-OBS-001（其自身也误引 SUP-008，见 TODO-052）。

## 背景

SPEC P9-OPEN-007 要求 P9A 交付 `workflow_progress` 表（8 字段 + 5 态枚举）与读 API，
并有硬指标「流程状态变更到持久化 ≤ 500ms」。
全仓 0 命中（`grep -rn "workflow_progress" app/ alembic/`），属绿地方。

### ⚠️ 同名不同表：`SUP-008 V1.1 §8.5` 另有一个 `workflow_progress`

SUP-008 §8.5 的 `CREATE TABLE workflow_progress` 是 **14 字段**的
**项目作业流程进度百分比表**（`sequence_no / main_workflow_item / progress_percent /
external_condition_1..5(+_progress) / start_date / completion_date`，
`UNIQUE(project_id, sequence_no)`），来源是 1216D132 实例 Excel Sheet 2「作业流程」导入。

它与本 ADR 的观测表**领域不同**：那是「项目作业进度」，本表是「签署/变更单/代录的
工作流步骤状态」。把两个领域塞进一张表，正是本 ADR §后果 那条
「写入点超出这个数 ⇒ 回本 ADR 修订，不要就地加」的同类错误。

**裁决（2026-10-20，决策委员会）**：本 ADR 采用 SPEC/ADR 的观测表；
若将来要建 SUP-008 §8.5 那张表，**必须另起表名**（建议 `project_job_progress`），
**不得复用 `workflow_progress`**。登记见 `TODOS.md` TODO-052。

`app/services/state_machine.py`（404 行）承载状态转移，`StateMachineService.transition()`
在 `:348` 只做 `await self.session.flush()` —— **它不 commit**。
真正的 commit 在调用方，例如 `app/api/v1/records.py:215` 的 `await session.commit()`。
另有一个事务包装器 `app/core/commit_or_rollback.py`（async context manager），
目前只有 `app/api/v1/config.py` 在用。

⚠️ 这一点纠正了一处常见误解：**`state_machine.py` 不是事务边界所在**，
它只是事务内的一个参与者。§③ 的裁决正建立在这个实测事实上。

## 决策

### ① 写入点清单

三个工作流各一处，共 **3 个写入点**：

1. **签署**：`sign-step` 推进 / 退回时，写被推进的那一步
2. **变更单**：`deliverable_type=CHANGE_NOTICE` 的创建与自动关闭
3. **代录批准**：`customer-approval/proxy` 的状态变更

不写「打开页面」「查看」等读行为 —— 本表是**流程进度**，不是访问日志。

#### 🔒 写入层：必须在 **service 层**，不得在 API 层

（决策委员会 2026-10-19 补充裁定）

上面的三条说的是**何时写**。**由哪一层写**同样是被本 ADR 约束的，且这一层选错的后果
不是「风格不好」，是**观测层出现系统性盲区**。

**判定依据是实测的可达路径**，不是偏好。`StateMachineService.transition()` 今天有
**四条**入口，其中**两条完全不经过 API 层**：

| 入口 | 所在层 | 有无 HTTP 请求 |
|---|---|---|
| `app/api/v1/records.py:204` / `:258` | API | 有 |
| `app/services/stream_service.py:428` | service | 不一定 |
| `app/services/cia_engine.py:85`（`cia_mark_stale` 事件处理者） | service | **无** |
| ↑ 由 `app/workers/cia_tasks.py` 的 **ARQ cron** 驱动（1 分钟增量 / 5 分钟全量 CIA 扫描） | worker | **完全没有** |

⇒ **若把写入放在 API 层，所有 cron 驱动的 STALE 标记在 `workflow_progress` 里都是隐形的。**
而 cron 恰恰是 STALE 标记的主要来源之一 —— 也就是说，写错层之后观测层看起来是通的，
只是**系统性漏掉了最需要观测的那部分**。这种失效不报错、不告警。

**规则**：

1. 写入点落在 **service 层**（P9A 新建的签署 / 变更单 / 代录 service，或其调用方
   service）。P9A 设计 service 时确定具体方法名。
2. **不得**写在 `app/api/v1/*` 的路由处理函数里。
3. 若某个流程的触发方**本身**已在 service 层（如 `cia_mark_stale` 那样由
   事件/cron 驱动），则写入随该 service，**不**上移到任何 API 层。

> 推论（也是 P9A 的硬约束）：**观测写入的可测试性跟着 service 走** ——
> service 可以被单测直接调用而绕过 HTTP。若写入在 API 层，
> 「service 单测全绿」会掩盖「观测层在生产的主要路径上根本没被触发」。

### ② 同步写 vs 异步写

**同步写，与业务状态在同一事务内。**

SPEC 的 500ms 是**上界**不是目标。异步（ARQ）引入的是「已提交但未入队」的丢失窗口与
「已入队但队列挂了」的延迟不可控 —— 观测层恰恰是出问题时要信的东西，它不能自己变成
不确定的。同步写的成本（多一次 INSERT）远低于观测层不可信的成本。

**本 ADR 只裁定 `workflow_progress` 用同步写，不延伸至通知。**

⚠️ **「通知清理」与「通知发送」是两个不同的问题，不要混读**（决策委员会 2026-10-19 指出）：

| | 归属 | 状态 |
|---|---|---|
| **通知清理**（30 天过期删除） | ADR-0049 §④ | ✅ **已裁定挂 ARQ**（P9A-NOT-004）—— 与有无邮件无关，是本地定时任务 |
| **通知发送**（流程变更时通知相关人） | ADR-0049 §① | ⬜ **明确未锁** —— 本版无邮件服务器，原「异步以免阻塞外部投递」的理由已失效；留待 P9A 按写侧实际压力决定并回填 |

⇒ 「ARQ 留给通知**清理**」**不**意味着 ADR-0049 已裁定通知**发送**用 ARQ。

> ⚠️ **时序差要写明，不要当成不存在**：
> 若 P9A 最终把**通知发送**也做成异步，则会出现
> 「`workflow_progress` 已写 COMPLETED，但通知尚未入队/发送」的窗口。
> **这不是错误**（通知延迟是常态），但它是**已知行为**，排障时不能反过来
> 当成观测层不可信。若通知最终同步写，本窗口不存在。

### ③ 与 P1 状态机事务的边界

**不设独立边界。** `workflow_progress` 写入发生在**调用方**的事务内，
即由发起状态变更的那个事务负责写，**不由 `state_machine.py` 内部埋点**。

理由：埋点式写入会把观测代码耦合进状态机核心路径，让 P7 已验收的状态机承担 P9 的变更风险；
调用方写入则让「谁触发流程」与「流程进度记哪」在同一个可读的事务里 ——
而事务边界本来就在调用方（`records.py:215` 显式 commit）。

失败语义：**与主事务同生共死** —— 观测写失败则整个状态变更回滚。

> 这个取舍不是对称的：观测层不可信的代价（排障时被错误数据误导）远高于
> 「多一次 INSERT 把主流程拖慢几毫秒」的代价。

### ④ 与计算模块事务的关系

**无关。** 计算结果落库（各 `*_persist_service`）不产生流程进度，不写本表。
计算是「得出一个值」，不是「推进一个流程」。

## 后果

- 表结构 8 字段 + 5 态枚举（PENDING/IN_PROGRESS/COMPLETED/SKIPPED/FAILED）由
  **P9A-OBS-001** 落迁移，走 `TimestampMixin` 三列纪律
  （`app/models/mixins.py:34-41`：created_at 带 server_default + timezone、
  updated_at 可空 + `onupdate`、created_by 可空）。
- **实现偏离（2026-10-20，P9A-2 B0 落地后登记）** —— 上面的「8 字段」是**原始设计**，
  实际落地为 **10 个业务列** + `progress_id` 主键 + TimestampMixin 三列。
  多出的两列是被 P9A 自己的需求强制要求的，不是口味：
  - `workflow_type` —— 读 API 的 URL 段是 `{workflow_type}/{workflow_id}`，
    且 §① 的三个写入点靠它区分；缺了它，一次签署与一次代录的进度行无法分辨。
    实现为 3 值 Enum `WorkflowType`（SIGN / CHANGE_NOTICE / CUSTOMER_APPROVAL_PROXY），
    让「不要就地加第四类工作流」这条约束在**类型层**成立。
  - `project_id` —— `workflow_id` 是多态的（版本 ID / 交付物 ID），无法 join 回项目，
    而读 API 要按项目鉴权（越权 404）；这一列是授权的唯一依据。
  另有两处**改名**：`step_no` → `step_order`、`step_name` → `step_role`，
  为与 `SignatureMatrix.steps_json` 的键（`step_order` / `sign_role`）逐字一致。
  ⇒ 下一个实施者读到本段「8 字段」而代码是 10 列时，**代码是对的、本段过时**。
  偏差登记 `TODOS.md` TODO-053（不回改 SPEC 正文：SPEC 是绑定权威，改它要重走 §7.2 验收；
  改为在 SPEC §3.2.3 P9A-OBS-001 处加同样的实现偏离注记）。
- 写入面落在 `app/services/workflow_progress_writer.py`，且**只有一个公开入口**
  `record_step()`（有测试钉住「不得出现第二个写入口」）；读面是
  `app/services/workflow_progress_service.py`（`GET /workflow-progress/{type}/{id}`）。
  ADR-0047 §① 三个写入点的现状：**SIGN ✅ / CUSTOMER_APPROVAL_PROXY ✅ /
  CHANGE_NOTICE ❌ 未实现** —— `change_notice_service.create_change_notice` 目前直接
  `raise NotImplementedError`（等 P9A-DLV-007），所以「变更单的创建与自动关闭」
  今天没有可达触发路径。**这是「不可演示」不是「不采纳」**，登记 TODO-057。
- 500ms 验收（P9A-OBS-004）用同步写达成，无需异步管道。
- 读 API 供 P9B 甘特图消费，其响应 schema 必须显式声明（P9A-DLV-010 零裸字段约束）。
- 3 个写入点若将来超出这个数，说明有第四类工作流被漏登记 —— 届时回本 ADR 修订，
  不要就地加写入点。
- **写入层必须在 service 层**（见 §① 🔒 小节）。这条不是风格约束，是**可观测性的前提**：
  状态机有一条 ARQ cron 入口完全不经过 API 层，写在 API 层会让 cron 驱动的状态变更
  在观测层里系统性隐形。

## 尚未解决

- **`commit_or_rollback` 只有 `config.py` 一个使用者**，其余 API 走显式
  `session.commit()`。P9A 新增的 3 个写入点该跟随哪种写法未裁决 ——
  本 ADR 只要求「与主事务同生共死」，两种写法都满足。跟随邻近代码即可，
  统一包装器是独立重构，不在本 ADR 范围。

  **「邻近代码」本身不一致时的裁决规则**（决策委员会 2026-10-19 补充）：
  **以该写入点所在 service 内的邻近代码为准，而不是以整个模块或仓库的多数写法为准。**

  理由：同一 service 内的写法一致性是**局部正确性**（同一事务边界、同一 session 生命周期，
  读代码的人一眼能确认「它和主流程一起提交」）；跨模块统一是**重构**，是另一件事。
  为了一条新写入点去统一别人的 commit 风格，等于把 P9A 的观测层任务
  悄悄变成一次事务边界重构 —— 风险面和 ADR 想解决的问题完全不同。

  例外：若该 service **内部**就混用两种写法（同一文件里一半显式 `commit()`、
  一半 `commit_or_rollback`），跟随**该写入点直接相邻**的那个调用点，
  并在该 service 内留一行注释指明两种写法并存（不要顺手统一，登记到 `TODOS.md`）。
