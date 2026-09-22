# Eval suite

Run with `claude plugin eval`, ablated with/without the plugin. Cases:

| case | tag | what it covers |
|---|---|---|
| `01-live-bootstrap-plan-deploy` | `live` | Bootstrap an empty workspace, build `REGION` → `STG_REGION`, push a branch, create a cloud Environment, plan → deploy → refresh into it. 23 graders. |
| `02-neg-plain-snowflake-sql` | — | Negative: a plain Snowflake question must not pull the Coalesce skills in. |
| `00-sandbox-probe` | `probe` | Scratch case for sandbox egress and credential passing. Delete once the harness settles. |

## Configuration

This repository is public, so no case hard-codes a domain, project, account,
database, schema or repository. Every site-specific value is read from an
environment variable at run time; the cases carry only variable names.

The operator exports these before running. They live in an untracked `.env` at
the repository root (gitignored) and are re-exported under `EVAL_*` names
because the eval sandbox strips variables whose names contain TOKEN, PAT, AUTH,
KEY or SECRET.

| variable | holds | secret |
|---|---|---|
| `EVAL_COA_DOMAIN` | Coalesce app URL | no |
| `EVAL_COA_PROJECT` | cloud project ID the run deploys into | no |
| `EVAL_COA_CONNECTION` | warehouse connection account for new Environments | no |
| `EVAL_COA_CLOUD` | Coalesce API token | **yes** |
| `EVAL_SNOWFLAKE_ACCOUNT` | Snowflake account | no |
| `EVAL_SNOWFLAKE_USER` | Snowflake user | no |
| `EVAL_SNOWFLAKE_WAREHOUSE` | warehouse for local `coa run` | no |
| `EVAL_SNOWFLAKE_PK_FILE` | path to the key-pair `.p8` (the file is copied into the sandbox) | path to a **secret** |
| `EVAL_SOURCE_DB` / `EVAL_SOURCE_SCHEMA` | source data location | no |
| `EVAL_TARGET_DB` / `EVAL_TARGET_SCHEMA` | target location for built tables | no |
| `EVAL_GIT_REMOTE` | repository the case pushes its branch to | no |
| `EVAL_GH_CRED` | GitHub token for that push | **yes** |

## Running

See [EVALS.md](../EVALS.md) at the repository root for setup, the run command,
how to evaluate an open pull request, and how to read the results.

## Reading the results

See [EVALS.md](../EVALS.md).
