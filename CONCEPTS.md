# Concepts

> Shared domain vocabulary for this project — entities, named processes, and status
> concepts with project-specific meaning. Seeded with core domain vocabulary, then
> accretes as ce-compound and ce-compound-refresh process learnings; direct edits are
> fine. Glossary only, not a spec or catch-all.

## Schema and migrations

### Schema drift
A disagreement between what the ORM models declare and what the migration chain actually
created in the database. It is directional: either the migration is missing something the
ORM declares, or the database carries something the ORM does not.

Drift does not announce itself. A missing table breaks loudly because the query names a
table nobody created; a missing column or constraint stays invisible because nothing
between the ORM and the database checks that the two agree. Two properties make it
persistent:

- **The test suite cannot see it.** When tests materialize their schema from ORM metadata
  rather than by running migrations, the test database is a rendering of the ORM and
  therefore agrees with the ORM by definition. A green suite is not evidence about the
  real database.
- **The drift guard has a precondition.** The guard refuses to run while the database is
  behind the code's head revision. A migration committed but not yet applied does not make
  the guard pass — it stops the guard from running at all, which reads identically to
  "nothing to report" unless you check that it executed.

### Idempotent migration guard
An existence flag on a migration operation (`create_index` / `drop_index` / `drop_table`)
that makes re-running the migration harmless. Applied in pairs — drop-then-create — the
pair is idempotent without either half being independently safe.

Not every operation can be guarded. Constraint-creation operations accept an existence
flag at the call site but discard it, so a constraint migration that "has a guard" may
guard nothing. **A guard that is accepted silently is worse than no guard**, because it
reads as protection. Verify that the flag changes the emitted behavior, not just that the
call succeeds.

### Constraint naming convention
Generated names for indexes, unique constraints, foreign keys, and primary keys, derived
by template from the table and column names rather than authored by hand. Because the
names are derived, they cannot be guessed correctly — a hand-written name that looks
reasonable will not match what the ORM produces, and the mismatch is itself reported as
drift even when the constraint is present and correct.

When adding constraints in a migration, derive the name the convention produces. Use the
template expansion, not a plausible guess.

## Descriptions and comments

### ORM column comment
The description string declared alongside a mapped column in the data model. Read by
anyone inspecting the model source. It is documentation attached to code, not schema.

### Pydantic field description
The description carried by a schema field, which is what serializes into API
documentation and is the only carrier for the shape of a structured payload stored in a
single database column. This is the project's single source of truth for **description
text**.

### Column comment (database)
A description string stored on the column inside the database, carrying no runtime
behavior. It is written and compared by the migration toolchain, entirely separately from
the two description texts above.

## Audit columns

### Mixin audit columns
The creation and update bookkeeping columns a shared base class contributes to every model
that inherits it: who created the record, when it was created, when it was last updated.
They are part of the model's column set but appear nowhere in the individual model's own
body.

This is the structural reason a hand-written table migration can omit them: enumerating a
model's columns by reading its own declaration misses everything the base class supplied.
The created-at and updated-at columns are often written out from a comment naming them,
which makes the omission invisible — the comment names the ones the author noticed.

*Avoid:* audit fields, tracking columns

### Creator attribution
The identifier recorded on a record at creation. Nullable by design: records created by
system processes or before the actor was known carry no creator. Distinct from *audit
columns* generally, which also cover update timestamps.

## Relationships

- Every model that records who created it does so through **mixin audit columns**;
  standalone models without the base class carry the columns in their own body instead.
- **ORM column comment**, **Pydantic field description**, and **column comment (database)**
  are three independent texts. Only the first two are held to a consistency rule; the
  third is owned by the migration toolchain and is not part of the description contract.