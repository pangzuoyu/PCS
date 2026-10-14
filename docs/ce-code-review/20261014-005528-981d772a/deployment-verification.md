# Deployment Checklist: P8 报表与输出 — migrations p8_001..p8_007

## Observed state on the dev DB (`pcs`, read-only, 2026-10-14)

| Item | Observed |
|---|---|
| `alembic_version` | **`p8_007`** — the chain is ALREADY APPLIED on dev |
| `uv run alembic check` | `No new upgrade operations detected.` **exit 0** (no drift) |
| alembic | 1.19.1 |
| `report_files` | 0 rows, 48 kB |
| `report_execution_logs` | 0 rows, 40 kB |
| `report_definitions` | **8 rows** (6 PUBLISHED / 2 DRAFT), 64 kB |
| `report_styles` | **2 rows**, 64 kB |
| `heat_results` | 0 rows, 40 kB |
| `audit_logs` | 10 rows, 88 kB (column is `occurred_at`, **not** `created_at`) |
| DB size | 15 MB |
| All 7 new columns/indexes present | confirmed via `information_schema` / `pg_indexes` |
| Redis | `localhost:6379` reachable |
| Chain linearity | `p7_s5_008 → p8_001 → … → p8_007`, single head, no branches |

**This is a re-apply deploy, not a first-run deploy.** The pre-deploy checks are
calibrated for that — see 🔴 #1 and #2.

---

## 🔴 Pre-Deploy (Required)

### #1 — Prove the revision actually ran, and which one
```bash
cd pcs-backend && uv run alembic current && uv run alembic heads
```
**Expected:** `current` = `p8_007 (head)`. **Any divergence = STOP.**
Per `CLAUDE.md`, an unapplied committed migration silently blocks `alembic check` —
a passing check can mean "never ran". Run `current` vs `heads` *first*.

### #2 — 🔴 CRITICAL: verify the p8_007 backfill ACTUALLY filled rows
`p8_007` lines 36-39 use `UPDATE … WHERE status IS NULL`. That predicate is only
correct on a database where the column was added by *this* version of the migration
(new column ⇒ every existing row NULL ⇒ all filled).

If any environment ran an **earlier** revision of p8_007 that already set
`DEFAULT 'QUEUED'`, existing rows are non-NULL ⇒ the backfill matches **zero rows**
⇒ already-succeeded executions stay `QUEUED` forever, and the reclaimer will rewrite
them as `FAILED`. `ADD COLUMN IF NOT EXISTS` is a silent no-op in exactly this case,
and `alembic current` still reads `p8_007` — the version number cannot detect it.

```bash
psql "$DATABASE_URL" -c "
SELECT count(*) FILTER (WHERE status IS NULL)                       AS still_null,
       count(*) FILTER (WHERE report_file_id IS NOT NULL
                          AND status <> 'FINISHED')                AS finished_mislabelled,
       count(*) FILTER (WHERE report_file_id IS NULL
                          AND status = 'FINISHED')                 AS finished_without_file,
       count(*)                                                      AS total
FROM report_execution_logs;"
```
**Expected:** `still_null = 0`, `finished_mislabelled = 0`, `finished_without_file = 0`.
**Dev today: total = 0 — the backfill has never been exercised on real rows.**

### #3 — Save the baseline counts BEFORE touching anything
```bash
psql "$DATABASE_URL" -c "
SELECT 'report_definitions' t, count(*) FROM report_definitions
UNION ALL SELECT 'report_styles',       count(*) FROM report_styles
UNION ALL SELECT 'report_files',        count(*) FROM report_files
UNION ALL SELECT 'report_execution_logs', count(*) FROM report_execution_logs
UNION ALL SELECT 'heat_results',        count(*) FROM heat_results
UNION ALL SELECT 'audit_logs',          count(*) FROM audit_logs;"
```

### #4 — 🔴 CRITICAL: p8_001 is DESTRUCTIVE. Confirm nothing re-runs it
`p8_001` is `drop_table(if_exists=True)` × 4 then `create_table`. It is safe **only**
because it is the first node of the chain and runs exactly once. It becomes a full
data wipe if anyone runs `alembic downgrade p7_s5_008` then upgrades again, or a
fresh/staging DB is stamped at `p7_s5_008` while `report_definitions` already holds
real P8 rows.

**Dev carries 8 `report_definitions` + 2 `report_styles` rows** — real P8 data that a
p8_001 re-run destroys outright.

### #5 — Confirm the p8_001 drop order survives the legacy FK
Drops in reverse create order: `report_execution_logs → report_definitions →
report_files → report_styles`. Legacy bootstrap `dd47298c9c38` gave
`report_execution_logs.report_id` an FK to `report_definitions.report_id`.

### #6 — Confirm no long-running transaction will hold a lock
**There is no `lock_timeout` or `statement_timeout` set anywhere in the repo**
(`alembic.ini`, `env.py`, `.env` all clean). A blocked `ALTER` will wait indefinitely,
holding a queue of blocked queries behind it.

### #7 — Confirm disk / worker / queue are quiesced
```bash
ps aux | grep -E "arq|uvicorn.*worker" | grep -v grep
redis-cli -u redis://localhost:6379/0 ping    # expect PONG
ls pcs-backend/var/reports | wc -l            # 323 observed
```
**STOP condition:** a worker is live during the migration.

---

## 🟡 Deploy Steps

> ⚠️ Neither `alembic.ini` nor `alembic/env.py` sets `transaction_per_migration`.
> Alembic's default is **one transaction for the entire `upgrade head`**. Locks taken
> by p8_001's `DROP TABLE` are held until the very last commit. If **any** of the seven
> fails, **all seven roll back together**. A mid-chain failure is therefore *not* an
> emergency rollback situation.

| # | Command | Locking impact | Rollback action |
|---|---|---|---|
| 0 | Quiesce app + worker | — | restart |
| 1 | `alembic current` — record before | none | — |
| 2 | `pg_dump -Fc -t report_definitions -t report_styles -t report_files -t report_execution_logs -f /tmp/p8_pre.dump` | ACCESS SHARE only | n/a — this IS the rollback |
| 3 | Optionally `SET lock_timeout='5s'; SET statement_timeout='120s'` | guards #6 | re-run; DDL already rolled back |
| 4 | `alembic upgrade head` | **ACCESS EXCLUSIVE** on all 4 tables, held for the full chain | aborts wholesale |
| 5 | `alembic check`; **check the exit code is `0`, not `1`** | ACCESS SHARE | — |
| 6 | Restart app, then worker | — | — |

**Old-code compatibility:** p8_001 **does** break in-flight old code. Legacy
`report_definitions` had PK `report_id`; p8_001 recreates it with PK `def_id`. Any
process still running the pre-`d0a6a31` ORM will raise
`column "report_id" does not exist`. **There is no rolling-deploy window for the
report subsystem.** Step 0 (quiesce) is mandatory, not advisory.

---

## 🟢 Post-Deploy (Within 5 Minutes)

```bash
# G1 — revision landed: SELECT version_num FROM alembic_version;  → p8_007
# G2 — drift gate: uv run alembic check; echo "EXIT=$?"  → EXIT=0
# G3 — report_definitions has 14 columns. If you see `report_id` or `query_json`,
#      p8_001 did NOT run.
# G4 — report_execution_logs.status: character varying | NO | 'QUEUED'::character varying
#      is_nullable=NO   => 健康，即 p8_007 的 SET NOT NULL 已生效。
#      is_nullable=YES  => a prior revision added the column without the constraint. STOP.
# G5 — 9 indexes present across report_execution_logs + report_files
# G6 — heat_results gained exactly 7 columns
# G7 — no data loss vs. the #3 baseline
# G8 — EXPLAIN the reclaimer's query; Seq Scan on a populated table = index not helping
```

---

## 🔵 Monitoring (First 24 Hours)

**Reclaimer schedule:** `worker.py:158-179` registers `reclaim-stale-report-tasks` at
`minute={3, 33}`, hourly. Threshold `STALE_MINUTES = 15` (`report_tasks.py:72`).
**Detection latency is 15–45 minutes.**

### 🚨 Alert 1 — the p8_007 backfill mislabel, surfacing as a FAILED burst
```sql
SELECT status, count(*) FROM report_execution_logs GROUP BY 1 ORDER BY 2 DESC;
-- 🚨 ALERT: QUEUED count == the pre-deploy baseline, OR FAILED spikes with zero
--           REPORT_GENERATED.

SELECT r.log_id, r.status, r.report_file_id,
       r.condition_snapshot->>'reclaimed_at' AS reclaimed_at
FROM report_execution_logs r
WHERE r.status='FAILED' AND r.condition_snapshot ? 'reclaimed_at'
ORDER BY r.updated_at DESC LIMIT 50;
```
`reclaimed_at` present ⇒ written by `reclaim_stale_execution_logs`
(`report_tasks.py:296-301`), not a genuine render failure. **Remediation:** correct
with an explicit, reviewed `UPDATE … SET status='FINISHED' WHERE log_id IN (…)` —
not a blanket revert, since genuinely-failed rows are indistinguishable by `status`.

### 🚨 Alert 2 — `report_files` stuck in PENDING
Any PENDING older than 15 min past the next :03/:33 tick ⇒ worker is dead, not slow.
`DELETING` is the three-step-delete intermediate — the reclaimer deliberately skips it.

### 🚨 Alert 3 — ARQ retry amplification
```sql
SELECT detail_json->>'attempt_no' AS attempt_no, count(*)
FROM audit_logs WHERE action='REPORT_FAILED' AND occurred_at > now() - interval '1 hour'
GROUP BY 1 ORDER BY 1;
-- 🚨 ALERT: attempt_no > 3 exists => max_tries is not 3.
```

### ⚪ Silent checks
- `select task_id, count(*) from report_files where task_id is not null group by 1
  having count(*) > 1` → **expect 0 rows**.
- Dev has **323 files in `var/reports` vs 0 `report_files` rows** — pre-existing,
  not a migration defect, but record it as a baseline.

---

## 🔄 Rollback

**Restoring from the pre-deploy dump is strictly safer than `alembic downgrade`** —
every downgrade in this chain is destructive.

| Migration | Downgrade | Data loss |
|---|---|---|
| p8_007 | `DROP INDEX` + `DROP COLUMN status` | Every status value ever written |
| p8_006 | `DROP INDEX` + `DROP COLUMN task_id` | The 202→file bridge |
| p8_005 | `DROP INDEX` + `DROP COLUMN report_file_id, task_id` | The bridge, one step earlier |
| p8_004 | `DROP COLUMN` ×4 on `heat_results` | 4 columns |
| p8_003 | `DROP COLUMN` ×3 on `heat_results` | 3 columns |
| p8_002 | `DROP COLUMN doc_no, rev` | verify-endpoint fields |
| p8_001 | `DROP TABLE` ×4 | **Catastrophic** — destroys all 4 tables |

⚠️ After `alembic downgrade p7_s5_008`, a re-upgrade re-runs p8_001 →
drop+create. **Safe ONLY because the tables are then empty.** If you restored rows
from the dump but did not downgrade, that re-upgrade WIPES THEM.

---

## ⚠️ Missing checklist items

1. **🔴 HIGH — the p8_007 backfill is untested against non-empty data, everywhere.**
   `report_execution_logs` is 0 rows on dev, so `UPDATE … WHERE status IS NULL` has
   never matched a row in any environment. Pre-deploy #2 is a *read* check that is
   vacuous wherever `total = 0`.
2. **🔴 HIGH — no test pins `p8_007` against the partial-run case.** Nothing verifies
   the *backfill* side of the hazard: column exists + already defaulted ⇒ backfill
   skips every row ⇒ silent.
3. **🔴 HIGH — `CREATE INDEX` is not `CONCURRENTLY` on three tables** (p8_005/006/007).
   `report_execution_logs` is an audit table that is never pruned. Either
   `CONCURRENTLY` (needs a deliberate design decision — incompatible with the single-
   transaction default) or an explicit written acceptance of a maintenance window.
4. **🟡 MEDIUM — no `lock_timeout` anywhere.**
5. **🟡 MEDIUM — the report subsystem has no rolling-deploy path, and that isn't
   written down.**
6. **🟡 MEDIUM — no post-deploy verification that the reclaimer's own writes are
   correct.** `reclaim_stale_execution_logs` **mutates `condition_snapshot`**, adding
   `reclaimed_at`/`reclaim_reason` into what is otherwise the reproducibility record.
7. **🟢 LOW — orphan disk files.** 323 files vs 0 rows.
8. **🟢 LOW — `heat_results` new columns have no writer yet.** All 7 will be NULL on
   every row until the HTRI parser lands.

### Two open questions for the deploy owner
1. **Which environment is this actually deploying to?** Dev is already at `p8_007` with
   clean drift. If the target is a DB that has *never* run p8_001, 🔴 #4's data-loss
   branch is live and a dump is mandatory.
2. **Is any environment carrying pre-p8_001 legacy rows in `report_definitions`?**
   p8_001's docstring asserts those are 0-row shells. That assertion is the entire
   safety basis for the destructive pattern.
