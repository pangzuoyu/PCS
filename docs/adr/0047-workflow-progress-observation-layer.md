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

### ② 同步写 vs 异步写

**同步写，与业务状态在同一事务内。**

SPEC 的 500ms 是**上界**不是目标。异步（ARQ）引入的是「已提交但未入队」的丢失窗口与
「已入队但队列挂了」的延迟不可控 —— 观测层恰恰是出问题时要信的东西，它不能自己变成
不确定的。同步写的成本（多一次 INSERT）远低于观测层不可信的成本。

（ARQ 仍留给通知清理任务，见 ADR-0049。）

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

## 尚未解决

- **`commit_or_rollback` 只有 `config.py` 一个使用者**，其余 API 走显式
  `session.commit()`。P9A 新增的 3 个写入点该跟随哪种写法未裁决 ——
  本 ADR 只要求「与主事务同生共死」，两种写法都满足。跟随邻近代码即可，
  统一包装器是独立重构，不在本 ADR 范围。
