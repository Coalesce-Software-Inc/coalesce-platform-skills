---
name: coalesce-create-stage-node
description: Create a new Coalesce staging node from a source node — a Stage that maps every source column 1:1, with the V2 node-type preflight check and coa verification loop.
---

<!-- coalesce-node-managed: true -->

> **Prerequisite:** load `coalesce-pipelines` first if it is not already loaded in this session. This skill assumes its rules, its "Node types" section, and its core loop.

# Create a stage node

A stage node is the first hop out of a Source: it selects the source's columns unchanged so later layers build on a stable name.

## 1. Pick the staging node type

Follow "Node types" in coalesce-pipelines: list `nodeTypes/` and `.coa/cache/packages/*/nodeTypes/`, read each `definition.yml`, and find the staging-layer type. Do not assume it is called `Stage`; in the Snowflake, Databricks, and BigQuery base packages it is `Work`, and on ClickHouse (no base package) it is the built-in `sqlStage` (V2) or `Stage` (V1). Then:

- **It has `fileVersion: 2`:** write a `.sql` node (step 4). Note the type's `id`.
- **None on disk:** run `coa install -d <dir>` and look again. If there is still no staging type of either version (for example, install printed "No packages to install."), the base package isn't declared: stop and ask before running `coa init`. On ClickHouse, "No packages to install." is normal and the built-in types are already in `nodeTypes/`.
- **Only a V1 staging type exists:** write the node as V1 `.yml` using "Authoring a new V1 node" in the [V1 nodes reference](../coalesce-pipelines/reference/v1-nodes.md), then go to step 5. Do not stop, do not upgrade the type, and never point a `.sql` node at it (the columns would be silently empty).

## 2. Read the source

Find the source node with `coa create -d <dir> --list-nodes` and read `nodes/<SRC_LOCATION>-<SRC_NAME>.yml` for the full column list. Use the file, not memory of what the table usually contains. If there is no Source node yet, create it with `coa sources list` / `coa sources add`. Note the exact spelling and case of the source node's `name` and of each column: the `ref()` and every column reference must match them.

## 3. Check the target name

The file is `nodes/<LOCATION>-<NAME>.sql` (or `.yml` for V1), in the location the user asked for, with an UPPER_SNAKE_CASE name.

If `nodes/<LOCATION>-<NAME>.sql` or `.yml` already exists, stop. Tell the user the node exists and what it contains. Do not overwrite it, and do not create a renamed duplicate.

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

- `@id` is a fresh UUID v4. `@nodeType` is the id from step 1, copied exactly as the type's `definition.yml` spells it (the value above is a stand-in). Both lines are bare.
- List every source column, one per line. Never `SELECT *`.
- Write each source column, and the `ref()` name, exactly as the Source file spells them. The example's uppercase names fit Snowflake. On ClickHouse, names are case-sensitive and usually lowercase, so the same stage reads:

  ```sql
  @id("3f29c8a1-7b04-4e6d-9c2a-1d5e8f0a6b73")
  @nodeType("sqlStage")

  SELECT
      c_custkey AS C_CUSTKEY @notNull,
      c_name    AS C_NAME,
      c_address AS C_ADDRESS
  FROM {{ ref("SRC", "customer") }} CUSTOMER
  ```

  A wrong case passes validate and both dry-runs, then fails at run (`Unknown expression identifier`).
- `FROM` uses `{{ ref("LOCATION", "NAME") }}` with both arguments.
- A plain 1:1 stage needs no column annotations. On ClickHouse, every V2 column is created `Nullable`, so add `@notNull` to NOT NULL key columns that later nodes will sort or merge on, as with `C_CUSTKEY` above (see the [ClickHouse reference](../coalesce-pipelines/reference/platforms/clickhouse.md)).

## 5. Verify

1. `coa validate -d <dir>`: 0 errors and 0 warnings. If an error points at existing shared config you were not asked to touch, report it; do not edit shared config to make validate pass.
2. `coa create -d <dir> --include "{ <NAME> }" --dry-run --verbose`: the DDL lists every column with a real type. An empty column list means the type is V1 or the SELECT is not explicit; go back to step 1. A type of `UNKNOWN` (`Nullable(UNKNOWN)` on ClickHouse) means the `ref()` did not resolve; check its name and case.
3. `coa run -d <dir> --include "{ <NAME> }" --dry-run --verbose`: the DML is non-empty. Empty run SQL means the node's `config` lacks the type's defaults; fix it against the type's `nodeMetadataSpec`. A node materialized as a view has no run SQL by design ("no DML to preview").

Stop after the dry-runs unless the user wants the table materialized.
