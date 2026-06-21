---
name: coalesce-sql-transformation
description: Use when editing the SQL inside existing Coalesce V2 node files (.sql) — changing column expressions, joins, filters, CTEs, inline column annotations, or ref() macros. Not for creating/deleting node files (use coalesce-pipeline-structure).
---
<!-- coalesce-node-managed: true -->

# SQL Transformation

Scope: the SQL inside V2 node files (`.sql`, fileVersion 2) — the SELECT body,
column expressions, inline column annotations, and `{{ ref(...) }}` macros.
The `coa` CLI is the source of truth: run `coa describe sql-format` and
`coa describe schema <type>` whenever unsure, and prefer it over the bundled
example files (they currently FAIL `coa validate`).

Shared format rules (refs, annotations, V1/V2, naming):
[sql-format reference](../coalesce-pipelines/reference/sql-format.md).

## Allowed operations

- Edit existing `nodes/<LOCATION>-<NAME>.sql` files.
- Add/remove/reorder columns; change joins, filters, aggregations, CTEs.
- Add/update inline column annotations (only the real set: `@isBusinessKey`,
  `@isChangeTracking`, `@id`, `@description`).
- Fix SQL syntax or format violations.

## Constraints

- NEVER modify an existing `@id` (node or column). New `@id` values are fresh
  UUIDs; never reuse one.
- Do NOT change `@nodeType` as part of SQL work — swapping a node type is a
  shared-config change, ASK FIRST. Its value must match a node type in
  `nodeTypes/<ID>/` or a package type ID.
- Keep `@id` and `@nodeType` as the first lines, before any SQL.
- Refs take BOTH args: `{{ ref("LOCATION", "NODE_NAME") }}`. Prefer double
  quotes for new/edited refs; leave existing valid single-quoted refs alone.
  Never hardcode `db.schema.table`; never reduce to one arg.
- Keep Snowflake column aliases consistent with the file you are editing.
- Do NOT create or delete node files (coalesce-pipeline-structure's job).
- Do NOT touch non-SQL files (`.yml` nodes, jobs, subgraphs, locations,
  macros).
- V1-only node type? STOP and surface it — do not silently bump fileVersion or
  swap node types (the silently-empty-columns trap; see the reference).

## Workflow (per node)

1. Read `.claude/workspace-context.json` (if present), then the target `.sql`
   file.
2. Make the requested edit — only the node(s) asked for.
3. Verify with coa (LOCAL warehouse commands, not deployment):
   - `coa validate -d <dir>` (schema + scanners)
   - `coa create -d <dir> --include "{ NODE }" --dry-run --verbose` (inspect DDL)
   - `coa run -d <dir> --include "{ NODE }" --dry-run --verbose` (inspect DML,
     if relevant)
4. Fix and re-validate until clean. Iterate downstream nodes only if asked.

## Ask first (shared config — can break unrelated nodes)

Editing nodes outside the request; touching `nodeTypes/`, locations,
workspaces, environments, jobs, macros, `data.yml`; bumping `fileVersion` or
swapping node types / template patterns.
