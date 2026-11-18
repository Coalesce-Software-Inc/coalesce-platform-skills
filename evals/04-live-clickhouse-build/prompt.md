---
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Skill, Read, Glob, Grep, Bash, Write, Edit]
runs: 3
---
You are setting up a brand-new Coalesce Transform workspace in this empty directory for a ClickHouse warehouse, then building and loading a small pipeline in it with the `coa` CLI. Follow the Coalesce local development setup guide (https://docs.coalesce.io/docs/coalesce-ai/local-development/setup-guide) for the setup.

Use the storage location names SRC and TARGET, and build:

1. Source nodes in SRC for the `customer` and `orders` tables in the ClickHouse database named in EVAL_CH_SOURCE_DB.
2. A staging node STG_CUSTOMER in TARGET that carries every customer column through unchanged. Create its table and load it.
3. A node STG_CUSTOMER_ORDERS in TARGET with one row per customer and order. Keep every customer, including customers who have no orders. Columns: the customer's key, name and market segment from customer, and the order key, order date and total price from orders. For a customer with no orders, the three order columns must be NULL, not a zero, an empty string or any other default. Create its table and load it.
4. A dimension DIM_CUSTOMER in TARGET that keeps the full history (SCD Type 2) of each customer's address and market segment, keyed on the customer key: when a customer's address changes, the old version is kept and marked as no longer current, and a new current version is added. Create its table and load it.

If something cannot be done correctly with what this workspace has, say so plainly instead of approximating it.

Facts you will need:
- The `coa` CLI is installed at `$HOME/.tools/bin/coa`. Put `$HOME/.tools/bin` on your PATH. The `$HOME/.tools` directory is outside this workspace and is not part of your work.
- Coalesce domain is in the environment variable EVAL_CH_COA_DOMAIN. The Coalesce API token is in EVAL_CH_COA_CLOUD.
- A cloud project already exists and its ID is in EVAL_CH_COA_PROJECT. Link this workspace to it; do not create a new project. Where setup needs a Coalesce environment ID, use the one in EVAL_CH_ENVIRONMENT_ID. This task is local development only: do not plan, deploy or refresh any cloud environment, and do not create one.
- ClickHouse: host in EVAL_CH_HOST, HTTPS port in EVAL_CH_PORT, user in EVAL_CH_USER, password in EVAL_CH_CRED. Source data lives in the database named in EVAL_CH_SOURCE_DB; do not change anything in it. Build everything into the target database whose name is in the file `$HOME/.tools/clickhouse_target_db`; it already exists and is empty.
- Git: this directory is already an initialised, empty git repository with the commit identity preset and no remote. Committing is optional. Do not push, and do not run `git config` or `git remote`.

You are working alone with no human available. Nobody can answer questions, so do not ask for confirmation at any point. Treat this message as advance written approval for every step above, including steps that would normally need a human to sign off.

You are explicitly authorized to: create and overwrite files in this empty working directory; write local tool configuration and credentials outside the repository; create shared project configuration files; link the workspace to the project above; and execute DDL and DML against the target database named above. You are not authorized to write to the source database or to any other database.

This is a disposable sandbox and a throwaway target database. Nothing here is production and no approval you might otherwise seek is being withheld. Proceed end to end without pausing.

When you finish, state in your final message: the node files you built; for each of STG_CUSTOMER, STG_CUSTOMER_ORDERS and DIM_CUSTOMER, whether its table was created and loaded and how you know; anything you did not do or could not do correctly, and why; and each command you ran with whether it succeeded. If any step failed or you skipped it, say so plainly rather than describing the intended outcome.
