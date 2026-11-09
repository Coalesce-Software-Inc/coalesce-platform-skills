<!-- coalesce-node-managed: true -->

# coa CLI Reference

Pass `-d <repo>` (the repo root, where `data.yml`, `locations.yml`, and `nodes/` live) on every workspace command.

## describe: built-in docs (read-only)

- Topics: `coa describe` (overview), `concepts`, `sql-format`, `selectors`, `node-types`, `workflow`, `structure`.
- `coa describe schema <type>`: `node`, `nodeType`, `job`, `subgraph`, `locations`, `environment`, `macro`, `workspace`, `data`.
- `coa describe command <name>`: `create`, `run`, `validate`, and so on.

These are static manuals, not listings. `coa describe node-types` documents the node type format; it does not list the types this workspace has. Read `nodeTypes/` and `.coa/cache/packages/*/nodeTypes/` for that.

## The loop commands

- `coa validate -d <repo>` (`--json` for machine output). Schema checks on every YAML file plus 15 offline graph scanners (broken refs, missing types, duplicate names, bad storage locations). No warehouse and no profile needed. `--include` scopes the scanners only; schema validation always covers all files. The scanners need a `workspace.yml` to map locations. Without one they report "setup failed" and you get schema validation only; `coa doctor --fix` bootstraps the file (ask first).
- `coa create -d <repo> --include "{ NODE }" --dry-run --verbose` renders the DDL. Check the column list is populated.
- `coa run -d <repo> --include "{ NODE }" --dry-run --verbose` renders the DML. Empty output means the node's `config` is missing its type's defaults.
- `coa create` / `coa run` without `--dry-run` execute against the warehouse with the resolved profile's credentials. Local development, not deploy.
- `coa create -d <repo> --list-nodes` (or `coa run ... --list-nodes`) lists nodes and ids.
- `coa sources list -d <repo>` lists warehouse tables per location; `coa sources add -d <repo>` scaffolds Source nodes from them.

The Cloud Operations commands (`coa plan`, `deploy`, `refresh`, `rerun`, `cancel`, `runs`, `environments`, …) drive the cloud plan/deploy process, are not part of the local loop, and always need explicit approval. See coalesce-deploy.

## Selectors (`--include` / `--exclude`)

Case-insensitive, with minimatch globs. Quote the selector and escape inner quotes: `--include "{ location: \"STG\" }"`.

- `{ NAME }`, `{ name: "X" }`, `{ location: "STG" }`, `{ nodeType: "Work" }`, `{ subgraph: "G" }`, `{ nodeID: "123" }`, `{ * }`
- Globs: `{ name: "STG_*" }`, `{ name: "?RDERS" }`, `{ location: "S*" }`
- OR with `||` or `OR`. AND with `,`, a space, or `AND`: `{ name: "ORDERS", location: "SRC" }`.
- `{ NODE }+` is the node and everything downstream (blast radius).
- `+{ NODE }` is the node and everything upstream.

## init: bootstrap a workspace (ask first)

`coa init -d <dir>` writes `~/.coa/config` (token, environmentID, warehouse credentials), scaffolds `data.yml`, `locations.yml`, `workspace.yml`, and `.gitignore`, declares the base node types package, optionally hydrates packages, and verifies with doctor. Phases already satisfied are skipped silently. Always pass `--non-interactive` plus per-field flags (`--token`, `--environmentID`, `--snowflakeAccount`, …) so it fails fast instead of prompting. `--skip-install`, `--skip-doctor`, and `--force` exist.

Without `--profile`, init writes into the profile the workspace already resolves to. With `--profile <name>` it writes that section and binds the workspace to it. The binding is written after the credential phases, so a failed init leaves no new binding, but it can leave a half-written profile (the token is stored before the warehouse is tested). `coa init --profile <name>` is also how you rewrite an existing profile's credentials, because `coa profile create` refuses an existing name.

## doctor: diagnose config, auth, warehouse

`coa doctor -d <dir> [--profile <p>]` checks the project files, cloud auth, connection credentials, and live warehouse connectivity (`--json` available). It changes nothing but does call the cloud and warehouse with your token. `--fix` bootstraps a missing `workspace.yml` and updates `.gitignore`; that is a shared-config change, so ask first.

The header line reports the profile in force and what selected it: `coa <version> | platform: snowflake | profile: prod (workspace.yml)`. `Issues found — see above` prints for any warning, including a missing gitignore entry, and doctor exits 0 either way. Read the individual checks.

## install: hydrate packages

`coa install -d <dir> [--profile <p>]` downloads the packages declared under `packages/` into `.coa/cache/` so `create` and `run` can render their node types. Run it after init and after pulling a repo that uses packages. It only fetches and caches, so it is safe without asking. With nothing declared it prints "No packages to install." Package types appear as a read-only tree at `.coa/cache/packages/<alias>/nodeTypes/<Name>-<id>/`; never edit it.

## profile: manage `~/.coa/config`

Every section of `~/.coa/config` is a profile. Manage them with `coa profile` and never hand-edit the ini. Every subcommand takes the global `--config <path>` and `--json`.

- `list [-d <dir>]`: each section with its platform and whether it has cloud credentials, plus which profile a command in `-d` would use and why. Rows show a section's own fields, so one that inherits from `[default]` shows `-`.
- `show <name>`: the section's fields and the effective profile (layered over `[default]`), secrets redacted.
- `use <name> [-d <dir>]`: bind the workspace by writing `profile: <name>` to its `workspace.yml`.
- `unset [-d <dir>]`: remove the binding.
- `create <name> <per-field flags>`: runs a live connection test and writes the section only if it passes. Warehouse half only. Refuses an existing name.
- `set-cloud <name> --token <t> [--domain <d>] [--environmentID <id>]`: writes the cloud half and leaves the rest alone. Domain precedence: `--domain`, the section's stored domain, `[default]`'s, then the built-in default. A token-only call never repoints an existing domain.
- `delete <name> [-d <dir>]`: refuses `default`. Appends the section to `<config>.backup` first, then clears the binding in `-d` only. Other workspaces bound to it are left dangling.
- `rename <old> <new> [-d <dir>]`: refuses `default`. Rewrites the binding in `-d` only, writes no backup, and does not rewrite a `[default] profile=<old>` key.

`create`, `set-cloud`, and `init` accept `--non-interactive`; use it so a missing value fails instead of prompting. Profile names may contain letters, digits, `-`, `_`, spaces, `@`, and parentheses. Refused: `.`, `;`, `#`, `]`, line breaks, leading or trailing spaces, and the empty name.

```
coa profile create dbx --non-interactive --platformKind Databricks \
  --databricksHost <h> --databricksPath <p> --databricksToken <t>
coa profile create bq --non-interactive --platformKind BigQuery \
  --bigQueryServiceAccountKey ./key.json
coa profile set-cloud dbx --non-interactive --token <t> --environmentID 42
coa profile use dbx -d ./my-workspace
```

### Which profile a command uses

Highest precedence first:

1. `--profile <name>` on the command.
2. The workspace binding (`profile:` in `workspace.yml`).
3. The config's `[default] profile=` key.
4. `default`.

Only commands that act on a workspace directory read the binding: `run`, `create`, `sources`, `install`, `serve`, `doctor`, `init`, `auth warehouse login`, and `coa profile`. Cloud Operations commands do not, so pass `--profile` on those. `coa validate` reads no profile.

Check before reaching for `--profile`: run `coa profile list -d <dir>`. If the workspace is bound, omit the flag, because it overrides the profile the user chose. If nothing is bound, pass `--profile <name>` for the workspace's platform.

### Platform check

`coa profile use` and `coa init` refuse a profile whose platform disagrees with the workspace:

- No `data.yml`: any platform.
- `data.yml` with no recognized `platformKind`: counts as Snowflake.
- `data.yml` naming a platform: that platform only.

A profile's platform is its `platformKind`, else the one implied by its `snowflakeAuthType` / `databricksAuthType` / `bigQueryAuthType` field, read from the effective profile. The error reads `Profile "dbx" is for databricks, but this is a snowflake workspace.` It appears at bind time from `use`/`init` and at load time from `run`/`create`. Binding a profile with no warehouse credentials succeeds with a warning; local execution fails until they exist.

### Credentials

Supported: Snowflake (`Basic`, `KeyPair`, `OAuth`), Databricks (`Token`, `OAuthM2M`), BigQuery (`ServiceAccount`, `ApplicationDefault`). `coa init` and `coa profile create` share one set of per-field flags: `--platformKind <Snowflake|Databricks|BigQuery>` plus that platform's flags. Snowflake OAuth stores only the auth type (and optional client id, secret, redirect URI) in the profile; the tokens come from `coa auth warehouse login -d <dir>`, a browser flow.

`workspace.yml` holds the profile binding, local location mappings, and runtime parameters, never credentials. Never put secrets in repo files.

### Failure modes

- A value of literally `true`, `false`, or `null` cannot be stored: the ini parser reads it back as a boolean or null. A write is refused whole (`Refusing to change <path>: the edit would not read back as intended`), and a hand-edited one aborts commands with `Expected profile <p> field <f> to be a string`.
- A binding or `[default] profile=` naming a deleted profile fails every credential-reading command (`Unable to find profile <name>`, or `profile "<name>" not found. Available: …` from doctor). Fix with `coa profile list`, then `coa profile use <name> -d <dir>` or `unset`.
- `coa plan` prompts when the repo has uncommitted changes and has no `--non-interactive`; piped, it hangs silently. Commit first or pass `--gitsha <sha>`.

## Approval gates (`coa describe workflow`)

- Without asking: `coa validate`, `coa describe`, any `--dry-run`, `coa install`, `coa doctor` without `--fix`, `coa profile list` / `show`.
- Ask first: anything that writes credentials or shared config. That covers `coa init`, `coa doctor --fix`, `coa profile create` / `set-cloud` / `delete` / `rename` / `use` / `unset`, edits to `data.yml`, `locations.yml`, `workspace.yml`, node types, jobs, macros, environments, every Cloud Operations command, and any push to a remote.
