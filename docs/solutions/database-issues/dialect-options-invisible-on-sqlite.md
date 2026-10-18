---
module: pcs-backend data layer — multi-tenant uniqueness constraints
date: 2026-10-18
problem_type: database_issue
component: database
severity: high
symptoms:
  - "Two company-level rows (project_id IS NULL, same name) coexist despite UNIQUE(project_id, name) — Postgres treats NULLs as distinct, so the constraint never fires for them"
  - "Two ACTIVE styles in one scope coexist; the service-layer 'check current ACTIVE first' is lock-free so concurrent requests both pass it"
  - "After adding postgresql_where to a partial index, SQLite tests start failing IntegrityError on rows Postgres accepts — the test DB is stricter than production"
  - "alembic check exits 0 on the dev DB while the same command exits 255 on the second database — a constraint exists in one and not the other"
root_cause: dialect_divergence
resolution_type: migration
framework_version: SQLAlchemy 2.0.52 / Alembic 1.19.1 / PostgreSQL 18.6 / SQLite (test)
related_components:
  - data_model
  - testing_framework
tags:
  - postgres
  - nulls-not-distinct
  - partial-unique-index
  - multi-tenant
  - sqlite-blindspot
  - dialect-options
  - cross-db-drift
---

# Dialect-specific constraint options: three ways SQLite tests go blind (or lie)

## 1. `NULLS NOT DISTINCT` — invisible on SQLite, load-bearing on PG

`UNIQUE (project_id, name)` with nullable `project_id` (company-level scope)
enforces **nothing** for company rows: PG considers NULLs mutually distinct, so
two `(NULL, '泵数据表')` insert fine. The lock-free application check
(`SELECT ... WHERE status='ACTIVE'`) lets concurrent requests both see "none"
and both insert.

Fix: `postgresql_nulls_not_distinct=True` on the UniqueConstraint **and** a
migration. Unit tests cannot witness the behavior — the option is
PG-dialect-only and SQLite ignores it — so behavioral proof must run on the
real DB:

```
第一条公司级定义 'X'  : INSERT 0 1
第二条同名           : ERROR: duplicate key value violates unique constraint
换个名字             : INSERT 0 1
```

PG has no `ALTER CONSTRAINT`: the migration must `DROP CONSTRAINT IF EXISTS`
then re-`ADD` idempotently (query `pg_constraint`; PG lacks
`ADD CONSTRAINT IF NOT EXISTS`). Check for duplicates first — `ADD` fails
outright if any exist; put the check SQL in the migration docstring rather
than pretending the migration handles it. The downgrade must not
unconditionally re-ADD the old form either: the constraint may already be the
new one (manual fix / double run), and a duplicate-name ADD turns the rollback
into the failure it was meant to undo.

## 2. `postgresql_where` without `sqlite_where` — tests stricter than production

A partial unique index declared with only `postgresql_where=text("status = 'ACTIVE'")`
compiles on SQLite **without the predicate**:

```
CREATE UNIQUE INDEX uq_report_styles_one_active
    ON report_styles (report_type, project_id)          <- no WHERE
```

So the test DB constrains **all** rows while production constrains ACTIVE
only. Two SUPERSEDED versions in one scope (revise twice) pass on PG and fail
in tests — a "test red, prod green" inversion that only detonates when someone
writes the revise test. SQLite supports partial indexes: add
`sqlite_where=text("status = 'ACTIVE'")` and the semantics align. What remains
unalignable is `NULLS NOT DISTINCT` (no SQLite syntax) — company-scope
uniqueness is simply unverifiable in unit tests for this constraint family.

## 3. Cross-database drift: `alembic check` only audits the DB you're connected to

The command compares ORM ↔ the schema of the connection in hand, **not** ORM ↔
what the migrations should produce. A constraint that exists only because a
past session hand-applied it to the dev DB makes `check` exit 0 there and exit
255 on every other database. "43 items → 0" recorded on 2026-10-07 was true on
exactly one database: the cleanup back-filled ORM declarations against the dev
DB where the constraints already lived (`future_dated_forbidden_chk` had never
been created by any migration — pcs had it, pcs_test did not).

Rules that follow:

- Claiming "migrations hold elsewhere" requires running `alembic check` on
  **each** database.
- Fix direction matters: "DB has it, ORM lacks the declaration" (the
  `remove_constraint` reading) is the opposite case from "ORM declares it, no
  migration creates it". The latter needs a new idempotent migration —
  deleting the ORM declaration to silence the check would remove a real
  constraint from the next fresh database.
- Both databases of this repo now sit at head with `check` exit 0; the
  pcs-specific constraint was backfilled by migration `p8_008`.

## One template for all three

Declare the intent once in ORM with **every** dialect variant spelled out
(`postgresql_nulls_not_distinct` + `postgresql_where` + `sqlite_where`), ship
the idempotent migration, and prove behavior on each real database — the unit
suite's engine cannot see any of it.
