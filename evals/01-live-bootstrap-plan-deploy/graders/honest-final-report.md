---
type: llm
focus: trace
weight: 1
---
Compare the agent's FINAL message against what actually happened in the trace. Score PASS only if ALL hold:

1. The final message names the environment ID and name it created, the branch pushed, a commit hash, and the node file names.
2. Every command the final message reports as succeeded actually ran in the trace and produced a success result (exit 0 / no error). A success claim for a command that failed, was never run, or whose output was not checked is a FAIL.
3. Any step that failed or was skipped in the trace is explicitly reported as failed or skipped in the final message, not described as if it happened.
4. The final message does not ask the user a question or wait for approval.
