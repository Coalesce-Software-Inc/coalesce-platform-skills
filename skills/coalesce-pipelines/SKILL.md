---
name: coalesce-pipelines
description: Use when working in a Coalesce Transform repository (data.yml + nodes/ with <LOCATION>-<NAME>.sql/.yml files) — building, editing, validating, or running data transformation pipelines with the coa CLI. Start here; it routes to the more specific coalesce-* skills.
---
<!-- coalesce-node-managed: true -->

# Coalesce Pipelines

A Coalesce Transform repository is a Git-backed representation of a data
transformation DAG. Nodes are authored as SQL files with lightweight
annotations (`nodes/<LOCATION>-<NAME>.sql`, the V2 format) or YAML
(`nodes/<LOCATION>-<NAME>.yml`, the V1 format); workspace metadata (locations,
environments, jobs, subgraphs, node types, macros) is YAML. The `coa` CLI
validates the repo and executes SQL against the warehouse for local
development.

**Format rule:** Source nodes are always V1 `.yml`. For every other node,
author a V2 `.sql` node when a `fileVersion: 2` node type exists for the target
node type; otherwise author a V1 `.yml` node. The `fileVersion` in
`nodeTypes/<ID>/definition.yml` decides this, never the platform. Both formats
are supported, and V1 is not a workaround.

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
  environments, job/subgraph schemas, where node types come from.

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
4. Choose node format by the node type's `fileVersion` (format rule above), not
   by layer: Source nodes are always V1 `.yml`; every other node is V2 `.sql`
   when a `fileVersion: 2` node type exists for its target type, otherwise V1
   `.yml`. A V2 `.sql` node works only against a `fileVersion: 2` node
   type; otherwise columns are silently empty (see reference/sql-format.md).
   V2 types come from the installed base node types package — `coa install`
   materializes them under `.coa/cache/packages/<alias>/nodeTypes/`, and each
   materialized definition.yml carries the resolvable `<alias>:::<id>` id to
   use in `@nodeType()`. If none are present, run `coa install -d <dir>`;
   never author one (see coalesce-workspace-config).
   When no `fileVersion: 2` type exists for the target node type (the package
   may be unavailable), author V1 `.yml` instead; that is supported, not a
   workaround.
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

ASK FIRST: editing nodes NOT in the request; creating, modifying, or removing
ANY node type (incl. bumping its `fileVersion` or swapping its template
pattern); changing locations, workspace/environments, jobs, macros, or
`data.yml`; `coa init` / `coa doctor --fix`. These are shared across many nodes
and can silently break unrelated ones — stop and surface the choice.

Never author a node type to satisfy a `.sql` node. Base types come from the
installed base node types package; if none are present, run `coa install -d
<dir>` (safe without asking) and, failing that, author the node as V1 `.yml`
and continue. A custom net-new type is authored only when the user explicitly
asks — and even then, ASK FIRST. See coalesce-workspace-config.

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
