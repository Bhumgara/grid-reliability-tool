-- Horizon counts for the new historical window
SELECT
    forecast_horizon_hours,
    COUNT(*) AS row_count
FROM elexon_margin
WHERE event_time_utc >= '2026-09-01T00:00:00+00:00'
  AND event_time_utc <= '2026-09-08T00:00:00+00:00'
GROUP BY forecast_horizon_hours
ORDER BY forecast_horizon_hours;


-- Number of unique target timestamps
SELECT
    COUNT(DISTINCT event_time_utc) AS unique_times
FROM elexon_margin
WHERE event_time_utc >= '2026-09-01T00:00:00+00:00'
  AND event_time_utc <= '2026-09-08T00:00:00+00:00';


-- Find settlement periods that don't contain all five horizons
SELECT
    event_time_utc,
    COUNT(*) AS horizon_count,
    GROUP_CONCAT(forecast_horizon_hours) AS horizons
FROM elexon_margin
WHERE event_time_utc >= '2026-09-01T00:00:00+00:00'
  AND event_time_utc <= '2026-09-08T00:00:00+00:00'
GROUP BY event_time_utc
HAVING COUNT(*) <> 5
ORDER BY event_time_utc;