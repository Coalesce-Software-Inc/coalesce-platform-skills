---
name: coalesce-pipelines
description: Use when working in a Coalesce Transform repository (data.yml + nodes/ with <LOCATION>-<NAME>.sql/.yml files) — building, editing, validating, running, or deploying data transformation pipelines with the coa CLI. Start here; it routes to the more specific coalesce-* skills.
---
<!-- coalesce-node-managed: true -->

# Coalesce Pipelines

A Coalesce Transform repository is a Git-backed representation of a data
transformation DAG. Nodes are authored as **SQL nodes** — SQL files with
lightweight annotations (`nodes/<LOCATION>-<NAME>.sql`) — or **YAML nodes**
(`nodes/<LOCATION>-<NAME>.yml`); workspace metadata (locations, environments,
jobs, subgraphs, node types, macros) is YAML. The `coa` CLI validates the
repo, executes SQL against the warehouse for local development, and plans
and deploys to Coalesce Environments.

Coalesce formerly called these Node V2 (SQL) and Node V1 (YAML). The app's
**Build Settings > Node Types** and the `coa describe` / `coa validate` text
still show V1/V2; read V2 as SQL and V1 as YAML. The internal marker is
unchanged: a SQL node type has `fileVersion: 2` in its `definition.yml`, a
YAML node type has `1` or none.

**Format rule:** Source nodes are always YAML `.yml`. For every other node,
author a SQL `.sql` node when a SQL node type (`fileVersion: 2`) exists for
the target node type; otherwise author a YAML `.yml` node. The `fileVersion`
in `nodeTypes/<ID>/definition.yml` decides this, never the platform. Both
kinds are supported, and YAML is not a workaround.

## Glossary and authoring policy

"Author" applies to two different artifacts with two different policies —
always be explicit about which one you mean:

| Term | Artifact | Files | Authoring policy |
|------|----------|-------|------------------|
| **SQL node** (formerly V2) | A transformation instance on a SQL node type | `nodes/<LOC>-<NAME>.sql` | **Author freely** — files + CLI or the Coalesce UI, whichever fits. |
| **YAML node** (formerly V1) | A transformation instance on a YAML node type | `nodes/<LOC>-<NAME>.yml` | **Author freely** — same policy. The UI generates this format natively; authoring it by hand is supported but intricate (see coalesce-v1-yaml-nodes). |
| **Node type** | The reusable template contract | `nodeTypes/<Name>-<ID>/` (definition.yml + create.sql.j2 + run.sql.j2) | **Search first, never author on your own.** Prefer existing packaged node types — they are official (`coa install`, then check `nodeTypes/` and `.coa/cache/packages/*/nodeTypes/`). If no SQL node type fits, author the node as YAML `.yml` instead. A custom node type is created or extended ONLY on the user's explicit request — ASK FIRST (see coalesce-workspace-config). |

Disambiguation traps: `fileVersion: 1/2` appears on both node files and node
type definitions (a `.sql` node requires a `fileVersion: 2` node type);
`@nodeType` (SQL node annotation) and `operation.sqlType` (YAML node field)
name the same concept.

## Orient first

1. If `.claude/workspace-context.json` exists in the repo, READ IT FIRST — it
   carries the current node inventory, edges, jobs, subgraphs, environments,
   and diagnostics, and tells you what exists and where.
2. If it does not exist (running outside the Coalesce Node app), orient with
   `coa describe structure`, `coa create -d <repo> --list-nodes`, and file
   inspection.
3. In a COLD workspace — no `nodes/` directory, or `--list-nodes` empty — the
   entry points are the warehouse, not the graph: `coa sources list` shows the
   tables available per location, and `coa sources add` scaffolds Source nodes
   from them. Start there, then build downstream nodes on top.
4. Also list the node types you actually have before naming one: read
   `nodeTypes/` and `.coa/cache/packages/*/nodeTypes/` (see Rules 4 and 6).

## Reference (read as needed)

- [coa CLI](reference/coa-cli.md) — describe topics, the core loop, selectors,
  init/doctor/install, the Cloud Operations commands, approval gates,
  local-vs-deploy.
- [SQL format](reference/sql-format.md) — SQL vs YAML nodes, `@id`/`@nodeType`,
  `ref()` macros, reserved and declared annotations, naming.
- [YAML spec](reference/yaml-spec.md) — data.yml, locations, workspace,
  environments, job/subgraph schemas, where node types come from, the SQL
  node type template context.

## Core loop (every change)

Define → `coa validate -d <repo>` → `coa create --dry-run --include "{ NODE }"`
(add `--verbose` for SQL) → `coa run --dry-run --verbose --include "{ NODE }"`
→ `coa create` → `coa run` → verify → iterate, one node at a time. Both
dry-runs are mandatory: `create --dry-run` only proves the DDL renders, while a
node whose `config` is missing its node-type defaults renders ZERO run SQL and
would silently load no data (see coalesce-pipeline-structure).
`coa create`/`coa run` without `--dry-run` execute SQL DIRECTLY against the
warehouse — that is LOCAL development, NOT deploy. Deploying is a separate,
approved step: commit and push, then `coa plan` / `coa deploy` against an
Environment (or the Coalesce web UI) — see coalesce-cloud-api ("Deploy
journey").

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
   by layer: Source nodes are always YAML `.yml`; every other node is a SQL
   `.sql` node when a SQL node type exists for its target type, otherwise a
   YAML `.yml` node. Both are freely authorable; neither is "legacy". When
   both kinds of type exist for a layer, prefer SQL where the node's value is
   its SQL (transforms, metrics, joins) and YAML where its value is
   configuration (SCD2 Dimensions and other config-driven patterns). A `.sql`
   node works only against a `fileVersion: 2` node type; otherwise columns
   are silently empty (see reference/sql-format.md).
   SQL node types come from the installed base node types package — `coa
   install` materializes them under `.coa/cache/packages/<alias>/nodeTypes/`,
   and each materialized definition.yml carries the resolvable
   `<alias>:::<id>` id to use in `@nodeType()`. Node types are SEARCH-FIRST:
   if none are present, run `coa install -d <dir>` and re-check the file
   system; never author one (see coalesce-workspace-config). `coa install`
   hydrates only packages already declared under `packages/` and prints "No
   packages to install." otherwise — `coa init` writes that declaration, so
   if `packages/` is absent the fix is to re-run `coa init` (ask the user
   first), never to hand-create shared config. When no SQL node type exists
   for the target node type (the package may be unavailable), author YAML
   `.yml` instead; that is supported, not a workaround.
5. Reference upstream nodes with `{{ ref("LOC", "NAME") }}` (both args).
   Never hardcode `db.schema.table`.
6. Use the correct node type per layer (staging → persistent staging →
   fact/dimension → view); don't use the staging type for everything. NODE
   TYPE NAMES VARY BY WORKSPACE — never assume a type called `Stage` exists.
   In the base node types packages the staging-layer type is typically named
   `Work` (e.g. `base-node-types:::204`). Discover the real names before
   naming one: list `nodeTypes/` and `.coa/cache/packages/*/nodeTypes/` and
   read each `definition.yml` (`name`, `description`, `nodeMetadataSpec`).
   Plain built-in names (`Stage`, `View`, `Dimension`, `Fact`,
   `persistentStage`) resolve ONLY when those built-in YAML types are present
   in `nodeTypes/` — `coa init` writes them there when the base package is
   unavailable. Guessing a name yields
   `error[missingNodeType]: node type "X" is not available`.
7. Keep changes minimal — modify only what the task requires.
8. After editing, run `coa validate`, then `coa create --dry-run` AND
   `coa run --dry-run --verbose`, before executing anything. Also pass
   `--profile <name>` matching the workspace platform on every command that
   accepts one (`sources`, `create`, `run`, `install`, `doctor`, and the
   cloud commands); `coa validate` has no `--profile` flag.
9. Treat `coa describe` and `coa <command> --help` as the source of truth.
   The bundled example-repository FAILS `coa validate` — never copy its
   shapes. Where `coa describe` still says V1/V2 or "no deployment step",
   the binary's `--help` is the authority (see reference/coa-cli.md).

## Guardrail — ask before editing shared config

In scope without asking: create/edit the specific nodes the user requested,
and read-only commands (`coa validate`, `coa describe`, any `--dry-run`).

ASK FIRST: editing nodes NOT in the request; creating, modifying, or removing
ANY node type (incl. bumping its `fileVersion` or swapping its template
pattern); changing locations, workspace/environments, jobs, macros, or
`data.yml`; `coa init` / `coa doctor --fix`; and every cloud-mutating command
(`coa deploy`, `coa refresh`, `coa environments|projects create|update|
delete`). These are shared across many nodes, or visible to the whole team —
stop and surface the choice.

Node types are search-first, and the search ends in a package, never in a
file you write. Never author a node type to satisfy a `.sql` node. Base types
come from the installed base node types package; if none are present, run
`coa install -d <dir>` (safe without asking — but it is a no-op unless
`packages/` already declares a package), re-check `nodeTypes/` and
`.coa/cache/packages/*/nodeTypes/`, and, failing that, author the node as
YAML `.yml` and continue. A custom net-new type is authored only when the
user explicitly asks — and even then, ASK FIRST. Report which path you took
and why. See coalesce-workspace-config.

## When to use the other coalesce-* skills

- **coalesce-sql-transformation** — editing SQL inside existing SQL nodes
  (columns, joins, annotations, refs).
- **coalesce-v1-yaml-nodes** — reading, editing, and authoring YAML `.yml`
  nodes (the UI/API-generated format): file shape, the id-based column graph,
  and what is safe to edit. Use it whenever a task touches a `nodes/*.yml`
  file.
- **coalesce-pipeline-structure** — creating/deleting/renaming/rewiring nodes,
  jobs, subgraphs (DAG topology).
- **coalesce-workspace-config** — data.yml, locations, workspace,
  environments, node type definitions/templates.
- **coalesce-cloud-api** — coa init/doctor/install, credentials, and the
  deploy journey (environments, plan, deploy, refresh).
- **coalesce-git-publication** — branches, commits, pushing work so it can be
  planned/deployed.
- **coalesce-review-risk** — read-only review of changes: validation evidence,
  blast radius, risk flags.
- Task recipes: **coalesce-create-stage-node**, **coalesce-add-column**,
  **coalesce-rename-node-cascade**, **coalesce-create-job**.
