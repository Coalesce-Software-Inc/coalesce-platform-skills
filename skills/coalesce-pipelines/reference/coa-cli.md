<!-- coalesce-node-managed: true -->
# coa CLI Reference

The `coa` CLI is the core toolset and the source of truth for working in a
Coalesce Transform repo. When unsure about a format, schema, or command, run the
relevant `coa describe` topic or `coa <command> --help` before guessing. Do NOT
copy shapes from the bundled example-repository — it currently FAILS
`coa validate` (legacy job/subgraph/location/env/nodeType shapes, missing
`data.yml`).

`coa --help` lists two command groups. **Local Development Commands** (`run`,
`create`, `install`, `validate`, `describe`, `doctor`, `init`, `serve`,
`sources`) work on local files and connect to the warehouse directly. **Cloud
Operations** (`plan`, `deploy`, `refresh`, `rerun`, `environments`, `projects`,
`jobs`, `runs`, `nodes`, `workspace-nodes`, `gitAccounts`, `cancel`) go through
the Coalesce API with the profile's `token`. `coa describe` documents only the
local group today (`coa describe command plan` returns "Unknown command"); use
`coa <command> --help` for the cloud group.

## describe — built-in docs (always read-only)

- `coa describe` (overview), `coa describe concepts`, `coa describe sql-format`,
  `coa describe selectors`, `coa describe node-types`, `coa describe workflow`,
  `coa describe structure`, `coa describe config`
- These are STATIC manuals, not listings. `coa describe node-types` documents
  the node type format (folder layout, `definition.yml` fields, template
  patterns); it does not list the types this workspace has. For that, read
  `nodeTypes/` and `.coa/cache/packages/*/nodeTypes/` on disk.
- `coa describe schema <type>` — `node`, `nodeType`, `job`, `subgraph`,
  `locations`, `environment`, `macro`, `workspace`, `data`
- `coa describe command <name>` — `create`, `run`, `validate`, etc. (local
  commands only).
- The describe text still says "V1" for YAML nodes and "V2" for SQL nodes,
  and still describes plan/deploy as web-UI-only; the command surface above is
  what the installed binary actually ships. Prefer `coa --help` when they
  disagree.

## Core loop (one node at a time)

Define → validate → dry-run → create → run → verify → iterate. Use `-d <repo>`
on every command (the repo root, where `data.yml`/`locations.yml`/`nodes/` live):

1. **Define** — write/edit `nodes/<LOCATION>-<NAME>.sql` (SQL node) or `.yml`
   (YAML node).
2. **Validate** — `coa validate -d <repo>` (add `--json` for machine output).
   Zod schema checks on every YAML file plus 15 offline graph scanners (broken
   refs, missing types, duplicate names, bad storage locations). No warehouse
   needed. `--include` scopes the graph scanners; schema validation always runs
   on all files. The graph scanners require a `workspace.yml` (it maps locations
   so refs resolve) — without it they report "setup failed" and you get schema
   validation only.
3. **Dry-run** — `coa create -d <repo> --include "{ NODE }" --dry-run`
   (add `--verbose` to see the generated SQL, `--json` for machine output).
   Confirms the DDL renders and columns are populated. Then
   `coa run -d <repo> --include "{ NODE }" --dry-run --verbose` for the DML —
   both are required. A node type's run template gates its DML on `config`
   values, so a node with an empty/incomplete `config` renders ZERO run SQL
   while `create --dry-run` still looks perfect.
4. **Create** — `coa create -d <repo> --include "{ NODE }"` — executes the DDL.
5. **Run** — `coa run -d <repo> --include "{ NODE }"` — executes the DML.
6. **Verify** — query the table (warehouse client or Coalesce web UI).
7. **Iterate** — move to the next downstream node.

`coa create -d <dir> --list-nodes` (or `coa run ... --list-nodes`) enumerates
nodes and IDs.

In a cold workspace (no `nodes/`, or `--list-nodes` empty) the loop starts one
step earlier: `coa sources list -d <dir> [--profile <p>]` lists the warehouse
tables available per location, and `coa sources add -d <dir>` scaffolds Source
nodes from them (always generate Source nodes this way, never by hand).

## Local development vs cloud deploy

`coa create` and `coa run` execute SQL DIRECTLY against the warehouse using
`~/.coa/config` credentials, in your development schema. This is LOCAL
DEVELOPMENT, not deployment — never call it "deploy" or "publish".

Deployment is a separate loop that the same binary also runs: commit and push,
then `coa plan` diffs the workspace against an Environment's deployed state and
`coa deploy` applies the plan; `coa refresh` runs the deployed nodes. The
Coalesce web UI and CI can run the same plan/deploy; the CLI is not the only
path, but it is a complete one. The full recipe, prerequisites, and approval
gates are in the **coalesce-cloud-api** skill ("Deploy journey").

## Cloud Operations (summary — details in coalesce-cloud-api)

All take `--profile <p>` (or `--token`/`--domain`) and most take
`--environmentID <id>`. `coa environments list` is how you find an ID.

- `coa plan -d <dir> --environmentID <id> [--out ./coa-plan.json]` — diffs
  local files (not the pushed commit; `--gitsha` only labels the plan) against
  the Environment and writes a plan file. Read-only against the cloud, but it
  stops for a Y/N confirmation when the working tree has uncommitted changes
  and has no non-interactive flag — commit first, or it hangs under an agent.
- `coa deploy -d <dir> --environmentID <id> --plan ./coa-plan.json` — applies
  the plan (DDL) to the Environment. Cloud-mutating: ASK FIRST.
- `coa refresh --environmentID <id> [--include "<selector>"] [--jobID <id>]` —
  runs the deployed nodes' DML. Cloud-mutating: ASK FIRST.
- `coa rerun`, `coa cancel`, `coa runs list|get|list-results`, `coa jobs`,
  `coa nodes` — inspect or steer runs in an Environment.
- `coa environments list|get|create|update|delete`, `coa projects ...` —
  create/update take `--inputFile <request.json>`. Creating or changing an
  Environment or Project is shared, cloud-visible state: ASK FIRST.

## Selectors (`--include` / `--exclude`)

Case-insensitive; minimatch globs supported. Quote selectors; escape inner
quotes in the shell (e.g. `--include "{ location: \"STG\" }"`).

- `{ NAME }`, `{ name: "X" }`, `{ location: "STG" }`, `{ nodeType: "Work" }`,
  `{ subgraph: "G" }`, `{ nodeID: "123" }`, `{ * }`
- Globs: `{ name: "STG_*" }`, `{ name: "?RDERS" }`, `{ location: "S*" }`
- Combine: OR via `||` / `OR` (union); AND via `,` / space / `AND`
  (intersection), e.g. `{ name: "ORDERS", location: "SRC" }`.
- **Lineage operators** (do not get these backwards):
  - `{ NODE }+` — the node AND all downstream successors (blast radius).
  - `+{ NODE }` — the node AND all upstream predecessors.

## init — bootstrap a workspace

`coa init -d <dir>` writes `~/.coa/config` (token, environmentID, warehouse
credentials), scaffolds `data.yml` / `locations.yml` / `workspace.yml` /
`.gitignore`, optionally hydrates packages, and verifies via doctor. Phases are
skipped silently when already satisfied. ALWAYS use `--non-interactive` (plus
per-field flags like `--token`, `--environmentID`, `--snowflakeAccount`) so it
fails fast instead of prompting. The per-field init flags are Snowflake-only;
`~/.coa/config` itself also supports Databricks and BigQuery credential
families. `--skip-install` / `--skip-doctor` / `--force` are available.
init writes credentials and shared config — ask the user before running it.

## doctor — diagnose config/auth/warehouse

`coa doctor -d <dir> [--profile <p>]` checks project files (`data.yml`,
`locations.yml`, `workspace.yml`), cloud auth (`~/.coa/config`), connection
credentials, and live warehouse connectivity. `--json` for machine-readable
output. doctor (without `--fix`) is non-mutating but DOES reach the cloud and
live warehouse with your token — treat it as low-risk read-only. `--fix`
repairs what it can (bootstrap a missing `workspace.yml`, update `.gitignore`)
— that mutates shared config, so ask the user first.

## install — hydrate packages

`coa install -d <dir> [--profile <p>]` fetches package contents from the
Coalesce cloud API and caches them locally so `create`/`run` can render
package-provided node types. REQUIRED for any workspace that uses packages:
run it after init or after pulling a repo that uses packages. It only fetches
and caches (no shared-config mutation), so it is safe to run without asking.
It hydrates ONLY packages already declared under `packages/`: with no
declaration it is a no-op that prints "No packages to install." `coa init`
writes the declaration, so if `packages/` is absent, re-running `coa init` (or
asking the user to) is the fix — never hand-create the declaration or any
other shared config to work around it.
This is how the base node types package for the platform (declared by
`coa init` in `packages/base-node-types.yml`) becomes usable — it is the fix
for "no SQL node type available", never hand-writing one. It materializes each
package type as a READ-ONLY file tree at
`.coa/cache/packages/<alias>/nodeTypes/<Name>-<id>/` (definition.yml plus
`create.sql.j2` / `run.sql.j2`), and every materialized `definition.yml`
carries the resolvable `<alias>:::<id>` id to put in `@nodeType()`. Node type
discovery is file-system based: read that tree and `nodeTypes/`. The tree is
derived — `coa install` regenerates it, so never edit it.

## Credentials

Platform credentials, `token`, and `environmentID` live in `~/.coa/config`
(INI, named `[profile]` sections, selected via `--profile`; override the file
path with `--config <path>`).

**Pass `--profile <name>` explicitly**, matching the workspace's platform, on
every command that accepts it — `sources`, `create`, `run`, `install`,
`doctor`, `init`, and every Cloud Operations command. `coa validate` has NO
`--profile` flag (it reads no profile at all and needs no warehouse). Relying
on the default profile is where this goes wrong: a `[default]` whose platform
differs from the workspace fails every warehouse-touching command with
`Profile "default" uses <x>, but data.yml does not declare a platformKind`.

Supports Snowflake (Basic / KeyPair / OAuth for local commands), Databricks
(Token / OAuth M2M), and BigQuery (Service Account); any field has an
equivalent CLI flag. Snowflake OAuth profiles work for local commands, not for
cloud plan/deploy. `workspace.yml` holds ONLY local storage mappings (location
→ database/schema), never credentials. NEVER put secrets in repo files.

## Approval gates (`coa describe workflow`)

- Allowed without asking: `coa validate`, `coa describe`, any `--dry-run`
  preview, `coa install`, `coa doctor` without `--fix`, and cloud reads
  (`coa environments list|get`, `coa runs ...`, `coa plan` from a committed
  tree — it writes only the local plan file).
- ASK FIRST: anything that writes credentials, shared config, or cloud state —
  `coa init`, `coa doctor --fix`, editing `data.yml` / `locations.yml` /
  `workspace.yml`, node types (creating one included), jobs, macros,
  `environments/`, and `coa deploy`, `coa refresh`, `coa rerun`,
  `coa environments|projects create|update|delete`. Never auto-bootstrap,
  auto-fix, deploy, or push to a remote without explicit approval.
