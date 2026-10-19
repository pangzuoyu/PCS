# ADR-0049：通知与待办数据模型 —— 通知建表 / 待办实时计算

- Status: **accepted**
- Date: 2026-10-19
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/models/deliverable.py`、`app/workers/worker.py`、`app/services/report/arq_queue.py`、`TODOS.md` TODO-016
- Informed: P9A 实施者、P9B 通知中心 / 待办栏
- Supersedes: —
- Superseded by: —
- Related: P9-OPEN-010、ADR-0047（观测层）、ADR-0046 §背景（通知语义由登录/签署事件驱动）、SPEC §3.2.4 P9A-NOT-001~005、ADR-0041 §编号预留（故取 0049）

## 背景

通知与待办两表在 P0 清单中均无，P9A 需新建。
实测 `grep -rn "notifications|__tablename__ = \"todos\"" app/ alembic/` → **0 命中**，属绿地方。

ADR-0007（客户凭证代录）已引入「通知」语义（签署事件需通知他人）。

**结论先行：两者形态不同，不该统一。** 待办的真值随签署矩阵推进而自动变化，
通知是离散发生过的事实。

**本版无邮件服务器**（P9-OPEN-002 裁决，2026-10-19 用户）：
通知主通道为**站内信**（铃铛 + 待办列表），邮件是下一版功能。
这直接影响 §① 写侧是否异步的理由 —— 见该节。

## 决策

### ① notifications：建表

通知是**发生过的事实**（某人某时被退回、某单被审批），无法从当前状态反推 ——
「你被退回过」在记录已改正后依然成立，但实时计算会返回空。

建 `notifications` 表。`GET /notifications` 按 `recipient_id + read_at` 索引，
`PUT /notifications/{id}/read` 标记已读。

**通道抽象（P9-OPEN-002 裁决落地）**：通知写侧须经一个通道抽象
（`NotificationChannel` 协议 + `InAppChannel` 实现）。邮件作为其未来的一个实现，
**本版不写** `EmailChannel` —— 不写空壳实现：空壳会假装邮件通道已就绪，
下一版接的时候才发现签名不对。
**不得**在 service 里写 `if 走邮件: ...`，那会让「预留」变成「临时 if」。

**写侧是否异步**：本版**没有外部投递**，异步的理由不再是「不阻塞外部通道的延迟」，
只剩「不阻塞写库」。因此异步与否不再是体验决策 ——
留待 P9A 按写侧实际压力决定，**本 ADR 不锁**。（原计划写「异步」的理由已随邮件移除而失效，
照抄会得到一个前提错误的论证。）

### ② todos：实时计算

待办的真值是「**当前**谁被卡住」，它由签署矩阵的当前步骤决定，随每次签署推进自动改变。

建表意味着每次推进都要 UPDATE 全部下游步骤的 todo 行 —— 写放大，且引入了
「todo 表与 matrix 表不一致」的窗口。实时计算直接查
`SignatureMatrix.steps_json`（`app/models/deliverable.py:159`，JSONB）中当前步骤的
`sign_role` × 当前用户角色 → 命中即一条待办。

**没有一行会过期**，因为它每次查询都从真值重算。

### ③ ≤500ms 的索引支撑

- 待办（实时计算）：走 `deliverables` 现有索引
  （`uq_deliverables_scope`、`uq_deliverables_doc_no`、`project_id` 上的 index，
  `deliverable.py:35-44`）+ `steps_json` 内存解析，无 JOIN 大表。
  验收以 `EXPLAIN ANALYZE` 确认无全表扫为准（P9A-NOT-003 验收）。
  ⚠️ **现有索引里没有任何按用户/角色的索引** —— 待办查询要先按
  「当前用户有权的 project」缩小集合。若这一步走的是 `user_projects`，
  P9A 需确认那条路径有可用索引，否则 500ms 达不到。
- 通知（建表）：`ix_notifications_recipient_unread (recipient_id, read_at)`
  部分索引 `WHERE read_at IS NULL`。这是 500ms 指标的全部支撑 —— **该索引必须进迁移**。

### ④ 通知保留 30 天清理：ARQ 任务 + 失败路径覆盖

清理任务挂 ARQ（`app/workers/worker.py`，与既有 worker 同栈）。

**照既有 cron 的三个已踩过的坑写**（`worker.py:145-160` 的注释是血泪）：

1. 必须是 `CronJob` **实例**不是 dict —— ARQ 0.28 的 `Worker.__init__` 直接校验类型，
   dict 会让 worker **构造就抛**。
2. 后 13 个参数是**必填位置参数**，没有默认值。
3. **`None` 不等于「不限」，等于「这一位不参与匹配」** ——
   秒位传 `None` ⇒ 匹配的那一分钟里每秒都命中。每秒位一律写 `0`。

**必须补失败注入测试**（TODO-016 显示 ARQ 失败路径覆盖率为零）：
构造 worker 抛异常 → 断言任务被重试/进 DLQ，而非静默消失。
P9A-NOT-004 验收明确要求这条测试存在。

**并加一条注册断言**：仓库已有
`tests/workers/test_worker_registers_all_enqueued_tasks.py`，断言
「入队的 ⊆ 已注册的」。**ARQ 对未注册的函数名不报错，job 静静躺在队列里**
（`worker.py:136-140` 记录的踩坑）—— 清理任务漏注册的症状是
「30 天后通知还在，且没人知道」。把清理任务纳入那条既有断言。

## 后果

- 迁移纪律：新表走 `TimestampMixin` 三列纪律（`app/models/mixins.py:34-41`：
  created_at 带 server_default + timezone、updated_at 可空 + `onupdate`、created_by 可空）；
  `drop_table` 只出现在 `downgrade()` 且带 `if_exists`。
- `todos` 不建表 ⇒ SPEC §3.2.4 P9A-NOT-002 记为「按本 ADR 走实时计算，无迁移」。
- 待办/通知的响应 schema 仍受 P9A-DLV-010 零裸字段约束。
- **P9-OPEN-006（WebSocket + 降级轮询）权重上升**：去掉邮件后，实时推送成了通知唯一的
  及时性来源。降级状态必须**可观测**（健康端点或指标），不能只靠前端感觉 ——
  通知静默失效正是 ADR-0047 立观测层要防的那类问题。

## 尚未解决

- **通知写侧同步还是异步未锁**（见 §①）。本版无外部投递，原「异步以免阻塞外部通道」
  的理由已不成立；需 P9A 按实际写侧压力决定，并回本 ADR 补记。
- **用户离线时无处可达**：站内信只在用户登录时可见，离线用户直到自己登录前
  收不到任何主动提醒。开发版可接受；正式版上此行为前**必须**有邮件或推送通道。
