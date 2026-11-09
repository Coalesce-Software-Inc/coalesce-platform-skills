<!-- coalesce-node-managed: true -->
# Workspace YAML Artifacts

Confirm every shape with `coa describe schema <type>` before editing. All of
these files are shared config: ask the user before changing any of them.

## Repository layout

```
.
├── data.yml          # central manifest (required)
├── locations.yml     # storage location names (required)
├── workspace.yml     # profile binding + local db/schema mappings (optional, local-only)
├── nodes/            # node files: <LOCATION>-<NAME>.sql / .yml (flat)
├── nodeTypes/        # workspace-local node types: <DisplayName>-<ID>/
├── packages/         # package declarations (base node types package)
├── environments/     # environment configs
├── subgraphs/        # logical node groupings
├── jobs/             # orchestration definitions
└── macros/           # reusable SQL macros
```

## data.yml (required)

`{ fileVersion, platformKind?: snowflake|databricks|fabric|bigquery,
defaultStorageMapping? }`. Only `fileVersion` is required. No other keys are
allowed.

## locations.yml (required)

`{ defaultStorageMapping, locations: [<NAME>, ...], fileVersion: 1 }`. A list
of location names plus a default mapping name. No database or schema here, and
no other keys.

A location name must match everywhere it appears: the node filename prefix,
`locations.yml`, the `workspace.yml` mappings, and each environment's
`mappingDefinitions`. Renaming a location touches all of them.

## workspace.yml (optional, local-only, gitignored)

`{ profile: <name>, locations: { <NAME>: { database, schema } },
parameters: { <name>: <json-value> } }`.

- `locations` is the local mapping `coa create` / `coa run` use. The validate
  graph scanners need it to resolve refs.
- `profile` is the name of a `~/.coa/config` section, never credentials. Write
  it with `coa profile use <name> -d <dir>` or `coa init --profile <name>`,
  clear it with `coa profile unset`; do not hand-write it.
- `coa doctor --fix` can bootstrap a missing file (ask first).

## environments/<NAME>.yml

`{ name, id, type: "Environment", fileVersion,
mappingDefinitions: { <LOC>: { database, schema } } }`. All fields required.

## Job (jobs/<NAME>.yml)

Not a steps array.

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Integer string matching `^-?\d+$`, e.g. `"1"`. Not a UUID. Unique among jobs. |
| `type` | yes | Constant `Job`. |
| `fileVersion` | yes | Constant `1`. |
| `name` | no | Human-readable name. |
| `includeSelector` | no | Selector string: the nodes the job targets. |
| `excludeSelector` | no | Selector string subtracted from the include set. |

```yaml
id: "1"
type: Job
fileVersion: 1
name: BUILD_TARGET
includeSelector: '{ location: "TARGET" }+'
excludeSelector: '{ name: "TEST_*" }'
```

A job file with a `steps: [{ selector }]` array is a legacy shape that fails
`coa validate`. Do not add an `includeSelector` inside one; flag it for
migration.

## Subgraph (subgraphs/<NAME>.yml)

Not a nodes array. `{ id, type: "Subgraph", fileVersion: 1, name,
steps: ["<node id>", ...] }`. Each step is a node's id (a `.yml` node's `id:`
or a `.sql` node's `@id`).

```yaml
id: "1"
type: Subgraph
fileVersion: 1
name: ANALYTICS
steps: ["a1b2c3d4", "e5f6a7b8"]
```

The serve UI resolves membership as `steps ∩ live-node-ids` and silently drops
any step that is not a real node id. Subgraphs with a `nodes:` list, or with
`steps` holding node names or selector strings, are legacy shapes you may meet
in existing repos.

## Node types (nodeTypes/<DisplayName>-<ID>/)

Base node types are not authored here. They ship in the base node types
package, declared in `packages/base-node-types.yml` by `coa init` and
materialized by `coa install` under `.coa/cache/packages/`
(`.coa/cache/packages.json` is the machine cache that tree mirrors). How to
find and choose a type is in the coalesce-pipelines skill.

A node type folder holds:

- **definition.yml**: `{ isDisabled, name, id, type: "NodeType", fileVersion,
  metadata: { nodeMetadataSpec, error: null } }`. `nodeMetadataSpec` is a YAML
  string with required `capitalized`, `short`, `plural`, `tagColor` and
  optional `config`, `systemColumns`, `annotations`. Its `config` holds the
  defaults a hand-authored node must copy into `operation.config`: run
  templates gate their DML on them (Work-204 on `config.insertStrategy ==
  'INSERT'` and `config.truncateBefore`), so `config: {}` renders zero run
  SQL.
- **create.sql.j2** (DDL) and **run.sql.j2** (DML): Jinja templates.

### Templates for a `fileVersion: 2` type

Only relevant when the user has asked for a custom type. Build the projection
by iterating `sources` then `source.columns`, and guard create with
`WHERE 1=0` (the CTAS pattern, which does not depend on `col.dataType`):

```jinja
CREATE OR REPLACE TABLE {{ ref_no_link(node.location.name, node.name) }} AS
{% for source in sources %}
SELECT
{% for col in source.columns %}
    {{ get_source_transform(col) }} AS "{{ col.name }}"{%- if not loop.last -%}, {% endif %}
{% endfor %}
{{ source.join }}
WHERE 1=0
{% endfor %}
```

`run.sql.j2` uses the same column iteration without the guard:

```jinja
{{ stage('Truncate') }}
TRUNCATE IF EXISTS {{ ref_no_link(node.location.name, node.name) }}
{% for source in sources %}
{{ stage('Insert') }}
INSERT INTO {{ ref_no_link(node.location.name, node.name) }}
SELECT
{% for col in source.columns %}
    {{ get_source_transform(col) }} AS "{{ col.name }}"{%- if not loop.last -%}, {% endif %}
{% endfor %}
{{ source.join }}
{% endfor %}
```

Never write a V2 body as `{{ node.sql }}` or `SELECT *`; either renders a
zero-column table. V1 types use explicit-column DDL
(`{{ col.name }} {{ col.dataType }}`).

After any template edit, run both dry-runs for the affected nodes:
`coa create -d <dir> --include "{ nodeType: \"<Name>\" }" --dry-run --verbose`
and the same with `coa run`. Config gating lives in `run.sql.j2`, so the
create dry-run alone proves nothing about whether data would load.

## Macros (macros/)

Reusable SQL referenced from node transformations. Shape:
`coa describe schema macro`.
