---
name: coalesce-cloud-api
description: Use for the cloud-adjacent surface of the coa CLI — bootstrapping a workspace (coa init), diagnosing config/auth/warehouse connectivity (coa doctor), hydrating packages (coa install), and credential/profile questions (~/.coa/config).
---
<!-- coalesce-node-managed: true -->

# Cloud API & Workspace Bootstrap

Scope: the cloud-adjacent surface of the `coa` CLI — bootstrapping a
workspace, diagnosing config/auth/warehouse, and hydrating packages. These are
real local commands, NOT a REST push/deploy client. Treat `coa describe
<topic>` and `coa describe schema <type>` as the source of truth; the bundled
example-repository fails `coa validate`, so never copy its config shapes.

Full command details (init/doctor/install flags, credential families,
selectors, the core loop):
[coa-cli reference](../coalesce-pipelines/reference/coa-cli.md).

## Local development vs cloud deploy

`coa create` and `coa run` execute DDL/DML DIRECTLY against the warehouse
using credentials from `~/.coa/config`. This is LOCAL DEVELOPMENT, not
deployment. Never call create/run "deploy" or "publish". Genuine plan/deploy
runs against a deployed environment — git push → Coalesce web UI / CI plans
(diff desired vs deployed state) and deploys. The CLI's Cloud Operations
commands (`coa plan`, `coa deploy`, `coa refresh`, …) drive that same process
and are outside this loop; every one of them requires explicit user approval.

## The four commands

- **`coa init -d <dir>`** — writes `~/.coa/config` (token, environmentID,
  warehouse credentials), scaffolds `data.yml`/`locations.yml`/
  `workspace.yml`/`.gitignore`, optionally hydrates packages, verifies via
  doctor. Phases are skipped silently when already satisfied. ALWAYS use
  `--non-interactive` plus per-field flags (`--token`, `--environmentID`,
  `--snowflakeAccount`, …) so it fails fast instead of prompting. With
  `--profile <name>` it writes into that profile and binds the workspace to it
  once the credentials verify. Writes credentials and shared config — ASK FIRST.
- **`coa doctor -d <dir> [--profile <p>]`** — checks project files, cloud
  auth, connection credentials, and live warehouse connectivity (`--json` for
  machine output). Run it before any warehouse-touching command. Non-mutating,
  but it DOES reach the cloud and warehouse with your token. `--fix` mutates
  shared config — ASK FIRST.
- **`coa install -d <dir> [--profile <p>]`** — fetches package contents from
  the Coalesce cloud API and caches them locally so `create`/`run` can render
  package-provided node types. REQUIRED for any workspace that uses packages
  (after init, or after pulling such a repo). Fetch/cache only — safe to run
  without asking. It hydrates only packages ALREADY DECLARED under
  `packages/`; with no declaration it is a no-op printing "No packages to
  install." `coa init` writes that declaration, so if `packages/` is absent
  the fix is re-running `coa init` (ask the user first) — never hand-create
  the declaration or other shared config to work around it.
- **`coa profile <list|show|use|unset|create|set-cloud|delete|rename>`** — the
  ONLY supported way to manage `~/.coa/config` sections. See Profiles below.

## Profiles

Every section of `~/.coa/config` is a profile. NEVER hand-edit the ini file —
use `coa profile`. Subcommand-by-subcommand behavior, flags, name rules and
failure modes live in the `profile` section of the
[coa-cli reference](../coalesce-pipelines/reference/coa-cli.md); what matters
here is which profile a command lands on and what needs approval.

Resolution, highest precedence first: `--profile` > the workspace's binding
(`profile:` in its gitignored `workspace.yml`) > the config's `[default]
profile=` key > `default`. `coa profile list -d <dir>` and `coa doctor` both
report the profile in force and which of the four selected it.

Only commands that act on a workspace directory read the binding — `run`,
`create`, `sources`, `install`, `serve`, `doctor`, `init`, `auth warehouse
login`, `coa profile`. Cloud Operations commands resolve from flags alone, so
pass `--profile` on those.

Bindings are per workspace directory, which is what lets workspaces on different
platforms coexist on one machine. `coa profile use` and `coa init` both refuse a
profile whose platform disagrees with the workspace's `data.yml` (a `data.yml`
recording no `platformKind` counts as Snowflake; no `data.yml` at all is
unconstrained), so the mismatch surfaces at bind time instead of mid-run.

## Credentials

Platform credentials, `token`, `domain`, and `environmentID` live in
`~/.coa/config` (INI; every section is a profile, `--profile` to select,
`--config <path>` to override).

**Check the binding before passing `--profile`.** Start with `coa profile list
-d <dir>`. If the workspace is bound, run local commands WITHOUT `--profile` —
the flag outranks the binding, so passing one out of habit silently overrides
the profile the user chose for that workspace. When nothing is bound, pass
`--profile <name>` matching the workspace's platform on every command that takes
it (`coa sources`, `create`, `run`, `install`, `doctor`, `init`); `coa validate`
has NO `--profile` flag, reads no profile, and needs no warehouse. Leaning on an
unexamined default is the common failure: a profile whose platform differs from
the workspace fails every warehouse-touching command with `Profile "<name>" is
for <x>, but this is a <y> workspace.`

Snowflake (Basic/KeyPair/OAuth), Databricks (Token/OAuthM2M), and BigQuery
(ServiceAccount/ApplicationDefault) are all fully supported; every field has a
CLI flag on both `coa init` and `coa profile create`. Snowflake OAuth is the
exception: the tokens come from `coa auth warehouse login -d <dir>`, a browser
flow, not from the config. Beyond its profile binding, `workspace.yml` holds
only local storage mappings and runtime parameters, never credentials. NEVER put
secrets in repo files.

## Approval gates

- Without asking: `coa validate`, `coa describe`, `--dry-run` previews,
  `coa install`, and `coa doctor` without `--fix` (low-risk read-only, but a
  live cloud/warehouse call — not purely offline).
- Without asking, additionally: `coa profile list`, `coa profile show`
  (read-only, secrets redacted).
- ASK FIRST: anything that writes credentials or shared config — `coa init`,
  `coa profile create/set-cloud/delete/rename/use/unset`, `coa doctor --fix`,
  editing `data.yml`/`locations.yml`/`workspace.yml`, every Cloud Operations
  command (`plan`, `deploy`, `refresh`, `rerun`, `cancel`), or any operation
  that mutates state the cloud sees. `delete` and `rename` are destructive and
  repair only the binding in `-d <dir>`; other workspaces bound to that profile
  break.
  Never auto-bootstrap, auto-fix, or push to a remote without explicit approval.
