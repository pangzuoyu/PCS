---
module: pcs-backend test suite — conftest engine fixtures
date: 2026-10-18
problem_type: testing_issue
component: testing_framework
severity: high
symptoms:
  - "A test that opens a second session to prove a task committed its state passes even when the code only flush()ed — the assertion is void"
  - "The reclaimer cron was entirely inert (no commit) for weeks with green CI; the commit-ness test written to catch it was green before the fix"
  - "Session A inserts without committing; session B SELECT sees the row"
root_cause: test_fixture_semantics
resolution_type: test_infrastructure_fix
framework_version: SQLAlchemy 2.0.52 / aiosqlite / pytest-asyncio
related_components:
  - background_worker
  - data_model
tags:
  - sqlite
  - staticpool
  - transaction-isolation
  - false-green
  - observation-point
  - test-fixture-blind-spot
---

# `sqlite+aiosqlite:///:memory:` is StaticPool: "read it from another session" proves nothing

## The probe (reproduce it yourself)

```python
engine = create_async_engine("sqlite+aiosqlite:///:memory:")
engine.pool.__class__.__name__      # -> StaticPool

# session A: INSERT, no commit
# session B: SELECT count(*)  ->  1      <- reads A's UNCOMMITTED row
# session A: rollback()
# session B: SELECT count(*)  ->  0
```

`:memory:` databases live and die with their connection, so SQLAlchemy pins one
connection via `StaticPool`. **Every session in the process shares that
connection**, and a single SQLite connection sees its own uncommitted writes.
Transaction isolation between sessions — the thing the test was trying to
observe — does not exist.

## Why this is worse than a buggy test

The correct *principle* ("read from another session, or you're just reading the
task's own uncommitted data") was applied and documented in the test's
docstring. The principle is right; the fixture silently defeats it. That
combination — right principle, defeated observation — is the most convincing
kind of green. It let an entirely inert reclaimer cron (bug-169) and a
"commits its state" test that proved nothing (bug-171) coexist for weeks.

Three false-green grades, in order of difficulty:

| Grade | Shape | Example |
|---|---|---|
| 1 | Test asserts the wrong thing | bug-143/145/149/150 |
| 2 | Observation method defeated by fixture | **this document** (StaticPool) |
| 3 | Feature never executes; no test even involved | bug-174 (QR never printed) |

Grade 3 needs no test bug at all, which is why "write the tests correctly"
cannot catch it — see the derived rule below.

## Fix: file-backed SQLite when the observation is "uncommitted"

```python
engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/probe.db")
maker = async_sessionmaker(engine, expire_on_commit=False)
# seed + commit in one session; run the code under test with {"session_factory": maker};
# assert from a session created *after* — now genuinely another connection
```

A file-backed DB gets a connection pool with real per-connection transactions;
B's SELECT now returns committed state only. Working example:
`tests/workers/test_report_tasks.py::test_cron_reclaim_commits_so_the_state_survives_its_own_session`
— which failed correctly against the pre-fix code only after the switch from
`:memory:`.

Conftest deliberately stays on `:memory:` (thousands of tests depend on its
speed); only tests whose *subject is commit-ness* reach for `tmp_path`.

## Derived rule: optional features need a "did fire" test

For any `if optional_payload:` / `if send_email:` / `if enable_cache:` branch,
at least one test must assert the branch **executes** with the feature on — not
only "doesn't crash with it off". An empty branch cannot fail, so green is the
default there. bug-174: the QR payload was complete and signed, but an upstream
"empty ⇒ skip" rule (whose premise had drifted from the verify endpoint's real
behavior) meant the QR never rendered — everything green, feature never ran.

## Audit trail

11 tests in this repo build a second session or use `db_engine` directly.
Three disclose their StaticPool limitation honestly (they serialize the critical
section with an `asyncio.Lock` and comment that PG row locks are the real
guarantee) — those are the pattern to copy. Two were confirmed void (the
bug-171 pair). Six remain unverified: see TODOS.md「StaticPool 让『开第二个
session 读』在本仓全仓失效」, including `test_rbac_audit_row_real_db`, whose
name promises a real DB while running on the in-memory engine.
