---
name: coalesce-sql-transformation
description: Use when editing the SQL inside existing Coalesce SQL node files (.sql, formerly V2) — changing column expressions, joins, filters, CTEs, inline column annotations, or ref() macros. Not for creating/deleting node files (use coalesce-pipeline-structure).
---

<!-- coalesce-node-managed: true -->

> **Prerequisite:** load `coalesce-pipelines` first if it is not already loaded in this session. This skill assumes its rules and core loop.

# SQL Transformation

Scope: the SELECT body of existing `nodes/<LOCATION>-<NAME>.sql` files. Column expressions, joins, filters, aggregations, CTEs, inline column annotations, and `{{ ref(...) }}` macros. Format details: [sql-format reference](../coalesce-pipelines/reference/sql-format.md).

## Out of scope here

- Creating or deleting node files (coalesce-pipeline-structure).
- `.yml` nodes ([YAML nodes reference](../coalesce-pipelines/reference/v1-nodes.md)), jobs, subgraphs, locations, macros.
- Changing `@nodeType`, bumping a type's `fileVersion`, or anything under `nodeTypes/`. If the node's type turns out to be a YAML type (`extensionVersionMismatch` from validate), stop and ask.
- Nodes the user did not name.

## Workflow, per node

1. Read `.claude/workspace-context.json` if present, then the target file and the upstream nodes it reads from. Confirm every column you plan to use exists upstream.
2. Check that each `{{ ref("LOC", "NAME") }}` in the file points at a real `nodes/LOC-NAME.sql` or `.yml`. A ref with the wrong location is a latent bug in the node you were asked to edit: fix the location argument and say that you did.
3. Make the edit. Keep `@id` and `@nodeType` untouched on the first lines, keep the file's alias and quote style, and give every new ref both arguments in double quotes. Use only reserved annotations and ones the node type declares (sql-format reference).
4. Verify:
   - `coa validate -d <dir>`
   - `coa create -d <dir> --include "{ NODE }" --dry-run --verbose`
   - `coa run -d <dir> --include "{ NODE }" --dry-run --verbose`
5. Repeat until validate shows 0 errors and 0 warnings and both dry-runs render the change. Touch downstream nodes only if asked.
