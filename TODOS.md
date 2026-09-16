# TODOS.md — PCS 延后工作清单

> 由 /plan-eng-review 2026-08-29 建立。每项含来源裁决编号，完成后移除并在 STATUS.md 记录。

## TODO-001: 前端测试基建（vitest + RTL）

- **状态**: P1 第一周 | **来源**: eng-review 2026-08-29（7A）
- **What**: 引入 vitest + @testing-library/react；写首批 3 个测试文件
- **Why**: `apiFetch` 的 401 静默刷新重试（时序图 ⑫–⑱）、`RequireAuth` 守卫、登录表单校验是前端最易错逻辑，P0 期间全靠 Task 13 手工联调，无自动护栏
- **首批清单**:
  - `src/services/api.test.ts`：401 → refresh 成功 → 原请求重试成功；refresh 也 401 → logout + 跳 /login
  - `src/App.test.tsx`：无 token 访问 `/` → Navigate `/login`；有 token → 渲染布局
  - `src/pages/LoginPage.test.tsx`：空表单校验提示；`VITE_ENABLE_MOCK_AUTH=true` 时 Mock 角色下拉渲染、false 时不渲染
- **Context**: P0 骨架期 UI 高速变动，测试价值密度低故未建（SPEC-P0-FE-001 验收仅 lint+build）。P1 引入时同步把 `vitest run` 接入 npm scripts
- **Depends on**: 无（P1 启动即可做）

## TODO-002: refresh token 吊销机制（token_version）

- **状态**: P1 | **来源**: eng-review 2026-08-29（2A）
- **What**: users 表加 `token_version` 列；`create_token` 写入 claim；`decode_token` 校验
- **Why**: 无状态 JWT 的 logout 只清前端内存，refresh token 被盗后 7 天有效期内无法作废
- **Context**: P0 内部部署（HTTPS + 令牌仅内存）风险可接受；P1 加列 + Alembic 增量迁移成本低，decode 集中在 `app/core/security.py` 一处
- **Depends on**: P0 完成（users 表已建）

## TODO-003: JSONB GIN 索引

- **状态**: P1 报表/列表查询端点落地时 | **来源**: eng-review 2026-08-29（8A）
- **What**: 按实际查询模式为高频 JSONB 列建 GIN 索引（候选：`streams.composition_json`、`equipment_list.design_parameters_json`、`deliverable_versions.record_snapshot_json`）
- **Why**: P0 查询模式未定，盲建拖慢全部写入且大概率选错列；SPEC 3.4 "JSONB 支持索引查询"由此兑现
- **Depends on**: 首个按 JSONB 内容过滤的端点（P7 设备查询或 P8 报表）

---

## TODO-004: CORS 中间件

- **状态**: P1 部署架构确定后 | **来源**: P0 review 2026-09-01（P0-1）
- **What**: `app/main.py` 加 `CORSMiddleware`，`Settings.allowed_origins: str = "http://localhost:5173"`，env 注入生产域名
- **Why**: P0 无生产部署，dev 态靠 Vite proxy 掩盖；前后端分开部署时 preflight 会 403
- **Depends on**: 部署架构（是否同域 / Nginx 反代 / 独立域名）

## TODO-005: LDAP TLS

- **状态**: P1 真实 AD 连接时 | **来源**: P0 review 2026-09-01（P0-3）
- **What**: `Settings.ldap_use_start_tls: bool = False`；`ldap3.Server(..., use_ssl=startswith("ldaps://"))` 或 `conn.start_tls()`
- **Why**: P0 仅用 Samba 测试域，生产明文 bind 不可接受
- **Depends on**: IT 提供 LDAPS 端口 + CA 证书

## TODO-006: 认证安全加固（限流 + 审计）

- **状态**: P1 生产部署前 | **来源**: P0 review 2026-09-01（P0-4）
- **What**:
  - 加 `slowapi` 依赖，`/auth/login`、`/auth/refresh` 装饰 `@limiter.limit("10/minute")`
  - login 成功/失败均写 `audit_logs`（user_id nullable、action 枚举 LOGIN_SUCCESS / LOGIN_FAILED、ip 字段）
- **Why**: P0 骨架期无速率限制可被暴力破解；审计留痕
- **Depends on**: TODO-007（JWT 过期细分）一并落地以减少日志噪声

## TODO-007: JWT 过期/无效细分

- **状态**: P1 前端测试基建同窗口 | **来源**: P0 review 2026-09-01（P2-1）
- **What**: `app/core/security.py` 拆 `jwt.ExpiredSignatureError → PcsError(code="AUTH_EXPIRED_TOKEN")` vs `jwt.InvalidTokenError → PcsError(code="AUTH_INVALID_TOKEN")`；前端 axios 拦截器据此决定 refresh 还是清 session 跳 /login
- **Why**: 当前均映射为 INVALID_TOKEN，前端无法区分"刷新一次"和"重新登录"
- **Depends on**: TODO-001（前端测试基建）

## TODO-008: equipment_list FK 约束名 rename 迁移

- **状态**: P1 第一周 | **来源**: P0 review 2026-09-01（P2-7）
- **What**: alembic 增量迁移 `op.execute("ALTER TABLE equipment_list RENAME CONSTRAINT fk_equipment_list_type_code TO fk_equipment_list_type_code_composite")`
- **Why**: 模型已 rename；DB 端约束仍为旧名。下次 `alembic check` 会产生 diff
- **Depends on**: 无

## TODO-009: 血缘递归深度限制

- **状态**: P1 血缘引擎开发时 | **来源**: P0 review 2026-09-01（收尾-2）
- **What**: `data_lineage.parent_lineage_id` self-FK 递归查询设上限 ≤ 8
- **Depends on**: P1 血缘 API 端点

## TODO-010: 多态 FK 应用层校验

- **状态**: P1 deliverable binding service 层 | **来源**: P0 review 2026-09-01（收尾-3）
- **What**: `deliverable_record_bindings`（record_type + record_id）多态 FK 无 DB 约束，service 层校验 record_id 在对应 record_type 表中存在
- **Depends on**: P1 deliverable 模块

---

## TODO-011: record_change_snapshots snapshot_status + ADR-0024

- **状态**: P1 Sprint 2 | **来源**: gstack eng-review Issue 9（2026-09-01）
- **What**: `record_change_snapshots` 表追加 `snapshot_status String(20)` 字段（ACTIVE/CONSUMED/ABANDONED，默认 ACTIVE）；写 ADR-0024 修订 ADR-0012 "CHECKED→STALE 自动存快照"为"CHECKED→CHANGE_PENDING / STALE→CHANGE_PENDING / CHECKED→DRAFT 时创建快照"；同步 DICT-ALL-003 → V3.2
- **Why**: 决议 9 锁定：STALE 期间数据未修改，提前存快照是浪费存储；新设计存储减半且与 ADR-0012 等价
- **Depends on**: 无（Sprint 2 migration 一并执行）

## TODO-012: make_draft_record fixture 覆盖 17 种 record type

- **状态**: P1 Sprint 1 测试基建 | **来源**: gstack eng-review Issue 9 + 外部视角 4
- **What**: `tests/conftest.py` 提供 `make_draft_record(record_type, **kwargs)` fixture，覆盖 RECORD_TYPE_REGISTRY 全部 17 类（16 calc + equipment_list）；P1 测试基础设施
- **Why**: Sprint 2+ 测试需要直接造 DRAFT 记录；外部视角指出 doc_no_sequences UNIQUE 在 Sprint 1 即生效，fixture 需默认填值防冲突
- **Depends on**: RECORD_TYPE_REGISTRY 落地（Sprint 1）

## TODO-013: STALE→CHANGE_PENDING 时记录 change_pending_since + old_record_hash_before_change

- **状态**: P1 Sprint 2 | **来源**: gstack eng-review Issue 9 验证细节
- **What**: StateMachineService 在 STALE→CHANGE_PENDING 时记录 `record.change_pending_since = now` + `record.old_record_hash_before_change = record.record_hash`（保存 CHANGE 前的 STALE 基线哈希，用于后续哈希重算校验）
- **Why**: 撤销批准需校验当前哈希是否仍匹配快照哈希；不存 STALE 期哈希则撤销语义模糊
- **Depends on**: TODO-011（snapshot_status 字段）

## TODO-014: 设备联动最终一致性窗口声明（ADR-0025）

- **状态**: P1 Sprint 3 | **来源**: gstack eng-review 外部视角 3（2026-09-01）
- **What**: ADR-0025 明确：CHECKED 状态变化 → 设备同步延迟 ≤ 5 分钟（CIA cron 兜底）；声明中间窗口容忍度（"状态 CHECKED 但设备记录 STALE"最长 5 分钟）；CI/前端需要展示"设备同步中"标记
- **Why**: 状态机 Sprint 2 同步 + 设备联动 Sprint 3 异步 → 中间窗口未被声明则上线后易引发 P4 用户困惑
- **Depends on**: cia_engine 实现

## TODO-015: lineage_ctx 事务回滚清理语义文档化

- **状态**: P1 Sprint 3 | **来源**: gstack eng-review 外部视角 P4 接入验证
- **What**: lineage_tracker.py docstring + SPEC-P1 V1.3 文档：ctxmgr 内 add_source 的 entry 在 session.rollback() 时由 SQLAlchemy 自动清理（依赖 session.add + transaction rollback 语义）；装饰器 wrapper 内 track 同理；P4 开发者无需手写清理代码
- **Why**: 外部视角指出"零侵入"承诺需明确：lineage_ctx 是否事务回滚自动清理
- **Depends on**: lineage_tracker 实现

## TODO-016: ARQ 失败注入测试 + DLQ 触发逻辑测试

- **状态**: P1 Sprint 3 | **来源**: gstack eng-review 外部视角测试盲点 1
- **What**: tests/test_arq_failure.py：mock cia_tasks 抛异常 → ARQ 默认 3 次重试 → 失败入 DLQ；mock Redis 断开 → worker lifespan 重启；mock concurrent enqueue 同 project_id → 任务去重
- **Why**: dev/prod 双形态测试-生产漂移 + 失败路径是 ops 关键路径
- **Depends on**: ARQ 配置（Issue 1）

## TODO-017: P4 接入验收 e2e 测试从 1 扩展到 4

- **状态**: P1 Sprint 3 验收 | **来源**: gstack eng-review 外部视角 5
- **What**: tests/test_p4_integration.py：FLASH / PUMP / PIPE / PIPE_NET 四个模块各写一个 e2e：模拟"计算 → DRAFT → SUBMIT → IN_APPROVAL → CHECKED"全路径；验证 @lineage 装饰器自动写 data_lineage（source + target 哈希）；验证 StateMachineService.transition 落 audit_logs
- **Why**: 单一 FLASH e2e 不能证明 @lineage + StateMachineService 对 PUMP/PIPE/PIPE_NET 同样"零侵入"
- **Depends on**: P4 模块骨架（mock 即可，不需 P4 全部实现）

## TODO-018: ARQ 自动清理任务独立文件结构

- **状态**: P1 Sprint 1 | **来源**: gstack eng-review 外部视角技术债
- **What**: workspace 自动清理任务放独立 `app/workers/workspace_tasks.py`（独立于 cia_tasks.py）；WorkerSettings 注册两个 task 入口
- **Why**: 任务职责分离；后续 PROD 监控/重试策略可分别配置
- **Depends on**: Sprint 1 ARQ 配置（Issue 1）

## TODO-019: CORS prod 启动校验函数位置

- **状态**: P1 Sprint 1 | **来源**: gstack eng-review 外部视角技术债
- **What**: 在 `app/main.py` lifespan startup 阶段调用 `_validate_cors_for_production()`：若 `is_production` 且 `allowed_origins` 包含 `*` 或未设置 → raise RuntimeError；明确断言函数位于 lifespan 而非 middleware（middleware 阶段太晚）
- **Why**: prod 启动期早失败；避免 middleware 404 后才发现 CORS 错配
- **Depends on**: Sprint 1 CORS 配置（Issue 5）

## TODO-020: ADR-0012 + ADR-0024 交叉引用 + SPEC/DICT 同步

- **状态**: P1 Sprint 2 | **来源**: gstack eng-review 外部视角技术债
- **What**: ADR-0024 写完后：(a) ADR-0012 加注"已由 ADR-0024 修订快照时机"；(b) SPEC-P1 V1.2 §3.2.2 → V1.3 更新快照语义章节；(c) DICT-ALL-003 V3.1 → V3.2 表38加 snapshot_status 字段；(d) SUP-007 §3.1 文字同步
- **Why**: 多文档一致性；防止 P4 开发期读旧文档误用快照 API
- **Depends on**: TODO-011（snapshot_status 字段落地）

## TODO-021: 同步 engine 与 asyncpg engine 连接池配置与 lifespan 顺序

- **状态**: P1 Sprint 1 | **来源**: gstack eng-review 外部视角技术债
- **What**: `app/db/session.py` 双引擎连接池：sync engine 保留 `pool_size=5, max_overflow=45, pool_pre_ping=True, pool_timeout=30, pool_recycle=1800`（P0）；async engine `pool_size=10, max_overflow=20`（P1 工作负载更大）；lifespan startup 先建 async engine + probe 连接，再 init sync engine，shutdown 反向
- **Why**: 双引擎同进程共存，避免启动顺序错乱导致 ARQ 任务拿不到 session
- **Depends on**: Sprint 1 双引擎落地（Issue 1）

## TODO-022: data_lineage timestamp 索引（P4 中后期）

- **状态**: P4 开发中后期（data_lineage > ~10⁴ 条时）| **来源**: gstack eng-review 第三轮补充 4（2026-09-01）
- **What**: `CREATE INDEX ix_data_lineage_timestamp ON data_lineage(timestamp)`；P1-MVP 阶段不加（全表扫 <100ms）
- **Why**: CIA cron 每 1 分钟扫最近 7 天血缘条目；P4 计算模块大量创建记录后血缘量增长，按需评估
- **Depends on**: 性能测试触发

## TODO-023: P4 计算函数装饰器签名约定写入 CLAUDE.md 和 P4 模板

- **状态**: P1 Sprint 3 启动前 | **来源**: gstack eng-review 第三轮补充 2（2026-09-01）
- **What**: CLAUDE.md 新增"P4 计算函数签名约定"章节：`async def calculate_xxx(db: AsyncSession, *, param1, param2) -> RecordType`，db 必须为关键字参数；新建 `docs/p4-template.md` 装饰器使用模板
- **Why**: 装饰器从 `kwargs["db"]` 获取，函数签名约束是契约
- **Depends on**: 无（实施前即可）

---

## 已裁决不做（非 TODO）

- **CI/CD 流水线（原 SPEC-P0 §3.2.5 / P0-CICD-001）**：单人开发不需要。多人协作时再作为新需求重新提出。（用户裁决 2026-08-29，eng-review Issue 9）

---

## ✅ P1-MVP 已完成（2026-09-01）

- **核心交付**：状态机（Sprint 2）+ 血缘追踪 LineageTracker/@lineage/lineage_ctx（Sprint 3）+ CIA 引擎 scan/propagate/propagate_to_equipment（Sprint 3）+ 工作区 CRUD + 输入清单 ChecklistDashboard
- **质量门**：`ruff check` ✅ / `mypy`（Sprint 3 5 文件）✅ / `pytest` 138 passed（计划 ≥120）
- **迁移**：Alembic 升级 pcs + pcs_test 双侧实跑通过（Sprint 3.1/3.2）
- **前端**：`tsc --noEmit` ✅ / `vite build` ✅（dist 297.53 kB gzipped）
- **e2e 验收**：test_p4_flash_full_path（FLASH-like 计算 + 装饰器 + 状态机 DRAFT→IN_APPROVAL→CHECKED 全路径）
- **关键 bug 修复**：`updated_at` `onupdate=func.now()` 导致 in-memory `state.dict` 与 DB 漂移，CIA scan 永远 mismatch（测试侧 refresh 同步，生产侧 SELECT 自然拿到正确值）

## ⏭️ P2 Sprint 1 Step 0 后续修正项（V3.4 §第六部分路线图）

DICT V3.4 已发布（`spec/PCS-DICT-ALL-003 V3.4.md`），配置层 8 表 ORM 修正 + data_lineage/audit_logs 反向更新 + 命名偏差 21 处裁决已落地。剩余修正项按阶段推进：

### TODO-024: equipment_list 完整对齐 DICT V3.3（~3h）
- **状态**: P2 Sprint 2 | **来源**: D13 Schema 审计
- **What**: equipment_list 当前 ORM 18 列 vs DICT 74 列，缺 ~56 字段（D3 审计清单）。需补 package_no / sub_project / unit_no / tag_in_3d / tag_in_esr / actual_key_parameter_json / 多个 vendor/order/cost/installation/weight/paint/drawing/registration 字段；rename 6 处命名（equipment_description / installation_location / net_weight / paint / process_engineering_remarks / flowsheet_drawing_number）
- **Why**: P3 集成层启动必备；equipment_list 是设备联动/CIA/代录/报表的中央表
- **Depends on**: DICT V3.4（已发）

### TODO-025: pump_results 补 6 列（~3h）
- **状态**: P4 Task 0 | **来源**: D13 Schema 审计
- **What**: pump_results 缺 `dependencies_json`（D2 裁决）+ `performance_curve_json` / `seal_bearing_json` / `instrumentation_json` / `test_inspection_json` / `remark`（D10 裁决）
- **Why**: P4 PUMP 模块启动阻塞；D2/D10 spec 已落但 ORM 未跟上
- **Depends on**: P4 Task 0

### TODO-026: P5 模块平铺字段/data_sheet_json 展开（~9 表，各模块开发时顺带）
- **状态**: P5 各模块开发期 | **来源**: D13 Schema 审计
- **What**: vessel_results / heat_results / cv_results / pipe_network_results / restriction_results / flare_system_results / cooling_tower_results / sep_equip_results / filtration_results / open_channel_results 当前 ORM 用 input_json/output_json 简化容器，DICT 要求各模块平铺字段或专属 *_json 子结构。按 SUP-001~014 整合（V3.3 第三部分）补齐
- **Why**: 数据结构与 SUP 文档对齐，便于查询/报表
- **Depends on**: P5 各模块启动

### TODO-027: cost_est_results 补 RecordMixin（~P7 启动时）
- **状态**: P7 开发时 | **来源**: D13 Schema 审计
- **What**: cost_est_results 当前 ORM 5 列（cost_est_id/equipment_id/estimated_cost/currency/cost_index_year/created_at），缺 RecordMixin（project_id/workspace_id/sign_status/record_hash）+ tag_number + cost_estimate_json；equipment_id UNIQUE 与 DICT 不一致
- **Why**: P7 成本估算模块需走状态机 + 审批
- **Depends on**: P7 启动

### TODO-028: 10 张计算表主键 rename 落地（每模块各 ~1h）
- **状态**: P5 各模块开发时 | **来源**: D13 Schema 审计 §4.1
- **What**: vessel_id→vessel_calc_id / heat_exchanger_id→heat_calc_id / cv_id→cv_calc_id / net_id→network_id / restriction_id→orifice_calc_id / ct_id→ct_calc_id / psychro_id→psychro_calc_id / sep_equip_id→sep_calc_id / filter_id→filter_calc_id / channel_id→channel_calc_id。DICT 为准，ORM 逐步 rename
- **Why**: ORM↔DICT 命名统一；后续审计/比较免歧义
- **Depends on**: P5 各模块启动

### TODO-029: P2 Sprint 4 报表 perf 预算测试落地（D26）
- **状态**: P2 Sprint 4 启动时 | **来源**: D26 gstack-plan-eng-review
- **What**: 加 `test_cia_propagation_perf_budget` — 100 下游 record / depth 8 / ≤500ms 预算。超出则触发 SELECT IN 批量优化。
- **Why**: CIA 传播当前 N+1，负载小可不优化；但 P4 计算模块接入后下游 record 可能破千，预算测试提前锁定 perf 基线
- **Pros**: 提前发现性能回归；提供优化触发条件
- **Cons**: 多一个测试用例
- **Depends on**: P2 Sprint 4 启动

### TODO-030: openpyxl 导出流式写入（D28 触发条件）
- **状态**: 条件触发（test_export_perf_budget 失败） | **来源**: D28 gstack-plan-eng-review
- **What**: 切换 `openpyxl.Workbook(write_only=True)`，逐行 `ws.append()` 写入；放弃 in-memory 模式
- **Why**: 当前实现 10k 行 × 20 列 ≤2s + ≤50MB 内存预算；超出则启用流式（~30min 工作量）
- **Pros**: 内存占用降到几 MB（流式）
- **Cons**: write_only 不支持读取现有 workbook、样式受限；调试更复杂
- **Depends on**: P2 Sprint 4 — test_export_perf_budget 必须先落地



## ⏭️ 延后至 P1.2

- TODO-014：设备联动最终一致性窗口声明（ADR-0025）
- TODO-015：lineage_ctx 事务回滚清理语义文档化
- TODO-016：ARQ 失败注入 + DLQ 测试
- TODO-017：P4 接入验收 e2e 从 FLASH 扩展到 PUMP/PIPE/PIPE_NET
- 交付物生成 / 变更单 / 客户代录 / LineagePanel / ChangeNotification / RevTimeline
- `mypy --strict`：P1.2 收尾时启用
- 快照归档清理：P1.2

## 🔓 P1-MVP 关闭后可启动

P4（FLASH / PIPE / PUMP / PIPE_NET 计算模块接入）

- **P4 Task 0（FLASH 开发前，~6h）**：合并 D4 + D5 + D8 三项，1 个工作日内完成。
  - **D4** 装饰器语法扩展：`@lineage` 接受 `sources: list[tuple[str, str]]` + `target_type` / `dependency_type` 参数，向后兼容裸 `tuple[str, ...]`。
  - **D5** source_record_hash 抓取：按参数名提取 UUID → 查 RECORD_TYPE_REGISTRY 映射 ORM 类 → 抓 source record_hash 写入 `data_lineage.source_record_hash`。
  - **D8** importlinter 架构契约：`contracts.py` 定义分层依赖规则（FLASH/PIPE/PUMP/PIPE_NET 禁止 import `common_fluid_props`；PUMP/PIPE_NET 禁止 import `pipe_calc`），`test_architecture_contracts.py` 在 pytest 执行。
  - **测试更新**：兼容性测试 + 新语法覆盖。
  - 文档基线：DF-001 §4.2 + §4.3 + §9 v1.1 已加注此扩展计划与 importlinter 护栏。
- **P4 Sprint 2（CIA 跨表传播）**：实现 §4.4 双模式传播。包含 D6（新增 `CIAEngine.propagate_from_source(source_type, source_id)` 方法 + `_mark_stale` 幂等性增强 + 递归传播带访问集防环 + 深度限制 ≤8）。触发顺序：scan → 自身 STALE → 反查 `data_lineage.source_ref_type/source_ref_id` → 标下游 STALE → 设备联动。DF-001 §7.2 加注 + §4.4 已锁定。
- **PUMP 模块起步先决项**：`pump_results` 表新增 `dependencies_json` 列（JSON 内含 stream_id / suction_pipe_id / discharge_pipe_id 全部 nullable + 派生 all_checked），由 DICT-011 V1.1 §2.5 + §2.5.1 裁决（D9）。Alembic 增量迁移 + 模型字段 + 三层 FK 校验：① Service 写入时 SELECT 验证引用存在；② 状态机守卫在 SUBMIT_FOR_CHECK 前计算 all_checked；③ CIA scan 周期比对 source_record_hash + 孤儿检测。
- **CIA scope 收紧**：DICT/DF-001 再次复核——`CIA_TRACKED_TYPES` 当前为 `("PipingResult",)`；FlashResult 不在扫描范围（CIA 不直接扫 FLASH，由血统矩阵判定）。PUMP/PIPE_NET 通过 equipment linkage 传播 STALE，不直接扫。


## TODO-031: preconditions 接入 run_unit_tests 发布门禁
- **状态**: ✅ 已完成（2026-09-04，用户裁决提前至本窗口，不等 Sprint 1.12）| **来源**: 终审 Important#4（R22 裁决 2026-09-04）
- **What**: FormulaService.run_unit_tests 读 content_json["preconditions"]，调用已实现的 run_unit_tests_with_preconditions（~10 行 + 2 测试）；当前该方法零调用方，V1.4 §3.2.2a 仅引擎层闭环
- **Depends on**: ~~Sprint 1.12（formula test/preview 端点同窗）~~ 已接线：PUBLISH 端点经 run_unit_tests 自动触发 pre/post 校验，PreconditionViolation → 全局 handler 422 信封；2 测试入 tests/api/v1/test_config.py

## TODO-032: 四个真库测试文件迁 conftest SQLite fixtures
- **状态**: 随 P1.2 doc_no 原子分配波 | **来源**: 终审 Important#5（2026-09-04）
- **What**: test_category3_seeds / test_toe_conversion_service / test_detail_templates / test_htri_template_schema 从 get_async_session_factory()（真 PG）迁到 db_session fixtures；test_detail_templates 每跑提交 2+2 行无清理、永久推高 template_version_seq 的问题一并解决
- **Depends on**: P1.2

## TODO-033: Sprint 1.9 终审 DEFER 清单（终审 minor，全部非阻塞）
- **状态**: 待窗口 | **来源**: Sprint 1.9 whole-branch 终审（2026-09-06，ad25700..b458b97 干净闭环，295 passed）
- **What**（按建议归置窗口）:
  - Sprint 2 前端对接须知：`ProjectPipeClassResponse.pipe_class` 恒 null（ORM 无 relationship，每等级需二次 GET）；equip-lib search `limit>200` 现返回 422（原为 clamp）
  - P3 物流向导：CATEGORY_3 新三表 rows 为 dict（既有六表为 list，读取方需知）；OBSOLETE 等级字段仍可 PUT 覆写（spec 只裁状态单向、未禁字段编辑，P3 前裁决是否冻结）；`commissioning_date` 无 YYYY-MM-DD 格式校验（前端可补）
  - 卫生批（一 cleanup commit 可收）：main.py:28「6 张」注释过时；petroleum_service.py:34 `_CONVERT` 悬置注释 + 测试「≈0.494」→0.5061 文案 + 两文件首行路径注释 wart；pipe_class_service `_STATUS_OK` 死常量；creates_six 用例改名；IMPORT_BAD_HEADER 422 补一条 6 行用例；import 空单元格 `str(None)→"None"` 入库缺口；equip_lib description 未截断（name 已截）
  - 计划文档：Spec 引用 §3.2.4 应为 §3.2.3（P2-COEF-001 三行系数表）；§3.2.5 CoolProp 行与 iapws 替代实现的对应关系 P3 复核时回写
- **Depends on**: 各自窗口（Sprint 2 / P3 / 卫生批随时）

### TODO-034: Excel 导入模板版本管理（P4 启动时）
- **状态**: P4 | **来源**: plan-eng-review 2026-09-08（用户裁决 P4 再议）
- **What**: `stream_import_template.xlsx` 加 `template_version: str` 元数据（写入 sheet0 隐藏行或文件属性）；导入时校验版本兼容，不兼容返 STREAM_TEMPLATE_VERSION_MISMATCH 错误码 + 升级指引 URL
- **Why**: P3 阶段模板固定为 V1；P4 起字段可能增减，旧模板导入会缺列/多列；无版本管理会导致静默数据丢失
- **Context**: 用户 2026-09-08 显式裁决 P4 再议；本 Sprint 仅生成 V1 模板，无版本字段
- **Depends on**: P4 SIM 扩展启动

### TODO-035: 物流校验规则 22 条 P4 补全
- **状态**: P4 | **来源**: plan-eng-review 2026-09-08（user 决议 P3 仅骨架）
- **What**: spec §第四部分 22 条校验规则，P3.2 SIM-7 仅实现 3 条典型（相态矛盾 / 偏差 >5% / MW 优先级）。P4 补齐剩余 19 条：饱和蒸汽压、临界压缩因子、Cv 计算边界、雷诺数判定、热力学一致性等
- **Why**: 完整校验是工艺计算可信度基础；P3 阶段骨架够用，P4 工艺计算模块接入需全部 22 条
- **Context**: P3.2 SIM-7 已落 BLOCK/WARN/INFO 三级骨架；新规则仅需添加 `ConflictResolver.check_<rule>()` 方法
- **Depends on**: P4 SIM 扩展 + 工艺计算模块接入

### TODO-036: StreamSignStatus P4 ALTER TYPE 9 态扩展
- **状态**: P4 启动时 | **来源**: spec V1.6 §P4-OPEN-010（已记录 P4）
- **What**: PG enum 'streamsignstatus' 当前 4 态（DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED），P4 扩展为 P1 记录层 9 态全集（DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED/STALE/CHANGE_PENDING/CHANGED/REVERSAL_PENDING/OBSOLETE）。`ALTER TYPE streamsignstatus ADD VALUE 'STALE' ...`（PG enum value add 不可逆，需独立 migration + 备份）
- **Why**: SIM-4 已落 4 态；P4 接入工艺计算模块后状态机需 STALE/CHANGE_PENDING/CHANGED 触发 CIA 引擎传播
- **Context**: spec §P4-OPEN-010 已锁定；`ALTER TYPE ... ADD VALUE` 不可逆 → P3 必须先备份 enum definition
- **Depends on**: P4 工艺计算模块启动

### TODO-037: unreliable=True 物流下游计算拒绝（P4）
- **状态**: P4 | **来源**: plan-eng-review 2026-09-08（用户裁决 P4 再议）
- **What**: P3 SIM-10 仅标记 `unreliable=True` 在 PRO/II NOT_CONVERGED/ABORTED 单元产品上；P4 工艺计算器调用接口需硬拒绝：`POST /api/v1/calculate/...` 校验所有 input stream 的 unreliable 字段，任意 True → 422 STREAM_UNRELIABLE_BLOCKED + 列出不可靠流名
- **Why**: 不可靠数据进入计算会污染下游；仅标记不阻止等于没做
- **Context**: user 2026-09-08 显式裁决 P3 仅标记；P4 工艺计算模块启动时再实现硬拒绝
- **Depends on**: P4 工艺计算模块接入 + CIA 引擎

### TODO-038: PRO/II 5 样例 .inp 文件 fixtures 正式入库
- **状态**: SIM-2 启动时 | **来源**: plan-eng-review 2026-09-08
- **What**: 当前 SIM-2 计划从历史对话文本重建 5 个 .inp 文件（石油分馏 / NH3-H2O 未收敛 / MIXER+COLUMN 含侧线 / 酸性水汽提 / FCC 催化裂化）到 `pcs-backend/app/seeds/proii_samples/`。后续若有真实用户 .inp 文件，需整理脱敏后入库作为回归测试基线（覆盖更复杂工艺配置）
- **Why**: 单元测试基线完备性取决于样例多样性；用户真实工艺配置是质量保证金标准
- **Context**: SIM-2 Step 3 由我从对话历史文本重建；P3 Sprint 末若有真实项目 .inp 可用，整理脱敏后入 git
- **Depends on**: SIM-2 启动 + 后续真实项目数据脱敏流程

---

## ⏭️ P4.5 批 3 延后项（2026-09-16 落地时识别）

批 3（Tasks 27-35）前端计算模块 + PMS/BEDD/向导 完成；以下为实现中显式标记"留 P5 / 完整版"的延后项。

### TODO-039: 前端 7 个 type 占位文件 P5-1 由 api.d.ts 替换
- **状态**: P5-1（api:gen 输出后） | **来源**: 批 3 实施（2026-09-16，7 个 type 文件加 `TODO(api-migration)` 标注）
- **What**: 当前 `pcs-frontend/src/types/{pipeClass,flash,pipe,pump,pipeNet,pms,common}.ts` 是 V1 mock props shape（与 P5-1 真实 OpenAPI 不一定同字段顺序/枚举值/可空性）。P5-1 calculate 入口契约冻结后，由 `src/types/api.d.ts` 替换这 7 个文件；前端 import 全部从 `./api` 引
- **Why**: 当前类型来源不唯一（mock types 与 OpenAPI types 并存）；P5-1 后必须以 OpenAPI 为准
- **Context**: 批 3 计划修订 item 6 已记录"前端类型来源唯一性"
- **Depends on**: P5-1 OpenAPI 契约冻结

### TODO-040: PIPE_NET 完整版（reactflow / 自动布局 / 环路检测 / 序列化）
- **状态**: PIPE_NET 完整功能 sprint | **来源**: Task 33 PipeNetTopologyPage 实施（2026-09-16，提交 e5ea389）
- **What**: V1 极简版手写 SVG 渲染 + 基础校验；完整版需：reactflow 拖拽节点 / 自动布局算法（dagre 或 ELK）/ 环路检测算法（DFS）/ 拓扑序列化导入导出
- **Why**: 拓扑是 PIPE_NET 模块核心；V1 占位不足以支持工程实用
- **Context**: Task 33 提交明确写"V1 极简版：手写 SVG 渲染 + 基础校验；完整功能（reactflow 拖拽 / 自动布局 / 环路检测 / 序列化）留 PIPE_NET 完整版"
- **Depends on**: PIPE_NET 完整功能 sprint 启动

### TODO-041: 前端 MSW handlers 契约冻结（P5-1 后重写）
- **状态**: P5-1（OpenAPI 契约冻结后） | **来源**: 批 3 实施（MSW handlers 当前与 mock props shape 对齐）
- **What**: `pcs-frontend/src/mocks/handlers.ts` 当前按前端 mock types 写；P5-1 backend OpenAPI 冻结后必须按真实端点重写（路径 / 请求 / 响应 / 错误码 / 状态码），并删除不再使用的 mock handlers
- **Why**: P5-1 之后前端不能继续按 mock 协议工作；必须与真实后端契约对齐
- **Context**: 当前 MSW 让前端可独立运行；P5-1 后 MSW 仍有用（dev / e2e 离线），但契约必须与生产对齐
- **Depends on**: P5-1 OpenAPI 契约冻结 + 9 态 enum 扩展

### TODO-042: PIPE_LINE_LIST 25 列 DETAIL 视图补全
- **状态**: P5 SIM 扩展时 | **来源**: Task 32 PipeLineListPage 实施（2026-09-16）
- **What**: 当前 PipeLineListPage DETAIL 视图 25 列含 `compressor_kw` / `compressor_count` / `heat_duty_kw` 等计算结果字段，但 P5 之前 calculation 表未必齐全，部分列会显示空。P5 SIM/FLASH/PIPE/PUMP 计算结果入库后，需要回填这 25 列对应的 backend 字段映射
- **Why**: 用户在 P5 之前切到 DETAIL 视图会看到大量空列；需评估是否在 P5 之前默认 BASIC only
- **Context**: 批 3 提交 e427efb；BASIC 11 列 + DETAIL 25 列的双视图设计为后续计算结果预留
- **Depends on**: P5 各计算模块入库 + 列填充策略裁决
