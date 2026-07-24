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
layers build on a stable name. `coa describe sql-format` and `coa describe
node-types` are the source of truth; consult them if anything below is unclear.

> NOTE: the bundled example repo may currently FAIL `coa validate` for reasons
> unrelated to your node (legacy job/subgraph/location/env/nodeType shapes, a
> missing `workspace.yml`/`data.yml`). Treat `coa describe schema <type>` as
> ground truth over the example files. If `coa validate`/`coa create` errors
> point at workspace config you were not asked to touch, surface that to the
> user rather than silently "fixing" shared config (see step 0 and step 4).

## 0. Critical preflight — does a V2 Stage node type exist?

A `.sql` node is a V2 node and REQUIRES a node type whose `definition.yml` has
`fileVersion: 2`. If you point `@nodeType(...)` at a V1 Stage type (the built-in
default, `fileVersion: 1` or absent), the node loads but its columns are
**silently empty** (`columns: []`) — `coa create`/`coa run` then emit broken
DDL/DML with no error. (`coa describe sql-format`, `coa describe node-types`.)

Check what Stage type actually exists:

- Look in `nodeTypes/` for a Stage definition. Node types live in
  `nodeTypes/<DisplayName>-<ID>/definition.yml`; the `@nodeType()` value is the
  `id` field (also the part after the last dash in the folder name). Read its
  `fileVersion` (absent or `1` = V1; `2` = V2).
- `coa describe schema nodeType` documents the shape; `coa describe node-types`
  covers authoring.

Then branch:

- **A V2 Stage node type exists (`fileVersion: 2`)** — proceed; author a `.sql`
  node (preferred for all transformations). Note its `id` for step 3.
- **`nodeTypes/` has no V2 Stage type (greenfield)** — install one, then
  proceed. This is a sanctioned setup step: a brand-new node type can't break
  existing nodes because none use it yet, so do it WITHOUT asking and report it
  in your summary. Follow `coa describe node-types` for the folder layout,
  `definition.yml` (`fileVersion: 2`), and the V2 `create.sql.j2` / `run.sql.j2`
  template pattern — the full recipe and the validate step live in the
  **coalesce-workspace-config** skill ("Installing a V2 node type"). Note the
  new type's `id` for step 3.
- **Only a V1 Stage type exists AND other nodes already use it** — upgrading it
  changes DDL/DML for every node of that type, so **STOP and ASK the user
  first** before bumping its `fileVersion`. (Do not fall back to a V1 `.yml`
  node — `.yml` is legacy, reserved for Source nodes.)

  Never silently write a `.sql` node against a V1 Stage type — that is the
  empty-columns trap above.

## 1. Gather the source

1. Identify the source node, its location, and its columns. Use `coa` as the
   authoritative surface: `coa create -d <dir> --list-nodes` (or `coa run -d
   <dir> --list-nodes`) to enumerate nodes, and read the source file
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

Required top annotations, before any SQL:

- `@id("<UUID>")` — PREFER a fresh UUID v4. NEVER reuse or modify an existing
  node's `@id`; duplicate IDs collide across the workspace.
- `@nodeType("<TypeID>")` — the V2 Stage type ID you found in step 0 (the `id`
  from `nodeTypes/<DisplayName>-<ID>/definition.yml`, or a package type ID).

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
step 0. `Stage` is a valid built-in common type ID, but the built-in `Stage` is
V1 — only use `@nodeType("Stage")` literally if a `fileVersion: 2` node type
with that exact `id` exists in `nodeTypes/`. Otherwise substitute the real V2
type ID.

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
   back to step 0 (install a V2 type if greenfield; ask before upgrading an
   in-use type).

`coa create`/`coa run` execute SQL DIRECTLY against the warehouse (local
development, not deployment). Stop after the dry-run unless the user wants to
materialize the table; cloud deploy is a separate git-push + web-UI flow.
