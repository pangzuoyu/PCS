# P7 Sprint 1 — ce-code-review Report

- **Run**: `20261001-sprint1-d8f67f72`
- **Date**: 2026-10-01
- **Batch**: P7 Sprint 1 (commit `496b84d`..`8ea056b`, 38 files, 10,097 lines)
- **Depth**: full (hard_block_full triggered by `migrations` class)
- **Mode**: report-only (no `apply:local`)
- **Verdict**: **Not ready** — Sprint 1 batch was shipped WITHOUT resolving 5 P0 + 15 P1.

---

## Coverage

| Reviewer | Tier | Reason |
|---|---|---|
| correctness | session | always-on core |
| data-migration | mid | 3 alembic migrations + schema drift → hard_block_full |
| security | session | 12 new API endpoints + ACL + audit |
| adversarial | session (in-process fallback) | auth + persistence writes + audit integrity; no codex CLI |
| api-contract | mid | 19 new endpoints + G-08 baseline rolled |

**Skipped:** project-standards, testing, performance, maintainability, reliability, agent-native, learnings.

**Peer coverage:** adversarial lens ran via in-process `adversarial-reviewer` (fallback per `cross-model-review.md`).

---

## Headline numbers

| Reviewer | Critical/High | Med | Low/Info | Total | Verdict |
|---|---|---|---|---|---|
| correctness | 2 P0 + 3 P1 | 3 P2 | 3 P3 | 11 | — |
| data-migration | 1 CRITICAL + 1 HIGH | 1 MED | 1 LOW + 2 INFO | 6 | BLOCK |
| security | 2 CRITICAL + 4 HIGH | 7 MED | 7 LOW + 2 INFO | 22 | BLOCK |
| adversarial | 2 CRITICAL + 8 HIGH | 4 MED | 4 LOW | 18 | — |
| api-contract | 1 HIGH | 2 MED | 3 LOW + 3 INFO | 9 | HOLD |

**Total unique (de-duped across reviewers):** 5 P0 + 15 P1 + ~16 P2/P3.

---

## Top findings (must-fix before merge)

### P0 — 5 blocking bugs

| ID | Title | File | Owner | Conf | Reviewers |
|---|---|---|---|---|---|
| F-P0-001 | PSYCHRO type_code 'X' collides with 'Motor/Electrical' — psychrometric CHECKED mis-classified | `type_code_map.py:13` | human | 100 | correctness |
| F-P0-002 | GET /util/summary 'latest' returns random UtilResult (UUIDv4 order, not created_at) | `persist_service.py:108` | human | 100 | correctness |
| F-P0-003 | State machine audit bypass — sync_from_source mutates EquipmentList.sign_status directly (zero AuditLog writes) | `sync_service.py:128` | human | 100 | adversarial, security |
| F-P0-004 | Cross-project IDOR — every endpoint trusts client project_id (ACL only checks role, pre-existing) | `equip_list.py` + `util.py` | human | 100 | security |
| F-P0-005 | audit_logs GIN index built WITHOUT CONCURRENTLY — production outage on deploy | `p7_s1_002_audit_logs_jsonb_gin.py:32` | downstream-resolver | 100 | data-migration |

### P1 — 15 high-priority issues

| ID | Title | Conf |
|---|---|---|
| F-P1-001 | UtilResults ORM missing composite (project_id, workspace_id) index — schema drift | 75 |
| F-P1-002 | advisory_lock silent no-op on OperationalError | 100 |
| F-P1-003 | SourceModule dispatcher silently drops unknown modules | 100 |
| F-P1-004 | summary_service coalesces 'absent' vs 'explicit 0' silently | 100 |
| F-P1-005 | RESOLVE_STALE_CHANGED records hash_changed=false — semantic mismatch | 100 |
| F-P1-006 | aggregate_and_save overwrites manual entries for 6 unmapped categories | 100 |
| F-P1-007 | summary_service generic write loop drops 6 of 13 categories silently | 100 |
| F-P1-008 | query_by_fuel_year returns stale coefficient on year-rollover | 100 |
| F-P1-009 | G-08 baseline + endpoint code in same batch — frontend snapshot drift | 75 |
| F-P1-010 | bulk-sync Pydantic Literal validation contradicts 'partial failure 容错' claim | 75 |
| F-P1-011 | EquipmentTypeCodeService.seed_defaults all-or-nothing | 75 |
| F-P1-012 | EquipmentTypeCode count 3-way mismatch: 26/31/24 | 75 |
| F-P1-013 | consumption_json accepts NaN/Inf — poisons downstream toe_total | 100 |
| F-P1-014 | GET /equipment-list/{id} + /util/results/{id} return any record by UUID | 75 |
| F-P1-015 | toe_total counts 6 categories (incl CONDENSATE) but by_category returns only 5 | 75 |

---

## Detailed findings

### F-P0-001: PSYCHRO type_code 'X' collides with 'Motor/Electrical'

**Severity:** P0 | **Confidence:** 100 | **File:** `pcs-backend/app/services/equip_list/type_code_map.py:13`

**Evidence:**
```
type_code_map.py:13 — PSYCHRO maps to type_code 'X'
equipment_type_code_service.py:78 — 'X' defined as 'Motor / Electrical' (category=ELECTRICAL)
```

**Why it matters:** Every psychrometric CHECKED EquipmentList record mis-classifies as electrical. Latent until first PSYCHRO sync fires.

**Suggested fix:** Either change PSYCHRO type_code to a unique letter (e.g., 'P' if free) OR add PSYCHRO-specific code to SEED_TYPE_CODES.

---

### F-P0-002: GET /util/summary 'latest' returns random UtilResult

**Severity:** P0 | **Confidence:** 100 | **File:** `pcs-backend/app/services/util/persist_service.py:108`

**Evidence:**
```
persist_service.py:108 — orders by `UtilResult.util_result_id DESC` (UUIDv4 random)
util.py:166, 192, 224 — /util/summary, /energy-consumption, /water-balance all use this 'latest' fallback
```

**Why it matters:** User-visible "latest snapshot" is a random pick; reports non-deterministic.

**Suggested fix:** Order by `created_at DESC` instead of util_result_id DESC.

---

### F-P0-003: State machine audit bypass — sync_from_source mutates EquipmentList.sign_status directly

**Severity:** P0 | **Confidence:** 100 | **Files:** `sync_service.py:128, 167`

**Evidence:**
- sync_from_source mutates EquipmentList.sign_status via direct ORM update
- sync_service writes zero AuditLog rows; bypasses state_machine.transition(); TRANSITION_ROLES ACL not consulted
- audit_observations: STATE machine_audit_write_call_count=1; audit_log_inserts_in_sprint1_services=0 (expected many)

**Why it matters:** Defense-in-depth backbone of P3+ Issue 6 silently broken. Audit trail integrity compromised.

**Suggested fix:** Route EquipmentList.sign_status updates through state_machine.transition(); add Postgres trigger as defense-in-depth (out of Sprint scope; document in ADR-0045).

---

### F-P0-004: Cross-project IDOR — every endpoint trusts client project_id

**Severity:** P0 | **Confidence:** 100 | **File:** `pcs-backend/app/api/v1/equip_list.py`

**Evidence:**
- 12 endpoints accept arbitrary project_id/workspace_id without ownership check
- persist_service.py:103, util.py:62 — None-leak: omit project_id ⇒ unfiltered rows from all projects

**Why it matters:** Any DESIGNER can list/read/INSERT into any project's UtilResults + EquipmentList. Pre-existing across PCS.

**Suggested fix:** Add UserProject/WorkspaceMember model + per-project ACL check.

---

### F-P0-005: audit_logs GIN index built WITHOUT CONCURRENTLY

**Severity:** P0 | **Confidence:** 100 | **File:** `p7_s1_002_audit_logs_jsonb_gin.py:32`

**Evidence:**
- CREATE INDEX without postgresql_concurrently=True
- audit_logs is hot append-only table; CREATE INDEX acquires SHARE lock that blocks DML for build window

**Why it matters:** Production deploy will cause minutes-long INSERT outage.

**Suggested fix:** Add `postgresql_concurrently=True` and `if_not_exists=True` to `op.create_index`.

---

### F-P1-001..015 (medium-high P1)

See synthesized-findings.json for full details. Top fixes:
- **F-P1-005**: state_machine hash_changed semantics
- **F-P1-013**: NaN/Inf Pydantic constraint on Float fields
- **F-P1-015**: API contract CONDENSATE inconsistency

---

## Coverage gaps

- 9 testing_gaps identified
- Top gaps: PSYCHRO collision test, audit-bypass test, cross-project IDOR exploit, GIN build-time measurement, CONDENSATE consistency, year-rollover test

---

## Verdict

**Not ready** for merge. Sprint 1 was approved and shipped to main without resolving these findings.

**Critical post-hoc action items:**
1. Immediate hotfix branch: 5 P0 + critical P1 (F-P1-005, F-P1-013, F-P1-015)
2. Add regression tests for the discovered attack vectors (audit bypass, IDOR, GIN build, latest snapshot)
3. Add ADR note: Sprint 1 batch-end QA missed these — recommend automated cross-reviewer dispatch for next batch
4. Forward-resolve F-P0-004 (IDOR) by Sprint 3 (UserProject model)

**Recommended next batch:** `hotfix(p7-s1-postreview): Sprint 1 critical fixes (5 P0 + 4 P1)`.

---

## Artifacts

| Path | Purpose |
|---|---|
| `/tmp/compound-engineering-1000/ce-code-review/20261001-sprint1-d8f67f72/finish-input.json` | Dispatch → leaves handoff |
| `/tmp/compound-engineering-1000/ce-code-review/20261001-sprint1-d8f67f72/synthesized-findings.json` | Merged findings (Stage 5 output) |
| `/tmp/compound-engineering-1000/ce-code-review/20261001-sprint1-d8f67f72/raw-returns.json` | Per-reviewer return summary |
| `/tmp/compound-engineering-1000/ce-code-review/20261001-sprint1-d8f67f72/metadata.json` | Run metadata + verdict |
| `/tmp/compound-engineering-1000/ce-code-review/20261001-sprint1-d8f67f72/{correctness,data-migration,security,adversarial,api-contract}.json` | Per-reviewer artifacts |