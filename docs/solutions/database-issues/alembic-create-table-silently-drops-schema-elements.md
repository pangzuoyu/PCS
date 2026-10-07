---
module: pcs-backend data layer — Alembic migration chain
date: 2026-10-07
problem_type: database_issue
component: database
severity: high
symptoms:
  - "psycopg.errors.UndefinedColumn: column \"created_by\" of relation \"user_projects\" does not exist, on every ORM INSERT, raised from real Postgres while the test suite is green"
  - pg_constraint reports zero foreign keys on user_projects — 8 constraints present, all PK / UNIQUE / NOT NULL
  - "Full suite green (3954 passed, 0 failed) while the real database rejects the same INSERT"
  - "alembic check aborts with \"Target database is not up to date\", so the drift guard never reports anything at all"
root_cause: data_integrity
resolution_type: migration
framework_version: SQLAlchemy 2.0.52 / Alembic 1.19.1 / PostgreSQL 18.6 (observed on the dev DB; note the project's declared container is postgres:16-alpine, so the running dev DB does not match it)
related_components:
  - data_model
  - testing_framework
  - tooling
tags:
  - alembic
  - migration
  - schema-drift
  - foreign-key
  - sqlalchemy
  - postgres
  - inherited-columns
  - test-fixture-blind-spot
---

# Hand-written `op.create_table` silently drops inherited columns and foreign keys

## Problem

A hand-written Alembic `op.create_table(...)` lost two kinds of schema element without
any error: an inherited mixin column that was never declared, and all four foreign keys,
which were passed as bare positional arguments that Alembic discarded silently. The
entire test suite stayed green through both.

This is a general Alembic hazard, not a quirk of one table: `op.create_table(*args)`
forwards its arguments to the DDL compiler, which dispatches on each object's type.
Anything that is neither a `Column` nor a `Constraint` is dropped without a warning.

## Symptoms

On real Postgres, any INSERT through the ORM failed:

```
psycopg.errors.UndefinedColumn: column "created_by" of relation "user_projects" does not exist
```

The failing write is `UserProjectService.grant_project_access` —
`pcs-backend/app/services/user_project_service.py:81` — which writes the authorization
table read by the cross-project IDOR guard (`pcs-backend/app/api/v1/_guard.py:42`).
Grants could not be written, so the guard had nothing to read.

The missing foreign keys were silent even at runtime. `pg_constraint` reported zero FK
constraints on `user_projects`, and SQLAlchemy's inspector reflected `[]`. The
consequences were data-integrity only, with no exception:

- a grant could point at a nonexistent `user_id` / `project_id`, leaving permanent orphans
- `ondelete="CASCADE"` never fired — deleting a user or project left grants in effect
- because login derives `user_id` deterministically as `uuid5(NAMESPACE_DNS, username)`
  (`pcs-backend/app/api/v1/auth.py:264`), a recreated account with the same username got
  the same id and silently inherited the stale grants

## What Didn't Work

**Concluding "it's nullable, so inserts are fine."** Reading `information_schema.columns`
showed `is_nullable = YES` for `created_by`, and the natural inference was that a nullable
column is optional. That inference was wrong, and was caught by actually running the
INSERT rather than reasoning about it. SQLAlchemy's ORM INSERT puts no-default nullable
columns in the column list:

```sql
INSERT INTO user_projects (id, user_id, project_id, role_in_project,
                           granted_at, created_by, created_at, updated_at)
VALUES (...)
```

Nullability governs what value may be stored, not whether the column is named at all.
(UPDATE paths were unaffected, since the ORM only SETs dirty fields — which is why the
defect surfaced only on new grants.)

**Fixing the FKs with raw SQL in the unquoted two-part form.** Writing
`REFERENCES users.user_id` raised `psycopg.errors.InvalidSchemaName: schema "users" does
not exist`. The message is actively misleading: it reads as though a schema were missing,
but the table exists — that identifier form is simply not valid here. It reproduced
identically on a temp table, which ruled out the table being at fault. Both
`REFERENCES users(user_id)` (function form) and `REFERENCES "users" ("user_id")` (quoted
form) worked.

**Believing `alembic check` was passing.** It was not running. It refuses with "Target
database is not up to date" whenever the database revision trails the code head, so a
committed-but-unapplied migration blocked the guard entirely. Both defects surfaced only
after that migration was applied. The guard had not been reporting clean — it had not been
reporting at all.

## Solution

Two migrations, both idempotent so a re-run is harmless.

**Restore the missing inherited column** —
`pcs-backend/alembic/versions/p7_s5_006_user_projects_created_by.py`:

```python
def upgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS created_by UUID")

def downgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS created_by")
```

Bare `uuid`, nullable, no FK, no `server_default`, no comment — matching
`TimestampMixin.created_by` at `pcs-backend/app/models/mixins.py:35`, so the fix
introduces no secondary drift.

**Restore the 4 foreign keys** —
`pcs-backend/alembic/versions/p7_s5_007_user_projects_fks.py`:

```python
_FOREIGN_KEYS = (
    ("fk_user_projects_user_id_users", "user_id", "users", "user_id", "CASCADE"),
    ("fk_user_projects_project_id_projects", "project_id", "projects", "project_id", "CASCADE"),
    ("fk_user_projects_granted_by_users", "granted_by", "users", "user_id", None),
    ("fk_user_projects_revoked_by_users", "revoked_by", "users", "user_id", None),
)

def upgrade() -> None:
    for name, column, ref_table, ref_column, ondelete in _FOREIGN_KEYS:
        op.drop_constraint(name, _TABLE, type_="foreignkey", if_exists=True)
        kwargs = {"ondelete": ondelete} if ondelete else {}
        op.create_foreign_key(name, _TABLE, ref_table, [column], [ref_column], **kwargs)
```

The drop-then-create pair is naturally idempotent: a re-run drops whatever exists and
recreates it.

**The original buggy call**, from
`pcs-backend/alembic/versions/p7_open_010_user_projects_blocker3.py:27-44`:

```python
op.create_table(
    "user_projects",
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("user_id", UUID(as_uuid=True), nullable=False),
    # ...
    # Timestamps from TimestampMixin
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKey("users.user_id", ondelete="CASCADE", name="fk_user_projects_user_id"),
    sa.ForeignKey("projects.project_id", ondelete="CASCADE", name="fk_user_projects_project_id"),
    sa.ForeignKey("users.user_id", name="fk_user_projects_granted_by"),
    sa.ForeignKey("users.user_id", name="fk_user_projects_revoked_by"),
)
```

Two independent faults in one call. The `# Timestamps from TimestampMixin` comment is
doing the reader's thinking: it names two of the mixin's three columns and gives no hint
that a third exists. And the four `sa.ForeignKey(...)` objects at the end read as though
they were part of the column definitions above, but they are neither `Column` nor
`Constraint`.

## Why This Works

**The FK loss is a silent argument-type mismatch.** A `sa.ForeignKey` is a
*referenced-target descriptor* — it belongs inside a `Column`, where the compiler reads it
via `column.foreign_keys` to emit `REFERENCES`. Handed in as a top-level positional
argument, no dispatch branch matches and the object is dropped. Nothing about the call is
invalid enough for Alembic to complain about; the DDL is just quietly wrong.

**The `created_by` loss is an inherited-column transcription gap.**
`UserProject(TimestampMixin, Base)` at `pcs-backend/app/models/project.py:160` declares
only the columns in its own body; the three audit columns come from the mixin at
`pcs-backend/app/models/mixins.py:35`. Anyone transcribing columns by reading the class
body sees the eight local columns and nothing else. The two that *were* declared were
added by hand from the comment, so it looked complete. A prior catch-all migration,
`p6_5_006_orm_db_drift_final_fix`, had swept the database with
`ADD COLUMN IF NOT EXISTS` for missing mixin columns, but `user_projects` was created
later (P7-7+ BLOCKER-3) and fell outside that sweep.

**The test suite could not see either defect, structurally.**
`pcs-backend/tests/conftest.py:113` builds the test schema from the ORM, not from
migrations:

```python
engine = create_async_engine("sqlite+aiosqlite:///:memory:")   # conftest.py:91
...
async with engine.begin() as conn:
    await conn.run_sync(SA_Base.metadata.create_all)             # conftest.py:113
```

`create_all` materializes `SA_Base.metadata`, so every ORM column exists by construction
and every ORM FK is emitted correctly. **The test database is a rendering of the ORM, so it
agrees with the ORM by definition.** This is the sharp edge of the setup: a missing
*table* shows up, because the query would name a table `create_all` never made — but a
missing *column* or *constraint* stays green, because the tests read the same metadata the
ORM does and never touch the migration chain. A green suite is therefore not evidence
about the real database.

**Verification that distinguished the two fixes.** Re-running the same INSERT in a
rolled-back transaction against real Postgres moved the failure from `UndefinedColumn` to
`ForeignKeyViolation`. That progression is the actual proof: the first error meant the
column was absent; the second meant the column now exists *and* referential integrity is
being enforced — exactly what was missing before. `pg_constraint` then confirmed all four
FKs with `ON DELETE CASCADE` on `user_id` and `project_id`.

**Constraint names had to be derived, not copied.** `pcs-backend/app/db/base.py:10`
defines a naming convention:

```python
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

which expands the first FK to `fk_user_projects_user_id_users`. `alembic check` compares
names as well as shapes, so reusing the hand-written names would have left the drift
reported even with the constraints present.

## Prevention

**Write FKs inside the column.** This is the correct form, and the only form
`op.create_table` honors:

```python
sa.Column("user_id", UUID(as_uuid=True),
          sa.ForeignKey("users.user_id", ondelete="CASCADE",
                        name="fk_user_projects_user_id"),
          nullable=False),
```

**Checklist for any hand-written `op.create_table`:**

- Enumerate every column, **including ones inherited from mixins**. Read the mixin class,
  not just the target class body.
- Never pass a bare `ForeignKey` as a positional argument to `op.create_table`. Every FK
  must be nested inside its `Column`.
- Derive constraint names from `NAMING_CONVENTION`, not by hand — otherwise
  `alembic check` reports drift on a schema that is actually correct.
- Prefer `op.create_foreign_key(...)` over raw
  `ALTER TABLE ... ADD CONSTRAINT ... REFERENCES`. Alembic handles identifier quoting;
  the unquoted two-part `REFERENCES users.user_id` form raises `InvalidSchemaName`.
- Pair `op.drop_constraint(..., if_exists=True)` with `op.create_foreign_key(...)` so the
  migration is safe to re-run.
- A trailing comment naming a mixin is not a substitute for reading the mixin — it names
  the columns the author noticed, not the columns that exist.

**Ask the database, not the ORM.** The ORM metadata said four FKs existed; only the
database could refute it. These are what settled it:

```sql
SELECT conname, contype FROM pg_constraint
WHERE conrelid = 'user_projects'::regclass;
```

```python
from sqlalchemy import inspect
inspect(engine).get_foreign_keys("user_projects")   # returned []
```

**A real-DB check is the only reliable gate when tests build schema from ORM metadata.**
If `conftest.py` uses in-memory SQLite plus `create_all`, the suite's silence about
migration drift carries no information. Run `alembic check` against real Postgres as a
separate manual gate after touching anything under `pcs-backend/alembic/versions/`.

**Know `alembic check`'s failure modes before trusting its verdict:**

- It **exits 255, not 1**, when it detects drift. A wrapper step that tests for exit code
  1 will read a real finding as a pass.
- It exits non-zero with "Target database is not up to date" when the DB revision trails
  code head. **That is a failure of the check, not a pass.** Confirm
  `uv run alembic current` matches `uv run alembic heads` before reading any result.
- "No output" is meaningful only once you know it ran. This defect was initially recorded
  as "guard green" when the guard had never executed.

**This repo's static gate.** `pcs-backend/scripts/check_migration_idempotency.py` already
walks `ast.Call` nodes and already special-cases `op.create_table` (it maps the op to `[]`
because `create_table` takes no idempotency keyword). A positional-arg-type check belongs
there and is nearly free — it is pure AST, has nothing to do with the metadata comparison
that made a static *column-coverage* checker impractical in this repo.

## Related records

The full incident is recorded elsewhere in the repo; this doc consolidates and generalizes
it rather than adding new findings.

- `.wolf/buglog.json` — `bug-143` (missing `created_by`), `bug-144` (dropped FKs),
  `bug-142` (a guard script that reported OK forever because it matched substrings in a
  context window instead of parsing the call structure — the same epistemics: an API
  assumed to work a certain way that quietly did nothing)
- `TODOS.md` — the drift write-ups, and the recorded rejection of a static *column
  coverage* checker (that rejection is scoped to column coverage, not to argument-type
  checks)
- `CLAUDE.md` (repo root) — the standing 「漂移盲区」 rule this doc supplies the concrete
  failure modes for; also `.wolf/cerebrum.md` under Do-Not-Repeat

Two related mechanisms that also failed to catch this. Static review with a dedicated
data-migration stage ran three times over this work (`docs/ce-code-review/`) and did not
flag either defect. Notably, those same diffs show **other** migrations using the correct
nested form —

```python
sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.project_id"), nullable=False),
sa.Column("created_by", UUID(as_uuid=True), nullable=True),
```

— so the omission on `user_projects` is an outlier rather than the house style. That is
the reassuring half of the finding; the unsettling half is that a review pass can read
straight past a construct it has seen correctly written dozens of times.