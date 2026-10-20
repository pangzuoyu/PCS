# ADR-0048：编辑锁 —— Redis 为主 + DB 审计留痕

- Status: **accepted**
- Date: 2026-10-19
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/services/advisory_lock.py`、`app/core/config.py`、`app/workers/`、`app/models/mixins.py`
- Informed: P9A 实施者、P9B 并发控制前端
- Supersedes: —
- Superseded by: —
- Related: P9-OPEN-009、SPEC **§6.21 EditLockIndicator**（P9A-LCK-001~005，2026-10-20 D1 补写 —— 此前这条引用指向的条款**根本不存在**）、SPEC §3.2.2 `P9A-ADM-001/002`（停用入口，2026-10-19 补）、
  **ekris-redis-lock-degradation（2026-04-09，user-stated）—— 见 §⑤ 的显式关系声明**、
  ADR-0041 §编号预留（故取 0048）、`TODOS.md` TODO-048（`RECORD_TYPE_REGISTRY` 名不副实）

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
> 其中 **9 张连 `updated_at` 也没有**；另有 `two_phase_results` 有 hash 但**无 `updated_at`**。
>
> 🔻 **但「有缺口」≠「需要补」。** 经 2026-10-19 裁决收窄（见 §⑥ 收窄表）：
> **这 11 张里只有 1 张真的需要补** —— `cost_est_results`，因为它是**唯一**
> 「可编辑（`PATCH /results/{id}`，且无 sign_status 门禁）∧ 无任何并发令牌」的表。
> 其余 10 张**没有手动编辑端点**，保护一个不存在的并发是死代码。
>
> ⇒ **`cost_est_results` 在 P9A 补列之前没有 DB 兜底**，这是本 ADR 交给 P9A 的**唯一**实际缺口。
>
> **前端要求**：Redis 降级横幅不能是全局一句话。对 `cost_est_results` 的记录，
> 横幅须额外提示「**本次编辑无冲突检测**」（而不是让用户以为有 DB 兜底）。
> 这不是可选的措辞优化 —— 用户在无保护状态下编辑，**必须知道**。
>
> **🔻 2026-10-20 D1/D2 落地口径（实现说明）**：横幅里「本次编辑无冲突检测」这半句
> 由 **`GUARDED_TABLES`（`app/services/edit_guard.py`）**决定 —— 即「该表的
> 保存路径**已接上** DB 层冲突检测」，**不是**「该表有 record_hash 列」。
>
> 理由：横幅是给用户的**事实陈述**。
>
> - **D1 阶段**（D2 未接线）：任何表的保存路径都没有冲突检出能力 ⇒ 所有表
>   都带这半句（对 `cost_est_results` 而言与本节的要求一致）。
> - **D2 之后**：6 张可编辑表的保存路径**全部**接上了 guard ⇒
>   `GUARDED_TABLES` = 6 张表 ⇒ 这半句**对它们都不再出现**。
>   ⇒ **本节「对 `cost_est_results` 的记录，横幅须额外提示『本次编辑无冲突
>   检测』」自 D2 起不再成立** —— 它的前提是「cost_est 没有 DB 兜底」，
>   而 D0 补了 `record_hash`、D2 接了 guard，前提已消失。
>   横幅机制**保留**（`GUARDED_TABLES` 仍是单一来源）：将来若新增一张
>   「可编辑 ∧ 未接线」的表，它会**自动**带上这半句。


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
> **🔻 2026-10-19 裁决收窄：「11 张」是计数口径，不是施工口径。**
> 补列的**前提是有手动编辑路径** —— 没有编辑场景，并发保护保护的是一个不存在的并发。
> 实测全部写端点（`grep -rnE '@router\.(put|patch)\([^)]*results' app/api/v1/*.py`）：
>
> | 表 | 手动编辑端点 | 需不需要兜底 |
> |---|---|---|
> | `flare_results` / `cooling_tower_results` / `psychro_results` | ✅ `PATCH /results/{id}` | ❌ 已有 hash + updated_at，**已全覆盖** |
> | **`cost_est_results`** | ✅ `PATCH /results/{id}`（`cost_est.py:376`），**且无 sign_status 门禁** —— 注释原文「所有状态可 PATCH」 | 🔴 **唯一需要补的** |
> | `util_results` | ❌ `util.py` 只有 GET + POST | 不需要 |
> | `sim_*` 8 张 | ❌ `sim_imports_query.py` **全是 GET**（expired / detail / preview / warnings） | 不需要 |
> | `two_phase_results` | ❌ 无编辑端点 | **不需要** —— 从覆盖缺口移除 |
>
> ⇒ **施工范围 = 1 张表：`cost_est_results` 补 `record_hash` + 接 `finalize_calc_record`。**

> **🔻 2026-10-20 D0 落地时的两条形状裁决**（P9A-4 D0）：
> 1. **列形状 = `String(64)` NOT NULL default `''`**，与全库另外 **25 张**
>    `record_hash` 表**完全同形**。计划原文写的 `String(16)` + nullable 被否决：
>    16 是**值**的长度（`calc_lineage._HASH_PREFIX`）不是列宽；空串是「未计算」
>    的唯一哨兵（本节下面的退化阶梯就是按 `record_hash == ""` 写的），
>    用 NULL 会让阶梯漏判。守卫：
>    `tests/alembic/test_p9_006_cost_est_record_hash.py`
>    `test_every_record_hash_column_in_the_repo_has_the_same_shape`。
> 2. **回填做进迁移**，不留「记得手工跑一次脚本」的后门（本仓吃过
>    「守门没跑却看着是绿的」亏）。回填复用 app 侧唯一的哈希实现
>    （`calc_lineage.compute_record_hash`），**不在迁移里复制第二份算法**。
> 它是**唯一「可编辑 ∧ 无任何并发令牌」**的表，且因为无签署态门禁，
> 它恰恰是 Redis 降级时最容易被两人同时改的那张。
>
> 🔎 **`RECORD_TYPE_REGISTRY` 的语义澄清（2026-10-19 实测，影响本节的论证措辞）**：
>
> 有人会以为「`CostEstResult` 已在 `RECORD_TYPE_REGISTRY` 里，所以补 `record_hash` 列是
> **补一个漏掉的必备列**」。**不是。** 实测三条：
>
> | 查什么 | 结果 |
> |---|---|
> | `RECORD_TYPE_REGISTRY` 是什么类型？ | `dict[str, type]` —— 纯「名称 → 类」映射 |
> | `finalize_calc_record` 体内引用它几次？ | **0 次** —— 它靠鸭子类型（`record.record_hash = ...`），**从不查注册表** |
> | `app/` 里除定义与 `__all__` 外的消费者？ | **0 个** —— 只有测试断言它的成员与数量 |
>
> ⇒ **登记与「必须有 `record_hash` 列」之间没有任何代码关系。**
> 「登记 = 必须有列」和「登记 = 纯枚举」两个选项**都不对** —— 注册表根本不是那个意思。
>
> 两个后果：
> 1. **`cost_est_results` 补 `record_hash` 是「补兜底」（并发保护需要），
>    不是「补漏」（注册表完整性）。** 论证按前者写。
> 2. **不要加「registry ⇒ 有 record_hash 列」的一致性测试** —— 那是个**不存在的不变式**，
>    加了会立刻红在 `CostEstResult` 上，或反过来逼出不需要的列。
>
> ⚠️ **注册表名不副实，是一条真实的误导源**：`RECORD_TYPE_REGISTRY` 看起来像
> 「finalize 支持的类型清单」，但 finalize 根本不查它。于是 `CostEstResult` 在表里
> ⇒ 读者以为它被 finalize 支持 ⇒ 实际调了会抛 `AttributeError`（`cost_est_persist_service.py:15`
> 正是靠这条注释挡住的）。**防线是注释不是代码。** 登记为 TODO-049。
>
> ⚠️ **「无编辑路径」是当前事实，不是永久属性。** 若 P9B 新增 SIM 导入结果的
> 编辑入口（或 `util_results` 的可编辑字段），本节结论失效 ⇒ **回本 ADR 修订**，
> 不得就地补列。触发条件写在「尚未解决」1。
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

**🔻 2026-10-20 实施期更正（本句原文与代码不符）**：原文写「`compute_record_hash`
排除自身与生命周期列 ⇒ **不检测** `sign_status` / `approval_step` 等批准状态
字段的变化」。**实测不成立** —— `calc_lineage._EXCLUDED_KEYS` 只排除
`record_hash` 自身 + `created_at` / `created_by` / `updated_at` / `updated_by`
**五个**生命周期列，**工作流状态列参与哈希**。

⇒ 两条后果：

1. **职责切分要靠「重算时机」实现，不能靠「哈希不覆盖状态列」**。
   若在状态流转时也重算 hash，状态流转就会改掉 stored hash ⇒ 客户端手里的
   基线失效 ⇒ 用户在**没跟任何人冲突**的情况下收到假 409。
   ⇒ **重算只允许发生在「业务字段编辑路径」**（6 个 update service），
   **不得**用全局 flush 钩子（那会把状态流转也算进去）。
   守卫：`tests/services/test_record_hash_invariant.py`
   `test_status_transition_does_not_move_the_hash` +
   `test_sign_status_participates_in_the_hash`（后者钉住「状态列参与哈希」
   这个**事实**，好让将来想改的人知道自己在改什么）。
2. 批准状态的并发**仍然**由状态机事务 + `pg_advisory_xact_lock`
   （`app/services/advisory_lock.py`）负责 —— 职责切分不变，只是**实现位置**
   从「哈希的排除集」搬到了「重算的时机」。

**🔻 2026-10-20 实施期更正（更严重的一条）：阶梯的前提是「hash 会被更新」。**
原文的阶梯隐含假设「`record_hash` 反映记录当前内容」。**实测：它不反映** ——
6 条 PATCH 路径的 update service **一律不重算** hash
（`cool_tower_persist_service.py:251` 明写「不重新触发 record_hash 计算」；
flare / psychro 同款注释；filtration / open_channel / cost_est 连注释都没有）。

⇒ 若不重算，阶梯会**永远走「放行」分支**（`当前 record_hash == expected_hash`
恒成立，因为 stored hash 冻结在创建那一刻）⇒ **D2 的 guard 对 6 张表中的 5 张
是彻底的空操作** ⇒ 丢失更新（B 静默覆盖 A）检测不到。
⇒ 本 ADR 新增**硬前提**（P9A-4 D0 落地）：**业务字段编辑路径必须重算
`record_hash`**，否则 record_hash 这层「正确性保护」名存实亡。
守卫：`tests/architecture/test_record_hash_contract.py`（集合关系契约：
新加的 PATCH /results 端点必须登记，且重算调用必须在 setattr 之后、
commit 之前）。

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

> 🔻 **2026-10-20 D2 落地时更正**：原文写的是**顶层三字段**
> （`error_code` / `message` / `conflict`）。**本仓的统一错误信封是
> `{code, message, detail, trace_id}`**（`app/core/errors.py::ErrorResponse`，
> 全局异常处理器产出，所有 4xx/5xx 都走它）⇒ 冲突对象放进 `detail.conflict`。
> 照原文实现 ⇒ 前端要解析**两种**错误信封 ⇒ 必有一处漏解析。
> ⇒ 冲突对象的**内容**不变，只是**信封**归一。

```json
{
  "code": "RECORD_EDIT_CONFLICT",
  "message": "该记录无法安全保存，请刷新后重新编辑",
  "detail": {
    "conflict": {
      "record_type": "cooling_tower_results",
      "record_id": "…uuid…",
      "your_expected_hash": "…16 hex…",
      "current_hash": "…16 hex…",
      "changed_by": "…uuid… 或 null…",
      "changed_at": "2026-10-19T10:22:31+08:00 或 null",
      "basis": "record_hash | updated_at | no_baseline"
    }
  },
  "trace_id": "…"
}
```

- `message` 是**通用**措辞（两种 basis 都用它）：`basis` 才是分流依据 ——
  「别人改了」（刷新有用）与「没有基线」（刷新没用）的前端文案不同。
- 冲突对象有**显式 schema**：`app/schemas/edit_conflict.py::ConflictDetail`
  （P9A-DLV-010 零裸字段）。

- `basis` 三值对应 §⑥ 三条判定分支 —— 让前端能区分「别人改了」（刷新有用）
  与「记录没基线」（刷新没用，应联系管理员）。

**`changed_by` / `changed_at` 的契约约束（三条，强制）**：

1. 🔻 **2026-10-19 裁决（原「恒为 `null`」已废止）** —— 每次编辑保存写一条
   `audit_logs`（`action = RECORD_EDITED`，与 `RECORD_EDIT_OVERWROTE_STALE_BASELINE` 并列）。
   `changed_by` 从**本次编辑对应的那条**审计取，取不到才置 `null`。
   **不得**用「该记录最近一条审计」泛匹配去凑。
2. **不得**用 `updated_at` 冒充 `changed_at` —— `updated_at` 是行级时间戳，
   只说明「这行被改过」，不说明「是谁改的」。用它填是**精确性伪装，比 null 更有害**。
3. **`audit_logs.detail_json` 的字段级摘要必须有显式 schema**
   （受 P9A-DLV-010 零裸字段约束），**不得是自由 dict**。
   `detail_json` 的 `changed_fields` 供 409 弹窗的「查看差异」动作 ——
   **「不显示修改人」不能叠加「不显示改了哪」**，否则是双重降级。

> **为什么裁决从「不写编辑审计」改成「写」（决策委员会 2026-10-19，原建议 B，实测后翻转）**：
>
> 原论证是「409 是低频异常，编辑保存是高频主路径，别为低频弹窗给主路径加写入」。
> 这条论证成立的前提是**不提供字段级 diff**。一旦要求 409 说得出「改了哪」，
> 前提就没了 ——
>
> 实测：`change_diff_json` 只在**计算收口**（`calc_lineage`）/ `cia_engine` /
> `change_impact` / `flash_persist` 里写，**编辑保存路径一个都不写**。
> 而 `record_hash` 是哈希不是内容，**无法事后 diff**。
>
> ⇒ 要显示 diff，**主路径上就非写不可**。三选一：
>
> | | 谁改了 | 改了哪 | 主路径写入 |
> |---|---|---|---|
> | **A：写 `audit_logs`（本裁决）** | ✅ | ✅（`detail_json`） | 一行，**无迁移** |
> | B2：写 `data_lineage` diff | ❌ | ✅ | 一行（更重，无 who） |
> | B0：什么都不写 | ❌ | ❌ | 零 |
>
> **A 用一次写入同时给出「谁」和「改了哪」，B2 花同样的代价只给一半。**
> 「保留策略未定」这个顾虑对 A 与 B2 **同等成立**，不能只用来否 A。
> `audit_logs` 已有 `user_id` / `action` / `resource_type` / `resource_id` / `detail_json`
> ⇒ **不需要迁移**。
>
> ⚠️ **A 的已知代价**：写侧增速取决于编辑频率，而 `audit_logs` 的**保留期尚未裁决**
> （P9-OPEN-003 只定了导出格式）。P9A 须一并提出保留期方案，否则审计表只增不减。

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

1. 🔻 **已由 2026-10-19 裁决收窄为 1 张表**：`cost_est_results` 补 `record_hash` +
   接 `finalize_calc_record`（**2026-10-20 由 P9A-4 D0 落地**，见 §⑥ 的
   实施期裁决 + 迁移 `p9_006`）。**不引入 `row_version`** —— 那会在 `record_hash` 之外
   叠加第二套并发令牌，P9A 实施者每写一个保存路径都要判断「这张表用哪个」，
   正是 bug-180~191 词表分叉的同构问题。同一把钥匙。
   **触发条件（结论可能失效）**：若 P9B 新增 SIM 导入结果的编辑入口，或
   `util_results` 出现可编辑字段 ⇒ §⑥ 收窄表失效，**回本 ADR 修订**，不得就地补列。
2. 🔻 **2026-10-20 更正**：`record_hash` **确实覆盖**批准状态字段
   （`sign_status` / `approval_step`）—— 原写「不检测」与代码不符（见 §⑥ 的
   实施期更正）。「编辑保护不覆盖批准状态」这个**职责切分仍然成立**，
   但实现位置从「哈希的排除集」搬到了「重算的时机」（只重算业务字段编辑路径）。
   若 P9A 实施时发现签署流程本身也需要并发保护（而不只是编辑），
   **本 ADR 不覆盖该场景**，需回本 ADR 修订。
3. ~~**「编辑保存」是否写 `audit_logs` 未裁决**~~ —— **已裁决**：写（§⑦ 裁决 2）。
   随之产生的**新**未决项：**`audit_logs` 的保留期**（P9-OPEN-003 只定了导出格式）。
   编辑审计让这张表的增速取决于编辑频率，P9A 须一并提出保留期方案。
