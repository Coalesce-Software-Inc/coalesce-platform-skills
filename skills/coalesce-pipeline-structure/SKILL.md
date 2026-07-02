---
name: coalesce-pipeline-structure
description: Use when creating, deleting, renaming, or rewiring Coalesce nodes, subgraphs, or jobs — changing the structural topology of the transformation DAG. Not for editing SQL inside an existing node (use coalesce-sql-transformation).
---
<!-- coalesce-node-managed: true -->

# Pipeline Structure

Scope: creating, deleting, renaming, and rewiring nodes, subgraphs, and jobs —
the structural topology of the transformation DAG. The `coa` CLI is the source
of truth and the verifier: when unsure of a shape, run `coa describe <topic>`
or `coa describe schema <type>` instead of guessing. Never copy shapes from
the example repo files — they use legacy shapes that fail `coa validate`.

Shared references:
[sql-format](../coalesce-pipelines/reference/sql-format.md) (node files, refs,
annotations) and
[yaml-spec](../coalesce-pipelines/reference/yaml-spec.md) (job/subgraph
schemas, node types).

## Core loop (every change)

Define → `coa validate -d <dir>` →
`coa create --dry-run --include "{ NODE }"` (add `--verbose` for SQL) →
`coa create` → `coa run` → verify → iterate. `coa create`/`coa run` execute
SQL DIRECTLY against the warehouse — LOCAL development, NOT deploy. Cloud
plan/deploy is separate (git push → web UI/CI).

## In scope without asking

- Create/edit the specific nodes the user asked for in `nodes/`.
- Read-only commands: `coa validate`, `coa describe`, any `--dry-run`.
- Creating a BRAND-NEW node type when the requested `.sql` node needs one and
  no compatible V2 type exists (greenfield bootstrap). A new type is referenced
  only by your new nodes, so it can't break existing ones — it's a prerequisite
  of the request. Recipe: [sql-format → Bootstrapping a V2 node type](../coalesce-pipelines/reference/sql-format.md).

## ASK FIRST (shared config — can silently break unrelated nodes)

- Editing nodes NOT in the request.
- Editing, removing, or replacing an EXISTING node type (`nodeTypes/*`) that
  other nodes already use, or bumping its `fileVersion` / swapping its template
  patterns.
- Changing locations, workspaces, environments, jobs, macros, or `data.yml`.

## Creating a node (V2 .sql — preferred for ALL transformations)

- File: `nodes/<LOCATION>-<NAME>.sql`. The filename sets location + name;
  `@location` is ignored. Case-sensitive; NAME unique (`.yml` and `.sql`
  cannot coexist for the same location+name); UPPER_SNAKE_CASE by repo
  convention; `nodes/` has no subdirectories.
- Required top annotations before any SQL: `@id("<fresh UUID>")` (never reuse
  an existing one) and `@nodeType("<TypeID>")` — which MUST resolve to a
  `fileVersion: 2` node type, or columns are SILENTLY EMPTY (broken DDL/DML).
- Use V1 (`.yml`, fileVersion 1) only for Source nodes and V1-only types.
- Refs, column annotations, and a full example: see the sql-format reference.
  Only `@isBusinessKey`, `@isChangeTracking`, `@id`, `@description` exist.

## Impact analysis (lineage selectors)

- Downstream dependents of NODE: `--include "{ NODE }+"`
- Upstream sources of NODE: `--include "+{ NODE }"`

Use these (not manual text search) before deleting or renaming.

## Delete / rename / rewire

- Delete: confirm `{ NODE }+` has no dependents (or rewire them first).
- Rename: rename the FILE (keep the same `@id`), then update every downstream
  `{{ ref("LOC","OLD") }}` to the new name, plus any job/subgraph selectors —
  the coalesce-rename-node-cascade skill has the full procedure.
- After any change, re-run `coa validate` to catch broken references.

## Job and subgraph shapes

Jobs are NOT a steps array (`includeSelector`/`excludeSelector` strings,
integer-string `id`); subgraphs store selector STRINGS in `steps` (NOT a
`nodes` array). Exact schemas, examples, and legacy-shape warnings: see the
yaml-spec reference, and confirm with `coa describe schema job` /
`coa describe schema subgraph`. Jobs and subgraphs are shared config — ask
first.
