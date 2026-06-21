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
   are fresh UUIDs.
2. NEVER delete a node without checking downstream dependents
   (`--include "{ NODE }+"` or a ref search).
3. When renaming a node, update ALL downstream `{{ ref(...) }}` calls (see the
   coalesce-rename-node-cascade skill).
4. Prefer V2 `.sql` for new transformation nodes — but only against a
   `fileVersion: 2` node type; otherwise columns are silently empty (see
   reference/sql-format.md).
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

ASK FIRST: editing nodes NOT in the request; adding/removing/editing node
types (`nodeTypes/*`); changing locations, workspace/environments, jobs,
macros, or `data.yml`; bumping `fileVersion` or swapping template patterns;
`coa init` / `coa doctor --fix`. These are shared across many nodes and can
silently break unrelated ones — stop and surface the choice.

## When to use the other coalesce-* skills

- **coalesce-sql-transformation** — editing SQL inside existing V2 nodes
  (columns, joins, annotations, refs).
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
