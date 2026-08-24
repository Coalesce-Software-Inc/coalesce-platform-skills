# Coalesce Platform Skills

A portable set of agent skills for working with the Coalesce Platform with an 
initial focus on Transform Workspace building, editing, validating, and running data transformation
pipelines with the `coa` CLI. Each skill is a directory with a `SKILL.md`
(name + description frontmatter, markdown body) following the open Agent
Skills format, so the same package works in any tool that reads it.

## Supported tools

- Claude Code (CLI, desktop, IDE extensions)
- Claude Agent SDK
- Snowflake Cortex Code
- Codex and other tools that read SKILL.md skills and AGENTS.md

Skills carry guidance only. Tool permissions, turn limits, and budgets are
enforced by whatever harness runs the agent, using its own permission model.

## What's inside

- `skills/coalesce-pipelines/` — the umbrella skill: repo layout, the core
  validate → dry-run → create → run loop, format rules, guardrails, and
  routing to the other skills. Shared reference docs live in its `reference/`
  subdirectory (coa CLI, SQL format, YAML schemas).
- Specialist skills: `coalesce-sql-transformation`,
  `coalesce-v1-yaml-nodes`, `coalesce-pipeline-structure`, `coalesce-workspace-config`,
  `coalesce-cloud-api`, `coalesce-git-publication`, `coalesce-review-risk`,
  `coalesce-transform-mcp-install`.
- Task recipes: `coalesce-create-stage-node`, `coalesce-add-column`,
  `coalesce-rename-node-cascade`, `coalesce-create-job`.
- `templates/workspace-CLAUDE.md` — the small per-workspace instruction file
  (see below).

## Installation

**Claude Code plugin (recommended).** This repo is a Claude Code plugin
marketplace. Add it once, then install the plugin:

```sh
/plugin marketplace add Coalesce-Software-Inc/coalesce-platform-skills
/plugin install coalesce-platform-skills@coalesce
```

or from the CLI:

```sh
claude plugin marketplace add Coalesce-Software-Inc/coalesce-platform-skills
claude plugin install coalesce-platform-skills@coalesce
```

The `/plugin` UI shows a "Will install" review (the skills it adds and a
context-cost estimate) before anything is added. After installing during a
session, run `/reload-plugins` to pick the skills up without restarting.

### Updating

```sh
claude plugin marketplace update coalesce
claude plugin update coalesce-platform-skills
```

Then `/reload-plugins`, or restart the session.

Don't skip the first command. `/plugin update` decides whether a newer version
exists by reading the marketplace manifest from your local clone, and Claude
Code does not reliably refresh that clone first — so on its own it can report
"already at the latest version" while a newer release exists. Uninstalling and
reinstalling also works but is never necessary, and it discards your
enable/disable state.

The plugin is pinned to a release tag, so an update moves you between released
versions rather than to whatever happens to be on the default branch. What
changed in each version is on the
[Releases](https://github.com/Coalesce-Software-Inc/coalesce-platform-skills/releases)
page.

**Standalone script.** For tools that read `~/.claude/skills/` directly (or to
install without the plugin system):

```sh
./install.sh                 # installs into ~/.claude/skills/
./install.sh /custom/path    # or a custom skills directory
```

Because it copies from your working tree, this is also how to try local changes.
The marketplace entry pins a release tag, so installing the plugin from a local
clone gets you that tag rather than your edits.

The installer never overwrites a skill you have customized: every managed
file carries an HTML comment marker, `coalesce-node-managed: true`. Remove
that line from a skill's SKILL.md and the installer will
leave the whole skill directory alone from then on. Managed `coalesce-*`
skills that are no longer part of the package are removed on install.

**Other agents (`npx skills`).** For Cursor, Codex, and the other agents that
read the open SKILL.md format, the [Vercel Labs `skills`
CLI](https://github.com/vercel-labs/skills) installs directly from this repo:

```sh
npx skills add Coalesce-Software-Inc/coalesce-platform-skills -g
```

`-g` installs into the user scope (`~/.claude/skills/` for Claude Code); omit
it to install into the current project's `./.claude/skills/`. This is a
third-party tool and does not honor the `coalesce-node-managed` marker, so
avoid combining it with `install.sh` in the same skills directory.

## Per-workspace CLAUDE.md / AGENTS.md

Skills are user-level and apply to every Coalesce repo on the machine. Each
workspace additionally gets a small `CLAUDE.md` (and an identical `AGENTS.md`
for tools that read that name) from `templates/workspace-CLAUDE.md`: it states
what the repo is and points the agent at the `coalesce-pipelines` skill. Copy
the template into the workspace yourself. It uses the same managed marker, so
user edits below a removed marker are preserved.

Dynamic workspace state (node inventory, diagnostics) is NOT in these files —
if a harness generates `.claude/workspace-context.json` per invocation, the
skills tell agents to read it when present and fall back to `coa describe`
when not.
