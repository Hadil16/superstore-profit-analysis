-- Superstore profit analysis: the business questions in SQL (SQLite).
-- Run against data/superstore.db (built by load_data.py).
-- Profit margin = profit / sales. Amounts are in US dollars.

-- ---------------------------------------------------------------
-- Q0. Data audit: row count, missing values and the loss-making lines
-- ---------------------------------------------------------------
SELECT COUNT(*)                                          AS total_rows,
       SUM(profit IS NULL OR sales IS NULL OR discount IS NULL) AS rows_with_missing_values,
       SUM(profit < 0)                                   AS rows_losing_money,
       ROUND(100.0 * SUM(profit < 0) / COUNT(*), 1)      AS pct_rows_losing_money
FROM orders;

-- ---------------------------------------------------------------
-- Q1. Which categories sell a lot but earn little?
-- ---------------------------------------------------------------
SELECT category,
       ROUND(SUM(sales), 0)                       AS sales,
       ROUND(SUM(profit), 0)                      AS profit,
       ROUND(100.0 * SUM(profit) / SUM(sales), 1) AS margin_pct
FROM orders
GROUP BY category
ORDER BY margin_pct;

-- ---------------------------------------------------------------
-- Q2. Which regions are the least profitable, and do they discount more?
-- ---------------------------------------------------------------
SELECT region,
       ROUND(SUM(sales), 0)                       AS sales,
       ROUND(SUM(profit), 0)                      AS profit,
       ROUND(100.0 * SUM(profit) / SUM(sales), 1) AS margin_pct,
       ROUND(100 * AVG(discount), 1)              AS avg_discount_pct
FROM orders
GROUP BY region
ORDER BY margin_pct;

-- ---------------------------------------------------------------
-- Q3. At which discount level do we start losing money?
-- CASE WHEN puts each order line in a discount bucket.
-- ---------------------------------------------------------------
SELECT CASE WHEN discount = 0    THEN '1. no discount'
            WHEN discount <= 0.2 THEN '2. 1-20%'
            WHEN discount <= 0.4 THEN '3. 21-40%'
            ELSE '4. over 40%'
       END                                        AS discount_bucket,
       COUNT(*)                                   AS nb_order_lines,
       ROUND(SUM(sales), 0)                       AS sales,
       ROUND(SUM(profit), 0)                      AS profit,
       ROUND(100.0 * SUM(profit) / SUM(sales), 1) AS margin_pct
FROM orders
GROUP BY discount_bucket
ORDER BY discount_bucket;

-- ---------------------------------------------------------------
-- Q4. Which sub-categories lose money?
-- ---------------------------------------------------------------
SELECT sub_category,
       ROUND(SUM(sales), 0)                       AS sales,
       ROUND(SUM(profit), 0)                      AS profit,
       ROUND(100.0 * SUM(profit) / SUM(sales), 1) AS margin_pct
FROM orders
GROUP BY sub_category
ORDER BY profit;

-- ---------------------------------------------------------------
-- Q5. Do the customer segments differ?
-- ---------------------------------------------------------------
SELECT segment,
       ROUND(SUM(sales), 0)                       AS sales,
       ROUND(SUM(profit), 0)                      AS profit,
       ROUND(100.0 * SUM(profit) / SUM(sales), 1) AS margin_pct
FROM orders
GROUP BY segment
ORDER BY profit;

-- ---------------------------------------------------------------
-- Q6. HAVING: sub-categories that lose money AND use big discounts.
-- HAVING filters the groups (WHERE filters the rows before grouping).
-- ---------------------------------------------------------------
SELECT sub_category,
       COUNT(*)                                          AS nb_order_lines,
       ROUND(100.0 * SUM(discount > 0.2) / COUNT(*), 1)  AS pct_lines_over_20_discount,
       ROUND(SUM(profit), 0)                             AS profit
FROM orders
GROUP BY sub_category
HAVING SUM(profit) < 0
ORDER BY profit;
