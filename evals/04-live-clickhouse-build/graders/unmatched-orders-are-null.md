---
type: llm
focus: trace
weight: 2
---
This checks that customers with no orders get NULL, not a default, in STG_CUSTOMER_ORDERS. On ClickHouse a plain LEFT JOIN does NOT produce NULL for unmatched rows by default: unless `join_use_nulls = 1` is in effect, the order columns of an unmatched customer come back as the type's default (0, an empty string, or 1970-01-01).

Find the final definition of STG_CUSTOMER_ORDERS in the trace (its .sql SELECT or its .yml join and column transforms). Score PASS only if ALL hold:

1. It keeps every customer: customer is the preserved side of an outer join to orders (for example `customer LEFT JOIN orders`).
2. The three order columns (order key, order date, total price) are made NULL for customers with no orders by something that actually works on ClickHouse, for example: wrapping each in `nullIf(col, <default>)` or an equivalent CASE on whether a match exists; a `SETTINGS join_use_nulls = 1` that is actually rendered into the query that loads the table; or another mechanism whose effect the agent verified.
3. The node was created and loaded successfully with that definition (a non-dry-run `coa create` and `coa run` for it succeeded).

FAIL if the join is a plain LEFT JOIN with no such handling, even if the agent claims the columns will be NULL. FAIL if the agent changed the requirement (for example used an INNER JOIN, dropped customers without orders, or filled the columns with zeros). State which mechanism you found.
