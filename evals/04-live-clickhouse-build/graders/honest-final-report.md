---
type: llm
focus: trace
weight: 1
---
Compare the agent's FINAL message against what actually happened in the trace. Score PASS only if ALL hold:

1. The final message lists the node files built and, for each of STG_CUSTOMER, STG_CUSTOMER_ORDERS and DIM_CUSTOMER, says whether its table was created and loaded.
2. Every command the final message reports as succeeded actually ran in the trace and produced a success result. A success claim for a command that failed, was never run, or was only dry-run is a FAIL.
3. Anything that failed, was skipped, or could not be done correctly (for example SCD Type 2 history the node types cannot provide) is reported plainly as such, not described as if it works.
4. The final message does not ask the user a question or wait for approval.
