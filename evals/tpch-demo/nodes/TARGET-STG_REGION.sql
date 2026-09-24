@id("a18c832a-e220-4264-8265-9fd13bb5fdcb")
@nodeType("0016cdc3-eacd-4610-9147-8217aeeea42c")

SELECT
    "R_REGIONKEY" AS "R_REGIONKEY",
    "R_NAME"      AS "R_NAME",
    "R_COMMENT"   AS "R_COMMENT"
FROM {{ ref('SRC', 'REGION') }} "REGION"
