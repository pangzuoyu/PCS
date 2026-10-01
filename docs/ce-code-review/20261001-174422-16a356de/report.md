# P7 Sprint 2 — ce-code-review Report

- **Run**: `20261001-174422-16a356de`
- **Date**: 2026-10-01
- **Batch**: P7 Sprint 2 (commit `85d1215`..`8f5f65e`, 32 files, 22,998 lines)
- **Depth**: full (hard_block_full triggered by `migrations` class)
- **Mode**: report-only (no `apply:local`)
- **Verdict**: **Not ready** — fix all 4 P0 + 4 critical P1 before merge

---

## Coverage

| Reviewer | Tier | Reason |
|---|---|---|
| correctness | session | always-on core |
| data-migration | mid | 6 alembic migrations → hard_block_full |
| security | session | 8 new endpoints, ACL changes (auth/data boundary) |
| adversarial | session (in-process fallback) | auth + persistence writes; no codex CLI for cross-model peer |

**Skipped (judgment calls):** project-standards (low value for new tables), testing (basic CRUD coverage), performance (no major concerns), maintainability (large but no smell), reliability (no clear gaps), agent-native (no agent surfaces), learnings (no solutions/ corpus).

**Peer coverage:** adversarial lens ran via in-process `adversarial-reviewer` (fallback per `cross-model-review.md`). No cross-model corroboration; `independent_reviewers: []` for promotion purposes.

---

## Top findings (must-fix before merge)

### P0 — 4 blocking bugs

| ID | Title | File | Owner | Conf |
|---|---|---|---|---|
| F-P0-001 | T5 service steam/water toe_factor unit ambiguity — totals may be 1000x wrong | `utility_energy_summary_service.py:167` | human | 100 |
| F-P0-002 | T5 summarize_energy_year TOCTOU race — concurrent POSTs return 500 | `utility_energy_summary_service.py:245` | downstream-resolver | 100 |
| F-P0-003 | `tolerance_pct` guard raises TypeError when `xls_reference.total_toe` is None | `utility_energy_summary_service.py:236` | downstream-resolver | 75 |
| F-P0-004 | `tolerance_status` server_default='OK' silently masks 'never computed' — false-negative compliance audits | `p7_open_009_005_utility_energy_summary.py:165` | downstream-resolver | 100 |

### P1 — 8 high-priority issues

| ID | Title | File | Conf |
|---|---|---|---|
| F-P1-001 | `annual_consumption` override accepted without plausibility check — silent data integrity drift | `api/v1/util.py:380` | 75 |
| F-P1-002 | 5-min TTL cache for `ConfigEnergyConversionFactor` not implemented | `utility_energy_resolution_service.py:102` | 75 |
| F-P1-003 | T5 service ignores `business_year` when aggregating T1/T2/T3 | `utility_energy_resolution_service.py:57` | 100 |
| F-P1-004 | T5 service falls back to hardcoded defaults when CONFIG row missing — silent data drift | `utility_energy_resolution_service.py:154` | 75 |
| F-P1-005 | No project/workspace access control — ACL is role-only (pre-existing) | `api/v1/util.py:380` | 75 |
| F-P1-006 | `func.now()` ORM-set may fail on SQLite for idempotent UPDATE | `utility_energy_resolution_service.py:270` | 50 |
| F-P1-007 | `UtilResultsResponse` missing 4 new aggregator columns — undocumented schema decision | `schemas/util.py:35` | 75 |
| F-P1-008 | T0 seed script runs out-of-band of alembic | `p7_open_009_t0_seed_energy_conversion_factors.py:1` | 75 |

### P2 — 9 medium-priority issues
F-P2-001..009 (see synthesized-findings.json for details)

### P3 — 3 low-priority issues
F-P3-001..003 (see synthesized-findings.json for details)

---

## Detailed findings

### F-P0-001: T5 service steam/water toe_factor unit ambiguity

**Severity:** P0 | **Confidence:** 100 (multiple reviewers) | **File:** `pcs-backend/app/services/util/utility_energy_summary_service.py:167`

**Evidence:**
```
pcs-backend/app/services/util/utility_energy_summary_service.py:167 — `agg.steam_t_yr * s_toe` multiplies TONNES by toe_factor 0.0760 (per kg in config model docstring; service treats as per-tonne)
```

Golden fixture Case 1: 20000 t × 0.0760 = 1520 kg — only correct if factor is per-tonne, not per-kg. Either model docstring or service is wrong; fixture follows service. Tests pass either way (wrong-on-both-sides).

**Why it matters:** Shipped 综合能耗 reports will be 0.1% of real numbers if per-kg interpretation; tolerance vs XLS_REFERENCE will always show EXCEEDED — UI dashboards break.

**Suggested fix:** Pick one: (A) Update `ConfigEnergyConversionFactor` docstring + seed comment to say steam/water `toe_factor` is per-tonne (matches service math). (B) Service: change to `agg.steam_t_yr * 1000 * s_toe` (and `* 1000 * w_toe` for water) and recompute golden fixture. Confirm with 工艺室 which unit GB/T 50441 appendix uses.

---

### F-P0-002: T5 summarize_energy_year TOCTOU race

**Severity:** P0 | **Confidence:** 100 (multiple reviewers) | **File:** `utility_energy_summary_service.py:245`

**Evidence:**
```
utility_energy_summary_service.py:245-296 — non-locking SELECT then INSERT-or-UPDATE branch without `for_update()` or transaction wrap
```

Two concurrent POSTs to `/api/v1/util/energy-summary/aggregate` for same `(project_id, business_year, source)` both pass SELECT, both fall into 'new' branch, both call `db.add()`; second commit trips UNIQUE(project_id, business_year, source) → 500.

**Why it matters:** Nightly batch concurrent POST `/energy-summary/aggregate` will produce intermittent IntegrityError 500s.

**Suggested fix:** Use `INSERT ... ON CONFLICT (project_id, business_year, source) DO UPDATE SET ...` raw PG SQL (asyncpg upsert), OR catch IntegrityError and re-apply UPDATE branch.

---

### F-P0-003: `tolerance_pct` guard raises TypeError when `xls_reference.total_toe` is None

**Severity:** P0 | **Confidence:** 75 | **File:** `utility_energy_summary_service.py:236`

**Evidence:**
```
utility_energy_summary_service.py:236 — `if xls_reference is not None and xls_reference.total_toe > 0:`
```

**Suggested fix:** Replace `and xls_reference.total_toe > 0` with `and xls_reference.total_toe is not None and xls_reference.total_toe > 0`.

---

### F-P0-004: `tolerance_status` server_default='OK' silently masks 'never computed'

**Severity:** P0 | **Confidence:** 100 | **File:** `p7_open_009_005_utility_energy_summary.py:165`

**Evidence:**
```
alembic/versions/p7_open_009_005_utility_energy_summary.py:163-167 — server_default='OK'
app/models/util.py:477-480 — server_default='OK' on column
```

**Why it matters:** G-08 dashboards / compliance audits interpret 'OK' as 'computed and within 2%' — false negatives ship silently.

**Suggested fix:** Drop server_default (force explicit assignment in service) OR change to 'NA'. Add CHECK: `tolerance_status='OK' ⇒ tolerance_pct IS NOT NULL AND tolerance_pct <= 2.0`.

---

### F-P1-001..008 (medium-high P1)

See synthesized-findings.json for full details. Top fixes:
- **F-P1-001**: reject client `annual_consumption` override; only server-derived
- **F-P1-002**: implement 5-min TTL cache (仿 `_compound_config_cache.py`)
- **F-P1-003**: add `business_year` to T1/T2/T3 subtables
- **F-P1-005**: pre-existing IDOR — flag for P7-7+ UserProject model

---

## Coverage gaps

- 12 testing_gaps across correctness + security + data-migration + adversarial
- Top gaps: concurrent summarize test, plausible implausability override, cross-project DESIGNER access, JSONB-vs-5-table consistency, summary_service STEAM unit calculation

---

## Verdict

**Not ready** for merge.

**Ready after fixes:** All 4 P0 + 4 critical P1 (F-P1-001 / F-P1-002 / F-P1-005 / F-P1-007). Estimated work: 1-2 days.

**Recommended next batch:** `chore(p7-s2-fix): T5 service P0 fixes + downstream-resolver follow-ups`.

---

## Artifacts

| Path | Purpose |
|---|---|
| `finish-input.json` | Dispatch → leaves handoff |
| `synthesized-findings.json` | Merged findings (Stage 5 output) |
| `raw-returns.json` | Per-reviewer return summary |
| `metadata.json` | Run metadata + verdict |
| `correctness.json` / `data-migration.json` / `security.json` / `adversarial.json` | Per-reviewer artifacts |