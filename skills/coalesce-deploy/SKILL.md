---
name: coalesce-deploy
description: Use when promoting a Coalesce Transform workspace to a cloud Environment with the coa CLI — choosing or creating the Environment (coa environments), writing the committed environments/<NAME>.yml mapping file coa plan needs, running coa plan, reviewing coa-plan.json, coa deploy, coa refresh, and reading run results (coa runs, coa nodes). Also rerun/cancel of a failed or running refresh. Every mutating step is ASK FIRST.
---
<!-- coalesce-node-managed: true -->

> **Prerequisite — load `coalesce-pipelines` first.** If you have not already
> loaded the `coalesce-pipelines` skill in this session, load it now, read its
> "Orient first" step and Rules, then return here. Credentials, profiles, and
> `coa init`/`doctor` are in coalesce-cloud-api; committing and pushing is in
> coalesce-git-publication. This skill starts where those stop: the work is
> validated, committed, and pushed.

# Plan, deploy, and refresh a cloud Environment

`coa create` / `coa run` are local development against the warehouse. Getting
the same pipeline to run as a managed **Environment** in the Coalesce App is a
separate, cloud-side process driven by the CLI's Cloud Operations commands:

| Step | Command | What it does |
|---|---|---|
| Deploy | `coa plan` → `coa deploy` | Diffs the workspace against the Environment's deployed state and applies the **DDL** (create/alter/drop tables and views, metadata). |
| Refresh | `coa refresh` | Runs the **DML** (truncate/insert/merge) for deployed nodes. Requires a successful deploy first. |
| Recover | `coa rerun <runID>`, `coa cancel <runID>` | Retry the failed nodes of a refresh; stop a run in flight. |

Every one of these is a real change to shared cloud state and to the target
database. They are **ASK FIRST**, one at a time, with the plan summary in the
user's hands before `deploy`.

## Step 0 — Orient

1. **The work must be committed.** `git status --short` is clean for Coalesce
   files and the branch is pushed (coalesce-git-publication). `coa plan` reads
   the *local working directory*, so an unpushed or dirty tree plans something
   nobody else can see, and a dirty tree makes `plan` prompt (see Step 3).
2. **Pick the profile explicitly.** Cloud Operations commands do NOT read the
   workspace's profile binding; pass `--profile <name>` on every command in this
   skill. `coa profile list -d <dir>` shows what exists. The profile needs
   `domain`, `token`, and — for `plan`/`deploy`/`refresh`/`rerun` and, in
   practice, for the `environments`/`nodes`/`runs` groups too — a complete
   warehouse credential set (Snowflake KeyPair or Basic; Databricks; BigQuery).
   Snowflake OAuth profiles fail every cloud command with `Snowflake OAuth
   (browser sign-in) is supported for local workspace commands only`. The
   deploy and refresh run under those warehouse credentials, so that identity
   needs rights on the Environment's target database and schema.
3. `coa doctor -d <dir> --profile <p>` — cloud token and warehouse both `✓`
   before you spend a plan on a broken profile.
4. **Know the target.** The user names the Environment (by name or ID) or asks
   for a new one. Never pick one for them and never plan or deploy against an
   Environment the user did not name — even "just to see the diff": a plan
   against the wrong Environment is cheap, a deploy is not.

## Step 1 — Find or create the Environment

List and read are safe to run without asking:

```sh
# The environments/nodes/runs/jobs/projects groups take NO --domain flag;
# domain comes from the profile. Use --format json — the text table wraps
# createdBy over three lines and cannot be parsed. Never use --paging.
coa environments list --profile <p> --project <projectID> --format json --skipConfirm \
  | jq -r '.data[] | [.id, .name, .status] | @tsv'
coa environments get --profile <p> --environmentID <id> --format json --skipConfirm
```

`list` returns `{data: [{id, name, project, status, createdAt, createdBy}],
total, limit, next, orderBy}`; `--project <projectID>` filters server-side.
`get` returns the full record: `connectionAccount`, `defaultStorageMapping`,
`currentMappings` (`{LOC: {database, schema}}`), `runTimeParameters`,
`status` (`Waiting` idle; `Deploying`/`Refreshing` in flight; `Failed Deploy`/
`Failed Refresh` after an error), and `deployedCommit` once something has been
deployed. **`id` is a string** (`"42"`), everywhere.

**Create** (ASK FIRST — new shared cloud object). Coalesce 7.36+; the installed
build takes flags (older docs show `--inputFile <request.json>` with the same
fields):

```sh
coa environments create --profile <p> --skipConfirm --format json \
  --name "<name>" --project <projectID> \
  --connectionAccount <snowflake account, e.g. xy12345.us-central1.gcp> \
  --defaultStorageMapping TARGET \
  --mappings '{"SRC":{"database":"<DB>","schema":"<SCHEMA>"},"TARGET":{"database":"<DB>","schema":"<SCHEMA>"}}' \
  --description "<why this environment exists>"
```

Databricks uses `--accessUrl` instead of `--connectionAccount`. The response is
the same record `get` returns — read `.id` from it and report it. Give every
storage location in `locations.yml` a mapping and make `--defaultStorageMapping`
one of them. Create/update never accept warehouse passwords or OAuth tokens;
the CLI deploys with your profile's credentials, and App-driven runs use the
User Credentials set in **Build Settings › Environments**.

`coa environments update --environmentID <id> --inputFile <patch.json>` is a
partial update (omitted fields unchanged, `null` clears). `coa environments
delete --environmentID <id> --skipConfirm` is destructive and irreversible —
ASK FIRST, quote the name and ID back, and only after confirming no runs or
job schedules depend on it.

## Step 2 — The committed Environment mapping file (the gotcha)

`coa plan` does **not** read the Environment's `currentMappings` from the
API. It resolves every node's storage location from a file in the repo,
`environments/<NAME>.yml`, whose `id` equals the `--environmentID` you pass.
`coa init` does not scaffold it, and without it a plan against a fresh
Environment fails like this even though `environments get` shows perfect
mappings:

```
  Errors (3)
  ✖ Missing or Invalid Storage Mappings
      • Storage Location SRC has an invalid schema or database value. Schema: "N/A", Database: "N/A".
      • Storage Location TARGET has an invalid schema or database value. Schema: "N/A", Database: "N/A".
  ✖ Invalid Storage Location
      • Node STG_REGION is configured to use the Storage Location TARGET, but the Mapping ... Schema: N/A, Database: N/A.
  ✖ Errors Detected
  ✖ Plan failed: Issues preventing deployment were found; please review the issues itemized above.
```

The fix is one file, `coa describe schema environment` — all five keys
required, nothing else allowed:

```yaml
fileVersion: 1
id: "42"                        # the Environment ID, quoted string — this is the lookup key
name: my-dev-environment        # the Environment's name in the App
type: Environment
mappingDefinitions:             # one entry per name in locations.yml
  SRC:
    database: COALESCE_SAMPLE_DATABASE
    schema: TPCH_SF001
  TARGET:
    database: ANALYTICS_DEV
    schema: PUBLIC
```

- Keys under `mappingDefinitions` must match `locations.yml` names exactly;
  every location a node uses needs one. Copy the values from `environments get
  … | jq .currentMappings` so the App and the CLI agree.
- This is shared config under `environments/` (coalesce-workspace-config):
  writing it for the Environment the user asked you to deploy to is implied by
  the request; changing an existing Environment's mappings is ASK FIRST.
- Run `coa validate -d <dir>` (it schema-checks the file), then commit and
  push it with explicit paths — every teammate and CI deploying to that
  Environment needs it. The UI writes these files too when a Workspace deploys.

## Step 3 — Plan

```sh
coa plan --profile <p> --environmentID <id> -d <dir> --out ./coa-plan.json \
  --gitsha "$(git rev-parse HEAD)"
```

- **Files come from `-d`/the working directory, never from the pushed commit.**
  `--gitsha` only labels the plan (the App shows it as the deployed commit).
  Without it, `plan` reads the current branch's HEAD, prints a `Git context`
  block, and if any tracked Coalesce path (`nodes/`, `nodeTypes/`,
  `environments/`, `jobs/`, `subgraphs/`, `macros/`, `packages/`, `data.yml`,
  `locations.yml`) is modified or untracked it prompts `You have uncommitted
  changes in this branch … Press Y to proceed or N to cancel` — there is no
  non-interactive flag and a piped run hangs with no output. Commit first (the
  right answer) or pass `--gitsha` (skips the git check entirely).
- `--parameters '{"key":"value"}'` overrides Environment defaults **at plan
  time**; the SQL is rendered then. `--parameters` on `deploy` does nothing.
  Undefined `{{ parameters… }}` references surface as **warnings** and do not
  block the plan.
- `--enableCache` only when plans are slow; `--include`/`--exclude` are not
  supported on `plan` — a plan covers the whole workspace. Exclude a node with
  `deployEnabled: false` in its file (and know that flipping it on a deployed
  node **drops** that object at the next deploy).
- Success prints `● Plan starting` … `Plan completed successfully  (9.3s)` and
  writes the plan file; failure prints `Errors (N)` blocks and `✖ Plan failed:
  …`. Only five messages per block are shown — add `--verbose` for all of them.
  Warnings print as `Warnings (N)` and still write the file.

**Review `coa-plan.json` before asking to deploy** — it is the only preview
you get. Never hand-edit it; fix the files and re-plan.

```sh
jq '{env: .targetEnvironment, commit: .gitInfo.oid, stop: .issues.stop, warn: .issues.warn,
     added:   (.phasedNodeEdits.addedTable   | keys | length),
     altered: (.phasedNodeEdits.alteredTable | keys | length),
     deleted: (.phasedNodeEdits.deletedTable | keys | length)}' coa-plan.json
# per-node detail; node IDs map to names via environmentState.steps
jq -r '.environmentState.steps | to_entries[] | [.key, .value.operation.locationName, .value.operation.name] | @tsv' coa-plan.json
jq '.phasedNodeEdits | map_values(map_values(map(.description)))' coa-plan.json
```

Top-level keys: `targetEnvironment` (the ID), `gitInfo{oid, commit.message}`,
`issues{stop, warn}`, `phasedNodeEdits{addedTable, alteredTable, deletedTable}`
keyed by node ID (each edit has a `description` such as `Adding metadata for
REGION`), `phasedDependencies`, `presyncDetails`, `environmentState{steps,
locations, jobs, macros, installedPackages, …}`, `runtimeParameters`. Tell the
user what will be added, altered and — above all — **deleted**; `deletedTable`
entries are DROP statements against the Environment's database. A
`nodeChangeSummaries` of `{}` on a first deploy is normal.

## Step 4 — Deploy (ASK FIRST, with the plan summary)

```sh
coa deploy --profile <p> --environmentID <id> --plan ./coa-plan.json --out ./coa-deploy-results.json
```

- No `-d`: deploy consumes the plan file. The plan is bound to the
  `targetEnvironment` inside it; re-plan after *any* file change or for a
  different Environment.
- Output: `● Deployment starting`, `● Deploy run initialized  RunCounter: 1234`
  (that is the run ID), a `Making metadata updates` presync phase, then
  `Deployment completed successfully  (10.2s)` or `✖ Deploy failed: …`. Presync
  lines like `Object unexpectedly exists at location` / `Object missing from
  expected location` mean it adopted or recreated warehouse objects changed
  outside Coalesce — report them, they are not errors.
- `--out` JSON is `{runResults: {runID, runType: "deploy", runStatus,
  environmentID, runStartTime, runEndTime, runTimeParameters,
  runResults: [{nodeID, runState, queryResultSequence: {name, queryResults:
  [{name, sql, status, success, error, rowsInserted?}]}}]}}` (note the nested
  `runResults.runResults`). `runStatus` is one of `completed`, `failed`,
  `canceled`, `running`, `waitingToRun`.
- A failed deploy leaves the Environment in `Failed Deploy`; fix, re-plan,
  re-deploy. `refresh` refuses to run in that state unless
  `--forceIgnoreEnvironmentStatus` — never pass that without asking.
- Keep the artifacts out of the repo. `coa init`'s `.gitignore` covers
  `workspace.yml` and `.coa/` but not these; append `coa-plan.json` and
  `coa-*-results.json` (the docs do the same), or write them under `$TMPDIR`.

## Step 5 — Refresh (ASK FIRST)

```sh
coa refresh --profile <p> --environmentID <id> --include '{ * }' --out ./coa-refresh-results.json
coa refresh --profile <p> --environmentID <id> --include '{ STG_REGION }'
coa refresh --profile <p> --environmentID <id> --include '{ location: "TARGET" }' --exclude '{ nodeType: "Source" }'
coa refresh --profile <p> --environmentID <id> --jobID <jobID> --parallelism 8
```

- Selectors are the App's Selector Query syntax (`coa describe selectors`):
  `{ NAME }`, `{ name: "X" }`, `{ location: "L" }`, `{ nodeType: "Stage" }`,
  `+{ X }` for upstream, joined with `OR`. Refreshing a Source node only
  validates the table exists (`SELECT 1 … LIMIT 0`); the DML happens in the
  transformation nodes.
- `--parameters '<json>'` **replaces the whole runtime-parameter map** for that
  run — omitted keys are gone. Pass the full map or omit the flag to use the
  Environment defaults.
- Output mirrors deploy: `● Refresh run initialized  RunCounter: 1235` …
  `Refresh completed successfully  (11.8s)`. The `--out` shape is the same
  with `runType: "refresh"`; per-query `rowsInserted` is the row count to
  report.

## Step 6 — Verify and report

Read-only, run without asking:

```sh
coa environments get --profile <p> --environmentID <id> --format json --skipConfirm \
  | jq '{status, deployedCommit, currentMappings}'          # status Waiting, deployedCommit == the sha you planned
coa nodes list --profile <p> --environmentID <id> --format json --skipConfirm \
  | jq -r '.data[] | [.name, .locationName, .nodeType, .database, .schema] | @tsv'
coa runs list --profile <p> --environmentID <id> --limit 5 --format json --skipConfirm \
  | jq -r '.data[] | [.id, .runType, .runStatus, .runStartTime] | @tsv'
coa runs get --profile <p> --runID <runID> --format json --skipConfirm        # runDetails, userCredentials (no secrets), runStatus
coa runs list-results --profile <p> --runID <runID> --format json --skipConfirm \
  | jq -r '.data[] | .name as $n | .queryResults[] | [$n, .name, .status, (.rowsInserted // "")] | @tsv'
```

Then tell the user: Environment name and ID, the commit deployed, the deploy
and refresh run IDs with their `runStatus`, the nodes now in the Environment,
rows loaded per node, and any presync or warning lines verbatim. If a step
failed or was skipped, say so; do not describe the intended outcome.

## Failed or stuck runs

```sh
coa rerun <runID> --profile <p> --environmentID <id> --out ./coa-rerun-results.json   # runID is POSITIONAL
coa cancel <runID> --profile <p> --environmentID <id>
```

`rerun` retries only the nodes that failed in that refresh and does **not**
carry the original `--parameters` — pass them again. Both are ASK FIRST.
Deploys are not rerun: fix, re-plan, re-deploy.

## Approval gates

- **Without asking:** `coa environments list/get`, `coa nodes list/get`,
  `coa runs list/get/list-results`, `coa jobs get`, `coa projects list/get`,
  `coa doctor` without `--fix`, `coa validate`, reading `coa-plan.json` and
  result files.
- **Implied by "plan/deploy X to Environment Y":** `coa plan` against Y,
  writing `environments/<Y>.yml` for Y if it is missing, appending the plan and
  result artifacts to `.gitignore`.
- **ASK FIRST, each time, with the specifics:** `coa deploy` (show the
  add/alter/delete summary), `coa refresh`/`rerun` (say which nodes, into
  which database.schema), `coa cancel`, `coa environments create/update/
  delete`, any `--forceIgnoreEnvironmentStatus`, changing an existing
  Environment's `mappingDefinitions`, and any `--parameters` override.
- **NEVER:** plan or deploy against an Environment the user did not name;
  deploy a plan generated from uncommitted or unpushed files; hand-edit
  `coa-plan.json`; commit `coa-plan.json` or result files; pass `--token` on
  the command line when a profile exists (it lands in shell history and logs —
  and never echo it); use `--paging`; call `coa create`/`coa run` a deploy.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Missing properties: environmentID` from `environments`/`nodes`/`runs` | The profile has no `environmentID`; the API groups read it from the profile even for `list`. | Use a profile written by `coa init`/`coa profile set-cloud` with an `environmentID`, or pass `--environmentID` where the command takes it. |
| `[authFromProfile] Could not determine valid auth type from CLI config … Provided fields: ["domain","environmentID","token"]` | Profile has cloud fields but no warehouse credentials. The API groups still require a complete platform profile. | Use the profile that `coa init` created (KeyPair/Basic + token), or `coa profile create` one (ASK FIRST). |
| `error: unknown option '--domain'` on `environments list` | Those groups have no `--domain`. | Drop it; the profile supplies the domain. |
| `coa <group> <sub> --help` prints the root help | Shell passed the arguments as one word (zsh `$var` does not split), or an older build. | Quote/split correctly, or `coa <group> help <sub>`. |
| `Missing or Invalid Storage Mappings … Schema: "N/A"` | No `environments/<NAME>.yml` with `id` equal to `--environmentID`, or a location missing from its `mappingDefinitions`. | Step 2. |
| `Plan failed: Issues preventing deployment were found` with little detail | Validation errors (column-reference false positives on SQL nodes, YAML reference errors) or truncated messages. | `coa validate --verbose -d <dir>`; re-run `plan` with `--verbose`. |
| `plan` prints nothing and hangs | Waiting on the uncommitted-changes prompt. | Commit, or pass `--gitsha`. |
| `Snowflake OAuth (browser sign-in) is supported for local workspace commands only` | OAuth profile on a cloud command. | `--profile` with KeyPair or Basic. |
| Environment stuck in `Failed Deploy`; `refresh` refuses | Last deploy failed. | Fix and re-deploy; `--forceIgnoreEnvironmentStatus` only with approval. |
| Deploy shows `deletedTable` entries you did not expect | A node file was removed, renamed, or got `deployEnabled: false`. | Stop and confirm with the user — those are DROPs. |
| `Deployment completed` but the App shows no Workspace | CLI deploys need no Workspace; the App only *browses* via one. | Connect the repo to the Project and attach the pushed branch to a Workspace in the App (setup guide, Step 5). |
