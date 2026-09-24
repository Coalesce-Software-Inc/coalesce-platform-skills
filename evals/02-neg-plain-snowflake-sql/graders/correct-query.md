---
type: llm
focus: last_message
weight: 1
---
Score PASS only if the reply is a single SQL query that: joins ORDERS to CUSTOMER (O_CUSTKEY = C_CUSTKEY) and CUSTOMER to NATION (C_NATIONKEY = N_NATIONKEY); aggregates O_TOTALPRICE with SUM grouped by nation name; orders by that total descending; limits to 5 rows. A one-line note around the query is acceptable, but the reply must not mention Coalesce, coa, nodes, or pipelines.
