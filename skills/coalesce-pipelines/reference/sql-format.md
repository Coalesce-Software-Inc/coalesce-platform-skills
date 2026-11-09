<!-- coalesce-node-managed: true -->
# Node SQL Format: V2 (.sql) nodes

`coa describe sql-format` and `coa describe concepts` are the source of truth.
Which format to author, and how to find a node type, are in the
coalesce-pipelines skill. V1 `.yml` nodes are covered by coalesce-v1-yaml-nodes.

## What each format is for

- **V2 `.sql`**: the node's value is its SQL (transforms, joins, metrics,
  business logic). Columns and data types are inferred from the SELECT.
- **V1 `.yml`**: the node's value is its configuration. Source nodes,
  config-driven patterns such as SCD2 Dimensions, and any node whose type has
  no `fileVersion: 2` definition.

## File naming

- `nodes/<LOCATION>-<NAME>.sql`. The filename sets location and name; an
  `@location` annotation is ignored. `nodes/` has no subdirectories.
- Filenames are case-sensitive. `<LOC>-<NAME>.yml` and `<LOC>-<NAME>.sql`
  cannot coexist.
- Names are UPPER_SNAKE_CASE by convention. Match the repo: typically
  `SRC-<TABLE>` for sources, `TARGET-STG_<NAME>` for stages.

## The two required annotations

```sql
@id("b2c3d4e5-f6a7-8901-bcde-f12345678901")
@nodeType("base-node-types:::204")
SELECT
    CUSTOMER_ID @isBusinessKey,
    EMAIL @description("primary contact"),
    UPDATED_AT @isChangeTracking
FROM {{ ref("STG", "STG_CUSTOMERS") }}
```

- `@id("<UUID>")`: a fresh UUID v4 for a new node. Never reuse or change an
  existing one.
- `@nodeType("<id>")`: the `id` field of a `fileVersion: 2` type's
  `definition.yml`, read off disk. The value above is a stand-in.
- These are the first two lines, nothing else precedes the SQL, and they are
  written bare. A bare `@id(...)` is not valid SQL, but do not comment it out:
  `coa` cannot read `-- @id(...)`, so the node is silently dropped from the
  graph while `coa validate` still reports 0 errors.

After writing a node, confirm it loaded with `coa create --dry-run --verbose
--include "{ NODE }"`. "0 nodes matched" means the annotations were not read.
An empty column list means `@nodeType` points at a V1 type.

## References

Jinja macros with both arguments. There is no name-only form. Never hardcode
`db.schema.table`.

- `{{ ref("LOCATION", "NODE_NAME") }}`: resolves to the table and creates a
  lineage edge.
- `{{ ref_no_link("LOCATION", "NODE_NAME") }}`: resolves, no edge.
- `{{ ref_link("LOCATION", "NODE_NAME") }}`: edge only, emits no SQL.

LOCATION must be the location the node file lives in. A wrong location still
validates with exit 0 and shows only as `warning[namedDependencyUnresolved]`;
treat that warning as an error.

Use double quotes for new or edited refs. Existing single-quoted refs resolve
the same way (matching is case-insensitive); leave them alone.

## Column annotations

Placed after the alias and before the comma: `CREATED_AT @isChangeTracking,`.

Native, always available:

- `@isBusinessKey`: the MERGE/SCD key. Required on Persistent Stage and
  Dimension. Affects DDL.
- `@isChangeTracking`: Persistent Stage change detection. Affects DML.
- `@id("col-id")`: column lineage. Metadata only.
- `@description("text")`: docs. Metadata only.

Declared: a node type's `nodeMetadataSpec` may carry an `annotations:` block
declaring more node- and column-level annotations (for example a data quality
test library). That block is the only list of what the type's templates act
on. Values reach the template as `true` for a bare annotation,
`{parameters: [...]}` for a parameterized one, and an ordered array for one
declared `allowsMultiple`. Node-level values land on `config.<name>`,
column-level ones on `col.<name>`.

Do not invent annotations. `@isSurrogateKey`, `@pii`, and `@synqMonitor` are not
in the spec (`isSurrogateKey` is a V1 `.yml` column field, not a `.sql`
annotation).

Hazards (verified on coa 7.42.5):

- An undeclared or misspelled annotation is accepted and does nothing, with no
  warning. Declared names are case-sensitive; check spelling against the
  type's `annotations:` block first.
- For multiple values, repeat the annotation.
  `@accepted_values("'A'") @accepted_values("'B'")` renders `NOT IN ('A',
  'B')`; `@accepted_values("'A'", "'B'")` renders only the first value
  (TRA-2486). The same holds for `@rejected_values`, `@preSQL`, `@postSQL`,
  `@tests`, `@inHash`.
- An annotation named after a SQL keyword fails to parse, which is why the
  packaged test is `@uniqueness`, not `@unique`.
- A declared `default` is documentation only. Omit the annotation to get the
  template's fallback.
- `coa validate` rejects unquoted boolean arguments such as
  `@tests("...", true, "After")` that the runtime accepts (TRA-2483). That is
  a known false positive. Do not quote the boolean: `"false"` is a string and
  Jinja treats it as true.

## SQL conventions

- Snowflake dialect unless `data.yml` says otherwise.
- Aliases are bare UPPER_SNAKE_CASE (`SUM(QUANTITY * UNIT_PRICE) AS
  LINE_TOTAL`). The source expression may quote the underlying column
  (`T."COL"`). Some existing nodes use double-quoted aliases; match the file
  you are editing.
- Keep the existing column order.
- List columns explicitly, never `SELECT *`. A V2 type infers its columns by
  parsing the SELECT, so `SELECT *` renders a zero-column table while validate
  stays green. To stage every column 1:1, read the source's columns and list
  each one.
