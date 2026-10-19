# ADR-0048：编辑锁 —— Redis 为主 + DB 审计留痕

- Status: **accepted**
- Date: 2026-10-19
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/services/advisory_lock.py`、`app/core/config.py`、`app/workers/`、`app/models/mixins.py`
- Informed: P9A 实施者、P9B 并发控制前端
- Supersedes: —
- Superseded by: —
- Related: P9-OPEN-009、SPEC §3.2.5 P9A-LCK-001~005、
  **ekris-redis-lock-degradation（2026-04-09，user-stated）—— 见 §⑤ 的显式关系声明**、
  ADR-0041 §编号预留（故取 0048）

## 背景

`app/services/advisory_lock.py` 提供两个 `pg_advisory_xact_lock` 封装，但它们
**都不能直接当编辑锁**：事务结束即释放，无 TTL、无持有者身份、无心跳、无续期。
编辑锁需要「跨请求存活 30 分钟并在超时后自动释放」。

Redis 已在栈内（`app/core/config.py:43` `redis_url`、`app/workers/`、
`app/services/report/arq_queue.py`），不是新引入的基础设施。

## 决策

### ① 存储：Redis

Redis 存锁（`lock:edit:{record_type}:{record_id}`，value = 持有者 user_id + 获取时刻），
**理由**是编辑锁的语义是「租约」，天然需要 TTL 与原子续期 —— 这正是 Redis 的形状。
DB 表做不到「30 分钟后自动过期」而不写清理任务。

**DB 保留审计留痕**：锁的 acquire/release 写 `audit_logs`，供 P9B 审计页与事后追溯。
审计记录**不参与**锁判定（审计可延迟，锁不能）。

### ② 自动续期

前端心跳默认 60s 一次（SPEC §2.5），打 `POST /locks/{type}/{id}/renew`，
后端 `SET key value EX 30 NX` 语义下的 compare-and-expire 重置 TTL。

心跳频率取 60s 而非更短：TTL 30min 对 60s 心跳有 30 倍余量，网络抖一次不会失锁；
而 10s 心跳在多人编辑时是白烧的往返。**心跳停止 = 30 分钟后自动释放**，不需客户端显式解锁。

### ③ 超时清理

Redis TTL 30 分钟自动清理，无需定时任务。

### ④ 与状态机事务的关系

**解耦。** 编辑锁是 UX 层的互斥（防两人同时改一版），不是业务正确性的保证。
状态机转移的正确性由 `state_machine.py` + `audit_logs` 负责，**不依赖编辑锁存在**。

因此：持有锁不提交状态变更 ⇒ 不阻塞他人；他人无锁提交状态变更 ⇒ 合法。
推论：**不得**把「无编辑锁」当作状态转移的前置条件。

### ⑤ Redis 不可用时的降级 —— 两层锁：Redis 是体验层，DB 是正确性层

> **本条与 `ekris-redis-lock-degradation`（2026-04-09，user-stated，confidence 9/10）的关系**
>
> 该 learning 原文：「If Redis unavailable, must return 503 immediately.
> **No lockless concurrent allowed.**」
>
> **裁定已作出（2026-10-19，用户）**：该 learning 的语义为「禁止**无保护**下的并发」
> 而非「必须事前拒绝」—— 事后检测（乐观比对）同样构成并发保护，不是 lockless。
> 故采纳下面的双层方案，而非 fail-closed。
>
> **本条的可证伪条件**：若用户日后把该 learning 改判为「必须事前拒绝」
> （事后检测不算），则 §⑤ 作废、改为 fail-closed（503），§⑥/§⑦ 随之作废。
> 此条件已由用户裁定，不留给后续 ADR 作者重新解释。

```
        ┌──────────────────────────────────────────────┐
Redis   │ 编辑锁（悲观，事前拒绝）                      │
层      │  体验：他人持锁时直接只读，看得到持锁人是谁     │
        │  失效后果：无（仅体验降级）                   │
        └──────────────────────────────────────────────┘
                            ↓ Redis 不可用时才落到这层
        ┌──────────────────────────────────────────────┐
DB      │ record_hash 比对（乐观，事后检测）            │
层      │  正确性：保存时发现已被他人改动 → 409          │
        │  失效后果：见 §⑥ 的覆盖缺口（分表而异）        │
        └──────────────────────────────────────────────┘
```

**Redis 不可用时：编辑锁降级**（前端横幅「锁服务不可用，保存时可能冲突」），
**保存路径仍由 DB 层兜底**。不是无锁放行 —— 放行的是**体验**，拦住并发的是 DB。

> ⚠️ **「拦住并发的是 DB」这一保证只对 §⑥ 表中的 19 张表成立**（决策委员会 2026-10-19 指出，
> 本段原读起来像全覆盖的保证，与 §⑥ 的实测缺口矛盾）。
>
> 实测：**10 张表没有 `record_hash`**（`sim_*`(8) / `util_results` / `cost_est_results`），
> 其中 **9 张连 `updated_at` 也没有** ⇒ 对它们，Redis 降级后**DB 兜底不成立**，
> 每次编辑保存都落 `no_baseline`。另有 `two_phase_results` 有 hash 但**无 `updated_at`**，
> 退化阶梯缺第二档。
>
> ⇒ **这 11 张表的编辑并发保护是 P9A 的未决迁移决策**（见「尚未解决」1），
> 在该决策落地前它们**没有 DB 兜底**。
>
> **前端要求**：Redis 降级横幅不能是全局一句话。对落在上述 11 张表的记录，
> 横幅须额外提示「**本次编辑无冲突检测**」（而不是让用户以为有 DB 兜底）。
> 这不是可选的措辞优化 —— 用户在无保护状态下编辑，**必须知道**。

告警走日志 ERROR + P9B 前端顶栏横幅。

推论（对 §④ 的加强）：**不得**把「持有编辑锁」当作任何写入的前置条件；
正确性由 §⑥ 的比对保证，不由锁保证。

### ⑥ 兜底粒度：per-record，复用 `record_hash`（多数表零迁移，但**不是全覆盖**）

**首选令牌 = `RecordMixin.record_hash`**（`app/models/mixins.py`），**不新增列**。
两条已核实的事实支撑这个选择：

1. `record_hash` 由 `RecordMixin` 提供，业务结果表多数已有
   （实测：29 张 `*_result(s)` 表中 **19 张有** `record_hash`）⇒ 这 19 张**零迁移**。
2. **比对范式已存在**：`app/services/cia_engine.py:101` 已在做「当前 record_hash 与
   `data_lineage` 最新 hash 比对」（change-impact 用）。复用同一范式，不新造概念。

> ⚠️ **「全部 21 张表零迁移覆盖」是错的，2026-10-19 实测更正。**
> 实测 29 张业务结果表里 **10 张没有 `record_hash` 列**：
>
> | 表 | 有 record_hash | 有 updated_at | 属哪一类 |
> |---|---|---|---|
> | `sim_tower_results` / `sim_unit_op_results` / `sim_calculator_results` / `sim_compressor_results` / `sim_cstr_results` / `sim_reactor_results` / `sim_splitter_results` / `sim_stca_results`（8 张） | ❌ | ❌ | SIM 导入结果（`created_at` 单列） |
> | `util_results` | ❌ | ✅ | 公用工程消耗汇总 |
> | `cost_est_results` | ❌ | ❌ | 造价估算 |
>
> **另有 1 张有 hash 但无 `updated_at`**：`two_phase_results`（有 `record_hash`，
> 时间列只有 `created_at`）⇒ 它的退化阶梯里**没有第二档令牌**。
>
> ⇒ **结论**：兜底覆盖**按表而异，必须逐表声明**，不能笼统说「零迁移全覆盖」。
> 上面 10 张 + `two_phase_results`（合计 **11 张**）若 P9A 要对其做编辑并发保护，
> **需要新列**（`record_hash` 或一个通用 `row_version`）—— 这是本 ADR 未消除的欠账，
> 已在「尚未解决」登记。
>
> **复核命令（数字不要手数）**：
>
> ```bash
> cd pcs-backend
> uv run python -c "
> from app.db.base import Base
> import app.models
> res=[(t.name,'record_hash' in t.columns,'updated_at' in t.columns)
>      for t in Base.metadata.sorted_tables
>      if t.name.endswith('_result') or '_results' in t.name]
> print('总', len(res), '| 有 hash', sum(h for _,h,_ in res), '| 无 hash', sum(not h for _,h,_ in res))
> print('有 hash 无 updated_at:', [n for n,h,u in res if h and not u])
> print('两者都无:', [n for n,h,u in res if not h and not u])
> "
> ```
>
> 期望输出：`总 29 | 有 hash 19 | 无 hash 10` / 有 hash 无 updated_at: `['two_phase_results']`
> / 两者都无: 9 张。
> ⚠️ 本 ADR 初稿手数写成了「18 / 11 / 12」，三个数全错。**表覆盖率必须用脚本枚举。**

> ⚠️ **「`finalize_calc_record` 是唯一收口」也是错的，2026-10-19 实测更正。**
> `app/services/calc_lineage.py:156` 的 `finalize_calc_record` **不是** `record_hash`
> 的唯一写入点。实证旁路：
>
> | 路径 | 行为 | 对兜底的影响 |
> |---|---|---|
> | `heat/thermosiphon_persist_service.py:166`、`cv/cv_persist.py:189`、`restriction/restriction_persist.py:184` | 直接调 `compute_record_hash()`，不经 finalize | 写入**正确** hash ⇒ 兜底照常生效 |
> | `pump/pump_chain_persist.py:191`、`pipe/pipe_chain_persist.py:200`、`pipe_net/pipe_net_persist.py:113` | persist 时先 `record_hash = ""`，指望后续 finalize 填充 | **空 hash ⇒ 落到下方退化分支** |
>
> 前一类无害，后一类意味着 **`updated_at` 不是罕见边角，而是 pump / pipe / pipe_net
> 三类记录的常态路径**。实施时这三类记录的冲突检测依赖 `onupdate`，不是依赖 hash。

#### 这三类在 persist → finalize 之间到底有没有保护窗口？（实测结论）

先答一个必须答清的问题：这三类记录的 `record_hash = ""` 窗口，**是不是一个可观测的无保护期**？

**实测：不是。** 窗口是**事务内**的，任何并发会话都看不到它：

```
pump_chain_persist.py:191   row.record_hash = ""
                    :193     db.add(row); await db.flush()      ← INSERT，updated_at 仍为 NULL
                    :195     await finalize_calc_record(...)    ← 同一事务内，无 commit
calc_lineage.py:179          record.record_hash = compute_record_hash(record)
                    :183     tracker.track(...) 内部 flush      ← UPDATE，onupdate 触发，updated_at 落值
```

`finalize_calc_record` 的 docstring 明写「本函数 **不 commit**（flush 由 LineageTracker
内部完成），提交由调用方控制」。**两次 flush 之间没有 commit ⇒ 没有别的会话能读到
`hash=""` 的行。** 三张表（`pump_results` / `piping_results` / `pipe_network_results`）
也都在 §⑥ 表中的 19 张里，且**都有 `updated_at`**。

⚠️ 顺带纠正一个容易顺手写下的说法：**不能说「窗口内走退化阶梯第二档」** ——
INSERT 不触发 `onupdate`，那一瞬 `updated_at` 是 **NULL**，落的是 `no_baseline` 不是第二档。
之所以不构成问题，是因为那个状态根本不可观测。

> **真正的残留风险不是窗口，是「提交了但没 finalize」**：若某个调用方改了
> `record_hash = ""` 却漏掉 `finalize_calc_record` 而直接 commit，该行就**永久**停在
> `hash=""` + `updated_at=NULL`（若是全新 INSERT）⇒ 落 `no_baseline`。
> P9A 加审计 `RECORD_EDIT_OVERWROTE_STALE_BASELINE` 时应能看见这类行；
> 建议 P9A 顺带加一条**自检**：定期扫 `record_hash = ''` 的行并告警
> （这是「计算结果已落库但哈希从未生成」的可靠信号）。

**粒度 = per `{module}/{record_id}`**，与 Redis 锁粒度一致。
不做「事务内多行独立 version」—— 交付物侧 `issue` 跨表事务
（改 Deliverable + 写 DeliverableVersion + 写绑定 + 写 workflow_progress）
的并发控制已由 **P9A-DLV-003 的 doc_no 原子序号分配**承担，
不需要 record_hash 重复覆盖。

**已知覆盖缺口（写明，不掩盖）**：`record_hash` 注释写明「仅设计参数参与」，
且 `compute_record_hash` 排除自身与生命周期列（`created_at` / `created_by` / `updated_at`）。
因此它**不检测** `sign_status` / `approval_step` 等批准状态字段的变化。

这是**正确的职责切分**：编辑锁保护「设计内容正在被改」，不保护「批准状态」。
批准状态的并发由状态机事务 + `pg_advisory_xact_lock`（`app/services/advisory_lock.py`）
负责，两者不重叠。

**退化处理（必须实现，不得省略）**：`record_hash` 是 `nullable=False, default=""`，
**未计算过的记录是空串**。两个空串相等 ⇒ 冲突检测失效。故：

```
保存请求带 expected_hash（+ expected_updated_at）
  ├─ 当前 record_hash != "" 且 != expected_hash  → 409 CONFLICT (basis=record_hash)
  ├─ 当前 record_hash == expected_hash           → 放行（正常路径）
  └─ 当前 record_hash == ""                       ← pump/pipe/pipe_net 常态
       ├─ 有 updated_at 且 != expected_updated_at → 409 CONFLICT (basis=updated_at)
       ├─ 有 updated_at 且 == expected_updated_at → 放行
       └─ 无 updated_at（two_phase_results，及上表 9 张连 updated_at 也没有的）
           且客户端也没给基线                       → 409 (basis=no_baseline)
```

⚠️ `updated_at` 是 `nullable` 且只在 UPDATE 时刷新（`onupdate=func.now()`）。
新建后从未被 UPDATE 过的记录 `updated_at` 为 NULL ⇒ 必须走 `no_baseline` 分支，
**不得**把 NULL 当「相等」放行 —— 那会让从未计算过的记录完全无保护。

### ⑦ 409 冲突响应契约

冲突是**预期路径**，不是异常。契约必须让前端知道该做什么。

**状态码** `409`。**不得** 500（用户无从下手），**不得** 200 + 空体。

**响应体**（受 P9A-DLV-010 零裸字段约束，字段必须显式声明）：

```json
{
  "error_code": "RECORD_EDIT_CONFLICT",
  "message": "该记录已被他人修改，请刷新后重新编辑",
  "conflict": {
    "record_type": "PipingResult",
    "record_id": "…uuid…",
    "your_expected_hash": "…16 hex…",
    "current_hash": "…16 hex…",
    "changed_by": "…uuid… 或 null…",
    "changed_at": "2026-10-19T10:22:31+08:00 或 null",
    "basis": "record_hash | updated_at | no_baseline"
  }
}
```

- `basis` 三值对应 §⑥ 三条判定分支 —— 让前端能区分「别人改了」（刷新有用）
  与「记录没基线」（刷新没用，应联系管理员）。

**`changed_by` / `changed_at` 的契约约束（三条，强制）**：

1. **只在 `audit_logs` 中确实对应「本次编辑写入」的条目存在时才填**，否则置 `null`。
   **不得**用「该记录最近一条审计」这种泛匹配去凑。
2. **不得**用 `updated_at` 冒充 `changed_at` —— `updated_at` 是行级时间戳，
   只说明「这行被改过」，不说明「是谁改的」。用它填会让弹窗说
   「该记录已被 X 于 **上一次别人修改的时间** 修改」，这是**精确性伪装，比 null 更有害**。
3. 若产品要求 409 弹窗显示修改人，**P9A 必须为编辑保存补审计**。
   这是产品需求 → 实现的单向依赖，**不要**在实现阶段才发现做不到而回退成「显示不出修改人」。

> **为什么第 1 条这么严（背景，非约束）**：编辑保存路径今天**不存在** ——
> `records.py` 现有 6 个路由里没有改内容的 PUT/PATCH（`POST /piping/{id}/transition`
> 与 `DELETE` 走的是 `StateMachineService.transition()`，那是**状态流转**，不是编辑保存）。
> 所以「编辑保存写不写审计」是 **P9A 的新决策**，不是可查证的既有事实。
> 若 P9A 不补这条审计，`audit_logs` 里只有状态流转与锁 acq/rel，
> 「最近一条审计」很可能与本次编辑**无关** ⇒ **把冲突归因给错误的人** ——
> 而这比 `null` 更糟：`null` 让用户知道「系统不知道是谁」，
> 错误归因会让用户去质问一个无辜的人。

**审计**：409 本身**不写** `audit_logs`（读侧拒绝，非状态变更）。
但**无锁期间保存成功且 `expected_hash` 与库中上一值不符**时，
必须写一条 `action = RECORD_EDIT_OVERWROTE_STALE_BASELINE`。
这条审计是事后能看见「谁在锁失效期间覆盖了别人」的**唯一**途径。

**前端交互**：409 → 弹窗「该记录已被 X 于 Y 修改」，两个动作：
「查看差异」/「放弃我的修改并刷新」。**不得自动重试**（会无限循环覆盖）。

## 顺带发现的独立缺陷（本 ADR 只登记，不在 P9-Prep 修）

`app/services/advisory_lock.py:27-28` 的 `acquire_record_lock` 用
`abs(hash(record_table))` / `abs(hash(record_id))` 取 classid/objid。
**Python 的 `str.__hash__` 默认按进程随机加盐（`PYTHONHASHSEED`）**，
多 worker 部署下同一 `(table, id)` 在不同进程得到不同 key ⇒ **跨进程根本不串行**，
`pg_advisory_xact_lock` 静默失效。

同文件 `acquire_equip_list_lock` 用的是 PG 侧 `hashtext(:key)`（`:67`），
跨进程一致 —— 是对的。

**处置**：本 ADR 不改（属 P7 状态机范畴，且改动面在已验收代码里）。
登记到 `TODOS.md`（TODO-047），归属 P9A-LCK 或独立修复。
裁定方向：**统一到 `hashtext()`**。

## 尚未解决

1. **上表 10 张无 `record_hash` 的表 + `two_phase_results`（合计 11 张）的兜底令牌未裁决。**
   > 计数由脚本枚举得出，不是手数（见 §⑥ 下方复核命令）：
   > `29 张 *_result(s)｜19 有 record_hash｜10 无｜two_phase_results 有 hash 无 updated_at`。
   > 其中 **9 张连 `updated_at` 也没有**（10 张无 hash 的里除 `util_results` 外全都没有）。
   §⑥ 的退化阶梯对它们只能落到 `no_baseline`（= 每次保存都 409，或需明确放行策略）。
   是给这 11 张补 `record_hash`、还是引入一个通用 `row_version` 整数列（所有表都加），
   属 P9A 的迁移决策，本 ADR 只声明覆盖缺口，不预选方案。
2. **`record_hash` 不检测批准状态字段**（`sign_status` / `approval_step`）。
   若 P9A 实施时发现签署流程本身也需要并发保护（而不只是编辑），
   **本 ADR 不覆盖该场景**，需回本 ADR 修订。
3. **「编辑保存」是否写 `audit_logs` 未裁决**（契约约束见 §⑦ 三条，此处只记未决部分）。
   编辑保存路径今天**不存在**（`records.py` 无改内容的 PUT/PATCH），所以这不是可查证的
   既有事实，是 P9A 的新决策。**未决的是「要不要补这条审计」**；
   补了之后怎么填是已定的 —— 严格按 §⑦ 三条，不满足就置 `null`。
