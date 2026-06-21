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

## The three commands

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
  without asking.

## Credentials

Platform credentials, `token`, and `environmentID` live in `~/.coa/config`
(INI, `[profile]` sections, `--profile` to select, `--config <path>` to
override). Snowflake (Basic/KeyPair), Databricks (Token/OAuth M2M), and
BigQuery (Service Account) are supported; every field has a CLI flag.
`workspace.yml` holds ONLY local storage mappings, never credentials. NEVER
put secrets in repo files.

## Approval gates

- Without asking: `coa validate`, `coa describe`, `--dry-run` previews,
  `coa install`, and `coa doctor` without `--fix` (low-risk read-only, but a
  live cloud/warehouse call — not purely offline).
- ASK FIRST: anything that writes credentials or shared config — `coa init`,
  `coa doctor --fix`, editing `data.yml`/`locations.yml`/`workspace.yml`, or
  any operation that mutates state the cloud sees. Never auto-bootstrap,
  auto-fix, or push to a remote without explicit approval.
