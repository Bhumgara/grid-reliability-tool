-- ============================================================
-- DRM INSPECTIONS
-- ============================================================

-- Horizon counts for the selected historical window
SELECT
    forecast_horizon_hours,
    COUNT(*) AS row_count
FROM elexon_margin
WHERE event_time_utc >= '2026-09-01T00:00:00+00:00'
  AND event_time_utc <= '2026-09-08T00:00:00+00:00'
GROUP BY forecast_horizon_hours
ORDER BY forecast_horizon_hours;


-- Number of unique DRM timestamps
SELECT
    COUNT(DISTINCT event_time_utc) AS unique_margin_times
FROM elexon_margin
WHERE event_time_utc >= '2026-09-01T00:00:00+00:00'
  AND event_time_utc <= '2026-09-08T00:00:00+00:00';


-- Find settlement periods that don't contain all five DRM horizons
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


-- Total number of 1-hour DRM target rows
SELECT
    COUNT(*) AS target_rows
FROM elexon_margin
WHERE forecast_horizon_hours = 1;


-- Null DRM target values
SELECT
    COUNT(*) AS null_margin_values
FROM elexon_margin
WHERE forecast_horizon_hours = 1
  AND derated_margin_mw IS NULL;


-- ============================================================
-- DEMAND INSPECTIONS
-- ============================================================

-- Total demand rows
SELECT
    COUNT(*) AS demand_rows
FROM elexon_demand;


-- Demand date range
SELECT
    MIN(event_time_utc) AS earliest_demand_time,
    MAX(event_time_utc) AS latest_demand_time
FROM elexon_demand;


-- Null demand values
SELECT
    COUNT(*) AS null_demand_values
FROM elexon_demand
WHERE demand_mw IS NULL;


-- Sample demand records
SELECT
    event_time_utc,
    demand_mw,
    published_at_utc
FROM elexon_demand
ORDER BY event_time_utc
LIMIT 10;


-- ============================================================
-- DRM ↔ DEMAND JOIN INSPECTIONS
-- ============================================================

-- Sample joined rows
SELECT
    m.event_time_utc,
    m.derated_margin_mw,
    d.demand_mw,
    d.published_at_utc AS demand_published_at_utc
FROM elexon_margin AS m
JOIN elexon_demand AS d
    ON m.event_time_utc = d.event_time_utc
WHERE m.forecast_horizon_hours = 1
ORDER BY m.event_time_utc
LIMIT 20;


-- Count successful timestamp matches
SELECT
    COUNT(*) AS joined_rows
FROM elexon_margin AS m
JOIN elexon_demand AS d
    ON m.event_time_utc = d.event_time_utc
WHERE m.forecast_horizon_hours = 1;


-- Find DRM target rows with no matching demand row
SELECT
    m.event_time_utc
FROM elexon_margin AS m
LEFT JOIN elexon_demand AS d
    ON m.event_time_utc = d.event_time_utc
WHERE m.forecast_horizon_hours = 1
  AND d.event_time_utc IS NULL
ORDER BY m.event_time_utc;


-- Join coverage percentage
SELECT
    COUNT(d.event_time_utc) AS matched_targets,
    COUNT(*) AS total_targets,
    ROUND(
        100.0 * COUNT(d.event_time_utc) / COUNT(*),
        3
    ) AS match_percentage
FROM elexon_margin AS m
LEFT JOIN elexon_demand AS d
    ON m.event_time_utc = d.event_time_utc
WHERE m.forecast_horizon_hours = 1;