---
type: llm
focus: trace
weight: 1
---
Examine the coa commands in the trace for the nodes STG_CUSTOMER and STG_CUSTOMER_ORDERS. Score PASS only if ALL hold:

1. For STG_CUSTOMER, a `coa create` and then a `coa run` that are NOT dry-runs (no `--dry-run` flag) and that include STG_CUSTOMER both completed successfully on their last attempt: exit code 0, no "✖" line for that node, no error such as "Unknown expression identifier", "does not exist" or "Syntax error".
2. The same holds for STG_CUSTOMER_ORDERS.
3. Each successful `coa run` actually executed an insert for the node (its output shows the node passing with one or more statements), rather than "Template rendered zero SQL stages" or an empty run.
4. Neither node reached success by editing anything under nodeTypes/ or by hard-coding a database.table in place of a two-argument ref().

Earlier failed attempts that were then fixed are fine; judge the final attempt. A step that was only described, or only dry-run, counts as not done. If any of 1-4 fails, FAIL and name which.
