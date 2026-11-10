---
name: coalesce-pipelines
description: Use when working in a Coalesce Transform repository (data.yml + nodes/ with <LOCATION>-<NAME>.sql/.yml files) — building, editing, validating, or running data transformation pipelines with the coa CLI, including editing V1 .yml nodes and shared config (data.yml, locations, environments, jobs, node types). Start here; it routes to the more specific coalesce-* skills.
---

<!-- coalesce-node-managed: true -->

# Coalesce Pipelines

A Coalesce Transform repository is a Git-backed data transformation DAG. Nodes live in a flat `nodes/` directory as `<LOCATION>-<NAME>.sql` (V2) or `<LOCATION>-<NAME>.yml` (V1). Locations, environments, jobs, subgraphs, node types, and macros are YAML. The `coa` CLI validates the repo and runs SQL against the warehouse for local development.

`coa describe <topic>` and `coa describe schema <type>` are the source of truth for every format. The bundled example-repository fails `coa validate`, so never copy its shapes.

The other coalesce-\* skills assume everything on this page.

## Orient first

1. If `.claude/workspace-context.json` exists, read it first. It holds the node inventory, edges, jobs, subgraphs, environments, and diagnostics.
2. Otherwise use `coa describe structure`, `coa create -d <repo> --list-nodes`, and the files themselves.
3. In a cold workspace (no `nodes/`, or `--list-nodes` is empty), start from the warehouse: `coa sources list` shows the tables per location and `coa sources add` scaffolds Source nodes. Never hand-write Source YAML.
4. List the node types you have before naming one (see "Node types").

## Which format to author

- Source nodes are always V1 `.yml`.
- Every other node is V2 `.sql` when a `fileVersion: 2` node type exists for the type you need, and V1 `.yml` otherwise. The `fileVersion` in the type's `definition.yml` decides, never the platform or the layer.
- Both formats are supported and freely authorable. V1 is not a workaround.
- When a type has both a V1 and a V2 definition, use V2 if the node's value is its SQL and V1 if it is configuration (an SCD2 Dimension). `@isBusinessKey` and `@isChangeTracking` work in both.
- A `.sql` node pointed at a V1 type (`fileVersion: 1` or absent) still loads, but its columns are silently empty and the DDL/DML is broken, with no error.
- `@nodeType` (V2 annotation) and `operation.sqlType` (V1 field) name the same thing.

## Node types: find one, never author one

Type names vary by workspace, so read them off disk before you name one:

- `nodeTypes/<DisplayName>-<ID>/definition.yml` holds workspace-local types.
- `.coa/cache/packages/<alias>/nodeTypes/<Name>-<id>/definition.yml` holds package types, a read-only tree that `coa install` regenerates.

In each `definition.yml`, `name`, `description`, and `nodeMetadataSpec` tell you the layer, `fileVersion` tells you the format, and the `id` field is the value for `@nodeType()` (`<alias>:::<id>` for a package type). Never parse the id from the folder name (names and ids can both contain dashes).

- The base packages ship no `Stage` type. Their staging type is typically `Work` (`base-node-types:::204`).
- The built-in names (`Stage`, `View`, `Dimension`, `Fact`, `persistentStage`) are V1 and resolve only when those types exist in `nodeTypes/`; `coa init` writes them there when the base package is unavailable.
- A guessed name fails with `error[missingNodeType]: node type "X" is not available`.
- Use the right type for the layer (staging, persistent staging, fact/dimension, view), not the staging type for everything.

If no suitable type is on disk:

1. Run `coa install -d <dir>` and look again. It is safe without asking. It hydrates only packages already declared under `packages/`; "No packages to install." means none are declared, and the fix for a missing base package is `coa init` (ask first). To add another Marketplace package, use coalesce-install-package.
2. If there is still no `fileVersion: 2` type but a suitable V1 type is on disk, author the node as V1 `.yml` and continue. If there is no suitable type at all, stop and ask before running `coa init`. The base package exists only in the production registry, so a lower environment may never have one.

Say which path you took. Create, modify, or upgrade a node type only when the user explicitly asks, and ask first even then; `coa describe node-types` and the yaml-spec reference cover the format. Do not fix a `.sql` node's empty columns by bumping its type's `fileVersion`: that changes the DDL/DML of every node using the type.

## Core loop (one node at a time)

1. Edit the node.
2. `coa validate -d <repo>`
3. `coa create -d <repo> --include "{ NODE }" --dry-run --verbose`
4. `coa run -d <repo> --include "{ NODE }" --dry-run --verbose`
5. When the user wants it materialized: `coa create`, then `coa run`, then verify. Otherwise stop after the dry-runs.

Move to the next node once this one is clean.

Both dry-runs are required. The create dry-run proves only that the DDL renders. Run templates gate their DML on `config`, so a node missing its type's config defaults renders zero run SQL and would load no data.

Clean means 0 errors and 0 warnings. `coa validate` exits 0 with warnings standing, and a warning is a real defect. The common one is `warning[namedDependencyUnresolved]: "LOC"."NAME" is not a node`: a `ref()` names a location where that node file does not exist. Fix the location argument to where `nodes/LOC-NAME.*` actually lives (a `STG_*` node lives in its own location, such as `TARGET`, not in `SRC`). Never delete the ref or leave the warning.

`coa create` and `coa run` without `--dry-run` execute SQL directly against the warehouse. That is local development, not deploy. Work reaches the cloud only through git push, then plan and deploy (coalesce-deploy).

Before any warehouse command, run `coa profile list -d <dir>`. If the workspace is bound to a profile, omit `--profile`, because the flag overrides the binding. If nothing is bound, pass `--profile <name>` for the workspace's platform on `sources`, `create`, `run`, `install`, and `doctor`. `coa validate` takes no profile.

## Rules

1. Never modify or reuse an existing `@id` (node or column). New ids are fresh UUIDs.
2. In a `.sql` node, `@id` and `@nodeType` are the first lines and are written bare, never behind `--` or inside `/* */`. `coa` cannot read a commented annotation: the node is silently dropped from the graph while validate still reports 0 errors.
3. Reference upstream nodes with `{{ ref("LOC", "NAME") }}`, both arguments. Never hardcode `db.schema.table`.
4. Before deleting a node, check its dependents with `--include "{ NODE }+"` or a ref search. When renaming, update every reference (coalesce-rename-node-cascade).
5. Change only what the task requires.

## Ask first

You may, without asking: create or edit the nodes the user named, and run read-only commands (`coa validate`, `coa describe`, any `--dry-run`, `coa install`).

Ask before:

- editing nodes outside the request;
- touching shared config: `data.yml`, locations, `workspace.yml`, environments, jobs, subgraphs, macros, `packages/`, or anything under `nodeTypes/` (including a `fileVersion` bump or template swap);
- running `coa create` or `coa run` without `--dry-run`, unless the request asked for materialized tables;
- running `coa init` or `coa doctor --fix`;
- pushing to a remote, unless the request asked for the push.

Shared config is used by many nodes, and an edit there can silently break unrelated ones.

## Reference

- [coa CLI](reference/coa-cli.md): describe topics, selectors, init, doctor, install, profiles, approval gates.
- [SQL format](reference/sql-format.md): V2 node files, annotations, refs, naming.
- [YAML spec](reference/yaml-spec.md): data.yml, locations, workspace, environments, job and subgraph schemas, node type folders, and what to check when editing shared config.
- [V1 nodes](reference/v1-nodes.md): read before touching any `nodes/*.yml`. File shape, the id-based column graph, safe edits, and the template for authoring one.

## Other coalesce-\* skills

- **coalesce-sql-transformation**: edit SQL inside existing V2 nodes.
- **coalesce-pipeline-structure**: create, delete, rename, or rewire nodes, jobs, subgraphs.
- **coalesce-cloud-api**: `coa init`, `doctor`, `install`, profiles, credentials.
- **coalesce-git-publication**: branch, commit, push.
- **coalesce-deploy**: environments, `coa plan`, `deploy`, `refresh`, run results. All ask first.
- **coalesce-review-risk**: read-only review of changes.
- Recipes: **coalesce-create-stage-node**, **coalesce-add-column**, **coalesce-rename-node-cascade**, **coalesce-create-job**, **coalesce-install-package**.
- **coalesce-create-app**: build a workspace app in `apps/<id>/` that Coalesce Desktop or `coa serve` opens as a tab.
