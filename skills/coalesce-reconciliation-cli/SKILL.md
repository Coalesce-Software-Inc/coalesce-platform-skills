---
name: coalesce-reconciliation-cli
description: Use when two datasets in different databases should agree but might not - validating a migration, checking a replica or CDC stream for drift, verifying an ETL or pipeline copied data correctly, or investigating a reported mismatch between an operational database and a warehouse. Drives the synq-recon CLI to detect, localise, diagnose and fix the difference at its root cause in the pipeline. Triggers on reconciliation, synq-recon, recon suite, data drift, replication lag, row checksum, bisection drill-down, "do these two tables match", "did the migration lose anything".
---
<!-- coalesce-node-managed: true -->

# Reconciliation

Prove two datasets agree across databases — and when they don't, find out
where, work out why, fix the cause, and prove the fix.

Only counts and checksums leave the database by default. No row values.

**No suite yet, or the one you have can't answer the next question?** Load
the `coalesce-reconciliation-authoring` skill. It covers writing the suite YAML: a
baseline per table, then one narrower reconciliation per question, instead of
hand-querying the two sides. This skill covers running what you wrote.

## The loop

Each step is more expensive than the one before it. Do not skip ahead.

```
 1. check-config          parse the suite            free, no DB
 2. plan                  read the SQL it will run   free, no DB
 3. check-config --db     validate against the DBs   planner only, no scan
 4. run-check             detect                     2 queries per recon
 5. run-drill             localise                   2 queries per level
 6. diagnose              read the pipeline code     free
 7. fix the cause         edit code / schema         free
 8. re-run 4              prove it                   2 queries per recon
    └── not green? back to 5, with what you learned
```

Stop when `run-check` reports every reconciliation `MATCH`. **That is the only
success condition.** Not "the diff looks right", not "the fix should work".

### Always pass `-o json` when parsing

`-o` defaults to `toon` when an AI-agent environment marker is present, so you
will *not* get JSON unless you ask. And logs go to stderr:

```bash
synq-recon run-check suite.yaml --no-report -o json 2>/dev/null
```

Use `2>/dev/null`, **never `2>&1`** — merging stderr into stdout makes the JSON
unparseable. `run --auto-drill -o json` emits *several* documents, so for
parsing run the two stages separately: `run-check -o json`, then
`run-drill -o json`.

Exit code `1` means "differences found". That is a result, not a failure.

## Reading a difference

`run-drill` returns mismatch leaves. **Read `mismatch_types`, not the count
direction** — a target with one row more can still be missing a live row and
carrying two orphans.

| `mismatch_types`      | Means                                    |
|-----------------------|------------------------------------------|
| `MISSING_IN_TARGET`   | Rows on source, none on target — a gap   |
| `MISSING_IN_SOURCE`   | Rows on target, none on source — orphans |
| `COUNT_MISMATCH`      | Both have rows, different numbers        |
| `DATA_MISMATCH`       | Same rows, checksums differ — a value changed |

### Signatures worth recognising

The *shape* of a finding usually names the bug class before you read any code:

| What you see | Almost always |
|---|---|
| Counts equal, checksums differ | A value was transformed on the way in: truncation, rounding, a bad enum mapping, a timezone shift. Row counts alone would pass this. |
| Target is an exact multiple of source, checksum scales with it | A batch loaded more than once. Look for an append that should have been a truncate-and-reload, or a retry with no idempotency. |
| One tight contiguous key range missing | A single load batch failed and was never replayed — or a filter someone added during an incident and never removed. |
| Differences in a contiguous block at the **top** of the key range | A regression. On an ascending key, the key range *is* the timeline — find what changed in the pipeline on that date. |
| Differences scattered thinly everywhere | Usually not one bug. Switch to aggregate mode and group by something meaningful before drilling further. |
| Thousands of leaves, drill taking minutes | **Stop.** Bisection only works when data is mostly identical. See below. |

### When bisection degenerates

Bisection is O(log n) *because* it discards what matches. If most rows differ,
nothing is discarded and it becomes thousands of queries each scanning a slice
of the table. Localise first with `mode: aggregate` and a `COUNT` measure
grouped by a natural partition — roughly one query per side per level — then
drill a dataset narrowed to the groups that diverged.

### Aggregate mode reads in business terms

Pair `SUM` with `COUNT` on the same column. `SUM` alone cannot distinguish *a
row is missing* from *a value is wrong* — the total is short either way. Side
by side they are unmistakable, and it costs nothing extra.

`SUBGROUP_MISMATCH` means the divergence is below this node; keep reading down.
`MEASURE_MISMATCH` means this group's own numbers differ.

## Getting to the rows

Every mismatch leaf carries ready-to-run SQL for both sides, already filtered
to the segment:

```bash
synq-recon run-drill suite.yaml --include <name> --no-report -o json 2>/dev/null \
  | jq -r '.investigation_queries[0] | .source_query, .target_query'
```

Run those against the two databases to see the actual values. This is the point
at which row values enter the picture — on your terms, for a hundred rows
rather than a million. Prefer it to raising `reporting.level`.

## Fixing

**Fix the cause, not the symptom.** The reconciliation tells you a target
disagrees with its source. The repair belongs wherever the divergence was
introduced — pipeline code, a transformation, a schema definition — not in the
data.

In order of preference:

1. **The pipeline code.** A wrong mapping, a stale filter, a truncation, a
   non-idempotent append.
2. **The schema.** A target column narrower or less precise than its source
   will keep destroying data on every run. Widen it; do not make the loader
   cut values to fit.
3. **The data**, only as a backfill *after* the cause is fixed — otherwise the
   next run reintroduces the damage.

Then re-run the pipeline and reconcile again.

### Never

- **Never edit the source of truth** to make a reconciliation pass. The source
  is what the target is being held against.
- **Never patch target rows** to silence a finding while the code that produced
  them is unchanged.
- **Never loosen a threshold, drop a column from the comparison, or narrow a
  `where` clause** to turn a finding green. If a difference is genuinely
  acceptable, say so explicitly and explain why.
- **Never hand-query the warehouse instead of running a reconciliation.** A
  reconciliation is recorded, reproducible and comparable to the next run. Use
  SQL to *inspect* what a finding points at, not to replace the finding.
- **Never put `NOW()`, `CURRENT_DATE` or `GETDATE()` in a dataset query.** The
  two sides evaluate them at different instants and manufacture differences.
  Use a template variable resolved once into both sides.
- **Never synthesise a concatenated key.** `key_columns: [a, b]` range-filters
  on the column tuple and can use an index; `a || '|' || b` forces a full scan
  per segment.
- **Never compare a live source against a lagging target without a `cutoff:`.**
  Rows still in flight look exactly like missing rows.

## Working on a suite

- `key_columns` must be **unique** and should be **indexed**. Each drill level
  range-filters on it. `check-config --db` warns when it is not indexed — that
  warning is the difference between seconds and minutes.
- `exclude_columns` the bookkeeping that exists on one side only — load
  timestamps, batch ids, surrogate keys. Otherwise every run reports a
  difference forever and people stop reading them.
- `row_checksum` compares columns **positionally**, so both sides must present
  the same number of them. `source has N columns but target has M` means name
  the columns explicitly on both sides, or exclude the extras.
- Keep credentials in `.connections.yaml` beside the suite, git-ignored. The
  CLI discovers it from the working directory.

The full authoring guide, with every field, a worked example for each mode and
the question-to-reconciliation patterns, is in the `coalesce-reconciliation-authoring`
skill.

## Before any workspace write

`upload-config`, `promote`, `run-remote`, `trigger`, `suite delete` all act on
whichever workspace the credential resolves to. Run `synq-recon auth whoami`
and confirm the `workspace:` line **first**. There is no `--workspace`
override by design.

Use `--no-report` for local work: it resolves no credential and opens no
connection to the platform.

## More

- `reference/cli.md` — commands, flags, jq recipes, audit-log paths, costs,
  and what each error message means.
- Official guidance: https://docs.synq.io/reconciliation/agent-workflow
