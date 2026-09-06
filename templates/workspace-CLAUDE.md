<!-- coalesce-node-managed: true -->
<!-- Remove the line above to prevent Coalesce Node from overwriting your edits. -->

# Coalesce Transform Repository

This is a Coalesce Transform workspace: a Git-backed representation of a data
transformation DAG. Nodes live in `nodes/` as `<LOCATION>-<NAME>.sql` (V2) or
`.yml` (V1) files — Source nodes are always V1, and every other node is V2
when a `fileVersion: 2` node type exists for its type, otherwise V1; workspace
metadata (locations, environments, jobs, subgraphs, node types, macros) is
YAML. The `coa` CLI validates the repo and runs SQL against the warehouse for
local development — `coa describe <topic>` is the source of truth for every
format and schema.

## Use the Coalesce Agent Skills

Detailed guidance lives in the **Coalesce Agent Skills** (user-level skills,
installed at `~/.claude/skills/coalesce-*`). Start with the
`coalesce-pipelines` skill — it covers the repo layout, the core
validate/dry-run/create/run loop, the format rules, and routes to the
specialist skills (SQL edits, structure changes, workspace config, git
publication, review).

If the `coalesce-pipelines` skill is not available in this environment,
install the Coalesce Agent Skills package (see the `coalesce-agent-skills`
distribution: run its `install.sh`, or let the Coalesce Node desktop app sync
it automatically).

## Two rules that always apply

1. `coa create` / `coa run` execute SQL directly against the warehouse —
   local development, NOT deploy. Work reaches the cloud only via git push,
   then plan/deploy in the Coalesce web UI or CI.
2. Ask before editing shared config (`data.yml`, `locations.yml`,
   `workspace.yml`, `environments/`, `jobs/`, `macros/`, `packages/`,
   `nodeTypes/`) — an edit there can silently break unrelated nodes.

If `.claude/workspace-context.json` exists, read it first — it holds the
current node inventory, edges, jobs, environments, and diagnostics.

In a cold workspace with no `nodes/` yet, start from the warehouse instead:
`coa sources list` shows the tables per location and `coa sources add`
scaffolds the Source nodes to build on.
