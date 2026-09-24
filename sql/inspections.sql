-- ============================================================
-- ELEXON LOLPDRM DRM INSPECTIONS
-- ============================================================

-- Horizon counts for the selected historical window
SELECT
    forecast_horizon_hours,
    COUNT(*) AS row_count
FROM elexon_margin_lolpdrm
WHERE event_time_utc >= '2026-09-01T00:00:00+00:00'
  AND event_time_utc <= '2026-09-08T00:00:00+00:00'
GROUP BY forecast_horizon_hours
ORDER BY forecast_horizon_hours;


-- Number of unique DRM timestamps
SELECT
    COUNT(DISTINCT event_time_utc) AS unique_margin_times
FROM elexon_margin_lolpdrm
WHERE event_time_utc >= '2026-09-01T00:00:00+00:00'
  AND event_time_utc <= '2026-09-08T00:00:00+00:00';


-- Find settlement periods that don't contain all five DRM horizons
SELECT
    event_time_utc,
    COUNT(*) AS horizon_count,
    GROUP_CONCAT(forecast_horizon_hours) AS horizons
FROM elexon_margin_lolpdrm
WHERE event_time_utc >= '2026-09-01T00:00:00+00:00'
  AND event_time_utc <= '2026-09-08T00:00:00+00:00'
GROUP BY event_time_utc
HAVING COUNT(*) <> 5
ORDER BY event_time_utc;


-- Total number of 1-hour DRM target rows
SELECT
    COUNT(*) AS target_rows
FROM elexon_margin_lolpdrm
WHERE forecast_horizon_hours = 1;


-- Null DRM target values
SELECT
    COUNT(*) AS null_margin_values
FROM elexon_margin_lolpdrm
WHERE forecast_horizon_hours = 1
  AND derated_margin_mw IS NULL;


-- ============================================================
-- ELEXON INDO DEMAND INSPECTIONS
-- ============================================================

-- Total demand rows
SELECT
    COUNT(*) AS demand_rows
FROM elexon_demand_indo;


-- Demand date range
SELECT
    MIN(event_time_utc) AS earliest_demand_time,
    MAX(event_time_utc) AS latest_demand_time
FROM elexon_demand_indo;


-- Null demand values
SELECT
    COUNT(*) AS null_demand_values
FROM elexon_demand_indo
WHERE demand_mw IS NULL;


-- Sample demand records
SELECT
    event_time_utc,
    demand_mw,
    published_at_utc
FROM elexon_demand_indo
ORDER BY event_time_utc
LIMIT 10;


-- ============================================================
-- LOLPDRM ↔ INDO JOIN INSPECTIONS
-- ============================================================

-- Sample joined rows
SELECT
    m.event_time_utc,
    m.derated_margin_mw,
    d.demand_mw,
    d.published_at_utc AS demand_published_at_utc
FROM elexon_margin_lolpdrm AS m
JOIN elexon_demand_indo AS d
    ON m.event_time_utc = d.event_time_utc
WHERE m.forecast_horizon_hours = 1
ORDER BY m.event_time_utc
LIMIT 20;


-- Count successful timestamp matches
SELECT
    COUNT(*) AS joined_rows
FROM elexon_margin_lolpdrm AS m
JOIN elexon_demand_indo AS d
    ON m.event_time_utc = d.event_time_utc
WHERE m.forecast_horizon_hours = 1;


-- Find DRM target rows with no matching demand row
SELECT
    m.event_time_utc
FROM elexon_margin_lolpdrm AS m
LEFT JOIN elexon_demand_indo AS d
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
FROM elexon_margin_lolpdrm AS m
LEFT JOIN elexon_demand_indo AS d
    ON m.event_time_utc = d.event_time_utc
WHERE m.forecast_horizon_hours = 1;

-- ============================================================
-- ELEXON FUELHH GENERATION INSPECTIONS
-- ============================================================

SELECT
    COUNT(*) AS generation_rows,
    COUNT(DISTINCT event_time_utc) AS unique_generation_times
FROM elexon_generation_fuelhh;


-- Which fuel types are actually present?
SELECT
    fuel_type,
    COUNT(*) AS row_count
FROM elexon_generation_fuelhh
GROUP BY fuel_type
ORDER BY fuel_type;


-- Number of fuels reported for each half-hour
SELECT
    event_time_utc,
    COUNT(DISTINCT fuel_type) AS fuel_count
FROM elexon_generation_fuelhh
GROUP BY event_time_utc
ORDER BY event_time_utc
LIMIT 20;


-- Null generation values
SELECT
    COUNT(*) AS null_generation_values
FROM elexon_generation_fuelhh
WHERE generation_mw IS NULL;


-- Sample
SELECT
    event_time_utc,
    fuel_type,
    generation_mw,
    published_at_utc
FROM elexon_generation_fuelhh
ORDER BY event_time_utc, fuel_type
LIMIT 40;

-- ============================================================
-- NESO GENERATION MIX INSPECTIONS
-- ============================================================

SELECT
    COUNT(*) AS generation_mix_rows,
    COUNT(DISTINCT interval_start_utc) AS unique_generation_times
FROM neso_generation_mix;


SELECT
    MIN(interval_start_utc) AS earliest_generation_time,
    MAX(interval_start_utc) AS latest_generation_time
FROM neso_generation_mix;


SELECT
    interval_start_utc,
    wind_pct,
    solar_pct,
    gas_pct,
    nuclear_pct
FROM neso_generation_mix
ORDER BY interval_start_utc
LIMIT 10;


-- Check percentage totals
SELECT
    interval_start_utc,
    ROUND(
        biomass_pct +
        coal_pct +
        imports_pct +
        gas_pct +
        nuclear_pct +
        other_pct +
        hydro_pct +
        solar_pct +
        wind_pct,
        1
    ) AS total_pct
FROM neso_generation_mix
ORDER BY interval_start_utc
LIMIT 20;

-- ============================================================
-- NESO DEMAND INSPECTIONS
-- ============================================================

SELECT *
FROM neso_demand_update
ORDER BY
    settlement_date DESC,
    settlement_period DESC
LIMIT 10;