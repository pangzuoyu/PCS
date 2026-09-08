# PCS P3.2 SIM 全量审计报告 V1.0

| 项 | 值 |
|---|---|
| 审计日期 | 2026-09-09 |
| 审计对象 | P3.2 SIM Sprint（13 task 全部 completed） |
| 对照基准 | `docs/PCS-PLAN-P3.2-SIM.md` V1.0 + Spec §3.2 + §3.4 + §5.5 + 用户中途裁决 |
| 触发 | SIM-12 收口后用户主动要求 |
| 结论 | **核心数据流 100% 覆盖；治理层（状态机/性能/架构一致性）偏离 4 项需裁决** |

---

## 1. 严重偏离（4 项，需用户裁决）

### 🚨 D-1：状态机集成完全缺失（Plan §SIM-4 + Spec §3.4）

| 项 | Plan | Actual |
|---|---|---|
| 状态机集成 | `StreamService.transition()` + `SELECT FOR UPDATE` + 复用 P1 `StreamSignStateMachine` | **StreamService 无 transition 方法** |
| API 端点 | POST /streams/{id}/submit, /approve, /reject 等 | **完全无对应端点** |
| P1 复用 | 集成 `app.services.state_machine.StreamSignStateMachine` | Stream `sign_status` 仅为字段，无状态机流转 |
| D9 并发安全 | `SELECT ... FOR UPDATE` 防并发覆盖 | **未实现**（仅 numbering_service 有 FOR UPDATE） |

**影响**：物流无法走 DRAFT → IN_APPROVAL → CHECKED 生命周期，前端无法做"提交审核"按钮。整个 P3 Sprint 的核心价值（9 态流转）未落地。

**Spec §3.4 引用**：spec 明文要求 `stream_sign_status` 4 态（P3 活跃）+ 状态机方法。

**P1 已就绪未对接**：`app/services/state_machine.py` 已实现 `RecordSignStatus9` 9 态枚举 + 13 事件 transition 表 + `transition()` 异步方法，但 Stream 服务层完全没调用。

**证据**：
```bash
$ grep -nE "transition|submit|check_reject|approve" app/services/stream_service.py
# 无匹配
$ grep -nE "StreamSignStateMachine" app/services/stream_service.py
# 无匹配
```

---

### 🚨 D-2：D9 critical gap #1 文件大小限制未实现

| 项 | Plan | Actual |
|---|---|---|
| 文件大小限制 | middleware 校验，10MB 上限，返 413 | **无 size 校验** |
| 错误码 | `STREAM_IMPORT_FILE_TOO_LARGE` | 未实现 |

**Plan §D9 原文**：「上传 .inp 文件大小限制 10 MB（spec §性能 ≤ 30s/1000 条推算 50 流约 500KB，10MB 是 20x 安全余量）」

**影响**：恶意上传 1GB 文件可耗尽磁盘 / 内存 / parser hang。Plan 明确列为 critical gap，未闭环。

**证据**：
```bash
$ grep -nE "max.*size|10.*MB|413|FILE_TOO_LARGE" app/api/v1/imports.py app/main.py
# 无匹配
```

---

### 🚨 D-3：D7 N+1 防护未实现

| 项 | Plan | Actual |
|---|---|---|
| selectinload | `StreamService.list` 用 `selectinload(Stream.state_points)` | **无 selectinload** |
| 性能测试 | 验证 list 触发 query ≤ 2 | 未做 |

**影响**：列表页查询会触发 N+1（每个 stream 一次 state_points 查询）。当前测试数据量小不可见，生产规模（>100 stream）会慢。

**证据**：
```bash
$ grep -n "selectinload" app/services/stream_service.py
# 无匹配
```

---

### 🚨 D-4：D2 stateful preview 表未建（与 P2 PC5 模式不一致）

| 项 | Plan | Actual |
|---|---|---|
| 预览持久化 | `stream_import_previews` 表 + preview_id commit（复用 P2 `pipe_class_import_previews` 模式） | **stateless round-trip JSON** |
| 幂等键 | (project_id, import_session_id, tag_number, case_type) | 仅 (project_id, stream_name) |

**Plan §D2 原文**：「user 2026-09-08 显式裁决」要求 stateful。

**注**：用户在 SIM-11 阶段说过"问题 4 preview/commit 二次冲突 ✅ 可接受"，但这是**结果接受**，不是**架构裁决**——plan 仍要求 stateful 设计。

**证据**：
```bash
$ grep -rn "stream_import_previews\|preview_id\|import_session" app/ alembic/
# 无匹配（pipe_class_import_previews 存在，stream_import_previews 不存在）
```

---

## 2. 中度偏离（实施偏差，非缺陷）

### M-1：路径结构偏离（cosmetic，更合理）

| Plan 路径 | Actual 路径 | 评价 |
|---|---|---|
| `app/services/parsers/proii_parser.py` | `app/services/proii_parser.py` | 无子目录，更简洁 ✓ |
| `app/services/parsers/excel_parser.py` | `app/services/excel_parser.py` | 同上 ✓ |
| `app/services/importers/proii_importer.py` + `excel_importer.py` | 合并为 `app/services/import_service.py` | 合并合理（少 1 文件） ✓ |
| `app/seeds/proii_samples/` | `tests/fixtures/proii/` | **更合理**：fixtures 是测试专属 |
| `app/seeds/excel_templates/stream_import_template.xlsx` | `tests/fixtures/excel/streams_sample.xlsx` | 同上 ✓ |

### M-2：API 端点路径偏离

| Plan | Actual |
|---|---|
| `/projects/{pid}/streams/import/proii/preview` | `/projects/{pid}/imports/proii/preview` |

实际更合理（imports 是独立子路由）。✓

### M-3：错误码偏离

| Plan | Actual | 评价 |
|---|---|---|
| Excel 缺 tag_number → `STREAM_MISSING_TAG_NUMBER` | `SIM_IMPORT_PARSE_ERROR` | 当前错误码覆盖，未细分子类（可接受） |
| 文件超大 → `STREAM_IMPORT_FILE_TOO_LARGE` | 未实现 | 关联 D-2 |

### M-4：sign_status 列类型偏离

| Plan | Actual | 评价 |
|---|---|---|
| `varchar(20)` → `varchar(32)` | PG native enum `streamsignstatus` | **实际更优**（强类型安全） |

Plan 没跟上 P1 已落地的 enum 决策。实施期间自然演进，更合理。

### M-5：SIM-V02 阈值不一致

| Plan | Actual |
|---|---|
| "WARN（用户值优先但偏差 >5%）" | `_MOLAR_MASS_TOL = 0.01` (1%) |

实际阈值更严格（1% vs plan 5%），是 spec §工艺实践参考。✓ 更合理但与 plan 字面冲突。

---

## 3. Spec 强约束项覆盖核查

| Spec § | 要求 | 落地 | 备注 |
|---|---|---|---|
| §3.2 双层 case_type | StreamCaseType + StatePointCaseType 独立 | ✅ | DB CHECK 双约束 |
| §3.2.3 表 2 物性 17+ 字段 | 全列 | ✅ | sim-1 落地 |
| §3.3.1 ≤ 5s/100 条物性补全 | asyncio.gather 并行 | ✅ | test_complete_batch_100_streams_under_5_seconds |
| §3.4 状态机 4 态（DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED）| P3 活跃 4 态 | ⚠️ | **Stream 服务层未集成**（P1 状态机已实现但未对接 SIM） |
| §5.3 Pydantic Field(description=...) 每字段 | 全 schema | ✅ | 检查 stream.py 全部字段 |
| §5.3 错误码分级（BLOCK/WARN/INFO） | SIM-V/SIM-E/PR-V/PRX-V/SIM-SV 前缀 | ✅ | conflict_resolver.py |
| §5.5 PRO/II + Excel 导入 | 4 端点（preview/commit × 2 格式） | ✅ | imports.py |
| §6 增量幂等 | 同 stream_name 重复 signup 跳过 | ✅ | UniqueConstraint |
| §7 ACL | DESIGNER + PC + SA | ✅ | 11 端点全部 require_roles |

---

## 4. Plan self-review 锁定项核查

| # | 议题 | 裁决 | 当前状态 |
|---|---|---|---|
| 5 样例构造 | V1.0.1 采纳 | ✅ 已落地 5 双文件 fixture |
| Parser 三版支持 | V2.71+V4.17+V8.x | ✅ proii_parser.py |
| 字段顺序不构成契约 | 用户裁决 | ✅ 无 sort 依赖 |
| 状态机并发 SELECT FOR UPDATE | Plan 锁定 | ❌ **未实现**（D-1） |
| 10MB 文件大小限制 | Plan 锁定 critical gap | ❌ **未实现**（D-2） |
| 幂等键 (project_id, stream_name) | Plan 锁定 | ✅ 等效（无 import_session_id 维度，但 SKIP 行为正确） |
| stream_import_previews 表 | Plan 锁定 | ❌ **未实现**（D-4） |
| 不可靠单元产品下游拒绝 | TODO-037 P4 再议 | 标记但未实现 |
| 22 条校验规则全覆盖 | Plan 仅做 3 类骨架 | ✅ TODO-035 后置 |
| Excel 模板版本管理 | TODO-034 P4 再议 | V1 模板已用 |

---

## 5. 漏项清单（未在原 TODO-039/040/041/042 中）

| # | 项 | 来源 | 优先级 |
|---|---|---|---|
| 1 | **StreamService 状态机 transition 方法** + 6 个 API 端点（submit/approve/reject/initiate_change/pass_change/mark_stale）| Spec §3.4 + Plan §SIM-4 | **P0 — Sprint 内必补** |
| 2 | **文件大小 middleware**（10MB → 413 STREAM_IMPORT_FILE_TOO_LARGE） | Plan §D9 critical gap | P1 |
| 3 | **selectinload(state_points) 防 N+1** | Plan §D7 | P1 |
| 4 | **stream_import_previews 表**（stateful preview，与 P2 PC5 一致）| Plan §D2 | P2（YAGNI） |
| 5 | **状态机审计日志**（每次 transition 写入 audit）| Plan §SIM-4 隐含 | P2 |

---

## 6. 整体偏离评分

| 维度 | 状态 | 备注 |
|---|---|---|
| 物流数据模型 | ✅ 100% | schema/ORM/Schema 三套全对齐 |
| 三入口导入 | ✅ 100% | PRO/II + Excel + 手工 |
| 物性补全链路 | ✅ 100% | COMMON 集成 + 性能预算 |
| 冲突检测三级 | ✅ 100% | 4 大维度 |
| 状态机生命周期 | ❌ **0%** | P1 已实现但未对接 SIM |
| 性能（N+1 / 文件大小） | ❌ 30% | 仅物性补全 perf 通过 |
| 架构一致性（stateful preview） | ❌ 0% | 与 P2 PC5 不一致 |

**整体偏离**：**核心数据流 100% 覆盖，治理层（状态机 + 性能 + 架构一致性）偏离较大**。

---

## 7. 用户裁决请求

| 优先级 | 项 | 估时 | 决策点 |
|---|---|---|---|
| **P0** | StreamService 状态机 transition + 6 API + SELECT FOR UPDATE | 1d | 是否补 SIM-13（1d）闭环？ |
| **P1** | selectinload(state_points) 防 N+1 | 0.25d | 是否补 SIM-14（0.25d）？ |
| **P1** | 文件大小 middleware 10MB | 0.25d | 是否补 SIM-15（0.25d）？ |
| **P2** | stream_import_previews 表 | 1d | 接受偏离？或补 SIM-16（1d）？ |
| **P2** | 状态机审计日志 | 0.5d | 是否一并补？ |

---

## 8. 已锁定的原 TODO（不变）

| TODO | 内容 | 来源 |
|---|---|---|
| TODO-034 | Excel 模板版本管理 | Plan §self-review |
| TODO-035 | 22 条校验规则 19 条未做 | Plan §self-review |
| TODO-037 | 不可靠单元产品下游计算拒绝 | Plan §self-review |
| TODO-039 | PRO/II composition 抽取 + libid→CAS | 用户裁决 YAGNI P4 |
| TODO-040 | Alembic migration round-trip 单测 | SIM-12 报告 |
| TODO-041 | export_service 性能预算测试偶发超时 | SIM-12 报告 |
| TODO-042 | SIM-10 commit 阶段 BLOCK 流可优化为事务回滚 | SIM-12 报告 |

---

## 9. 审计方法

### 9.1 数据来源
- 17 个 P3.2 SIM 提交（`git log 4dc6316..HEAD`）
- 49 个新增测试（13 SIM-10 service + 12 SIM-10 API + 16 SIM-10.2 service + 12 E2E）
- 全量回归 675 passing（591 基线 + 84 累计）
- 覆盖率 88%（≥ 80% 目标）

### 9.2 审计工具
- `git log` 提交链对照 plan 任务列表
- `grep -nE "selectinload|FOR UPDATE|transition|preview_id"` 验证 P0 偏离
- `pytest --cov=app --cov-report=term` 覆盖率
- `uv run ruff check` lint 验证

### 9.3 审计范围
- ✅ 代码层：app/models + app/services + app/api + app/schemas
- ✅ Schema 层：4 个 alembic migrations
- ✅ 测试层：49 个 SIM 相关测试 + 12 E2E
- ✅ 文档层：plan / spec / close report / audit report
- ⚠️ 未审计：性能压测（spec ≤30s/1000 条需独立 perf harness）

---

_V1.0 审计完成 · 2026-09-09 · 待用户裁决 D-1~D-4 优先级_
