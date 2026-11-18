---
type: llm
focus: trace
weight: 1
---
Find in the trace the final contents of the STG_CUSTOMER node file (nodes/TARGET-STG_CUSTOMER.sql or nodes/TARGET-STG_CUSTOMER.yml) and the column list of the customer source node (nodes/SRC-customer.yml). Score PASS only if ALL hold:

1. STG_CUSTOMER carries every column of the customer source node, none missing and none added. Output names may be renamed only in letter case.
2. Each source column is referenced with exactly the spelling and letter case the source node uses (ClickHouse column names are case-sensitive), either in the SELECT of a .sql node or through sourceColumnReferences lineage in a .yml node.
3. It reads from the source node through a two-argument ref() naming the source node exactly as its file name spells it, not a hard-coded database.table.

If you cannot find the final file contents in the trace, FAIL and say so.
