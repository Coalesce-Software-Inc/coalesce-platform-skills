---
name: coalesce-workspace-config
description: Use when a task touches Coalesce shared workspace configuration — data.yml, locations.yml, workspace.yml, environments/, or node type definitions and Jinja templates in nodeTypes/. Everything here is high-risk shared config requiring user confirmation before edits.
---
<!-- coalesce-node-managed: true -->

# Workspace Configuration

Scope: the SHARED, high-risk files — `data.yml`, `locations.yml`,
`workspace.yml`, `environments/`, and node type definitions in `nodeTypes/`.
Treat `coa describe <topic>` and `coa describe schema <type>` as the source of
truth — NOT the example files (the bundled example-repository fails
`coa validate`).

File shapes, the location-name consistency rule, node type authoring, and the
V2 CTAS template pattern:
[yaml-spec reference](../coalesce-pipelines/reference/yaml-spec.md).
Credentials and `~/.coa/config`:
[coa-cli reference](../coalesce-pipelines/reference/coa-cli.md).

## GUARDRAIL — surface the choice FIRST

Every file in this scope is shared across many nodes; an edit here can
SILENTLY break unrelated nodes. None of it is in-scope-without-asking. Before
editing node types, `locations.yml`, `workspace.yml`, `environments/`,
`data.yml`, jobs, macros, or bumping `fileVersion` / swapping template
patterns: STOP, explain the impact, and get the user's go-ahead. Read-only
commands (`coa describe`, `coa validate`, `coa doctor` without `--fix`, any
`--dry-run`) you may run freely. Never put secrets in repo files —
credentials live in `~/.coa/config`.

## The fileVersion 1 vs 2 trap

V2 `.sql` nodes (the default for staging/intermediate transforms) REQUIRE a node type with
`fileVersion: 2` in its `definition.yml`. With fileVersion 1 (or absent), a
`.sql` node parses to `columns: []` — no error, but broken DDL/DML at render.
For V2, `col.dataType` is `UNKNOWN`, so templates MUST use the CTAS pattern
(iterate `sources` → `source.columns`, guard create with `WHERE 1=0`) and
never emit `{{ col.dataType }}`. V1 node types use explicit-column DDL. Full
template example in the yaml-spec reference.

## Workflow (define → validate → dry-run → verify)

1. Confirm the change with the user (guardrail above).
2. `coa describe schema <type>` to confirm the exact shape; edit the file.
3. `coa validate -d <dir>` (add `--json`) — schemas + 15 graph scanners
   (storage locations, node types, missing types, duplicates).
4. `coa doctor -d <dir> [--profile <p>]` — verifies
   data.yml/locations.yml/workspace.yml, auth, and warehouse connectivity.
   `coa doctor --fix` can bootstrap a missing `workspace.yml` / update
   `.gitignore` — still a shared-file change, confirm with the user first.
5. For node-type/template edits, prove the contract holds:
   `coa create -d <dir> --include "{ nodeType: \"<Name>\" }" --dry-run
   --verbose` (and `--json`) — confirm columns render and SQL is non-empty
   for affected nodes.
6. `coa create`/`coa run` execute SQL DIRECTLY against the warehouse — LOCAL
   development, NOT deploy/publish. Cloud plan/deploy is separate (git push →
   Coalesce web UI/CI).
