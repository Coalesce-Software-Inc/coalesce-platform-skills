---
name: coalesce-reconciliation-authoring
description: Use when two datasets in different databases should agree and you need to find out where and why they don't, but there is no reconciliation suite yet - or the suite you have cannot answer the next question. Also use the moment you are about to hand-write SELECT, COUNT, SUM or GROUP BY queries against a source and a target to compare them - write a reconciliation instead. Explains how to author synq-recon suite YAML, one reconciliation per question, grown as the investigation narrows and kept afterwards as the regression suite. Pairs with the `coalesce-reconciliation-cli` skill, which runs, drills and reads the suite. Triggers on "the numbers look wrong", "the warehouse doesn't match", "what did the pipeline break", "write a suite", "add a reconciliation", suite.yaml.
---
<!-- coalesce-node-managed: true -->

# Authoring reconciliations

When two datasets should agree and don't, **do not query your way to the
answer.** Write each question down as a reconciliation in a suite file and let
`synq-recon` answer it. The suite you end up with *is* the investigation. Once
it is green, it is also the proof of the fix and the check that catches the
next regression.

Connections are given. `.connections.yaml` in the working directory defines
them by name, and the CLI finds it on its own. You refer to a connection by
that name. You never write credentials, and you never edit that file.

This skill is about **writing** the suite. The `coalesce-reconciliation-cli` skill covers
**running** it: the check → drill loop, reading `mismatch_types`, the bug-class
signatures, the investigation queries. Load both.

## Why a reconciliation beats a query

| You were about to write | Write this instead | Why |
|---|---|---|
| `SELECT COUNT(*)` on each side | a `row_checksum` reconciliation | Same two queries, but it also catches *changed values*. Equal counts are the most common false all-clear. |
| `SELECT *` from both sides, then diff | `run-drill` on that reconciliation | Localises in O(log n) round trips. Only counts and checksums leave the database, so no rows land in your context. |
| `GROUP BY day` on both sides, compared by eye | an `aggregate` reconciliation | Compared group by group against a threshold, and drilled down the hierarchy for you. |
| Casts to line up `DECIMAL`/`NUMERIC`, `DATETIME`/`TIMESTAMP` | nothing | The tool negotiates a hash both engines can compute and aligns types first. Hand comparisons across engines manufacture false differences. |
| A one-off query in your scrollback | a named entry in `suite.yaml` | Re-runnable after the fix, so the query that found the problem is the one that proves it gone. |

Detection is 2 queries per reconciliation, and each drill level adds 2 more.
The output is the same size whether the table holds a thousand rows or a
billion.

### When SQL is still the right tool

- **Rows of a localised difference.** Run the `investigation_queries` a drill
  hands back, narrowed further and with a `LIMIT`. This is the one point where
  row values enter the picture: a hundred rows, on your terms.
- **Schema facts** that the pipeline code, the DDL and `check-config --db`
  don't give you.
- **Migrations** you have been asked to write.

Never to count, sum, group or compare the two sides. If you catch yourself
about to, write the reconciliation.

## The workflow: grow the suite

```
 1. inventory    what is copied, from where, how          read code + DDL, no queries
 2. baseline     one row_checksum per table                every shared column
 3. validate     check-config → plan → check-config --db   free / planner only
 4. detect       run-check                                 `coalesce-reconciliation-cli` skill
 5. localise     run-drill                                 `coalesce-reconciliation-cli` skill
 6. next question → add a narrower reconciliation          patterns below
    └── back to 3, for the new one only: --include <name>
 7. fix the cause, re-run the pipeline
 8. prove it     run-check on the WHOLE suite              every entry MATCH
```

### 1. Inventory

Read the pipeline before touching a database. List every table it writes: the
source it reads, how it loads (truncate-and-reload, append, merge), and any
filter or transformation on the way. Then read both DDLs for each pair:

- the **primary key**: this becomes `key_columns`
- columns that exist **on one side only**, such as load timestamps, batch ids
  and surrogate keys: these become `exclude_columns`
- **width and type differences** (`VARCHAR(255)` → `VARCHAR(64)`,
  `DECIMAL(12,2)` → `NUMERIC(10,0)`): each one is already a hypothesis

### 2. Baseline

One `row_checksum` reconciliation for each table the pipeline loads, named
after the table, comparing **every column both sides share**.

```yaml
# yaml-language-server: $schema=https://schemas.synq.io/synq-recon/v1/config.schema.json
name: billing-warehouse
title: Billing (app) vs warehouse
description: The warehouse copy of the billing database, held against its source.

reconciliations:
  invoices:
    title: Invoices
    description: Every invoice, every column. Missing, extra or changed rows all show here.
    source:
      connection: app               # a name from .connections.yaml
      table: billing.invoices       # as that database spells it in SQL
    target:
      connection: dw
      table: finance.invoices
      exclude_columns: [_etl_loaded_at]   # target-only bookkeeping, by design
    key_columns: [invoice_id]       # unique and indexed on both sides
    mode: row_checksum
    bisection:
      factor: 10
      threshold: 500
```

This is the net. At 2 queries a table it is cheap, and it catches lost rows,
duplicated rows and rewritten values alike. Don't trust anything narrower until
the baseline has run. **Exclude a column only because it exists on one side by
design, never because it differs.**

### 6. Ask the next question as a new reconciliation

Every finding raises a question. Answer it by *adding* a reconciliation next to
the baseline, not with SQL and not by editing the baseline.

| The question | The reconciliation that answers it |
|---|---|
| **Which column** changed? | Same table, with `columns:` narrowed to the key plus one column (or one related group) on both sides. Write one per group; the ones that mismatch name the culprits. |
| Rows missing **and** values changed in the same table? | Separate them first. A column split only attributes changes where row counts agree, because a missing row makes *every* column split mismatch. Add a `where:` scoped to the range the drill returned, then split columns inside it. |
| **Two causes** in one range? | Scope with `where:`, then split by column. Two column groups mismatching in the same range means two separate causes that happen to share a date. |
| Did it **start at a point** in time? | Two `where:`-scoped copies either side of the date: a deploy date in the code, or where the drill's top-of-range block begins. Green before and red after means a regression. |
| **How much**, and in which business slice? | `aggregate` with `SUM` and `COUNT` on the same column, grouped by a meaningful hierarchy (day > currency, region > product). Equal count with a different sum means values changed; a different count means rows are missing or extra. |
| A **categorical value** rewritten? | `aggregate` with `COUNT` of the key, grouped by that column. A money total can't see it. |
| **Duplicates**? | The baseline catches them: the target count is higher. Drill to find the range, and read the multiple. |
| Most rows differ and the drill runs forever | Stop drilling. Localise with an `aggregate` grouped by a natural partition, then add a `where:`-narrowed row reconciliation for just the groups that diverged. |

A column split, scoped to the range where rows exist on both sides:

```yaml
  invoices-recent-amounts:
    title: Recent invoices - amount columns only
    description: >-
      Splits the recent checksum block by column. A mismatch here means
      amounts were changed on load; the sibling split covers status.
    source:
      connection: app
      table: billing.invoices
      columns: [invoice_id, currency, amount_due]
      where: "issued_at >= '2026-03-01'"
    target:
      connection: dw
      table: finance.invoices
      columns: [invoice_id, currency, amount_due]
      where: "issued_at >= '2026-03-01'"
    key_columns: [invoice_id]
    mode: row_checksum
```

An aggregate in business terms. Derived group columns need a `query:`, written
in each side's own dialect:

```yaml
  revenue-by-day:
    title: Invoiced amount by day and currency
    description: SUM beside COUNT - a missing invoice and a changed amount look different.
    source:
      connection: app
      query: |
        SELECT DATE(issued_at) AS issued_day, currency, amount_due, invoice_id
        FROM billing.invoices
    target:
      connection: dw
      query: |
        SELECT issued_at::date AS issued_day, currency, amount_due, invoice_id
        FROM finance.invoices
    key_columns: [invoice_id]       # the indexed row identity, NOT the group column
    mode: aggregate
    aggregate:
      measures:
        - column: amount_due
          function: [SUM, COUNT]
      group_columns: [issued_day, currency]   # outermost first
      thresholds:
        absolute: 0.01              # exact to the cent; no percentage, see reference
```

### 8. Prove it, and keep what you wrote

Re-run the pipeline, then run `run-check` on the **whole** suite. You are done
when every reconciliation reports MATCH: the baseline and every narrower one
you added.

Don't delete the narrower ones once they are green. Each is a regression check
for the exact failure it found. Give every reconciliation a `description` that
says what a mismatch would mean, so whoever reads the next failure knows what
broke.

## Validate every edit before running it

| Step | Command | Cost |
|---|---|---|
| Parse, required fields, time-dependent SQL | `synq-recon check-config suite.yaml` | none |
| Read the exact SQL each side will run | `synq-recon plan suite.yaml --include <name>` | none |
| Both sides resolve, same column count, key indexed | `synq-recon check-config suite.yaml --db` | planner only |
| Detect, for the new entry only | `synq-recon run-check suite.yaml --include <name> --no-report -o json 2>/dev/null` | 2 queries |

When `check-config --db` complains, fix the suite before you run it:

- **`source has N columns but target has M`**: `row_checksum` compares
  positionally. Name the same `columns:` in the same order on both sides, or
  `exclude_columns` the one-side-only extras.
- **`key_column(s) not backed by an index`**: every drill level range-filters
  on the key, so an unindexed key full-scans every segment. Pick the indexed
  row identity. In `aggregate` mode that is still the row key, not the group
  column.

## Rules

- **Never weaken a reconciliation that is already in the suite.** Don't loosen
  its threshold, drop a column, or add or narrow a `where:` to turn it green.
  Narrow the question by *adding* a reconciliation beside it.
- **Never exclude a column because it differs.** Exclusions are for columns
  that exist on one side by design.
- **Never use `NOW()` or `CURRENT_DATE`** in a `where:` or `query:`. The two
  sides evaluate them at different instants. Use a literal date or a
  `variables:` entry.
- **Never concatenate a key** (`a || '-' || b`). List the columns:
  `key_columns: [a, b]`.
- **Never raise `reporting.level`** to get row values. Use the investigation
  queries a drill returns.
- **Never put credentials in the suite**, and never edit `.connections.yaml`.

## More

- `reference/suite-yaml.md`: every field, with worked examples for each mode,
  `table` vs `query`, `where:` across dialects, `column_mapping`, `variables:`,
  `cutoff:`, bisection sizing, and naming.
- The `coalesce-reconciliation-cli` skill: running the suite, drilling, reading results.
- Official guidance: https://docs.synq.io/reconciliation/agent-workflow
