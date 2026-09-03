<!-- coalesce-node-managed: true -->
# coa CLI Reference

The `coa` CLI is the core toolset and the source of truth for working in a
Coalesce Transform repo. When unsure about a format, schema, or command, run the
relevant `coa describe` topic before guessing. Do NOT copy shapes from the
bundled example-repository — it currently FAILS `coa validate` (legacy
job/subgraph/location/env/nodeType shapes, missing `data.yml`).

## describe — built-in docs (always read-only)

- `coa describe` (overview), `coa describe concepts`, `coa describe sql-format`,
  `coa describe selectors`, `coa describe node-types`, `coa describe workflow`,
  `coa describe structure`
- These are STATIC manuals, not listings. `coa describe node-types` documents
  the node type format (folder layout, `definition.yml` fields, template
  patterns); it does not list the types this workspace has. For that, read
  `nodeTypes/` and `.coa/cache/packages/*/nodeTypes/` on disk.
- `coa describe schema <type>` — `node`, `nodeType`, `job`, `subgraph`,
  `locations`, `environment`, `macro`, `workspace`, `data`
- `coa describe command <name>` — `create`, `run`, `validate`, etc.

## Core loop (one node at a time)

Define → validate → dry-run → create → run → verify → iterate. Use `-d <repo>`
on every command (the repo root, where `data.yml`/`locations.yml`/`nodes/` live):

1. **Define** — write/edit `nodes/<LOCATION>-<NAME>.sql` (V2) or `.yml` (V1).
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
`~/.coa/config` credentials. This is LOCAL DEVELOPMENT, not deployment — never
call it "deploy" or "publish". There is no `coa deploy`. Genuine cloud
plan/deploy is a separate process: git push, then plan/deploy in the Coalesce
web UI or CI (it diffs the pushed Git state against the deployed environment).

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
fails fast instead of prompting. `init` and `coa profile create` share one set
of per-field warehouse flags, so `--platformKind Snowflake|Databricks|BigQuery`
plus that platform's flags works on either. `--skip-install` / `--skip-doctor` /
`--force` are available.
init writes credentials and shared config — ask the user before running it.

## doctor — diagnose config/auth/warehouse

`coa doctor -d <dir> [--profile <p>]` checks project files (`data.yml`,
`locations.yml`, `workspace.yml`), cloud auth (`~/.coa/config`), connection
credentials, and live warehouse connectivity. `--json` for machine-readable
output. doctor (without `--fix`) is non-mutating but DOES reach the cloud and
live warehouse with your token — treat it as low-risk read-only. `--fix`
repairs what it can (bootstrap a missing `workspace.yml`, update `.gitignore`)
— that mutates shared config, so ask the user first.

## profile — manage `~/.coa/config` profiles

Every section of `~/.coa/config` is a profile. Manage them with the CLI; NEVER
hand-edit the ini file.

- `coa profile list [-d <dir>]` — every section with its platform and whether it
  carries cloud credentials, plus which profile a command run in `-d` would use
  and why. Each row shows that section's OWN fields.
- `coa profile show <name>` — one section's fields AND the effective profile
  (that section layered over `[default]`). Secrets redacted in both.
- `coa profile use <name> [-d <dir>]` — bind this workspace to a profile, so
  local commands in that directory use it without `--profile`. Refuses a profile
  whose platform does not match the workspace.
- `coa profile unset [-d <dir>]` — remove the binding; selection falls back to
  the config's own default.
- `coa profile create <name> --platformKind <Snowflake|Databricks|BigQuery>
  <per-field flags>` — runs a LIVE connection test and writes the new section
  only if it passes. Pass `--non-interactive` so a missing value fails instead of
  prompting. Configures the warehouse half only; cloud auth (`token`,
  `environmentID`) is `coa init`'s job.
- `coa profile delete <name> [-d <dir>]` / `coa profile rename <old> <new>
  [-d <dir>]` — both refuse `default` (every other profile inherits from it), and
  both repair the binding in `-d <dir>` if it pointed at the affected profile.

Every subcommand takes `--format json` for machine output, with secrets redacted.

`coa profile create` examples (flags come from the same set `coa init` uses):

```
coa profile create staging --platformKind Snowflake
coa profile create dbx --non-interactive --platformKind Databricks \
  --databricksHost <h> --databricksPath <p> --databricksToken <t>
coa profile create bq --non-interactive --platformKind BigQuery \
  --bigQueryServiceAccountKey ./key.json
```

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
for "no V2 node type available", never hand-writing one. It materializes each
package type as a READ-ONLY file tree at
`.coa/cache/packages/<alias>/nodeTypes/<Name>-<id>/` (definition.yml plus
`create.sql.j2` / `run.sql.j2`), and every materialized `definition.yml`
carries the resolvable `<alias>:::<id>` id to put in `@nodeType()`. Node type
discovery is file-system based: read that tree and `nodeTypes/`. The tree is
derived — `coa install` regenerates it, so never edit it.

## Credentials

Platform credentials, `token`, and `environmentID` live in `~/.coa/config`
(INI; every section is a profile, selected via `--profile`; override the file
path with `--config <path>`). Manage sections with `coa profile` — never by
editing the ini.

Profile resolution, highest precedence first:

1. `--profile <name>` on the command.
2. The workspace's binding — `profile: <name>` in its `workspace.yml`, written
   by `coa profile use <name> -d <dir>`.
3. The config's own `[default] profile=` key.
4. `default`.

`coa profile list` and `coa doctor` both report the active profile AND which of
those four selected it. A named profile inherits any field it omits from
`[default]`; `coa profile show <name>` prints that effective, inherited view.

**Pass `--profile <name>` explicitly**, matching the workspace's platform, on
every command that accepts it — `sources`, `create`, `run`, `install`,
`doctor`, `init`. `coa validate` has NO `--profile` flag (it reads no profile
at all and needs no warehouse). Relying on the default profile is where this
goes wrong: a `[default]` whose platform differs from the workspace fails
every warehouse-touching command with `Profile "default" uses <x>, but
data.yml does not declare a platformKind`.

A binding covers only commands that act on a workspace directory (`create`,
`run`, `serve`, `install`, `doctor`, `profile`). Cloud-side commands resolve
from flags alone and ignore the binding, so pass `--profile` there.

Per-workspace bindings are how several workspaces on different platforms coexist
on one machine. Binding is validated up front: `coa profile use` refuses a
profile whose platform disagrees with the workspace's `data.yml` (a workspace
that records no platform is treated as Snowflake), so the mismatch surfaces at
bind time rather than mid-run.

Supports Snowflake (Basic / KeyPair), Databricks (Token / OAuthM2M), and
BigQuery (ServiceAccount / ApplicationDefault); every field has an equivalent
CLI flag on `coa init` and `coa profile create`. Beyond the profile binding,
`workspace.yml` holds only local storage mappings (location → database/schema)
and runtime parameters — never credentials. NEVER put secrets in repo files.

## Approval gates (`coa describe workflow`)

- Allowed without asking: `coa validate`, `coa describe`, any `--dry-run`
  preview, `coa install`, and `coa doctor` without `--fix`.
- ASK FIRST: anything that writes credentials or shared config — `coa init`,
  `coa doctor --fix`, editing `data.yml` / `locations.yml` / `workspace.yml`,
  node types (creating one included), jobs, macros, environments. Never
  auto-bootstrap, auto-fix, or push to a remote without explicit approval.
