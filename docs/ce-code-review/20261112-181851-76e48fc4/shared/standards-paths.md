# Standards paths (Stage 3b) — criteria files that govern this diff

Apply these criteria files **rule by rule** against the changed files they
govern. Cite the rule (file + section) for every finding. Do not invent
standards beyond these files.

## 1. `/home/pangzy/code_project/PCS/CLAUDE.md` — governs **every** changed file in the repo

Highest-value rules for this diff (read the file for the full text):

- **分层约束** — `core` must not import from `api`/`models`; `services` must not import from `api`. (The new `app/core/ai_*.py`, `app/services/ai/*`, `app/api/v1/ai/*` are exactly where this bites.)
- **迁移漂移盲区** — changing `alembic/versions/*` requires the ORM columns to be manually reconciled; SQLite unit tests do **not** enforce VARCHAR length, Postgres does.
- **发布前检查** — `alembic check` on **both** DBs (`pcs` / `pcs_test`) in **separate processes** (alembic `settings` is a cached pydantic instance ⇒ a second DB in the same process silently reuses the first); exit code is **255**, not 1; "no output" ≠ "consistent"; `op.create_index` must carry `if_not_exists=True`; partial unique index + `ON CONFLICT` requires `index_where`.
- **物流面项目守卫** — project-level access guards; 404 shape for single-object endpoints; **project authorization rows** are required for access to work.
- **测试前检查** — unit tests run in-memory SQLite built from ORM metadata (not from migration artifacts); `pcs_test` exists but is not the unit-test DB.
- **前端 UI 规范** — the frontend UI is governed by `docs/PCS-UI-SPEC.md` (see §2); fields/enums/permissions/error codes come from OpenAPI + meta API; on conflict with the SPEC, OpenAPI wins and the SPEC revision is registered.
- **Per-Batch QA Gate** — each sprint batch ends with a browser regression; `.gstack/` is gitignored; **do not** use `git checkout <commit> --detach`.
- **口径要求** — no hardcoded secrets; no `console.log`; errors handled explicitly; immutable patterns; functions <50 lines; files <800 lines; no deep nesting; no mutation; 80% coverage expectation for new functionality.

## 2. `/home/pangzy/code_project/PCS/docs/PCS-UI-SPEC.md` — governs the **frontend** changes

Changed files it governs: `pcs-frontend/src/layouts/MainLayout.tsx` (the AI placeholder button), `pcs-frontend/src/main.tsx` (mock gating), `pcs-frontend/src/types/api.d.ts`, `pcs-frontend/e2e/fixtures.ts`, `pcs-frontend/e2e/real_backend_smoke.spec.ts`, `pcs-frontend/playwright.config.ts`, `pcs-frontend/vite.config.ts`, `pcs-frontend/package.json`.

The SPEC is **V1.0 frozen**; it is the sole encoding basis for frontend UI. Check the AI placeholder against the SPEC's interaction/disabled/tooltip conventions, and check that any new API field/enum used by the frontend matches the OpenAPI contract rather than the SPEC.

## 3. `/home/pangzy/code_project/PCS/spec/P10 AI预留与测试部署开发规格说明书.md` — governs the **whole AI reservation slice** and the test-infrastructure slice

Changed files it governs: `pcs-backend/app/core/ai_cidr.py`, `ai_sanitizer.py`, `ai_errors.py`, `outbound_ai_client.py`, `ai_audit_middleware.py`, `pcs-backend/app/api/v1/ai/routes.py`, `pcs-backend/app/schemas/ai.py`, `pcs-backend/app/api/v1/health.py`, `pcs-backend/app/core/errors.py`, `pcs-backend/app/core/config.py`, `pcs-backend/app/main.py`, `pcs-backend/app/models/system.py`, `pcs-backend/app/services/ai/arq_queue.py`, `pcs-backend/app/workers/ai_audit_tasks.py`, `pcs-backend/app/workers/worker.py`, `pcs-backend/alembic/versions/p10_001_ai_audit_request_fields.py`, `pcs-backend/scripts/seed_e2e_data.py`, `pcs-backend/scripts/check_migration_idempotency.py`, `docker-compose.yml`, `pcs-frontend/src/layouts/MainLayout.tsx`.

⚠️ **Read the SPEC's 第五部分「与仓库现状的偏离登记」(D1–D22) BEFORE reporting any spec mismatch.** Each D-entry records a deliberate, already-adjudicated divergence between the SPEC and the repository as it actually is. A divergence listed there is a **decision**, not a defect. Only report a mismatch that is *not* covered by a D-entry (and check the ledger's `Ruling:` lines for anything the D-table does not capture).

⚠️ The plan referenced "P10 SPEC V1.3.1"; the SPEC that actually exists in the repo is **V1.0** (this itself is registered as D20). Judge against the file that exists.

## 4. `/home/pangzy/code_project/PCS/.claude/rules/openwolf.md` — governs repo working conventions

Applies to all changed files: bug logging discipline (buglog entries with `fix_commit`), the cerebrum Do-Not-Repeat list (check it — a rule already recorded there is a lesson the change may have re-learned), and the anatomy/status maintenance rules.
