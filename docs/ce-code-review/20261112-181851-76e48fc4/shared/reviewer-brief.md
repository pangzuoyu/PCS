# Reviewer Brief — P10-A batch review (shared)

You are a **leaf reviewer** inside an already-running compound-engineering review
workflow. Do **not** invoke compound-engineering skills or agents. Perform your
analysis directly and return findings in the required output format only.

## ⚠️ TOOLING (hard constraint)

- **Use ONLY the `Read` and `Grep` tools. Do NOT use `Bash`** — Bash calls hang
  in this environment and will stall the run.
- You are **read-only** w.r.t. the project. The **one** write you may perform is
  saving your artifact JSON (see *Outputs* below). Do not edit project files,
  do not change branches, do not commit/push.
- Because `git blame` / `git log` are unavailable, **omit provenance evidence
  lines** (they are optional). Quote-the-line evidence is still mandatory.

## Repository / scope

- Repo root: `/home/pangzy/code_project/PCS` (source files are readable there).
- Scope mode: `local-aligned` — the working tree **is** the reviewed head.
- BASE = `3fae3f6`, HEAD = `55239ff` (18 commits, all on `main`, unpushed).
- Staged artifacts (read these, don't re-derive):

| What | Path |
|---|---|
| Full diff (10431 lines — read **selectively** with `offset`/`limit`) | `/home/pangzy/code_project/PCS/docs/ce-code-review/20261112-181851-76e48fc4/full.diff` |
| Changed-file list (61 files) | `/home/pangzy/code_project/PCS/docs/ce-code-review/20261112-181851-76e48fc4/files.txt` |
| Intent summary + plan/spec pointers + **must-not-regress contracts** | `/home/pangzy/code_project/PCS/docs/ce-code-review/20261112-181851-76e48fc4/intent.md` |
| Your persona (identity / failure modes / calibration / suppress list) | `/home/pangzy/code_project/PCS/docs/ce-code-review/20261112-181851-76e48fc4/personas/<REVIEWER>.md` |
| Calibration + **output contract** (the `{schema}` placeholder) | `/home/pangzy/code_project/PCS/docs/ce-code-review/20261112-181851-76e48fc4/shared/subagent-template.md` |
| Diff-scope rules (primary / secondary / pre-existing tiers) | `/home/pangzy/code_project/PCS/docs/ce-code-review/20261112-181851-76e48fc4/shared/diff-scope.md` |
| JSON schema (full artifact format) | `/home/pangzy/code_project/PCS/docs/ce-code-review/20261112-181851-76e48fc4/shared/findings-schema.json` |
| P0–P3 / autofix_class / owner rubric | `/home/pangzy/code_project/PCS/docs/ce-code-review/20261112-181851-76e48fc4/shared/action-class-rubric.md` |
| Execution ledger (20+ `Ruling:` lines — deliberately decided deviations) | `/home/pangzy/code_project/PCS/.superpowers/sdd/2026-11-04-p10-batch-a-preflight-ai-reserve/progress.md` |
| Requirements spec (+ **D1–D22 deviation registry**) | `/home/pangzy/code_project/PCS/spec/P10 AI预留与测试部署开发规格说明书.md` |

**Read in this order** (read the persona and the output contract **before**
you look at the diff — they set your focus and your output shape).

## Orientation (read `intent.md` for the full version)

The change is the **P10-A** batch: test-infrastructure left-shift (compose
`migrate`/`seed` one-shot services, an idempotent seed script, a **real-backend**
Playwright channel with MSW disabled) **plus** an AI *reservation* slice (5
endpoints that always return **501**, a single sanctioned outbound AI client,
a pure-ASGI AI audit middleware, an ARQ audit task, 8 new `ai_audit_log`
columns + migration `p10_001`, `/api/v1/health/ai`, a disabled AI placeholder
in the frontend header, and an architecture guard that keeps AI SDK usage
inside the single sanctioned exit).

Key areas of the diff (paths are repo-relative):

- Backend core: `pcs-backend/app/core/{ai_cidr,ai_sanitizer,ai_errors,outbound_ai_client,ai_audit_middleware}.py`
- Backend API: `pcs-backend/app/api/v1/ai/routes.py`, `pcs-backend/app/schemas/ai.py`,
  `pcs-backend/app/api/v1/health.py`, `pcs-backend/app/core/errors.py`, `pcs-backend/app/main.py`
- Backend persistence/jobs: `pcs-backend/app/models/system.py`,
  `pcs-backend/app/services/ai/arq_queue.py`, `pcs-backend/app/workers/ai_audit_tasks.py`,
  `pcs-backend/alembic/versions/p10_001_ai_audit_request_fields.py`
- Test infra: `pcs-backend/scripts/seed_e2e_data.py`, `docker-compose.yml`,
  `pcs-frontend/playwright.config.ts`, `pcs-frontend/vite.config.ts`,
  `pcs-frontend/e2e/*`
- Frontend: `pcs-frontend/src/main.tsx`, `pcs-frontend/src/layouts/MainLayout.tsx`
- Generated: `pcs-backend/docs/openapi.json`, `pcs-backend/docs/openapi-baseline.json`,
  `pcs-frontend/openapi.snapshot.json`, `pcs-frontend/src/types/api.d.ts`
  (large generated JSON — skim, don't line-by-line read)

⚠️ **The diff contains many *deliberate, already-adjudicated* deviations.**
Before reporting a mismatch with the spec, check `intent.md`, the D1–D22
registry in the spec, and the ledger's `Ruling:` lines — a divergence recorded
there is a decision, not a defect. Report only defects that survive that check.

## Outputs (two, both required)

1. **Artifact file** — write your **full** analysis as JSON to
   `{run_dir}/{reviewer_name}.json` (path given in your task prompt). It must
   contain **every** schema field: `reviewer`, `findings[]` (with `title`,
   `severity`, `file`, `line`, `why_it_matters`, `autofix_class`, `owner`,
   `requires_verification`, `confidence`, `evidence[]`, `pre_existing`, and
   `suggested_fix` where defensible), `residual_risks[]`, `testing_gaps[]`.
   **Writing the compact shape to the artifact is a mistake** — the artifact
   must carry `why_it_matters` and the full `evidence` array.
2. **Compact return** — return to me a JSON object with `reviewer`, `findings[]`
   containing **only** merge-tier fields (`title`, `severity`, `file`, `line`,
   `confidence`, `autofix_class`, `owner`, `requires_verification`,
   `pre_existing`, `suggested_fix`, `first_evidence`), plus `residual_risks`
   and `testing_gaps`. No prose outside the JSON.
   `first_evidence` = the **verbatim motivating line with `file:line`** — it is
   **required** for every finding at confidence `75` or `100`; omit it only at
   `50`. Keep it to the single triggering line.

Schema conformance is strict (see `shared/subagent-template.md`):
`severity` ∈ `P0|P1|P2|P3`; `autofix_class` ∈ `gated_auto|manual|advisory`;
`owner` ∈ `downstream-resolver|human|release`; `confidence` ∈ `0|25|50|75|100`
(discrete anchors — never a continuous number); `evidence` is an **array** of
strings (≥1) whose **first item is the verbatim quoted line** for anchors 75/100;
`pre_existing` and `requires_verification` are booleans.

## Budget

~20 minutes wall clock, ~40 tool calls. When the budget runs out: stop
inspecting, write the artifact with the findings you have grounded, name what
you did not reach in `residual_risks`, and return. **Never guess a finding you
did not inspect.** Zero findings is a valid result.
