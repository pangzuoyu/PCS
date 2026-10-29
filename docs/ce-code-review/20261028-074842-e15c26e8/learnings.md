# Institutional Learnings Search Results

Reviewer: learnings-researcher | Run: 20261028-074842-e15c26e8 | Scope: P9B-2 (signing workflow + ADMIN frontend, POST /projects, approval chain from signature matrices, migrations p9_012/p9_013, audit pagination + CSV export, state-machine seed + ratchet guard, MSW fidelity)

Corpus searched: `docs/solutions/` (6 documents, all frontmatter-screened, 5 full-read). Excluded: `framework-integration-issues/arq-028-worker-silent-failure-modes.md` — the diff contains no ARQ/worker code (only incidental "service worker" text in e2e notes); no rule in it is reachable from this batch. Vocabulary grounded in `CONCEPTS.md` (schema drift, idempotent migration guard, constraint naming convention).

Headline: this batch largely **institutionalizes** the corpus rather than violating it — the state-machine seed guard, the `satisfies`-typed mocks, and the p9_013 ratchet test are direct implementations of documented learnings. One changed-line contradiction found (lock-free get-or-create without the collision-reread this same file already established), plus one learning-derived hardening note and three rule-followed notes.

---

## 1. Lock-free check-then-insert on the default matrix row — new code skips the collision-reread its own sibling established

**Matched rule** — `docs/solutions/database-issues/dialect-options-invisible-on-sqlite.md` (symptom 2, frontmatter): *"Two ACTIVE styles in one scope coexist; the service-layer 'check current ACTIVE first' is lock-free so concurrent requests both pass it."* The documented mitigation shape already exists in this repo: `_ensure_binding` catches the constraint collision and re-reads.

**Relevance — changed line contradicting it.** New in this diff:

- `pcs-backend/app/services/signature_matrix_service.py:790` — `_get_or_create_default_record_matrix`: SELECT by `(matrix_name, status='ACTIVE')` → `.first()` → if none, `db.add(matrix)` + flush. No `except IntegrityError` anywhere in the method (the three IntegrityError handlers in the file sit at other methods; `_ensure_binding` at line 627 is the one with the reread).
- Caller: `pcs-backend/app/api/v1/projects.py` (`create_project` → `ensure_default_record_matrix`, inside POST /projects' single transaction).

Concurrent `POST /projects` while no ACTIVE `DEFAULT_RECORD_3_LEVEL` exists (i.e. the first two projects ever created, or after the template is renamed/disabled) → both pass the SELECT → both INSERT → `uq_signature_matrices_name_status` (migration p9_010; ORM declaration `pcs-backend/app/models/deliverable.py:159`) rejects one with an **unhandled IntegrityError → 500**, instead of the reread-and-recover `_ensure_binding` performs for the binding row in the same flow. Note this is a **documented-risk match, not data corruption**: the unique constraint means the failure mode is a spurious 500 on one request, not two ACTIVE templates (that stronger symptom is blocked because `status` is non-NULL here, so the learning's `NULLS NOT DISTINCT` blind spot does not apply). Also mitigating: `ensure_change_notice_matrix` (same shape, earlier batch) means the new code copies an existing house pattern — this is drift from the *better* in-file precedent, not an outlier. p9_010's own downgrade docstring frames the DB constraint as the concurrency backstop, so the maintainers have already reasoned about this window once.

Suggested fix (defensible from the in-file precedent): wrap the `db.add(matrix)`/flush in the same try/except-IntegrityError → rollback-statement → re-SELECT pattern `_ensure_binding` uses at `signature_matrix_service.py:627`.

Severity if emitted as a finding: P2, confidence 75 (constraint verified in both p9_010 and ORM; absence of handler verified in the method body; consequence is a narrow-window 500).

---

## 2. Guard-test epistemics: the batch applies the learning — one residual weaker than the rest

**Matched rule** — `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`: *"内容相等 ≠ 派生"* (§1), *"凡是「证明 A 引用了 B」的断言，都不该用文本匹配"* (§2), *"判据要打在引擎保证上…不要打在渲染产物上"* (§3), *"mock 与契约一致是正确性的一部分"* (§4).

**Relevance — none (rule followed), with one changed-line hardening note.** Followed, verifiably:

- `pcs-backend/tests/architecture/test_frontend_state_machine_seed.py` asserts whole-object equality (`seed == backend`) against the live `get_state_machine()` — structural, not substring. Its skipif design explicitly splits "frontend package absent → skip" from "package present but seed file absent → fail", which is precisely the learning's silent-pass-guard trap (a renamed seed file would otherwise SKIP the module to exit 0 forever). The docstring names that trap.
- `pcs-frontend/src/mocks/seed/meta.ts` — hand-written 21-transition table deleted, replaced by `import rawStateMachine from "./meta.state-machine.json"` with an explicit "⚠️ 不要 cast" comment preserving `tsc --strict` as the type-level gate. This is §4's fix pattern, and the deleted hand-written seed is recorded (buglog/TODOS refs in the STATUS.md hunk) as the exact "mock masks a missing button" defect the learning describes.
- New seeds across `pcs-frontend/src/mocks/seed/*.ts` use `satisfies components['schemas'][...]` (AdminUserOut, DeliverableProgressResponse, RecordActionResponse, etc.) — the compile-time seed→contract assertion §4 recommends.

Hardening note (learning-derived, low severity — presence vs position): `pcs-backend/tests/alembic/test_p9_013_bind_default_record_matrix.py` (`test_backfill_only_touches_projects_without_record_binding`, `test_default_matrix_is_created_only_when_missing`) assert `"NOT EXISTS" in sql` and literal SQL substrings on the **evaluated** SQL string. Presence-of-substring proves the clause exists somewhere, not that it guards the right thing — if the NOT EXISTS drifted into the wrong clause (e.g. inside the `CROSS JOIN` subquery instead of the project-filtering WHERE), the test stays green. This is a weaker cousin of §2's defeat mode; the file's own docstring correctly explains why evaluated-SQL beats AST-on-f-string for the placeholders, so the observation is about assertion strength, not a wrong method. Suggested hardening: assert the NOT EXISTS subquery references `project_signature_matrix_bindings b` (it partially does) or parse the statement. P3 at most; report as advisory.

---

## 3. StaticPool commit-ness trap — rule carried into the batch's own STATUS; no violating test found

**Matched rule** — `docs/solutions/testing-issues/sqlite-staticpool-hides-uncommitted.md`: *"Session A inserts without committing; session B SELECT sees the row"*; derived rule: *"For any `if optional_payload:` branch, at least one test must assert the branch executes with the feature on."*

**Relevance — none (rule followed; note for synthesis).** The `.wolf/STATUS.md` hunk in this diff re-encodes the trap for the new tests ("in-memory SQLite 的 StaticPool 让 `db` 与独立 client 共用连接 ⇒ … 造完 fixture 先 `commit()`"), and no new test in the diff opens a second session to assert commit-ness (the shape the fixture voids). Did-fire coverage exists for the new optional surfaces: CSV export has `tests/lib/csv.test.ts`, `tests/pages/audit/AuditLogPage.export.test.tsx`, and e2e `audit_log.spec.ts`. Documented residual, not a violation: p9_013's SQL (`gen_random_uuid()`, `::jsonb`) is PG-only and **never executed by any test** — the ratchet test states this openly and defers to `alembic check` per database. That is the corpus's accepted posture, provided the manual per-DB gate actually runs before release (see §4).

---

## 4. Migration drift blind spot — ORM↔migration lockstep and derived constraint names both honored

**Matched rule** — `docs/solutions/database-issues/alembic-create-table-silently-drops-schema-elements.md`: *"Derive constraint names from `NAMING_CONVENTION`, not by hand"*; *"A real-DB check is the only reliable gate when tests build schema from ORM metadata"*; CONCEPTS.md「漂移盲区」: *"改任何 `alembic/versions/*` 时必须手动核对 ORM 列同步"*.

**Relevance — none (rule followed; note for synthesis).**

- `parent_deliverable_id`: migration p9_012 (`op.drop_column`) and the ORM column removal in `pcs-backend/app/models/deliverable.py` land in the same diff — no ORM↔migration divergence introduced. The replacement comment marks the absence and its reason (the healthy inverse of the learning's lying-comment pattern).
- p9_012's downgrade FK name `fk_deliverables_parent_deliverable_id_deliverables` is exactly `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s` — derived per the convention rule, not guessed.
- No `op.create_table` appears in the new migrations, so the silent-positional-argument-drop hazard is unreachable here.
- Residual (documented, manual): the per-database `alembic check` gates (`pcs` AND `pcs_test`, exit **255** semantics, `current` vs `heads` first) remain human-run — the new test file's docstring says so explicitly. Before this batch ships, someone must actually run them; a green in-memory suite carries no information about p9_013 executing on real Postgres.
- Buglog cross-check (bug-2041): p9_006's backfill failed on a fresh CI database because it queried via **ORM entities** (SELECT named columns that older schemas lack). p9_013's backfill is raw `op.execute` SQL with explicit column lists — it does not repeat that shape. The STATUS.md hunk carries the lesson forward ("CI 是活的（全新 Postgres）⇒ 改迁移必须在全新库上验"), so the fresh-DB CI run is the gate that would catch any p9_013 SQL error; keep it in the required verification for this batch.

---

## 5. Narrow declaration / silent fallback — no STATUS_META-style semantic rewrite in changed components

**Matched rule** — `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md`: *"`STATUS_META[status] ?? STATUS_META.DRAFT`：一个 ACTIVE 的管子等级在页面上显示「草稿」…缺失的值被填成某个默认值，而不是显式失败"*; *"fixture 只能用契约类型构造"*.

**Relevance — none (rule followed; note for synthesis).** Grepped the full diff for the semantic-fallback shape (`?? STATUS_META`, `?? META.`, dict-lookup-with-default): zero hits in the changed components (`WorkflowProgressPanel`, `RecordTimeline`, `RecordActions`, `DeliverableSignDialog`); the only `??` defaults are benign empty-arrays for query data. Fixtures/mocks use contract types via `satisfies` (§2 above). Where the backend degrades, it degrades loudly or explicitly: `resolve_project_matrix` raises 409 `SIGNATURE_MATRIX_NOT_ACTIVE` for a bound-but-inactive matrix (no silent swap to the builtin), and the dangling-binding → `None` → caller-422 path is a documented configuration-state choice, not a value rewrite. Nothing in the changed lines contradicts the rule.

---

## Summary table

| # | Learning doc | Classification | Violating line |
|---|---|---|---|
| 1 | dialect-options-invisible-on-sqlite (lock-free check-then-insert) | **changed line contradicting** | `pcs-backend/app/services/signature_matrix_service.py:790` (no IntegrityError-reread; sibling `_ensure_binding:627` has it) |
| 2 | guard-test-fooled-by-lying-comment | none (followed) + **changed line, advisory hardening** | `pcs-backend/tests/alembic/test_p9_013_bind_default_record_matrix.py` — substring-on-SQL asserts presence, not position |
| 3 | sqlite-staticpool-hides-uncommitted | none (followed; note) | — |
| 4 | alembic-create-table-silently-drops-schema-elements | none (followed; manual per-DB gate must actually run) | — |
| 5 | narrow-declaration-is-not-a-constraint | none (followed) | — |
| — | arq-028-worker-silent-failure-modes | out of scope (no worker code in diff) | — |

For synthesis: items 1 (P2) and 2 (P3 advisory) are the actionable candidates; items 3–5 are confirmations that documented risk postures held, plus the standing manual gates (per-DB `alembic check`, exit 255, `current` vs `heads` first) that this batch correctly *documents* but does not automate — release checklist material, not a code defect.
