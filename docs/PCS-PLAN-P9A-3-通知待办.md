# P9A-3 通知 + 待办

> 本文件是 `docs/PCS-PLAN-P9A.md`（总纲）的 **C 号 lane**。
> 共享的 Global Constraints / Review Focus / 失败模式 在总纲，只写一遍。
> **前置**：通知由 B 的流程事件触发，但 C 本身不 import B 的模块 ⇒ **可与 B 并行**
> **本 lane 的完成判定**（与总纲 §完成标准 对应）：见文末。

---

### C0：迁移基座（`notifications` 表 + 部分索引）

**Files:**
- Create: `pcs-backend/alembic/versions/p9_003_notifications.py`
- Create: `pcs-backend/app/models/notification.py`
- Test: `pcs-backend/tests/migrations/test_p9_003_notifications.py`

**Interfaces:**
- Produces: 表 `notifications`（10 列）+ 索引 `ix_notifications_recipient_unread (recipient_id, read_at) WHERE read_at IS NULL`
- ⚠️ 该索引是 **500ms 指标的全部支撑**（ADR-0049 §③）—— **必须进迁移**，不是「以后优化」

- [ ] **Step 1: 写失败测试**

- [ ] **Step 1: 写失败测试**（ADR-0049 §① 的「不写空壳」要有可执行的守卫）

```python
def test_no_email_channel_shell_in_repo():
    """全仓 grep 'EmailChannel' 必须 0 命中 —— 空壳会假装邮件通道已就绪。"""
def test_no_channel_type_branch_in_service():
    """service 层不得出现 if 走邮件 / channel_type == ... —— 那是「临时 if」。"""
async def test_in_app_writes_exactly_one_row(...): ...
async def test_delivery_result_reason_is_enum_not_free_string(...): ...
async def test_detail_json_has_explicit_schema(...):
    """P9A-DLV-010：detail_json 的字段级摘要必须有 schema，不是自由 dict。"""
async def test_channel_protocol_has_exactly_one_method(...):
    """最小接口只有一个 deliver —— 多定义 can_deliver/on_failure 就是预想未来。"""
```

```python
def test_notifications_partial_index_exists():
"""部分索引是 500ms 指标的全部支撑（ADR-0049 §③）。"""
    idx = Base.metadata.tables["notifications"].indexes
    t = [i for i in idx if i.name == "ix_notifications_recipient_unread"][0]
    assert [c.name for c in t.columns] == ["recipient_id", "read_at"]
    assert t.dialect_options["postgresql"]["where"] is not None
```

- [ ] **Step 2: 跑测试确认红** → **Step 3: ORM 声明**（`Notification` 模型，
  `detail_json` 用 JSONB）→ **Step 4: 写迁移**（10 个 `op.create_table/create_index`）
- [ ] **Step 5: 双库验漂移**

```bash
cd pcs-backend && uv run alembic upgrade head && uv run python scripts/gate_alembic_check.py
# 第二库（CLAUDE.md 读法③）
DATABASE_URL="$(grep -oE '^DATABASE_URL=.*' .env | cut -d= -f2 | sed 's|@localhost:5432/pcs$|@localhost:5432/pcs_test|')" \
  uv run python scripts/gate_alembic_check.py
```

- [ ] **Step 6: commit**

```bash
git add -A && git commit -m "feat(P9A): notifications 表迁移 + 部分索引（500ms 指标的全部支撑）"
```

---

### C1：通知写入侧（`NotificationChannel` + `InAppChannel`）

**Files:** Create `app/services/notifications/`（`channel.py` / `in_app.py` / `payload.py`）
**Interfaces:** 严格照 ADR-0049 §① 的最小接口，**不得自创签名**

```python
class NotificationPayload:   # frozen dataclass，不是 ORM，不传 recipient: User
    notification_id: uuid.UUID
    recipient_id: uuid.UUID
    kind: str
    title: str
    body: str
    created_at: datetime
    meta: dict[str, Any]

@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    reason: str | None = None

class NotificationChannel(Protocol):
    async def deliver(self, payload: NotificationPayload) -> DeliveryResult: ...
```

- [ ] **Step 1: 写失败测试**
  - `test_in_app_does_not_write_empty_email_shell` —— 全仓 `grep -ri "EmailChannel"` 必须 0 命中
  - `test_no_branch_on_channel_type_in_service` —— service 层 `grep "if.*走邮件\|channel_type =="` 必须 0 命中
  - `test_detail_json_has_explicit_schema` —— 受 P9A-DLV-010 零裸字段约束

- [ ] **Step 2: 实现**（`InAppChannel.deliver` 只写 `notifications` 行）

- [ ] **Step 3: commit**

---

---

### C2：WebSocket 推送（Redis pub/sub）+ 降级可观测

**Files:**
- Create: `app/api/v1/ws.py`
- Create: `app/services/broadcaster.py`（**Redis pub/sub**，非进程内）
- Modify: `app/api/v1/health.py`（`HealthResponse` 加两个字段）
- Modify: `app/models/project.py` / `app/models/system.py`（`UserStatus` 无关；仅 health schema）
- Test: `tests/api/v1/test_ws_notifications.py`、`tests/services/test_broadcaster.py`

**Interfaces:**
- Consumes: `REDIS_URL`（`app/core/config.py:43`，ARQ 已在用）、ADR-0049 §⑤/§⑥
- Produces:
  - `WS /api/v1/ws/notifications`（需鉴权：token 走 query 或 header）
  - `GET /notifications?after=<last_seen>` —— **断线兜底路径**，pub/sub 不持久化（§⑤ 约束 1）
  - `HealthResponse` 新增 `realtime: str` 与 `realtime_reason: str | None`
  - channel 命名：`ws:notify:{user_id}`

> ⚠️ **必须跨进程。** 进程内 broadcaster 在多 worker 下会让连接到 A 的用户收不到 B 产生的
> 通知，**且不报错**。这与 **TODO-047 同形状**（进程内 `hash()` → 多 worker 静默失效），
> 而 **dev 单 uvicorn 进程（`README.md:64` 无 `--workers`）会掩盖它**，P10 容量规格已按
> 4 workers 设计。⇒ **禁止用「文档限制单进程部署」替代跨进程正确性**。

- [ ] **Step 1: 写失败测试**（每条对应 ADR-0049 §⑤ 的一个约束）

```python
async def test_push_crosses_process_boundary(broadcaster, fake_redis):
    # 约束：跨进程。B 的广播必须能被 A 上连着的该用户收到
    ...  # 订阅端与发布端用两个独立连接模拟两个 worker

async def test_messages_during_disconnect_are_recoverable_via_api(client):
    # 约束 1：pub/sub 不持久化，断线期间的消息由 notifications 表兜底
    ...  # GET /notifications?after=<last_seen> 返回断线期间那几条

async def test_subscription_uses_separate_connection_from_arq_pool():
    # 约束 3：订阅会阻塞，不能与 ARQ 的 BLPOP 共用同一连接
    ...  # 断言订阅端不在 ARQ 连接池里

async def test_broadcaster_records_degraded_state():
    # 约束 2 + §⑥：发布失败要留下可读标志
    ...  # broadcaster.status == 'degraded'

async def test_health_realtime_reflects_broadcaster_without_blocking(client):
    # §⑥ 约束 1：/health 读缓存标志，**零额外探测**；
    #   Redis 挂掉时 /health 的响应时间**不得**因此改变
    ...  # 断言 Redis 不可达时 /health 仍快速返回且 realtime == 'degraded'

async def test_health_returns_200_even_when_realtime_degraded(client):
    # §⑥ 约束 2：状态码语义不变
    ...

async def test_realtime_reason_is_enum_not_free_string():
    # §⑥ 约束 3：枚举契约
    ...  # 只允许 redis_unavailable / redis_timeout / pubsub_error / null
```

- [ ] **Step 2: 实现 broadcaster（Redis pub/sub）**

```python
# app/services/broadcaster.py  骨架
class Broadcaster:
    def __init__(self, redis_url: str) -> None:
        self._pub = ...          # 发布：可复用 ARQ 的连接池（普通命令）
        self._sub = None         # 订阅：**独立连接**，startup 建立 / shutdown 关闭
        self.status = "ok"       # 约束 2：/health 只读这个标志，不做探测
        self.reason: str | None = None

    async def start(self) -> None:
        """订阅本 worker 上有连接的用户各自的 channel（懒订阅）。"""
        ...

    async def publish(self, recipient_id: uuid.UUID, payload: NotificationPayload) -> None:
        try:
            await self._pub.publish(f"ws:notify:{recipient_id}", payload.json())
            self.status, self.reason = "ok", None
        except Exception as e:
            self.status = "degraded"
            self.reason = "redis_unavailable" if ... else "pubsub_error"
            logger.error("通知推送失败，降级到轮询: %s", e)
```

  channel 按 `recipient_id` 分（§⑤ 约束 4）：单用户多设备 → 同 channel 多订阅者都收到；
  跨 worker → B 发布 → A 收到 → 推给用户。
  📌 **分片决策点**：连接数超约 5000 时再考虑按 hash 分片，现在不做（YAGNI），
  但阈值写在这里，免得将来无人记得。

- [ ] **Step 3: `/health` 扩展字段（§⑥）**

```python
class HealthResponse(BaseModel):
    status: str                       # 既有：ok / degraded
    database: str                     # 既有：up / down
    realtime: str                     # 新增：ok / degraded
    realtime_reason: str | None       # 新增：redis_unavailable / redis_timeout / pubsub_error / null
```

  ⚠️ **三条硬约束**：
  1. **不阻塞主路径** —— `/health` 现在已同步 `check_database_async()`（`app/db/session.py:108`，
     **无显式超时**，靠连接池）。`realtime` **读 broadcaster 的标志，零额外探测**。
  2. **状态码不变** —— degraded 时仍 200。`realtime` **仅供观测，不得用于 liveness/readiness**
     （否则 Redis 挂了会触发服务重启循环）。要 readiness 就另建端点，不复用 `/health`。
  3. **`realtime_reason` 是枚举**，不是自由字符串 —— 自由字符串前端无法可靠判断。

  📌 **语义**：`realtime` 检测的是 **pub/sub 可达性**，不是 Redis 整体健康。二者当前等价，
  但它**只承诺「WS 推送能力」**。排障时不得把它当「Redis 挂了」的唯一判据。

- [ ] **Step 4: 断线兜底 API**

```python
@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(after: datetime | None = None, ...
                               limit: int = Query(50, le=200), ...
                               db: ... = Depends(get_db)) -> NotificationListResponse:
    """**断线兜底路径**（ADR-0049 §⑤ 约束 1）。
    pub/sub 不持久化 ⇒ 重连后靠这里拉未读。
    """
```

  ⚠️ 走 ADR-0049 §③ 的部分索引 `ix_notifications_recipient_unread (recipient_id, read_at)
  WHERE read_at IS NULL`。**`after` 参数要能命中这个索引**，否则 500ms 达不到 ——
  `EXPLAIN ANALYZE` 确认无全表扫。

- [ ] **Step 5: 回归 + commit**

```bash
uv run pytest tests/api/v1/test_ws_notifications.py tests/services/test_broadcaster.py -q
uv run python scripts/check_openapi_payload_coverage.py   # RC 必须 0
git add -A && git commit -m "feat(P9A): WebSocket 推送走 Redis pub/sub + /health realtime 降级信号"
```

---

---

### C3：ARQ 通知清理 + 失败注入

**Files:** Create `app/workers/notification_tasks.py`；Modify `app/workers/worker.py`
**Interfaces:** 复用既有 cron 写法（`worker.py:145-160` 的三个坑注释）

- [ ] **Step 1: 写失败测试**（TODO-016 的缺口，本阶段必须补）
  - `test_cleanup_failure_is_retried_not_silently_dropped` —— 构造 worker 抛异常，断言重试/DLQ
  - **注册断言**：`tests/workers/test_worker_registers_all_enqueued_tasks.py` 已存在
    （断言「入队的 ⊆ 已注册的」），把清理任务纳入。⚠️ **ARQ 对未注册的函数名不报错**，
    job 静静躺在队列里 —— 症状是「30 天后通知还在，且没人知道」。

- [ ] **Step 2: 实现**（`CronJob` **实例**不是 dict；后 13 个位置参数必填；

- [ ] **Step 1b: 补齐测试清单**（评审补）

```python
async def test_cleanup_failure_is_retried_not_silently_dropped(...):
    """TODO-016 的缺口。⚠️ 既有 cron 的 max_tries=1（worker.py:164,170）意味着
    **失败不重试** —— 通知清理必须显式设 max_tries >= 2，否则这条测试必红。"""
async def test_cleanup_task_is_registered_in_worker(...):
    """纳入既有 test_worker_registers_all_enqueued_tasks.py 的断言。
    ⚠️ ARQ 对未注册的函数名不报错，job 静静躺在队列里。"""
async def test_cron_job_is_instance_not_dict(...):
    """dict 会让 worker 构造就抛（worker.py:146-149 的血泪）。"""
async def test_cron_second_is_zero_not_none(...):
    """second=None 等于每秒命中，不是「不限」（worker.py:155-157）。"""
async def test_cleanup_only_deletes_read_and_expired(...):
    """30 天清理不得删未读通知 —— 那是删用户的东西。"""
async def test_cleanup_is_idempotent(...): ...
```
  **秒位写 `0`，传 `None` 等于每秒命中** —— `worker.py:155-157` 有血泪注释）

- [ ] **Step 3: commit**

---

---

### C4：待办实时计算

**Files:** Create `app/services/todo_service.py`；Modify `app/api/v1/deliverables.py`
**Produces:** `GET /api/v1/todos`（**不建表**，ADR-0049 §②）

- [ ] **Step 1: 写失败测试**（从 `steps_json` 当前步骤 × 用户角色重算；无 todo 行可过期）

- [ ] **Step 1: 写失败测试**

```python
async def test_todo_computed_from_current_step_role(...):      # steps_json × 用户角色
async def test_todo_empty_when_no_matching_role(...):           # 不是全部用户的 todo
async def test_no_persisted_todo_rows(...):
    """ADR-0049 §②：不建表 ⇒ 不该有任何行被写。「没有一行会过期」因为每次重算。"""
async def test_todo_reflects_signature_advance_immediately(...):
    """推进一步后，待办**立即**变化 —— 这是「实时计算」相对建表的全部意义。"""
async def test_todo_respects_project_scope(...):                # 越权不出现
async def test_todo_query_uses_partial_index(...):
    """⚠️ deliverables 现有索引里没有按用户/角色的（ADR-0049 §③）。
    EXPLAIN ANALYZE 断言无全表扫，否则 500ms 达不到。"""
```

- [ ] **Step 2: 500ms 验收 —— 分段计时，不加索引**（2026-10-19 D7 裁决）

> **为什么不加 `(project_id, deliverable_type)` 复合索引**（委员会约束 3 的适用场景）：
> 待办主查询**不过滤 `deliverable_type`** —— 签署矩阵按 `module` + `doc_type` 绑定
> （`signature_matrices`，`app/models/deliverable.py:150`），不是按 deliverable_type；
> `DeliverableType` 有 10 个值（`deliverable.py:51-54`），签署任务覆盖其中**所有绑了矩阵的**。
> 复合索引的第二列在主查询里不出现 ⇒ **白占写入开销与 schema 复杂度**。
> 现有索引已够：`ix_user_projects_active (user_id, project_id, revoked_at)`
> （`project.py:178`）+ `deliverables.project_id` 上的 index。
> 变更报警那条 `CHANGE_NOTICE` 是**子集**，在拿到 project 集合后 Python 过滤即可。

> ⚠️ **不要用 EXPLAIN 决定是否加索引**（委员会缺陷 1）：开发库 `projects=0`、
> `deliverables=0`（2026-10-19 实测）⇒ planner 在小表上**必然**选 Seq Scan，
> 加了索引后仍然 Seq Scan。**检测结果无法区分「缺索引」与「数据少」。**

```python
@pytest.mark.slow
async def test_todo_sql_and_parse_both_within_budget(...):
    """500ms 预算必须**分段**验证 —— EXPLAIN 只测 SQL，测不出 Python 解析 steps_json。

    SQL 查询（EXPLAIN ANALYZE）        <= X ms
    Python 解析 steps_json（计时）      <= Y ms
    两者之和                             <= 500 ms

    ⚠️ 不得用「EXPLAIN 走 Index Scan」当作性能达标的唯一判据：
    SQL 优化到 10ms 但 Python 解析 600ms 时，EXPLAIN 会绿而指标仍不达标。
    """
    t0 = perf_counter(); rows = await fetch_deliverables(...); t1 = perf_counter()
    todos = compute_todos(rows);        t2 = perf_counter()
    print(f'SQL {(t1-t0)*1000:.1f}ms  解析 {(t2-t1)*1000:.1f}ms')
    assert (t2 - t0) * 1000 <= 500

@pytest.mark.slow
async def test_todo_at_expected_data_volume(...):
    """⚠️ 小表下测不出真实性能。用生成数据造到**每 project 几百个 deliverable**
    的量级再测，否则 500ms 是假达标。"""
```

> **加索引的前置条件（写下来，将来触发时按此判断）**：
> 若真实数据量下测出超预算，**先确认瓶颈在 SQL 而非 Python 解析**；
> 确认后才考虑加索引，且加完必须**验证索引确实被 planner 选中** ——
> 「加了索引就假设它会被用到」是把 schema 变更当成性能保证。
> 若选择性不足（如 `CHANGE_NOTICE` 占 50%），复合索引无用，应改**部分索引**
> （`WHERE deliverable_type = 'CHANGE_NOTICE'`）。

⚠️ `deliverables` 现有索引里**没有任何按用户/角色的索引**（ADR-0049 §③）。
待办查询要先按「当前用户有权的 project」缩小集合 ⇒ **必须确认 `user_projects`
路径有可用索引**，否则 500ms 达不到。用 `EXPLAIN ANALYZE` 证明**无全表扫**。

- [ ] **Step 3: commit**

---
