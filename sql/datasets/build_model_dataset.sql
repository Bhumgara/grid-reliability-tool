SELECT
    event_time_utc AS target_time_utc,
    published_at_utc AS target_published_at_utc,
    settlement_date,
    settlement_period,
    derated_margin_mw AS target_drm_mw
FROM elexon_margin_lolpdrm
WHERE forecast_horizon_hours = 1
  AND derated_margin_mw IS NOT NULL
ORDER BY event_time_utc;