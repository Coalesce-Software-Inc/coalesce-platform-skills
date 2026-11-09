---
name: coalesce-cloud-api
description: Use for the cloud-adjacent surface of the coa CLI — bootstrapping a workspace (coa init), diagnosing config/auth/warehouse connectivity (coa doctor), hydrating packages (coa install), and credential/profile questions (~/.coa/config).
---
<!-- coalesce-node-managed: true -->

# Cloud API & Workspace Bootstrap

Scope: bootstrapping a workspace, diagnosing config, auth, and warehouse
connectivity, hydrating packages, and profiles. These are local commands, not
a deploy client; plan/deploy/refresh belong to coalesce-deploy. Flags, profile
subcommands, and failure modes are in the
[coa-cli reference](../coalesce-pipelines/reference/coa-cli.md).

## The commands

- **`coa init -d <dir>`** writes `~/.coa/config` and scaffolds `data.yml`,
  `locations.yml`, `workspace.yml`, `.gitignore`, and the base package
  declaration. Always pass `--non-interactive` plus per-field flags. Writes
  credentials and shared config: ask first.
- **`coa doctor -d <dir> [--profile <p>]`** checks project files, cloud auth,
  credentials, and live warehouse connectivity. It changes nothing but calls
  the cloud and warehouse with your token. `--fix` changes shared config: ask
  first.
- **`coa install -d <dir> [--profile <p>]`** downloads the packages declared
  under `packages/` so their node types can render. Safe without asking. "No
  packages to install." means nothing is declared; the base package's
  declaration comes from `coa init`, and other packages from
  coalesce-install-package.
- **`coa profile ...`** is the only supported way to manage `~/.coa/config`.
  Never hand-edit the ini.

## Diagnosing a broken setup

When asked what is wrong with a config or connection, diagnose and report; do
not repair unless asked.

1. Read what is there: `coa profile list -d <dir>`, `coa profile show <name>`
   (secrets redacted), the workspace's `data.yml`, `locations.yml`, and
   `workspace.yml`, and `~/.coa/config` if the CLI output is not enough.
2. Run `coa doctor -d <dir>` if you may use the network and the user has not
   ruled it out. Read each check; `Issues found — see above` prints for any
   warning and doctor exits 0 either way.
3. Report each defect with the file or profile field it lives in, what is
   wrong with it, and the fix, and say what you could not verify.
4. Honor the user's limits exactly. If they say not to run a command, do not
   run it, including to "just check". Do not edit `~/.coa/config` or run
   `coa init` / `coa doctor --fix` on your own initiative. Never print a
   secret.

## Which profile a command uses

Precedence: `--profile`, then the workspace binding (`profile:` in
`workspace.yml`), then the config's `[default] profile=` key, then `default`.
`coa profile list -d <dir>` and the doctor header both show the profile in
force and what selected it.

- If the workspace is bound, run local commands without `--profile`; the flag
  overrides the user's binding.
- If nothing is bound, pass `--profile <name>` for the workspace's platform on
  `sources`, `create`, `run`, `install`, `doctor`, `init`. A profile for the
  wrong platform fails with `Profile "<name>" is for <x>, but this is a <y>
  workspace.`
- Only workspace commands read the binding. Cloud Operations commands resolve
  from flags alone.
- `coa validate` takes no profile and needs no warehouse.

Bindings are per workspace directory, which lets workspaces on different
platforms coexist. `coa profile use` and `coa init` refuse a profile whose
platform disagrees with `data.yml` (no `platformKind` counts as Snowflake; no
`data.yml` is unconstrained).

## Credentials

Platform credentials, `token`, `domain`, and `environmentID` live in
`~/.coa/config`. Snowflake (Basic, KeyPair, OAuth), Databricks (Token,
OAuthM2M), and BigQuery (ServiceAccount, ApplicationDefault) are supported,
with a CLI flag for every field on `coa init` and `coa profile create`.
Snowflake OAuth tokens come from `coa auth warehouse login -d <dir>`, a
browser flow. `workspace.yml` holds a profile name and local mappings, never
credentials. Never put secrets in repo files.

## Approval gates

- Without asking: `coa validate`, `coa describe`, `--dry-run`, `coa install`,
  `coa doctor` without `--fix`, `coa profile list` / `show`.
- Ask first: `coa init`, `coa doctor --fix`, `coa profile create` /
  `set-cloud` / `delete` / `rename` / `use` / `unset`, edits to `data.yml` /
  `locations.yml` / `workspace.yml`, every Cloud Operations command, and any
  push. `delete` and `rename` repair only the binding in `-d <dir>`; other
  workspaces bound to that profile break.
