<!-- coalesce-node-managed: true -->

# Node SQL Format: SQL (.sql) nodes

`coa describe sql-format` and `coa describe concepts` are the source of truth. Which kind of node to author, and how to find a node type, are in the coalesce-pipelines skill. YAML `.yml` nodes are covered by the [YAML nodes reference](v1-nodes.md).

## File naming

- `nodes/<LOCATION>-<NAME>.sql`. The filename sets location and name; an `@location` annotation is ignored. `nodes/` has no subdirectories.
- Filenames are case-sensitive. `<LOC>-<NAME>.yml` and `<LOC>-<NAME>.sql` cannot coexist.
- Names are `UPPER_SNAKE_CASE` by convention. Match the repo: typically `SRC-<TABLE>` for sources, `TARGET-STG_<NAME>` for stages.

## The two required annotations

```sql
@id("b2c3d4e5-f6a7-8901-bcde-f12345678901")
@nodeType("<alias>:::<id>")
@description("Customer staging")
SELECT
    CUSTOMER_ID @not_null @uniqueness,
    EMAIL @description("primary contact"),
    UPDATED_AT
FROM {{ ref("STG", "STG_CUSTOMERS") }}
```

- `@id("<UUID>")`: a fresh UUID v4 for a new node. Never reuse or change an existing one.
- `@nodeType("<id>")`: the `id` field of a SQL node type's `definition.yml` (`fileVersion: 2`), read off disk and copied whole. `"<alias>:::<id>"` above is a stand-in for the SQL `Work` type from Base Node Types - SQL; `@not_null` and `@uniqueness` work only because that type declares them.
- These are the first two lines, nothing else precedes the SQL, and they are written bare. A bare `@id(...)` is not valid SQL, but do not comment it out: `coa` cannot read `-- @id(...)`, so `coa validate` fails with `Missing @id annotation` and `coa create` refuses to load the workspace.

After writing a node, confirm it loaded with `coa create --dry-run --verbose --include "{ NODE }"`. An empty column list means `@nodeType` points at a YAML type; `coa validate` reports that as `error[extensionVersionMismatch]`.

## Node options: annotations, never a `config` block

The rule starts at the node type. A SQL node type has no `config` block in its `nodeMetadataSpec`: it declares its node options under `annotations:`. `config:` belongs to YAML types only. Never add one to a SQL type, and never carry one over when turning a YAML type into a SQL type; rewrite each item as an annotation declaration. Templates read the values as `config.<name>`, but that is the template's name for them, not a block anyone writes.

The node follows its type. A `.sql` node sets options with the node-level annotations its type declares, written above the leading `WITH` or `SELECT`, and carries no `config` of its own (no YAML header, no `operation.config`, no sidecar `.yml`). Leave an annotation out to get the template's default.

If the option you need is not declared by the type, say so and ask. Do not add a `config:` block to the type to get it.

## References

Jinja macros with both arguments. There is no name-only form. Never hardcode `db.schema.table`.

- `{{ ref("LOCATION", "NODE_NAME") }}`: resolves to the table and creates a lineage edge.
- `{{ ref_no_link("LOCATION", "NODE_NAME") }}`: resolves, no edge.
- `{{ ref_link("LOCATION", "NODE_NAME") }}`: edge only, emits no SQL.

LOCATION must be the location the node file lives in. A wrong location still validates with exit 0 and shows only as `warning[namedDependencyUnresolved]`; treat that warning as an error.

Use double quotes for new or edited refs. Existing single-quoted refs resolve the same way (matching is case-insensitive); leave them alone.

## Annotations: a reserved set plus what the node type declares

Node-level annotations sit above the leading `WITH` or `SELECT`. Column-level annotations go after the alias and before the comma: `CREATED_AT @not_null,`. Syntax: bare `@name` (a flag), or `@name("value", 2, true)` with positional literal arguments, strings quoted and numbers and booleans unquoted.

Reserved, on every SQL node type and validated by Coalesce:

- Node-level: `@id` and `@nodeType` (above); `@description("text")`; `@materializationType("table")` or `("view")`, lowercase, defaulting to table; `@deployDisabled`, bare, which excludes the node from cloud deploy while local `coa create` and `coa run` still build it (`@deployDisabled(true)` is a validate error).
- Column-level: `@description("text")`; `@notNull`, a DDL `NOT NULL` constraint and not a test; `@defaultValue("0")` or `@defaultValue("'NA'")`, quoted for the column's type.
- Column `@id("col-id")` is also accepted (lineage; metadata only).
- Exception: on a type whose `nodeMetadataSpec` sets `deployStrategy: advanced`, `@materializationType` belongs to the type, which declares its own values. The SQL `Work`, `Dimension`, and `Fact` in Base Node Types - SQL 2.3.0 are advanced types and accept `"transient table"` as well. Coalesce does not check the value on those types (validate passes any string), so read the type's declaration before writing one. On any other SQL type a value outside `table` and `view` is a validate error.

Declared: everything else exists only if the node type declares it in the `annotations:` block of its `nodeMetadataSpec`. That block is the only list of what the type's templates act on. Values reach the template as `true` for a bare annotation, `{parameters: [...]}` for a parameterized one, and an ordered array of those for one declared `allowsMultiple`. Node-level values land on `config.<name>`, column-level ones on `col.<name>`.

`@isBusinessKey` and `@isChangeTracking` are declared annotations, not reserved ones. In Base Node Types - SQL the `Dimension` declares both and the `Fact` declares `@isBusinessKey`; the `Work` declares neither, so on a `Work` node they draw a warning and do nothing. The `Work` declares `@writeMode`, `@disableTests`, `@tests`, `@preSQL`, `@postSQL`, `@tag`, the column tests (`@not_null`, `@uniqueness`, `@empty`, `@accepted_values`, `@rejected_values`, `@min_max`, `@min_value`, `@max_value`, `@freshness`, `@relative_time`), `@inHash`, and `@clusterKey`. Read the type's own `definition.yml` rather than relying on this list.

Hazards (verified on coa 7.53.3 with Base Node Types - SQL 2.3.0):

- An undeclared or misspelled annotation is a validate warning, `warning[annotationNameUnknown]`, often with a "Did you mean" suggestion, and the annotation is ignored. Declared names are case-sensitive. A warning is a defect: fix the name against the type's `annotations:` block or remove it. Never declare it on the node type to silence the warning; that is shared config.
- Multi-value annotations follow the declaration. One declared `allowsMultiple` hydrates one array entry per occurrence; without the flag, repeating it keeps only the last occurrence. What a template does with several arguments in one call is the type's choice, so read the annotation's `description`. The packaged `Work` reads `@accepted_values("'A'", "'B'")`, `@accepted_values("'A','B'")`, and the repeated form alike (all render `NOT IN ('A', 'B')`), and documents one call per column.
- An annotation named after a SQL keyword fails to parse, which is why the packaged test is `@uniqueness`, not `@unique`.
- A declared `default` is documentation only. Omit the annotation to get the template's fallback.
- A quoted boolean is a string: `@disableTests("false")` hydrates as `{parameters: ["false"]}`. The packaged types normalize it, but a template that tests the value directly treats any non-empty string as true. Write `@disableTests(false)`.
- A macro call in the SELECT, such as `{{ get_hash("H") }} AS ROW_HASH`, does not render in local `coa create` and `coa run` (TRA-2487): the column is typed `UNKNOWN`, validate warns `unknownColumnDataType`, and the load emits `"ROW_HASH" AS "ROW_HASH"`. The Coalesce app renders it. When the node must run locally, compute the value in plain SQL and say why.

Do not invent annotations. `@pii` and `@synqMonitor` are declared by no packaged type, and `@isSurrogateKey` exists only where a type declares it (the SQL `Dimension` does). `isSurrogateKey` is also a YAML `.yml` column field, which is not a `.sql` annotation.

## SQL conventions

- Snowflake dialect unless `data.yml` says otherwise.
- Aliases are bare UPPER_SNAKE_CASE (`SUM(QUANTITY * UNIT_PRICE) AS LINE_TOTAL`). The source expression may quote the underlying column (`T."COL"`). Some existing nodes use double-quoted aliases; match the file you are editing.
- Keep the existing column order.
- List columns explicitly rather than `SELECT *`. Current `coa` expands `SELECT *` to the source's columns, but the node's columns then change whenever the source does, and each column's name is its identity downstream. To stage every column 1:1, read the source's columns and list each one.
- Alias every expression. If a type comes through as `UNKNOWN`, add an explicit cast.
