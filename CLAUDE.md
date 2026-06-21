# Coalesce Workspace

A base-state Coalesce workspace for evaluating how well coding agents build real data transformations. **zero transform nodes exist yet**.

Coalesce Transform is a metadata-driven data transformation platform built for enterprise-scale cloud data warehouses. Rather than hand-writing and orchestrating thousands of SQL scripts, data teams build pipelines as a visual DAG of typed nodes (Source, Stage, Dimension, Fact, View, and custom node types), and Transform generates the underlying DDL and DML for the target platform — currently Snowflake, Databricks, and Microsoft Fabric. The platform separates Deploy (structural DDL changes) from Refresh (DML transformations that load data), with isolated Workspaces mapped to Git branches and promotable Environments (DEV/QA/PROD) so teams can develop, review, and ship changes with the same rigor as application code.

The value comes from what's built in around the modeling layer: column-level lineage that propagates automatically, reusable templates and Marketplace packages (Data Vault, Dynamic Tables, Iceberg, Incremental Loading, Cortex ML, and more), embedded data-quality tests, native Git integration with all major providers, a REST API and coa CLI for CI/CD automation, and Coalesce AI features like Copilot for natural-language pipeline building and auto-generated documentation. For new users, the mental model is: define what the data should look like as nodes and columns, let Transform generate and run the how against your warehouse, and use Git + Environments to govern the change-management lifecycle end-to-end.

## Primary Reference: `coa describe`

`coa describe <topic>` is the authoritative reference for everything in this workspace — file formats, schemas, selector grammar, node-type internals. Consult it before guessing. Useful entry points:

| Command | Covers |
|---|---|
| `coa describe` | overview, commands, where to start |
| `coa describe sql-format` | V2 `.sql` annotation syntax (`@id`, `@nodeType`, column annotations, `{{ ref() }}`) |
| `coa describe concepts` | node types, V1 vs V2, pipeline layering |
| `coa describe sources` | viewing available tables for source node creation |
| `coa describe node-types` | authoring custom node types and templates |
| `coa describe selectors` | `--include` / `--exclude` selector grammar |
| `coa describe structure` | workspace directory layout |
| `coa describe workflow` | iterative dev loop, what is/isn't safe to edit |
| `coa describe schema <X>` | full JSON schema for any file type |
| `coa describe config` | `~/.coa/config` profile shape |

## Workspace Layout

```
data.yml          fileVersion: 3 — workspace metadata
workspace.yml     location → database/schema mappings (currently YOUR_DATABASE/YOUR_SCHEMA placeholders; replace before `coa run`)
locations.yml     storage locations (12 SRC_*, plus STAGING, TARGET, EDW, REVOPS, PARTNER_CONNECT_METRICS)
nodeTypes/        5 node type definitions (Stage, Dimension, Fact, View, PersistentStage)
```

## Authoring Transform Nodes

**Always use V2 `.sql` format for new transform nodes.** V1 `.yml` is legacy — the existing 62 source nodes are `.yml` because Source is V1-only built-in, but every new node you author should be `.sql`. See `coa describe sql-format`.

Filename — not an annotation — sets location and name:

```
nodes/<LOCATION>-<NAME>.sql
```

Every `.sql` file must start with two annotations, before any SQL:

```sql
@id("550e8400-e29b-41d4-a716-446655440000")   -- always a real UUID, not a kebab string
@nodeType("Stage")                            -- must match a node type ID in nodeTypes/
SELECT
    "ID"            AS "ID",
    "CUSTOMER_ID"   AS "CUSTOMER_ID" @isBusinessKey,   -- column annotations: AFTER alias, BEFORE comma
    "CREATED_AT"    AS "CREATED_AT" @isChangeTracking
FROM {{ ref("SRC_LOCATION", "TABLE_NAME") }}
```

Node-type IDs in this workspace — use exactly these strings in `@nodeType(...)`:

| Node type ID | Layer | Required column annotations |
|---|---|---|
| `Stage` | first-hop cleanup, truncated each run | none |
| `persistentStage` (camelCase!) | accumulate across runs | `@isBusinessKey`; `@isChangeTracking` recommended |
| `Dimension` | SCD entity | `@isBusinessKey` |
| `Fact` | event / measure | `@isBusinessKey` if incremental |
| `View` | read-only aggregation (currently `isDisabled: true` in definition) | none |

### CRITICAL: V2 `.sql` requires a V2 node type

All 5 node types in `nodeTypes/` are currently `fileVersion: 1`. **Writing `.sql` files against V1 node types fails silently** — the node loads, but `columns: []` in the template context, producing empty/broken DDL at create-time. There is no parse error.

Before authoring transforms, the relevant node type(s) must be at `fileVersion: 2` with templates switched to the CTAS pattern (see `coa describe node-types` for the V1 vs V2 template patterns). When the task requires authoring `.sql` nodes against a V1 node type, **upgrade that node type to `fileVersion: 2` as part of the work** — it's a prerequisite, not an optional aside. Make the upgrade, then call it out explicitly in your summary (which node type, V1→V2, template pattern changed) so the change is reviewable. Do NOT fall back to authoring transforms in V1 `.yml` — `.yml` is legacy and reserved for the existing source nodes.

## Pipeline Architecture

Sources → Stages → Persistent Stages → Facts / Dimensions → Views. Use the right node type per layer — **do not reuse `Stage` for downstream layers** (you lose truncation/SCD/view semantics and end up with a flat pipeline that has no structural meaning).

Convention for this workspace: intermediates land in `STAGING`, final analytics in `TARGET`.

## Build / Test / Validate Loop

Every node must complete the full local + deployed cycle before the next node is started. The deployed half is the real correctness gate — local steps are preconditions, not the bar. Errors caught here are isolated to the node you just built; errors deferred to the end of a batch compound across the DAG.

For each node:

```
1. edit                                                   # author the .sql file
2. coa validate -d .                                      # schema + offline scanners
3. coa create -d . --include "{ NODE }" --dry-run         # preview DDL
4. coa create -d . --include "{ NODE }"                   # execute DDL against warehouse
5. coa run    -d . --include "{ NODE }"                   # execute DML against warehouse
6. verify locally                                         # spot-check the table in the warehouse
7. coa plan   -d . --profile <P> --environmentID <ID>     # diff workspace vs deployed state → coa-plan.json
8. review coa-plan.json                                   # confirm the delta matches expectation
9. coa deploy --profile <P> --environmentID <ID>          # apply coa-plan.json to the environment
10. verify deployed                                        # confirm the node ships and behaves in the target env
11. next node
```

Useful selector variants (see `coa describe selectors`):

```
coa create -d . --include "{ NODE_NAME }+"              # node plus all downstream
coa create -d . --include "+{ NODE_NAME }"              # node plus all upstream
```

`coa plan` automatically generates only the delta between the local workspace and the deployed environment — you don't need to scope it to a single node. Plan output goes to `./coa-plan.json` by default; `coa deploy` reads that same file. Credentials come from `~/.coa/config` via `--profile`; the environment ID identifies which deployed target to compare/apply against.

Both `coa plan` and `coa deploy` are synchronous against the Coalesce cloud API. Like `coa create` and `coa run`, they are part of the inner loop — not a separate "deployment phase."

## Working Practices

- **Always pass `--debug` to `coa`.** Without it, many errors are suppressed and you get misleading "success" output.
- **Never pipe `coa` through `grep` / `head` / `tail`.** SIGPIPE on the consumer can kill `coa` mid-run — applies to `create`, `run`, `plan`, `deploy`, `refresh`. Redirect to a file (`coa ... > /tmp/out.log 2>&1`) and read that.
- **Never interrupt `coa create` / `run` / `plan` / `deploy` / `refresh`.** They are synchronous and stateful — cancelling can leave the workspace or the deployed environment in a broken half-applied state.
- **Always review `coa-plan.json` before deploying.** The plan is the source of truth for what will change in the target environment. Inspect the diff; if anything is unexpected (deletes you didn't intend, columns dropped, type changes), stop and resolve before `coa deploy`.
- **`coa validate` first.** Offline issues (broken refs, schema errors, duplicate names, column mismatches) are cheap to catch here; warehouse errors are not.
- **Cast `NULL` in `UNION ALL`.** Bare `NULL` columns confuse type inference and break DDL — use `NULL::VARCHAR` (or the appropriate explicit type).
- **Filter `_FIVETRAN_DELETED` in staging** when the source has it. Not every source does (e.g. `SRC_RIPPLING_SPEND` is file-based and has no `_FIVETRAN_DELETED`).
- **Avoid joining one-to-many children at the parent grain** — fans out rows. Roll children up first, then join.
- **Add a source-system discriminator** (e.g. `'RAMP' AS SOURCE_SYSTEM`) in `UNION ALL` fact tables so rows from different sources stay distinguishable.
- **Match source column names exactly.** Source YAML columns are case-sensitive; double-quote identifiers in transforms.

## Safe to Change Without Asking

- Create or edit the transform nodes the user asked for (always `nodes/*.sql` — never `.yml` for new transforms).
- Run any read-only `coa` command (`validate`, `describe`, `create --dry-run`, `run --dry-run`, `--list-nodes`).
- Upgrade a node type to `fileVersion: 2` (definition + templates) when it's a prerequisite for the `.sql` nodes you were asked to build — see the CRITICAL note above. Call the upgrade out in your summary.

**Ask first** before:
- Editing existing source nodes that weren't part of the request.
- Editing `nodeTypes/` in ways *not* required by the requested work (e.g. changing a node type unrelated to the nodes you're building) — the V2 upgrade needed to author requested `.sql` nodes is expected and doesn't need a prompt.
- Touching `workspace.yml`, `locations.yml`, `data.yml`, `macros/`, `jobs/`, `environments/`, `subgraphs/`.

## Output Quality Bar

A node is not "done" until every item below holds. Apply the bar **per node**, not at the end of a batch — a node that passes locally but fails `plan`/`deploy` blocks every downstream node until it's fixed, so catch it before moving on.

**Authoring correctness (preconditions):**
- `coa validate -d .` passes with no errors.
- `coa create --dry-run --json` returns no template-failure entries (empty SQL, comment-only, missing DDL).
- Every `{{ ref(...) }}` resolves to a node that exists.
- Column names match source YAML exactly (case-sensitive).
- Every `@id()` is a unique UUID — no collisions with the 62 existing source node IDs.
- Filenames follow `<LOCATION>-<NAME>.sql` for every new transform node.
- Correct node type per layer (no `Stage` masquerading as `Fact`).
- Intermediates in `STAGING`, finals in `TARGET`.

**Local execution:**
- `coa create` against the warehouse succeeds.
- `coa run` against the warehouse succeeds.
- Local spot-check of the resulting table confirms expected shape and row counts.

**Deployed (the actual bar):**
- `coa plan` generates without error and the resulting `coa-plan.json` diff matches the intended change (no surprise deletes, no unintended column drops, no type-coercion surprises).
- `coa deploy` applies cleanly to the target environment.
- Post-deploy verification in the target environment confirms the node ships and behaves as in local — same row counts where applicable, no schema drift, no downstream nodes broken.

If any deployed-tier check fails, fix that node before authoring the next one.
