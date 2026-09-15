---
name: coalesce-cloud-api
description: Use for the cloud-facing surface of the coa CLI — bootstrapping a workspace (coa init), diagnosing config/auth/warehouse connectivity (coa doctor), hydrating packages (coa install), credential/profile questions (~/.coa/config), and the deploy journey from a validated local workspace to a deployed Environment (coa environments, plan, deploy, refresh).
---
<!-- coalesce-node-managed: true -->

# Cloud API, Workspace Bootstrap, and Deploy

Scope: the cloud-facing surface of the `coa` CLI — bootstrapping a workspace,
diagnosing config/auth/warehouse, hydrating packages, and taking a validated
local pipeline through plan and deploy into a Coalesce Environment. Treat
`coa <command> --help`, `coa describe <topic>` and `coa describe schema <type>`
as the source of truth; the bundled example-repository fails `coa validate`,
so never copy its config shapes.

Full command details (init/doctor/install flags, credential families,
selectors, the core loop, the Cloud Operations summary):
[coa-cli reference](../coalesce-pipelines/reference/coa-cli.md).

## Local development vs cloud deploy

`coa create` and `coa run` execute DDL/DML DIRECTLY against the warehouse
using credentials from `~/.coa/config`, in the developer's own schema. This is
LOCAL DEVELOPMENT, not deployment. Never call create/run "deploy" or
"publish".

Deployment is a second loop the same `coa` binary runs: `coa plan` diffs the
workspace against an Environment's deployed state, `coa deploy` applies the
plan, `coa refresh` runs the deployed nodes. `coa --help` lists these under
**Cloud Operations**. (`coa describe workflow` still describes plan/deploy as
web-UI-only; the binary is the authority.) The Coalesce web UI and CI can
run the same plan/deploy, so use whichever the user prefers — but never tell
a user the CLI cannot do it.

## The three bootstrap commands

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

## Deploy journey — validated locally, now ship it

Run this when the user asks to deploy, promote, publish to an Environment, or
"get this into Coalesce". Walk the steps in order and say which one you are
on; every step past 1 is visible to the whole team.

1. **Prove the local state.** `coa validate -d <dir>` is clean (0 errors, 0
   warnings) and the create/run dry-runs render for the nodes in scope.
   Commit the work on a branch (see coalesce-git-publication). `coa plan` and
   `coa deploy` stop for a Y/N confirmation when the working tree has
   uncommitted changes and have no non-interactive flag, so under an agent
   they hang silently — always run them from a clean, committed tree. Push
   before deploying so the deployed state is reproducible from Git.
2. **Pick or create the Environment.** `coa environments list --profile <p>`
   shows the Environments and their IDs. If there is none, the user needs a
   Project and an Environment — created in the Coalesce App (**Build
   Settings > Environments**), or with `coa projects create` / `coa
   environments create --inputFile <request.json>` (`project`, `name`,
   `oauthEnabled`, and `connectionAccount` for Snowflake are required; see
   `coa environments create --help`). Creating one is cloud state: ASK FIRST.
   Plan fails with one error per node such as `Storage Location TARGET ...
   Schema: N/A, Database: N/A` when the project has no Environment or the
   Environment has no mappings — that error means "do steps 2 and 3", not
   that the nodes are broken.
3. **Give the Environment its storage mappings.** Deploy-time mappings come
   from `environments/<NAME>.yml` in the workspace (`name`, `id`, `type:
   Environment`, `fileVersion`, and `mappingDefinitions` with a
   `{database, schema}` pair for EVERY location in `locations.yml`). `coa
   plan` reads this file; the Environment created via API or UI does not
   carry the mappings by itself, and editing the file never creates or
   renames an Environment — the `id` must be one from `coa environments
   list`. Shape: `coa describe schema environment`. Shared config: confirm
   the values with the user, commit the file, push.
4. **Credentials.** The CLI's plan/deploy/refresh use the warehouse
   credentials of the profile you pass with `--profile` (Snowflake Basic or
   KeyPair; Snowflake OAuth profiles do not work for cloud commands). Runs
   started from the Coalesce App or a schedule use the Environment's own
   credentials, set in the App under **Build Settings > Environments > User
   Credentials** — a browser step the user must do. Say which applies.
5. **Plan.** `coa plan -d <dir> --environmentID <id> --profile <p>` writes
   `./coa-plan.json` (add it to `.gitignore`). Read the plan back to the
   user: nodes created, altered, dropped. Plan validates mappings but NOT
   that the target database/schema exist — check that before deploying, or
   deploy fails per node with `Schema '<DB>.<SCHEMA>' does not exist`.
6. **Deploy.** Only with explicit approval: `coa deploy -d <dir>
   --environmentID <id> --plan ./coa-plan.json --profile <p>`. Report the
   result; `--out results.json` captures it.
7. **Refresh.** Only with approval: `coa refresh --environmentID <id>
   --profile <p> [--include "<selector>"]` runs the deployed nodes' DML.
   Inspect with `coa runs list --environmentID <id>` and `coa runs
   list-results --runID <n>`; a test stage can show status Success with an
   attached error string, so read the results, not just the status.

After an `environments update --inputFile`, re-read the Environment with
`coa environments get` and confirm nothing you did not mention was cleared.

## Credentials

Platform credentials, `token`, and `environmentID` live in `~/.coa/config`
(INI, `[profile]` sections, `--profile` to select, `--config <path>` to
override).

**Always pass `--profile <name>` explicitly**, matching the workspace's
platform, on every command that accepts it — `coa sources`, `create`, `run`,
`install`, `doctor`, `init`, and every Cloud Operations command. `coa
validate` has NO `--profile` flag; it reads no profile and needs no
warehouse. Leaning on the default profile is the common failure: a
`[default]` whose platform differs from the workspace fails every
warehouse-touching command with `Profile "default" uses <x>, but data.yml
does not declare a platformKind`.

Snowflake (Basic/KeyPair/OAuth), Databricks (Token/OAuth M2M), and BigQuery
(Service Account) are supported; every field has a CLI flag. `workspace.yml`
holds ONLY local storage mappings, never credentials. NEVER put secrets in
repo files.

## Approval gates

- Without asking: `coa validate`, `coa describe`, `--dry-run` previews,
  `coa install`, `coa doctor` without `--fix`, and cloud reads (`coa
  environments list|get`, `coa projects list`, `coa runs ...`, `coa jobs
  ...`, and `coa plan` from a committed tree — it only writes the local plan
  file). These are low-risk but live cloud/warehouse calls, not purely
  offline.
- ASK FIRST: anything that writes credentials, shared config, or cloud state
  — `coa init`, `coa doctor --fix`, editing `data.yml`/`locations.yml`/
  `workspace.yml`/`environments/`, `coa deploy`, `coa refresh`, `coa rerun`,
  `coa cancel`, and `coa environments|projects create|update|delete`. Never
  auto-bootstrap, auto-fix, deploy, or push to a remote without explicit
  approval.
