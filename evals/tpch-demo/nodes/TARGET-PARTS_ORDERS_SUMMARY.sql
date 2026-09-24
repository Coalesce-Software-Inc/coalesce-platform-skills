@id("b5e8d3a2-7c6f-4e91-b2d4-9f0a3c7e5816")
@nodeType("0016cdc3-eacd-4610-9147-8217aeeea42c")

SELECT
    P."P_PARTKEY"                                                   AS P_PARTKEY,
    P."P_NAME"                                                      AS P_NAME,
    P."P_TYPE"                                                      AS P_TYPE,
    P."P_BRAND"                                                     AS P_BRAND,
    P."P_MFGR"                                                      AS P_MFGR,
    P."P_SIZE"                                                      AS P_SIZE,
    P."P_CONTAINER"                                                 AS P_CONTAINER,
    P."P_RETAILPRICE"                                               AS P_RETAILPRICE,
    PS."PS_AVAILQTY"                                                AS PS_AVAILQTY,
    PS."PS_SUPPLYCOST"                                              AS PS_SUPPLYCOST,
    COUNT(DISTINCT L."L_ORDERKEY")                                  AS TOTAL_ORDERS,
    COUNT(L."L_LINENUMBER")                                         AS TOTAL_LINE_ITEMS,
    SUM(L."L_QUANTITY")                                             AS TOTAL_QUANTITY_ORDERED,
    SUM(L."L_EXTENDEDPRICE")                                        AS TOTAL_GROSS_REVENUE,
    SUM(L."L_EXTENDEDPRICE" * (1 - L."L_DISCOUNT"))                AS TOTAL_NET_REVENUE,
    AVG(L."L_EXTENDEDPRICE" * (1 - L."L_DISCOUNT"))                AS AVG_NET_REVENUE_PER_LINE,
    SUM(L."L_QUANTITY") / NULLIF(COUNT(DISTINCT L."L_ORDERKEY"), 0) AS AVG_QUANTITY_PER_ORDER,
    MIN(O."O_ORDERDATE")                                            AS FIRST_ORDER_DATE,
    MAX(O."O_ORDERDATE")                                            AS LAST_ORDER_DATE
FROM {{ ref('TARGET', 'STG_PART') }} P
LEFT JOIN {{ ref('TARGET', 'STG_LINEITEM') }} L
    ON P."P_PARTKEY" = L."L_PARTKEY"
LEFT JOIN {{ ref('TARGET', 'STG_ORDERS') }} O
    ON L."L_ORDERKEY" = O."O_ORDERKEY"
LEFT JOIN {{ ref('TARGET', 'STG_PARTSUPP') }} PS
    ON P."P_PARTKEY" = PS."PS_PARTKEY"
GROUP BY
    P."P_PARTKEY",
    P."P_NAME",
    P."P_TYPE",
    P."P_BRAND",
    P."P_MFGR",
    P."P_SIZE",
    P."P_CONTAINER",
    P."P_RETAILPRICE",
    PS."PS_AVAILQTY",
    PS."PS_SUPPLYCOST"
