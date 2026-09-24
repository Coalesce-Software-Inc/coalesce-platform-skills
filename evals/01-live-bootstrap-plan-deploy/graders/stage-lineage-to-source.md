---
type: llm
focus: {source: file, path: nodes/TARGET-STG_REGION.yml}
weight: 1
---
This is the staging node file. Score PASS only if ALL hold:

1. It declares exactly three columns named R_REGIONKEY, R_NAME, R_COMMENT (no extra columns, none missing, none renamed).
2. Every column carries lineage back to an upstream node: each column has a sourceColumnReferences entry with at least one columnReferences item (a stepCounter/columnCounter pair) or, if this is a .sql node, the SELECT reads FROM a two-argument ref() macro. A column with an empty columnReferences list, or a hardcoded database.schema.table in place of lineage, is a FAIL.
3. The node is a staging/transformation node (not sqlType Source), in location TARGET, named STG_REGION, and if it is a V1 file its operation.config sets insertStrategy, truncateBefore, and testsEnabled (the type's defaults) rather than being empty.
