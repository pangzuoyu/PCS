---
module: pcs-backend workers — ARQ task lifecycle
date: 2026-10-18
problem_type: framework_integration_issue
component: background_worker
severity: high
symptoms:
  - "A job that always fails runs exactly once: audit_logs has one REPORT_FAILED row (attempt_no=1), the arq:retry:{job_id} counter stays at 0, the row stays PENDING forever, the frontend polls until timeout"
  - "enqueue succeeds, the API returns 202, then worker logs `job <id>, function <function ... at 0x...> not found` and the job fails — every layer silent, polling shows RUNNING until timeout"
  - "Cron job registered with second=None fires 59 times per minute instead of being unrestricted"
  - "Reclaimer cron runs, logs 回收僵死报表任务 N 个, then nothing lands in the DB — every rewrite rolled back on session close"
  - "Worker leaks one DB connection per job until `remaining connection slots are reserved for roles with SUPERUSER` surfaces on an unrelated command"
root_cause: framework_semantics_misread
resolution_type: code_fix
framework_version: arq 0.28 / SQLAlchemy 2.0.52 async / PostgreSQL 18.6
related_components:
  - data_model
  - api_layer
  - testing_framework
tags:
  - arq
  - background-worker
  - retry-semantics
  - cron
  - session-lifecycle
  - commit-boundary
  - silent-failure
---

# ARQ 0.28 worker: five silent failure modes from misread framework semantics

All five were live in this repo (bug-163..170, fixed 2026-10-13..14). None produce an
error at the point of misuse; each surfaces far away or never. ARQ's source is the
only reliable reference — its defaults are guesses waiting to happen.

## 1. ARQ does not retry ordinary exceptions — ever

`arq/worker.py:612-637` branches on exactly three exception types: `Retry`,
`asyncio.CancelledError`, `RetryJob`. Everything else takes
`else: failed, finish = True` — the job dies on the spot.

So `WorkerSettings.max_tries = 3` guarantees nothing by itself: it bounds how many
times a `Retry` **may** recur; it does not trigger retries. A task body raising
`PcsError`/`RuntimeError` runs once, full stop.

**Fix pattern** (both task bodies):

```python
if attempt_no < MAX_TRIES:
    raise Retry(defer=RETRY_DEFER_S) from e   # the ONLY thing ARQ retries
raise      # attempts exhausted: re-raise the original so ARQ records the cause
```

Two traps around this:

- `Retry` subclasses `RuntimeError`, so `pytest.raises(RuntimeError)` passes for
  both branches. Deleting the `if attempt_no < MAX_TRIES` guard makes **zero**
  existing assertions red — pin the *types* separately
  (`test_retry_and_final_failure_are_distinguishable_exceptions`).
- Final state (`status = FAILED`) must be written only on the last attempt; a
  mid-retry FAILED is a fake terminal the user sees before the retry succeeds.

## 2. `enqueue_job` takes a function *name string*

`arq/connections.py` serializes the first argument as `function_name`; the worker
looks it up via `self.functions[function_name]` — a dict keyed by `str`. Passing
the function object enqueues fine and the API returns 202, then the worker logs
`function <function ...> not found` and fails the job. Still import the function
in the enqueue helper so a typo explodes *before* enqueue, not after.

Unrecognized kwargs (e.g. `max_tries=3`) are silently forwarded as **task
arguments** — no error, no effect. `Retry` is an exception class, not a config
object; `retry=Retry(max=3)` is a `TypeError`.

## 3. `CronJob(second=None)` means every second, not "unrestricted"

`arq/cron.py:_get_next_dt` starts with `if v is None: continue` — `None` means
the field does not participate, so `minute={3,33}, second=None` fires at
:03.00, :03.01 … :03.59. Pin an explicit `second=0` and count firings in a test
over a simulated two hours.

## 4. The task's session: who opens it, who closes it, who commits

Three separate defects, one theme — the ARQ boundary is a **process** boundary,
not a request boundary, so nobody closes or commits for you:

- **Session leak**: a task opening its own session must close it. Per-job leak
  exhausts PG connection slots and the error lands on an unrelated command
  (e.g. a migration). Fix structurally: one `@asynccontextmanager session_scope`
  in `worker.py` that owns `close()`, so "remembering" is not required.
- **Cron entry took a bare session** via `ctx["session_factory"]()` — never
  closed (48 leaks/day at two runs/hour), and the reclaimers it called only
  `flush()`ed. Every FAILED rewrite and REPORT_FAILED audit row rolled back on
  release: the reclaimer was *entirely inert* while logging success.
- **flush vs commit**: a state write after `db.commit()` opens a **new**
  transaction that the scope's rollback discards — silently. Terminal states and
  audits must be written *before* the commit they belong to.

Testing note: proving "committed, not flushed" needs an observation point the
default fixtures cannot provide — see
`testing-issues/sqlite-staticpool-hides-uncommitted.md`.

## 5. Commit ordering across the enqueue boundary

The endpoint must **commit its bookkeeping row before enqueueing**, and must
pre-select the task id to do so (`enqueue_job` accepts `_job_id`;
`job_id = _job_id or uuid4().hex` in `arq/connections.py:148`). Enqueue-first
opens three windows: the worker finishes and updates a row that does not exist
yet (link silently lost, polling 404s on a finished job), an endpoint failure
between enqueue and commit leaves a file with no audit row, and the linking
UPDATE has no rowcount check to notice. When enqueue fails *after* the commit,
mark the just-committed row FAILED with the enqueue error — otherwise it hangs
QUEUED for the reclaimer to mislabel 15 minutes later.

## The meta-rule

Every one of these was verified by reading `arq/`'s source or running a real
Redis worker, not by reasoning about plausible behavior. ARQ's documentation
does not foreground any of them. When integrating ARQ (or any queue), the
source of `worker.py`'s retry branch and `connections.py`'s serialization is
short and decisive — read it before trusting retries, ids, or cron fields.
