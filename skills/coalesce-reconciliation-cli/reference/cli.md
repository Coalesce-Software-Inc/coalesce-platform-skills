# synq-recon reference

Condensed from https://docs.synq.io/reconciliation/agent-workflow and the CLI
reference. Load this when you need a flag, a jq path, or an error message.

## Commands

### Local — these spend warehouse queries

| Command | Does | Cost |
|---|---|---|
| `check-config suite.yaml` | Parse, check required fields, warn on time-dependent SQL | None, never connects |
| `check-config suite.yaml --db` | Connect, plan every query with `LIMIT 0`, report columns/size/keys, warn on unindexed key | Planner call per query + metadata sweep |
| `plan suite.yaml` | Print the resolved execution plan and the exact SQL both sides will run | None |
| `run-check suite.yaml` | Stage 1: count + checksum per side | 2 queries per reconciliation |
| `run-drill suite.yaml` | Stage 2: bisect the key space | 2 queries per level (not per segment) |
| `run suite.yaml --auto-drill` | Both stages | Sum of the above |
| `recheck <run>` | Re-run what a finished run ran, report what moved | Scoped to what was left open — cheaper than starting over |
| `drill-deeper <run>` | Continue a previous drill from where it stopped | As above |
| `audit-logs queries <run>` | Get a finished run's investigation SQL back | None, reads the log |

`recheck` and `drill-deeper` take a local audit-log file or a stored run's
invocation id, and **need `--connections`** — an audit log records connection
names, never credentials.

### Workspace — no warehouse cost, but they write

`auth whoami` · `upload-config` · `suite …` · `promote` / `unpromote` ·
`run-remote` · `trigger` · `deployment …` · `runs …` · `connections …` ·
`entities …`

Confirm `auth whoami` before any of the mutating ones.

## Flags

| Flag | Notes |
|---|---|
| `--include <name>` | Repeatable. Filter reconciliations. **Positional names fail** with `accepts 1 arg(s), received 2`. |
| `--exclude <name>` | Repeatable. |
| `--no-report` | Resolve no credential, open no platform connection. Use for local work. Or `RECON_NO_REPORT`. |
| `-o json` | **Required for parsing.** Default is `toon` under an AI-agent env marker, `table` for a human terminal. |
| `--connections <path>` | Explicit connections file. Auto-discovered as `.connections.yaml` / `connections.yaml` in the working directory. |
| `--audit-log <path>` | Full JSON record of the run. Trailing `/` for an auto-named file in a directory. |
| `--depth N` | Cap drill depth. |
| `--threshold N` | Stop drilling below this segment size. |
| `--max-table-rows` / `--max-table-bytes` | Estimate scan size first and warn past the threshold. Default `0` = off. |
| `--fail-on` | `run-remote --wait` / `trigger --wait` only. Default `mismatched,failed`. `--fail-on=passed` inverts, for a canary. |
| `--drill=false` | **Pass explicitly on `run-remote`.** Omitting it does not mean off — it falls through to each reconciliation's `bisection.enabled`. |

## Exit codes

Local commands: `0` everything matched · `1` differences found **or** the
command failed.

`run-remote --wait` / `trigger --wait`: `0` passed · `1` a `--fail-on`
condition was met · `2` the run itself failed.

## jq recipes

```bash
# names that differ
synq-recon run-check suite.yaml --no-report -o json 2>/dev/null \
  | jq -r '.results[] | select(.match == false) | .name'

# key ranges where a difference lives
synq-recon run-drill suite.yaml --include orders --no-report -o json 2>/dev/null \
  | jq -r '.mismatch_leaves[] | "\(.segment.min_key) .. \(.segment.max_key)"'

# how each leaf differs - read this, not the count direction
synq-recon run-drill suite.yaml --include orders --no-report -o json 2>/dev/null \
  | jq -r '.mismatch_leaves[] | "\(.segment.min_key)..\(.segment.max_key) \(.mismatch_types|join(","))"'

# ready-to-run SQL for one difference, both sides
synq-recon run-drill suite.yaml --include orders --no-report -o json 2>/dev/null \
  | jq -r '.investigation_queries[0] | .source_query, .target_query'
```

`run-drill -o json` top level: `name`, `title`, `total_segments`,
`mismatch_count`, `max_depth`, `duration_ms`, `root_segment`,
`mismatch_leaves`, `investigation_queries`, `diff_queries`, `reporting_level`.

Each leaf carries `drill_stop_reason`, `diff_queries`, and every
`mismatch_types` that applies — a segment differing in both size and content
reports two.

## Audit-log paths

```bash
jq -r '.reconciliations[].reconciliation.name' audit.json
jq -r '.reconciliations[].stages[].quick_check_result? | select(.) | "\(.source_count) vs \(.target_count)"' audit.json
jq -r '.reconciliations[].stages[].bisection_result?.mismatch_leaves[]?.segment | "\(.min_key)..\(.max_key)"' audit.json
```

Two traps:

- **Casing.** A local `--audit-log` file is snake_case (`mismatch_leaves`). The
  same log fetched with `audit-logs get <id> -o json` is camelCase
  (`mismatchLeaves`). A jq path for one silently returns `null` on the other.
- **Counts are strings.** In the audit log, 64-bit ints are quoted
  (`"source_count": "10"`) — unlike `run-check -o json`, where they are
  numbers. Compare with `tonumber`.

## Suite fields

```yaml
# yaml-language-server: $schema=https://schemas.synq.io/synq-recon/v1/config.schema.json
name: ...
title: ...
connections: {}          # or a separate .connections.yaml
reconciliations:
  <id>:
    source: {connection, table | query, columns | exclude_columns, where}
    target: {...}
    key_columns: [...]           # unique, indexed; a list for composite keys
    mode: row_count | row_checksum | aggregate     # row_checksum is default
    column_mapping: {src: tgt}   # for genuinely different names
    case_insensitive: true       # on by default
    hash_algorithm: auto | md5 | farm_fingerprint | xxhash64
    bisection:
      factor: 32                 # segments per level, max 1024
      threshold: 16384           # stop drilling below this segment size
      strategy: quantile | hash | time | auto
      time_column: ...           # required for strategy: time
      time_granularity: hour | day | week | month | quarter | year
    aggregate:
      measures: [{column, function: [SUM, COUNT, AVG, MIN, MAX]}]
      group_columns: [...]       # a hierarchy, outermost first
      thresholds:
        absolute: 0.01
        percentage: 0.001
        percentage_mode: source | target | symmetric
        per_column: {col: {...}}
        per_measure: {"SUM(x)": {...}}
    cutoff:                      # for a lagging target
      column: updated_at
      truncate: hour
      offset: "-30m"
      combine: min | max | source | target
    window: {...}                # sliding or fixed lookback
    reporting:
      level: count_only | with_keys | detailed
      sample_limit: 100
      consent_acknowledged: true # required for `detailed`
variables: {}                    # {{ name }} in queries, resolved once per run
setup: {} / teardown: {}         # SQL per connection
strict_time_references: false    # make NOW()/CURRENT_DATE an error
```

Threshold resolution, most specific first:
`per_column[c].per_measure[m]` → `per_measure[m]` → `per_column[c]` →
`thresholds`. A group passes if it is within **either** the absolute or the
percentage limit — so a percentage tolerance on a large total will hide small
absolute errors.

`full` is a legacy spelling of `row_checksum`.

## Supported databases

PostgreSQL · MySQL · MSSQL · Oracle · Snowflake · BigQuery · Redshift ·
Databricks · ClickHouse · Trino · Athena · Microsoft Fabric · DuckDB
(local files and MotherDuck). Source and target need not match.

## Errors

| What you see | What it means |
|---|---|
| `no connections defined` (offline `check-config`) | The suite's `connection:` values are workspace integration ids. Pass `--connections <file>`; add `--db` to connect. |
| `open suite.yaml: no such file or directory` | Wrong working directory. |
| Every query fails `--db` with "table does not exist" | `--db` does not run the suite's `setup:` SQL. Expected for setup-created tables; go straight to a run. |
| `source has N columns but target has M columns` | `row_checksum` compares positionally. Name columns on both sides, or `exclude_columns` the extras. |
| `no connections available to replay run …` | `recheck` / `drill-deeper` need `--connections`. |
| `accepts 1 arg(s), received 2` | A reconciliation name passed positionally. Use `--include`. |
| Thousands of leaves, minutes of runtime | Data is not mostly-identical. Localise with aggregate mode first. |
| `-o json` will not parse | Either `2>&1` merged the logs, or it was `run --auto-drill`, which emits several documents. |
| A promoted suite still runs the old comparison | A deployment is an immutable snapshot. Re-promote after editing. |
