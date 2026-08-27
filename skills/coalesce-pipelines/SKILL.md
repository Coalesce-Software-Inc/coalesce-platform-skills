---
name: coalesce-pipelines
description: Use when working in a Coalesce Transform repository (data.yml + nodes/ with <LOCATION>-<NAME>.sql/.yml files) — building, editing, validating, or running data transformation pipelines with the coa CLI. Start here; it routes to the more specific coalesce-* skills.
---
<!-- coalesce-node-managed: true -->

# Coalesce Pipelines

A Coalesce Transform repository is a Git-backed representation of a data
transformation DAG. Nodes are authored as SQL files with lightweight
annotations (`nodes/<LOCATION>-<NAME>.sql`) or YAML (`.yml` for Source and
V1-only types); workspace metadata (locations, environments, jobs, subgraphs,
node types, macros) is YAML. The `coa` CLI validates the repo and executes SQL
against the warehouse for local development.

## Glossary and authoring policy

"Author" applies to two different artifacts with two different policies —
always be explicit about which one you mean:

| Term | Artifact | Files | Authoring policy |
|------|----------|-------|------------------|
| **Node (V2)** | A transformation instance | `nodes/<LOC>-<NAME>.sql` | **Author freely** — files + CLI or the Coalesce UI, whichever fits. |
| **Node (V1)** | A transformation instance | `nodes/<LOC>-<NAME>.yml` | **Author freely** — same policy. The UI generates this format natively; authoring it by hand is supported but intricate (see coalesce-v1-yaml-nodes). |
| **Node type** | The reusable template contract | `nodeTypes/<Name>-<ID>/` (definition.yml + create.sql.j2 + run.sql.j2) | **Search first, author last.** Prefer existing packaged node types — they are official. Create or extend a custom node type ONLY when the use case cannot be met by an existing type. |

Disambiguation traps: `fileVersion: 1/2` appears on both node files and node
type definitions (a V2 `.sql` node requires a `fileVersion: 2` node type);
`@nodeType` (V2 annotation) and `operation.sqlType` (V1 field) name the same
concept.

## Orient first

1. If `.claude/workspace-context.json` exists in the repo, READ IT FIRST — it
   carries the current node inventory, edges, jobs, subgraphs, environments,
   and diagnostics, and tells you what exists and where.
2. If it does not exist (running outside the Coalesce Node app), orient with
   `coa describe structure`, `coa create -d <repo> --list-nodes`, and file
   inspection.

## Reference (read as needed)

- [coa CLI](reference/coa-cli.md) — describe topics, the core loop, selectors,
  init/doctor/install, approval gates, local-vs-deploy.
- [SQL format](reference/sql-format.md) — V2 vs V1 nodes, `@id`/`@nodeType`,
  `ref()` macros, the complete column annotation set, naming.
- [YAML spec](reference/yaml-spec.md) — data.yml, locations, workspace,
  environments, job/subgraph schemas, node type authoring.

## Core loop (every change)

Define → `coa validate -d <repo>` → `coa create --dry-run --include "{ NODE }"`
(add `--verbose` for SQL) → `coa create` → `coa run` → verify → iterate, one
node at a time. `coa create`/`coa run` execute SQL DIRECTLY against the
warehouse — that is LOCAL development, NOT deploy. Work reaches the cloud only
via git push, then plan/deploy in the Coalesce web UI or CI.

## Rules

1. NEVER modify or reuse an existing `@id` (node or column). New `@id` values
   are fresh UUIDs. In a `.sql` node, `@id` and `@nodeType` are BARE first
   lines — never prefixed with `--` or wrapped in `/* */`. A commented-out
   annotation is invisible to `coa`: the node is silently dropped from the
   graph (validate still shows 0 errors, but the node is never built). See
   reference/sql-format.md → "Write the annotations BARE".
2. NEVER delete a node without checking downstream dependents
   (`--include "{ NODE }+"` or a ref search).
3. When renaming a node, update ALL downstream `{{ ref(...) }}` calls (see the
   coalesce-rename-node-cascade skill).
4. Choose node format by where its value lives — V2 `.sql` when the node's
   value is its SQL (transforms, metrics, joins; the natural fit for file and
   agent authoring), V1 `.yml` when its value is configuration (Source nodes
   via `coa sources add`, and config-driven patterns like SCD2 Dimensions).
   Both formats are freely authorable; neither is "legacy". A V2 `.sql` node
   works only against a `fileVersion: 2` node type; otherwise columns are
   silently empty (see reference/sql-format.md). If no suitable V2 node type
   exists, SEARCH existing packaged node types first; create a custom type
   only when nothing fits (see coalesce-workspace-config).
5. Reference upstream nodes with `{{ ref("LOC", "NAME") }}` (both args).
   Never hardcode `db.schema.table`.
6. Use the correct node type per layer (Stage → Persistent Stage →
   Fact/Dimension → View); don't use Stage for everything.
7. Keep changes minimal — modify only what the task requires.
8. After editing, run `coa validate` then `coa create --dry-run` before
   executing anything.
9. Treat `coa describe` as the source of truth. The bundled example-repository
   FAILS `coa validate` — never copy its shapes.

## Guardrail — ask before editing shared config

In scope without asking: create/edit the specific nodes the user requested,
and read-only commands (`coa validate`, `coa describe`, any `--dry-run`).

ASK FIRST: editing nodes NOT in the request; modifying/removing a node type
that existing nodes use (incl. bumping its `fileVersion` or swapping its
template pattern); changing locations, workspace/environments, jobs, macros, or
`data.yml`; `coa init` / `coa doctor --fix`. These are shared across many nodes
and can silently break unrelated ones — stop and surface the choice.

Node types are search-first: when a needed node type is missing, look for an
existing packaged node type before creating one (`coa install`, the package
registry, or ask the user which packages their org uses). Installing a package
type or, when nothing fits, a NEW `fileVersion: 2` custom type in a workspace
with none of that layer can't break existing nodes — do it, then report which
path you took and why. See coalesce-workspace-config.

## When to use the other coalesce-* skills

- **coalesce-sql-transformation** — editing SQL inside existing V2 nodes
  (columns, joins, annotations, refs).
- **coalesce-v1-yaml-nodes** — reading/explaining V1 `.yml` nodes (the
  UI/API-generated format): file shape, the id-based column graph, and what is
  safe to edit. Use it whenever a task touches a `nodes/*.yml` file.
- **coalesce-pipeline-structure** — creating/deleting/renaming/rewiring nodes,
  jobs, subgraphs (DAG topology).
- **coalesce-workspace-config** — data.yml, locations, workspace,
  environments, node type definitions/templates.
- **coalesce-cloud-api** — coa init/doctor/install, credentials, cloud
  bootstrap and diagnostics.
- **coalesce-git-publication** — branches, commits, pushing work so it can be
  planned/deployed.
- **coalesce-review-risk** — read-only review of changes: validation evidence,
  blast radius, risk flags.
- Task recipes: **coalesce-create-stage-node**, **coalesce-add-column**,
  **coalesce-rename-node-cascade**, **coalesce-create-job**.
