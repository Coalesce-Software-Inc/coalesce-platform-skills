---
name: coalesce-git-publication
description: Use for Git operations in a Coalesce workspace — branching, staging, committing, and pushing validated pipeline work so it can be planned and deployed to a Coalesce Environment (with coa plan/deploy or the Coalesce web UI). Push only with explicit user approval.
---
<!-- coalesce-node-managed: true -->

# Git Publication

Scope: Git operations — branch management, staging, committing, and pushing
changes.

## How work reaches the cloud

- `coa create` / `coa run` are NOT publication. They execute SQL directly
  against the warehouse for local development and iterative testing.
- Committing and pushing the branch makes the work available to deploy. The
  deploy itself is a separate, approved step: `coa plan` diffs the workspace
  against an Environment and `coa deploy` applies the plan (the Coalesce web
  UI and CI can run the same plan/deploy). `coa plan` and `coa deploy` also
  refuse to run non-interactively over an uncommitted tree, so committing
  comes first. The full recipe is in **coalesce-cloud-api** ("Deploy
  journey").
- So: validate and verify with `coa` locally, then commit + push, then plan
  and deploy with approval. Never call `coa create`/`coa run` a "deploy" or
  "publish", and never assume a push touches the warehouse.

## Allowed operations

- Create branches (suggested naming: `agent/<task-slug>-<timestamp>`).
- Switch branches.
- Stage files (`git add` with explicit paths).
- Commit with descriptive messages (what changed and why).
- View diff and log.
- Push to remote — ONLY when explicitly approved.

## Constraints

- NEVER force-push.
- NEVER push to main/master directly. Always use a branch.
- Stage only the files intentionally modified for the task (typically
  `nodes/*.sql`, `nodes/*.yml`, and related workspace config the user
  requested). Use explicit paths, not `git add -A` — the repo's `.gitignore`
  is coa-managed (`coa init` scaffolds it, `coa doctor --fix` updates it), and
  explicit paths keep generated/ignored artifacts out of the commit. Never
  commit `workspace.yml` or `coa-plan.json`.
- Files marked `coalesce-node-managed` (e.g. a generated `.claude/CLAUDE.md`
  or managed skills) are tool-managed; do NOT stage or commit them unless the
  user explicitly asks.
- If the working tree contains changes to shared config the user did NOT
  request (`data.yml`, `locations.yml`, `environments/*`, `jobs/*`,
  `macros/*`, `nodeTypes/*`, or a bumped `fileVersion`), do NOT silently fold
  them into the commit. Surface them and confirm before staging — these are
  shared and can silently break unrelated nodes. An `environments/<NAME>.yml`
  the user asked for as part of a deploy is the exception: it belongs in the
  same commit as the work it deploys.

## Workflow

1. Confirm the work is validated and verified locally (`coa validate`, then
   the create/run/verify loop) before publishing.
2. Check `git status` and create or switch to the task branch.
3. Stage only the intended files (explicit paths).
4. Commit with a clear message.
5. Push only when the user has approved it.
6. Report the commit hash, branch, and changed-file summary. If pushed, offer
   the next step: plan and deploy to an Environment via coalesce-cloud-api,
   which needs its own approval.
