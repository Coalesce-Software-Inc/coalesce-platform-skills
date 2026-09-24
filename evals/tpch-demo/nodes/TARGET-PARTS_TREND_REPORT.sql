@id("3a7f2e91-c4b5-4d8e-a6f3-8c1d5e9b2047")
@nodeType("0016cdc3-eacd-4610-9147-8217aeeea42c")

SELECT
    DATE_TRUNC('MONTH', O."O_ORDERDATE")                            AS ORDER_MONTH,
    YEAR(O."O_ORDERDATE")                                           AS ORDER_YEAR,
    P."P_TYPE"                                                      AS PART_TYPE,
    P."P_BRAND"                                                     AS PART_BRAND,
    P."P_MFGR"                                                      AS PART_MFGR,
    COUNT(DISTINCT O."O_ORDERKEY")                                  AS ORDER_COUNT,
    COUNT(L."L_LINENUMBER")                                         AS LINE_ITEM_COUNT,
    SUM(L."L_QUANTITY")                                             AS TOTAL_QUANTITY,
    SUM(L."L_EXTENDEDPRICE")                                        AS GROSS_REVENUE,
    SUM(L."L_EXTENDEDPRICE" * (1 - L."L_DISCOUNT"))                AS NET_REVENUE,
    SUM(L."L_EXTENDEDPRICE" * L."L_DISCOUNT")                      AS TOTAL_DISCOUNT,
    AVG(L."L_DISCOUNT")                                             AS AVG_DISCOUNT_RATE,
    AVG(L."L_QUANTITY")                                             AS AVG_QUANTITY_PER_LINE
FROM {{ ref('TARGET', 'STG_LINEITEM') }} L
INNER JOIN {{ ref('TARGET', 'STG_ORDERS') }} O
    ON L."L_ORDERKEY" = O."O_ORDERKEY"
INNER JOIN {{ ref('TARGET', 'STG_PART') }} P
    ON L."L_PARTKEY" = P."P_PARTKEY"
GROUP BY
    DATE_TRUNC('MONTH', O."O_ORDERDATE"),
    YEAR(O."O_ORDERDATE"),
    P."P_TYPE",
    P."P_BRAND",
    P."P_MFGR"
ORDER BY
    ORDER_YEAR,
    ORDER_MONTH,
    GROSS_REVENUE DESC
