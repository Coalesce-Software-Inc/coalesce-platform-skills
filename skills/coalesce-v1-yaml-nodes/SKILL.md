---
name: coalesce-v1-yaml-nodes
description: Use when reading, explaining, editing, or authoring Coalesce V1 YAML nodes (nodes/<LOCATION>-<NAME>.yml) — the node format the UI/API also generates. Covers the file shape, the id-based column lineage graph, safe edits, and the checklist for authoring a new V1 node by hand (Source nodes, config-driven types, or when no fileVersion 2 node type exists).
---

<!-- coalesce-node-managed: true -->

> **Prerequisite:** load `coalesce-pipelines` first if it is not already loaded in this session. This skill assumes its rules, its "Node types" section, and its core loop.

# V1 YAML nodes

V1 nodes are the YAML format at `nodes/<LOCATION>-<NAME>.yml`. The Coalesce UI and API produce it natively: a serialized node, including a column lineage graph keyed by ids. Most existing workspaces are mostly V1.

You may read, edit, and author V1 nodes. Author one by hand when the type is config-driven (an SCD2 Dimension) or has no `fileVersion: 2` definition. Generate Source nodes with `coa sources add` instead.

`coa describe schema node` is the authoritative shape (there is no `coa describe node` topic). Check fields against it, not against a sibling file.

## File shape

Five required top-level keys, nothing else allowed:

| Key           | Value                                           |
| ------------- | ----------------------------------------------- |
| `fileVersion` | `1`                                             |
| `id`          | node UUID. Immutable; anchors the column graph. |
| `name`        | node name                                       |
| `type`        | constant `Node`                                 |
| `operation`   | everything else                                 |

`operation.type` selects one of two shapes:

- **`sourceInput`**: a Source node. `sqlType: Source`, `metadata` holds only `columns`, plus a `metadata.join.joinCondition` of the form `FROM {{ ref('SRC', 'TABLE') }}`. Required: `locationName`, `name`, `sqlType`, `type`, `metadata`.
- **`sql`**: every transformation node. Required: `locationName`, `name`, `type`, `isMultisource`, `metadata` (with `columns` and `sourceMapping`), `materializationType` (`table` or `view`).

Other `operation` fields: `database` / `schema` (usually `""`, resolved from mappings), `description`, `deployEnabled`, `config`, `overrideSQL`, `version: 1`.

**`sqlType` is the node type**, the V1 counterpart of `@nodeType`: a built-in name or the `id` of a type on disk (`sqlType: "41"` resolves to the type whose `definition.yml` has `id: 41`). Find it as coalesce-pipelines "Node types" describes. A V1 node needs a type with `fileVersion: 1` or none.

**`config` is load-bearing.** Run templates gate their DML on it: Work-204 emits its INSERT only when `config.insertStrategy == 'INSERT'` and its truncate only when `config.truncateBefore`. The UI writes these defaults invisibly; a hand-authored node must copy them from the type's `nodeMetadataSpec`. `config: {}` passes validate and the create dry-run and renders zero run SQL.

**Identity comes from the YAML, not the filename** (the opposite of `.sql` nodes). `coa` reads `name` and `operation.locationName`. Keep the filename, `name`, `operation.name`, and `operation.locationName` in sync anyway.

## The column graph

Columns reference each other by id, not by name:

- `columnReference.stepCounter`: always this node's own `id`.
- `columnReference.columnCounter`: this column's id (a UUID; a bare integer in older exports).
- `sourceColumnReferences[].columnReferences[]`: `{stepCounter, columnCounter}` pairs naming the upstream node's `id` and the upstream column's `columnCounter`. This is the lineage edge.
- `sourceColumnReferences[].transform`: the SQL expression. `""` means pass-through.
- A column with no upstream (`COUNT(*)`, `CURRENT_TIMESTAMP`) uses `columnReferences: []`, or the sentinel `stepCounter: "0"` / `columnCounter: "0"`, with the expression in `transform`.

A fabricated id still parses, and lineage then points nowhere. Read ids out of the upstream file.

## `sourceMapping`

A list of source groups, each requiring `name`, `join`, `dependencies`:

- `join.joinCondition`: the literal `FROM ... JOIN ... WHERE ...` SQL with `{{ ref('LOCATION', 'NODE') }}` macros (and sometimes `{{ this }}`).
- `dependencies[]`: `{locationName, nodeName}` graph edges. These are by name, so a node rename breaks them.
- `aliases`: SQL alias → upstream node `id`.
- `noLinkRefs[]`: referenced without an edge (typically the node itself).
- `customSQL.customSQL`: a raw SQL override.

More than one group makes a multisource node (`isMultisource: true`): each group is a separate insert path, and every column has one `sourceColumnReferences` entry per group, in order.

## Reading a V1 node

| Question | Where to look |
| --- | --- |
| Columns and types | `operation.metadata.columns[].name` / `.dataType` |
| What a column computes | its `sourceColumnReferences[].transform` |
| Where a column comes from | its `columnReferences[]`: the node whose `id` matches `stepCounter`, then the column whose `columnCounter` matches |
| Upstream nodes | `sourceMapping[].dependencies[]` and the `ref()`s in `joinCondition` |
| Downstream nodes | `coa create --include "{ NAME }+" --dry-run`, or grep `nodeName: NAME` in `nodes/` |
| Merge/SCD key | columns with `isBusinessKey: true` / `keyColumnType` |
| Node type | `operation.sqlType` |
| Table or view | `operation.materializationType` |

`coa create --include "{ NAME }" --dry-run --verbose` shows the SQL a V1 node actually renders.

## Editing an existing node

Fine when asked:

- A node or column `description`.
- An existing column's `transform`, or a `joinCondition` (SQL strings that do not touch the id graph).
- `deployEnabled`, or a `config` value the user names.
- A column's `dataType`, to clear a Column Data Types warning.
- **Adding a column:** append to `operation.metadata.columns` an object with `name`, `dataType`, `description: ""`, `nullable`, a `columnReference` of `{stepCounter: <this node's id>, columnCounter: <fresh UUID>}`, and `sourceColumnReferences` pointing at the real upstream node id and column `columnCounter` (or `columnReferences: []` with the expression in `transform` for a computed column).

Do not:

- Change any existing `id`, `columnCounter`, or `stepCounter`.
- Tidy the file: no key reordering, no dropping fields that look redundant (`aliases`, `noLinkRefs`), no requoting `ref()` calls. These files are machine-serialized, and churn causes round-trip conflicts with the UI.
- Convert a `.sql` node to `.yml`.
- Rename by editing the file alone. Use coalesce-rename-node-cascade.

Removing columns or restructuring `sourceMapping` means cross-wiring ids by hand. Follow the id rules above, and prefer the Coalesce UI when one is at hand.

After any edit run `coa validate` and both dry-runs. The scanners that police V1 nodes: Column Sources / Source Mappings / Dependencies / References (the id graph resolves; a rename shows as `sourceMapping dependency does not resolve: LOC.NAME`), Column Data Types (warning), Column Names, Duplicate Node IDs and Names, Circular Dependencies, Node Type Validity, Storage Locations.

## Authoring a new V1 node

```yaml
fileVersion: 1
id: <fresh UUID v4>
name: <NAME>
type: Node
operation:
  type: sql
  sqlType: <TYPE_NAME_OR_ID> # read off disk; often Work, not Stage
  locationName: <LOCATION>
  name: <NAME> # mirrors the top-level name
  isMultisource: false
  materializationType: table
  config: # copy the type's nodeMetadataSpec defaults
    insertStrategy: INSERT
    truncateBefore: true
    testsEnabled: false
  metadata:
    columns:
      - name: <COLUMN>
        dataType: <TYPE> # copy from the upstream column
        description: "" # required by validate
        nullable: true
        columnReference:
          stepCounter: <this node's id>
          columnCounter: <fresh UUID v4>
        sourceColumnReferences:
          - columnReferences:
              - stepCounter: <upstream node id>
                columnCounter: <upstream column's columnCounter>
            transform: "" # "" = pass-through; else the SQL expression
    sourceMapping:
      - name: <NAME>
        aliases: { <ALIAS>: <upstream node id> }
        dependencies:
          - { locationName: <SRC_LOCATION>, nodeName: <SRC_NAME> }
        join:
          joinCondition: |-
            FROM {{ ref('<SRC_LOCATION>', '<SRC_NAME>') }} "<ALIAS>"
        noLinkRefs: []
        customSQL:
          customSQL: ""
```

1. Copy the column list (names, types, `columnCounter` values) from the upstream node file. Never invent it.
2. Set `sqlType` to a type that exists on disk and `config` to that type's defaults.
3. `transform` is what `get_source_transform(col)` emits; put the aliased expression there (`"CUSTOMER"."C_CUSTKEY"`) or leave `""` for pass-through.
4. For an SCD2 Dimension: `isBusinessKey: true` on the key column, `isChangeTracking: true` on tracked columns, and the system columns the type's `systemColumns` spec names (surrogate key with `isSurrogateKey: true`, `SYSTEM_VERSION`, `SYSTEM_CURRENT_FLAG`, and the start/end/create/ update dates with their `isSystem*` flags and transforms).
5. Verify: `coa validate -d <dir>`, then `coa create` and `coa run`, each with `--include "{ <NAME> }" --dry-run --verbose`. The DDL must list the columns. Empty run SQL ("Template rendered zero SQL stages") means `config` is missing defaults. Show the user the rendered SQL before anything executes.
