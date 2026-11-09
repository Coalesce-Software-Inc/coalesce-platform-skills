---
name: coalesce-add-column
description: Add a column to an existing Coalesce V2 (.sql) transformation node, placing any column annotation after the alias and before the comma, then verifying with coa.
---

<!-- coalesce-node-managed: true -->

> **Prerequisite:** load `coalesce-pipelines` first if it is not already loaded in this session. This skill assumes its rules and core loop.

# Add a column

In scope: editing the node the user named, and read-only `coa` commands. Ask before editing any other node (including an upstream node, to make a column exist) or anything under `nodeTypes/`.

## 1. Find the node

Open `nodes/<LOCATION>-<NAME>.sql`. If the name is ambiguous, run `coa create -d <dir> --list-nodes`.

- If the file is a V1 `.yml` node, the edit is still in scope. Follow "Adding a column" in coalesce-v1-yaml-nodes, then verify as in step 4.
- For a `.sql` node, check that its `@nodeType` resolves to a `fileVersion: 2` type. If it does not, the new column would be silently dropped. Stop and ask rather than upgrading the type.

## 2. Confirm where the column comes from

- **From an upstream node:** find the `{{ ref("LOC", "NAME") }}` it comes through, open that node's file, and confirm the source column is really there. If it is missing, stop and report that. Do not write SQL against a column you have not seen in the file, and do not edit the upstream node without asking.
- **Computed:** write the expression. Any new table reference uses `{{ ref("LOC", "NAME") }}` with both arguments.

## 3. Add it to the SELECT

- Append it before `FROM` unless the user gave a position. Match the existing indentation.
- Write `<expression> AS ALIAS` with a bare UPPER_SNAKE_CASE alias, or follow the alias style the file already uses. A bare column needs no alias.
- A column annotation goes after the alias and before the comma: `CUSTOMER_ID AS CUSTOMER_KEY @isBusinessKey,`
- Use only the native annotations (`@isBusinessKey`, `@isChangeTracking`, `@id("col-id")`, `@description("text")`) or ones the node type declares. Never add or change the node's top-level `@id`.

## 4. Verify

1. `coa validate -d <dir>`: 0 errors and 0 warnings. A V2 node's column types are inferred, so a clean validate does not prove the column exists.
2. `coa create -d <dir> --include "{ <NAME> }" --dry-run --verbose`: the new column appears in the DDL.
3. `coa run -d <dir> --include "{ <NAME> }" --dry-run --verbose`: the new column appears in the DML.

Fix and repeat until clean. Do not run `coa create` or `coa run` without `--dry-run` unless the user asks. Report anything you could not resolve within scope.
