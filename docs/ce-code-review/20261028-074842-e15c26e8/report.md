## Code Review Results

**Scope:** `346c696..751826f` on `main` (30 commits, standalone diff; untracked plan drafts and the P10 spec draft excluded)
**Intent:** P9B-2 batch: signing workflow + ADMIN frontend plus supporting backend. Backend: POST /projects auto-binds ACTIVE RECORD matrix; migrations p9_012 (drop dead column) + p9_013 (backfill default RECORD matrix); GET /deliverables/{id}/progress aggregate; GET /records/{module}/{id}/edits project-guarded; approval chain derived from project RECORD matrix (submit-approval `extra=forbid` breaking change); SignStepRequest + reason. Frontend: RecordActions with role gates, record drawer + comments + timeline, deliverable progress page + sign dialog, ADMIN user management + audit log (server pagination + CSV export), mock fidelity. Gates must be pre-positioned (role/matrix/reason => disable + reason), no silent degradation; plan RF-1..RF-16 are named acceptance criteria.
**Mode:** markdown report-only (no local apply)

**Reviewers:** correctness, project-standards, testing, maintainability, security, performance, api-contract, data-migration, adversarial, learnings-researcher, deployment-verification-agent
- correctness -- always-on session reviewer
- project-standards -- root CLAUDE.md criteria apply (instruction-file fallback; no CODING_STANDARDS.md/AGENTS.md in repo)
- testing -- 30 test files changed + behavior changes
- maintainability -- 6025 exec non-test lines, new api client layer + components
- security -- role gates, project guards, CSV export, secondary auth
- performance -- aggregate endpoint query shape, export fan-out
- api-contract -- new routes, `extra=forbid` breaking change, baseline roll
- data-migration -- p9_012 column drop + p9_013 backfill
- adversarial -- 6000+ exec lines, auth + persistence + silent-pass guard
- learnings-researcher -- docs/solutions corpus has plausible matches (alembic/SQLite/MSW)
- deployment-verification-agent -- destructive DDL + backfill migration artifacts

### Triage Groups

| Group | Findings | Context | Preferred Resolution | Why |
|-------|----------|---------|----------------------|-----|
| Record approval chain resolved from live matrix, not frozen at submit (decision-gate then apply-queue) | #1, #9 | Pending approval role is re-derived from the current project binding at every intermediate step (records_actions.py:512), so a mid-approval rebind changes who may sign after the one-time self-review check at submit has passed; the same resolver's new non-ACTIVE 409 branch ships untested | Decide the freeze mechanism first (#1: chain snapshot at submit mirroring deliverable_service.py:1105-1130, or a per-step submitter-identity re-assert), then write #9's 409 test against the settled shape | APPROVAL_SELF_REVIEW_FORBIDDEN is enforced exactly once, at submit; everything after trusts mutable configuration |
| POST /projects create-path guards (one small decision, then apply-queue) | #4, #5, #6 | The new create endpoint checks existence but not workspace type, uniqueness, or concurrent first-use of the default matrix | Settle the FORMAL-only policy in #4 (backend 422 WORKSPACE_NOT_FORMAL + listWorkspaces filter), then apply #5 (IntegrityError -> 409 at the flush) and #6 (savepoint + reread around the default-matrix INSERT, mirroring bind_to_project/_ensure_binding) mechanically | All three sit in the same 30-line create path; one review of the transaction covers all fixes |
| AuditLogPage pagination correctness (apply-queue) | #10, #8 | The applied-filter freeze happens inside loadAuditLogs, so pagination queries with un-applied edits, and this batch's new audit_id tiebreaker has no disjoint-pages test | Fix #10 first (only the 查询 handler sets appliedFilter; loadAuditLogs queries with the applied value), then add #8's ordering test, which also pins #10's behavior | Both concern the same list-loading path; the test written second should assert both the freeze and the stable ordering |

### P1 -- High

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 1 | `pcs-backend/app/api/v1/records_actions.py:512` | Mid-flight matrix rebind defeats APPROVAL_SELF_REVIEW_FORBIDDEN (CWE-863) | security | 75 |

- **#1** — A project lead can approve their own record after submission. The self-review prohibition is checked only once, at submit-approval (records_actions.py:406), against the matrix bound at that moment; when an intermediate step is approved, the pending role is re-derived from the LIVE project matrix (`_next_approval_role` -> `resolve_project_matrix` fresh), and `bind_to_project` allows rebinding a project's RECORD matrix at any time with no guard for in-flight IN_APPROVAL records (signature_matrices.py:299-301 just overwrites matrix_id). Attack: a lead submits while the chain is CHECKER->REVIEWER->APPROVER (self-check passes), rebinds to include their own role at the next step index, then signs the remaining steps themselves (the step gate at records_actions.py:479 only compares `record.approval_role != actor.role`). Deliverable signing already fixed this class by snapshotting steps on the version at issue time (`_steps_for_version`, deliverable_service.py:1127); the record-side chain has no equivalent. Fix: freeze the normalized steps (matrix_id + parsed steps) in a JSON column on the record at submit-approval and read that snapshot in `_next_approval_role`; or, if schema change must be avoided, re-assert the self-review rule at each approval step (403 when the approving actor is the submitter). Validation: confirmed (protected subject: authorization-authentication); incidence was not measured — a defect the code permits but no one showed to occur. Design call on freeze mechanism, then mechanical implementation.

### P2 -- Moderate

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 4 | `pcs-backend/app/api/v1/projects.py:87` | Project in PERSONAL workspace: 201 success notice, then every submit-approval 403s forever | project-standards, adversarial | 100 |
| 5 | `pcs-backend/app/api/v1/projects.py:99` | Duplicate project_no POST returns 500, not 409 | adversarial | 100 |
| 6 | `pcs-backend/app/services/signature_matrix_service.py:813` | First-project race: default-matrix insert 500s without fallback | learnings, adversarial | 100 |
| 8 | `pcs-backend/app/api/v1/audit.py:87` | Audit pagination tiebreaker fix shipped with no backend test | testing | 75 |
| 9 | `pcs-backend/app/services/signature_matrix_service.py:737` | resolve_project_matrix non-ACTIVE 409 branch has no test | testing | 75 |
| 10 | `pcs-frontend/src/pages/audit/AuditLogPage.tsx:133` | Pagination silently applies the un-applied audit filter | adversarial, maintainability | 75 |
| 11 | `pcs-frontend/src/pages/deliverables/DeliverableProgressPage.tsx:190` | Deliverable progress list error never cleared; table stays hidden after one failed fetch | correctness | 75 |

- **#4** — `create_project` only checks the workspace EXISTS, not that it is FORMAL, while every downstream signing action gates on `require_formal_project_workspace` (403 for non-FORMAL, _guard.py:95). The admin UI offers every workspace `GET /workspaces` returns (no type filter), and the frontend `listWorkspaces` comment claims 只取 FORMAL but filters nothing. Picking a PERSONAL workspace yields 201 plus the notice 已自动绑定记录级签署矩阵，可以提交批准了 — exactly the 「项目建好了但送不了审」 half-built state the endpoint docstring promises cannot happen. Fix: after `db.get(Workspace, ...)`, `if workspace.workspace_type != 'FORMAL': raise PcsError(code='WORKSPACE_NOT_FORMAL', status=422)` matching the existing gate; also filter listWorkspaces results client-side. Design call (is TEMPORARY also valid?), then mechanical. Validation: confirmed.
- **#5** — An admin who re-submits the create form after a timeout, or types an existing 项目编号 (the Field description itself says 全局唯一), gets an unhandled IntegrityError surfaced as a raw 500 — the missing-workspace case five lines up is carefully mapped to a typed 404, and no global IntegrityError handler exists in app/core or main.py. Fix: wrap the flush in `try/except IntegrityError -> rollback -> raise PcsError(code='PROJECT_NO_CONFLICT', status=409)`; test: two POSTs with the same project_no, second is 409. Validation: confirmed.
- **#6** — On the first two concurrent `POST /projects` on a DB with no ACTIVE `DEFAULT_RECORD_3_LEVEL` row (fresh install, or after the template is renamed/disabled), both transactions run `_get_or_create_default_record_matrix`, both SELECT-see nothing (READ COMMITTED), both INSERT, and the loser hits `uq_signature_matrices_name_status` (added by p9_010 specifically for this race) with an unhandled IntegrityError -> 500 and the whole project creation rolls back. The in-file siblings handle the identical race (`_ensure_binding` line 514 catches + rereads; bind_to_project's savepoint + reread); this method skips it. This is also a changed-line contradiction of the solutions corpus (docs/solutions/database-issues/dialect-options-invisible-on-sqlite.md, symptom 2). Fix: savepoint + reread around the INSERT — plain db.rollback() is unsafe because the caller's project INSERT shares the transaction; add a two-concurrent-create test. Validation: confirmed (protected subject: concurrency); incidence was not measured.
- **#8** — Commit 1fba41d added the `audit_id` tiebreaker to both list endpoints (the fix's own comment names the user-visible failure: identical-timestamp rows get unstable OFFSET pagination on Postgres, so CSV export can duplicate and drop rows), but changed no backend test file: test_pagination_limit_offset paginates without equal `occurred_at` rows and never asserts ordering/tie stability. If the tiebreaker is reverted or reordered, tests/test_audit_query.py stays green. Fix: seed ~5 rows with identical occurred_at, fetch two pages, assert disjoint + union = full set; mirror for the config-audit endpoint (audit.py:230). Validation: confirmed.
- **#9** — When a project's bound RECORD matrix goes non-ACTIVE (DRAFT/PENDING/OBSOLETE), submit-approval/approval-step promise a loud 409 `SIGNATURE_MATRIX_NOT_ACTIVE` (new branch this batch, reachable from both call sites records_actions.py:393 and :348) instead of a misleading 422. Repo-wide grep shows the only two SIGNATURE_MATRIX_NOT_ACTIVE assertions target bind_to_project and ensure_change_notice_matrix — not resolve_project_matrix. The branch can be broken or changed while the suite stays green. Fix: in test_record_approval_chain.py, bind a PENDING matrix, POST submit-approval, expect 409 + code. Validation: confirmed.
- **#10** — The page's own invariant (comment at lines 73-75: the table and CSV export use the filter frozen at the last 查询 click) is broken: `setAppliedFilter(auditFilter)` sits inside `loadAuditLogs`, which the page effect also invokes on every page/pageSize change. User edits the filter without clicking 查询 (hint shows), clicks page 2 — page 2 is fetched with the NEW filter while page 1 showed the OLD one, the hint vanishes as if applied, and a subsequent CSV export uses a filter the user never applied; the table mixes two result sets under one total. Fix: freeze only in the 查询 handler; `loadAuditLogs` queries with the already-applied value. Update AuditLogPage.export.test.tsx expectations.
- **#11** — One failed deliverables-list fetch permanently hides the table for as long as the page is mounted: listError is set in the catch, nothing ever resets it, and rendering is gated on `{!listError && <Table/>}` — every later successful refetch (page change, the automatic reload after a successful sign/issue) still populates items/total while the table stays unrendered. A user who signs a step successfully then sees a stale error with no table has no recovery except a full page reload. Fix: `setListError(null)` before the api.get call, same convention as AuditLogPage.tsx:86; test: fail first GET, succeed on reloadToken bump, assert table renders.

### P3 -- Low

| # | File | Issue | Reviewer | Confidence |
|---|------|-------|----------|------------|
| 12 | `docs/PCS-UI-SPEC.md:2340` | UI-SPEC revision table: V2.3 row glued into the V2.2 row | project-standards | 100 |
| 18 | `pcs-frontend/src/components/deliverables/DeliverableSignDialog.tsx:141` | Sign dialog keeps stale proxy credentials across reopen | correctness | 75 |

- **#12** — The V2.3 entry (the 2026-10-27 fix batch: any-step self-review criterion, matrix-not-bound UI branch, inline change-action demotion, reason-required fix) was appended to the end of the V2.2 row with no line break (`Claude CodeV2.3\t2026-10-27` mid-line), so the register jumps V2.2 -> V2.4 and grepping the table for V2.3 finds nothing. Anyone tracing the approval-chain contract history silently misses an entire revision. Fix: one newline before `V2.3\t2026-10-27`.
- **#18** — Reopening the proxy (代录) dialog pre-fills the previous submission's AD username/password and the previous issue description/purpose. The dialog's own discipline comment says every open resets prior state, but the open-effect only resets error/submitting/showReason/reason — `proxyForm` (including `secondary_password`) and the issue fields are never touched, and antd's `destroyOnHidden` does not unmount this state. An operator proxying approvals in a row can silently submit with the previous entry's credentials (Input.Password shows only dots). Fix: reset `proxyForm` to the initial literal, plus `purpose` and `description`, in the same open-effect.

### Requirements Completeness

Plan: `docs/PCS-PLAN-P9B-2-签署流程与ADMIN前端.md` (plan_source: inferred — auto-discovered, no plan: argument; contains no session-settled decisions). All 13 implementation units have corresponding work in the diff:

| Unit | Scope | Status | Evidence |
|------|-------|--------|----------|
| T-1 | POST /projects + default RECORD matrix bind + read bindings | met | 979119b (+ p9_013 backfill + 建项目入口 in 595384a, Batch F) |
| T-2 | Drop dead column `deliverables.parent_deliverable_id` (p9_012) | met | fc4c9e2 |
| T0 | Aggregate progress endpoint GET /deliverables/{id}/progress | met | f646b48 |
| T1 | Project-guarded edit audit read endpoint | met | c68bbf0 |
| T2 | Approval chain derived from project RECORD matrix (breaking change) | met | 678cc7b |
| T3 | Frontend api clients (4 groups) | met | 701d48e |
| T4 | RecordActions, meta-driven gates | met | bb123bb |
| T5 | Record drawer + comments + state timeline | met | 5852465 |
| T6 | Deliverable progress page + action timeline | met | 7fe7e29 |
| T7 | ADMIN user management + audit log (query + export) | met | 1a0097a |
| T8 | Deliverable-level sign write surface (issue / sign / proxy) | met | a293269 |
| T9 | TODO-067 deferred minors (7 items) | met | 012dd04, 6b0db55, d9c2548 (+ extended Batch B~E: 8a6d05a, e159926, 0459c95) |
| T10 | QA gate + closure | met | 478b547 (TODO-054/065/066/067 closed + buglog), d0e75cc STATUS; final-review fix batch d422ed3/1fba41d/33706d8/6b69797 |

RF-1..RF-16 (the plan's named acceptance criteria) all trace to landed work (gates pre-positioned: d422ed3, 5800a8b; state-machine seed + ratchet guard: f033a8f + 6b69797 pre-commit; export/401 fixes: 1fba41d; deferred minor fidelity: e159926, 0459c95). Residual RF-adjacent gaps are carried as findings: #1 qualifies RF-2's backend 403 backstop (defeatable by mid-flight rebind), #10 affects RF-11's export fidelity, #8 pins the audit pagination RF-11 depends on.

Reverse check (unrequested behavior rules): none found. The `extra=forbid` submit-approval contract change and matrix-derived chain are plan-mandated (R-17, open question 4b); the Batch B~F deferred-minor additions postdate the plan text but are remediation from the batch's own final-review loop and are SPEC-registered (V2.4, 5c1172a).

### Actionable Findings

| # | File | Issue | Route | Notes |
|---|------|-------|-------|-------|
| 1 | `pcs-backend/app/api/v1/records_actions.py:512` | Approval chain re-derived from live matrix defeats self-review ban | `manual -> downstream-resolver` | Confirmed (validation); incidence not measured; decide freeze mechanism (snapshot vs per-step submitter check) |
| 4 | `pcs-backend/app/api/v1/projects.py:87` | Create accepts non-FORMAL workspace -> dead-end project | `manual -> downstream-resolver` | Confirmed (validation); settle FORMAL-only policy, then mechanical |
| 5 | `pcs-backend/app/api/v1/projects.py:99` | Duplicate project_no -> raw 500 | `gated_auto -> downstream-resolver` | Confirmed (validation); `suggested_fix` present |
| 6 | `pcs-backend/app/services/signature_matrix_service.py:813` | Concurrent first-project default-matrix insert -> unhandled 500 | `gated_auto -> downstream-resolver` | Confirmed (validation); incidence not measured; `suggested_fix` present |
| 8 | `pcs-backend/app/api/v1/audit.py:87` | Tiebreaker fix untested (identical-timestamp pagination) | `gated_auto -> downstream-resolver` | Confirmed (validation); `suggested_fix` present |
| 9 | `pcs-backend/app/services/signature_matrix_service.py:737` | Non-ACTIVE bound matrix 409 branch untested | `gated_auto -> downstream-resolver` | Confirmed (validation); `suggested_fix` present |
| 10 | `pcs-frontend/src/pages/audit/AuditLogPage.tsx:133` | Pagination applies un-applied filter; export baseline drifts | `gated_auto -> downstream-resolver` | No verdict (cap tail); `suggested_fix` present |
| 11 | `pcs-frontend/src/pages/deliverables/DeliverableProgressPage.tsx:190` | List error never cleared; table stuck hidden | `gated_auto -> downstream-resolver` | No verdict (cap tail); `suggested_fix` present |
| 12 | `docs/PCS-UI-SPEC.md:2340` | V2.3 revision row glued into V2.2 row | `gated_auto -> downstream-resolver` | No verdict (cap tail); one-newline fix |
| 18 | `pcs-frontend/src/components/deliverables/DeliverableSignDialog.tsx:141` | Stale proxy credentials persist across dialog reopen | `gated_auto -> downstream-resolver` | No verdict (cap tail); `suggested_fix` present |

### Pre-existing Issues

| # | File | Issue | Reviewer |
|---|------|-------|----------|
| PE-1 | `pcs-backend/app/api/v1/deliverables.py:241` | Snapshot endpoint leaks enum class name in sign_status | api-contract |

- **PE-1** — GET /deliverables/{id}/versions/{rev}/snapshot returns sign_status as `DeliverableSignStatus.APPROVED` instead of `APPROVED` (`str()` on a `(str, enum.Enum)` member; no `__str__` override). Predates this batch (23c8c25, 2026-10-07), but this batch rolled a fresh openapi-baseline.json over the endpoint and corrected the identical pattern elsewhere in the same file (.value at :289 and :339) without fixing this one, so the newly frozen baseline documents a value that violates the documented vocabulary at runtime. Fix: `.value` at :241 + a snapshot sign_status assertion. Does not count toward the verdict.

### Learnings & Past Solutions

- [Known Pattern — followed] `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` — the state-machine seed test asserts whole-object equality against the live backend; seeds use `satisfies`-typed contract fixtures. One hardening note on the p9_013 test's substring asserts is carried under Testing gaps.
- [Known Pattern — followed] `docs/solutions/testing-issues/sqlite-staticpool-hides-uncommitted.md` — the STATUS.md hunk re-encodes the trap; did-fire coverage exists for CSV export; p9_013 PG-only SQL is never executed by tests (documented posture, gated by the manual per-DB alembic check).
- [Known Pattern — followed] `docs/solutions/database-issues/alembic-create-table-silently-drops-schema-elements.md` — p9_012 column drop and ORM removal land together; downgrade FK name derived per NAMING_CONVENTION; the manual per-DB alembic check (exit 255 semantics, current-vs-heads first) must actually run before release.
- [Known Pattern — followed] `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md` — no semantic-fallback shape in changed components; the resolver degrades loudly (409/422).
- [Out of scope] `docs/solutions/framework-integration-issues/arq-028-worker-silent-failure-modes.md` — no worker code in the diff.
- [Contradiction -> finding] `docs/solutions/database-issues/dialect-options-invisible-on-sqlite.md` symptom 2 (lock-free check-then-insert) is contradicted by `_get_or_create_default_record_matrix` — serialized as finding #6 above, citation preserved in its evidence.

### Deployment Notes

Verdict from the deployment-verification pass: GO, conditional on all blocking pre-deploy checks passing and backend + frontend shipping in the same maintenance window.

- Pre-deploy (read-only, per DB — pcs AND pcs_test): A) prove p9_012 safe to drop (0 rows / 0 non-null `parent_deliverable_id`; re-run the writers grep); B) count p9_013 blast radius in advance (unbound projects; exactly one ACTIVE `DEFAULT_RECORD_3_LEVEL` with 3 steps — a same-name non-ACTIVE row means STOP and get a ruling); C) `alembic current` == `heads` == p9_013 first, then `alembic check` exit 0 (255 = real drift = NO-GO; drive pcs_test via in-process `DATABASE_URL`, never `set_main_option`); D) CI green on 751826f (fresh-schema upgrade is the gate that would catch any p9_013 SQL error).
- Deploy-order coupling (blocking knowledge): there is NO compatible mixed state — old frontend + new backend 422s every submit-approval (`extra=forbid`), new frontend + old backend 422s too. Migrations + backend + rebuilt frontend in one window; serve index.html no-cache and announce a hard reload (stale bundles extend the 422 window). Never roll back only one side.
- Rollback: p9_012 drop is irreversible (accepted: 0 data, 0 writers); p9_013's downgrade deletes ALL RECORD bindings pointing at the default ACTIVE matrix — backfilled AND runtime-created post-upgrade bindings (broader than its docstring says); re-running `upgrade head` heals fully, at the cost of a 422 `RECORD_APPROVAL_MATRIX_NOT_BOUND` outage window. No code-only rollback exists (old ORM vs migrated DB 500s) — prefer roll-forward.
- First-24h monitoring: 4xx rate on `/records/*/submit-approval` (stale-bundle spike decaying to ~0); `RECORD_APPROVAL_MATRIX_NOT_BOUND` in logs should be 0; `UndefinedColumn` mentioning `parent_deliverable_id` = code/migration skew; occasional 403 `APPROVAL_SELF_REVIEW_FORBIDDEN` is intended new behavior (brief support/users); binding growth should track project creation.

### Coverage

**Cross-model peer (verbatim):** "Cross-model independent adversarial review: not run — no different-provider CLI installed on this machine (only the claude CLI, same serving family as the host); the adversarial lens ran in-process instead."

**Validator (Stage 5b):** one batch of 8 findings (#1, #2, #3, #4, #5, #6, #8, #9), ordered by severity and stable #; verdicts landed within the bound. Outcome: 6 confirmed (#1, #4, #5, #6, #8, #9), 2 rejected (#2, #3), 0 unresolved, 0 malformed, 0 failed, 0 shortcut-skipped. The 4 remaining actionable findings (#10, #11, #12, #18) are a cap tail with no verdict — not validation-degraded. No protected-subject reclassification was needed.
- Rejected #2 (Two simultaneous signers erase one signature; protected subject concurrency): short-hash provenance — `git show 346c696:pcs-backend/app/services/deliverable_service.py` already contains `async def sign_step` (line 694) with the identical unlocked read-modify-write of signature_summary_json, and this batch's hunks only add the reason parameter/entry. Citation independently confirmed by read-only inspection (this report leaf): sign_step at :694 in the base, batch diff touches no `signature_summary_json` write line. Real defect, pre-existing and unaffected by this batch — worth tracking separately, out of scope here.
- Rejected #3 (Secondary auth accepts any AD credential; protected subject authorization-authentication): short-hash provenance — the LDAP bind and unchecked `secondary_username` forwarding were introduced in 77d2e78 (feat(P9A)), an ancestor of base 346c696; this batch's deliverables.py changes only add the role gate and workspace guard. Citation independently confirmed: 77d2e78 exists, is an ancestor, added secondary_auth.py (76 lines); the batch diff does not touch secondary_auth.py. Real defect, pre-existing — worth tracking separately, out of scope here.

**Run mechanics and coverage sentences (all 19, verbatim):**
- Cross-model independent adversarial review: not run — no different-provider CLI installed on this machine (only the claude CLI, same serving family as the host); the adversarial lens ran in-process instead.
- Standards criteria came from the instruction-file fallback: repo root CLAUDE.md (no CODING_STANDARDS.md or AGENTS.md exists in this repo).
- Untracked files excluded from scope: five docs/superpowers/plans/2026-09-30-* plan drafts and spec/PCS-SPEC-P10*.md (untracked spec draft).
- Dispatch degraded to serial single-agent redispatch: the initial 11-agent concurrent batch and a 6-agent retry each exhausted the account 5-hour API quota (429 code 1308); all 11 reviewers were ultimately collected via small serial batches. All artifacts landed; only wall-clock suffered.
- A read-only file-presence monitor agent (statusboard) ran alongside; it reviewed no code.
- Reviewer generational suffixes (-r3/-r4) in agent names are retry artifacts; each artifact's internal reviewer field is canonical.
- 25 candidates entered the merge (24 persona findings + 1 learnings-serialized solutions-corpus contradiction); the first mechanical pass produced 23 primary / 1 pre-existing / 1 suppressed; semantic reconciliation merged 3 pairs (workspace_type, default-matrix race, audit-filter freeze) and the final pass settled 20 primary / 1 pre-existing / 1 suppressed, 0 malformed, exact-fingerprint duplicates 0.
- Every compact reviewer return omitted first_evidence (null) and the helper's evidence[0] backfill did not trigger, so synthesis recovered 24 quotes verbatim from the per-reviewer artifacts' evidence[0] (23 at anchor 75/100, 1 at anchor 50) before validation; the helper reports first_evidence_backfilled = 0 and quote-gate demotions at 75/100 = 0 (anchor-50 entry was quote-recovered to escape the malformed partition and was then confidence-suppressed, not quote-demoted).
- Mode-aware demotion count: 8 (7 single-reviewer P2/P3 advisories from maintainability/adversarial routed to residual_risks, 1 testing-origin P3 routed to testing_gaps); 1 suppressed candidate (P3 anchor 50) was routed to residual_risks and no other suppressed candidate remained to discard.
- suppressed_by_confidence: 1 finding at anchor 50; 0 at other anchors.
- The learnings-researcher found one changed-line contradiction of the solutions corpus (dialect-options-invisible-on-sqlite.md symptom 2, lock-free check-then-insert); it was serialized as an anchor-100 learnings finding and merged into primary #6 with the citation preserved in its evidence. No Compound Packs were configured (roster.packs empty).
- Plan was discovered as inferred (docs/PCS-PLAN-P9B-2-签署流程与ADMIN前端.md); it contains no session-settled decisions (settled_decisions empty, no session-settled markers in the document), so settlement reconciliation discarded 0 findings.
- Intent summary confidence is inferred.
- Validator shortcut-skips: 0 of 12 selected findings (basis: the cross-model peer did not run, and all in-process reviewers share one serving model, so no finding carries an adversarial-<provider> artifact with independence_verified:true).
- Validator batch: 8 findings (#1, #2, #3, #4, #5, #6, #8, #9) ordered by severity and stable #; the normal cap applied with no P0/P1 overflow (3 P1s fit inside the cap); the 4 remaining actionable P2/P3 findings (#10, #11, #12, #18) stay primary without a verdict - a cap tail, not a validation-degraded status.
- Failed or timed-out reviewers: none. Fast pass: no preliminary findings were emitted.
- No claim was rejected outright during admission; every dropped-from-primary item is recorded in residual_risks or testing_gaps above with its reason.
- No local apply was authorized (mode.apply_local false): Stage 5c did not run and the tree is untouched.
- Soft-bucket dedup: 5 persona-supplied testing gaps were dropped as restatements of primary/pre-existing fix asks or of kept residual risks; 1 chainCache residual merged across two reviewers; 1 p9_013 assertion-strength gap merged across two reviewers.

**Residual risks (advisory, not findings):**
- correctness + maintainability — RecordActions.tsx:149 `chainCache` is a module-level Map that is only written, never invalidated: after an admin binds/rebinds a project's RECORD matrix, an already-mounted SPA keeps the stale unbound/bound verdict (提交批准 stays disabled, or the self-review gate uses old roles) until a full page reload. Deliberate N+1-avoidance tradeoff that contradicts the component's own 门禁前置 goal.
- correctness — CommentPanel.send() appends the new comment to whichever page is currently viewed: posting while on a non-last page renders the comment on the wrong page (cosmetic only; backend order stays correct).
- correctness — MSW snapshot handler always returns the seed rev-B snapshot regardless of the :rev path param (dev-only fidelity gap; real backend keys on rev).
- correctness — Frontend gates consume the singular `role` from auth state; verification was grep-only — if the token ever carries multiple roles, these gates diverge from backend checks that use `actor.roles`.
- project-standards — Downgrade paths of the two new migrations were never exercised on a live schema (test_p9_013 asserts SQL shape only). p9_012's downgrade re-adds the column with an FK name derived from the convention — if the original create-table constraint name differed, a downgraded-then-upgraded DB drifts by constraint name.
- project-standards — CLAUDE.md 知识库 asks that new solutions be written back to docs/solutions/; this 30-commit batch added none — the durable lessons currently live only in code comments, TODOS.md and local-only .gstack QA reports.
- testing — Backend tests run against in-memory SQLite, not the Postgres the audit OFFSET-pagination comment targets; cross-engine ordering guarantees are only truly exercised on Postgres (repo-known trap: a wrong migration stays green on SQLite).
- testing — Coverage-by-absence claims (untested branches) were established with repo-wide text grep plus full reads of the relevant test files; a test exercising a branch without asserting its error code could have been missed.
- maintainability — deliverable_service.py grew 1298->1420 lines and mocks/handlers.ts 1003->1029; both were already past the 800-line ceiling before this diff, and the per-batch growth keeps accruing extraction debt nobody has scheduled.
- maintainability — Two label vocabularies now describe the same workflow-type set (WORKFLOW_TABS vs SECTION_LABELS); adding a workflow type requires updating both, and their label texts already diverge ('签署' vs '签署进度').
- security — require_formal_project_workspace is deliberately fail-open for projects with no workspace metadata (documented TODO-076, _guard.py:110-117); an unattached legacy project skips the workspace tier of the sign-flow gates.
- security — Mock login routes are claimed production-guarded (secondary_auth.py docstring; app/main.py not independently inspected) — if that guard regresses, the secondary-auth LDAP bind is the only remaining check on proxy recording (compounds with rejected pre-existing #3 above).
- performance — AuditLogPage.tsx:181-183 comment still claims the audit endpoints order 'occurred_at DESC 无 tiebreaker' though this batch added audit_id tiebreakers; the stale comment will mislead future maintainers about why the export row-count check exists.
- api-contract — GET /deliverables?sign_status=... accepts an arbitrary string (raw == compare against the PG native enum column); invalid values are not mapped to 422. Pre-existing and unchanged this batch; exact failure mode not run, so recorded rather than emitted.
- api-contract — New workflow business error codes (422 RECORD_APPROVAL_MATRIX_NOT_BOUND / RECORD_MODULE_UNKNOWN, 403 APPROVAL_SELF_REVIEW_FORBIDDEN / APPROVAL_ROLE_MISMATCH, 409 SIGN_STEP_OUT_OF_ORDER / RECORD_INVALID_TRANSITION) are not declared via responses= in OpenAPI — family-consistent and the frontend parses the envelope generically, but contract consumers cannot discover them from the baseline.
- api-contract — MSW mock for GET /records/:module/:record_id/edits ignores limit/offset (signFlow.ts:276-285) while the same batch fixed the audit-logs mock to honor pagination; no observable drift today, but a future paginated UI would silently show the unpaginated seed in dev.
- api-contract — StateTransition name collision (meta.py:92 pydantic model vs enums.py:267 enum) is real but confined to separate modules; already registered as plan constraint #1 — no runtime contract impact.
- data-migration — p9_013's _CREATE_BINDINGS INSERT has never inserted an actual row on any real database (0 projects everywhere); the backfill's row-producing path runs for the first time on the first project-bearing database this migration meets.
- data-migration — p9_013's downgrade deletes ALL module='RECORD' bindings whose matrix_id is the default ACTIVE matrix — including runtime-created and admin-made binds, broader than the docstring's 删掉回填的绑定.
- data-migration — pcs-backend/docs/schema_compact_orm.md:73 still lists deliverables.parent_deliverable_id after the p9_012 drop (symptom of pre-existing doc drift).
- adversarial — approval-step / submit-approval under concurrent double-submit converge on the scalar columns but write duplicate APPROVAL_STEP_PASSED / RECORD_TRANSITION audit rows (no row lock); lesser sibling of the rejected pre-existing sign_step lost-update.
- adversarial — e2e specs were not adversarially reviewed this run (budget); mock approval-step is fully static, so no e2e exercises the terminal state of the record approval chain.
- adversarial — Mock sign-step enforces order but not sign_role / can_self_check / can_skip despite its 语义照抄后端 header — the 403 role-mismatch and 409 skip-forbidden branches cannot be reproduced in dev.
- adversarial — Audit export loop verified safe against the partial-file scenario: downloadCsv runs only after the loop completes; a mid-loop 401 redirects via the code-gated interceptor as intended.
- Stage-5 demotions retained here: #7 errorText copy-pasted in two components while a central formatter (describePcsError) was added the same batch (unify in api/errors.ts; the shared formatter then needs direct unit tests); #13 ProjectCreate docstring contradicts its own client-settable fields (reword); #14 MOCK_PROJECT_ID dead export; #15 dead invisible text node in UserAdminPage; #16 record_edits imports private _load_record across API modules; #17 empty steps_json matrix would 500 at submit (API enforces min 1 step, so not creatable via API — defense-in-depth); #20 new `as never` casts defeat generated-type checking (widen prop types); unnumbered — reason-modal action error renders behind the still-open modal mask.

**Testing gaps:**
- No test asserts EXPORT_PAGE_SIZE (200) stays within the backend /audit-logs `le=200` cap — a future cap reduction breaks CSV export only against the real backend.
- test_project_creation.py only ever constructs a FORMAL workspace; no negative test for POST /projects with a PERSONAL/TEMPORARY workspace — exactly the hole finding #4 slipped through.
- GET /projects/{project_id}/signature-matrices (new read endpoint) has no test for the cross-project guard (check_project_access_or_404) — the sibling write endpoint's guard is tested.
- ensure_default_record_matrix's dangling-binding repair branch (binding exists, matrix deleted -> rebind default) is new and untested; only the healthy-binding path is covered.
- POST /projects OpenAPI description promises full-transaction atomicity (建行 + 绑矩阵 + 建模板, any failure rolls back); no test injects a mid-transaction failure.
- No negative test documents behavior for GET /deliverables?sign_status=<invalid value>.
- test_p9_013_bind_default_record_matrix.py never executes the migration against any engine (imports the module, asserts rendered SQL strings); a future column rename would pass every unit test and only surface in CI's fresh-schema upgrade.
- No concurrency test anywhere in test_deliverable_sign_step.py (30 tests) or test_record_approval_chain.py (9 tests) for two simultaneous signers/approvers.
- handlers.test.ts 新端点的 handler 都注册了 ratchet lists only 9 of ~17 signFlow endpoints, and for issue/sign-step/proxy it Ajv-validates test-authored literals rather than actual handler output — response-shape drift in those handlers keeps the suite green.
- Mock submit-approval returns depth 2 while the backend default RECORD matrix is depth 3 — dev UI shows 'Step 1/2' against a system that will really run 3; nothing pins the mock depth to SignatureMatrixService.DEFAULT_RECORD_STEPS.
- Nothing pins the meta handler's served shape beyond seed equality — if handlers.ts:992 ever serializes through a different transform, the pytest guard stays green.
- p9_013 test asserts literal substrings ("NOT EXISTS" in sql) — presence-of-substring proves the clause exists somewhere, not that it guards the right relation; harden by asserting the NOT EXISTS subquery references project_signature_matrix_bindings (learning: docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md §2).
- Stage-5 demotion retained here: #19 resetMockSignState resets only sign state, not comments/admin seed — the next test exercising admin disable or comment POST inherits earlier tests' mutations (order-dependent flake).

**Removable surface:** ~28 lines / 3 files across residual-risk items #7 (errorText dedup), #14 (1 line), #15 (3 lines) — dead-weight signal only, not a reduction target.

---

> **Verdict:** Ready with fixes
>
> **Reasoning:** One confirmed P1 remains open: #1, the mid-flight matrix rebind that defeats the record self-review prohibition (validator-confirmed on a protected subject; incidence unmeasured). An open P1 caps the verdict at Ready with fixes. The create-path guard group (#4/#5/#6) and the audit pagination pair (#10/#8) are confirmed-or-clear P2s worth fixing in the same pass. All 13 plan implementation units landed; requirements completeness is clean, and the destructive-migration batch ships with a credible Go/No-Go checklist whose deploy-order coupling (backend + frontend in one window) must be honored. Rejected findings #2 (sign_step lost update) and #3 (secondary auth accepts any AD credential) are real but pre-existing per verified provenance — track them separately; they do not block this batch.
>
> **Fix order:** #1 (decide freeze mechanism, then implement) -> #4 then #5 + #6 (one transaction review covers all three) -> #10 then #8 (same list-loading path; second test pins both) -> #9 -> #11 -> #18 -> #12.

**Actionable recap (self-sufficient):**

| # | Sev | Where | What | Response |
|---|-----|-------|------|----------|
| 1 | P1 | `records_actions.py:512` | Approval chain re-derived from live matrix; rebind lets submitter self-approve remaining steps | manual design call (snapshot at submit vs per-step submitter check), then fix — validator-confirmed |
| 4 | P2 | `projects.py:87` | Create accepts non-FORMAL workspace -> project can never enter approval | settle FORMAL-only policy, backend 422 + frontend filter — validator-confirmed |
| 5 | P2 | `projects.py:99` | Duplicate project_no -> raw 500 | map IntegrityError to 409 + test — validator-confirmed |
| 6 | P2 | `signature_matrix_service.py:813` | Concurrent first-project default-matrix insert -> unhandled 500 | savepoint + reread like sibling _ensure_binding + test — validator-confirmed |
| 8 | P2 | `audit.py:87` | Tiebreaker fix shipped untested | identical-occurred_at disjoint-pages test — validator-confirmed |
| 9 | P2 | `signature_matrix_service.py:737` | Non-ACTIVE bound matrix 409 branch untested | red-first 409 SIGNATURE_MATRIX_NOT_ACTIVE test — validator-confirmed |
| 10 | P2 | `AuditLogPage.tsx:133` | Pagination applies un-applied filter; export baseline drifts | freeze appliedFilter only in 查询 handler |
| 11 | P2 | `DeliverableProgressPage.tsx:190` | List error never cleared; table stuck hidden after one failed fetch | setListError(null) per load + recovery test |
| 12 | P3 | `PCS-UI-SPEC.md:2340` | V2.3 revision row glued into V2.2 row | one newline |
| 18 | P3 | `DeliverableSignDialog.tsx:141` | Stale proxy credentials persist across reopen | reset proxyForm/purpose/description in open-effect |

Report artifact: `/tmp/compound-engineering-1000/ce-code-review/20261028-074842-e15c26e8/report.md`
