---
name: coalesce-create-stage-node
description: Create a new Coalesce staging node from a source node — a Stage that maps every source column 1:1, with the V2 node-type preflight check and coa verification loop.
---
<!-- coalesce-node-managed: true -->

> **Prerequisite — load `coalesce-pipelines` first.** If you have not already
> loaded the `coalesce-pipelines` skill in this session, load it now, read its
> "Orient first" step, core `coa` loop, and Rules, then return here. This skill
> assumes those invariants (bare `@id`/`@nodeType` first lines, `fileVersion: 2`
> node types, one-node-at-a-time validate → dry-run → create loop) are already
> in context.

Create a Stage node that maps every column of a source node 1:1. A Stage is the
first hop out of a Source: it selects the source's columns unchanged so later
layers build on a stable name. `coa describe sql-format` and `coa describe node-types`
 document the node file and node type formats; consult them if anything below is
 unclear.

## 0. Critical preflight — does a V2 Stage node type exist?

A `.sql` node is a V2 node and REQUIRES a node type whose `definition.yml` has
`fileVersion: 2`. If you point `@nodeType(...)` at a V1 Stage type
(`fileVersion: 1` or absent), the node loads but its columns are
**silently empty** (`columns: []`) — `coa create`/`coa run` then emit broken
DDL/DML with no error. (`coa describe sql-format`, `coa describe node-types`.)

Check what Stage type actually exists:

- `.coa/cache/packages/*/nodeTypes/<Name>-<id>/definition.yml` — the installed
  package types, materialized as a read-only file tree by `coa install`. The
  normal Stage type is a package type from the base node types package; each
  materialized `definition.yml` carries the resolvable id in `<alias>:::<id>`
  form, and that exact id is what `@nodeType()` takes. Never edit this tree —
  `coa install` regenerates it. (`coa describe node-types` documents the folder
  layout and `definition.yml` fields; it does not list what is installed.)
- A workspace-local definition, if any, lives in
  `nodeTypes/<DisplayName>-<ID>/definition.yml`; the `@nodeType()` value is the
  `id` field (also the part after the last dash in the folder name). Read its
  `fileVersion` (absent or `1` = V1; `2` = V2). `coa describe schema nodeType`
  documents the shape.

Then branch:

- **A V2 Stage node type exists (`fileVersion: 2`)** — proceed; author a `.sql`
  node (preferred for all transformations). Note its `id` for step 3.
- **`nodeTypes/` has no V2 Stage type** — run `coa install -d <dir>` to hydrate
  the workspace's packages (safe, no need to ask), then re-check `nodeTypes/`
  and `.coa/cache/packages/*/nodeTypes/`. Do NOT create a node type yourself:
  V2 types come from the platform's base node types package (`coa init`
  declares it; the package may be unavailable outside production registries).
- **Only a V1 Stage type exists (`fileVersion` absent or `1`)**: author the
  Stage as a V1 `.yml` node. Do NOT upgrade the node type and do NOT stop: V1
  is the supported authoring format whenever the workspace's node types are V1.
  The `fileVersion` in `nodeTypes/<ID>/definition.yml` decides this, never the
  platform. Follow the recipe in
  **coalesce-pipeline-structure** ("Creating a V1 (.yml) node"), copy the
  column list from the source node in `nodes/`, then go straight to step 4 to
  verify. Bumping an in-use type's `fileVersion` changes DDL/DML for every node
  of that type, so that still requires **STOP and ASK the user first**.

  Never silently write a `.sql` node against a V1 Stage type — that is the
  empty-columns trap above.

## 1. Gather the source

1. Identify the source node, its location, and its columns. Use `coa` as the
   authoritative surface: `coa create -d <dir> --list-nodes` 
   (or `coa run -d <dir> --list-nodes`) to enumerate nodes, and read the source file
   (`nodes/<SRC_LOCATION>-<SRC_NAME>.yml`) for its column names. Do not rely on
   cached context as ground truth.
2. Note every source column name; the Stage maps them 1:1.

## 2. Decide the target file

- Path: `nodes/<LOCATION>-<NAME>.sql` (V2) or `.yml` (V1). The filename sets the
  location and name — an `@location` annotation is ignored. `nodes/` is flat (no
  subdirectories).
- Names are `UPPER_SNAKE_CASE` and unique. A name collides if either
  `nodes/<LOCATION>-<NAME>.yml` or `nodes/<LOCATION>-<NAME>.sql` already exists —
  the two extensions cannot coexist. Confirm the name is free before writing.
- Use the staging location the user asked for (commonly `STG`). Do not assume a
  fixed location.

## 3. Write the V2 `.sql` node

(If step 0 sent you down the V1 path, write the `.yml` per the
coalesce-pipeline-structure recipe and skip to step 4.)

Required top annotations, before any SQL:

- `@id("<UUID>")` — PREFER a fresh UUID v4. NEVER reuse or modify an existing
  node's `@id`; duplicate IDs collide across the workspace.
- `@nodeType("<TypeID>")` — the V2 Stage type ID you found in step 0. Normally a
  package ID, `<alias>:::<id>`; a workspace-local type uses the `id` from
  `nodeTypes/<DisplayName>-<ID>/definition.yml`.

Then a `SELECT` mapping each source column 1:1, and a `FROM` using a
double-quoted `ref()` with BOTH args:

```sql
@id("3f29c8a1-7b04-4e6d-9c2a-1d5e8f0a6b73")
@nodeType("Stage")

SELECT
    "C_CUSTKEY"    AS "C_CUSTKEY",
    "C_NAME"       AS "C_NAME",
    "C_ADDRESS"    AS "C_ADDRESS"
FROM {{ ref("SRC", "CUSTOMER") }} CUSTOMER
```

In the example above, `"Stage"` stands in for the actual V2 Stage type ID from
step 0 — usually a package ID of the form `<alias>:::<id>`. `Stage` is a valid
common type ID, but a `Stage` type is typically V1: only use
`@nodeType("Stage")` literally if a `fileVersion: 2` node type with that exact
`id` exists. Otherwise substitute the real V2 type ID verbatim as the type's
`definition.yml` on disk spells it.

Rules:

- `{{ ref("LOCATION", "NODE_NAME") }}` — double quotes, both args required.
  There is no name-only form. `ref()` creates the lineage edge and resolves to
  the real `database.schema.table`; NEVER hardcode `db.schema.table`.
- A plain 1:1 Stage needs no column annotations. If you want lineage IDs or
  docs, the only valid column annotations are `@id("col-id")` and
  `@description("text")` (both metadata-only), placed AFTER the alias and BEFORE
  the comma. `@isBusinessKey` / `@isChangeTracking` belong on Persistent
  Stage/Dimension, not a plain Stage. Do NOT invent annotations.

## 4. Verify with coa (mandatory)

Run the core loop and fix issues before moving on:

1. `coa validate -d <dir>` — schema + graph scanners pass (broken refs,
   duplicate names, missing node types, etc.). Add `--json` for machine-readable
   output. If errors point only at pre-existing workspace config you were not
   asked to touch, surface that to the user — do not edit shared config to make
   validate pass.
2. `coa create -d <dir> --include "{ <NAME> }" --dry-run --verbose` — inspect the
   generated DDL. If the column list is empty, the node type is still V1 — go
   back to step 0 and point `@nodeType` at a V2 package type (ask before
   upgrading an in-use type).

`coa create`/`coa run` execute SQL DIRECTLY against the warehouse (local
development, not deployment). Stop after the dry-run unless the user wants to
materialize the table; cloud deploy is a separate git-push + web-UI flow.
