CREATE TABLE IF NOT EXISTS elexon_margin (
    event_time_utc TEXT NOT NULL,
    published_at_utc TEXT NOT NULL,
    forecast_horizon_hours INTEGER NOT NULL,
    settlement_date TEXT NOT NULL,
    settlement_period INTEGER NOT NULL,
    derated_margin_mw REAL,
    loss_of_load_probability REAL,
    source TEXT NOT NULL,

    PRIMARY KEY (
        event_time_utc,
        forecast_horizon_hours
    )
);