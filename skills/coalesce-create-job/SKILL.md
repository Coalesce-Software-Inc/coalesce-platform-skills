---
name: coalesce-create-job
description: Create a Coalesce job that selects nodes to create/run, using the correct coa job schema (includeSelector/excludeSelector strings, integer-string id — not a steps array).
---
<!-- coalesce-node-managed: true -->

> **Prerequisite — load `coalesce-pipelines` first.** If you have not already
> loaded the `coalesce-pipelines` skill in this session, load it now, read its
> "Orient first" step, core `coa` loop, and Rules, then return here. This skill
> assumes those invariants (bare `@id`/`@nodeType` first lines, `fileVersion: 2`
> node types, one-node-at-a-time validate → dry-run → create loop) are already
> in context.

A **job** is a named orchestration definition that selects which nodes to operate on
via selector strings. It is **not** a list of steps. Treat `coa describe schema job`
as the source of truth — the schema below is current as of writing.

> GUARDRAIL: Jobs live in shared workspace config (`jobs/`), like locations,
> workspaces, environments, macros, and `data.yml`. Creating or editing a job is
> **ASK FIRST**, not free-to-edit. If the user did not explicitly ask for a job,
> confirm before writing one. (`coa describe workflow` → "Ask before doing".)

## Job schema (`coa describe schema job`)

A job file is `jobs/<JOB_NAME>.yml` with exactly these fields:

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `id` | yes | string | **Integer** string matching `^-?\d+$`, e.g. `"1"`. NOT a UUID. Must be unique among jobs. |
| `type` | yes | string | Constant `Job`. |
| `fileVersion` | yes | number | Constant `1`. |
| `name` | no | string | Human-readable job name. |
| `includeSelector` | no | string | A selector string (see below) — the nodes the job targets. |
| `excludeSelector` | no | string | Optional selector string subtracted from the include set. |

There is **no `steps` array** on a job (that belongs to subgraphs). The selection is
expressed entirely through `includeSelector` / `excludeSelector`.

### Correct YAML example

```yaml
id: "1"
type: Job
fileVersion: 1
name: BUILD_TARGET
includeSelector: '{ location: "TARGET" }+'
excludeSelector: '{ name: "TEST_*" }'
```

## Selectors (`coa describe selectors`)

Selector matching is case-insensitive and uses brace blocks. Common forms:

- `{ NAME }` or `{ name: "ORDERS" }` — match a node by name (glob ok: `{ name: "STG_*" }`)
- `{ location: "STG" }` — all nodes in a location
- `{ nodeType: "Stage" }` — all nodes of a type (Source, Stage, Dimension, Fact, View, ...)
- `{ subgraph: "My Group" }` — all nodes in a subgraph
- `{ nodeID: "123" }` — by internal node id
- `{ * }` — all nodes

**Lineage operators** (do not get these backwards):

- `{ NODE }+` — the node **and all downstream successors** (suffix `+`)
- `+{ NODE }` — the node **and all upstream predecessors** (prefix `+`)

**Combining**: OR via `||` / `OR` (union — multiple different nodes);
AND via `,` / space / `AND` (intersection — one node filtered by several properties).

```text
{ name: "ORDERS" } || { name: "CUSTOMER" }     # either node (OR)
{ name: "ORDERS", location: "SRC" }            # ORDERS in SRC (AND)
{ location: "STG" }+                           # everything in STG and downstream
```

## Procedure

1. Decide the selector(s). Confirm what they resolve to with read-only coa commands:
   ```bash
   coa create -d <dir> --list-nodes                                 # list available nodes/IDs
   coa create -d <dir> --include "<selector>" --dry-run             # preview matched nodes
   coa create -d <dir> --include "<selector>" --dry-run --verbose   # also show generated SQL
   ```
2. Pick the next free integer `id` (string form, e.g. `"2"`) — do not reuse an
   existing job id and do not use a UUID.
3. Write `jobs/<JOB_NAME>.yml` with the fields above.
4. Validate the schema and scan for problems:
   ```bash
   coa validate -d <dir>
   coa validate -d <dir> --json     # machine-readable
   ```
   Fix any reported errors and re-validate.

A job only **selects** nodes; running it locally is just `coa create` / `coa run`
with the job's selector against the warehouse (local development, not a deploy).
Cloud plan/deploy is a separate process (git push → Coalesce web UI / CI).
