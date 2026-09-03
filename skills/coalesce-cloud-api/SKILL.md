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
deployment. Never call create/run "deploy" or "publish". There is no
`coa deploy`. Genuine cloud plan/deploy is a separate process — git push →
Coalesce web UI / CI plans (diff desired vs deployed state) and deploys. That
is outside the local CLI and always requires explicit user approval.

## The four commands

- **`coa init -d <dir>`** — writes `~/.coa/config` (token, environmentID,
  warehouse credentials), scaffolds `data.yml`/`locations.yml`/
  `workspace.yml`/`.gitignore`, optionally hydrates packages, verifies via
  doctor. Phases are skipped silently when already satisfied. ALWAYS use
  `--non-interactive` plus per-field flags (`--token`, `--environmentID`,
  `--snowflakeAccount`, …) so it fails fast instead of prompting. Writes
  credentials and shared config — ASK FIRST.
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
- **`coa profile <list|show|use|unset|create|delete|rename>`** — the ONLY
  supported way to manage `~/.coa/config` sections. See Profiles below.

## Profiles

Every section of `~/.coa/config` is a profile. NEVER hand-edit the ini file —
use `coa profile`:

- `coa profile list [-d <dir>]` — sections, their platform, whether each carries
  cloud credentials, and which profile that directory resolves to and why.
- `coa profile show <name>` — the section's own fields plus the effective
  profile (the section layered over `[default]`), secrets redacted.
- `coa profile use <name> [-d <dir>]` / `coa profile unset [-d <dir>]` — bind or
  unbind this workspace's profile.
- `coa profile create <name> --platformKind <Snowflake|Databricks|BigQuery>
  <per-field flags> --non-interactive` — live connection test FIRST; nothing is
  written if it fails. Warehouse credentials only; `token` / `environmentID`
  remain `coa init`'s job. Writes credentials — ASK FIRST.
- `coa profile delete <name>` / `coa profile rename <old> <new>` — both refuse
  `default` (every other profile inherits from it) and repair a binding in
  `-d <dir>` that pointed at the affected profile. Deleting/renaming is
  destructive — ASK FIRST.

All of them accept `--format json`, with secrets redacted.

Resolution, highest precedence first: `--profile` > the workspace's binding
(`profile:` in its gitignored `workspace.yml`) > the config's `[default]
profile=` key > `default`. `coa profile list` and `coa doctor` report the active
profile and which of the four picked it.

Bindings are per workspace directory, which is what lets workspaces on different
platforms coexist on one machine. `coa profile use` refuses a profile whose
platform disagrees with the workspace's `data.yml`, so the mismatch surfaces at
bind time instead of mid-run. Bindings apply to commands that act on a workspace
directory; cloud-side commands resolve from flags alone, so pass `--profile`
there.

## Credentials

Platform credentials, `token`, and `environmentID` live in `~/.coa/config`
(INI; every section is a profile, `--profile` to select, `--config <path>` to
override).

**Always pass `--profile <name>` explicitly**, matching the workspace's
platform, on every command that accepts it — `coa sources`, `create`, `run`,
`install`, `doctor`, `init`. `coa validate` has NO `--profile` flag; it reads
no profile and needs no warehouse. Leaning on the default profile is the
common failure: a `[default]` whose platform differs from the workspace fails
every warehouse-touching command with `Profile "default" uses <x>, but
data.yml does not declare a platformKind`.

Snowflake (Basic/KeyPair), Databricks (Token/OAuthM2M), and BigQuery
(ServiceAccount/ApplicationDefault) are all fully supported; every field has a
CLI flag on both `coa init` and `coa profile create`. Beyond its profile
binding, `workspace.yml` holds only local storage mappings and runtime
parameters, never credentials. NEVER put secrets in repo files.

## Approval gates

- Without asking: `coa validate`, `coa describe`, `--dry-run` previews,
  `coa install`, and `coa doctor` without `--fix` (low-risk read-only, but a
  live cloud/warehouse call — not purely offline).
- Without asking, additionally: `coa profile list`, `coa profile show`
  (read-only, secrets redacted).
- ASK FIRST: anything that writes credentials or shared config — `coa init`,
  `coa profile create/delete/rename/use/unset`, `coa doctor --fix`, editing `data.yml`/`locations.yml`/`workspace.yml`, or
  any operation that mutates state the cloud sees. Never auto-bootstrap,
  auto-fix, or push to a remote without explicit approval.
