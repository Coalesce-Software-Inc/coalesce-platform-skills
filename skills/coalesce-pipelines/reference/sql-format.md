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
is a Source node → YAML node. (A SQL node type can carry the same merge
semantics when it declares `@isBusinessKey` / `@isChangeTracking` — the
Base Node Types - SQL `Dimension` type does — so the choice is about
authoring ergonomics, not a capability gap.)

Since 7.44.0 the app labels the two kinds **YAML** / **SQL** in the **Type**
column of **Build Settings > Node Types** and in the Create Node Type menu,
and `coa validate` messages say YAML / SQL node types. `coa describe` still
says V1/V2, as do releases before 7.44.0: read V1 as YAML and V2 as SQL.

## The wrong-kind node type trap

A `.sql` node REQUIRES a SQL node type — one whose `definition.yml` has
`fileVersion: 2`. If `@nodeType` points at a YAML type (`fileVersion: 1` or
absent), `coa validate` reports `error[extensionVersionMismatch]: ... uses a
.sql file but its node type "<Type>" requires a .yml file`. Validate catches
it; `coa create`/`coa run` do not — skip validate and they render the node's
columns as **EMPTY** (`columns: []`) and emit a zero-column table. The built-in common types (Source, Stage, View, Dimension, Fact,
Persistent Stage) are YAML types; using them in a `.sql` file triggers this
trap. Never assume a name or a kind: the YAML base package `coa init`
installs ships no `Stage` type (its staging type is a YAML `Work`,
`base-node-types:::204`), and SQL node types come from a separate package,
Base Node Types - SQL, that `coa init` does not install (see
coalesce-workspace-config, "Getting SQL node types"). If no SQL node type
exists, run `coa install` and re-check `nodeTypes/` and
`.coa/cache/packages/*/nodeTypes/`; if the SQL package is not declared, offer
to add it via coalesce-install-package (ask first); if none is available,
author the node as YAML instead. Upgrading a YAML type that
existing nodes already use changes their DDL/DML, so that requires approval.
Never silently write a `.sql` node against a YAML type. Recipe + validate
step: coalesce-workspace-config ("Getting SQL node types") and
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
  ID after the last dash in the folder name) or a package node type ID of
  the form `"<alias>:::<id>"`, read verbatim off the materialized
  `definition.yml`.

Keep `@id` and `@nodeType` as the first lines. Other node-level annotations
(`@description`, `@materializationType`, `@deployDisabled`, and whatever the
node type declares)
also go above the leading `WITH` or `SELECT`. Match the existing `.sql`
nodes: annotations precede the SQL; there is no bare `fileVersion` line.

### Write the annotations BARE — never as SQL comments

`coa` reads `@id`/`@nodeType` only when they are **bare** lines (no `--`, no
`/* */`). They look like they belong in a comment because a bare `@id("…")`
line is not itself valid Snowflake SQL — but do NOT "fix" that by commenting
them. A `.sql` node whose annotations are commented out has, as far as `coa` is
concerned, NO `@id` and NO `@nodeType`. `coa validate` still reports **no
problems** — so a green validate proves nothing here — while `coa create`
fails the whole workspace load with `Failed to extract metadata from ...:
Missing @id annotation or @id has no value`, and the app cannot load the node
either.

```sql
-- WRONG — commented out; coa ignores these, and create then fails to load
-- @id("b2c3d4e5-f6a7-8901-bcde-f12345678901")
-- @nodeType("<alias>:::<id>")
SELECT ...
```

```sql
-- RIGHT — bare annotations on the first two lines
@id("b2c3d4e5-f6a7-8901-bcde-f12345678901")
@nodeType("<alias>:::<id>")
SELECT ...
```

After writing a node, confirm the node actually loaded — do not trust a green
`coa validate` alone. Run `coa create --dry-run --verbose --include "{ NODE }"`
and check the node appears with its columns rendered. `Missing @id annotation`
means the annotations were not read (commented out or missing); empty columns
mean a YAML `@nodeType` (validate reports that one as
`extensionVersionMismatch`).

## References

Double-quoted Jinja macros with BOTH args — there is NO name-only /
single-arg form. Never hardcode `db.schema.table`. The LOCATION arg must be
the location the node file actually lives in (`nodes/<LOCATION>-<NAME>.*`);
a ref to the wrong location still validates with exit 0, surfacing only as
`warning[namedDependencyUnresolved]: "LOC"."NAME" is not a node` — treat that
warning as an error and correct the location.

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
placed AFTER the alias and BEFORE the comma, e.g. `CREATED_AT @notNull,`.
Syntax: bare `@name` (a flag), or `@name("value", 2, true)` with positional
literal arguments — strings quoted, numbers and booleans unquoted.

**Reserved annotations** (every SQL node type; validated by Coalesce):

- Node-level: `@id`, `@nodeType` (managed — never edit), `@description("text")`,
  `@materializationType("table"|"view")` (lowercase; defaults to table),
  `@deployDisabled` (bare, no argument: `@deployDisabled(true)` is a
  validate error; excludes the node from cloud deploy, while local
  `coa create`/`coa run` still build it).
- Exception: on a node type whose `nodeMetadataSpec` sets
  `deployStrategy: advanced` (e.g. Base Node Types - SQL Advanced),
  `@materializationType` is NOT reserved in the table/view sense. The node
  type owns its values (declared under `annotations:` with its own
  `options`, e.g. `"transient table"`), Coalesce does not check them, and the
  value still arrives as `node.materializationType`. Read the type's
  declaration before writing one; on any other type, a value outside
  `table`/`view` is a validate error.
- Column-level: `@description("text")`, `@notNull` (a DDL NOT NULL constraint,
  not a test), `@defaultValue("0")` / `@defaultValue("'NA'")` (quoted for the
  column's type).
- `@isBusinessKey` and `@isChangeTracking` are NOT reserved. They are ordinary
  declared annotations: a merge or SCD type declares them and its templates
  read them (the Base Node Types - SQL `Dimension` does); the SQL `Work` type
  does not, so on a `Work` node `coa validate` warns and they are ignored.

**Column identity: the column name IS the column ID. Never write `@id` on a
column.** On a SQL node there are no column ids to mint: each column's
identity (`columnReference.columnCounter`) is its name as the warehouse sees
it — an unquoted alias uppercased (`AS nation_name` → `NATION_NAME`), a quoted
alias exactly as written (`AS "Mixed_Case"` → `Mixed_Case`). That name is
what downstream nodes, lineage, and plan diffing key on, so renaming a column
is creating a new one. The parser does accept `@id("...")` on a column (it is
an undocumented reserved name, so `coa validate` does not warn on it) and
silently re-keys the column's identity to that string; every existing
name-based reference to the column (from YAML nodes and from the app) then
breaks, `coa validate` only warns on the downstream node
(`sourceColumnMissing`), and the downstream load renders `NULL` for that
column instead of failing. `@id` belongs on the node line only. (Author-set
column identity is a future feature, TRA-8; until it ships, nothing should
write column `@id`.) A YAML node downstream of a SQL node references its
columns by that name: see coalesce-v1-yaml-nodes, "Referencing a SQL node's
columns".

**Declared annotations**: a SQL node type's `nodeMetadataSpec` may carry an
`annotations:` block declaring additional node- and column-level annotations
(e.g. a data quality test library). Values hydrate into template context as
`true` for a bare annotation, `{parameters: [...]}` for a parameterized one,
and an ordered array of those for an annotation declared `allowsMultiple`.
Node-level values land on `config.<name>`; column-level values are flattened
onto the column object as `col.<name>`. Check the node type's `definition.yml`
for what it declares — that is the only list of what its templates act on.
In Coalesce's Base Node Types - SQL package, for example, the `Work` type
declares `@writeMode`, `@disableTests`, `@tests`, `@preSQL`, `@postSQL` at
node level and column tests such as `@not_null`, `@uniqueness`,
`@accepted_values`, `@min_max`, `@freshness`, plus `@inHash` for hash keys;
the `Dimension` type (package 2.1.0+) adds `@mergeStrategy`,
`@isBusinessKey`, `@isChangeTracking`, and the SCD system-column flags.

Hazards (verified on coa 7.45.4 with Base Node Types - SQL 2.1.0):

- **An undeclared or misspelled annotation is a `coa validate` warning, and
  it is ignored.** Since coa 7.43.0 `coa validate` reports
  `warning[annotationNameUnknown]: ... @<name> is not a known annotation for
  node type "<Type>"` for any node or column annotation the node type does
  not declare (reserved names excepted); the value hydrates, but no template
  reads it. A warning is a defect (coalesce-pipelines Rule 8): fix the
  spelling and casing against the node type's `annotations:` block (declared
  names are case-sensitive) or remove the annotation. Never declare it on the
  node type yourself to silence the warning — that is shared config. Older coa
  gives no warning at all.
- **Multi-value annotations follow the node type's declaration.** An
  annotation declared `allowsMultiple: true` hydrates one array entry per
  occurrence; without it, repeating the annotation keeps only the last
  occurrence. What a template does with several arguments in one call is the
  node type's choice, so read the annotation's `description`. The current
  SQL `Work` type accepts `@accepted_values("'A'", "'B'")`,
  `@accepted_values("'A','B'")`, and the repeated form alike, and documents
  one call per column; releases before September 2026 rendered only the
  first value of the one-call form (TRA-2486), so on a pinned older release
  repeat the annotation.
- An annotation named `unique` collides with the SQL keyword and fails to
  parse; that is why the packaged test is `@uniqueness`. Avoid SQL keywords
  as annotation names.
- A declared `default` is documentation only. Nothing applies it at runtime;
  the node type's template supplies the fallback, so omit the annotation to
  get the default rather than writing the default value out.
- A quoted boolean is a string: `@disableTests("false")` is `"false"`, which
  Jinja treats as true. Write `@disableTests(false)` or omit the annotation.
- **Macro calls inside the node's SELECT do not render locally.** The Base
  Node Types - SQL README shows `{{ get_hash("HK") }} AS ROW_HASH`; local
  `coa create`/`coa run` type that column `UNKNOWN` and emit the
  self-reference `"ROW_HASH" AS "ROW_HASH"` (TRA-2487). The Coalesce app
  renders it. Until fixed, compute hashes in plain SQL when the node must run
  locally, and tell the user why.

Do NOT invent annotations that are neither reserved nor declared by the node
type: `@pii` and `@synqMonitor` are declared by no packaged type,
`@isSurrogateKey` exists only on types that declare it (the SQL `Dimension`
does), and column `@id` is never written (see "Column identity" above).
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
@nodeType("<alias>:::<id>")
@description("Customer staging")
@writeMode("append")
SELECT
    CUSTOMER_ID @not_null @uniqueness,
    EMAIL @description("primary contact"),
    UPDATED_AT
FROM {{ ref("STG", "STG_CUSTOMERS") }}
```

(`"<alias>:::<id>"` stands for the SQL `Work` type from Base Node Types - SQL
— id `707` on Snowflake, with `<alias>` whatever the workspace's package
declaration names; read it verbatim off the materialized `definition.yml`.
`@writeMode`, `@not_null`, and `@uniqueness` work only because that type
declares them. `@isBusinessKey` / `@isChangeTracking` go on a type that
declares them, such as the package's SQL `Dimension`.)
Note the annotation lines are BARE — no leading `--`. That is deliberate and
required (see "Write the annotations BARE" above).
