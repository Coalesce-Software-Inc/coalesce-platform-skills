---
name: coalesce-reflect
description: Use at the end of a Coalesce session, or when the user asks to reflect, do a retro, capture lessons, or send feedback on the coalesce-* skills. Reviews what went wrong or was slow, maps each lesson to the skill that should have prevented it, and — only with explicit approval — opens a pull request against the public skills repo (through a fork when the user cannot push to it).
---
<!-- coalesce-node-managed: true -->

# Reflect and Send Skill Feedback

Scope: turning what happened in this session into small, reviewed edits to the
coalesce-* skills, and delivering them as a pull request to
`Coalesce-Software-Inc/coalesce-platform-skills`.

This skill never edits the installed skills in place. Installed copies are a
pinned release (the plugin cache or `~/.claude/skills/`) and are overwritten on
the next update. All edits happen in a fresh clone of the repository.

## Two approval gates

Nothing leaves the machine without the user saying yes. There are exactly two
stops, and neither may be skipped or assumed from earlier approval in the
session (for example an approval to push the workspace does NOT cover this):

1. **Pick the lessons.** Show the lesson list; the user chooses which to keep.
2. **Publish.** Show the account the fork goes to (or the branch on the main
   repo), the full diff, and the PR title and body. Wait for an explicit yes
   before forking, pushing, or opening the PR.

If the user declines at either gate, stop. Offer to save the lessons or the
patch to a local file instead.

## Step 1: Find the lessons

Review the whole session, not just the last task. Look for:

- **User corrections.** The user said "no", "that's wrong", "use X instead", or
  undid something.
- **Failed then fixed.** A `coa` command, flag, file format, or selector that
  errored and was retried in a different way. Capture the exact error text.
- **Wrong or stale guidance.** A skill said something that turned out to be
  false, out of date, or missing a case that came up.
- **Routing misses.** The right skill was not loaded, or a skill loaded for a
  task it does not cover.
- **Near-misses on guardrails.** Something risky almost happened (shared config
  edit, push without approval, warehouse mutation) and a skill could have
  warned earlier.
- **Wasted effort.** Long searches or repeated trial and error that one
  sentence of guidance would have avoided.

Drop anything that is:

- A one-off slip the skills already cover clearly. Keep it only if the
  guidance exists but is buried or easy to miss, and say so.
- Specific to this workspace (its node names, locations, conventions). That
  belongs in the workspace's own `CLAUDE.md` / `AGENTS.md`; offer to add it
  there instead.
- A limitation of the model or harness that no skill text can fix.

For each remaining lesson, write:

- **What happened**: one or two sentences, with the command and error verbatim.
- **Skill**: the `coalesce-*` skill (and section) that should have prevented
  it, or "new skill" if none fits.
- **Proposed change**: the smallest edit that would have prevented it. Prefer
  sharpening an existing rule over adding a new section.
- **How to test**: a one-line eval idea (a prompt and what a pass looks like).

If nothing survives the filter, say so and stop. An empty retro is a fine
outcome; do not invent lessons.

## Step 2: Scrub for the public repo

The repository is public. Before showing the lessons, remove or generalize:

- Account names, Coalesce domains, project and environment IDs, warehouse
  account identifiers, user names, email addresses.
- Database, schema, table, and column names from the user's data. Replace them
  with TPC-H names (`ORDERS`, `CUSTOMER`, `NATION`) or placeholders like
  `<SOURCE_DB>`.
- Tokens, keys, connection strings, file paths under the home directory, and
  the user's own SQL beyond the minimum needed to show the problem.

Show the scrubbed text at gate 1 so the user sees exactly what would be
published. When you say what was removed, name the kind of value ("the
Snowflake account, the source database and table"), never the value itself.
Repeating a removed name in the summary puts it back in text that may be
copied into the PR.

## Gate 1: Choose the lessons

Present the numbered lessons (scrubbed) and ask which to include. Accept "all",
"none", or a subset. Stop on "none".

## Step 3: Prepare the change

Requires `git` and the GitHub CLI (`gh`). Check `gh auth status`. If `gh` is
missing or not logged in, skip to **No GitHub CLI** below.

```sh
REPO=Coalesce-Software-Inc/coalesce-platform-skills
ME=$(gh api user --jq .login)
CAN_PUSH=$(gh api "repos/$REPO" --jq .permissions.push)
WORK=$(mktemp -d)/coalesce-platform-skills
gh repo clone "$REPO" "$WORK" -- --branch develop --single-branch
cd "$WORK"
git switch -c "skill-feedback/<short-slug>-$(date +%Y%m%d)"
```

- Clone into a temporary directory, never inside the user's Coalesce
  workspace, so its Git history stays untouched.
- `develop` is the base branch. The installed skills may be older than
  `develop`: read each target `skills/<name>/SKILL.md` in the clone first, and
  drop or adjust any lesson that `develop` already covers.
- Edit only `skills/*/SKILL.md` and files under `skills/*/reference/`. Keep the
  frontmatter and the `coalesce-node-managed` marker line intact. Match the
  surrounding style: short rules, the reason behind them, exact commands.
- Do not bump versions in `.claude-plugin/`; the release workflow does that.
- If `claude` is on the PATH, run `claude plugin validate . --strict` and fix
  anything it reports.
- Commit with explicit paths (`git add skills/<name>/SKILL.md`), never
  `git add -A`. Message: `Skill feedback: <one-line summary>`.

Decide where the branch goes, but do not act on it yet:

- `CAN_PUSH` is `true`: push the branch to the main repository. No fork.
- Otherwise: push to the user's fork (`$ME/coalesce-platform-skills`),
  creating it if needed.

## Gate 2: Confirm publishing

Show, in one message:

- Where it goes: "a new fork in your GitHub account `<ME>`", "your existing
  fork `<ME>/coalesce-platform-skills`", or "a branch on
  `Coalesce-Software-Inc/coalesce-platform-skills`".
- The branch name and the output of `git show --stat HEAD` plus the full diff.
- The PR title and body (template below).

Ask: "Create the fork (if needed), push this branch, and open the PR?" Proceed
only on an explicit yes. Anything else, including silence or a question, is
not a yes.

## Step 4: Publish

With push access:

```sh
git push -u origin HEAD
gh pr create --repo "$REPO" --base develop --title "<title>" --body-file <body.md>
```

Without push access:

```sh
# Creates the fork if missing, reuses it if present, and adds it as remote
# "fork" while "origin" stays pointed at the main repository.
gh repo fork "$REPO" --default-branch-only --remote --remote-name fork
git push -u fork HEAD
gh pr create --repo "$REPO" --base develop --head "$ME:$(git branch --show-current)" \
  --title "<title>" --body-file <body.md>
```

- NEVER force-push. NEVER push to `develop` or `main`.
- If the fork was just created, GitHub may need a few seconds before the push
  succeeds; retry the push once after a short wait.
- If the organization blocks forking or the push is rejected, stop and report
  the exact error. Fall back to **No GitHub CLI**.

Report the PR URL, the branch, and the fork (if one was used). Mention that the
temporary clone at `$WORK` can be deleted.

## PR body template

```markdown
## Summary
<one or two sentences: what kept going wrong and what the change does>

## Lessons
### 1. <short title>
- **What happened:** <scrubbed description, command and error verbatim>
- **Skill:** `<coalesce-skill>` (<section>)
- **Change:** <what the edit says now>
- **Suggested eval:** <prompt and pass condition>

## Context
- Plugin version in use: <version, if known>
- Filed with the `coalesce-reflect` skill.
```

## No GitHub CLI

When `gh` is unavailable, not logged in, or publishing fails:

1. Make the edits and the commit in the clone as above (a plain
   `git clone https://github.com/Coalesce-Software-Inc/coalesce-platform-skills.git`
   works without `gh`).
2. Run `git format-patch -1 HEAD -o <dir>` and give the user the patch path.
3. Point them to
   `https://github.com/Coalesce-Software-Inc/coalesce-platform-skills/issues/new`
   and offer the PR body text to paste, with the patch attached.
