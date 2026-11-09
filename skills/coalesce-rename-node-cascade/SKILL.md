---
name: coalesce-rename-node-cascade
description: Rename a Coalesce node and cascade the new name through every downstream ref(), job selector, and subgraph selector, with quote-agnostic matching and validation.
---

<!-- coalesce-node-managed: true -->

> **Prerequisite:** load `coalesce-pipelines` first if it is not already loaded in this session. This skill assumes its rules and core loop.

# Rename a node and cascade

Renaming a node means renaming its file and updating every reference to it. References live in three places: `ref()` macros in other nodes, job `includeSelector` / `excludeSelector` strings, and subgraph `steps`. Shapes come from `coa describe selectors`, `coa describe schema job`, and `coa describe schema subgraph`.

**Scope.** The file rename and the `ref()` updates in other node files are in scope. Jobs and subgraphs are shared config: do the in-scope edits first, then show the job/subgraph edits the rename needs and confirm before applying them. If the request already covers every reference ("update everything that references it"), that is the approval; apply them.

## Steps

1. **Locate.** Find the node's location, file, and dependents from `.claude/workspace-context.json`, or `coa create -d <dir> --list-nodes` plus a search. Read the node file.

2. **Check both names.**

   - The new name must be free: neither `nodes/<LOCATION>-<NEW_NAME>.sql` nor `.yml` may exist. Stop if one does.
   - Look for a same-named node at another location: `ls nodes/*-<OLD_NAME>.*`. Names are unique only per location, so a twin is legal. If one exists, it changes steps 4, 5, and 6.

3. **Move the file** to `nodes/<LOCATION>-<NEW_NAME>.sql` (or `.yml`). Leave `@id` and `@nodeType` unchanged. For a `.sql` node the filename is the name, so nothing inside the file changes. For a `.yml` node also update `name` and `operation.name`, and in dependents the matching `sourceMapping[].dependencies[].nodeName`.

4. **Update `ref()` calls** in every other node. Rewrite only the name argument of refs whose location argument is this node's location, and keep each file's quote style. Refs may use single or double quotes, and the macro may be `ref`, `ref_link`, or `ref_no_link`, so search with a pattern that accepts all of them, case-insensitively:

   ```
   ref(_link|_no_link)?\(\s*['"]<LOCATION>['"]\s*,\s*['"]<OLD_NAME>['"]\s*\)
   ```

   A search for one quote style misses the others. Refs to a twin at another location stay as they are.

5. **Update selectors** in `jobs/*.yml` (`includeSelector`, `excludeSelector`) and `subgraphs/*.yml` (`steps`).

   - Rewrite exact name tokens: `{ <OLD_NAME> }` and `{ name: "<OLD_NAME>" }`.
   - A `steps` entry that is a node id needs no change, because the id did not change.
   - If a twin exists, a name-only token matches both nodes. Leave it unchanged so it keeps matching the twin, and report it in step 8 for the user to decide. Rewriting it would silently drop the twin.
   - A job in the legacy `steps: [{ selector }]` shape has no `includeSelector` to edit. Do not invent one; report the stale shape.

6. **Sweep for leftovers.** `coa validate` passes even when a selector names a node that no longer exists, so search for the bare old name in both file contents and file names:

   ```
   grep -ri "<OLD_NAME>" .
   git ls-files | grep -i "<OLD_NAME>"
   ```

   Ignore hits that are a different identifier containing the old name (the new name itself, or `<OLD_NAME>_ARCHIVE`). With no twin, the rename is done only when nothing else remains. With a twin, every remaining hit must belong to the twin: its file, refs to its location, and the name-only selectors you left in step 5. Never edit the twin's references to get the count to zero.

7. **Verify.**

   ```
   coa validate -d <dir>
   coa create -d <dir> --include "{ <NEW_NAME> }+" --dry-run --verbose
   coa run    -d <dir> --include "{ <NEW_NAME> }+" --dry-run --verbose
   ```

   Validate must be clean, and both dry-runs must render non-empty SQL for the node and its dependents. If validate reports the graph scanners as "setup failed", `workspace.yml` is missing and references were not checked; ask before running `coa doctor --fix`.

8. **Report.** List the files changed, including any lineage selector (`{ NODE }+`, `+{ NODE }`) you rewrote. Also list, without changing them:
   - any name-only selector left ambiguous because of a twin, with the nodes it matches, asking which it should target;
   - glob selectors whose match set shifts with the new name (for example `{ name: "STG_P*" }`).

Change nothing beyond the rename. A leaf node with no references is a one-file move.
