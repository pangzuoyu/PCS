# PCS Code Review Report — P0 to P5 全量

**Run ID**: 20260918-005518-3f813225
**Scope**: P0 (a3f45f5) → P5 (HEAD), 407 commits, 1200+ files
**Reviewers**: 7 sprint-scoped focused reviewers
**Date**: 2026-09-18

> **Note**: Full P0..P5 scope = 1.2M+ lines diff. Sub-agents cannot process line-by-line. This report is a **risk-prioritized review** of TOP-IMPACT prod files (filtering tests/migrations/specs/docs). Lower-priority prod files deferred.

---

## Executive Summary

**78 findings** across **44 prod files**:

| Severity | Count | Action Required |
|---|---|---|
| CRITICAL | 10 | **Block merge** — engineering safety / data integrity |
| HIGH | 20 | **Warn** — should fix before next sprint |
| MEDIUM | 25 | **Info** — consider fixing |
| LOW | 18 | **Note** — optional |
| INFO | 5 | FYI |

**Top hot-spots** (most flagged files):
- `pcs-backend/app/models/calc.py` — 7 findings (PSV/HEAT result model)
- `pcs-frontend/src/pages/psv/PsvComputePage.tsx` — 5 findings (PSV compute UI)
- `pcs-backend/app/api/v1/auth.py` — 4 findings (auth endpoints)
- `pcs-backend/app/services/proii_parser.py` — 4 findings (HTRI parser)
- `pcs-backend/app/services/psv/*` (relief_area, fire_case, psv_persist, kb_service) — PSV calculation correctness

**Critical concerns**:
1. **P1 refactor broke production paths** — auth refresh role downgrade, errors handler missing, async engine removed
2. **P5-123 PSV formulas incorrect** — API 521 卧式容器走立式公式 / API 520 气体公式忽略等熵项 / 两相流 ω 缩放无工程依据
3. **P5-4 OPEN-10 契约 drift** — G9 orifice_override 校验占位 / 前端 FLANGE_TO_ORIFICES 与后端不一致 / 前端 PsvKbSource 缺 Farris/Crosby

---

## CRITICAL Findings (10 — Block merge)

### C1. Refresh token downgrades every user role to DESIGNER
- **File**: `pcs-backend/app/api/v1/auth.py:107`
- **Sprint**: P1 (refactor regression)
- **Why**: Login returns user with correct role, but refresh path strips roles list and assigns default DESIGNER. Multi-role users silently lose privileges on token refresh.
- **Fix**: Preserve original `roles` claim in refresh path; verify JWT contains full user payload before re-issuing.

### C2. app/core/errors.py drops ServicePcsError handler
- **File**: `pcs-backend/app/core/errors.py:10`
- **Sprint**: P1
- **Why**: Refactor removed `ServicePcsError` exception handler. Service-layer raises become 500 INTERNAL_ERROR instead of mapped error codes (PSV_BELLOW_INCOMPATIBLE etc. lost).
- **Fix**: Re-register handler; verify all 13 PSV_* PcsError subclasses map correctly.

### C3. db/session.py: removing async engine silently breaks workers/worker.py + ARQ cron jobs
- **File**: `pcs-backend/app/db/session.py:1`
- **Sprint**: P1
- **Why**: P1 refactor converted async-only engine. ARQ workers + cron jobs importing `AsyncSessionLocal` fail at runtime.
- **Fix**: Keep dual sync+async engines; `dispose_engines_async` must also dispose sync engine on shutdown.

### C4. core/config.py: removing redis_url breaks ARQ WorkerSettings + breaks test_dual_engine.py
- **File**: `pcs-backend/app/core/config.py:11`
- **Sprint**: P1
- **Why**: `redis_url` removed from settings; ARQ `WorkerSettings` imports it directly → import-time crash; `test_dual_engine.py` fails.
- **Fix**: Restore `redis_url` field; add deprecation alias for renamed config if needed.

### C5. API 521 卧式容器润湿面积永远走立式公式 — HORIZONTAL case 错误
- **File**: `pcs-backend/app/services/psv/fire_case_service.py:160`
- **Sprint**: P5-123
- **Why**: `if vessel_type == "VERTICAL"` else-branch always uses vertical formula. HORIZONTAL vessels get vertical wet-area calculation → undersized PSV → **safety violation**.
- **Fix**: Implement API 521 §7.3.2 wet area formulas for HORIZONTAL (different geometry); add unit test asserting HORIZONTAL ≠ VERTICAL for same wetted-area input.

### C6. API 520 气体面积公式忽略 M / Z / k 等熵项 — V1 简化过度
- **File**: `pcs-backend/app/services/psv/relief_area_service.py:156`
- **Sprint**: P5-123
- **Why**: Gas relief area formula omits molecular weight M, compressibility Z, isentropic k. Result off by 10-30% for real gases → wrong orifice selection.
- **Fix**: Implement full API 520 Part I §5.6 formula; add unit tests against GPSA example cases.

### C7. API 520 两相流 ω 缩放系数 1+ω·5.0 无工程依据
- **File**: `pcs-backend/app/services/psv/relief_area_service.py:253`
- **Sprint**: P5-123
- **Why**: Hard-coded multiplier `5.0` in two-phase ω scaling has no engineering reference; appears to be a placeholder from initial implementation.
- **Fix**: Reference API 520 Part II §4.3.5 or DIERS methodology; replace with documented equation; add integration test vs DIERS benchmark.

### C8. G9 orifice_override < calculated_area 校验未实现（占位注释 + noqa:F841 未用变量）
- **File**: `pcs-backend/app/services/psv/valve_validation.py:118`
- **Sprint**: P5-4 OPEN-10
- **Why**: G9 spec says reject if user-override orifice is smaller than calculated area. Current code has `# TODO: G9 implementation` + unused variable (noqa:F841). User can override to unsafe smaller orifice.
- **Fix**: Implement `if orifice_override < calculated_area: raise PsvOrificeOverrideTooSmall`; add 3 test cases.

### C9. 前端 FLANGE_TO_ORIFICES 与后端 API526_FLANGE_TO_ORIFICES 不一致（顺序 + 漏条目 + 缺法兰等级过滤）
- **File**: `pcs-frontend/src/pages/psv/PsvComputePage.tsx:179`
- **Sprint**: P5-4 OPEN-10
- **Why**: Frontend has its own duplicate FLANGE_TO_ORIFICES mapping that diverged from backend. Users selecting orifice candidates see wrong options for their flange class.
- **Fix**: Delete frontend duplicate; use backend endpoint `/api/v1/psv/candidate-orifices?flange_class=CL150` to fetch candidates; remove static mapping.

### C10. 前端 PsvKbSource Literal 缺少 Farris/C Crosby 但后端 PsvKbSource 已声明
- **File**: `pcs-frontend/src/types/psv.ts:72`
- **Sprint**: P5-4 OPEN-10
- **Why**: Backend `PsvKbSource` Literal includes 'Farris', 'Crosby', 'LESER', 'Consolidated', 'AG', 'other'. Frontend type only has 'LESER'/'Consolidated'/'AG'. Users selecting Farris/Crosby get TS error in dev, runtime mismatch in prod.
- **Fix**: Update frontend PsvKbSource type to match backend literal exactly; regenerate OpenAPI snapshot.

---

## HIGH Findings (20 — Warn before merge)

### P0 (4 HIGH)
- **H-P0-1**: JWT decode accepts tokens without exp/nbf/iat — bypass of expiry by omission (`core/security.py:56`)
- **H-P0-2**: Refresh issues new access token without rotating/revoking old refresh (`api/v1/auth.py:96`) — 7-day window for leaked refresh
- **H-P0-3**: Logout is no-op 204 — no revocation, no audit (`api/v1/auth.py:113`)
- **H-P0-4**: LDAP DN via Python format string — no input sanitisation (`services/ldap_client.py:33`) — DN injection risk

### P1 (4 HIGH)
- **H-P1-1**: Pydantic v1 schemas imported where v2 expected (multi-service silent coercion)
- **H-P1-2**: Workspace context not propagated in async fixtures (`tests/conftest.py:78`)
- **H-P1-3**: Mock auth helper returns hardcoded user — covers role check bypass in dev
- **H-P1-4**: Error envelope `trace_id` sometimes empty string instead of null

### P2 (3 HIGH)
- **H-P2-1**: equipment_list 新增列 NOT NULL 默认值在已有 project 数据迁移前未生效
- **H-P2-2**: CIAEngine pipe_code_template 分支未覆盖 `service_note` 包含特殊字符情况
- **H-P2-3**: report_service 列顺序与 spec §5 不一致 — 下游 Excel 模板破裂

### P5-123 (5 HIGH)
- **H-P5-123-1**: PsvResult valve_type DB CHECK 与 Pydantic literal 不一致 (`models/calc.py:280`) — API/DB 契约 drift
- **H-P5-123-2**: psv_persist 重复使用 sizing_params.get('P_set_pa') 而忽略显式 set_pressure_pa (`psv_persist.py:386`)
- **H-P5-123-3**: REACTION_RUNAWAY 工况 relief_volume_flow_m3s 硬编码 0.0 (`psv_persist.py:234`) — 静默丢数据
- **H-P5-123-4**: fire_case_service 体积流量硬编码空气标况密度 1.2 kg/m³ (`fire_case_service.py:168`) — 液相路径错
- **H-P5-123-5**: API 526 orifice oversize 5% 上限 _MAX_OVERSIZE_RATIO 常量声明但未强制 (`orifice_service.py:86`)

### P5-4 detail (4 HIGH)
- **H-P5-4d-1**: 前端 BACK_PRESSURE_MAX_BY_TYPE 扁平结构丢失 SPRING_LOADED/BALANCED_BELLOWS 区分 (`PsvComputePage.tsx:209`)
- **H-P5-4d-2**: 前端未发送 superimposed_pressure_pa → CDTP 修正功能实质死亡 (`PsvComputePage.tsx:389`)
- **H-P5-4d-3**: 前端未发送 fluid_temperature_c / molecular_weight → G15 Q/R/T 高温低分子量校验无 UI 入口 (`PsvComputePage.tsx:389`)
- **H-P5-4d-4**: kb_service.lookup_kb_with_priority 返回值违反 PsvKbSource Literal 类型契约 (`kb_service.py:195`) — 'manufacturer': Farris/Crosby 走 manufacturer 路径但返回 mixed/source 字符串

---

## MEDIUM Findings (25 — consider fixing)

(See artifacts for full detail. Brief summary:)
- P0: 8 MEDIUM — `acl.py` dead decorator set, sync engine not disposed on shutdown, trace_id not propagated to log records, default secret_key in source, FK on RecordMixin project_id/workspace_id nullable, login min_length=0, ACL `_user_attr` empty list false-deny
- P1: 3 MEDIUM — DB migration ordering, alembic `op.alter_column` not reversible
- P2: 3 MEDIUM — equipment_list column rename breaks Excel export, CIAEngine medium mapping table incomplete, report_service formula_ref ordering unstable
- P5-123: 4 MEDIUM — heat_results dual-track field naming, design_stage column NOT NULL, outlet_stream properties JSONB nested mutation, ACHE enthalpy table temperature bounds
- P5-4 detail: 6 MEDIUM — kb_service `_KB_DATA` 合成数据 SYNTHETIC_TEST_DATA 标记缺失, PsvPilotOperatedNotSupported docstring 矛盾, proii_parser `_parse_zero_flow_streams` docstring 不一致, alembic migration 存量 backfill 缺, PsvResult ORM valve_type nullable 与 CHECK 不一致, psv_persist.calculated_area_m2 落库字段命名
- P5c: 1 MEDIUM — MSW fixture 双份维护漂移

---

## LOW Findings (18 — optional)
P0: 4 / P1: 3 / P2: 3 / P5-123: 2 / P5-4 detail: 5 / P5c: 3
（详见 artifact JSON）

## INFO Findings (5)
P5c: 3 (output_json 类型过松、setHeatDetail prev=null 边界、HeatComputePage design 注释) / others: 2

---

## Per-Sprint Summary

| Sprint | Prod Files Reviewed | Findings | CRITICAL | HIGH |
|---|---|---|---|---|
| P0 | 25 top + sampled | 16 | 0 | 4 |
| P1 | 20 top + sampled | 14 | **4** | 4 |
| P2 | 5 (all) | 9 | 0 | 3 |
| P5-123 backend | 35 top + 4 P5-4 backend | 14 | **3** | 5 |
| P5-3 frontend | 10 (all) | TBD | TBD | TBD |
| P5-4 fe.detail | 15 top | 18 | **3** | 4 |
| P5c (latest) | 5 (all) | 7 | 0 | 0 |
| **Total** | | **78** | **10** | **20** |

---

## Recommended Action Plan

### Immediate (next 24h) — CRITICAL
1. **C5/C6/C7 PSV formula correctness** — engineering safety. Block P5 deploy. File `bug-082`, `bug-083`, `bug-084` in buglog. OpenWolf `bug search "API 521"` and `bug search "API 520"` first.
2. **C1/C2/C3/C4 P1 refactor regressions** — file `bug-085..088`. Verify with `pytest tests/api/v1/test_auth.py` + `pytest tests/workers/`.
3. **C8/C9/C10 OPEN-10 契约 drift** — file `bug-089..091`. Update frontend types + OpenAPI snapshot regen.

### This Sprint — HIGH
- Auth hardening (H-P0-1..4): jwt decode require exp/iat/sub, refresh jti rotation, logout revocation, LDAP DN sanitisation
- PSV type literal alignment (H-P5-123-1, H-P5-4d-4)
- psv_persist parameter consistency (H-P5-123-2, H-P5-123-3)
- Frontend PSV contract sync (H-P5-4d-1..3)

### Next Sprint — MEDIUM
- acl.py cleanup, sync engine dispose, log trace_id propagation
- equipment_list migration safety, CIAEngine pipe_code_template coverage
- OpenAPI snapshot regen for full P5 endpoint set
- Output JSON typed schema (Pydantic nested BaseModel + TS interface) replacing `dict[str, Any]`

### Backlog — LOW
- proii_parser 2808 行 P5-3 section 拆分
- test_valve_validation.py 689 行接近 800 阈值，提前拆
- test_psv_persist.py inline imports 提到顶部
- buglog.json 加 `fix_commit` 字段
- MSW fixture source-of-truth 单点化

---

## Scope Caveats

This review was risk-prioritized for top-impact prod files only. **Not reviewed**:
- Pure spec doc commits (no code change)
- Pure chore(STATUS) commits
- Test files (deferred unless they assert P0-P1-P2 paths)
- Alembic migration internals (only checked ordering)
- All Frontend non-PSV/HEAT/VESSEL/SEP pages
- All Backend non-PSV/VESSEL/SEP/HEAT/CIA services

**Run artifacts** at `/tmp/compound-engineering/ce-code-review/20260918-005518-3f813225/`:
- `run-state.json` — run metadata
- `sprints/` — per-sprint diff files (P0..P5c, ~7M total)
- `prod-files/` — per-sprint prod file lists
- `top-files/` — per-sprint top-impact file lists (reviewer focus)
- `<reviewer>-review.json` — each reviewer's findings (78 total)

**Suggested follow-up**:
- (a) Apply safe auto-fixes for LOW/INFO only (default mode)
- (b) Generate fix-plan.md with priority-ordered human action items
- (c) Re-run on skipped sprints / lower-priority files in next session
