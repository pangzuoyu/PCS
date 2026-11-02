# P9B-2 Deployment Checklist — Go/No-Go (deployment-verification)

**Verdict: GO**, conditional on every blocking pre-deploy check (§2) passing and on the
backend + frontend shipping in the **same maintenance window** (§5 — there is no
compatible mixed version state for submit-approval).

Scope of this document: operational readiness only. Schema-drift / migration-correctness
findings belong to the data-migration reviewer and are not repeated here.

---

## 1. What is being deployed (operational summary)

| Artifact | Effect | Risk class |
|---|---|---|
| `alembic/versions/p9_012_drop_parent_deliverable_id.py` | `ALTER TABLE deliverables DROP COLUMN parent_deliverable_id` | **Destructive DDL** — data in the column is unrecoverable |
| `alembic/versions/p9_013_bind_default_record_matrix.py` | Creates global matrix row `DEFAULT_RECORD_3_LEVEL` (ACTIVE) if missing + backfills `module='RECORD'` binding for every project lacking one (2 × `INSERT..SELECT`, no DDL) | Data transform, idempotent |
| Backend code | ORM drops `parent_deliverable_id`; `POST /projects` binds default RECORD matrix in-transaction; submit-approval derives approval chain from the bound matrix; `SubmitApprovalRequest` became `extra="forbid"` (only `reason` accepted) | **Breaking API contract** — old frontend 422s |
| Frontend | vite build against updated `openapi.snapshot.json`; submits only `{reason}` | Must ship with backend |

Chain verified: `p9_011 → p9_012 → p9_013` (head = `p9_013`).
`p9_013`'s raw INSERTs are safe against the ORM models: `created_at` has
`server_default=func.now()` (`app/models/mixins.py:36`), `created_by`/`updated_at`
are nullable — no missing NOT NULL column. `gen_random_uuid()` is built in on
Postgres 13+ (PG 18 here — no pgcrypto dependency).

Databases in play: `pcs` (dev/prod), `pcs_test` (alignment target), CI fresh schema.
The same procedure runs per database.

---

## 2. Blocking pre-deploy checks (read-only)

Run on **each** target DB (`pcs`, `pcs_test`) before touching anything. Any FAIL = NO-GO.

### A. p9_012 is provably safe to drop (0 data, 0 writers)

```sql
SELECT count(*) AS total_rows,
       count(parent_deliverable_id) AS non_null_parent
FROM deliverables;
```
- **PASS**: `non_null_parent = 0` (ideally `total_rows = 0` too).
- **FAIL**: `non_null_parent > 0` → STOP; export those rows
  (`COPY (SELECT deliverable_id, parent_deliverable_id FROM deliverables WHERE parent_deliverable_id IS NOT NULL) TO '...csv'`)
  and get a human ruling before proceeding.

Writers already verified zero this batch: repo-wide grep for `parent_deliverable_id`
hits only docstrings/comments (`app/schemas/deliverable_progress.py:23`,
`app/services/deliverable_service.py:272`, one test comment) and the historical
baseline migration `dd47298c9c38` — no live code reads or writes the column.
Re-run to confirm at deploy time:

```bash
cd pcs-backend && grep -rn "parent_deliverable_id" app/ --include=*.py | grep -v "#"
# PASS: no output (all remaining hits are comments — verify by eye)
```

### B. p9_013 blast radius is known in advance

```sql
-- How many bindings the migration will insert (projects without a RECORD binding)
SELECT count(*) FROM projects p
WHERE NOT EXISTS (
  SELECT 1 FROM project_signature_matrix_bindings b
  WHERE b.project_id = p.project_id AND b.module = 'RECORD'
);
-- Record this number; post-deploy check D3 must show unbound = 0.

-- Pre-existing DEFAULT_RECORD_3_LEVEL rows (0 or 1 expected)
SELECT matrix_id, matrix_name, module, status, jsonb_array_length(steps_json) AS steps
FROM signature_matrices
WHERE matrix_name = 'DEFAULT_RECORD_3_LEVEL';
-- 0 rows → migration creates it. 1 row ACTIVE steps=3 → reused as-is (bindings all point at it).
-- 1 row non-ACTIVE → migration creates a *second* ACTIVE row (uniqueness is (name,status) only)
--   → STOP and get a ruling; two same-name matrices differing in status will confuse later lookups.
```

### C. Alembic state is clean and actually up to date

```bash
cd pcs-backend
uv run alembic heads     # expect: p9_013 (head)
uv run alembic current   # expect: p9_011 — if anything older, note it:
                         # upgrade will chain through intermediate revisions too;
                         # re-check A/B after any unexpected intermediate revision applies.
```
Per project rules: `alembic check` exit 0 with **`alembic current` == head confirmed
first** (a blocked check that never ran prints nothing and looks like a pass).
Exit 255 = real drift = NO-GO.

For `pcs_test`, drive it via the `DATABASE_URL` env var in-process (password never on
the CLI); **never** `Config.set_main_option` — `alembic/env.py:18` overwrites it back
to the dev DB. After connecting, confirm the revision actually moved (see §3).

⚠️ **验多个库 ⇒ 一库一个进程**（2026-11-02 实测打脸，见 `.wolf/cerebrum.md`）：
alembic 的 `settings` 是 **pydantic 缓存实例** ⇒ **同一进程内第二次改
`os.environ['DATABASE_URL']` 不生效** ⇒ 第二遍连的仍是第一个库。而 `upgrade`
是幂等的 ⇒ 两遍都打印同一个 `(head)`，**输出无法区分** ⇒ 上一轮 QA 报告据此
写下「pcs / pcs_test 两库都已到 head 且 check exit 0」—— 那是**假证据**
（`pcs_test` 实际还停在旧 revision，是评审员直查库才发现的）。
⇒ 上面的「进程内派生 URL」配方只适用于**单个**库；要验多个库 ⇒ **每库起独立
进程**，且**必须直查库的 `alembic_version` + 目标列存在性**，不能只信命令输出。

### D. CI green on the batch commit

- Signal: CI run on commit `751826f` (batch tip) is green — it exercises the fresh
  schema path (create + upgrade head).
- ⚠️ **更正（2026-11-02，P9B-2F 复审 #11）**：本条原文还声称 CI 跑
  `tests/alembic/test_p9_013_bind_default_record_matrix.py`（含降级环）——
  **它不跑**。`.github/workflows/check-api-drift.yml` 的步骤是
  `alembic upgrade head` / `export_openapi.py` / `check-api-drift.sh` /
  `check_migration_idempotency.py` / 可视化渲染器测试 / 前端 typecheck ——
  **一条后端 pytest 都不跑** ⇒ 那些引擎级测试在 CI 上永远 `pytest.skip`
  ⇒ **绿灯证明不了它们跑过**。
  ⇒ p9_013 / p9_014 的引擎级验证（含降级环）必须**在有本地 PostgreSQL 的
  机器上手动跑**：`cd pcs-backend && uv run pytest tests/alembic/ -v`。

---

## 3. Migration execution

Single command, both revisions, one maintenance window:

```bash
cd pcs-backend
# password via env / .env — never on the command line
uv run alembic upgrade head
```

**Success signals**: exit 0 AND the log lines
`Running upgrade p9_011 -> p9_012` and `Running upgrade p9_012 -> p9_013`,
then `uv run alembic current` prints `p9_013 (head)`.

| Migration | Statements | Locks taken | Expected runtime | Batching | Rollback |
|---|---|---|---|---|---|
| p9_012 | 1 × `DROP COLUMN` | `ACCESS EXCLUSIVE` on `deliverables` (blocks all concurrent access to that table for the DDL duration) | < 1 s at 0 rows | None — single statement, table empty | Re-adds column **empty**; original data unrecoverable (§6) |
| p9_013 | 2 × `INSERT..SELECT` (no DDL) | `ROW EXCLUSIVE` on `signature_matrices`, `project_signature_matrix_bindings`; `ACCESS SHARE` on `projects` | < 1 s at dev scale; scales with project count in a single set-based statement — no per-row round trips, no batching needed below ~10⁵ projects | None | `DELETE` of **all** `module='RECORD'` bindings pointing at the default ACTIVE matrix — backfilled **and** runtime-created (§6) |

**`pcs_test` alignment** (same window): in-process env-var method per project CLAUDE.md,
then `command.current(cfg)` — **the printed revision must be `p9_013`**; if it still
shows the old revision the command silently ran against `pcs` (known failure shape,
2026-10-20). Then `command.check(cfg)` → exit 0.

No application-level downtime requirement beyond the window itself: the ACCESS
EXCLUSIVE lock on `deliverables` is millisecond-scale, but deploy backend code +
frontend in the same window regardless (§5).

---

## 4. Post-deploy verification — complete within 5 minutes

Run in order; each item names its pass signal.

**D1. Column is gone** (target DB):
```sql
SELECT count(*) FROM information_schema.columns
WHERE table_name = 'deliverables' AND column_name = 'parent_deliverable_id';
-- PASS: 0
```

**D2. Default matrix exists, exactly one ACTIVE, 3 steps**:
```sql
SELECT matrix_name, status, jsonb_array_length(steps_json) AS steps
FROM signature_matrices
WHERE matrix_name = 'DEFAULT_RECORD_3_LEVEL' AND status = 'ACTIVE';
-- PASS: exactly 1 row, steps = 3
```

**D3. Zero unbound projects** (the whole point of p9_013):
```sql
SELECT count(*) AS unbound FROM projects p
WHERE NOT EXISTS (
  SELECT 1 FROM project_signature_matrix_bindings b
  WHERE b.project_id = p.project_id AND b.module = 'RECORD'
);
-- PASS: 0  (pre-deploy check B predicted this backfill count)
```

**D4. No dangling bindings** (FK integrity after backfill):
```sql
SELECT count(*) FROM project_signature_matrix_bindings b
LEFT JOIN signature_matrices m ON m.matrix_id = b.matrix_id
WHERE m.matrix_id IS NULL;
-- PASS: 0
```

**D5. API smoke** (needs a running backend + auth):
1. `GET /api/v1/.../login` or health → **200**.
2. `GET /api/v1/projects` → **200**.
3. `GET` project matrix bindings endpoint (`/projects/{id}/signature-matrices` per new
   API) → **200** with a `module: "RECORD"` entry, `matrix_name: "DEFAULT_RECORD_3_LEVEL"`.
4. **Submit-approval, new contract**: pick a DRAFT record in a formal-project workspace,
   `POST /api/v1/records/{module}/{record_id}/submit-approval` with body
   `{"reason": "deploy-verify"}` → **200**, response shows `approval_depth: 3`,
   `approval_role: "CHECKER"`, `approval_step: 1`.
5. **Submit-approval, old contract rejected**: same endpoint with body
   `{"approval_role": "CHECKER", "approval_depth": 1}` → **422**
   (proves `extra="forbid"` is live — this is the expected, desired failure).
6. Roll the smoke record back / discard it, or leave it IN_APPROVAL if a test record.
7. `SELECT count(*) FROM workflow_progress WHERE created_at > now() - interval '10 minutes';`
   → ≥ 1 new row from the smoke submit (observable proof the approval chain writes progress).

**D6. Project creation end-to-end** (SYSTEM_ADMIN creds):
`POST /api/v1/projects` → **201**; then
```sql
SELECT count(*) FROM project_signature_matrix_bindings
WHERE module = 'RECORD' AND project_id = '<new project_id>';
-- PASS: 1
```

**D7. Frontend served and current**: browser loads the app; submit-approval from the UI
succeeds on a DRAFT record (no 422); browser console free of errors. If the UI 422s on
submit-approval while D5.4 passes via curl → a stale bundle is being served (§5).

**D8. Drift gate on each DB**: `uv run alembic current` = `p9_013 (head)` then
`uv run alembic check` → exit 0.

Any D-item failing → §6 rollback decision tree.

---

## 5. Frontend/backend deploy-order coupling (blocking knowledge)

**There is no compatible mixed state.** Both orders break submit-approval during the gap:

- **Old frontend + new backend** (the stated deploy order — backend first, vite build
  served after): the old UI still sends `approval_role` + `approval_depth`;
  `SubmitApprovalRequest` is now `extra="forbid"` (`app/schemas/records_actions.py:100`)
  and accepts only `reason` → **every submit-approval returns 422** until the new
  frontend is served.
- **New frontend + old backend** (reverse order): the new UI sends only `{reason}`;
  the old backend required the client to supply `approval_role`/`approval_depth`
  (the contract this batch removes) → 422 as well.

Therefore:
1. Deploy migrations + backend code, then **immediately** `npm run build` and serve the
   new frontend — same window, minutes apart at most. Treat "backend live" to
   "frontend live" as one deploy step with a sub-part, not two deployments.
2. **Stale browser bundles extend the window**: vite hashes assets, but users with the
   app already open (or a cached `index.html`) keep executing old JS and will 422 on
   every submit-approval. Serve `index.html` with no-cache headers, and announce a
   hard reload to active users; monitor per §7 until 422 spike subsides.
3. The rollback of one side implies the rollback of the other (§6) — never roll back
   only the frontend or only the backend.

Secondary behavior change to brief support/users on: a user whose own global role
appears anywhere in the approval chain (CHECKER/REVIEWER/APPROVER) now gets
**403 `APPROVAL_SELF_REVIEW_FORBIDDEN`** on submit (`records_actions.py:406-414`) —
intended anti-self-review, but it will look like a regression to affected users.

---

## 6. Rollback plan

### Decision tree

1. **Backend logic bug, data intact** → prefer **roll forward** (fix patch). Reason:
   there is no code-only rollback: the old ORM still declares `parent_deliverable_id`,
   so old code against the migrated DB 500s on every deliverables read
   (`UndefinedColumn`). Any rollback of code **requires** downgrading migrations with it.
2. **p9_013 must come out** (bad backfill) → `alembic downgrade -1` + redeploy old
   backend + old frontend. Acceptable: see loss analysis below — **re-running
   `upgrade head` later heals everything p9_013's downgrade deletes**.
3. **p9_012 must come out** → `alembic downgrade -2` (passes through p9_013's
   downgrade first). The re-added column is **empty** — see irreversibility note.

### Commands and signals

```bash
cd pcs-backend
uv run alembic downgrade -1     # p9_013 -> p9_012
# Signal: "Running downgrade p9_013 -> p9_012", then:
#   SELECT count(*) FROM project_signature_matrix_bindings
#   WHERE module = 'RECORD' AND matrix_id IN (SELECT matrix_id FROM signature_matrices
#       WHERE matrix_name = 'DEFAULT_RECORD_3_LEVEL' AND status = 'ACTIVE');
#   -> 0   (matrix row itself must still exist: SELECT count(*) ... -> 1)
uv run alembic downgrade -1     # p9_012 -> p9_011 (only if the column must return)
# Signal: information_schema query from D1 -> 1 (column present again)
```
Then redeploy the matching old backend code and old frontend bundle together, and
re-verify the old submit-approval contract (body WITH `approval_role`/`approval_depth`
→ 200).

### p9_012 irreversibility — why acceptable

The downgrade re-adds `parent_deliverable_id` as an empty nullable column; whatever the
column held before `DROP COLUMN` is gone with no recovery path (no soft-delete, no
archive). This is acceptable **only** because, verified this batch and re-verified at
deploy time (§2A): the table had **0 rows / 0 non-null values**, and the column had
**0 writers and 0 readers** in live code (remaining grep hits are comments and the
historical baseline migration). After deploy the column cannot reacquire data — no
code references it. If §2A ever fails on a future environment, this migration is a
NO-GO there until the data is exported and ruled on.

### p9_013 downgrade — exact loss surface

`downgrade` executes: `DELETE FROM project_signature_matrix_bindings WHERE
module = 'RECORD' AND matrix_id IN (SELECT matrix_id FROM signature_matrices WHERE
matrix_name = 'DEFAULT_RECORD_3_LEVEL' AND status = 'ACTIVE')`. That deletes:

- every **backfilled** binding p9_013's upgrade created, **and**
- every **runtime-created** binding from post-upgrade `POST /projects`
  (`SignatureMatrixService._get_or_create_default_record_matrix` reuses the same
  named ACTIVE row, so those bindings point at exactly the matrix the DELETE matches), **and**
- any binding an admin deliberately (re)bound to the default matrix via the admin API.

It **keeps**: the matrix row itself (global template — deleting it would dangle
bindings created by a future upgrade), all bindings to *other* matrices, and all
non-RECORD bindings.

Loss assessment: between downgrade and any re-upgrade, every project's submit-approval
returns 422 `RECORD_APPROVAL_MATRIX_NOT_BOUND`. Re-running `upgrade head` re-backfills
**all** projects lacking a RECORD binding — including post-upgrade-created projects —
against the same kept matrix row, so the state is fully reconstructed. The genuinely
irreversible loss is nil; the operational cost is the 422 outage window plus the
frontend rollback (§5).

---

## 7. First-24h monitoring focus

| Signal | Where | Healthy | Action if abnormal |
|---|---|---|---|
| 4xx rate on `/records/*/submit-approval` | access logs | brief spike right after deploy (stale bundles), decaying to ~0 | still spiking after 1 h → stale `index.html` cache; fix headers / announce reload (§5.2) |
| `RECORD_APPROVAL_MATRIX_NOT_BOUND` in app logs | backend logs | 0 occurrences | a project lost its RECORD binding → run D3 SQL, find the project, rebind or re-run backfill logic; investigate what deleted it |
| `UndefinedColumn` / `ProgrammingError` mentioning `parent_deliverable_id` | backend logs | 0 | code/migration skew (old code on new DB) → §6 tree case 1 |
| 500s on `POST /projects` with `IntegrityError` on `signature_matrices` | backend logs | rare (only exact-concurrent first-project creation) | known accepted race (service docstring: unique constraint from p9_010 returns 500, not 409); retry succeeds — do not roll back for this alone |
| `APPROVAL_SELF_REVIEW_FORBIDDEN` (403) | backend logs | occasional, expected | intended new behavior (§5 briefing); if flooding, check whether a whole role group can no longer submit |
| Binding growth tracks project creation | nightly: `SELECT (SELECT count(*) FROM projects) AS projects, (SELECT count(*) FROM project_signature_matrix_bindings WHERE module='RECORD') AS record_bindings;` | record_bindings ≥ projects | any unbound project → rebind; means something creates projects outside `POST /projects` |
| `workflow_progress` writes on approval steps | `SELECT count(*) FROM workflow_progress WHERE created_at > now() - interval '24 hours';` | > 0 once approvals are used | approval chain silent stall → inspect record `sign_status`/`approval_step` |
| Duplicate `DEFAULT_RECORD_3_LEVEL` ACTIVE rows | `SELECT status, count(*) FROM signature_matrices WHERE matrix_name='DEFAULT_RECORD_3_LEVEL' GROUP BY status;` | exactly 1 ACTIVE | should be impossible (p9_010 unique); if seen, stop and investigate constraint state |

---

## 8. Residual operational risks

- The 422 window in §5 is unavoidable given `extra="forbid"` was chosen deliberately
  (silent-ignore would be worse); its length is governed purely by frontend deploy +
  browser cache hygiene, both addressed above.
- `pcs_test` verification depends on the env-var connection method; a silent wrong-DB
  run has happened before (2026-10-20) — the revision-print check in §3 is the guard.
- This checklist assumes single-node dev→prod with no read replicas; if a replica is
  added later, DDL replication lag for `DROP COLUMN` needs its own gate.
