INSERT INTO elexon_margin_lolpdrm (
    event_time_utc,
    published_at_utc,
    forecast_horizon_hours,
    settlement_date,
    settlement_period,
    derated_margin_mw,
    loss_of_load_probability,
    source
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)

ON CONFLICT (
    event_time_utc,
    forecast_horizon_hours
)
DO UPDATE SET
    published_at_utc = excluded.published_at_utc,
    settlement_date = excluded.settlement_date,
    settlement_period = excluded.settlement_period,
    derated_margin_mw = excluded.derated_margin_mw,
    loss_of_load_probability = excluded.loss_of_load_probability,
    source = excluded.source;