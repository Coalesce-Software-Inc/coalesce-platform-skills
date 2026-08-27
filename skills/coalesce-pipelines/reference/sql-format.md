<!-- coalesce-node-managed: true -->
# Node SQL Format — V2 (.sql) vs V1 (.yml)

`coa describe sql-format` and `coa describe concepts` are the source of truth.

## Two formats — choose by where the node's value lives

Both formats are first-class and both are freely authorable (files + CLI or
the Coalesce UI). Neither is "legacy". Pick by what carries the node's value:

- **V2 — `.sql`, `fileVersion: 2` — the node's value is its SQL.** Transforms,
  metrics, joins, business logic. Columns AND data types are inferred from the
  SELECT (aggregates included), so the rendered DDL is fully typed. The natural
  format for file-based and agent authoring. File at
  `nodes/<LOCATION>-<NAME>.sql`.
- **V1 — `.yml`, `fileVersion: 1` — the node's value is its configuration.**
  Source nodes (generate with `coa sources add`, never by hand) and
  config-driven patterns like SCD2 Dimensions, where business-key +
  change-tracking flags drive a generated merge no one should write by hand.
  Explicit columns with source mappings. Also required for any V1-only node
  type. File at `nodes/<LOCATION>-<NAME>.yml`; see `coa describe schema node`
  and the coalesce-v1-yaml-nodes skill before authoring or editing one.

(Both curated annotations `@isBusinessKey` and `@isChangeTracking` work in V2
as well — the choice is about authoring ergonomics, not a capability gap.)

## The silently-empty-columns trap

A V2 `.sql` node REQUIRES a node type whose `nodeTypes/<ID>/definition.yml` has
`fileVersion: 2`. If `@nodeType` points at a V1 (or absent-fileVersion) type,
the node still loads but its columns are **SILENTLY EMPTY** (`columns: []`) —
`coa create`/`coa run` then emit broken DDL/DML with no error. The built-in
common types (Source, Stage, View, Dimension, Fact, Persistent Stage) are V1;
using them in a `.sql` file triggers this trap. If a needed V2 node type does
not exist, install one before authoring the node: creating a NEW V2 type in a
workspace that has none of that layer (greenfield) is sanctioned without asking;
upgrading a V1 type that existing nodes already use changes their DDL/DML, so
that STILL requires approval. Never silently write a `.sql` node against a V1
type. Recipe + validate step: coalesce-workspace-config ("Installing a V2 node
type") and `coa describe node-types`.

## File naming

- The filename — `nodes/<LOCATION>-<NAME>.sql` or `.yml` — sets the node's
  location and name. A bare `@location` annotation is ignored. `nodes/` is
  flat (no subdirectories).
- Filenames are case-sensitive and NAME must be unique:
  `nodes/<LOC>-<NAME>.yml` and `nodes/<LOC>-<NAME>.sql` cannot coexist.
- By convention names are UPPER_SNAKE_CASE — `coa` does not enforce casing,
  but match the repo. Typical conventions: `SRC-<TABLE>` for sources,
  `TARGET-STG_<NAME>` for stages, `TARGET-<NAME>` for derived nodes.

## Required top annotations (before any SQL)

- `@id("<UUID>")` — stable, immutable identifier. PREFER a fresh UUID v4 for
  new nodes. NEVER reuse or modify an existing `@id` (node or column).
- `@nodeType("<TypeID>")` — must match a node type in `nodeTypes/<ID>/` (the
  ID after the last dash in the folder name) or a package node type ID
  (e.g. `"dynamic-tables:::347"`).

Keep `@id` and `@nodeType` as the first lines. Match the existing `.sql`
nodes: only those two annotations precede the SQL (no bare `fileVersion`
line).

### Write the annotations BARE — never as SQL comments

`coa` reads `@id`/`@nodeType` only when they are **bare** lines (no `--`, no
`/* */`). They look like they belong in a comment because a bare `@id("…")`
line is not itself valid Snowflake SQL — but do NOT "fix" that by commenting
them. A `.sql` node whose annotations are commented out has, as far as `coa` is
concerned, NO `@id` and NO `@nodeType`: the node is **silently dropped from the
graph** — `coa validate` still reports 0 errors (the node simply isn't there),
`coa create` never builds it, and lineage is missing. This is the single most
common way a "finished" node quietly does nothing.

```sql
-- WRONG — commented out; coa ignores these, node is silently dropped
-- @id("b2c3d4e5-f6a7-8901-bcde-f12345678901")
-- @nodeType("STG_V2")
SELECT ...
```

```sql
-- RIGHT — bare annotations on the first two lines
@id("b2c3d4e5-f6a7-8901-bcde-f12345678901")
@nodeType("STG_V2")
SELECT ...
```

After writing a node, confirm the node actually loaded — do not trust a green
`coa validate` alone. Run `coa create --dry-run --verbose --include "{ NODE }"`
and check the node appears with its columns rendered; "0 nodes matched" or empty
columns means the annotations were not read (commented out, missing, or a V1
`@nodeType`).

## References

Double-quoted Jinja macros with BOTH args — there is NO name-only /
single-arg form. Never hardcode `db.schema.table`.

- `{{ ref("LOCATION", "NODE_NAME") }}` — resolves to the table AND creates a
  lineage edge.
- `{{ ref_no_link("LOCATION", "NODE_NAME") }}` — resolves, no edge (e.g. the
  node's own table inside a template).
- `{{ ref_link("LOCATION", "NODE_NAME") }}` — edge only, emits no SQL.

PREFER double quotes for NEW or edited refs (per `coa describe sql-format`).
Refs are quote-agnostic in practice — existing repos often use single quotes
(`{{ ref('LOC','NAME') }}`) and `coa` resolves either style
case-insensitively. Leave existing valid single-quoted refs alone; do not
rewrite them just to change quote style.

## Column annotations — a native set plus what the node type declares

Placed AFTER the alias and BEFORE the comma, e.g.
`CREATED_AT @isChangeTracking,`.

**Native annotations** (always available):

- `@isBusinessKey` — required on Persistent Stage + Dimension (optional on
  Stage); the MERGE/SCD key; **affects DDL**.
- `@isChangeTracking` — Persistent Stage change detection; **affects DML**.
- `@id("col-id")` — column lineage; metadata only.
- `@description("text")` — docs; metadata only.

**Declared annotations**: a node type's `nodeMetadataSpec` may carry an
`annotations:` block declaring additional node- and column-level annotations
(e.g. a data quality test library). Declaring a column annotation makes the
parser accept it inline and flatten it onto the column object in template
context (`{parameters: [...]}`, or `true` for parameterless). Check the node
type's `definition.yml` for what is legal on that type.

Hazards, all verified:

- **An UNDECLARED column annotation silently zeroes out ALL columns of the
  node** — validate may stay green while create renders empty DDL. If a node's
  columns vanish, check for a typo'd or undeclared annotation first.
- Repeated annotations collapse (last one wins), even with
  `allowsMultiple: true`. Pass lists variadically in ONE call:
  `@accepted_values("A", "B", "C")`.
- An annotation named `unique` collides with the SQL keyword and fails
  validation; use a different name (or a parameterized form like
  `@tests("unique")` where the type declares it).
- Node-level declared annotations (other than `@materializationType` and
  `@description`) do NOT currently reach template context — declaring them
  documents intent but templates cannot act on them locally.

Do NOT invent annotations that are neither native nor declared by the node
type: `@isSurrogateKey`, `@pii`, `@synqMonitor` are NOT in the spec.
(`isSurrogateKey` exists as a boolean column field in the V1 node JSON schema —
legitimate in a `.yml` node — but it is NOT a `.sql` column annotation.)

## SQL conventions

- Target Snowflake SQL dialect (unless the repo's `data.yml` says otherwise).
- Aliases in hand-authored SELECTs are bare UPPER_SNAKE_CASE identifiers
  (e.g. `SUM(QUANTITY * UNIT_PRICE) AS LINE_TOTAL`); the source expression may
  quote the underlying column (`T."COL"`). Double-quoted aliases appear in
  node-type Jinja templates that emit generated DDL, and in some existing
  nodes — match the file you are editing.
- Preserve existing column ordering; keep changes minimal.
- ENUMERATE columns explicitly in a V2 node's SELECT — never `SELECT *`. A
  V2 node type infers its column set by parsing the SELECT; `SELECT *` leaves
  nothing to parse, so `coa create` renders a zero-column table (degenerate
  DDL) even though `coa validate` stays green. If the task says "stage every
  column 1:1", read the source's columns (`coa describe` or the source `.yml`)
  and list each one. Confirm with `coa create --dry-run --verbose` that the
  rendered DDL actually projects the columns.

## Example V2 node

```sql
@id("b2c3d4e5-f6a7-8901-bcde-f12345678901")
@nodeType("Dimension")
SELECT
    CUSTOMER_ID @isBusinessKey,
    EMAIL @description("primary contact"),
    UPDATED_AT @isChangeTracking
FROM {{ ref("STG", "STG_CUSTOMERS") }}
```

(`"Dimension"` stands in for a real V2 node type ID from `nodeTypes/` — the
built-in `Dimension` is V1.) Note the first two lines are BARE — no leading
`--`. That is deliberate and required (see "Write the annotations BARE" above).
