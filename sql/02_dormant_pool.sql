-- Supply-Demand Reactivation Engine — Query B
-- Dormant courier pool by city.
-- Definition: active (≥1 delivery) in weeks 5–24 ago, ZERO deliveries in last 4 weeks.
-- This query scans ~6 months of courier-week rows — run separately on EXPLORATION_XS.

ALTER SESSION SET QUERY_TAG = 'reactivation-engine:dormant-pool';

SELECT
  d.FLEET_CITY    AS city,
  d.FLEET_COUNTRY AS country,
  COUNT(DISTINCT CASE WHEN r.COURIER_ID IS NULL THEN d.COURIER_ID END) AS dormant_couriers
FROM (
  -- Couriers active at some point in the 5–24 week window
  SELECT DISTINCT COURIER_ID, FLEET_CITY, FLEET_COUNTRY
  FROM PRODUCTION.COURIER.COURIER_PARTNER_METRICS
  WHERE PERIOD = 'week'
    AND REPORT_TIMESTAMP >= DATEADD(week, -24, DATE_TRUNC('week', CURRENT_DATE()))
    AND REPORT_TIMESTAMP <  DATEADD(week,  -4, DATE_TRUNC('week', CURRENT_DATE()))
    AND COUNT_DELIVERIES_COMPLETED > 0
) d
LEFT JOIN (
  -- Couriers who delivered at least once in the last 4 weeks (not dormant)
  SELECT DISTINCT COURIER_ID, FLEET_CITY, FLEET_COUNTRY
  FROM PRODUCTION.COURIER.COURIER_PARTNER_METRICS
  WHERE PERIOD = 'week'
    AND REPORT_TIMESTAMP >= DATEADD(week, -4, DATE_TRUNC('week', CURRENT_DATE()))
    AND COUNT_DELIVERIES_COMPLETED > 0
) r USING (COURIER_ID, FLEET_CITY, FLEET_COUNTRY)
GROUP BY d.FLEET_CITY, d.FLEET_COUNTRY
ORDER BY dormant_couriers DESC;
