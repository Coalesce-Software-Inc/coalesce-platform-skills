# Suite YAML reference

Everything needed to write a suite by hand. Examples use a made-up billing
database (`app`, MySQL) copied into a warehouse (`dw`, Postgres). Swap in the
connection names from your own `.connections.yaml`.

## Skeleton

```yaml
# yaml-language-server: $schema=https://schemas.synq.io/synq-recon/v1/config.schema.json
name: billing-warehouse            # machine name, kebab-case
title: Billing (app) vs warehouse
description: >-
  What this suite proves, in a sentence someone else can act on.

variables:                         # optional; {{ name }} in where/query
  since: "2026-03-01"

reconciliations:
  <id>:                            # kebab-case; what --include takes
    title: ...
    description: ...               # what a MISMATCH here would mean
    source: { ... }                # a side
    target: { ... }                # a side
    key_columns: [...]
    mode: row_checksum | row_count | aggregate
    bisection: { ... }             # row modes
    aggregate: { ... }             # aggregate mode
```

No `connections:` block. They come from `.connections.yaml`, discovered from
the working directory, so the suite carries no credentials and can be shared
or uploaded as is.

## A side: `source` / `target`

| Field | Use |
|---|---|
| `connection` | A name defined in `.connections.yaml`. Required. |
| `table` | The table as that database spells it in SQL: MySQL `db.table`, Postgres `schema.table`, Snowflake `DB.SCHEMA.TABLE`. Prefer this to `query`, because the tool can introspect columns, keys and indexes. |
| `query` | Free SQL in that side's dialect, for derived columns (`DATE(ts)` vs `ts::date`), joins, or a subset of rows you can't express as a `where`. Both sides must return the same column names. No trailing `;`. |
| `columns` | Compare only these columns, in this order. The key must be among them. |
| `exclude_columns` | Compare everything except these. For columns that exist on one side by design. |
| `where` | A predicate added to the side's query, in that side's dialect. Plain literals (`'2026-03-01'`, `42`) are portable between most engines; functions often are not. |

A side takes either `table` or `query`, not both. `columns`,
`exclude_columns` and `where` go with `table`.

### Positional comparison

`row_checksum` hashes each row's columns **in order**, so both sides must
present the same number of columns in the same order. With `table:` alone and
no `columns:`, that is the tables' own column order.

- Tables whose order or set differs: list `columns:` explicitly on both sides.
- A target-only column: `exclude_columns: [_loaded_at]` on the target.
- A column that was **renamed**: `column_mapping: {source_name: target_name}`
  at the reconciliation level.

`check-config --db` prints each side's resolved column count. Two different
numbers means fix the suite before you run it.

## `key_columns`

The row identity. Each drill level range-filters on it, so it must be:

- **unique**, or the drill cannot split cleanly
- **indexed** on both sides, or every segment is a full scan
  (`check-config --db` warns)
- a **list**, never a concatenation: `key_columns: [tenant_id, invoice_id]`

In `aggregate` mode `key_columns` is still the indexed row identity. The
grouping is set by `group_columns`. Setting the key to the group column
triggers the unindexed-key warning and full-scans every segment.

## Modes

| Mode | Compares | Catches | Reach for it when |
|---|---|---|---|
| `row_checksum` | count + checksum of every compared column, per key range | missing, extra and changed rows | the default; differences are expected to be rare |
| `row_count` | count per key range | missing and extra rows only | a presence-only check, or a quick multiplicity check on a table with no reliable column set |
| `aggregate` | measures per group | totals and counts per business slice | differences are widespread, or you need the answer in business terms |

`full` is a legacy spelling of `row_checksum`.

## `bisection` (row modes)

```yaml
bisection:
  factor: 10         # segments per level (max 1024)
  threshold: 500     # stop splitting below this many rows
  strategy: quantile # quantile | hash | time | auto
```

- **`threshold` is the leaf size you're willing to read rows for.** A damaged
  contiguous block of N rows comes back as roughly N / threshold leaves. With
  1,100 affected rows, `threshold: 100` returns about a hundred leaves and
  `500` returns about a dozen. Keep it small for a few scattered rows and
  raise it for a block.
- **`factor`**: about 10 for tables up to a few million rows, 32 or more
  beyond. Each level costs 2 queries whatever the factor.
- **`strategy: time`**, with `time_column` and `time_granularity` (`hour` …
  `year`), splits by time instead of key quantiles. Use it when the key is
  not ordered by time but a timestamp is indexed.

Defaults are `factor: 32`, `threshold: 16384`, sized for large tables. For
anything under a few million rows, set them explicitly.

## `aggregate`

```yaml
mode: aggregate
key_columns: [invoice_id]            # indexed row identity
aggregate:
  measures:
    - column: amount_due
      function: [SUM, COUNT]         # SUM, COUNT, AVG, MIN, MAX
  group_columns: [issued_day, currency]   # a hierarchy, outermost first
  thresholds:
    absolute: 0.01
```

- **Always pair `SUM` with `COUNT`** on the same column. On its own a short
  `SUM` can't tell a missing row from a changed value. Side by side they are
  unambiguous, and the count costs nothing extra.
- **To count a categorical column**: measure `COUNT` of the key, and group by
  the category.
- **`group_columns` is a drill hierarchy.** Differences at day level drill
  into currency within that day. Put the coarse, meaningful partition first.
- **Group columns that don't exist in the table** (a date from a timestamp, a
  bucket) need a `query:` side, one per dialect:

```yaml
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
```

### Thresholds

```yaml
thresholds:
  absolute: 0.01            # |source - target| allowed per group
  percentage: 0.001         # or relative, 0.1%
  percentage_mode: source   # source | target | symmetric
  per_measure:
    "COUNT(amount_due)": { absolute: 0 }
  per_column:
    amount_due: { absolute: 0.01 }
```

A group passes if it is within **either** limit. On a six-figure daily total,
a percentage tolerance swallows a rounding error of several units, so use
`absolute` alone for money unless there is a real reason (FX conversion, float
columns) to tolerate drift. If you do, say so in the `description`.
Resolution runs from most specific to least:
`per_column[c].per_measure[m]` → `per_measure[m]` → `per_column[c]` →
`thresholds`.

## `variables`

```yaml
variables:
  since: "2026-03-01"

reconciliations:
  invoices-since:
    source: { connection: app, table: billing.invoices, where: "issued_at >= '{{ since }}'" }
    target: { connection: dw,  table: finance.invoices, where: "issued_at >= '{{ since }}'",
              exclude_columns: [_etl_loaded_at] }
    key_columns: [invoice_id]
    mode: row_checksum
```

Resolved once per run into both sides. Override at run time without editing
the file: `--var since=2026-01-01`. `plan` prints the resolved SQL. This is
how you parameterise a window; never with `NOW()`.

## `cutoff` (live or lagging targets)

```yaml
cutoff:
  column: updated_at
  truncate: hour
  offset: "-30m"
  combine: min        # min | max | source | target
```

Compares both sides only up to a common watermark, so rows still in flight
don't read as missing. Required whenever the source is being written to while
the target catches up. A snapshot copy with a static source doesn't need it.

## `reporting`

Leave it at the default, `count_only`. `with_keys` and `detailed` put key
values or row values into the run record, and `detailed` also requires
`consent_acknowledged: true`. To see rows, run the drill's
`investigation_queries` instead.

## Naming and descriptions

| Reconciliation | Name | Description says |
|---|---|---|
| Baseline, one per table | `invoices` | "Every invoice, every column." |
| Column split | `invoices-amounts`, `invoices-status` | which columns, and what a mismatch there means |
| Range or time scoped | `invoices-since-2026-03-01` | the boundary, and why it is there |
| Business aggregate | `revenue-by-day`, `invoices-by-status` | the question it answers in business terms |

Someone reading a failing run should know what broke from the name and
description alone.

## Checklist before `run-check`

- [ ] every `connection:` is a name in `.connections.yaml`
- [ ] `key_columns` unique and indexed; in aggregate mode, the row key
- [ ] both sides present the same columns, in the same order
- [ ] `exclude_columns` lists only one-side-by-design columns
- [ ] no `NOW()` / `CURRENT_DATE`; windows use literals or `variables:`
- [ ] `bisection` sized for the table
- [ ] money thresholds are `absolute`
- [ ] `check-config` and `check-config --db` both pass
