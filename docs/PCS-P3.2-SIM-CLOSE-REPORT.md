# PCS P3.2 SIM Sprint 收口报告 V1.1

| 项 | 值 |
|---|---|
| 收口日期 | 2026-09-09（V1.1 更新 SIM-13 闭环） |
| Sprint | P3.2 SIM（Process Simulation 流程模拟） |
| Plan 文件 | `docs/PCS-PLAN-P3.2-SIM.md` |
| Spec 版本 | V1.6 §3.2 + §3.4 + §5.5 |
| 总耗时 | 14 task × ~10d（含 SIM-13 合并任务 1.5d） |
| 主负责人 | Claude (MiniMax-M3) + 用户裁决 |

> **V1.1 修订**：新增 SIM-13 task（用户 2026-09-09 裁决 P0/P1 必补项合并为一个 task）。
> 闭环审计 D-1 状态机集成 / D-2 文件大小 middleware / D-3 selectinload。
> D-4 stateful preview 表 记录为 TODO-043 后置 P2；状态机审计日志 记录为 TODO-044。
> 状态机部分状态从「⚠️ 未集成（P1 已就绪）」改为「✅ SIM-13 闭环」。

---

## 1. 任务交付清单（14/14）

| ID | 任务 | 状态 | 关键产出 | commit |
|---|---|---|---|---|
| SIM-1 | streams schema 升级 + ORM + Schema 三套 | ✅ | 4 列新增 / 9 ORM 字段 / 15 schema 字段 | `81baee6` |
| SIM-2 | PRO/II .inp 双文件解析器 | ✅ | `parse_proii_files` / 5 fixture 样例 / V2.71+V4.17+V8.x 三版支持 | `c3fc46d`+`7b8d96a` |
| SIM-3 | 物性补全服务 | ✅ | `complete_properties` + `MISSING_CAS/NOT_FOUND/ERROR` 转译 | `f1d38bb` |
| SIM-4 | 物流 CRUD service | ✅ | `StreamService.create/update/delete` + SIM-3+SIM-7 集成 | `77e7bcf` |
| SIM-5 | Excel 解析器 | ✅ | 双 Sheet 解析 + CAS alias + 单位规整 | `96c7145` |
| SIM-6 | 手工表单 API | ✅ | 5 端点 + 15 集成测试 | `e425ba9` |
| SIM-7 | 三级冲突检测服务 | ✅ | 4 大维度（SIM-V/SIM-E/PR-V/PRX-V）+ Conflict dataclass | `0a92191` |
| SIM-8 | 状态点 CRUD | ✅ | 5 端点 + 26 测试 + 合并到 StreamService | `93cdc67`+`4ca9f0e` |
| SIM-9 | 状态点冲突检测 | ✅ | SIM-SV01~SV05 5 规则 + SV03 双层阈值 | `45e6562`+`f32063d` |
| SIM-10 | PRO/II + Excel 导入预览 + commit | ✅ | ImportService + 4 API + 13 service + 12 API 测试 | `adbf35d` |
| **SIM-10.1** | **streams.is_unreliable 列（用户裁决补丁）** | ✅ | **收敛分层透传到 DB** | `6348474` |
| **SIM-10.2** | **streams.is_mixed_phase 列（用户裁决补丁）** | ✅ | **MIXED 相事实持久化** | `59fae21` |
| SIM-11 | 三入口 E2E 集成测试 | ✅ | 12 E2E + 收敛/路径/聚合/migration 幂等 | `d2ff039` |
| **SIM-13** | **状态机集成 + N+1 防护 + 文件大小 middleware**（用户裁决 P0/P1 合并） | ✅ | **StreamService.transition + 6 API + selectinload + 10MB middleware + 2 migrations** | `dad61a7` |
| **SIM-12** | **Sprint 收口报告** | ✅ | **本文件（V1.1）** | — |

### 1.1 收口口径
- 14 个主任务全部完成（含 2 个用户中途裁决的补丁 SIM-10.1/10.2 + 1 个用户裁决的合并 task SIM-13）
- 关闭 1 个长期待办（bug-062：state_label 重复）
- 闭环审计 4 项严重偏离（D-1/D-2/D-3 落地 SIM-13；D-4 记录 TODO-043 后置）
- 新增 4 列状态机字段（change_pending_since / change_resolved_at / change_resolved_by）+ PG enum streamsignstatus 4→9 态

---

## 2. 关键指标

### 2.1 代码增量（vs commit `4dc6316` P3 Sprint 基线）

| 维度 | 数量 |
|---|---|
| 源文件（app/alembic）新增/修改 | 15 files, +3,331 lines |
| 测试文件（含 fixtures）新增/修改 | 27 files, +4,887 lines |
| Alembic migrations | 4 |
| 提交数 | 17（P3.2 SIM 范围） |
| Fixture 样例 | PRO/II 5 套（.inp+.out）+ Excel 1 套（13 文件） |

### 2.2 测试覆盖

| 指标 | 值 | 目标 | 状态 |
|---|---|---|---|
| 全量回归 | **702 passing** | 不退化 | ✅（591 → 675 → 702，+111） |
| 覆盖率 | **88%**（app/ 总） | ≥ 80% | ✅ |
| SIM-10/10.1/10.2/11/13 新增测试 | 76 tests | — | ✅（+27 SIM-13） |
| E2E 测试 | 12 SIM-11 | — | ✅ |
| Ruff lint（SIM 文件） | 0 errors | 0 | ✅ |

**SIM 模块覆盖明细**：

| 模块 | 覆盖率 |
|---|---|
| `proii_parser.py` | 92% |
| `excel_parser.py` | 87% |
| `property_completion.py` | 98% |
| `conflict_resolver.py` | 98% |
| `stream_service.py` | 94% |
| `import_service.py` | 89% |
| `schemas/stream.py` | 100% |
| `models/project.py`（含 is_unreliable/is_mixed_phase） | 100% |
| `api/v1/imports.py` | （含于 api_router 聚合） |
| `api/v1/streams.py` | （含于 api_router 聚合） |

### 2.3 Alembic 迁移链

```
p3_sim_stream_schema_upgrade           (SIM-1)
  ↓
p3sim_state_points_unique_label        (SIM-10 闭环 bug-062)
  ↓
p3sim_stream_is_unreliable             (SIM-10.1 用户裁决)
  ↓
p3sim_stream_is_mixed_phase            (SIM-10.2 用户裁决)
  ↓
p3sim_stream_state_machine_fields      (SIM-13：3 状态机字段)
  ↓
p3sim_stream_sign_status_extend        (SIM-13：PG enum 4→9 态；不可逆)
```

6 个 migration 顺序幂等，pcs/pcs_test 双库已对齐。**注**：p3sim_stream_sign_status_extend 的 ADD VALUE 不可逆（PG enum 限制），降级需手动 ALTER TABLE TYPE varchar。

---

## 3. 用户裁决记录（核心）

### 3.1 Plan 阶段裁决（2026-09-08）

| # | 议题 | 裁决 | 影响 |
|---|---|---|---|
| 1 | SIM-1/SIM-3 并行 | ✅ | 节省 1d |
| 2 | 5 样例构造方案 | ✅ 采纳 V1.0.1 | fixtures 入 git，仓库 sample/ -m regression 不入 |
| 3 | StreamResponse 字段顺序 | 不构成契约 | 灵活 |
| 4 | SIM-7 三级冲突 + 4 大维度 | ✅ | 模块化 |
| 5 | SIM-9 状态点 5 规则 SV01~SV05 | ✅ | 完整 |
| 6 | SIM-4 集成 SIM-3+SIM-7 BLOCK 拒绝 / WARN 保存+返回 / INFO 保存+返回 | ✅ | 严格分级 |

### 3.2 补丁阶段裁决（2026-09-09）

| # | 议题 | 裁决 | 落地 |
|---|---|---|---|
| 7 | PRO/II composition 抽取 + libid→CAS | YAGNI 后置 P4 | composition_json=None，TODO-039 |
| 8 | is_unreliable 列 | ✅ 加 | SIM-10.1 |
| 9 | preview/commit 二次冲突 | ✅ 可接受 | 当前行为是正确快照校验 |
| 10 | MIXED 相 SIM-V01 BLOCK | 绕过 + is_mixed_phase 持久化 | SIM-10.2 |

---

## 4. 未解决问题清单（TODO 表）

| TODO | 内容 | 优先级 | 后续 sprint | 影响范围 |
|---|---|---|---|---|
| **TODO-039** | PRO/II composition 抽取（组分组成 + libid→CAS 映射） | P4 | P4 计算模块 | 下游 CAS-based 计算模块需 composition |
| **TODO-040** | Alembic migration round-trip 单测（downgrade→upgrade） | 低 | P4.x | CI 兜底迁移可逆性 |
| **TODO-041** | export_service 性能预算测试偶发超时 | 低 | — | 非 SIM 范围，非 P3.2 阻塞项 |
| **TODO-042** | SIM-10 commit_proii 阶段对 BLOCK 流的处理可优化为事务回滚（非逐条 try/except） | 低 | P3.x 重构 | 当前行为正确，仅性能 |
| **TODO-043** | 导入预览 stateful 落表（用户审计 D-4 后置 P2） | P2 | P3.x | 当前预览为 stateless（preview_id 在响应中丢弃）；如需审计 / 重放 / 大文件分段，需落 stream_import_previews 表 |
| **TODO-044** | 状态机审计日志结构化（用户裁决后置） | 中 | P3.x | 当前 AuditService 写入 resource_type="streams" + resource_id=str(stream_id)；如需 transfer 原因 / snapshot 链 / 角色变更审计，需扩展 schema |

---

## 5. 交付物清单

### 5.1 代码

```
app/api/v1/imports.py            4 端点（PRO/II preview/commit + Excel preview/commit）
app/api/v1/streams.py            5 端点（手工 CRUD，含 state point 嵌套）
app/services/import_service.py   preview/commit 调度 + convergence 分层 + is_unreliable 透传
app/services/proii_parser.py     V2.71/V4.17/V8.x 三版支持 + 收敛状态提取
app/services/excel_parser.py     双 Sheet 解析 + CAS alias + 单位规整
app/services/conflict_resolver.py  4 大维度（SIM-V/SIM-E/PR-V/PRX-V）
app/services/property_completion.py  MISSING_CAS/NOT_FOUND/ERROR → INFO/WARN/WARN
app/services/stream_service.py   CRUD 集成 SIM-3+SIM-7
app/models/project.py            Stream + StreamStatePoint + 3 列升级（is_unreliable, is_mixed_phase）
app/schemas/stream.py            StreamBase + StreamCreate + StreamUpdate + StreamStatePoint*
alembic/versions/p3_sim_*.py     4 migrations
```

### 5.2 测试

```
tests/services/test_proii_parser.py        15 测试（5 样例覆盖）
tests/services/test_excel_parser.py         8 测试
tests/services/test_property_completion.py  6 测试
tests/services/test_conflict_resolver.py    9 测试
tests/services/test_stream_service.py       8 测试
tests/services/test_state_point_crud.py     9 测试
tests/services/test_state_point_conflict.py 12 测试（SV01~SV05）
tests/services/test_import_service.py      16 测试（含 SIM-10/10.1/10.2）
tests/api/v1/test_streams_api.py           26 测试
tests/api/v1/test_state_points_api.py       6 测试
tests/api/v1/test_imports_api.py           12 测试
tests/e2e/test_sim_three_entry_consistency.py  12 测试
tests/fixtures/proii/                       5 套 .inp+.out 双文件
tests/fixtures/excel/streams_sample.xlsx    1 套 Excel
```

---

## 6. 风险与已知限制

1. **composition_json=None 持久化**：PRO/II 入口落库的流 composition 字段为空字符串键 NULL。P4 计算模块需识别「composition is None → 视为不可参与组分相关计算」。

2. **MIXED 相绕过 SIM-V01**：当前 phase=None 触发不到 BLOCK，但 is_mixed_phase=True 标记保留了数据事实。P4 composition 抽取时可精准回填。

3. **状态机部分状态（✅ SIM-13 闭环）**：Stream 状态机 9 态闭环（DRAFT → IN_APPROVAL → CHECKED → CHECK_REJECTED / CHANGE_PENDING → CHANGED / STALE 等），6 个 API 端点（submit/approve/reject/initiate-change/pass-change/mark-stale）已上线；SELECT FOR UPDATE 防并发覆盖；TRANSITION_ROLES 角色校验落地。剩余 TODO-043（stateful preview 落表）和 TODO-044（结构化审计日志）为可选 P3.x 增强。

4. **export_service 性能预算测试**：在并行负载下偶发超时（非 SIM 相关）。需独立排查（TODO-041）。

5. **降级路径**：alembic chain 6 个 migration 未做 downgrade→upgrade 循环单测（TODO-040）。p3sim_stream_sign_status_extend 的 ADD VALUE 不可逆（PG enum 限制），降级需手动 ALTER TABLE TYPE varchar。生产环境升级前需人工 verify。

---

## 7. 收口 Checklist

- [x] 14 个主任务全部 completed（含 SIM-13 用户裁决合并任务）
- [x] 全量回归 702 passing（591 → 675 → 702, +111）
- [x] 覆盖率 88%（≥ 80% 目标）
- [x] Ruff lint 0 errors on SIM files
- [x] Alembic migration 顺序幂等（pcs + pcs_test），6 个迁移
- [x] bug-062 已闭环（SV05 UniqueConstraint + service IntegrityError 转译）
- [x] 用户裁决的 2 个补丁（SIM-10.1/10.2）已落地
- [x] E2E 三入口一致性已覆盖
- [x] 闭环审计 D-1/D-2/D-3 已落地 SIM-13；D-4 记录 TODO-043
- [x] 状态机 6 端点 + SELECT FOR UPDATE + selectinload N+1 防护 + 10MB 上传限制 middleware 已落地
- [x] 未解决问题已记录为 TODO-039/040/041/042/043/044

**P3.2 SIM Sprint 收口通过 ✅**

---

## 8. 下一步建议

| Sprint | 任务 | 依赖 |
|---|---|---|
| P3.3+ | 设备/换热器/反应器侧 SIM 集成 | 复用 SIM-3+SIM-4 链路 |
| P4.x | composition 抽取 + libid→CAS（TODO-039） | SIM-10.2 is_mixed_phase 标记 |
| P4.x | 设备侧 PFD/P&ID 联动 | 复用 SIM-10 import service |

---

_V1.0 收口 · 2026-09-09 · main_
