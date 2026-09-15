<!-- coalesce-node-managed: true -->
# Node File Format — SQL nodes (.sql) and YAML nodes (.yml)

`coa describe sql-format` and `coa describe concepts` are the source of truth.

## Two kinds of node — the node type's fileVersion decides

Coalesce has two kinds of node type, and every node takes the kind of its
type. Both are first-class and both are freely authorable (files + CLI or the
Coalesce UI). Neither is "legacy". The hard rule: Source nodes are always
YAML `.yml`; for every other node, author a SQL `.sql` node when a SQL node
type exists for the target node type, otherwise author a YAML `.yml` node.
The `fileVersion` in the type's `definition.yml` decides this, never the
platform. A workspace whose node types are all YAML authors all of its
transformation nodes as YAML, and that is supported, not a workaround.

- **SQL node — `.sql`, on a SQL node type (formerly "V2"; `fileVersion: 2`
  in the type's `definition.yml`).** The node's value is its SQL: transforms,
  metrics, joins, business logic. Columns AND data types are inferred from the
  SELECT (aggregates included), so the rendered DDL is fully typed. The natural
  format for file-based and agent authoring. File at
  `nodes/<LOCATION>-<NAME>.sql`.
- **YAML node — `.yml`, on a YAML node type (formerly "V1"; `fileVersion: 1`
  or absent).** The node's value is its configuration: Source nodes (generate
  with `coa sources add`, never by hand), config-driven patterns like SCD2
  Dimensions where business-key + change-tracking flags drive a generated
  merge no one should write by hand, and every transformation node whose
  target type has no SQL definition. Explicit columns with source mappings.
  File at `nodes/<LOCATION>-<NAME>.yml`; see `coa describe schema node` and
  the coalesce-v1-yaml-nodes skill before authoring or editing one.

Rule of thumb when the target layer has BOTH a YAML and a SQL type available:
the node's value is its SQL → SQL node; its value is its configuration, or it
is a Source node → YAML node. (`@isBusinessKey` and `@isChangeTracking` work
on SQL nodes too — the choice is about authoring ergonomics, not a capability
gap.)

The app still labels the two kinds **Node V1** / **Node V2** in **Build
Settings > Node Types** and shows **V1** / **V2** in the **Version** column;
`coa describe` and `coa validate` messages still say V1/V2 as well. Read
V1 as YAML and V2 as SQL.

## The silently-empty-columns trap

A `.sql` node REQUIRES a SQL node type — one whose `definition.yml` has
`fileVersion: 2`. If `@nodeType` points at a YAML type (`fileVersion: 1` or
absent), the node still loads but its columns are **SILENTLY EMPTY**
(`columns: []`) — `coa create`/`coa run` then emit broken DDL/DML with no
error. The built-in common types (Source, Stage, View, Dimension, Fact,
Persistent Stage) are YAML types; using them in a `.sql` file triggers this
trap. If no SQL node type exists, install one before authoring the node (`coa
install`, then re-check `nodeTypes/` and `.coa/cache/packages/*/nodeTypes/`);
if none is available, author the node as YAML instead. Upgrading a YAML type
that existing nodes already use changes their DDL/DML, so that requires
approval. Never silently write a `.sql` node against a YAML type. Recipe +
validate step: coalesce-workspace-config ("Getting SQL node types") and
`coa describe node-types`.

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
  (e.g. `"base-node-types:::204"`).

Keep `@id` and `@nodeType` as the first lines. Other node-level annotations
(`@description`, `@materializationType`, and whatever the node type declares)
also go above the leading `WITH` or `SELECT`. Match the existing `.sql`
nodes: annotations precede the SQL; there is no bare `fileVersion` line.

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
-- @nodeType("base-node-types:::204")
SELECT ...
```

```sql
-- RIGHT — bare annotations on the first two lines
@id("b2c3d4e5-f6a7-8901-bcde-f12345678901")
@nodeType("base-node-types:::204")
SELECT ...
```

After writing a node, confirm the node actually loaded — do not trust a green
`coa validate` alone. Run `coa create --dry-run --verbose --include "{ NODE }"`
and check the node appears with its columns rendered; "0 nodes matched" or empty
columns means the annotations were not read (commented out, missing, or a YAML
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

`ref()` is the only Jinja a SQL node's body supports. Keep the ref in a
top-level FROM/JOIN or a top-level CTE; a ref buried in a nested subquery may
run fine and still not register as a DAG edge.

## Annotations — a reserved set plus what the node type declares

Node-level annotations sit above the SELECT; column-level annotations are
placed AFTER the alias and BEFORE the comma, e.g. `CREATED_AT @isChangeTracking,`.
Syntax: bare `@name` (a flag), or `@name("value", 2, true)` with positional
literal arguments — strings quoted, numbers and booleans unquoted.

**Reserved annotations** (every SQL node type; validated by Coalesce):

- Node-level: `@id`, `@nodeType` (managed — never edit), `@description("text")`,
  `@materializationType("table"|"view")` (lowercase; defaults to table).
- Column-level: `@description("text")`, `@notNull` (a DDL NOT NULL constraint,
  not a test), `@defaultValue("0")` / `@defaultValue("'NA'")` (quoted for the
  column's type).
- Also accepted on the SQL parser's native set: `@isBusinessKey` (MERGE/SCD
  key; **affects DDL**; required on Persistent Stage + Dimension types),
  `@isChangeTracking` (change detection; **affects DML**), and column
  `@id("col-id")` (lineage; metadata only).

**Declared annotations**: a SQL node type's `nodeMetadataSpec` may carry an
`annotations:` block declaring additional node- and column-level annotations
(e.g. a data quality test library). Values hydrate into template context as
`true` for a bare annotation, `{parameters: [...]}` for a parameterized one,
and an ordered array of those for an annotation declared `allowsMultiple`.
Node-level values land on `config.<name>`; column-level values are flattened
onto the column object as `col.<name>`. Check the node type's `definition.yml`
for what it declares — that is the only list of what its templates act on.
Coalesce's Base Node Types - SQL package, for example, declares `@writeMode`,
`@disableTests`, `@tests`, `@preSQL`, `@postSQL` at node level and column
tests such as `@not_null`, `@uniqueness`, `@accepted_values`, `@min_max`,
`@freshness`, plus `@inHash` for hash keys.

Hazards (verified on coa 7.42.5):

- **An undeclared or misspelled annotation does nothing, silently.** The
  parser accepts any name and hydrates the value under the name as written;
  no template reads it, so the node validates, creates, and runs as if the
  annotation were absent. `coa validate` emits no warning today. When an
  option seems ignored, compare the spelling and casing against the node
  type's `annotations:` block first (declared names are case-sensitive).
- **Multi-value tests: repeat the annotation, never pass several values in
  one call.** `@accepted_values("'A'") @accepted_values("'B'")` renders
  `NOT IN ('A', 'B')`; the variadic form `@accepted_values("'A'", "'B'")`
  renders only the first value with no error (TRA-2486). Same for
  `@rejected_values`, `@preSQL`, `@postSQL`, `@tests`, `@inHash`.
- An annotation named `unique` collides with the SQL keyword and fails to
  parse; that is why the packaged test is `@uniqueness`. Avoid SQL keywords
  as annotation names.
- A declared `default` is documentation only. Nothing applies it at runtime;
  the node type's template supplies the fallback, so omit the annotation to
  get the default rather than writing the default value out.
- A quoted boolean is a string: `@disableTests("false")` is `"false"`, which
  Jinja treats as true. Write `@disableTests(false)` or omit the annotation.
- `coa validate` currently rejects unquoted boolean arguments such as
  `@tests("...", true, "After")` that the runtime accepts (TRA-2483). Treat
  that one error as a known false positive, not as a reason to quote the
  boolean.
- **Macro calls inside the node's SELECT do not render locally.** The Base
  Node Types - SQL README shows `{{ get_hash("HK") }} AS ROW_HASH`; local
  `coa create`/`coa run` type that column `UNKNOWN` and emit the
  self-reference `"ROW_HASH" AS "ROW_HASH"` (TRA-2487). The Coalesce app
  renders it. Until fixed, compute hashes in plain SQL when the node must run
  locally, and tell the user why.

Do NOT invent annotations that are neither reserved nor declared by the node
type: `@isSurrogateKey`, `@pii`, `@synqMonitor` are NOT in the spec.
(`isSurrogateKey` exists as a boolean column field in the YAML node JSON
schema — legitimate in a `.yml` node — but it is NOT a `.sql` column
annotation.)

## SQL conventions

- Target Snowflake SQL dialect (unless the repo's `data.yml` says otherwise).
- Aliases in hand-authored SELECTs are bare UPPER_SNAKE_CASE identifiers
  (e.g. `SUM(QUANTITY * UNIT_PRICE) AS LINE_TOTAL`); the source expression may
  quote the underlying column (`T."COL"`). Double-quoted aliases appear in
  node-type Jinja templates that emit generated DDL, and in some existing
  nodes — match the file you are editing.
- Preserve existing column ordering; keep changes minimal.
- ENUMERATE columns explicitly in a SQL node's SELECT — never `SELECT *`. A
  SQL node type infers its column set by parsing the SELECT; `SELECT *` leaves
  nothing to parse, so `coa create` renders a zero-column table (degenerate
  DDL) even though `coa validate` stays green. If the task says "stage every
  column 1:1", read the source's columns (`coa describe` or the source `.yml`)
  and list each one. Confirm with `coa create --dry-run --verbose` that the
  rendered DDL actually projects the columns.
- Alias every expression. The alias is the column's identity on a SQL node
  (renaming it deploys a new column). If a type comes through as `UNKNOWN`,
  add an explicit cast.

## Example SQL node

```sql
@id("b2c3d4e5-f6a7-8901-bcde-f12345678901")
@nodeType("base-node-types:::204")
@description("Customer dimension staging")
@writeMode("append")
SELECT
    CUSTOMER_ID @isBusinessKey @not_null,
    EMAIL @description("primary contact"),
    UPDATED_AT @isChangeTracking
FROM {{ ref("STG", "STG_CUSTOMERS") }}
```

(`"base-node-types:::204"` stands in for a real SQL node type ID read off
disk; `@writeMode` and `@not_null` work only because that type declares them.)
Note the annotation lines are BARE — no leading `--`. That is deliberate and
required (see "Write the annotations BARE" above).
