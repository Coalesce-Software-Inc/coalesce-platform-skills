---
name: coalesce-pipeline-structure
description: Use when creating, deleting, renaming, or rewiring Coalesce nodes, subgraphs, or jobs — changing the structural topology of the transformation DAG. Not for editing SQL inside an existing node (use coalesce-sql-transformation).
---

<!-- coalesce-node-managed: true -->

> **Prerequisite:** load `coalesce-pipelines` first if it is not already loaded in this session. This skill assumes its rules, its "Node types" section, and its core loop.

# Pipeline Structure

Scope: creating, deleting, renaming, and rewiring nodes, and the job and subgraph files that select them. When unsure of a shape, run `coa describe <topic>` or `coa describe schema <type>`. References: [sql-format](../coalesce-pipelines/reference/sql-format.md), [yaml-spec](../coalesce-pipelines/reference/yaml-spec.md).

## Impact analysis

- Dependents of NODE: `coa create -d <dir> --include "{ NODE }+" --dry-run`
- Upstream of NODE: `--include "+{ NODE }"`

Lineage selectors follow graph edges only, so they miss `ref_no_link` uses, jobs, and subgraphs. Search for those too: `grep -rn "<NAME>" nodes jobs subgraphs`, and `grep -rn "<node id>" subgraphs` (steps are usually node ids).

## Create a node

1. Pick the node type (coalesce-pipelines, "Node types") and with it the format.
2. Confirm the name is free: neither `nodes/<LOCATION>-<NAME>.sql` nor `.yml` exists. If one does, stop and tell the user; do not overwrite it or create a variant.
3. **V2 `.sql`** (a `fileVersion: 2` type exists): the first two lines are a bare `@id("<fresh UUID>")` and `@nodeType("<id from definition.yml>")`, followed by a SELECT that lists its columns explicitly and reads from `{{ ref("LOC", "NAME") }}`. Full format and annotations: sql-format reference. For a 1:1 stage, use coalesce-create-stage-node.
4. **V1 `.yml`** (no V2 type for what you need, or a config-driven type such as an SCD2 Dimension): follow "Authoring a new V1 node" in the [V1 nodes reference](../coalesce-pipelines/reference/v1-nodes.md). Source nodes come from `coa sources add`, never by hand.
5. Run the core loop. `coa create --dry-run --verbose --include "{ NODE }"` must show the node with its columns; `coa validate` alone stays green for a node that was silently dropped.

## Delete a node

1. Run the impact analysis above, both the lineage selector and the name search.
2. If anything depends on the node (a downstream `ref()`, a job or subgraph selector), do not delete it. Tell the user what depends on it, by name, and ask how to proceed: rewire the dependents, delete them too, or leave the node. A request that calls the node "unused" is a belief to check, not an approval to break its dependents.
3. If nothing depends on it, delete the node file and nothing else, then run `coa validate`.

## Rename a node

Use coalesce-rename-node-cascade.

## Rewire (insert a node between two others)

1. Create the new node reading from the upstream node.
2. In the downstream node, change only the `ref()` that pointed at the upstream node so it points at the new node. Check that every column the downstream node uses is exposed by the new node.
3. Leave the upstream node untouched.
4. Validate, then dry-run `{ NEW_NODE }+` with both `coa create` and `coa run`.

## Jobs and subgraphs

Both are shared config; ask first unless the user requested the change. Job recipe: coalesce-create-job. Subgraph `steps` are node ids, not names, and the serve UI silently drops a step that is not one. Shapes and legacy forms: yaml-spec reference.
