---
name: coalesce-review-risk
description: Use when reviewing Coalesce pipeline changes for correctness, impact, and risk before approval — READ-ONLY analysis of diffs, coa validate/dry-run evidence, and downstream blast radius. Never edits files or runs warehouse-mutating commands.
---

<!-- coalesce-node-managed: true -->

# Review & Risk

Analyze a change so the user can decide whether to approve it. This is read-only: never edit, stage, commit, or run `coa create` / `coa run` without `--dry-run`. Use `coa` output as evidence and do not minimize risk.

References: [coa-cli](../coalesce-pipelines/reference/coa-cli.md) for selectors, [sql-format](../coalesce-pipelines/reference/sql-format.md) for the rules being checked.

## Checklist

1. Read the diff (`git diff`, `git diff --staged`). List the nodes added, modified, deleted, and renamed.
2. For each modified node, read the changed SQL against the upstream nodes it reads from. Check that join keys pair the columns that actually relate the two tables, and that filters, aggregations, and column mappings still mean what the node's name and neighbors say they should. A change can be valid SQL and still wrong.
3. Run `coa validate -d <dir> --json` and report every error and warning. The JSON is nested: `data.validation.results[]` (`{ file, status, errors: [{ path, message }] }`) and `data.validation.summary`. Quote the failing file, path, and message.
4. Run `coa create -d <dir> --dry-run --json` and `coa run -d <dir> --dry-run --json`. Report template failures: empty SQL, comment-only output, missing DDL.
5. Blast radius: enumerate `{ NODE }+` for each touched node (`+{ NODE }` is upstream; do not reverse them).
6. Check which jobs (`includeSelector` / `excludeSelector`) and subgraphs (`steps`) pick up the change.

## Risks to flag

- A `.sql` node whose `@nodeType` is not a `fileVersion: 2` type: columns are silently empty.
- A hand-authored `.yml` node with empty or partial `operation.config`: it passes validate and the create dry-run but renders zero run SQL.
- Deleted or renamed nodes that still have dependents or stale `ref()`s.
- One-argument `ref()`, hardcoded `db.schema.table`, or column annotations that are neither reserved (`@description`, `@notNull`, `@defaultValue`) nor used by the node type's templates or declared by it. A column `@id` on a type that does not require one re-keys the column.
- A node or column change that `coa create` would apply to a table that already holds data: create replaces the table empty.
- On ClickHouse (`platformKind: tdbc-clickhouse`; rules in the [ClickHouse reference](../coalesce-pipelines/reference/platforms/clickhouse.md)):
  - an SCD2, history, or upsert node built on a built-in type (it appends a full copy every run), or SQL that uses `MERGE`;
  - source columns or `ref()` names whose case differs from the upstream file, and Snowflake-only functions (`IFF` and the like); both pass validate and dry-run;
  - a `LEFT JOIN` whose unmatched columns are used as if NULL (ClickHouse gives `0` / `''` by default);
  - a Nullable column in `orderBy` or `partitionBy` on a built-in type;
  - a changed sort key, partition, primary key, or key column on a deployed table (recreated empty, history lost);
  - `@writeMode("truncateInsert")` on an SCD2 Dimension.
- Edits to shared config: `nodeTypes/`, locations, workspace, environments, jobs, macros, `data.yml`, `fileVersion` bumps, template swaps. A new `nodeTypes/` folder counts; ask whether the user requested a custom type.
- Any change under `apps/`: this is code, not config. A workspace app runs with the user's permissions as soon as anyone opens it in Coalesce. Read the changed files and flag network calls to outside hosts, writes outside the app's data folder, `exec` or `shell: true`, `innerHTML` with workspace values, reads of `~/.coa/config` or other credentials, committed secrets, CORS headers, and a removed `Host` or write check. Rules: [coalesce-create-app](../coalesce-create-app/SKILL.md).

## Report

State a verdict, then the findings with the specific file, column, and `coa` output behind each. Say plainly when the analysis is incomplete (validate could not run, selectors unscoped).
