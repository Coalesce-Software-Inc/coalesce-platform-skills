# Running the eval suite

The plugin ships a `claude plugin eval` suite under `evals/`. Every case runs
twice, once with the plugin loaded and once without, so a result says what the
plugin changed rather than what the model can do.

| case | tag | what it covers |
|---|---|---|
| `01-live-bootstrap-plan-deploy` | `live` | The full workflow against real infrastructure: bootstrap an empty workspace, build `REGION` and `STG_REGION`, push a branch, create a cloud Environment, then plan, deploy and refresh into it. 24 graders. |
| `02-neg-plain-snowflake-sql` | — | Negative case. A plain Snowflake question must not load the Coalesce skills. |
| `00-sandbox-probe` | `probe` | Scratch case for sandbox network access and credential passing. Excluded from default runs. |

The live case talks to a real Coalesce cloud and a real Snowflake account. A
single run costs roughly **$8 to $12** and takes **20 to 45 minutes**, and it
leaves a cloud Environment behind that nothing deletes.

## One-time setup

You need three things.

**1. The `coa` CLI on your PATH.** `evals/01-live-bootstrap-plan-deploy/setup.sh`
copies the installed package into each sandbox, so whatever version you have is
the version under test. Check with `coa --version`.

**2. A Snowflake key-pair private key file** readable on this machine.

**3. An untracked `.env` at the repository root.** It is gitignored and must
never be committed. `evals/README.md` lists every variable and marks which two
hold secrets. Most values can carry the names the rest of your tooling already
uses; `evals/run.sh` maps them:

| the script reads | falling back to |
|---|---|
| `EVAL_COA_CLOUD` | `AUTH_TOKEN` |
| `EVAL_GH_CRED` | `DEV_AGENT_GITHUB_PAT` |
| `EVAL_SNOWFLAKE_ACCOUNT` | `DEV_AGENT_WORKSPACE_SNOWFLAKE_ACCOUNT` |
| `EVAL_SNOWFLAKE_USER` | `DEV_AGENT_WORKSPACE_SNOWFLAKE_USER` |
| `EVAL_SNOWFLAKE_PK_FILE` | `DEV_AGENT_SNOWFLAKE_PK` |

The renaming exists because the eval sandbox strips variables whose names
contain TOKEN, PAT, AUTH, KEY or SECRET. Anything passed under those names
never reaches the case.

## Running

```sh
evals/run.sh                    # the live case, one run per arm
evals/run.sh --case '02-*'      # a different case
evals/run.sh --runs 3           # three runs per arm
evals/run.sh --print            # assemble the command and show it, run nothing
```

`run.sh` sources `.env`, applies the mapping above, checks every variable
resolves before spending anything, and derives the sandbox network grants from
your configuration. Flags you pass replace the matching default rather than
being appended.

Start with `--print`. It costs nothing and catches an incomplete `.env`, which
is the usual reason a run dies ten minutes in.

This repository is public, so no case and no script contains a domain, project,
warehouse account, database, schema or repository. Every site-specific value is
read from the environment at run time.

## Evaluating an open pull request

`claude plugin eval .` tests the plugin **at the path it is run from**, so
pointing it at a pull request means running it from a worktree that has that
pull request's code. The eval suite lives on `develop`, so a branch cut before
the suite landed needs `develop` merged into it first.

```sh
# 1. A worktree holding develop plus the pull request's changes.
git fetch origin
git worktree add --detach /tmp/eval-pr<N> origin/develop
cd /tmp/eval-pr<N>
git merge origin/<the pull request's branch>

# 2. Resolve any conflicts, then confirm the tree is clean.
git status --porcelain          # must print nothing

# 3. Credentials. .env is gitignored, so it does not follow a worktree.
ln -s /path/to/your/main/checkout/.env .env

# 4. Check, then run.
evals/run.sh --print
evals/run.sh
```

Do not skip step 2. `claude plugin validate . --strict` **passes on a tree with
conflict markers still in the skill files**, so nothing downstream will warn
you, and you will spend a full run evaluating a broken plugin. `git status` is
the check that works.

Two related traps:

- GitHub's `refs/pull/<N>/merge` ref and the `mergeable` field are computed
  lazily and go stale after the base branch moves. Do the merge yourself.
- Clean up when you are done: `git worktree remove --force /tmp/eval-pr<N>`.

## Reading the results

Each run writes `evals/results/<timestamp>/` with an `aggregate-result.json` and
a `report.html`. That directory is gitignored; it is several megabytes per run.

**Read effort, not just score.** With `max_turns` at 120 a determined agent
reaches a correct result either way, so the score saturates and stops
discriminating. Across the five runs recorded on pull request #28 the score
difference changed sign (-0.06, +0.18, 0.00, +0.04, +0.04) while the arm
without the plugin made more `coa` calls and hit more CLI errors every single
time.

```sh
evals/tools/trace-metrics.py evals/results/*/aggregate-result.json
```

It prints turns, bash calls, `coa` calls, CLI errors and per-subcommand counts
for each arm. It needs explicit paths, not a bare invocation.

It reads the preserved sandboxes, which is why `run.sh` passes `--keep-temp`.
Those sandboxes live under `/private/tmp` and are reaped by the operating
system, so run this soon after the eval. Once they are gone the tool reports
`trace reaped` and only the scores in `aggregate-result.json` survive.

`coa describe` counts are the clearest single signal: an agent with no skill to
read calls it repeatedly to work out the CLI's schema.

## After a run

Every live run creates a cloud Environment and does not delete it. There is no
teardown step yet, so delete them by hand or they accumulate.
