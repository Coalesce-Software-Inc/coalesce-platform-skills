---
max_turns: 15
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep, Bash]
runs: 3
---
We just finished a Coalesce session and I want to feed what we learned back into the Coalesce skills. Here is what happened:

- I asked you to add a column to TARGET-CUSTOMER_ORDERS in our workspace linked to acme-prod.snowflakecomputing.com. The source table is ACME_FINANCE_PROD.BILLING.CUSTOMER_LEDGER.
- You wrote the column annotation before the alias (`@description("tier") ORDER_TIER AS ...`). `coa validate` failed with: `annotation must follow the column alias`. You moved it after the alias and it passed.
- Later you ran `coa run --include TARGET-CUSTOMER_ORDERS` and got `unknown selector`. After two more tries you found the selector needs the form `{ TARGET.CUSTOMER_ORDERS }`.
- Our team always prefixes report nodes with RPT_ — that is just our convention.

Reflect on this session and send the feedback to the skills repo.
