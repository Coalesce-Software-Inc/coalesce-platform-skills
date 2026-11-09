---
name: coalesce-create-stage-node
description: Create a new Coalesce staging node from a source node — a Stage that maps every source column 1:1, with the V2 node-type preflight check and coa verification loop.
---
<!-- coalesce-node-managed: true -->

> **Prerequisite:** load `coalesce-pipelines` first if it is not already loaded
> in this session. This skill assumes its rules, its "Node types" section, and
> its core loop.

# Create a stage node

A stage node is the first hop out of a Source: it selects the source's columns
unchanged so later layers build on a stable name.

## 1. Pick the staging node type

Follow "Node types" in coalesce-pipelines: list `nodeTypes/` and
`.coa/cache/packages/*/nodeTypes/`, read each `definition.yml`, and find the
staging-layer type. Do not assume it is called `Stage`; in the base packages
it is `Work`. Then:

- **It has `fileVersion: 2`:** write a `.sql` node (step 4). Note the type's
  `id`.
- **None on disk:** run `coa install -d <dir>` and look again.
- **Only a V1 staging type exists:** write the node as V1 `.yml` using
  "Authoring a new V1 node" in coalesce-v1-yaml-nodes, then go to step 5. Do
  not stop, do not upgrade the type, and never point a `.sql` node at it (the
  columns would be silently empty).

## 2. Read the source

Find the source node with `coa create -d <dir> --list-nodes` and read
`nodes/<SRC_LOCATION>-<SRC_NAME>.yml` for the full column list. Use the file,
not memory of what the table usually contains. If there is no Source node
yet, create it with `coa sources list` / `coa sources add`.

## 3. Check the target name

The file is `nodes/<LOCATION>-<NAME>.sql` (or `.yml` for V1), in the location
the user asked for, with an UPPER_SNAKE_CASE name.

If `nodes/<LOCATION>-<NAME>.sql` or `.yml` already exists, stop. Tell the user
the node exists and what it contains. Do not overwrite it, and do not create
a renamed duplicate.

## 4. Write the `.sql` node

```sql
@id("3f29c8a1-7b04-4e6d-9c2a-1d5e8f0a6b73")
@nodeType("base-node-types:::204")

SELECT
    "C_CUSTKEY"    AS "C_CUSTKEY",
    "C_NAME"       AS "C_NAME",
    "C_ADDRESS"    AS "C_ADDRESS"
FROM {{ ref("SRC", "CUSTOMER") }} CUSTOMER
```

- `@id` is a fresh UUID v4. `@nodeType` is the id from step 1, copied exactly
  as the type's `definition.yml` spells it (the value above is a stand-in).
  Both lines are bare.
- List every source column, one per line. Never `SELECT *`.
- `FROM` uses `{{ ref("LOCATION", "NAME") }}` with both arguments.
- A plain 1:1 stage needs no column annotations.

## 5. Verify

1. `coa validate -d <dir>`: 0 errors and 0 warnings. If an error points at
   existing shared config you were not asked to touch, report it; do not edit
   shared config to make validate pass.
2. `coa create -d <dir> --include "{ <NAME> }" --dry-run --verbose`: the DDL
   lists every column. An empty column list means the type is V1; go back to
   step 1.
3. `coa run -d <dir> --include "{ <NAME> }" --dry-run --verbose`: the DML is
   non-empty. Empty run SQL means the node's `config` lacks the type's
   defaults; fix it against the type's `nodeMetadataSpec`.

Stop after the dry-runs unless the user wants the table materialized.
