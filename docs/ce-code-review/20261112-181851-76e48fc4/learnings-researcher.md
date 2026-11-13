# Institutional Learnings Search Results

> Reviewer persona: **learnings-researcher** · Scope: P10-A batch (`3fae3f6..55239ff`)
> Search roots: `docs/solutions/` only (no Compound Packs declared).
> Every corpus entry was read **in full**; each was then checked against the **changed
> code** in this diff and classified as **honored / contradicted / not touched**.

## Search Context

- **Feature/Task**: Reviewing the P10-A batch (AI *reservation* slice — 5× 501 endpoints,
  single sanctioned outbound AI client, pure-ASGI AI audit middleware, ARQ idempotent audit
  task, 8 new `ai_audit_log` columns + migration `p10_001`, `/api/v1/health/ai`, architecture
  guard — plus test-infrastructure left-shift: compose `migrate`/`seed` one-shot services,
  idempotent seed script, real-backend Playwright channel with MSW disabled).
- **Keywords Used**: AI audit middleware, ARQ background job, idempotent audit write,
  partial unique index, ON CONFLICT, index_where, PII sanitization, CIDR allowlist,
  internal-only AI egress, Alembic migration vs ORM drift, compose test profile, seed script,
  Playwright real-backend channel, architecture guard, get-or-create, savepoint, IntegrityError,
  StaticPool, migration idempenency guard, information_schema, search_path.
- **Grounding**: `CONCEPTS.md` was read (schema drift / idempotent migration guard /
  constraint naming convention / deferred FK / constraint substitute / mixin audit columns /
  creator attribution). It supplied the canonical vocabulary used below ("schema drift",
  "idempotent migration guard", "constraint naming convention").
- **Files Scanned**: 10 solution files in `docs/solutions/` (all read in full — the corpus is
  small, so no grep pre-filter was needed) + `CONCEPTS.md` + 27 project files read for
  diff-side verification (migration, ORM, middleware, ARQ task/enqueue/worker, CIDR, sanitizer,
  health, main, seed script, 8 new test files, compose, playwright/vite config, conftest).
- **Relevant Matches**: 10 of 10 (5 expanded below with per-line verdicts; 5 summarized under
  "Additional matches").
- **Critical Patterns**: `docs/solutions/patterns/critical-patterns.md` **does not exist** in this
  repo — section omitted.

## Relevant Learnings

### 1. ARQ 0.28 worker: five silent failure modes from misread framework semantics

- **File**: `docs/solutions/framework-integration-issues/arq-028-worker-silent-failure-modes.md`
- **Module**: pcs-backend workers — ARQ task lifecycle
- **Problem Type**: `framework_integration_issue`
- **Severity**: high
- **Relevance**: The batch adds a brand-new ARQ task (`write_ai_audit_log`) + a new enqueue
  helper + a worker registration — i.e. it touches every one of the five recorded failure modes.
  **2 of 5 honored, 1 contradicted (finding candidate), 2 not applicable.**

  **HONORED — §2 "`enqueue_job` takes a function *name string*"**:
  `pcs-backend/app/services/ai/arq_queue.py:66` — `job = await pool.enqueue_job("write_ai_audit_log", **payload)`
  (name string, not the function object), and the §2 prescription "Still import the function in
  the enqueue helper so a typo explodes *before* enqueue" is applied at
  `pcs-backend/app/services/ai/arq_queue.py:59` — `from app.workers.ai_audit_tasks import write_ai_audit_log  # noqa: F401`.

  **HONORED — §4 "Session leak / flush vs commit"**: the task opens its own session and closes it
  (`pcs-backend/app/workers/ai_audit_tasks.py:162` — `async with factory() as session:`) and
  commits the row (`pcs-backend/app/workers/ai_audit_tasks.py:141,144` — `await session.commit()`),
  i.e. terminal state is written *by* the commit it belongs to, not after it.

  **HONORED — §2/"ARQ does not error on unregistered function names"**: the task is registered
  (`pcs-backend/app/workers/worker.py:160` — `write_ai_audit_log,`) and a dedicated ratchet exists
  (`pcs-backend/tests/services/ai/test_ai_audit_task.py:99-110`).

  **CONTRADICTED — §1 "ARQ does not retry ordinary exceptions — ever"** ⇒ **finding candidate (P2)**.
  Corpus rule: *"So `WorkerSettings.max_tries = 3` guarantees nothing by itself: it bounds how many
  times a `Retry` **may** recur; it does not trigger retries. A task body raising
  `PcsError`/`RuntimeError` runs once, full stop."*

  Contradicting changed line — `pcs-backend/tests/services/ai/test_ai_audit_task.py:5`:
  > `ARQ 默认 `max_tries=5`（本批不显式改）⇒ **重试必然发生** ⇒`

  Two separate factual errors in one line: (a) the retry premise is exactly what the corpus rule
  refutes; (b) `max_tries` is **3** in this repo, not 5, and it is set explicitly —
  `pcs-backend/app/workers/worker.py:48` (`MAX_TRIES = 3`) and `pcs-backend/app/workers/worker.py:237`
  (`max_tries = MAX_TRIES`).

  This is **not** an adjudicated deviation: the batch's own ledger already ruled on this exact
  premise — `.superpowers/sdd/2026-11-04-p10-batch-a-preflight-ai-reserve/progress.md:185-189`:
  > *"计划说「ARQ 默认 max_tries=5 ⇒ 重试必然发生 ⇒ 幂等不是锦上添花」—— 但 **arq 0.28 只对 `Retry` 异常重试**（其余当场判死，见本仓 bug-168）⇒「重试必然发生」**不成立**。… 但理由改写为「重投语义」而非「现在就在重试」。代价：无（实现不变，注释改对）。"*

  The **production** docstring was corrected (`pcs-backend/app/workers/ai_audit_tasks.py:12-14`:
  *"⚠️ **arq 0.28 只对 `Retry` 异常重试**（其余异常当场判死）⇒ 「重试必然发生」在本仓**不成立**"*)
  but the **test module's** docstring — the copy a future maintainer reads first — still carries
  the disproven claim. This is the corpus's `guard-test-fooled-by-lying-comment` §5 family
  ("注释比代码乐观") landing inside the same batch that corrected it elsewhere.

- **Key Insight**: ARQ's `max_tries` is a ceiling on `Retry`-driven recurrences, never a trigger.
  Idempotency must be justified by *redelivery* semantics, not by "ARQ will retry".

---

### 2. 守门测试会被它所守护的那行注释骗过 (A guard test fooled by the comment it guards)

- **File**: `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`
- **Module**: pcs-backend + pcs-frontend 测试有效性
- **Problem Type**: `testing_issue`
- **Severity**: high
- **Relevance**: The batch adds (a) a *new* architecture guard and (b) a *new* migration-shape
  guard, and rewrites the frontend mock/real-backend split. **1 honored (strongly), 1 contradicted
  (finding candidate), 1 partially honored.**

  **HONORED — the architecture guard uses AST, not text.** The corpus rule is *"别扫文本，走 AST …
  **凡是「证明 A 引用了 B」的断言，都不该用文本匹配。**"*
  `pcs-backend/tests/architecture/test_no_direct_ai_sdk.py:111` parses the module
  (`tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))`) and matches
  `ast.Import` / `ast.ImportFrom` nodes (`:61-70`), `ast.Call` nodes for httpx (`:73-85`), and
  `ast.Attribute`/`ast.Constant` for the endpoint markers (`:88-96`). Comments cannot reach the AST
  ⇒ the guard is exactly what the corpus asks for. The batch also verified it with a probe
  (ledger `progress.md:215-216`: "守门自己被验过 … 两条规则都红 ⇒ 删掉又绿").

  **HONORED — compose guard parses YAML, not text.** `pcs-backend/tests/scripts/test_compose_test_profile.py:32`
  uses `yaml.safe_load(...)` and asserts on the parsed structure (e.g. `:46`
  `assert "test" in (services["seed"].get("profiles") or [])`).

  **HONORED — the mock-channel/real-channel split is structural, not env-driven.**
  `pcs-frontend/playwright.config.ts:56-75` starts a **second** server on port 5174 with
  `VITE_ENABLE_MOCK=false` and `reuseExistingServer: false`, and
  `pcs-frontend/src/main.tsx:14` skips MSW on `import.meta.env.VITE_ENABLE_MOCK !== 'false'`.
  This directly implements the corpus's "mock 与契约一致是正确性的一部分" (§4) — the real-backend
  channel is the mechanism that makes mock drift visible.

  **CONTRADICTED — the migration-shape guard text-matches the file it guards** ⇒ **finding candidate (P2)**.
  Corpus rule: *"第二版改用 `inspect.getsource(module)` 找 `'EXPORT_FORMATS'` 子串。**还是绿的** …
  因为那句**说谎的注释**正好写着「取自 `watermark.EXPORT_FORMATS`」，子串命中了。… **凡是「证明 A 引用了 B」的断言，都不该用文本匹配。**"*

  Contradicting changed line — `pcs-backend/tests/alembic/test_p10_001_ai_audit_fields.py:103`:
  > `assert "request_id IS NOT NULL" in src`

  `src` is the **raw text of the migration file** (`:48-49` — `_source()` returns
  `MIGRATION.read_text(encoding="utf-8")`). The same string is already present in the migration's
  **own docstring** — `pcs-backend/alembic/versions/p10_001_ai_audit_request_fields.py:20`:
  > "`WHERE request_id IS NOT NULL` 显式声明 partial："

  ⇒ deleting `postgresql_where=sa.text("request_id IS NOT NULL")` from the `op.create_index(...)`
  call (`:81-88`) leaves this test **green**. The guard's stated purpose ("唯一索引是 partial") is
  exactly what the text match fails to establish — and the failure it would cause is the one the
  batch itself just fixed in production (`bug-2159`: PG `ON CONFLICT` cannot match a non-partial
  index ⇒ *every* AI audit write raises `InvalidColumnReferenceError` ⇒ **only** the manually-run
  PG lane would catch it).

  The hazard is acknowledged **in the same file** for a neighbouring assertion —
  `pcs-backend/tests/alembic/test_p10_001_ai_audit_fields.py:110`:
  > "⚠️ 按**调用块**逐个查（不能数全文出现次数 —— docstring 里也出现了这个词）"

  ⇒ the per-call-block treatment was applied to `if_not_exists` but not to the partial-index
  assertion. The **ORM side** of the same property is checked structurally and is sound
  (`:142-144` — `idx.dialect_options["postgresql"]["where"]`).

- **Key Insight**: An assertion that a file *contains* a string proves nothing about the file's
  *structure*; the same string can live in the docstring, in a comment, or in a dead code path.

---

### 3. 引擎级迁移测试：隔离 schema + 子进程 alembic（本仓无自动化 PG 通道）

- **File**: `docs/solutions/testing-issues/engine-level-migration-tests-skipif-pg.md`
- **Module**: pcs-backend 测试 — alembic 引擎级测试（隔离 schema）
- **Problem Type**: `testing_issue`
- **Severity**: medium
- **Relevance**: The batch adds a real-PG test file and a compose PG/test profile. **Largely
  honored; one contradiction (finding candidate).**

  **HONORED — no false delegation.** The new PG test states the channel honestly
  (`pcs-backend/tests/services/ai/test_ai_audit_task_pg.py:22-24`):
  > "⚠️ `pg` marker 的用例平时被 `pytest.skip` 静默跳过 ⇒ 绿灯**证明不了**它们跑过 ⇒ **必须**经 `scripts/pytest_pg.sh`（唯一入口）跑。"

  It does **not** claim CI verifies it — precisely the failure the corpus calls out
  ("**false delegation**（比没有测试更糟 —— 下一个维护者以为 CI 在验 ⇒ 不会去补测试）").

  **HONORED — the isolated-schema recipe is followed** (`:166-224`): create schema in a
  subprocess with the *original* URL, `alembic upgrade head` in a subprocess with
  `options=-csearch_path=<schema>`, then assert **after** the subprocess (the corpus's pitfall ③:
  "断言留在本地、迁移在子进程" — the assertions live inside the script that reads the migrated DB).

  **HONORED — pitfall ① (literal `{schema}` / assertion masking) is avoided**: the schema name
  travels through `os.environ["ISO_SCHEMA"]` (`:178,183`), never as an f-string placeholder.

  **CONTRADICTED — cleanup must be loud** ⇒ **finding candidate (P2)**.
  Corpus rule: *"隔离 schema 的**清理**是测试的一部分，不是善后 —— 清理失败要**响亮**"*; the corpus
  symptom list names this exact failure: *"隔离 schema 的 `DROP SCHEMA` 清理失败被静默吞掉 ⇒
  孤儿 schema 留在开发库里，而 DDL 已经落地"*.

  Contradicting changed lines — `pcs-backend/tests/services/ai/test_ai_audit_task_pg.py:225-248`:
  the `finally` block runs `subprocess.run([... "DROP SCHEMA IF EXISTS " + os.environ["ISO_SCHEMA"] + " CASCADE" ...])`
  and **never inspects `returncode`** — in contrast to the CREATE-SCHEMA step in the same file,
  `pcs-backend/tests/services/ai/test_ai_audit_task_pg.py:189`:
  > `assert created.returncode == 0, f"CREATE SCHEMA 失败:\n{created.stderr}"`

  ⇒ a failed `DROP SCHEMA` (e.g. an open connection in the isolated schema) is swallowed ⇒ the
  orphan schema survives **in the developer's database**, exactly as the corpus records. The
  lesson's pitfall ① also applies to the asymmetry: an assertion placed *inside* `finally` would
  mask the real error, so the fix is to assert **after** the `try/finally`, not inside it.

- **Key Insight**: A test that leaves state behind when it fails is worse than a test that
  doesn't run — the next run then collides with the debris.

---

### 4. get-or-create 默认行的并发兜底：savepoint 内插 + 撞约束重读赢家

- **File**: `docs/solutions/database-issues/get-or-create-default-row-race-savepoint-reread.md`
- **Module**: pcs-backend signature_matrix_service
- **Problem Type**: `database_issue`
- **Severity**: medium
- **Relevance**: The batch writes a **brand-new** seed script whose entire job is "create-if-absent"
  — literally the shape the corpus says to look up before writing. **Contradicted (finding candidate).**

  Corpus rule: *"**`db.add` 在 `begin_nested()` 之内** —— savepoint 建立时会先 flush 一次 pending …
  **恢复分支只读不写** —— 撞约束后重读赢家返回，绝不 update … **别用裸 `db.rollback()`**"* and
  *"这是本仓 solutions 语料第二次记同族 … ⇒ **新写 get-or-create 时直接来查这条**"*.

  Contradicting changed lines — all five helpers in `pcs-backend/scripts/seed_e2e_data.py` use the
  bare lock-free "SELECT ⇒ see empty ⇒ INSERT" shape with no savepoint and no `IntegrityError`
  recovery, e.g. `pcs-backend/scripts/seed_e2e_data.py:104-119`:
  > `existing = (` / `await db.execute(select(Workspace).where(Workspace.workspace_id == SEED_WORKSPACE_ID))` / `)` / `if existing is not None:` / `    return existing` … `db.add(ws)` / `await db.flush()`

  Same shape at `:123-144` (`_ensure_project`), `:147-172` (`_ensure_users`), `:175-196`
  (`_ensure_grants`), `:199-225` (`_ensure_streams`). The batch's own test module names the
  constraints that would be hit (`pcs-backend/tests/scripts/test_seed_e2e_data.py:3-5`: *"第二次跑
  要么撞唯一约束（`users.username` / `uq_user_projects_user_project`）"*).

  Impact assessment (honest): the failure is **loud**, not silent — the `IntegrityError` aborts
  the script and nothing is committed (the `commit()` is at `pcs-backend/scripts/seed_e2e_data.py:252`,
  after all the inserts) ⇒ no data corruption. The exposure is the concurrent-first-run window:
  two overlapping `seed` invocations (compose `seed` service + a manual run, or a restarted
  container whose previous `seed` is still alive) ⇒ one of them aborts ⇒ the E2E channel starts
  with missing rows ⇒ the whole real-backend channel 404s (`pcs-backend/scripts/seed_e2e_data.py:18-24`
  explains that missing `UserProject` rows make every project-guarded endpoint 404).

- **Key Insight**: The house pattern for get-or-create is *savepoint + insert inside it + catch
  `IntegrityError` + re-read the winner read-only*. A bare `SELECT`-then-`INSERT` is only safe
  when nothing else can write concurrently.

---

### 5. `sqlite+aiosqlite:///:memory:` is StaticPool: "read it from another session" proves nothing

- **File**: `docs/solutions/testing-issues/sqlite-staticpool-hides-uncommitted.md`
- **Module**: pcs-backend test suite — conftest engine fixtures
- **Problem Type**: `testing_issue`
- **Severity**: high
- **Relevance**: The batch adds two new "the data really landed" tests — one for the seed script,
  one for the ARQ audit task. Both observe the DB through the **same** session/connection that
  wrote it. **Contradicted in substance (finding candidate, P3)** — the production code is
  correct (both do commit), but the *guard* cannot distinguish "committed" from "flushed".

  Corpus rule: *"A test that opens a second session to prove a task committed its state passes
  even when the code only flush()ed — the assertion is void"*; fix: *"file-backed SQLite when the
  observation is 'uncommitted' … assert from a session created **after**"*.

  Void observation sites:
  - `pcs-backend/tests/scripts/test_seed_e2e_data.py:34-48` — `seed(db_session)` is called with the
    very session the assertions then read (`:44-48` — `assert await _count(db_session, Project) == 1`).
    The compose `seed` service is a **one-shot container** (`docker-compose.yml:123-147`): the data
    must survive session close / process exit. A `flush()`-only regression would leave this test
    green.
  - `pcs-backend/tests/services/ai/test_ai_audit_task.py:70` — `assert await _count(db_session) == 1`,
    where the writer used a *different* session (`worker_ctx`) — but both come from the same
    `db_engine`, i.e. the same StaticPool connection, so the "committed" claim is equally unproven.

  Mitigating context: the corpus's grade-2 false green is *not* fully unguarded here — the PG lane
  (`pcs-backend/tests/services/ai/test_ai_audit_task_pg.py:115-157`) does read the table from a
  separate session/connection on a real Postgres, and the ledger records that lane was actually run
  (`progress.md:228` — "PG 车道 **6 passed**（+1）"). But that lane is manual, so the *default* green
  still means nothing about durability.

- **Key Insight**: "The row is visible from another session" is not evidence of a commit when both
  sessions share one SQLite connection. Use a file-backed DB for commit-ness observations.

---

## Additional matches (relevant, not expanded)

- **`docs/solutions/database-issues/dialect-options-invisible-on-sqlite.md`** (`database_issue`,
  medium) — *"Declare the intent once in ORM with **every** dialect variant spelled out
  (`postgresql_nulls_not_distinct` + `postgresql_where` + `sqlite_where`)"*. **Partially honored /
  form-level divergence (P3 note, not a defect):** both the ORM
  (`pcs-backend/app/models/system.py:200-205`) and the migration
  (`pcs-backend/alembic/versions/p10_001_ai_audit_request_fields.py:81-88`) declare
  `postgresql_where=text("request_id IS NOT NULL")` with **no** `sqlite_where`, so the SQLite test
  schema gets a predicate-less unique index. In *this* instance the observable divergence is nil —
  SQLite also treats NULLs as distinct inside a UNIQUE index, so multiple NULL `request_id` rows
  are allowed on both engines — so the corpus's "tests stricter than production" inversion does
  **not** materialize. Worth one line of `sqlite_where` to keep the intent explicit for the next
  partial index whose predicate is not NULL-based.
- **`docs/solutions/database-issues/alembic-create-table-silently-drops-schema-elements.md`**
  (`database_issue`, high) — **Not applicable, and the corpus's prescription is already
  implemented.** `p10_001` adds columns to an existing table (`op.add_column`), so the
  `op.create_table` FK-drop hazard does not reach it, and all 8 new columns are nullable additive
  (no mixin-column transcription gap). The corpus's suggested static check is in place:
  `pcs-backend/scripts/check_migration_idempotency.py:71-86` (`_check_create_table_args`, pure AST,
  `sa.ForeignKey` deliberately excluded from the allow-list). Minor note: the migration uses
  `op.add_column` rather than the corpus's re-runnable `ALTER TABLE … ADD COLUMN IF NOT EXISTS`
  idiom, so it is not re-runnable after a partial failure — mitigated by PG transactional DDL and
  by the repo's own exemption (`check_migration_idempotency.py:36` — `"op.add_column": []`).
- **`docs/solutions/database-issues/information-schema-not-scoped-by-search-path.md`**
  (`database_issue`, medium) — **Not touched.** The new PG test asserts through ORM queries only
  (`pcs-backend/tests/services/ai/test_ai_audit_task_pg.py:118-146` — `select(func.count())…`);
  no `information_schema` / `pg_catalog` metadata query appears in the batch, so the
  "cross-schema counting" trap is not reachable. The isolated schema is also created *by
  migrations* (not by ORM metadata), so the schema-shape is migration-rendered by construction.
- **`docs/solutions/security-issues/midflight-config-rebind-defeeds-one-shot-guards.md`**
  (`security_issue`, high) — **Mostly honored; one criteria-split note (P3).** The corpus's core
  point — *"启动时过了不代表此刻还成立"* — is implemented twice: startup validation
  (`pcs-backend/app/main.py:171` → `validate_ai_startup_config`) and **call-time** re-validation
  (`pcs-backend/app/core/outbound_ai_client.py:67` — `validate_ai_endpoint(self.endpoint, self.cidrs)`).
  Two residual observations: (a) the call-time check validates the endpoint **captured at client
  construction** (`pcs-backend/app/core/outbound_ai_client.py:46-57`), whereas the authoritative
  `system_settings.ai_endpoint` is runtime-editable and read fresh per request elsewhere
  (`pcs-backend/app/api/v1/health.py:146-149`) ⇒ P10-B must build the client per request from the
  DB value or the corpus's exact shape ("one-shot check + runtime-rebindable source") reappears;
  (b) `/api/v1/health/ai` deliberately refuses DNS (`pcs-backend/app/api/v1/health.py:181-189` —
  "域名 ⇒ **不解析 DNS** ⇒ 恒 degraded") while the startup check *does* resolve DNS
  (`pcs-backend/app/main.py:171` → `pcs-backend/app/core/ai_cidr.py:101-127`) ⇒ the same
  configuration gets two opposite verdicts from two components — the "口径分叉" family the batch's
  own code flags at `pcs-backend/app/core/ai_cidr.py:86-89` ("两个安全相关判断可能给出相反结论").
  Not exploitable in P10-A (the 501 paths never call out), but it is a shape to pin before P10-B.
- **`docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md`** (`testing_issue`,
  high) — **Honored.** The 8 new columns are narrow declarations (`String(64/128/200/80/50)`), and
  the writer truncates to exactly those widths (`pcs-backend/app/workers/ai_audit_tasks.py:69-75`
  and `:88-91`), so a client-controlled over-long `X-Request-ID` cannot make PG raise
  `22001 string_data_right_truncation` and silently drop the whole audit row (the batch's own
  H-1 / `bug-2160`). Residual, non-blocking: truncation is a *silent* rewrite — two distinct
  client-supplied request IDs longer than 128 chars become indistinguishable in the audit trail
  (no uniqueness impact: the idempotency key is the server-generated `request_id`).

## Findings Candidates (contradictions with corpus rules)

| # | Sev | Corpus rule | Changed line that contradicts it |
|---|-----|-------------|--------------------------------------|
| 1 | **P2** | arq-028 §1 — *"ARQ does not retry ordinary exceptions — ever … `max_tries` guarantees nothing by itself"* | `pcs-backend/tests/services/ai/test_ai_audit_task.py:5` — "ARQ 默认 `max_tries=5`（本批不显式改）⇒ **重试必然发生** ⇒" (repo value is 3: `pcs-backend/app/workers/worker.py:48`, `:237`; the batch's own ledger corrected this premise at `progress.md:185-189`, but only in the production docstring) |
| 2 | **P2** | guard-test-fooled-by-lying-comment — *"凡是「证明 A 引用了 B」的断言，都不该用文本匹配"* | `pcs-backend/tests/alembic/test_p10_001_ai_audit_fields.py:103` — `assert "request_id IS NOT NULL" in src` — satisfied by the migration's own docstring `pcs-backend/alembic/versions/p10_001_ai_audit_request_fields.py:20`, so deleting `postgresql_where` keeps it green |
| 3 | **P2** | engine-level-migration-tests-skipif-pg — *"隔离 schema 的**清理**是测试的一部分，不是善后 —— 清理失败要**响亮**"* | `pcs-backend/tests/services/ai/test_ai_audit_task_pg.py:225-248` — `finally` block runs `DROP SCHEMA … CASCADE` in a subprocess and never checks `returncode` (contrast `:189`) |
| 4 | **P2** | get-or-create-default-row-race-savepoint-reread — *"**`db.add` 在 `begin_nested()` 之内** … 撞约束后重读赢家"* | `pcs-backend/scripts/seed_e2e_data.py:104-119` (and `:123-144`, `:147-172`, `:175-196`, `:199-225`) — lock-free SELECT-then-INSERT, no savepoint, no `IntegrityError` recovery |
| 5 | **P3** | sqlite-staticpool-hides-uncommitted — *"read it from another session proves nothing … 用 file-backed SQLite"* | `pcs-backend/tests/scripts/test_seed_e2e_data.py:34-48` and `pcs-backend/tests/services/ai/test_ai_audit_task.py:70` — observations made through the writing session / same StaticPool connection ⇒ commit-ness unproven (code does commit; the *guard* is void) |

## Residual Risks

- **Audit completeness depends on the ARQ worker being alive.** The audit row is written *only* by
  the worker (`pcs-backend/app/workers/ai_audit_tasks.py:147-179`); the endpoint merely enqueues
  (`pcs-backend/app/core/ai_audit_middleware.py:204`) and enqueue failure is a warning only
  (`pcs-backend/app/services/ai/arq_queue.py:68`). If Redis or the worker is down, requests still
  return 501 and the audit table is **completely blind** — the corpus's ARQ lesson §5 warns about
  exactly this window ("an endpoint failure between enqueue and commit leaves a file with no audit
  row"). Deliberate ("审计是旁路"), so reported as a risk, not a defect — but it should be pinned
  as an explicit decision before P10-B turns the reservation on.
- **No automated PG lane (corpus rule still stands).** The batch adds a *manual* compose
  `pg`/`test` profile (`docker-compose.yml:99-147`) and honest `pg`-marked tests, but CI still
  runs no backend pytest ⇒ engine-level assertions remain skip-by-default; "green CI" continues to
  prove nothing about migrations (corpus: *"绿灯**证明不了**它们跑过"*).
- **A third PG database now exists.** `pcs_pgtest` (`docker-compose.yml:18-41`) is migrated by the
  compose `migrate` service, but the repo's standing pre-release checklist (CLAUDE.md「发布前检查」)
  names only `pcs` / `pcs_test` for `alembic check`. The corpus rule: *"Claiming 'migrations hold
  elsewhere' requires running `alembic check` on **each** database."*
- **Two security-relevant verdicts for one configuration** (startup resolves DNS and passes;
  `/api/v1/health/ai` reports `degraded` / "没验证过") — see learning 5 above.
- **Silent truncation** of client-controlled `client_request_id` at 128 chars
  (`pcs-backend/app/workers/ai_audit_tasks.py:88-91`).

## Testing Gaps

- The dialect-shape assertion does **not** pin `index_where`
  (`pcs-backend/tests/services/ai/test_ai_audit_task.py:161-164` asserts only `"ON CONFLICT"`,
  `"request_id"`, `"DO NOTHING"`) ⇒ it would have stayed green with the `bug-2159` defect that broke
  every PG audit write. A `"request_id IS NOT NULL" in text` assertion on the *rendered* PG
  statement would close it (rendered text is fine here — it is a dialect rendering, not a source
  scan).
- No test proves the **seed data survives session close / process exit** — the actual requirement of
  the one-shot compose `seed` service (`docker-compose.yml:123-147`).
- No test covers **concurrent** seed runs (the get-or-create race); the corpus's own detection
  recipe (patch `db.execute` to simulate the opponent row) is available.
- No test pins that the migration's `op.create_index` call keeps its `postgresql_where` **structurally**
  (the ORM side is pinned structurally at `tests/alembic/test_p10_001_ai_audit_fields.py:142-144`;
  the migration side is not).
- The AI audit row's durability is proven only on the manually-run PG lane; the default (SQLite)
  lane cannot distinguish committed from flushed.

## Recommendations

1. **Fix the stale ARQ rationale in the test module** — replace
   `pcs-backend/tests/services/ai/test_ai_audit_task.py:5-7` with the wording already used in
   `pcs-backend/app/workers/ai_audit_tasks.py:12-14` ("job 可能被重投 / 将来加退避重试"), and drop
   the wrong `max_tries=5` (repo value: 3). This is a one-line docstring edit and it closes the last
   copy of a claim the batch's own ledger already ruled false.
2. **Make the partial-index guard structural** — parse the migration's `op.create_index` call with
   `ast` and assert the `postgresql_where` keyword's value (the same per-call-block technique the
   neighbouring `if_not_exists` test already uses at
   `pcs-backend/tests/alembic/test_p10_001_ai_audit_fields.py:113-116`), so the migration's own
   docstring can no longer satisfy the assertion.
3. **Make the PG test's cleanup loud** — capture the `DROP SCHEMA` subprocess result in the `finally`
   block and assert on it **after** the `try/finally` (not inside it, which would mask a real
   failure), mirroring the `CREATE SCHEMA` assertion at
   `pcs-backend/tests/services/ai/test_ai_audit_task_pg.py:189`.
4. **Adopt the house get-or-create shape in the seed script** — wrap each `db.add` + `flush` in
   `async with db.begin_nested():` and add an `except IntegrityError:` branch that re-reads the
   winner read-only (never `update`, never bare `rollback`). It is a mechanical change to five
   helpers and it makes the script safe under an overlapping run.
5. **Add one durability test per writer** — a file-backed SQLite (`tmp_path`) test for the seed
   script asserting the rows are visible from a session created *after* the writer's session
   closed, and the equivalent assertion for the ARQ audit task; this is what upgrades the default
   green from "possibly flushed" to "committed".
6. **Record the new database in the pre-release checklist** — `pcs_pgtest` needs its own
   `alembic check` entry (per-DB, independent process, direct `alembic_version` + index verification),
   matching the corpus's cross-database rule.
7. **Capture the remaining corpus lessons** — the batch produced at least three new durable
   learnings that the corpus does not yet hold: (a) the ARQ audit-row durability chain (enqueue →
   worker → idempotent insert) and its failure modes, (b) the compose `migrate`/`seed` one-shot
   pattern (and the "test profile is silent" trap), (c) the real-backend Playwright channel as the
   structural answer to "mock hides contract drift". `docs/solutions/` currently has no entry for
   any of these, and the P10-A batch re-derived the ARQ lesson from scratch in a test docstring —
   a concrete demonstration that the corpus entry existed but was not consulted.
