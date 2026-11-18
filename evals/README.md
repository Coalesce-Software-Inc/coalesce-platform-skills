# Eval suite

Run with `claude plugin eval`, ablated with/without the plugin. Cases:

| case | tag | what it covers |
|---|---|---|
| `01-live-bootstrap-plan-deploy` | `live` | Bootstrap an empty workspace, build `REGION` → `STG_REGION`, push a branch, create a cloud Environment, plan → deploy → refresh into it. 23 graders. |
| `02-neg-plain-snowflake-sql` | — | Negative: a plain Snowflake question must not pull the Coalesce skills in. |
| `03-create-app` | `offline` | Build a workspace app over the `medallion-greenfield` sample (nodes by location, column counts, search), then start it the way Coalesce does. Checks the runtime contract, the port guard, and the node list it serves. No cloud, warehouse or git. |
| `04-live-clickhouse-build` | `live`, `clickhouse` | Bootstrap a ClickHouse workspace, add `customer` and `orders` sources, build and load `STG_CUSTOMER` and a customer-to-orders LEFT JOIN that must give NULL for customers without orders, and handle a request for SCD Type 2 history without faking it. Local only: no cloud deploy, no push. 13 graders. |
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

The ClickHouse case (`04-*`) needs these instead. `run.sh` only requires the variables of the cases a run selects.

| variable | holds | secret |
|---|---|---|
| `EVAL_CH_COA_DOMAIN` | Coalesce app URL for the ClickHouse project (defaults to `EVAL_COA_DOMAIN`) | no |
| `EVAL_CH_COA_CLOUD` | Coalesce API token for that domain (defaults to `EVAL_COA_CLOUD`) | **yes** |
| `EVAL_CH_COA_PROJECT` | cloud project (platform `tdbc-clickhouse`) the workspace links to | no |
| `EVAL_CH_ENVIRONMENT_ID` | an existing environment ID `coa init` can record; the case never deploys to it | no |
| `EVAL_CH_HOST` / `EVAL_CH_PORT` | ClickHouse host and HTTPS port (port defaults to `8443`) | no |
| `EVAL_CH_USER` | ClickHouse user | no |
| `EVAL_CH_CRED` | ClickHouse password | **yes** |
| `EVAL_CH_SOURCE_DB` | database holding TPC-H `customer` and `orders` (read only) | no |
| `EVAL_CH_TARGET_DB_PREFIX` | prefix for the target database `setup.sh` creates per run (`<prefix>_<timestamp>_<random>`); the user needs `CREATE DATABASE` | no |
| `EVAL_COA_PKG_DIR` | optional: a `coa` package directory (holding `coa.js`) to test instead of the `coa` on PATH; it must support ClickHouse | no |

## Running

See [EVALS.md](../EVALS.md) at the repository root for setup, the run command,
how to evaluate an open pull request, and how to read the results.

## Reading the results

See [EVALS.md](../EVALS.md).
