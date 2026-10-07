# TODOS.md — PCS 延后工作清单

> **2026-10-06 全量核销重写。** 原文件 46 条积压自 2026-08，状态字段写的是「P1 Sprint 2」这类时间锚，
> P1–P7 全部收口后已完全失去意义，且无一条被勾销 —— 越堆越长、越不敢看。
> 本次对每条做只读实证核验，判定依据为 `文件:行号`，见每条「证据」。

## 判定图例

| 标记 | 含义 |
|---|---|
| 🔴 **OPEN** | 确实还没做 |
| 🟡 **PARTIAL** | 做了一半 |
| ⚪ **BLOCKED** | 宿主模块未开工 / 等外部方，暂不可动 |
| ✅ **DONE** | 已落地（**不要按原文重做**——多条实际路径与条目描述不同） |
| 🚫 **WONTFIX** | 已被产品/架构裁决关闭，**改回去会破坏既有契约** |
| ♻️ **STALE** | 描述已过时，任务本身失去意义，需重新裁决而非照做 |

**维护规则**：新增条目必须带 `证据` 字段；关闭条目移到文末归档表，不要删（编号是追溯索引）。
最后全量核销：2026-10-06。

---

## 🔴 P0 — 真问题（部署阻塞 / 安全）

> 现状（2026-10-07）：4 项中 3 项已做。仅 **TODO-002 token_version** 仍开放。

### ✅ TODO-004 + TODO-019: CORS middleware 已挂载（2026-10-06）

- **原症状**: `grep -rn add_middleware app/` 全仓 0 命中 —— `cors_allow_origins` 配置项在，
  中间件从未挂载。**前后端一分域部署 preflight 直接 403**，dev 靠 Vite proxy 掩盖。
  旧的 `test_cors_allow_origins_parsed` 只测配置解析，不测中间件 —— 又一个「测了但没测到东西」。
- **落地**: `create_app()` 挂 `CORSMiddleware`（`allow_credentials=False`，全栈 Bearer token
  无 cookie，开凭证还会与 `*` 冲突）；lifespan startup 调 `validate_cors_for_production()`。
- **新函数**（`app/core/config.py`）: `parse_cors_origins()` / `validate_cors_for_production()`。
  prod 下 `*` 或空串均 fail-fast —— 症状会是「所有接口 403」，极难自查，必须启动期炸。
- **验证**: 8 条新测试（含真实 preflight 往返）。全量 3932 passed / 0 failed（+8）。
- ⚠️ **未覆盖**: lifespan startup 真正触发 fail-fast 的端到端路径（需跑 lifespan →
  依赖真实 DB）。函数本身有测试，调用点是一行，读代码可确认。

### ✅ TODO-006: 认证端点限流 + 登录审计（2026-10-07，`d196daa`）

- `/auth/login` 与 `/auth/refresh` 各 10 次/分钟/IP；login 成功与失败**都**写
  `audit_logs`（`LOGIN_SUCCESS` / `LOGIN_FAILED` + ip）——失败不记等于暴力破解无痕。
- `AuditService.write` 增加可选 `ip` 参数（`audit_logs.ip` 是 INET 列，此前无法填）。
- 实施中修掉两个真 bug（均由测试暴露）：
  1. **审计写入能把登录打挂** —— INET 列只接受合法 IP，而 `request.client.host`
     在 TestClient 下是 `"testclient"`，PG 抛 DataError → 登录 500。加 `_normalize_ip()`。
     unix socket 场景同样会给出非 IP 值，非纯理论问题
  2. **两处测试污染真实开发库** —— `/login` 新增 DB 依赖后 `test_auth.py` /
     `test_mock_auth.py` 的 TestClient 打到真实 pcs 库。已补 in-memory override，
     实测 `audit_logs` 全程 0 行
- 验证：全量 3938 passed（+6）

### TODO-002: refresh token 吊销机制（token_version）

- **What**: users 表加 `token_version`；`create_token` 写入 claim；`decode_token` 校验。
- **Why**: 无状态 JWT 的 logout 只清前端内存，被盗 refresh token 7 天内无法作废。
- **证据**: `grep -rln token_version pcs-backend/ --include=*.py` 全仓 0 命中。
- **Owner**: 待认领

### ✅ TODO-007: JWT 过期 / 无效已细分（2026-10-07，`d196daa`）

- `security.py:116` docstring 早就承诺「由调用方转 PcsError」，但全仓
  `EXPIRED_TOKEN` 零命中 —— **承诺从未落地**。现拆为：
  `_decode_bearer` → `EXPIRED_TOKEN` / `INVALID_TOKEN`；
  `/auth/refresh` → `EXPIRED_REFRESH` / `INVALID_REFRESH`（对称）。
- 错误码注册表是 AST 派生的，4 个码自动收录（已实测）。
- **不重命名 `INVALID_TOKEN`**：被 `tests/test_auth.py` 与前端 meta seed 引用，
  改名收益不抵破坏面。
- ⚠️ **前端静默刷新仍未做**（TODO-001 遗留项）。`api/client.ts` 对任何 401 都直接
  跳登录。前端 meta seed 的 `ui_behavior` 因此保持 `redirect_to_login` 而非
  写成未实现的「静默刷新」——种子数据不应承诺没实现的行为。
  分码当前价值在可观测性。

---

## 🟡 开放技术债

### TODO-032: 真库测试文件迁 conftest SQLite fixture

- **What**: `get_async_session_factory()`（真 PG）→ `db_session` fixture。
- **⚠️ 范围被严重低估**: 条目只列 4 个文件，**实测 27 个**。不是 4 文件修补，是全测试目录级别的工程。
  27 个清单见归档区备注。附带修 `test_detail_templates` 每跑推高 `template_version_seq` 无清理的问题。
- **Owner**: 待认领

### TODO-035: 物流校验规则 22 条补全 —— ♻️ 描述与实现脱节，先定扩展点

- **What**: P3.2 SIM-7 只实现 3 条典型；P4 需补齐剩余（饱和蒸汽压、临界压缩因子、Cv 边界、热力学一致性…）。
- **⚠️ 条目描述与代码不符**: 条目说「新增 `ConflictResolver.check_<rule>()` 方法」——
  实测 `app/services/conflict_resolver.py` **0 个 `def check_`**，实际是 4 个私有 `_check_prx_v01/v03/v05/v06`
  + `resolve_proii_import`。**扩展点不存在，19 条规则无处挂载。动手前必须先裁决扩展点形态。**
- **Owner**: 待认领

### TODO-026: P5 模块平铺字段 / data_sheet_json 展开（9/10 未做）

- **What**: 10 张结果表里 9 张仍是 `input_json`/`output_json` 简化容器。
- **证据**: `app/models/calc.py` — VesselResult:416 / SepEquip:655 / Heat:681 / Cv:785 / Restriction:892 / Flare:400 / PipeNetwork:139。
  **现成模板**: `CoolingTowerResult` 已按 DICT-007 §SUP-012 加了 14 子结构（`calc.py:949-980`），照它做剩下 9 张。
- **Owner**: 待认领

### TODO-029: CIA 传播性能预算测试

- **What**: `test_cia_propagation_perf_budget` —— 100 下游 record / depth 8 / ≤500ms。
- **证据**: 全仓 `perf_budget` 只命中 `tests/services/test_export_service.py:53`（导出预算），CIA 那个从无。
  **对照**: 同批的 TODO-030 导出预算已落地并触发了 write_only 改造 —— 同一个 D26/D28 决议，一落地一没落地。
- **Owner**: 待认领

### TODO-034: Excel 导入模板版本管理

- **What**: 导入模板加 `template_version`；导入时校验，不兼容返 `STREAM_TEMPLATE_VERSION_MISMATCH`。
- **证据**: `STREAM_TEMPLATE_VERSION_MISMATCH` 全仓 0 命中；现有 `template_version_seq` 是 DB 侧序列，与模板文件无关。
- **Why**: P4 起字段增减后，旧模板导入会**静默**缺列/多列丢数据。
- **Owner**: 待认领

### TODO-016: ARQ 失败注入 + DLQ 测试

- **⚠️ 命名陷阱**: `tests/test_arq_failure.py` **存在**，但内容是 workspace 清理测试，
  与失败路径/DLQ 无关。`worker.py` 无 `max_tries` 配置。**失败路径覆盖为零。**
- **Owner**: 待认领

### TODO-017: P4 接入验收 e2e 从 1 扩到 4

- **现状**: 只有 `tests/test_lineage.py:423 test_p4_flash_full_path`。PUMP/PIPE/PIPE_NET 只有单元/persist 测试，
  无「计算 → DRAFT → CHECKED + @lineage 写血缘 + 状态机落审计」全路径。
- **性质**: P4 已收口，这条是**当时遗漏的验收缺口**，不是未来项。
- **Owner**: 待认领

### TODO-039 + TODO-041: 前端类型来源唯一性 + MSW 契约冻结（🔴 逾期 ~20 天）

- **What**: 7 个 mock type 文件（pipeClass/flash/pipe/pump/pipeNet/pms/common）改 import 自 `./api`；
  MSW handlers 按 OpenAPI 重写。
- **证据**: 7 文件全在，`grep -c "TODO(api-migration)"` 逐文件均为 1，`from './api'` 计数为 0；27 处页面仍从 `../types/*` 导入。
  `src/mocks/handlers.ts`（28.8K）文件头注释仍写「当前按前端 mock types 写」。
- **⚠️ STATUS.md 的说法只对了一半**: P5-1 确已闭环，但「解除了 039/041 的依赖」≠「039/041 已完成」——
  触发条件早已过去，代码原封不动。属**逾期**。
- **Owner**: 待认领

### TODO-040: PIPE_NET 完整版（reactflow / 布局 / 环路检测 / 序列化）

- **证据**: `package.json` 无 reactflow/dagre/elkjs 依赖；`PipeNetTopologyPage.tsx` 仍手写 SVG。
- **Owner**: 待认领

### TODO-044: Per-Batch QA Gate —— ⚠️ 闸门写在了错误的层级

- **现状**: `gstack-qa` 在 `~/.claude/settings.json` 已 `"on"` ✓；`.gstack/qa-reports/` 6 份报告 ✓。
- **⚠️ 问题**: 流程写在**全局** `~/.claude/CLAUDE.md`，项目根 `CLAUDE.md` grep 0 命中。
  换机器/换人/重新 clone 即失效，实际靠人肉记忆维持，且无自动化钩子。
- **修法**: 把闸门流程写进**项目根** `CLAUDE.md`（可入库、可 review），全局只留指针。
- **Owner**: 待认领

### TODO-028: 10 张计算表主键 rename（命名债，DICT 为准）

- **What**: `vessel_id→vessel_calc_id` / `heat_exchanger_id→heat_calc_id` / `cv_id→cv_calc_id` / `net_id→network_id` /
  `restriction_id→orifice_calc_id` / `ct_id→ct_calc_id` / `psychro_id→psychro_calc_id` / `sep_equip_id→sep_calc_id` /
  `filter_id→filter_calc_id` / `channel_id→channel_calc_id`。
- **证据**: `grep -rn "vessel_calc_id|heat_calc_id|orifice_calc_id|psychro_calc_id" app/models/` **仅 2 处命中** —— 基本未做。
- **Why**: ORM↔DICT 命名统一，后续审计/比对免歧义。**纯命名债，不影响功能**，但每张表都要配迁移，越晚做越贵。
- **Owner**: 待认领

### TODO-014: 设备联动「设备同步中」前端标记（🟡 PARTIAL）

- **What**: ADR-0025 已声明 CHECKED 状态变化的 ≤5 分钟一致性窗口 + 「状态 CHECKED 但设备记录 STALE」中间态，
  并要求 CI/前端展示「设备同步中」标记。**ADR 写完了，前端没跟。**
- **证据**: `docs/adr/0025-equipment-eventual-consistency-window.md:6,13,24` 已写；
  `grep -rn "设备同步|同步中|syncing" pcs-frontend/src/` **0 命中**。
- **注意**: 这个窗口现在对用户**不可见** —— 用户看到「已 CHECKED 但设备显示 STALE」时无从判断是同步中还是出问题。
- **Owner**: 待认领

### TODO-015: lineage_ctx 事务回滚清理语义文档化

- **What**: docstring + SPEC 说明 ctxmgr 内 entry 在 `session.rollback()` 时自动清理，P4 开发者无需手写清理。
- **证据**: `app/services/lineage.py` / `lineage_extension.py` grep `rollback|回滚|事务` 0 命中。
- **Owner**: 待认领

### TODO-023: 计算函数签名约定写入 CLAUDE.md

- **证据**: `docs/p4-template.md` 不存在；项目根 `CLAUDE.md` 无该章节。装饰器从 `kwargs["db"]` 取值，签名是硬契约。
- **Owner**: 待认领

---

## ⚪ BLOCKED — 宿主未开工 / 等外部方

### TODO-005: LDAP TLS
- 等 IT 提供 LDAPS 端口 + CA 证书。`app/` 全仓无 `use_start_tls`/`use_ssl`。

### TODO-010: 多态 FK 应用层校验
- **前提不成立**: 挂「P1 deliverable 模块」，但 deliverable 至今**只有 5 张表 ORM 骨架，无 service、无 API、无路由**
  （`DeliverableRecordBinding` 在 `app/api/`、`app/services/` 零命中）。没有写入方就没有校验点。
  deliverable 开工时再捡起。

### TODO-012: make_draft_record fixture 覆盖全部 record type
- **描述已过时**: 条目写「17 类」，实测 `RECORD_TYPE_REGISTRY` 现有 **21 类**（P5-0-1b 又 +1 thermosiphon）。
  且 `make_draft_record` 在 `tests/` 全仓 0 命中，conftest 只有 `make_asset`/`make_user`。
  **照原文实现会写错** —— 要做先按 21 类重写条目。

---

## ♻️ STALE — 需重新裁决，不是照做

### TODO-042: PIPE_LINE_LIST DETAIL 视图补全
- 条目说「DETAIL 25 列含 `compressor_kw`/`heat_duty_kw` 等计算结果字段，部分列显示空」。
- **实测**: `PipeLineListPage.tsx` 全文件仅 21 个 `dataIndex`；`compressor_kw` 全仓 **0 命中**。
  **25 列契约已不存在**（列被删，不是待回填）。需先裁决 DETAIL 到底要哪些列，否则「回填」无处可指。

### TODO-033: Sprint 1.9 终审 DEFER 卫生批
- 自然消解若干；仍有残留：`pipe_class_service.py:49 _STATUS_OK` 死常量、`test_category3_seeds.py:58 creates_six` 命名、
  `app/main.py:33`「6 张」注释过时。均为 LOW，纯清理。

### TODO-003: JSONB GIN 索引（🟡 PARTIAL）
- 已建 1 个（`p7_s1_002_audit_logs_jsonb_gin.py:37`）；条目列的 3 个候选列未建。
- 触发条件「首个按 JSONB 内容过滤的端点」是否已出现需确认；未出现则不急。

### TODO-020: ADR-0012 ↔ ADR-0024 交叉引用（🟡 PARTIAL，单向）
- ADR-0024 已引用 ADR-0012（`:6,:11,:31`）；**ADR-0012 未反向标注被 0024 修订**。
- SPEC/DICT 同步部分：DICT-ALL-003 已滚到 **V3.6**，条目里说的「V3.2」已过时。

### `mypy --strict`（P1.2 收尾项）
- `pyproject.toml` 无 `strict` 配置，未启用。

### TODO-008 的隐性债（✅ DONE 但有雷）
- FK 改名**不是**用 `RENAME CONSTRAINT` 达成的，而是靠 `p1_sprint3_nullable_equipment_type_codes.py:36`
  `DROP CONSTRAINT pk_equipment_type_codes CASCADE` 的副作用连带删掉旧 FK，再用新名重建。
- **⚠️ 该迁移 downgrade 时会重建旧名 `fk_equipment_list_type_code`**（`:98-104`）——
  若将来跑 downgrade→upgrade，ORM 与 DB 会漂移。值得加一条注释或补一个正式 rename 迁移。

---

## 🕐 时间债（非代码）

### PRO/II 真实工程数据脱敏入库
- `tests/fixtures/proii/` 现有 5 个 .inp + 5 个 .inp.out **已入 git，但全是从对话历史重建的合成文件**。
- 仓库根 `sample/` 有真实工程数据（`dmc.inp` / `huafeng140_FCC2015.out` / `200FlexiCoking1.out` + 多个华南海东 xlsx），**尚未脱敏入库**。
- 单元测试基线的多样性取决于样例多样性 —— 真实工艺配置才是质量保证。

---

## ✅ 已关闭归档（核销于 2026-10-06，**勿按原文重做**）

| 条目 | 实际落地路径（与条目描述不同处已标） |
|---|---|
| TODO-001 前端测试基建 | `pcs-frontend/vitest.config.ts`；现 569 tests |
| TODO-008 FK 改名 | ✅ 但绕过式，见 STALE 区雷点 |
| TODO-009 血缘递归深度 | `lineage.py:149,176 max_depth=10`（**条目写 ≤8，实际落 10**）+ 环检测 |
| TODO-011 snapshot_status + ADR-0024 | `p1_sprint2_state_machine.py:39` 加列 / `deliverable.py:259` ORM / ADR status: accepted |
| TODO-013 | `change_pending_since` DONE（`state_machine.py:327,329`）；`old_record_hash_before_change` → 🚫 WONTFIX（ADR-0024 明写不新增列，改从快照读） |
| TODO-014 ADR-0025 | 见上方开放技术债区（ADR 已写，前端标记未实现） |
| TODO-018 ARQ 独立文件 | `app/workers/workspace_tasks.py` + `worker.py:61-63` 注册 |
| TODO-021 双引擎连接池 | `app/db/session.py:33-37`（5/45/30/1800）+ `:67-71`（10/20） |
| TODO-022 data_lineage 索引 | ✅ **列已改名 `occurred_at`**，索引随之建（`models/system.py:68`） |
| TODO-024 equipment_list 对齐 DICT | 条目称「18 列缺 56」→ **实测 69 列**，早做完了 |
| TODO-025 pump_results 补 6 列 | 实测 26 列 |
| TODO-030 openpyxl write_only | `export_service.py:45` write_only=True；条件链已走完（in-memory 10k×20 实测 6.8s > 2s 预算） |
| TODO-031 preconditions 门禁 | 复核通过：`config.py:297` PUBLISH → `formula_service.py:72,76` |
| TODO-036 StreamSignStatus 9 态 | `p3_sim_stream_sign_status_extend.py` |
| TODO-037 unreliable 硬拒绝 | `calc_entry.py:53 STREAM_UNRELIABLE_BLOCKED` / `UnreliableStreamGuard` |
| TODO-038 PRO/II fixtures | **路径不是 `app/seeds/proii_samples/`**，实际在 `tests/fixtures/proii/`，5 组已 tracked |
| TODO-043 Dashboard 3 端点 | `mocks/handlers.ts:138,142,146` 三条已注册 |
| P6-OPEN-009 psv_results 缺列 | `p6_5_006_orm_db_drift_final_fix.py` 已补 |
| P5-2 PSV 多标准前置 | `p5_0_5_psv_multi_standard.py` + `models/psv_standards.py` + `services/psv/psv_persist.py` |
| P1.2 组件清单 | `LineageGraph.tsx` / `RevTimeline.tsx` / `ChangeImpactPanel.tsx` 都在（**已改名**，非原名） |

**TODO-032 的 27 个真库测试文件**（超出条目声称的 4 个）：
`tests/models/{test_pipe_class_migration, test_sup008_result_fields, test_htri_template_schema, test_calc_audit_fields, test_sup008_column_sizing_design_stage}`、
`tests/services/{test_toe_conversion_service, test_cepci_seed, pipe/test_pipe_chain, pipe/test_two_phase, cool_tower/test_heat_aggregator, cool_tower/test_cool_tower_persist_service, psychro/test_saturation_persist_integration, psychro/test_psychro_persist_service, flare/test_flare_persist_service, flare/test_relief_aggregator, open_channel/test_open_channel_persist_service, filtration/test_filtration_persist_service}`、
`tests/{test_audit_guard, test_rbac_audit, test_cia_tasks}`、
`tests/seeds/{test_detail_templates, test_category3_seeds}`、
`tests/scripts/{test_p6_3_gate_04_seed, test_p6_3_gate_05_seed, test_p6_3_gate_06_seed}`

---

## 🚫 已裁决不做

- **CI/CD 流水线**（原 SPEC-P0 §3.2.5）：单人开发裁决 2026-08-29。多人协作时重新提出。
- **TODO-027 cost_est_results 补 RecordMixin**：`CostEstResult` docstring 明写「与设备一对一，不带 sign_status（跟随所属设备）」，
  cerebrum Do-Not-Repeat 亦记录此契约（与 `TwoPhaseResult` 同）。**补 RecordMixin 会破坏它。**
- **TODO-013 的 `old_record_hash_before_change` 列**：ADR-0024 Consequences 明确「P1-MVP 不新增列，从快照表读取旧哈希」。

---

## 核销方法学备注

- 4 组并行只读核验（子代理）+ 主会话实证，覆盖 44 条编号项 + 4 条无编号项，无一条凭印象下判。
- ⚠️ **核验时慎用组合正则**：本次发现子代理首轮 `grep "A\|B"` 被 rtk 过滤层吞掉、误报「0 匹配」，
  拆成两个独立 `grep -c` 后才得真实计数。多模式核验应逐条单发。

---

## ✅ `alembic check` 假漂移已修（2026-10-06，`app/models/__init__.py` 补 `util`）

- **原症状**：`uv run alembic check` 恒报 130 条（14 remove_table / 88 remove_index /
  26 add_index / 2 add_column），全假。CLAUDE.md 指定的人工守门动作因此形同虚设。
- **根因**：`alembic/env.py:7` 只 `import app.models  # 注册全部 53 表`，
  而 `app/models/__init__.py` 列了 16 个模块却**独漏 `util`**。
  实测：修复前裸 `import app.models` → **95 表**；修复后 → **102 表**。
- **修法**：`app/models/__init__.py` 补 `from app.models.util import *`。
  该包 docstring 明写「alembic/env.py 依赖本包导入即注册全部表」——漏 `util` 违反的是它自己的契约。
- **效果**：130 → **84** 条，`remove_table` 归零（7 张 UTIL 表对 autogenerate 可见了）。
- **为什么测试此前没炸**：`tests/conftest.py:34` 的 `from app.api.v1 import api_router`
  链式带出了 util 模型。**曾误判为「测试库缺 7 张表」，实测证伪**（隔离跑
  `tests/services/util/test_gas_media_and_low_temp_heat.py` → 8 passed）。特此记录以免重犯。
- **验证**：全量 3924 passed / 0 failed（与修复前同基线）；test_schema 7 passed；
  ruff clean；幂等闸 0 violations。

## 🟡 `alembic check` 剩余 84 条**真**索引漂移（2026-10-06 假漂移修复后暴露）

- **性质**：上面那条修好后，守门终于能说真话了 —— 剩下这 84 条是**真的** ORM↔迁移索引不一致。
- **构成**：52 `remove_index`（DB 有、ORM 无）+ 30 `add_index`（ORM 有、DB 无）+ 2 `add_column`。
- **典型形态是改名对不上**，而非「缺索引」：
  - `ix_cepci_year`（DB） vs `ix_cepci_index_series_year`（ORM）
  - `ix_equipment_deletion_audit_project_equipment`（DB，复合） vs
    `ix_equipment_deletion_audit_project_id` + `..._equipment_id`（ORM，两个单列）
  - `ix_audit_logs_detail_json_gin`（DB，GIN） 在 ORM 侧无对应声明
- **危害**：低于表级漂移（不影响功能、不丢数据），但会让每次 `alembic check` 都被噪声淹没，
  守门价值再次打折。**长期风险是「改名对不上」这类会被误当成噪声忽略，而它恰恰是最容易
  让人以为索引还在的地方。**
- **修法**：逐个裁决「ORM 对 / 迁移对」，对的一侧改另一侧。改 ORM 侧零迁移成本；
  改迁移侧需新迁移（注意 `p7_s5_` 已在幂等白名单）。建议按表分批，不要一次性动 84 条。
- **Owner**：待认领（**未做**，仅登记）

## 🟡 CATEGORY_6 地基 5 项：4 项已做，1 项按裁决不做（2026-10-07 更新）

**原 5 项硬伤**（`docs/PCS-NOTE-equipment_lib-废弃-2026-10-06.md`）的现状：

| # | 项 | 状态 |
|---|---|---|
| 1 | `type_code` 根本没采集（相似度无主匹配键） | ✅ 已做 `5017ced`。settle 采集，**源设备优先**（源是权威，避免调用方与源各报一个导致型号错配） |
| 2 | settle 无去重约束 | 🚫 **按裁决不做** —— 用户 2026-10-07 选「不硬去重，交给相似度归并」。库内允许重复，相似度是唯一识别手段 |
| 3 | `weight_kg` / `key_dimensions` 埋在 JSONB 无索引 | ⏸️ **有意延后**。相似度形态是「取候选集 → Python 打分」而非 SQL 内过滤排序，当前无支撑表达式索引的查询模式；CATEGORY_6 真库 0 行。属投机性工作 |
| 4 | `category` 无枚举 + 零索引 | ✅ 已做 `1448e02`（`p7_s5_004`）。CHECK 约束拒收域外值 + `(category,status)` 复合索引 |
| 5 | 审批语义冲突（SPEC 要单层，实际 5 态链） | ⏸️ **未做**，需产品裁决 + 动审批状态机，不宜顺手改 |

**相似度本身已实现**（`3702888`，UI-SPEC §7.16）：5 维加权、缺数据跳过权重重新归一、
`ref_*` 参照参数 + 按相似度降序 + 三档（≥90% RECOMMEND / 80~90% VERIFY / <80% DISPLAY_ONLY）。

实施中修掉一个设计缺陷：`equipment_type` 原被当相似度维度，但它同时是**检索过滤条件** ——
筛 PUMP 时每条在「类型」上恒为 1.0 而其余维度缺值跳过，导致**全部条目都算出 1.0/RECOMMEND，
信号变成噪声**。已移出维度集（单元测试当时全绿，实际跑数据才暴露）。

- **附带事实**：`ConfigAsset` CATEGORY_6 在真库仍 **0 行** —— 设备库功能从未被真实使用过。
  上述能力均只在 SQLite 测试库中验证过。
- **Owner**: 待认领

## 🔜 UI-SPEC §7.16 与实现的完整差额 —— **已裁决延后到下一版本**（2026-10-07）

> 用户裁决：本版本不做，作为未来功能增强。**不是遗忘，是裁决。**
> 完整决策记录 + 下一版本启动前的两个前提见
> `docs/PCS-NOTE-UI-SPEC-7.16-设备库检索延后-2026-10-07.md`。

**更正**：上文「地基 5 项全部完成」是错的。那 5 项是首轮审计识别出的**后端缺口**，
不是与 SPEC 的完整差额。逐条核对 SPEC §7.16 后，13 项要求只满足 2 项：

| SPEC §7.16 要求 | 状态 |
|---|---|
| **检索 · 工艺条件模糊搜索** | ❌ 只有 `keyword` → 设备名 ILIKE，**不是工艺条件**（压力/温度/介质） |
| **检索 · 参数区间** | ❌ 完全没有 min/max 过滤 |
| **检索 · 相似度计算** | ✅ 已做 |
| **结果列 · 设备类型 / 规格 / 材质 / 重量 / 标准图号** | ❌ `AssetResponse` 只有 asset_id/category/name/status/current_version，**SPEC 要的 8 列里 5 列没暴露** |
| **结果列 · 相似度** | ✅ 已做 |
| **结果列 · 原项目 / 投用日期** | ❌ 没有 |
| **limit ≤ 200** | ✅ |
| **分页** | ❌ 只有 limit，无 offset / total |
| **前端页面** | ❌ **完全没有**（`pcs-frontend/src` 下除生成的 `api.d.ts` 外零引用） |

### 两个额外发现

1. **「参数区间」当前无法实现，不只是没写**。`ApplicableConditions` 把工艺条件存成
   **自由文本区间串**（`pressure_mpa="0.1~2.5 MPa"`、`temperature_c="-20~200 °C"`），
   要做区间查询必须先解析文本。这是数据模型问题，不是加个索引的事。
2. **CATEGORY_6 第 3 项（JSONB 索引）当初的延后理由是错的**。我当时的理由是
   「没有支撑表达式索引的查询模式」—— 但 SPEC §7.16 **明确要求参数区间**，
   那就是查询模式。SPEC 是需求，不是等数据来了才成立。延后理由应改为
   「需先解决 applicable_conditions 自由文本的数据模型问题」。

- **Owner**：待认领（规模明显大于上面那 5 项，建议单独立项而非并入 CATEGORY_6）

---

## 🔴 9 个既有 `p7_open_*`/`p7_s1_*` 迁移缺幂等 guard（2026-10-07 恢复登记）

> ⚠️ **本条曾在 2026-10-06 的 `TODOS.md` 全量重写中丢失**（只剩 `STATUS.md` 提过），
> 2026-10-07 补回。重写整份文件时用 `Write` 覆盖，漏抄了尾部两个无编号条目。

- **现状**：`scripts/check_migration_idempotency.py` 的 `checked_prefixes` 覆盖
  `p7_s2_`/`p7_s3_`/`p7_s4_`/`p7_s5_`（0 violations ✅）。
  但全部 23 个 `p7_*.py` 里有 **9 个落在白名单外**，其 `drop_table`/`create_index`/
  `drop_index` 没有幂等 guard，闸看不见：
  - `p7_open_009_001_utility_power_items`（5 处）
  - `p7_open_009_002_utility_fuel_gas`（7 处）
  - `p7_open_009_003_utility_heat_exchange`（7 处）
  - `p7_open_009_005_utility_energy_summary`（6 处）
  - `p7_open_009_t0_config_energy_conversion_factors`（1 处 `drop_table`）
  - `p7_open_010_r1_classification_fields`（6 处）
  - `p7_open_010_user_projects_blocker3`（7 处）
  - `p7_s1_002_audit_logs_jsonb_gin`（2 处）
  - `p7_s1_005_util_results`（6 处）
- **风险**：downgrade 往返在这些迁移上不幂等。
- **不能无审查批量加 guard** —— 加 `if_exists=True` 会改变 downgrade 在
  「表不存在」时的行为，需逐个确认语义。
- **修法顺序（不能反）**：逐个补 `if_exists=True` / `if_not_exists=True` →
  补完一个从前缀白名单移一个 → 最后白名单改「全部 `p7_*`」。
  **顺序反了会让钩子立刻在无关文件上失败**（P7 Sprint 4 #12 报告里担心的情形，
  实测确认成立）。
- **Owner**：待认领

## ✅ `.wolf/buglog.json` id 重号已去重（2026-10-07）

> 同上，本条也在 2026-10-06 重写中丢失，2026-10-07 补回并当场修复。

- **登记时的描述已过时**：当时记的是「四条 `bug-2026` + `bug-031`/`bug-002` 各重复，
  共 6 条重号」。实际 `bug-2026` 那四条早已被改成 `QA-2026-09-16-001..004`，
  **只剩 2 对重复**：`bug-002`（2 条）、`bug-031`（2 条）。
- **为何可以改号**：原方案说「不改历史条目的 id，因为 `fix_commit` 是 STATUS 反查的
  单点来源」。实测这 4 条的 `fix_commit` **全是空**，没有反查链可断 ——
  前提不成立，所以可以安全改号。
- **处置**：按「早的保留原号（稳定）」，晚的补空洞号，并双向 `related_bugs` 互链 +
  `id_reassigned_from` / `id_reassigned_reason` 留痕：

  | 保留 | 改号 | 改号原因 |
  |---|---|---|
  | `bug-002`（Incorrect value in code, 08-31） | `bug-039` | alembic `tag_number ... already exists`（09-16） |
  | `bug-031`（Wrong operator, 09-01 08:18） | `bug-072` | alembic `NameError: name Enum is not defined`（09-01 13:01） |

  复核：140 条，重复 0 个。
- **编号规则（防止复发）**：新条目用**顺序号 `bug-NNN`，下一个 = 当前 max+1**。
  **绝不使用年份式编号**（`bug-2026` 正是当初 4 条撞号的根因 —— 新条目按
  `max+1` 算出 `bug-2027` 时，`bug-2026` 这个非序号已经存在，于是继承了重号）。
- **Owner**: 已关闭
