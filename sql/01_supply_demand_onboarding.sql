-- Supply-Demand Reactivation Engine — Query A
-- Fast query: pre-aggregated tables only (CITY_METRICS_GD, FLEET_SUPPLY_HOURS, ONBOARDING_METRICS_GD)
-- Run weekly; covers the most recently completed week (Mon–Sun).
-- Warehouse: EXPLORATION_XS

ALTER SESSION SET QUERY_TAG = 'reactivation-engine:supply-demand';

WITH
supply AS (
  SELECT
    CITY,
    COUNTRY,
    COUNT_ACTIVE_COURIERS                                                           AS active_couriers,
    COUNT_ACTIVE_COURIERS_LAST_PERIOD                                               AS active_couriers_prev,
    ROUND(
      100.0 * (COUNT_ACTIVE_COURIERS - COUNT_ACTIVE_COURIERS_LAST_PERIOD)
      / NULLIF(COUNT_ACTIVE_COURIERS_LAST_PERIOD, 0), 1
    )                                                                               AS courier_wow_pct,
    ROUND(DISTINCT_ACTIVE_TIME_MINS_NUM / NULLIF(COUNT_ACTIVE_COURIERS, 0) / 60, 1) AS avg_hours_per_courier
  FROM PRODUCTION.COURIER.CITY_METRICS_GD
  WHERE PERIOD = 'week'
    AND REPORT_TIMESTAMP = DATEADD(week, -1, DATE_TRUNC('week', CURRENT_DATE()))
    AND COUNT_ACTIVE_COURIERS > 0
),

demand AS (
  SELECT
    CITY,
    COUNTRY,
    SUM(NUMBER_DELIVERIES)                     AS orders_last_week,
    ROUND(SUM(COALESCE(SUPPLY_HOURS, 0)), 0)   AS total_supply_hours,
    ROUND(AVG(AVG_DELIVERY_TIME), 1)           AS avg_delivery_time_mins
  FROM PRODUCTION.COURIER.FLEET_SUPPLY_HOURS
  WHERE REPORT_TIME_UTC >= DATEADD(week, -1, DATE_TRUNC('week', CURRENT_DATE()))
    AND REPORT_TIME_UTC <  DATE_TRUNC('week', CURRENT_DATE())
  GROUP BY CITY, COUNTRY
),

onboarding AS (
  SELECT
    CITY,
    COUNTRY,
    COUNT_COURIER_APPLICATIONS                                                          AS applications_last_week,
    COUNT_FIRST_DELIVERIES                                                              AS rtd_first_deliveries,
    ROUND(DELIVERY_CONVERSION_28_DAY_NUM / NULLIF(DELIVERY_CONVERSION_28_DAY_DENOM, 0), 3) AS conversion_28d
  FROM PRODUCTION.COURIER.ONBOARDING_METRICS_GD
  WHERE PERIOD = 'week'
    AND REPORT_TIMESTAMP = DATEADD(week, -1, DATE_TRUNC('week', CURRENT_DATE()))
)

SELECT
  s.CITY,
  s.COUNTRY,
  s.active_couriers,
  s.active_couriers_prev                          AS active_couriers_prev_week,
  COALESCE(s.courier_wow_pct, 0)                  AS courier_wow_pct,
  COALESCE(s.avg_hours_per_courier, 0)            AS avg_hours_per_courier,
  COALESCE(d.orders_last_week, 0)                 AS orders_last_week,
  COALESCE(d.avg_delivery_time_mins, 0)           AS avg_delivery_time_mins,
  COALESCE(d.total_supply_hours, 0)               AS total_supply_hours,
  COALESCE(o.applications_last_week, 0)           AS applications_last_week,
  COALESCE(o.rtd_first_deliveries, 0)             AS rtd_first_deliveries,
  COALESCE(o.conversion_28d, 0)                   AS onboarding_conversion_28d
FROM supply s
LEFT JOIN demand     d ON s.CITY = d.CITY AND s.COUNTRY = d.COUNTRY
LEFT JOIN onboarding o ON s.CITY = o.CITY AND s.COUNTRY = o.COUNTRY
ORDER BY s.active_couriers DESC;
