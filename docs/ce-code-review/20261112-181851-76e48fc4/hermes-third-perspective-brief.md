# Third-perspective adversarial review — P10-A

You are an **independent third-perspective reviewer**. A review round has already
finished on this batch (11 reviewer lenses, a merge pass, and a validator pass).
Your job is **not** to redo that review. Your job is to **attack it**.

You are the third perspective: the code was read by lenses running on the
session model family, and the merge/validation was done by another agent of the
same family. You are a different model family. Assume the round was wrong in
somewhere and go find it.

## What to read (all paths relative to the repo root `/home/pangzy/code_project/PCS`)

| What | Path |
|---|---|
| **The report under attack** | `docs/ce-code-review/20261112-181851-76e48fc4/report.md` |
| Merged findings (27 primary + pre-existing + residual risks + testing gaps) | `docs/ce-code-review/20261112-181851-76e48fc4/synthesized-findings.json` |
| Validator verdicts (23 selected findings: 22 confirmed, 1 rejected) | `docs/ce-code-review/20261112-181851-76e48fc4/validator-verdicts.json` |
| Every compact reviewer return | `docs/ce-code-review/20261112-181851-76e48fc4/raw-returns.json` |
| The reviewed diff | `docs/ce-code-review/20261112-181851-76e48fc4/full.diff` (large — read selectively) |
| Changed-file list | `docs/ce-code-review/20261112-181851-76e48fc4/files.txt` |
| Intent summary, plan/spec pointers, must-not-regress contracts | `docs/ce-code-review/20261112-181851-76e48fc4/intent.md` |
| The corpus research that fed the round | `docs/ce-code-review/20261112-181851-76e48fc4/learnings-researcher.md` |
| The reviewed source | the repo itself (BASE `3fae3f6`, HEAD `55239ff`, branch `main`) |

Read the report first, then the code it cites. **Do not trust the report's
quotes — verify each one against the file.**

## Ground rules (violating these wastes the round)

- **READ-ONLY.** Do not edit, create, or delete any file in the repo. Do not run
  `git` commands that mutate state (no checkout / commit / stash / reset). Do
  not run the test suite, migrations, docker, or the seed script. Read and
  search only.
- The repo's own OpenWolf rules (`.claude/rules/openwolf.md`) and
  `CLAUDE.md` are context, not tasks. Do not update `.wolf/*`, do not log bugs,
  do not touch TODOS.md. This is a read-only opinion pass.
- **The batch's deviation registry is adjudicated.** `spec/P10 AI预留与测试部署开发规格说明书.md`
  part 5 lists **D1–D22** — deliberate, already-ruled divergences between the
  SPEC and the repository as it is. The execution ledger
  (`.superpowers/sdd/2026-11-04-p10-batch-a-preflight-ai-reserve/progress.md`)
  records the `Ruling:` lines. **A divergence registered there is a decision,
  not a defect** — do not report it. If you believe a registered deviation is
  nevertheless wrong, say so explicitly and name the D-entry you are overruling
  and why.
- The reviewed batch's own must-not-regress contracts (R1–R9, listed in
  `intent.md`) are the ground truth for what "correct" means here.
- Report only defects you can quote. A finding needs the verbatim line that
  makes it true (`file:line`).

## Your three jobs

### 1. Attack the retained findings (findings #1–#27 in the report)

For **each** of the 27 numbered findings, decide:

- `confirmed` — you inspected the code and the defect is really there and
  really matters as described.
- `rejected` — the cited code does not show it, the surrounding code already
  handles it, it predates and is unaffected by this diff, or it is only an
  unsupported preference. Quote what refutes it.
- `unresolved` — you could not get the evidence either way in your budget. Say
  what is missing.

Also flag **`overclaimed`** findings: real but materially less severe than the
report says (state the severity you would use), and **`severity-ok`** ones you
agree with.

### 2. Find what the round MISSED

Read the diff and the touched code with fresh eyes and look for real defects
that none of the 11 lenses reported. This is the highest-value part of your
job. Prioritise:

- the AI audit chain (middleware → ARQ → worker → `ai_audit_log`): loss,
  duplication, mis-attribution, ordering, idempotency, silent-drop paths;
- the seed script and the compose test profile: destructive behaviour, wrong
  database, non-idempotency, unexecuted guards;
- the real-backend E2E channel and the Playwright/vite configuration: a path
  that can pass green while the real thing is red;
- the OpenAPI contract, the generated artifacts (`openapi.json`,
  `openapi.snapshot.json`, `src/types/api.d.ts`), and the frontend consumer:
  drift between code and published contract;
- the migration `p10_001` vs the ORM `AiAuditLog`: column/index/predicate drift,
  deploy-window behaviour, rollback;
- anything that only shows on **real Postgres** (SQLite is the default test
  lane and hides dialect differences);
- anything that only shows at **runtime** rather than in a unit test.

### 3. Check the round's own reasoning

- Did the merge drop or over-promote anything? (Compare `raw-returns.json`
  against the report's numbered findings — a finding that three lenses
  reported but that vanished from the report is a merge bug.)
- Is the verdict ("Ready with fixes") justified by the evidence?

## Output format — return ONE JSON object, nothing else

```json
{
  "reviewer": "hermes-third-perspective",
  "model": "<the model you actually ran on>",
  "scope_read": "<which files you actually inspected>",
  "verdicts": [
    { "#": 1, "status": "confirmed | rejected | unresolved", "reason": "one or two sentences, with file:line evidence" }
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
  "overclaimed": [
    { "#": 12, "suggested_severity": "P2", "reason": "why the report's severity is too high" }
  ],
  "merge_issues": [
    "findings reported by lenses but missing from the report, or severity changes that look unearned"
  ],
  "verdict_agreement": "agree | disagree | partly — one or two sentences on the 'Ready with fixes' verdict",
  "residual_notes": "anything else worth the round's attention (max 10 short lines)"
}
```

Rules: one `verdicts` entry for **every** number 1–27 (no gaps, no duplicates).
`missed_findings` may be empty if you genuinely find nothing new — but look
hard first, and if you find nothing, say what you checked. No prose outside the
JSON object.
