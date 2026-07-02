<!-- coalesce-node-managed: true -->
# Node SQL Format — V2 (.sql) vs V1 (.yml)

`coa describe sql-format` and `coa describe concepts` are the source of truth.

## Two formats

- **V2 — `.sql`, `fileVersion: 2` — PREFERRED for all transformation nodes**
  (Stage, View, Dimension, Fact, Persistent Stage). File at
  `nodes/<LOCATION>-<NAME>.sql`. Columns are inferred from the SELECT.
- **V1 — `.yml`, `fileVersion: 1`** — required for Source nodes and any
  V1-only node type. File at `nodes/<LOCATION>-<NAME>.yml`. Columns are
  explicit, with data types and source mappings (no `.sql` annotations) — see
  `coa describe schema node`.

## The silently-empty-columns trap

A V2 `.sql` node REQUIRES a node type whose `nodeTypes/<ID>/definition.yml` has
`fileVersion: 2`. If `@nodeType` points at a V1 (or absent-fileVersion) type,
the node still loads but its columns are **SILENTLY EMPTY** (`columns: []`) —
`coa create`/`coa run` then emit broken DDL/DML with no error. The built-in
common types (Source, Stage, View, Dimension, Fact, Persistent Stage) are V1;
using them in a `.sql` file triggers this trap.

If a needed V2 node type does not exist, do NOT point `@nodeType` at a V1 type
and do NOT bump the `fileVersion` of an existing V1 type (that silently
rewrites every node already using it). Instead:

- **The task requires `.sql` nodes and no compatible V2 type exists** (e.g. a
  greenfield repo with only the V1 built-ins) — **create a brand-new V2 node
  type** (recipe below) and point your new nodes at it. A new node type is
  referenced only by the nodes you are adding, so it cannot break anything that
  already exists — this is an in-scope prerequisite of the request, not a
  shared-config edit that needs sign-off.
- **You would have to edit/replace an EXISTING node type, bump its
  `fileVersion`, or swap its template patterns** — that IS a shared-config edit
  (other nodes depend on it); STOP and ask first.

## Bootstrapping a V2 node type

When you must create one, author `nodeTypes/<DisplayName>-<ID>/` with three
files. PREFER a fresh UUID for `<ID>`; the `@nodeType()` value is that `id`.
`coa describe node-types` is the authoritative reference.

`definition.yml` — `fileVersion: 2` is what makes `.sql` columns parse:

```yaml
fileVersion: 2
id: 9f8e7d6c-5b4a-4938-8271-0a1b2c3d4e5f
name: Stage
type: NodeType
isDisabled: false
metadata:
  error: null
  nodeMetadataSpec: |
    capitalized: Stage
    short: STG
    plural: Stages
    tagColor: '#2EB67D'
```

`create.sql.j2` — V2 templates MUST use CTAS (`col.dataType` is UNKNOWN for V2,
so an explicit-type `CREATE TABLE (...)` renders `UNKNOWN` and Snowflake
rejects it):

```jinja
{{ stage('Create Table') }}
CREATE OR REPLACE TABLE {{ ref_no_link(node.location.name, node.name) }} AS
{% for source in sources %}
SELECT
{% for col in source.columns %}
    {{ get_source_transform(col) }} AS "{{ col.name }}"
    {%- if not loop.last -%}, {% endif %}
{% endfor %}
{{ source.join }}
WHERE 1=0
{% endfor %}
```

`run.sql.j2`:

```jinja
{{ stage('Truncate') }}
TRUNCATE IF EXISTS {{ ref_no_link(node.location.name, node.name) }};
{% for source in sources %}
{{ stage('Insert') }}
INSERT INTO {{ ref_no_link(node.location.name, node.name) }}
SELECT
{% for col in source.columns %}
    {{ get_source_transform(col) }} AS "{{ col.name }}"
    {%- if not loop.last -%}, {% endif %}
{% endfor %}
{{ source.join }}
{% endfor %}
```

Then `coa validate` should show `Extension/version mismatch` ✔ and a
`coa create --dry-run --verbose` on one of your nodes should emit a full column
list (NOT empty) — that proves the type is wired correctly.

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

> ⚠️ Annotations are LIVE node metadata, not SQL. Write them as the first
> physical lines, WITHOUT a `--` prefix and NOT inside a `/* */` block. A
> commented-out `@id`/`@nodeType` (e.g. `-- @id("...")`) is the single most
> common failure: `coa` cannot extract the metadata, so it **silently drops the
> file** — `coa validate` still reports 0 errors (the phantom node simply
> doesn't exist), but `coa create` then fails to load the workspace. A green
> `coa validate` does NOT prove your node exists. Confirm with
> `coa create --dry-run --verbose --include "{ <NAME> }"`: it must emit real
> DDL with your columns, not a load error.

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

## Column annotations — the COMPLETE set

Placed AFTER the alias and BEFORE the comma, e.g.
`CREATED_AT @isChangeTracking,`:

- `@isBusinessKey` — required on Persistent Stage + Dimension (optional on
  Stage); the MERGE/SCD key; **affects DDL**.
- `@isChangeTracking` — Persistent Stage change detection; **affects DML**.
- `@id("col-id")` — column lineage; metadata only.
- `@description("text")` — docs; metadata only.

Do NOT invent annotations: `@isSurrogateKey`, `@pii`, `@synqMonitor`,
`@prgTest` are NOT in the coa SQL annotation spec. (`isSurrogateKey` exists as
a boolean column field in the V1 node JSON schema — legitimate in a `.yml`
node — but it is NOT a `.sql` column annotation.)

## SQL conventions

- Target Snowflake SQL dialect (unless the repo's `data.yml` says otherwise).
- Aliases in hand-authored SELECTs are bare UPPER_SNAKE_CASE identifiers
  (e.g. `SUM(QUANTITY * UNIT_PRICE) AS LINE_TOTAL`); the source expression may
  quote the underlying column (`T."COL"`). Double-quoted aliases appear in
  node-type Jinja templates that emit generated DDL, and in some existing
  nodes — match the file you are editing.
- Preserve existing column ordering; keep changes minimal.

## Example V2 node

✅ CORRECT — `@id`/`@nodeType` are the first physical lines, UNcommented, and
each column is listed explicitly (no `SELECT *`):

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
built-in `Dimension` is V1.)

❌ WRONG — two independent bugs, each of which `coa validate` still reports as
"0 errors" (so a green validate does NOT prove the node works). Do NOT do this:

```sql
-- @id("b2c3d4e5-f6a7-8901-bcde-f12345678901")   ← commented → node dropped
-- @nodeType("Dimension")                          ← commented → node dropped
SELECT *                                           ← empty columns → broken DDL
FROM {{ ref("STG", "STG_CUSTOMERS") }}
```

1. **Commented annotations.** `@id(...)` / `@nodeType(...)` are Coalesce
   metadata that `coa` parses BEFORE handing the SQL to the warehouse — they
   are valid, required top-of-file lines and must stay UNcommented. A `--`
   prefix makes `coa` fail to extract metadata and SILENTLY DROP the file:
   validate is green (phantom node) but `coa create` fails to load it. If you
   are tempted to comment them "so the SQL parses", don't — that is exactly
   what breaks the node.
2. **`SELECT *`.** A V2 node infers its columns from the explicit SELECT list;
   with `SELECT *` there are no inferred columns, so the node type's CTAS
   template renders degenerate DDL like
   `CREATE OR REPLACE TABLE ... AS SELECT * WHERE 1 = 0` — no columns, no data.
   List every column explicitly with an alias (`"COL" AS "COL"`), even for a
   1:1 stage. Confirm with `coa create --dry-run --verbose`: the previewed
   `CREATE ... AS SELECT` must enumerate your columns, not show `SELECT *`.
