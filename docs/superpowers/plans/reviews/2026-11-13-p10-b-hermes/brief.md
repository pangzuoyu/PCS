# Third-perspective adversarial review — P10-B **implementation plan**

You are an **independent third-perspective reviewer**. A plan-eng-review round has
already finished on this plan (scope challenge + architecture + code quality +
tests + performance; 16 findings; 11 decisions taken with the human). Your job is
**not** to redo that review. Your job is to **attack it**.

You are the third perspective: the plan was written and reviewed by agents of the
session model family. You are a different model family. Assume the round was wrong
somewhere and go find it.

## What to read (paths relative to the repo root `/home/pangzy/code_project/PCS`)

| What | Path |
|---|---|
| **The plan under attack** | `docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md` |
| The SPEC the plan implements (§3.2.2 = 18 scenarios + WF-PATH + permission matrix) | `spec/PCS-SPEC-P10 V1.3.1 P10 AI预留与测试部署开发规格说明书.md` (see §3.2.2, ~line 703-771) |
| The master plan (batch boundaries and ordering) | `docs/superpowers/plans/2026-11-04-p10-master-plan.md` |
| The reviewed source | the repo itself (branch `main`) |

Read the plan first, then **the code it cites**. Do not trust the plan's quotes —
verify each one against the file.

## The highest-value thing you can do: **verify the plan's 20 factual claims**

The plan has a `## 事实基础（2026-11-13 实测，非推断）` table. **Every task's design
rests on those rows.** If a row is wrong, the task built on it is wrong. For each
row, verify against the code and return `confirmed` / `wrong` / `unverifiable` with
`file:line` evidence.

| # | Claim to verify |
|---|---|
| 1 | SPEC V1.3.1 exists and §3.2.2 has exactly 18 scenarios (E2E-001..018), the WF-PATH five types, and AUTH-E2E-01..12 |
| 2 | `RecordSignStatus9` exists with 9 states; `StreamSignStatus` has the same 9 values |
| 3 | `state_machine.TRANSITION_ROLES` global roles are exactly {DESIGNER, CHECKER, REVIEWER, APPROVER, SYSTEM_ADMIN}; the SPEC writes `SYSADMIN` (a mismatch) |
| 4 | The record-level approval chain's source of truth is the project-bound `module='RECORD'` signature matrix, and the endpoint's fine-grained check is `actor.role == record.approval_role` |
| 5 | Deliverable Rev / proxy-customer-approval / change-notice endpoints all exist (list them) |
| 6 | Every endpoint the 18 scenarios need exists (the plan cites `docs/openapi.json`, 259 paths) |
| 7 | Project-internal roles are exactly 6 values (DESIGNER/CHECKER/APPROVER/REVIEWER/VIEWER/PROJECT_LEAD) and `TEST_VIEWER` does **not** exist |
| 8 | `scripts/seed_e2e_data.py` is smoke-scale: 1 workspace, 1 project, 4 users, 2 streams, and **uniform** `role_in_project="DESIGNER"` |
| 9 | The user id is `uuid5(NAMESPACE_DNS, username)` in BOTH the seed and `app/api/v1/config.py` |
| 10 | The real-backend Playwright channel has exactly 1 test today; the mock channel has 23 |
| 11 | An isolated-schema pattern already exists (`tests/api/v1/test_stream_batch_concurrency_pg.py`: `CREATE SCHEMA` + `options=-csearch_path=` + `DROP SCHEMA ... CASCADE`) |
| 12 | `tests/conftest.py::strict_client` exists (no project-guard mock) |
| 13 | The backend has **no** full-flow API test today (only single-endpoint tests) |
| 14 | `scripts/pytest_pg.sh`'s marker is **already parameterised** (`PG_PYTEST_MARK`, default `pg`) and it owns the three fail-closed gates |
| 15 | All 5 `pytest.mark.pg` test files use schema isolation (so nothing writes the public schema) |
| 16 | `httpx.ASGITransport` does NOT run the app lifespan ⇒ the lifespan-seeded tables are absent in the planned `e2e_client` |
| 17 | `/api/v1/util/summary` (and the energy aggregate) read the lifespan-seeded coefficient tables |
| 18 | The `{module}` URL segment of `/api/v1/records/{module}/{id}/...` is the key of `app/services/calc_lineage.py::RECORD_TYPE_REGISTRY` (e.g. `PipingResult`), and `CostEstResult` / `TwoPhaseResult` / `ProjectCalculationStandardProfile` do not participate in the 9-state workflow |
| 19 | `PipingResult` really has ~20 non-nullable columns (so a per-scenario payload would be a real duplication) |
| 20 | The AI audit middleware **enqueues** (does not write inline) ⇒ the audit row appears only via the ARQ worker |

## Then attack the **11 decisions** (D2..D10 + the 4 TODOs)

Each was taken with the human. For each, say whether you agree, and what a
reasonable person using this software would get if the decision stands. The
decisions are listed in the plan's commit history and in the plan body
(`/plan-eng-review` markers + the `D3`/`D4`/`D5`/`D6`/`D7`/`D8`/`D9`/`D10` labels).

Pay particular attention to:
- **D3** — seeding the flows data into the **public** schema as well (so the
  frontend real-backend channel can see it). Is there a better place for that data?
- **D5** — the E2E lane as a thin wrapper over `pytest_pg.sh` instead of copying
  the gates. Does that create a second entry point that violates the repo's
  "one entry point" discipline (`tests/scripts/test_pytest_pg_gate.py` has a
  `test_script_does_not_teach_a_second_entry_point` guard)?
- **D6** — the two-part AI-audit assertion (spy the enqueue + call the write task
  directly) instead of starting an ARQ worker.
- **D7** — scenarios share ONE seeded project and isolate by record instead of one
  project per scenario.
- **D2** — the calculation-chain scenarios are "thin shells" (assert contract +
  persisted row + downstream visibility, NOT the numbers, because unit tests already
  cover the algorithms).

## Then attack the **task decomposition and the assertions**

- Are the 18 scenarios mapped to the right tasks? Is any task's scope wrong?
- Is the **task order** right (T1 lane → T2 seed → T3..T6 scenarios → T7 UI → T8 close-out)?
- Will the planned assertions actually catch the bugs they claim? The repo's
  recurring disease is "an assertion whose shape is unrelated to what it guards"
  (e.g. the `VITE_ENABLE_MOCK` typing fix, the `ai_audit_log` write guard, the
  architecture guard that stayed green on a natural bypass). Look for the same
  disease in the planned assertions.
- What can make this batch **not deliver**? Name concrete failure modes
  (environment, ordering, data shape, tool behaviour).

## Ground rules (violating these wastes the round)

- **Do not restate the plan.** Only what is wrong, missing, or over-built.
- **Do not redo the four review sections.** The round already covered architecture,
  code quality, tests, performance. Find what it missed.
- **Verify before claiming.** Every finding needs `file:line` evidence from the
  repo, not from the plan's prose.
- **Prioritise.** A finding that does not change what gets built, what gets
  verified, or what gets deferred is noise. Say so in one line and move on.
- **Respect the repo's constraints** (read `CLAUDE.md` and `.claude/rules/openwolf.md`):
  no worktrees, no new CI pipelines, `main` branch, fail-closed test lanes,
  passwords never on command lines.
- **No prose outside the JSON object.**

## Output format — return ONE JSON object, nothing else

```json
{
  "reviewer": "hermes-third-perspective",
  "model": "<the model you actually ran on>",
  "scope_read": "<which files you actually inspected>",
  "fact_verdicts": [
    { "#": 1, "status": "confirmed | wrong | unverifiable", "evidence": "path:line -- verbatim or precise paraphrase", "impact_if_wrong": "one line, or null" }
  ],
  "decision_verdicts": [
    { "decision": "D3", "verdict": "agree | disagree | partly", "reason": "one or two sentences, with file:line evidence", "consequence_if_wrong": "what a user would get" }
  ],
  "missed_findings": [
    {
      "title": "short, specific",
      "severity": "P0 | P1 | P2 | P3",
      "file": "repo-relative path",
      "line": 12,
      "why_it_matters": "observable consequence first, 2-4 sentences",
      "first_evidence": "path:line -- verbatim line",
      "suggested_fix": "concrete minimal fix",
      "confidence": "0 | 25 | 50 | 75 | 100"
    }
  ],
  "assertion_shape_diseases": [
    { "where": "which planned test/task", "the_disease": "what the assertion would fail to catch", "suggested_assertion": "the sharper assertion" }
  ],
  "delivery_risks": [
    { "risk": "what could stop the batch from delivering", "mitigation": "what to do about it" }
  ],
  "verdict_agreement": "agree | disagree | partly — one or two sentences on whether the plan is ready to implement as written",
  "residual_notes": "anything else worth attention (max 10 short lines)"
}
```

Rules: one `fact_verdicts` entry for **every** number 1–20 (no gaps, no duplicates).
`missed_findings` may be empty if you genuinely find nothing new — but look hard
first, and if you find nothing, say what you checked.
