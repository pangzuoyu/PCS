# ADR-0047：workflow_progress 观测层 —— 写入点、同步性与事务边界

- Status: **accepted**
- Date: 2026-10-19
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/services/state_machine.py`、`app/core/commit_or_rollback.py`、`app/api/v1/records.py`
- Informed: P9A 实施者、P9B 甘特图组件
- Supersedes: —
- Superseded by: —
- Related: SUP-008 V1.1 §2.6、P9-OPEN-007、SPEC §3.2.3 P9A-OBS-001~004、ADR-0041 §编号预留（故取 0047）

## 背景

SPEC P9-OPEN-007 要求 P9A 交付 `workflow_progress` 表（8 字段 + 5 态枚举）与读 API，
并有硬指标「流程状态变更到持久化 ≤ 500ms」。
全仓 0 命中（`grep -rn "workflow_progress" app/ alembic/`），属绿地方。

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

**本 ADR 只裁定 `workflow_progress` 用同步写，不延伸至通知。** 通知的
同步/异步选择属 ADR-0049 §①，该处**明确未锁**（本版无邮件服务器，原「异步以免阻塞
外部投递」的理由已失效），留待 P9A 按写侧实际压力决定并回填。

已确定属于 ARQ 范围的只有一件：**通知保留 30 天的清理任务**（ADR-0049 §④，
P9A-NOT-004）。

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
