<!-- coalesce-node-managed: true -->

# ClickHouse workspaces

Read this when `data.yml` has `platformKind: tdbc-clickhouse`. It overrides the Snowflake-shaped defaults elsewhere in the coalesce-\* skills. Ignore it for every other platform.

ClickHouse differs from Snowflake at almost every step, and most of the differences pass `coa validate` and both dry-runs, then fail or load wrong data only when the SQL executes. Treat a clean validate and clean dry-runs as necessary, not sufficient.

## Identity and storage

- `platformKind` is `tdbc-clickhouse`. Package IDs drop the `tdbc-` prefix: a ClickHouse package is `@coalesce/clickhouse/<name>`.
- ClickHouse has no database/schema split. A location maps to a ClickHouse database, stored in the `schema` field:
  - `workspace.yml`: `locations: { SRC: { schema: tpch }, TARGET: { schema: ANALYTICS } }`, no `database` key.
  - `environments/<NAME>.yml` and `coa environments create --mappings`: `{ "database": "", "schema": "<clickhouse database>" }`.
- **The target database must already exist.** `coa init` accepts a name that does not exist, and `coa create` then fails with `Database <NAME> does not exist`. `coa` has no command that runs ad-hoc SQL, so do not try to create it through a node. Tell the user to run `CREATE DATABASE <NAME>` (or have an admin do it), then continue.

## Connection

- A profile has `platformKind=tdbc-clickhouse`, `platformAuthType=user-password` (the only supported type), `platformHost`, `platformPort` (8443 for ClickHouse Cloud), `platformUsername`, `platformPassword`. Create it with the generic flags: `coa profile create <name> --non-interactive --platformKind tdbc-clickhouse --platformAuthType user-password --platformHost <h> --platformPort 8443 --platformUsername <u> --platformPassword <p>`. `--platformKind ClickHouse` and `clickhouse` are rejected, with an error that lists only Snowflake, Databricks and BigQuery.
- `coa init` takes the same `--platform*` flags plus `--srcSchema` / `--targetSchema` for the location databases.
- ClickHouse Cloud services idle out. The first call after a pause can take over a minute while the service wakes, and Coalesce Desktop gives up after 30 s with `no response from <host>:8443 within connectTimeoutMs (30000 ms)`. Retry once before treating it as a credentials or network problem.

## Names are case-sensitive

- `coa sources add` imports tables and columns exactly as ClickHouse stores them, usually lowercase: `nodes/SRC-customer.yml`, column `c_custkey`.
- Write source column references exactly as the Source `.yml` spells them. `"C_CUSTKEY"`, `C_CUSTKEY` and `c_custkey` are three different names; only the one that matches works. A wrong case passes validate and both dry-runs, then fails at run with `Unknown expression identifier C_CUSTKEY ... Maybe you meant: ['c_custkey']`.
- `ref()` must match the node's name and case: `{{ ref("SRC", "customer") }}`, not `"CUSTOMER"`. A wrong case shows as `warning[namedDependencyUnresolved]`, and the create dry-run renders `Nullable(UNKNOWN)` column types while still reporting `passed`.
- Aliases keep the case you write. New node and column names may follow the repo's UPPER_SNAKE_CASE convention; downstream nodes must then use that case too.
- Coalesce Desktop's **Validate Select** runs the SELECT against ClickHouse and catches case errors. The CLI has no equivalent, so read the Source file instead of guessing.

## SQL dialect

Write ClickHouse SQL, not Snowflake SQL. Snowflake-only functions pass validate and both dry-runs, then fail at execution.

- `if(cond, a, b)`, not `IFF`. Check any function you are not sure of against the ClickHouse function reference.
- **There is no `MERGE`.** It is a syntax error. See "Upserts and history" for what to do instead, and explain that to the user rather than writing MERGE.
- Put `UNION` / `UNION ALL` inside a CTE; at the top level the node parser can misread the clauses after it.
- `LEFT JOIN` does not produce NULL for unmatched rows by default: ClickHouse returns the type's default (`0`, `''`, `1970-01-01`). Handle it deliberately: the package's `joinUseNulls` runtime parameter or `@joinUseNulls` (views), or `nullIf` / `coalesce` in the SELECT. Say which you chose.
- `FixedString(n)` values are padded with `\0`. Use `toString()` or `trimRight()` before comparing them to other strings or exporting them.

## Node types

ClickHouse has no base node types package. `coa init` writes the built-in types to `nodeTypes/`, and `coa install` printing "No packages to install." is normal; do not run `coa init` to look for a base package.

| Type (id) | Format | What it does |
|---|---|---|
| `Stage` | V1 | TRUNCATE, then INSERT |
| `persistentStage`, `Dimension`, `Fact` | V1 | INSERT only (append), `truncateBefore: false` |
| `View` | V1 | view |
| `sqlStage` | V2 | TRUNCATE, then INSERT; the staging type for `.sql` nodes |
| `sqlView` | V2 | view |

None of the built-in types has a business key, a merge, or system columns. Their templates are the same INSERT; only the truncate default differs. `isBusinessKey`, `isChangeTracking` and the `isSystem*` flags are accepted and ignored.

**Never build an SCD2, "keeps history", or upsert node on a built-in type.** A built-in Dimension appends a full copy of the source on every run: two runs of a 25-row source leave 50 rows, with no error. History and upserts need the ClickHouse SQL node types package (below).

### Table config

ClickHouse types carry table options the Snowflake types do not:

| Config | Default | Meaning |
|---|---|---|
| `tableEngine` | `MergeTree` | the table `ENGINE` |
| `orderBy` | `tuple()` | the sort key; `tuple()` means none |
| `partitionBy` | none | the partition expression |

- V1: set them in `operation.config` along with the type's other defaults.
- V2 on a built-in type: set them as node-level annotations above the SELECT, `@orderBy("c_custkey")`, `@partitionBy("toYYYYMM(o_orderdate)")`, `@tableEngine("ReplacingMergeTree")`. The built-in types declare no annotations, so validate does not check the names; spell them exactly.

### Nullability

- Every column of a V2 node is created `Nullable(...)`, even when the source column is NOT NULL. Mark key columns `@notNull`.
- A V1 column is Nullable when `nullable: true`. Copy `nullable` from the upstream column (ClickHouse sources are usually `false`) instead of hard-coding `true`.
- On the built-in types a Nullable column cannot be in `orderBy` / `partitionBy`: create fails with `Sorting key contains nullable columns, but merge tree setting allow_nullable_key is disabled`. (The package types add `allow_nullable_key = 1` themselves.)
- `Array` and `Map` columns cannot be Nullable; mark them `@notNull` or every plan reports them as changed.
- A NULL inserted into a non-nullable column is stored as the type's default (`0`, `''`), not rejected.

## Upserts and history: the ClickHouse SQL node types package

The ClickHouse SQL node types package provides `SQLWork`, `SQLDimension` (SCD1 and SCD2) and `SQLFact`, with merge strategies (`@mergeStrategy("changeTracking" | "lastModified" | "allColumnMatch")`) implemented as ClickHouse INSERTs plus either a clean-up DELETE (MergeTree) or a ReplacingMergeTree. Its README is the reference for every annotation: https://github.com/coalesceio/clickhouse-node-types-sql

**It is not in the Coalesce Marketplace yet.** It will be published there like the other platforms' packages once production supports ClickHouse; until then `coa install` cannot fetch it and coalesce-install-package will not find it. When a task needs history, an upsert, or a MERGE:

1. Tell the user it needs the ClickHouse SQL node types package, which is not yet published to the Marketplace, and that they should ask Coalesce for it.
2. Do not build it on a built-in type, do not copy node types into `nodeTypes/` yourself, and do not write MERGE.
3. If the package is already present (its types are on disk under `nodeTypes/` or `.coa/cache/packages/`), use it as described below.

Using the package once it is present:

- Its `SQLDimension` and `SQLFact` require a column `@id("<short id>")` on every column (the coa default of "no column @id" does not apply to these types). `@isSurrogateKey` is a declared annotation here and needs `@notNull` (and `@defaultValue("generateUUIDv4()")` for a UUID key).
- SCD2 needs `@isBusinessKey`, `@isChangeTracking` on the tracked columns (or `@lastModifiedTracking(2)`), and `@isSystemVersion`, `@isSystemCurrentFlag`, `@isSystemCreateDate`, `@isSystemUpdateDate @notNull` and `@isSystemEndDate`. Use `DateTime64(6)` for the system dates, not `DateTime`.
- The package types add `allow_nullable_key = 1` themselves when a table has a sort or partition key. On a MergeTree, `@optimize` runs `OPTIMIZE TABLE ... FINAL` after the load.
- Before the first deploy, settle with the user: the package parameter `engine` (MergeTree or ReplacingMergeTree; changing it later does not recreate existing tables), the runtime parameter `readWithFinal: true` in every environment when any table is a ReplacingMergeTree, and `joinUseNulls`, set once and the same in every environment. The runtime parameter `querySettings` sets ClickHouse query settings (memory, threads, spill to disk) for every table load; a node's own `@querySettings` is merged with it.
- Views follow only their own node's settings, never runtime parameters: use `@final`, `@joinUseNulls`, and `@querySettings` on the view node.
- A ReplacingMergeTree keeps replaced rows until a background merge. Readers outside Coalesce need `FINAL` or `SETTINGS final = 1` on their ClickHouse user.
- `@writeMode("truncateInsert")` on an SCD2 Dimension erases its history on every run. Keys deleted from the source are never expired.

## Rebuilds lose data

- `coa create` without `--dry-run` runs `CREATE OR REPLACE TABLE`: the table comes back empty. Before running it on a table that may hold data, ask the user.
- A deploy that changes a node's `orderBy`, `partitionBy`, primary key, or a key column's name or type recreates the table empty, including a Dimension's whole SCD2 history. The package shows a `Warning: Table Recreated (<reason>)` stage when this happens. Flag any such change before planning.
- Adding a `@notNull` column without `@defaultValue` to a loaded table fills existing rows with the type's default.

## Deploying

- Cloud `coa plan` / `deploy` / `refresh` for ClickHouse need the `enableTdbcPlatform` feature flag on the Coalesce organization. Without it, plan fails with `Platform 'tdbc-clickhouse' requires the 'enableTdbcPlatform' feature flag, which is not enabled for this organization`. That is an org setting; tell the user to contact Coalesce.
- `coa environments create` takes `--connectionAccount https://<host>:8443/` for ClickHouse, and `--mappings` with `"database": ""`.
