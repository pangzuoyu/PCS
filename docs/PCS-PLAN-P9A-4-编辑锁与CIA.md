# P9A-4 编辑锁 + CIA 分流

> 本文件是 `docs/PCS-PLAN-P9A.md`（总纲）的 **D 号 lane**。
> 共享的 Global Constraints / Review Focus / 失败模式 在总纲，只写一遍。
> **前置**：D2（Redis 锁端点）与 D3（CIA 分流）无前置；**D1 编辑保存路径需 B 的保存端点** ⇒ D1 在 B 之后
> **本 lane 的完成判定**（与总纲 §完成标准 对应）：见文末。

---

### D0：迁移基座（`cost_est_results.record_hash` + 回填）

**Files:**
- Create: `pcs-backend/alembic/versions/p9_004_cost_est_record_hash.py`
- Modify: `pcs-backend/app/models/calc.py`（`CostEstResult.record_hash`）
- Test: `pcs-backend/tests/migrations/test_p9_004_cost_est.py`

**Interfaces:**
- Consumes: `compute_record_hash`（`app/services/calc_lineage.py:127`）
- Produces: `cost_est_results.record_hash: str | None`（String(16)）

> **为什么只补这一张**（2026-10-19 裁决收窄）：29 张 `*_result(s)` 表里 19 张已有
> `record_hash`；其余 11 张中 **`cost_est_results` 是唯一「可编辑 ∧ 无任何并发令牌」**的
> （`PATCH /results/{id}`，且**无 sign_status 门禁** ⇒「所有状态可 PATCH」）。
> `util_results` / `sim_*`(8) / `two_phase_results` **无手动编辑端点**，不需要兜底。
> 详见 ADR-0048 §⑥ 收窄表。**不引入 `row_version`** —— 会造第二套并发令牌。
>
> ⚠️ `cost_est_persist_service.py:15` 那条「不调用 finalize_calc_record」的注释
> **在本迁移后需要更新** —— 它当前是唯一防线，而**防线是注释不是代码**（TODO-048）。
> 补列后应改由代码保证（`finalize_calc_record` 显式校验）。

- [ ] **Step 1: 写失败测试**
- [ ] **Step 2: 跑测试确认红**

- [ ] **Step 3: ORM + 迁移**（单列，无 CHECK）

> 📌 **`String(16)` 的长度依据已核实**（2026-10-19）：
> `calc_lineage.py:102` `_HASH_PREFIX = 16`，`:153`
> `return hashlib.sha256(...).hexdigest()[:_HASH_PREFIX]` ⇒ **恰好 16 字符**。
> 若将来换成 `md5` 或 `blake2b` 而不同步改这一列，**截断后的 hash 与完整 hash 不等 ⇒
> 比对永远失败**。改算法时必须同查这一列。

- [ ] **Step 1b: 补齐测试清单**（评审补）

```python
def test_cost_est_has_record_hash_column(): ...
def test_record_hash_is_nullable_and_string16(): ...
async def test_backfill_covers_every_existing_row(...):
    """回填后 record_hash IS NULL 的行数 == 0。不回填则 D2 一律 no_baseline。"""
async def test_backfill_is_stable(...):
    """compute_record_hash 幂等（calc_lineage.py:132 的契约）：重跑两次 hash 不变。"""
async def test_backfill_matches_live_computation(...):
    """回填值 == 对该行现算的值 —— 防止用错函数或算在错误的列集合上。"""
```
- [ ] **Step 4: 回填存量 hash**（新列 nullable ⇒ 存量行为空，不回填则 D2 一律 `no_baseline`）

```bash
cd pcs-backend
uv run python -c "
import asyncio
from sqlalchemy import select
from app.db.session import get_async_session_factory
from app.models.calc import CostEstResult
from app.services.calc_lineage import compute_record_hash
async def main():
    async with get_async_session_factory()() as s:
        rows = (await s.execute(select(CostEstResult))).scalars().all()
        for r in rows:
            r.record_hash = compute_record_hash(r)
        await s.commit()
        print(f'回填 {len(rows)} 行')
asyncio.run(main())
"
```

- [ ] **Step 5: 双库验漂移 + commit**

```bash
git add -A && git commit -m "feat(P9A): cost_est_results 补 record_hash（唯一可编辑且无令牌的表）"
```

---
### D1：编辑锁 Redis 端点

**Files:** Create `app/api/v1/locks.py`、`app/services/edit_lock.py`
**Produces:** `POST /locks/{type}/{id}/acquire|release|renew`

- [ ] **Step 1: 写失败测试**

```python
async def test_acquire_grants_lock_to_first_caller(...): ...
async def test_acquire_returns_conflict_when_held(...):
    """他人持锁 ⇒ 返回持锁人信息，不是裸 409 —— 体验层的全部价值在此。"""
async def test_renew_extends_ttl_only_for_current_holder(...):
    """⚠️ 他人的心跳不得延长我的锁。"""
async def test_renew_rejects_expired_lock(...): ...
async def test_release_is_owner_only(...):
    """非持有者 release ⇒ 403，不得释放别人的锁。"""
async def test_lock_expires_after_ttl_without_heartbeat(edit_lock):
    """TTL 到期后锁自动释放（ADR-0048 §③）。

    ⚠️ **不要用「假时钟」或「查 TTL」**（2026-10-19 委员会必修）：
    - 假时钟：Redis 的 TTL 是**服务端**计算的，客户端无法 patch（freezegun 只管 Python 的 time）
    - 查 TTL：`TTL key` 只返回剩余秒数（如 1799），证明的是「当前还剩多久」，
      **不是**「到期后会释放」。要证明到期行为必须等它过期。

    ⇒ **TTL 是可注入参数**（ADR-0048 §② 的 30min 是默认值，不是硬编码），
    测试传短值。这不是为测试改实现 —— TTL 本来就该是配置项。
    """
    await edit_lock.acquire(..., ttl_seconds=2)
    assert await edit_lock.is_held(...) is True
    await asyncio.sleep(3)
    assert await edit_lock.is_held(...) is False


async def test_default_ttl_is_30_minutes(edit_lock):
    """别为了测试把默认值也改了 —— 生产仍须是 30 分钟（ADR-0048 §②）。"""
    assert edit_lock.DEFAULT_TTL_SECONDS == 30 * 60

async def test_redis_down_warns_and_allows_not_503(...):
    """ADR-0048 §⑤ + ekris-redis-lock-degradation 的裁定：
    Redis 不可用时**降级放行 + ERROR 日志 + 横幅**，不是 503。
    （若用户改判该 learning 为「必须事前拒绝」，此测试要改为断言 503 ——
      ADR §⑤ 写了可证伪条件。）"""
async def test_degradation_banner_mentions_no_conflict_detection_for_cost_est(...):
    """路由到 cost_est_results 时横幅须写「本次编辑无冲突检测」——
    它是唯一「可编辑 ∧ 无 DB 兜底」的表（裁决 1 + D0）。"""
async def test_acquire_does_not_consult_database(...):
    """锁是 UX 层，不得因 DB 慢而变慢 —— 否则 Redis 快也没用。"""
```

[→E2E] `test_two_sessions_one_holder` —— 两个真实会话抢同一记录，
断言第二个被拒。**真 Redis，不 mock**（内存替身不会复现 TTL 与 compare-and-expire）。

- [ ] **Step 2: 实现**（key = `lock:edit:{record_type}:{record_id}`，TTL 30min，心跳 60s）

- [ ] **Step 3: commit**

---

---

### D2：编辑保存 + 409 契约 + 编辑审计（共享 guard）

**Files:**
- Create: `pcs-backend/app/services/edit_guard.py`（**阶梯 + 409 + 审计的唯一实现**）
- Create: `pcs-backend/app/schemas/edit_conflict.py`（`ConflictResponse` 显式 schema）
- Modify: **6 个** persist service（清单见下，**不是 23 个**）
- Test: `tests/services/test_edit_guard.py`（阶梯只测**一遍**）、`tests/api/v1/test_edit_conflict.py`

**Interfaces:**
- Consumes: ADR-0048 §⑥ 退化阶梯 + §⑦ 契约（**三条强制约束**）、`compute_record_hash`
- Produces:
  - `TABLE_CAPABILITIES: dict[str, TableCapability]` —— **显式**声明每张可编辑表的并发令牌
  - `async def check_conflict(session, *, record_type, record_id, expected_hash,
    expected_updated_at) -> ConflictCheckResult` —— **纯检查，无副作用**
  - `async def record_edit_audit(session, *, record_type, record_id, user_id,
    changed_fields, overwrote_stale_baseline) -> None` —— **纯写审计**
  - `ConflictCheckResult(conflict: ConflictResponse | None, overwrote_stale_baseline: bool)`

> **DRY 的核心收益**：阶梯、409 判定、审计格式**只有一份实现**。
> 调用点 5~8 行，但按表定制的只有「提取上下文」和 `changed_fields` 计算。
> 与既有先例同形：`compute_record_hash` / `finalize_calc_record` 已经是「多 persist 路径
> 共享同一实现」的模式。

#### 接入清单（实测，**6 个不是 23 个**）

```bash
cd pcs-backend
grep -rn -A 2 '@router\.\(patch\|put\)(' app/api/v1/*.py | grep -B 1 '"/results'
```

| 端点 | 表 | record_hash | updated_at | 需 D0 补列？ |
|---|---|---|---|---|
| `cool_tower.py:355` | `cooling_tower_results` | ✅ | ✅ | — |
| `filtration.py:443` | `filtration_results` | ✅ | ✅ | — |
| `flare.py:478` | `flare_system_results` | ✅ | ✅ | — |
| `open_channel.py:505` | `open_channel_results` | ✅ | ✅ | — |
| `psychro.py:644` | `psychro_results` | ✅ | ✅ | — |
| `cost_est.py:376` | `cost_est_results` | ❌ | ❌ | ✅ **D0** |

> ✅ **列的核实命令**（执行时复跑一次，结果须与上表一致）：
> ```bash
> cd pcs-backend && uv run python -c "
> from app.db.base import Base; import app.models
> for n in ['cooling_tower_results','filtration_results','flare_system_results',
>           'open_channel_results','psychro_results','cost_est_results']:
>     c = Base.metadata.tables[n].columns
>     print(n, 'record_hash' in c, 'updated_at' in c)"
> ```
> 若某张表与上表不符 ⇒ `TABLE_CAPABILITIES` 会漏登记，`check_conflict` 抛
> `UnregisteredTableError`（这是**期望行为**，不是 bug —— 见约束 3）。
> 
> ⚠️ **从「有 PATCH/PUT 的端点」反查，不要从「所有 `*_persist_service.py`」正着数** ——
> 后者有 23 个，其中 17 个没有编辑路径，guard 根本不会被调用，改了也是无用改动 + 风险。

#### guard 的四条设计约束（2026-10-19 决策委员会 D5）

1. **拆成两个函数，不得合并。** `check_conflict` 发生在保存**前**（冲突则不保存、不写审计），
   `record_edit_audit` 发生在保存**后**。合并会导致「冲突时误写审计」或「保存失败时漏写审计」。
2. **`check_conflict` 返回 `ConflictCheckResult` 而非 `None`。** 它必须**同时**给出
   「是否冲突」与「本次保存是否覆盖了别人的改动」—— 后者由调用方在保存**之后**传给
   `record_edit_audit`。若只返回 `conflict`，每个调用点会各自发明传递方式，然后漂移。
   它**返回**而不抛异常：抛异常会让每个调用点都要 try/except。
3. **表能力用 `TABLE_CAPABILITIES` 显式映射，不用 ORM 反射。**
   反射把「ORM 有列」当成「表有能力」，而两者可能不一致 —— `cost_est_results` 现在就是这样
   （无列，但被登记进了 `RECORD_TYPE_REGISTRY`，见 TODO-048）。
   **漏登记要抛 `UnregisteredTableError`，不得静默走 `no_baseline`。**
   测试须断言「所有有编辑路径的表都在映射里」。
4. **`changed_fields` 是字段名列表，不是完整值。** 完整值进 `detail_json` 会让审计表
   膨胀（一次大改版几十 KB）；字段名足够 409 弹窗显示「改了哪」。

- [ ] **Step 1: 写失败测试** —— **阶梯只测一遍**（guard 内部），调用点只验「guard 被正确调用」

```python
# tests/services/test_edit_guard.py —— 阶梯的唯一测试处
async def test_empty_hash_falls_to_updated_at(...):        # pump/pipe/pipe_net 常态路径
async def test_null_updated_at_is_no_baseline_not_equal(...):
    """⚠️ NULL 当「相等」放行 ⇒ 从未计算过的记录完全无保护。"""
async def test_conflict_basis_has_three_values(...):
async def test_check_conflict_returns_overwrote_stale_baseline(...):
    """约束 2：返回 ConflictCheckResult，带 overwrote_stale_baseline。"""
async def test_check_conflict_is_pure(...):
    """约束 1：纯检查 —— 调用前后 audit_logs 行数不变。"""
async def test_unregistered_table_raises(...):
    """约束 3：漏登记抛 UnregisteredTableError，不静默走 no_baseline。"""

# tests/api/v1/test_edit_conflict.py —— 每个端点只验接线
async def test_cost_est_patch_conflicts_on_stale_hash(...):
    # 只验：guard 被调用 + 409 契约三字段 + changed_fields 正确传递
    # **不重复验阶梯**（那是 guard 的测试）
```

- [ ] **Step 2: 实现 `edit_guard.py`**（按上面四条约束）
- [ ] **Step 3: 接 6 个 persist 路径**（每处：提取上下文 → check → 保存 → 审计）
- [ ] **Step 4: `record_hash=''` 自检告警**（Review Focus ③）

真正的残留风险不是 persist→finalize 窗口（事务内，不可观测），而是**提交了但漏 finalize**
⇒ 行永久停在 `hash=""`。加一条定时扫描并告警。

- [ ] **Step 5: 回归 + commit**

```bash
uv run pytest tests/services/test_edit_guard.py tests/api/v1/test_edit_conflict.py -q
uv run python scripts/check_openapi_payload_coverage.py   # RC 必须 0
git add -A && git commit -m "feat(P9A): 编辑冲突共享 guard（三分支阶梯 + 409 契约 + 编辑审计）"
```

---

---

### D3：CIA 哈希判定分流 + `manual-adjust`

**Files:** Modify `app/api/v1/change_impact.py`
**Produces:** `POST /change-impact/{record_type}/{record_id}/confirm`（**与既有的
`confirm-recalc` 是两个端点** —— 后者无哈希判定分流，是 P1 交付的传播触发器）

- [ ] **Step 1: 写失败测试**

```python
async def test_unchanged_result_returns_no_change_without_credentials(...):
    """P9A-CIA-001：结果不变 → STALE_RESOLVED_NO_CHANGE，**免凭证**。"""
async def test_changed_result_requires_change_pending_credentials(...):
    """结果变化 → CHANGE_PENDING，须走签署链。"""
async def test_confirm_and_confirm_recalc_are_separate_endpoints(...):
    """⚠️ confirm 是**新端点**，confirm-recalc 是 P1 已有的**传播触发器**
    （change_impact.py:27，无哈希判定分流）。两者语义不同，不可合并。"""
async def test_confirm_reuses_cia_engine_hash_comparison(...):
    """复用 cia_engine.py:101 的比对范式，不另造概念。"""
async def test_manual_adjust_requires_permission_and_writes_audit(...):
    """P9A-CIA-002：manual-adjust 端点今天不存在，需新建；必须限权 + 审计。"""
async def test_stale_resolution_path_is_recorded(...):
    """走 no_change / pending 两条路径都要落 stale_resolution_path（mixins.py 有列）。"""
```

- [ ] **Step 2: 实现**（复用 `cia_engine.py:101` 的 record_hash 比对范式）

- [ ] **Step 3: commit**

---
