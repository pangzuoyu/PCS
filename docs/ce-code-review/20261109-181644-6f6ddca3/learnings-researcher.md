## Institutional Learnings Search Results

### Search Context
- **Feature/Task**: Review of batch "P9B-4 emergency batch" (base `3a929b6` → head `cbc701b`, 8 commits) — adds project-level access guards to ~20 logistics endpoints in `pcs-backend` (404 byte-identical to "does not exist", never 403), adds guarded endpoint `GET /streams/{id}/review-log`, adds `POST /projects` auto-grant of the creator, adds `scripts/seed_user_project_access.py`, adds a `strict_client` pytest fixture that does not mock the guard, and swaps the frontend 校核记录 Tab from `GET /audit-logs` to the new guarded endpoint.
- **Keywords Used**: 项目守卫 / guard / 404-vs-403 / 同形性 / 逐字相同 / strict_client / mock 守卫 / UserProject / grant / seed / review-log / audit_logs / RECORD_TRANSITION / get-or-create / savepoint / IntegrityError / enum vocabulary / mock-contract drift / rowKey / transition vocabulary.
- **Files Scanned**: 10 solution docs in `docs/solutions/` (all read in full) + `.wolf/cerebrum.md` (Do-Not-Repeat, ~1926 lines) + repo `CLAUDE.md` + `CONCEPTS.md` (present; vocabulary: 物流/Stream、项目/Project、校核、校对转移、审计流水) + the full 19,730-line diff (backend code, 5 new backend test files, conftest, seed script, frontend API/mock/tab/types/tests).
- **Relevant Matches**: 6 of 10 solution docs directly bear on this diff (`midflight-config-rebind-defeeds-one-shot-guards`, `guard-test-fooled-by-lying-comment`, `narrow-declaration-is-not-a-constraint`, `get-or-create-default-row-race-savepoint-reread`, `sqlite-staticpool-hides-uncommitted`, `engine-level-migration-tests-skipif-pg`, `alembic-create-table-silently-drops-schema-elements`); plus 4 new Do-Not-Repeat entries in `.wolf/cerebrum.md` written **by this very batch** (「无权」与「不存在」必须逐字同形 / 守卫必须早于一切业务门禁 / 测试 client 把守卫 mock 成永远 True / SQLite 单测不强制 FK).
- **Compound Packs**: none (resolver returned zero roots) — no pack rules cited.

### Critical Patterns
`docs/solutions/patterns/critical-patterns.md` does not exist in this repo — section omitted.

---

### Relevant Learnings (findings = places where this diff **contradicts** a recorded rule)

#### 1. The review-log endpoint's `action` filter can never match the transitions it promises — and the test fabricates audit rows the state machine never writes

- **File**: `pcs-backend/app/services/stream_review_log_service.py` (new file), `pcs-backend/app/services/state_machine.py`, `pcs-backend/tests/api/v1/test_stream_review_log.py` (new file)
- **Module**: pcs-backend — logistics audit trail / API layer
- **Problem Type**: `testing_issue` (false-green) + `logic_error` in the new endpoint
- **Severity**: high
- **Rule (quoted)** — `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`:
  > 「注释是**愿望**，代码是字面量。」
  > 「**mock 与契约一致是正确性的一部分**，不是开发体验问题。」
  and `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md`:
  > 「**断言新代码时，fixture 只能用契约类型构造**。如果 fixture 与被测对象共用一份错误类型，测试数量再多也是零信号。」
  and `docs/solutions/testing-issues/sqlite-staticpool-hides-uncommitted.md` (grade-3 false green):
  > 「Grade 3 | Feature never executes; no test even involved」
- **Relevance / contradicting lines**:
  - The endpoint filters `AuditLog.action == "RECORD_TRANSITION"` — `pcs-backend/app/services/stream_review_log_service.py:64`.
  - But the state machine writes **one audit row per transition** whose `action` comes from `TRANSITION_AUDIT_ACTION` — `pcs-backend/app/services/state_machine.py:121-123`:
    ```
    StateTransition.SUBMIT_FOR_CHECK: AuditAction.RECORD_TRANSITION,
    StateTransition.PASS_CHECK:      AuditAction.APPROVAL_STEP_PASSED,
    StateTransition.REJECT_CHECK:    AuditAction.APPROVAL_STEP_REJECTED,
    ```
    (`state_machine.py:475` writes `action=TRANSITION_AUDIT_ACTION[transition]` and `detail={"transition": transition.value, ...}` in the *same* row.)
    ⇒ `PASS_CHECK` / `REJECT_CHECK` rows carry `action = APPROVAL_STEP_PASSED / APPROVAL_STEP_REJECTED` ⇒ the `action == "RECORD_TRANSITION"` filter **excludes them** ⇒ the endpoint can only ever return `SUBMIT_FOR_CHECK` rows, while its own docstring, the OpenAPI description and the `ReviewLogItem.transition` schema description all promise three transitions (`SUBMIT_FOR_CHECK / PASS_CHECK / REJECT_CHECK`). The failure is **silent** (200 + partial list) — the designer still cannot see 校对通过 / 校对驳回, i.e. exactly the content TODO-112 exists to deliver.
  - The new test's fixture **fabricates the shape the real writer never produces** — `pcs-backend/tests/api/v1/test_stream_review_log.py:93-95`:
    ```
    """造一条 `RECORD_TRANSITION` 审计行（形状照抄状态机写的）。"""
    row = AuditLog(
        action="RECORD_TRANSITION",
    ```
    The docstring asserts "copied the shape the state machine writes"; the state machine writes `APPROVAL_STEP_PASSED`/`APPROVAL_STEP_REJECTED` for two of the three transitions. ⇒ the whole suite is green on rows that production never produces — the textbook "comment beats the guard" false green recorded in `guard-test-fooled-by-lying-comment.md`.
  - Note: the *old* frontend path had the same `action=RECORD_TRANSITION` pre-filter (`StreamReviewLogTab.tsx` before this diff, `auditApi.listAuditLogs({action:'RECORD_TRANSITION'})`), so the defect is inherited — but this diff **newly codifies** it into a documented contract, so the changed line `stream_review_log_service.py:64` is the right place to fix it.
- **Key Insight**: a fixture must be built from the **real writer's** shape, not from a hand-written copy that merely looks plausible; and a "returns the right thing" test must be able to fail for the right reason. Deriving the filter from `AuditAction` (e.g. `in_([AuditAction.RECORD_TRANSITION.value, AuditAction.APPROVAL_STEP_PASSED.value, AuditAction.APPROVAL_STEP_REJECTED.value])`) or dropping the `action` predicate entirely (the `detail.transition` filter already selects the three) removes the class of defect.

#### 2. `ensure_user_row` is a lock-free get-or-create on a UNIQUE column — the exact shape `docs/solutions/` says to look up before writing one

- **File**: `pcs-backend/app/services/user_project_service.py` (new function, line 231); call site `pcs-backend/app/api/v1/projects.py` (`create_project`)
- **Module**: pcs-backend — data model / API layer
- **Problem Type**: `database_issue`
- **Severity**: high
- **Rule (quoted)** — `docs/solutions/database-issues/get-or-create-default-row-race-savepoint-reread.md`:
  > 「「首次触发才建全局默认行」的 get-or-create，在**库为空 + 并发首建**时必然出现窗口。症状是偶发 500（难复现），而单测（SQLite StaticPool 单连接）永远串行 ⇒ 测不出。」
  > 「**新写 get-or-create 时直接来查这条。**」
  > 「同文件已有修好的同族方法（`_ensure_binding`）而新方法没抄 ⇒ **评审时按「模式 grep」查同文件的同形方法**，别只看单方法」
  > 「**别用裸 `db.rollback()`** —— 调用方（如 POST /projects 的项目 INSERT）与本插入同事务」
- **Relevance / contradicting lines**:
  - `pcs-backend/app/services/user_project_service.py:265-285` — `ensure_user_row` does SELECT-by-`user_id` → SELECT-by-`username` → `session.add(row)` → `await session.flush()` (line 283-284). No savepoint, no `IntegrityError` recovery, no re-read of the winner. `users.username` is `unique=True` (`pcs-backend/app/models/project.py:147`).
  - This function is newly reachable from `POST /projects` (`create_project`): the creator of a project now *always* goes through it, and per ADR-0046 §③b mock logins never create `users` rows ⇒ the row is genuinely absent on the first call ⇒ **two concurrent `POST /projects` by the same user** (double-click / form resubmit) both see "no row", both INSERT, the loser hits `uq users.username` ⇒ uncaught `IntegrityError` ⇒ 500 ⇒ and because the project INSERT is in the same transaction, the whole project creation rolls back — the "偶发 500 + 整个项目创建回滚" symptom the doc names verbatim.
  - Same-family gap newly reachable: `UserProjectService.grant_project_access` (`user_project_service.py:83-107`, called by `create_project` in this diff) is also a lock-free SELECT-then-INSERT against `user_projects` UNIQUE(`user_id`, `project_id`) (`pcs-backend/app/models/project.py:190-193`) ⇒ same race, same 500, same full rollback. This is the doc's own "按『模式 grep』查同文件的同形方法" case: the correctly-fixed sibling (`_get_or_create_default_record_matrix`, savepoint + re-read winner) exists in the codebase, and neither new path copies it.
- **Key Insight**: the recorded fix is three-part and all three parts are missing here — (1) `async with db.begin_nested():` around the INSERT, (2) `db.add()` **inside** the savepoint, (3) on `IntegrityError`, re-read the winner and return it **read-only** (never overwrite the winner's columns), re-raising if the violated constraint is not the expected one.

#### 3. Same-shape ("逐字同形") is maintained by hand-written duplicate literals — contradicting the rule this batch itself wrote into `.wolf/cerebrum.md`

- **File**: `pcs-backend/app/api/v1/streams.py`, `pcs-backend/app/api/v1/lineage.py`, `pcs-backend/app/services/stream_batch_service.py`
- **Module**: pcs-backend — API layer / authorization
- **Problem Type**: `convention (inferred)` — contradicting a Do-Not-Repeat rule added by this same batch
- **Severity**: medium
- **Rule (quoted)** — `.wolf/cerebrum.md` → 「### 「无权」与「不存在」必须**逐字同形**，否则可枚举 UUID（2026-11-09 · P9B-4 紧急批次）」:
  > 「⇒ 同形性不靠「两处写一样的话」，靠**同一个 helper**。」
  and `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` §1:
  > 「**内容相等 ≠ 派生** … ⇒ 断言必须是**结构**的。」
  and `.wolf/cerebrum.md` (pre-existing rule):
  > 「**同一份配置只能有一份解析实现。**」
- **Relevance / contradicting lines**:
  - `pcs-backend/app/api/v1/streams.py:242` and `:254` — `_load_stream_guarded` writes the *same* `raise PcsError(f"Stream {stream_id} 不存在", code="SIM_STREAM_NOT_FOUND", status=404)` **twice** (once for "not found", once for "no access"). The helper's own docstring (line 231-233) claims:
    > 「⚠️ 文案沿用 `StreamService.get` 的措辞（`Stream {id} 不存在`）⇒ … ⇒ 同形性不靠「两处写一样的话」，靠**同一个 helper**。」
    but the wording is a third hand-written copy of `pcs-backend/app/services/stream_service.py:331` / `:517` (`f"Stream {stream_id} 不存在"`) — textual equality, not derivation. Same pattern for the state point: `streams.py:281` vs `stream_service.py:671`.
  - `pcs-backend/app/api/v1/lineage.py:210` — the new cross-project 404 writes the literal `"no lineage for record"` a **third** time in the file (already at `:103` and `:134`).
  - `pcs-backend/app/services/stream_batch_service.py:269-270` and `:294-295` — the "not found" branch and the new "cross-project" branch each hand-write `reason="SIM_STREAM_NOT_FOUND", detail=f"物流 {stream_id} 不存在"`.
  - Why this matters concretely: the "same-shape" tests (`test_stream_project_guard.py::test_not_found_and_cross_project_are_indistinguishable`, `test_stream_batch_submit_of_only_foreign_stream_looks_identical_to_missing`) compare the **two guard branches against each other** — they never compare the guard's message against `StreamService.get`'s message. ⇒ if `StreamService` rewords its 404 (or a future endpoint routes around the guard), the enumeration vector returns **with the whole suite still green**.
- **Key Insight**: the rule's own prescription is to derive the not-found message from **one** source (a shared constant / a service-level helper the guard and the service both call) and to assert *structurally* (same code object) that both branches use it, not textually.

#### 4. `REVIEW_TRANSITIONS` and the audit-action/resource-type literals are hand-copied enum values, not derived from the enums

- **File**: `pcs-backend/app/services/stream_review_log_service.py:36-46, 62-67`
- **Module**: pcs-backend — logistics audit trail
- **Problem Type**: `convention (inferred)` — single-source-of-truth drift risk
- **Severity**: medium
- **Rule (quoted)** — `.wolf/cerebrum.md` (pre-existing):
  > 「**同一份配置只能有一份解析实现。** … ⇒ 解析规则**收敛到唯一入口** … 调用方只做转换，不自己解析。」
  and `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` §1:
  > 「四份输出格式白名单… 注释是**愿望**，代码是字面量 … ⇒ 断言必须是**结构**的。」
- **Relevance / contradicting lines**:
  - `stream_review_log_service.py:36-46` — `REVIEW_TRANSITIONS = ("SUBMIT_FOR_CHECK", "PASS_CHECK", "REJECT_CHECK")` is a hand-written copy of `app/models/enums.py:291-293` (`StateTransition.SUBMIT_FOR_CHECK / PASS_CHECK / REJECT_CHECK`); the module docstring even claims "这是**唯一**一份口径（后端过滤）" — the *filter location* is unique, but the *vocabulary* is a second copy.
  - `stream_review_log_service.py:62` `AuditLog.resource_type == "streams"` and `:64` `AuditLog.action == "RECORD_TRANSITION"` are string literals; the house style in the same codebase derives them (`pcs-backend/app/api/v1/records_actions.py:449` uses `AuditAction.RECORD_TRANSITION.value`).
  - Impact: if a `StateTransition` value is renamed, the endpoint silently returns `[]` (or a partial list) — no error, no exception, the Tab just shows 「（无校核记录）」 — indistinguishable from "never reviewed". The frontend keeps a **third** copy of the vocabulary in `StreamReviewLogTab.tsx` (`TRANSITION_LABEL`), which only affects labels, so it will not surface the drift either.
- **Key Insight**: vocabulary that must agree across the DB filter, the contract and the UI should be derived from the enum at the point of use (`StateTransition.PASS_CHECK.value`), with the assertion pinned **structurally** (e.g. `REVIEW_TRANSITIONS == tuple(t.value for t in (...))`) rather than by a hand-written literal that merely happens to be equal today.

#### 5. The new frontend mock is not typed against the contract it stands in for — the recorded compile-time probe is missing

- **File**: `pcs-frontend/src/mocks/handlers.ts:279-298` (new handler), `pcs-frontend/src/api/stream.ts:47` (`ReviewLogItem = components['schemas']['ReviewLogItem']`)
- **Module**: pcs-frontend — mock layer
- **Problem Type**: `testing_issue` (contract drift / false green)
- **Severity**: medium
- **Rule (quoted)** — `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md` §4:
  > 「推论：**mock 与契约一致是正确性的一部分**，不是开发体验问题。mock 越宽松，它替页面/后端扛的越多，而那些差异平时不可见。」
  > 「### 找出这类的低成本手法 … 加一条编译期断言，让 `tsc` 去比：
  > `const _conforms: PipeClassResponse[] = seedPipeClasses; void _conforms;`」
- **Relevance / contradicting lines**:
  - `pcs-frontend/src/mocks/handlers.ts:279-298` — the new `/api/v1/streams/:stream_id/review-log` handler returns **untyped inline literals** inside `HttpResponse.json([...])`; nothing ties them to `ReviewLogItem`. The API layer *is* contract-derived (`stream.ts:47`), so a contract rename (`operator` → `operator_id`, `transition` → a Literal union) would leave `tsc` green and leave the dev mock serving the old shape — the page keeps "looking right" in dev while production returns the new shape.
  - Related, same file family: the backend contract types `transition` as a bare `string` (`pcs-frontend/src/types/api.d.ts`, `ReviewLogItem.transition: string`) rather than the three-value Literal — the same "contract doesn't record the vocabulary" defect recorded as bug-2113 (`deliverable.sign_status` in OpenAPI is a bare `{"type":"string"}` ⇒ vocabulary drift is invisible to any drift check). Since finding #1 already shows the backend's own vocabulary handling is wrong, a Literal here would have made the mismatch loud at `tsc` time.
- **Key Insight**: a mock that is not statically bound to the contract type is a **dev-only** liability — it absorbs drift that would otherwise surface in the browser regression; bind it (`const _conforms: ReviewLogItem[] = [...]`) so `tsc` fails when the contract moves.

#### 6. (Pre-existing, newly reachable — not a changed line) `guard_project` fixture and the seed script depend on `grant_project_access`, whose lock-free get-or-create is unguarded

- **File**: `pcs-backend/tests/conftest.py` (`grant_project` fixture, new), `pcs-backend/scripts/seed_user_project_access.py` (new), `pcs-backend/app/services/user_project_service.py:83-107`
- **Module**: pcs-backend — test infrastructure / ops script
- **Problem Type**: `database_issue`
- **Severity**: low
- **Rule (quoted)** — `docs/solutions/database-issues/get-or-create-default-row-race-savepoint-reread.md`:
  > 「恢复分支只读不写 —— 撞约束后重读赢家返回，绝不 update（否则把赢家的列改回自己的版本 = 第二种数据损坏）」
- **Relevance**: both new entry points call `grant_project_access` concurrently-sensitive code without the savepoint recipe (same root cause as finding #2, different function). The seed script is single-shot CLI ⇒ negligible; the `grant_project` fixture runs inside a single test session ⇒ negligible. Listed for completeness — the fix belongs in `grant_project_access` itself, which also covers finding #2's second half.
- **Key Insight**: put the savepoint + re-read-winner once inside `grant_project_access` and once inside `ensure_user_row`, rather than at each call site.

---

### Recommendations

1. **Fix finding #1 before merge** — drop the `action == "RECORD_TRANSITION"` predicate from `list_review_log` (the `detail.transition` filter already selects exactly the three transitions) or widen it to the three real `AuditAction` values; and rebuild the test fixture `_audit()` so it derives `action` from `TRANSITION_AUDIT_ACTION[StateTransition(...)]` (or drives a **real** `StreamService.transition`) instead of hardcoding `"RECORD_TRANSITION"` for all three. Otherwise the new endpoint ships a documented 3-transition contract that can only ever deliver 1, with a green suite vouching for it.
2. **Apply the recorded get-or-create recipe to `ensure_user_row`** (savepoint around `session.add` + `flush`, re-read the winner on `IntegrityError`, return the winner read-only, re-raise on an unexpected constraint) — and fix `grant_project_access` the same way, since `POST /projects` now makes both reachable from a user-facing write path. The unique-violation symptom will otherwise surface as an intermittent 500 that rolls back the whole project creation.
3. **Honour the rule this batch wrote**: derive the 404 wording once and share it. Concretely — a single module-level message/helper used by both the "not found" and the "no access" branches of `_load_stream_guarded` / `_load_state_point_guarded`, a single `"no lineage for record"` constant in `lineage.py`, a single constant for the batch's failure text, and have `StreamService.get` / `get_state_point` consume the same source rather than keeping parallel copies. Then pin the *structure* (both branches raise the same constructed error) rather than the text.
4. **Derive the transition vocabulary** from `StateTransition` / `AuditAction` in `stream_review_log_service.py` instead of hand-writing it, and consider typing `ReviewLogItem.transition` as a Literal in the OpenAPI schema so a vocabulary drift becomes a `tsc`/drift-check failure rather than a silently empty Tab.
5. **Bind the new frontend mock to the contract type** with the recorded compile-time probe so a contract change turns `tsc` red instead of being absorbed by the mock.
6. **No action needed** on the parts of this batch that already honour the recorded rules — the `strict_client` fixture restores the guard *before every request* (closing the "client's function-scoped monkeypatch leaks into strict_client" window), guard tests seed through the ORM rather than through `client`, the same-shape tests use **one** uuid for both the "missing" and "cross-project" probes, the guard is ordered before payload/business gates, the `users` row is created before any `user_projects` write (FK precondition asserted directly rather than relying on SQLite), the buglog entries carry `fix_commit`, and the endpoint inventory (10 stream + 6 transition + 3 lineage + batch + review-log) matches the "20 endpoints" claim in `CLAUDE.md`.

### Not reached within budget
- `docs/solutions/` files were all read (10/10); `.wolf/cerebrum.md` was mined for the Do-Not-Repeat section (the security/testing/database subsections were read; the engineering/calculation sections were skimmed and judged out of scope for a backend authorization batch).
- Not independently executed: the test suite, `alembic check` on both databases, or the PG lane (`scripts/pytest_pg.sh`) — findings #1, #2 and #3 are grounded in static reading of the changed code plus the recorded rules, not in a failing-test run.
- Not reviewed line-by-line: `pcs-backend/docs/openapi.json` / `openapi-baseline.json` / `pcs-frontend/openapi.snapshot.json` (regenerated artifacts), `.wolf/anatomy*.json` (hook-maintained index), and the `TODOS.md` / `docs/PCS-UI-SPEC.md` prose updates beyond the endpoint-count claim.
