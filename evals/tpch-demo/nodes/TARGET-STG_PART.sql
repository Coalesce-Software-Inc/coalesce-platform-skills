@id("b24594fc-61df-4f7e-9cbe-1a5b64951246")
@nodeType("0016cdc3-eacd-4610-9147-8217aeeea42c")

SELECT
    "P_PARTKEY"     AS "P_PARTKEY",
    "P_NAME"        AS "P_NAME",
    "P_MFGR"        AS "P_MFGR",
    "P_BRAND"       AS "P_BRAND",
    "P_TYPE"        AS "P_TYPE",
    "P_SIZE"        AS "P_SIZE",
    "P_CONTAINER"   AS "P_CONTAINER",
    "P_RETAILPRICE" AS "P_RETAILPRICE",
    "P_COMMENT"     AS "P_COMMENT"
FROM {{ ref('SRC', 'PART') }} PART
