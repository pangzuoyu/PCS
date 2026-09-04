# P1 横切关注点框架 实施计划

**Goal**：交付 SPEC-P1 V1.2 §3.2.1–3.2.6 六大横切能力的 P1-MVP 子集——使 P4–P6 计算模块可直接复用（状态机 + 血缘 + CIA + 工作区 + 输入清单）。交付物与变更单延后至 P1.2（P8 报表前完成）。复用 P0 已有的 53 表 Schema。

**Spec**：`spec/工艺专用综合计算软件需求规格说明书 Web版 P1.md` V1.2、`spec/PCS-DICT-ALL-003 V3.1`、ADR-0019~0023、SUP-004/005/007。

**Tech 追加**：ARQ（异步任务）+ Redis Stream 队列（已在 compose）+ Alembic 增量迁移 + asyncpg（异步 DB）。

---

## 一、范围（已按 eng-review 2026-09-01 拆分）

| 模块 | P1-MVP（本次） | P1.2（推迟至 P8 前） | 备注 |
|---|---|---|---|
| A 工作区管理 | ✅ | — | P1-MVP 必做 |
| B 状态机引擎 | ✅ | — | P4 前置，P1-MVP 必做 |
| C 数据血缘 | ✅ | — | P4 FLASH/PIPE/PUMP 计算模块直接依赖 |
| D 交付物与变更单 | — | ✅ P1.2 | P8 REPORT 前完成；P4 只需记录层 CHECKED 即可 |
| E 输入清单 | ✅ | — | P1-MVP 必做 |
| F 变更影响分析 | ✅（核心） | 通知面板 → P1.2 | 哈希扫描 + STALE + 设备联动；前端通知推迟 |
| G 前端组件 | StatusTag / WorkspaceSwitcher / ChecklistDashboard | LineagePanel / ChangeNotification / RevTimeline | API 在 P1-MVP 落地，前端组件 P1.2 补 |

**合计**：
- P1-MVP：~4350 LOC（后端 ~4000 + 前端 ~350），≥120 测试，3 次 migration
- P1.2：~2700 LOC（交付物 + 客户代录 + 3 前端组件），≥45 测试，1 次 migration

**P1 表数量变化**：0（SPEC-P1 V1.2 与 DICT-ALL-003 V3.1 一致，仅用 P0 已建 53 表）。`test_schema.test_table_count_is_53` 断言无需调整。

---

## 二、执行阶段（P1-MVP 三 sprint）

**Sprint 1：基础设施 + 工作区 + 输入清单 + CORS**
- **DB 基础设施**：`app/db/session.py` 追加 `async_session_factory`（asyncpg）、`get_db()` FastAPI 依赖（async generator）；装 `asyncpg` 依赖；同步 engine + async engine 双引擎 lifespan 顺序（async first，TODO-021）
- **Redis 健康**：扩展 `app/api/v1/health.py` 输出 `{"status":"ok","database":"up","redis":"up"}`
- **ARQ 接入**：worker 与 FastAPI 同进程（dev），`app/workers/arq_settings.py` + lifespan 启停；dev 模式 `create_worker(WorkerSettings)` + `async_task`（含 cron_jobs 自动调度）；prod 用独立命令 `uv run arq app.workers.arq_settings.WorkerSettings`；**Sprint 1 WorkerSettings.cron_jobs 仅配 `cleanup_expired_workspaces`，Sprint 3 追加 `cron_cia_delta` / `cron_cia_full`（避免 Sprint 1 启动时引用 cia_tasks.py 不存在的模块导致 ImportError）**
- **Alembic 增量机制**：每 sprint 一个 `alembic revision` 新 head；P0 的 `dd47298c9c38` 保留为基线
- **Sprint 1 迁移**：`p1_sprint1_workspace_checklist.py` 追加 `doc_no_sequences UNIQUE(project_id, template_id, scope_key)` 约束（P1.2 编号原子分配前置，可暂不消费）
- **工作区**：service + API（GET workspaces / POST / DELETE / 自动清理）+ 前端 WorkspaceSwitcher；**导入到 FORMAL 功能推迟到 P1.2**（设计缺陷 6）；自动清理任务（ARQ cron：PERSONAL 90 天 / TEMPORARY 7 天，**物理删除过期工作区 + 关联记录**——删除顺序：先计算记录（含 equipment_list，RecordMixin.workspace_id）→ 再 streams → 最后 workspace；若 FK ON DELETE 行为为 NO ACTION 则清理任务按依赖顺序手动 delete；FORMAL 工作区不清理）
- **输入清单**：service + API（GET `{project_id}` / GET completeness / PUT `{project_id}/item/{input_id}`）+ 前端 ChecklistDashboard；PUT 语义：更新 value + source_type + status（VERIFIED/ASSUMED/NOT_STARTED），VERIFIED 状态记录 verified_by/verified_at；完整性阻塞独立端点 GET completeness
- **CORS**（TODO-004）：`CORSMiddleware` + `Settings.allowed_origins`，env 注入；prod 启动期 `_validate_cors_for_production()` 断言（TODO-019）
- **测试 ≥30**（含清理任务/门禁 403 / async session 基础 / 输入清单 PUT 验证逻辑 / CORS prod 启动校验 / AuditAction 枚举值≤50 字符约束）

**Sprint 2：状态机引擎 + 前端 StatusTag**
- `app/services/state_machine.py`：**StateMachineService** 类（非纯函数！），`async transition(record, transition, actor, reason)`：状态变更 + **副作用一体化**（仅数据即将被修改时写 `record_change_snapshots`、撤销批准恢复快照、弃用处理位号——SUP-007 §3.1 全责）+ 落 audit_logs；**transition 顶部加 `pg_advisory_xact_lock` 防止并发竞争**（架构决策 14）
- 完整 `StateTransition` 枚举（架构决策 15）：SUBMIT / APPROVAL_STEP_PASS / APPROVAL_STEP_REJECT / MARK_STALE / RESOLVE_STALE_NO_CHANGE / RESOLVE_STALE_CHANGED / SUBMIT_CHANGE / CHANGE_CHECK_PASS / ABANDON_CHANGE / REQUEST_REVERSAL / APPROVE_REVERSAL / REJECT_REVERSAL / OBSOLETE；P1.2 补充 RESOLVE_BY_NOTICE / RESOLVE_BY_DELIVERABLE
- 6 个 API 端点：`/records/{record_type}/{record_id}/{submit|approval-step|abandon-change|request-reversal|reversal-decision|obsolete|status}`（`status` 查询端点不装门禁，其余 5 个装 `Depends(require_formal_workspace)`）
- **RecordResponse 最小响应**（架构决策 16）：仅流程字段 `record_type/record_id/sign_status/record_hash/approval_step/approval_depth/transition_at`；业务字段响应由 P4-P6 各计算模块 API 自行定义
- 通用 CRUD **不提供**：记录创建/更新由 P4–P6 各计算模块 API 实现；测试用 `tests/conftest.py` 的 `make_draft_record` fixture 直写 DB（TODO-012 扩展 17 种 record type）
- 前端 StatusTag 组件（含 IN_APPROVAL step n/N 进度）
- **Sprint 2 迁移**：`p1_sprint2_state_machine.py` 必须包含 `op.add_column('record_change_snapshots', sa.Column('snapshot_status', sa.String(20), nullable=False, server_default='ACTIVE'))`；状态机逻辑全部在 service 层
- **测试 ≥40**（9 态 × 多路径 + 守卫 + 副作用断言 + 审计落库 + advisory lock 并发）

**Sprint 3：血缘 + CIA 核心 + 完成前端**
- **血缘装饰器**：`@lineage(sources=[(param_name, source_type), ...], target_type, dependency_type)`，`@functools.wraps(func)` 保留元数据；调用函数后自动写 `data_lineage`（source_id+source_record_hash → target_id+target_record_hash）
- **上下文管理器**：`async with lineage_ctx(db, target_type, target_id):` 用于计算函数内部多步来源收集；**P4 调用顺序：先创建 record → flush 获得 PK → 进 ctxmgr 收集依赖**（架构决策 17）
- 上下游追溯 API：`/lineage/{module}/{record_id}/{upstream|downstream|graph}`
- **ARQ 异步 CIA 任务**（`app/workers/cia_tasks.py`）：`async def scan_cia_task(ctx, project_id)` 独立创建 `async_session_factory()`，不依赖 FastAPI 依赖注入
- **CIA 触发机制（架构决策 18）**：ARQ cron 每 1 分钟扫 `data_lineage` 表 source_record_hash != 当前 source 记录哈希的条目；5 分钟兜底扫全量；P1.2 或 P2 可升级为事件驱动（PG LISTEN/NOTIFY）
- **confirm-recalc 端点（架构决策 19）**：`change_impact.py` 提供 `/change-impact/{record_type}/{record_id}/confirm-recalc` 高层动作；触发哈希比较 → 哈希不变调 `StateMachineService.transition(record, RESOLVE_STALE_NO_CHANGE)`；哈希变化调 `transition(record, RESOLVE_STALE_CHANGED)`；状态机不暴露 CONFIRM_RECALC 复合动作
- 链式传播（ADR-0022 物流转换边 DEVICE_TRANSFORMATION）：CIA 标记 STALE 后链式向下游传播
- 设备联动（ADR-0005 + ADR-0025）：来源记录 STALE 后 ≤ 5 分钟内设备记录同步 STALE；设备一览表发布（P1.2）前必须等待 CIA 扫描完成；扫描失败 3 次设备记录 `actual_data_status = NEED_RECALC` + `audit_logs.action=CIA_NOTIFIED` + `remarks="SCAN_FAILED"` + 告警
- **Sprint 3 迁移**：`p1_sprint3_lineage_cia.py`——若 schema 无变化则仅占位记录
- **测试 ≥50**（血缘自动写入 + CIA 异步 cron + STALE 路径 + 链式传播 + 设备联动 + 上下游追溯 + 4 个 P4 接入 e2e：FLASH/PUMP/PIPE/PIPE_NET，TODO-017）

---

## 三、关键架构决策

1. **迁移策略**：P0 单版本迁移已上线；P1 起改增量，每次 sprint 一个 `alembic revision`（不重新生成 P0 历史）。

2. **ARQ 接入 + 异步 Session**：worker 与 FastAPI 同进程（uvicorn 启动时 launch_task 协程）。Redis 已有，仅需在 `app/main.py` lifespan 中启停 worker。任务失败 3 次后入 DLQ（TODO-016 补失败注入测试）。
   - **`app/db/session.py` 同步 + async 双引擎**：保留 P0 同步 engine（同步端点/迁移），**新增 `async_session_factory()` 用 asyncpg**（异步端点/ARQ 任务）；连接池配置见 TODO-021
   - **ARQ 任务函数独立创建 session**：`async def scan_cia_task(ctx, project_id): async with async_session_factory() as session: ...`——不依赖 FastAPI 依赖注入

3. **状态机实现**（**非纯函数，是 Service 类**）：`app/services/state_machine.py` 定义 `StateMachineService(session)`，`async transition(record, transition, actor, reason)` 一站式：合法性 + 副作用（CHECKED→CHANGE_PENDING / STALE→CHANGE_PENDING / CHECKED→DRAFT 自动写 `record_change_snapshots`，撤销批准恢复快照，弃用处理位号释放 ADR-0011）+ 落 `audit_logs`（action=RECORD_TRANSITION）。**caller 不复制副作用逻辑**。STALE 期间数据未修改不写快照（ADR-0024 修订 ADR-0012）。

4. **血缘自动写**（`@lineage` 装饰器主 + `lineage_ctx` 补充 + `LineageTracker.track()` 手动）：
   - 装饰器覆盖 80% 静态依赖场景：`@lineage(sources=[("stream_id", "STREAM")], target_type="FLASH_RESULT", dependency_type="CALCULATION")`
   - ctxmgr 覆盖多步动态依赖：`async with lineage_ctx(db, target_type, target_id) as lt: lt.add_source(...)`
   - 手动 track 用于"计算+提交+血缘同事务"
   - 三者共享 `LineageTracker` 类与 `_get_current_hash`，非三套实现
   - 事务回滚由 SQLAlchemy 自动清理 `data_lineage` 行（TODO-015 文档化）
   - **P4 计算模块零侵入接入**

5. **工作区门禁**：`Depends(require_formal_workspace)` 直接查 `record.workspace_id` 对应 `Workspace.workspace_type`，非 FORMAL 返回 403；返回 `record` 供端点直接使用避免重复加载。装在 `submit/approval-step/abandon/request-reversal/reversal-decision/obsolete` 六个端点上；`status` 查询端点不装门禁。P1.2 交付物端点因无 record，workspace_id 来自请求体另行校验。

6. **快照哈希**：发布时 `record_change_snapshots` 存完整 JSON；`deliverable_record_bindings` 存 record_hash（仅哈希）。两份职责单一，不冗余（P1.2 落地）。
   - **快照时机（ADR-0024 修订 ADR-0012）**：仅数据即将偏离 CHECKED 基线时写——CHECKED→CHANGE_PENDING / STALE→CHANGE_PENDING（哈希变化确认）/ CHECKED→DRAFT
   - **CHECKED→STALE 不写快照**（数据未修改）
   - 撤销批准时读 `snapshot_status=ACTIVE` 快照，同事务恢复 + 标记 `CONSUMED`

7. **位号终身唯一**（**P0 已正确实现，保留不动**）：TaggedRecordMixin 的 DB UniqueConstraint `(project_id, tag_number)` / piping 的 `(project_id, line_no)` **保留**——覆盖含 OBSOLETE 全记录，弃用不复用。

8. **编号原子分配**（P1.2 落地，P1-MVP 仅建 UNIQUE 约束）：`pg_insert(...).on_conflict_do_update(set_={"current_value": col + 1}).returning(...)` 并发安全。Sprint 1 起 UNIQUE 已生效，fixture `make_draft_record` 默认填值（TODO-012）。

9. **通用 CRUD 不提供**：P1 records.py **不**实现 POST/PATCH records；记录创建/更新由 P4–P6 计算模块 API 实现。测试用 `tests/conftest.py` 的 `make_draft_record` fixture 直写 DB（TODO-012 扩展 17 种）。

10. **CIA 通知**：P1-MVP 写入 `audit_logs`（action=CIA_NOTIFIED）+ `data_lineage` 标记 STALE；前端通知面板 P1.2 落地。**P4 开发期靠查询 audit_logs 即可感知**。设备联动最终一致性窗口 ≤ 5 分钟（CIA cron 兜底，TODO-014 ADR-0025）。

11. **AuditAction 完整枚举**（P1 扩展）：`app/models/enums.py` 新增 AuditAction 字符串枚举覆盖 P0+P1 全部 action（认证/CRUD/状态机/变更/快照/血缘/CIA/工作区/输入清单/客户批准预留）。统一入口 `AuditService(session).write(...)`。audit_logs.action 字段已是 String(50) 无 DB 迁移。

12. **CORS 配置**：Dev 默认 `http://localhost:5173`；prod 启动期 `lifespan` 校验 `allowed_origins` 已显式设置且不含 `*`（TODO-019 落地函数位置）。

13. **ARQ 失败处理**：默认 3 次重试 + DLQ + 告警（TODO-016 补测试）。

14. **并发控制（advisory lock）**：`StateMachineService.transition` 顶部加 `pg_advisory_xact_lock(record_id)` 防止同 record 并发 transition。UUID 转 int 用 `uuid.UUID(int=int(uuid)) >> 64` 截断（bigint 范围）；锁随事务结束自动释放。

15. **StateTransition 完整枚举**（`app/models/enums.py`）：
    - 正向：`SUBMIT` / `APPROVAL_STEP_PASS` / `APPROVAL_STEP_REJECT`
    - STALE 路径：`MARK_STALE` / `RESOLVE_STALE_NO_CHANGE` / `RESOLVE_STALE_CHANGED`
    - 变更：`SUBMIT_CHANGE` / `CHANGE_CHECK_PASS` / `ABANDON_CHANGE`
    - 撤销：`REQUEST_REVERSAL` / `APPROVE_REVERSAL` / `REJECT_REVERSAL`
    - 弃用：`OBSOLETE`
    - P1.2 预留：`RESOLVE_BY_NOTICE` / `RESOLVE_BY_DELIVERABLE`（交付物关闭变更路径）

16. **RecordResponse 最小化**（`app/schemas/records.py`）：P1 状态机端点响应仅含流程字段 `record_type/record_id/sign_status/record_hash/approval_step/approval_depth/approval_role/locked_by_deliverable/change_resolved_by/obsoleted_reason/transition_at`；业务字段响应由 P4-P6 各计算模块 API 自行定义。**transition_at 取自 `record.updated_at`**（状态机 transition 必触发 SQLAlchemy onupdate 刷新 updated_at；精确转移时间以 `audit_logs.timestamp` 为准，P1.2 审计日志查询接口提供）。

17. **lineage_ctx 两阶段模式**：P4 计算函数顺序：先 `db.add(record)` → `flush()` 获得 PK → 进 `async with lineage_ctx(db, target_type, target_id) as lt` 收集依赖 → 退出时 flush。需在 CLAUDE.md 和 P4 开发模板明确。

18. **CIA 触发机制（两层轮询）**：
    - **快速增量**：ARQ cron 每 1 分钟扫 `data_lineage.timestamp >= now() - 7 days` 条目（利用表已有 timestamp 字段，零 migration）
    - **全量兜底**：ARQ cron 每 5 分钟扫全部 `data_lineage` 条目
    - **扫描逻辑**：对每条 `source_record_hash` 与当前 source 记录哈希比较，不匹配 → 标记 target STALE
    - P1-MVP 不加索引（数据量 ~10²，全表扫 <100ms）；P4 中后期按 TODO-022 评估加 `ix_data_lineage_timestamp` 索引
    - P1.2 / P2 可升级为 PG LISTEN/NOTIFY 事件驱动

19. **confirm-recalc 分层**：`change_impact.py` 提供 `/confirm-recalc` 高层动作（哈希比较 + 选择目标状态）；内部调用 `StateMachineService.transition` 执行单步转移。状态机不暴露 CONFIRM_RECALC 复合枚举值。

20. **P4 计算函数签名约定**（写入 CLAUDE.md 和 P4 开发模板）：
    - `db: AsyncSession` 必须为**关键字参数**（装饰器从 `kwargs["db"]` 获取）
    - 使用 `@lineage` 的函数必须返回 ORM 记录（未 flush 也可；装饰器退出前自动 flush）
    - 血缘写入在函数返回后、装饰器退出前执行（与函数主事务同 lifecycle）
    - 模板示例：`async def calculate_xxx(db: AsyncSession, *, param1, param2) -> RecordType: ...`

21. **StateMachine 合法转移矩阵前置**（架构决策 + 测试驱动）：Sprint 2 启动前先写 `ALLOWED_TRANSITIONS: dict[RecordSignStatus9, set[StateTransition]]` 守卫矩阵 + 对应单元测试，作为可测试的显式文档，再实现 `transition()` 逻辑。矩阵：

    ```python
    ALLOWED_TRANSITIONS = {
        DRAFT: {SUBMIT, OBSOLETE},
        IN_APPROVAL: {APPROVAL_STEP_PASS, APPROVAL_STEP_REJECT},
        CHECKED: {MARK_STALE, SUBMIT_CHANGE, OBSOLETE},
        STALE: {RESOLVE_STALE_NO_CHANGE, RESOLVE_STALE_CHANGED},
        CHANGE_PENDING: {CHANGE_CHECK_PASS, ABANDON_CHANGE, OBSOLETE},
        CHANGED: {REQUEST_REVERSAL, OBSOLETE},
        REVERSAL_PENDING: {APPROVE_REVERSAL, REJECT_REVERSAL},
        CHECK_REJECTED: {SUBMIT},  # 修改后重新提交
        OBSOLETE: set(),  # 终点
    }
    ```

---

## 四、文件结构（增量新增，不动 P0 既有）

**后端**：
```
app/services/
│   state_machine.py        # Sprint 2（StateMachineService + advisory lock）
│   workspace_service.py    # Sprint 1（CRUD + 自动清理，导入功能 P1.2）
│   deliverable_service.py  # P1.2
│   lineage_tracker.py      # Sprint 3（装饰器 + ctxmgr + tracker.track）
│   cia_engine.py           # Sprint 3
│   checklist_service.py    # Sprint 1
│   audit_service.py        # Sprint 1（AuditService.write 统一入口）
app/api/v1/
│   workspaces.py           # Sprint 1
│   checklist.py            # Sprint 1
│   records.py              # Sprint 2（6 端点，最小 RecordResponse）
│   deliverables.py         # P1.2
│   lineage.py              # Sprint 3（upstream/downstream/graph）
│   change_impact.py        # Sprint 3（confirm-recalc 高层动作）
app/workers/
│   arq_settings.py         # Sprint 1（WorkerSettings + cron_jobs）
│   cia_tasks.py            # Sprint 3（CIA 扫描）
│   workspace_tasks.py      # Sprint 1（自动清理，独立于 cia_tasks，TODO-018）
alembic/versions/
│   p1_sprint1_workspace_checklist.py
│   p1_sprint2_state_machine.py
│   p1_sprint3_lineage_cia.py
tests/
│   test_workspace.py       # Sprint 1
│   test_checklist.py       # Sprint 1
│   test_state_machine.py   # Sprint 2
│   test_lineage.py         # Sprint 3
│   test_cia.py             # Sprint 3
```

**前端（P1-MVP）**：
```
src/components/
│   StatusTag.tsx           # Sprint 2
│   WorkspaceSwitcher.tsx   # Sprint 1
│   ChecklistDashboard.tsx  # Sprint 1
src/types/
│   records.ts              # Sprint 2（RecordResponse 最小响应的 TS interface）
│   workspace.ts            # Sprint 1
│   checklist.ts            # Sprint 1
```

**前端（P1.2）**：
```
src/components/
│   RevTimeline.tsx
│   LineagePanel.tsx
│   ChangeNotification.tsx
```

---

## 五、验收标准

**P1-MVP（本次）**：
1. **后端**：`ruff check app+tests` 0 error；`mypy app+tests` 0 error；`pytest` 全绿（≥120 用例）；`alembic upgrade head` 在 pcs+pcs_test 两侧成功。
2. **前端**：`tsc --noEmit` 0 error；`vite build` 成功。
3. **P4 接入验证**：写 1 个 e2e 测试模拟 FLASH 计算模块调用 `@lineage` 装饰器 + 状态机走 DRAFT→CHECKED 全路径，确认 P4 模块可直接复用 P1-MVP API。

**P1.2（P8 报表前）**：交付物 + 客户代录 + 3 前端组件 ≥45 测试。

---

## 六、已决问题（开 Sprint 1 前已裁决）

| 编号 | 问题 | 裁决 | 落地位置 |
|---|---|---|---|
| **P1-OPEN-A** | ARQ 同进程 vs 拆 worker | **dev 同 / prod 拆** | Sprint 1 `app/main.py` lifespan；prod 命令 `uv run arq app.workers.arq_settings.WorkerSettings` |
| **P1-OPEN-B** | 客户代录 MFA 方式 | **AD 密码二次** | **P1.2** `/customer-approval/proxy` 端点 |
| **P1-OPEN-C** | 个人区归档提醒 | **提前 7 天日志提醒**（邮件后补） | Sprint 1 ARQ cron 任务 |
| **P1-OPEN-D** | CIA 异步频率 | **变更 1 分钟内启动 + 5 分钟兜底 cron** | Sprint 3 `app/workers/cia_tasks.py` |
| **P1-OPEN-E** | TODO-004~006 何时纳入 | **仅 CORS 进 Sprint 1**；TLS + 限流延后 | Sprint 1 `app/main.py` CORSMiddleware |
| **P1-OPEN-F** | 增量迁移机制 | **是** | Sprint 1 起每 sprint `alembic revision` |
| **P1-OPEN-G** | 前端组件交付节奏 | **本次 3 个，3 个延后 P1.2** | Sprint 1+2 末 tsc + vite build |
| **P1-OPEN-H** | P1 范围拆分 | **MVP（5 模块 + 3 前端）+ P1.2（交付物 + 3 前端）** | 本计划 |

**仍待 IT/外部确认（不阻塞 P1-MVP 启动）**：
- SPEC P1-OPEN-001 MFA 基础设施现状（仅 P1.2 客户代录需要）
- SPEC P1-OPEN-004 版本快照回滚功能（已确认 P1 全期不做）

**ADR 修订（eng-review 2026-09-01 锁定）**：
- **ADR-0024 修订 ADR-0012**：CHECKED→STALE 不再自动存快照；改为 CHECKED→CHANGE_PENDING / STALE→CHANGE_PENDING / CHECKED→DRAFT 时创建快照。理由：STALE 期间数据未修改，提前存快照是浪费存储。
- **ADR-0025（新增）设备联动最终一致性**：
  - 状态：Accepted / 2026-09-01（v5 修正：复用 `equipment_list.actual_data_status = NEED_RECALC`，零 Schema 变更）
  - 来源记录 STALE → 设备记录 STALE 传播是异步的（依赖 CIA 扫描）
  - 扫描完成前存在窗口期（≤ 5 分钟，cron 兜底），期间来源已 STALE 但设备仍 CHECKED，**此为可接受的最终一致性**
  - 约束：设备一览表发布（P1.2）前必须等待 CIA 扫描完成；扫描失败 3 次 → `equipment_list.actual_data_status = NEED_RECALC` + `audit_logs.action=CIA_NOTIFIED` + remarks `"SCAN_FAILED"` + 告警；扫描恢复后设备记录按正常状态机路径更新
- **DICT-ALL-003 → V3.2**：表38 `record_change_snapshots` 追加 `snapshot_status String(20)`（ACTIVE/CONSUMED/ABANDONED）。
- **SPEC-P1 V1.2 → V1.3**：§3.2.2 快照语义章节同步 ADR-0024；§3.2.5 设备联动章节同步 ADR-0025。
- **SUP-007 §3.1** 文字同步。

**P1-MVP 配套 TODOS**（详 `TODOS.md`）：
- TODO-011~013：snapshot_status 字段 + make_draft_record 17 类型 + STALE→CHANGE_PENDING 旧哈希记录
- TODO-014~017：ADR-0025 设备联动容忍度 + lineage_ctx 文档化 + ARQ 失败注入 + 4 个 P4 e2e
- TODO-018~021：workspace_tasks 独立文件 + CORS 启动校验 + ADR/DICT/SPEC 同步 + 双引擎 lifespan

---

## 八、Failure modes 清单（gstack eng-review 2026-09-01）

| 故障模式 | 影响 | 缓解 |
|---|---|---|
| asyncpg 连接池耗尽 | API 端点 503 | pool_size=10 + max_overflow=20 + pool_pre_ping |
| Redis 断开 | ARQ 任务丢失 | WorkerSettings lifespan 启停 + 任务重试 + 5 分钟 cron 兜底 |
| ARQ 任务失败 3 次 | DLQ 累积 | 告警 + admin 查询 DLQ 人工重试 |
| 同步 engine 阻塞 | 异步端点延迟 | 同步仅用于 P0 auth/health/migration；P1 全部 async |
| 状态机并发竞争 | 重复 transition | `pg_advisory_xact_lock(record_id)` + 短事务 |
| 快照表膨胀 | 存储成本 | snapshot_status=CONSUMED 定时归档（P1.2） |
| CIA 扫描漏触发 | 上游变更未传播 | 1 分钟事件 + 5 分钟 cron 双保险 |
| doc_no_sequences UNIQUE 冲突 | 编号分配失败 | pg_insert ON CONFLICT DO UPDATE 原子 |
| 同步/异步 engine 启停顺序 | ARQ 拿不到 session | lifespan 顺序：async first → sync；shutdown 反向（TODO-021） |
| 设备联动中间窗口 | 状态 CHECKED 但设备 STALE | ADR-0025 声明 ≤ 5 分钟容忍 + CI 标记（TODO-014） |

---

## 九、GSTACK ENG-REVIEW 报告（2026-09-01）

### 9.1 流程

Step 0 范围裁决：P1-MVP（5 模块 + 3 前端，~4350 LOC + ≥120 测试 + 3 migrations）；P1.2（交付物 + 客户代录 + 3 前端）延后至 P8 前。

### 9.2 架构裁决（Issue 1-9 锁定摘要）

| # | 议题 | 裁决 |
|---|---|---|
| 1 | 端点同步模式 | 全 async def（asyncpg + async_sessionmaker） |
| 2 | 状态机多态 | API 层 RECORD_TYPE_REGISTRY + Service 用 record.__table__ 反射 |
| 3 | 事务边界 | Service 只 flush 不 commit；caller 负责 |
| 4 | 血缘场景 | @lineage 装饰器主（80%）+ lineage_ctx 补（动态）+ tracker.track() 手动 |
| 5 | CORS 默认值 | Dev 默认 localhost；prod 启动期校验显式设置 |
| 6 | AuditAction 枚举 | 完整字符串枚举 + AuditService.write() 统一入口 |
| 7 | 工作区门禁 | Depends(require_formal_workspace) 直接查 record.workspace_id |
| 8 | ARQ 重试 | 默认 3 次 + DLQ + 告警 |
| 9 | 快照时机 | ADR-0024：仅数据即将被修改瞬间（CHECKED→CHANGE_PENDING / STALE→CHANGE_PENDING / CHECKED→DRAFT）；CHECKED→STALE 不写 |

### 9.3 外部视角（独立 subagent）发现

#### 关键风险
1. **StateMachineService 一体化副作用是单点风险源**：5 写入目标耦合 → 测试矩阵大。建议 Sprint 2 实施时考虑事件总线（至少快照写可独立测试）。
2. **ARQ dev/prod 双形态测试-生产漂移**：TODO-016 补 e2e 验证 lifespan 启停。
3. **设备联动归属模糊**：ADR-0025 声明 ≤ 5 分钟最终一致窗口（TODO-014）。
4. **doc_no_sequences UNIQUE Sprint 1 死代码风险**：TODO-012 fixture 默认填值。
5. **P4 接入验收仅 1 e2e**：TODO-017 扩展至 4 个（FLASH/PUMP/PIPE/PIPE_NET）。

#### 范围问题
- P1.2 隐性依赖链（P1-MVP 不做发布路径演练）
- 前端通知面板延后但 audit_logs CIA_NOTIFIED 已写入（文档化临时约定）
- 客户代录 MFA 全延后（无演示版 P4 验收通道）

#### P4 接入验证
- @lineage 装饰器对纯计算函数零侵入（PUMP/PIPE/FLASH 数值求解）
- P4 多步事务内 lineage_ctx 事务回滚自动清理（TODO-015 文档化）
- StateMachineService 要求 caller 传 record 对象（多一行侵入）

#### 测试盲点（已在 TODOS）
- ARQ 失败注入 → TODO-016
- 并发 doc_no_sequences → P1.2 范畴
- StateMachineService 部分提交回滚 → Sprint 2 测试覆盖

#### 技术债（已在 TODOS）
- record_change_snapshots P0 已建，Sprint 2 加 snapshot_status → TODO-011
- workspace 自动清理独立文件 → TODO-018
- CORS prod 校验函数位置 → TODO-019
- ADR-0012 + ADR-0024 交叉引用 → TODO-020
- 双引擎 lifespan 顺序 → TODO-021

### 9.4 Section 2/3/4 跳过理由

P1-MVP 代码尚未编写。Code Quality / Performance review 需基于具体代码；现仅完成架构层面（Section 1）+ 外部视角 + Failure modes。Section 2/3/4 推迟到 Sprint 1 后期（代码就绪后）。

### 9.5 下一里程碑

1. Sprint 1 启动 → 按 §二 Sprint 1 任务清单执行
2. Sprint 1 末 → 补 Section 2/3/4（基于已写代码）
3. Sprint 2/3 同上节奏
4. P1.2 启动前 → ADR-0025（设备联动容忍度）落地

---

## 十、P1 计划 v4 变更（2026-09-01 集成实施审阅）

### 10.1 硬矛盾（4 项已修正）

| # | 矛盾 | 修正 |
|---|---|---|
| 1 | `imported_from_workspace_id` 字段不存在 | 用 `data_lineage` 表 `source_type=WORKSPACE_IMPORT` 记录（与 ADR-0016 "历史由血缘+审计承载" 一致）；零 Schema 变更 |
| 2 | `old_record_hash_before_change` 字段不存在 | 不新增字段；从 `record_change_snapshots.record_hash` 读取 |
| 3 | `workspaces.status` 字段不存在 | 物理删除过期工作区 + 关联记录（PERSONAL/TEMPORARY 试算数据可丢） |
| 4 | `snapshot_status` 列需 migration | Sprint 2 migration 必含 `op.add_column('record_change_snapshots', sa.Column('snapshot_status', sa.String(20), nullable=False, server_default='ACTIVE'))`；Sprint 2 不再是占位 |

### 10.2 设计缺陷（7 项已裁决）

| # | 缺陷 | 裁决 |
|---|---|---|
| 1 | lineage_ctx target_id 鸡生蛋 | P4 先创建 record → flush → 进 ctxmgr 收集依赖 |
| 2 | @lineage 多 source 语法 | `sources=[(param_name, source_type), ...]` 元组列表 |
| 3 | confirm-recalc 与状态机边界 | change_impact.py 高层 + state_machine.py 单步；状态机不暴露 CONFIRM_RECALC |
| 4 | CIA 上游变更触发机制 | ARQ cron 每 1 分钟扫 data_lineage 哈希不匹配；5 分钟兜底扫全量 |
| 5 | StateTransition 枚举未定义 | 补全 13 个枚举（P1-MVP）+ 2 个 P1.2 预留 |
| 6 | 工作区导入功能复杂度低估 | **推迟到 P1.2**；Sprint 1 LOC 净身 ~400 |
| 7 | RecordResponse 17 种响应模型 | **最小响应**（仅流程字段）；P4-P6 自定义完整响应 |

### 10.3 补充（4 项已纳入）

| # | 补充 | 落地位置 |
|---|---|---|
| 1 | pg_advisory_xact_lock 并发控制 | 架构决策 14 |
| 2 | ADR-0025 内容定义 | §六 ADR 修订 |
| 3 | ARQ dev 同进程 cron_jobs 调度 | Sprint 1 lifespan 描述 |
| 4 | 输入清单 PUT 端点语义 | Sprint 1 端点描述 |

### 10.4 LOC 影响

- Sprint 1：~1200 → ~800（导入功能去除 -400）
- Sprint 2：~1200 → ~1300（snapshot_status 迁移 + advisory lock + StateTransition 枚举 +100）
- Sprint 3：~1600 → ~1700（confirm-recalc 端点 + CIA cron 实现 + P4 4 个 e2e +100）
- **P1-MVP 合计**：~4000 → ~3800 LOC（净减 200 LOC；测试密度提升）

---

## 十一、P1 计划 v5 变更（2026-09-01 集成第三轮审阅）

### 11.1 文档不一致（2 项已修正）

| # | 不一致 | 修正 |
|---|---|---|
| 1 | 架构决策 4 装饰器签名 `source_param` 单数写法残留 | 改为 `sources=[(param_name, source_type), ...]` 元组列表（与 Issue 4 + 分叉 2 一致） |
| 2 | `transition_at` 字段来源未定义 | 用 `record.updated_at`（P0 TimestampMixin，onupdate 自动刷新）；精确转移时间以 `audit_logs.timestamp` 为准（P1.2 审计日志查询接口提供） |

### 11.2 实现细节补充（5 项已落地）

| # | 补充 | 落地位置 |
|---|---|---|
| 1 | 工作区物理删除顺序 | Sprint 1 描述：计算记录（含 equipment_list）→ workspace；Sprint 1 实施前 `inspector.get_foreign_keys()` 复核 FK ON DELETE 行为 |
| 2 | 装饰器 db 参数约定 | 架构决策 20：`db: AsyncSession` 必须为关键字参数；CLAUDE.md + P4 模板（TODO-023） |
| 3 | Sprint 1 cron_jobs 仅配 workspace 清理 | Sprint 1 描述：避免 Sprint 1 启动时引用 cia_tasks.py 不存在模块；Sprint 3 追加 `cron_cia_delta` / `cron_cia_full` |
| 4 | CIA 扫描两层（1 分钟增量 + 5 分钟全量） | 架构决策 18：利用 `data_lineage.timestamp` 已有字段，零 migration；P1-MVP 不加索引（TODO-022 推迟到 P4 中后期） |
| 5 | ALLOWED_TRANSITIONS 守卫矩阵测试前置 | 架构决策 21：Sprint 2 启动前先写矩阵 + 单元测试作为可测试显式文档，再实现 transition 逻辑 |

### 11.3 ADR-0025 v5 修正版

| v4 原文 | v5 修正 |
|---|---|
| 扫描失败 3 次设备记录标记 `AFFECTED_UNKNOWN` + 告警（字段是否存在待决） | 复用 `equipment_list.actual_data_status = NEED_RECALC`（P0 已有枚举值）+ `audit_logs.action=CIA_NOTIFIED` + `remarks="SCAN_FAILED"` + 告警；零 Schema 变更 |

### 11.4 LOC 影响

- 净增 ≈ 0（v5 仅文档/逻辑调整，未扩大 Sprint 边界）
- 测试增：ALLOWED_TRANSITIONS 守卫矩阵 9 × 13 = 117 用例框架（实施前全部通过）

---

## 十四、P1 计划 v6 变更（2026-09-01 集成第四轮审阅 — 文书修正）

### 14.1 矛盾修正（1 项）

| # | 矛盾 | 修正 |
|---|---|---|
| 1 | §十一 编号重复（v5 变更 + 未解决问题清单同名）+ §七 P1.2 范围位置错乱 | 第二个 §十一 → §十二（未解决问题清单）；§七 → §十三（P1.2 范围） |

### 14.2 误报澄清（1 项）

| # | 误报 | 实际情况 |
|---|---|---|
| 2 | 架构决策 4 装饰器签名 `source_param` 单数残留 | **已修正**（line 79 已为 `@lineage(sources=[("stream_id", "STREAM")], ...)`，grep 确认 4 处全为 `sources=`）；§11.1 表条目保留作为 v5 变更历史 |

### 14.3 内容补充（3 项）

| # | 补充 | 落地 |
|---|---|---|
| 1 | Sprint 3 设备联动残留 `AFFECTED_UNKNOWN` 文字 | 改为 `actual_data_status = NEED_RECALC` + `audit_logs.action=CIA_NOTIFIED` + `remarks="SCAN_FAILED"` + 告警（与 ADR-0025 v5 一致） |
| 2 | 前端 TS 类型文件缺失 | §四 文件结构新增 `src/types/{records,workspace,checklist}.ts` |
| 3 | AuditAction 长度校验测试缺失 | Sprint 1 测试清单新增 `AuditAction 枚举值≤50 字符约束`（`tests/test_audit.py::test_audit_action_max_length_50`） |

### 14.4 LOC 影响

- 净增 ≈ 0（v6 仅文书与测试增项，无代码功能扩展）
- 测试增：1 条 AuditAction 长度校验

### 14.5 当前章节结构（已无编号冲突）

§一 范围 → §二 执行阶段 → §三 架构决策 → §四 文件结构 → §五 验收标准 → §六 已决问题 → §八 Failure modes → §九 GSTACK REPORT → §十 v4 变更 → §十一 v5 变更 → §十二 未解决问题 → §十三 P1.2 范围

---

## 十二、未解决问题清单（v4 截至 2026-09-01）

### 阻塞 P1-MVP 启动的（0 项）
无

### 不阻塞但需 Sprint 内澄清的（2 项）
- Sprint 1 ARQ worker 启动顺序与 FastAPI startup 哪个先？（计划假设 ARQ worker 后启动，让 FastAPI 先暴露 health）
- Sprint 2 状态机事件总线是否真要落地？（外部视角建议但非必须；先以当前 Service 一体化实现，必要时再重构）

### 仍待 IT/外部确认（3 项）
- SPEC P1-OPEN-001 MFA 基础设施现状（仅 P1.2 客户代录需要）
- SPEC P1-OPEN-004 版本快照回滚功能（已确认 P1 全期不做）
- P0 53 表是否包含 `record_change_snapshots`？P1 计划隐含 yes，落地前需 `inspector.get_table_names()` 复核

### v4 实施审阅新增（3 项）
- **P4 API 模板**：P4 计算函数需遵循"先创建记录 → flush → 再收集依赖"模式；需写入 CLAUDE.md 和 P4 模块开发模板（TODO-023 落地）
- **StateTransition 枚举 13 项与 SUP-007 路径一致性**：实施前需对照 SUP-007 §3.1 复核所有 9 态的合法转移矩阵（已基于 SUP-007 草拟，但需 Sprint 2 实施前最终确认）
- ~~**CIA 扫描失败 3 次后设备 `AFFECTED_UNKNOWN` 标记**：此字段是否新增到 equipment_list 表？若是则需 Sprint 3 migration（待决）~~ **v5 已裁决**：复用 `equipment_list.actual_data_status = NEED_RECALC`，不新增字段（ADR-0025 v5 修正版）

### v5 实施审阅新增（3 项）
- **物理删除顺序与 FK 约束**：Sprint 1 实施前需 `inspector.get_foreign_keys()` 复核 streams/workspaces/计算表 FK 的 ON DELETE 行为；清理代码实现按 `计算记录 → streams → workspace` 顺序手动 delete
- **P4 装饰器 db 关键字参数约定**：CLAUDE.md 与 `docs/p4-template.md` 模板（TODO-023）；约束函数签名 `async def calculate_xxx(db: AsyncSession, *, param1, param2) -> RecordType`
- **ALLOWED_TRANSITIONS 守卫矩阵测试前置**：Sprint 2 启动前先写守卫矩阵 + 单元测试作为可测试显式文档（架构决策 21），再实现 transition 逻辑

---

## 十三、P1.2 范围（P8 前补齐）

| 项 | 估计 LOC | 估计测试 |
|---|---|---|
| deliverable service + 5 API（创建/issue/versions/snapshot/proxy） | ~1000 | ≥25 |
| customer-approval/attachment（multipart + SHA-256 + 文件存储 backend） | ~400 | ≥10 |
| RevTimeline + LineagePanel + ChangeNotification 前端组件 | ~800 | — |
| 1 次 alembic 迁移（如需） | — | — |
| **P1.2 合计** | **~2200** | **≥35** |