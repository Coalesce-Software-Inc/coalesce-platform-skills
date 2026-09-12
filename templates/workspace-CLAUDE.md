<!-- coalesce-node-managed: true -->
<!-- Remove the line above to prevent Coalesce Node from overwriting your edits. -->

# Coalesce Transform Repository

This is a Coalesce Transform workspace: a Git-backed representation of a data
transformation DAG. Nodes live in `nodes/` as `<LOCATION>-<NAME>.sql` (SQL
nodes) or `.yml` (YAML nodes) files — the node type decides which: a SQL node
type (`fileVersion: 2` in its definition; the app still labels it "V2")
takes `.sql`, a YAML node type (formerly "V1") takes `.yml`, and Source nodes
are always YAML. Workspace metadata (locations, environments, jobs,
subgraphs, node types, macros) is YAML. The `coa` CLI validates the repo, runs
SQL against the warehouse for local development, and plans and deploys to
Coalesce Environments — `coa describe <topic>` and `coa <command> --help` are
the source of truth for every format, schema, and command.

## Use the Coalesce Agent Skills

Detailed guidance lives in the **Coalesce Agent Skills** (user-level skills,
installed at `~/.claude/skills/coalesce-*`). Start with the
`coalesce-pipelines` skill — it covers the repo layout, the core
validate/dry-run/create/run loop, the format rules, and routes to the
specialist skills (SQL edits, structure changes, workspace config, git
publication, deploy, review).

If the `coalesce-pipelines` skill is not available in this environment,
install the Coalesce Agent Skills package (see the `coalesce-agent-skills`
distribution: run its `install.sh`, or let the Coalesce Node desktop app sync
it automatically).

## Two rules that always apply

1. `coa create` / `coa run` execute SQL directly against the warehouse —
   local development, NOT deploy. Deploying is its own approved step: commit
   and push, then `coa plan` / `coa deploy` against an Environment (or the
   Coalesce web UI). Never deploy, refresh, or push without approval.
2. Ask before editing shared config (`data.yml`, `locations.yml`,
   `workspace.yml`, `environments/`, `jobs/`, `macros/`, `packages/`,
   `nodeTypes/`) — an edit there can silently break unrelated nodes.

If `.claude/workspace-context.json` exists, read it first — it holds the
current node inventory, edges, jobs, environments, and diagnostics.

In a cold workspace with no `nodes/` yet, start from the warehouse instead:
`coa sources list` shows the tables per location and `coa sources add`
scaffolds the Source nodes to build on.
