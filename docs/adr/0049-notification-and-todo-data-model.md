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

#### `NotificationChannel` 的最小接口

「不写空壳」这条只有在**协议本身有最小定义**时才成立 ——
否则「先写 InAppChannel，将来加 EmailChannel」只是把同一个「签名不对」的问题
推迟到下一版，而推迟的问题会在下一版以「签名不对」的形式原样回来
（决策委员会 2026-10-19 指出）。

```python
class NotificationPayload:        # frozen dataclass，不是 ORM
    notification_id: uuid.UUID
    recipient_id: uuid.UUID
    kind: str                      # 枚举：签署/退回/代录/变更单…
    title: str
    body: str
    created_at: datetime
    meta: dict[str, Any]           # 通道无关的附加上下文（record_type/id 等）

@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    reason: str | None = None      # 未送达时的原因，供调用方决定是否降级

class NotificationChannel(Protocol):
    async def deliver(self, payload: NotificationPayload) -> DeliveryResult: ...
```

**四条设计约束，每条都对应一个具体失败模式**：

| 约束 | 若违反会怎样 |
|---|---|
| 入参是 **DTO 不是 ORM 对象**，且**不传 `recipient: User`** | 通道与 ORM 耦合 ⇒ 将来邮件通道要在 ORM 会话里取用户，多一个失败面。收件人已在 `payload.recipient_id` 里 |
| **只有一个方法**，不预定义 `can_deliver` / `on_failure` / 批量接口 | 预先猜测下一版的需求 = 重蹈空壳覆辙。这些等接邮件时按真实需求加 |
| **`delivered` / `reason` 现在就用上** | 见下方说明 —— 这是唯一一处「为下一版预留」的字段，必须写明为什么 |
| **通道不做路由** | 写侧注入一个实现即可；本版只有站内信一个通道。出现第二个通道时再引入注册表 |

⚠️ **关于 `delivered` / `reason` 在本版恒为 `delivered=True`** ——
写出来是为了让将来的邮件通道**有地方报告失败**。
邮件的典型失败是 SMTP 拒收：若协议里没有这两个字段，接邮件的人第一反应就是
在 service 里加 `try/except` 记日志 —— 那正是 §① 明令禁止的**「临时 if」**。
有了 `DeliveryResult`，失败是一条**返回值**，不是一段散在调用点的异常处理。

**`InAppChannel.deliver()` 的职责边界**：

- **做**：写 `notifications` 一行（这是通知的**真值来源**）
- **不做**：WebSocket 推送。**通道不应该知道 WebSocket 存在** ——
  一个「邮件通道」里出现 WebSocket 调用是荒谬的，而本版的唯一实现是站内信。

⚠️ **但推送不能因此缺席**。P9-OPEN-006 已裁定「WebSocket + 降级轮询」且**是本版通知
体验的关键路径** —— 而 WebSocket 是**服务端推送**，服务端不推就没有它。
⇒ **推送的接线义务在本版**：写侧在 `deliver()` 成功后通知一个进程内 broadcaster，
由它向该 `recipient_id` 的连接推。推送与持久化**分开**（可分别测试），
但**不许缺席**。「登录时轮询能看到」只是降级路径，不能当成推送已实现。

**写侧是否异步**：本版**没有外部投递**，异步的理由不再是「不阻塞外部通道的延迟」，
只剩「不阻塞写库」。因此异步与否不再是体验决策 ——
留待 P9A 按写侧实际压力决定，**本 ADR 不锁**。（原计划写「异步」的理由已随邮件移除而失效，
照抄会得到一个前提错误的论证。）

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
  具体对应 ADR-0047 §② 的时序差说明：若通知发送做成异步，会出现
  「`workflow_progress` 已写 COMPLETED 但通知尚未发送」的窗口 ——
  那是**已知行为不是错误**，但排障时不得反过来当成观测层不可信。
  （换言之：观测层保证「流程进度可信」，不保证「通知已送达」。两者不要混为一谈。）

## 尚未解决

- **通知写侧同步还是异步未锁**（见 §①）。本版无外部投递，原「异步以免阻塞外部通道」
  的理由已不成立；需 P9A 按实际写侧压力决定，并回本 ADR 补记。
- **用户离线时无处可达**：站内信只在用户登录时可见，离线用户直到自己登录前
  收不到任何主动提醒。开发版可接受；正式版上此行为前**必须**有邮件或推送通道。
  **验收分界（决策委员会 2026-10-19 补充）**：
  - **P9A 验收只要求两件事** —— ① `InAppChannel.deliver()` 写入 `notifications` 行；
    ② WebSocket 推送在连接建立时可用（P9-OPEN-006 的关键路径，**不得**缺席）。
  - **P9A 验收不要求**「离线用户在断线期间收到推送」。那是**产品上线门禁**，
    归属本版结束后的产品评审，**不占 P9A 验收**。
  - 写这一条是为了防止反过来的两种误判：把「离线可达」当成 P9A 验收项而做无用功，
    或在 P9A 验收时用「离线可达」否掉一个本来合格的交付。
