---
name: coalesce-git-publication
description: Use for Git operations in a Coalesce workspace — branching, staging, committing, and pushing validated pipeline work so it can be planned and deployed from the Coalesce cloud. Push only when the user asked for it or approved it.
---

<!-- coalesce-node-managed: true -->

# Git Publication

Committing and pushing a branch is how work reaches the Coalesce cloud; plan and deploy are a separate step (coalesce-deploy). `coa create` and `coa run` publish nothing, and a push does not touch the warehouse.

## Workflow

1. Confirm the work is validated (`coa validate`, both dry-runs).
2. `git status`, then create or switch to a task branch. Suggested name: `agent/<task-slug>-<timestamp>`. Never commit to or push `main`/`master` directly.
3. Stage the intended files by explicit path, not `git add -A`. Work the user already staged stays staged.
4. Commit with a message that says what changed and why.
5. Push only when the user asked for it or has approved it. If the request did not mention pushing, stop after the commit, tell the user the branch and remote, and ask.
6. Report the commit hash, branch, and changed files, and whether the push happened or is waiting on their confirmation. After a push, the next step is plan/deploy, only if the user asks for it.

## Constraints

- Never force-push.
- Do not stage files marked `coalesce-node-managed` (a generated `.claude/CLAUDE.md`, managed skills) unless the user asks.
- If the working tree has shared-config changes the user did not request (`data.yml`, `locations.yml`, `workspace.yml`, `jobs/`, `macros/`, `nodeTypes/`, a bumped `fileVersion`), do not fold them into the commit. Point them out and ask.
- The `.gitignore` is coa-managed (`coa init` scaffolds it, `coa doctor --fix` updates it). Explicit paths keep generated artifacts out of the commit.
