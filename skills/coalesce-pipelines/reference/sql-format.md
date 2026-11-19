<!-- coalesce-node-managed: true -->

# Node SQL Format: V2 (.sql) nodes

`coa describe sql-format` and `coa describe concepts` are the source of truth. Which format to author, and how to find a node type, are in the coalesce-pipelines skill. V1 `.yml` nodes are covered by the [V1 nodes reference](v1-nodes.md).

## File naming

- `nodes/<LOCATION>-<NAME>.sql`. The filename sets location and name; an `@location` annotation is ignored. `nodes/` has no subdirectories.
- Filenames are case-sensitive. `<LOC>-<NAME>.yml` and `<LOC>-<NAME>.sql` cannot coexist.
- Names are `UPPER_SNAKE_CASE` by convention. Match the repo: typically `SRC-<TABLE>` for sources, `TARGET-STG_<NAME>` for stages. Source nodes keep the warehouse's spelling, so on a case-sensitive platform such as ClickHouse they are often lowercase (`SRC-customer.yml`).

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

- `@id("<UUID>")`: a fresh UUID v4 for a new node. Never reuse or change an existing one.
- `@nodeType("<id>")`: the `id` field of a `fileVersion: 2` type's `definition.yml`, read off disk. The value above is a stand-in.
- These are the first two lines, nothing else precedes the SQL, and they are written bare. A bare `@id(...)` is not valid SQL, but do not comment it out: `coa` cannot read `-- @id(...)`, so the node is silently dropped from the graph while `coa validate` still reports 0 errors.

After writing a node, confirm it loaded with `coa create --dry-run --verbose --include "{ NODE }"`. "0 nodes matched" means the annotations were not read. An empty column list means `@nodeType` points at a V1 type.

## References

Jinja macros with both arguments. There is no name-only form. Never hardcode `db.schema.table`.

- `{{ ref("LOCATION", "NODE_NAME") }}`: resolves to the table and creates a lineage edge.
- `{{ ref_no_link("LOCATION", "NODE_NAME") }}`: resolves, no edge.
- `{{ ref_link("LOCATION", "NODE_NAME") }}`: edge only, emits no SQL.

LOCATION must be the location the node file lives in. A wrong location still validates with exit 0 and shows only as `warning[namedDependencyUnresolved]`; treat that warning as an error.

Use double quotes for new or edited refs. Existing single-quoted refs resolve the same way; leave them alone. Write NODE_NAME exactly as the node file spells it: on ClickHouse, `ref("SRC", "CUSTOMER")` does not resolve to `nodes/SRC-customer.yml` and shows as `namedDependencyUnresolved`.

## Column annotations

Placed after the alias and before the comma: `CREATED_AT @isChangeTracking,`.

Reserved, available on every SQL node type:

- Column: `@description("text")` (docs), `@notNull` (DDL: the column is created NOT NULL), `@defaultValue("expr")` (DDL default; quote for the type, `"0"` or `"'NA'"`).
- Node, above the SELECT: `@description("text")`, `@materializationType("table" | "view")`, `@deployDisabled`.

Read by the type's templates, so they act only on types that use them:

- `@isBusinessKey`: the MERGE/SCD key. Required on Persistent Stage and Dimension types that merge. Affects DDL.
- `@isChangeTracking`: change detection for Persistent Stage and SCD2 Dimension. Affects DML.

On a config-style type with no `annotations:` block whose templates do not read them (every ClickHouse built-in type, for example) they are accepted and ignored, with no warning. On a type that declares an `annotations:` block without them, validate warns `annotationNameUnknown`.

Column `@id`: a `.sql` column's name is its identity, and an `@id` on a column re-keys it, so downstream references by name break. Write a column `@id` only when the node type requires one (the ClickHouse SQL node types package's Dimension and Fact do).

Declared: a node type's `nodeMetadataSpec` may carry an `annotations:` block declaring more node- and column-level annotations (for example a data quality test library). That block is the only list of what the type's templates act on. Values reach the template as `true` for a bare annotation, `{parameters: [...]}` for a parameterized one, and an ordered array for one declared `allowsMultiple`. Node-level values land on `config.<name>`, column-level ones on `col.<name>`. A node-level annotation also lands on `config.<name>` on a type with no `annotations:` block, which is how a V2 node sets a template config value such as ClickHouse's `@orderBy("c_custkey")`.

Do not invent annotations. `@pii` and `@synqMonitor` are not in the spec. `@isSurrogateKey` is a V1 `.yml` column field, not a `.sql` annotation, except on types that declare it (the ClickHouse SQL node types package does).

Hazards (verified on coa 7.42.5):

- An undeclared or misspelled annotation is accepted, often with no warning, and does nothing unless a template happens to read that exact `config.<name>` / `col.<name>`. Names are case-sensitive; check spelling against the type's `annotations:` block, or for a type without one, against the config names its templates read.
- For multiple values, repeat the annotation. `@accepted_values("'A'") @accepted_values("'B'")` renders `NOT IN ('A', 'B')`; `@accepted_values("'A'", "'B'")` renders only the first value (TRA-2486). The same holds for `@rejected_values`, `@preSQL`, `@postSQL`, `@tests`, `@inHash`.
- An annotation named after a SQL keyword fails to parse, which is why the packaged test is `@uniqueness`, not `@unique`.
- A declared `default` is documentation only. Omit the annotation to get the template's fallback.
- `coa validate` rejects unquoted boolean arguments such as `@tests("...", true, "After")` that the runtime accepts (TRA-2483). That is a known false positive. Do not quote the boolean: `"false"` is a string and Jinja treats it as true.

## SQL conventions

- Write the dialect of the platform in `data.yml`: Snowflake when `platformKind` is absent or `snowflake`, Databricks SQL, BigQuery GoogleSQL, and for ClickHouse its own dialect (see the [ClickHouse reference](platforms/clickhouse.md); there is no `MERGE`). A function the platform lacks passes validate and both dry-runs and fails only at execution.
- Aliases are bare UPPER_SNAKE_CASE (`SUM(QUANTITY * UNIT_PRICE) AS LINE_TOTAL`). The source expression may quote the underlying column (`T."COL"`). Some existing nodes use double-quoted aliases; match the file you are editing. Write each source column exactly as the upstream node spells it: on a case-sensitive platform (ClickHouse), `"C_CUSTKEY"` and `c_custkey` are different columns.
- Keep the existing column order.
- List columns explicitly, never `SELECT *`. A V2 type infers its columns by parsing the SELECT, so `SELECT *` renders a zero-column table while validate stays green. To stage every column 1:1, read the source's columns and list each one.
