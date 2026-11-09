---
name: coalesce-create-job
description: Create a Coalesce job that selects nodes to create/run, using the correct coa job schema (includeSelector/excludeSelector strings, integer-string id — not a steps array).
---
<!-- coalesce-node-managed: true -->

> **Prerequisite:** load `coalesce-pipelines` first if it is not already loaded
> in this session. This skill assumes its rules and core loop.

# Create a job

A job is a named selection of nodes, expressed as selector strings. It is not
a list of steps. `coa describe schema job` and `coa describe selectors` are the
source of truth; read both before writing. If the request describes a
different shape (a `steps` array, a UUID id), write the schema's shape and
tell the user why.

Jobs are shared config under `jobs/`. A user asking for the job is the
approval to create it; otherwise ask first.

## The shape

```yaml
id: "1"                # integer string, unique among jobs; not a UUID
type: Job
fileVersion: 1
name: BUILD_TARGET
includeSelector: '{ location: "TARGET" }+'
excludeSelector: '{ name: "TEST_*" }'
```

## Procedure

1. Write the selectors and check what they match:
   ```bash
   coa create -d <dir> --list-nodes
   coa create -d <dir> --include "<include>" --exclude "<exclude>" --dry-run
   coa run    -d <dir> --include "<include>" --exclude "<exclude>" --dry-run --verbose
   ```
   The matched set should be exactly the nodes the user described. The run
   dry-run matters: a selected node with empty run SQL would load no data.
2. Pick the next free integer `id` by reading the existing `jobs/*.yml`.
3. Write `jobs/<JOB_NAME>.yml`.
4. `coa validate -d <dir>` until it is clean.

A job only selects nodes. Running it locally is `coa create` / `coa run` with
its selectors, which is local development, not a deploy.
