---
type: llm
focus: last_message
weight: 1
---
The workspace has exactly eight nodes, all in storage location BRONZE, with these column counts:
CUSTOMER 8, LINEITEM 16, NATION 4, ORDERS 9, PART 9, PARTSUPP 5, REGION 3, SUPPLIER 7.

Note: BRONZE-SUPPLIER.yml is indented differently from the other node files, so a parser that matches a fixed indentation reports 0 columns for SUPPLIER. That is wrong.

Read the node list the agent's final message reports the server returned. (Whether that report matches the real tool output is checked by a separate grader.) Score PASS only if it contains all eight nodes, groups or labels them under BRONZE, and gives the correct column count for every one of the eight. Any missing node, extra node, or wrong count is a FAIL; name it.
