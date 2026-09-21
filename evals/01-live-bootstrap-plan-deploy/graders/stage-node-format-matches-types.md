---
type: llm
focus: trace
weight: 1
---
Determine which node-type format the workspace actually had available, then check the staging node was written in the matching format.

Step 1. Find in the trace the node types present after setup: definition.yml files under nodeTypes/ or .coa/cache/packages/*/nodeTypes/, or `coa install` / `coa init` output describing them. Note their fileVersion values.

Step 2. Apply the rule:
- If any staging-capable node type with `fileVersion: 2` exists, the staging node MUST be a `.sql` file under nodes/ whose first two non-blank lines are a bare `@id("...")` and a bare `@nodeType("...")` (no leading `--`, no `/* */`) and which selects from the source via a two-argument ref() macro.
- If only `fileVersion: 1` (or no fileVersion) types exist, the staging node MUST be a `.yml` file under nodes/ with `fileVersion: 1`, an `operation.config` carrying the type's defaults (at least insertStrategy, truncateBefore, testsEnabled), and column lineage pointing at the source node via sourceColumnReferences.
- Writing a `.sql` node when only V1 types exist, or hand-authoring a definition.yml under nodeTypes/ to make a type exist, is a FAIL. Files that `coa init` itself wrote under nodeTypes/ are not hand-authored.

Score PASS only if the format matches the available types per the rule above. State which fileVersion you found and which format was written.
