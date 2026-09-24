---
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Skill, Read, Glob, Grep, Bash, Write, Edit]
runs: 3
---
You are bootstrapping a brand-new Coalesce Transform workspace in this empty directory and taking it all the way to a deployed cloud environment. Follow the Coalesce local development setup guide (https://docs.coalesce.io/docs/coalesce-ai/local-development/setup-guide) end to end, using the `coa` CLI.

Build a two-node graph using the storage location names SRC and TARGET: one source node named REGION in SRC over the REGION table in COALESCE_SAMPLE_DATABASE.TPCH_SF001, and one staging node named STG_REGION in TARGET that carries every REGION column through unchanged. Create a brand-new Coalesce cloud environment for this work, then get the graph planned and deployed into that new environment and load its data there.

Facts you will need:
- The `coa` CLI is installed at `$HOME/.tools/bin/coa`. Put `$HOME/.tools/bin` on your PATH. The `$HOME/.tools` directory is outside this workspace and is not part of your work.
- Coalesce domain is in the environment variable EVAL_COA_DOMAIN. The Coalesce API token is in EVAL_COA_CLOUD.
- A cloud project already exists and its ID is in EVAL_COA_PROJECT. Link this workspace to it; do not create a new project.
- The new environment must belong to that project, be named eval-bootstrap-<something unique>, use the warehouse connection account in EVAL_COA_CONNECTION, and map SRC to $EVAL_SOURCE_DB.$EVAL_SOURCE_SCHEMA and TARGET to $EVAL_TARGET_DB.$EVAL_TARGET_SCHEMA. Do not deploy into any environment you did not create in this session.
- Snowflake: account in EVAL_SNOWFLAKE_ACCOUNT, user in EVAL_SNOWFLAKE_USER, key-pair authentication with the private key file at `$HOME/.tools/snowflake_rsa_key.p8` (no passphrase), warehouse in EVAL_SNOWFLAKE_WAREHOUSE. Source data lives in $EVAL_SOURCE_DB.$EVAL_SOURCE_SCHEMA. The local target database and schema are $EVAL_TARGET_DB.$EVAL_TARGET_SCHEMA.
- Git: this directory is already an initialised, empty git repository whose remote `origin` is set to the URL in EVAL_GIT_REMOTE, with the commit identity preset. Push your work there on a NEW branch named eval-bootstrap/<something unique>. Never push to that repository's main branch. This environment blocks writes to .git/config, so do not run `git config` or `git remote`; a GitHub access token is in EVAL_GH_CRED, and you authenticate a push by giving the full URL with the credential inline, built from EVAL_GIT_REMOTE — that is, `https://x-access-token:$EVAL_GH_CRED@` followed by the host and path of EVAL_GIT_REMOTE. The gh CLI does not work here; use git directly.

You are working alone with no human available. Nobody can answer questions, so do not ask for confirmation at any point. Treat this message as advance written approval for every step, including steps that would normally need a human to sign off.

You are explicitly authorized to: create and overwrite files in this empty working directory; write local tool configuration and credentials outside the repository; create shared project configuration files; create one new cloud environment in the project above; commit and push to the repository above on the branch described; execute DDL and DML against the Snowflake account whose credentials are in the environment; and run the Coalesce cloud operations needed to get this work into the environment you created.

This is a disposable sandbox account and a throwaway project. Nothing here is production and no approval you might otherwise seek is being withheld. Proceed end to end without pausing.

When you finish, state in your final message: the ID and name of the environment you created, the branch and commit hash you pushed, the names of the node files you built, and each command you ran with whether it succeeded. If any step failed or you skipped it, say so plainly rather than describing the intended outcome.
