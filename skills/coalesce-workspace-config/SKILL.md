---
name: coalesce-workspace-config
description:  Use when a task touches Coalesce shared workspace configuration — data.yml, locations.yml, workspace.yml, environments/, or node type definitions and Jinja templates in nodeTypes/. Everything here is high-risk shared config requiring user confirmation before edits.
---
<!-- coalesce-node-managed: true -->

> **Prerequisite — load `coalesce-pipelines` first.** If you have not already
> loaded the `coalesce-pipelines` skill in this session, load it now, read its
> "Orient first" step, core `coa` loop, and Rules, then return here. This skill
> assumes those invariants (bare `@id`/`@nodeType` first lines, `fileVersion: 2`
> node types, one-node-at-a-time validate → dry-run → create loop) are already
> in context.

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

**One sanctioned exception (see "Installing a V2 node type" below):** getting a
node type into a workspace that has *no* type of that layer — SEARCH-FIRST:
install an existing packaged node type when one fits (packages are official);
create a brand-new custom `fileVersion: 2` type only when nothing does. Either
way it can't break existing nodes, so proceed without asking and report which
path you took and why. Modifying or upgrading a node type that existing nodes
already depend on is NOT covered by this exception and still requires approval.

## The fileVersion 1 vs 2 trap

V2 `.sql` nodes REQUIRE a node type with `fileVersion: 2` in its
`definition.yml`. With fileVersion 1 (or absent), a `.sql` node parses to
`columns: []` — no error, but broken DDL/DML at render.

Template pattern note: current `coa` INFERS `col.dataType` for V2 nodes
(verified: fully typed DDL renders even for aggregate SELECTs), so
explicit-column DDL templates work. Older builds surfaced `UNKNOWN`; the CTAS
pattern (iterate `sources` → `source.columns`, guard create with `WHERE 1=0`)
remains the conservative fallback. Whichever pattern you use, PROVE it with
`coa create --dry-run --verbose` before authoring nodes against it. Full
template example in the yaml-spec reference.

## Installing a V2 node type

When a task needs a V2 `.sql` node but no `fileVersion: 2` node type of that
layer exists, the workspace must gain one before the `.sql` node can render.
`coa describe node-types` is the authoritative how-to — it documents the folder
layout, `nodeMetadataSpec`, and the exact V1-vs-V2 template patterns. Read it
and `coa describe schema nodeType`; do NOT copy template bodies from example
files (they may fail `coa validate`).

**Decide the path first — search before you author:**

1. **Search existing packaged node types FIRST.** Packages are the official,
   maintained types: check what the org already installed (`packages/`,
   `coa install`), the package registry, and ask the user which packages their
   team uses. If a packaged type covers the use case, install and use it.
2. **No existing type fits (greenfield)** — create a custom `fileVersion: 2`
   type WITHOUT asking; it can't break existing nodes because none use it yet.
   Report the new node type in your summary (name, `fileVersion: 2`, template
   pattern used) and note WHY no existing type fit.
3. **A V1 type is already in use by other nodes** — upgrading it changes the
   generated DDL/DML for *every* node of that type. STOP and ASK first; on
   approval, bump `fileVersion` and swap templates to the V2 pattern.
4. **Extending an existing type** (new declared annotations, template changes)
   follows the same rule as upgrading: if nodes already use it, ASK first.

**Install steps (greenfield):**
Reference `coa describe node-types` for examples of the following elements
1. Create `nodeTypes/<DisplayName>-<UUID>/` — the folder MUST contain three
   files: `definition.yml`, `create.sql.j2`, AND `run.sql.j2`. A node type with
   only `definition.yml` (no templates) renders nothing — every node of that
   type builds a zero-column / empty table. Prefer a real UUID for the ID to
   avoid collisions.
2. `definition.yml` — `fileVersion: 2`, `type: NodeType`, the UUID `id`, and a
   `nodeMetadataSpec` (capitalized/short/plural/tagColor; config/systemColumns
   as needed). Shape per `coa describe schema nodeType`.
3. `create.sql.j2` and `run.sql.j2` — the V2 CTAS template pattern. Do NOT
   hand-write your own Jinja from scratch and do NOT use `{{ node.sql }}` as the
   body — a template that doesn't iterate `sources`/`source.columns` renders
   degenerate DDL (empty projection or `SELECT *`), so every node of the type
   builds a zero-column table even when the node's SELECT lists columns. Copy
   the exact V2 templates from `coa describe node-types` verbatim; they are the
   authoritative, working pattern. The canonical V2 Stage pair is below — use it
   as-is (only swap the display name / colors) unless `coa describe` differs, in
   which case `coa describe` wins.



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
   `coa create -d <dir> --include "{ nodeType: \"<Name>\" }" --dry-run --verbose`
   (and `--json`) — confirm columns render and SQL is non-empty
   for affected nodes.
6. `coa create`/`coa run` execute SQL DIRECTLY against the warehouse — LOCAL
   development, NOT deploy/publish. Cloud plan/deploy is separate (git push →
   Coalesce web UI/CI).
