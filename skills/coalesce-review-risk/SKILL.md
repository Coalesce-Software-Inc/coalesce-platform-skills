---
name: coalesce-review-risk
description: Use when reviewing Coalesce pipeline changes for correctness, impact, and risk before approval — READ-ONLY analysis of diffs, coa validate/dry-run evidence, and downstream blast radius. Never edits files or runs warehouse-mutating commands.
---
<!-- coalesce-node-managed: true -->

# Review & Risk

Analyze a change so the user can decide whether to approve it. This is
read-only: never edit, stage, commit, or run `coa create` / `coa run` without
`--dry-run`. Use `coa` output as evidence and do not minimize risk.

References: [coa-cli](../coalesce-pipelines/reference/coa-cli.md) for
selectors, [sql-format](../coalesce-pipelines/reference/sql-format.md) for the
rules being checked.

## Checklist

1. Read the diff (`git diff`, `git diff --staged`). List the nodes added,
   modified, deleted, and renamed.
2. For each modified node, read the changed SQL against the upstream nodes it
   reads from. Check that join keys pair the columns that actually relate the
   two tables, and that filters, aggregations, and column mappings still mean
   what the node's name and neighbors say they should. A change can be valid
   SQL and still wrong.
3. Run `coa validate -d <dir> --json` and report every error and warning. The
   JSON is nested: `data.validation.results[]` (`{ file, status, errors:
   [{ path, message }] }`) and `data.validation.summary`. Quote the failing
   file, path, and message.
4. Run `coa create -d <dir> --dry-run --json` and `coa run -d <dir> --dry-run
   --json`. Report template failures: empty SQL, comment-only output, missing
   DDL.
5. Blast radius: enumerate `{ NODE }+` for each touched node (`+{ NODE }` is
   upstream; do not reverse them).
6. Check which jobs (`includeSelector` / `excludeSelector`) and subgraphs
   (`steps`) pick up the change.

## Risks to flag

- A `.sql` node whose `@nodeType` is not a `fileVersion: 2` type: columns are
  silently empty.
- A hand-authored `.yml` node with empty or partial `operation.config`: it
  passes validate and the create dry-run but renders zero run SQL.
- Deleted or renamed nodes that still have dependents or stale `ref()`s.
- One-argument `ref()`, hardcoded `db.schema.table`, or column annotations that
  are neither native (`@isBusinessKey`, `@isChangeTracking`, `@id`,
  `@description`) nor declared by the node type.
- Edits to shared config: `nodeTypes/`, locations, workspace, environments,
  jobs, macros, `data.yml`, `fileVersion` bumps, template swaps. A new
  `nodeTypes/` folder counts; ask whether the user requested a custom type.

## Report

State a verdict, then the findings with the specific file, column, and `coa`
output behind each. Say plainly when the analysis is incomplete (validate
could not run, selectors unscoped).
