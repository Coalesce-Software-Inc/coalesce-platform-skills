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
SILENTLY break unrelated nodes. Before editing `locations.yml`,
`workspace.yml`, `environments/`, `data.yml`, jobs, macros, or modifying a node
type that other nodes already use (including bumping its `fileVersion` /
swapping its template pattern): STOP, explain the impact, and get the user's
go-ahead. Read-only commands (`coa describe`, `coa validate`, `coa doctor`
without `--fix`, any `--dry-run`) you may run freely. Never put secrets in repo
files — credentials live in `~/.coa/config`.

**One sanctioned exception (see "Installing a V2 node type" below):** creating a
brand-new `fileVersion: 2` node type in a workspace that has *no* V2 type of
that layer is a greenfield setup step — do it without asking, then report it.
Modifying or upgrading a node type that existing nodes already depend on is NOT
covered by this exception and still requires approval.

## The fileVersion 1 vs 2 trap

V2 `.sql` nodes (preferred for all transforms) REQUIRE a node type with
`fileVersion: 2` in its `definition.yml`. With fileVersion 1 (or absent), a
`.sql` node parses to `columns: []` — no error, but broken DDL/DML at render.
For V2, `col.dataType` is `UNKNOWN`, so templates MUST use the CTAS pattern
(iterate `sources` → `source.columns`, guard create with `WHERE 1=0`) and
never emit `{{ col.dataType }}`. V1 node types use explicit-column DDL. Full
template example in the yaml-spec reference.

## Installing a V2 node type

When a task needs a V2 `.sql` node but no `fileVersion: 2` node type of that
layer exists, the workspace must gain one before the `.sql` node can render.
`coa describe node-types` is the authoritative how-to — it documents the folder
layout, `nodeMetadataSpec`, and the exact V1-vs-V2 template patterns. Read it
and `coa describe schema nodeType`; do NOT copy template bodies from example
files (they may fail `coa validate`).

**Decide the path first:**

- **Greenfield (no V2 type of that layer in `nodeTypes/`)** — install one
  WITHOUT asking. This is the sanctioned setup step: it can't break existing
  nodes because none use it yet. Report the new node type in your summary
  (name, `fileVersion: 2`, template pattern used).
- **A V1 type is already in use by other nodes** — upgrading it changes the
  generated DDL/DML for *every* node of that type. STOP and ASK first; on
  approval, bump `fileVersion` and swap templates to the V2 pattern.

**Install steps (greenfield):**

1. Create `nodeTypes/<DisplayName>-<UUID>/` (prefer a real UUID for the ID to
   avoid collisions).
2. `definition.yml` — `fileVersion: 2`, `type: NodeType`, the UUID `id`, and a
   `nodeMetadataSpec` (capitalized/short/plural/tagColor; config/systemColumns
   as needed). Shape per `coa describe schema nodeType`.
3. `create.sql.j2` and `run.sql.j2` — the V2 template pattern from
   `coa describe node-types`. V2 `col.dataType` is `UNKNOWN`, so the create
   template must not emit `{{ col.dataType }}`; follow the pattern `coa describe`
   prescribes and confirm it renders (next section) rather than assuming.

**Validate the initial state (proves the trap is gone):**

- `coa validate -d <dir>` passes.
- `coa create -d <dir> --include "{ nodeType: \"<Name>\" }" --dry-run --json` —
  columns render and the SQL is non-empty. Empty columns mean the type is still
  effectively V1; fix before authoring nodes against it.

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
