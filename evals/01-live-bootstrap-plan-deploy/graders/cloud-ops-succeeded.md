---
type: llm
focus: trace
weight: 1
---
Examine the coa cloud operations in the trace. Score PASS only if ALL hold:

1. A `coa environments create` command completed successfully and returned a new environment ID. Its name starts with eval-bootstrap-, it belongs to the cloud project the prompt names, and its mappings put SRC on the source database and schema the prompt gives and TARGET on the target database and schema the prompt gives.
2. A `coa plan` command against THAT new environment ID completed successfully (exit code 0, no "✖" failure line, and a plan output file such as coa-plan.json was produced or referenced).
3. A `coa deploy` command against the same environment ID ran AFTER that plan and consumed it (no deploy without a preceding successful plan), and completed successfully (exit 0, no "✖", no error JSON).
4. A `coa refresh` command against the same environment ID ran AFTER the deploy and completed successfully.
5. Before the cloud operations, the staging table was built and loaded locally: a `coa create` and a `coa run` (not dry-run) completed successfully.
6. No plan, deploy, or refresh was run against any environment other than the one created in this session.

A command that errored, timed out, or was only described but never executed counts as not done. If any of 1-6 is missing or failed, FAIL and name which.
