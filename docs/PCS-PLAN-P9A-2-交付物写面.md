# P9A-2 交付物写面 + workflow_progress 观测层

> 本文件是 `docs/PCS-PLAN-P9A.md`（总纲）的 **B 号 lane**。
> 共享的 Global Constraints / Review Focus / 失败模式 在总纲，只写一遍。
> **前置**：触发源在本 lane 内，但 `created_by` 需登录身份 ⇒ 与 A 可并行，收口时合流
> **本 lane 的完成判定**（与总纲 §完成标准 对应）：见文末。

---

### B0：迁移基座（`workflow_progress` 表 + 5 态枚举）

**Files:**
- Create: `pcs-backend/alembic/versions/p9_002_workflow_progress.py`
- Create: `pcs-backend/app/models/workflow_progress.py`
- Modify: `pcs-backend/app/models/enums.py`（`WorkflowProgressState`）
- Test: `pcs-backend/tests/migrations/test_p9_002_workflow_progress.py`

**Interfaces:**
- Consumes: `TimestampMixin` 三列纪律（`app/models/mixins.py:34-41`）
- Produces: 表 `workflow_progress`（8 业务字段 + 三列）+ `WorkflowProgressState` 5 态
  （PENDING / IN_PROGRESS / COMPLETED / SKIPPED / FAILED）
- ⚠️ **不建 `todos` 表** —— 按 ADR-0049 §② 走实时计算（C4）

- [ ] **Step 1: 写失败测试**（8 字段齐全 + 5 态齐全 + 三列纪律）
- [ ] **Step 2: 跑测试确认红** → **Step 3: ORM + 枚举** → **Step 4: 写迁移**

- [ ] **Step 1b: 补齐测试清单**（评审补，2026-10-19）

```python
def test_workflow_progress_columns_are_exactly_the_8_business_ones(): ...
def test_workflow_progress_inherits_timestamp_mixin_three():   # created_by/created_at/updated_at
def test_updated_at_is_nullable_and_has_onupdate():
    """TimestampMixin 纪律：updated_at 可空 + onupdate=func.now()（mixins.py:38-40）。"""
def test_created_at_has_server_default_and_timezone(): ...
@pytest.mark.parametrize("s", ["PENDING","IN_PROGRESS","COMPLETED","SKIPPED","FAILED"])
def test_state_enum_is_exactly_5_values(s): ...
def test_no_todos_table_exists():
    """ADR-0049 §②：todos **不建表**，走实时计算。建了就是第二个真相源。"""
    assert "todos" not in Base.metadata.tables
```

[→E2E] 不适用（纯 schema）。
- [ ] **Step 5: 双库验漂移**（同 C0 Step 5 的两条命令）
- [ ] **Step 6: commit**

```bash
git add -A && git commit -m "feat(P9A): workflow_progress 表迁移 + 5 态枚举（ADR-0047 §①）"
```

---
### B1：交付物 `issue` 端点

**Files:**
- Modify: `pcs-backend/app/api/v1/deliverables.py`
- Modify: `pcs-backend/app/services/deliverable_service.py`（现 169 行 / 4 个**读**方法，新增写方法）
- Create: `pcs-backend/app/schemas/deliverable_write.py`
- Test: `pcs-backend/tests/api/v1/test_deliverable_issue.py`

**Interfaces:**
- Consumes: `NumberingService.next_value`（已有，`app/services/numbering_service.py:42`）；
  `deliverables` / `deliverable_versions` 表（已有，无迁移）
- Produces:
  - `DeliverableService.issue(*, deliverable_id, version_purpose: str, actor_user_id) -> DeliverableVersionOut`
    —— **T5/T6 的前置**：只有 issue 产出的版本才能 sign
  - `DeliverableIssueResponse`（**显式声明**，零裸字段）—— 至少含
    `deliverable_id / version_id / rev / doc_no / version_purpose / sign_status / issued_at`
  - `POST /api/v1/deliverables/{deliverable_id}/issue`

- [ ] **Step 1: 写失败测试**（doc_no 原子分配不重复 / 版本目的合法 / 显式响应模型无裸字段）

- [ ] **Step 1: 写失败测试**

⚠️ `NumberingService.next_value` 已用 `SELECT ... FOR UPDATE` 行锁
（`app/services/numbering_service.py:52` 注释自陈「Postgres 串行化同 scope 并发取号」）
⇒ 原子性**已有**，但**没有任何测试证明它**。本 task 顺带补上。

```python
async def test_doc_no_unique_under_concurrent_issue(...):      # [→E2E] 见下
    """并发取号不撞号。依赖 next_value 的 FOR UPDATE 行锁。"""

async def test_doc_no_follows_numbering_template(...):          # 版本目的/模板映射
async def test_issue_rejects_invalid_version_purpose(...):     # 非法值 422
async def test_issue_rejects_unbound_project(...):             # 项目没绑矩阵
async def test_issue_creates_first_deliverable_version(...):    # rev 从 1 起
async def test_issue_is_idempotent_on_second_call(...):
    """重复 issue 同一版本目的 ⇒ 409，不是静默产生第 2 个版本。"""
async def test_issue_writes_created_by_from_current_user(...):  # 零裸字段
async def test_response_model_has_no_bare_fields(...):
    """P9A-DLV-010：DeliverableIssueResponse 必须显式声明。"""
```

[→E2E] `test_doc_no_unique_under_concurrent_issue` —— 用两个独立 session 并发
issue 同一 project，断言 `doc_no` 不重复。**真 PG，不 mock**（内存 SQLite 没有
`FOR UPDATE` 语义，会给假绿）。

- [ ] **Step 2: 确认红**

- [ ] **Step 3: 实现**

⚠️ **并发控制用 `numbering_service.next_value` 的原子序号**（SPEC P9A-DLV-003），
不要自己 `max(doc_no)+1` —— 后者在并发下必然撞号。

- [ ] **Step 4: 零裸字段自检 + commit**

```bash
uv run python scripts/check_openapi_payload_coverage.py   # RC 必须 0（不得从 71 上涨）
git add -A && git commit -m "feat(P9A): 交付物 issue 端点（doc_no 原子分配）"
```

---

---

### B2：`sign-step` 端点 + 观测写入点 ①

**Files:**
- Modify: `pcs-backend/app/api/v1/deliverables.py`
- Modify: `pcs-backend/app/services/deliverable_service.py`（新增 `sign_step`）
- Create: `pcs-backend/app/services/workflow_progress_writer.py`
- Test: `pcs-backend/tests/api/v1/test_deliverable_sign_step.py`、`tests/services/test_workflow_progress_writer.py`

**Interfaces:**
- Consumes: Task 4 的 `issue` 产物（`DeliverableVersionOut`）；
  `SignatureMatrix.steps_json`（`app/models/deliverable.py:159`）
- Produces:
  - `DeliverableService.sign_step(*, version_id, step_index, decision: str,
    actor_user_id, actor_role) -> SignStepOut`
    —— `decision` ∈ `SIGN / RETURN / SKIP`
  - `async def record_step(*, session, workflow_type, workflow_id, step_order,
    step_role, state, actor_user_id) -> None`
    —— **观测写入的唯一入口**，T5/T6/T7 三条工作流共用；**必须 service 层调用**
  - `POST /api/v1/deliverables/{id}/sign-step`
  - `WorkflowProgressState`（Task 1 的 5 态枚举）

- [ ] **Step 1: 写失败测试**，其中必须含一条**cron 等价断言**：

```python
@pytest.mark.asyncio
async def test_sign_step_writes_progress_via_service_not_api(session):
    """Review Focus ①：观测写入必须在 service 层。
    直接调 service（不经 API）仍要写 workflow_progress —— 否则 cron/事件驱动的
    调用路径会完全绕过观测层（cia_engine 的 cia_mark_stale 就是这种路径）。"""
    svc = DeliverableService(session)
    await svc.sign_step(...)
    rows = (await session.execute(select(WorkflowProgress.__table__))).scalars().all()
    assert rows, "service 直调必须仍然写观测"
```

- [ ] **Step 2: 确认红**

- [ ] **Step 3: 实现**（`workflow_progress_writer.record_step` 是唯一写入口，3 个工作流共用）

- [ ] **Step 4: 回归 + commit**

---

---

### B3：代录 `customer-approval/proxy` 端点 + 二次认证

**Files:** Modify `app/api/v1/deliverables.py`；Create `app/services/secondary_auth.py`
**Interfaces:**
- Consumes: `ldap_client.authenticate`（`:58`）、`customer_approval_attachments` 表（已有）
- Produces: `POST /api/v1/deliverables/{id}/customer-approval/proxy`；
  `verify_secondary_auth(*, session, username, password) -> None`

- [ ] **Step 1: 写失败测试**，含 ADR-0046 与 MFA 决议的**三条硬约束**：

```python
async def test_fallback_audit_action_is_not_sign_2fa_ok(session):
    """ADR 裁决 2 落地约束 1：审计 action 必须是 SIGN_2FA_FALLBACK。
    复用 SIGN_2FA_OK 会掩盖「我们没上真 MFA」这个事实。"""
    ...
    assert "SIGN_2FA_FALLBACK" in actions
    assert "SIGN_2FA_OK" not in actions


async def test_secondary_auth_is_not_exempt_for_mock_user():
    """MFA 裁决：豁免范围限定登录层，`verify_secondary_auth()` 函数本身不豁免。
    本测试**不经过 mock 登录路径** —— 否则 mock 全绿会被读成「二次认证验证过了」。"""
    with pytest.raises(PcsError):
        await verify_secondary_auth(session=session, username="alice", password="wrong")
```

- [ ] **Step 2: 确认红**

- [ ] **Step 3: 实现**

- [ ] **Step 4: 回归 + commit**

---

---

### B4：records 9 端点（4 接线 + 5 新建）

**Files:** Modify `app/api/v1/records.py`；Create `app/api/v1/comments.py`
**Interfaces:**
- Consumes: Task 1/2/5 已建；**已有的** `record_cancellation_service` / `reversal_approval_service` / `change_notice_service`
- Produces: 7 个 records 写端点 + `GET /deliverables/{id}/actions`

- [ ] **Step 0（🔒 阻塞，不得跳过）：核对 `approve_change_notice` 与 SPEC `abandon-change` 的语义**

> **这是本计划里唯一可能造成数据语义错误的地方。**
> `approve` 与 `abandon` 是**相反动作** —— 接错方向会让用户「批准」一个他以为在
> 「放弃」的变更。**不得因为函数名叫 approve 就假设它是「批准」——先读实现。**

```bash
cd pcs-backend
sed -n '260,360p' app/services/change_notice_service.py   # approve_change_notice 全文
grep -rn "abandon" ../spec/PCS-REQ-2026-002-SPEC-P9*.md
```

**判定**：
| 读到的语义 | 结论 |
|---|---|
| 「批准变更单、变更生效」 | **不等同** ⇒ `abandon-change` 需新建实现，**不要接线** |
| 「放弃变更、变更作废」 | 等同 ⇒ 可接线 |
| 读不出来 / 语义混合 | **停**，记入 ledger 并提请裁决，不许猜 |

**产出要求**：核对结论写进 B4 的 commit message。**无结论则 B4 不得开工。**
> ⚠️ 不要用「写个空测试占位」来代替这一步 —— 空测试永远绿，
> 会把「唯一可能造成数据语义错误的地方」伪装成已覆盖。

---

- [ ] **Step 1: 先核对再接线**（不要假设已有 service 的语义等于 SPEC 端点）

```bash
# 对每个待接线端点，读它的 docstring 确认：入参、状态机约束、返回值是否与 SPEC 一致
sed -n '126,190p' app/services/record_cancellation_service.py     # obsolete
sed -n '106,200p' app/services/reversal_approval_service.py        # request_reversal
sed -n '260,360p' app/services/change_notice_service.py            # abandon-change?
```
⚠️ **`approve_change_notice` 的语义是否等同 SPEC 的 `abandon-change` 必须人工确认。**
approve 与 abandon 是相反动作，**接错方向会让用户「批准」一个他以为在「放弃」的变更**。
若不等同 ⇒ 记入 ledger，另建实现。

- [ ] **Step 2: 每个端点走 TDD**（失败测试 → 实现 → 绿 → 单独 commit）

**测试清单（7 个端点，评审补）** —— 逐端点，**不写「同 Task 1」的占位**：

```python
# ---- 4 个接线端点（接已有 service）：测「端点层契约」，不重测 service 逻辑
# （service 已有约 450 行测试，见 tests/services/test_{reversal_approval,
#    record_cancellation,change_notice_service}.py）
async def test_obsolete_endpoint_returns_409_when_bound_to_deliverable(...):
    """BoundObsoleteError（record_cancellation_service.py:24）→ 409，不是 500。"""
async def test_request_reversal_requires_active_snapshot(...): ...
async def test_reversal_decision_approve_and_reject_both_reachable(...):
    """**approve 与 reject 是相反动作** —— 两个分支都要端到端测，
    否则会出现「只接通 approve、reject 永远 500」的半成品。"""

# ---- 3 个新建端点
async def test_submit_approval_advances_step_and_respects_depth(...):
    """按批准深度显示 Step n/N；深度耗尽后拒绝。"""
async def test_submit_approval_rejects_self_check_when_forbidden(...):
    """can_self_check=false 时提交人==设计人 ⇒ 403。"""
async def test_approval_step_returns_only_allowed_transitions(...):
    """不该暴露非法转移 —— 非法集合应在服务端裁掉，不靠前端过滤。"""
async def test_comments_are_project_scoped_and_paginated(...): ...
async def test_comments_reject_empty_body(...): ...
async def test_actions_endpoint_lists_audit_derived_history(...):
    """⚠️ 数据源未定（见「尚未解决」2）—— 先钉住测试，
    实现时若改数据源，这个测试的期望值要同步改。"""
```

[→E2E] `test_sign_to_reversal_full_journey` —— 签署到撤销的完整用户旅程，
跨 `deliverable_service` + `state_machine` + `reversal_approval_service` 三个 service。
单测各自绿但链路断（事务边界没对齐）只有 E2E 能抓。

- [ ] **Step 3: 零裸字段自检**

⚠️ **`records.py` 现有 6 个路由全部是 `response_model=dict` / `list[dict]`**
（`records.py:40,78,116,167,219,270`）。P9A-DLV-010 只约束**新增**，但既有 6 个
裸 `dict` 会计入 71 基线。**不要顺手改**（那是 TODO-039/041 的债，不在本阶段）。

- [ ] **Step 4: commit**

---

---

### B5：观测层读 API + 500ms 验收

**Files:** Create `app/api/v1/workflow_progress.py`、`app/schemas/workflow_progress.py`
**Produces:** `GET /api/v1/workflow-progress/{workflow_type}/{workflow_id}`

- [ ] **Step 1: 写失败测试**（显式响应模型；甘特图所需的 5 态齐全）

- [ ] **Step 1: 写失败测试**

```python
async def test_response_model_declares_every_field(...):       # 零裸字段
async def test_returns_all_five_states(...):                   # 甘特图要 5 态齐全
async def test_unknown_workflow_returns_404(...):              # 不静默空数组
async def test_read_api_is_project_scoped(...):
    """越权读到别的项目的进度 ⇒ 404（check_record_access_or_404 的既有惯例）。"""
async def test_progress_rows_ordered_by_step_order(...):       # 甘特图依赖顺序
```

- [ ] **Step 4: 500ms 验收（SPEC P9A-OBS-004）—— 实测，不接受「同步写所以快」**

```python
@pytest.mark.slow
async def test_observed_p99_under_500ms(...):
    """状态变更 → 观测行可查，p99 <= 500ms。必须打印实测值，不许只断言通过。"""
```

- [ ] **Step 2: 实现**

- [ ] **Step 3: 500ms 验收（SPEC P9A-OBS-004）**

```bash
# 必须实测，不接受「同步写所以很快」的论证
uv run python -c "
import asyncio, time
...  # 见下方验收清单
"
```
验收清单：① 三条工作流均有写入；② 写入到可查的 p99 ≤ 500ms；③ **cron 驱动的变更也有观测**。

- [ ] **Step 4: commit**

---

---

## 后续（2026-10-26 · TODO-080）：`approve_change_notice` 已删除

⚠️ **本计划里提到的 `ChangeNoticeService.approve_change_notice` 现已删除**
（连同死代码 `_apply_record_resolution`）。

**为什么删而不是修**（当时 R-1 只说「不再作为审批入口、保留为内部『关记录』步骤」
⇒ 实施时发现它**绕过矩阵**（谁都能直接批准 ⇒ 3 级校审形同虚设）**且连记录都不
关**（用了它记录永远停在 CHANGED）⇒ 留着就是一条「看起来能用、其实破坏签署链」
的路）。

⇒ **变更单的关闭路径现在唯一** = `sign_step` 签完最后一步（置 APPROVED）⇒
`close_on_approved` ⇒ 记录 CHANGED → CHECKED + 写观测 + 写通知行。
⚠️ 审批通过的通知逻辑原先**只在**被删的方法里 ⇒ 真实路径**从不通知任何人**
⇒ 随删除**迁到** `close_on_approved`。
