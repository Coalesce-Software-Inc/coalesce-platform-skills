---
name: coalesce-workspace-config
description:  Use when a task touches Coalesce shared workspace configuration — data.yml, locations.yml, workspace.yml, environments/, or node type definitions and Jinja templates in nodeTypes/. Everything here is high-risk shared config requiring user confirmation before edits.
---
<!-- coalesce-node-managed: true -->

> **Prerequisite:** load `coalesce-pipelines` first if it is not already loaded
> in this session. This skill assumes its rules, its "Node types" section, and
> its core loop.

# Workspace Configuration

Scope: `data.yml`, `locations.yml`, `workspace.yml`, `environments/`, and node
type definitions under `nodeTypes/`. File shapes and template patterns:
[yaml-spec reference](../coalesce-pipelines/reference/yaml-spec.md).
Credentials and profiles:
[coa-cli reference](../coalesce-pipelines/reference/coa-cli.md).

## Confirm before every edit

Each of these files is used by many nodes, and an edit can silently break
unrelated ones. Before changing any of them, or a node type that nodes
already use, explain the impact and get the user's go-ahead. Read-only
commands (`coa describe`, `coa validate`, `coa doctor` without `--fix`, any
`--dry-run`) need no approval.

- Never put secrets in repo files. Credentials live in `~/.coa/config`,
  managed with `coa profile`.
- The `profile:` key in `workspace.yml` is a profile name written by
  `coa profile use` or `coa init --profile`, not by hand. Changing it repoints
  every local command in the directory at different credentials, so it also
  needs approval.

## Node types

Finding and choosing a type is covered in coalesce-pipelines ("Node types").
The rules that matter here:

- V2 types are not authored. They come from the base node types package, which
  `coa init` declares in `packages/base-node-types.yml` and `coa install`
  hydrates. `packages/` shows which packages the workspace expects; if you are
  unsure which the org uses, ask.
- If no V2 type can be had (the base package exists only in the production
  registry; lower environments return 404), author nodes as V1 `.yml`. Do not
  create a `nodeTypes/` folder to fill the gap, and do not stop.
- Do not fix a `.sql` node with empty columns by bumping its type's
  `fileVersion`. Point `@nodeType` at a V2 package type instead. Upgrading a
  type changes the DDL/DML of every node that uses it.
- A custom type is only for something net-new that the user explicitly asks
  for. Ask first, then follow `coa describe node-types` and
  `coa describe schema nodeType`.

When reviewing an existing type's templates: current `coa` infers
`col.dataType` for V2 nodes, so explicit-column DDL works; older builds
surfaced `UNKNOWN`, and the CTAS pattern in the yaml-spec reference is the
conservative choice. Either way, prove a type with `coa create --dry-run
--verbose` before authoring nodes against it.

## Workflow

1. Confirm the change with the user.
2. `coa describe schema <type>` for the exact shape, then edit.
3. `coa validate -d <dir>`.
4. `coa doctor -d <dir> [--profile <p>]` to check the project files, auth, and
   warehouse connectivity. `--fix` is itself a shared-config change.
5. After a node type or template edit, run
   `coa create -d <dir> --include "{ nodeType: \"<Name>\" }" --dry-run --verbose`
   and the same with `coa run`. Columns must render and the SQL must be
   non-empty for the affected nodes.
